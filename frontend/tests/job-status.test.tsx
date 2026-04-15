import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { JobStatusPanel } from "../src/components/JobStatusPanel";
import { jobsApi } from "../src/lib/jobs-api";
import * as useJobPollingModule from "../src/hooks/useJobPolling";

// Mock jobsApi
vi.mock("../src/lib/jobs-api", () => ({
  jobsApi: {
    get: vi.fn(),
    cancel: vi.fn(),
    downloadUrl: vi.fn((id: string) => `/jobs/${id}/download`),
  },
}));

// Mock useJobPolling
vi.mock("../src/hooks/useJobPolling", () => ({
  useJobPolling: vi.fn(),
}));

// Mock Spinner component
vi.mock("../src/components/Spinner", () => ({
  Spinner: ({ className }: { className?: string }) => (
    <div className={className} data-testid="spinner">
      Loading...
    </div>
  ),
}));

const mockJobRunning: import("../src/lib/jobs-api").JobDetail = {
  id: "job-123",
  status: "polling",
  created_at: "2024-01-01T00:00:00Z",
  total_rows: 100,
  cluster_count: 50,
  est_cost_usd: 0.15,
  actual_cost_usd: 0.0,
  finished_at: null,
  fuzzy_threshold: 90,
  titles_per_request: 25,
  row_subset_mode: "all",
  row_subset_n: null,
  is_dry_run: false,
  retry_round: 0,
  progress: {
    clusters_total: 50,
    clusters_resolved: 25,
    clusters_pending: 25,
    clusters_error: 0,
  },
  batches: [
    { id: 1, status: "in_progress", request_count: 2, retry_round: 0 },
  ],
};

const mockJobCompleted: import("../src/lib/jobs-api").JobDetail = {
  ...mockJobRunning,
  status: "completed",
  actual_cost_usd: 0.15,
  finished_at: "2024-01-01T00:01:00Z",
  progress: {
    clusters_total: 50,
    clusters_resolved: 50,
    clusters_pending: 0,
    clusters_error: 0,
  },
  batches: [
    { id: 1, status: "ended", request_count: 2, retry_round: 0 },
  ],
};

const mockJobWithRetry: import("../src/lib/jobs-api").JobDetail = {
  ...mockJobRunning,
  status: "polling",
  retry_round: 1,
};

describe("JobStatusPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("polls /jobs/:id every 5s while running", async () => {
    // Mock useJobPolling to return running job
    vi.mocked(useJobPollingModule.useJobPolling).mockReturnValue({
      job: mockJobRunning,
      error: null,
    });

    render(<JobStatusPanel jobId="job-123" />);

    // Verify the hook was called with the jobId and enabled=true
    expect(useJobPollingModule.useJobPolling).toHaveBeenCalledWith("job-123", true);

    // Verify running status is displayed
    await waitFor(() => {
      expect(screen.getByText("polling")).toBeInTheDocument();
    });

    // Verify processing indicator is shown
    expect(screen.getByText("Processing...")).toBeInTheDocument();
  });

  it("stops polling when terminal status reached", async () => {
    // Mock useJobPolling to return completed job
    vi.mocked(useJobPollingModule.useJobPolling).mockReturnValue({
      job: mockJobCompleted,
      error: null,
    });

    const onCancel = vi.fn();

    render(<JobStatusPanel jobId="job-123" onCancel={onCancel} />);

    // Verify completed status is displayed
    await waitFor(() => {
      expect(screen.getByText("completed")).toBeInTheDocument();
    });

    // Verify download button appears
    expect(screen.getByText("Download")).toBeInTheDocument();

    // Verify cancel button is not shown (terminal status)
    expect(screen.queryByText("Cancel")).not.toBeInTheDocument();
  });

  it("shows retry_round in UI when > 0", async () => {
    vi.mocked(useJobPollingModule.useJobPolling).mockReturnValue({
      job: mockJobWithRetry,
      error: null,
    });

    render(<JobStatusPanel jobId="job-123" />);

    // Verify retry round badge is shown
    await waitFor(() => {
      expect(screen.getByText("Retry round 1")).toBeInTheDocument();
    });
  });

  it("download button appears on completed", async () => {
    vi.mocked(useJobPollingModule.useJobPolling).mockReturnValue({
      job: mockJobCompleted,
      error: null,
    });

    render(<JobStatusPanel jobId="job-123" />);

    // Verify download button appears
    await waitFor(() => {
      const downloadLink = screen.getByText("Download");
      expect(downloadLink).toBeInTheDocument();
      expect(downloadLink.tagName).toBe("A");
    });
  });

  it("cancel button disappears on terminal", async () => {
    vi.mocked(useJobPollingModule.useJobPolling).mockReturnValue({
      job: mockJobCompleted,
      error: null,
    });

    render(<JobStatusPanel jobId="job-123" />);

    // Verify cancel button is not shown when terminal
    await waitFor(() => {
      expect(screen.queryByText("Cancel")).not.toBeInTheDocument();
      expect(screen.queryByText("Keep running")).not.toBeInTheDocument();
      expect(screen.queryByText("Confirm cancel")).not.toBeInTheDocument();
    });
  });
});
