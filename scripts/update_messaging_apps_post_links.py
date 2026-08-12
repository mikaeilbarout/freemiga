"""
One-time content update — moves the "access-blocked-messaging-apps-iran"
post (seeded by scripts/seed_blog_posts.py) into the shared "VPN & Proxy
Guides" category, attaches the "VPN"/"Iran" tags, and refreshes its content
with inline links to the other posts.

seed_blog_posts.py's seed_blog_posts() is idempotent by slug and skips a
post that already exists, so it can't push this fix to a post already in
the database — this is the one-off migration that does that, matching the
pattern update_blog_fa_formal.py uses for the same kind of post-deploy fix.

Safe to re-run: always overwrites category_id, tags, and content for this
one slug with the current data in seed_blog_posts.py, and does nothing if
the slug isn't found (e.g. on a fresh DB where seed_blog_posts hasn't run
yet — there it's seeded correctly already, this script is a no-op).

Run once, after scripts/seed_blog_posts.py has already created the post:
    docker compose exec app python -m scripts.update_messaging_apps_post_links
"""
from app.database import SessionLocal
from app.models import BlogPost
from scripts.seed_blog_posts import CATEGORY, POSTS, TAGS, _get_or_create_category, _get_or_create_tags


def update() -> None:
    db = SessionLocal()
    try:
        post = db.query(BlogPost).filter(BlogPost.slug == POSTS[0]["slug"]).first()
        if not post:
            print("Post not found — nothing to update (seed_blog_posts.py will seed it correctly).")
            return

        category = _get_or_create_category(db, CATEGORY["name_en"], CATEGORY["name_fa"])
        tags = _get_or_create_tags(db, TAGS)

        data = POSTS[0]
        post.category_id = category.id
        post.tags = tags
        post.content_en = data["content_en"]
        post.content_fa = data["content_fa"]

        db.commit()
        print("Updated — post moved to shared category, tags attached, links added.")
    finally:
        db.close()


if __name__ == "__main__":
    update()
