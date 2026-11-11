"""Create the isolated development database; never modify the prototype database."""

import psycopg
from psycopg import sql

with psycopg.connect(
    "postgresql://rescueloop:rescueloop@127.0.0.1:5432/postgres",
    autocommit=True,
    connect_timeout=10,
) as db:
    name = "rescueloop_rebuild"
    if not db.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        print("Created isolated rebuild database")
    else:
        print("Isolated rebuild database exists; unchanged")
