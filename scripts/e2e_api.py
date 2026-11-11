"""Run browser tests against a fresh, isolated PostgreSQL schema."""

import os
import sys
from pathlib import Path
import psycopg
from psycopg import sql
import uvicorn

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "services/backend"))
url = os.environ.get(
    "E2E_DATABASE_URL",
    "postgresql+psycopg://rescueloop:rescueloop@127.0.0.1:5432/rescueloop_e2e",
)
if not url.endswith("/rescueloop_e2e"):
    raise RuntimeError("Browser tests require a dedicated rescueloop_e2e database")
admin_url = (
    url.replace("postgresql+psycopg://", "postgresql://").rsplit("/", 1)[0]
    + "/postgres"
)
with psycopg.connect(admin_url, autocommit=True, connect_timeout=10) as connection:
    if not connection.execute(
        "SELECT 1 FROM pg_database WHERE datname=%s", ("rescueloop_e2e",)
    ).fetchone():
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier("rescueloop_e2e"))
        )
os.environ.update(
    DATABASE_URL=url,
    APP_ENV="test",
    SUPABASE_URL="",
    SUPABASE_SERVICE_ROLE_KEY="",
    TWILIO_ACCOUNT_SID="",
    TWILIO_AUTH_TOKEN="",
    PUBLIC_WEBHOOK_URL="",
    DEMO_MODE="true",
    AI_MODE="demo",
    GROQ_API_KEY="",
    LOCAL_VERIFICATION_ONLY="false",
    DEMO_TOKEN="local-rescueloop-demo",
    CORS_ORIGINS="http://127.0.0.1:3001",
)
from app.persistence.session import Base, engine, SessionLocal
from app.persistence import models
from app.domain.seed import seed

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
with SessionLocal() as db:
    seed(db)
uvicorn.run("app.main:app", host="127.0.0.1", port=8002)
