"""
One-time schema migration — adds the "removed" OrderStatus enum value, used
when a customer deletes one of their own plans from the dashboard (see
routers/orders.py's remove_order).

This project has no migration framework (see scripts/init_db.py):
Base.metadata.create_all() never alters a native Postgres enum type that's
already there. Same pattern as scripts/add_stars_payment_support.py.

Idempotent: uses IF NOT EXISTS, so safe to re-run.

Run once, after pulling the code that adds plan deletion:
    docker compose exec app python -m scripts.add_order_removed_status
"""
from sqlalchemy import text

from app.database import engine


def migrate() -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'removed'"))
        # SQLite (local dev): status is a plain VARCHAR, not a native enum
        # type, so "removed" needs no schema change.
    print("Done — OrderStatus.removed is ready.")


if __name__ == "__main__":
    migrate()
