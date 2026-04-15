# 12 — Reliability Test Suite

The 9 mandatory tests from `spec/18-reliability-contract.md`. Every one is a task. Every task is a full scenario, end-to-end, using `FakeAnthropicBatchClient`. If any of these fail, the row-count invariant is broken.

Note: Dry-run reliability is covered by P07-11 (synchronous completion with invariant enforcement). The tests below cover real (mocked) Anthropic flow.

All tests live in `backend/tests/reliability/`.

---

### P12-01 — Test 1: Row count equals input across sizes

**Deps:** P08-09, P11-03
**Files:** `backend/tests/reliability/test_01_row_count.py`
**Goal:** For fixtures of 1, 100, 1000, and 10000 rows, a successful run produces an output CSV with exactly that many data rows (excluding header).

**Implementation:**
```python
import pytest

@pytest.mark.parametrize("n_rows", [1, 100, 1000, 10000])
def test_row_count_equals_input(n_rows, conn, fake_anthropic, run_e2e):
    job_id = run_e2e(n_rows=n_rows, conn=conn, fake=fake_anthropic)
    csv_bytes = export_job_to_csv(conn, job_id)
    data_rows = csv_bytes.decode("utf-8-sig").splitlines()[1:]  # skip header
    assert len(data_rows) == n_rows
```

`run_e2e` is a helper fixture that: creates a preview job, commits, completes the fake batch with synthetic answers, runs one worker tick, returns the job id.

**Test:** `cd backend && uv run pytest tests/reliability/test_01_row_count.py -v`

Required assertions:
- `test_row_count_equals_input[1]`
- `test_row_count_equals_input[100]`
- `test_row_count_equals_input[1000]`
- `test_row_count_equals_input[10000]`

**Done when:**
- [ ] All 4 parametric cases pass.

---

### P12-02 — Test 2: Row order preserved

**Deps:** P12-01
**Files:** `backend/tests/reliability/test_02_row_order.py`
**Goal:** The output CSV's `original` column, in order, matches the input row ordering exactly.

**Implementation:**
Feed an input where every row is a distinct title (e.g. `"Title {i}"`). After export, zip the data rows with the input list and assert each `original` matches position.

**Test:** `cd backend && uv run pytest tests/reliability/test_02_row_order.py -v`

Required assertions:
- `test_row_order_preserved_exactly`
- `test_row_order_after_clustering_still_matches_input`

**Done when:**
- [ ] Both tests pass.

---

### P12-03 — Test 3: Every input row is in output

**Deps:** P12-01
**Files:** `backend/tests/reliability/test_03_input_output_set.py`
**Goal:** Set of `original` values in output equals set of input values (accounting for duplicates).

**Implementation:**
Use an input with duplicates and unique values mixed. Assert `Counter(input) == Counter(output[original])`.

**Test:** `cd backend && uv run pytest tests/reliability/test_03_input_output_set.py -v`

Required assertions:
- `test_output_multiset_equals_input_multiset`
- `test_no_hallucinated_rows`

**Done when:**
- [ ] Both tests pass.

---

### P12-04 — Test 4: Duplicates get identical answers

**Deps:** P12-01
**Files:** `backend/tests/reliability/test_04_duplicates_consistent.py`
**Goal:** If the same `original` appears 10 times in the input, all 10 output rows have the same `male_es`, `female_es`, `category`.

**Implementation:**
Input has 10 × `"Jefe de Compras"` + 5 other titles. After export, group output by `original`, assert all 10 rows for `"Jefe de Compras"` are byte-identical in the answer columns.

**Test:** `cd backend && uv run pytest tests/reliability/test_04_duplicates_consistent.py -v`

Required assertions:
- `test_all_duplicate_originals_have_same_male_es`
- `test_all_duplicate_originals_have_same_female_es`
- `test_all_duplicate_originals_have_same_category`

**Done when:**
- [ ] All 3 pass.

---

### P12-05 — Test 5: Stragglers recovered via retry

**Deps:** P08-09
**Files:** `backend/tests/reliability/test_05_stragglers_recovered.py`
**Goal:** Mock Anthropic to return N-1 results on the first batch, all results on the retry. Final output has all rows populated, error_rows == 0.

**Implementation:**
Same as P08-09 but focused on the output CSV. Assert:
- Final job status is `completed`.
- All rows in the CSV are populated.
- `error` column is empty for every row.
- There are exactly 2 `batches` rows for the job.

**Test:** `cd backend && uv run pytest tests/reliability/test_05_stragglers_recovered.py -v`

Required assertions:
- `test_stragglers_recovered_final_csv_all_populated`
- `test_stragglers_recovery_produces_two_batches`
- `test_stragglers_recovery_error_rows_is_zero`

**Done when:**
- [ ] All 3 pass.

---

### P12-06 — Test 6: Malformed JSON triggers schema_violation

**Deps:** P08-04, P11-03
**Files:** `backend/tests/reliability/test_06_malformed_json.py`
**Goal:** Mock Anthropic to return results where one request has `stop_reason == "end_turn"` but no `tool_use` block, and another has an invalid schema (missing `male_es`). Both should be marked `schema_violation`/`tool_call_missing` and retried.

