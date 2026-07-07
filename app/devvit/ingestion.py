"""Postgres persistence for authenticated Devvit recipe-card commands."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Job, Recipe, SourceItem, Subreddit
from app.devvit.contracts import DevvitIngestionResult, DevvitRecipeCardRequest
from app.jobs.service import create_job_with_status
from app.recipes.extractor import ExtractedRecipe, extract_recipe


def ingest_devvit_request(
    session: Session,
    payload: DevvitRecipeCardRequest,
) -> DevvitIngestionResult:
    """Upsert source and recipe data, then create or reuse one queued job."""
    existing_job = session.scalar(
        select(Job).where(Job.command_comment_id == payload.command_comment_id)
    )
    if existing_job is not None:
        return DevvitIngestionResult(
            job_id=existing_job.id,
            created=False,
            status=existing_job.status,
        )

    extracted = extract_recipe(payload.source_title, payload.source_body)
    subreddit = _upsert_subreddit(session, payload.subreddit)
    source_item = _upsert_source_item(session, payload, subreddit)
    _upsert_recipe(session, source_item, payload, extracted)
    job, created = create_job_with_status(
        session,
        payload.command_comment_id,
        source_item.id,
        requester_username=payload.requester_username,
    )
    return DevvitIngestionResult(job_id=job.id, created=created, status=job.status)


def _upsert_subreddit(session: Session, name: str) -> Subreddit:
    statement = (
        insert(Subreddit)
        .values(name=name, enabled=True)
        .on_conflict_do_update(index_elements=[Subreddit.name], set_={"enabled": True})
        .returning(Subreddit)
    )
    return session.execute(statement).scalar_one()


def _upsert_source_item(
    session: Session,
    payload: DevvitRecipeCardRequest,
    subreddit: Subreddit,
) -> SourceItem:
    values = {
        "reddit_fullname": payload.source_fullname,
        "item_type": payload.source_type,
        "permalink": payload.source_permalink,
        "author_id": None,
        "subreddit_id": subreddit.id,
        "raw_data": payload.model_dump(mode="json"),
    }
    statement = (
        insert(SourceItem)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[SourceItem.reddit_fullname],
            set_={key: value for key, value in values.items() if key != "reddit_fullname"},
        )
        .returning(SourceItem)
    )
    return session.execute(statement).scalar_one()


def _upsert_recipe(
    session: Session,
    source_item: SourceItem,
    payload: DevvitRecipeCardRequest,
    extracted: ExtractedRecipe,
) -> Recipe:
    spec = extracted.to_card_spec(f"r/{payload.subreddit} · Reddit")
    values = {
        "source_item_id": source_item.id,
        "title": spec.title,
        "slug": spec.slug,
        "spec_data": spec.model_dump(mode="json"),
    }
    statement = (
        insert(Recipe)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[Recipe.source_item_id],
            set_={key: value for key, value in values.items() if key != "source_item_id"},
        )
        .returning(Recipe)
    )
    return session.execute(statement).scalar_one()
