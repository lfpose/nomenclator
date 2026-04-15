import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { RouterProvider } from "@tanstack/react-router";
import { createMemoryHistory } from "@tanstack/react-router";
import { createRouter, createRootRoute, createRoute } from "@tanstack/react-router";

// Mock the ThemeToggle component to avoid theme-related side effects
vi.mock("@/components/ThemeToggle", () => ({
  ThemeToggle: () => <button aria-label="Toggle theme">Theme</button>,
}));

// Mock the api.logout function
vi.mock("@/lib/api", () => ({
  api: {
    logout: vi.fn().mockResolvedValue({ ok: true }),
  },
}));

// Helper to render Header with router context
function renderHeaderWithRouter() {
  const memoryHistory = createMemoryHistory({ initialEntries: ["/"] });
  const rootRoute = createRootRoute({
    component: () => (
      <div>
        <Header />
      </div>
    ),
  });
  const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: () => <div>Tool</div> });
  const aboutRoute = createRoute({ getParentRoute: () => rootRoute, path: "/about", component: () => <div>About</div> });
  const docsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/docs", component: () => <div>Docs</div> });
  const routeTree = rootRoute.addChildren([indexRoute, aboutRoute, docsRoute]);
  const router = createRouter({ routeTree, history: memoryHistory });

  return render(<RouterProvider router={router} />);
}

describe("Root Layout", () => {
  it("renders wordmark", async () => {
    renderHeaderWithRouter();

    const wordmark = await screen.findByText(/nomenclator/i);
    expect(wordmark).toBeInTheDocument();
    expect(wordmark).toHaveClass("font-serif");
  });

  it("header has 3 nav links", async () => {
    renderHeaderWithRouter();

    const toolLink = await screen.findByRole("link", { name: /tool/i });
    const aboutLink = await screen.findByRole("link", { name: /about/i });
    const docsLink = await screen.findByRole("link", { name: /docs/i });

    expect(toolLink).toBeInTheDocument();
    expect(aboutLink).toBeInTheDocument();
    expect(docsLink).toBeInTheDocument();
  });

  it("header has theme toggle button", async () => {
    renderHeaderWithRouter();

    const themeToggle = await screen.findByRole("button", { name: /toggle theme/i });
    expect(themeToggle).toBeInTheDocument();
  });

  it("header has logout button", async () => {
    renderHeaderWithRouter();

    const logoutButton = await screen.findByRole("button", { name: /logout/i });
    expect(logoutButton).toBeInTheDocument();
  });

  it("footer is rendered", () => {
    render(<Footer />);

    const footer = screen.getByRole("contentinfo");
    expect(footer).toBeInTheDocument();
    expect(footer).toHaveTextContent(/nomenclator/i);
  });
});
