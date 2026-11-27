/**
 * TanStack Query options for the unified Operations run inventory.
 *
 * The inventory polls while visible, with backoff after a temporary failure.
 * An overview polls only while healthy and non-terminal; a failed overview
 * waits for explicit recovery. These reads never replay a command.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchRunInventory,
  fetchRunOverview,
  fetchRunProblemFiles,
  type RunInventoryQueryOptions,
  type RunOverviewRead,
  type RunInventoryRead,
  type RunProblemFilesQueryOptions,
  type RunProblemFilesRead,
} from "../../shared/api/api-client";
import {
  TERMINAL_RUN_STATUSES,
  type RunSummary,
} from "../../entities/operations/run";

export const runInventoryQueryKey = "operations.run-inventory" as const;

/** The bounded active-work polling interval shared by every run read. */
export const RUN_REFETCH_INTERVAL = 5_000;
const RUN_UNAVAILABLE_REFETCH_INTERVAL = 10_000;

/**
 * The shared refetch policy for one inventory page or selected overview.
 *
 * A temporary read failure backs off before polling again. Every successful
 * inventory read repeats every 5 seconds while visible so
 * new terminal rows and changed recovery links appear without a write action.
 * A selected overview follows its own lifecycle and settles when terminal.
 */
export function runRefetchInterval(
  read: RunInventoryRead | RunOverviewRead | undefined,
  readFailed = false,
): number | false {
  if (readFailed || read === undefined) return false;
  if (!read.ok) {
    return read.failure.kind === "unavailable"
      ? RUN_UNAVAILABLE_REFETCH_INTERVAL
      : false;
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

export const runProblemFilesQueryKey = "operations.problem-files" as const;

export function runProblemFilesQueryOptions(
  token: string | null,
  options: RunProblemFilesQueryOptions,
) {
  return queryOptions({
    queryKey: [
      runProblemFilesQueryKey,
      options.problem ?? "all",
      options.from ?? "",
      options.to ?? "",
      options.cursor ?? null,
    ],
    queryFn: (): Promise<RunProblemFilesRead> =>
      fetchRunProblemFiles(token, options),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
    // Attention is exactly the live current-problem population; a change in
    // a Task/item resolves or re-types the file. The same bounded read repeats
    // only while visible, so a resolved row leaves without replaying work.
    refetchInterval: (query) =>
      query.state.data?.ok === true
        ? RUN_REFETCH_INTERVAL
        : query.state.data?.failure.kind === "unavailable"
          ? RUN_UNAVAILABLE_REFETCH_INTERVAL
          : false,
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
    // An open detail polls only healthy active work. Once it offers
    // “重新读取任务”, the next read belongs to that action, not the list poll.
    refetchInterval: (query) =>
      query.state.data?.ok === true
        ? runRefetchInterval(query.state.data, query.state.status === "error")
        : false,
    refetchIntervalInBackground: false,
  });
}

/** Whether any listed run can still change state. */
export function hasActiveRuns(items: readonly RunSummary[]): boolean {
  return items.some((item) => !TERMINAL_RUN_STATUSES.includes(item.status));
}
