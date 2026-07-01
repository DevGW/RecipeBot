"""FastAPI delivery service for completed recipe cards."""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.config.settings import Settings, get_settings
from app.db.models import Card
from app.db.session import build_session_factory
from app.storage.artifacts import ArtifactPaths, read_metadata, resolve_card_artifacts

CardLoader = Callable[[int], Card | None]


def create_app(
    settings: Settings | None = None,
    *,
    card_loader: CardLoader | None = None,
) -> FastAPI:
    """Create the card delivery application with injectable database access."""
    resolved_settings = settings or get_settings()
    load_card = card_loader or _database_card_loader(resolved_settings)
    application = FastAPI(title="RecipeBot", docs_url=None, redoc_url=None)

    def load_paths(card_id: int) -> ArtifactPaths:
        """Load and validate the filesystem paths for one card."""
        card = load_card(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="card not found")
        try:
            return resolve_card_artifacts(resolved_settings.artifact_root, card_id, card)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="card artifacts not found") from error

    def file_response(card_id: int, filename: str, media_type: str) -> FileResponse:
        """Build a response for one fixed artifact filename."""
        paths = load_paths(card_id)
        artifact = {
            "card.png": paths.png,
            "card.svg": paths.svg,
            "card.pdf": paths.pdf,
            "recipe-card.zip": paths.zip,
        }[filename]
        if not artifact.is_file():
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(artifact, media_type=media_type, filename=filename)

    @application.api_route("/health", methods=["GET", "HEAD"])
    def health() -> dict[str, str]:
        """Report that the HTTP process is ready to serve requests."""
        return {"status": "ok"}

    @application.get("/cards/{card_id}", response_class=HTMLResponse)
    def card_landing_page(card_id: int) -> HTMLResponse:
        """Show a plain HTML preview and download page for a completed card."""
        paths = load_paths(card_id)
        try:
            metadata = read_metadata(paths)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="card metadata not found") from error

        title = escape(str(metadata.get("title") or "Recipe card"))
        source_url = metadata.get("source_url")
        source_link = ""
        if isinstance(source_url, str) and _is_reddit_url(source_url):
            safe_source_url = escape(source_url, quote=True)
            source_link = (
                f'<p class="source"><a href="{safe_source_url}" rel="noopener noreferrer">'
                "View source on Reddit</a></p>"
            )
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · RecipeBot</title>
  <style>
    body {{ margin: 0 auto; max-width: 960px; padding: 32px 20px 64px;
            background: #fffdf8; color: #23211f; font-family: system-ui, sans-serif; }}
    h1 {{ font-size: clamp(2rem, 5vw, 3.5rem); margin-bottom: 20px; }}
    img {{ display: block; width: 100%; height: auto; border: 1px solid #ddd4c8;
           box-shadow: 0 12px 36px rgba(55, 45, 35, 0.12); }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 24px 0; }}
    a {{ color: #7b4028; font-weight: 650; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <nav aria-label="Card downloads">
    <a href="/cards/{card_id}/card.png">PNG</a>
    <a href="/cards/{card_id}/card.svg">SVG</a>
    <a href="/cards/{card_id}/card.pdf">PDF</a>
    <a href="/cards/{card_id}/recipe-card.zip">ZIP bundle</a>
  </nav>
  {source_link}
  <img src="/cards/{card_id}/card.png" alt="{title} recipe card preview">
</body>
</html>
"""
        return HTMLResponse(html)

    @application.get("/cards/{card_id}/card.png")
    def card_png(card_id: int) -> FileResponse:
        """Return the rendered PNG preview for a card."""
        return file_response(card_id, "card.png", "image/png")

    @application.get("/cards/{card_id}/card.svg")
    def card_svg(card_id: int) -> FileResponse:
        """Return the vector SVG artifact for a card."""
        return file_response(card_id, "card.svg", "image/svg+xml")

    @application.get("/cards/{card_id}/card.pdf")
    def card_pdf(card_id: int) -> FileResponse:
        """Return the printable PDF artifact for a card."""
        return file_response(card_id, "card.pdf", "application/pdf")

    @application.get("/cards/{card_id}/recipe-card.zip")
    def card_zip(card_id: int) -> FileResponse:
        """Return the complete downloadable artifact bundle for a card."""
        return file_response(card_id, "recipe-card.zip", "application/zip")

    return application


def _database_card_loader(settings: Settings) -> CardLoader:
    session_factory = build_session_factory(settings.database_url)

    def load_card(card_id: int) -> Card | None:
        """Load one card in a short-lived database session."""
        with session_factory() as session:
            return session.get(Card, card_id)

    return load_card


def _is_reddit_url(value: str) -> bool:
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    return parsed.scheme in {"http", "https"} and (
        hostname == "reddit.com" or hostname.endswith(".reddit.com")
    )


app = create_app()
