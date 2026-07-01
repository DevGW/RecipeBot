"""Single-process Postgres-backed recipe-card worker."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, get_settings
from app.db.models import Card, Job, Recipe
from app.db.session import build_session_factory
from app.jobs.service import (
    claim_next_queued_job,
    get_job,
    mark_job_completed,
    mark_job_failed,
    set_job_state,
)
from app.jobs.states import JobState
from app.reddit.client import build_reddit_client
from app.reddit.delivery import RedditDeliveryService
from app.rendering.card_spec import RecipeCardSpec
from app.rendering.renderer import RenderedCardPaths, render_card
from app.storage.artifacts import create_job_bundle

RenderFunction = Callable[..., RenderedCardPaths]
RENDER_VERSION = "1"


class JobWorker:
    """Claim and process durable jobs one at a time."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings,
        *,
        renderer: RenderFunction = render_card,
        delivery_service: RedditDeliveryService | None = None,
    ) -> None:
        """Configure the worker with database, settings, and rendering dependencies."""
        self.session_factory = session_factory
        self.settings = settings
        self.renderer = renderer
        self.delivery_service = delivery_service

    def run_once(self) -> bool:
        """Process at most one queued job and report whether a job was claimed."""
        with self.session_factory.begin() as session:
            job = claim_next_queued_job(session)
            job_id = job.id if job is not None else None

        if job_id is None:
            return False

        try:
            self.process_job(job_id)
        except Exception as error:
            self._record_failure(job_id, error)
        return True

    def run_forever(self, poll_interval: float = 2.0) -> None:
        """Continuously process jobs, sleeping briefly when the queue is empty."""
        while True:
            if not self.run_once():
                time.sleep(poll_interval)

    def process_job(self, job_id: int) -> Card:
        """Load, render, store, and complete one previously claimed job."""
        recipe_id, spec, source_url = self._load_recipe_spec(job_id)
        self._transition(job_id, JobState.RENDERING)
        output_directory = self.settings.artifact_root / "jobs" / str(job_id)
        paths = self.renderer(
            spec,
            output_directory,
            imagemagick_binary=self.settings.imagemagick_binary,
            rsvg_convert_binary=self.settings.rsvg_convert_binary,
        )

        self._transition(job_id, JobState.STORING)
        card_id = self._store_card(job_id, recipe_id, paths)
        create_job_bundle(
            self.settings.artifact_root,
            self.settings.artifact_base_url,
            job_id=job_id,
            card_id=card_id,
            title=spec.title,
            slug=spec.slug,
            source_url=source_url,
        )

        # Delivery is part of the durable messaging phase and must succeed before completion.
        self._transition(job_id, JobState.MESSAGING)
        self._deliver_result(job_id)
        with self.session_factory.begin() as session:
            job = self._require_job(session, job_id)
            card = session.get(Card, card_id)
            if card is None:
                raise RuntimeError(f"card {card_id} disappeared while completing job {job_id}")
            mark_job_completed(session, job, card)
            return card

    def _deliver_result(self, job_id: int) -> None:
        if self.delivery_service is not None:
            self.delivery_service.deliver_job(job_id)
            return
        with self.session_factory.begin() as session:
            job = self._require_job(session, job_id)
            requester_username = job.requester_username
        if not requester_username or not self.settings.reddit_dm_results:
            return
        reddit = None if self.settings.reddit_dry_run else build_reddit_client(self.settings)
        RedditDeliveryService(reddit, self.session_factory, self.settings).deliver_job(job_id)

    def _load_recipe_spec(self, job_id: int) -> tuple[int, RecipeCardSpec, str | None]:
        with self.session_factory.begin() as session:
            job = self._require_job(session, job_id)
            set_job_state(session, job, JobState.PARSING)
            if job.source_item is None:
                raise ValueError(f"job {job_id} has no associated source item")
            recipe = session.scalar(
                select(Recipe).where(Recipe.source_item_id == job.source_item.id)
            )
            if recipe is None:
                raise ValueError(f"source item {job.source_item.id} has no recipe")
            return (
                recipe.id,
                RecipeCardSpec.model_validate(recipe.spec_data),
                job.source_item.permalink,
            )

    def _store_card(
        self,
        job_id: int,
        recipe_id: int,
        paths: RenderedCardPaths,
    ) -> int:
        with self.session_factory.begin() as session:
            card = session.scalar(
                select(Card).where(
                    Card.recipe_id == recipe_id,
                    Card.render_version == RENDER_VERSION,
                )
            )
            if card is None:
                card = Card(recipe_id=recipe_id, render_version=RENDER_VERSION)
                session.add(card)
            card.svg_path = str(paths.svg)
            card.png_path = str(paths.png)
            card.pdf_path = str(paths.pdf)
            session.flush()

            job = self._require_job(session, job_id)
            job.card = card
            session.flush()
            return card.id

    def _transition(self, job_id: int, state: JobState) -> None:
        with self.session_factory.begin() as session:
            set_job_state(session, self._require_job(session, job_id), state)

    def _record_failure(self, job_id: int, error: Exception) -> None:
        with self.session_factory.begin() as session:
            job = self._require_job(session, job_id)
            reason = f"{type(error).__name__}: {error}"
            mark_job_failed(session, job, reason)

    @staticmethod
    def _require_job(session: Session, job_id: int) -> Job:
        job = get_job(session, job_id)
        if job is None:
            raise RuntimeError(f"job {job_id} does not exist")
        return job


def build_worker(settings: Settings | None = None) -> JobWorker:
    """Build a worker from environment-backed application settings."""
    resolved_settings = settings or get_settings()
    return JobWorker(
        build_session_factory(resolved_settings.database_url),
        resolved_settings,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the worker once or continuously from the command line."""
    parser = argparse.ArgumentParser(description="Run the RecipeBot database worker")
    parser.add_argument("--once", action="store_true", help="process at most one queued job")
    arguments = parser.parse_args(argv)
    worker = build_worker()
    if arguments.once:
        worker.run_once()
    else:
        worker.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
