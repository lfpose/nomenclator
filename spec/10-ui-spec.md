# 10 — UI Spec

Reference: diagrams 2 (page map) and 5 (sequence) in `solution-overview.md`.

## Routes

TanStack Router, three routes:

- `/` — Tool (default landing after login)
- `/about` — About
- `/docs` — Docs / Guide

A root layout wraps all three with a header, the theme toggle, a small nav, and a footer.

## Auth gate

A `beforeLoad` hook on the root layout checks session validity via `GET /me`. If 401, redirect to an inline password form (not a separate route — just a state the root layout can render). After a successful `POST /auth`, reload to the target route.

## Tool page — `/`

The entire page is a single form plus a job history panel. No wizard, no modals for the form itself. Single column, max-width ~860px, generous whitespace.

### Layout (top to bottom)

1. **Title** — "Nomenclator" in serif display, subtitle "Standardize messy job titles into canonical Spanish forms."
2. **Upload area** — a large drop zone accepting CSV + a small "or paste titles" disclosure that expands into a textarea.
2a. **Row subset selector** — A group with: a `<Select>` dropdown ("All rows" / "First N" / "Random sample"), a number input for N (shown when not "All rows"), and a small toggle between "First N" and "Random sample". Default is "All rows".
3. **Taxonomy textarea** — labeled "Allowed categories (one per line)", with a placeholder showing the default set. Optional.
3a. **Prompt & examples area** — Two fields: the system prompt `<Textarea>` (pre-filled with default, editable) and the few-shot examples `<Textarea>` (pre-filled, editable as JSON or plain text). Below them: a "Review Prompt" `<Button>` (secondary style). When clicked, shows a review `<Card>` with the AI's assessment (safe/issues/suggestions). The button text changes to "Re-review" after first use.
4. **Advanced disclosure** — collapsed by default. Contains:
   - Threshold `<Slider>`, 50–100, default 90, with a live value and a helper text explaining the tradeoff. Tooltip: "Controls how similar two titles must be to merge into one cluster. Higher = stricter (fewer merges). Default 90 works well for most Spanish job title datasets."
   - `titles_per_request` `<Input>` (number), 1–50, default 25. Tooltip: "How many titles to bundle into each AI request. Higher = cheaper but less reliable. Default 25 is the sweet spot."
   - Prompt override `<Textarea>`, initially empty, with a "Reset to default" button.
   - **Dry-run toggle** — a `<Switch>` component labeled "Dry run (no API cost)" with a `<Tooltip>` explaining it returns fake results for testing.
5. **Preview button** — primary. Disabled until an input is present. Text: "Preview clusters".
6. **Preview result panel** — hidden until preview runs. Shows:
   - The counts row: `13,600 → 8,142 uniques → 2,618 clusters · est $0.24`.
   - A warning badge if any cluster has > 50 members.
   - A table of the top 10 largest clusters (collapsible rows showing members).
   - A "Re-cluster" button (replaces Preview when in preview state).
   - A "Submit job" button — primary. This is the commit action.
7. **Job status panel** — replaces the preview panel once a job is committed. Shows:
   - Current state, retry round, rolling progress (resolved / total clusters).
   - A live timer since submit.
   - A "Cancel" button.
   - A "Download CSV" button that appears only when state == `completed`.
8. **History panel** — below the form. A reverse-chronological list of past jobs. Each row: date, status badge, counts, cost, download button (for completed jobs). Click a row to expand details (batches, error breakdown).

### States

The form can be in one of these states:

- `idle` — no input, everything disabled except uploads.
- `input_loaded` — input present, preview button enabled.
- `previewing` — spinner on the preview button, form locked.
- `previewed` — preview panel visible, operator can re-cluster or submit.
- `reclustering` — small spinner on the re-cluster button, table greyed.
- `reviewing_prompt` — spinner on review button, rest of form accessible.
- `submitting` — spinner on submit, form locked.
- `running` — status panel visible, job in non-terminal state.
- `completed` — download button prominent.
- `failed` — error message + "Retry job" button.
- `cancelled` — message + "Start over" button.

