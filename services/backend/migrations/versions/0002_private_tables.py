"""Keep application tables private when hosted on Supabase's exposed schema."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = (
    "merchants",
    "memberships",
    "customers",
    "products",
    "orders",
    "policies",
    "conversations",
    "messages",
    "cases",
    "pickup_slots",
    "reservations",
    "refunds",
    "evidence",
    "reviews",
    "audit_logs",
    "jobs",
)


def upgrade():
    # Business reads and writes go through FastAPI with a trusted server database role.
    # No browser-facing RLS policies are granted; Supabase anon/authenticated are denied.
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
