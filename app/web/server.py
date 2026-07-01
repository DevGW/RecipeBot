"""Flask delivery service for completed recipe cards."""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from urllib.parse import urlsplit

from flask import Flask, Response, abort, current_app, jsonify, request, send_file
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, get_settings
from app.db.models import Card
from app.db.session import build_session_factory
from app.devvit.auth import verify_signature
from app.devvit.contracts import DevvitIngestionResult, DevvitRecipeCardRequest
from app.devvit.ingestion import ingest_devvit_request
from app.storage.artifacts import ArtifactPaths, read_metadata, resolve_card_artifacts

CardLoader = Callable[[int], Card | None]
DevvitIngestor = Callable[[DevvitRecipeCardRequest], DevvitIngestionResult]
SessionFactory = sessionmaker[Session]


def create_app(
    settings: Settings | None = None,
    *,
    card_loader: CardLoader | None = None,
    devvit_ingestor: DevvitIngestor | None = None,
) -> Flask:
    """Create the Flask card-delivery application with injectable database access."""
    resolved_settings = settings or get_settings()
    session_factory = None
    if card_loader is None or devvit_ingestor is None:
        session_factory = build_session_factory(resolved_settings.database_url)
    load_card = card_loader or _database_card_loader(session_factory)
    ingest_from_devvit = devvit_ingestor or _database_devvit_ingestor(session_factory)
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

    @application.route("/privacy", methods=["GET", "HEAD"])
    def privacy() -> Response:
        """Return the public RecipeBot privacy policy."""
        return Response(privacy_policy_html(), mimetype="text/html")

    @application.route("/terms", methods=["GET", "HEAD"])
    def terms() -> Response:
        """Return the public RecipeBot terms of use."""
        return Response(terms_of_use_html(), mimetype="text/html")

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
        """Authenticate and queue one normalized recipe-card request from Devvit."""
        if not resolved_settings.devvit_ingestion_enabled:
            abort(404)

        raw_body = request.get_data(cache=True)
        if resolved_settings.devvit_require_hmac and not verify_signature(
            resolved_settings.devvit_webhook_secret,
            request.headers.get("X-RecipeBot-Timestamp"),
            request.headers.get("X-RecipeBot-Signature"),
            raw_body,
            tolerance_seconds=resolved_settings.devvit_signature_tolerance_seconds,
        ):
            response = jsonify(error="unauthorized")
            response.status_code = 401
            return response

        try:
            payload = DevvitRecipeCardRequest.model_validate(request.get_json(silent=True))
        except ValidationError:
            response = jsonify(error="invalid request body")
            response.status_code = 400
            return response

        try:
            result = ingest_from_devvit(payload)
        except Exception as error:
            current_app.logger.error(
                "Devvit recipe-card ingestion failed (%s)",
                type(error).__name__,
            )
            response = jsonify(error="ingestion failed")
            response.status_code = 500
            return response

        card_url = f"{resolved_settings.artifact_base_url.rstrip('/')}/{result.job_id}"
        return jsonify(
            status="queued" if result.created else "existing",
            job_id=result.job_id,
            card_url=card_url,
        )

    return application


def _database_card_loader(session_factory: SessionFactory) -> CardLoader:
    def load_card(card_id: int) -> Card | None:
        """Load one card in a short-lived database session."""
        with session_factory() as session:
            return session.get(Card, card_id)

    return load_card


def _database_devvit_ingestor(session_factory: SessionFactory) -> DevvitIngestor:
    def ingest(payload: DevvitRecipeCardRequest) -> DevvitIngestionResult:
        """Persist one Devvit request in a single database transaction."""
        with session_factory.begin() as session:
            return ingest_devvit_request(session, payload)

    return ingest


def _is_reddit_url(value: str) -> bool:
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    return parsed.scheme in {"http", "https"} and (
        hostname == "reddit.com" or hostname.endswith(".reddit.com")
    )


