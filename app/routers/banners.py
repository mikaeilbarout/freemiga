import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import Banner
from app.schemas import BannerOut

UPLOAD_DIR = "app/static/uploads/banners"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/api/banners", tags=["banners"])
admin_router = APIRouter(
    prefix="/api/admin/banners", tags=["admin-banners"], dependencies=[Depends(require_admin)]
)


def _sniff_image_ext(data: bytes) -> str | None:
    # Extension is derived from sniffed magic bytes, never from the
    # client-supplied filename or Content-Type header (both attacker-
    # controlled) — otherwise e.g. an SVG uploaded with a spoofed
    # "image/png" Content-Type would be accepted and served by StaticFiles
    # as image/svg+xml, a stored-XSS vector.
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return None


def _save_image(data: bytes, ext: str) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(data)
    return f"/static/uploads/banners/{filename}"


async def _read_validated_image(image: UploadFile) -> tuple[bytes, str]:
    data = await image.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Image must be under 5 MB")
    ext = _sniff_image_ext(data)
    if ext is None:
        raise HTTPException(400, "Image must be JPEG, PNG, WEBP, or GIF")
    return data, ext


@router.get("", response_model=list[BannerOut])
def list_banners(db: Session = Depends(get_db)):
    return (
        db.query(Banner)
        .filter(Banner.is_active.is_(True))
        .order_by(Banner.sort_order)
        .all()
    )


@admin_router.get("", response_model=list[BannerOut])
def admin_list_banners(db: Session = Depends(get_db)):
    return db.query(Banner).order_by(Banner.sort_order).all()


@admin_router.post("", response_model=BannerOut)
async def create_banner(
    headline: str | None = Form(None),
    subtext: str | None = Form(None),
    link_url: str | None = Form(None),
    sort_order: int = Form(0),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    data, ext = await _read_validated_image(image)
    banner = Banner(
        image_path=_save_image(data, ext),
        headline=headline or None,
        subtext=subtext or None,
        link_url=link_url or None,
        sort_order=sort_order,
    )
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return banner


@admin_router.put("/{banner_id}", response_model=BannerOut)
async def update_banner(
    banner_id: str,
    headline: str | None = Form(None),
    subtext: str | None = Form(None),
    link_url: str | None = Form(None),
    sort_order: int | None = Form(None),
    is_active: bool | None = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(404, "Banner not found")

    if headline is not None:
        banner.headline = headline or None
    if subtext is not None:
        banner.subtext = subtext or None
    if link_url is not None:
        banner.link_url = link_url or None
    if sort_order is not None:
        banner.sort_order = sort_order
    if is_active is not None:
        banner.is_active = is_active
    if image is not None and image.filename:
        data, ext = await _read_validated_image(image)
        banner.image_path = _save_image(data, ext)

    db.commit()
    db.refresh(banner)
    return banner


@admin_router.delete("/{banner_id}")
def delete_banner(banner_id: str, db: Session = Depends(get_db)):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(404, "Banner not found")
    db.delete(banner)
    db.commit()
    return {"ok": True}
