/**
 * Tests for SubmitButton component
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { SubmitButton } from "../src/components/SubmitButton";

// Mock the api module
vi.mock("../src/lib/api", async () => {
  const actual = await vi.importActual<typeof import("../src/lib/api")>("../src/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      post: vi.fn(),
    },
  };
});

import { api } from "../src/lib/api";

const mockPost = vi.mocked(api.post);

describe("SubmitButton", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("calls commit with prompt and taxonomy", async () => {
    mockPost.mockResolvedValue({
      job_id: "test-job-id",
      status: "submitted",
    });

    const onSubmit = vi.fn();
    const onError = vi.fn();

    render(
      <SubmitButton
        jobId="test-job-id"
        promptOverride="custom prompt"
        taxonomy={`category1\ncategory2`}
        titlesPerRequest={25}
        isDryRun={false}
        onSubmit={onSubmit}
        onError={onError}
      />
    );

    const button = screen.getByRole("button", { name: /submit job/i });
    button.click();

    await vi.waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/jobs/test-job-id/commit", {
        prompt_override: "custom prompt",
        taxonomy: "category1\ncategory2",
        titles_per_request: 25,
        is_dry_run: false,
      });
    });
  });

  it("transitions to running state on 202", async () => {
    mockPost.mockResolvedValue({
      job_id: "test-job-id",
      status: "submitted",
    });

    const onSubmit = vi.fn();
    const onError = vi.fn();

    render(
      <SubmitButton
        jobId="test-job-id"
        isDryRun={false}
        onSubmit={onSubmit}
        onError={onError}
      />
    );

    const button = screen.getByRole("button", { name: /submit job/i });
    button.click();

    await vi.waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith("test-job-id");
    });
  });

  it("shows spend_cap_exceeded error with reset date", async () => {
    const error = {
      code: "spend_cap_exceeded",
      message: "Monthly spend cap exceeded",
      status: 409,
      details: {
        error: {
          code: "spend_cap_exceeded",
          reset_date: "2026-05-15",
        },
      },
    };
    mockPost.mockRejectedValue(error);

    const onSubmit = vi.fn();
    const onError = vi.fn();

    render(
      <SubmitButton
        jobId="test-job-id"
        isDryRun={false}
        onSubmit={onSubmit}
        onError={onError}
      />
    );

    const button = screen.getByRole("button", { name: /submit job/i });
    button.click();

    await vi.waitFor(() => {
      expect(onError).toHaveBeenCalledWith(
        "Monthly spend cap exceeded",
        {
          code: "spend_cap_exceeded",
          resetDate: "2026-05-15",
        }
      );
    });
  });

  it("shows job_already_running error", async () => {
    const error = {
      code: "job_already_running",
      message: "Another job is already running",
      status: 409,
      details: {
        error: {
          code: "job_already_running",
        },
      },
    };
    mockPost.mockRejectedValue(error);

    const onSubmit = vi.fn();
    const onError = vi.fn();

    render(
      <SubmitButton
        jobId="test-job-id"
        isDryRun={false}
        onSubmit={onSubmit}
        onError={onError}
      />
    );

    const button = screen.getByRole("button", { name: /submit job/i });
    button.click();

    await vi.waitFor(() => {
      expect(onError).toHaveBeenCalledWith(
        "Another job is already running",
        {
          code: "job_already_running",
        }
      );
    });
  });

  it("sends is_dry_run when toggle is on", async () => {
    mockPost.mockResolvedValue({
      job_id: "test-job-id",
      status: "submitted",
    });

    const onSubmit = vi.fn();
    const onError = vi.fn();

    render(
      <SubmitButton
        jobId="test-job-id"
        isDryRun={true}
        onSubmit={onSubmit}
        onError={onError}
      />
    );

    const button = screen.getByRole("button", { name: /submit job/i });
    button.click();

    await vi.waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/jobs/test-job-id/commit", {
        is_dry_run: true,
      });
    });
  });
});
