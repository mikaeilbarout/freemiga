"""
One-time schema setup — creates tables and seeds the default plans.

Run this ONCE before starting the app server, as its own process (see the
Dockerfile). It must NOT run inside the app's FastAPI startup handler: under
gunicorn with multiple workers, every worker fires that handler concurrently,
and Postgres has no "CREATE TYPE IF NOT EXISTS" for the Enum columns here —
two workers racing to create the same enum type crashes with a
UniqueViolation on pg_type. Running schema setup as a single process before
gunicorn spawns any workers avoids the race entirely.
"""
from app.database import Base, SessionLocal, engine
from app.models import Plan


def seed_plans() -> None:
    db = SessionLocal()
    try:
        if db.query(Plan).count() == 0:
            db.add_all([
                Plan(name="Free Trial", price_usdt=0, data_limit_gb=1, duration_days=1),
                Plan(name="Basic", price_usdt=5, data_limit_gb=10, duration_days=30),
                Plan(name="Standard", price_usdt=9, data_limit_gb=30, duration_days=30),
                Plan(name="Unlimited", price_usdt=15, data_limit_gb=100, duration_days=30),
            ])
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_plans()
    print("Database schema ready.")
