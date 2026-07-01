"""Create the initial RecipeBot schema.

Revision ID: 20260701_0001
Revises: None
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260701_0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    """Create all initial persistence tables and constraints."""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("reddit_username", sa.String(length=64), nullable=False, unique=True),
        *_timestamps(),
    )
    op.create_table(
        "subreddits",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_table(
        "source_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("reddit_fullname", sa.String(length=32), nullable=False),
        sa.Column("item_type", sa.String(length=16), nullable=False),
        sa.Column("permalink", sa.Text(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("subreddit_id", sa.BigInteger(), sa.ForeignKey("subreddits.id"), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("reddit_fullname", name="uq_source_items_reddit_fullname"),
    )
    op.create_table(
        "recipes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "source_item_id", sa.BigInteger(), sa.ForeignKey("source_items.id"), nullable=False
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("spec_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("source_item_id", name="uq_recipes_source_item_id"),
    )
    op.create_table(
        "cards",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("recipe_id", sa.BigInteger(), sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("render_version", sa.String(length=32), nullable=False),
        sa.Column("svg_path", sa.Text(), nullable=False),
        sa.Column("png_path", sa.Text(), nullable=False),
        sa.Column("pdf_path", sa.Text(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("recipe_id", "render_version", name="uq_cards_recipe_render_version"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("command_comment_id", sa.String(length=32), nullable=False),
        sa.Column("source_item_id", sa.BigInteger(), sa.ForeignKey("source_items.id")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text()),
        *_timestamps(),
        sa.UniqueConstraint("command_comment_id", name="uq_jobs_command_comment_id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("job_id", sa.BigInteger(), sa.ForeignKey("jobs.id")),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("reddit_fullname", sa.String(length=32), unique=True),
        sa.Column("body", sa.Text(), nullable=False),
        *_timestamps(),
    )


def downgrade() -> None:
    """Drop all initial persistence tables in dependency order."""
    tables = ("messages", "jobs", "cards", "recipes", "source_items", "subreddits", "users")
    for table_name in tables:
        op.drop_table(table_name)
