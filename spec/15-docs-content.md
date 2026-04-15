# 15 — Docs Content

The `/docs` route is the in-app user guide and self-documentation surface. It is built from Markdown (or MDX) files colocated with the frontend source and rendered with live mermaid diagrams. The content here is the authoritative outline — prose drafts live inline so the implementer can paste them in.

## Navigation structure

Sticky left sidebar with anchor links:

1. What this does
2. Quickstart
3. How it works
4. Architecture
5. Error codes
6. Costs and limits
7. FAQ
8. Troubleshooting

## 1. What this does

_Tone: plain, direct, slightly poetic but restrained._

> Nomenclator standardizes messy job titles into canonical Spanish forms. You hand it a CSV full of raw LinkedIn titles; it hands back the same file with three new columns: the masculine form, the feminine form, and a category. Same rows, same order, just cleaner.
>
> The tool is built for exactly one job inside the broader problem of cleaning a leads database. If you upload 13,600 raw titles, expect ~2,500 canonical ones. That's the whole point.

## 2. Quickstart

Step-by-step, with screenshots (or stylized illustrations for v1 if no screenshots yet):

1. Log in with the shared password.
2. Drop a CSV on the Tool page, or paste titles into the textarea.
3. Paste your allowed categories into the taxonomy field (or leave it empty for free-form).
3b. *(Optional)* Click **Review Prompt** to get AI feedback on your prompt and examples. Edit if needed.
3c. *(Optional)* Change the row selector to "First 100 rows" for a test run, or toggle "Dry run" to test without API costs.
4. Click **Preview clusters**. Wait a few seconds.
5. Look at the top 10 largest clusters. If anything looks wrong, drag the threshold up and **Re-cluster**.
6. Click **Submit job**.
7. Close the tab if you want. Come back later; it'll be done.
8. Click **Download CSV**. Done.

## 3. How it works

Three paragraphs, each accompanied by a mermaid diagram embedded from `solution-overview.md`.

### Dedup and cluster

Embed diagram **#6 (Pipeline)**.

> Before we ask the AI anything, we normalize your titles (trim, strip accents, lowercase) and group identical ones together. Then we do a second pass with a fuzzy matching algorithm (`token_set_ratio` from `rapidfuzz`) that catches near-duplicates like "Jefe Compras" and "Jefe de Compras". Every cluster is represented by a single "representative" title, and only that one gets sent to the AI. The answer propagates to every member automatically.
>
> **Why it matters:** without clustering, the AI might translate "Jefe Compras" and "Jefe de Compras" differently because it sees them in different batches with different context. Clustering guarantees they receive the same canonical output.

### Batch to Anthropic

Embed diagram **#5 (Sequence)**.

> We send the cluster representatives to Anthropic in bundles of 25 per request, inside one big batch submission. Anthropic processes the batch asynchronously — it can take minutes or up to a day — and we poll for the results. You don't have to keep the tab open.

### Enforce the row-count promise

Embed diagram **#12 (Reliability chain)**.

> The hardest problem with AI-in-CSVs is the AI quietly losing rows. We defend against this in seven layers: forced tool-call output, explicit per-title IDs that we diff against the response, schema validation on every parse, a retry loop for missing titles, and a hard pre-write assertion that the output has the same number of rows as the input. If any step fails, you get an error — never a quietly truncated file.

## 4. Architecture

Embed diagram **#1 (System context)** and **#10 (Deployment)**.

> One FastAPI process on a single Fly.io machine. SQLite on the attached volume holds all state: jobs, rows, clusters, batches, spend. An asyncio background worker inside the same process handles polling Anthropic and retrying stragglers. No Celery, no Redis, no moving parts. The frontend is a Vite-built React bundle served by the same Python process.

## 5. Error codes

Table with every code, meaning, and typical cause. Pulled from `18-reliability-contract.md`:

