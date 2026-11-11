"""Prepare the private evidence bucket and verify synthetic image access."""

import json
import sys
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/backend"))
from app.core.config import get_settings
from app.integrations.storage import normalize_image, upload, signed_url
from verify_integrations import safe_error


def verify():
    s = get_settings()
    base = s.supabase_url.rstrip("/")
    headers = {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
    }
    result = {}
    key = None
    with httpx.Client(base_url=base, headers=headers, timeout=30) as client:
        response = client.get("/storage/v1/bucket")
        response.raise_for_status()
        bucket = next(
            (b for b in response.json() if b["id"] == s.supabase_storage_bucket), None
        )
        if bucket is None:
            created = client.post(
                "/storage/v1/bucket",
                json={
                    "id": s.supabase_storage_bucket,
                    "name": s.supabase_storage_bucket,
                    "public": False,
                    "file_size_limit": 8 * 1024 * 1024,
                    "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
                },
            )
            created.raise_for_status()
            result["bucket_created"] = True
        checked = client.get(f"/storage/v1/bucket/{quote(s.supabase_storage_bucket)}")
        checked.raise_for_status()
        if checked.json().get("public"):
            raise RuntimeError("Evidence bucket must be private")
        result["private_bucket"] = "passed"
        try:
            data = normalize_image(
                (ROOT / "data/demo/assets/test-evidence.png").read_bytes()
            )
            key = upload("integration-verification", data)
            result["application_upload"] = "passed"
            url = signed_url(key)
            downloaded = httpx.get(url, timeout=20)
            downloaded.raise_for_status()
            result["signed_download"] = (
                "passed" if downloaded.content == data else "content_mismatch"
            )
            for name, path in [
                ("unsigned_access", "object"),
                ("public_access", "object/public"),
            ]:
                denied = httpx.get(
                    f"{base}/storage/v1/{path}/{quote(s.supabase_storage_bucket)}/{quote(key)}",
                    timeout=15,
                )
                result[name] = (
                    "denied"
                    if denied.status_code in {400, 401, 403, 404}
                    else "UNEXPECTED_ACCESS"
                )
        finally:
            if key:
                cleaned = client.request(
                    "DELETE",
                    f"/storage/v1/object/{quote(s.supabase_storage_bucket)}",
                    json={"prefixes": [key]},
                )
                cleaned.raise_for_status()
                result["synthetic_object_cleanup"] = "passed"
    return result


if __name__ == "__main__":
    try:
        result = verify()
    except Exception as exc:
        result = safe_error(exc)
    print(json.dumps(result, indent=2))
    path = ROOT / ".local/rebuild-run/supabase-storage-check.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
