"""Environment-backed application configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an optional ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        enable_decoding=False,
    )

    database_url: str = Field(
        default="postgresql+psycopg://recipebot:recipebot@localhost:5432/recipebot",
        validation_alias="DATABASE_URL",
    )
    bot_enabled: bool = Field(default=False, validation_alias="BOT_ENABLED")
    enabled_subreddits: list[str] = Field(
        default_factory=list,
        validation_alias="ENABLED_SUBREDDITS",
    )
    allow_source_images: bool = Field(default=False, validation_alias="ALLOW_SOURCE_IMAGES")
    max_source_images: int = Field(default=4, ge=0, validation_alias="MAX_SOURCE_IMAGES")
    artifact_root: Path = Field(default=Path("artifacts"), validation_alias="ARTIFACT_ROOT")
    artifact_base_url: str = Field(
        default="http://localhost:8000/cards",
        validation_alias="ARTIFACT_BASE_URL",
    )
    imagemagick_binary: str = Field(default="magick", validation_alias="IMAGEMAGICK_BINARY")
    rsvg_convert_binary: str = Field(
        default="rsvg-convert",
        validation_alias="RSVG_CONVERT_BINARY",
    )
    web_host: str = Field(default="127.0.0.1", validation_alias="WEB_HOST")
    web_port: int = Field(default=8000, ge=1, le=65535, validation_alias="WEB_PORT")
    devvit_ingestion_enabled: bool = Field(
        default=False,
        validation_alias="DEVVIT_INGESTION_ENABLED",
    )
    devvit_webhook_secret: str | None = Field(
        default=None,
        validation_alias="DEVVIT_WEBHOOK_SECRET",
    )
    devvit_require_hmac: bool = Field(
        default=True,
        validation_alias="DEVVIT_REQUIRE_HMAC",
    )
    devvit_signature_tolerance_seconds: int = Field(
        default=300,
        ge=1,
        validation_alias="DEVVIT_SIGNATURE_TOLERANCE_SECONDS",
    )
    reddit_client_id: str | None = Field(default=None, validation_alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str | None = Field(
        default=None,
        validation_alias="REDDIT_CLIENT_SECRET",
    )
    reddit_username: str | None = Field(default=None, validation_alias="REDDIT_USERNAME")
    reddit_password: str | None = Field(default=None, validation_alias="REDDIT_PASSWORD")
    reddit_user_agent: str = Field(
        default="RecipeBot/0.1 by an-unconfigured-user",
        validation_alias="REDDIT_USER_AGENT",
    )
    reddit_command: str = Field(default="!recipecard", validation_alias="REDDIT_COMMAND")
    reddit_dry_run: bool = Field(default=True, validation_alias="REDDIT_DRY_RUN")
    reddit_dm_results: bool = Field(default=True, validation_alias="REDDIT_DM_RESULTS")
    reddit_public_fallback_on_dm_failure: bool = Field(
        default=False,
        validation_alias="REDDIT_PUBLIC_FALLBACK_ON_DM_FAILURE",
    )
    reddit_public_ack_on_queue: bool = Field(
        default=False,
        validation_alias="REDDIT_PUBLIC_ACK_ON_QUEUE",
    )

    @field_validator("enabled_subreddits", mode="before")
    @classmethod
    def parse_enabled_subreddits(cls, value: Any) -> Any:
        """Accept either a JSON array or a comma-separated subreddit list."""
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            return json.loads(stripped)
        return [item.strip() for item in stripped.split(",") if item.strip()]


def get_settings() -> Settings:
    """Create a fresh settings instance from the current environment."""
    return Settings()
