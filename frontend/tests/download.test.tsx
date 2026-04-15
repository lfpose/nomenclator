import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DownloadButton } from "../src/components/DownloadButton";

describe("DownloadButton", () => {
  it("button href is /jobs/:id/download", () => {
    render(<DownloadButton jobId="test-job-id" status="completed" />);
    const link = screen.getByRole("link", { name: /download csv/i });
    expect(link).toHaveAttribute("href", "/jobs/test-job-id/download");
  });

  it("button hidden when not completed", () => {
    const { container } = render(<DownloadButton jobId="test-job-id" status="running" />);
    const link = container.querySelector('a[href="/jobs/test-job-id/download"]');
    expect(link).toBeNull();
  });

  it("button has download attribute", () => {
    render(<DownloadButton jobId="test-job-id" status="completed" />);
    const link = screen.getByRole("link", { name: /download csv/i });
    expect(link).toHaveAttribute("download");
  });
});