def _legal_page_html(page_title: str, sections: list[tuple[str, list[str]]]) -> str:
    """Render a simple public legal page using the RecipeBot web style."""
    section_html = []
    for heading, paragraphs in sections:
        paragraph_html = "".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)
        section_html.append(f"<section><h2>{escape(heading)}</h2>{paragraph_html}</section>")
    body = "\n  ".join(section_html)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(page_title)} · RecipeBot</title>
  <style>
    body {{ margin: 0 auto; max-width: 960px; padding: 32px 20px 64px;
            background: #fffdf8; color: #23211f; font-family: system-ui, sans-serif;
            line-height: 1.6; }}
    h1 {{ font-size: clamp(2rem, 5vw, 3rem); margin-bottom: 12px; }}
    h2 {{ font-size: 1.25rem; margin: 28px 0 12px; }}
    p {{ margin: 0 0 14px; }}
    a {{ color: #7b4028; font-weight: 650; }}
    nav {{ margin-bottom: 28px; }}
  </style>
</head>
<body>
  <nav aria-label="RecipeBot legal pages">
    <a href="/privacy">Privacy Policy</a> · <a href="/terms">Terms of Use</a>
  </nav>
  <h1>{escape(page_title)}</h1>
  {body}
</body>
</html>
"""


def privacy_policy_html() -> str:
    """Return the public RecipeBot privacy policy HTML document."""
    return _legal_page_html(
        "Privacy Policy",
        [
            (
                "Overview",
                [
                    (
                        "RecipeBot is a recipe-card service for Reddit communities. "
                        "When a user posts the !recipecard command, RecipeBot receives "
                        "Reddit command metadata and the parent post or comment recipe "
                        "content needed to generate a recipe card artifact."
                    ),
                ],
            ),
            (
                "Data we receive",
                [
                    (
                        "RecipeBot receives Reddit command metadata such as the command "
                        "comment id, requester username, subreddit, source type, source "
                        "fullname, source title, source body, permalink, URL, and creation "
                        "timestamp."
                    ),
                    (
                        "RecipeBot uses that data only to generate recipe card artifacts "
                        "and to operate the service."
                    ),
                ],
            ),
            (
                "Data we store",
                [
                    (
                        "RecipeBot stores job, source, and artifact metadata in PostgreSQL "
                        "so requests can be processed, retried, and served reliably."
                    ),
                    (
                        "Generated recipe card artifacts are hosted publicly under "
                        "/cards/ with a numeric card id and related download routes."
                    ),
                ],
            ),
            (
                "What we do not collect",
                [
                    "RecipeBot does not collect Reddit passwords.",
                    (
                        "RecipeBot does not ask users for Reddit OAuth client secrets "
                        "or other Reddit account credentials."
                    ),
                ],
            ),
            (
                "How we use data",
                [
                    "RecipeBot does not sell user data.",
                    "RecipeBot does not use the data for advertising.",
                    (
                        "RecipeBot does not use tracking, analytics cookies, or third-party "
                        "marketing tools on these public pages."
                    ),
                ],
            ),
            (
                "Removal requests",
                [
                    (
                        "Users and moderators may request removal of generated artifacts "
                        "by contacting the RecipeBot developer through the Reddit app "
                        "listing or Developer Portal contact path."
                    ),
                ],
            ),
        ],
    )


def terms_of_use_html() -> str:
    """Return the public RecipeBot terms of use HTML document."""
    return _legal_page_html(
        "Terms of Use",
        [
            (
                "Service",
                [
                    (
                        "RecipeBot helps Reddit communities turn recipe posts and comments "
                        "into downloadable recipe card artifacts. The service is triggered "
                        "when a user posts the exact !recipecard command on Reddit."
                    ),
                ],
            ),
            (
                "Reddit data used by the service",
                [
                    (
                        "To provide the service, RecipeBot receives Reddit command metadata "
                        "and the parent post or comment recipe content associated with the "
                        "command."
                    ),
                    (
                        "That data is used to generate recipe card artifacts and to store "
                        "job, source, and artifact metadata in PostgreSQL."
                    ),
                ],
            ),
            (
                "Hosted artifacts",
                [
                    (
                        "Completed recipe cards are hosted under /cards/ with a numeric "
                        "card id, along with related PNG, SVG, PDF, and ZIP download routes."
                    ),
                ],
            ),
            (
                "Acceptable use",
                [
                    (
                        "You may use RecipeBot only for lawful purposes and in accordance "
                        "with Reddit's rules and the policies of the communities where the "
                        "app is installed."
                    ),
                    (
                        "Do not attempt to disrupt the service, access non-public endpoints "
                        "without authorization, or misuse generated artifacts."
                    ),
                ],
            ),
            (
                "Accounts and credentials",
                [
                    "RecipeBot does not collect Reddit passwords.",
                    (
                        "RecipeBot does not use Reddit OAuth client secrets provided by users."
                    ),
                ],
            ),
            (
                "Data sharing and advertising",
                [
                    "RecipeBot does not sell user data.",
                    "RecipeBot does not use the data for advertising.",
                ],
            ),
            (
                "Removal requests",
                [
                    (
                        "If you want a generated artifact removed, contact the RecipeBot "
                        "developer through the Reddit app listing or Developer Portal "
                        "contact path."
                    ),
                ],
            ),
            (
                "Changes",
                [
                    (
                        "These terms may be updated as the service evolves. Continued use "
                        "of RecipeBot after changes are posted means you accept the updated "
                        "terms."
                    ),
                ],
            ),
        ],
    )
