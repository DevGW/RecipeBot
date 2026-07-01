"""Tests for durable job service operations."""

from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.db.models import Card, Job
from app.jobs.service import (
    claim_next_queued_job,
    create_job,
    create_job_with_status,
    mark_job_completed,
    mark_job_failed,
)
from app.jobs.states import JobState


def test_create_job_prevents_duplicate_command_comments() -> None:
    """A conflicting command id should return the existing job instead of inserting another."""
    session = MagicMock(spec=Session)
    existing = Job(id=8, command_comment_id="t1_duplicate", status=JobState.QUEUED.value)
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.scalar.return_value = existing

    result = create_job(session, "t1_duplicate", source_item_id=3)
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert result is existing
    assert "ON CONFLICT (command_comment_id) DO NOTHING" in sql
    session.add.assert_not_called()


def test_create_job_with_status_reports_new_insert() -> None:
    """Callers should be able to distinguish a new job from an existing one."""
    session = MagicMock(spec=Session)
    inserted = Job(id=9, command_comment_id="t1_new", status=JobState.QUEUED.value)
    session.execute.return_value.scalar_one_or_none.return_value = inserted

    job, created = create_job_with_status(
        session,
        "t1_new",
        source_item_id=3,
        requester_username="reader",
    )

    assert job is inserted
    assert created is True
    session.scalar.assert_not_called()


def test_claim_uses_oldest_first_order_and_skip_locked() -> None:
    """Claiming should lock only the oldest available queued row."""
    session = MagicMock(spec=Session)
    queued = Job(id=4, command_comment_id="t1_next", status=JobState.QUEUED.value)
    session.scalar.return_value = queued

    result = claim_next_queued_job(session)
    statement = session.scalar.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert result is queued
    assert queued.status == JobState.CLAIMED.value
    assert "ORDER BY jobs.created_at ASC, jobs.id ASC" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    session.flush.assert_called_once_with()


def test_mark_job_failed_records_reason() -> None:
    """Failure updates should retain a reason and terminal timestamp."""
    session = MagicMock(spec=Session)
    job = Job(command_comment_id="t1_failure", status=JobState.RENDERING.value)

    mark_job_failed(session, job, "ImageMagick failed")

    assert job.status == JobState.FAILED.value
    assert job.error_message == "ImageMagick failed"
    assert job.finished_at is not None
    session.flush.assert_called_once_with()


def test_mark_job_completed_links_card() -> None:
    """Completion updates should link the output card and clear prior errors."""
    session = MagicMock(spec=Session)
    job = Job(
        command_comment_id="t1_complete",
        status=JobState.MESSAGING.value,
        error_message="old error",
    )
    card = Card(
        recipe_id=2,
        render_version="1",
        svg_path="card.svg",
        png_path="card.png",
        pdf_path="card.pdf",
    )

    mark_job_completed(session, job, card)

    assert job.status == JobState.COMPLETED.value
    assert job.card is card
    assert job.error_message is None
    assert job.finished_at is not None
    session.flush.assert_called_once_with()
