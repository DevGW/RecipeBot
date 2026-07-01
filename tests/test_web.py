"""Tests for the FastAPI card delivery service."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.config.settings import Settings
from app.db.models import Card
from app.storage.artifacts import create_job_bundle, resolve_job_artifacts
from app.web.server import create_app


@pytest.fixture
def web_client(tmp_path: Path) -> TestClient:
    """Create a web client backed by one complete sample artifact bundle."""
    paths = resolve_job_artifacts(tmp_path, 11)
    paths.directory.mkdir(parents=True)
    paths.svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    paths.png.write_bytes(b"sample png")
    paths.pdf.write_bytes(b"sample pdf")
    create_job_bundle(
        tmp_path,
        "http://testserver/cards",
        job_id=11,
        card_id=6,
        title="Tomato & <Herb> Toast",
        slug="tomato-herb-toast",
        source_url="https://reddit.com/r/recipes/comments/example",
    )
    card = Card(
        id=6,
        recipe_id=2,
        render_version="1",
        svg_path=str(paths.svg),
        png_path=str(paths.png),
        pdf_path=str(paths.pdf),
    )
    settings = Settings(
        _env_file=None,
        ARTIFACT_ROOT=tmp_path,
        ARTIFACT_BASE_URL="http://testserver/cards",
    )
    def load_test_card(card_id: int) -> Card | None:
        """Return the fixture card for its known id."""
        return card if card_id == 6 else None

    return TestClient(create_app(settings, card_loader=load_test_card))


def test_health_route(web_client: TestClient) -> None:
    """The health route should return a small readiness response."""
    response = web_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_landing_page_shows_preview_and_downloads(web_client: TestClient) -> None:
    """The landing page should safely show title, source, preview, and artifact links."""
    response = web_client.get("/cards/6")

    assert response.status_code == 200
    assert "Tomato &amp; &lt;Herb&gt; Toast" in response.text
    assert '<img src="/cards/6/card.png"' in response.text
    assert 'href="/cards/6/card.svg"' in response.text
    assert 'href="/cards/6/card.pdf"' in response.text
    assert 'href="/cards/6/recipe-card.zip"' in response.text
    assert "https://reddit.com/r/recipes/comments/example" in response.text


@pytest.mark.parametrize(
    ("route", "media_type"),
    [
        ("card.png", "image/png"),
        ("card.svg", "image/svg+xml"),
        ("card.pdf", "application/pdf"),
        ("recipe-card.zip", "application/zip"),
    ],
)
def test_direct_file_routes(web_client: TestClient, route: str, media_type: str) -> None:
    """Each direct artifact route should return the expected content type."""
    response = web_client.get(f"/cards/6/{route}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(media_type)
    assert response.content


def test_unknown_card_returns_not_found(web_client: TestClient) -> None:
    """Unknown card identifiers should not expose any filesystem details."""
    response = web_client.get("/cards/999")

    assert response.status_code == 404
