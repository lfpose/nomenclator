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

export type ClusterMember = {
  cluster_id: number;
  row_index: number;
  original: string;
  normalized: string;
};

export type TopCluster = {
  cluster_id: number;
  representative_original: string;
  normalized_key: string;
  member_count: number;
  members: ClusterMember[];
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
  total_input_rows?: number;
  selected_rows?: number;
};

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
  preview: (form: FormData): Promise<PreviewResponse> =>
    api.postForm<PreviewResponse>("/jobs/preview", form),

  /**
   * Recluster an existing job with a new threshold
   */
  recluster: (jobId: string, threshold: number): Promise<PreviewResponse> =>
    api.post<PreviewResponse>(`/jobs/${jobId}/recluster`, { threshold }),

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
   * Get the download URL for a completed job
   */
  downloadUrl: (jobId: string): string => `/jobs/${jobId}/download`,

  /**
   * Get current spend status
   */
  spend: (): Promise<SpendResponse> =>
    api.get<SpendResponse>("/spend"),
};
