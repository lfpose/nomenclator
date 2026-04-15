# 07 — Job Lifecycle

Reference: diagram 4 in `solution-overview.md`. This doc is the text version with transition semantics and the resume-on-restart algorithm.

## States

| State | Terminal | Description |
|---|---|---|
| `draft` | no | Job row created, no input ingested yet. Transient; rarely stored. |
| `preview` | no | Input ingested, clustered, awaiting commit. Reclustering allowed. No Anthropic spend yet. |
| `queued` | no | Commit accepted, batch submission in progress. Transient (microseconds). |
| `submitted` | no | Batch posted to Anthropic, awaiting first poll. |
| `polling` | no | Worker is polling this job's batch(es). |
| `retrying` | no | Stragglers found, retry batch being prepared or just submitted. Transient. |
| `completed` | **yes** | Job finished (possibly with error rows). CSV downloadable. |
| `failed` | **yes** | Catastrophic job-level failure. No CSV. |
| `cancelled` | **yes** | Operator cancelled. No CSV. |

"Transient" = the server passes through it in the same request/worker tick and persists the next state. Still visible during the moment, but rarely seen by the operator.

## Transitions

Every transition writes a log line: `transition job_id from={old} to={new} reason={why}`.

| From | To | Trigger | Side effects |
|---|---|---|---|
| (nothing) | `draft` → `preview` | `POST /jobs/preview` succeeds | Parse input, insert job_rows and clusters, compute cost estimate |
| `preview` | `preview` | `POST /jobs/:id/recluster` | DELETE clusters, INSERT new clusters, UPDATE job_rows.cluster_id |
| `preview` | (deleted at session end) | tab closed, next day | Nothing — preview jobs linger in DB; see retention note below |
| `preview` | `queued` → `submitted` | `POST /jobs/:id/commit` | Spend cap check, concurrency check, build batch requests, POST to Anthropic, INSERT batches + batch_requests |
| `queued` | `failed` | Anthropic POST errors synchronously | Mark failed, log error |
| `queued` | `cancelled` | `POST /jobs/:id/cancel` | Mark cancelled; since batch hasn't been created, nothing to cancel upstream |
| `submitted` | `polling` | first worker tick retrieves a non-`in_progress` status or any successful response | Update `polled_at` |
| `submitted` | `cancelled` | `POST /jobs/:id/cancel` | Call Anthropic cancel, mark cancelled |
| `polling` | `polling` | worker tick, Anthropic still in progress | Update `polled_at` |
| `polling` | `completed` | all batches `ended` + all clusters resolved (possibly with error codes) | Write answers to clusters, insert spend_log, set finished_at |
| `polling` | `retrying` | all batches `ended` + stragglers exist + `retry_round < 3` + spend cap ok | Build retry batch, POST to Anthropic, INSERT batches (round+1) |
| `polling` | `completed` | all batches `ended` + stragglers exist + (`retry_round == 3` OR spend cap would fail) | Flag stragglers with error code, set finished_at |
| `polling` | `failed` | all batch_requests failed with schema/API errors on every retry | Mark failed |
| `polling` | `cancelled` | `POST /jobs/:id/cancel` | Anthropic cancel for in-flight batches, mark cancelled |
| `retrying` | `submitted` | retry batch successfully posted | Standard poll path resumes |
| `retrying` | `failed` | retry batch post errors | Mark failed |
| `retrying` | `cancelled` | operator cancel | Cancel in-flight batches |

## Resume-on-restart

On FastAPI startup, the lifespan hook:

1. Opens DB connection, runs any pending migrations.
2. Starts the background worker task.
3. Worker's first tick runs immediately (not delayed by the 30s interval).
4. Worker query: `SELECT * FROM jobs WHERE status IN ('submitted','polling','retrying')`.
5. For each such job, the worker polls its current `batches` (ordered by `retry_round DESC`, most recent retry round first) via Anthropic's batch status endpoint.
6. Normal polling / completion / retry logic takes over from there.

A job in `queued` on startup is anomalous — it means the server crashed between inserting the job row and posting to Anthropic. Worker logs a warning and transitions it to `failed` with reason `restart_during_queue`.

A job in `draft` or `preview` on startup is fine; the operator's work in progress survives and they can continue or abandon.

## Retention

- `preview` jobs older than 7 days are auto-deleted on a daily worker sweep (low priority; doesn't affect correctness).
- Completed, failed, cancelled jobs are kept forever.
- No UI for deletion in v1.

## Single-concurrency enforcement

The commit endpoint, before doing anything, runs:
```sql
SELECT COUNT(*) FROM jobs
WHERE status IN ('queued','submitted','polling','retrying');
```
If ≥ 1, return 409 `job_already_running`.

This is a global check (not per-session) because v1 has one operator.

## Spend cap checkpoints

The cap is evaluated at two moments:

1. **Commit** — the HTTP handler checks before POSTing to Anthropic. Failure returns 409.
2. **Retry submission** — the background worker checks before POSTing a retry. Failure flags stragglers with `error=spend_cap_exceeded` and transitions to `completed`.

Both use the same query: `SELECT COALESCE(SUM(usd), 0) FROM spend_log WHERE at > :thirty_days_ago`. The estimate adds to this; if the sum exceeds $20, block.

## Dry-run jobs

Dry-run jobs follow the exact same state machine as normal jobs.

The difference is in the worker: instead of calling Anthropic, it generates fake responses inline for each cluster representative — `male_es = "{representative} (M)"`, `female_es = "{representative} (F)"`, `category = "DRY_RUN"`.

State transitions for dry runs are: `preview` → `queued` → `submitted` → `polling` → `completed`. The `submitted` → `polling` → `completed` transitions happen in a single worker tick, since all responses are generated immediately without any external API call.

Dry-run jobs do not enter `retrying` state — there are no stragglers because all responses are deterministic and always complete.

The spend cap pre-check at commit is skipped for dry-run jobs (`is_dry_run = 1`). A $0 entry is still written to `spend_log` for audit consistency.

## Error vs failure

Repeating because it's load-bearing:

- **`completed` with `error_rows > 0`** is a normal outcome. The CSV is delivered; some rows carry per-row error codes.
- **`failed`** means no CSV can be produced. Reserved for catastrophic cases: all Anthropic requests errored, or the pre-write assertion tripped, or a batch POST raised exceptionally.
