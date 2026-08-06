"""
One-off — sends a real Conversions API event carrying Reddit's "Test
Events" test_id, so you can confirm in Reddit Ads Manager's own test
panel that REDDIT_PIXEL_ID / REDDIT_CAPI_ACCESS_TOKEN and the endpoint/
body shape in services/reddit_capi.py are actually correct — before any
real customer traffic goes through them.

Get the test_id from Reddit Ads Manager: Events Manager -> your pixel ->
Conversions API -> Test Events. Pass it as the first CLI argument.

Reddit's UI says to add test_id "to the event", but their API rejects
it there ("unknown field" — confirmed against the real endpoint), so
this tries the two other places a request-level test marker plausibly
belongs and reports which one Reddit actually accepts. Whichever one
works should get folded into services/reddit_capi.py's real request
building — this script is deliberately NOT just calling send_event(),
since send_event's job is the real production shape, not a grab-bag of
placements no real caller should ever need.

Per Reddit's own instructions, test_id must never be sent in production
— that's precisely why this lives here rather than as a permanent
option on send_event().

Safe to delete after use.

Run:
    docker compose exec app python -m scripts.test_reddit_capi <test_id>
"""
import asyncio
import sys
import time

import httpx

from app.config import settings
from app.services import reddit_capi


def _base_event() -> dict:
    return {
        "event_at": int(time.time() * 1000),
        "action_source": "WEBSITE",
        "type": {"tracking_type": "SignUp"},
        "user": {"email": reddit_capi._hash_email("capi-test@freemiga.com")},
    }


async def _try(label: str, body: dict) -> bool:
    url = reddit_capi.REDDIT_CAPI_URL_TEMPLATE.format(pixel_id=settings.REDDIT_PIXEL_ID)
    print(f"\n--- Trying: {label} ---")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url, json=body, headers={"Authorization": f"Bearer {settings.REDDIT_CAPI_ACCESS_TOKEN}"},
        )
    print(f"HTTP {resp.status_code}")
    print(resp.text)
    return resp.status_code < 300


async def main() -> None:
    if not reddit_capi.is_configured():
        print("REDDIT_PIXEL_ID / REDDIT_CAPI_ACCESS_TOKEN aren't set — nothing to test.")
        return

    test_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not test_id:
        print("Usage: python -m scripts.test_reddit_capi <test_id>")
        return

    event = _base_event()

    attempts = [
        ("test_id inside data, alongside events", {"data": {"test_id": test_id, "events": [event]}}),
        ("test_id at request root, alongside data", {"test_id": test_id, "data": {"events": [event]}}),
    ]

    for label, body in attempts:
        try:
            if await _try(label, body):
                print(f"\n>>> SUCCESS with: {label}")
                print(">>> Check Reddit Ads Manager's Test Events panel for this test_id now.")
                print(">>> Tell Claude which one worked so it can be made the permanent shape.")
                return
        except Exception as e:
            print(f"Request failed: {e}")

    print("\nNone of the tried placements worked — paste the last error above.")


if __name__ == "__main__":
    asyncio.run(main())
