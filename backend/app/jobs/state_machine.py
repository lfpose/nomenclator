"""State machine validator for job status transitions.

Defines the allowed transitions between job states and provides
functions to check and assert valid transitions.
"""

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"preview", "cancelled"},
    "preview": {"preview", "queued", "cancelled"},
    "queued": {"submitted", "failed", "cancelled"},
    "submitted": {"polling", "cancelled", "failed"},
    "polling": {"polling", "retrying", "completed", "failed", "cancelled"},
    "retrying": {"submitted", "completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def is_allowed(from_state: str, to_state: str) -> bool:
    """Check if a transition between states is allowed.

    Args:
        from_state: The current job state.
        to_state: The desired job state.

    Returns:
        True if the transition is allowed, False otherwise.
    """
    return to_state in ALLOWED_TRANSITIONS.get(from_state, set())


def assert_allowed(from_state: str, to_state: str) -> None:
    """Assert that a transition between states is allowed.

    Args:
        from_state: The current job state.
        to_state: The desired job state.

    Raises:
        ValueError: If the transition is not allowed.
    """
    if not is_allowed(from_state, to_state):
        raise ValueError(f"Invalid transition: {from_state} -> {to_state}")
