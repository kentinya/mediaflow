/**
 * TanStack Query boundaries for the manual Organize journey.
 *
 * Reads are ordinary bounded queries; mutations are owned by the pages that
 * submit them. Every query and mutation disables automatic retry so an
 * ambiguous admission, rejection or 401/403 is never replayed silently: the
 * operator reads the current durable state and decides.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchOrganizeExecution,
  fetchOrganizeExecutions,
  fetchOrganizeIntent,
  fetchOrganizePreviewDetail,
  type OrganizeExecutionListQueryOptions,
} from "../../shared/api/api-client";

export const organizeIntentQueryKey = "operations.organize-intent" as const;

export function organizeIntentQueryOptions(
  token: string | null,
  intentId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [organizeIntentQueryKey, intentId],
    queryFn: () => fetchOrganizeIntent(token, intentId),
    enabled: token !== null && intentId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const organizePreviewQueryKey = "operations.organize-preview" as const;

export function organizePreviewQueryOptions(
  token: string | null,
  previewId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [organizePreviewQueryKey, previewId],
    queryFn: () => fetchOrganizePreviewDetail(token, previewId),
    enabled: token !== null && previewId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const organizeExecutionQueryKey =
  "operations.organize-execution" as const;

export function organizeExecutionQueryOptions(
  token: string | null,
  executionId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [organizeExecutionQueryKey, executionId],
    queryFn: () => fetchOrganizeExecution(token, executionId),
    enabled: token !== null && executionId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 2_000,
  });
}

export const organizeExecutionListQueryKey =
  "operations.organize-execution-list" as const;

export function organizeExecutionListQueryOptions(
  token: string | null,
  options: OrganizeExecutionListQueryOptions,
  enabled = true,
) {
  return queryOptions({
    queryKey: [organizeExecutionListQueryKey, options],
    queryFn: () => fetchOrganizeExecutions(token, options),
    enabled:
      token !== null &&
      (Boolean(options.previewId) || Boolean(options.intentId)) &&
      enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}
