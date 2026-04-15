# 18 — Reliability Contract

The single most load-bearing document in this spec. If an implementation change breaks anything here, fix the implementation — do not weaken the contract.

## The hard promise

> **Every row in the uploaded CSV corresponds to exactly one row in the downloaded CSV, in the same order.**
>
> Every output row is in one of two states:
> - **Populated** — `male_es`, `female_es`, `category` filled, `error` empty.
> - **Flagged** — `error` contains a machine-readable code; the three answer columns may be empty or best-effort.
>
> No row is ever silently dropped. No row is ever duplicated. Order is preserved byte-for-byte on the row axis.

This holds for jobs in state `completed`. A job in `failed` produces no file at all — this is a feature, not a loophole. Partial CSVs are never returned.

### Partial runs

For jobs with `row_subset_mode != 'all'`, the invariant applies to the *selected* subset, not the full input file. If the operator selects "First 100 rows" from a 13,600-row file, the output CSV has exactly 100 rows. The `total_rows` field on the job reflects the subset size for invariant purposes.

### Dry-run jobs

Dry-run jobs enforce the same row-count invariant with fake data. The pre-write assertion still fires. This is by design — dry runs exist to validate the pipeline, and the invariant is part of the pipeline.

## Enforcement layers (reference: diagram 12 in `solution-overview.md`)

### Layer 0 — Clustering shrinks the problem surface

The LLM only ever sees cluster representatives, ~2,500 of them from 13,600 input rows. The 13,600 → 13,600 expansion happens as a pure SQL join on `cluster_id`, not inside the LLM loop. The guarantee becomes "N reps go in, N rep results come back" — much more tractable than "N rows go in, N rows come back through an LLM."

### Layer 1 — Anthropic tool use with forced `tool_choice`

Every request sets:
```python
tool_choice = {"type": "tool", "name": "emit_standardized_titles"}
tools       = [EMIT_STANDARDIZED_TITLES_TOOL]
```
The model cannot respond with prose. It cannot invent a different tool. It must produce a tool call whose arguments validate against our JSON schema. The schema has `minItems == maxItems == titles_per_request`, so the model must produce exactly the right number of entries.

### Layer 2 — Explicit per-title IDs, set-based diff

Every title is assigned an `id` of the form `t001`, `t002`, ... when packed into a request. The response must carry the same IDs. We compare sets, never positions:

```python
expected_ids = set(expected)
returned_ids = {r["id"] for r in response["results"]}

missing = expected_ids - returned_ids  # stragglers
extra   = returned_ids - expected_ids  # hallucinated; log + drop
```

Positional matching is forbidden everywhere in the codebase. Even when the lengths match, we look up by ID.

### Layer 3 — Sized `max_tokens`

For every request:
```python
max_tokens = titles_per_request * 80 + 200
```
80 tokens per title is 2–3× the expected per-title output; the +200 covers JSON overhead. Tight enough to fail loudly on pathological behavior, generous enough to never truncate on normal input. Retries use a new computation based on the halved TPR.

### Layer 4 — Pydantic parse-or-fail

Every raw response is parsed into a Pydantic model that mirrors the JSON schema. Any validation failure (missing field, wrong type, extra field) marks the entire `batch_request` as `status = failed` and the error code as `schema_violation`. **We do not try to salvage partial JSON.** Half-parsed output is worse than no output because it can silently corrupt the database.

### Layer 5 — Stragglers retry loop

After parsing all requests in a batch, collect all missing cluster IDs across all requests into a single pile. If the pile is non-empty and `retry_round < 3`, halve `titles_per_request` (25 → 12 → 6 → 1) and submit a new batch containing only those stragglers. Repeat until the pile is empty or the round budget is exhausted.

When the round budget is exhausted, flag the remaining stragglers' clusters with `error = max_retries_exceeded` and complete the job.

### Layer 6 — Row-count invariant as explicit code

Before writing the output CSV, run:

```python
assert len(output_rows) == len(input_rows), \
    f"Row count drift: in={len(input_rows)} out={len(output_rows)}"
```

If this ever fires, the job transitions to `failed` with reason `row_count_assertion`. A full crash report is logged with both counts and a sample of the first mismatched row. The operator gets an error, never a partial CSV.

### Layer 7 — Determinism of the export path

The export is a single SQL query:

