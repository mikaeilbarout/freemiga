"""
Ad-hoc diagnostic — prints, for every provisioned order, what Marzban
itself reports (status/expire/data_limit/used_traffic) side by side with
the customer's own username, so a "dashboard says Active but it shouldn't
be" report can be checked against ground truth directly.

Temporary — not part of the app; safe to delete after use.

Run:
    docker compose exec app python -m scripts.debug_order_status
"""
import asyncio
from datetime import datetime

from app.database import SessionLocal
from app.models import Order, OrderStatus
from app.services import marzban


async def main() -> None:
    db = SessionLocal()
    try:
        orders = db.query(Order).filter(Order.status == OrderStatus.provisioned).all()
        for o in orders:
            username = o.marzban_username
            try:
                data = await marzban.get_vpn_user(username)
            except Exception as e:
                print(f"{o.customer.username:20} {username:35} ERROR: {e}")
                continue
            expire_ts = data.get("expire")
            expire_str = datetime.utcfromtimestamp(expire_ts).isoformat() if expire_ts else "none"
            used = data.get("used_traffic", 0) / (1024**3)
            limit = data.get("data_limit", 0) / (1024**3) if data.get("data_limit") else 0
            print(
                f"{o.customer.username:20} {username:35} "
                f"marzban_status={data.get('status'):10} "
                f"expire={expire_str:22} (now={datetime.utcnow().isoformat()}) "
                f"used={used:.3f}GB / limit={limit:.3f}GB"
            )
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
