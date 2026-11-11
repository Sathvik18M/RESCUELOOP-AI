"""Live provider checks using synthetic data; never print credentials or provider bodies."""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from uuid import UUID

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/backend"))
from app.core.config import get_settings


def safe_error(exc):
    response = getattr(exc, "response", None)
    result = {"status": "failed", "error_type": type(exc).__name__}
    if response is not None:
        result["http_status"] = response.status_code
        try:
            body = response.json()
            detail = body.get("error", body)
            code = detail.get("code") if isinstance(detail, dict) else body.get("code")
            if isinstance(code, (int, str)) and re.fullmatch(
                r"[A-Za-z0-9_-]{1,80}", str(code)
            ):
                result["provider_code"] = code
        except (ValueError, AttributeError):
            pass
    return result


def groq_check():
    from app.agents.router import classify_many
    from app.agents.specialists import assess_image
    from app.integrations.storage import normalize_image

    s = get_settings()
    if not s.groq_api_key:
        return {"status": "missing_key"}
    # Direct verification only; do not change .env or the running application.
    s.ai_mode = "groq"
    start = monotonic()
    try:
        proposals = classify_many(
            "What is your return policy?",
            "Synthetic integration check. No customer data.",
        )
        result = {
            "status": "passed",
            "model": s.groq_model,
            "structured_text": proposals[0]["intent"] == "policy",
            "text_seconds": round(monotonic() - start, 2),
        }
    except Exception as exc:
        return {"model": s.groq_model, "text": safe_error(exc)}
    try:
        image = normalize_image(
            (ROOT / "data/demo/assets/test-evidence.png").read_bytes()
        )
        start = monotonic()
        assessment = assess_image(image, "image/jpeg")
        result["image"] = {
            "status": "passed",
            "quality": assessment["quality"],
            "model": s.groq_vision_model,
            "seconds": round(monotonic() - start, 2),
        }
    except Exception as exc:
        result["image"] = safe_error(exc)
    return result


def supabase_check():
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        return {"status": "missing_configuration"}
    result = {}
    headers = {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
    }
    with httpx.Client(
        base_url=s.supabase_url.rstrip("/"), headers=headers, timeout=20
    ) as client:
        try:
            response = client.get("/storage/v1/bucket")
            response.raise_for_status()
            buckets = response.json()
            bucket = next(
                (b for b in buckets if b["id"] == s.supabase_storage_bucket), None
            )
            result["service_credentials"] = "passed"
            result["evidence_bucket"] = (
                "missing"
                if not bucket
                else "private"
                if not bucket.get("public")
                else "PUBLIC_REQUIRES_FIX"
            )
        except Exception as exc:
            result["storage"] = safe_error(exc)
        try:
            UUID(s.seller_user_id)
            response = client.get(f"/auth/v1/admin/users/{s.seller_user_id}")
            response.raise_for_status()
            user = response.json()
            result["seller_user"] = (
                "exists" if user.get("id") == s.seller_user_id else "mismatch"
            )
            result["seller_email_confirmed"] = bool(user.get("email_confirmed_at"))
        except ValueError:
            result["seller_user"] = "invalid_or_missing_uuid"
        except Exception as exc:
            result["seller_user"] = safe_error(exc)
        try:
            response = client.get("/auth/v1/.well-known/jwks.json")
            response.raise_for_status()
            result["jwt_signing_keys"] = [
                key.get("alg") for key in response.json().get("keys", [])
            ]
        except Exception as exc:
            result["jwt_signing_keys"] = safe_error(exc)
    return result


def twilio_check():
    s = get_settings()
    if s.whatsapp_provider != "twilio":
        return {"enabled": False, "credentials": "preserved_not_checked"}
    if not s.twilio_account_sid or not s.twilio_auth_token:
        return {"status": "missing_configuration"}
    try:
        response = httpx.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}.json",
            auth=(s.twilio_account_sid, s.twilio_auth_token),
            timeout=20,
        )
        response.raise_for_status()
        account = response.json()
        return {
            "credentials": "passed",
            "account_status": account.get("status"),
            "account_type": account.get("type"),
            "public_webhook_origin_configured": bool(s.public_webhook_url),
            "twilio_console_webhook": "not_verified_by_this_check",
            "whatsapp_delivery": "pending_real_inbound_and_delivered_reply",
        }
    except Exception as exc:
        return safe_error(exc)


if __name__ == "__main__":
    checks = {
        "groq": groq_check,
        "supabase": supabase_check,
        "twilio": twilio_check,
    }
    results = {"checked_at": datetime.now(timezone.utc).isoformat()}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(check) for name, check in checks.items()}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as exc:
                results[name] = safe_error(exc)
            print(json.dumps({name: results[name]}), flush=True)
    target = ROOT / ".local/rebuild-run/integration-check.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, indent=2), encoding="utf-8")
