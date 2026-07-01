"""Safe librsvg and ImageMagick subprocess helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def svg_to_png_command(binary: str, source: Path, destination: Path) -> list[str]:
    """Build the rsvg-convert command used to rasterize an SVG."""
    return [
        binary,
        "--format",
        "png",
        "--background-color",
        "white",
        "--output",
        str(destination),
        str(source),
    ]


def png_to_pdf_command(binary: str, source: Path, destination: Path) -> list[str]:
    """Build the ImageMagick command used to wrap a PNG in a PDF."""
    return [binary, str(source), "-units", "PixelsPerInch", "-density", "144", str(destination)]


def render_svg_to_png(
    source: Path,
    destination: Path,
    *,
    binary: str = "rsvg-convert",
) -> None:
    """Render an SVG to PNG with rsvg-convert and preserve diagnostic output."""
    _run_command(
        svg_to_png_command(binary, source, destination),
        missing_error="rsvg-convert is required for SVG rasterization",
    )


def render_png_to_pdf(
    source: Path,
    destination: Path,
    *,
    binary: str = "magick",
) -> None:
    """Render a PNG to PDF with ImageMagick and preserve diagnostic output."""
    _run_command(
        png_to_pdf_command(binary, source, destination),
        missing_error=f"ImageMagick binary is unavailable: {binary}",
    )


def _run_command(command: list[str], *, missing_error: str) -> None:
    if shutil.which(command[0]) is None:
        raise RuntimeError(missing_error)
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError(missing_error) from error
    except subprocess.CalledProcessError as error:
        stdout = (error.stdout or "").strip() or "<empty>"
        stderr = (error.stderr or "").strip() or "<empty>"
        raise RuntimeError(
            f"render command failed ({error.returncode}): {' '.join(command)}; "
            f"stdout: {stdout}; stderr: {stderr}"
        ) from error
