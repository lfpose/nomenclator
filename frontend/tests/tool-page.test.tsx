/**
 * Tests for Tool page (index route)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import IndexRoute from "../src/routes/index";
import { jobsApi } from "../src/lib/jobs-api";
import { useToolForm } from "@/hooks/useToolForm";
import { useNotification } from "@/hooks/useNotification";

// Mock all the hooks and components
vi.mock("@/hooks/useToolForm");
vi.mock("@/hooks/useNotification");
vi.mock("@/lib/jobs-api");

vi.mock("@/components/InputArea", () => ({
  InputArea: ({ onInput }: { onInput: (input: any) => void }) => (
    <div data-testid="input-area">
      <button
        onClick={() => onInput({ file: new File(["test"], "test.csv") })}
      >
        Upload CSV
      </button>
    </div>
  ),
}));

vi.mock("@/components/TaxonomyInput", () => ({
  TaxonomyInput: ({ label }: { label: string }) => (
    <div data-testid="taxonomy-input">{label}</div>
  ),
}));

vi.mock("@/components/AdvancedPanel", () => ({
  AdvancedPanel: () => <div data-testid="advanced-panel">Advanced</div>,
}));

vi.mock("@/components/JobStatusPanel", () => ({
  JobStatusPanel: ({ jobId }: { jobId: string }) => (
    <div data-testid="job-status-panel">{jobId}</div>
  ),
}));

vi.mock("@/components/HistoryList", () => ({
  HistoryList: ({ jobs }: { jobs: any[] }) => (
    <div data-testid="history-list">{jobs.length} jobs</div>
  ),
}));

describe("Tool page", () => {
  beforeEach(() => {
    vi.resetAllMocks();

    // Default mock for useNotification
    vi.mocked(useNotification).mockReturnValue({
      hasRequestedPermission: false,
      requestPermission: vi.fn(),
      notifyJobTerminal: vi.fn(),
    } as any);

    // Default mock for jobsApi.list
    vi.mocked(jobsApi.list).mockResolvedValue({ jobs: [] });
  });

  it("shows only form in idle state", async () => {
    vi.mocked(useToolForm).mockReturnValue({
      state: {
        toolState: { kind: "idle" as const },
        row_subset_mode: "all" as const,
        row_subset_n: null,
        is_dry_run: false,
      },
      loadInput: vi.fn(),
      startPreview: vi.fn(),
      previewSuccess: vi.fn(),
      startRecluster: vi.fn(),
      reclusterSuccess: vi.fn(),
      startCommit: vi.fn(),
      commitSuccess: vi.fn(),
      pollUpdate: vi.fn(),
      pollFailed: vi.fn(),
      pollCancelled: vi.fn(),
      reset: vi.fn(),
    } as any);

    render(<IndexRoute />);

    // Check for form elements
    expect(screen.getByTestId("input-area")).toBeInTheDocument();
    expect(screen.getByTestId("taxonomy-input")).toBeInTheDocument();
    expect(screen.getByTestId("advanced-panel")).toBeInTheDocument();

    // Check that preview panel and status panel are NOT shown
    expect(screen.queryByTestId("job-status-panel")).not.toBeInTheDocument();
  });

  it("shows preview panel after preview success", async () => {
    const previewResponse = {
      job_id: "test-job-id",
      total_rows: 100,
      exact_unique_rows: 80,
      cluster_count: 20,
      largest_cluster_size: 10,
      est_cost_usd: 0.25,
      top_clusters: [
        {
          cluster_id: 1,
          representative_original: "Test Job",
          normalized_key: "test job",
          member_count: 10,
          members: [],
        },
      ],
      warnings: [],
    };

    vi.mocked(useToolForm).mockReturnValue({
      state: {
        toolState: {
          kind: "previewed" as const,
          preview: previewResponse,
        },
        row_subset_mode: "all" as const,
        row_subset_n: null,
        is_dry_run: false,
      },
      loadInput: vi.fn(),
      startPreview: vi.fn(),
      previewSuccess: vi.fn(),
      startRecluster: vi.fn(),
      reclusterSuccess: vi.fn(),
      startCommit: vi.fn(),
      commitSuccess: vi.fn(),
      pollUpdate: vi.fn(),
      pollFailed: vi.fn(),
      pollCancelled: vi.fn(),
      reset: vi.fn(),
    } as any);

    render(<IndexRoute />);

    // Check for preview elements
    expect(screen.getByText(/100/)).toBeInTheDocument();
    expect(screen.getByText(/80 uniques/)).toBeInTheDocument();
    expect(screen.getByText(/20 clusters/)).toBeInTheDocument();
    expect(screen.getByText(/est \$0.25/)).toBeInTheDocument();
    expect(screen.getByText("Test Job")).toBeInTheDocument();
    expect(screen.getByText("10 members")).toBeInTheDocument();

    // Check for action buttons
    expect(screen.getByRole("button", { name: /re-cluster/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit job/i })).toBeInTheDocument();
  });

  it("shows status panel after commit", async () => {
    vi.mocked(useToolForm).mockReturnValue({
      state: {
        toolState: {
          kind: "running" as const,
          jobId: "test-job-id",
        },
        row_subset_mode: "all" as const,
        row_subset_n: null,
        is_dry_run: false,
      },
      loadInput: vi.fn(),
      startPreview: vi.fn(),
      previewSuccess: vi.fn(),
      startRecluster: vi.fn(),
      reclusterSuccess: vi.fn(),
      startCommit: vi.fn(),
      commitSuccess: vi.fn(),
      pollUpdate: vi.fn(),
      pollFailed: vi.fn(),
      pollCancelled: vi.fn(),
      reset: vi.fn(),
    } as any);

    render(<IndexRoute />);

    // Check for job status panel
    expect(screen.getByTestId("job-status-panel")).toBeInTheDocument();
    expect(screen.getByTestId("job-status-panel")).toHaveTextContent("test-job-id");

    // Check that preview elements are NOT shown
    expect(screen.queryByRole("button", { name: /re-cluster/i })).not.toBeInTheDocument();
  });

  it("shows history below form at all times", async () => {
    const mockJobs = [
      {
        id: "job-1",
        status: "completed",
        created_at: "2024-01-01T00:00:00Z",
        total_rows: 100,
        cluster_count: 20,
        est_cost_usd: 0.25,
        actual_cost_usd: 0.23,
        finished_at: "2024-01-01T00:05:00Z",
        fuzzy_threshold: 90,
        titles_per_request: 25,
        row_subset_mode: null,
        row_subset_n: null,
        is_dry_run: false,
      },
      {
        id: "job-2",
        status: "failed",
        created_at: "2024-01-02T00:00:00Z",
        total_rows: 50,
        cluster_count: 10,
        est_cost_usd: 0.12,
        actual_cost_usd: 0,
        finished_at: null,
        fuzzy_threshold: 85,
        titles_per_request: 20,
        row_subset_mode: null,
        row_subset_n: null,
        is_dry_run: false,
      },
    ];

    vi.mocked(jobsApi.list).mockResolvedValue({ jobs: mockJobs });

    vi.mocked(useToolForm).mockReturnValue({
      state: {
        toolState: { kind: "idle" as const },
        row_subset_mode: "all" as const,
        row_subset_n: null,
        is_dry_run: false,
      },
      loadInput: vi.fn(),
      startPreview: vi.fn(),
      previewSuccess: vi.fn(),
      startRecluster: vi.fn(),
      reclusterSuccess: vi.fn(),
      startCommit: vi.fn(),
      commitSuccess: vi.fn(),
      pollUpdate: vi.fn(),
      pollFailed: vi.fn(),
      pollCancelled: vi.fn(),
      reset: vi.fn(),
    } as any);

    render(<IndexRoute />);

    // Wait for jobs to load
    await waitFor(() => {
      expect(screen.getByTestId("history-list")).toBeInTheDocument();
    });

    expect(screen.getByTestId("history-list")).toHaveTextContent("2 jobs");
    expect(screen.getByText("Job history")).toBeInTheDocument();
  });

  it("shows spend footer", async () => {
    vi.mocked(useToolForm).mockReturnValue({
      state: {
        toolState: { kind: "idle" as const },
        row_subset_mode: "all" as const,
        row_subset_n: null,
        is_dry_run: false,
      },
      loadInput: vi.fn(),
      startPreview: vi.fn(),
      previewSuccess: vi.fn(),
      startRecluster: vi.fn(),
      reclusterSuccess: vi.fn(),
      startCommit: vi.fn(),
      commitSuccess: vi.fn(),
      pollUpdate: vi.fn(),
      pollFailed: vi.fn(),
      pollCancelled: vi.fn(),
      reset: vi.fn(),
    } as any);

    render(<IndexRoute />);

    // Check for footer - use getAllByText since "Nomenclator" appears in header too
    const nomenclatorElements = screen.getAllByText(/nomenclator/i);
    expect(nomenclatorElements.length).toBeGreaterThan(0);

    // Check for footer-specific text
    expect(screen.getByText(/v1\.0/i)).toBeInTheDocument();
    expect(screen.getByText(/built for a single operator/i)).toBeInTheDocument();
    expect(screen.getByText(/quis custodiet ipsos custodes\?/i)).toBeInTheDocument();

    // Check that there's a footer element
    const footer = document.querySelector("footer");
    expect(footer).toBeInTheDocument();
    expect(footer).toHaveTextContent(/Nomenclator · v1\.0 · built for a single operator · quis custodiet ipsos custodes\?/i);
  });
});
