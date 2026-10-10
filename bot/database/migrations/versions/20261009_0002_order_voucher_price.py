from alembic import op

revision = "20261009_0002"
down_revision = "20260513_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS voucher_total_price NUMERIC(12, 4)"
    )
    op.execute(
        "ALTER TABLE virtual_number_orders ADD COLUMN IF NOT EXISTS voucher_total_price NUMERIC(10, 4)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS voucher_total_price")
    op.execute("ALTER TABLE virtual_number_orders DROP COLUMN IF EXISTS voucher_total_price")