# 08 — Background Worker

The asyncio task running inside the FastAPI process that polls Anthropic, processes results, and handles straggler retries. Reference: `spec/07-job-lifecycle.md`, `spec/18-reliability-contract.md`, `solution-overview.md` #5.

Every test in this phase uses `FakeAnthropicBatchClient` from P05-09 — no real API calls.

---

### P08-01 — Worker module skeleton

**Deps:** P01-03, P02-01
**Files:** `backend/app/worker/poller.py`, `backend/tests/worker/test_worker_skeleton.py`
**Goal:** An `asyncio` task that can be started and stopped cleanly, updates an in-memory heartbeat every tick.

**Implementation:**
```python
import asyncio
import time
import logging

log = logging.getLogger("nomenclator.worker")

class Worker:
    def __init__(self, client, db_factory, tick_interval: float = 30.0) -> None:
        self._client = client
        self._db_factory = db_factory
        self._tick_interval = tick_interval
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.last_tick_at: float = 0.0

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
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
        # Implemented in P08-03 onwards
        pass
```

**Test:** `cd backend && uv run pytest tests/worker/test_worker_skeleton.py -v`

Required assertions:
- `test_worker_start_and_stop_clean`
- `test_worker_heartbeat_updates_on_tick`
- `test_worker_continues_after_tick_exception`

**Done when:**
- [ ] All 3 tests pass using `asyncio_mode=auto`.

---

### P08-02 — Lifespan integration

**Deps:** P08-01
**Files:** `backend/app/main.py` (extend), `backend/tests/worker/test_lifespan.py`
**Goal:** Wire the worker into FastAPI's `lifespan` so it starts on boot and stops on shutdown.

**Implementation:**
```python
from contextlib import asynccontextmanager
from .worker.poller import Worker
from .db import get_connection
from .anthropic.client import RealAnthropicClient
from .settings import settings

@asynccontextmanager
async def lifespan(app):
    client = RealAnthropicClient(api_key=settings.anthropic_api_key)
    worker = Worker(client=client, db_factory=get_connection)
    await worker.start()
    app.state.worker = worker
    try:
        yield
    finally:
        await worker.stop()
```

Update `create_app` to pass `lifespan=lifespan`.

**Test:** `cd backend && uv run pytest tests/worker/test_lifespan.py -v`

Required assertions:
- `test_lifespan_starts_worker`
- `test_lifespan_stops_worker_cleanly`

**Done when:**
- [ ] Both tests pass with a mocked worker.

---

### P08-03 — Tick: scan non-terminal jobs and poll

**Deps:** P02-05, P02-08, P05-08, P08-01
**Files:** `backend/app/worker/poller.py` (extend), `backend/tests/worker/test_tick_poll.py`
**Goal:** Implement `tick()` so it scans non-terminal jobs, polls each batch, and updates batch/job status.

Note: dry-run jobs will already be in `completed` state by the time the worker runs (they complete synchronously in `commit_job`), so the worker naturally skips them. No code change needed.

**Implementation:**
```python
async def tick(self) -> None:
    conn = self._db_factory()
    try:
        from ..dao import jobs as jobs_dao, batches as batches_dao
        active = [j for j in jobs_dao.list_jobs(conn) if j.status in {"submitted", "polling", "retrying"}]
        for job in active:
            batches = batches_dao.list_batches_for_job(conn, job.id)
            for batch in batches:
                if batch.status in {"ended", "canceled", "expired"}:
                    continue
                status = self._client.get_batch_status(batch.id)
                batches_dao.update_batch_status(
                    conn, batch.id, status=status["processing_status"],
                    polled_at=int(time.time()),
                    completed_at=int(time.time()) if status["processing_status"] == "ended" else None,
                )
                if status["processing_status"] == "ended":
                    await self._on_batch_ended(conn, job, batch)
            # Update job status based on batches
            if any(b.status not in {"ended", "canceled", "expired"} for b in batches):
                from ..jobs.service import transition
                if job.status == "submitted":
                    transition(conn, job.id, "polling", reason="first_poll")
    finally:
        conn.close()

async def _on_batch_ended(self, conn, job, batch):
    pass  # wired in P08-04
```

**Test:** `cd backend && uv run pytest tests/worker/test_tick_poll.py -v`

Required assertions (use `FakeAnthropicBatchClient`):
- `test_tick_ignores_terminal_jobs`
- `test_tick_polls_submitted_jobs_and_transitions_to_polling`
- `test_tick_updates_batch_polled_at`
- `test_tick_skips_already_ended_batches`

**Done when:**
- [ ] All 4 tests pass.

---

### P08-04 — On-batch-ended: fetch and parse results

**Deps:** P02-07, P02-09, P05-06, P05-07, P07-02, P07-08, P08-03
**Files:** `backend/app/worker/poller.py` (extend), `backend/tests/worker/test_on_batch_ended.py`
**Goal:** When a batch transitions to `ended`, fetch its results, parse each, write answers to clusters.

