"""Tests for Devvit persistence orchestration."""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.db.models import Job, Recipe, SourceItem, Subreddit
from app.devvit.contracts import DevvitRecipeCardRequest
from app.devvit.ingestion import ingest_devvit_request
from app.jobs.states import JobState
from app.recipes.extractor import ExtractedRecipe


def _request() -> DevvitRecipeCardRequest:
    return DevvitRecipeCardRequest(
        command_comment_id="t1_command",
        requester_username="example_user",
        subreddit="recipes",
        source_type="comment",
        source_fullname="t1_parent",
        source_title="Tomato Toast",
        source_body="Ingredients:\n- bread\nDirections:\n1. Toast.",
        source_permalink="https://www.reddit.com/r/recipes/comments/example/comment",
        source_url="https://www.reddit.com/r/recipes/comments/example/comment",
        created_utc=1780000000,
    )


def test_ingestion_builds_source_recipe_and_queued_job() -> None:
    """Devvit ingestion must reuse extraction and the durable job service."""
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    payload = _request()
    extracted = ExtractedRecipe(
        title="Tomato Toast",
        ingredients=["bread"],
        instructions=["Toast."],
    )
    subreddit = Subreddit(id=1, name="recipes", enabled=True)
    source_item = SourceItem(
        id=2,
        reddit_fullname="t1_parent",
        item_type="comment",
        permalink=payload.source_permalink,
        subreddit_id=1,
        raw_data={},
    )
    recipe = Recipe(
        id=3,
        source_item_id=2,
        title="Tomato Toast",
        slug="tomato-toast",
        spec_data={},
    )
    job = Job(id=4, command_comment_id="t1_command", status=JobState.QUEUED.value)

    with (
        patch("app.devvit.ingestion.extract_recipe", return_value=extracted) as extract,
        patch("app.devvit.ingestion._upsert_subreddit", return_value=subreddit) as add_subreddit,
        patch("app.devvit.ingestion._upsert_source_item", return_value=source_item) as add_source,
        patch("app.devvit.ingestion._upsert_recipe", return_value=recipe) as add_recipe,
        patch(
            "app.devvit.ingestion.create_job_with_status",
            return_value=(job, True),
        ) as add_job,
    ):
        result = ingest_devvit_request(session, payload)

    assert result.job_id == 4
    assert result.created is True
    assert result.status == JobState.QUEUED.value
    extract.assert_called_once_with(payload.source_title, payload.source_body)
    add_subreddit.assert_called_once_with(session, "recipes")
    add_source.assert_called_once_with(session, payload, subreddit)
    add_recipe.assert_called_once_with(session, source_item, payload, extracted)
    add_job.assert_called_once_with(
        session,
        "t1_command",
        2,
        requester_username="example_user",
    )


def test_ingestion_returns_duplicate_before_upserting_source() -> None:
    """A known command id must return its job without touching source records."""
    session = MagicMock(spec=Session)
    session.scalar.return_value = Job(
        id=9,
        command_comment_id="t1_command",
        status=JobState.QUEUED.value,
    )

    with patch("app.devvit.ingestion.extract_recipe") as extract:
        result = ingest_devvit_request(session, _request())

    assert result.job_id == 9
    assert result.created is False
    assert result.status == JobState.QUEUED.value
    extract.assert_not_called()
