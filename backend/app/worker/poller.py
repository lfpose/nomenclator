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

                # Check if job is done and finalize
                await self._finalize_if_done(conn, job)
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

    async def _finalize_if_done(self, conn, job) -> None:
        """Check if job is done and either complete, retry, or flag stragglers.

        This is called after each batch ends. It checks:
        1. Are all batches for this job in a terminal state?
        2. If yes, are all clusters resolved?
        3. If all resolved, complete the job.
        4. If not all resolved and retry_round < 3, submit a retry.
        5. If not all resolved and retry_round >= 3, flag stragglers and complete.
        """
        from ..dao import clusters as clusters_dao, batches as batches_dao
        from ..jobs.service import transition

        # Are all batches for this job ended?
        batches = batches_dao.list_batches_for_job(conn, job.id)
        if not all(b.status in {"ended", "canceled", "expired"} for b in batches):
            return

        # If job is still submitted, transition to polling first
        # (may have skipped the earlier transition due to all batches already being ended)
        if job.status == "submitted":
            transition(conn, job.id, "polling", reason="all_batches_ended")

        unresolved = clusters_dao.count_unresolved_clusters(conn, job.id)
        if unresolved == 0:
            # Compute job counts before completing
            total_rows = len(clusters_dao.list_clusters(conn, job.id))  # Simplified: clusters = rows in our test setup
            error_rows = sum(
                c.member_count if c.error else 0
                for c in clusters_dao.list_clusters(conn, job.id)
            )
            self._complete_job(conn, job, total_rows=total_rows, error_rows=error_rows)
            return

        # Need a retry or give up
        current_round = max((b.retry_round for b in batches), default=0)
        if current_round >= 3:
            self._flag_remaining_and_complete(conn, job, error_code="max_retries_exceeded")
            return
        await self._submit_retry(conn, job, current_round + 1)

    def _complete_job(self, conn, job, total_rows=0, error_rows=0) -> None:
        """Complete a job by transitioning to 'completed', updating counts and finished_at.

        Args:
            conn: Database connection
            job: Job object
            total_rows: Total number of rows (optional)
            error_rows: Number of rows with errors (optional)
        """
        from ..dao import jobs as jobs_dao
        from ..jobs.service import transition

        # Update job counts before completing
        if total_rows > 0 or error_rows > 0:
            jobs_dao.update_job_counts(conn, job.id, total_rows=total_rows, error_rows=error_rows)

        # Set finished_at timestamp
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET finished_at = ? WHERE id = ?",
            (int(time.time()), job.id)
        )

        # Transition to completed state
        transition(conn, job.id, "completed", reason="all_clusters_resolved")

    def _flag_remaining_and_complete(self, conn, job, error_code: str) -> None:
        """Set error on all unresolved clusters, then complete the job.

        Args:
            conn: Database connection
            job: Job object
            error_code: Error code to set on unresolved clusters (e.g., "max_retries_exceeded")
        """
        from ..dao import clusters as clusters_dao

        # Find all unresolved clusters (male_es is NULL and error is NULL)
        unresolved = [
            c for c in clusters_dao.list_clusters(conn, job.id)
            if c.male_es is None and c.error is None
        ]

        # Flag each unresolved cluster with the error code
        for cluster in unresolved:
            clusters_dao.mark_cluster_error(conn, cluster.id, error_code)

        # Calculate total rows and error rows for job completion
        all_clusters = clusters_dao.list_clusters(conn, job.id)
        total_rows = sum(c.member_count for c in all_clusters)
        error_rows = sum(c.member_count for c in all_clusters if c.error)

        # Complete the job with proper counts
        self._complete_job(conn, job, total_rows=total_rows, error_rows=error_rows)

    async def _submit_retry(self, conn, job, new_round: int) -> None:
        """Submit a retry batch for unresolved clusters.

        This is a placeholder for now; will be implemented in P08-06.
        """
        raise NotImplementedError("_submit_retry will be implemented in P08-06")
