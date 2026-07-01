"""Conservative deterministic extraction of recipe sections from Reddit text."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from app.recipes.slug import make_slug
from app.rendering.card_spec import RecipeCardSpec

SECTION_NAMES = {
    "ingredients": "ingredients",
    "ingredient": "ingredients",
    "instructions": "instructions",
    "directions": "instructions",
    "method": "instructions",
    "steps": "instructions",
    "notes": "notes",
    "tips": "notes",
}
FACT_PATTERNS = {
    "servings": re.compile(r"^(?:serves|servings|yield)\s*:\s*(.+)$", re.IGNORECASE),
    "prep_time": re.compile(r"^prep(?:\s+time)?\s*:\s*(.+)$", re.IGNORECASE),
    "cook_time": re.compile(r"^cook(?:\s+time)?\s*:\s*(.+)$", re.IGNORECASE),
    "recipe_type": re.compile(r"^(?:type|course)\s*:\s*(.+)$", re.IGNORECASE),
}


class ExtractedRecipe(BaseModel):
    """Deterministic recipe data suitable for the existing renderer contract."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str = ""
    ingredients: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    recipe_type: str = "Recipe"
    servings: str = "Not specified"
    prep_time: str = "Not specified"
    cook_time: str = "Not specified"
    used_fallback: bool = False

    def to_card_spec(self, source_label: str) -> RecipeCardSpec:
        """Convert extracted content into the renderer's validated card contract."""
        return RecipeCardSpec(
            title=self.title,
            slug=make_slug(self.title),
            description=self.description,
            source_label=source_label,
            recipe_type=self.recipe_type,
            servings=self.servings,
            prep_time=self.prep_time,
            cook_time=self.cook_time,
            ingredients=self.ingredients,
            instructions=self.instructions,
            notes=self.notes,
            image_paths=[],
        )


def extract_recipe(source_title: str, source_body: str) -> ExtractedRecipe:
    """Extract explicit recipe sections or return a renderer-safe text fallback."""
    title = _clean_title(source_title) or "Untitled Recipe"
    body = _clean_body(source_body)
    sections: dict[str, list[str]] = {
        "preamble": [],
        "ingredients": [],
        "instructions": [],
        "notes": [],
    }
    facts = {
        "recipe_type": "Recipe",
        "servings": "Not specified",
        "prep_time": "Not specified",
        "cook_time": "Not specified",
    }
    current_section = "preamble"
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        heading = _section_heading(stripped)
        if heading is not None:
            current_section = heading
            continue
        fact = _quick_fact(stripped)
        if fact is not None:
            key, value = fact
            facts[key] = value
            continue
        sections[current_section].append(stripped)

    ingredients = [_clean_list_item(item) for item in sections["ingredients"]]
    instructions = [_clean_list_item(item) for item in sections["instructions"]]
    ingredients = [item for item in ingredients if item]
    instructions = [item for item in instructions if item]
    if ingredients and instructions:
        return ExtractedRecipe(
            title=title,
            description="\n".join(sections["preamble"]),
            ingredients=ingredients,
            instructions=instructions,
            notes=[_clean_list_item(item) for item in sections["notes"] if item],
            **facts,
        )

    fallback_text = body or "The source did not include readable recipe text."
    return ExtractedRecipe(
        title=title,
        description=fallback_text[:1200],
        ingredients=["See the source recipe text."],
        instructions=["Refer to the source description and notes for preparation details."],
        notes=[fallback_text],
        used_fallback=True,
        **facts,
    )


def _clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()[:200]


def _clean_body(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.splitlines()).strip()


def _section_heading(value: str) -> str | None:
    normalized = re.sub(r"^[#\s]+|[:\s]+$", "", value).casefold()
    return SECTION_NAMES.get(normalized)


def _quick_fact(value: str) -> tuple[str, str] | None:
    cleaned = re.sub(r"^[-*•]\s*", "", value)
    for key, pattern in FACT_PATTERNS.items():
        match = pattern.match(cleaned)
        if match:
            return key, match.group(1).strip()[:100]
    return None


def _clean_list_item(value: str) -> str:
    return re.sub(r"^(?:[-*•]\s*|\d+[.)]\s*)", "", value).strip()
