"""sse notify trigger

Revision ID: 002_sse_notify_trigger
Revises: 001_baseline
Create Date: 2026-04-10
"""
from alembic import op


revision = "002_sse_notify_trigger"
down_revision = "001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_order_update() RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify('order_' || NEW.id, row_to_json(NEW)::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER order_update_notify
            AFTER UPDATE ON orders
            FOR EACH ROW EXECUTE FUNCTION notify_order_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS order_update_notify ON orders;")
    op.execute("DROP FUNCTION IF EXISTS notify_order_update();")
