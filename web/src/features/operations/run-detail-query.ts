/**
 * TanStack Query options for the selected-run detail reads (RO-3).
 *
 * All three reads share the run inventory's bounded polling policy: they
 * refetch only while the selected run may still change, pause on hidden
 * pages through `refetchIntervalInBackground: false` and settle once the run
 * reached a terminal state. A read is side-effect-free, so a poll repeats
 * exactly the same bounded GET and never replays a command.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchRunProblemItems,
  fetchRunItemEvidence,
  fetchRunItems,
  fetchRunRecords,
  fetchTaskItemRecovery,
  type RunItemEvidenceRead,
  type RunItemsRead,
  type RunProblemItemsRead,
  type RunRecordsRead,
} from "../../shared/api/api-client";
import type { OperationsRead } from "../../shared/api/api-client";
import type { TaskItemRecoveryModel } from "../../entities/operations/task-item-recovery";
import type { RunProblemType } from "../../entities/operations/run";
import { RUN_REFETCH_INTERVAL } from "./run-query";

export const runItemsQueryKey = "operations.run-items" as const;
export const runProblemItemsQueryKey = "operations.run-problem-items" as const;
export const runRecordsQueryKey = "operations.run-records" as const;
export const runItemEvidenceQueryKey = "operations.run-item-evidence" as const;
export const taskItemRecoveryQueryKey =
  "operations.task-item-recovery" as const;

function detailRefetchInterval(
  read: OperationsRead<unknown> | undefined,
  active: boolean,
  readFailed = false,
): number | false {
  return active && !readFailed && read?.ok === true
    ? RUN_REFETCH_INTERVAL
    : false;
}

export interface RunDetailQueryContext {
  readonly runId: string;
  /** Poll while the run is non-terminal; settle when it reached a terminal state. */
  readonly active: boolean;
}

/**
 * The exact server page/filter identity of the primary-item read. The same
 * key selects this one read for an in-place terminal re-read without touching
 * sibling pages or filters.
 */
export function runItemsPageQueryKey(context: {
  readonly runId: string;
  readonly status: string | null;
  readonly cursor: string | null;
}) {
  return [
    runItemsQueryKey,
    context.runId,
    context.status ?? "all",
    context.cursor ?? null,
  ] as const;
}

export function runItemsQueryOptions(
  token: string | null,
  context: RunDetailQueryContext & {
    readonly status: string | null;
    readonly cursor: string | null;
  },
) {
  return queryOptions({
    queryKey: runItemsPageQueryKey(context),
    queryFn: (): Promise<RunItemsRead> =>
      fetchRunItems(token, {
        runId: context.runId,
        status: context.status,
        cursor: context.cursor,
        limit: 20,
      }),
    enabled: token !== null && context.runId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
    refetchInterval: (query) =>
      detailRefetchInterval(
        query.state.data,
        context.active,
        query.state.status === "error",
      ),
    refetchIntervalInBackground: false,
  });
}

export function runProblemItemsQueryOptions(
  token: string | null,
  context: RunDetailQueryContext & {
    readonly problem: RunProblemType;
    readonly cursor: string | null;
  },
) {
  return queryOptions({
    queryKey: [
      runProblemItemsQueryKey,
      context.runId,
      context.problem,
      context.cursor ?? null,
    ],
    queryFn: (): Promise<RunProblemItemsRead> =>
      fetchRunProblemItems(token, {
        runId: context.runId,
        problem: context.problem,
        cursor: context.cursor,
        limit: 20,
      }),
    enabled: token !== null && context.runId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
    refetchInterval: (query) =>
      detailRefetchInterval(
        query.state.data,
        context.active,
        query.state.status === "error",
      ),
    refetchIntervalInBackground: false,
  });
}

/**
 * One bounded page of the same organize Task's settled items.
 *
 * The Files overview keeps a skipped/ignored result after a newer plan stops
 * publishing that file, so it reads the exact durable TaskItem through the
 * same authorized run-items endpoint the Task Center uses. The filter and the
 * bounded limit keep the read zero-mutation, and the key stays under the run
 * items prefix so the ordinary per-item invalidation refreshes it.
 */
export function filesSettledRecordsQueryOptions(
  token: string | null,
  context: {
    readonly runId: string;
    readonly status: "skipped" | "ignored";
  },
) {
  return queryOptions({
    queryKey: [
      runItemsQueryKey,
      context.runId,
      "files-settled",
      context.status,
    ],
    queryFn: (): Promise<RunItemsRead> =>
      fetchRunItems(token, {
        runId: context.runId,
        status: context.status,
        limit: 100,
      }),
    enabled: token !== null && context.runId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
    refetchInterval: false,
  });
}

export function runRecordsQueryOptions(
  token: string | null,
  context: RunDetailQueryContext & {
    readonly kind: string | null;
    readonly cursor: string | null;
  },
) {
  return queryOptions({
    queryKey: [
      runRecordsQueryKey,
      context.runId,
      context.kind ?? "all",
      context.cursor ?? null,
    ],
    queryFn: (): Promise<RunRecordsRead> =>
      fetchRunRecords(token, {
        runId: context.runId,
        kind: context.kind,
        cursor: context.cursor,
        limit: 20,
      }),
    enabled: token !== null && context.runId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
    refetchInterval: (query) =>
      detailRefetchInterval(
        query.state.data,
        context.active,
        query.state.status === "error",
      ),
    refetchIntervalInBackground: false,
  });
}

export function runItemEvidenceQueryOptions(
  token: string | null,
  context: RunDetailQueryContext & { readonly itemId: string },
) {
  return queryOptions({
    queryKey: [runItemEvidenceQueryKey, context.runId, context.itemId],
    queryFn: (): Promise<RunItemEvidenceRead> =>
      fetchRunItemEvidence(token, context.runId, context.itemId),
    enabled:
      token !== null && context.runId.length > 0 && context.itemId !== "",
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
    refetchInterval: (query) =>
      detailRefetchInterval(
        query.state.data,
        context.active,
        query.state.status === "error",
      ),
    refetchIntervalInBackground: false,
  });
}

export function taskItemRecoveryQueryOptions(
  token: string | null,
  context: RunDetailQueryContext & {
    readonly taskId: string;
    readonly itemId: string;
  },
) {
  return queryOptions({
    queryKey: [taskItemRecoveryQueryKey, context.taskId, context.itemId],
    queryFn: (): Promise<OperationsRead<TaskItemRecoveryModel>> =>
      fetchTaskItemRecovery(token, context.taskId, context.itemId),
    enabled:
      token !== null && context.taskId.length > 0 && context.itemId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 0,
    refetchInterval: (query) =>
      detailRefetchInterval(
        query.state.data,
        context.active,
        query.state.status === "error",
      ),
    refetchIntervalInBackground: false,
  });
}
