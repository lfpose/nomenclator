import pytest
import sqlite3

from app.db import _apply_migrations
from tests.anthropic.fake_client import FakeAnthropicBatchClient


@pytest.fixture
def conn():
    """Create a fresh in-memory SQLite connection with migrations applied."""
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(c)
    yield c
    c.close()


@pytest.fixture
def fake_anthropic() -> FakeAnthropicBatchClient:
    """Provide a fresh fake Anthropic client for testing."""
    return FakeAnthropicBatchClient()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Suppress 'no tests collected' exit code (5) during scaffolding phase."""
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = pytest.ExitCode.OK
