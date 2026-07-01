"""Tests for the recipe-card render contract."""

import pytest
from pydantic import ValidationError

from app.rendering.card_spec import RecipeCardSpec


def valid_spec_data() -> dict:
    """Return a minimal valid recipe specification mapping."""
    return {
        "title": "Tomato Toast",
        "slug": "tomato-toast",
        "description": "A quick snack.",
        "source_label": "Static fixture",
        "recipe_type": "Snack",
        "servings": "2",
        "prep_time": "5 minutes",
        "cook_time": "3 minutes",
        "ingredients": ["2 slices bread", "1 tomato"],
        "instructions": ["Toast the bread.", "Top with tomato."],
        "notes": [],
        "image_paths": [],
    }


def test_card_spec_accepts_valid_content() -> None:
    """A complete recipe should satisfy the render contract."""
    spec = RecipeCardSpec.model_validate(valid_spec_data())

    assert spec.slug == "tomato-toast"
    assert len(spec.ingredients) == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [("slug", "Not A Slug"), ("ingredients", []), ("instructions", [""])],
)
def test_card_spec_rejects_invalid_content(field: str, value: object) -> None:
    """Invalid slugs and empty recipe content should be rejected."""
    data = valid_spec_data()
    data[field] = value

    with pytest.raises(ValidationError):
        RecipeCardSpec.model_validate(data)
