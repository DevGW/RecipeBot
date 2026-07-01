"""Durable job lifecycle states."""

from enum import StrEnum


class JobState(StrEnum):
    """Represent each durable phase of a recipe-card job."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    PARSING = "parsing"
    RENDERING = "rendering"
    STORING = "storing"
    MESSAGING = "messaging"
    COMPLETED = "completed"
    FAILED = "failed"