**Implementation:**
```python
async def _on_batch_ended(self, conn, job, batch) -> None:
    from ..dao import batch_requests as br_dao, clusters as clusters_dao
    from ..anthropic.response_parser import parse_tool_call, analyze_stragglers, ParseError
    from ..jobs.service import record_batch_cost

    results = self._client.get_batch_results(batch.id)
    requests = br_dao.list_requests_for_batch(conn, batch.id)
    requests_by_id = {r.id: r for r in requests}

    total_in_tokens, total_out_tokens = 0, 0

    for result in results:
        custom_id = result["custom_id"]
        req = requests_by_id.get(custom_id)
        if req is None:
            continue
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
                conn, cluster_id,
                male_es=result_obj.male_es,
                female_es=result_obj.female_es,
                category=result_obj.category,
            )
        br_dao.mark_request_completed(conn, custom_id, raw_response=str(result))
        if analysis.missing_ids:
            br_dao.mark_request_missing(conn, custom_id)

    record_batch_cost(
        conn, job_id=job.id, batch_id=batch.id,
        input_tokens=total_in_tokens, output_tokens=total_out_tokens,
    )
```

**Test:** `cd backend && uv run pytest tests/worker/test_on_batch_ended.py -v`

Required assertions:
- `test_on_batch_ended_writes_answers_to_clusters`
- `test_on_batch_ended_records_spend`
- `test_on_batch_ended_marks_schema_violation_requests_failed`
- `test_on_batch_ended_marks_request_missing_when_stragglers_present`
- `test_on_batch_ended_skips_unknown_custom_id`

**Done when:**
- [ ] All 5 tests pass.

---

### P08-05 — Completion detection and stragglers decision

**Deps:** P07-02, P08-04
**Files:** `backend/app/worker/poller.py` (extend), `backend/tests/worker/test_completion_decision.py`
**Goal:** After a batch's `_on_batch_ended` runs, decide: are all clusters resolved? If yes, complete the job. If not, and `retry_round < 3`, schedule a retry. Else flag stragglers and complete.

**Implementation:**
```python
async def _finalize_if_done(self, conn, job) -> None:
    from ..dao import clusters as clusters_dao, batches as batches_dao
    from ..jobs.service import transition

    # Are all batches for this job ended?
    batches = batches_dao.list_batches_for_job(conn, job.id)
    if not all(b.status in {"ended", "canceled", "expired"} for b in batches):
        return

    unresolved = clusters_dao.count_unresolved_clusters(conn, job.id)
    if unresolved == 0:
        self._complete_job(conn, job)
        return

    # Need a retry or give up
    current_round = max((b.retry_round for b in batches), default=0)
    if current_round >= 3:
        self._flag_remaining_and_complete(conn, job, error_code="max_retries_exceeded")
        return
    await self._submit_retry(conn, job, current_round + 1)
```

Also implement `_complete_job` (transition to `completed`, update counts and finished_at) and `_flag_remaining_and_complete` (set `error` on all unresolved clusters, then complete).

**Test:** `cd backend && uv run pytest tests/worker/test_completion_decision.py -v`

Required assertions:
- `test_all_resolved_transitions_to_completed`
- `test_unresolved_with_round_lt_3_triggers_retry`
- `test_unresolved_at_round_3_flags_max_retries_exceeded`
- `test_completion_updates_finished_at`
- `test_completion_updates_error_row_count`

**Done when:**
- [ ] All 5 tests pass.

---

### P08-06 — Retry submission

**Deps:** P02-07, P02-08, P02-09, P05-04, P05-08, P06-02, P08-05
**Files:** `backend/app/worker/poller.py` (extend), `backend/tests/worker/test_retry_submission.py`
**Goal:** Build a new batch containing only unresolved clusters, with `titles_per_request` halved. Submit it. Insert `batches` (round+1) and `batch_requests`. Transition job to `retrying` → `submitted`.

**Implementation:**
```python
async def _submit_retry(self, conn, job, new_round: int) -> None:
    from ..dao import clusters as clusters_dao, batches as batches_dao, batch_requests as br_dao
    from ..anthropic.request_builder import build_request_params, TitleInput
    from ..jobs.service import transition, check_cap

    unresolved = [c for c in clusters_dao.list_clusters(conn, job.id) if c.male_es is None and c.error is None]
    new_tpr = max(1, job.titles_per_request // (2 ** new_round))

    # Cost check
    from ..pricing import estimate_cost
    est = estimate_cost(len(unresolved), new_tpr)
    cap = check_cap(conn, est)
    if not cap.ok:
        self._flag_remaining_and_complete(conn, job, error_code="spend_cap_exceeded")
        return

    transition(conn, job.id, "retrying", reason=f"stragglers_round_{new_round}")

    # Build and submit
    from ..dao import task_templates as tt_dao
    template = tt_dao.get_template(conn, job.task_template_id)
    system_prompt = build_system_prompt(template.system_prompt, template.few_shots)  # or import

    request_bodies = []
    request_cluster_groups = []
    for chunk_start in range(0, len(unresolved), new_tpr):
        chunk = unresolved[chunk_start : chunk_start + new_tpr]
        titles = [TitleInput(id=f"t{i+1:03d}", title=c.representative_original) for i, c in enumerate(chunk)]
        req = build_request_params(
            titles=titles,
            system_prompt=system_prompt,
            taxonomy=job.user_taxonomy,
            titles_per_request=len(chunk),
        )
        custom_id = f"{job.id}-r{new_round}-c{chunk_start}"
        request_bodies.append({"custom_id": custom_id, "params": req})
        request_cluster_groups.append((custom_id, [c.id for c in chunk]))

    batch_id = self._client.submit_batch(request_bodies)
    # Find parent batch (most recent round)
    prev_batches = batches_dao.list_batches_for_job(conn, job.id)
    parent_id = max(prev_batches, key=lambda b: b.retry_round).id
    batches_dao.insert_batch(
        conn, id=batch_id, job_id=job.id, retry_round=new_round, parent_batch_id=parent_id,
        status="in_progress", request_count=len(request_bodies),
    )
    for custom_id, cluster_ids in request_cluster_groups:
        br_dao.insert_request(conn, id=custom_id, batch_id=batch_id, cluster_ids=cluster_ids)
    transition(conn, job.id, "submitted", reason=f"retry_round_{new_round}_submitted")
```

