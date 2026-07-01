"""Flask delivery service for completed recipe cards."""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from urllib.parse import urlsplit

from flask import Flask, Response, abort, jsonify, send_file

from app.config.settings import Settings, get_settings
from app.db.models import Card
from app.db.session import build_session_factory
from app.storage.artifacts import ArtifactPaths, read_metadata, resolve_card_artifacts

CardLoader = Callable[[int], Card | None]


def create_app(
    settings: Settings | None = None,
    *,
    card_loader: CardLoader | None = None,
) -> Flask:
    """Create the Flask card-delivery application with injectable database access."""
    resolved_settings = settings or get_settings()
    load_card = card_loader or _database_card_loader(resolved_settings)
    application = Flask(__name__)

    def load_paths(card_id: int) -> ArtifactPaths:
        """Load and validate the filesystem paths for one card."""
        card = load_card(card_id)
        if card is None:
            abort(404)
        try:
            return resolve_card_artifacts(resolved_settings.artifact_root, card_id, card)
        except ValueError:
            abort(404)

    def file_response(card_id: int, filename: str, media_type: str) -> Response:
        """Build a response for one fixed artifact filename."""
        paths = load_paths(card_id)
        artifact = {
            "card.png": paths.png,
            "card.svg": paths.svg,
            "card.pdf": paths.pdf,
            "recipe-card.zip": paths.zip,
        }[filename]
        if not artifact.is_file():
            abort(404)
        return send_file(
            artifact,
            mimetype=media_type,
            as_attachment=False,
            download_name=filename,
            conditional=True,
        )

    @application.route("/health", methods=["GET", "HEAD"])
    def health() -> Response:
        """Report that the HTTP process is ready to serve requests."""
        return jsonify(status="ok")

    @application.route("/cards/<int:card_id>", methods=["GET", "HEAD"])
    def card_landing_page(card_id: int) -> Response:
        """Show a plain HTML preview and download page for a completed card."""
        paths = load_paths(card_id)
        try:
            metadata = read_metadata(paths)
        except ValueError:
            abort(404)

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
        return Response(html, mimetype="text/html")

    @application.route("/cards/<int:card_id>/card.png", methods=["GET", "HEAD"])
    def card_png(card_id: int) -> Response:
        """Return the rendered PNG preview for a card."""
        return file_response(card_id, "card.png", "image/png")

    @application.route("/cards/<int:card_id>/card.svg", methods=["GET", "HEAD"])
    def card_svg(card_id: int) -> Response:
        """Return the vector SVG artifact for a card."""
        return file_response(card_id, "card.svg", "image/svg+xml")

    @application.route("/cards/<int:card_id>/card.pdf", methods=["GET", "HEAD"])
    def card_pdf(card_id: int) -> Response:
        """Return the printable PDF artifact for a card."""
        return file_response(card_id, "card.pdf", "application/pdf")

    @application.route(
        "/cards/<int:card_id>/recipe-card.zip",
        methods=["GET", "HEAD"],
    )
    def card_zip(card_id: int) -> Response:
        """Return the complete downloadable artifact bundle for a card."""
        return file_response(card_id, "recipe-card.zip", "application/zip")

    @application.post("/internal/devvit/recipecard")
    def devvit_recipecard() -> Response:
        """Reserve the disabled Devvit ingestion endpoint for a future integration."""
        if not resolved_settings.devvit_ingestion_enabled:
            abort(404)
        response = jsonify(error="Devvit ingestion is not implemented")
        response.status_code = 501
        return response

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
