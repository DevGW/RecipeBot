"""Durable Reddit delivery for completed recipe-card artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import praw
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings
from app.db.models import Job, Message
from app.reddit.messages import (
    ArtifactLinks,
    format_dm_body,
    format_dm_subject,
    format_public_fallback,
)
from app.storage.artifacts import read_metadata, resolve_card_artifacts

logger = logging.getLogger(__name__)


class DeliveryError(RuntimeError):
    """Indicate that no configured Reddit delivery path succeeded."""


@dataclass(frozen=True)
class DeliveryContext:
    """Collect the requester and links needed for one delivery attempt."""

    requester_username: str
    command_comment_id: str
    links: ArtifactLinks


class RedditDeliveryService:
    """Send and durably track DM results with an optional public fallback."""

    def __init__(
        self,
        reddit: praw.Reddit | None,
        session_factory: sessionmaker[Session],
        settings: Settings,
    ) -> None:
        """Configure delivery with Reddit, database, and application dependencies."""
        self.reddit = reddit
        self.session_factory = session_factory
        self.settings = settings

    def deliver_job(self, job_id: int) -> Message | None:
        """Deliver one job idempotently and raise when all configured paths fail."""
        if not self.settings.reddit_dm_results:
            logger.info("Reddit DM delivery is disabled for job %s", job_id)
            return None

        context = self._load_context(job_id)
        subject = format_dm_subject(context.links)
        body = format_dm_body(context.links)
        message = self._prepare_message(job_id, context.requester_username, "dm", body)
        if message.status == "sent":
            return message
        if self.settings.reddit_dry_run:
            logger.info("Dry run: would DM u/%s for job %s", context.requester_username, job_id)
            return message
        if self.reddit is None:
            raise DeliveryError("Reddit client is required when dry-run mode is disabled")

        try:
            result = self.reddit.redditor(context.requester_username).message(
                subject=subject,
                message=body,
            )
        except Exception as error:
            self._mark_failed(message.id, error)
            if not self.settings.reddit_public_fallback_on_dm_failure:
                raise DeliveryError(f"DM delivery failed: {error}") from error
            return self._send_public_fallback(job_id, context)

        return self._mark_sent(message.id, result)

    def _load_context(self, job_id: int) -> DeliveryContext:
        with self.session_factory.begin() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise DeliveryError(f"job {job_id} does not exist")
            if not job.requester_username:
                raise DeliveryError(f"job {job_id} has no requesting Reddit username")
            if job.card is None or job.card.id is None:
                raise DeliveryError(f"job {job_id} has no rendered card")
            links = build_delivery_links(job, self.settings.artifact_root)
            return DeliveryContext(
                requester_username=job.requester_username,
                command_comment_id=job.command_comment_id,
                links=links,
            )

    def _prepare_message(
        self,
        job_id: int,
        recipient: str,
        message_type: str,
        body: str,
    ) -> Message:
        with self.session_factory.begin() as session:
            message = session.scalar(
                select(Message).where(
                    Message.job_id == job_id,
                    Message.message_type == message_type,
                )
            )
            if message is None:
                message = Message(
                    job_id=job_id,
                    direction="outbound",
                    recipient_username=recipient,
                    message_type=message_type,
                    status="queued",
                    body=body,
                )
                session.add(message)
            elif message.status != "sent":
                message.status = "queued"
                message.body = body
                message.error_message = None
            session.flush()
            return message

    def _mark_sent(self, message_id: int, result: Any) -> Message:
        with self.session_factory.begin() as session:
            message = _require_message(session, message_id)
            external_id = _external_message_id(result)
            message.status = "sent"
            message.external_message_id = external_id
            message.reddit_fullname = (
                external_id if external_id and external_id.startswith("t") else None
            )
            message.error_message = None
            session.flush()
            return message

    def _mark_failed(self, message_id: int, error: Exception) -> Message:
        with self.session_factory.begin() as session:
            message = _require_message(session, message_id)
            message.status = "failed"
            message.error_message = f"{type(error).__name__}: {error}"
            session.flush()
            return message

    def _send_public_fallback(self, job_id: int, context: DeliveryContext) -> Message:
        body = format_public_fallback(context.links)
        message = self._prepare_message(
            job_id,
            context.requester_username,
            "public_reply",
            body,
        )
        if message.status == "sent":
            return message
        if self.reddit is None:
            raise DeliveryError("Reddit client is required for public fallback delivery")
        comment_id = context.command_comment_id.removeprefix("t1_")
        try:
            result = self.reddit.comment(comment_id).reply(body)
        except Exception as error:
            self._mark_failed(message.id, error)
            raise DeliveryError(f"public fallback delivery failed: {error}") from error
        return self._mark_sent(message.id, result)


def build_delivery_links(job: Job, artifact_root: Path) -> ArtifactLinks:
    """Build validated public delivery links from a rendered job's metadata."""
    if job.card is None or job.card.id is None:
        raise DeliveryError("job has no rendered card")
    paths = resolve_card_artifacts(artifact_root, job.card.id, job.card)
    metadata = read_metadata(paths)
    urls = metadata.get("urls")
    if not isinstance(urls, dict):
        raise DeliveryError("artifact metadata has no public URLs")
    try:
        return ArtifactLinks(
            title=str(metadata["title"]),
            landing=str(urls["landing"]),
            png=str(urls["png"]),
            pdf=str(urls["pdf"]),
            svg=str(urls["svg"]),
            zip=str(urls["zip"]),
        )
    except KeyError as error:
        raise DeliveryError(f"artifact metadata is missing {error.args[0]}") from error


def _require_message(session: Session, message_id: int) -> Message:
    message = session.get(Message, message_id)
    if message is None:
        raise DeliveryError(f"delivery message {message_id} does not exist")
    return message


def _external_message_id(result: Any) -> str | None:
    if result is None:
        return None
    value = getattr(result, "name", None) or getattr(result, "id", None)
    return str(value) if value else None
