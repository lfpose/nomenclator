# 07 — Job Service Layer

The orchestration layer sitting between HTTP handlers and the DAOs. Enforces the state machine, single-concurrency, and cap checks.

Reference: `spec/07-job-lifecycle.md`.

---

### P07-01 — State machine validator

**Deps:** P01-02
**Files:** `backend/app/jobs/state_machine.py`, `backend/tests/jobs/test_state_machine.py`
**Goal:** Pure function: given `(from_state, to_state)`, return True iff the transition is allowed.

**Implementation:**
```python
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft":     {"preview", "cancelled"},
    "preview":   {"preview", "queued", "cancelled"},
    "queued":    {"submitted", "failed", "cancelled"},
    "submitted": {"polling", "cancelled", "failed"},
    "polling":   {"polling", "retrying", "completed", "failed", "cancelled"},
    "retrying":  {"submitted", "completed", "failed", "cancelled"},
    "completed": set(),
    "failed":    set(),
    "cancelled": set(),
}

def is_allowed(from_state: str, to_state: str) -> bool:
    return to_state in ALLOWED_TRANSITIONS.get(from_state, set())

def assert_allowed(from_state: str, to_state: str) -> None:
    if not is_allowed(from_state, to_state):
        raise ValueError(f"Invalid transition: {from_state} -> {to_state}")
```

**Test:** `cd backend && uv run pytest tests/jobs/test_state_machine.py -v`

Required assertions:
- `test_allowed_draft_to_preview`
- `test_allowed_preview_to_queued`
- `test_allowed_polling_to_completed`
- `test_disallowed_completed_to_anything`
- `test_disallowed_failed_to_anything`
- `test_disallowed_cancelled_to_anything`
- `test_disallowed_skip_states` — `draft → submitted` disallowed.
- `test_assert_allowed_raises_on_invalid`

**Done when:**
- [ ] All 8 tests pass.

---

### P07-02 — Job transition with logging

**Deps:** P02-05, P07-01
**Files:** `backend/app/jobs/service.py`, `backend/tests/jobs/test_transition.py`
**Goal:** Single function to transition a job, validating via state machine, logging the change.

**Implementation:**
```python
import logging
from ..dao import jobs as jobs_dao
from .state_machine import assert_allowed

log = logging.getLogger("nomenclator.jobs")

def transition(conn, job_id: str, new_status: str, reason: str) -> None:
    job = jobs_dao.get_job(conn, job_id)
    if job is None:
        raise ValueError(f"job not found: {job_id}")
    assert_allowed(job.status, new_status)
    jobs_dao.update_job_status(conn, job_id, new_status)
    log.info(
        "job.transition",
        extra={"job_id": job_id, "from": job.status, "to": new_status, "reason": reason},
    )
```

**Test:** `cd backend && uv run pytest tests/jobs/test_transition.py -v`

Required assertions:
- `test_transition_draft_to_preview_updates_db`
- `test_transition_raises_on_invalid_from_state`
- `test_transition_raises_on_missing_job`
- `test_transition_logs_structured_event` — use `caplog` to assert `job_id`, `from`, `to`, `reason` are in the record.

**Done when:**
- [ ] All 4 tests pass.

---

### P07-03 — Single-concurrency check

**Deps:** P02-05
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_concurrency.py`
**Goal:** Function that raises if any non-terminal job exists.

**Implementation:**
```python
class ConcurrencyError(Exception):
    pass

def assert_no_running_job(conn) -> None:
    if jobs_dao.count_active_jobs(conn) > 0:
        raise ConcurrencyError("job_already_running")
```

**Test:** `cd backend && uv run pytest tests/jobs/test_concurrency.py -v`

Required assertions:
- `test_no_running_job_when_empty`
- `test_raises_when_polling_job_exists`
- `test_raises_when_retrying_job_exists`
- `test_does_not_raise_when_only_completed_jobs`

**Done when:**
- [ ] All 4 tests pass.

---

### P07-04 — Create job from preview

**Deps:** P02-05, P02-06, P02-07, P03-04, P04-06, P06-01, P07-02
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_create_from_preview.py`
**Goal:** Top-level function: `create_preview_job(conn, *, file_bytes, text, threshold, titles_per_request) -> PreviewResult`.

**Implementation:**
- Call `ingest()` from `csv_io.ingest`.
- Call `run_clustering()` from `cluster.pipeline`.
- Call `jobs_dao.create_job()`.
- Bulk-insert `job_rows` with `row_index`.
- Insert `clusters` rows and update `job_rows.cluster_id`.
- Compute cost estimate via `estimate_job_cost`.
- Update job counts.
- Return a `PreviewResult` with counts, cost, top 10 clusters.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PreviewResult:
    job_id: str
    total_rows: int
    exact_unique_rows: int
    cluster_count: int
    largest_cluster_size: int
    est_cost_usd: float
    top_clusters: list[dict]  # {representative, member_count, members}
    warnings: list[dict]       # {type, cluster_id, ...}
