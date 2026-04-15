/**
 * PreviewPanel component
 * Button that calls /jobs/preview; on success shows counts, est cost, top clusters table, and a "Re-cluster" button
 * Includes row subset selector in the form. Preview panel shows both "total rows" and "selected rows" for partial runs.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle } from "lucide-react";
import { Spinner } from "./Spinner";
import { jobsApi } from "@/lib/jobs-api";
import type { PreviewResponse } from "@/lib/jobs-api";

interface PreviewPanelProps {
  input?: { file?: File; text?: string };
  threshold: number;
  titlesPerRequest: number;
  taxonomy?: string;
  promptOverride?: string;
  rowSubsetMode: "all" | "first_n" | "random_n";
  rowSubsetN: number | null;
  isDryRun?: boolean;
  onPreviewSuccess: (preview: PreviewResponse) => void;
  onRecluster: (threshold: number) => void;
  // Future parameters for API calls
  _taxonomy?: string;
  _promptOverride?: string;
  _isDryRun?: boolean;
}

export function PreviewPanel({
  input,
  threshold,
  titlesPerRequest,
  rowSubsetMode,
  rowSubsetN,
  onPreviewSuccess,
  onRecluster,
  // Unused parameters - will be used in future when we send taxonomy/prompt/dry-run to API
  _taxonomy,
  _promptOverride,
  _isDryRun,
}: PreviewPanelProps) {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  void _taxonomy;
  void _promptOverride;
  void _isDryRun;
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [localThreshold, setLocalThreshold] = useState(threshold);

  const handlePreview = async () => {
    if (!input) return;

    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      if (input.file) {
        formData.append("file", input.file);
      }
      if (input.text) {
        formData.append("text", input.text);
      }
      formData.append("threshold", threshold.toString());
      formData.append("titles_per_request", titlesPerRequest.toString());
      formData.append("row_subset_mode", rowSubsetMode);
      if (rowSubsetN !== null) {
        formData.append("row_subset_n", rowSubsetN.toString());
      }

      const result = await jobsApi.preview(formData);
      setPreview(result);
      setLocalThreshold(threshold);
      onPreviewSuccess(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to preview";
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRecluster = () => {
    if (!preview) return;
    onRecluster(localThreshold);
  };

  const hasInput = input && (input.file || input.text);
  const isPartial = preview?.total_input_rows !== undefined && preview.selected_rows !== undefined;

  return (
    <div className="space-y-4">
      {/* Preview button */}
      <Button
        type="button"
        onClick={handlePreview}
        disabled={!hasInput || isLoading}
        className="w-full"
      >
        {isLoading ? <Spinner className="mr-2 h-4 w-4" /> : null}
        {isLoading ? "Previewing..." : "Preview clusters"}
      </Button>

      {/* Error display */}
      {error && (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-red-800">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <div>
              <p className="font-medium">Error</p>
              <p className="text-sm">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Preview results */}
      {preview && !isLoading && (
        <Card>
          <CardHeader>
            <CardTitle>Preview results</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Counts row */}
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">
                {isPartial && preview.total_input_rows !== undefined && preview.selected_rows !== undefined
                  ? `${preview.total_input_rows.toLocaleString()} → ${preview.selected_rows.toLocaleString()} selected →`
                  : `${preview.total_rows.toLocaleString()} →`}
              </span>
              <span className="font-medium">
                {preview.exact_unique_rows.toLocaleString()} uniques →
              </span>
              <span className="font-medium">
                {preview.cluster_count.toLocaleString()} clusters
              </span>
              <span className="text-muted-foreground">·</span>
              <span className="font-medium">est ${preview.est_cost_usd.toFixed(2)}</span>
            </div>

            {/* Large cluster warning */}
            {preview.warnings.some((w) => w.type === "large_cluster") && (
              <div className="flex items-center gap-2">
                <Badge variant="destructive">Large cluster warning</Badge>
                <span className="text-sm text-muted-foreground">
                  Some clusters have more than 50 members
                </span>
              </div>
            )}

            {/* Top clusters table */}
            <div className="space-y-2">
              <h3 className="font-medium">Top {Math.min(10, preview.top_clusters.length)} largest clusters</h3>
              <div className="space-y-2">
                {preview.top_clusters.slice(0, 10).map((cluster) => (
                  <div key={cluster.cluster_id} className="rounded-md border p-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <p className="font-medium">{cluster.representative_original}</p>
                        <p className="text-sm text-muted-foreground">{cluster.member_count} members</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Re-cluster button */}
            <Button
              type="button"
              variant="outline"
              onClick={handleRecluster}
              disabled={isLoading}
              className="w-full"
            >
              Re-cluster (threshold: {localThreshold})
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
