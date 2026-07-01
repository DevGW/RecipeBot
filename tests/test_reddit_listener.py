"""Tests for allowlisted Reddit listener behavior."""

from unittest.mock import MagicMock

from app.config.settings import Settings
from app.reddit.listener import RedditListener


def test_listener_builds_selector_only_from_enabled_subreddits() -> None:
    """The PRAW selector should contain exactly the configured subreddit allowlist."""
    listener = RedditListener(
        MagicMock(),
        MagicMock(),
        Settings(_env_file=None, ENABLED_SUBREDDITS="recipes,cooking"),
    )

    assert listener.subreddit_selector() == "recipes+cooking"


def test_listener_streams_only_allowlisted_subreddits() -> None:
    """PRAW should stream new comments only from the combined explicit allowlist."""
    reddit = MagicMock()
    subreddit = reddit.subreddit.return_value
    subreddit.stream.comments.return_value = []
    listener = RedditListener(
        reddit,
        MagicMock(),
        Settings(_env_file=None, ENABLED_SUBREDDITS="recipes,cooking"),
    )

    listener.listen()

    reddit.subreddit.assert_called_once_with("recipes+cooking")
    subreddit.stream.comments.assert_called_once_with(skip_existing=True)
