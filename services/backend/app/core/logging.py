"""Keep Sandbox URL bearer credentials out of server access logs."""
import logging


class WebhookAccessFilter(logging.Filter):
    def filter(self, record):
        return "/webhooks/360dialog/" not in record.getMessage()


def protect_webhook_logs():
    logging.getLogger("uvicorn.access").addFilter(WebhookAccessFilter())
