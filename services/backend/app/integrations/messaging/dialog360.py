"""360dialog Sandbox transport. Only the configured tester can receive messages."""

import hmac
from datetime import timedelta

import httpx

from app.core.config import get_settings
from app.domain.common import utc
from app.integrations.messaging.base import (
    CapabilityUnavailable,
    PermanentProviderError,
    SandboxQuotaExceeded,
    WindowClosed,
)
from app.persistence.models import now

name = "360dialog_sandbox"
minimum_send_interval = 3
BASE_URL = "https://waba-sandbox.360dialog.io"


def credentials():
    s = get_settings()
    from app.integrations.whatsapp import is_configured

    if not is_configured(s) or s.whatsapp_provider != name:
        raise PermanentProviderError("360dialog Sandbox configuration is incomplete")
    return s


def send_text(recipient, text, last_inbound, local_id):
    s = credentials()
    if now() - utc(last_inbound) > timedelta(hours=24):
        raise WindowClosed()
    if not hmac.compare_digest(recipient, s.d360_sandbox_recipient):
        raise PermanentProviderError("Sandbox recipient does not match the configured tester")
    recipient_field = "recipient" if s.d360_recipient_type == "bsuid" else "to"
    response = httpx.post(
        BASE_URL + "/v1/messages",
        headers={"D360-API-KEY": s.d360_api_key},
        json={
            "messaging_product": "whatsapp",
            recipient_field: recipient,
            "type": "text",
            "text": {"body": text},
        },
        timeout=20,
    )
    # In this Sandbox, 429 means the fixed 25-request allowance is exhausted.
    if response.status_code == 429:
        raise SandboxQuotaExceeded("360dialog Sandbox message allowance is exhausted")
    response.raise_for_status()
    body = response.json()
    message_id = body.get("messages", [{}])[0].get("id")
    if not isinstance(message_id, str) or not 1 <= len(message_id) <= 200:
        raise ValueError("Provider accepted response has no valid message identifier")
    return message_id


def fetch_status(provider_id):
    raise CapabilityUnavailable("360dialog Sandbox delivery is verified by webhook receipts")


def download_media(reference):
    raise CapabilityUnavailable("360dialog Sandbox does not support retrieving media")
