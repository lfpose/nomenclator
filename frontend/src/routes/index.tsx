/**
 * Tool page (/) — workspace layout.
 * Left column: setup (input + config). Right column: results / status.
 * No page-level scroll; each column scrolls internally if needed.
 */

import { useEffect, useState } from "react";
import { useToolForm } from "@/hooks/useToolForm";
import { jobsApi } from "@/lib/jobs-api";
import { DEFAULT_SYSTEM_PROMPT, DEFAULT_FEW_SHOTS } from "@/lib/defaults";
import { InputArea } from "@/components/InputArea";
import { RowSubsetSelector } from "@/components/RowSubsetSelector";
import { TaxonomyInput } from "@/components/TaxonomyInput";
import { PromptReviewPanel } from "@/components/PromptReviewPanel";
import { AdvancedPanel } from "@/components/AdvancedPanel";
import { JobStatusPanel } from "@/components/JobStatusPanel";
import { HistoryList } from "@/components/HistoryList";
import { ClusterPreview } from "@/components/ClusterPreview";
import { StepIndicator } from "@/components/StepIndicator";
import { ErrorModal, type ErrorDetails } from "@/components/ErrorModal";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  FileText,
  RefreshCw,
  X,
} from "lucide-react";

export default function IndexRoute() {
  const {
    state,
    loadInput,
    startPreview,
    previewSuccess,
    previewFailed,
    startRecluster,
    reclusterSuccess,
    startCommit,
    commitSuccess,
    pollFailed,
    pollCancelled,
    reset,
    setRowSubsetMode,
    setRowSubsetN,
    setDryRun,
  } = useToolForm();

  const [threshold, setThreshold] = useState(80);
  const [titlesPerRequest, setTitlesPerRequest] = useState(25);
  const [seedTitles, setSeedTitles] = useState("");
  const [taxonomy, setTaxonomy] = useState("");
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [fewShots, setFewShots] = useState(DEFAULT_FEW_SHOTS);
  const [lastError, setLastError] = useState<ErrorDetails | null>(null);
  const [errorOpen, setErrorOpen] = useState(false);
  const showError = (details: ErrorDetails) => {
    setLastError(details);
    setErrorOpen(true);
  };

  const [jobs, setJobs] = useState<
    ReturnType<typeof jobsApi.list> extends Promise<infer T> ? T : { jobs: [] }
  >({ jobs: [] });

  // Section open/closed state
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [promptOpen, setPromptOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    jobsApi.list().then(setJobs).catch(console.error);
  }, []);

  const handleInputLoad = (input: { file?: File; text?: string }) => {
    loadInput(input);
  };

  const handlePreview = async () => {
    if (state.toolState.kind !== "input_loaded") return;
    startPreview();
    try {
      const formData = new FormData();
      if (state.toolState.input.file) formData.append("file", state.toolState.input.file);
      if (state.toolState.input.text) formData.append("text", state.toolState.input.text);
      formData.append("threshold", threshold.toString());
      formData.append("titles_per_request", titlesPerRequest.toString());
      formData.append("row_subset_mode", state.row_subset_mode);
      if (state.row_subset_n !== null) {
        formData.append("row_subset_n", state.row_subset_n.toString());
      }
      if (seedTitles.trim()) {
        formData.append("canonical_titles_text", seedTitles);
      }
      const preview = await jobsApi.preview(formData);
      previewSuccess(preview);
      setSettingsOpen(false);
      setLastError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to preview";
      previewFailed(msg);
      showError({ title: "Preview failed", context: "POST /jobs/preview", error: err });
    }
  };

  const handleRecluster = async (newThreshold: number) => {
    if (state.toolState.kind !== "previewed") return;
    startRecluster();
    try {
      const parsedSeeds = seedTitles.split("\n").map(s => s.trim()).filter(Boolean);
      const result = await jobsApi.recluster(
        state.toolState.preview.job_id,
        newThreshold,
        parsedSeeds.length ? parsedSeeds : undefined,
      );
      setThreshold(newThreshold);
      reclusterSuccess(result);
      setLastError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to recluster";
      pollFailed(state.toolState.preview.job_id, msg);
      showError({ title: "Re-cluster failed", context: "POST /jobs/{id}/recluster", error: err });
    }
  };

  const handleCommit = async () => {
    if (state.toolState.kind !== "previewed") return;
    startCommit();
    try {
      const promptOverride =
        systemPrompt !== DEFAULT_SYSTEM_PROMPT ? systemPrompt : undefined;
      const response = await jobsApi.commit(state.toolState.preview.job_id, {
        prompt_override: promptOverride,
        taxonomy: taxonomy || undefined,
        titles_per_request: titlesPerRequest,
        is_dry_run: state.is_dry_run,
      });
      commitSuccess(response.job_id);
    } catch (err) {
      const error = err as { code?: string; message?: string };
      const msg = error.message || "Failed to submit job";
      pollFailed(state.toolState.preview.job_id, msg);
      showError({ title: "Submit failed", context: "POST /jobs/{id}/commit", error: err });
    }
  };

  const handleCancel = () => {
    if (state.toolState.kind !== "running") return;
    pollCancelled(state.toolState.jobId);
  };

  const handleReset = () => reset();

  const k = state.toolState.kind;
  const hasInput = k !== "idle";
  const inputFile =
    k === "input_loaded" && state.toolState.input.file
      ? state.toolState.input.file
      : null;
  const inputText =
    k === "input_loaded" && state.toolState.input.text
      ? state.toolState.input.text
      : null;

  // Compact chip for the input once loaded (also visible during preview/run states
  // that don't carry the input anymore — show "input set" instead).
  const showInputChip =
    k === "previewing" ||
    k === "previewed" ||
    k === "reclustering" ||
    k === "submitting" ||
    k === "running";

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
      <StepIndicator toolState={state.toolState} />

      <div className="flex-1 min-h-0 flex">
        {/* LEFT — setup */}
        <aside className="w-[420px] flex-shrink-0 border-r flex flex-col overflow-hidden">
          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
            {/* Input section */}
            <section data-testid="section-input" className="space-y-2">
              <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                1 · Input
              </h2>
              {showInputChip ? (
                <Card className="px-3 py-2 flex items-center gap-2 text-sm">
                  <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <span className="flex-1 truncate font-medium">Input loaded</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleReset}
                    data-testid="btn-reset-input"
                    title="Start over with new input"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </Card>
              ) : hasInput && (inputFile || inputText) ? (
                <Card className="px-3 py-2 flex items-center gap-2 text-sm">
                  <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <span
                    className="flex-1 truncate font-medium"
                    title={inputFile?.name || "pasted text"}
                  >
                    {inputFile?.name ||
                      `pasted text · ${
                        (inputText || "").split("\n").filter(Boolean).length
                      } lines`}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => loadInput({})}
                    aria-label="Remove input"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </Card>
              ) : (
                <InputArea onInput={handleInputLoad} />
              )}
            </section>

            {/* Settings collapsible */}
            <section data-testid="section-settings" className="space-y-2">
              <Collapsible open={settingsOpen} onOpenChange={setSettingsOpen}>
                <CollapsibleTrigger className="w-full flex items-center justify-between text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
                    <span>2 · Settings</span>
                    {settingsOpen ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-4 pt-3">
                  <RowSubsetSelector
                    mode={state.row_subset_mode}
                    n={state.row_subset_n}
                    onModeChange={setRowSubsetMode}
                    onNChange={setRowSubsetN}
                  />
                  <TaxonomyInput
                    value={seedTitles}
                    onChange={setSeedTitles}
                    label="Seed titles (optional)"
                    id="seed-titles"
                    placeholder={"Software Engineer\nSales Manager\nData Analyst\nHR Business Partner\nFinancial Controller"}
                    rows={5}
                  />
                  <TaxonomyInput
                    value={taxonomy}
                    onChange={setTaxonomy}
                    label="Allowed categories (optional)"
                    id="taxonomy"
                    rows={3}
                  />
                  <AdvancedPanel
                    threshold={threshold}
                    onThresholdChange={setThreshold}
                    titlesPerRequest={titlesPerRequest}
                    onTitlesPerRequestChange={setTitlesPerRequest}
                    isDryRun={state.is_dry_run}
                    onDryRunChange={setDryRun}
                  />
                </CollapsibleContent>
              </Collapsible>
            </section>

            {/* Prompt collapsible (rarely touched) */}
            <section className="space-y-2">
              <Collapsible open={promptOpen} onOpenChange={setPromptOpen}>
                <CollapsibleTrigger className="w-full flex items-center justify-between text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
                    <span>3 · Prompt</span>
                    {promptOpen ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-4 pt-3">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="system-prompt" className="text-sm">
                        System prompt
                      </Label>
                      {systemPrompt !== DEFAULT_SYSTEM_PROMPT && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSystemPrompt(DEFAULT_SYSTEM_PROMPT)}
                        >
                          Reset
                        </Button>
                      )}
                    </div>
                    <Textarea
                      id="system-prompt"
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      rows={6}
                      className="font-mono text-xs max-h-40 overflow-y-auto"
                      style={{ fieldSizing: "fixed" } as React.CSSProperties}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="few-shots" className="text-sm">
                        Few-shot examples
                      </Label>
                      {fewShots !== DEFAULT_FEW_SHOTS && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setFewShots(DEFAULT_FEW_SHOTS)}
                        >
                          Reset
                        </Button>
                      )}
                    </div>
                    <Textarea
                      id="few-shots"
                      value={fewShots}
                      onChange={(e) => setFewShots(e.target.value)}
                      rows={6}
                      className="font-mono text-xs max-h-40 overflow-y-auto"
                      style={{ fieldSizing: "fixed" } as React.CSSProperties}
                    />
                  </div>
                  <PromptReviewPanel prompt={systemPrompt} fewShots={fewShots} />
                </CollapsibleContent>
              </Collapsible>
            </section>
          </div>

          {/* Sticky action bar */}
          <div className="border-t p-3 flex-shrink-0 bg-background space-y-2">
            {lastError && (
              <button
                type="button"
                role="alert"
                onClick={() => setErrorOpen(true)}
                className="w-full rounded-md border border-destructive bg-destructive/10 p-2 text-xs text-destructive flex items-start gap-2 hover:bg-destructive/15 text-left"
                data-testid="error-banner"
                title="Click to see full error"
              >
                <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                <span className="flex-1 truncate">{bannerText(lastError)}</span>
                <span className="text-xs underline shrink-0">details</span>
              </button>
            )}
            {(k === "idle" ||
              k === "input_loaded" ||
              k === "previewing" ||
              k === "previewed" ||
              k === "reclustering") && (
              <Button
                className="w-full"
                onClick={handlePreview}
                disabled={k !== "input_loaded"}
                data-testid="btn-preview"
              >
                {k === "previewing" || k === "reclustering" ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    {k === "reclustering" ? "Re-clustering..." : "Previewing..."}
                  </>
                ) : k === "previewed" ? (
                  "Re-preview"
                ) : (
                  "Preview clusters"
                )}
              </Button>
            )}
            {(k === "running" || k === "completed" || k === "failed" || k === "cancelled") && (
              <Button
                className="w-full"
                variant="outline"
                onClick={handleReset}
                data-testid="btn-start-over"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Start over
              </Button>
            )}
          </div>
        </aside>

        {/* RIGHT — results / status */}
        <section className="flex-1 min-w-0 flex flex-col overflow-hidden">
          <div className="flex-1 min-h-0 p-4 flex flex-col overflow-hidden">
            {(k === "idle" || k === "input_loaded") && (
              <EmptyState
                title={k === "idle" ? "Upload a CSV to start" : "Ready to preview"}
                subtitle={
                  k === "idle"
                    ? "Drop a file or paste titles on the left."
                    : "Click 'Preview clusters' to see how titles will be grouped."
                }
              />
            )}

            {k === "previewing" && (
              <EmptyState
                title="Clustering..."
                subtitle="Computing fuzzy matches against the threshold."
                loading
              />
            )}

            {k === "submitting" && (
              <EmptyState
                title="Submitting job..."
                subtitle="Queueing the LLM batch."
                loading
              />
            )}

            {(k === "previewed" || k === "reclustering") && (
              <ClusterPreview
                preview={state.toolState.preview}
                threshold={threshold}
                onRecluster={() => handleRecluster(threshold)}
                onSubmit={handleCommit}
                reclustering={k === "reclustering"}
              />
            )}

            {(k === "running" || k === "completed") && (
              <JobStatusPanel jobId={state.toolState.jobId} onCancel={handleCancel} />
            )}

            {k === "failed" && (
              <Card className="p-6 border-destructive">
                <div className="flex items-start gap-4">
                  <AlertCircle className="h-6 w-6 text-destructive flex-shrink-0 mt-0.5" />
                  <div className="flex-1 space-y-3">
                    <div>
                      <h3 className="font-medium text-destructive">Job failed</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        {state.toolState.message}
                      </p>
                    </div>
                    <Button variant="outline" onClick={handleReset}>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Retry
                    </Button>
                  </div>
                </div>
              </Card>
            )}

            {k === "cancelled" && (
              <Card className="p-6">
                <div className="space-y-3">
                  <h3 className="font-medium">Job cancelled</h3>
                  <p className="text-sm text-muted-foreground">
                    Start over with a new upload.
                  </p>
                  <Button variant="outline" onClick={handleReset}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Start over
                  </Button>
                </div>
              </Card>
            )}
          </div>

          {/* History drawer */}
          <Collapsible
            open={historyOpen}
            onOpenChange={setHistoryOpen}
            className="border-t flex-shrink-0"
          >
            <CollapsibleTrigger
              data-testid="toggle-history"
              className="w-full flex items-center justify-between px-4 py-2 text-sm hover:bg-muted/40"
            >
                <span className="font-medium">
                  History{" "}
                  <span className="text-muted-foreground">({jobs.jobs?.length || 0})</span>
                </span>
                {historyOpen ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="max-h-64 overflow-y-auto p-4 border-t bg-muted/20">
                <HistoryList jobs={jobs.jobs} />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </section>
      </div>

      <ErrorModal
        open={errorOpen}
        onClose={() => setErrorOpen(false)}
        details={lastError}
      />
    </div>
  );
}

function bannerText(d: ErrorDetails): string {
  const e = d.error;
  // Prefer the dev-mode exception_message surfaced by the backend.
  const apiDetails =
    e && typeof e === "object" && "details" in e
      ? ((e as { details?: Record<string, unknown> }).details ?? null)
      : null;
  const excMsg = apiDetails?.exception_message as string | undefined;
  if (excMsg) return excMsg;
  if (e instanceof Error) return e.message;
  return String(e);
}

function EmptyState({
  title,
  subtitle,
  loading = false,
}: {
  title: string;
  subtitle: string;
  loading?: boolean;
}) {
  return (
    <div
      className="h-full flex items-center justify-center"
      data-testid="empty-state"
    >
      <div className="text-center space-y-2 max-w-sm">
        {loading && (
          <RefreshCw className="h-8 w-8 mx-auto text-muted-foreground animate-spin" />
        )}
        <h2 className="text-lg font-medium">{title}</h2>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>
    </div>
  );
}