| Code | HTTP / Row | Meaning | Typical cause |
|---|---|---|---|
| `encoding_invalid` | HTTP 400 | Uploaded file isn't UTF-8. | Re-saving the file as UTF-8 fixes it. |
| `delimiter_unknown` | HTTP 400 | CSV delimiter isn't comma or semicolon. | Tab-delimited file — re-save. |
| `input_empty` | HTTP 400 | Zero data rows. | Check your file. |
| `input_too_large` | HTTP 400 | More than 50,000 rows. | Split into chunks. |
| `input_contains_blank_rows` | HTTP 400 | Some row normalizes to empty. | Clean your file. |
| `spend_cap_exceeded` | HTTP 409 / row | Monthly $20 cap would be exceeded. | Wait for reset. |
| `job_already_running` | HTTP 409 | Another job is in flight. | Wait or cancel. |
| `max_retries_exceeded` | row | The model failed to produce a valid answer for this cluster after 3 rounds. | Rare; try a different prompt. |
| `schema_violation` | row | Model output didn't match the expected schema. | Usually transient. |
| `tool_call_missing` | row | Model returned prose instead of the tool call. | Transient. |
| `truncated` | row | Output hit `max_tokens`. | Lower `titles_per_request` in Advanced. |

## 6. Costs and limits

> Every run is metered against a hard $20/month ceiling. A typical 13k-row job costs about $0.30, so the cap is generous — it's there to protect against bugs or misuse, not as a realistic budget.
>
> The cap is a rolling 30-day window. If a commit would exceed it, the tool refuses; you can wait a few days until older entries drop out of the window.

Show a small inline chart of `spent_this_month / cap`.

## 7. FAQ

- **Why does my file need a header row?** Because we auto-detect the delimiter from the first row, and we want to be unambiguous about where data starts. Any header name works — we only read the first column anyway.
- **Can I run two jobs at the same time?** No, v1 is single-concurrency. This prevents accidental spend doubling.
- **What happens if I close the tab mid-job?** Nothing bad. The server keeps working. Come back when you want; the job will be there.
- **What if the server restarts?** The job resumes from its last saved batch ID. You won't notice.
- **Why Spanish only?** Because that's the problem the tool was built for. v2 may add language selection.
- **Can I edit the prompt?** Yes, in the Advanced section. The default is tuned — only override if you know what you're changing.
- **Why does the preview take a few seconds?** Fuzzy clustering is O(n²) in the number of unique titles. 8,000 uniques = ~64 million comparisons. We do it in under 3 seconds but it isn't free.
- **What does "Review Prompt" do?** It sends your prompt and examples to Claude for a quick quality check — are the instructions clear, are the examples good, is it safe? It's optional but recommended if you've edited the default prompt.
- **Can I run a test with just a few rows?** Yes — change the row selector from "All rows" to "First N" or "Random sample". Only those rows will be processed.
- **What is dry-run mode?** It runs the full pipeline with fake results instead of calling the AI. Useful for testing that your CSV uploads correctly and the workflow completes. Costs nothing.
- **Does a dry run count toward the spend cap?** No.

## 8. Troubleshooting

For when something weird happens. Short and honest:

> If a job fails or gets stuck, check the following in order:
>
> 1. **The job's status panel** — the error message is usually specific.
> 2. **The History list** — look at past runs. Is this an isolated problem or a pattern?
> 3. **Fly logs** — `fly logs | grep job_id=<id>`. Every state transition is logged.
> 4. **The database** — `fly ssh console` then `sqlite3 /data/nomenclator.db`. Tables are documented in the architecture doc.
>
> If the problem reproduces reliably, it's a bug — file an issue in the repo.

## Rendering notes

- Use `mermaid` npm package, dynamically imported on the `/docs` route only (so it isn't bundled into the Tool page).
- Render in both dark and light modes by swapping `theme: 'dark' | 'default'` on the mermaid init.
- Anchors for each section come from the H2 headings; sidebar links use the same fragment.
