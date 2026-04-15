# 04 — Non-Functional Requirements

## Performance budgets

| Operation | Target | Hard ceiling |
|---|---|---|
| Page load (Tool) | < 1s on broadband | 3s |
| Clustering preview (≤ 20k rows) | < 3s | 10s |
| Clustering preview (20k–50k rows) | < 10s | 30s |
| Re-cluster on threshold change | < 1s (uses cache) | 5s |
| Form submit (commit → 202 response) | < 2s | 5s |
| Download endpoint response | < 1s (SQL join stream) | 3s |
| End-to-end job (13k rows, haiku batch) | 5–30 min typical | Anthropic's 24h batch SLA |

Clustering is the only CPU-intensive step. Python + rapidfuzz handles 8k × 8k in well under 3 seconds; the 20k ceiling is generous.

## Resource budgets

| Resource | Target |
|---|---|
| Single Fly machine | 1 vCPU, 1 GB RAM |
| Peak memory during clustering | < 200 MB |
| SQLite file | < 500 MB projected for the first year |
| Fly volume | 10 GB (overprovisioned for comfort) |

## Browser support

- **Supported:** latest Chrome, Firefox, Edge, Safari on desktop.
- **Not supported:** mobile browsers (no UI work is done for them), IE, browsers older than two years.
- No polyfills beyond what Vite's default targets include.

## Accessibility

Best-effort WCAG 2.1 AA. Specifically:

- All interactive elements reachable by keyboard with visible focus states.
- Color contrast ≥ 4.5:1 for normal text, ≥ 3:1 for large text, in both modes.
- All form inputs have associated labels.
- Error messages are announced via `role="alert"`.
- No automated WCAG audit is required for v1, but nothing intentionally blocks it.

## Security baseline

- All traffic HTTPS (Fly terminates TLS).
- Session cookie `HttpOnly; Secure; SameSite=Lax`.
- Password stored as argon2id hash in Fly secret, never in DB, never in logs.
- Anthropic API key stored as Fly secret, never returned to the frontend.
- No user-supplied input is ever echoed into the system prompt without escaping.
- Rate limits: 5 login attempts/minute/IP; 10 job submissions/hour/session.
- See `12-security.md` for detail.

## Observability

- Structured JSON logs to stdout (Fly captures).
- Log levels: `DEBUG`, `INFO`, `WARN`, `ERROR`.
- Every HTTP request logs method, path, status, duration.
- Every state transition logs `job_id`, `from`, `to`, `reason`.
- Every Anthropic API call logs `batch_id`, `endpoint`, `status_code`, `duration_ms`, `cost_usd` on response.
- No external analytics. No Sentry (v1). Errors surface in Fly logs.
- `GET /health` returns 200 with DB connectivity and worker heartbeat timestamp.

## Uptime

- No SLA. This is a private tool used by one person maybe twice a month.
- Fly auto-restarts on crash.
- Background worker is resumed on boot; interrupted jobs resume from their last `batch_id`.
- Planned downtime (deploys) is acceptable at any time.

## Data retention

- Jobs, rows, clusters, batches, batch_requests, spend_log: kept indefinitely.
- Session rows: purged when `expires_at < now`, done lazily on auth check.
- No GDPR obligations for a private internal tool, but still: no personal data about third parties is stored. Job titles are public information.

## Internationalization

- UI is English only in v1.
- Output language is Spanish (the task's whole point).
- UTF-8 end-to-end.

## Build and deploy

- Single Dockerfile, multi-stage: Node build for the React bundle → Python runtime copying the static assets.
- `fly deploy` is the only command needed. No CI in v1.
- Fly secrets set via `fly secrets set`, not committed.
- Rollback via `fly releases rollback`.

## Testing

- Unit tests for the clustering algorithm (fixtures: small contrived sets with known expected clusters).
- Unit tests for CSV parsing (various encodings, delimiters, edge cases).
- Unit tests for cost estimation.
- Unit tests for the state machine (transition validity).
- One integration test that mocks Anthropic and runs a 50-row job end-to-end.
- No e2e browser tests in v1.
- `pytest` runs in < 10s.
