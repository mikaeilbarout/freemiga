"""
One-time backfill — grants every EXISTING Marzban user access to all VLESS
inbounds currently in settings.MARZBAN_INBOUND_TAGS (e.g. both the
Cloudflare-fronted WS_TLS inbound and the REALITY one).

Why this was needed: app/services/marzban.py's create_vpn_user() used to
hardcode a single inbound tag (MARZBAN_INBOUND_TAG), so every user created
before that was fixed to use MARZBAN_INBOUND_TAGS only ever got assigned to
one inbound — their subscription showed 2 configs instead of 4. This script
brings existing users up to date without needing a renewal.

Safe to re-run — users that already have every tag are skipped.

Run on the server:
    docker compose exec app python -m scripts.backfill_marzban_inbounds
"""
import asyncio

import httpx

from app.config import settings
from app.services.marzban import _get_token

_PAGE_SIZE = 200


async def main() -> None:
    wanted = set(settings.MARZBAN_INBOUND_TAGS)
    if not wanted:
        print("MARZBAN_INBOUND_TAGS is empty — nothing to do.")
        return
    print(f"Target inbound tags: {sorted(wanted)}")

    token = await _get_token()
    headers = {"Authorization": f"Bearer {token}"}
    updated = 0
    skipped = 0
    offset = 0

    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            resp = await client.get(
                f"{settings.MARZBAN_BASE_URL}/api/users",
                headers=headers,
                params={"offset": offset, "limit": _PAGE_SIZE},
            )
            resp.raise_for_status()
            page = resp.json().get("users", [])
            if not page:
                break

            for user in page:
                username = user["username"]
                current = set(user.get("inbounds", {}).get("vless", []))
                if wanted <= current:
                    skipped += 1
                    continue

                merged = sorted(current | wanted)
                put_resp = await client.put(
                    f"{settings.MARZBAN_BASE_URL}/api/user/{username}",
                    headers=headers,
                    json={"inbounds": {"vless": merged}},
                )
                if put_resp.status_code >= 400:
                    print(f"  FAILED {username}: {put_resp.status_code} {put_resp.text}")
                    continue
                print(f"  {username:35} {sorted(current)} -> {merged}")
                updated += 1

            offset += _PAGE_SIZE

    print(f"Done — updated {updated} user(s), {skipped} already had every tag.")


if __name__ == "__main__":
    asyncio.run(main())
