/**
 * Tests for useToolForm hook
 * Tests the Tool page's form state machine
 */

import { describe, expect, test } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useToolForm } from "../src/hooks/useToolForm";

describe("useToolForm", () => {
  test("idle → input_loaded on file set", () => {
    const { result } = renderHook(() => useToolForm());

    // Initial state should be idle
    expect(result.current.state.toolState.kind).toBe("idle");

    // Load input with file
    act(() => {
      result.current.loadInput({
        file: new File(["data"], "test.csv", { type: "text/csv" }),
      });
    });

    // State should now be input_loaded
    expect(result.current.state.toolState.kind).toBe("input_loaded");
    if (result.current.state.toolState.kind === "input_loaded") {
      expect(result.current.state.toolState.input.file).toBeDefined();
    }
  });

  test("input_loaded → previewing → previewed on API success", () => {
    const { result } = renderHook(() => useToolForm());

    // Load input
    act(() => {
      result.current.loadInput({
        file: new File(["data"], "test.csv", { type: "text/csv" }),
      });
    });

    // Start preview
    act(() => {
      result.current.startPreview();
    });

    expect(result.current.state.toolState.kind).toBe("previewing");

    // Preview success
    act(() => {
      result.current.previewSuccess({
        job_id: "abc123",
        total_rows: 100,
        exact_unique_rows: 95,
        cluster_count: 50,
        largest_cluster_size: 10,
        est_cost_usd: 0.25,
        top_clusters: [],
        warnings: [],
      });
    });

    expect(result.current.state.toolState.kind).toBe("previewed");
  });

  test("previewed → reclustering → previewed on threshold change", () => {
    const { result } = renderHook(() => useToolForm());

    // Set up previewed state
    act(() => {
      result.current.loadInput({
        file: new File(["data"], "test.csv", { type: "text/csv" }),
      });
      result.current.startPreview();
      result.current.previewSuccess({
        job_id: "abc123",
        total_rows: 100,
        exact_unique_rows: 95,
        cluster_count: 50,
        largest_cluster_size: 10,
        est_cost_usd: 0.25,
        top_clusters: [],
        warnings: [],
      });
    });

    expect(result.current.state.toolState.kind).toBe("previewed");

    // Start recluster
    act(() => {
      result.current.startRecluster();
    });

    expect(result.current.state.toolState.kind).toBe("reclustering");

    // Recluster success
    act(() => {
      result.current.reclusterSuccess({
        job_id: "abc123",
        total_rows: 100,
        exact_unique_rows: 95,
        cluster_count: 45, // Different cluster count after recluster
        largest_cluster_size: 12,
        est_cost_usd: 0.23,
        top_clusters: [],
        warnings: [],
      });
    });

    expect(result.current.state.toolState.kind).toBe("previewed");
  });

  test("previewed → submitting → running on commit", () => {
    const { result } = renderHook(() => useToolForm());

    // Set up previewed state
    act(() => {
      result.current.loadInput({
        file: new File(["data"], "test.csv", { type: "text/csv" }),
      });
      result.current.startPreview();
      result.current.previewSuccess({
        job_id: "abc123",
        total_rows: 100,
        exact_unique_rows: 95,
        cluster_count: 50,
        largest_cluster_size: 10,
        est_cost_usd: 0.25,
        top_clusters: [],
        warnings: [],
      });
    });

    // Start commit
    act(() => {
      result.current.startCommit();
    });

    expect(result.current.state.toolState.kind).toBe("submitting");

    // Commit success
    act(() => {
      result.current.commitSuccess("abc123");
    });

    expect(result.current.state.toolState.kind).toBe("running");
    if (result.current.state.toolState.kind === "running") {
      expect(result.current.state.toolState.jobId).toBe("abc123");
    }
  });

  test("running → completed when poll returns completed", () => {
    const { result } = renderHook(() => useToolForm());

    // Set up running state
    act(() => {
      result.current.loadInput({
        file: new File(["data"], "test.csv", { type: "text/csv" }),
      });
      result.current.startPreview();
      result.current.previewSuccess({
        job_id: "abc123",
        total_rows: 100,
        exact_unique_rows: 95,
        cluster_count: 50,
        largest_cluster_size: 10,
        est_cost_usd: 0.25,
        top_clusters: [],
        warnings: [],
      });
      result.current.startCommit();
      result.current.commitSuccess("abc123");
    });

    expect(result.current.state.toolState.kind).toBe("running");

    // Poll update with completed status
    act(() => {
      result.current.pollUpdate({
        id: "abc123",
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
      });
    });

    expect(result.current.state.toolState.kind).toBe("completed");
  });

  test("running → failed when poll returns failed", () => {
    const { result } = renderHook(() => useToolForm());

    // Set up running state
    act(() => {
      result.current.loadInput({
        file: new File(["data"], "test.csv", { type: "text/csv" }),
      });
      result.current.startPreview();
      result.current.previewSuccess({
        job_id: "abc123",
        total_rows: 100,
        exact_unique_rows: 95,
        cluster_count: 50,
        largest_cluster_size: 10,
        est_cost_usd: 0.25,
        top_clusters: [],
        warnings: [],
      });
      result.current.startCommit();
      result.current.commitSuccess("abc123");
    });

    expect(result.current.state.toolState.kind).toBe("running");

    // Poll failed
    act(() => {
      result.current.pollFailed("abc123", "Job failed due to API error");
    });

    expect(result.current.state.toolState.kind).toBe("failed");
    if (result.current.state.toolState.kind === "failed") {
      expect(result.current.state.toolState.jobId).toBe("abc123");
      expect(result.current.state.toolState.message).toBe("Job failed due to API error");
    }
  });

  test("reviewing_prompt state on review click", () => {
    const { result } = renderHook(() => useToolForm());

    // Start review prompt
    act(() => {
      result.current.startReviewPrompt();
    });

    expect(result.current.state.toolState.kind).toBe("reviewing_prompt");

    // Review prompt success - should return to same state
    act(() => {
      result.current.reviewPromptSuccess();
    });

    expect(result.current.state.toolState.kind).toBe("reviewing_prompt");
  });

  test("row subset state tracked", () => {
    const { result } = renderHook(() => useToolForm());

    // Initial state
    expect(result.current.state.row_subset_mode).toBe("all");
    expect(result.current.state.row_subset_n).toBe(null);

    // Change to first_n
    const newState1 = result.current.setRowSubsetMode("first_n");
    expect(newState1.row_subset_mode).toBe("first_n");
    expect(newState1.row_subset_n).toBe(null); // Should be null initially

    // Set row_subset_n
    const newState2 = result.current.setRowSubsetN(50);
    expect(newState2.row_subset_n).toBe(50);

    // Change to all - row_subset_n should be cleared
    const newState3 = result.current.setRowSubsetMode("all");
    expect(newState3.row_subset_mode).toBe("all");
    expect(newState3.row_subset_n).toBe(null);
  });

  test("dry run toggle tracked", () => {
    const { result } = renderHook(() => useToolForm());

    // Initial state
    expect(result.current.state.is_dry_run).toBe(false);

    // Enable dry run
    const newState1 = result.current.setDryRun(true);
    expect(newState1.is_dry_run).toBe(true);

    // Disable dry run
    const newState2 = result.current.setDryRun(false);
    expect(newState2.is_dry_run).toBe(false);
  });
});
