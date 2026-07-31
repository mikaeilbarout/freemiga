from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.auth import require_admin
from app.database import get_db
from app.models import BlogCategory, BlogPost, BlogPostStatus, BlogTag
from app.schemas import BlogCategoryOut, BlogPostAdminOut, BlogTagOut
from app.services.blog import reading_time_minutes, slugify
from app.services.uploads import read_validated_image, save_image

router = APIRouter(
    prefix="/api/admin/blog", tags=["admin-blog"], dependencies=[Depends(require_admin)]
)


def _unique_slug(db: Session, model, base_slug: str, exclude_id: str | None = None) -> str:
    slug = base_slug
    n = 2
    while True:
        query = db.query(model).filter(model.slug == slug)
        if exclude_id:
            query = query.filter(model.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{n}"
        n += 1


# ---- Categories ----

@router.get("/categories", response_model=list[BlogCategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(BlogCategory).order_by(BlogCategory.name_en).all()


@router.post("/categories", response_model=BlogCategoryOut)
def create_category(name_en: str = Form(...), name_fa: str = Form(...), db: Session = Depends(get_db)):
    slug = _unique_slug(db, BlogCategory, slugify(name_en))
    category = BlogCategory(slug=slug, name_en=name_en, name_fa=name_fa)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}")
def delete_category(category_id: str, db: Session = Depends(get_db)):
    category = db.query(BlogCategory).filter(BlogCategory.id == category_id).first()
    if not category:
        raise HTTPException(404, "Category not found")
    db.query(BlogPost).filter(BlogPost.category_id == category_id).update({"category_id": None})
    db.delete(category)
    db.commit()
    return {"ok": True}


# ---- Tags ----

@router.get("/tags", response_model=list[BlogTagOut])
def list_tags(db: Session = Depends(get_db)):
    return db.query(BlogTag).order_by(BlogTag.name_en).all()


@router.post("/tags", response_model=BlogTagOut)
def create_tag(name_en: str = Form(...), name_fa: str = Form(...), db: Session = Depends(get_db)):
    slug = _unique_slug(db, BlogTag, slugify(name_en))
    tag = BlogTag(slug=slug, name_en=name_en, name_fa=name_fa)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: str, db: Session = Depends(get_db)):
    tag = db.query(BlogTag).filter(BlogTag.id == tag_id).first()
    if not tag:
        raise HTTPException(404, "Tag not found")
    db.delete(tag)
    db.commit()
    return {"ok": True}


# ---- Posts ----

@router.get("/posts")
def list_posts(
    db: Session = Depends(get_db),
    q: str | None = None,
    page: int = 1,
    page_size: int = 10,
):
    query = db.query(BlogPost).options(
        selectinload(BlogPost.category), selectinload(BlogPost.tags)
    )
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(BlogPost.title_en.ilike(like))
    total = query.count()
    posts = (
        query.order_by(BlogPost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [BlogPostAdminOut.model_validate(p) for p in posts]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/posts/{post_id}", response_model=BlogPostAdminOut)
def get_post(post_id: str, db: Session = Depends(get_db)):
    post = (
        db.query(BlogPost)
        .options(selectinload(BlogPost.category), selectinload(BlogPost.tags))
        .filter(BlogPost.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@router.post("/posts", response_model=BlogPostAdminOut)
async def create_post(
    slug: str | None = Form(None),
    category_id: str | None = Form(None),
    title_en: str = Form(...),
    title_fa: str = Form(...),
    excerpt_en: str = Form(...),
    excerpt_fa: str = Form(...),
    content_en: str = Form(...),
    content_fa: str = Form(...),
    author: str | None = Form(None),
    status: str = Form("draft"),
    tag_ids: str = Form(""),  # comma-separated
    featured_image: UploadFile | None = File(None),
    og_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    try:
        post_status = BlogPostStatus(status)
    except ValueError:
        raise HTTPException(400, "Invalid status")

    base_slug = slugify(slug or title_en)
    post = BlogPost(
        slug=_unique_slug(db, BlogPost, base_slug),
        category_id=category_id or None,
        title_en=title_en,
        title_fa=title_fa,
        excerpt_en=excerpt_en,
        excerpt_fa=excerpt_fa,
        content_en=content_en,
        content_fa=content_fa,
        author=author or None,
        status=post_status,
        published_at=datetime.utcnow() if post_status == BlogPostStatus.published else None,
        reading_time_min=reading_time_minutes(content_en),
    )
    if featured_image is not None and featured_image.filename:
        data, ext = await read_validated_image(featured_image)
        post.featured_image = save_image(data, ext, "blog")
    if og_image is not None and og_image.filename:
        data, ext = await read_validated_image(og_image)
        post.og_image = save_image(data, ext, "blog")

    if tag_ids.strip():
        ids = [t.strip() for t in tag_ids.split(",") if t.strip()]
        post.tags = db.query(BlogTag).filter(BlogTag.id.in_(ids)).all()

    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.put("/posts/{post_id}", response_model=BlogPostAdminOut)
async def update_post(
    post_id: str,
    slug: str | None = Form(None),
    category_id: str | None = Form(None),
    title_en: str | None = Form(None),
    title_fa: str | None = Form(None),
    excerpt_en: str | None = Form(None),
    excerpt_fa: str | None = Form(None),
    content_en: str | None = Form(None),
    content_fa: str | None = Form(None),
    author: str | None = Form(None),
    status: str | None = Form(None),
    tag_ids: str | None = Form(None),  # comma-separated
    featured_image: UploadFile | None = File(None),
    og_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")

    if slug is not None and slug.strip() and slug.strip() != post.slug:
        post.slug = _unique_slug(db, BlogPost, slugify(slug), exclude_id=post_id)
    if category_id is not None:
        post.category_id = category_id or None
    if title_en is not None:
        post.title_en = title_en
    if title_fa is not None:
        post.title_fa = title_fa
    if excerpt_en is not None:
        post.excerpt_en = excerpt_en
    if excerpt_fa is not None:
        post.excerpt_fa = excerpt_fa
    if content_en is not None:
        post.content_en = content_en
        post.reading_time_min = reading_time_minutes(content_en)
    if content_fa is not None:
        post.content_fa = content_fa
    if author is not None:
        post.author = author or None
    if status is not None:
        try:
            new_status = BlogPostStatus(status)
        except ValueError:
            raise HTTPException(400, "Invalid status")
        if new_status == BlogPostStatus.published and post.status != BlogPostStatus.published:
            post.published_at = datetime.utcnow()
        post.status = new_status
    if tag_ids is not None:
        ids = [t.strip() for t in tag_ids.split(",") if t.strip()]
        post.tags = db.query(BlogTag).filter(BlogTag.id.in_(ids)).all() if ids else []
    if featured_image is not None and featured_image.filename:
        data, ext = await read_validated_image(featured_image)
        post.featured_image = save_image(data, ext, "blog")
    if og_image is not None and og_image.filename:
        data, ext = await read_validated_image(og_image)
        post.og_image = save_image(data, ext, "blog")

    db.commit()
    db.refresh(post)
    return post


@router.delete("/posts/{post_id}")
def delete_post(post_id: str, db: Session = Depends(get_db)):
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    db.delete(post)
    db.commit()
    return {"ok": True}
