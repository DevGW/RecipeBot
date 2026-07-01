"""Validated input contract for recipe-card rendering."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecipeCardSpec(BaseModel):
    """Describe all content needed to render one recipe card."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = ""
    source_label: str = Field(min_length=1, max_length=200)
    recipe_type: str = Field(min_length=1, max_length=100)
    servings: str = Field(min_length=1, max_length=100)
    prep_time: str = Field(min_length=1, max_length=100)
    cook_time: str = Field(min_length=1, max_length=100)
    ingredients: list[str] = Field(min_length=1)
    instructions: list[str] = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)
    image_paths: list[Path] = Field(default_factory=list)

    @field_validator("ingredients", "instructions", "notes")
    @classmethod
    def reject_blank_list_items(cls, values: list[str]) -> list[str]:
        """Reject empty content items that would create blank layout rows."""
        if any(not value.strip() for value in values):
            raise ValueError("list items must not be blank")
        return values
