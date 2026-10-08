from alembic import op

from bot.database.models import Base

revision = "20260513_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)

    for statement in (
        "ALTER TYPE depositstatus ADD VALUE IF NOT EXISTS 'VERIFYING'",
        "ALTER TYPE depositstatus ADD VALUE IF NOT EXISTS 'REVIEW'",
        "ALTER TYPE depositstatus ADD VALUE IF NOT EXISTS 'CANCELLED'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(5) DEFAULT 'es'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_spent NUMERIC(12, 4) DEFAULT 0.0000",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS warranty_hours INTEGER DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS provider_order_id VARCHAR(128)",
        "ALTER TABLE stock_alerts ADD COLUMN IF NOT EXISTS product_name VARCHAR(255)",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS log_message_id BIGINT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_vip BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_expires_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_warned_24h BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_warned_2h BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS active_coupon_code VARCHAR(32)",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS verification_started_at TIMESTAMP",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS auto_monitor BOOLEAN DEFAULT FALSE NOT NULL",
        "UPDATE deposits SET auto_monitor = TRUE WHERE status = 'PENDING' AND expires_at > CURRENT_TIMESTAMP",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS user_message_id BIGINT",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS user_message_is_media BOOLEAN DEFAULT FALSE NOT NULL",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS block_number BIGINT",
        "ALTER TABLE users ALTER COLUMN balance TYPE NUMERIC(16, 8)",
        "ALTER TABLE deposits ALTER COLUMN exact_amount TYPE NUMERIC(16, 8)",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS referral_commission_amount NUMERIC(16, 8) DEFAULT 0.00000000 NOT NULL",
        "ALTER TABLE deposits ALTER COLUMN referral_commission_amount TYPE NUMERIC(16, 8)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS provider_note TEXT DEFAULT '' NOT NULL",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'COMPLETED' NOT NULL",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(16) DEFAULT 'bot' NOT NULL",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS rating INTEGER DEFAULT NULL",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS voucher_message_id BIGINT DEFAULT NULL",
        "ALTER TABLE virtual_number_orders ADD COLUMN IF NOT EXISTS voucher_message_id BIGINT DEFAULT NULL",
        "ALTER TABLE virtual_number_orders ADD COLUMN IF NOT EXISTS rating INTEGER DEFAULT NULL",
        "ALTER TABLE virtual_number_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(16) DEFAULT 'bot'",
        "ALTER TABLE virtual_number_orders ALTER COLUMN fivesim_order_id DROP NOT NULL",
        "ALTER TABLE virtual_number_orders ALTER COLUMN phone DROP NOT NULL",
        "ALTER TABLE virtual_number_orders ALTER COLUMN status SET DEFAULT 'PROCESSING'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE",
        "ALTER TABLE ticket_messages ADD COLUMN IF NOT EXISTS admin_notification_pending BOOLEAN DEFAULT FALSE NOT NULL",
        "ALTER TABLE ticket_messages ADD COLUMN IF NOT EXISTS admin_notification_kind VARCHAR(16)",
        "ALTER TABLE ticket_messages ADD COLUMN IF NOT EXISTS user_notification_pending BOOLEAN DEFAULT FALSE NOT NULL",
    ):
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("El baseline no es reversible porque eliminaría datos de producción")