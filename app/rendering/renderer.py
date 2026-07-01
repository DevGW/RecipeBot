"""Recipe-card rendering orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.rendering.card_spec import RecipeCardSpec
from app.rendering.imagemagick import render_png_to_pdf, render_svg_to_png
from app.rendering.svg_layout import render_recipe_svg


@dataclass(frozen=True)
class RenderedCardPaths:
    """Filesystem paths produced by a completed card render."""

    svg: Path
    png: Path
    pdf: Path


def render_card(
    spec: RecipeCardSpec,
    output_directory: Path,
    *,
    imagemagick_binary: str = "magick",
    rsvg_convert_binary: str = "rsvg-convert",
) -> RenderedCardPaths:
    """Write SVG, PNG, and PDF artifacts for a validated recipe specification."""
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = RenderedCardPaths(
        svg=output_directory / "card.svg",
        png=output_directory / "card.png",
        pdf=output_directory / "card.pdf",
    )
    paths.svg.write_text(render_recipe_svg(spec), encoding="utf-8")
    render_svg_to_png(paths.svg, paths.png, binary=rsvg_convert_binary)
    render_png_to_pdf(paths.png, paths.pdf, binary=imagemagick_binary)
    return paths