```sql
SELECT
  jr.original,
  COALESCE(c.male_es, '')   AS male_es,
  COALESCE(c.female_es, '') AS female_es,
  COALESCE(c.category, '')  AS category,
  COALESCE(c.error, '')     AS error
FROM job_rows jr
LEFT JOIN clusters c ON jr.cluster_id = c.id
WHERE jr.job_id = :job_id
ORDER BY jr.row_index ASC;
```

Every `job_row` is in the output. Every row's ordering comes from `row_index`. The `LEFT JOIN` + `COALESCE` means a row whose cluster is missing (should never happen, but if it does) still gets an entry with blank answers — not a dropped row.

## Full error code table (for `clusters.error`)

| Code | Meaning | When it's set |
|---|---|---|
| `max_retries_exceeded` | Stragglers survived all 3 retry rounds | Round 3 complete, still missing |
| `schema_violation` | The request's response failed Pydantic validation | At parse time, inherited by all clusters in that request if there's no recovery |
| `tool_call_missing` | Model returned prose instead of invoking the tool | At parse time |
| `truncated` | Response hit `max_tokens` and was cut off | At parse time (detected via `stop_reason`) |
| `spend_cap_exceeded` | A retry would have pushed monthly spend over cap | At retry submission check |
| `anthropic_error` | Anthropic returned a per-request error in the batch results | At parse time |
| `blank_after_normalize` | (reserved; see OQ-01) | Currently unused; preview fails instead |

A populated row has `error = NULL`. The frontend treats empty string and NULL identically.

## HTTP error codes (for `error.code` in response envelope)

Returned to the client as `{ "error": { "code": "...", "message": "...", "details": {} } }`. These are distinct from the per-row cluster error codes above.

| Code | HTTP | Meaning |
|---|---|---|
| `unauthenticated` | 401 | Session missing or expired |
| `rate_limited` | 429 | Too many requests |
| `encoding_invalid` | 400 | Non-UTF-8 upload |
| `delimiter_unknown` | 400 | CSV delimiter couldn't be detected |
| `input_empty` | 400 | Zero data rows |
| `input_too_large` | 400 | > 50,000 rows |
| `input_contains_blank_rows` | 400 | Some row normalizes to empty |
| `job_not_found` | 404 | No job with that ID |
| `invalid_state` | 409 | Operation not valid in the job's current state |
| `spend_cap_exceeded` | 409 | Estimated cost would exceed monthly cap |
| `job_already_running` | 409 | Single-concurrency rule |
| `bad_threshold` | 400 | Threshold outside 50–100 |
| `bad_titles_per_request` | 400 | TPR outside 1–50 |
| `internal_error` | 500 | Unexpected server error |

## The test suite that guards the contract

A dedicated pytest module (`tests/test_reliability_contract.py`) asserts:

1. **Ingestion → export equals input count** for synthetic fixtures of 1, 100, 1000, 10000 rows.
2. **Row order is preserved** via explicit `row_index` checks.
3. **Every input row is in the output** (set comparison).
4. **Duplicates in the input remain duplicates in the output** with the same answers.
5. **Mocking Anthropic to return N-1 rows for a request** triggers the stragglers retry, which recovers the missing row.
6. **Mocking Anthropic to return malformed JSON for a request** marks that request `schema_violation` and retries.
7. **Mocking Anthropic to always fail one specific title** exhausts retries and produces a flagged row with `max_retries_exceeded`. Row count still matches.
8. **Mocking the spend cap to reject retries** flags remaining stragglers with `spend_cap_exceeded`. Row count still matches. Job is `completed`, not `failed`.
9. **The pre-write assertion fires** when a test forces a count mismatch, and the job transitions to `failed` with no CSV produced.

These tests are mandatory. Breaking any of them breaks the contract. CI (when it exists) must run them on every commit.

## What the contract does NOT guarantee

Honesty: there are things the contract does not promise. Listed explicitly so no one misreads the promise:

- **Semantic correctness.** The Spanish standardized titles may be wrong — the contract is structural, not semantic. Bad outputs with `error = NULL` are possible (e.g. the model produces a plausible but wrong translation). The operator still needs to sanity-check.
- **Zero cluster failures.** Some titles may legitimately fail all retries. Those rows appear in the output with an error code and no answer. This is compliant with the contract.
- **Sub-second latency.** The contract is about correctness, not speed.
- **Anthropic uptime.** If Anthropic is down, jobs transition to `failed`. The operator cannot download a CSV in that case. This is not a contract violation.
- **Disk integrity.** The contract assumes SQLite is healthy. A corrupted Fly volume can silently break anything. Operational concern, not architectural.
