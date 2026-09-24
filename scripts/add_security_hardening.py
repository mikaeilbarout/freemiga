"""
One-time schema migration for the security fixes:

- customers.auth_version — bumped on password change/reset to sign out
  every other session (see app/auth.py's start_session/session_customer)
- password_reset_codes.attempts — wrong guesses per reset code (see
  routers/auth.py's reset_password)
- telegram_link_tokens table — one-time "Connect Telegram" links (see
  routers/auth.py's telegram_link)

This project has no migration framework (see scripts/init_db.py):
Base.metadata.create_all() creates missing tables but never adds columns to
an existing one. Same pattern as scripts/add_stars_payment_support.py.

Idempotent: safe to re-run.

Run once, after pulling the code that adds these:
    docker compose exec app python -m scripts.add_security_hardening
"""
from sqlalchemy import text

from app.database import Base, engine
import app.models  # noqa: F401 — registers every table on Base.metadata

COLUMNS = [
    ("customers", "auth_version", "INTEGER NOT NULL DEFAULT 0"),
    ("password_reset_codes", "attempts", "INTEGER NOT NULL DEFAULT 0"),
]


def migrate() -> None:
    with engine.begin() as conn:
        for table, column, ddl in COLUMNS:
            if engine.dialect.name == "postgresql":
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"))
            else:
                # SQLite (local dev) has no ADD COLUMN IF NOT EXISTS.
                existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    # New tables only (telegram_link_tokens) — never touches existing ones.
    Base.metadata.create_all(bind=engine)
    print("Done — auth_version, reset-code attempts and telegram_link_tokens are ready.")


if __name__ == "__main__":
    migrate()
