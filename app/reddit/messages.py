"""Formatting helpers for private and public Reddit delivery messages."""

from pydantic import BaseModel, ConfigDict


class ArtifactLinks(BaseModel):
    """Public links and title needed to format Reddit delivery messages."""

    model_config = ConfigDict(extra="forbid")

    title: str
    landing: str
    png: str
    pdf: str
    svg: str
    zip: str


def format_dm_subject(links: ArtifactLinks) -> str:
    """Format the subject for a completed recipe-card private message."""
    return f"Your RecipeBot card: {links.title}"[:100]


def format_dm_body(links: ArtifactLinks) -> str:
    """Format a Markdown private message containing every completed artifact link."""
    return (
        f"Your recipe card for **{links.title}** is ready.\n\n"
        f"[Open the card landing page]({links.landing})\n\n"
        f"Direct downloads: [PNG]({links.png}) · [PDF]({links.pdf}) · "
        f"[SVG]({links.svg}) · [ZIP bundle]({links.zip})\n\n"
        "— RecipeBot"
    )


def format_public_fallback(links: ArtifactLinks) -> str:
    """Format the short public reply used only after a failed DM."""
    return f"I couldn't send you a private message. Your recipe card is ready: {links.landing}"


def format_queue_acknowledgement() -> str:
    """Format the optional public acknowledgement for a newly queued command."""
    return "Your recipe card request has been queued. I'll send the result by private message."
