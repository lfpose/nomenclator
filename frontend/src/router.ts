import { createRouter, createRootRoute, createRoute } from "@tanstack/react-router";
import RootLayout from "./routes/__root";
import IndexRoute from "./routes/index";

const rootRoute = createRootRoute({
  component: RootLayout,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: IndexRoute,
});

const routeTree = rootRoute.addChildren([indexRoute]);

export const router = createRouter({ routeTree });

export type Router = typeof router;