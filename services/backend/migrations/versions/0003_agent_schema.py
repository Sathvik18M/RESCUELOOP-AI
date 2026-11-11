"""Move any initial LangGraph state into a private schema."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    connection.execute(sa.text("CREATE SCHEMA IF NOT EXISTS rescueloop_agents"))
    for table in ("checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        old = connection.execute(sa.text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}).scalar()
        new = connection.execute(
            sa.text("SELECT to_regclass(:name)"), {"name": f"rescueloop_agents.{table}"}
        ).scalar()
        if old and not new:
            connection.execute(sa.text(f'ALTER TABLE public."{table}" SET SCHEMA rescueloop_agents'))


def downgrade():
    # Keep persisted agent state private when reverting application migrations.
    pass
