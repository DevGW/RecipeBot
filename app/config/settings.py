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
        default="http://localhost:8000/artifacts",
        validation_alias="ARTIFACT_BASE_URL",
    )
    imagemagick_binary: str = Field(default="magick", validation_alias="IMAGEMAGICK_BINARY")

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
