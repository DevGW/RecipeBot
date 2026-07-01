"""Tests for the Flask card delivery service."""

from pathlib import Path

from flask.testing import FlaskClient
import pytest

from app.config.settings import Settings
from app.db.models import Card
from app.storage.artifacts import create_job_bundle, resolve_job_artifacts
from app.web.server import create_app


@pytest.fixture
def web_client(tmp_path: Path) -> FlaskClient:
    """Create a Flask client backed by one complete sample artifact bundle."""
    paths = resolve_job_artifacts(tmp_path, 11)
    paths.directory.mkdir(parents=True)
    paths.svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    paths.png.write_bytes(b"sample png")
    paths.pdf.write_bytes(b"sample pdf")
    create_job_bundle(
        tmp_path,
        "http://localhost/cards",
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
        ARTIFACT_BASE_URL="http://localhost/cards",
    )

    def load_test_card(card_id: int) -> Card | None:
        """Return the fixture card for its known id."""
        return card if card_id == 6 else None

    application = create_app(settings, card_loader=load_test_card)
    application.config.update(TESTING=True, TEST_ARTIFACT_DIRECTORY=str(paths.directory))
    return application.test_client()


def test_health_get_and_head(web_client: FlaskClient) -> None:
    """The health route should support local and production readiness checks."""
    get_response = web_client.get("/health")
    head_response = web_client.head("/health")

    assert get_response.status_code == 200
    assert get_response.get_json() == {"status": "ok"}
    assert head_response.status_code == 200
    assert head_response.data == b""


def test_landing_page_get_and_head(web_client: FlaskClient) -> None:
    """The landing page should safely show preview, source, and download links."""
    get_response = web_client.get("/cards/6")
    head_response = web_client.head("/cards/6")
    html = get_response.get_data(as_text=True)

    assert get_response.status_code == 200
    assert "Tomato &amp; &lt;Herb&gt; Toast" in html
    assert '<img src="/cards/6/card.png"' in html
    assert 'href="/cards/6/card.svg"' in html
    assert 'href="/cards/6/card.pdf"' in html
    assert 'href="/cards/6/recipe-card.zip"' in html
    assert "https://reddit.com/r/recipes/comments/example" in html
    assert head_response.status_code == 200
    assert head_response.data == b""


@pytest.mark.parametrize(
    ("route", "media_type"),
    [
        ("card.png", "image/png"),
        ("card.svg", "image/svg+xml"),
        ("card.pdf", "application/pdf"),
        ("recipe-card.zip", "application/zip"),
    ],
)
def test_direct_file_get_and_head(
    web_client: FlaskClient,
    route: str,
    media_type: str,
) -> None:
    """Each known artifact route should support GET and HEAD with its media type."""
    get_response = web_client.get(f"/cards/6/{route}")
    head_response = web_client.head(f"/cards/6/{route}")

    assert get_response.status_code == 200
    assert get_response.content_type.startswith(media_type)
    assert get_response.data
    assert head_response.status_code == 200
    assert head_response.content_type.startswith(media_type)
    assert head_response.data == b""


def test_missing_card_and_artifact_return_not_found(web_client: FlaskClient) -> None:
    """Unknown cards and absent known files should return 404 without path details."""
    assert web_client.get("/cards/999").status_code == 404
    assert web_client.get("/cards/999/card.png").status_code == 404

    artifact_directory = Path(web_client.application.config["TEST_ARTIFACT_DIRECTORY"])
    (artifact_directory / "card.pdf").unlink()
    response = web_client.get("/cards/6/card.pdf")

    assert response.status_code == 404
    assert str(artifact_directory) not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "path",
    [
        "/cards/6/../metadata.json",
        "/cards/6/%2e%2e/metadata.json",
        "/cards/6/card.png/../../metadata.json",
        "/cards/not-an-integer/card.png",
    ],
)
def test_path_traversal_and_invalid_ids_are_blocked(
    web_client: FlaskClient,
    path: str,
) -> None:
    """Only integer card ids and fixed artifact filenames should be routable."""
    assert web_client.get(path).status_code == 404


def test_devvit_endpoint_is_disabled_by_default(web_client: FlaskClient) -> None:
    """The future Devvit ingestion endpoint should be hidden unless explicitly enabled."""
    response = web_client.post("/internal/devvit/recipecard", json={"source": "test"})

    assert response.status_code == 404
