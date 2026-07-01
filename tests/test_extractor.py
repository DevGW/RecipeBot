"""Tests for deterministic recipe extraction."""

from app.recipes.extractor import extract_recipe


def test_extract_recipe_sections_and_quick_facts() -> None:
    """Explicit ingredients and directions sections should produce structured content."""
    body = """A fast pantry dinner.

Servings: 4
Prep Time: 10 minutes
Cook Time: 20 minutes

## Ingredients
- 12 ounces pasta
- 1 lemon

## Directions
1. Boil the pasta.
2. Toss with lemon.

## Notes
- Reserve a little pasta water.
"""

    recipe = extract_recipe("Lemon Pasta", body)

    assert recipe.title == "Lemon Pasta"
    assert recipe.description == "A fast pantry dinner."
    assert recipe.ingredients == ["12 ounces pasta", "1 lemon"]
    assert recipe.instructions == ["Boil the pasta.", "Toss with lemon."]
    assert recipe.notes == ["Reserve a little pasta water."]
    assert recipe.servings == "4"
    assert recipe.prep_time == "10 minutes"
    assert recipe.cook_time == "20 minutes"
    assert recipe.used_fallback is False


def test_extract_recipe_fallback_preserves_cleaned_text() -> None:
    """Ambiguous source prose should be preserved without inventing recipe structure."""
    recipe = extract_recipe("A family dish", "Mix everything until it looks right.\nServe warm.")

    assert recipe.used_fallback is True
    assert "Mix everything" in recipe.description
    assert recipe.notes == ["Mix everything until it looks right.\nServe warm."]
    assert recipe.ingredients == ["See the source recipe text."]
    assert recipe.to_card_spec("Reddit fixture").slug == "a-family-dish"
