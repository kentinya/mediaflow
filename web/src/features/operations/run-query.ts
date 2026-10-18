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
 * The shared refetch policy for one inventory page or selected overview.
 *
 * An undefined (not yet loaded) or failed read never schedules a poll; a read
 * every successful inventory read repeats every 5 seconds while visible so
 * new terminal rows and changed recovery links appear without a write action.
 * A selected overview follows its own lifecycle and settles when terminal.
 */
export function runRefetchInterval(
  read: RunInventoryRead | RunOverviewRead | undefined,
  readFailed = false,
): number | false {
  if (readFailed || read === undefined || !read.ok) {
    return false;
  }
  const model = read.model;
  if ("items" in model) {
    return RUN_REFETCH_INTERVAL;
  }
  return !TERMINAL_RUN_STATUSES.includes(model.status)
    ? RUN_REFETCH_INTERVAL
    : false;
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
    // The visible inventory is a live, bounded view of durable run and
    // recovery-link changes, including additions after every current row is
    // terminal. Hidden tabs pause through refetchIntervalInBackground.
    refetchInterval: (query) =>
      runRefetchInterval(query.state.data, query.state.status === "error"),
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
    refetchInterval: (query) =>
      runRefetchInterval(query.state.data, query.state.status === "error"),
    refetchIntervalInBackground: false,
  });
}

/** Whether any listed run can still change state. */
export function hasActiveRuns(items: readonly RunSummary[]): boolean {
  return items.some((item) => !TERMINAL_RUN_STATUSES.includes(item.status));
}
