"""Shared image-upload handling.

Extracted from backend/app/products.py's upload_product_image so other
flows -- like seller/logistics registration, which need to accept a logo
or profile photo before the person has an authenticated account to call an
auth-gated upload endpoint -- can reuse the exact same validation and
storage logic instead of duplicating (and inevitably drifting from) it.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"


async def save_uploaded_image(file: UploadFile) -> str:
    """Validate and persist an uploaded image, returning its public /uploads/ URL.

    Raises HTTPException(400) for anything that doesn't look like a real,
    reasonably-sized image -- callers don't need to re-check.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported image format")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    destination = UPLOADS_DIR / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    destination.write_bytes(content)
    return f"/uploads/{filename}"
