from datetime import datetime
from typing import Protocol


class WindowClosed(Exception):
    pass


class PermanentProviderError(Exception):
    pass


class ProviderDisabled(PermanentProviderError):
    pass


class CapabilityUnavailable(PermanentProviderError):
    pass


class SandboxQuotaExceeded(PermanentProviderError):
    pass


class MessagingProvider(Protocol):
    name: str
    minimum_send_interval: int

    def credentials(self): ...
    def send_text(self, recipient: str, text: str, last_inbound: datetime, local_id: str) -> str: ...
    def fetch_status(self, provider_id: str) -> str: ...
    def download_media(self, reference: str) -> bytes: ...
