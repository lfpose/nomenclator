# Nomenclator — Requirements

## Round 1 — Initial 50 questions

### Motivation & audience

**1. In one sentence, what problem does this tool solve for you personally?**
We have 16k titles, we need to batch tell an AI in small chunks to convert 16K to standardized (male, female and category) so that from 1 random ass job title directly from LinkedIn we get male standardized version, female and category.

**2. Who is the primary user — just you, a small circle, or the public?**
Mostly my colleague who deals with leads database.

**3. Is this a personal tool, portfolio piece, or something you'd ship commercially?**
For my own company, but potentially a public project... though we need to define security practices here. At first I'd like a public website but only to be used by a specific person.

**4. What triggered the idea — a specific frustration, a story, a historical rabbit hole?**
Requirement raised by colleague.

**5. Any deadline or event you want it ready by?**
No deadline.

### Concept & naming

**6. Is the tool literally named "Nomenclator," or do you want a different product name?**
Yes.

**7. How literal is the Roman framing — aesthetic flavor only, or woven into mechanics/vocabulary (e.g. calling entries "cives," lists "tabulae")?**
Name only for now.

**8. Is the core job remembering names of people, or broader (people + context + relationships + events)?**
What? No — the goal is standardizing job titles.

**9. Should it feel like a tool, a game, or a study aid?**
Tool.

**10. One-sentence tagline you'd want on the landing hero?**
No tagline. But if I HAD to, it would be something mixing Roman nomenclator + what it actually does: standardizing job titles.

### Core functionality

**11. Do users add entries manually, import from contacts/CSV, or both?**
Import CSV → export CSV. But also works with plain text CSV — like a textbox where I can paste and copy out of.

**12. What fields per person: name, photo, role, where-met, notes, tags, last-interaction — which are mandatory vs optional?**
Doesn't make sense here.

**13. Photos: required, optional, or not at all?**
N/A.

