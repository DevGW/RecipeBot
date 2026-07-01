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

    settings = Settings(_env_file=None)

    assert settings.database_url.endswith("@db/recipes")
    assert settings.bot_enabled is True
    assert settings.enabled_subreddits == ["recipes", "cooking"]
    assert settings.allow_source_images is True
    assert settings.max_source_images == 2
    assert str(settings.artifact_root) == "/tmp/recipebot-artifacts"
    assert settings.artifact_base_url == "https://cards.example.test"
    assert settings.imagemagick_binary == "/usr/local/bin/magick"


def test_settings_accept_json_subreddit_list(monkeypatch) -> None:
    """JSON arrays should also be accepted for list-valued environment settings."""
    monkeypatch.setenv("ENABLED_SUBREDDITS", '["recipes", "baking"]')

    assert Settings(_env_file=None).enabled_subreddits == ["recipes", "baking"]
