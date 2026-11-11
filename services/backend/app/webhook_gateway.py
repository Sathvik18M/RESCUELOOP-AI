"""Small public surface for a temporary WhatsApp tunnel; seller APIs stay local."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.webhooks import router
from app.api.dialog360_webhooks import router as dialog360_router
from app.core.logging import protect_webhook_logs
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app):
    get_settings().validate_runtime()
    yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.include_router(router)
app.include_router(dialog360_router)
protect_webhook_logs()


@app.get("/health")
def health():
    return {"status": "ok", "service": "rescueloop-whatsapp-webhook"}
