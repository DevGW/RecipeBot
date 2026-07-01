"""Tests for environment-backed settings."""

from app.config.settings import Settings


def test_settings_load_from_environment(monkeypatch) -> None:
    """Environment variables should populate typed application settings."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db/recipes")
    monkeypatch.setenv("BOT_ENABLED", "true")
    monkeypatch.setenv("ENABLED_SUBREDDITS", "recipes, cooking")
    monkeypatch.setenv("ALLOW_SOURCE_IMAGES", "1")
    monkeypatch.setenv("MAX_SOURCE_IMAGES", "2")
    monkeypatch.setenv("ARTIFACT_ROOT", "/tmp/recipebot-artifacts")
    monkeypatch.setenv("ARTIFACT_BASE_URL", "https://cards.example.test")
    monkeypatch.setenv("IMAGEMAGICK_BINARY", "/usr/local/bin/magick")
    monkeypatch.setenv("RSVG_CONVERT_BINARY", "/usr/local/bin/rsvg-convert")
    monkeypatch.setenv("WEB_HOST", "0.0.0.0")
    monkeypatch.setenv("WEB_PORT", "8097")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "client-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("REDDIT_USERNAME", "recipebot")
    monkeypatch.setenv("REDDIT_PASSWORD", "password")
    monkeypatch.setenv("REDDIT_USER_AGENT", "RecipeBot tests")
    monkeypatch.setenv("REDDIT_COMMAND", "!recipecard")
    monkeypatch.setenv("REDDIT_DRY_RUN", "true")
    monkeypatch.setenv("REDDIT_DM_RESULTS", "true")
    monkeypatch.setenv("REDDIT_PUBLIC_FALLBACK_ON_DM_FAILURE", "false")
    monkeypatch.setenv("REDDIT_PUBLIC_ACK_ON_QUEUE", "false")

    settings = Settings(_env_file=None)

    assert settings.database_url.endswith("@db/recipes")
    assert settings.bot_enabled is True
    assert settings.enabled_subreddits == ["recipes", "cooking"]
    assert settings.allow_source_images is True
    assert settings.max_source_images == 2
    assert str(settings.artifact_root) == "/tmp/recipebot-artifacts"
    assert settings.artifact_base_url == "https://cards.example.test"
    assert settings.imagemagick_binary == "/usr/local/bin/magick"
    assert settings.rsvg_convert_binary == "/usr/local/bin/rsvg-convert"
    assert settings.web_host == "0.0.0.0"
    assert settings.web_port == 8097
    assert settings.reddit_client_id == "client-id"
    assert settings.reddit_client_secret == "client-secret"
    assert settings.reddit_username == "recipebot"
    assert settings.reddit_password == "password"
    assert settings.reddit_user_agent == "RecipeBot tests"
    assert settings.reddit_command == "!recipecard"
    assert settings.reddit_dry_run is True
    assert settings.reddit_dm_results is True
    assert settings.reddit_public_fallback_on_dm_failure is False
    assert settings.reddit_public_ack_on_queue is False


def test_settings_accept_json_subreddit_list(monkeypatch) -> None:
    """JSON arrays should also be accepted for list-valued environment settings."""
    monkeypatch.setenv("ENABLED_SUBREDDITS", '["recipes", "baking"]')

    assert Settings(_env_file=None).enabled_subreddits == ["recipes", "baking"]
