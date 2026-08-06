"""
One-off — sends a single real Conversions API event carrying Reddit's
"Test Events" test_id, so you can confirm in Reddit Ads Manager's own
test panel that REDDIT_PIXEL_ID / REDDIT_CAPI_ACCESS_TOKEN and the
endpoint/body shape in services/reddit_capi.py are actually correct —
before any real customer traffic goes through them.

Get the test_id from Reddit Ads Manager: Events Manager -> your pixel ->
Conversions API -> Test Events. Pass it as the first CLI argument.

Per Reddit's own instructions, test_id must never be sent in production
— that's precisely why this lives here rather than as something any
real call site (routers/tracking.py) ever touches.

Safe to delete after use.

Run:
    docker compose exec app python -m scripts.test_reddit_capi <test_id>
"""
import asyncio
import sys

from app.services import reddit_capi


async def main() -> None:
    if not reddit_capi.is_configured():
        print("REDDIT_PIXEL_ID / REDDIT_CAPI_ACCESS_TOKEN aren't set — nothing to test.")
        return

    test_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not test_id:
        print("Usage: python -m scripts.test_reddit_capi <test_id>")
        return

    resp = await reddit_capi.send_event(
        "SignUp",
        email="capi-test@freemiga.com",
        test_id=test_id,
    )
    if resp is None:
        print("FAILED — the request never completed (network error / exception). Check the app logs.")
        return

    print(f"HTTP {resp.status_code}")
    print(resp.text)
    if resp.status_code < 300:
        print("\nSent OK — now check Reddit Ads Manager's Test Events panel for this test_id.")
    else:
        print("\nReddit rejected the request — the error above says why.")


if __name__ == "__main__":
    asyncio.run(main())
