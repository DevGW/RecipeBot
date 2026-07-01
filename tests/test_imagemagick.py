"""Tests for safe librsvg and ImageMagick command construction."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.rendering.imagemagick import (
    png_to_pdf_command,
    render_svg_to_png,
    svg_to_png_command,
)


def test_svg_to_png_command_uses_argument_array() -> None:
    """SVG conversion should use a shell-free rsvg-convert argument list."""
    command = svg_to_png_command(
        "rsvg-convert",
        Path("input card.svg"),
        Path("card.png"),
    )

    assert command == [
        "rsvg-convert",
        "--format",
        "png",
        "--background-color",
        "white",
        "--output",
        "card.png",
        "input card.svg",
    ]


def test_png_to_pdf_command_uses_argument_array() -> None:
    """PDF conversion should be represented as a shell-free argument list."""
    assert png_to_pdf_command("magick", Path("card.png"), Path("card.pdf")) == [
        "magick",
        "card.png",
        "-units",
        "PixelsPerInch",
        "-density",
        "144",
        "card.pdf",
    ]


def test_render_does_not_enable_shell() -> None:
    """The conversion runner should never pass a shell invocation option."""
    with (
        patch("app.rendering.imagemagick.shutil.which", return_value="/usr/bin/rsvg-convert"),
        patch("app.rendering.imagemagick.subprocess.run") as run,
    ):
        render_svg_to_png(
            Path("input.svg"),
            Path("output.png"),
            binary="rsvg-convert",
        )

    run.assert_called_once_with(
        svg_to_png_command("rsvg-convert", Path("input.svg"), Path("output.png")),
        check=True,
        capture_output=True,
        text=True,
    )


def test_missing_rsvg_convert_has_clear_error() -> None:
    """A missing rasterizer should fail before conversion with an actionable message."""
    with (
        patch("app.rendering.imagemagick.shutil.which", return_value=None),
        patch("app.rendering.imagemagick.subprocess.run") as run,
        pytest.raises(RuntimeError, match="rsvg-convert is required for SVG rasterization"),
    ):
        render_svg_to_png(Path("input.svg"), Path("output.png"))

    run.assert_not_called()


def test_conversion_error_includes_stdout_and_stderr() -> None:
    """Failed renderer commands should retain both captured diagnostic streams."""
    error = subprocess.CalledProcessError(
        1,
        ["rsvg-convert"],
        output="renderer output",
        stderr="invalid SVG",
    )
    with (
        patch("app.rendering.imagemagick.shutil.which", return_value="/usr/bin/rsvg-convert"),
        patch("app.rendering.imagemagick.subprocess.run", side_effect=error),
        pytest.raises(RuntimeError) as raised,
    ):
        render_svg_to_png(Path("input.svg"), Path("output.png"))

    assert "stdout: renderer output" in str(raised.value)
    assert "stderr: invalid SVG" in str(raised.value)
