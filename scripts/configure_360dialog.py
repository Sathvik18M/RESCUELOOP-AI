"""Register the existing private FastAPI callback without printing any credential."""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/backend"))
from app.integrations.messaging.dialog360 import BASE_URL, credentials


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configure", action="store_true", help="Register the callback with 360dialog"
    )
    args = parser.parse_args()
    s = credentials()
    origin = urlparse(s.public_webhook_url)
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.username
        or origin.password
        or origin.path not in {"", "/"}
        or origin.query
        or origin.fragment
    ):
        raise ValueError("PUBLIC_WEBHOOK_URL must be an HTTPS origin")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", s.d360_webhook_secret):
        raise ValueError(
            "Webhook secret must be a random URL-safe token, 32-128 characters"
        )
    if s.d360_recipient_type == "phone" and not re.fullmatch(
        r"[1-9]\d{7,14}", s.d360_sandbox_recipient
    ):
        raise ValueError(
            "Sandbox phone must contain country code and number, digits only"
        )
    if not 1 <= len(s.d360_sandbox_recipient) <= 200:
        raise ValueError("Invalid recipient length")
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "provider": s.whatsapp_provider,
        "configured_locally": True,
        "live_whatsapp_verified": False,
    }
    if args.configure:
        callback = (
            s.public_webhook_url.rstrip("/")
            + "/webhooks/360dialog/"
            + s.d360_webhook_secret
        )
        # No redirects: never forward a bearer URL or API key to another origin.
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            health = client.get(s.public_webhook_url.rstrip("/") + "/health")
            health.raise_for_status()
            if health.json().get("service") != "rescueloop-whatsapp-webhook":
                raise ValueError("Expected the restricted WhatsApp gateway")
            probe = client.post(callback, json={"entry": []})
            probe.raise_for_status()
            rejected = client.post(
                s.public_webhook_url.rstrip("/") + "/webhooks/360dialog/invalid",
                json={"entry": []},
            )
            if rejected.status_code != 403:
                raise ValueError("Webhook authentication check failed")
            response = client.post(
                BASE_URL + "/v1/configs/webhook",
                headers={"D360-API-KEY": s.d360_api_key},
                json={"url": callback},
            )
            response.raise_for_status()
            if response.json().get("url") != callback:
                raise ValueError("Provider did not confirm the configured callback")
            result.update(
                {"webhook_registered": True, "unauthenticated_request_rejected": True}
            )
    target = ROOT / ".local/rebuild-run/360dialog-configuration.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- Never emit a secret-bearing exception at this CLI boundary.
        # Exception strings / provider responses can contain the callback URL or key.
        result = {"status": "failed", "error_type": type(exc).__name__}
        response = getattr(exc, "response", None)
        if response is not None:
            result["http_status"] = response.status_code
        print(json.dumps(result))
        raise SystemExit(1)
