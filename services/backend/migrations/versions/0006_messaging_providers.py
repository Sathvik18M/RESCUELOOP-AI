"""Pin conversations to providers and persist delivery receipts before send completion."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "conversations",
        sa.Column("messaging_provider", sa.String(30), nullable=False, server_default="twilio"),
    )
    op.add_column("conversations", sa.Column("provider_recipient", sa.String(200), nullable=True))
    op.alter_column("customers", "phone", existing_type=sa.String(30), nullable=True)
    op.create_table(
        "delivery_receipts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("merchant_id", sa.String(50), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_id", sa.String(200), nullable=False),
        sa.Column("recipient", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_id", "status", "merchant_id"),
    )
    op.create_index("ix_delivery_receipts_merchant_id", "delivery_receipts", ["merchant_id"])
    op.create_index("ix_delivery_receipts_provider_id", "delivery_receipts", ["provider_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE delivery_receipts ENABLE ROW LEVEL SECURITY")


def downgrade():
    bind = op.get_bind()
    if (
        bind.execute(sa.text("SELECT count(*) FROM delivery_receipts")).scalar()
        or bind.execute(
            sa.text("SELECT count(*) FROM conversations WHERE messaging_provider != 'twilio'")
        ).scalar()
        or bind.execute(sa.text("SELECT count(*) FROM customers WHERE phone IS NULL")).scalar()
    ):
        raise RuntimeError("Export provider-specific records before downgrade; no records removed")
    op.drop_table("delivery_receipts")
    op.drop_column("conversations", "provider_recipient")
    op.drop_column("conversations", "messaging_provider")
    op.alter_column("customers", "phone", existing_type=sa.String(30), nullable=False)
