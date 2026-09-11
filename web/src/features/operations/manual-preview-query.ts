/**
 * TanStack Query options for manual Preview reads.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchManualPreviewDetail,
  fetchManualPreviews,
  type ManualPreviewListQueryOptions,
} from "../../shared/api/api-client";

export const manualPreviewDetailQueryKey =
  "operations.manual-preview-detail" as const;

export function manualPreviewDetailQueryOptions(
  token: string | null,
  previewId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [manualPreviewDetailQueryKey, previewId],
    queryFn: () => fetchManualPreviewDetail(token, previewId),
    enabled: token !== null && previewId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 15_000,
  });
}

export const manualPreviewListQueryKey =
  "operations.manual-preview-list" as const;

export function manualPreviewListQueryOptions(
  token: string | null,
  options: ManualPreviewListQueryOptions,
  enabled = true,
) {
  return queryOptions({
    queryKey: [manualPreviewListQueryKey, options],
    queryFn: () => fetchManualPreviews(token, options),
    enabled:
      token !== null &&
      options.scopeKind.length > 0 &&
      options.scopeId.length > 0 &&
      enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 15_000,
  });
}
