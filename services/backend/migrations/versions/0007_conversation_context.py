"""Persist conversation context and source-attributed shipment evidence without inventing events."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("context", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "shipment_events",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("merchant_id", sa.String(50), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("order_id", sa.String(50), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("proof", sa.JSON(), nullable=False),
    )
    op.create_index("ix_shipment_events_merchant_id", "shipment_events", ["merchant_id"])
    op.create_index("ix_shipment_events_order_id", "shipment_events", ["order_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE shipment_events ENABLE ROW LEVEL SECURITY")


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM shipment_events")).scalar() or bind.execute(
        sa.text("SELECT count(*) FROM conversations WHERE CAST(context AS TEXT) != '{}'")
    ).scalar():
        raise RuntimeError("Export conversation context and shipment evidence before downgrade; nothing removed")
    op.drop_table("shipment_events")
    op.drop_column("conversations", "context")
