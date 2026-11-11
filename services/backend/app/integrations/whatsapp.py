"""Provider-independent WhatsApp transport; no automatic fallback between accounts."""

from app.core.config import get_settings
from app.integrations.messaging.base import (
    CapabilityUnavailable,
    MessagingProvider,
    PermanentProviderError,
    ProviderDisabled,
    SandboxQuotaExceeded,
    WindowClosed,
)

__all__ = [
    "CapabilityUnavailable",
    "PermanentProviderError",
    "ProviderDisabled",
    "SandboxQuotaExceeded",
    "WindowClosed",
    "download_media",
    "fetch_status",
    "get_provider",
    "is_configured",
    "send_text",
]


def is_configured(settings=None):
    s = settings or get_settings()
    if s.whatsapp_provider == "twilio":
        return all([s.twilio_account_sid, s.twilio_auth_token, s.twilio_whatsapp_from, s.public_webhook_url])
    if s.whatsapp_provider == "360dialog_sandbox":
        return bool(
            s.d360_api_key
            and s.d360_sandbox_recipient
            and len(s.d360_webhook_secret) >= 32
            and s.public_webhook_url.startswith("https://")
        )
    return False


def get_provider(name=None) -> MessagingProvider:
    s = get_settings()
    selected = name or s.whatsapp_provider
    if selected == "disabled" or selected != s.whatsapp_provider:
        raise ProviderDisabled("This conversation's messaging provider is disabled")
    if selected == "twilio":
        from app.integrations.messaging import twilio

        return twilio
    if selected == "360dialog_sandbox":
        from app.integrations.messaging import dialog360

        return dialog360
    raise ProviderDisabled("Unknown messaging provider")


def send_text(phone, text, last_inbound, local_id, provider=None):
    return get_provider(provider).send_text(phone, text, last_inbound, local_id)


def fetch_status(provider_id, provider=None):
    return get_provider(provider).fetch_status(provider_id)


def download_media(reference, provider=None):
    return get_provider(provider).download_media(reference)
