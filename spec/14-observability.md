# 14 — Observability

V1 minimum: structured JSON logs to stdout, a health endpoint, and a few named metrics in log lines. No Prometheus, no Sentry, no Datadog. Fly captures stdout into its log stream; `fly logs` is the primary debugging tool.

## Logging

### Format

Structured JSON, one line per event. Example:

```json
{"ts":"2026-04-10T14:03:22.104Z","level":"INFO","logger":"nomenclator.jobs","event":"job.transition","job_id":"a1b2c3d4","from":"polling","to":"completed","reason":"all_clusters_resolved","error_rows":0,"duration_ms":842112}
```

Standard fields on every line:

- `ts` — ISO 8601 UTC.
- `level` — `DEBUG`, `INFO`, `WARN`, `ERROR`.
- `logger` — the Python logger name (`nomenclator.{module}`).
- `event` — a short dotted identifier (`job.transition`, `batch.submitted`, `worker.tick`, `auth.login`, `http.request`).

Everything else is event-specific structured context.

### Loggers and what they log

| Logger | Events |
|---|---|
| `nomenclator.http` | `http.request` for every served request, with `method`, `path`, `status`, `duration_ms`, `session_id_short`. |
| `nomenclator.auth` | `auth.login`, `auth.logout`, `auth.denied`, `auth.rate_limited`. |
| `nomenclator.jobs` | `job.created`, `job.transition`, `job.preview`, `job.commit`, `job.cancel`, `job.download`. |
| `nomenclator.cluster` | `cluster.started`, `cluster.done` with counts and duration_ms. |
| `nomenclator.batch` | `batch.submitted`, `batch.polled`, `batch.completed`, `batch.results_fetched`, `batch.retry_submitted`. |
| `nomenclator.anthropic` | `anthropic.request`, `anthropic.response` with `endpoint`, `status_code`, `duration_ms`, `cost_usd` (on completion). |
| `nomenclator.worker` | `worker.started`, `worker.tick`, `worker.sleep`, `worker.error`. |
| `nomenclator.db` | Migrations, unusual query failures. No per-query logging — too noisy. |
| `nomenclator.review` | `review.requested`, `review.completed`, `review.failed` with `quality_score`, `safe`, `duration_ms`. |

### What they log — additional notes

- Dry-run jobs are logged with `is_dry_run=true` on every job-related event.
- Prompt review calls are logged with duration and the quality_score result (never the full prompt content).

### Redaction

A single `RedactingFilter` runs on every log record. It scrubs:

- Anything matching `sk-ant-[a-zA-Z0-9\-_]+` → `sk-ant-***REDACTED***`
- Any field named `password` or `sid` (raw) → `***`
- CSV row samples: at DEBUG only, max 3 rows, max 200 chars per row.

The filter is defensive — the code already avoids logging secrets, but defense in depth is cheap.

### Log levels by environment

- Production: `INFO` default. `DEBUG` for specific loggers via env var `LOG_LEVEL_OVERRIDES='nomenclator.cluster=DEBUG'`.
- Development: `DEBUG` default.
- Tests: `WARN` to keep pytest output clean.

## Error handling

- Uncaught exceptions in HTTP handlers → caught by a FastAPI exception handler that logs at `ERROR` with stack trace, returns 500 `internal_error` (no stack to the client).
- Uncaught exceptions in the worker task → logged at `ERROR` with stack trace, the worker sleeps 30s and continues. The task is restarted automatically by its wrapper loop; it does not die.
- Anthropic API errors (4xx/5xx) → logged, handled by retry logic or failure transition depending on context.
- Pydantic validation errors → logged at `WARN` with the offending field paths.

## Health endpoint

```
GET /health
```

Public, no auth. Returns:

```json
{
  "ok": true,
  "db": "ok",
  "worker_heartbeat": "2026-04-10T14:03:22Z",
  "worker_last_tick_seconds_ago": 12,
  "version": "1.0.0"
}
```

Logic:

- `db` — attempt `SELECT 1`. On failure, `"db": "error"`, `ok: false`, HTTP 503.
- `worker_heartbeat` — the worker updates an in-memory timestamp on every tick. Health endpoint reads it.
- `worker_last_tick_seconds_ago` — computed from the heartbeat. If > 120s, `ok: false`.
- `version` — from `settings.version`.

Fly's health check hits this endpoint; a 503 triggers an automatic restart.

## Metrics without a metrics system

V1 has no time-series metrics backend. The events we'd want to graph are all in the logs, which Fly retains for a few days. If anyone wants to compute "jobs per week" or "average clustering latency," they grep the logs.

Possible metrics to add in v2 (not v1): `job.count`, `job.duration`, `anthropic.cost`, `cluster.latency_ms`, `batch.retry_count`.

## Error budget / SLO

None. Single-operator internal tool.

## Debugging playbook

Common "what happened to my job" flow:

1. `fly logs | grep job_id=a1b2c3d4` — full audit trail.
2. `fly ssh console` → `sqlite3 /data/nomenclator.db` → inspect `jobs`, `clusters`, `batch_requests` directly.
3. Look at `batch_requests.raw_response` for the failing request.
4. Check `spend_log` for unexpected cost entries.

This is documented in `15-docs-content.md` under the "Troubleshooting" section so the operator can self-serve.
