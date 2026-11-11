import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# A dedicated test database may be supplied for PostgreSQL integration tests.
# Otherwise each test uses an isolated in-memory database. Never reset the demo database.
os.environ["APP_ENV"] = "test"
os.environ["LOCAL_VERIFICATION_ONLY"] = "false"
os.environ["AI_MODE"] = "demo"
os.environ["DEMO_MODE"] = "true"
os.environ["DEMO_TOKEN"] = "test-token"
os.environ["WHATSAPP_PROVIDER"] = "disabled"
for key in [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_WHATSAPP_FROM",
    "PUBLIC_WEBHOOK_URL",
    "D360_API_KEY",
    "D360_SANDBOX_RECIPIENT",
    "D360_WEBHOOK_SECRET",
]:
    os.environ[key] = ""

from app.core.config import get_settings
from app.persistence.session import Base, get_db
from app.persistence import models
from app.main import app
from app.domain.seed import seed
from app.agents.workflows import orchestrator


@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL", "sqlite://")
    if url != "sqlite://" and "rescueloop_test" not in url:
        raise RuntimeError("TEST_DATABASE_URL must point to a dedicated rescueloop_test database")
    kwargs = (
        {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool} if url == "sqlite://" else {}
    )
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )()
    seed(session)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


@pytest.fixture
def client(db):
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: db
    orchestrator.workflow = orchestrator.build_graph()
    # Without lifespan: database schema and workflow are managed by this fixture.
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def auth():
    return {"Authorization": "Bearer test-token"}
