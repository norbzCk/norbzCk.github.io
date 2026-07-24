"""Baseline runtime schema moved from app startup into Alembic.

Revision ID: 20260428_01
Revises:
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa

from backend.models import Base


revision = "20260428_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    statements = [
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS image_url VARCHAR",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS rating_avg DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS rating_count INTEGER DEFAULT 0",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS provider_id INTEGER",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS seller_id INTEGER",
        "ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS phone VARCHAR",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS address VARCHAR",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS profile_photo VARCHAR",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS product_id INTEGER",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'Received'",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS rating INTEGER",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS rated_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS provider_id INTEGER",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS provider_name VARCHAR",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS seller_id INTEGER",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS status_reason VARCHAR",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS delivery_address VARCHAR",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS delivery_phone VARCHAR",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS delivery_notes VARCHAR",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS delivery_method VARCHAR DEFAULT 'Standard'",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS order_id INTEGER",
        "ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS order_item_id INTEGER",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS pickup_lat DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS pickup_lng DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS destination_lat DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS destination_lng DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS current_lat DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS current_lng DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS estimated_distance_km DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS last_location_name VARCHAR",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS tracking_updated_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS picked_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS failure_reason VARCHAR",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS proof_type VARCHAR",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS proof_note TEXT",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS cod_amount_received DOUBLE PRECISION",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS rating INTEGER",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS rated_at TIMESTAMPTZ",
        "ALTER TABLE IF EXISTS delivery_orders ADD COLUMN IF NOT EXISTS rating_comment TEXT",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS auto_confirm BOOLEAN DEFAULT FALSE",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS operating_hours VARCHAR",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS shop_logo_url VARCHAR",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS shop_images VARCHAR",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS website_url VARCHAR",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS social_facebook VARCHAR",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS social_instagram VARCHAR",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS social_whatsapp VARCHAR",
        "ALTER TABLE IF EXISTS business_users ADD COLUMN IF NOT EXISTS social_x VARCHAR",
        "CREATE INDEX IF NOT EXISTS ix_sales_order_id ON sales(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_sales_order_item_id ON sales(order_item_id)",
        "CREATE INDEX IF NOT EXISTS ix_orders_customer_id ON orders(customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(status)",
        "CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_order_status_history_order_id ON order_status_history(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_conversation_threads_order_id ON conversation_threads(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_conversation_messages_thread_id ON conversation_messages(thread_id)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_reservations_order_id ON inventory_reservations(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_shipment_events_delivery_id ON shipment_events(delivery_id)",
        "CREATE INDEX IF NOT EXISTS ix_payment_attempts_order_id ON payment_attempts(order_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs(entity_type)",
    ]

    for statement in statements:
        op.execute(sa.text(statement))


def downgrade() -> None:
    # This baseline migration is intentionally non-destructive.
    pass
