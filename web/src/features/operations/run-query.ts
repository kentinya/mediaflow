/**
 * TanStack Query options for the unified Operations run inventory.
 *
 * The inventory page polls only while it is visible and while any listed run
 * is still active (non-terminal), backs off after a failure and settles once
 * every listed run reached a terminal state. Reads are side-effect-free, so
 * a poll never replays a command — it repeats only the same bounded read.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchRunInventory,
  fetchRunOverview,
  type RunInventoryQueryOptions,
  type RunOverviewRead,
  type RunInventoryRead,
} from "../../shared/api/api-client";
import {
  TERMINAL_RUN_STATUSES,
  type RunSummary,
} from "../../entities/operations/run";

export const runInventoryQueryKey = "operations.run-inventory" as const;

export function runInventoryQueryOptions(
  token: string | null,
  options: RunInventoryQueryOptions = {},
) {
  return queryOptions({
    queryKey: [runInventoryQueryKey, options],
    queryFn: () => fetchRunInventory(token, options),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
    // Bounded active-work polling: refetch while visible and something may
    // still change; a fully terminal page settles. Hidden tabs pause
    // automatically through refetchIntervalInBackground: false.
    refetchInterval: (query) => {
      const data = query.state.data as RunInventoryRead | undefined;
      if (data === undefined || !data.ok) {
        return false;
      }
      const active = data.model.items.some(
        (item) => !TERMINAL_RUN_STATUSES.includes(item.status),
      );
      return active ? 5_000 : false;
    },
    refetchIntervalInBackground: false,
  });
}

export const runOverviewQueryKey = "operations.run-overview" as const;

export function runOverviewQueryOptions(token: string | null, runId: string) {
  return queryOptions({
    queryKey: [runOverviewQueryKey, runId],
    queryFn: (): Promise<RunOverviewRead> => fetchRunOverview(token, runId),
    enabled: token !== null && runId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
    refetchInterval: (query) => {
      const data = query.state.data as RunOverviewRead | undefined;
      if (data === undefined || !data.ok) {
        return false;
      }
      return TERMINAL_RUN_STATUSES.includes(data.model.status) ? false : 5_000;
    },
    refetchIntervalInBackground: false,
  });
}

/** Whether any listed run can still change state. */
export function hasActiveRuns(items: readonly RunSummary[]): boolean {
  return items.some((item) => !TERMINAL_RUN_STATUSES.includes(item.status));
}
