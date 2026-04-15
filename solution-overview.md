# Nomenclator — Solution Overview

Visual reference for the v1 build. Every diagram below is Mermaid; the same diagrams will be reused in the in-app Docs page so the tool is self-documenting.

---

## 1. System context

Who talks to what. A single human ("the operator") uses a browser, which talks to one FastAPI server on Fly.io, which talks to SQLite on the same volume and to Anthropic's Message Batches API. Python is chosen for the backend specifically so we can use `rapidfuzz` for the clustering step (see diagrams 6 and 6b); Node has no equivalent of the same quality.

The FastAPI process runs **two concurrent things** in one Python process: (1) the HTTP request handlers, and (2) a long-running asyncio **background worker** started in the FastAPI lifespan that periodically scans SQLite for non-terminal jobs and polls Anthropic for batch status. One process, one Fly machine, no Celery / Redis / extra moving parts.

```mermaid
flowchart LR
    Operator([Operator<br/>single user])
    Browser[Browser<br/>React + Vite + TS<br/>TanStack Router]
    subgraph FastAPI["FastAPI process"]
        HTTP[HTTP handlers<br/>routes /auth /jobs /...]
        Worker[Background worker<br/>asyncio task<br/>polls Anthropic + retries]
    end
    DB[(SQLite<br/>Fly volume)]
    Anthropic[Anthropic<br/>Message Batches API<br/>claude-haiku-4-5]

    Operator -->|HTTPS| Browser
    Browser <-->|JSON · session cookie| HTTP
    HTTP <--> DB
    Worker <--> DB
    HTTP -->|submit batch| Anthropic
    Worker <-->|poll + fetch results| Anthropic
```

---

## 2. Frontend page map

Three routes, all under one SPA. TanStack Router handles the split. Tool is the only interactive page; About and Docs are content.

```mermaid
flowchart TB
    Root[/ root layout<br/>header + theme toggle/]
    Tool[/tool<br/>upload · prompt · run · download/]
    About[/about<br/>etymology + purpose/]
    Docs[/docs<br/>guide + mermaid diagrams/]

    Root --> Tool
    Root --> About
    Root --> Docs

    Tool --> Jobs[Jobs panel<br/>history + status]
    Tool --> Form[Single giant form<br/>input · prompt · taxonomy · submit]
```

---

## 3. Data model (v1, with v2 seam)

The `task_templates` table is the seam for future generality. In v1 it has exactly one seeded row, `job_titles_es`. Every `job` references a template, so v2 is additive. The `clusters` table is new: it stores the fuzzy-clustering result so row expansion at the end of a job is a deterministic join, and so the operator can audit which titles were treated as the same.

```mermaid
erDiagram
    task_templates ||--o{ jobs : "used by"
    jobs ||--o{ batches : "fans out to"
    jobs ||--o{ job_rows : "contains"
    jobs ||--o{ clusters : "grouped into"
    clusters ||--o{ job_rows : "contains members"
    batches ||--o{ batch_requests : "split into"
    batch_requests }o--o{ clusters : "resolves (via cluster_ids)"

    task_templates {
        text id PK "job_titles_es (v1 only)"
        text name
        text system_prompt
        json few_shots
        json output_columns
        int default_titles_per_request
    }

    jobs {
        text id PK
        text task_template_id FK
        text status "draft|preview|queued|submitted|polling|retrying|completed|failed|cancelled"
        text user_prompt_override
        text user_taxonomy
        int fuzzy_threshold "default 90"
        int titles_per_request "default 25"
        int total_rows
        int exact_unique_rows
        int cluster_count
        int completed_rows
        int error_rows
        real est_cost_usd
        real actual_cost_usd
        int created_at
        int finished_at
    }

    batches {
        text id PK "anthropic batch_id"
        text job_id FK
        int retry_round "0=initial, 1+ retries"
        text parent_batch_id "self-FK, nullable"
        text status
        int request_count
        int submitted_at
        int polled_at
        int completed_at
    }

    batch_requests {
        text id PK "== Anthropic custom_id"
        text batch_id FK
        json cluster_ids "which clusters this req covers"
        text status "pending|completed|failed|missing"
        text raw_response
        text error
    }

    clusters {
        int id PK
        text job_id FK
        text representative_original "title sent to LLM"
        text normalized_key
        int member_count
        int retry_count "incremented per straggler round"
        text male_es
        text female_es
        text category
        text error "error code, nullable"
    }

    job_rows {
        int id PK
        text job_id FK
        int cluster_id FK
        int row_index "stable input order for export"
        text original
        text normalized
        bool is_representative
    }

    spend_log {
        int id PK
        text job_id FK
        text batch_id FK "nullable, for retry attribution"
        real usd
        int at
    }

    sessions {
        text id PK
        int created_at
        int expires_at
    }
```

