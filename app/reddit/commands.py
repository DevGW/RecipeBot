"""Recognition rules for supported Reddit commands."""

from __future__ import annotations

from typing import Any


def is_recipe_card_command(
    comment: Any,
    *,
    command: str = "!recipecard",
    bot_username: str | None = None,
) -> bool:
    """Return whether a live, non-bot comment contains only the configured command."""
    body = getattr(comment, "body", None)
    if not isinstance(body, str) or body.strip() != command:
        return False
    if body in {"[deleted]", "[removed]"}:
        return False
    if getattr(comment, "removed_by_category", None) is not None:
        return False

    author = getattr(comment, "author", None)
    if author is None:
        return False
    author_name = getattr(author, "name", str(author))
    if bot_username and author_name.casefold() == bot_username.casefold():
        return False
    return True
