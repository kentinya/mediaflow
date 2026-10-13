/**
 * TanStack Query boundary for one definition-bound Automation Run once.
 *
 * Reads are ordinary bounded queries with automatic retry disabled: an
 * ambiguous or denied read is never replayed silently, and the operator decides
 * from the current durable state.  Polling is deliberately modest so durable
 * progress becomes visible promptly without hammering the backend.
 */

import { queryOptions } from "@tanstack/react-query";
import { fetchAutomationRunOnce } from "../../shared/api/api-client";

export const automationRunOnceQueryKey =
  "operations.automation-run-once" as const;

export function automationRunOnceQueryOptions(
  token: string | null,
  discoveryId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [automationRunOnceQueryKey, discoveryId],
    queryFn: () => fetchAutomationRunOnce(token, discoveryId),
    enabled: token !== null && discoveryId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 1_000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data === undefined || !data.ok || data.model === undefined) {
        return false;
      }
      // Durable work is polled only while it is genuinely still progressing.
      return data.model.phase === "discovering" ||
        data.model.phase === "analyzing"
        ? 2_000
        : false;
    },
  });
}
