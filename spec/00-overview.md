# 00 — Overview

## What Nomenclator is

A private, single-operator web tool that standardizes messy job titles (scraped from LinkedIn and similar sources) into canonical Spanish forms. For each input title it produces three outputs: a standardized male form, a standardized female form, and a category. It is used to clean a leads database so downstream outreach emails can segment correctly.

## V1 scope, in one sentence

Upload a CSV (or paste a column), configure prompt and taxonomy, optionally review prompt quality via a single AI call, choose to process all rows or a subset for test runs, toggle dry-run mode to validate workflow without API costs, preview fuzzy clusters, commit, let Anthropic's batch API process the cluster representatives, download a CSV with the same number of rows in the same order — where each row is either populated or flagged with a specific error code.

## V1 non-goals

Multi-user accounts, admin panels, mobile UI, PWA, offline mode, cross-run caching, embedding-based clustering, user-defined output columns from a blank slate, task templates other than `job_titles_es`, analytics, email notifications. See `16-out-of-scope.md`.

## V1 → V2 → V3 trajectory

- **v1 (current):** exactly one task, `job_titles_es`. Hard-coded UX. Generic infra underneath.
- **v2:** 2–3 more tasks (industries, companies, etc.) added by seeding `task_templates` rows and adding per-template form variants. No engine rewrite.
- **v3:** fully generic — operator defines output columns and prompt from a blank form. Not in v1 scope; data model will not block it.

## Architecture at a glance

- **Frontend:** React + Vite + TypeScript + TanStack Router + Tailwind CSS + shadcn/ui. Single SPA, three routes: `/` (Tool), `/about`, `/docs`.
- **Backend:** Python 3.12 + FastAPI + rapidfuzz + pandas + httpx + `sqlite3` stdlib, one process with an embedded asyncio background worker.
- **Storage:** SQLite on a persistent Fly volume.
- **LLM:** Anthropic Messages Batches API, model `claude-haiku-4-5`, forced tool use with a strict JSON schema.
- **Deployment:** Fly.io, one app, one machine, one region. Static frontend bundle served by the same FastAPI process.
- **Auth:** single shared password → argon2 hash in Fly secrets → httpOnly session cookie backed by a `sessions` table.

## The three hard promises

1. **Row-count invariant.** Output has exactly as many rows as input, in the same order. No row is ever silently dropped. See `18-reliability-contract.md`.
2. **Spend cap.** Hard $20/month ceiling. Enforced before every Anthropic call, including retries. See `13-cost-model.md`.
3. **Consistency.** Semantically-duplicate titles (e.g. "Jefe Compras" vs "Jefe de Compras") are resolved by a single cluster representative so they cannot receive divergent standardizations. See `09b-clustering.md`.
4. **Safe to experiment.** Prompt review, row subsets, and dry-run mode let the operator validate their configuration — quality, scope, and end-to-end wiring — before committing to a full paid run.

## Spec map

| File | Purpose |
|---|---|
| `00-overview.md` | This document. Entry point. |
| `01-glossary.md` | Canonical definitions of every term. |
| `02-user-stories.md` | Operator flows, happy path + edges. |
| `03-functional-requirements.md` | Numbered FR-### list, testable. |
| `04-non-functional.md` | Performance, browser support, a11y, ops. |
| `05-data-model.md` | Full SQLite DDL + indexes + constraints. |
| `06-api-contract.md` | Every endpoint with request/response schemas. |
| `07-job-lifecycle.md` | State machine, transitions, resume rules. |
| `08-prompt-spec.md` | System prompt, few-shots, Anthropic tool schema. |
| `09-csv-spec.md` | Input parsing + output formatting rules. |
| `09b-clustering.md` | The clustering algorithm in detail. |
| `10-ui-spec.md` | Pages, components, states, interactions. |
| `11-design-system.md` | Color, type, spacing, primitives. |
| `12-security.md` | Auth, secrets, rate limits, CSRF. |
| `13-cost-model.md` | Pricing, estimation, cap enforcement. |
| `14-observability.md` | Logs, errors, health endpoint. |
| `15-docs-content.md` | In-app Docs page outline + mermaid list. |
| `16-out-of-scope.md` | Explicit non-goals. |
| `17-open-questions.md` | Remaining ambiguities. |
| `18-reliability-contract.md` | The row-count invariant and its enforcement. |

## How to read this spec

`00` and `01` first, then `03` (requirements) and `18` (reliability contract) together — those are the load-bearing documents. `05`, `06`, `07`, `08`, `09`, `09b` are implementation-detail for the backend. `10`, `11`, `15` for the frontend. Everything else is reference.

`solution-overview.md` at the repo root is the visual companion (13 mermaid diagrams); every diagram there is authoritative and this spec directory must stay in sync with it.
