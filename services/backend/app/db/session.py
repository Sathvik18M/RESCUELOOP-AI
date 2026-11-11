from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


connection_args = {"connect_timeout": 10} if get_settings().database_url.startswith("postgresql") else {}
engine = create_engine(get_settings().database_url, pool_pre_ping=True, connect_args=connection_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
