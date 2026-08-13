"""
One-time schema migration — adds the "stars" PaymentMethod enum value and
Order.telegram_charge_id to an existing database, for Telegram Stars
payments (see app/services/telegram_bot.py and app/config.py's
TELEGRAM_STARS_PER_USD).

This project has no migration framework (see scripts/init_db.py):
Base.metadata.create_all() only creates tables that don't exist yet — it
never alters a table (or a native Postgres enum type) that's already
there. Same pattern as scripts/add_plan_is_featured_column.py.

Idempotent: uses IF NOT EXISTS throughout, so safe to re-run.

Run once, after pulling the code that adds Stars payment support:
    docker compose exec app python -m scripts.add_stars_payment_support
"""
from sqlalchemy import text

from app.database import engine


def migrate() -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            # ALTER TYPE ... ADD VALUE cannot run inside a transaction on
            # Postgres < 12; production runs Postgres 16 (docker-compose.yml),
            # where it's fine as a normal statement.
            conn.execute(text("ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'stars'"))
            conn.execute(text(
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS telegram_charge_id VARCHAR"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_telegram_charge_id "
                "ON orders (telegram_charge_id)"
            ))
        else:
            # SQLite (local dev): payment_method is a plain VARCHAR, not a
            # native enum type, so "stars" needs no type change — just the
            # new column.
            existing = {row[1] for row in conn.execute(text("PRAGMA table_info(orders)"))}
            if "telegram_charge_id" not in existing:
                conn.execute(text("ALTER TABLE orders ADD COLUMN telegram_charge_id VARCHAR"))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_telegram_charge_id "
                "ON orders (telegram_charge_id)"
            ))
    print("Done — orders.telegram_charge_id and PaymentMethod.stars are ready.")


if __name__ == "__main__":
    migrate()
