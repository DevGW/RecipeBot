"""Tests for durable Reddit result delivery behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.models import Message
from app.reddit.delivery import DeliveryContext, DeliveryError, RedditDeliveryService
from app.reddit.messages import ArtifactLinks


def _links() -> ArtifactLinks:
    return ArtifactLinks(
        title="Lemon Pasta",
        landing="https://cards.example/cards/7",
        png="https://cards.example/cards/7/card.png",
        pdf="https://cards.example/cards/7/card.pdf",
        svg="https://cards.example/cards/7/card.svg",
        zip="https://cards.example/cards/7/recipe-card.zip",
    )


def _context() -> DeliveryContext:
    return DeliveryContext(
        requester_username="hungry_reader",
        command_comment_id="t1_command",
        links=_links(),
    )


def _message(message_id: int, message_type: str, status: str = "queued") -> Message:
    return Message(
        id=message_id,
        job_id=7,
        direction="outbound",
        recipient_username="hungry_reader",
        message_type=message_type,
        status=status,
        body="body",
    )


def _settings(*, fallback: bool = False) -> Settings:
    return Settings(
        _env_file=None,
        REDDIT_DRY_RUN=False,
        REDDIT_PUBLIC_FALLBACK_ON_DM_FAILURE=fallback,
    )


def test_successful_dm_delivery_is_marked_sent() -> None:
    """A successful PRAW message call should persist a sent delivery result."""
    reddit = MagicMock()
    reddit.redditor.return_value.message.return_value = SimpleNamespace(name="t4_message")
    service = RedditDeliveryService(reddit, MagicMock(), _settings())
    queued = _message(1, "dm")
    sent = _message(1, "dm", "sent")
    service._load_context = MagicMock(return_value=_context())
    service._prepare_message = MagicMock(return_value=queued)
    service._mark_sent = MagicMock(return_value=sent)

    result = service.deliver_job(7)

    assert result is sent
    reddit.redditor.assert_called_once_with("hungry_reader")
    reddit.redditor.return_value.message.assert_called_once()
    service._mark_sent.assert_called_once_with(1, reddit.redditor.return_value.message.return_value)


def test_dm_failure_is_persisted_without_public_fallback() -> None:
    """A failed DM should be recorded and raised when public fallback is disabled."""
    reddit = MagicMock()
    error = RuntimeError("messages disabled")
    reddit.redditor.return_value.message.side_effect = error
    service = RedditDeliveryService(reddit, MagicMock(), _settings(fallback=False))
    queued = _message(2, "dm")
    service._load_context = MagicMock(return_value=_context())
    service._prepare_message = MagicMock(return_value=queued)
    service._mark_failed = MagicMock()

    with pytest.raises(DeliveryError, match="DM delivery failed"):
        service.deliver_job(7)

    service._mark_failed.assert_called_once_with(2, error)
    reddit.comment.assert_not_called()


def test_public_fallback_runs_only_after_dm_failure_when_enabled() -> None:
    """An enabled fallback should reply to the command only after the DM raises."""
    reddit = MagicMock()
    dm_error = RuntimeError("messages disabled")
    reddit.redditor.return_value.message.side_effect = dm_error
    reply_result = SimpleNamespace(name="t1_fallback")
    reddit.comment.return_value.reply.return_value = reply_result
    service = RedditDeliveryService(reddit, MagicMock(), _settings(fallback=True))
    dm_message = _message(3, "dm")
    reply_message = _message(4, "public_reply")
    sent_reply = _message(4, "public_reply", "sent")
    service._load_context = MagicMock(return_value=_context())
    service._prepare_message = MagicMock(side_effect=[dm_message, reply_message])
    service._mark_failed = MagicMock()
    service._mark_sent = MagicMock(return_value=sent_reply)

    result = service.deliver_job(7)

    assert result is sent_reply
    service._mark_failed.assert_called_once_with(3, dm_error)
    reddit.comment.assert_called_once_with("command")
    reddit.comment.return_value.reply.assert_called_once()
    service._mark_sent.assert_called_once_with(4, reply_result)


def test_sent_dm_is_not_sent_or_recorded_again() -> None:
    """Repeated delivery handling should reuse a sent DM without another Reddit call."""
    reddit = MagicMock()
    service = RedditDeliveryService(reddit, MagicMock(), _settings())
    sent = _message(5, "dm", "sent")
    service._load_context = MagicMock(return_value=_context())
    service._prepare_message = MagicMock(return_value=sent)

    assert service.deliver_job(7) is sent
    assert service.deliver_job(7) is sent

    reddit.redditor.assert_not_called()
    assert service._prepare_message.call_count == 2


def test_prepare_message_reuses_existing_database_record() -> None:
    """Preparing a repeated message type should update its row without inserting another."""
    session_factory = MagicMock()
    session = session_factory.begin.return_value.__enter__.return_value
    existing = _message(6, "dm", "failed")
    existing.error_message = "old failure"
    session.scalar.return_value = existing
    service = RedditDeliveryService(MagicMock(), session_factory, _settings())

    result = service._prepare_message(7, "hungry_reader", "dm", "new body")

    assert result is existing
    assert existing.status == "queued"
    assert existing.error_message is None
    assert existing.body == "new body"
    session.add.assert_not_called()


def test_mark_failed_persists_status_and_diagnostic() -> None:
    """The failure update should store both terminal status and a useful error message."""
    session_factory = MagicMock()
    session = MagicMock(spec=Session)
    session_factory.begin.return_value.__enter__.return_value = session
    message = _message(8, "dm")
    session.get.return_value = message
    service = RedditDeliveryService(MagicMock(), session_factory, _settings())

    result = service._mark_failed(8, RuntimeError("messages disabled"))

    assert result is message
    assert message.status == "failed"
    assert message.error_message == "RuntimeError: messages disabled"
    session.flush.assert_called_once_with()
