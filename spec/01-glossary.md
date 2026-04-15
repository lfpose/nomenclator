# 01 — Glossary

Canonical definitions. Every other spec file uses these terms exactly as defined here. When in doubt, grep this file.

**Answer columns** — the three output fields `male_es`, `female_es`, `category` that the LLM produces for each cluster representative. Stored on `clusters`, inherited by rows via `cluster_id`.

**Batch** — a single submission to Anthropic's Messages Batches API. Contains multiple independent `batch_requests`. Has a status lifecycle managed by Anthropic and mirrored in our `batches` table.

**Batch request** — one element inside a batch submission, identified by a `custom_id`. Carries one prompt with `titles_per_request` cluster representatives bundled into a JSON array, and expects one structured response covering all of them.

**Category** — one of the three answer columns. A short Spanish classification of the role's function (e.g. "Ventas", "Tecnología", "Operaciones"). Taxonomy is supplied by the operator per-job.

**Cluster** — a group of near-duplicate titles treated as a single canonical entity for LLM resolution. Produced by the clustering step from connected components of the similarity graph. Every input row belongs to exactly one cluster (clusters of size 1 are common and valid).

**Cluster representative** — the single title sent to the LLM on behalf of an entire cluster. Deterministically selected: most frequent in input; ties broken by shortest length; ties broken by alphabetical order.

**Commit** — the operator action (POST `/jobs/:id/commit`) that transitions a job from `preview` to `queued` and triggers the first batch submission. This is the point of no return for Anthropic spend.

**Custom ID** — Anthropic's per-request identifier in a batch. We use it as the primary key for the `batch_requests` table, so mapping results back is trivial.

**Dedup (exact)** — the step before clustering that collapses titles identical under normalization. Reduces row count with zero semantic risk.

**Dry-run mode** — A UI toggle that makes the server return fake deterministic responses instead of calling Anthropic. Jobs run in dry-run mode cost $0 and are marked with a "Dry run" badge in history. Used for testing the full workflow without incurring API costs.

**Error code** — a machine-readable string (e.g. `max_retries_exceeded`, `schema_violation`, `spend_cap_exceeded`) written to the `error` column on a cluster when the row could not be fully resolved. See `18-reliability-contract.md` for the full list.

**Error row** — any output row whose `error` column is non-empty. It still appears in the CSV; the three answer columns may be empty or best-effort.

**Female form** — the standardized feminine Spanish version of a job title. For titles that are identical in both forms (e.g. "Ingeniero") the value is the same as the male form.

**Few-shot example** — a pair of input title + expected JSON output embedded in the system prompt to guide model behavior. Stored on `task_templates.few_shots`.

**Flagged row** — see "error row".

**Job** — one end-to-end run of the tool: one CSV upload, one set of parameters, one final downloaded CSV. Identified by a UUID. Has a lifecycle state machine (`07-job-lifecycle.md`).

**Length ratio** — the safety gate on fuzzy clustering: `min(len(a), len(b)) / max(len(a), len(b))`. Must be ≥ 0.6 for two titles to be considered for merging.

**Male form** — the standardized masculine Spanish version of a job title.

**Normalized key** — a lowercased, accent-stripped, punctuation-stripped, whitespace-collapsed version of the original title. Used only as a key for exact dedup and as input to the fuzzy similarity computation. The original is always preserved.

**Operator** — the single human user of the tool. Not "user" (avoided to reduce ambiguity with "user prompt").

**Original** — the raw title as received from the input, preserved verbatim in `job_rows.original` and echoed exactly in the output CSV's `original` column.

**Partial run** — A job that processes only a subset of the input rows (first N or random N) instead of all rows. The row-count invariant applies to the selected subset, not the full input. Useful for test runs before committing to a large dataset.

**Populated row** — an output row whose answer columns are filled and `error` is empty.

**Preview** — the pre-commit phase where the operator sees cluster counts, top clusters, and cost estimate. No Anthropic calls are made during preview. A job in `preview` state can be re-clustered locally as many times as desired, or abandoned.

**Prompt (system / user)** — the two parts of the LLM instruction. The system prompt is fixed per task template; the operator can override it per job. The few-shots are part of the system prompt in v1.

**Prompt review** — An optional pre-commit step where the operator's prompt and few-shot examples are sent to Claude Haiku (single non-batch call) for quality and safety validation. The review checks whether the prompt is well-formed for standardization, whether it is safe, and suggests improvements.

**Representative** — see "cluster representative".

**Retry round** — an integer on `batches`. Round 0 is the initial submission. Rounds 1–3 are straggler retries triggered by unresolved clusters from the previous round. Retry submissions run with `titles_per_request` halved from the previous round (25 → 12 → 6 → 1).

**Row index** — the stable 0-based position of a row in the input, preserved on `job_rows.row_index`. The output CSV is always ordered by this column, so input order is preserved byte-for-byte on the row axis.

**Row subset** — The selection of a portion of the input rows for processing. Three modes: `all` (default, process every row), `first_n` (take the first N rows in order), `random_n` (randomly sample N rows with a deterministic seed).

**Spend log** — the append-only `spend_log` table recording every actual USD cost incurred against Anthropic. Sum of the last 30 days is the enforcement target for the monthly cap.

**Straggler** — a cluster representative that was expected in a batch response but was missing, malformed, or rejected by the tool-output schema. Stragglers are the only thing retry rounds care about.

**Task template** — a row in the `task_templates` table encoding everything task-specific: system prompt, few-shots, output columns, default `titles_per_request`. V1 seeds exactly one: `job_titles_es`.

**Taxonomy** — the list of allowed category values for a job. Supplied by the operator as a newline- or comma-separated list in the form. If empty, the LLM may emit any category (freeform mode).

**Threshold** — the minimum `token_set_ratio` score for two titles to be considered for merging. Default 90. Tunable per job via the preview slider.

**Titles per request** — the number of representatives bundled into a single batch request. Default 25. Halved during retry rounds.

**Token set ratio** — rapidfuzz metric comparing the set of tokens in two strings after normalization. Primary similarity metric for clustering. Better than `token_sort_ratio` for our case because Spanish titles' main variation is dropped/added stop words.

**Tool use (Anthropic)** — the API feature where we define a JSON schema and force the model to respond via a "tool call" matching that schema. Used in v1 for structural output guarantees. `tool_choice` is set to force our specific tool.

**Worker (background)** — the asyncio task started in FastAPI's `lifespan` that polls Anthropic for batch status, fetches results, writes them to SQLite, and triggers straggler retries. Runs in the same Python process as the HTTP handlers. There is exactly one.
