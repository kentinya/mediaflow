import { QueryClient } from "@tanstack/react-query";

/**
 * The single server-state query/cache boundary. Automatic retries and
 * window-focus refetches are disabled so the Dashboard request only repeats
 * through the explicit bounded refresh action.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
    },
  });
}
