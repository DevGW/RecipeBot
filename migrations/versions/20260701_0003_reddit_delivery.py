"""Add durable Reddit delivery tracking.

Revision ID: 20260701_0003
Revises: 20260701_0002
"""

from alembic import op
import sqlalchemy as sa

revision = "20260701_0003"
down_revision = "20260701_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add requester identity and delivery-attempt fields."""
    op.add_column("jobs", sa.Column("requester_username", sa.String(length=64)))
    op.add_column("messages", sa.Column("recipient_username", sa.String(length=64)))
    op.add_column("messages", sa.Column("message_type", sa.String(length=32)))
    op.add_column("messages", sa.Column("status", sa.String(length=16)))
    op.add_column("messages", sa.Column("external_message_id", sa.String(length=64)))
    op.add_column("messages", sa.Column("error_message", sa.Text()))
    op.execute(
        "UPDATE messages SET recipient_username = '', message_type = 'dm', status = 'sent'"
    )
    op.alter_column("messages", "recipient_username", nullable=False)
    op.alter_column("messages", "message_type", nullable=False)
    op.alter_column("messages", "status", nullable=False)
    op.create_unique_constraint(
        "uq_messages_job_message_type",
        "messages",
        ["job_id", "message_type"],
    )


def downgrade() -> None:
    """Remove requester identity and delivery-attempt fields."""
    op.drop_constraint("uq_messages_job_message_type", "messages", type_="unique")
    op.drop_column("messages", "error_message")
    op.drop_column("messages", "external_message_id")
    op.drop_column("messages", "status")
    op.drop_column("messages", "message_type")
    op.drop_column("messages", "recipient_username")
    op.drop_column("jobs", "requester_username")
