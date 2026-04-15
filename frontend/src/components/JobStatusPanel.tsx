import { useState } from "react";
import { useJobPolling } from "@/hooks/useJobPolling";
import { jobsApi } from "@/lib/jobs-api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Spinner } from "@/components/Spinner";

interface JobStatusPanelProps {
  jobId: string;
  onCancel?: () => void;
}

export function JobStatusPanel({ jobId, onCancel }: JobStatusPanelProps) {
  const { job, error } = useJobPolling(jobId, true);
  const [isCancelling, setIsCancelling] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const isTerminal = job && ["completed", "failed", "cancelled"].includes(job.status);
  const isRunning = job && ["submitted", "polling", "retrying"].includes(job.status);

  const handleCancel = async () => {
    if (showCancelConfirm) {
      setIsCancelling(true);
      try {
        await jobsApi.cancel(jobId);
        onCancel?.();
      } catch (err) {
        console.error("Failed to cancel job:", err);
      } finally {
        setIsCancelling(false);
        setShowCancelConfirm(false);
      }
    } else {
      setShowCancelConfirm(true);
    }
  };

  const handleDismissCancel = () => {
    setShowCancelConfirm(false);
  };

  if (error) {
    return (
      <Card className="p-4 border-destructive">
        <p className="text-destructive">{error}</p>
      </Card>
    );
  }

  if (!job) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-2">
          <Spinner />
          <p className="text-sm text-muted-foreground">Loading job status...</p>
        </div>
      </Card>
    );
  }

  const statusColors: Record<string, "default" | "secondary" | "destructive"> = {
    draft: "secondary",
    preview: "secondary",
    queued: "secondary",
    submitted: "default",
    polling: "default",
    retrying: "secondary",
    completed: "default",
    failed: "destructive",
    cancelled: "secondary",
  };

  return (
    <Card className="p-4">
      <div className="space-y-4">
        {/* Status header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant={statusColors[job.status] || "secondary"}>
              {job.status}
            </Badge>
            {isRunning && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner className="h-4 w-4" />
                <span>Processing...</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isTerminal && (
              <a
                href={jobsApi.downloadUrl(jobId)}
                download
                className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 py-2"
              >
                Download
              </a>
            )}
            {!isTerminal && (
              <>
                {showCancelConfirm ? (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleDismissCancel}
                      disabled={isCancelling}
                    >
                      Keep running
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleCancel}
                      disabled={isCancelling}
                    >
                      {isCancelling ? (
                        <>
                          <Spinner className="h-4 w-4 mr-1" />
                          Cancelling...
                        </>
                      ) : (
                        "Confirm cancel"
                      )}
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCancel}
                    disabled={isCancelling}
                  >
                    Cancel
                  </Button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Progress information */}
        {job.progress && (
          <div className="space-y-2">
            <div className="text-sm text-muted-foreground">
              {job.total_rows} rows · {job.est_cost_usd.toFixed(2)} USD est.
            </div>
            {job.progress.clusters_total > 0 && (
              <div className="text-sm text-muted-foreground">
                {job.progress.clusters_resolved} / {job.progress.clusters_total} clusters resolved
                {job.progress.clusters_error > 0 && ` · ${job.progress.clusters_error} errors`}
              </div>
            )}
          </div>
        )}

        {/* Retry round indicator */}
        {job.retry_round > 0 && (
          <div>
            <Badge variant="secondary">Retry round {job.retry_round}</Badge>
          </div>
        )}
      </div>
    </Card>
  );
}
