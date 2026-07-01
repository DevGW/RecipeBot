"""Database engine and session construction."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_engine(database_url: str) -> Engine:
    """Create a Postgres SQLAlchemy engine for the configured database URL."""
    if not database_url.startswith(("postgresql://", "postgresql+")):
        raise ValueError("RecipeBot requires a PostgreSQL DATABASE_URL")
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    """Create the session factory used by scripts and workers."""
    return sessionmaker(build_engine(database_url), expire_on_commit=False)
