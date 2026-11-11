"""Keep LangGraph's internal tables outside Supabase's public API schema."""

from contextlib import contextmanager
from psycopg.conninfo import make_conninfo
from sqlalchemy import text
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import get_settings
from app.db.session import engine


@contextmanager
def checkpoint_store():
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS rescueloop_agents"))
    dsn = make_conninfo(
        get_settings().database_url.replace("postgresql+psycopg://", "postgresql://"),
        options="-c search_path=rescueloop_agents",
        connect_timeout=10,
    )
    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()
        yield saver
