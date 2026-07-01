"""Resolve command comments into normalized Reddit recipe sources."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class RedditSource(BaseModel):
    """Normalized fields extracted from a parent comment or submission."""

    model_config = ConfigDict(extra="forbid")

    reddit_fullname: str
    source_type: Literal["comment", "submission"]
    subreddit: str
    author: str | None
    permalink: str
    title: str
    body: str
    url: str | None
    created_utc: datetime | None


def resolve_recipe_source(command_comment: Any) -> RedditSource:
    """Prefer a parent comment as source, otherwise resolve the parent submission."""
    parent = command_comment.parent()
    fullname = str(getattr(parent, "name", ""))
    if fullname.startswith("t1_"):
        submission = getattr(parent, "submission", None)
        title = str(getattr(submission, "title", "") or "")
        return _source_from_object(parent, "comment", title=title, url=None)
    if fullname.startswith("t3_"):
        return _source_from_object(
            parent,
            "submission",
            title=str(getattr(parent, "title", "") or ""),
            url=_optional_string(getattr(parent, "url", None)),
        )
    raise ValueError("command parent is neither a Reddit comment nor submission")


def _source_from_object(
    source: Any,
    source_type: Literal["comment", "submission"],
    *,
    title: str,
    url: str | None,
) -> RedditSource:
    body_attribute = "body" if source_type == "comment" else "selftext"
    return RedditSource(
        reddit_fullname=str(source.name),
        source_type=source_type,
        subreddit=_subreddit_name(source),
        author=_author_name(getattr(source, "author", None)),
        permalink=_absolute_permalink(str(getattr(source, "permalink", ""))),
        title=title.strip(),
        body=str(getattr(source, body_attribute, "") or "").strip(),
        url=url,
        created_utc=_created_at(getattr(source, "created_utc", None)),
    )


def _subreddit_name(source: Any) -> str:
    subreddit = getattr(source, "subreddit", None)
    name = getattr(subreddit, "display_name", subreddit)
    if not name:
        raise ValueError("source has no subreddit")
    return str(name)


def _author_name(author: Any) -> str | None:
    if author is None:
        return None
    return str(getattr(author, "name", author))


def _absolute_permalink(value: str) -> str:
    if value.startswith("/"):
        return f"https://www.reddit.com{value}"
    return value


def _optional_string(value: Any) -> str | None:
    return str(value) if value else None


def _created_at(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc)