**Key design points:**

- **Standardized outputs** (`male_es`, `female_es`, `category`, `error`) live on `clusters`, not `job_rows`. Every row inherits its answer via `cluster_id`. Export is a pure SQL join, not a loop.
- **`batch_requests`** is the critical mapping table. Anthropic returns results keyed by `custom_id`, one line per request; each request handled `titles_per_request` cluster representatives bundled in a JSON array. Straggler detection = diff the expected `cluster_ids` set against the IDs present in the parsed response.
- **`batches.retry_round`** lets us distinguish the initial batch (round 0) from straggler retries (rounds 1–3). `parent_batch_id` is a self-FK for audit.
- **`job_rows.row_index`** is the stable input order so the CSV export preserves row ordering exactly.

---

## 4. Job lifecycle state machine

Every job walks this path. The server stores state in SQLite so a Fly restart mid-run resumes cleanly — on boot the background worker scans for non-terminal jobs and re-polls their `batch_id`s. The `preview` state is entered when the operator has uploaded rows and run the clustering preview but has not yet committed. Preview work is cheap (no Anthropic calls). The `retrying` state is entered when the initial batch returned with stragglers and a retry round is being submitted.

```mermaid
stateDiagram-v2
    [*] --> draft: user opens form
    draft --> preview: upload + cluster<br/>preview computed
    preview --> preview: threshold adjusted<br/>→ re-cluster (local only)
    preview --> queued: submit clicked<br/>(spend cap ok)
    draft --> [*]: abandoned
    preview --> [*]: abandoned

    queued --> submitted: batch posted<br/>to Anthropic
    queued --> cancelled: user cancels
    submitted --> polling: first poll ok
    submitted --> cancelled: user cancels
    polling --> polling: still running<br/>(backoff)
    polling --> retrying: stragglers found<br/>retry_round < 3
    polling --> completed: all clusters resolved<br/>(possibly with error rows)
    polling --> failed: catastrophic<br/>(API down, all requests errored)
    polling --> cancelled: user cancels

    retrying --> submitted: new batch posted<br/>retry_round++<br/>titles_per_request halved
    retrying --> completed: spend cap exceeded<br/>→ flag stragglers

    completed --> [*]: csv downloadable
    failed --> [*]: error visible
    cancelled --> [*]
```

**"Completed" vs "failed" — the important distinction:**

- `completed` = the job ran end-to-end and produced a CSV. `error_rows > 0` is allowed; those rows carry per-row `error` codes but the file is delivered.
- `failed` = the job could not produce any CSV. Reserved for catastrophic, job-level failures: Anthropic outage, all requests schema-failed, server crash mid-write, etc.

This matters because the row-count invariant (diagram 12) only holds for `completed` — failure produces no file, not a partial one.

---

## 5. Happy-path sequence — submit to download (with retries)

