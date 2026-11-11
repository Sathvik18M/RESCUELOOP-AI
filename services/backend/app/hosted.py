"""Supervise the API and durable worker in one free demo container.

Database migration/import is an explicit pre-deployment step. This entry point
never seeds, resets, imports data, or changes the provider webhook.
"""

import os
import signal
import subprocess
import sys
import time


def supervise(commands):
    children = []

    def stop(signum, frame):
        raise SystemExit(0)

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        for command in commands:
            children.append(subprocess.Popen(command))
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    # A clean unexpected exit also leaves half the app unavailable.
                    return code if code else 1
            time.sleep(0.5)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 15
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main():
    if not os.environ.get("PUBLIC_WEBHOOK_URL") and os.environ.get("RENDER_EXTERNAL_URL"):
        os.environ["PUBLIC_WEBHOOK_URL"] = os.environ["RENDER_EXTERNAL_URL"]
    from app.core.config import get_settings

    settings = get_settings()
    settings.validate_runtime()
    if settings.app_env not in {"staging", "production"}:
        raise ValueError("The hosted entry point requires staging or production")
    from sqlalchemy import text
    from app.persistence.session import engine

    with engine.connect() as conn:
        if conn.scalar(text("SELECT version_num FROM alembic_version")) != "0007":
            raise RuntimeError("Apply the repository migrations before starting the hosted app")
    return supervise([
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
         "--port", os.environ.get("PORT", "8000")],
        [sys.executable, "-m", "app.workers.worker"],
    ])


if __name__ == "__main__":
    raise SystemExit(main())
