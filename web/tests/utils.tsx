import { render } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import {
  RouterProvider,
  createMemoryHistory,
  createRoute,
  createRootRoute,
  createRouter,
} from "@tanstack/react-router";
import type { ReactElement } from "react";
import { AppProviders } from "../src/app/providers";
import { createAppRouter } from "../src/routes/router";

/**
 * Render the real route tree under the documented /ui-v2/ base path with a
 * fresh query cache per call. The router mounts asynchronously, so tests must
 * use `findBy*` queries before interacting with the rendered content.
 */
export function renderApp(initialPath: string): { queryClient: QueryClient } {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
    },
  });
  const router = createAppRouter(
    createMemoryHistory({ initialEntries: [initialPath] }),
  );
  render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { queryClient };
}

/**
 * Render a single component under the application providers and an isolated
 * router mounted at "/". The isolated tree has no product routes and no
 * AuthBoundary, so component tests can exercise one component's own states
 * deterministically while still having Router context for `Link` elements.
 */
export function renderWithProviders(
  element: ReactElement,
): ReturnType<typeof render> {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
    },
  });
  const rootRoute = createRootRoute();
  const elementRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: () => <>{element}</>,
  });
  const routeTree = rootRoute.addChildren([elementRoute]);
  const router = createRouter({
    routeTree,
    basepath: "/",
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  return render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
}