End-to-end timeline, including the stragglers retry loop and the split between HTTP handlers and the background worker. The operator can close the tab after submit and come back later; state lives in SQLite, the worker carries on.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator
    participant UI as Browser (SPA)
    participant API as FastAPI HTTP
    participant W as Background worker
    participant DB as SQLite
    participant AN as Anthropic Batches

    User->>UI: fill giant form<br/>(upload + prompt + taxonomy + threshold)
    UI->>API: POST /jobs/preview { rows, threshold }
    API->>API: parse CSV, normalize,<br/>exact dedup, cluster
    API->>DB: INSERT job (status=preview)<br/>INSERT job_rows, clusters
    API-->>UI: { job_id, exact_unique, cluster_count,<br/>top_clusters, est_cost_usd }

    opt threshold tweak
        UI->>API: POST /jobs/:id/recluster { threshold }
        API->>API: re-cluster (cached normalized)
        API->>DB: DELETE+INSERT clusters
        API-->>UI: updated counts + cost
    end

    User->>UI: click Submit
    UI->>API: POST /jobs/:id/commit<br/>{ prompt, taxonomy, titles_per_request }
    API->>API: spend cap check
    API->>AN: POST /v1/messages/batches<br/>(N requests, custom_id per request)
    AN-->>API: batch_id
    API->>DB: INSERT batches (round=0)<br/>INSERT batch_requests<br/>job.status=submitted
    API-->>UI: 202 { job_id }

    Note over UI: User may close tab here.

    loop worker tick every 30s
        W->>DB: SELECT jobs WHERE<br/>status IN (submitted, polling, retrying)
        W->>AN: GET /v1/messages/batches/:id
        AN-->>W: status (+ results_url when ended)
        W->>DB: UPDATE batches.polled_at
    end

    AN-->>W: batch ended
    W->>AN: GET results JSONL
    AN-->>W: one line per custom_id
    W->>W: parse tool output, validate IDs per request
    W->>DB: UPDATE clusters with answers<br/>UPDATE batch_requests.status

    alt all clusters resolved
        W->>DB: job.status=completed<br/>INSERT spend_log
    else stragglers found, retry_round < 3
        W->>W: collect missing cluster_ids<br/>halve titles_per_request
        W->>W: spend cap check
        alt cap ok
            W->>AN: POST new batch (retry)
            AN-->>W: new batch_id
            W->>DB: INSERT batches (round+1)<br/>parent_batch_id=prev<br/>job.status=retrying → submitted
            Note over W: loop back to polling
        else cap exceeded
            W->>DB: clusters.error=spend_cap_exceeded<br/>job.status=completed
        end
    else retry_round == 3
        W->>DB: clusters.error=max_retries_exceeded<br/>job.status=completed
    end

    User->>UI: reopen /tool
    UI->>API: GET /jobs (every 5s while non-terminal)
    API-->>UI: status
    UI->>User: browser Notification on completion
    User->>UI: click Download
    UI->>API: GET /jobs/:id/download
    API->>DB: SELECT job_rows JOIN clusters<br/>ORDER BY row_index
    API-->>UI: CSV (UTF-8 BOM, full rows)
```

---

## 6. Pipeline: dedup → cluster → batch → propagate

The consistency and cost-saving layer. 16k raw titles collapse to ~8k after exact dedup, then to ~2–4k after fuzzy clustering. **Only cluster representatives** go to the model; every other row inherits its answer via its cluster. This guarantees "Jefe Compras" and "Jefe de Compras" receive the *same* standardized output, which is the whole point of the tool. Without this step, the LLM would see similar titles in different batches with different few-shot neighbors and produce divergent answers — a silent failure mode that would only surface weeks later.

```mermaid
flowchart TB
    Input[Raw input rows<br/>~16k titles]
    ExactNorm[Normalize for exact match:<br/>trim · collapse spaces<br/>lowercase · strip accents]
    ExactDedup[Exact dedup<br/>~16k → ~8k]
    Cluster[rapidfuzz cluster<br/>token_sort_ratio ≥ threshold<br/>default 92]
    Reps[Pick representatives<br/>~8k → ~2–4k reps]
    Preview{Preview to user<br/>counts + largest clusters}
    Chunk[Chunk reps into<br/>requests<br/>25 titles per request]
    Submit[POST batch<br/>to Anthropic]
    Wait[Poll until done]
    Parse[Parse JSON responses<br/>validate per-title]
    Write[Write answers onto<br/>clusters table]
    Propagate[Propagate to<br/>all job_rows via cluster_id]
    Out[Output CSV<br/>original · male · female · category · error<br/>full 16k rows]

    Input --> ExactNorm --> ExactDedup --> Cluster --> Reps --> Preview
    Preview -- adjust threshold --> Cluster
    Preview -- commit --> Chunk --> Submit --> Wait --> Parse --> Write --> Propagate --> Out
