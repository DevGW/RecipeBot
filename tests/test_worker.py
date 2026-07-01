"""Tests for single-process worker behavior."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config.settings import Settings
from app.db.models import Card, Job
from app.jobs.states import JobState
from app.jobs.worker import JobWorker, main
from app.rendering.card_spec import RecipeCardSpec
from app.rendering.renderer import RenderedCardPaths


def test_worker_run_once_claims_and_processes_one_job() -> None:
    """One worker iteration should process exactly the single claimed job."""
    session_factory = MagicMock()
    session = session_factory.begin.return_value.__enter__.return_value
    renderer = MagicMock()
    settings = Settings(_env_file=None, ARTIFACT_ROOT=Path("artifacts"))
    worker = JobWorker(session_factory, settings, renderer=renderer)
    worker.process_job = MagicMock()
    claimed = Job(id=41, command_comment_id="t1_once", status=JobState.CLAIMED.value)

    with patch("app.jobs.worker.claim_next_queued_job", return_value=claimed):
        processed = worker.run_once()

    assert processed is True
    worker.process_job.assert_called_once_with(41)
    session_factory.begin.assert_called_once_with()


def test_worker_run_once_returns_false_for_empty_queue() -> None:
    """One worker iteration should return promptly when no queued job exists."""
    session_factory = MagicMock()
    worker = JobWorker(session_factory, Settings(_env_file=None), renderer=MagicMock())

    with patch("app.jobs.worker.claim_next_queued_job", return_value=None):
        assert worker.run_once() is False


def test_process_job_orchestrates_mocked_renderer(tmp_path: Path) -> None:
    """Processing should render, store, and complete a claimed job exactly once."""
    session_factory = MagicMock()
    session = session_factory.begin.return_value.__enter__.return_value
    renderer = MagicMock(
        return_value=RenderedCardPaths(
            svg=tmp_path / "card.svg",
            png=tmp_path / "card.png",
            pdf=tmp_path / "card.pdf",
        )
    )
    delivery_service = MagicMock()
    worker = JobWorker(
        session_factory,
        Settings(_env_file=None, ARTIFACT_ROOT=tmp_path),
        renderer=renderer,
        delivery_service=delivery_service,
    )
    spec = RecipeCardSpec(
        title="Worker Soup",
        slug="worker-soup",
        source_label="Test fixture",
        recipe_type="Soup",
        servings="2",
        prep_time="5 minutes",
        cook_time="20 minutes",
        ingredients=["1 cup stock"],
        instructions=["Simmer the stock."],
    )
    card = Card(
        id=12,
        recipe_id=9,
        render_version="1",
        svg_path="card.svg",
        png_path="card.png",
        pdf_path="card.pdf",
    )
    job = Job(id=41, command_comment_id="t1_process", status=JobState.CLAIMED.value)
    worker._load_recipe_spec = MagicMock(
        return_value=(9, spec, "https://reddit.com/r/recipes/comments/example")
    )
    worker._transition = MagicMock()
    worker._store_card = MagicMock(return_value=12)
    worker._require_job = MagicMock(return_value=job)
    session.get.return_value = card

    with (
        patch("app.jobs.worker.create_job_bundle") as create_bundle,
        patch("app.jobs.worker.mark_job_completed") as mark_completed,
    ):
        result = worker.process_job(41)

    assert result is card
    renderer.assert_called_once_with(
        spec,
        tmp_path / "jobs" / "41",
        imagemagick_binary="magick",
    )
    assert [call.args for call in worker._transition.call_args_list] == [
        (41, JobState.RENDERING),
        (41, JobState.STORING),
        (41, JobState.MESSAGING),
    ]
    worker._store_card.assert_called_once_with(41, 9, renderer.return_value)
    create_bundle.assert_called_once_with(
        tmp_path,
        "http://localhost:8000/cards",
        job_id=41,
        card_id=12,
        title="Worker Soup",
        slug="worker-soup",
        source_url="https://reddit.com/r/recipes/comments/example",
    )
    delivery_service.deliver_job.assert_called_once_with(41)
    mark_completed.assert_called_once_with(session, job, card)


def test_worker_cli_once_does_not_start_polling_loop() -> None:
    """The command-line once flag should invoke one iteration without polling."""
    worker = MagicMock()
    with patch("app.jobs.worker.build_worker", return_value=worker):
        result = main(["--once"])

    assert result == 0
    worker.run_once.assert_called_once_with()
    worker.run_forever.assert_not_called()