**Test:** `cd backend && uv run pytest tests/worker/test_retry_submission.py -v`

Required assertions:
- `test_retry_halves_titles_per_request`
- `test_retry_only_includes_unresolved_clusters`
- `test_retry_increments_round`
- `test_retry_records_parent_batch_id`
- `test_retry_blocks_on_spend_cap_and_flags_stragglers`
- `test_retry_transitions_through_retrying_to_submitted`

**Done when:**
- [ ] All 6 tests pass.

---

### P08-07 — Resume on startup

**Deps:** P02-05, P02-08, P08-03
**Files:** `backend/app/worker/poller.py` (extend), `backend/tests/worker/test_resume.py`
**Goal:** On worker start, immediately run one tick (not delayed by the interval) so jobs that were in flight when the server restarted get picked up.

**Implementation:**
Modify `_run()`:
```python
async def _run(self) -> None:
    log.info("worker.started")
    # Immediate first tick
    try:
        await self.tick()
    except Exception as e:
        log.error("worker.error", exc_info=e)
    self.last_tick_at = time.time()
    while not self._stop.is_set():
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=self._tick_interval)
        except asyncio.TimeoutError:
            try:
                await self.tick()
            except Exception as e:
                log.error("worker.error", exc_info=e)
            self.last_tick_at = time.time()
```

Also: on first tick after startup, handle any jobs stuck in `queued` (the pathological case where the server crashed between insert and submit) by transitioning them to `failed` with reason `restart_during_queue`.

**Test:** `cd backend && uv run pytest tests/worker/test_resume.py -v`

Required assertions:
- `test_first_tick_runs_immediately_on_start`
- `test_queued_job_on_startup_transitioned_to_failed`
- `test_submitted_job_polled_immediately`

**Done when:**
- [ ] All 3 tests pass.

---

### P08-08 — End-to-end happy path (mocked)

**Deps:** P07-06, P08-01..P08-07
**Files:** `backend/tests/worker/test_e2e_happy.py`
**Goal:** A single test that walks a job from preview → commit → worker tick → batch complete → all clusters resolved → job completed.

Note: Dry-run happy path is tested in P07-11, not here. The worker E2E tests cover real (mocked) Anthropic flow only.

**Implementation:**
- Use a small synthetic input (20 titles, 5 clusters).
- Use `FakeAnthropicBatchClient`.
- Commit job.
- Simulate batch completion by calling `fake_client.complete_batch(batch_id, results=[...])` with valid results for all 5 clusters.
- Call `worker.tick()` manually.
- Assert: job status = `completed`, all clusters have answers, `error_rows == 0`.

**Test:** `cd backend && uv run pytest tests/worker/test_e2e_happy.py -v`

Required assertions:
- `test_e2e_happy_path_completes`
- `test_e2e_happy_path_all_clusters_populated`
- `test_e2e_happy_path_spend_log_entry_recorded`

**Done when:**
- [ ] All 3 assertions pass.

---

### P08-09 — End-to-end with stragglers recovery

**Deps:** P08-08
**Files:** `backend/tests/worker/test_e2e_stragglers.py`
**Goal:** Mock Anthropic to return N-1 results on the initial batch, triggering a retry that recovers the missing one.

**Implementation:**
- Commit a job of 10 clusters, TPR=10.
- Complete initial batch with 9 results (missing cluster index 5).
- Call `worker.tick()` — should see stragglers, submit retry.
- Complete retry batch with the 1 missing result.
- Call `worker.tick()` again — should complete the job.
- Assert: all 10 clusters populated, job status = `completed`, `error_rows == 0`, 2 `batches` rows total (round 0 and round 1).

**Test:** `cd backend && uv run pytest tests/worker/test_e2e_stragglers.py -v`

Required assertions:
- `test_e2e_stragglers_recovered_via_retry`
- `test_e2e_two_batch_rows_after_retry`
- `test_e2e_final_state_is_completed_not_failed`

**Done when:**
- [ ] All 3 pass.
