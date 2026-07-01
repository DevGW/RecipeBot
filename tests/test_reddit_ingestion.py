"""Tests for Reddit command ingestion orchestration."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.models import Job, Recipe, SourceItem, Subreddit, User
from app.jobs.states import JobState
from app.recipes.extractor import ExtractedRecipe
from app.reddit.ingestion import ingest_command_comment
from app.reddit.source_resolver import RedditSource


def _command_comment() -> SimpleNamespace:
    return SimpleNamespace(
        name="t1_command",
        body="!recipecard",
        author=SimpleNamespace(name="reader"),
        removed_by_category=None,
    )


def _source() -> RedditSource:
    return RedditSource(
        reddit_fullname="t3_source",
        source_type="submission",
        subreddit="recipes",
        author="cook",
        permalink="https://www.reddit.com/r/recipes/comments/source",
        title="Tomato Toast",
        body="Ingredients:\n- bread\nDirections:\n1. Toast.",
        url="https://www.reddit.com/r/recipes/comments/source",
        created_utc=None,
    )


def test_ingestion_creates_source_recipe_and_queued_job() -> None:
    """A valid command should persist normalized records and queue one durable job."""
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    settings = Settings(
        _env_file=None,
        REDDIT_USERNAME="recipebot",
        REDDIT_DRY_RUN=True,
    )
    source = _source()
    extracted = ExtractedRecipe(
        title="Tomato Toast",
        ingredients=["bread"],
        instructions=["Toast."],
    )
    subreddit = Subreddit(id=1, name="recipes", enabled=True)
    user = User(id=2, reddit_username="cook")
    source_item = SourceItem(
        id=3,
        reddit_fullname="t3_source",
        item_type="submission",
        permalink=source.permalink,
        subreddit_id=1,
        raw_data={},
    )
    recipe = Recipe(
        id=4,
        source_item_id=3,
        title="Tomato Toast",
        slug="tomato-toast",
        spec_data={},
    )
    job = Job(id=5, command_comment_id="t1_command", status=JobState.QUEUED.value)

    with (
        patch("app.reddit.ingestion.resolve_recipe_source", return_value=source),
        patch("app.reddit.ingestion.extract_recipe", return_value=extracted),
        patch("app.reddit.ingestion._upsert_subreddit", return_value=subreddit) as add_subreddit,
        patch("app.reddit.ingestion._upsert_user", return_value=user) as add_user,
        patch("app.reddit.ingestion._upsert_source_item", return_value=source_item) as add_source,
        patch("app.reddit.ingestion._upsert_recipe", return_value=recipe) as add_recipe,
        patch("app.reddit.ingestion.create_job", return_value=job) as add_job,
    ):
        result = ingest_command_comment(session, _command_comment(), settings)

    assert result is job
    add_subreddit.assert_called_once_with(session, "recipes")
    add_user.assert_called_once_with(session, "cook")
    add_source.assert_called_once_with(session, source, subreddit, user)
    add_recipe.assert_called_once_with(session, source_item, source, extracted)
    add_job.assert_called_once_with(session, "t1_command", 3)


def test_duplicate_command_returns_existing_job_without_new_records() -> None:
    """An existing command id should not create another source, recipe, or job."""
    session = MagicMock(spec=Session)
    existing = Job(id=8, command_comment_id="t1_command", status=JobState.QUEUED.value)
    session.scalar.return_value = existing
    settings = Settings(_env_file=None)

    with (
        patch("app.reddit.ingestion.resolve_recipe_source") as resolve_source,
        patch("app.reddit.ingestion.create_job") as create_new_job,
    ):
        result = ingest_command_comment(session, _command_comment(), settings)

    assert result is existing
    resolve_source.assert_not_called()
    create_new_job.assert_not_called()
