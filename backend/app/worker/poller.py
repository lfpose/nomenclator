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
        """Poll active jobs and process results."""
        conn = self._db_factory()
        try:
            from ..dao import jobs as jobs_dao, batches as batches_dao

            # Filter to non-terminal jobs
            active = [
                j for j in jobs_dao.list_jobs(conn)
                if j.status in {"submitted", "polling", "retrying"}
            ]

            for job in active:
                batches = batches_dao.list_batches_for_job(conn, job.id)

                for batch in batches:
                    # Skip already-terminal batches
                    if batch.status in {"ended", "canceled", "expired"}:
                        continue

                    # Poll Anthropic for batch status
                    status = self._client.get_batch_status(batch.id)
                    batches_dao.update_batch_status(
                        conn,
                        batch.id,
                        status=status["processing_status"],
                        polled_at=int(time.time()),
                        completed_at=int(time.time()) if status["processing_status"] == "ended" else None,
                    )

                    # Handle completed batch
                    if status["processing_status"] == "ended":
                        await self._on_batch_ended(conn, job, batch)

                # Transition job from submitted to polling on first poll
                if any(b.status not in {"ended", "canceled", "expired"} for b in batches):
                    if job.status == "submitted":
                        from ..jobs.service import transition
                        transition(conn, job.id, "polling", reason="first_poll")
        finally:
            conn.close()

    async def _on_batch_ended(self, conn, job, batch) -> None:
        """Handle a batch that just ended by fetching results and updating clusters."""
        from ..dao import batch_requests as br_dao, clusters as clusters_dao
        from ..anthropic.response_parser import parse_tool_call, analyze_stragglers, ParseError
        from ..jobs.service import record_batch_cost

        results = self._client.get_batch_results(batch.id)
        requests = br_dao.list_requests_for_batch(conn, batch.id)
        requests_by_id = {r.id: r for r in requests}

        total_in_tokens, total_out_tokens = 0, 0
        had_matching_requests = False

        for result in results:
            custom_id = result["custom_id"]
            req = requests_by_id.get(custom_id)
            if req is None:
                continue
            had_matching_requests = True
            message = result.get("result", {}).get("message", {})
            usage = message.get("usage", {})
            total_in_tokens += usage.get("input_tokens", 0)
            total_out_tokens += usage.get("output_tokens", 0)
            try:
                tool_output = parse_tool_call(message)
            except ParseError as e:
                br_dao.mark_request_failed(conn, custom_id, error=e.code, raw_response=str(result))
                continue
            cluster_ids = req.cluster_ids  # list[int]
            expected_ids = {f"t{i+1:03d}" for i in range(len(cluster_ids))}
            analysis = analyze_stragglers(expected_ids, tool_output)
            # Map id -> cluster_id (positional by construction in P07-06)
            for title_id, result_obj in analysis.results_by_id.items():
                idx = int(title_id[1:]) - 1  # "t001" → 0
                cluster_id = cluster_ids[idx]
                clusters_dao.update_cluster_answers(
                    conn,
                    cluster_id,
                    male_es=result_obj.male_es,
                    female_es=result_obj.female_es,
                    category=result_obj.category,
                )
            br_dao.mark_request_completed(conn, custom_id, raw_response=str(result))
            if analysis.missing_ids:
                br_dao.mark_request_missing(conn, custom_id)

        # Only record spend if we had at least one matching request
        if had_matching_requests:
            record_batch_cost(
                conn,
                job_id=job.id,
                batch_id=batch.id,
                input_tokens=total_in_tokens,
                output_tokens=total_out_tokens,
            )