**14. Relationships between entries (X is Y's colleague) — in scope or not?**
N/A.

**15. Grouping: single flat list, tags, or explicit "circles" (work/family/etc.)?**
N/A.

**16. Search: by name only, or also by tag/context/notes?**
N/A.

**17. Quiz / flashcard recall mode — yes or no?**
N/A.

**18. Spaced repetition scheduling for review?**
N/A.

**19. Mnemonic suggestions (AI-generated or user-written)?**
N/A.

**20. Reminders like "you haven't seen X in 3 months"?**
N/A.

**21. Any AI features at all, or strictly deterministic?**
N/A.

### Data & privacy

**22. Local-only (IndexedDB/localStorage) or cloud-synced?**
Local only.

**23. Multi-device sync required for v1?**
It's a website only. Desktop browser.

**24. Accounts + auth, or no login at all?**
Not sure, ideally not but maybe.

**25. Export (JSON/CSV) and import — needed for v1?**
Already answered.

**26. Encryption-at-rest requirement, or trust the browser/provider?**
Local only. Though data is not really confidential.

**27. Any data you explicitly refuse to collect (analytics, IP, etc.)?**
No comment nor restrictions. It's non-critical data.

### Tech & architecture

**28. Preferred stack — React, Svelte, SolidJS, vanilla, Next.js, Astro?**
React + Vite + TS.

**29. TypeScript or plain JS?**
TS.

**30. Backend needed, or pure static/client-side?**
If needed, Hono.

**31. If backend: Node, Go, Python, Rust, serverless?**
Node.

**32. Database if any: SQLite, Postgres, Supabase, Firebase?**
If needed, SQLite.

**33. PWA / installable on phones?**
No.

**34. Mobile-first, desktop-first, or equal?**
Desktop-first.

**35. Offline support required?**
No.

### Design & UX

**36. Aesthetic direction: ancient-Roman (marble, serif, laurel), modern-minimal, index-card/analog, or something else?**
Modern minimal.

**37. Color palette instincts — warm stone/terracotta, monochrome, vivid?**
Monochrome.

**38. Typography: classical serif, modern sans, or mixed?**
Modern sans.

**39. Dark mode, light mode, or both?**
Both.

**40. Any sites/apps whose look you want to borrow from?**
No.

### About section

**41. Is the about section a separate route/page, or a scroll section on one page?**
Route.

**42. How deep does the history go — one paragraph, or real historical detail with sources?**
Very shallow, just 1–2 sentences max.

**43. Should you cite specific Roman figures (e.g. Cicero's nomenclator)?**
No.

**44. Any etymology breakdown of the word itself?**
Maybe yes — maybe this is the history thing actually.

**45. Tone: scholarly, playful, poetic?**
Straight to the point, a bit poetic.

### Scope, success, constraints

**46. What is explicitly out of scope — what must we NOT build?**
Users handling, admin panel.

**47. What would make this feel successful to you one month after launch?**
I can upload a file, set some instructions, get back the file with all the new columns filled exactly like I want them.

**48. Hard constraints (budget, no-AI, no-tracking, must-deploy-to-X)?**
AI must be used in a cheap mode, but should not be too expensive so it must be using batch. Must deploy with Fly.io.

**49. Open source or private? License if open?**
Either. Start private.

**50. What existing tools have you tried for this, and what did they lack?**
Used AI directly but didn't work for 100 rows so I must automate this.

---

### Summary of the idea

The user gives a specific prompt, examples, and a file of ~10,000 job titles. The tool takes this and (via batch AI calls) returns 4 columns:

- Original job title
- Standardized male job title
- Standardized female job title
- Category

---

## Round 2 — Architectural blockers

### AI & batching

**1. Which provider — OpenAI Batch API, Anthropic Message Batches, Gemini Batch, or open?**
Claude / Anthropic with batches.

**2. Who pays — you bring a server-side API key, or user pastes their own key in the UI?**
I pay to make it easy for them.

**3. Batch APIs can take minutes-to-24h. Async job + come-back-later OK, or do you want smaller synchronous chunks that finish in seconds (costlier, no batch discount)?**
That's good! (async)

**4. If async: how does the user get notified — just reopen the page, email, nothing?**
Let's brainstorm this.

**5. One job at a time, or a queue of multiple?**
1 job consists maybe of many sub-tasks right because of batches? But I guess to the user it's 1 job.

### Prompt & output

**6. Is the prompt + few-shot examples fixed in code, or editable in the UI per run?**
Yes, prompt + few short examples.

**7. Output language of the standardized titles: English, Spanish, same as input, user-selected?**
Spanish.

**8. Categories — fixed predefined taxonomy (you provide the list), or let the AI freeform them?**
Defined by user, maybe optional? So maybe a choice to let AI define.

**9. For English titles where male/female are identical (e.g. "Engineer"), do both columns get the same value, or leave female blank?**
Same value in both. But it's in Spanish, and even then yes some will just be the same.

### Data handling

**10. Max file size / row count cap for v1? (100? 20k? 50k?)**
No limit, but reasonable inputs are between 100 and 20k.

**11. Dedupe identical titles before sending to AI — yes (cheaper) or no?**
Yes, let's do all this before to get cheaper costs.

**12. Persistent cache: if "Senior Software Engineer" was processed last week, reuse it next upload?**
No — it's all like 1 task done monthly so I don't think it will make sense to cache and complexify.

**13. Input CSV — assume single column, or let user pick which column is the title?**
Assume single or first column.

**14. Rows that fail classification: skip, retry, or flag in output with an error column?**
Flag in output.

### Access

**15. "Public site but only one user" — shared password, basic auth, IP allowlist, or literally nothing?**
I don't know, but something secure as my AI API will be exposed to this task.

---

## Round 3 — Brainstorms & remaining blockers

### Brainstorm A — Notifications (Q4)

**Context:** Anthropic batch completes within 24h (often far less). User submits, walks away, comes back. Options:

- **(a) Jobs page only** — persistent list with status badges. User reloads to check. Simplest, zero infra.
- **(b) Browser Notification API** — page pings user if tab still open. Free, but requires tab alive.
- **(c) Email on completion** via Resend/Postmark free tier. Needs SMTP creds + user email input.
- **(d) Discord/Telegram/Slack webhook** — user pastes a webhook URL once, server posts on done. Zero auth cost, reliable.
- **(e) Server-Sent Events** to open tab + fallback to (a) on reconnect.

**My recommendation for v1:** (a) + (b) combined. Add (d) as a nice-to-have env-var setting.

**Your pick:** `a + b + d`, but (d) is not a must. At a least do (b).

Answer: A + B

### Brainstorm B — Access control (Q15)

**Context:** Server holds the Anthropic API key. You want it locked down but hate login friction. Options:

- **(a) Single shared password** → httpOnly session cookie, password hash in Fly secret. 1 input, persists 30d. Cheap.
- **(b) HTTP Basic Auth** at Hono middleware level. Browser native popup. Uglier UX but 5 lines of code.
- **(c) Cloudflare Access** in front of Fly: Google/GitHub SSO, zero code. Free tier exists. Best security.
- **(d) IP allowlist** via Fly edge: only your office/home IPs. Breaks on mobile/travel.
- **(e) Magic link by email** — no password to remember, requires SMTP.

Regardless of choice: rate limit + hard monthly spend cap on the Anthropic key (tracked in SQLite, refuse new jobs if over).

**My recommendation for v1:** (a) single password + spend cap. Simple, private, and the key never leaves the server.

**Your pick:** : what you suggested

---

### Remaining blockers

#### Prompt handling

**16. Re-ask Q6 — which is it?**
- (A) prompt + examples baked into code and immutable
- (B) editable in UI every run with a "default" pre-filled
- (C) editable but saved as presets in SQLite

_Answer:_ (B), save past prompts to SQLite

**17. Are the few-shot examples fixed by you, or do you want the UI to let you add/edit them per run?**
_Answer:_ let ui change!

#### Categories

**18. When user supplies the category taxonomy, how?**
- (A) paste a comma/newline list in a textarea
- (B) upload a separate file
- (C) both

_Answer:_ A

**19. If AI-freeform mode is picked, do you want it constrained ("max 40 distinct categories across the whole file") or truly open?**
_Answer:_ open

#### Input format

**20. Does the input CSV have a header row? Always, never, or detect?**
_Answer:_ always

**21. What delimiter — comma only, or also semicolon/tab (common in Spanish Excel exports)?**
_Answer:_ comma or semicolon

**22. Encoding — UTF-8 only, or also handle Latin-1/Windows-1252 (LinkedIn exports sometimes)?**
_Answer:_ UTF-8 only

**23. For the paste-textbox mode: one title per line, or also CSV-in-textbox?**
_Answer:_ plaintext, but maybe we can add some preview component

#### Output format

**24. Output CSV: UTF-8 with BOM (so Excel opens Spanish accents correctly) — yes?**
_Answer:_ yes

**25. Column order: original, male, female, category, error? Or different?**
_Answer:_ yes

**26. Error column: only present when there are errors, or always present?**
_Answer:_ always

#### Model & cost

**27. Anthropic model: `claude-haiku-4-5` (cheapest, fast) or `claude-sonnet-4-5` (smarter, ~5x pricier)? Batch gives 50% off either way.**
_Answer:_ haiku

**28. Hard monthly spend cap in USD — what number makes you comfortable? (e.g. $20, $50, $100)**
_Answer:_ 20 usd

**29. Per-job spend cap, or only monthly?**
_Answer:_ monthly

#### Job lifecycle

**30. When a batch is running, can the user submit another job, or is it blocked until the current one finishes?**
_Answer:_ blocked for now

**31. Job history — keep all past jobs visible, keep last N, or auto-delete after download?**
_Answer:_ all

**32. Can the user cancel a running batch? (Anthropic supports cancel.)**
_Answer:_ yes

**33. If the Fly server restarts mid-job: we store `batch_id` in SQLite and resume polling on boot — OK?**
_Answer:_ sure

#### Dedup details

**34. Case-insensitive dedup? ("SENIOR ENGINEER" == "Senior Engineer")**
_Answer:_ yes

**35. Trim whitespace + collapse inner spaces before dedup?**
_Answer:_ yes

**36. Strip trailing company suffixes like "at Google", "@ Acme", "| Remote"? Or leave raw?**
_Answer:_ raw

#### UX / pages

**37. Pages needed: (A) Home/Upload, (B) Jobs list, (C) Job detail, (D) About. Anything else?**
_Answer:_ id prefer a single page application, and other pages are really: About and Guide/docs

**38. On the home page: is the flow "one giant form with everything" or a wizard (step 1 upload, step 2 prompt, step 3 categories, step 4 confirm)?**
_Answer:_ 1 giant form, hate wizards

**39. About page content: just etymology of "nomenclator" + 1 line on what the tool does? Or more?**
_Answer:_ yes just a brief intro that makes you think, cool that makes sense and thats a cool thing to know about, but just that. maybe slightly poeitc. slightly.

#### Misc

**40. Logo / favicon: do you have one, want me to design something simple, or skip for now?**
_Answer:_ design simple placeholder for now

**41. Domain: do you have one lined up for Fly, or use the default `*.fly.dev`?**
_Answer:_ yes caset.cl, but i expect a subdomain

**42. Analytics: truly none, or privacy-friendly (Plausible/Umami) is fine?**
_Answer:_ none

---

## Round 4 — Additional direction from user

- **Routing:** use **TanStack Router**.
- **Docs:** include a **mermaid plugin** — the site should feel self-explanatory / self-documented. Architecture, data flow, and job lifecycle should be rendered as mermaid diagrams inside the Docs page.
- **Pages (final list):**
  1. **Tool** — the main upload / run / download flow.
  2. **About** — etymology of "nomenclator" + 1-line purpose, straight to the point, a touch poetic.
  3. **Docs / Guide** — how to use the tool, how it works under the hood (mermaid diagrams), limits, costs, FAQ.

This supersedes Q37 (pages list) and Q41-ish route concerns from earlier rounds.

---

## Round 5 — Generality decision

**Decision:** Narrow UX + generic infra, with a `task_template` seam from day 1.

- **v1 (now):** job titles only. The Tool page is hard-coded to the job-title flow: 4 output columns (`original`, `male_es`, `female_es`, `category`), tuned default prompt + few-shots, Spanish output. UX is hyper-focused on this one case.
- **v2 (near future):** add 2–3 more "tools" for common lead-DB cleanup tasks (e.g. industries → standardized ES taxonomy, company-name normalization, etc.). Done by inserting new `task_template` rows + a small form variant per template. No engine rewrite.
- **v3 (far future):** fully generic — user defines their own output columns + prompt from a blank form. Not in scope now, not in the UI now, but the data model won't block it.

**Under-the-hood rules for v1, enforced by the spec:**
- SQLite has a `task_templates` table from day one, with exactly one seeded row: `job_titles_es`.
- Every job row stores `task_template_id` as a FK. The job runner is template-agnostic: it reads the template's system prompt, few-shots, output column schema, and taxonomy handling from the row — never hard-coded per task in the runner.
- CSV serialization reads columns from the template's `output_columns` JSON, so adding a second template doesn't touch the export code.
- The React form for v1 is job-title-specific and lives in its own module, so a second template in v2 means adding a sibling module, not editing the v1 form.
- The Docs page explicitly mentions this: "v1 is job titles; the engine is generic and more tools are coming." The About page stays poetic and doesn't roadmap anything.

**What we are NOT doing in v1:**
- No "choose a template" dropdown.
- No user-authored prompts from a blank slate (they *can* edit the pre-filled job-title prompt per run, but the default is strong and the form is shaped around that one task).
- No dynamic column builder.
- No multi-template job history UI — history just lists jobs, all of which will be job-title jobs in v1.

---

---

## Round 6 — Clustering + Python backend

### Decision: adopt Option C (fuzzy clustering on representatives)

After a second-opinion review, the baseline plan of "exact dedup then LLM on all uniques" was rejected. The core reason is **not cost** — Haiku batch is already cheap enough to fit the $20/mo cap many times over — but **consistency**. When near-duplicate titles ("Jefe Compras" vs "Jefe de Compras") are sent to the model in different batches with different few-shot neighbors, the model produces divergent Spanish standardizations, silently defeating the whole tool. Clustering eliminates this by guaranteeing each cluster of near-duplicates is resolved by a single representative and propagated.

**Adopted pipeline:**

1. Parse CSV.
2. Normalize (trim, collapse whitespace, lowercase, strip accents) for the dedup/cluster keys only — originals preserved.
3. Exact dedup on normalized key.
4. Fuzzy cluster with `rapidfuzz.token_sort_ratio ≥ 92`, secondary gate `token_set_ratio ≥ 90`.
5. Pick one representative per cluster (shortest + most frequent).
6. Show the operator a cluster preview: counts, top 10 largest clusters with members, estimated cost. No Anthropic calls yet.
7. Operator tunes threshold if needed; re-cluster is local and instant.
8. Operator commits → spend cap check → batch submission of representatives only, 20–25 titles per request to amortize prompt.
9. Poll until complete → parse results → write to `clusters` table → propagate to all rows via `cluster_id` at export time via SQL join.

**Guardrails against misclustering:**
- Conservative default threshold (92).
- Mandatory preview step — no commit without it.
- Full cluster mapping persisted in SQLite for audit.
- "Large cluster" warning when any cluster exceeds 50 members.

### Decision: switch backend to Python

Node + Hono was the original choice. Now switching to **Python 3.12 + FastAPI + rapidfuzz + pandas + httpx + `sqlite3` stdlib** because:

- `rapidfuzz` is Python-native, C-backed, battle-tested, and the right tool for this job. Node alternatives are rougher and would force hand-rolling token-sort ratio.
- `pandas` handles CSV edge cases (delimiters, encoding, BOM) better than any Node lib.
- Future-proofs v2/v3: if we ever want semantic clustering via embeddings, `sentence-transformers` is Python.
- FastAPI maps cleanly onto the endpoint set originally planned for Hono.

Frontend remains React + Vite + TypeScript + TanStack Router. The stack is now split by language at a clean JSON boundary.

### Honest cost math (replacing the earlier "$0.50" handwave)

Assumptions: Haiku 4.5 batch rates ≈ $0.40/MTok input + $2/MTok output (50% off standard, *approximate — confirm at build time*), 500-token system prompt, 800-token few-shots, ~10 input + ~30 output tokens per title, 25 titles per request to amortize prompt overhead.

| Strategy | Reqs | Input | Output | Cost |
|---|---|---|---|---|
| Raw, 1 title / req | 13,600 | ~17.8 M | ~0.4 M | ~$7.80 |
| Exact dedup, 1 / req | ~8,000 | ~10.5 M | ~0.24 M | ~$4.60 |
| Exact dedup, 25 / req | ~320 | ~0.62 M | ~0.24 M | ~$0.65 |
| **Cluster + 25 / req (v1)** | **~120** | **~0.2 M** | **~0.09 M** | **~$0.25** |

All four fit the $20/mo cap. The motivation is consistency, not cost. The "$0.50" earlier was a middle-of-the-road guess that assumed ~half amortization; actual projected cost is tighter.

### Data model changes driven by clustering

- New `clusters` table: `id`, `job_id`, `representative`, `normalized_key`, `member_count`, `male_es`, `female_es`, `category`, `error`.
- `job_rows` loses the answer columns — now only `original`, `normalized`, `cluster_id`, `is_representative`.
- `jobs` gains `fuzzy_threshold`, `exact_unique_rows`, `cluster_count`.
- `batches` gains `request_count`, `titles_per_request`.
- New job state: `preview` (between `draft` and `queued`).

### Endpoint changes

- `POST /jobs/preview` — upload + cluster, returns counts + top clusters + cost estimate.
- `POST /jobs/:id/recluster` — re-run clustering with a new threshold. Local only, no Anthropic.
- `POST /jobs/:id/commit` — spend cap check + submit to Anthropic.
- Everything else (`GET /jobs`, `GET /jobs/:id`, `GET /jobs/:id/download`, `POST /jobs/:id/cancel`, `POST /auth`) unchanged in shape.

### What this does NOT change

- v1/v2/v3 trajectory (narrow UX, generic infra, `task_template` seam).
- Single shared-password auth.
- Single giant form UX (one new control added: threshold slider + "Preview clusters" button).
- Three pages: Tool, About, Docs.
- Mermaid-in-Docs for self-documentation.
- Fly.io deployment.
- $20/mo hard cap.

---

---

## Round 7 — Batching knobs + the row-count invariant

### Two separate "batch size" knobs

`titles_per_request` and `requests_per_batch` are different things and both are adjustable. v1 exposes both in an **Advanced** disclosure in the giant form; defaults cover ~99% of cases.

| Knob | Default | Range | Notes |
|---|---|---|---|
| `titles_per_request` | 25 | 1–50 | Titles bundled into one LLM call as a JSON array |
| `requests_per_batch` | all reps in one batch | 1–100,000 | Anthropic Batch API's hard cap |

**Why 25 as default** for `titles_per_request`:
- Amortizes the ~1,300-token prompt overhead across many titles.
- Output for 25 titles ≈ 1,400 tokens, comfortably under a 2,000-token `max_tokens` ceiling.
- One bad title only poisons 25 others at worst, and the straggler retry loop (see below) recovers from that.
- 50 starts hitting JSON truncation; 10 leaves cost on the table.

**`requests_per_batch`** almost never needs tuning. Anthropic accepts up to 100k requests per batch, so v1 always submits all of a job's representatives in a single batch call.

### The row-count invariant (the hard contract)

> **Every row in the uploaded CSV corresponds to exactly one row in the downloaded CSV, in the same order.**
> Every output row is either **populated** (all answer columns filled, `error` empty) or **flagged** (`error` populated with a specific reason, answer columns empty or best-effort). No row is ever silently dropped. No row is ever duplicated. Order is preserved.

This is enforced by a defense-in-depth stack, documented as diagram #12 in `solution-overview.md`:

1. **Clustering** reduces the problem surface: the LLM only ever sees representatives; the 16k → 16k expansion is a pure `SELECT … FROM job_rows JOIN clusters ORDER BY row_id`.
2. **Anthropic tool use** with a forced `tool_choice` and a strict `input_schema` requiring `minItems == maxItems == titles_per_request`. The model cannot respond with prose or partial output.
3. **Explicit IDs** (`t001`, `t002`, …) on every title. The output diff is set-based, never positional. Hallucinated extras are dropped, missing IDs are collected.
4. **Sized `max_tokens`** (~2,000 for 25 titles) prevents silent truncation.
5. **Pydantic parse-or-fail** — any schema violation invalidates the whole request; we never salvage partial garbage.
6. **Stragglers retry loop** — missing IDs across all requests are collected into one pile and re-batched with `titles_per_request` halved each round (25 → 12 → 6 → 1), up to 3 rounds.
7. **Pre-write assertion** — `assert len(out) == len(in)` before the CSV is produced. If it ever fires, the job transitions to `failed` with a crash report. The operator never receives a partial CSV.

### Implementation notes baked into the spec

- Each input row gets an immutable `row_id` on ingestion (stable ordering).
- Cluster size can be 1 (for unique titles) — that's fine, they go through the same path.
- A flagged row has its `error` column populated with a machine-readable reason, not free text: `max_retries_exceeded`, `schema_violation`, `tool_refusal`, `truncated`, etc. The operator can grep the output CSV for these.
- The Advanced disclosure also surfaces the error code table so the operator knows what each means.

### Spec file list gains one entry

`spec/18-reliability-contract.md` — the row-count invariant, the layered defense, the error code table, and the pre-write assertion. This is the most load-bearing document in the whole spec because it's the one promise the tool must never break.

**Updated spec file count: 18 files.**

---

_All requirements gathered. `solution-overview.md` now has 13 diagrams covering Rounds 1–7. Next step: generate `spec/` then `plan/`._
