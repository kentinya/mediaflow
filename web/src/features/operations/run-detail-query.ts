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
  fetchRunItemEvidence,
  fetchRunItems,
  fetchRunRecords,
  fetchTaskItemRecovery,
  fetchTaskRecoveryBatch,
  type RunItemEvidenceRead,
  type RunItemsRead,
  type RunRecordsRead,
} from "../../shared/api/api-client";
import type { OperationsRead } from "../../shared/api/api-client";
import type {
  RecoveryBatchModel,
  TaskItemRecoveryModel,
} from "../../entities/operations/task-item-recovery";
import { RUN_REFETCH_INTERVAL } from "./run-query";

export const runItemsQueryKey = "operations.run-items" as const;
export const runRecordsQueryKey = "operations.run-records" as const;
export const runItemEvidenceQueryKey = "operations.run-item-evidence" as const;
export const taskItemRecoveryQueryKey =
  "operations.task-item-recovery" as const;
export const recoveryBatchQueryKey = "operations.recovery-batch" as const;

export function recoveryBatchQueryCacheKey(context: {
  readonly taskId: string;
  readonly batchId: string;
  readonly principalId: string;
  readonly authGeneration: number;
}) {
  return [
    recoveryBatchQueryKey,
    context.authGeneration,
    context.principalId,
    context.taskId,
    context.batchId,
  ] as const;
}

function detailRefetchInterval(active: boolean): number | false {
  return active ? RUN_REFETCH_INTERVAL : false;
}

export interface RunDetailQueryContext {
  readonly runId: string;
  /** Poll while the run is non-terminal; settle when it reached a terminal state. */
  readonly active: boolean;
}

export function runItemsQueryOptions(
  token: string | null,
  context: RunDetailQueryContext & {
    readonly status: string | null;
    readonly cursor: string | null;
  },
) {
  return queryOptions({
    queryKey: [
      runItemsQueryKey,
      context.runId,
      context.status ?? "all",
      context.cursor ?? null,
    ],
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
    refetchInterval: detailRefetchInterval(context.active),
    refetchIntervalInBackground: false,
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
    refetchInterval: detailRefetchInterval(context.active),
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
    refetchInterval: detailRefetchInterval(context.active),
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
    refetchInterval: detailRefetchInterval(context.active),
    refetchIntervalInBackground: false,
  });
}

export function recoveryBatchQueryOptions(
  token: string | null,
  context: {
    readonly taskId: string;
    readonly batchId: string;
    readonly principalId: string;
    readonly authGeneration: number;
  },
) {
  return queryOptions({
    queryKey: recoveryBatchQueryCacheKey(context),
    queryFn: (): Promise<OperationsRead<RecoveryBatchModel>> =>
      fetchTaskRecoveryBatch(token, context.taskId, context.batchId),
    enabled:
      token !== null && context.taskId.length > 0 && context.batchId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 0,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (
        data?.ok === true &&
        ["completed", "partial", "failed", "cancelled"].includes(
          data.model.status,
        )
      ) {
        return false;
      }
      return RUN_REFETCH_INTERVAL;
    },
    refetchIntervalInBackground: false,
  });
}
