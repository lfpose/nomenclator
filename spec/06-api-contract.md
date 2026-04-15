# 06 — API Contract

All endpoints are JSON unless noted. All authenticated endpoints require a valid `sid` session cookie; omit and you get 401. Errors have a consistent shape. Times are ISO 8601 strings on the wire (the DB stores Unix seconds; conversion happens at serialization).

## Error envelope

```json
{
  "error": {
    "code": "spend_cap_exceeded",
    "message": "Monthly cap $20 would be exceeded (used: $18.30, estimated: $2.10). Cap resets 2026-05-10.",
    "details": { "used_usd": 18.30, "estimated_usd": 2.10, "reset_date": "2026-05-10" }
  }
}
```

Error codes used in HTTP responses:

| Code | HTTP | Meaning |
|---|---|---|
| `unauthenticated` | 401 | No or invalid session cookie. |
| `rate_limited` | 429 | Too many attempts. |
| `encoding_invalid` | 400 | Uploaded file isn't UTF-8. |
| `delimiter_unknown` | 400 | CSV delimiter wasn't comma or semicolon. |
| `input_empty` | 400 | Zero data rows after parsing. |
| `input_too_large` | 400 | More rows than the 50k hard cap. |
| `job_not_found` | 404 | No job with that id (or not yours). |
| `invalid_state` | 409 | Operation not valid in current job state. |
| `spend_cap_exceeded` | 409 | Estimated cost would exceed monthly cap. |
| `job_already_running` | 409 | V1 single-concurrency rule. |
| `bad_threshold` | 400 | Threshold out of 50–100 range. |
| `bad_titles_per_request` | 400 | TPR out of 1–50 range. |
| `bad_row_subset` | 400 | Row subset N out of range or mode invalid. |
| `prompt_review_failed` | 500 | Prompt review API call failed (non-critical, shown as warning). |
| `internal_error` | 500 | Unexpected server error. |

## Endpoints

### `POST /auth`

Request:
```json
{ "password": "..." }
```
Response 200:
```json
{ "ok": true }
```
Sets `Set-Cookie: sid=...; HttpOnly; Secure; SameSite=Lax; Max-Age=2592000`.

On failure: 401 with `unauthenticated`, rate-limited to 5/min/IP.

### `GET /me`

Authenticated. Returns 200 `{ "authenticated": true }` or 401.

### `POST /auth/logout`

Authenticated. Deletes the session row, clears the cookie. Returns 200.

---

### `POST /jobs/review-prompt`

Authenticated. Request:
```json
{
  "prompt": "Eres un asistente especializado...",
  "few_shots": "[{\"input\": \"...\", ...}]"
}
```

Makes a single non-batch call to Claude Haiku with a meta-prompt that evaluates the operator's prompt and few-shot examples for quality and safety.

Response 200:
```json
{
  "safe": true,
  "quality_score": "good",
  "issues": [],
  "suggestions": ["Consider adding a gender-neutral example"],
  "summary": "The prompt is well-structured for job title standardization..."
}
```

`quality_score` is one of: `"good"`, `"needs_work"`, `"poor"`.

Rate limited: 10/min/session. On Haiku API failure returns 500 with error code `prompt_review_failed` (non-critical; operator can proceed without reviewing).

### `POST /jobs/preview`

Authenticated. Accepts multipart form-data:

- `file`: optional CSV file (UTF-8, comma or semicolon, header row).
- `text`: optional pasted content (one title per line).
- `threshold`: integer, 50–100, default 90.
- `titles_per_request`: integer, 1–50, default 25.
- `row_subset_mode`: string, one of `all`, `first_n`, `random_n`. Default `all`.
- `row_subset_n`: integer, required when mode != `all`. Must be 1 ≤ n ≤ total rows.

Exactly one of `file` or `text` must be provided.

