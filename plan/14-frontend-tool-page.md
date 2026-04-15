# 14 — Frontend Tool Page

Reference: `spec/10-ui-spec.md`. All tests use `vitest` + `@testing-library/react` with `msw` for API mocking.

---

### P14-01 — API client functions for jobs

**Deps:** P13-03, P10-13
**Files:** `frontend/src/lib/jobs-api.ts`, `frontend/tests/jobs-api.test.ts`
**Goal:** Typed wrappers around every `/jobs*` and `/spend` endpoint.

**Implementation:**
```ts
import { api } from "./api";

export type ReviewResponse = {
  safe: boolean;
  quality_score: string;
  issues: string[];
  suggestions: string[];
  summary: string;
};

export type PreviewResponse = {
  job_id: string;
  total_rows: number;
  exact_unique_rows: number;
  cluster_count: number;
  largest_cluster_size: number;
  est_cost_usd: number;
  top_clusters: Array<{ representative: string; member_count: number; members: string[] }>;
  warnings: Array<{ type: string; [k: string]: unknown }>;
};

export type JobSummary = {
  job_id: string;
  status: string;
  created_at: string;
  row_subset_mode?: string;
  row_subset_n?: number | null;
  is_dry_run?: boolean;
  is_partial?: boolean;
};

export type JobDetail = JobSummary & {
  total_rows: number;
  est_cost_usd: number;
  batches: Array<{ batch_id: string; status: string }>;
};

export const jobsApi = {
  reviewPrompt: (prompt: string, fewShots: string) =>
    api.post<ReviewResponse>("/jobs/review-prompt", { prompt, few_shots: fewShots }),
  preview: (form: FormData) => api.postForm<PreviewResponse>("/jobs/preview", form),
  recluster: (jobId: string, threshold: number) =>
    api.post<PreviewResponse>(`/jobs/${jobId}/recluster`, { threshold }),
  commit: (jobId: string, body: { prompt_override?: string; taxonomy?: string; titles_per_request?: number; is_dry_run?: boolean }) =>
    api.post<{ job_id: string; status: string }>(`/jobs/${jobId}/commit`, body),
  cancel: (jobId: string) => api.post(`/jobs/${jobId}/cancel`),
  list: () => api.get<{ jobs: JobSummary[] }>("/jobs"),
  get: (jobId: string) => api.get<JobDetail>(`/jobs/${jobId}`),
  downloadUrl: (jobId: string) => `/jobs/${jobId}/download`,
  spend: () => api.get<{ used_usd: number; cap_usd: number; reset_date: string | null }>("/spend"),
};
```

Note: the `preview` FormData should include `row_subset_mode` and `row_subset_n` fields when applicable.

**Test:** `cd frontend && pnpm test --run tests/jobs-api.test.ts`

Required assertions:
- `test("preview posts multipart", ...)`
- `test("commit sends JSON body", ...)`
- `test("list returns typed array", ...)`
- `test("get returns typed object", ...)`
- `test("downloadUrl returns /jobs/:id/download", ...)`
- `test("reviewPrompt sends prompt and few_shots", ...)`

**Done when:**
- [ ] All 6 pass.

---

### P14-02 — Form state hook

**Deps:** P13-04
**Files:** `frontend/src/hooks/useToolForm.ts`, `frontend/tests/use-tool-form.test.tsx`
**Goal:** Custom hook holding the entire Tool page's form state machine (see `spec/10-ui-spec.md` "States" list).

**Implementation:**
```ts
export type ToolState =
  | { kind: "idle" }
  | { kind: "input_loaded"; input: { file?: File; text?: string } }
  | { kind: "previewing" }
  | { kind: "previewed"; preview: PreviewResponse }
  | { kind: "reclustering"; preview: PreviewResponse }
  | { kind: "reviewing_prompt" }
  | { kind: "submitting" }
  | { kind: "running"; jobId: string }
  | { kind: "completed"; jobId: string; job: JobDetail }
  | { kind: "failed"; jobId: string; message: string }
  | { kind: "cancelled"; jobId: string };

// Form fields include:
//   row_subset_mode: "all" | "first_n" | "random_n"
//   row_subset_n: number | null
//   is_dry_run: boolean

export function useToolForm() { /* ... useReducer ... */ }
```

**Test:** `cd frontend && pnpm test --run tests/use-tool-form.test.tsx`

