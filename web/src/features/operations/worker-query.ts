/**
 * TanStack Query options for Worker reads.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchWorkerReadiness,
  fetchWorkerList,
} from "../../shared/api/api-client";

export const workerReadinessQueryKey = "operations.worker-readiness" as const;

export function workerReadinessQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: [workerReadinessQueryKey],
    queryFn: () => fetchWorkerReadiness(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 15_000,
  });
}

export const workerListQueryKey = "operations.workers" as const;

export function workerListQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: [workerListQueryKey],
    queryFn: () => fetchWorkerList(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 15_000,
  });
}
