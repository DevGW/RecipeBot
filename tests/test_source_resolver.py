"""Tests for resolving Reddit command parents into recipe sources."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.reddit.source_resolver import resolve_recipe_source


def test_resolve_parent_comment() -> None:
    """A command reply to a comment should use that comment as the recipe source."""
    submission = SimpleNamespace(title="Grandma's Soup")
    parent = SimpleNamespace(
        name="t1_parent",
        body="Ingredients:\n- stock",
        subreddit=SimpleNamespace(display_name="recipes"),
        author=SimpleNamespace(name="cook"),
        permalink="/r/recipes/comments/abc/post/parent/",
        created_utc=1_700_000_000,
        submission=submission,
    )
    command = SimpleNamespace(parent=lambda: parent)

    source = resolve_recipe_source(command)

    assert source.reddit_fullname == "t1_parent"
    assert source.source_type == "comment"
    assert source.title == "Grandma's Soup"
    assert source.body.startswith("Ingredients")
    assert source.url is None
    assert source.permalink.startswith("https://www.reddit.com/")
    assert source.created_utc == datetime.fromtimestamp(1_700_000_000, timezone.utc)


def test_resolve_parent_submission() -> None:
    """A top-level command should use its parent submission as the recipe source."""
    parent = SimpleNamespace(
        name="t3_parent",
        title="Crispy Potatoes",
        selftext="Ingredients:\n- potatoes\nDirections:\n1. Roast.",
        subreddit=SimpleNamespace(display_name="cooking"),
        author=SimpleNamespace(name="roaster"),
        permalink="/r/cooking/comments/xyz/crispy_potatoes/",
        url="https://www.reddit.com/r/cooking/comments/xyz/crispy_potatoes/",
        created_utc=None,
    )
    command = SimpleNamespace(parent=lambda: parent)

    source = resolve_recipe_source(command)

    assert source.reddit_fullname == "t3_parent"
    assert source.source_type == "submission"
    assert source.subreddit == "cooking"
    assert source.author == "roaster"
    assert source.title == "Crispy Potatoes"
    assert source.url == parent.url
    assert source.created_utc is None
