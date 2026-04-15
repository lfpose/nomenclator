import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach } from "vitest";
import { ThemeToggle } from "@/components/ThemeToggle";

describe("ThemeToggle", () => {
  const originalMatchMedia = window.matchMedia;

  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Reset document class list
    document.documentElement.classList.remove("dark");
    // Mock matchMedia
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      media: "(prefers-color-scheme: dark)",
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });
  });

  afterEach(() => {
    // Restore original matchMedia
    window.matchMedia = originalMatchMedia;
  });

  test("applies dark class on toggle", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    // Initial state should not have dark class (mocked matchMedia returns false)
    expect(document.documentElement.classList.contains("dark")).toBe(false);

    // Click to toggle to dark
    const button = screen.getByRole("button", { name: /toggle theme/i });
    await user.click(button);

    // Now dark class should be present
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    // Click again to toggle back to light
    await user.click(button);

    // Dark class should be removed
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  test("persists to localStorage", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    // Click to toggle to dark
    const button = screen.getByRole("button", { name: /toggle theme/i });
    await user.click(button);

    // Check localStorage
    expect(localStorage.getItem("theme")).toBe("dark");

    // Click again to toggle to light
    await user.click(button);

    // Check localStorage
    expect(localStorage.getItem("theme")).toBe("light");
  });

  test("restores from localStorage on mount", () => {
    // Pre-set localStorage with "dark"
    localStorage.setItem("theme", "dark");

    // Render component - it should apply dark class from localStorage
    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
