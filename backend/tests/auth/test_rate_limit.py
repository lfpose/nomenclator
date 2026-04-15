from unittest.mock import patch

from app.auth.rate_limit import RateLimiter


def test_allows_under_limit() -> None:
    limiter = RateLimiter(limit=3, window_seconds=60.0)
    assert limiter.allow("key1") is True
    assert limiter.allow("key1") is True
    assert limiter.allow("key1") is True


def test_blocks_at_limit() -> None:
    limiter = RateLimiter(limit=3, window_seconds=60.0)
    assert limiter.allow("key1") is True
    assert limiter.allow("key1") is True
    assert limiter.allow("key1") is True
    assert limiter.allow("key1") is False
    assert limiter.allow("key1") is False


def test_resets_after_window() -> None:
    with patch("app.auth.rate_limit.time", side_effect=[0.0, 0.0, 0.0, 0.0, 61.0]):
        limiter = RateLimiter(limit=3, window_seconds=60.0)
        # Exhaust limit (all at time 0)
        assert limiter.allow("key1") is True
        assert limiter.allow("key1") is True
        assert limiter.allow("key1") is True
        assert limiter.allow("key1") is False

        # Fast-forward past window (time 61)
        assert limiter.allow("key1") is True


def test_independent_per_key() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60.0)
    # Key1 hits limit
    assert limiter.allow("key1") is True
    assert limiter.allow("key1") is True
    assert limiter.allow("key1") is False

    # Key2 is independent
    assert limiter.allow("key2") is True
    assert limiter.allow("key2") is True
    assert limiter.allow("key2") is False
