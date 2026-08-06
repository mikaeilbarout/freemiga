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

NOTE: Reddit's own docs (business.reddithelp.com/.../Conversions-API)
weren't fetchable while writing this (blocked automated requests), and
third-party integration docs disagree slightly on the exact API version
segment in the endpoint path. Before relying on this in production, open
the Conversions API setup page in Reddit Ads Manager itself — it shows
your account's exact endpoint/curl example — and update REDDIT_CAPI_BASE
below if it differs from what's here.
"""
import hashlib
import logging
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger("reddit_capi")

REDDIT_CAPI_BASE = "https://ads-api.reddit.com/api/v2.3/conversions/events"


def is_configured() -> bool:
    return bool(settings.REDDIT_CAPI_ACCOUNT_ID and settings.REDDIT_CAPI_ACCESS_TOKEN)


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
) -> None:
    if not is_configured():
        return
    # Reddit requires at least one attribution signal per event — with
    # neither of these there's nothing to match the event to, so the call
    # would just be rejected.
    if not click_id and not email:
        return

    user: dict = {}
    if email:
        user["email"] = _hash_email(email)
    if click_id:
        user["click_id"] = click_id
    if ip_address:
        user["ip_address"] = ip_address
    if user_agent:
        user["user_agent"] = user_agent

    event: dict = {
        "event_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": {"tracking_type": tracking_type},
        "user": user,
    }
    metadata: dict = {}
    if value is not None:
        metadata["currency"] = currency
        metadata["value_decimal"] = value
        metadata["item_count"] = 1
    if conversion_id:
        metadata["conversion_id"] = conversion_id
    if metadata:
        event["event_metadata"] = metadata

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{REDDIT_CAPI_BASE}/{settings.REDDIT_CAPI_ACCOUNT_ID}",
                json={"test_mode": False, "events": [event]},
                headers={"Authorization": f"Bearer {settings.REDDIT_CAPI_ACCESS_TOKEN}"},
            )
            if resp.status_code >= 300:
                logger.warning(
                    "Reddit CAPI %s event rejected: %s %s", tracking_type, resp.status_code, resp.text,
                )
    except Exception:
        logger.exception("Error sending Reddit CAPI %s event", tracking_type)
