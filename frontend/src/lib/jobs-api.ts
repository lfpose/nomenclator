/**
 * API client functions for jobs and spend endpoints
 * Typed wrappers around all backend API endpoints
 */

import { api } from "./api";

export type ReviewResponse = {
  safe: boolean;
  quality_score: string;
  issues: string[];
  suggestions: string[];
  summary: string;
};

export type TopCluster = {
  cluster_id: number;
  representative: string;
  normalized_key: string;
  member_count: number;
  members: string[];
  member_sims: number[];
};

export type PreviewWarning = {
  type: string;
  [k: string]: unknown;
};

export type PreviewResponse = {
  job_id: string;
  total_rows: number;
  exact_unique_rows: number;
  cluster_count: number;
  largest_cluster_size: number;
  est_cost_usd: number;
  top_clusters: TopCluster[];
  warnings: PreviewWarning[];
  size_distribution: Record<string, number>;
  clustering_mode: string;
  total_input_rows?: number;
  selected_rows?: number;
};

/**
 * Runtime validator for PreviewResponse. Throws with a precise message when a
 * required field is missing or the wrong type. Exists to catch BE/FE contract
 * drift loudly instead of silently rendering `undefined`.
 */
export function validatePreviewResponse(raw: unknown): PreviewResponse {
  const r = raw as Record<string, unknown>;
  const missing: string[] = [];
  const required = [
    "job_id",
    "total_rows",
    "exact_unique_rows",
    "cluster_count",
    "largest_cluster_size",
    "est_cost_usd",
    "top_clusters",
    "warnings",
    "size_distribution",
    "clustering_mode",
  ];
  for (const k of required) if (r?.[k] === undefined) missing.push(k);
  if (missing.length) {
    throw new Error(
      `PreviewResponse missing fields: ${missing.join(", ")}. Got: ${JSON.stringify(r).slice(0, 300)}`
    );
  }
  const clusters = r.top_clusters as unknown;
  if (!Array.isArray(clusters)) {
    throw new Error("PreviewResponse.top_clusters is not an array");
  }
  clusters.forEach((c, i) => {
    const cc = c as Record<string, unknown>;
    const need = ["cluster_id", "representative", "normalized_key", "member_count", "members"];
    const miss = need.filter((k) => cc?.[k] === undefined);
    if (miss.length) {
      throw new Error(`top_clusters[${i}] missing: ${miss.join(", ")}. Got keys: ${Object.keys(cc).join(",")}`);
    }
    if (!Array.isArray(cc.members)) {
      throw new Error(`top_clusters[${i}].members is not an array`);
    }
  });
  return r as unknown as PreviewResponse;
}

export type JobSummary = {
  id: string;
  status: string;
  created_at: string;
  total_rows: number;
  cluster_count: number;
  est_cost_usd: number;
  actual_cost_usd: number;
  finished_at: string | null;
  fuzzy_threshold: number;
  titles_per_request: number;
  row_subset_mode: string | null;
  row_subset_n: number | null;
  is_dry_run: boolean;
};

export type BatchSummary = {
  id: number;
  status: string;
  request_count: number;
  retry_round: number;
};

export type JobProgress = {
  clusters_total: number;
  clusters_resolved: number;
  clusters_pending: number;
  clusters_error: number;
};

export type JobDetail = JobSummary & {
  retry_round: number;
  progress: JobProgress;
  batches: BatchSummary[];
};

export type SpendResponse = {
  used_usd: number;
  cap_usd: number;
  reset_date: string | null;
};

export const jobsApi = {
  /**
   * Review a prompt for safety and quality
   */
  reviewPrompt: (prompt: string, fewShots: string): Promise<ReviewResponse> =>
    api.post<ReviewResponse>("/jobs/review-prompt", { prompt, few_shots: fewShots }),

  /**
   * Create a preview job from CSV or text input
   * FormData should include: file (File), text (string), threshold (number), titles_per_request (number)
   * Optionally: row_subset_mode (string), row_subset_n (number)
   */
  preview: async (form: FormData): Promise<PreviewResponse> => {
    const raw = await api.postForm<unknown>("/jobs/preview", form);
    if (import.meta.env.DEV) console.debug("[preview response]", raw);
    return validatePreviewResponse(raw);
  },

  /**
   * Recluster an existing job with a new threshold
   */
  recluster: async (jobId: string, threshold: number, canonicalTitles?: string[]): Promise<PreviewResponse> => {
    const raw = await api.post<unknown>(`/jobs/${jobId}/recluster`, {
      threshold,
      ...(canonicalTitles?.length ? { canonical_titles: canonicalTitles } : {}),
    });
    if (import.meta.env.DEV) console.debug("[recluster response]", raw);
    return validatePreviewResponse(raw);
  },

  /**
   * Commit a job to be processed by Anthropic
   * Body can include: prompt_override (string), taxonomy (string), titles_per_request (number), is_dry_run (boolean)
   */
  commit: (
    jobId: string,
    body: {
      prompt_override?: string;
      taxonomy?: string;
      titles_per_request?: number;
      is_dry_run?: boolean;
    }
  ): Promise<{ job_id: string; status: string }> =>
    api.post<{ job_id: string; status: string }>(`/jobs/${jobId}/commit`, body),

  /**
   * Cancel a job in progress
   */
  cancel: (jobId: string): Promise<{ ok: boolean }> =>
    api.post<{ ok: boolean }>(`/jobs/${jobId}/cancel`, {}),

  /**
   * List all jobs, newest first
   */
  list: (): Promise<{ jobs: JobSummary[] }> =>
    api.get<{ jobs: JobSummary[] }>("/jobs"),

  /**
   * Get details for a single job including progress and batches
   */
  get: (jobId: string): Promise<JobDetail> =>
    api.get<JobDetail>(`/jobs/${jobId}`),

  /**
   * Download the CSV for a completed job, ensuring credentials are sent.
   */
  downloadCsv: async (jobId: string): Promise<void> => {
    const res = await fetch(`/jobs/${jobId}/download`, { credentials: "include" });
    if (!res.ok) throw new Error(`Download failed: ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `nomenclator-${jobId.replace(/-/g, "").slice(0, 8)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },

  /**
   * Get current spend status
   */
  spend: (): Promise<SpendResponse> =>
    api.get<SpendResponse>("/spend"),
};
