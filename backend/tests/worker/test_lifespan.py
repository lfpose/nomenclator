"""Tests for lifespan integration with worker."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import create_app


def test_lifespan_starts_worker():
    """Verify that lifespan context manager starts the worker."""
    # Mock Worker and its methods
    mock_worker = MagicMock(spec_set=["start", "stop", "last_tick_at"])
    mock_worker.start = AsyncMock()
    mock_worker.stop = AsyncMock()
    mock_worker.last_tick_at = 0

    with patch("app.main.Worker", return_value=mock_worker):
        app = create_app()

        # TestClient triggers lifespan startup/shutdown
        with TestClient(app) as client:
            # Verify worker.start() was called during lifespan startup
            mock_worker.start.assert_awaited_once()

            # Verify worker is accessible via app.state
            assert app.state.worker is mock_worker

            # Make a simple request to verify app is working
            response = client.get("/health")
            assert response.status_code == 200


def test_lifespan_stops_worker_cleanly():
    """Verify that lifespan context manager stops the worker cleanly on shutdown."""
    # Mock Worker and its methods
    mock_worker = MagicMock(spec_set=["start", "stop"])
    mock_worker.start = AsyncMock()
    mock_worker.stop = AsyncMock()

    with patch("app.main.Worker", return_value=mock_worker):
        app = create_app()

        # TestClient triggers full lifespan cycle (startup + shutdown)
        with TestClient(app):
            # Worker should be started
            mock_worker.start.assert_awaited_once()

        # After exiting context, worker.stop() should have been called during shutdown
        mock_worker.stop.assert_awaited_once()
