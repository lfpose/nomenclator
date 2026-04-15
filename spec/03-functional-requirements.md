# 03 — Functional Requirements

Numbered, testable. Each FR is a contract. If a change to the code breaks an FR, the FR must be updated first.

## Authentication

**FR-001** — The site requires a valid session cookie to access any route other than `/auth`. Unauthenticated requests to protected routes return 401.

**FR-002** — There is exactly one shared password, stored as an argon2id hash in the Fly secret `AUTH_PASSWORD_HASH`.

**FR-003** — A successful `POST /auth` with the correct password issues a session cookie with attributes `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000` (30 days).

**FR-004** — The session cookie value is a random 256-bit token; its hash is stored server-side in the `sessions` table with an `expires_at` 30 days in the future.

**FR-005** — Failed login attempts are rate-limited to 5 per minute per IP, returning 429 beyond that.

## Input ingestion

**FR-010** — The `POST /jobs/preview` endpoint accepts input in two forms: a multipart file upload, or a `text` field containing pasted content.

**FR-011** — Uploaded CSV files must be UTF-8 encoded. Non-UTF-8 files produce a 400 with error code `encoding_invalid`.

**FR-012** — CSV delimiters are auto-detected between comma and semicolon. Tabs are not supported in v1.

**FR-013** — CSV files must have a header row. The first column is always treated as the title column, regardless of header name.

**FR-014** — Pasted content is treated as one title per line, blank lines skipped, no header expected.

**FR-015** — Zero-row inputs return 400 with error code `input_empty`.

**FR-016** — Inputs larger than 50,000 rows return 400 with error code `input_too_large`. (Soft UI warning at 25,000.)

## Clustering

**FR-020** — After ingestion, the server normalizes each title (strip accents, lowercase, drop punctuation, collapse whitespace) to produce a `normalized` string. Original is preserved.

**FR-021** — Rows with identical `normalized` values are exact-deduped for the clustering input set; all share a single cluster key.

**FR-022** — Fuzzy clustering uses `rapidfuzz.token_set_ratio` as the primary similarity metric, with a default threshold of 90 and a hard `len_ratio ≥ 0.6` guard.

**FR-023** — Connected components are computed via union-find. Every input row ends up in exactly one cluster; clusters of size 1 are valid.

**FR-024** — The cluster representative is selected deterministically: most frequent `original` in the cluster; tie-broken by shortest length; tie-broken by alphabetical order.

**FR-025** — Clustering completes in ≤ 5 seconds for inputs up to 20,000 rows on the target Fly machine.

**FR-026** — The preview response includes: total input rows, exact-unique count, cluster count, estimated cost in USD, and the top 10 largest clusters with all members.

**FR-027** — `POST /jobs/:id/recluster` re-runs clustering with a new threshold against the cached normalized set, replacing prior clusters. No Anthropic calls.

## Commit and submission

**FR-030** — `POST /jobs/:id/commit` accepts a `prompt` (optional override), `taxonomy` (optional override), and `titles_per_request` (optional override, default from template).

**FR-031** — Before submitting to Anthropic, the commit endpoint runs a spend-cap pre-check: `sum(spend_log.usd WHERE at > now - 30d) + estimated_cost ≤ $20`. On failure it returns 409 with error code `spend_cap_exceeded`.

**FR-032** — If another job is in any non-terminal state for the same operator session, commit returns 409 with error code `job_already_running`. V1 enforces single-concurrent-job.

**FR-033** — On successful commit, the job's cluster representatives are bundled into batch requests of size `titles_per_request`, a single Anthropic batch is submitted, and the `batches` + `batch_requests` rows are written.

**FR-034** — The batch submission uses Anthropic tool use with a forced `tool_choice` matching a schema whose `results` array has `minItems == maxItems == titles_per_request`.

**FR-035** — Every request carries explicit per-title IDs; responses are validated against those IDs set-wise (not positionally).

## Polling and retries

**FR-040** — A single background worker, started in FastAPI lifespan, polls Anthropic every 30 seconds (jittered ±5s) for all jobs in state `submitted`, `polling`, or `retrying`.

**FR-041** — On batch completion, the worker fetches results, parses via the Pydantic tool schema, and writes populated cluster rows. Any schema failure marks the whole `batch_request` as `failed` and its cluster IDs become stragglers.

**FR-042** — Stragglers are collected across all requests in the batch. If any exist and `retry_round < 3`, the worker halves `titles_per_request`, runs a spend-cap check, and submits a new retry batch.

**FR-043** — If the retry spend-cap check fails, remaining stragglers are flagged `error=spend_cap_exceeded` and the job transitions to `completed`.

**FR-044** — If `retry_round == 3` and stragglers still exist, they are flagged `error=max_retries_exceeded` and the job transitions to `completed`.

