"""Unit tests for the in-memory rate limiter."""

from __future__ import annotations

import pytest

from app.core.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    RateLimitRule,
    build_windowed_key,
)


pytestmark = pytest.mark.asyncio


async def test_limiter_allows_requests_under_limit() -> None:
    """Requests below the limit are accepted."""
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=2, window_seconds=60)
    key = build_windowed_key("test", "ip", "127.0.0.1", rule)

    await limiter.check(key, rule, now=1.0)
    await limiter.check(key, rule, now=2.0)


async def test_limiter_blocks_over_limit() -> None:
    """Requests over the fixed-window limit are blocked."""
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=1, window_seconds=60)
    key = build_windowed_key("test", "ip", "127.0.0.1", rule)

    await limiter.check(key, rule, now=1.0)

    with pytest.raises(RateLimitExceeded):
        await limiter.check(key, rule, now=2.0)


async def test_limiter_resets_after_window() -> None:
    """A new fixed window allows requests again."""
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=1, window_seconds=10)
    key = build_windowed_key("test", "ip", "127.0.0.1", rule)

    await limiter.check(key, rule, now=1.0)
    await limiter.check(key, rule, now=11.0)


async def test_different_keys_have_independent_limits() -> None:
    """Different caller keys do not share counters."""
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=1, window_seconds=60)
    first_key = build_windowed_key("test", "user", "alice", rule)
    second_key = build_windowed_key("test", "user", "bob", rule)

    await limiter.check(first_key, rule, now=1.0)
    await limiter.check(second_key, rule, now=2.0)


async def test_retry_after_is_reasonable() -> None:
    """Retry-After reflects the remaining fixed-window time."""
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=1, window_seconds=60)
    key = build_windowed_key("test", "ip", "127.0.0.1", rule)

    await limiter.check(key, rule, now=10.0)

    with pytest.raises(RateLimitExceeded) as exc_info:
        await limiter.check(key, rule, now=45.2)

    assert exc_info.value.retry_after == 25


async def test_disabled_limiter_allows_requests() -> None:
    """Disabled limiter mode accepts requests without counting them."""
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=1, window_seconds=60)
    key = build_windowed_key("test", "ip", "127.0.0.1", rule)

    await limiter.check(key, rule, enabled=False, now=1.0)
    await limiter.check(key, rule, enabled=False, now=2.0)


async def test_clear_function_clears_limiter_state() -> None:
    """Clearing state removes existing counters."""
    limiter = InMemoryRateLimiter()
    rule = RateLimitRule(limit=1, window_seconds=60)
    key = build_windowed_key("test", "ip", "127.0.0.1", rule)

    await limiter.check(key, rule, now=1.0)
    await limiter.clear()
    await limiter.check(key, rule, now=2.0)
