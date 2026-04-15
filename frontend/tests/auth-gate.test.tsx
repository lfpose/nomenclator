import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";
import { PasswordForm } from "@/components/PasswordForm";

// Mock the api module
vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));
import { api } from "@/lib/api";

describe("AuthGate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders password form when /me returns 401", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new Error("unauthenticated")
    );

    render(<AuthGate>Protected Content</AuthGate>);

    await waitFor(() => {
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("renders children when /me returns 200", async () => {
    vi.mocked(api.get).mockResolvedValue({ authenticated: true });

    render(<AuthGate>Protected Content</AuthGate>);

    await waitFor(() => {
      expect(screen.getByText("Protected Content")).toBeInTheDocument();
    });

    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it("password form error shows on 401", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new Error("unauthenticated")
    );
    vi.mocked(api.post).mockRejectedValue(
      new Error("Invalid password")
    );

    const onSuccess = vi.fn();
    const { container } = render(<PasswordForm onSuccess={onSuccess} />);

    const passwordInput = screen.getByLabelText(/password/i);
    const form = container.querySelector("form");

    // Submit the form
    await userEvent.type(passwordInput, "wrongpassword");
    form?.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));

    await waitFor(() => {
      const error = screen.getByRole("alert");
      expect(error).toBeInTheDocument();
      expect(error).toHaveTextContent("Invalid password");
    });

    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("password form success transitions to children", async () => {
    vi.mocked(api.get).mockRejectedValue(
      new Error("unauthenticated")
    );
    vi.mocked(api.post).mockResolvedValue({ ok: true });

    const onSuccess = vi.fn();
    const { container } = render(<PasswordForm onSuccess={onSuccess} />);

    const passwordInput = screen.getByLabelText(/password/i);
    const form = container.querySelector("form");

    // Submit the form with correct password
    await userEvent.type(passwordInput, "correctpassword");
    form?.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledTimes(1);
    });
  });
});
