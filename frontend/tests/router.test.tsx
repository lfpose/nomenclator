import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { RouterProvider } from "@tanstack/react-router";
import { createMemoryHistory } from "@tanstack/react-router";
import { createRouter, createRootRoute, createRoute } from "@tanstack/react-router";
import RootLayout from "../src/routes/__root";
import IndexRoute from "../src/routes/index";
import AboutRoute from "../src/routes/about";
import DocsRoute from "../src/routes/docs";

function createTestRouter(path: string) {
  const memoryHistory = createMemoryHistory({ initialEntries: [path] });
  const rootRoute = createRootRoute({ component: RootLayout });
  const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: IndexRoute });
  const aboutRoute = createRoute({ getParentRoute: () => rootRoute, path: "/about", component: AboutRoute });
  const docsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/docs", component: DocsRoute });
  const routeTree = rootRoute.addChildren([indexRoute, aboutRoute, docsRoute]);
  return createRouter({ routeTree, history: memoryHistory });
}

describe("Router", () => {
  it("renders Tool page at /", async () => {
    const router = createTestRouter("/");
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("heading", { name: "Tool", level: 1 })).toBeInTheDocument();
  });

  it("renders About page at /about", async () => {
    const router = createTestRouter("/about");
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("heading", { name: "About", level: 1 })).toBeInTheDocument();
  });

  it("renders Docs page at /docs", async () => {
    const router = createTestRouter("/docs");
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("heading", { name: "Docs", level: 1 })).toBeInTheDocument();
  });
});