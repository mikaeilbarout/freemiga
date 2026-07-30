"""
Shared validated-image-upload helper. Extension is derived from sniffed
magic bytes, never from the client-supplied filename or Content-Type header
(both attacker-controlled) — otherwise e.g. an SVG uploaded with a spoofed
"image/png" Content-Type would be accepted and served by StaticFiles as
image/svg+xml, a stored-XSS vector.
"""
import os
import uuid

from fastapi import HTTPException, UploadFile

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


def _sniff_image_ext(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return None


def save_image(data: bytes, ext: str, subdir: str) -> str:
    upload_dir = f"app/static/uploads/{subdir}"
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(upload_dir, filename), "wb") as f:
        f.write(data)
    return f"/static/uploads/{subdir}/{filename}"


async def read_validated_image(image: UploadFile) -> tuple[bytes, str]:
    data = await image.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Image must be under 5 MB")
    ext = _sniff_image_ext(data)
    if ext is None:
        raise HTTPException(400, "Image must be JPEG, PNG, WEBP, or GIF")
    return data, ext
