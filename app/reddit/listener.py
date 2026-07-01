"""Resilient allowlisted subreddit comment listener."""

from __future__ import annotations

import logging
import time
from typing import Any

import praw
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, get_settings
from app.db.session import build_session_factory
from app.reddit.client import build_reddit_client
from app.reddit.commands import is_recipe_card_command
from app.reddit.ingestion import ingest_command_comment

logger = logging.getLogger(__name__)


class RedditListener:
    """Watch an explicit subreddit allowlist and ingest exact recipe-card commands."""

    def __init__(
        self,
        reddit: praw.Reddit,
        session_factory: sessionmaker[Session],
        settings: Settings,
    ) -> None:
        """Configure the listener with Reddit, database, and application dependencies."""
        self.reddit = reddit
        self.session_factory = session_factory
        self.settings = settings

    def listen(self) -> None:
        """Consume one PRAW comment stream for the configured subreddit allowlist."""
        selector = self.subreddit_selector()
        logger.info("Listening for %s in r/%s", self.settings.reddit_command, selector)
        subreddit = self.reddit.subreddit(selector)
        for comment in subreddit.stream.comments(skip_existing=True):
            self.process_comment(comment)

    def run_forever(self, retry_delay: float = 5.0) -> None:
        """Restart the Reddit stream after errors without terminating the process."""
        if not self.settings.bot_enabled:
            logger.warning("Reddit listener is disabled; set BOT_ENABLED=true to run it")
            return
        while True:
            try:
                self.listen()
            except Exception:
                logger.exception("Reddit comment stream failed; retrying")
                time.sleep(retry_delay)

    def process_comment(self, comment: Any) -> None:
        """Ingest a matching comment while isolating failures to that comment."""
        if not is_recipe_card_command(
            comment,
            command=self.settings.reddit_command,
            bot_username=self.settings.reddit_username,
        ):
            return
        command_id = getattr(comment, "name", "unknown")
        try:
            with self.session_factory.begin() as session:
                job = ingest_command_comment(session, comment, self.settings)
            if job is not None:
                logger.info("Ingested Reddit command %s as job %s", command_id, job.id)
        except Exception:
            logger.exception("Failed to ingest Reddit command %s", command_id)

    def subreddit_selector(self) -> str:
        """Return the PRAW multi-subreddit selector for the explicit allowlist."""
        names = [name.strip() for name in self.settings.enabled_subreddits if name.strip()]
        if not names:
            raise ValueError("ENABLED_SUBREDDITS must contain at least one subreddit")
        return "+".join(names)


def build_listener(settings: Settings | None = None) -> RedditListener:
    """Build a Reddit listener from environment-backed application settings."""
    resolved_settings = settings or get_settings()
    return RedditListener(
        build_reddit_client(resolved_settings),
        build_session_factory(resolved_settings.database_url),
        resolved_settings,
    )
