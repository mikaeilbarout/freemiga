from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import Banner
from app.schemas import BannerOut
from app.services.uploads import read_validated_image, save_image

router = APIRouter(prefix="/api/banners", tags=["banners"])
admin_router = APIRouter(
    prefix="/api/admin/banners", tags=["admin-banners"], dependencies=[Depends(require_admin)]
)


async def _read_validated_image(image: UploadFile) -> tuple[bytes, str]:
    return await read_validated_image(image)


def _save_image(data: bytes, ext: str) -> str:
    return save_image(data, ext, "banners")


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
