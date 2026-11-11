"""Persist image clarity independently of seller verification.
Revision ID: 0005
Revises: ea7af894d94d
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "ea7af894d94d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "evidence", sa.Column("quality", sa.String(20), nullable=False, server_default="unassessed")
    )
    op.alter_column("reviews", "product_id", existing_type=sa.String(50), nullable=True)


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM reviews WHERE product_id IS NULL")).scalar():
        raise RuntimeError(
            "Export feedback on cases without products before downgrading; no records were removed."
        )
    op.alter_column("reviews", "product_id", existing_type=sa.String(50), nullable=False)
    op.drop_column("evidence", "quality")
