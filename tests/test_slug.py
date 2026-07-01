"""Tests for recipe slug generation."""

from app.recipes.slug import make_slug


def test_make_slug_normalizes_title() -> None:
    """Punctuation, accents, and whitespace should produce a URL-safe slug."""
    assert make_slug("  Crème Brûlée (Easy!)  ") == "creme-brulee-easy"


def test_make_slug_has_empty_fallback() -> None:
    """Titles without ASCII word characters should receive a stable fallback."""
    assert make_slug("***") == "recipe"
