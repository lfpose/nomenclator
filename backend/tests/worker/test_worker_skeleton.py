"""Tests for Worker skeleton (P08-01)."""

import asyncio

import pytest

from app.worker.poller import Worker


@pytest.mark.asyncio_mode("auto")
async def test_worker_start_and_stop_clean() -> None:
    """Worker starts and stops cleanly without errors."""

    async def dummy_db_factory():
        return None

    class DummyClient:
        pass

    worker = Worker(client=DummyClient(), db_factory=dummy_db_factory, tick_interval=0.1)

    await worker.start()
    assert worker._task is not None
    assert worker._task is not asyncio.current_task()

    await worker.stop()
    assert worker._task is None


@pytest.mark.asyncio_mode("auto")
async def test_worker_heartbeat_updates_on_tick() -> None:
    """Worker's last_tick_at heartbeat updates after each tick."""

    call_count = 0

    async def dummy_db_factory():
        return None

    class DummyClient:
        pass

    worker = Worker(client=DummyClient(), db_factory=dummy_db_factory, tick_interval=0.1)

    # Override tick to increment call_count
    original_tick = worker.tick

    async def tick_override():
        nonlocal call_count
        call_count += 1
        await original_tick()

    worker.tick = tick_override

    assert worker.last_tick_at == 0.0

    await worker.start()
    await asyncio.sleep(0.15)  # Wait for at least one tick

    assert call_count >= 1
    assert worker.last_tick_at > 0.0

    await worker.stop()


@pytest.mark.asyncio_mode("auto")
async def test_worker_continues_after_tick_exception() -> None:
    """Worker continues running after an exception in tick()."""

    call_count = 0

    async def dummy_db_factory():
        return None

    class DummyClient:
        pass

    worker = Worker(client=DummyClient(), db_factory=dummy_db_factory, tick_interval=0.1)

    # Override tick to raise an exception on first call only
    async def tick_override():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("First tick error")

    worker.tick = tick_override

    await worker.start()
    await asyncio.sleep(0.25)  # Wait for multiple ticks

    # Should have continued despite the exception
    assert call_count >= 2

    await worker.stop()
