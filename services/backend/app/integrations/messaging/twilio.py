"""Twilio transport. Sending is separate from delivery confirmation."""

from datetime import timedelta
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.domain.common import utc
from app.integrations.messaging.base import PermanentProviderError, WindowClosed
from app.persistence.models import now

name = "twilio"
minimum_send_interval = 3


def credentials():
    s = get_settings()
    if not all([s.twilio_account_sid, s.twilio_auth_token, s.twilio_whatsapp_from, s.public_webhook_url]):
        raise PermanentProviderError("Twilio configuration is incomplete")
    return s


def send_text(phone, text, last_inbound, local_id):
    s = credentials()
    if now() - utc(last_inbound) > timedelta(hours=24):
        raise WindowClosed()
    response = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json",
        auth=(s.twilio_account_sid, s.twilio_auth_token),
        data={
            "From": s.twilio_whatsapp_from,
            "To": "whatsapp:" + phone,
            "Body": text,
            "StatusCallback": f"{s.public_webhook_url.rstrip('/')}/webhooks/twilio/status?local_id={local_id}",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["sid"]


def fetch_status(provider_id):
    s = credentials()
    response = httpx.get(
        f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages/{provider_id}.json",
        auth=(s.twilio_account_sid, s.twilio_auth_token),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["status"]


def download_media(url):
    s = credentials()
    parsed = urlparse(url)
    # Signed webhook media is still untrusted. Restrict authenticated requests to this account.
    prefix = f"/2010-04-01/Accounts/{s.twilio_account_sid}/Messages/"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.twilio.com"
        or not parsed.path.startswith(prefix)
        or "/Media/" not in parsed.path
    ):
        raise PermanentProviderError("Unexpected media address")

    def read_limited(response):
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > 8 * 1024 * 1024:
                raise PermanentProviderError("Image exceeds upload limit")
        return bytes(content)

    # Stream both origins; never forward account credentials to a CDN.
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        with client.stream("GET", url, auth=(s.twilio_account_sid, s.twilio_auth_token)) as response:
            if not response.is_redirect:
                return read_limited(response)
            target = response.headers.get("location", "")
            host = urlparse(target)
            if host.scheme != "https" or not (
                (host.hostname or "").endswith(".twiliocdn.com")
                or (host.hostname or "").endswith(".twilio.com")
            ):
                raise PermanentProviderError("Unexpected media redirect")
        with client.stream("GET", target) as response:
            return read_limited(response)
