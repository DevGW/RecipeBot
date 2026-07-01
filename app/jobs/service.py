"""Transactional operations for durable jobs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Card, Job
from app.jobs.states import JobState


def create_job(session: Session, command_comment_id: str, source_item_id: int | None) -> Job:
    """Create a queued job or return the existing job for the same command comment."""
    statement = (
        insert(Job)
        .values(
            command_comment_id=command_comment_id,
            source_item_id=source_item_id,
            status=JobState.QUEUED.value,
        )
        .on_conflict_do_nothing(index_elements=[Job.command_comment_id])
        .returning(Job)
    )
    job = session.execute(statement).scalar_one_or_none()
    if job is not None:
        return job

    existing_job = session.scalar(
        select(Job).where(Job.command_comment_id == command_comment_id)
    )
    if existing_job is None:
        raise RuntimeError("job insert conflicted but the existing job could not be loaded")
    return existing_job


def get_job(session: Session, job_id: int) -> Job | None:
    """Fetch one job by primary key."""
    return session.get(Job, job_id)


def claim_next_queued_job(session: Session) -> Job | None:
    """Claim the oldest queued job while skipping rows locked by other workers."""
    statement = (
        select(Job)
        .where(Job.status == JobState.QUEUED.value)
        .order_by(Job.created_at.asc(), Job.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = session.scalar(statement)
    if job is None:
        return None
    job.status = JobState.CLAIMED.value
    job.claimed_at = datetime.now(timezone.utc)
    job.error_message = None
    session.flush()
    return job


def set_job_state(session: Session, job: Job, state: JobState) -> Job:
    """Move a job to a non-terminal lifecycle state."""
    if state in (JobState.COMPLETED, JobState.FAILED):
        raise ValueError("use the terminal-state helpers for completed or failed jobs")
    job.status = state.value
    session.flush()
    return job


def mark_job_failed(session: Session, job: Job, reason: str) -> Job:
    """Persist a failed terminal state and its diagnostic reason."""
    job.status = JobState.FAILED.value
    job.error_message = reason
    job.finished_at = datetime.now(timezone.utc)
    session.flush()
    return job


def mark_job_completed(session: Session, job: Job, card: Card) -> Job:
    """Persist a completed terminal state and link its rendered card."""
    job.status = JobState.COMPLETED.value
    job.card = card
    job.error_message = None
    job.finished_at = datetime.now(timezone.utc)
    session.flush()
    return job
