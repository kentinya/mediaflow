/**
 * TanStack Query options for Task reads.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchTaskList,
  fetchTaskDetail,
  type TaskListQueryOptions,
  type TaskDetailQueryOptions,
} from "../../shared/api/api-client";

export const taskListQueryKey = "operations.tasks" as const;

export function taskListQueryOptions(
  token: string | null,
  options: TaskListQueryOptions = {},
) {
  return queryOptions({
    queryKey: [taskListQueryKey, options],
    queryFn: () => fetchTaskList(token, options),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30_000,
  });
}

export const taskDetailQueryKey = "operations.task-detail" as const;

export function taskDetailQueryOptions(
  token: string | null,
  options: TaskDetailQueryOptions,
) {
  return queryOptions({
    queryKey: [taskDetailQueryKey, options.taskId, options],
    queryFn: () => fetchTaskDetail(token, options),
    enabled: token !== null && options.taskId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 15_000,
  });
}