Required assertions:
- `test("idle → input_loaded on file set", ...)`
- `test("input_loaded → previewing → previewed on API success", ...)`
- `test("previewed → reclustering → previewed on threshold change", ...)`
- `test("previewed → submitting → running on commit", ...)`
- `test("running → completed when poll returns completed", ...)`
- `test("running → failed when poll returns failed", ...)`
- `test("reviewing_prompt state on review click", ...)`
- `test("row subset state tracked", ...)`
- `test("dry run toggle tracked", ...)`

**Done when:**
- [ ] All 9 pass.

---

### P14-03 — Upload + paste input component

**Deps:** P13-06
**Files:** `frontend/src/components/InputArea.tsx`, `frontend/tests/input-area.test.tsx`
**Goal:** Drop zone + paste disclosure, emits `{ file?, text? }`.

**Test:** `cd frontend && pnpm test --run tests/input-area.test.tsx`

Required assertions:
- `test("drop zone accepts dropped CSV file", ...)`
- `test("drop zone click opens file input", ...)`
- `test("paste textarea expands and accepts text", ...)`
- `test("emits input on file drop", ...)`
- `test("emits input on text change", ...)`

**Done when:**
- [ ] All 5 pass.

---

### P14-04 — Taxonomy textarea

**Deps:** P13-01
**Files:** `frontend/src/components/TaxonomyInput.tsx`, `frontend/tests/taxonomy.test.tsx`
**Goal:** Controlled textarea (shadcn `<Textarea>`) with placeholder, label, optional state.

**Test:** `cd frontend && pnpm test --run tests/taxonomy.test.tsx`

Required assertions:
- `test("renders with default placeholder", ...)`
- `test("accepts multiline input", ...)`
- `test("emits change events", ...)`

**Done when:**
- [ ] All 3 pass.

---

### P14-05 — Advanced disclosure

**Deps:** P13-01
**Files:** `frontend/src/components/AdvancedPanel.tsx`, `frontend/tests/advanced-panel.test.tsx`
**Goal:** Collapsible panel (shadcn `<Collapsible>`) with threshold slider, titles_per_request input, prompt override textarea + reset button, and dry-run toggle. Threshold and titles_per_request have tooltips.

**Implementation:**
- Uses shadcn `<Collapsible>` instead of a custom Disclosure component.
- Add shadcn `<Switch>` for dry-run toggle with label and tooltip (see P14-17).
- Add shadcn `<Tooltip>` for threshold slider and titles_per_request (see P14-18).
- Threshold tooltip: "Controls how similar two titles must be to merge into one cluster. Higher = stricter (fewer merges). Default 90 works well for most Spanish job title datasets."
- Titles per request tooltip: "How many titles to bundle into each AI request. Higher = cheaper but less reliable. Default 25 is the sweet spot."

**Test:** `cd frontend && pnpm test --run tests/advanced-panel.test.tsx`

Required assertions:
- `test("starts collapsed", ...)`
- `test("expands on click", ...)`
- `test("threshold slider changes value", ...)`
- `test("titles_per_request input validates 1-50", ...)`
- `test("prompt override reset clears textarea", ...)`
- `test("dry run switch is present in advanced panel", ...)`
- `test("threshold tooltip text is present", ...)`
- `test("titles per request tooltip text is present", ...)`

**Done when:**
- [ ] All 8 pass.

---

### P14-06 — Preview button + preview panel

**Deps:** P14-01, P14-02, P14-03, P14-04, P14-05
**Files:** `frontend/src/components/PreviewPanel.tsx`, `frontend/tests/preview-panel.test.tsx`
**Goal:** Button that calls `/jobs/preview`; on success shows counts, est cost, top clusters table, and a "Re-cluster" button. Includes row subset selector in the form. Preview panel shows both "total rows" and "selected rows" for partial runs.

**Implementation:**
- Preview form sends `row_subset_mode` and `row_subset_n` in the FormData.
- When `is_partial` is true on the response, the panel shows both a "total rows" count and a "selected rows" count.

**Test:** `cd frontend && pnpm test --run tests/preview-panel.test.tsx`

Required assertions:
- `test("button disabled until input is present", ...)`
- `test("shows counts and est cost after preview", ...)`
- `test("shows top 10 largest clusters", ...)`
- `test("large cluster warning badge shown when warnings present", ...)`
- `test("re-cluster calls API with new threshold", ...)`
- `test("shows API error on preview failure", ...)`
- `test("shows selected rows count for partial runs", ...)`

**Done when:**
- [ ] All 7 pass.

---

### P14-07 — Top clusters table

**Deps:** P13-01
**Files:** `frontend/src/components/TopClustersTable.tsx`, `frontend/tests/top-clusters.test.tsx`
**Goal:** Table rows expandable on click to show members.

**Test:** `cd frontend && pnpm test --run tests/top-clusters.test.tsx`

