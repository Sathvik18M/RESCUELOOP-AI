"""Store only one-time recovery code digests, accessible through the server."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_recovery_codes",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column("digest", sa.String(64), nullable=False, unique=True),
        sa.Column("spent", sa.Boolean(), nullable=False),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE account_recovery_codes ENABLE ROW LEVEL SECURITY")
        if bind.scalar(sa.text("SELECT to_regclass('auth.users') IS NOT NULL")):
            op.create_foreign_key(
                "fk_recovery_auth_user",
                "account_recovery_codes",
                "users",
                ["user_id"],
                ["id"],
                referent_schema="auth",
                ondelete="CASCADE",
            )
            op.execute("REVOKE ALL ON account_recovery_codes FROM anon, authenticated, PUBLIC")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM account_recovery_codes WHERE NOT spent")):
        raise RuntimeError("Active seller recovery codes must be preserved before downgrade")
    op.drop_table("account_recovery_codes")
