"""Simple in-memory fixed-window rate limiting.

This limiter is suitable for the local, single-instance university backend used
in this project. Production deployments should use Redis, API gateway rate
limiting, or another distributed shared store so limits work across instances.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitRule:
    """A fixed-window rate-limit rule."""

    limit: int
    window_seconds: int


@dataclass
class _WindowState:
    """Counter state for a fixed window."""

    count: int
    window_started_at: float


class RateLimitExceeded(Exception):
    """Raised when a caller exceeds a rate limit."""

    def __init__(self, retry_after: int) -> None:
        """Store the seconds until the caller may retry."""
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded.")


class InMemoryRateLimiter:
    """Async-safe in-memory fixed-window limiter."""

    def __init__(self) -> None:
        """Create an empty limiter."""
        self._state: dict[str, _WindowState] = {}
        self._lock = asyncio.Lock()

    async def check(
        self,
        key: str,
        rule: RateLimitRule,
        *,
        enabled: bool = True,
        now: float | None = None,
    ) -> None:
        """Consume one request or raise RateLimitExceeded."""
        if not enabled:
            return
        if rule.limit < 1:
            raise ValueError("Rate limit must be at least 1.")
        if rule.window_seconds < 1:
            raise ValueError("Rate-limit window must be at least 1 second.")

        current_time = time.monotonic() if now is None else now
        async with self._lock:
            self._cleanup_expired(current_time)
            state = self._state.get(key)
            if state is None or current_time >= state.window_started_at + rule.window_seconds:
                self._state[key] = _WindowState(count=1, window_started_at=current_time)
                return

            if state.count >= rule.limit:
                window_ends_at = state.window_started_at + rule.window_seconds
                retry_after = max(1, math.ceil(window_ends_at - current_time))
                raise RateLimitExceeded(retry_after=retry_after)

            state.count += 1

    async def clear(self) -> None:
        """Clear all limiter state."""
        async with self._lock:
            self._state.clear()

    def _cleanup_expired(self, now: float) -> None:
        """Remove expired window states."""
        expired_keys = [
            key
            for key, state in self._state.items()
            if now >= state.window_started_at + _window_seconds_from_key(key)
        ]
        for key in expired_keys:
            self._state.pop(key, None)


GLOBAL_RATE_LIMITER = InMemoryRateLimiter()

REGISTER_RATE_LIMIT = RateLimitRule(limit=5, window_seconds=10 * 60)
LOGIN_RATE_LIMIT = RateLimitRule(limit=5, window_seconds=5 * 60)
REFRESH_RATE_LIMIT = RateLimitRule(limit=20, window_seconds=10 * 60)
DEVICE_KEY_UPLOAD_RATE_LIMIT = RateLimitRule(limit=30, window_seconds=10 * 60)
ONE_TIME_PREKEY_UPLOAD_RATE_LIMIT = RateLimitRule(limit=20, window_seconds=10 * 60)
PREKEY_BUNDLE_FETCH_RATE_LIMIT = RateLimitRule(limit=60, window_seconds=60)
USER_LOOKUP_RATE_LIMIT = RateLimitRule(limit=60, window_seconds=60)
MESSAGE_SEND_RATE_LIMIT = RateLimitRule(limit=60, window_seconds=60)
MESSAGE_FORWARD_RATE_LIMIT = RateLimitRule(limit=30, window_seconds=60)
MESSAGE_READ_RATE_LIMIT = RateLimitRule(limit=120, window_seconds=60)


def build_rate_limit_key(scope: str, caller_type: str, caller_id: str) -> str:
    """Build a safe rate-limit key from non-secret identity data."""
    return f"{scope}:{caller_type}:{caller_id}"


def build_windowed_key(scope: str, caller_type: str, caller_id: str, rule: RateLimitRule) -> str:
    """Build a key that includes the rule window for cleanup bookkeeping."""
    safe_key = build_rate_limit_key(scope, caller_type, caller_id)
    return f"{rule.window_seconds}:{safe_key}"


def _window_seconds_from_key(key: str) -> int:
    """Read the encoded window length from a limiter key."""
    window_seconds, _, _ = key.partition(":")
    try:
        return int(window_seconds)
    except ValueError:
        return 1
