/**
 * TanStack Query options for Job reads.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchJobList,
  fetchJobDetail,
  type JobListQueryOptions,
} from "../../shared/api/api-client";

export const jobListQueryKey = "operations.jobs" as const;

export function jobListQueryOptions(
  token: string | null,
  options: JobListQueryOptions = {},
) {
  return queryOptions({
    queryKey: [jobListQueryKey, options],
    queryFn: () => fetchJobList(token, options),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 30_000,
  });
}

export const jobDetailQueryKey = "operations.job-detail" as const;

export function jobDetailQueryOptions(token: string | null, jobId: string) {
  return queryOptions({
    queryKey: [jobDetailQueryKey, jobId],
    queryFn: () => fetchJobDetail(token, jobId),
    enabled: token !== null && jobId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 15_000,
  });
}
