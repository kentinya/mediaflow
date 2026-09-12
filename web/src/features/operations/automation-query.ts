/**
 * TanStack Query boundaries for the V2 Automation journey.
 *
 * Reads are ordinary bounded queries; mutations are owned by the pages that
 * submit them. Every query and mutation disables automatic retry so an
 * ambiguous admission, rejection or 401/403 is never replayed silently: the
 * operator reads the current durable state and decides.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchAutomationDefinition,
  fetchAutomationDefinitionDraft,
  fetchAutomationDefinitions,
  fetchAutomationOccurrences,
  fetchAutomationPreview,
  fetchAutomationPreviewItems,
} from "../../shared/api/api-client";

export const automationListQueryKey = "operations.automation-list" as const;

export function automationListQueryOptions(
  token: string | null,
  enabled = true,
) {
  return queryOptions({
    queryKey: [automationListQueryKey],
    queryFn: () => fetchAutomationDefinitions(token),
    enabled: token !== null && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const automationDefinitionQueryKey =
  "operations.automation-definition" as const;

export function automationDefinitionQueryOptions(
  token: string | null,
  definitionId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [automationDefinitionQueryKey, definitionId],
    queryFn: () => fetchAutomationDefinition(token, definitionId),
    enabled: token !== null && definitionId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const automationDraftQueryKey = "operations.automation-draft" as const;

export function automationDraftQueryOptions(
  token: string | null,
  definitionId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [automationDraftQueryKey, definitionId],
    queryFn: () => fetchAutomationDefinitionDraft(token, definitionId),
    enabled: token !== null && definitionId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const automationPreviewQueryKey =
  "operations.automation-preview" as const;

export function automationPreviewQueryOptions(
  token: string | null,
  definitionId: string,
  previewId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [automationPreviewQueryKey, definitionId, previewId],
    queryFn: () => fetchAutomationPreview(token, definitionId, previewId),
    enabled:
      token !== null &&
      definitionId.length > 0 &&
      previewId.length > 0 &&
      enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const automationPreviewItemsQueryKey =
  "operations.automation-preview-items" as const;

export function automationPreviewItemsQueryOptions(
  token: string | null,
  definitionId: string,
  previewId: string,
  after: number | null,
  enabled = true,
) {
  return queryOptions({
    queryKey: [automationPreviewItemsQueryKey, definitionId, previewId, after],
    queryFn: () =>
      fetchAutomationPreviewItems(token, definitionId, previewId, {
        limit: 50,
        after,
      }),
    enabled:
      token !== null &&
      definitionId.length > 0 &&
      previewId.length > 0 &&
      enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const automationOccurrencesQueryKey =
  "operations.automation-occurrences" as const;

export function automationOccurrencesQueryOptions(
  token: string | null,
  definitionId: string,
  cursor: string | null,
  direction: "previous" | "next",
  enabled = true,
) {
  return queryOptions({
    queryKey: [automationOccurrencesQueryKey, definitionId, direction, cursor],
    queryFn: () =>
      fetchAutomationOccurrences(token, definitionId, {
        limit: 20,
        cursor,
        direction,
      }),
    enabled: token !== null && definitionId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}