```

---

## 6b. Clustering algorithm internals

The risky step. Misclustering is silent corruption: if "Product Manager" and "Project Manager" fall into the same cluster, one representative propagates the wrong answer to every member. We mitigate with the right similarity metric, a conservative default threshold, a hard length-ratio guard, union-find for connected components, and a mandatory human preview before commit.

```mermaid
flowchart TB
    In[Exact-dedup'd titles<br/>~8k]
    Norm[Per-title normalization:<br/>strip accents · lowercase<br/>collapse inner whitespace<br/>drop punctuation]
    Pair["rapidfuzz.process.cdist<br/>metric = token_set_ratio<br/>~64M comparisons in ~2s"]
    Thresh{"token_set_ratio ≥ threshold<br/>AND len_ratio ≥ 0.6?"}
    Edges[Collect edges<br/>pairs above threshold]
    UF[Union-Find<br/>connected components<br/>= clusters]
    Pick["Pick representative:<br/>1. most frequent in input<br/>2. tiebreak: shortest length<br/>3. tiebreak: alphabetical"]
    Out2[clusters table<br/>+ cluster_id on each row]

    In --> Norm --> Pair --> Thresh
    Thresh -- yes --> Edges --> UF --> Pick --> Out2
    Thresh -- no --> Edges
```

**Why `token_set_ratio` as the primary metric (not `token_sort_ratio`):**

The dominant variation in real Spanish job titles is dropped/added stop words: `"Jefe Compras"` vs `"Jefe de Compras"`, `"Director Ventas"` vs `"Director de Ventas"`. `token_set_ratio` treats these as near-identical (typically 95–100) because it compares the set of tokens after handling common-vs-different words asymmetrically. `token_sort_ratio` is stricter and may score the same pair at ~80, pushing it below a 90 threshold and failing to merge.

**Why the length-ratio guard is mandatory:**

`token_set_ratio` alone has a failure mode: `"Jefe"` and `"Jefe de Compras Internacionales del Grupo"` both contain the token `"jefe"`, so the shorter-vs-longer set comparison can return a high score. A length-ratio gate (`min(len_a, len_b) / max(len_a, len_b) ≥ 0.6`) blocks these merges before they can happen. 0.6 is conservative; tunable per job.

**Connected components:** hand-rolled union-find (~20 lines, path compression + union by rank), not `networkx` — avoids a heavy dep and is faster for our sizes.

**Representative selection is fully deterministic:** same input → same representative, every time. Stability matters because the cluster preview the operator approves must be the same cluster structure that runs.

**Guardrails baked into v1:**
- Default threshold **90** on `token_set_ratio`; configurable per job (50–100).
- Hard gate: `len_ratio ≥ 0.6` always applied regardless of threshold.
- Preview endpoint returns the **top 10 largest clusters** with all members, so the operator can eyeball homogeneity before committing Anthropic spend.
- Full cluster mapping persisted in the `clusters` table for post-hoc audit.
- Clusters larger than 50 members trigger a "large cluster" warning in the preview UI.
- Expected latency: ~2–3 seconds for 8k uniques on a shared Fly machine. Acceptable for an interactive preview.

---

## 7. Spend cap enforcement

Hard $20/month ceiling. The estimate is computed **after clustering** (reflects actual representative count, not raw rows) and checked on the `/commit` call, before any Anthropic request. Rolling 30-day window. **Retry batches are also subject to the cap** — the background worker runs the same check before submitting a straggler retry, and flags remaining stragglers with `error=spend_cap_exceeded` if the cap would be busted.

```mermaid
flowchart TB
    Submit[commit or retry submission]
    Est[Estimate cost:<br/>reps ÷ titles_per_request<br/>× tokens_per_req<br/>× haiku batch rate]
    Sum[Sum spend_log<br/>last 30 days]
    Check{est + sum<br/>≤ $20?}
    Accept[POST batch to Anthropic<br/>INSERT spend_log on actual]
    Refuse1[/commit: 409 Conflict<br/>show cap + ETA to reset/]
    Refuse2[retry: flag stragglers<br/>error=spend_cap_exceeded<br/>job → completed/]

    Submit --> Est --> Sum --> Check
    Check -- yes --> Accept
    Check -- no, from commit --> Refuse1
    Check -- no, from retry --> Refuse2
```

---

## 8. Auth flow

Single shared password. Server stores an argon2 hash as a Fly secret. A successful login sets an httpOnly session cookie backed by the `sessions` table. All `/jobs` routes require the cookie.

```mermaid
sequenceDiagram
    actor User as Operator
    participant UI as Browser
    participant API as FastAPI server
    participant DB as SQLite

    User->>UI: open site
    UI->>API: GET /me
    API-->>UI: 401
    UI->>User: show password field
    User->>UI: type password
    UI->>API: POST /auth { password }
    API->>API: argon2.verify(hash, pwd)
    alt valid
        API->>DB: INSERT session (30d)
        API-->>UI: Set-Cookie: sid=...<br/>(httpOnly, Secure, SameSite=Lax)
        UI->>UI: route to /tool
    else invalid
        API-->>UI: 401 + rate-limit tick
    end
```

---

## 9. Scope trajectory — v1 → v2 → v3

The engine is generic from day one. The UX is not. v1 ships with one `task_template`; each later version adds templates (and, eventually, a blank-slate mode) without rewriting the runner.

```mermaid
flowchart LR
    subgraph v1["v1 — now"]
        direction TB
        v1ui[Hard-coded job-title form]
        v1t[1 template:<br/>job_titles_es]
        v1ui --> v1t
    end

    subgraph v2["v2 — near"]
        direction TB
        v2ui[Template picker<br/>+ per-template forms]
        v2a[job_titles_es]
        v2b[industries_es]
        v2c[companies_es]
        v2ui --> v2a
        v2ui --> v2b
        v2ui --> v2c
    end

    subgraph v3["v3 — far"]
        direction TB
        v3ui[Blank-slate builder<br/>custom columns + prompt]
        v3engine[Same generic<br/>job runner]
        v3ui --> v3engine
    end

    v1 --> v2 --> v3
```

---

## 10. Deployment topology on Fly.io

One app, one region initially, one persistent volume for SQLite + uploaded CSVs. Anthropic key lives in Fly secrets, never ships to the browser. The frontend is built into static assets and served by the same FastAPI process (or by Fly's static file serving); no separate CDN for v1.

```mermaid
flowchart LR
    CF[Cloudflare / DNS<br/>caset.cl subdomain]
    Fly[Fly.io app<br/>nomenclator<br/>Python 3.12 + static React build]
    Vol[(Persistent volume<br/>/data)]
    Secrets[Fly secrets<br/>ANTHROPIC_API_KEY<br/>AUTH_PASSWORD_HASH]
    Anthropic[Anthropic API]

    CF --> Fly
    Fly --> Vol
    Fly -.reads.-> Secrets
    Fly -->|outbound HTTPS| Anthropic
```

---

## 11. Cost model (why clustering matters more than batching)

Rough math for a 13,600-row run, showing why the consistency motivation dominates the cost motivation. Haiku 4.5 batch rates ≈ 50% off Haiku standard (~$0.80/MTok input, ~$4/MTok output — *ballpark*, confirm at build time).

```mermaid
flowchart LR
    subgraph Raw["no dedup, 1 title/req"]
        R1[13,600 reqs<br/>×1,310 in + 30 out<br/>≈ $7.80]
    end
    subgraph ExactOnly["exact dedup, 1 title/req"]
        E1[~8,000 reqs<br/>≈ $4.60]
    end
    subgraph ExactBundled["exact dedup, 25/req"]
        EB[~320 reqs<br/>≈ $0.65]
    end
    subgraph Clustered["cluster + 25/req (v1)"]
        C1[~120 reqs<br/>~2,500 reps<br/>≈ $0.25]
    end

    Raw --> ExactOnly --> ExactBundled --> Clustered
```

All four options fit inside the $20/mo cap comfortably. **The reason v1 uses clustering is not cost — it's that "Jefe Compras" and "Jefe de Compras" must produce the same Spanish output, and only clustering guarantees that.**

---

## 12. Reliability: guaranteeing N input rows → N output rows

The hardest problem in any LLM-CSV pipeline: "I sent 100 rows, I got 87 back." Defense-in-depth across seven layers, from preventing the failure to catching it if it happens anyway. The hard contract at the bottom: **the output CSV has exactly the same number of rows as the input, in the same order, and no row is ever silently dropped.**

```mermaid
flowchart TB
    L0[Layer 0 — Clustering<br/>LLM only sees reps<br/>16k→16k is pure SQL join]
    L1[Layer 1 — Anthropic tool use<br/>forced tool_choice +<br/>strict input_schema]
    L2[Layer 2 — Explicit IDs<br/>every title carries id=t001…<br/>diff input vs output set]
    L3[Layer 3 — Sized max_tokens<br/>~2000 for 25 titles<br/>no silent truncation]
    L4[Layer 4 — Pydantic validation<br/>parse-or-fail, no salvage]
    L5[Layer 5 — Stragglers retry<br/>halve titles_per_request<br/>up to 3 rounds]
    L6[Layer 6 — Row-count invariant<br/>every input row = one output row<br/>populated OR flagged with error]
    L7[Layer 7 — Pre-write assertion<br/>len out == len in<br/>or job fails hard]

    L0 --> L1 --> L2 --> L3 --> L4 --> L5 --> L6 --> L7
```

### The stragglers retry sub-flow

```mermaid
flowchart TB
    Main[Main batch submitted<br/>N reqs × 25 titles]
    Parse[Parse all results]
    Diff[Diff expected vs received IDs<br/>per request]
    OK{All IDs present?}
    Done[Merge into clusters table]
    Strag[Collect stragglers<br/>across all reqs]
    Retry{Retry round < 3?}
    Halve[titles_per_request halved<br/>25 → 12 → 6 → 1<br/>resubmit as new batch]
    Fail[Mark remaining cluster rows<br/>error = max_retries_exceeded]

    Main --> Parse --> Diff --> OK
    OK -- yes --> Done
    OK -- no --> Strag --> Retry
    Retry -- yes --> Halve --> Parse
    Retry -- no --> Fail --> Done
```

### The contract, written plainly

> Every row in the uploaded CSV corresponds to exactly one row in the downloaded CSV, in the same order.
> Every output row is in one of two states:
>
> - **Populated** — `male_es`, `female_es`, `category` filled, `error` empty.
> - **Flagged** — `error` contains a specific failure reason; the answer columns may be empty or best-effort.
>
> No row is ever silently dropped. No row is ever duplicated. Order is preserved.

This is enforceable because input rows get a stable `row_id` on ingestion, every row lands in a cluster (of size ≥1), every cluster is either resolved or flagged, and export is `SELECT … FROM job_rows JOIN clusters ORDER BY row_id` — a pure join. The pre-write assertion is the last line of defense: if `len(out) != len(in)` for any reason, the job transitions to `failed` and the operator gets an error, never a partial CSV.

---

## 13. The two batching knobs

Two separate things called "batch size," both adjustable, both meaningful:

```mermaid
flowchart TB
    subgraph Request["titles_per_request (default 25)"]
        direction LR
        T1[title 1]
        T2[title 2]
        Tn[… title 25]
        JSON[one JSON array in<br/>one JSON array out]
        T1 --> JSON
        T2 --> JSON
        Tn --> JSON
    end

    subgraph Batch["requests_per_batch (default: all reps in one batch)"]
        direction LR
        R1[request 1<br/>25 titles]
        R2[request 2<br/>25 titles]
        Rn[… request N<br/>25 titles]
        Anthropic[Anthropic Batch API<br/>hard cap: 100,000 reqs]
        R1 --> Anthropic
        R2 --> Anthropic
        Rn --> Anthropic
    end

    Request -.one of N in.-> Batch
```

**`titles_per_request` tradeoffs:**

| Setting | Cost | JSON reliability | Retry granularity |
|---|---|---|---|
| 1 | highest (no prompt amortization) | best | best |
| 10 | medium | good | good |
| **25 (default)** | low | good | acceptable |
| 50 | lowest | risky (truncation) | poor (one bad title kills many) |

**`requests_per_batch`** rarely needs tuning — Anthropic's batch endpoint happily accepts all the representatives for one job in a single submission. The only reason to split is if a job has > 100,000 reps, which won't happen at v1 scale.

Both knobs live in the Advanced disclosure of the giant form; defaults are invisible.

---

_All thirteen diagrams are authoritative for the spec build. Any change here must propagate into `spec/` and `plan/`._
