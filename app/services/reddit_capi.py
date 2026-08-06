"""
Reddit Conversions API (CAPI) — server-side reporting of SignUp/Purchase
events to Reddit Ads, alongside the client-side Reddit Pixel (see
_fonts.html and the Pixel calls in signup.html/pay.html). CAPI exists
specifically because the Pixel alone misses events blocked by ad blockers
or browser tracking prevention (Safari ITP, etc.) — the server-side call
doesn't depend on the visitor's browser cooperating. Both are fired for
the same event on purpose; Reddit dedupes them.

Best-effort only, same convention as marzban_guard.py: a failure here
must never affect signup/checkout, since by the time this runs the real
side effect (account created, order provisioned) has already happened.

Endpoint/body shape below is taken directly from the curl example on
this account's own Conversions API setup page in Reddit Ads Manager
(Events Manager -> pixel -> Conversions API -> Set up events) — not
third-party docs, which disagreed with each other and with this on
several fields (endpoint path, body wrapper, event_at format, field
names) when this was first written from those instead.
"""
import hashlib
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger("reddit_capi")

REDDIT_CAPI_URL_TEMPLATE = "https://ads-api.reddit.com/api/v3/pixels/{pixel_id}/conversion_events"


def is_configured() -> bool:
    return bool(settings.REDDIT_PIXEL_ID and settings.REDDIT_CAPI_ACCESS_TOKEN)


def _hash_email(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


async def send_event(
    tracking_type: str,
    *,
    email: str | None = None,
    click_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    conversion_id: str | None = None,
    value: float | None = None,
    currency: str = "USD",
    test_id: str | None = None,
) -> httpx.Response | None:
    """test_id is ONLY for one-off verification via Reddit Ads Manager's
    "Test Events" panel (see scripts/test_reddit_capi.py) — Reddit's own
    instructions there say to remove it before production, so no real
    call site (tracking.py) ever passes it. Returns the HTTP response so
    that one-off script can show the caller what actually happened;
    regular callers ignore the return value, same as before.

    Reddit's UI says to add test_id "to the event", but the real API
    rejects it there ("unknown field") — confirmed live, it actually
    belongs inside "data", as a sibling of "events".
    """
    if not is_configured():
        return None
    # Reddit requires at least one attribution signal per event — with
    # neither of these there's nothing to match the event to, so the call
    # would just be rejected.
    if not click_id and not email:
        return None

    user: dict = {}
    if email:
        user["email"] = _hash_email(email)
    if ip_address:
        user["ip_address"] = ip_address
    if user_agent:
        user["user_agent"] = user_agent

    event: dict = {
        "event_at": int(time.time() * 1000),  # Unix epoch milliseconds, per Reddit's own example
        "action_source": "WEBSITE",
        "type": {"tracking_type": tracking_type},
        "user": user,
    }
    if click_id:
        event["click_id"] = click_id  # sibling of "user", not nested inside it
    metadata: dict = {}
    if value is not None:
        metadata["currency"] = currency
        metadata["value"] = value
        metadata["item_count"] = 1
    if conversion_id:
        metadata["conversion_id"] = conversion_id
    if metadata:
        event["metadata"] = metadata

    data: dict = {"events": [event]}
    if test_id:
        data["test_id"] = test_id  # sibling of "events" inside "data" — confirmed against the live API

    url = REDDIT_CAPI_URL_TEMPLATE.format(pixel_id=settings.REDDIT_PIXEL_ID)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={"data": data},
                headers={"Authorization": f"Bearer {settings.REDDIT_CAPI_ACCESS_TOKEN}"},
            )
            if resp.status_code >= 300:
                logger.warning(
                    "Reddit CAPI %s event rejected: %s %s", tracking_type, resp.status_code, resp.text,
                )
            return resp
    except Exception:
        logger.exception("Error sending Reddit CAPI %s event", tracking_type)
        return None
