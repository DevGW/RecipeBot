"""Add durable job lifecycle fields.

Revision ID: 20260701_0002
Revises: 20260701_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20260701_0002"
down_revision = "20260701_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add job claim, completion, and rendered-card fields."""
    op.add_column("jobs", sa.Column("card_id", sa.BigInteger(), nullable=True))
    op.add_column("jobs", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_jobs_card_id_cards", "jobs", "cards", ["card_id"], ["id"])
    op.execute("UPDATE jobs SET status = 'queued' WHERE status = 'pending'")


def downgrade() -> None:
    """Remove job lifecycle fields and restore the prior pending state name."""
    op.execute("UPDATE jobs SET status = 'pending' WHERE status = 'queued'")
    op.drop_constraint("fk_jobs_card_id_cards", "jobs", type_="foreignkey")
    op.drop_column("jobs", "finished_at")
    op.drop_column("jobs", "claimed_at")
    op.drop_column("jobs", "card_id")
