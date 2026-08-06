"""
One-time backfill — re-pushes each provisioned order's device-limit
headroom to marzban-guard using the CURRENT formula in app/background.py
(plan.max_devices + 5).

Why this is needed: the device limit is only pushed to marzban-guard at
provisioning time (see background.py's _provision). Changing the headroom
constant only affects orders provisioned after the change — every order
provisioned earlier is still sitting in marzban-guard with whatever
headroom was in effect back then. This script brings existing orders up
to the current formula without needing a new purchase/renewal.

Safe to re-run — it just re-pushes the same computed value each time.

Run:
    docker compose exec app python -m scripts.backfill_guard_device_limits
"""
import asyncio

from app.database import SessionLocal
from app.models import Order, OrderStatus
from app.services import marzban_guard

DEVICE_LIMIT_HEADROOM = 5


async def main() -> None:
    if not marzban_guard.is_configured():
        print("marzban-guard is not configured (MARZBAN_GUARD_BASE_URL unset) — nothing to do.")
        return

    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.status == OrderStatus.provisioned)
            .all()
        )
        print(f"{len(orders)} provisioned order(s) found.")
        updated = 0
        for o in orders:
            plan = o.plan
            if plan.max_devices is None:
                continue
            new_limit = plan.max_devices + DEVICE_LIMIT_HEADROOM
            await marzban_guard.push_device_limit(o.marzban_username, new_limit)
            print(f"  {o.customer.username:20} {o.marzban_username:35} -> device_limit={new_limit}")
            updated += 1
        print(f"Done — pushed the new device limit for {updated} order(s).")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
