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
 * use `findBy*` queries before interacting with the rendered content. The
 * router is returned so a test can assert the real URL/search state and drive
 * browser Back/Forward through the history it owns.
 */
export function renderApp(initialPath: string): {
  queryClient: QueryClient;
  router: ReturnType<typeof createAppRouter>;
} {
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
  return { queryClient, router };
}

/**
 * Render a single component under the application providers and an isolated
 * router mounted at "/". The isolated tree has no product routes and no
 * AuthBoundary, so component tests can exercise one component's own states
 * deterministically while still having Router context for `Link` elements.
 */
export function renderWithProviders(
  element: ReactElement,
  queryClient: QueryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
    },
  }),
): ReturnType<typeof render> & { queryClient: QueryClient } {
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
  const result = render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return Object.assign(result, { queryClient });
}
