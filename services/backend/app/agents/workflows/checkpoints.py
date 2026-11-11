"""Keep LangGraph tables private and serialize first-start setup across API/worker."""

from contextlib import contextmanager, ExitStack
from psycopg.conninfo import make_conninfo
from sqlalchemy import text
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import get_settings
from app.persistence.session import engine


@contextmanager
def checkpoint_store():
    dsn = make_conninfo(
        get_settings().database_url.replace("postgresql+psycopg://", "postgresql://"),
        options="-c search_path=rescueloop_agents",
        connect_timeout=10,
    )
    with ExitStack() as stack:
        # Session advisory lock spans the independent connection used by saver.setup().
        # Autocommit makes CREATE SCHEMA visible before that connection is opened.
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text("SELECT pg_advisory_lock(hashtext('rescueloop-checkpoint-setup'))"))
            try:
                connection.execute(text("CREATE SCHEMA IF NOT EXISTS rescueloop_agents"))
                saver = stack.enter_context(PostgresSaver.from_conn_string(dsn))
                saver.setup()
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(hashtext('rescueloop-checkpoint-setup'))"))
        yield saver
