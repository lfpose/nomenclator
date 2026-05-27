import { useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { PreviewResponse, TopCluster } from "@/lib/jobs-api";

interface ClusterPreviewProps {
  preview: PreviewResponse;
  threshold: number;
  onRecluster: () => void;
  onSubmit: () => void;
  reclustering?: boolean;
}

function ClusterCard({ cluster, rank }: { cluster: TopCluster; rank: number }) {
  const [open, setOpen] = useState(false);
  const Icon = open ? ChevronDown : ChevronRight;
  return (
    <div
      data-testid="cluster-card"
      data-cluster-id={cluster.cluster_id}
      className="rounded-md border"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start justify-between gap-3 p-3 text-left hover:bg-muted/40 transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <Icon className="h-4 w-4 mt-0.5 flex-shrink-0 text-muted-foreground" />
          <span
            className="text-xs text-muted-foreground tabular-nums w-5 flex-shrink-0"
            aria-hidden
          >
            #{rank}
          </span>
          <div className="flex-1 min-w-0">
            <div
              data-testid="cluster-representative"
              className="font-medium truncate"
              title={cluster.representative}
            >
              {cluster.representative}
            </div>
            <div className="text-xs text-muted-foreground font-mono truncate">
              key: {cluster.normalized_key}
            </div>
          </div>
        </div>
        <Badge variant="secondary" data-testid="cluster-member-count">
          {cluster.member_count} members
        </Badge>
      </button>

      {open && (
        <div className="border-t bg-muted/20 p-3 space-y-1" data-testid="cluster-members">
          {cluster.members.map((m, i) => {
            const sim = cluster.member_sims?.[i];
            return (
              <div key={i} className="text-sm font-mono break-words flex items-baseline gap-2">
                <span className="text-muted-foreground shrink-0">{i + 1}.</span>
                <span className="flex-1">{m}</span>
                {sim !== undefined && (
                  <span className={`shrink-0 tabular-nums text-xs ${sim >= 90 ? "text-green-600 dark:text-green-400" : sim >= 80 ? "text-foreground/60" : "text-amber-600 dark:text-amber-400"}`}>
                    {sim.toFixed(0)}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SizeDistribution({ dist, total }: { dist: Record<string, number>; total: number }) {
  const bands = useMemo(() => {
    const defs: { label: string; test: (n: number) => boolean }[] = [
      { label: "1 (singletons)", test: (n) => n === 1 },
      { label: "2", test: (n) => n === 2 },
      { label: "3–5", test: (n) => n >= 3 && n <= 5 },
      { label: "6–10", test: (n) => n >= 6 && n <= 10 },
      { label: "11–25", test: (n) => n >= 11 && n <= 25 },
      { label: "26–50", test: (n) => n >= 26 && n <= 50 },
      { label: "50+", test: (n) => n > 50 },
    ];
    const counts = defs.map((d) => ({ label: d.label, count: 0, members: 0 }));
    Object.entries(dist).forEach(([k, v]) => {
      const size = Number(k);
      const clusters = v;
      const idx = defs.findIndex((d) => d.test(size));
      if (idx >= 0) {
        counts[idx].count += clusters;
        counts[idx].members += clusters * size;
      }
    });
    const nonEmpty = counts.filter((b) => b.count > 0);
    const max = Math.max(...nonEmpty.map((b) => b.count), 1);
    return nonEmpty.map((b) => ({
      ...b,
      pct: (b.count / max) * 100,
      sharePct: (b.count / total) * 100,
    }));
  }, [dist, total]);

  if (bands.length === 0) return null;

  return (
    <div className="space-y-1" data-testid="size-distribution">
      <div className="space-y-0.5">
        {bands.map(({ label, count, pct, sharePct, members }) => (
          <div key={label} className="flex items-center gap-2 text-xs">
            <span className="tabular-nums w-24 text-muted-foreground shrink-0">{label}</span>
            <div className="w-24 h-2.5 bg-muted rounded-sm overflow-hidden shrink-0">
              <div className="h-full bg-foreground/70" style={{ width: `${pct}%` }} />
            </div>
            <span className="tabular-nums text-muted-foreground">
              {count} · {members} rows ({sharePct.toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ClusterPreview({
  preview,
  threshold,
  onRecluster,
  onSubmit,
  reclustering = false,
}: ClusterPreviewProps) {
  const [showRaw, setShowRaw] = useState(false);
  const [showDist, setShowDist] = useState(false);

  const totalShown = preview.top_clusters.reduce((s, c) => s + c.member_count, 0);
  const coveredPct = preview.total_rows > 0 ? (totalShown / preview.total_rows) * 100 : 0;
  const isPartial =
    preview.total_input_rows !== undefined && preview.selected_rows !== undefined;

  const singletonCount = preview.size_distribution?.["1"] ?? 0;

  return (
    <TooltipProvider>
      <Card
        className="h-full flex flex-col overflow-hidden p-0"
        data-testid="preview-card"
      >
        {/* Header: summary stats only (fixed, compact) */}
        <div className="flex-shrink-0 px-4 py-3 border-b space-y-1.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span className="font-medium" data-testid="summary-total-rows">
              {preview.total_rows.toLocaleString()} rows
            </span>
            <span className="text-muted-foreground">→</span>
            <span className="font-medium">
              {preview.exact_unique_rows.toLocaleString()} uniques
            </span>
            <span className="text-muted-foreground">→</span>
            <span className="font-medium" data-testid="summary-cluster-count">
              {preview.cluster_count.toLocaleString()} clusters
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge
                  variant={preview.clustering_mode === "embeddings" ? "default" : "secondary"}
                  className="cursor-help text-xs"
                  data-testid="clustering-mode-badge"
                >
                  {preview.clustering_mode === "embeddings" ? "AI embeddings" : "Fuzzy match"}
                </Badge>
              </TooltipTrigger>
              <TooltipContent className="max-w-64">
                {preview.clustering_mode === "embeddings"
                  ? "Clustering uses OpenAI text-embedding-3-small — captures semantic similarity across languages (\"Gerente de TI\" and \"IT Manager\" can cluster together)."
                  : "Clustering uses rapidfuzz string matching — fast but character-level only. Set OPENAI_API_KEY to enable semantic embeddings."}
              </TooltipContent>
            </Tooltip>
            {singletonCount > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-xs text-amber-600 dark:text-amber-400 cursor-help">
                    ({singletonCount} singletons)
                  </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-64">
                  {singletonCount} titles didn't match any other title at threshold {threshold}.{" "}
                  {preview.clustering_mode === "embeddings"
                    ? `With AI embeddings, t=${threshold} requires very high cosine similarity. Try t=80 or t=75 — semantically similar titles like "Gerente de Ventas" and "Director Comercial" typically score 0.75–0.85.`
                    : "Try lowering the threshold to merge more clusters."}
                </TooltipContent>
              </Tooltip>
            )}
            <span className="text-muted-foreground">·</span>
            <span className="font-medium">largest {preview.largest_cluster_size}</span>
            <span className="text-muted-foreground">·</span>
            <span className="font-medium">est ${preview.est_cost_usd.toFixed(4)}</span>
          </div>

          {isPartial && (
            <div className="text-xs text-muted-foreground">
              Partial run: {preview.total_input_rows!.toLocaleString()} input →{" "}
              {preview.selected_rows!.toLocaleString()} selected
            </div>
          )}

          {preview.warnings.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {preview.warnings.map((w, i) => (
                <Badge key={i} variant="destructive">
                  {w.type}
                </Badge>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={() => setShowDist((v) => !v)}
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            {showDist ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            Size distribution
          </button>
          {showDist && <SizeDistribution dist={preview.size_distribution} total={preview.cluster_count} />}
        </div>

        {/* Scrollable cluster list */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-2">
          <div className="flex items-baseline justify-between">
            <h3 className="font-medium text-sm">
              Top {preview.top_clusters.length} clusters
            </h3>
            <span className="text-xs text-muted-foreground">
              covering {totalShown.toLocaleString()} of{" "}
              {preview.total_rows.toLocaleString()} rows ({coveredPct.toFixed(1)}%)
            </span>
          </div>
          <div className="space-y-2" data-testid="cluster-list">
            {preview.top_clusters.map((c, i) => (
              <ClusterCard key={c.cluster_id} cluster={c} rank={i + 1} />
            ))}
          </div>
          {preview.cluster_count > preview.top_clusters.length && (
            <div className="text-xs text-muted-foreground pt-1">
              {(preview.cluster_count - preview.top_clusters.length).toLocaleString()}{" "}
              smaller clusters not shown.
            </div>
          )}
        </div>

        {/* Footer: actions (fixed) */}
        <div className="flex-shrink-0 border-t p-3 space-y-2 bg-background">
          <div className="flex gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex">
                  <Button
                    variant="outline"
                    onClick={onRecluster}
                    disabled={reclustering}
                    data-testid="btn-recluster"
                  >
                    {reclustering ? "Re-clustering..." : `Re-cluster (t=${threshold})`}
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent className="max-w-72">
                <p className="font-medium mb-1">Similarity threshold (t={threshold})</p>
                <p className="text-xs">
                  Two job titles are grouped together when their string similarity score is ≥{threshold}/100.
                  Higher = stricter (more, smaller clusters). Lower = looser (fewer, bigger clusters).
                </p>
                <p className="text-xs mt-1 text-muted-foreground">
                  Uses fuzzy string matching — not AI. "Gerente de TI" and "Jefe de IT" won't merge even at t=70 because the strings look different.
                </p>
              </TooltipContent>
            </Tooltip>
            <Button
              onClick={onSubmit}
              disabled={reclustering}
              data-testid="btn-submit"
              className="flex-1"
            >
              Submit job
            </Button>
          </div>
          <div>
            <button
              type="button"
              onClick={() => setShowRaw((v) => !v)}
              className="text-xs text-muted-foreground hover:text-foreground"
              data-testid="toggle-raw"
            >
              {showRaw ? "Hide" : "Show"} raw response
            </button>
            {showRaw && (
              <pre
                data-testid="raw-response"
                className="mt-2 text-xs font-mono bg-muted p-3 rounded-md max-h-48 overflow-auto"
              >
                {JSON.stringify(preview, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </Card>
    </TooltipProvider>
  );
}
