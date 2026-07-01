"""Tests for exact Reddit command recognition."""

from types import SimpleNamespace

import pytest

from app.reddit.commands import is_recipe_card_command


def _comment(body: str, author: str | None = "reader") -> SimpleNamespace:
    author_object = SimpleNamespace(name=author) if author is not None else None
    return SimpleNamespace(body=body, author=author_object, removed_by_category=None)


def test_exact_recipe_card_command_matches() -> None:
    """The standalone configured command should be accepted."""
    assert is_recipe_card_command(_comment("!recipecard")) is True
    assert is_recipe_card_command(_comment("  !recipecard\n")) is True


@pytest.mark.parametrize(
    "body",
    ["!recipecard --images", "!recipecard please", "prefix!recipecard", "!recipecards"],
)
def test_command_with_flags_or_extra_text_is_ignored(body: str) -> None:
    """Flags, partial words, and surrounding text must not be accepted."""
    assert is_recipe_card_command(_comment(body)) is False


def test_bot_authored_command_is_ignored() -> None:
    """The configured bot account must not ingest its own comments."""
    comment = _comment("!recipecard", author="RecipeBotAccount")

    assert is_recipe_card_command(comment, bot_username="recipebotaccount") is False


def test_deleted_or_removed_command_is_ignored() -> None:
    """Comments without an author or marked as removed should be ignored."""
    assert is_recipe_card_command(_comment("!recipecard", author=None)) is False
    removed = _comment("!recipecard")
    removed.removed_by_category = "moderator"
    assert is_recipe_card_command(removed) is False
