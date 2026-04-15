import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PromptReviewPanel } from "../src/components/PromptReviewPanel";
import { api } from "../src/lib/api";

// Mock the api module
vi.mock("../src/lib/api", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    postForm: vi.fn(),
  },
}));

describe("PromptReviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("button calls review API with prompt and few_shots", async () => {
    const mockResponse = {
      safe: true,
      quality_score: "good",
      issues: [],
      suggestions: [],
      summary: "Looks good",
    };

    vi.mocked(api.post).mockResolvedValue(mockResponse);

    render(
      <PromptReviewPanel
        prompt="Test prompt"
        fewShots="[]"
      />
    );

    const button = screen.getByRole("button", { name: /review prompt/i });
    await userEvent.click(button);

    expect(api.post).toHaveBeenCalledWith("/jobs/review-prompt", {
      prompt: "Test prompt",
      few_shots: "[]",
    });
  });

  it("shows review card on success", async () => {
    vi.mocked(api.post).mockResolvedValue({
      safe: true,
      quality_score: "good",
      issues: [],
      suggestions: [],
      summary: "Looks good",
    });

    render(
      <PromptReviewPanel
        prompt="Test prompt"
        fewShots="[]"
      />
    );

    const button = screen.getByRole("button", { name: /review prompt/i });
    await userEvent.click(button);

    await expect(screen.findByText("Looks good")).toBeInTheDocument();
  });

  it("shows quality score badge", async () => {
    vi.mocked(api.post).mockResolvedValue({
      safe: true,
      quality_score: "good",
      issues: [],
      suggestions: [],
      summary: "Looks good",
    });

    render(
      <PromptReviewPanel
        prompt="Test prompt"
        fewShots="[]"
      />
    );

    const button = screen.getByRole("button", { name: /review prompt/i });
    await userEvent.click(button);

    await expect(screen.findByText("good")).toBeInTheDocument();
  });

  it("shows issues list", async () => {
    vi.mocked(api.post).mockResolvedValue({
      safe: true,
      quality_score: "good",
      issues: ["Issue 1", "Issue 2"],
      suggestions: [],
      summary: "Looks good",
    });

    render(
      <PromptReviewPanel
        prompt="Test prompt"
        fewShots="[]"
      />
    );

    const button = screen.getByRole("button", { name: /review prompt/i });
    await userEvent.click(button);

    await expect(screen.findByText("Issues")).toBeInTheDocument();
    await expect(screen.findByText("Issue 1")).toBeInTheDocument();
    await expect(screen.findByText("Issue 2")).toBeInTheDocument();
  });

  it("shows suggestions list", async () => {
    vi.mocked(api.post).mockResolvedValue({
      safe: true,
      quality_score: "good",
      issues: [],
      suggestions: ["Suggestion 1", "Suggestion 2"],
      summary: "Looks good",
    });

    render(
      <PromptReviewPanel
        prompt="Test prompt"
        fewShots="[]"
      />
    );

    const button = screen.getByRole("button", { name: /review prompt/i });
    await userEvent.click(button);

    await expect(screen.findByText("Suggestions")).toBeInTheDocument();
    await expect(screen.findByText("Suggestion 1")).toBeInTheDocument();
    await expect(screen.findByText("Suggestion 2")).toBeInTheDocument();
  });

  it("button text changes to Re-review after first use", async () => {
    vi.mocked(api.post).mockResolvedValue({
      safe: true,
      quality_score: "good",
      issues: [],
      suggestions: [],
      summary: "Looks good",
    });

    render(
      <PromptReviewPanel
        prompt="Test prompt"
        fewShots="[]"
      />
    );

    const button = screen.getByRole("button", { name: /review prompt/i });
    expect(button).toHaveTextContent("Review Prompt");

    await userEvent.click(button);

    await expect(screen.findByText("Looks good")).toBeInTheDocument();
    expect(button).toHaveTextContent("Re-review");
  });

  it("shows error on API failure without blocking", async () => {
    vi.mocked(api.post).mockRejectedValue(
      new Error("API failed")
    );

    render(
      <PromptReviewPanel
        prompt="Test prompt"
        fewShots="[]"
      />
    );

    const button = screen.getByRole("button", { name: /review prompt/i });
    await userEvent.click(button);

    await expect(screen.findByText("API failed")).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });
});