**Implementation:**
- First batch: 3 requests, 1 clean, 1 malformed (missing tool_use), 1 schema-invalid.
- Expect stragglers from the 2 broken requests.
- Second batch: all clean.
- Assert final state: `completed`, all rows populated.

**Test:** `cd backend && uv run pytest tests/reliability/test_06_malformed_json.py -v`

Required assertions:
- `test_malformed_request_marked_schema_violation`
- `test_missing_tool_call_marked_tool_call_missing`
- `test_both_recovered_in_retry`
- `test_final_csv_all_populated`

**Done when:**
- [ ] All 4 pass.

---

### P12-07 — Test 7: Persistent failure → max_retries_exceeded

**Deps:** P08-06
**Files:** `backend/tests/reliability/test_07_max_retries.py`
**Goal:** Mock Anthropic so one specific title ID is *always* missing from the response, across all retry rounds. After 3 retries, the cluster should be flagged `max_retries_exceeded`, and the job should still `completed` (not `failed`).

**Implementation:**
Return N-1 results on every retry round, always missing the same ID. Run the worker enough times to exhaust retries. Assert:
- Job status is `completed`.
- `error_rows == 1` (the one persistently failing row's cluster members).
- The output CSV has `error == "max_retries_exceeded"` for those rows, empty answer columns.
- Total row count still equals input count.

**Test:** `cd backend && uv run pytest tests/reliability/test_07_max_retries.py -v`

Required assertions:
- `test_persistent_failure_ends_in_completed_not_failed`
- `test_flagged_rows_have_max_retries_exceeded_error_code`
- `test_flagged_rows_count_matches_expected_cluster_size`
- `test_total_row_count_unchanged`

**Done when:**
- [ ] All 4 pass.

---

### P12-08 — Test 8: Spend cap during retry flags stragglers

**Deps:** P08-06, P06-02
**Files:** `backend/tests/reliability/test_08_cap_during_retry.py`
**Goal:** Simulate a spend log that's just under the cap. The initial batch returns stragglers. The retry's estimated cost would push us over → retry is refused, stragglers flagged `spend_cap_exceeded`, job still `completed`.

**Implementation:**
- Pre-seed `spend_log` with $19.90 of historical spend.
- Set `MONTHLY_SPEND_CAP_USD = 20.0`.
- Commit a job; complete first batch with stragglers.
- Worker tick should attempt retry → cap check fails → stragglers flagged.
- Assert job is `completed`, not `failed`; stragglers have `error == "spend_cap_exceeded"`.

**Test:** `cd backend && uv run pytest tests/reliability/test_08_cap_during_retry.py -v`

Required assertions:
- `test_retry_refused_by_cap_flags_stragglers`
- `test_job_status_is_completed_not_failed`
- `test_flagged_rows_carry_spend_cap_exceeded_code`
- `test_output_row_count_unchanged`

**Done when:**
- [ ] All 4 pass.

---

### P12-09 — Test 9: Pre-write assertion fires on drift

**Deps:** P11-03
**Files:** `backend/tests/reliability/test_09_drift_assertion.py`
**Goal:** Force a count mismatch (delete a `job_row` directly via SQL after the job is completed but before download) and assert the download fails with 500 + the job transitions to `failed`.

**Implementation:**
```python
def test_drift_assertion_fires(logged_in_client, conn, fake_anthropic, run_e2e):
    job_id = run_e2e(n_rows=10, ...)
    # Corrupt the database
    conn.execute("DELETE FROM job_rows WHERE job_id = ? AND row_index = 5", (job_id,))
    r = logged_in_client.get(f"/jobs/{job_id}/download")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    from app.dao.jobs import get_job
    assert get_job(conn, job_id).status == "failed"
```

**Test:** `cd backend && uv run pytest tests/reliability/test_09_drift_assertion.py -v`

Required assertions:
- `test_drift_assertion_fires_returns_500`
- `test_drift_transitions_job_to_failed`
- `test_drift_never_returns_csv_bytes`

**Done when:**
- [ ] All 3 pass.

---

### P12-10 — Test 10: Partial run row count matches subset

**Deps:** P03-07, P12-01
**Files:** `backend/tests/reliability/test_10_partial_run.py`
**Goal:** A partial run (first_n=50 from a 500-row input) produces a CSV with exactly 50 rows.

**Implementation:**
Run a full E2E with `row_subset_mode="first_n"`, `row_subset_n=50`, on a 500-row input. Assert output CSV has exactly 50 data rows, all populated.

**Test:** `cd backend && uv run pytest tests/reliability/test_10_partial_run.py -v`

Required assertions:
- `test_partial_run_output_has_exactly_n_rows`
- `test_partial_run_rows_are_first_n_from_input`
- `test_partial_run_all_rows_populated`

**Done when:**
- [ ] All 3 pass.

---

## Gate: the reliability phase is the hardest gate in the plan

**Do not proceed to Phase 13 (frontend) until every test in this file is green.** If any test is red, either the implementation is broken and must be fixed, or the test is wrong — in which case fix the test, do not weaken the contract.
