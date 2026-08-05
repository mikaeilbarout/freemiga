"""
One-time schema migration — adds Plan.is_featured to an existing `plans`
table.

This project has no migration framework (see scripts/init_db.py): schema
setup is just Base.metadata.create_all(), which only creates tables that
don't exist yet — it never alters a table that's already there. Adding a
new column to the Plan model (app/models.py) needs this kind of one-off
script to actually reach a live database that already has a `plans` table
with real rows in it.

Idempotent: uses ADD COLUMN IF NOT EXISTS (Postgres 9.6+, what production
runs — see docker-compose.yml), so safe to re-run.

Run once, after pulling the code that adds Plan.is_featured:
    python -m scripts.add_plan_is_featured_column
or, in the Docker deployment:
    docker compose exec app python -m scripts.add_plan_is_featured_column
"""
from sqlalchemy import text

from app.database import engine


def migrate() -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text(
                "ALTER TABLE plans ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT FALSE"
            ))
        else:
            # SQLite (local dev) has no ADD COLUMN IF NOT EXISTS — check first.
            existing = {row[1] for row in conn.execute(text("PRAGMA table_info(plans)"))}
            if "is_featured" not in existing:
                conn.execute(text(
                    "ALTER TABLE plans ADD COLUMN is_featured BOOLEAN NOT NULL DEFAULT 0"
                ))
    print("Done — plans.is_featured is ready.")


if __name__ == "__main__":
    migrate()