```

**Test:** `cd backend && uv run pytest tests/jobs/test_create_from_preview.py -v`

Required assertions:
- `test_preview_creates_job_with_status_preview`
- `test_preview_writes_all_job_rows`
- `test_preview_writes_clusters_with_representatives`
- `test_preview_assigns_cluster_id_to_every_row`
- `test_preview_computes_cost_estimate`
- `test_preview_returns_top_10_largest_clusters`
- `test_preview_emits_large_cluster_warning_above_50`
- `test_preview_propagates_ingest_errors`

**Done when:**
- [ ] All 8 tests pass.

---

### P07-05 — Recluster existing job

**Deps:** P07-04
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_recluster.py`
**Goal:** Given an existing job in `preview`, re-run clustering with a new threshold.

**Implementation:**
- Fetch existing `job_rows` for the job (reuse the cached normalized values from the DB).
- `DELETE FROM clusters WHERE job_id = ?`.
- `UPDATE job_rows SET cluster_id = NULL, is_representative = 0`.
- Run `run_clustering` with new threshold.
- Insert new clusters, update cluster_id on rows.
- Update job counts and cost estimate.
- Return `PreviewResult`.

Validate state must be `preview` or raise `invalid_state`.

**Test:** `cd backend && uv run pytest tests/jobs/test_recluster.py -v`

Required assertions:
- `test_recluster_replaces_previous_clusters`
- `test_recluster_preserves_job_rows_and_originals`
- `test_recluster_updates_cost_estimate`
- `test_recluster_raises_on_non_preview_state`
- `test_recluster_stricter_threshold_produces_more_clusters`

**Done when:**
- [ ] All 5 tests pass.

---

### P07-06 — Commit job

**Deps:** P02-08, P02-09, P04-06, P05-04, P05-08, P06-02, P07-03, P07-04
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_commit.py`
**Goal:** Commit a previewed job: cap check, concurrency check, build batch requests, submit to Anthropic, persist batches + batch_requests, transition to `submitted`.

**Implementation:**
- Must be in `preview` state; otherwise raise `invalid_state`.
- `assert_no_running_job(conn)`.
- Load clusters. Build per-request `TitleInput` groups of size `titles_per_request` (last request may be short → handle by either padding with a sentinel skipped or allowing a single smaller request; v1 decision: allow final request to be smaller and construct the tool schema with matching min/max).
- For each group, build request params via `build_request_params`.
- Compute total estimated cost from actual cluster count + `titles_per_request`.
- Run `check_cap`; if not ok, raise `SpendCapExceeded`.
- Call `client.submit_batch(requests)`.
- Persist `batches` row (retry_round=0) and `batch_requests` rows with `cluster_ids`.
- Transition job to `submitted`.

Note on the last-request-smaller handling: in `build_tool_schema`, the tool schema's `minItems`/`maxItems` must match the *current group's* size. Different requests in the same batch may have different schemas. That is allowed by Anthropic.

**Test:** `cd backend && uv run pytest tests/jobs/test_commit.py -v`

Required assertions (use `FakeAnthropicBatchClient`):
- `test_commit_builds_batch_requests`
- `test_commit_transitions_to_submitted`
- `test_commit_raises_on_non_preview_state`
- `test_commit_raises_on_spend_cap_exceeded`
- `test_commit_raises_on_concurrent_job`
- `test_commit_persists_batch_and_batch_requests`
- `test_commit_persists_cluster_ids_json`
- `test_commit_handles_last_smaller_request`

**Done when:**
- [ ] All 8 tests pass.

---

### P07-07 — Cancel job

**Deps:** P02-05, P02-08, P05-08, P07-02
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_cancel.py`
**Goal:** Cancel a job in a cancellable state.

**Implementation:**
```python
def cancel_job(conn, client, job_id: str) -> None:
    job = jobs_dao.get_job(conn, job_id)
    if job is None:
        raise ValueError("job_not_found")
    if job.status not in {"queued", "submitted", "polling", "retrying"}:
        raise ValueError("invalid_state")
    # Cancel any non-terminal batches upstream
    for batch in batches_dao.list_batches_for_job(conn, job_id):
        if batch.status not in {"ended", "canceled", "expired"}:
            try:
                client.cancel_batch(batch.id)
            except Exception:
                pass  # best effort
    transition(conn, job_id, "cancelled", reason="operator_cancel")
```

**Test:** `cd backend && uv run pytest tests/jobs/test_cancel.py -v`

Required assertions:
- `test_cancel_transitions_to_cancelled`
- `test_cancel_calls_anthropic_cancel_for_inflight_batches`
- `test_cancel_ignores_already_ended_batches`
- `test_cancel_raises_on_terminal_state`
- `test_cancel_swallows_anthropic_cancel_errors`

**Done when:**
- [ ] All 5 tests pass.

---

### P07-08 — Record actual cost on batch completion

