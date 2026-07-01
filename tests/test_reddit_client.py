"""Tests for isolated PRAW client construction."""

from unittest.mock import patch

import pytest

from app.config.settings import Settings
from app.reddit.client import build_reddit_client


def test_build_reddit_client_passes_configured_credentials() -> None:
    """PRAW should receive credentials only through the isolated client factory."""
    settings = Settings(
        _env_file=None,
        REDDIT_CLIENT_ID="client-id",
        REDDIT_CLIENT_SECRET="secret",
        REDDIT_USERNAME="recipebot",
        REDDIT_PASSWORD="password",
        REDDIT_USER_AGENT="RecipeBot tests",
    )

    with patch("app.reddit.client.praw.Reddit") as reddit_class:
        result = build_reddit_client(settings)

    assert result is reddit_class.return_value
    reddit_class.assert_called_once_with(
        client_id="client-id",
        client_secret="secret",
        username="recipebot",
        password="password",
        user_agent="RecipeBot tests",
    )


def test_build_reddit_client_rejects_missing_credentials() -> None:
    """Listener startup should fail clearly when authentication settings are absent."""
    with pytest.raises(ValueError, match="REDDIT_CLIENT_ID"):
        build_reddit_client(Settings(_env_file=None))