Required assertions:
- `test("renders one row per cluster", ...)`
- `test("members hidden by default", ...)`
- `test("click expands members list", ...)`
- `test("shows member count", ...)`

**Done when:**
- [ ] All 4 pass.

---

### P14-08 — Submit button → commit

**Deps:** P14-06
**Files:** `frontend/src/components/SubmitButton.tsx`, `frontend/tests/submit-commit.test.tsx`
**Goal:** Button that calls `/jobs/:id/commit` and transitions form state to `running`. Passes `is_dry_run` from form state.

**Implementation:** Commit call body includes `is_dry_run` field pulled from form state.

**Test:** `cd frontend && pnpm test --run tests/submit-commit.test.tsx`

Required assertions:
- `test("calls commit with prompt and taxonomy", ...)`
- `test("transitions to running state on 202", ...)`
- `test("shows spend_cap_exceeded error with reset date", ...)`
- `test("shows job_already_running error", ...)`
- `test("sends is_dry_run when toggle is on", ...)`

**Done when:**
- [ ] All 5 pass.

---

### P14-09 — Job status panel with polling

**Deps:** P14-01, P14-08
**Files:** `frontend/src/components/JobStatusPanel.tsx`, `frontend/src/hooks/useJobPolling.ts`, `frontend/tests/job-status.test.tsx`
**Goal:** Panel showing live status, progress, retry_round, cancel button, download button. Polls every 5s while non-terminal.

**Test:** `cd frontend && pnpm test --run tests/job-status.test.tsx`

Required assertions (use `vi.useFakeTimers()`):
- `test("polls /jobs/:id every 5s while running", ...)`
- `test("stops polling when terminal status reached", ...)`
- `test("shows retry_round in UI when > 0", ...)`
- `test("download button appears on completed", ...)`
- `test("cancel button disappears on terminal", ...)`

**Done when:**
- [ ] All 5 pass.

---

### P14-10 — Notifications integration

**Deps:** P14-09
**Files:** `frontend/src/hooks/useNotification.ts`, `frontend/tests/notification.test.tsx`
**Goal:** Request permission on first commit; fire Notification on terminal transition.

**Test:** `cd frontend && pnpm test --run tests/notification.test.tsx`

Required assertions (mock `window.Notification`):
- `test("requests permission on first commit", ...)`
- `test("fires notification on job complete", ...)`
- `test("no-op if permission denied", ...)`
- `test("does not request permission before commit", ...)`

**Done when:**
- [ ] All 4 pass.

---

### P14-11 — Cancel action

**Deps:** P14-09
**Files:** `frontend/src/components/JobStatusPanel.tsx` (extend), `frontend/tests/cancel-action.test.tsx`
**Goal:** Cancel button → `POST /jobs/:id/cancel` → confirmation dialog → UI transitions to `cancelled`.

**Test:** `cd frontend && pnpm test --run tests/cancel-action.test.tsx`

Required assertions:
- `test("confirm dialog shown before cancel", ...)`
- `test("cancel API called on confirm", ...)`
- `test("cancel not called on dismiss", ...)`
- `test("UI shows cancelled state after success", ...)`

**Done when:**
- [ ] All 4 pass.

---

### P14-12 — Download button

**Deps:** P14-09
**Files:** `frontend/src/components/DownloadButton.tsx`, `frontend/tests/download.test.tsx`
**Goal:** Download button triggers browser download via link to `/jobs/:id/download`.

**Test:** `cd frontend && pnpm test --run tests/download.test.tsx`

Required assertions:
- `test("button href is /jobs/:id/download", ...)`
- `test("button hidden when not completed", ...)`
- `test("button has download attribute", ...)`

**Done when:**
- [ ] All 3 pass.

---

### P14-13 — History list

**Deps:** P14-01
**Files:** `frontend/src/components/HistoryList.tsx`, `frontend/tests/history.test.tsx`
**Goal:** Reverse-chronological job list below the form, with expandable details. Shows "Dry run" badge for dry-run jobs and "Partial" badge for partial-run jobs.

**Test:** `cd frontend && pnpm test --run tests/history.test.tsx`

Required assertions:
- `test("renders jobs newest first", ...)`
- `test("shows status badge per job", ...)`
- `test("shows row count and cost", ...)`
- `test("expands row to show batches on click", ...)`
- `test("download link present for completed jobs only", ...)`
- `test("shows dry run badge", ...)`
- `test("shows partial badge", ...)`

**Done when:**
- [ ] All 7 pass.

---

### P14-14 — Tool page assembly

