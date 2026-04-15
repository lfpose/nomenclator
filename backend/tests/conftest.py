import pytest


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Suppress 'no tests collected' exit code (5) during scaffolding phase."""
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
