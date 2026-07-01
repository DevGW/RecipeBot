"""Deterministic SVG layout for recipe cards."""

from __future__ import annotations

from html import escape
from pathlib import Path
import textwrap

from app.rendering.card_spec import RecipeCardSpec

CARD_WIDTH = 1700
MARGIN = 120
CONTENT_WIDTH = CARD_WIDTH - (MARGIN * 2)


def _wrap(value: str, width: int) -> list[str]:
    return textwrap.wrap(value, width=width, break_long_words=False, break_on_hyphens=False) or [""]


def _text(x: int, y: int, value: str, css_class: str) -> str:
    return f'<text x="{x}" y="{y}" class="{css_class}">{escape(value)}</text>'


def _section(
    *,
    title: str,
    items: list[str],
    y: int,
    numbered: bool = False,
) -> tuple[list[str], int]:
    elements = [_text(MARGIN, y, title.upper(), "section-label")]
    y += 62
    for index, item in enumerate(items, start=1):
        prefix = f"{index}." if numbered else "•"
        lines = _wrap(item, 78)
        elements.append(_text(MARGIN + 4, y, prefix, "body strong"))
        for line_index, line in enumerate(lines):
            elements.append(_text(MARGIN + 58, y + (line_index * 43), line, "body"))
        y += max(1, len(lines)) * 43 + 20
    return elements, y + 40


def _image_uri(path: Path) -> str:
    try:
        return path.expanduser().resolve().as_uri()
    except ValueError:
        return str(path)


def render_recipe_svg(spec: RecipeCardSpec) -> str:
    """Render a recipe specification into a deterministic, dynamically sized SVG."""
    elements: list[str] = []
    y = 115

    for line_index, line in enumerate(_wrap(spec.title, 29)):
        elements.append(_text(MARGIN, y + (line_index * 76), line, "title"))
    y += len(_wrap(spec.title, 29)) * 76 + 25

    description_lines = _wrap(spec.description, 76) if spec.description else []
    for line_index, line in enumerate(description_lines):
        elements.append(_text(MARGIN, y + (line_index * 43), line, "description"))
    y += len(description_lines) * 43 + (55 if description_lines else 20)

    facts = [
        ("TYPE", spec.recipe_type),
        ("SERVINGS", spec.servings),
        ("PREP", spec.prep_time),
        ("COOK", spec.cook_time),
    ]
    fact_width = CONTENT_WIDTH // len(facts)
    elements.append(
        f'<rect x="{MARGIN}" y="{y}" width="{CONTENT_WIDTH}" height="132" rx="22" class="facts" />'
    )
    for index, (label, value) in enumerate(facts):
        x = MARGIN + (index * fact_width) + 32
        elements.append(_text(x, y + 43, label, "fact-label"))
        elements.append(_text(x, y + 91, value, "fact-value"))
    y += 192

    if spec.image_paths:
        image_href = escape(_image_uri(spec.image_paths[0]), quote=True)
        elements.append(
            f'<image x="{MARGIN}" y="{y}" width="{CONTENT_WIDTH}" height="500" '
            f'href="{image_href}" preserveAspectRatio="xMidYMid slice" />'
        )
        y += 560

    section, y = _section(title="Ingredients", items=spec.ingredients, y=y)
    elements.extend(section)
    section, y = _section(title="Directions", items=spec.instructions, y=y, numbered=True)
    elements.extend(section)
    if spec.notes:
        section, y = _section(title="Notes", items=spec.notes, y=y)
        elements.extend(section)

    footer_y = y + 30
    elements.append(
        f'<line x1="{MARGIN}" y1="{footer_y}" x2="{CARD_WIDTH - MARGIN}" '
        f'y2="{footer_y}" class="rule" />'
    )
    elements.append(_text(MARGIN, footer_y + 62, f"SOURCE  {spec.source_label}", "footer"))
    elements.append(_text(CARD_WIDTH - MARGIN, footer_y + 62, "RECIPEBOT", "footer end"))
    card_height = footer_y + 125

    body = "\n  ".join(elements)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{card_height}"
     viewBox="0 0 {CARD_WIDTH} {card_height}">
  <style>
    .background {{ fill: #fffdf8; }}
    text {{ font-family: "DejaVu Sans", Arial, sans-serif; fill: #23211f; }}
    .title {{ font-size: 68px; font-weight: 700; }}
    .description {{ font-size: 32px; fill: #625e58; }}
    .facts {{ fill: #f0eadf; }}
    .fact-label, .section-label {{
      font-size: 22px; font-weight: 700; letter-spacing: 3px; fill: #8b4f34;
    }}
    .fact-value {{ font-size: 31px; font-weight: 700; }}
    .body {{ font-size: 31px; }}
    .strong {{ font-weight: 700; fill: #8b4f34; }}
    .rule {{ stroke: #d7cec0; stroke-width: 2px; }}
    .footer {{ font-size: 21px; font-weight: 700; letter-spacing: 2px; fill: #746d64; }}
    .end {{ text-anchor: end; }}
  </style>
  <rect width="100%" height="100%" class="background" />
  {body}
</svg>
'''
