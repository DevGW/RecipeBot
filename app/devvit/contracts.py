"""Validated contracts for Devvit recipe-card webhook requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class DevvitRecipeCardRequest(BaseModel):
    """A normalized recipe-card command sent by the Devvit adapter."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command_comment_id: str = Field(min_length=4, max_length=32, pattern=r"^t1_[A-Za-z0-9]+$")
    requester_username: str = Field(min_length=1, max_length=64)
    subreddit: str = Field(min_length=1, max_length=64)
    source_type: Literal["comment", "submission"]
    source_fullname: str = Field(min_length=4, max_length=32)
    source_title: str = Field(default="", max_length=200)
    source_body: str
    source_permalink: str = Field(min_length=1, max_length=2048)
    source_url: str | None = Field(default=None, max_length=2048)
    created_utc: int | None = Field(default=None, ge=0)

    @field_validator("source_body")
    @classmethod
    def reject_empty_source_body(cls, value: str) -> str:
        """Reject source text that is empty after trimming whitespace."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("source_body must not be empty")
        return stripped

    @field_validator("source_fullname")
    @classmethod
    def validate_source_fullname(cls, value: str, info: ValidationInfo) -> str:
        """Require a Reddit fullname prefix matching the declared source type."""
        # Pydantic validates fields in declaration order, so source_type is available here.
        source_type = info.data.get("source_type")
        expected_prefix = "t1_" if source_type == "comment" else "t3_"
        if not value.startswith(expected_prefix) or not value[len(expected_prefix) :].isalnum():
            raise ValueError("source_fullname does not match source_type")
        return value


class DevvitIngestionResult(BaseModel):
    """Describe the durable job selected for one Devvit command."""

    job_id: int = Field(gt=0)
    created: bool