**FR-045** — If every batch request in the initial submission fails with a schema or API error, the job transitions to `failed` (not `completed`). No CSV is generated.

**FR-046** — On server restart, the worker scans non-terminal jobs and resumes polling from their stored `batch_id`s.

## Cancellation

**FR-050** — `POST /jobs/:id/cancel` is valid in states `queued`, `submitted`, `polling`, `retrying`. It calls Anthropic's cancel endpoint, marks the job `cancelled`, and returns 200.

**FR-051** — A cancelled job is not downloadable. Its data remains in SQLite for audit.

## Output and export

**FR-060** — `GET /jobs/:id/download` is only valid in state `completed`. Any other state returns 409.

**FR-061** — The exported CSV is UTF-8 with BOM. Column order is: `original`, `male_es`, `female_es`, `category`, `error`. All five columns are always present; `error` is empty for populated rows.

**FR-062** — The export row count equals the input row count, and the order matches input order (via `job_rows.row_index`).

**FR-063** — Before writing, the export asserts `len(output) == len(input)`. Failure triggers a log entry and transitions the job to `failed` — no partial CSV is ever returned.

**FR-064** — The download filename is `nomenclator-{job_id_short}.csv` where `job_id_short` is the first 8 hex characters of the job UUID.

## History

**FR-070** — `GET /jobs` returns all jobs ever created, most recent first. No pagination in v1 (total count is small).

**FR-071** — Completed jobs remain downloadable indefinitely; there is no auto-delete in v1.

## Pages

**FR-080** — The site has exactly three routes served by TanStack Router: `/` (the Tool, including upload form and job history), `/about`, `/docs`.

**FR-081** — The Tool page uses a single-form layout. No wizard, no stepper.

**FR-082** — The Tool form includes a collapsed "Advanced" section containing: threshold slider, `titles_per_request` input, prompt override textarea, row subset selector (mode + count), and dry-run toggle.

**FR-083** — The Docs page embeds mermaid diagrams live-rendered in the browser.

**FR-084** — Dark and light modes are both supported with an explicit toggle. Default follows `prefers-color-scheme`.

## Notifications

**FR-090** — When a job transitions from non-terminal to terminal while the operator's tab is open, the browser shows a Notification API popup (if permission granted).

**FR-091** — Notification permission is requested only after the first successful commit, not on page load.

## Prompt Review

**FR-100** — `POST /jobs/review-prompt` accepts a prompt string and a few_shots string (JSON). It makes a single non-batch call to Claude Haiku with a meta-prompt that evaluates the operator's prompt for quality and safety.

**FR-101** — The prompt review response includes `safe` (boolean), `quality_score` ("good"/"needs_work"/"poor"), `issues` (list of strings), `suggestions` (list of strings), and `summary` (string).

**FR-102** — Prompt review is optional. The operator can submit a job without reviewing the prompt.

**FR-103** — Prompt review validates both the main prompt text and the few-shot examples together.

**FR-104** — The prompt review call does NOT count toward the $20 monthly batch spend cap. It uses non-batch Haiku pricing, negligible cost (~$0.001 per call).

## Row Subset

**FR-110** — `POST /jobs/preview` accepts `row_subset_mode` (`all`, `first_n`, `random_n`) and `row_subset_n` (integer). Default mode is `all`.

**FR-111** — When `row_subset_mode` is `first_n`, only the first `row_subset_n` rows from the input are processed. When `random_n`, a random sample of `row_subset_n` rows is selected using a deterministic seed derived from the job ID.

**FR-112** — The output CSV for a partial run contains exactly `row_subset_n` rows, maintaining the same row-count invariant as a full run but scoped to the subset.

**FR-113** — Jobs with `row_subset_mode != 'all'` display a "Partial" badge in the history list.

**FR-114** — The preview response for partial runs shows the subset count alongside the full input count (e.g. "100 of 13,600 rows selected").

## Dry-Run Mode

**FR-120** — The UI exposes a "Dry run" toggle. When enabled, the job is created with `is_dry_run = 1`.

**FR-121** — Dry-run jobs skip all Anthropic API calls. The worker generates fake deterministic responses for each cluster: `male_es = "{representative} (M)"`, `female_es = "{representative} (F)"`, `category = "DRY_RUN"`.

**FR-122** — Dry-run jobs record $0 in `spend_log` and do not count toward the monthly spend cap.

**FR-123** — Dry-run jobs display a "Dry run" badge in the history list and job detail view.

**FR-124** — The single-concurrency rule (FR-032) still applies to dry-run jobs — they occupy the active slot like any other job.

**FR-125** — Dry-run jobs still enforce the row-count invariant and pre-write assertion.
