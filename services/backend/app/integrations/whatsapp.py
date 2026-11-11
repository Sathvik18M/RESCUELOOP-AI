from datetime import timedelta
from urllib.parse import urlparse
import httpx
from app.core.config import get_settings
from app.db.models import now
from app.modules.common import utc


def send_text(phone: str, text: str, last_inbound):
    settings = get_settings()
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        raise RuntimeError("WhatsApp credentials are not configured")
    payload = {"messaging_product": "whatsapp", "to": phone}
    if now() - utc(last_inbound) > timedelta(hours=24):
        if not settings.whatsapp_update_template:
            raise ValueError(
                "A configured, approved update template is required outside the messaging window"
            )
        payload.update(
            {
                "type": "template",
                "template": {
                    "name": settings.whatsapp_update_template,
                    "language": {"code": "en"},
                    "components": [{"type": "body", "parameters": [{"type": "text", "text": text[:1000]}]}],
                },
            }
        )
    else:
        payload.update({"type": "text", "text": {"body": text}})
    response = httpx.post(
        f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{settings.whatsapp_phone_number_id}/messages",
        headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["messages"][0]["id"]


def download_media(media_id: str):
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    response = httpx.get(
        f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{media_id}",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    url = response.json()["url"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or not any(
        (parsed.hostname or "").endswith("." + domain) or parsed.hostname == domain
        for domain in ("fbsbx.com", "facebook.com", "whatsapp.net")
    ):
        raise ValueError("Unexpected WhatsApp media host")
    content = bytearray()
    with httpx.stream("GET", url, headers=headers, timeout=30, follow_redirects=False) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > 8 * 1024 * 1024:
                raise ValueError("Photo exceeds the 8 MB upload limit")
    return bytes(content)
