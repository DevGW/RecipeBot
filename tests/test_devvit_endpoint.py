"""Tests for the authenticated Devvit ingestion endpoint."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

from flask import Flask
from flask.testing import FlaskClient
import pytest

from app.config.settings import Settings
from app.devvit.auth import build_signature
from app.devvit.contracts import DevvitIngestionResult, DevvitRecipeCardRequest
from app.web.server import create_app

SECRET = "correct horse battery staple"
ENDPOINT = "/internal/devvit/recipecard"


def _payload(*, source_body: str = "Ingredients:\n- bread\nDirections:\n1. Toast.") -> dict:
    return {
        "command_comment_id": "t1_command",
        "requester_username": "example_user",
        "subreddit": "recipes",
        "source_type": "comment",
        "source_fullname": "t1_parent",
        "source_title": "Tomato Toast",
        "source_body": source_body,
        "source_permalink": "https://www.reddit.com/r/recipes/comments/example/comment",
        "source_url": "https://www.reddit.com/r/recipes/comments/example/comment",
        "created_utc": 1780000000,
    }


@pytest.fixture
def devvit_app(tmp_path: Path) -> tuple[Flask, MagicMock]:
    """Build an enabled Flask app with an isolated ingestion callable."""
    settings = Settings(
        _env_file=None,
        ARTIFACT_ROOT=tmp_path,
        ARTIFACT_BASE_URL="https://recipebot.devgw.com/cards",
        DEVVIT_INGESTION_ENABLED=True,
        DEVVIT_WEBHOOK_SECRET=SECRET,
        DEVVIT_REQUIRE_HMAC=True,
        DEVVIT_SIGNATURE_TOLERANCE_SECONDS=300,
    )
    ingestor = MagicMock(
        return_value=DevvitIngestionResult(job_id=123, created=True, status="queued")
    )
    application = create_app(
        settings,
        card_loader=lambda _card_id: None,
        devvit_ingestor=ingestor,
    )
    application.config.update(TESTING=True)
    return application, ingestor


def _signed_post(
    client: FlaskClient,
    payload: dict,
    *,
    timestamp: str | None = None,
    signature: str | None = None,
):
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    resolved_timestamp = timestamp or str(int(time.time()))
    resolved_signature = signature or build_signature(SECRET, resolved_timestamp, raw_body)
    headers = {
        "X-RecipeBot-Timestamp": resolved_timestamp,
        "X-RecipeBot-Signature": resolved_signature,
        "Content-Type": "application/json",
    }
    return client.post(ENDPOINT, data=raw_body, headers=headers)


def test_missing_timestamp_is_unauthorized(devvit_app: tuple[Flask, MagicMock]) -> None:
    """An enabled endpoint must reject a request without its timestamp header."""
    application, ingestor = devvit_app
    raw_body = json.dumps(_payload()).encode("utf-8")
    response = application.test_client().post(
        ENDPOINT,
        data=raw_body,
        headers={
            "X-RecipeBot-Signature": "0" * 64,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.get_json() == {"ok": False, "error": "invalid_signature"}
    ingestor.assert_not_called()


def test_missing_signature_is_unauthorized(devvit_app: tuple[Flask, MagicMock]) -> None:
    """An enabled endpoint must reject a request without its signature header."""
    application, ingestor = devvit_app
    response = application.test_client().post(
        ENDPOINT,
        data=json.dumps(_payload()),
        headers={
            "X-RecipeBot-Timestamp": str(int(time.time())),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.get_json() == {"ok": False, "error": "invalid_signature"}
    ingestor.assert_not_called()


def test_invalid_signature_is_unauthorized(devvit_app: tuple[Flask, MagicMock]) -> None:
    """A signature not matching the raw request bytes must be rejected."""
    application, ingestor = devvit_app
    response = _signed_post(application.test_client(), _payload(), signature="0" * 64)

    assert response.status_code == 401
    assert response.get_json() == {"ok": False, "error": "invalid_signature"}
    ingestor.assert_not_called()


def test_stale_timestamp_is_unauthorized(devvit_app: tuple[Flask, MagicMock]) -> None:
    """A correctly signed request outside the replay window must be rejected."""
    application, ingestor = devvit_app
    stale_timestamp = str(int(time.time()) - 301)
    response = _signed_post(
        application.test_client(),
        _payload(),
        timestamp=stale_timestamp,
    )

    assert response.status_code == 401
    assert response.get_json() == {"ok": False, "error": "invalid_signature"}
    ingestor.assert_not_called()


def test_valid_hmac_queues_job_and_returns_card_url(
    devvit_app: tuple[Flask, MagicMock],
) -> None:
    """A valid signed request must queue its normalized payload and return its URL."""
    application, ingestor = devvit_app
    response = _signed_post(application.test_client(), _payload())

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "status": "queued",
        "job_id": 123,
        "card_url": "https://recipebot.devgw.com/cards/123",
    }
    submitted = ingestor.call_args.args[0]
    assert isinstance(submitted, DevvitRecipeCardRequest)
    assert submitted.command_comment_id == "t1_command"


def test_duplicate_command_returns_existing_job(
    devvit_app: tuple[Flask, MagicMock],
) -> None:
    """A duplicate command must report the existing durable job."""
    application, ingestor = devvit_app
    ingestor.return_value = DevvitIngestionResult(
        job_id=123,
        created=False,
        status="rendering",
    )

    response = _signed_post(application.test_client(), _payload())

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "status": "existing",
        "job_id": 123,
        "card_url": "https://recipebot.devgw.com/cards/123",
    }


def test_empty_source_body_is_rejected(devvit_app: tuple[Flask, MagicMock]) -> None:
    """Whitespace-only source text must fail validation before database ingestion."""
    application, ingestor = devvit_app
    response = _signed_post(application.test_client(), _payload(source_body="  \n "))

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "invalid_request_body"}
    ingestor.assert_not_called()


def test_ingestion_failure_returns_generic_error(
    devvit_app: tuple[Flask, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Database failures must not expose exception details or secrets to callers."""
    application, ingestor = devvit_app
    ingestor.side_effect = RuntimeError(f"database exploded with {SECRET}")

    with caplog.at_level("ERROR"):
        response = _signed_post(application.test_client(), _payload())

    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "ingestion_failed"}
    assert SECRET not in response.get_data(as_text=True)
    assert SECRET not in caplog.text
