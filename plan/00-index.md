# 00 — Plan Index

This directory breaks the build of Nomenclator v1 into ~100 small, individually-testable tasks suitable for a Ralph-style loop (one LLM session per task, each task gated by a passing test).

## How to use this plan

1. Start at the dependency DAG below. Do tasks in an order that respects dependencies.
2. For each task: open the relevant phase file, find the task by ID, execute exactly what it says.
3. Run the test command listed under **Test**. The task is done only when the test passes.
4. Mark the checkbox in the file and move on.
5. Never skip the test — if the test is wrong, **fix the test first** and do not weaken it.
6. If a task says something that contradicts `spec/`, the spec wins. Report the mismatch and fix the plan.

## Phase files

| File | Phase | Tasks | Prereqs |
|---|---|---|---|
| `01-scaffolding.md` | Repo + tooling scaffolding | 9 | — |
| `02-data-model-and-dao.md` | SQLite schema + DAO layer | 12 | 01 |
| `03-csv-and-normalization.md` | CSV parsing + text normalization | 7 | 01 |
| `04-clustering.md` | Fuzzy clustering pipeline | 8 | 01, 03 |
| `05-anthropic-client.md` | Anthropic batches client + tool use | 11 | 01 |
| `06-cost-and-cap.md` | Cost estimation + monthly cap | 4 | 01, 02 |
| `07-job-service.md` | Job service layer + state machine | 11 | 02, 03, 04, 05, 06 |
| `08-background-worker.md` | Asyncio worker + retry loop | 9 | 02, 05, 06, 07 |
| `09-auth.md` | Password auth + sessions + rate limits | 5 | 01, 02 |
| `10-http-api.md` | FastAPI endpoints | 17 | 07, 08, 09 |
| `11-export.md` | CSV export + pre-write assertion | 5 | 02, 07 |
| `12-reliability-test-suite.md` | The 9 mandatory reliability tests | 9 | 08, 10, 11 |
| `13-frontend-scaffolding.md` | Vite + TanStack Router + theme | 7 | 01 |
| `14-frontend-tool-page.md` | Tool page: form + preview + status | 18 | 13, 10 |
| `15-frontend-about-and-docs.md` | About + Docs pages + mermaid | 5 | 13 |
| `16-integration-test.md` | End-to-end integration test | 1 | 12, 14 |
| `17-deployment.md` | Dockerfile + fly.toml + secrets + CSP | 8 | 10, 14 |

**Total: ~136 tasks.**

## Dependency DAG (high level)

```
01 scaffolding
   ├── 02 data-model ──┐
   ├── 03 csv ─────────┤
   ├── 05 anthropic ───┤
   ├── 09 auth ────────┤
   └── 13 fe-scaffold ─┼── 14 fe-tool ──┐
                       │                │
    (02+03) → 04 cluster │              │
    (02+05) → 06 cost ───┤              │
    (02..06) → 07 jobs ──┤              │
    (02+05+06+07) → 08 worker ──┐       │
                               │       │
    (07+08+09) → 10 http-api ──┼───────┤
    (02+07) → 11 export ───────┤       │
                               │       │
    (08+10+11) → 12 reliability ├── 16 integration ── 17 deploy
                               │       │
            13 → 15 fe-about-docs      │
```

Tasks within a phase may have intra-phase deps (listed on each task). The phase-level order above is the safe default.

## Task template

Every task in this plan uses the same template:

```
### P##-## — Short name

**Deps:** comma-separated list of task IDs that must be green (or `—`)
**Files:** exact file paths the task will create or modify
**Goal:** one sentence

**Implementation:**
Terse notes. Prefer bulleted specifics over prose.

**Test:** `exact pytest/npm command`

Required assertions (test function names or assertion descriptions — must all exist and pass):
- assertion 1
- assertion 2
- ...

**Done when:**
- [ ] Test command exits 0
- [ ] All required assertions are present in the test file
- [ ] (other per-task gates)
```

## Conventions

- **Language:** Python 3.12 for backend. TypeScript for frontend.
- **Package manager (backend):** `uv` (fast, simple).
- **Package manager (frontend):** `pnpm`.
- **Test runner (backend):** `pytest`.
- **Test runner (frontend):** `vitest`.
- **Formatter (backend):** `ruff format`.
- **Linter (backend):** `ruff check`.
- **Formatter (frontend):** `prettier`.
- **Type checker (frontend):** `tsc --noEmit`.
- **Component library (frontend):** `shadcn/ui` (Tailwind + Radix).
- **CSS framework (frontend):** Tailwind CSS v4.
- **Commit style:** one commit per task, prefix with task ID: `P02-05: implement jobs DAO`.
- **Branching:** work directly on `main` for v1, or short-lived feature branches merged with `--no-ff`. Operator's call.

## Canonical directory layout

```
nomenclator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app factory
│   │   ├── settings.py
│   │   ├── pricing.py
│   │   ├── logging_config.py
│   │   ├── db.py                   # connection + migrations
│   │   ├── migrations/
│   │   │   └── 001_initial.sql
│   │   ├── dao/
│   │   │   ├── __init__.py
│   │   │   ├── task_templates.py
│   │   │   ├── jobs.py
│   │   │   ├── job_rows.py
│   │   │   ├── clusters.py
│   │   │   ├── batches.py
│   │   │   ├── batch_requests.py
│   │   │   ├── spend_log.py
│   │   │   └── sessions.py
│   │   ├── csv_io/
│   │   │   ├── parser.py
│   │   │   ├── normalize.py
│   │   │   └── exporter.py
│   │   ├── cluster/
│   │   │   ├── unionfind.py
│   │   │   ├── similarity.py
│   │   │   └── pipeline.py
│   │   ├── anthropic/
│   │   │   ├── client.py
│   │   │   ├── tool_schema.py
│   │   │   ├── request_builder.py
│   │   │   ├── response_parser.py
│   │   │   └── models.py           # pydantic
│   │   ├── jobs/
│   │   │   ├── service.py
│   │   │   ├── state_machine.py
│   │   │   └── estimator.py
│   │   ├── worker/
│   │   │   └── poller.py
│   │   ├── auth/
│   │   │   ├── passwords.py
│   │   │   ├── sessions.py
│   │   │   ├── middleware.py
│   │   │   └── rate_limit.py
│   │   └── api/
│   │       ├── auth.py
│   │       ├── jobs.py
│   │       ├── spend.py
│   │       ├── health.py
│   │       └── errors.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── fixtures/
│   │   ├── dao/
│   │   ├── csv/
│   │   ├── cluster/
│   │   ├── anthropic/
│   │   ├── jobs/
│   │   ├── worker/
│   │   ├── api/
│   │   └── reliability/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── routes/
│   │   │   ├── __root.tsx
│   │   │   ├── index.tsx          # Tool
│   │   │   ├── about.tsx
│   │   │   └── docs.tsx
│   │   ├── components/
│   │   │   └── ui/           # shadcn components (auto-generated)
│   │   ├── hooks/
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   └── theme.ts
│   │   └── styles/
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
├── Dockerfile
├── fly.toml
├── .env.example
├── spec/
├── plan/
├── solution-overview.md
└── README.md
```

## The golden rule

**If the test is correct, the implementation cannot be wrong.** Write the test first where the task allows. If you finish an implementation and the test is still passing *without running the code*, the test is wrong — fix it before moving on.
