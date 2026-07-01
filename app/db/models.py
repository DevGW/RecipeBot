"""SQLAlchemy models for RecipeBot's Postgres persistence layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all RecipeBot database models."""


class TimestampMixin:
    """Provide server-managed creation and update timestamps."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    """A Reddit user observed by the bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reddit_username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class Subreddit(TimestampMixin, Base):
    """A subreddit configured or observed by the bot."""

    __tablename__ = "subreddits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)


class SourceItem(TimestampMixin, Base):
    """A Reddit post or comment containing source recipe material."""

    __tablename__ = "source_items"
    __table_args__ = (
        UniqueConstraint("reddit_fullname", name="uq_source_items_reddit_fullname"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reddit_fullname: Mapped[str] = mapped_column(String(32), nullable=False)
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)
    permalink: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    subreddit_id: Mapped[int] = mapped_column(ForeignKey("subreddits.id"), nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    author: Mapped[User | None] = relationship()
    subreddit: Mapped[Subreddit] = relationship()


class Recipe(TimestampMixin, Base):
    """A normalized recipe extracted from one source item."""

    __tablename__ = "recipes"
    __table_args__ = (UniqueConstraint("source_item_id", name="uq_recipes_source_item_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_item_id: Mapped[int] = mapped_column(ForeignKey("source_items.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    spec_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    source_item: Mapped[SourceItem] = relationship()


class Card(TimestampMixin, Base):
    """A rendered version of a recipe card and its artifact locations."""

    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("recipe_id", "render_version", name="uq_cards_recipe_render_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    render_version: Mapped[str] = mapped_column(String(32), nullable=False)
    svg_path: Mapped[str] = mapped_column(Text, nullable=False)
    png_path: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_path: Mapped[str] = mapped_column(Text, nullable=False)

    recipe: Mapped[Recipe] = relationship()


class Job(TimestampMixin, Base):
    """A durable record of a requested recipe-card operation."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("command_comment_id", name="uq_jobs_command_comment_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    command_comment_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_item_id: Mapped[int | None] = mapped_column(ForeignKey("source_items.id"))
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"))
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source_item: Mapped[SourceItem | None] = relationship()
    card: Mapped[Card | None] = relationship()


class Message(TimestampMixin, Base):
    """An inbound or outbound bot message retained for auditability."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    reddit_fullname: Mapped[str | None] = mapped_column(String(32), unique=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    job: Mapped[Job | None] = relationship()
