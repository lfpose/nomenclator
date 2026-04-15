import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DropZone } from "../src/components/DropZone";

describe("DropZone", () => {
  it("handles file drop event", () => {
    const onFile = vi.fn();
    const { container } = render(<DropZone onFile={onFile} />);

    const dropZone = container.querySelector("div");
    expect(dropZone).toBeDefined();

    const file = new File(["content"], "test.csv", { type: "text/csv" });

    if (dropZone) {
      fireEvent.drop(dropZone, {
        dataTransfer: { files: [file] },
      } as unknown as React.DragEvent<HTMLDivElement>);
    }

    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("click opens file picker", () => {
    const onFile = vi.fn();
    render(<DropZone onFile={onFile} />);

    const dropZone = screen.getByText(/drop csv file here/i).closest("div");
    expect(dropZone).toBeDefined();

    if (dropZone) {
      fireEvent.click(dropZone);
    }

    const fileInput = document.querySelector('input[type="file"]');
    expect(fileInput).toBeDefined();
  });

  it("shows drag-over visual state", () => {
    const onFile = vi.fn();
    const { container } = render(<DropZone onFile={onFile} />);

    const dropZone = container.querySelector("div");
    expect(dropZone).toBeDefined();

    expect(dropZone).not.toHaveClass("border-primary", "bg-primary/5");

    if (dropZone) {
      fireEvent.dragOver(dropZone);
    }

    expect(dropZone).toHaveClass("border-primary", "bg-primary/5");

    if (dropZone) {
      fireEvent.dragLeave(dropZone);
    }

    expect(dropZone).not.toHaveClass("border-primary", "bg-primary/5");
  });

  it("calls onFile callback with dropped file", () => {
    const onFile = vi.fn();
    const { container } = render(<DropZone onFile={onFile} />);

    const dropZone = container.querySelector("div");
    expect(dropZone).toBeDefined();

    const file = new File(["data"], "test.csv", { type: "text/csv" });

    if (dropZone) {
      fireEvent.drop(dropZone, {
        dataTransfer: { files: [file] },
      } as unknown as React.DragEvent<HTMLDivElement>);
    }

    expect(onFile).toHaveBeenCalledTimes(1);
    expect(onFile).toHaveBeenCalledWith(file);
    expect(onFile.mock.calls[0][0]).toBeInstanceOf(File);
    expect(onFile.mock.calls[0][0].name).toBe("test.csv");
  });
});
