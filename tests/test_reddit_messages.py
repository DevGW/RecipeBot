"""Tests for Reddit delivery message formatting."""

from app.reddit.messages import ArtifactLinks, format_dm_body, format_dm_subject


def test_dm_body_contains_landing_and_every_artifact_link() -> None:
    """The private message should expose the landing page and every direct download."""
    links = ArtifactLinks(
        title="Lemon Pasta",
        landing="https://cards.example/cards/7",
        png="https://cards.example/cards/7/card.png",
        pdf="https://cards.example/cards/7/card.pdf",
        svg="https://cards.example/cards/7/card.svg",
        zip="https://cards.example/cards/7/recipe-card.zip",
    )

    body = format_dm_body(links)

    assert format_dm_subject(links) == "Your RecipeBot card: Lemon Pasta"
    assert "Lemon Pasta" in body
    assert links.landing in body
    assert links.png in body
    assert links.pdf in body
    assert links.svg in body
    assert links.zip in body
