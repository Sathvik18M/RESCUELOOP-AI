from io import BytesIO
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote
import httpx
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException
from app.core.config import ROOT, get_settings

MAX_BYTES = 8 * 1024 * 1024


def normalize_image(content: bytes):
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Photo must be smaller than 8 MB")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 20000000:
                raise HTTPException(422, "Use a JPEG, PNG, or WebP image under 20 megapixels")
            image.load()
            image.thumbnail((2048, 2048))
            output = BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=88)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "The file is not a supported image") from exc


def upload(merchant_id: str, content: bytes):
    key = f"{merchant_id}/{uuid4()}.jpg"
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_role_key:
        response = httpx.post(
            f"{settings.supabase_url}/storage/v1/object/{settings.supabase_storage_bucket}/{key}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "image/jpeg",
            },
            content=content,
            timeout=30,
        )
        response.raise_for_status()
    elif settings.demo_mode and settings.app_env != "production":
        path = ROOT / ".local/evidence" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    else:
        raise HTTPException(503, "Private storage is not configured")
    return key


def signed_url(key: str):
    settings = get_settings()
    response = httpx.post(
        f"{settings.supabase_url}/storage/v1/object/sign/{settings.supabase_storage_bucket}/{quote(key)}",
        headers={"Authorization": f"Bearer {settings.supabase_service_role_key}"},
        json={"expiresIn": 120},
        timeout=15,
    )
    response.raise_for_status()
    return f"{settings.supabase_url}/storage/v1{response.json()['signedURL']}"


def local_path(key: str):
    base = (ROOT / ".local/evidence").resolve()
    path = (base / key).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(404, "Image unavailable")
    return path
