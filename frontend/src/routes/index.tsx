/**
 * Tool page (/)
 * Main page for uploading CSV files, previewing clusters, and submitting jobs
 */

import { useEffect, useState } from "react";
import { useToolForm } from "@/hooks/useToolForm";
import { jobsApi } from "@/lib/jobs-api";
import { InputArea } from "@/components/InputArea";
import { TaxonomyInput } from "@/components/TaxonomyInput";
import { AdvancedPanel } from "@/components/AdvancedPanel";
import { JobStatusPanel } from "@/components/JobStatusPanel";
import { HistoryList } from "@/components/HistoryList";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlertCircle, RefreshCw } from "lucide-react";

export default function IndexRoute() {
  const {
    state,
    loadInput,
    startPreview,
    previewSuccess,
    startRecluster,
    reclusterSuccess,
    startCommit,
    commitSuccess,
    pollFailed,
    pollCancelled,
    reset,
  } = useToolForm();

  // Local state for form parameters
  const [threshold, setThreshold] = useState(90);
  const [titlesPerRequest, setTitlesPerRequest] = useState(25);
  const [taxonomy, setTaxonomy] = useState("");
  const [promptOverride, setPromptOverride] = useState("");

  // Jobs history
  const [jobs, setJobs] = useState<ReturnType<typeof jobsApi.list> extends Promise<infer T> ? T : { jobs: [] }>({ jobs: [] });

  useEffect(() => {
    jobsApi.list().then(setJobs).catch(console.error);
  }, []);

  // Handle input load
  const handleInputLoad = (input: { file?: File; text?: string }) => {
    loadInput(input);
  };

  // Handle preview
  const handlePreview = async () => {
    if (state.toolState.kind !== "input_loaded") return;

    startPreview();
    try {
      const formData = new FormData();
      if (state.toolState.input.file) {
        formData.append("file", state.toolState.input.file);
      }
      if (state.toolState.input.text) {
        formData.append("text", state.toolState.input.text);
      }
      formData.append("threshold", threshold.toString());
      formData.append("titles_per_request", titlesPerRequest.toString());
      formData.append("row_subset_mode", state.row_subset_mode);
      if (state.row_subset_n !== null) {
        formData.append("row_subset_n", state.row_subset_n.toString());
      }

      const preview = await jobsApi.preview(formData);
      previewSuccess(preview);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to preview";
      pollFailed("", errorMessage);
    }
  };

  // Handle recluster
  const handleRecluster = async (newThreshold: number) => {
    if (state.toolState.kind !== "previewed") return;

    startRecluster();
    try {
      const result = await jobsApi.recluster(state.toolState.preview.job_id, newThreshold);
      setThreshold(newThreshold);
      reclusterSuccess(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to recluster";
      pollFailed(state.toolState.preview.job_id, errorMessage);
    }
  };

  // Handle commit
  const handleCommit = async () => {
    if (state.toolState.kind !== "previewed") return;

    startCommit();
    try {
      const response = await jobsApi.commit(state.toolState.preview.job_id, {
        prompt_override: promptOverride || undefined,
        taxonomy: taxonomy || undefined,
        titles_per_request: titlesPerRequest,
        is_dry_run: state.is_dry_run,
      });
      commitSuccess(response.job_id);
    } catch (err) {
      const error = err as { code?: string; message?: string; details?: { error?: { code?: string; reset_date?: string } } };
      const errorMessage = error.message || "Failed to submit job";
      void (error.details?.error?.code || error.code); // Acknowledge code but don't use it
      pollFailed(state.toolState.preview.job_id, errorMessage);
    }
  };

  // Handle cancel
  const handleCancel = () => {
    if (state.toolState.kind !== "running") return;
    pollCancelled(state.toolState.jobId);
  };

  // Handle retry
  const handleRetry = () => {
    reset();
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Main content */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-8 space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-serif">Nomenclator</h1>
          <p className="text-muted-foreground">
            Standardize messy job titles into canonical Spanish forms.
          </p>
        </div>

        {/* Form sections */}
        <div className="space-y-6">
          {/* Input area */}
          <InputArea onInput={handleInputLoad} />

          {/* Taxonomy input */}
          <TaxonomyInput
            value={taxonomy}
            onChange={setTaxonomy}
            placeholder="Enter optional taxonomy (one category per line)"
            label="Allowed categories (one per line)"
            id="taxonomy"
            rows={10}
          />

          {/* Advanced panel */}
          <AdvancedPanel
            threshold={threshold}
            onThresholdChange={setThreshold}
            titlesPerRequest={titlesPerRequest}
            onTitlesPerRequestChange={setTitlesPerRequest}
            promptOverride={promptOverride}
            onPromptOverrideChange={setPromptOverride}
            isDryRun={state.is_dry_run}
            onDryRunChange={() => {
              // This would need to dispatch an action to update the state
              // For now, this is a placeholder since we don't have a dispatch for this
            }}
          />

          {/* Preview button (shown in input_loaded state) */}
          {state.toolState.kind === "input_loaded" && (
            <div className="flex justify-end">
              <Button onClick={handlePreview}>Preview clusters</Button>
            </div>
          )}

          {/* Preview panel (shown in previewed state) */}
          {state.toolState.kind === "previewed" && (
            <div className="space-y-4">
              <Card className="p-6 space-y-4">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium">{state.toolState.preview.total_rows.toLocaleString()} →</span>
                  <span className="font-medium">{state.toolState.preview.exact_unique_rows.toLocaleString()} uniques →</span>
                  <span className="font-medium">{state.toolState.preview.cluster_count.toLocaleString()} clusters</span>
                  <span className="text-muted-foreground">·</span>
                  <span className="font-medium">est ${state.toolState.preview.est_cost_usd.toFixed(2)}</span>
                </div>

                {state.toolState.preview.total_input_rows !== undefined &&
                  state.toolState.preview.selected_rows !== undefined && (
                  <div className="text-sm text-muted-foreground">
                    Partial run: {state.toolState.preview.total_input_rows.toLocaleString()} total rows → {state.toolState.preview.selected_rows.toLocaleString()} selected
                  </div>
                )}

                {/* Top clusters preview */}
                <div className="space-y-2">
                  <h3 className="font-medium">Top clusters</h3>
                  {state.toolState.preview.top_clusters.slice(0, 5).map((cluster: { cluster_id: number; representative_original: string; member_count: number }) => (
                    <div key={cluster.cluster_id} className="rounded-md border p-3">
                      <div className="flex justify-between">
                        <span className="font-medium">{cluster.representative_original}</span>
                        <span className="text-sm text-muted-foreground">{cluster.member_count} members</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Action buttons */}
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => handleRecluster(threshold)}>
                    Re-cluster
                  </Button>
                  <Button onClick={handleCommit}>Submit job</Button>
                </div>
              </Card>
            </div>
          )}

          {/* Job status panel (shown in running/completed/failed/cancelled states) */}
          {state.toolState.kind === "running" && (
            <JobStatusPanel
              jobId={state.toolState.jobId}
              onCancel={handleCancel}
            />
          )}

          {state.toolState.kind === "completed" && (
            <JobStatusPanel
              jobId={state.toolState.jobId}
              onCancel={handleCancel}
            />
          )}

          {state.toolState.kind === "failed" && (
            <Card className="p-6 border-destructive">
              <div className="flex items-start gap-4">
                <AlertCircle className="h-6 w-6 text-destructive flex-shrink-0 mt-0.5" />
                <div className="flex-1 space-y-4">
                  <div>
                    <h3 className="font-medium text-destructive">Job failed</h3>
                    <p className="text-sm text-muted-foreground mt-1">{state.toolState.message}</p>
                  </div>
                  <Button variant="outline" onClick={handleRetry}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Retry job
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {state.toolState.kind === "cancelled" && (
            <Card className="p-6">
              <div className="text-center space-y-4">
                <div>
                  <h3 className="font-medium">Job cancelled</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    The job was cancelled. You can start over with a new upload.
                  </p>
                </div>
                <Button variant="outline" onClick={handleRetry}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Start over
                </Button>
              </div>
            </Card>
          )}
        </div>

        {/* History panel */}
        <div className="space-y-4">
          <h2 className="text-xl font-serif">Job history</h2>
          <HistoryList jobs={jobs.jobs} />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t py-6">
        <div className="max-w-4xl mx-auto px-4 text-center text-sm text-muted-foreground">
          Nomenclator · v1.0 · built for a single operator · quis custodiet ipsos custodes?
        </div>
      </footer>
    </div>
  );
}
