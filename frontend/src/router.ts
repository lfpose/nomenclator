import { createRouter, createRootRoute, createRoute } from "@tanstack/react-router";
import RootLayout from "./routes/__root";
import IndexRoute from "./routes/index";
import AboutRoute from "./routes/about";
import DocsRoute from "./routes/docs";

const rootRoute = createRootRoute({
  component: RootLayout,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: IndexRoute,
});

const aboutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/about",
  component: AboutRoute,
});

const docsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/docs",
  component: DocsRoute,
});

const routeTree = rootRoute.addChildren([indexRoute, aboutRoute, docsRoute]);

export const router = createRouter({ routeTree });

export type Router = typeof router;