/**
 * TanStack Query options for the unified Operations run inventory.
 *
 * One shared bounded polling policy drives both the inventory page and the
 * selected run overview: each read polls only while it is visible and while
 * something it reports is still active (non-terminal), backs off after a
 * failure and settles once everything it reports reached a terminal state.
 * Reads are side-effect-free, so a poll never replays a command — it repeats
 * only the same bounded read.
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

/** The bounded active-work polling interval shared by every run read. */
export const RUN_REFETCH_INTERVAL = 5_000;

/**
 * The one shared refetch policy for an inventory page or one run overview.
 *
 * An undefined (not yet loaded) or failed read never schedules a poll; a read
 * reporting any non-terminal run repeats every 5 seconds; a fully terminal
 * read settles to `false`. The selected overview therefore follows the same
 * lifecycle as the list it was selected from instead of freezing at its
 * first render.
 */
export function runRefetchInterval(
  read: RunInventoryRead | RunOverviewRead | undefined,
): number | false {
  if (read === undefined || !read.ok) {
    return false;
  }
  const model = read.model;
  const active =
    "items" in model
      ? hasActiveRuns(model.items)
      : !TERMINAL_RUN_STATUSES.includes(model.status);
  return active ? RUN_REFETCH_INTERVAL : false;
}

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
    refetchInterval: (query) => runRefetchInterval(query.state.data),
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
    // The selected run follows the same shared policy as the list: it polls
    // only while its own state is still non-terminal.
    refetchInterval: (query) => runRefetchInterval(query.state.data),
    refetchIntervalInBackground: false,
  });
}

/** Whether any listed run can still change state. */
export function hasActiveRuns(items: readonly RunSummary[]): boolean {
  return items.some((item) => !TERMINAL_RUN_STATUSES.includes(item.status));
}
