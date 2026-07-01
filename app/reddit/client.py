"""Isolated construction of the authenticated PRAW client."""

from __future__ import annotations

import praw

from app.config.settings import Settings


def build_reddit_client(settings: Settings) -> praw.Reddit:
    """Build an authenticated PRAW client from validated application settings."""
    credentials = {
        "REDDIT_CLIENT_ID": settings.reddit_client_id,
        "REDDIT_CLIENT_SECRET": settings.reddit_client_secret,
        "REDDIT_USERNAME": settings.reddit_username,
        "REDDIT_PASSWORD": settings.reddit_password,
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise ValueError(f"missing Reddit settings: {', '.join(missing)}")
    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        username=settings.reddit_username,
        password=settings.reddit_password,
        user_agent=settings.reddit_user_agent,
    )
