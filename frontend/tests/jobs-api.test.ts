/**
 * Tests for jobs-api.ts
 * Tests typed wrappers around all /jobs* and /spend endpoints
 */

import { describe, it, expect, vi } from "vitest";
import { api } from "../src/lib/api";
import { jobsApi } from "../src/lib/jobs-api";

// Mock the api module
vi.mock("../src/lib/api", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    postForm: vi.fn(),
  },
}));

describe("jobs-api", () => {
  it("preview posts multipart", async () => {
    const formData = new FormData();
    formData.append("file", new File(["data"], "test.csv", { type: "text/csv" }));
    formData.append("threshold", "90");
    formData.append("titles_per_request", "25");

    const mockResponse = {
      job_id: "abc123",
      total_rows: 100,
      exact_unique_rows: 95,
      cluster_count: 50,
      largest_cluster_size: 10,
      est_cost_usd: 0.25,
      top_clusters: [],
      warnings: [],
    };

    vi.mocked(api.postForm).mockResolvedValue(mockResponse);

    const result = await jobsApi.preview(formData);

    expect(api.postForm).toHaveBeenCalledWith("/jobs/preview", formData);
    expect(result).toEqual(mockResponse);
  });

  it("commit sends JSON body", async () => {
    const body = {
      prompt_override: "custom prompt",
      taxonomy: "custom taxonomy",
      titles_per_request: 25,
      is_dry_run: false,
    };

    const mockResponse = {
      job_id: "abc123",
      status: "submitted",
    };

    vi.mocked(api.post).mockResolvedValue(mockResponse);

    const result = await jobsApi.commit("abc123", body);

    expect(api.post).toHaveBeenCalledWith("/jobs/abc123/commit", body);
    expect(result).toEqual(mockResponse);
  });

  it("list returns typed array", async () => {
    const mockResponse = {
      jobs: [
        {
          id: "job1",
          status: "completed",
          created_at: "2024-01-01T00:00:00Z",
          total_rows: 100,
          cluster_count: 50,
          est_cost_usd: 0.25,
          actual_cost_usd: 0.23,
          finished_at: "2024-01-01T00:05:00Z",
          fuzzy_threshold: 90,
          titles_per_request: 25,
          row_subset_mode: null,
          row_subset_n: null,
          is_dry_run: false,
        },
      ],
    };

    vi.mocked(api.get).mockResolvedValue(mockResponse);

    const result = await jobsApi.list();

    expect(api.get).toHaveBeenCalledWith("/jobs");
    expect(result).toEqual(mockResponse);
    expect(result.jobs[0].id).toBe("job1");
  });

  it("get returns typed object", async () => {
    const mockResponse = {
      id: "job1",
      status: "completed",
      created_at: "2024-01-01T00:00:00Z",
      total_rows: 100,
      cluster_count: 50,
      est_cost_usd: 0.25,
      actual_cost_usd: 0.23,
      finished_at: "2024-01-01T00:05:00Z",
      fuzzy_threshold: 90,
      titles_per_request: 25,
      row_subset_mode: null,
      row_subset_n: null,
      is_dry_run: false,
      retry_round: 0,
      progress: {
        clusters_total: 50,
        clusters_resolved: 50,
        clusters_pending: 0,
        clusters_error: 0,
      },
      batches: [],
    };

    vi.mocked(api.get).mockResolvedValue(mockResponse);

    const result = await jobsApi.get("job1");

    expect(api.get).toHaveBeenCalledWith("/jobs/job1");
    expect(result).toEqual(mockResponse);
    expect(result.progress.clusters_total).toBe(50);
  });

  it("downloadUrl returns /jobs/:id/download", () => {
    const url = jobsApi.downloadUrl("abc123");

    expect(url).toBe("/jobs/abc123/download");
    expect(url).toMatch(/^\/jobs\/[^/]+\/download$/);
  });

  it("reviewPrompt sends prompt and few_shots", async () => {
    const prompt = "Test prompt";
    const fewShots = '[{"input": "test", "male_es": "test", "female_es": "test", "category": "test"}]';

    const mockResponse = {
      safe: true,
      quality_score: "good",
      issues: [],
      suggestions: [],
      summary: "Looks good",
    };

    vi.mocked(api.post).mockResolvedValue(mockResponse);

    const result = await jobsApi.reviewPrompt(prompt, fewShots);

    expect(api.post).toHaveBeenCalledWith("/jobs/review-prompt", {
      prompt,
      few_shots: fewShots,
    });
    expect(result).toEqual(mockResponse);
  });
});