**Deps:** P02-10, P05-01, P06-03, P07-02
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_record_cost.py`
**Goal:** Helper called by the worker after parsing batch results.

**Implementation:**
```python
def record_batch_cost(
    conn, *, job_id: str, batch_id: str, input_tokens: int, output_tokens: int
) -> float:
    from .estimator import record_actual_spend
    return record_actual_spend(
        conn, job_id=job_id, batch_id=batch_id,
        input_tokens=input_tokens, output_tokens=output_tokens,
    )
```

**Test:** `cd backend && uv run pytest tests/jobs/test_record_cost.py -v`

Required assertions:
- `test_record_batch_cost_inserts_spend_log_entry`
- `test_record_batch_cost_returns_usd`

**Done when:**
- [ ] Both tests pass.

---

### P07-09 — Create preview with row subset

**Deps:** P03-07, P07-04
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_preview_subset.py`
**Goal:** Extend `create_preview_job` to accept `row_subset_mode` and `row_subset_n`, applying the subset before clustering.

**Implementation:**
```python
def create_preview_job(
    conn, *, file_bytes, text, threshold, titles_per_request,
    row_subset_mode="all", row_subset_n=None,
) -> PreviewResult:
    rows = ingest(file_bytes=file_bytes, text=text)
    total_input_rows = len(rows)
    rows = apply_row_subset(rows, row_subset_mode, row_subset_n, job_id)
    # ... rest of pipeline on the subset ...
```

The PreviewResult now includes `total_input_rows` (before subset) and `selected_rows` (after subset).

**Test:** `cd backend && uv run pytest tests/jobs/test_preview_subset.py -v`

Required assertions:
- `test_preview_all_mode_processes_all_rows`
- `test_preview_first_n_processes_only_n_rows`
- `test_preview_random_n_processes_only_n_rows`
- `test_preview_subset_larger_than_input_uses_all`
- `test_preview_stores_row_subset_mode_on_job`
- `test_preview_result_includes_total_and_selected_counts`

**Done when:**
- [ ] All 6 tests pass.

---

### P07-10 — Prompt review service

**Deps:** P05-10
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_prompt_review.py`
**Goal:** Thin wrapper that calls the prompt review client and handles errors gracefully.

**Implementation:**
```python
from ..anthropic.review import review_prompt, PromptReview

def review_operator_prompt(api_key: str, prompt: str, few_shots: str) -> PromptReview:
    return review_prompt(api_key, prompt, few_shots)
```

In the event of an API error, catch and raise `APIError("prompt_review_failed", ...)` with a user-friendly message.

**Test:** `cd backend && uv run pytest tests/jobs/test_prompt_review.py -v`

Required assertions:
- `test_review_returns_prompt_review_object`
- `test_review_propagates_api_errors_as_api_error`

**Done when:**
- [ ] Both tests pass.

---

### P07-11 — Dry-run mode in commit

**Deps:** P05-11, P07-06
**Files:** `backend/app/jobs/service.py` (extend), `backend/tests/jobs/test_commit_dry_run.py`
**Goal:** When `is_dry_run=True` is passed to `commit_job`, skip Anthropic submission. Instead, generate fake responses for all clusters immediately, write them, and transition directly to `completed`.

**Implementation:**
```python
def commit_job(conn, client, job_id, params) -> None:
    # ... existing validation ...
    is_dry_run = params.get("is_dry_run", False)
    if is_dry_run:
        jobs_dao.update_job_status(conn, job_id, "submitted")
        # Generate fake responses for all clusters
        clusters = clusters_dao.list_clusters(conn, job_id)
        from ..anthropic.dry_run import generate_dry_run_results
        for chunk_start in range(0, len(clusters), job.titles_per_request):
            chunk = clusters[chunk_start:chunk_start + job.titles_per_request]
            fake = generate_dry_run_results(
                [c.id for c in chunk],
                [c.representative_original for c in chunk],
            )
            for i, c in enumerate(chunk):
                clusters_dao.update_cluster_answers(
                    conn, c.id,
                    male_es=fake.results[i].male_es,
                    female_es=fake.results[i].female_es,
                    category=fake.results[i].category,
                )
        # Record $0 spend
        spend_log.insert_spend(conn, job_id=job_id, batch_id=None, usd=0, at=int(time.time()))
        transition(conn, job_id, "completed", reason="dry_run_complete")
        return
    # ... existing Anthropic submission logic ...
```

**Test:** `cd backend && uv run pytest tests/jobs/test_commit_dry_run.py -v`

Required assertions:
- `test_dry_run_commit_skips_anthropic_client`
- `test_dry_run_commit_generates_fake_answers`
- `test_dry_run_commit_transitions_to_completed`
- `test_dry_run_commit_records_zero_spend`
- `test_dry_run_commit_skips_cap_check`
- `test_dry_run_commit_sets_is_dry_run_on_job`

**Done when:**
- [ ] All 6 tests pass.
