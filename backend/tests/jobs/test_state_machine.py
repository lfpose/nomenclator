"""Tests for the job state machine validator."""

import pytest

from app.jobs.state_machine import ALLOWED_TRANSITIONS, assert_allowed, is_allowed


def test_allowed_draft_to_preview() -> None:
    """Verify draft -> preview is allowed."""
    assert is_allowed("draft", "preview")


def test_allowed_preview_to_queued() -> None:
    """Verify preview -> queued is allowed."""
    assert is_allowed("preview", "queued")


def test_allowed_polling_to_completed() -> None:
    """Verify polling -> completed is allowed."""
    assert is_allowed("polling", "completed")


def test_disallowed_completed_to_anything() -> None:
    """Verify completed state has no outgoing transitions."""
    assert not is_allowed("completed", "failed")
    assert not is_allowed("completed", "cancelled")
    assert not is_allowed("completed", "polling")
    assert len(ALLOWED_TRANSITIONS["completed"]) == 0


def test_disallowed_failed_to_anything() -> None:
    """Verify failed state has no outgoing transitions."""
    assert not is_allowed("failed", "completed")
    assert not is_allowed("failed", "cancelled")
    assert not is_allowed("failed", "queued")
    assert len(ALLOWED_TRANSITIONS["failed"]) == 0


def test_disallowed_cancelled_to_anything() -> None:
    """Verify cancelled state has no outgoing transitions."""
    assert not is_allowed("cancelled", "draft")
    assert not is_allowed("cancelled", "preview")
    assert not is_allowed("cancelled", "queued")
    assert len(ALLOWED_TRANSITIONS["cancelled"]) == 0


def test_disallowed_skip_states() -> None:
    """Verify draft -> submitted is disallowed (must go through preview/queued)."""
    assert not is_allowed("draft", "submitted")
    assert not is_allowed("preview", "polling")
    assert not is_allowed("queued", "retrying")


def test_assert_allowed_raises_on_invalid() -> None:
    """Verify assert_allowed raises ValueError on invalid transition."""
    with pytest.raises(ValueError, match="Invalid transition: completed -> failed"):
        assert_allowed("completed", "failed")

    with pytest.raises(ValueError, match="Invalid transition: draft -> submitted"):
        assert_allowed("draft", "submitted")

    # Should not raise for valid transition
    assert_allowed("draft", "preview")
