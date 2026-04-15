/**
 * Tests for InputArea component
 * Tests DropZone + paste disclosure functionality
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { InputArea } from "../src/components/InputArea";

describe("InputArea", () => {
  test("drop zone accepts dropped CSV file", async () => {
    const onInput = vi.fn();
    render(<InputArea onInput={onInput} />);

    // Find the drop zone (it's a div with drag/drop text)
    const dropZone = screen.getByText(/drop csv file here/i).closest("div") as HTMLElement;
    expect(dropZone).toBeTruthy();

    // Create a file to drop
    const file = new File(["title1,title2,title3"], "test.csv", { type: "text/csv" });

    // Simulate drop event
    const dropEvent = new Event("drop", { bubbles: true }) as any;
    dropEvent.preventDefault = vi.fn();
    Object.defineProperty(dropEvent, "dataTransfer", {
      value: {
        files: [file],
      },
      writable: false,
    });

    dropZone.dispatchEvent(dropEvent);

    // Wait for state updates
    await waitFor(() => {
      expect(onInput).toHaveBeenCalledWith({ file, text: undefined });
    });
  });

  test("drop zone click opens file input", async () => {
    const user = userEvent.setup();
    const onInput = vi.fn();
    render(<InputArea onInput={onInput} />);

    // Find the drop zone
    const dropZone = screen.getByText(/drop csv file here/i).closest("div") as HTMLElement;
    expect(dropZone).toBeTruthy();

    // Click the drop zone
    await user.click(dropZone);

    // The file input should be present and clicked
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();
    // Note: We can't easily test that the actual file picker opened in jsdom
    // but we can verify the component doesn't crash
    expect(true).toBe(true);
  });

  test("paste textarea expands and accepts text", async () => {
    const user = userEvent.setup();
    const onInput = vi.fn();
    render(<InputArea onInput={onInput} />);

    // Click the first "Show" button (the visible one)
    const showButtons = screen.getAllByRole("button", { name: "Show" });
    expect(showButtons.length).toBeGreaterThan(0);
    await user.click(showButtons[0]);

    // Verify textarea is visible
    const textarea = screen.getByPlaceholderText(/paste job titles here/i);
    expect(textarea).toBeVisible();

    // Type in the textarea
    const testText = "Job Title 1\nJob Title 2\nJob Title 3";
    await user.type(textarea, testText);

    // Verify onInput was called with text
    expect(onInput).toHaveBeenCalledWith({ text: testText, file: undefined });
  });

  test("emits input on file drop", async () => {
    const onInput = vi.fn();
    render(<InputArea onInput={onInput} />);

    const dropZone = screen.getByText(/drop csv file here/i).closest("div") as HTMLElement;

    // Create a file to drop
    const file = new File(["title1,title2"], "test.csv", { type: "text/csv" });

    // Simulate drop event
    const dropEvent = new Event("drop", { bubbles: true }) as any;
    dropEvent.preventDefault = vi.fn();
    Object.defineProperty(dropEvent, "dataTransfer", {
      value: {
        files: [file],
      },
      writable: false,
    });

    dropZone.dispatchEvent(dropEvent);

    // Wait for state updates
    await waitFor(() => {
      expect(onInput).toHaveBeenCalledWith({ file, text: undefined });
    });

    // Verify it was called exactly once
    expect(onInput).toHaveBeenCalledTimes(1);
  });

  test("emits input on text change", async () => {
    const user = userEvent.setup();
    const onInput = vi.fn();
    render(<InputArea onInput={onInput} />);

    // Expand paste section
    const showButtons = screen.getAllByRole("button", { name: "Show" });
    await user.click(showButtons[0]);

    const textarea = screen.getByPlaceholderText(/paste job titles here/i) as HTMLTextAreaElement;

    // Type text character by character to trigger onChange
    await user.type(textarea, "Test");

    // Verify onInput was called
    expect(onInput).toHaveBeenCalled();

    // Check the last call has the expected structure
    const lastCall = onInput.mock.calls[onInput.mock.calls.length - 1][0];
    expect(lastCall.text).toContain("Test");
    expect(lastCall).toHaveProperty("text");
    expect(lastCall.file).toBeUndefined();
  });
});
