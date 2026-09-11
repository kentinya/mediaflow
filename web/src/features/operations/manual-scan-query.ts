/**
 * TanStack Query options for manual Scan reads and mutations.
 */

import { queryOptions, type MutationOptions } from "@tanstack/react-query";
import {
  fetchManualScanDetail,
  submitManualScanCancellation,
  type ScanDetailQueryOptions,
} from "../../shared/api/api-client";

export const manualScanDetailQueryKey =
  "operations.manual-scan-detail" as const;

export function manualScanDetailQueryOptions(
  token: string | null,
  options: ScanDetailQueryOptions,
  enabled = true,
) {
  return queryOptions({
    queryKey: [manualScanDetailQueryKey, options.taskId, options],
    queryFn: () => fetchManualScanDetail(token, options),
    enabled: token !== null && options.taskId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 15_000,
  });
}

export function manualScanCancelMutationOptions(token: string | null) {
  return {
    mutationFn: (taskId: string) => submitManualScanCancellation(token, taskId),
    retry: false,
  } satisfies MutationOptions<
    Awaited<ReturnType<typeof submitManualScanCancellation>>,
    Error,
    string
  >;
}
