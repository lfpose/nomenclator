/**
 * Tests for PreviewPanel component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PreviewPanel } from "../src/components/PreviewPanel";
import type { PreviewResponse } from "../src/lib/jobs-api";
import { jobsApi } from "../src/lib/jobs-api";

describe("PreviewPanel", () => {
  const mockPreviewSuccess: PreviewResponse = {
    job_id: "test-job-id",
    total_rows: 100,
    exact_unique_rows: 80,
    cluster_count: 60,
    largest_cluster_size: 10,
    est_cost_usd: 0.15,
    top_clusters: [
      {
        cluster_id: 1,
        representative_original: "Jefe de Compras",
        normalized_key: "jefe compras",
        member_count: 10,
        members: [
          { cluster_id: 1, row_index: 0, original: "Jefe de Compras", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 1, original: "jefe de compras", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 2, original: "Jefe De Compras", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 3, original: "JEFE DE COMPRAS", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 4, original: "jefe de compras", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 5, original: "jefe de compras", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 6, original: "jefe de compras", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 7, original: "Jefe de Compras", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 8, original: "jefe de compras", normalized: "jefe compras" },
          { cluster_id: 1, row_index: 9, original: "Jefe de Compras", normalized: "jefe compras" },
        ],
      },
      {
        cluster_id: 2,
        representative_original: "Ingeniero de Software",
        normalized_key: "ingeniero software",
        member_count: 5,
        members: [
          { cluster_id: 2, row_index: 10, original: "Ingeniero de Software", normalized: "ingeniero software" },
          { cluster_id: 2, row_index: 11, original: "ingeniero de software", normalized: "ingeniero software" },
          { cluster_id: 2, row_index: 12, original: "Ingeniero De Software", normalized: "ingeniero software" },
          { cluster_id: 2, row_index: 13, original: "ingeniero software", normalized: "ingeniero software" },
          { cluster_id: 2, row_index: 14, original: "Ingeniero de software", normalized: "ingeniero software" },
        ],
      },
    ],
    warnings: [],
  };

  const mockPreviewWithWarning: PreviewResponse = {
    ...mockPreviewSuccess,
    warnings: [{ type: "large_cluster", cluster_id: 1, size: 60 }],
  };

  const mockPreviewPartial: PreviewResponse = {
    ...mockPreviewSuccess,
    total_input_rows: 500,
    selected_rows: 100,
  };

  const mockInput = {
    file: new File(["test,csv,data"], "test.csv", { type: "text/csv" }),
  };

  const defaultProps = {
    input: mockInput,
    threshold: 90,
    titlesPerRequest: 25,
    taxonomy: "",
    promptOverride: "",
    rowSubsetMode: "all" as const,
    rowSubsetN: null,
    isDryRun: false,
    onPreviewSuccess: vi.fn(),
    onRecluster: vi.fn(), // This is the callback we should check
  };

  let onReclusterCallback: ReturnType<typeof vi.fn>;

  let mockPreview: ReturnType<typeof vi.fn>;
  let mockRecluster: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.resetAllMocks();
    mockPreview = vi.fn().mockResolvedValue(mockPreviewSuccess);
    mockRecluster = vi.fn().mockResolvedValue(mockPreviewSuccess);
    onReclusterCallback = vi.fn();
    // Mock the entire jobsApi object
    Object.assign(jobsApi, {
      ...jobsApi,
      preview: mockPreview,
      recluster: mockRecluster,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("button disabled until input is present", () => {
    const props = {
      ...defaultProps,
      input: undefined,
    };
    render(<PreviewPanel {...props} />);

    const button = screen.getByRole("button", { name: /preview clusters/i });
    expect(button).toBeDisabled();
  });

  it("shows counts and est cost after preview", async () => {
    const props = {
      ...defaultProps,
      input: mockInput,
    };
    render(<PreviewPanel {...props} />);

    const button = screen.getByRole("button", { name: /preview clusters/i });
    expect(button).not.toBeDisabled();

    await userEvent.click(button);

    await waitFor(() => {
      expect(mockPreview).toHaveBeenCalled();
    });

    // Check individual elements with more flexible queries
    expect(screen.getByText((text) => text.includes("100"))).toBeInTheDocument();
    expect(screen.getByText((text) => text.includes("80"))).toBeInTheDocument();
    expect(screen.getByText("60 clusters")).toBeInTheDocument();
    expect(screen.getByText((text) => text.includes("$0.15"))).toBeInTheDocument();
  });

  it("shows top 10 largest clusters", async () => {
    const props = {
      ...defaultProps,
      input: mockInput,
    };
    render(<PreviewPanel {...props} />);

    const button = screen.getByRole("button", { name: /preview clusters/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Jefe de Compras")).toBeInTheDocument();
      expect(screen.getByText("10 members")).toBeInTheDocument();
      expect(screen.getByText("Ingeniero de Software")).toBeInTheDocument();
      expect(screen.getByText("5 members")).toBeInTheDocument();
    });
  });

  it("large cluster warning badge shown when warnings present", async () => {
    mockPreview.mockResolvedValue(mockPreviewWithWarning);

    const props = {
      ...defaultProps,
      input: mockInput,
    };
    render(<PreviewPanel {...props} />);

    const button = screen.getByRole("button", { name: /preview clusters/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/large cluster/i)).toBeInTheDocument();
    });
  });

  it("re-cluster calls API with new threshold", async () => {
    const props = {
      ...defaultProps,
      input: mockInput,
      threshold: 85,
      onRecluster: onReclusterCallback,
    };
    render(<PreviewPanel {...props} />);

    const button = screen.getByRole("button", { name: /preview clusters/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Jefe de Compras")).toBeInTheDocument();
    });

    const reclusterButton = screen.getByRole("button", { name: /re-cluster/i });
    await userEvent.click(reclusterButton);

    expect(onReclusterCallback).toHaveBeenCalledWith(85);
  });

  it("shows API error on preview failure", async () => {
    mockPreview.mockRejectedValue(new Error("API Error"));

    const props = {
      ...defaultProps,
      input: mockInput,
    };
    render(<PreviewPanel {...props} />);

    const button = screen.getByRole("button", { name: /preview clusters/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/api error/i)).toBeInTheDocument();
    });
  });

  it("shows selected rows count for partial runs", async () => {
    mockPreview.mockResolvedValue(mockPreviewPartial);

    const props = {
      ...defaultProps,
      input: mockInput,
      rowSubsetMode: "first_n" as const,
      rowSubsetN: 100,
    };
    render(<PreviewPanel {...props} />);

    const button = screen.getByRole("button", { name: /preview clusters/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/500/)).toBeInTheDocument();
      expect(screen.getByText(/100 selected/)).toBeInTheDocument();
      expect(screen.getByText("60 clusters")).toBeInTheDocument();
      expect(screen.getByText(/\$0\.15/i)).toBeInTheDocument();
    });
  });
});
