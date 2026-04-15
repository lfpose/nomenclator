/**
 * Tests for TaxonomyInput component
 * Tests controlled textarea with placeholder, label, and optional value
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { TaxonomyInput } from "../src/components/TaxonomyInput";

describe("TaxonomyInput", () => {
  test("renders with default placeholder", () => {
    const onChange = vi.fn();
    render(<TaxonomyInput onChange={onChange} />);

    // Check default placeholder
    const textarea = screen.getByPlaceholderText(/enter optional taxonomy/i);
    expect(textarea).toBeInTheDocument();
    expect(textarea).toBeVisible();
  });

  test("accepts multiline input", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TaxonomyInput onChange={onChange} />);

    const textarea = screen.getByPlaceholderText(/enter optional taxonomy/i) as HTMLTextAreaElement;

    // Type multiline input
    const multilineText = "Category 1\nCategory 2\nCategory 3";
    await user.type(textarea, multilineText);

    // Verify onChange was called for each character
    expect(onChange).toHaveBeenCalled();

    // Verify the last call has the full multiline text
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall).toBe(multilineText);

    // Verify textarea value contains line breaks
    expect(textarea.value).toBe(multilineText);
  });

  test("emits change events", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <TaxonomyInput
        onChange={onChange}
        label="Custom Label"
        placeholder="Custom placeholder"
      />
    );

    // Verify label is rendered
    const label = screen.getByText("Custom Label");
    expect(label).toBeInTheDocument();

    // Verify custom placeholder
    const textarea = screen.getByPlaceholderText("Custom placeholder");
    expect(textarea).toBeInTheDocument();

    // Type in textarea
    await user.type(textarea as HTMLTextAreaElement, "Test taxonomy");

    // Verify onChange was called for each character
    expect(onChange).toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledTimes(13); // One call per character

    // Verify the last call has the correct value
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall).toBe("Test taxonomy");
  });
});
