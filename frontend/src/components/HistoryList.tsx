import { useState } from "react";
import type { JobSummary } from "@/lib/jobs-api";
import { jobsApi } from "@/lib/jobs-api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface HistoryListProps {
  jobs: JobSummary[];
}

export function HistoryList({ jobs }: HistoryListProps) {
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);

  // Sort jobs by created_at descending (newest first)
  const sortedJobs = [...jobs].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

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

  if (sortedJobs.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        No jobs yet. Upload a CSV file or paste job titles to get started.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {sortedJobs.map((job) => {
        const isExpanded = expandedJobId === job.id;
        const isPartial = job.row_subset_mode !== "all";

        return (
          <Collapsible
            key={job.id}
            open={isExpanded}
            onOpenChange={(open) => setExpandedJobId(open ? job.id : null)}
          >
            <CollapsibleTrigger>
              <Card
                className={cn(
                  "p-4 cursor-pointer hover:bg-accent/50 transition-colors",
                  isExpanded && "border-primary"
                )}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {/* Expand/collapse icon */}
                    <div className="flex-shrink-0">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>

                    {/* Status badge */}
                    <div className="flex-shrink-0">
                      <Badge variant={statusColors[job.status] || "secondary"}>
                        {job.status}
                      </Badge>
                    </div>

                    {/* Row count and cost */}
                    <div className="flex items-center gap-2 text-sm text-muted-foreground flex-1 min-w-0">
                      <span className="truncate">
                        {job.total_rows} rows
                        {job.actual_cost_usd > 0
                          ? ` · $${job.actual_cost_usd.toFixed(4)}`
                          : job.est_cost_usd > 0
                          ? ` · est. $${job.est_cost_usd.toFixed(4)}`
                          : ""}
                      </span>
                    </div>

                    {/* Badges */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {job.is_dry_run && (
                        <Badge variant="secondary">Dry run</Badge>
                      )}
                      {isPartial && (
                        <Badge variant="secondary">Partial</Badge>
                      )}
                    </div>

                    {/* Download button for completed jobs */}
                    {job.status === "completed" && (
                      <button
                        type="button"
                        className="flex-shrink-0 text-sm text-primary hover:underline"
                        onClick={(e) => { e.stopPropagation(); jobsApi.downloadCsv(job.id); }}
                      >
                        Download
                      </button>
                    )}
                  </div>
                </div>
              </Card>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <Card className="mt-1 p-4 border-l-4 border-l-primary ml-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-muted-foreground">Created</div>
                    <div>{new Date(job.created_at).toLocaleString()}</div>
                  </div>
                  {job.finished_at && (
                    <div>
                      <div className="text-muted-foreground">Finished</div>
                      <div>{new Date(job.finished_at).toLocaleString()}</div>
                    </div>
                  )}
                  <div>
                    <div className="text-muted-foreground">Clusters</div>
                    <div>{job.cluster_count}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Threshold</div>
                    <div>{job.fuzzy_threshold}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Titles per request</div>
                    <div>{job.titles_per_request}</div>
                  </div>
                  {isPartial && (
                    <div>
                      <div className="text-muted-foreground">Subset</div>
                      <div>
                        {job.row_subset_mode} {job.row_subset_n ? `(${job.row_subset_n})` : ""}
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            </CollapsibleContent>
          </Collapsible>
        );
      })}
    </div>
  );
}