**Deps:** P14-02..P14-13
**Files:** `frontend/src/routes/index.tsx` (replaces placeholder), `frontend/tests/tool-page.test.tsx`
**Goal:** Stitch all the components together into the Tool page with the state machine driving which panels are visible.

**Test:** `cd frontend && pnpm test --run tests/tool-page.test.tsx`

Required assertions:
- `test("shows only form in idle state", ...)`
- `test("shows preview panel after preview success", ...)`
- `test("shows status panel after commit", ...)`
- `test("shows history below form at all times", ...)`
- `test("shows spend footer", ...)`

**Done when:**
- [ ] All 5 pass.
- [ ] `pnpm build` still succeeds.
- [ ] `pnpm tsc --noEmit` exits 0.

---

### P14-15 — Prompt review UI

**Deps:** P14-01, P14-02
**Files:** `frontend/src/components/PromptReviewPanel.tsx`, `frontend/tests/prompt-review.test.tsx`
**Goal:** "Review Prompt" button that calls the review endpoint and shows results in a card.

**Implementation:**
- Uses shadcn `<Button>` variant="secondary", `<Card>`, `<Badge>` for quality score.
- Shows: summary text, issues as a bulleted list, suggestions as a bulleted list.
- "Safe" indicator: green badge if safe, red destructive badge if not.
- Button text changes to "Re-review" after first use.
- Loading state shows `<Spinner>`.

**Test:** `cd frontend && pnpm test --run tests/prompt-review.test.tsx`

Required assertions:
- `test("button calls review API with prompt and few_shots", ...)`
- `test("shows review card on success", ...)`
- `test("shows quality score badge", ...)`
- `test("shows issues list", ...)`
- `test("shows suggestions list", ...)`
- `test("button text changes to Re-review after first use", ...)`
- `test("shows error on API failure without blocking", ...)`

**Done when:**
- [ ] All 7 pass.

---

### P14-16 — Row subset selector

**Deps:** P14-02
**Files:** `frontend/src/components/RowSubsetSelector.tsx`, `frontend/tests/row-subset.test.tsx`
**Goal:** A group with a Select dropdown and a number input for N.

**Implementation:**
- Uses shadcn `<Select>` with options: "All rows", "First N rows", "Random sample of N rows".
- When not "All", shows a number `<Input>` for N.
- Emits `{ mode: string, n: number | null }` on change.

**Test:** `cd frontend && pnpm test --run tests/row-subset.test.tsx`

Required assertions:
- `test("defaults to All rows", ...)`
- `test("shows N input when First N selected", ...)`
- `test("shows N input when Random sample selected", ...)`
- `test("hides N input when All selected", ...)`
- `test("emits mode and n on change", ...)`

**Done when:**
- [ ] All 5 pass.

---

### P14-17 — Dry-run toggle

**Deps:** P14-05
**Files:** `frontend/src/components/DryRunToggle.tsx`, `frontend/tests/dry-run-toggle.test.tsx`
**Goal:** A Switch + label + tooltip for dry-run mode, inside the Advanced section.

**Implementation:**
- Uses shadcn `<Switch>`, `<Label>`, `<Tooltip>`.
- Label: "Dry run (no API cost)".
- Tooltip: "Run the full pipeline with fake results instead of calling the AI. Useful for testing that your CSV uploads correctly. Costs nothing."

**Test:** `cd frontend && pnpm test --run tests/dry-run-toggle.test.tsx`

Required assertions:
- `test("renders switch with label", ...)`
- `test("toggle changes checked state", ...)`
- `test("tooltip appears on hover", ...)`
- `test("emits value on change", ...)`

**Done when:**
- [ ] All 4 pass.

---

### P14-18 — Parameter tooltips

**Deps:** P14-05
**Files:** `frontend/src/components/AdvancedPanel.tsx` (extend), `frontend/tests/parameter-tooltips.test.tsx`
**Goal:** Add tooltips to the threshold slider and titles_per_request input.

**Implementation:**
- Wrap each label with a shadcn `<Tooltip>` containing the explanation text from the spec.
- Threshold: "Controls how similar two titles must be to merge into one cluster. Higher = stricter (fewer merges). Default 90 works well for most Spanish job title datasets."
- Titles per request: "How many titles to bundle into each AI request. Higher = cheaper but less reliable. Default 25 is the sweet spot."

**Test:** `cd frontend && pnpm test --run tests/parameter-tooltips.test.tsx`

Required assertions:
- `test("threshold tooltip shows explanation", ...)`
- `test("titles per request tooltip shows explanation", ...)`

**Done when:**
- [ ] Both pass.
