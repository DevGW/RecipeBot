"""Database ingestion for validated Reddit recipe-card commands."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.models import Job, Recipe, SourceItem, Subreddit, User
from app.jobs.service import create_job
from app.recipes.extractor import ExtractedRecipe, extract_recipe
from app.reddit.commands import is_recipe_card_command
from app.reddit.source_resolver import RedditSource, resolve_recipe_source

logger = logging.getLogger(__name__)


def ingest_command_comment(session: Session, comment: Any, settings: Settings) -> Job | None:
    """Validate one command, upsert its source and recipe, and queue one durable job."""
    if not is_recipe_card_command(
        comment,
        command=settings.reddit_command,
        bot_username=settings.reddit_username,
    ):
        return None

    command_comment_id = str(getattr(comment, "name", ""))
    if not command_comment_id.startswith("t1_"):
        raise ValueError("command comment is missing a Reddit fullname")

    existing_job = session.scalar(
        select(Job).where(Job.command_comment_id == command_comment_id)
    )
    if existing_job is not None:
        logger.info("Command %s already maps to job %s", command_comment_id, existing_job.id)
        return existing_job

    source = resolve_recipe_source(comment)
    extracted = extract_recipe(source.title, source.body)
    subreddit = _upsert_subreddit(session, source.subreddit)
    user = _upsert_user(session, source.author) if source.author else None
    source_item = _upsert_source_item(session, source, subreddit, user)
    recipe = _upsert_recipe(session, source_item, source, extracted)
    requester_username = str(getattr(comment.author, "name", comment.author))
    job = create_job(
        session,
        command_comment_id,
        source_item.id,
        requester_username=requester_username,
    )

    if settings.reddit_dry_run:
        logger.info(
            "Dry run: queued job %s for recipe %s; no Reddit reply or DM will be sent",
            job.id,
            recipe.id,
        )
    else:
        logger.info("Queued job %s for recipe %s", job.id, recipe.id)
    return job


def _upsert_subreddit(session: Session, name: str) -> Subreddit:
    statement = (
        insert(Subreddit)
        .values(name=name, enabled=True)
        .on_conflict_do_update(index_elements=[Subreddit.name], set_={"enabled": True})
        .returning(Subreddit)
    )
    return session.execute(statement).scalar_one()


def _upsert_user(session: Session, username: str) -> User:
    statement = (
        insert(User)
        .values(reddit_username=username)
        .on_conflict_do_update(
            index_elements=[User.reddit_username],
            set_={"reddit_username": username},
        )
        .returning(User)
    )
    return session.execute(statement).scalar_one()


def _upsert_source_item(
    session: Session,
    source: RedditSource,
    subreddit: Subreddit,
    user: User | None,
) -> SourceItem:
    values = {
        "reddit_fullname": source.reddit_fullname,
        "item_type": source.source_type,
        "permalink": source.permalink,
        "author_id": user.id if user else None,
        "subreddit_id": subreddit.id,
        "raw_data": source.model_dump(mode="json"),
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
    source: RedditSource,
    extracted: ExtractedRecipe,
) -> Recipe:
    spec = extracted.to_card_spec(f"r/{source.subreddit} · Reddit")
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
