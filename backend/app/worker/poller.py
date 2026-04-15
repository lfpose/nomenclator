"""Background worker that polls Anthropic for batch results."""

import asyncio
import logging
import time

log = logging.getLogger("nomenclator.worker")


class Worker:
    """Asyncio task that polls Anthropic, processes results, and handles retries."""

    def __init__(self, client, db_factory, tick_interval: float = 30.0) -> None:
        """Initialize the worker.

        Args:
            client: AnthropicBatchClient instance (RealAnthropicBatchClient or FakeAnthropicBatchClient)
            db_factory: Function that returns a database connection (e.g., get_connection)
            tick_interval: Seconds between tick() calls (default 30.0)
        """
        self._client = client
        self._db_factory = db_factory
        self._tick_interval = tick_interval
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.last_tick_at: float = 0.0

    async def start(self) -> None:
        """Start the worker background task."""
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the worker and wait for the background task to finish."""
        self._stop.set()
        if self._task:
            await self._task
            self._task = None

    async def _run(self) -> None:
        """Main worker loop: tick periodically until stop is signaled."""
        log.info("worker.started")
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception as e:
                log.error("worker.error", exc_info=e)
            self.last_tick_at = time.time()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick_interval)
            except asyncio.TimeoutError:
                pass

    async def tick(self) -> None:
        """Poll active jobs and process results. Implemented in P08-03 onwards."""
        pass
