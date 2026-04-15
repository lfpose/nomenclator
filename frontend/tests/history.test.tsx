import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HistoryList } from "../src/components/HistoryList";
import type { JobSummary } from "../src/lib/jobs-api";
import { jobsApi } from "../src/lib/jobs-api";

// Mock jobsApi.downloadUrl to return predictable URLs
vi.mock("../src/lib/jobs-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lib/jobs-api")>();
  return {
    ...actual,
    jobsApi: {
      ...actual.jobsApi,
      downloadUrl: vi.fn((jobId: string) => `/jobs/${jobId}/download`),
    },
  };
});

function createMockJob(overrides: Partial<JobSummary> = {}): JobSummary {
  return {
    id: "job-001",
    status: "completed",
    created_at: "2024-01-15T10:30:00Z",
    total_rows: 100,
    cluster_count: 50,
    est_cost_usd: 0.25,
    actual_cost_usd: 0.24,
    finished_at: "2024-01-15T10:35:00Z",
    fuzzy_threshold: 90,
    titles_per_request: 25,
    row_subset_mode: "all",
    row_subset_n: null,
    is_dry_run: false,
    ...overrides,
  };
}

describe("HistoryList", () => {
  describe("renders jobs newest first", () => {
    it("should render jobs in reverse-chronological order", () => {
      // Use different row counts to distinguish jobs visually
      const jobs: JobSummary[] = [
        createMockJob({ id: "job-001", created_at: "2024-01-15T10:00:00Z", total_rows: 100 }),
        createMockJob({ id: "job-002", created_at: "2024-01-15T11:00:00Z", total_rows: 200 }),
        createMockJob({ id: "job-003", created_at: "2024-01-15T10:30:00Z", total_rows: 150 }),
      ];

      render(<HistoryList jobs={jobs} />);

      // Find all elements with truncate class in the main job cards
      const rowTexts = Array.from(document.querySelectorAll("span.truncate"));

      // Extract row counts in order
      const rowCounts = rowTexts
        .map((el) => {
          const text = el.textContent || "";
          const match = text.match(/(\d+)/);
          return match ? parseInt(match[1], 10) : 0;
        })
        .filter((n) => n > 0);

      // Jobs should be displayed newest first (200, 150, 100)
      expect(rowCounts).toEqual([200, 150, 100]);
    });
  });

  describe("shows status badge per job", () => {
    it("should display status badge for each job", () => {
      const jobs: JobSummary[] = [
        createMockJob({ id: "job-001", status: "completed" }),
        createMockJob({ id: "job-002", status: "failed" }),
        createMockJob({ id: "job-003", status: "running" }),
      ];

      render(<HistoryList jobs={jobs} />);

      expect(screen.getByText("completed")).toBeInTheDocument();
      expect(screen.getByText("failed")).toBeInTheDocument();
      expect(screen.getByText("running")).toBeInTheDocument();
    });
  });

  describe("shows row count and cost", () => {
    it("should display row count and estimated cost", () => {
      const jobs: JobSummary[] = [
        createMockJob({
          id: "job-001",
          total_rows: 100,
          est_cost_usd: 0.25,
          actual_cost_usd: 0,
        }),
      ];

      render(<HistoryList jobs={jobs} />);

      expect(screen.getByText((content) => content.includes("100 rows"))).toBeInTheDocument();
      expect(screen.getByText((content) => content.includes("est. $0.2500"))).toBeInTheDocument();
    });

    it("should display row count and actual cost when job is completed", () => {
      const jobs: JobSummary[] = [
        createMockJob({
          id: "job-001",
          total_rows: 100,
          est_cost_usd: 0.25,
          actual_cost_usd: 0.24,
        }),
      ];

      render(<HistoryList jobs={jobs} />);

      expect(screen.getByText((content) => content.includes("100 rows"))).toBeInTheDocument();
      expect(screen.getByText((content) => content.includes("$0.2400"))).toBeInTheDocument();
    });
  });

  describe("expands row to show details on click", () => {
    it("should expand job details on click", () => {
      const jobs: JobSummary[] = [
        createMockJob({
          id: "job-001",
          fuzzy_threshold: 90,
          titles_per_request: 25,
          cluster_count: 50,
        }),
      ];

      render(<HistoryList jobs={jobs} />);

      // Initially, details should not be visible
      expect(screen.queryByText("Clusters")).not.toBeInTheDocument();
      expect(screen.queryByText("Threshold")).not.toBeInTheDocument();

      // Click on the job card to expand (use the cursor-pointer button)
      const jobCard = screen.getByRole("button", { name: /completed/i });
      fireEvent.click(jobCard);

      // After clicking, details should be visible
      expect(screen.getByText("Clusters")).toBeInTheDocument();
      expect(screen.getByText("50")).toBeInTheDocument();
      expect(screen.getByText("Threshold")).toBeInTheDocument();
      expect(screen.getByText("90")).toBeInTheDocument();
    });
  });

  describe("download link present for completed jobs only", () => {
    it("should show download link for completed jobs", () => {
      const jobs: JobSummary[] = [createMockJob({ id: "job-001", status: "completed" })];

      render(<HistoryList jobs={jobs} />);

      const downloadLink = screen.getByText("Download");
      expect(downloadLink).toBeInTheDocument();
      expect(downloadLink.tagName).toBe("A");
      expect(downloadLink).toHaveAttribute("href", "/jobs/job-001/download");
      expect(downloadLink).toHaveAttribute("download");
    });

    it("should not show download link for non-completed jobs", () => {
      const jobs: JobSummary[] = [createMockJob({ id: "job-001", status: "preview" })];

      render(<HistoryList jobs={jobs} />);

      expect(screen.queryByText("Download")).not.toBeInTheDocument();
    });
  });

  describe("shows dry run badge", () => {
    it("should display 'Dry run' badge for dry-run jobs", () => {
      const jobs: JobSummary[] = [createMockJob({ id: "job-001", is_dry_run: true })];

      render(<HistoryList jobs={jobs} />);

      expect(screen.getByText("Dry run")).toBeInTheDocument();
    });

    it("should not display 'Dry run' badge for normal jobs", () => {
      const jobs: JobSummary[] = [createMockJob({ id: "job-001", is_dry_run: false })];

      render(<HistoryList jobs={jobs} />);

      expect(screen.queryByText("Dry run")).not.toBeInTheDocument();
    });
  });

  describe("shows partial badge", () => {
    it("should display 'Partial' badge for partial-run jobs", () => {
      const jobs: JobSummary[] = [
        createMockJob({
          id: "job-001",
          row_subset_mode: "first_n",
          row_subset_n: 50,
        }),
      ];

      render(<HistoryList jobs={jobs} />);

      expect(screen.getByText("Partial")).toBeInTheDocument();
    });

    it("should not display 'Partial' badge for all-row jobs", () => {
      const jobs: JobSummary[] = [
        createMockJob({
          id: "job-001",
          row_subset_mode: "all",
          row_subset_n: null,
        }),
      ];

      render(<HistoryList jobs={jobs} />);

      expect(screen.queryByText("Partial")).not.toBeInTheDocument();
    });
  });
});