Response 200:
```json
{
  "job_id": "a1b2c3d4-...",
  "total_rows": 13600,
  "selected_rows": 100,
  "row_subset_mode": "first_n",
  "exact_unique_rows": 8142,
  "cluster_count": 2618,
  "largest_cluster_size": 42,
  "est_cost_usd": 0.24,
  "top_clusters": [
    { "representative": "Jefe de Compras", "member_count": 42, "members": ["Jefe Compras", "Jefe de compras", "..."] },
    ...
  ]
}
```

`selected_rows` equals `total_rows` when `row_subset_mode` is `all`. For partial runs it shows the subset count alongside the full input count (e.g. "100 of 13,600 rows selected").

The returned `job_id` is for a row inserted with `status=preview`.

### `POST /jobs/:id/recluster`

Authenticated. Request:
```json
{ "threshold": 94 }
```
Valid only when job is in state `preview`. Response is the same shape as `POST /jobs/preview`.

### `POST /jobs/:id/commit`

Authenticated. Request:
```json
{
  "prompt_override": "optional full system-prompt replacement",
  "taxonomy": "Ventas\nTecnología\nOperaciones\nFinanzas\nRRHH\nOtros",
  "titles_per_request": 25,
  "is_dry_run": false
}
```

All fields optional. `is_dry_run` defaults to false. Pre-checks: spend cap (skipped for dry runs), single-concurrency, state must be `preview`.

Response 202:
```json
{ "job_id": "a1b2c3d4-...", "status": "submitted" }
```

### `POST /jobs/:id/cancel`

Authenticated. Valid in `queued`, `submitted`, `polling`, `retrying`. Calls Anthropic cancel, transitions job to `cancelled`, returns 200.

### `GET /jobs`

Authenticated. Returns all jobs, newest first:
```json
{
  "jobs": [
    {
      "id": "a1b2c3d4-...",
      "status": "completed",
      "total_rows": 13600,
      "cluster_count": 2618,
      "completed_rows": 13595,
      "error_rows": 5,
      "est_cost_usd": 0.24,
      "actual_cost_usd": 0.27,
      "created_at": "2026-04-10T14:03:00Z",
      "finished_at": "2026-04-10T14:18:42Z",
      "row_subset_mode": "all",
      "row_subset_n": null,
      "is_dry_run": false,
      "is_partial": false
    }
  ]
}
```

`is_partial` is a computed field: `true` when `row_subset_mode != 'all'`.

### `GET /jobs/:id`

Authenticated. Returns a single job with live status:
```json
{
  "id": "...",
  "status": "polling",
  "retry_round": 0,
  "progress": {
    "clusters_total": 2618,
    "clusters_resolved": 1104,
    "clusters_pending": 1514,
    "clusters_error": 0
  },
  "batches": [
    { "id": "batch_abc", "status": "in_progress", "request_count": 105, "retry_round": 0 }
  ],
  "est_cost_usd": 0.24,
  "actual_cost_usd": 0,
  "row_subset_mode": "all",
  "row_subset_n": null,
  "is_dry_run": false,
  "is_partial": false
}
```

`is_partial` is a computed field: `true` when `row_subset_mode != 'all'`.

Frontend polls this every 5 seconds while status is non-terminal.

### `GET /jobs/:id/download`

Authenticated. Valid only in state `completed`.

Response: `200 OK`, `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="nomenclator-a1b2c3d4.csv"`. Body is a UTF-8 CSV with a BOM, column order `original,male_es,female_es,category,error`.

### `GET /health`

Public. Returns:
```json
{
  "ok": true,
  "db": "ok",
  "worker_heartbeat": "2026-04-10T14:03:22Z",
  "version": "1.0.0"
}
```

## Rate limits

- `/auth`: 5/min/IP
- `/jobs/commit` (the costly one): 10/hour/session
- `/jobs/review-prompt`: 10/min/session (single Haiku call, not expensive, but prevent spam)
- Everything else: 60/min/session, enforced via a simple in-memory token bucket (lost on restart, fine for v1)

## CSRF

SameSite=Lax cookie + requiring `Content-Type: application/json` or multipart on mutating endpoints is sufficient for the single-operator threat model. No CSRF token in v1.
