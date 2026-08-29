"""Shared image-upload handling."""

from __future__ import annotations

import os
import uuid

import httpx
from fastapi import HTTPException, UploadFile

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB

SUPABASE_STORAGE_BUCKET = os.getenv(
    "SUPABASE_STORAGE_BUCKET",
    "product-images",
)


async def save_uploaded_image(file: UploadFile) -> str:
    """Validate and upload an image to Supabase Storage.

    Returns the permanent public URL of the uploaded image.
    """

    filename = file.filename or ""
    suffix = os.path.splitext(filename)[1].lower()

    if suffix not in ALLOWED_IMAGE_EXT:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format",
        )

    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File must be an image",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Empty file",
        )

    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Image too large (max 5MB)",
        )

    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_role_key = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        "",
    ).strip()

    if not supabase_url or not service_role_key:
        raise HTTPException(
            status_code=500,
            detail="Supabase image storage is not configured",
        )

    stored_filename = f"{uuid.uuid4().hex}{suffix}"
    storage_path = f"products/{stored_filename}"

    upload_url = (
        f"{supabase_url}/storage/v1/object/"
        f"{SUPABASE_STORAGE_BUCKET}/{storage_path}"
    )

    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Content-Type": file.content_type or "application/octet-stream",
        "Cache-Control": "3600",
        "x-upsert": "false",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                upload_url,
                content=content,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to image storage",
        ) from exc

    if response.status_code >= 300:
        try:
            error_data = response.json()
            detail = (
                error_data.get("message")
                or error_data.get("error")
                or response.text
            )
        except Exception:
            detail = response.text

        raise HTTPException(
            status_code=502,
            detail=f"Supabase Storage upload failed: {detail[:300]}",
        )

    public_url = (
        f"{supabase_url}/storage/v1/object/public/"
        f"{SUPABASE_STORAGE_BUCKET}/{storage_path}"
    )

    return public_url