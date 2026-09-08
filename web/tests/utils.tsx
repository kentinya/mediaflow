import { render } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import { RouterProvider, createMemoryHistory } from "@tanstack/react-router";
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

export function renderWithProviders(
  element: ReactElement,
): ReturnType<typeof render> {
  const queryClient = new QueryClient();
  return render(
    <AppProviders queryClient={queryClient}>{element}</AppProviders>,
  );
}
