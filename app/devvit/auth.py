"""HMAC SHA-256 authentication for Devvit webhook requests."""

from __future__ import annotations

import hashlib
import hmac
import re
import time

SIGNATURE_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def build_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    """Build the lowercase hexadecimal signature expected from Devvit."""
    message = timestamp.encode("ascii") + b"." + raw_body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str | None,
    timestamp: str | None,
    signature: str | None,
    raw_body: bytes,
    *,
    tolerance_seconds: int,
    now: float | None = None,
) -> bool:
    """Validate required headers, timestamp freshness, and the request HMAC."""
    if not secret or not timestamp or not signature:
        return False
    if not SIGNATURE_PATTERN.fullmatch(signature):
        return False
    try:
        request_time = int(timestamp)
    except (TypeError, ValueError):
        return False
    current_time = time.time() if now is None else now
    if abs(current_time - request_time) > tolerance_seconds:
        return False
    try:
        expected = build_signature(secret, timestamp, raw_body)
    except UnicodeEncodeError:
        return False
    return hmac.compare_digest(expected, signature)
