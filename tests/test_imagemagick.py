"""Tests for safe ImageMagick command construction."""

from pathlib import Path
from unittest.mock import patch

from app.rendering.imagemagick import (
    png_to_pdf_command,
    render_svg_to_png,
    svg_to_png_command,
)


def test_svg_to_png_command_uses_argument_array() -> None:
    """SVG conversion should be represented as a shell-free argument list."""
    command = svg_to_png_command("magick", Path("input card.svg"), Path("card.png"))

    assert command == [
        "magick",
        "-background",
        "white",
        "-density",
        "144",
        "input card.svg",
        "-strip",
        "card.png",
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
    with patch("app.rendering.imagemagick.subprocess.run") as run:
        render_svg_to_png(Path("input.svg"), Path("output.png"), binary="magick")

    run.assert_called_once_with(
        svg_to_png_command("magick", Path("input.svg"), Path("output.png")),
        check=True,
    )
