# 16 — Out of Scope

Everything on this page is intentionally not built in v1. Each item has a short reason. The list exists so future-you or a second developer doesn't waste time wondering "should I add this?" mid-implementation.

## Product scope

- **Multiple task templates.** V1 ships with exactly one: `job_titles_es`. The `task_templates` table is the seam for v2 additions; do not build a template picker or a second template in v1.
- **User-defined output columns.** The four-column output is fixed for the job-title task. V3 unlocks this; v1 does not.
- **Blank-slate prompt authoring.** Operators can override the default prompt, but the UI does not offer a "start from scratch" builder.
- **Non-Spanish output.** Spanish only. No language selector.
- **Tasks other than job titles.** No industry standardization, no company-name normalization, no city cleaning. All of that is v2.

## User and access

- **Multi-user accounts.** Single shared password. No per-user sessions, preferences, or ownership.
- **Role-based access.** There's one role: "the operator."
- **SSO / OAuth / magic links.** One password, done.
- **Admin panel.** There's nothing to administer. Tweak secrets via `fly secrets set`.
- **User management UI.** Not a thing here.
- **Password reset flow.** The password is a Fly secret. Change it by updating the secret and re-hashing.
- **Audit log of operator actions.** Logs are sufficient for v1.

## Notifications

- **Email notifications.** No SMTP integration. The Notification API + the Tool page's status panel are enough.
- **SMS / Telegram / Slack / Discord webhooks.** None. (Discord was discussed as a nice-to-have; deferred.)
- **In-app notification center.** The status panel and the history list cover this.

## Job lifecycle

- **Concurrent jobs.** V1 is single-concurrency. One job at a time.
- **Job queue visible to the operator.** No queue exists; there's always zero or one active job.
- **Scheduled / recurring jobs.** No cron, no "run every week."
- **Re-running a failed job with modified input.** Operator starts over from the form.
- **Partial re-runs** (only the stragglers from a completed job). The stragglers retry loop handles this automatically during the job; there's no manual "retry these rows" action.
- **Deleting a job from the UI.** Not exposed in v1. Data stays forever.

## Caching / performance

- **Cross-job caching.** Results are not carried over between runs. The operator said the task runs monthly and caching would add complexity for little benefit.
- **Embedding-based clustering.** We use string similarity (`token_set_ratio`). Sentence embeddings would be more powerful but heavier and unnecessary at this scale.
- **Approximate nearest neighbors** (ANN, FAISS, hnswlib). Not needed — all-vs-all at 8k uniques is fine.
- **Parallel worker processes.** One asyncio task in one process is enough.

## API and integrations

- **Public HTTP API for other tools.** The endpoints exist but are only documented for the SPA's use.
- **Webhooks out.** No outbound webhook on job completion.
- **Importing from Google Sheets / Airtable / HubSpot / Salesforce.** CSV only.
- **Exporting to anything other than CSV.** No JSON, no XLSX, no direct DB writes.
- **Command-line interface.** Web only.

## Frontend

- **Mobile / tablet UI.** Desktop only. Below 900px the page is usable but not optimized.
- **PWA installability.** Not configured.
- **Offline mode.** No service worker.
- **Localization of the UI.** English only.
- **Keyboard shortcuts beyond the defaults** (e.g. cmd-enter to submit). Nice-to-have; skip.
- **Drag-to-reorder taxonomy list.** The textarea is enough.
- **Rich preview of CSV before upload** (sortable table). Skip.

## Observability

- **Sentry / Datadog / any SaaS.** Fly logs only.
- **Metrics backend.** No Prometheus, no Grafana.
- **Alerts / on-call.** Tool is internal; downtime is non-critical.
- **Uptime SLA.** None.

## Testing and CI

- **End-to-end browser tests.** Skip for v1.
- **CI pipeline.** `fly deploy` from local is enough initially.
- **Staging environment.** One prod deploy.
- **Feature flags.** Not needed for a single-operator tool.

## Analytics

- **Plausible / Umami / GA.** None. The operator confirmed "truly none."

## Billing / payments

- **Stripe / subscription management.** It's a private tool.
- **Cost attribution per user.** One user.

## Deferred to v2 (explicit)

- Add a template picker UI.
- Seed `industries_es` and `companies_es` templates.
- Per-template form modules.
- Template switcher in the history list.
- Per-template cost dashboards.

## Deferred to v3 (explicit)

- Generic blank-slate task builder.
- Custom output column definition in the UI.
- Custom few-shot editor.
- Embedding-based clustering option.
