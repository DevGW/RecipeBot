"""Recipe slug utilities."""

from __future__ import annotations

import re
import unicodedata


def make_slug(value: str) -> str:
    """Convert a recipe title into a stable lowercase ASCII slug."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or "recipe"
