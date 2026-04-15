# 02 — User Stories

The operator is a single person from the company's sales/ops team. They're technical enough to paste CSVs and tune a threshold slider but not technical enough to write prompts from scratch or debug API errors. The stories below trace what they do, what they see, and what can go wrong.

## Happy path

### US-01 — First-time login

As the operator, I visit the site for the first time. I see a password field and nothing else. I paste the shared password. The server verifies it, sets a 30-day session cookie, and lands me on the `/tool` page. I stay logged in across browser restarts for 30 days.

### US-02 — Submit a clean run

I'm on `/tool`. I click "Upload CSV" and pick a file containing 13,600 raw LinkedIn job titles in a single column. The file uploads. I paste a list of six allowed categories into the taxonomy textarea ("Ventas, Tecnología, Operaciones, Finanzas, RRHH, Otros"). I leave the prompt textarea at its pre-filled default. I click "Preview clusters". After ~3 seconds the page shows: "13,600 rows → 8,142 exact uniques → 2,618 clusters at threshold 90", estimated cost `$0.24`, and the 10 largest clusters with their members listed. I skim them, nothing looks wrong, and I click "Submit". The page transitions to a status panel showing "Submitted — polling Anthropic (round 0)".

I close the tab and go to lunch. An hour later I reopen the site. The status panel shows "Completed". A big "Download CSV" button is prominent. I click it and get a file named `nomenclator-{job_id}.csv` with 13,600 rows, an `error` column that is empty for all of them, and the three answer columns populated. I paste it into my leads database.

### US-03 — Adjust threshold after seeing clusters

Same flow as US-02 but on preview I notice the largest cluster has 87 members and some of them look wrong — "Director Comercial" got merged with "Director Operaciones" because they share "director" and are short enough to pass length-ratio. I drag the threshold slider from 90 to 94 and click "Re-cluster". 1 second later the panel updates: "2,891 clusters, largest is 42, est cost $0.27". The bad cluster is gone. I submit.

### US-04 — Cancel a running job

I submitted a job but realized my taxonomy was wrong. The job is in state `polling`. I click "Cancel". The server tells Anthropic to cancel the batch, updates the job state to `cancelled`, and the UI shows a message with a link to start a new run with the same input pre-loaded.

## Edge cases and errors

### US-05 — Upload a malformed CSV

I upload a file that isn't really a CSV (binary, or wrong encoding). The preview call returns a 400 with a specific error: "Could not parse CSV: encoding not UTF-8 (detected: windows-1252). Please re-save your file as UTF-8." No job row is created. I re-save and retry.

### US-06 — Empty input

I upload a file with zero data rows (just a header). The preview call returns a 400: "Input contains 0 rows after parsing. Check your file." No job is created.

### US-07 — Paste instead of upload

Instead of uploading, I paste 300 titles into the textarea, one per line. Everything else works identically. The preview step parses the pasted text as a single-column input and clusters it.

### US-08 — Very large upload

I upload 40,000 rows. Preview still completes in ~5 seconds. The cost estimate comes back at ~$0.60. I submit. It still works — v1 has no hard row cap, but the UI shows a soft warning for anything over 25k.

### US-09 — Spend cap blocks commit

It's the end of the month and I've already run several jobs totaling $18.30. I upload a new file. The estimate comes back at $2.10. When I click Submit, the commit endpoint returns 409 with a specific message: "Monthly cap $20 would be exceeded (used: $18.30, estimated: $2.10). Cap resets on {date}." The job stays in `preview` state; I can return in a few days and submit then without re-uploading.

### US-10 — Spend cap blocks a retry

A large job completes its initial batch with ~50 stragglers. The worker halves `titles_per_request` and estimates the retry cost at $0.05. But my monthly total is at $19.98. The retry is refused. The stragglers are flagged with `error=spend_cap_exceeded`. The job transitions to `completed`, not `failed` — the CSV is still downloadable, the stragglers just have empty answer columns and the error code.

### US-11 — Stragglers recovered in retry round

The initial batch comes back with 12 missing titles. The worker sees `retry_round < 3`, halves `titles_per_request` from 25 to 12, submits a retry batch with just those 12 titles. The retry batch completes cleanly. Job transitions to `completed` with zero error rows. The operator never sees any of this — from their perspective it was a single job that just took slightly longer.

### US-12 — Catastrophic failure

Anthropic returns 500 on every single request in the batch. Two retry rounds also fail. The job transitions to `failed` (not `completed`) with a message: "All batch requests failed: Anthropic API errors. See logs." The operator can see the failure but cannot download a CSV (there is nothing to download). They can click "Retry job" which re-submits from the existing preview state.

### US-13 — Server restart mid-job

I submitted a job, the server is polling, and Fly restarts the machine (deploy, crash, whatever). On boot, the FastAPI lifespan starts the background worker, which scans for non-terminal jobs and resumes polling. The operator notices nothing; the job continues from where it left off.

### US-14 — Concurrent job blocked

A job is already running. I try to submit a second job. The commit endpoint returns 409 with "A job is already running. Cancel it or wait for it to complete." V1 constraint: one active job at a time.

### US-15 — Historical jobs

I visit `/tool` and see a list of my past jobs under the form, most recent first. Each row shows: creation date, status badge, row count, cost. I can click any completed job to re-download its CSV.

### US-16 — Reading the Docs page

I visit `/docs`. I see the purpose, a brief explanation of how clustering works, mermaid diagrams for architecture and pipeline, a table of error codes, and an FAQ. I learn what `max_retries_exceeded` means without asking anyone.

### US-17 — Reading the About page

I visit `/about`. I see two short paragraphs: the etymology of "nomenclator" and a sentence about what this v1 does. That's it. It makes me smile and I go back to work.

### US-18 — Review prompt before submitting

I've edited the default prompt and added my own few-shot examples. Before committing, I click "Review Prompt". After ~2 seconds a review card appears saying the prompt is well-formed, the few-shots cover the main cases, and suggesting I add an example with a gender-neutral title. I edit my examples, re-review — now it says "looks good." I proceed to preview and submit.

### US-19 — Run a partial job (first N rows)

I have a 13,600-row file but I want to test my prompt on a small sample first. I upload the file, then change the row selector from "All rows" to "First 100 rows". Preview runs on those 100 rows only (showing ~80 clusters). I submit, it finishes in under a minute, I download and spot-check the results. Satisfied, I start a new job with "All rows".

### US-20 — Run a random sample

Same as US-19 but I toggle "Random sample" instead of "First N". The system randomly selects 200 rows from my 13,600 and processes only those. The output CSV has exactly 200 rows.

### US-21 — Dry-run to test workflow

I'm setting up the tool for the first time and want to validate everything works without spending API credits. I toggle "Dry run" on, upload my CSV, preview, and submit. The job completes almost instantly with fake results (every male_es is "{title} (M)", category is "DRY_RUN"). I download the CSV and verify the structure is correct, all 13,600 rows present. The spend counter shows $0.00 for this job.

## Out of scope stories (for v1)

- Multi-user access with roles.
- Per-user prompt presets.
- Email notifications on completion.
- Importing from Google Sheets directly.
- Re-running a failed job with modified input.
- API access for other tools to call.
