"""
One-time content update — rewrites the Persian title/excerpt/content of the
four VPN & Proxy Guides posts (seeded by scripts/seed_vpn_proxy_blog.py) from
their original casual/colloquial Persian into formal written Persian,
with more detailed, SEO-oriented sections. English fields are
left untouched.

scripts/seed_vpn_proxy_blog.py's seed() is idempotent by slug and skips a
post that already exists, so it can't push a content edit to a post already
in the database — this script is the one-off migration that does that,
matching the pattern used for other post-deploy content fixes in this repo.

Safe to re-run: it always overwrites the Persian fields for these four
slugs with the current POSTS content in seed_vpn_proxy_blog.py, and does
nothing for any slug that isn't found (e.g. on a fresh DB where seed()
hasn't run yet).

Run once, after scripts/seed_vpn_proxy_blog.py has already created the posts:
    python -m scripts.update_blog_fa_formal
or, in the Docker deployment:
    docker compose exec app python -m scripts.update_blog_fa_formal
"""
from app.database import SessionLocal
from app.models import BlogPost
from scripts.seed_vpn_proxy_blog import POSTS


def update() -> None:
    db = SessionLocal()
    try:
        updated = 0
        for p in POSTS:
            post = db.query(BlogPost).filter(BlogPost.slug == p["slug"]).first()
            if not post:
                continue
            post.title_fa = p["title_fa"]
            post.excerpt_fa = p["excerpt_fa"]
            post.content_fa = p["content_fa"].strip()
            updated += 1
        db.commit()
        print(f"Done — {updated} post(s) updated to formal Persian, {len(POSTS) - updated} not found.")
    finally:
        db.close()


if __name__ == "__main__":
    update()
