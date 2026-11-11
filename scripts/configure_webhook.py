"""Save only a validated public webhook origin; preserve all other .env settings."""

import sys
from pathlib import Path
from urllib.parse import urlparse
from dotenv import set_key

origin = sys.argv[1].rstrip("/")
parsed = urlparse(origin)
if (
    parsed.scheme != "https"
    or not parsed.hostname
    or parsed.path
    or parsed.query
    or parsed.fragment
    or parsed.username
    or parsed.password
):
    raise SystemExit("Provide an HTTPS origin without a path or credentials")
path = Path(__file__).resolve().parents[1] / ".env"
if not path.exists():
    raise SystemExit("Configure .env first")
set_key(path, "PUBLIC_WEBHOOK_URL", origin, quote_mode="never")
print("Public webhook origin saved.")