Exactly one of these is active at any time; state transitions are driven by response codes and `/jobs/:id` polling.

### Polling

Once a job is `submitted` or later, the page polls `GET /jobs/:id` every **5 seconds** until the status is terminal. Polling uses `setInterval` in a React effect with cleanup.

### Notifications

- On first successful commit, request Notification API permission.
- On transition from non-terminal → terminal while the tab is visible, fire a `new Notification("Nomenclator — job completed", { body: "..." })`.
- Gracefully no-op if permission is denied.

## About page — `/about`

Static content. Two short paragraphs. Roughly:

> **nomenclator** — _n. Latin, from_ nōmen _(name)_ + _-clātor, from_ clāmāre _(to call)_.
>
> In ancient Rome a nomenclator was the servant who walked half a step behind a magistrate and whispered the right name for every face he met, so no citizen ever felt unseen. This tool does a narrower version of the same job: it listens to your messy catalogue of job titles and whispers back the correct canonical name for each one.

That's it. No images. No links other than the site nav. Center the text, serif typeface, wide line-height, breathing room above and below.

## Docs page — `/docs`

Content-heavy, long scroll, anchor links in a sticky sidebar. Sections:

1. **What this does** — one paragraph.
2. **How to use it** — the happy-path workflow, walking through upload → preview → submit → download with screenshots (or stylized illustrations in v1 if screenshots aren't ready).
3. **How it works under the hood** — embedded mermaid diagrams from `solution-overview.md` (subset listed in `15-docs-content.md`).
4. **Error codes** — table of every error code and what it means.
5. **Costs and limits** — brief explanation of the $20 cap and why it exists.
6. **FAQ** — 6–8 likely questions (e.g. "Why does my file need a header?", "Can I run two jobs at once?", "What happens if I close the tab?").

Mermaid is rendered client-side via `mermaid` npm package, lazily loaded on the docs route only (split chunk).

## Header and nav

- Logo-ish wordmark "nomenclator" on the left.
- Three nav links: Tool, About, Docs.
- Theme toggle on the right (sun / moon icon).
- Logout button on the far right.
- Sticky on scroll, slight backdrop blur.

## Footer

One line, small type: "Nomenclator · v1.0 · built for a single operator · _quis custodiet ipsos custodes?_" (humor optional, confirm with operator).

## Empty / loading / error states

- Empty upload area: icon + "Drop a CSV here or click to browse".
- Loading: subtle skeleton for the preview table, spinner button text change.
- Error: `role="alert"` red-on-red banner with the error code and the human message.

## Interactions to specify explicitly

- **Drop zone** accepts drag-and-drop AND click-to-browse.
- **Threshold slider** re-clusters on mouseup, not on every move (debounced 200ms also fine).
- **Top clusters table** rows expand on click to reveal all members.
- **Job status panel** never reloads the whole page; all updates come from polling.
- **History row click** expands inline, not a new page.

## Component references (shadcn/ui)

| Component | shadcn/ui name | Notes |
|---|---|---|
| Button | `<Button>` | variants: default, secondary, ghost, destructive, outline |
| Input | `<Input>` | text and number inputs |
| Textarea | `<Textarea>` | prompt and taxonomy fields |
| Slider | `<Slider>` | threshold range slider |
| Card | `<Card>` | preview result, review result, status containers |
| Badge | `<Badge>` | job state, cluster warnings |
| Dialog | `<Dialog>` | cancel job confirmation |
| Table | `<Table>` | clusters list and job history |
| Switch | `<Switch>` | dry-run toggle (new) |
| Tooltip | `<Tooltip>` | parameter explanations (new) |
| Select | `<Select>` | row subset mode picker (new) |
| Collapsible | `<Collapsible>` | replaces custom Disclosure for Advanced section |
| DropZone | custom component | no shadcn equivalent, styled with Tailwind |
| Spinner | custom component | simple Tailwind animation |

All interactive components come from shadcn/ui, which wraps Radix primitives with Tailwind-styled defaults. Custom components (DropZone, Spinner) are styled with Tailwind classes directly.
