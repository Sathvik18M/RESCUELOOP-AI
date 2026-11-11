from contextlib import asynccontextmanager, ExitStack
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import get_settings
from app.persistence.session import engine
from app.api.routes import router
from app.api.webhooks import router as webhooks
from app.api.dialog360_webhooks import router as dialog360_webhooks
from app.core.logging import protect_webhook_logs
from app.agents.workflows import orchestrator


@asynccontextmanager
async def lifespan(app):
    settings = get_settings()
    settings.validate_runtime()
    with ExitStack() as stack:
        if settings.database_url.startswith("postgresql"):
            from app.agents.workflows.checkpoints import checkpoint_store

            saver = stack.enter_context(checkpoint_store())
            orchestrator.workflow = orchestrator.build_graph(saver)
        yield


app = FastAPI(
    title="RescueLoop API",
    version="0.1.0",
    lifespan=lifespan,
    description="Merchant-scoped commerce, approvals, messaging, and demo integrations.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins.split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
app.include_router(webhooks)
app.include_router(dialog360_webhooks)
protect_webhook_logs()


@app.get("/health", tags=["health"])
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "ok", "service": "rescueloop-api"}
