"""Safe ImageMagick subprocess helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


def svg_to_png_command(binary: str, source: Path, destination: Path) -> list[str]:
    """Build the ImageMagick command used to rasterize an SVG."""
    return [
        binary,
        "-background",
        "white",
        "-density",
        "144",
        str(source),
        "-strip",
        str(destination),
    ]


def png_to_pdf_command(binary: str, source: Path, destination: Path) -> list[str]:
    """Build the ImageMagick command used to wrap a PNG in a PDF."""
    return [binary, str(source), "-units", "PixelsPerInch", "-density", "144", str(destination)]


def render_svg_to_png(
    source: Path,
    destination: Path,
    *,
    binary: str = "magick",
) -> None:
    """Render an SVG file to PNG with ImageMagick and fail on conversion errors."""
    subprocess.run(svg_to_png_command(binary, source, destination), check=True)


def render_png_to_pdf(
    source: Path,
    destination: Path,
    *,
    binary: str = "magick",
) -> None:
    """Render a PNG file to PDF with ImageMagick and fail on conversion errors."""
    subprocess.run(png_to_pdf_command(binary, source, destination), check=True)
