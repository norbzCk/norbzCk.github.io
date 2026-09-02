"""Shared image-upload handling.

Stores images as base64 data URIs directly in the database column that
references them (Product.image_url, BusinessUser.shop_logo_url,
LogisticsUser.profile_photo) -- not in Supabase Storage, not on local
disk. This is deliberate: it needs zero external service credentials and
zero persistent disk, both of which were live problems on Render (local
disk is ephemeral there, and Supabase Storage needs SUPABASE_URL/
SUPABASE_SERVICE_ROLE_KEY configured and the bucket marked public, which
wasn't happening -- uploads were failing outright with a 500).

A data URI (`data:image/png;base64,....`) is valid anywhere a normal image
URL is valid -- <img src="..."> renders it directly, no separate fetch or
static file route required. The tradeoff is DB row size, which is why the
size cap here is intentionally conservative (2MB raw, ~2.7MB once base64-
encoded) -- fine for product photos, not meant for large uploads.
"""
from __future__ import annotations

import base64
import os

from fastapi import HTTPException, UploadFile

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2MB raw (before base64 inflates it ~33%)


async def save_uploaded_image(file: UploadFile) -> str:
    """Validate an uploaded image and return it as a base64 data URI,
    ready to store directly in a DB column and render directly in an
    <img> tag with no further processing.
    """
    filename = file.filename or ""
    suffix = os.path.splitext(filename)[1].lower()

    if suffix not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    content_type = (file.content_type or "").strip()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large (max {MAX_IMAGE_BYTES // (1024 * 1024)}MB)",
        )

    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"
