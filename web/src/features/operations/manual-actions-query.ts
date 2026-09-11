/**
 * TanStack Query options for the manual action matrix read.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchManualActionMatrix,
  type ManualActionMatrixQueryOptions,
} from "../../shared/api/api-client";

export const manualActionsQueryKey = "operations.manual-actions" as const;

export function manualActionsQueryOptions(
  token: string | null,
  options: ManualActionMatrixQueryOptions,
  enabled = true,
) {
  return queryOptions({
    queryKey: [manualActionsQueryKey, options],
    queryFn: () => fetchManualActionMatrix(token, options),
    enabled: token !== null && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 15_000,
  });
}
