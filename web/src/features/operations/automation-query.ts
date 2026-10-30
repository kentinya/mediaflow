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
  fetchAutomationMetrics,
  fetchAutomationOccurrences,
  fetchAutomationRecords,
  type AutomationInventoryQueryOptions,
  type AutomationRecordsQueryOptions,
} from "../../shared/api/api-client";

export const automationListQueryKey = "operations.automation-list" as const;

/**
 * The bounded Automation inventory read.
 *
 * The submitted filters and page cursor are part of the query key, so a page
 * can never be rendered from a different filter state's rows: changing any
 * filter is a new server read, and a cursor is only ever taken from the
 * response to the identical state.
 */
export function automationListQueryOptions(
  token: string | null,
  options: AutomationInventoryQueryOptions = {},
  enabled = true,
) {
  return queryOptions({
    // The key names each submitted value explicitly: an object identity would
    // mint a new key on every render and turn the page into an endless
    // refetch loop.
    queryKey: [
      automationListQueryKey,
      options.q ?? null,
      options.enabled ?? null,
      options.library ?? null,
      options.state ?? null,
      options.sort ?? null,
      options.direction ?? null,
      options.limit ?? null,
      options.cursor ?? null,
    ],
    queryFn: () => fetchAutomationDefinitions(token, options),
    enabled: token !== null && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const automationMetricsQueryKey =
  "operations.automation-metrics" as const;

export function automationMetricsQueryOptions(
  token: string | null,
  enabled = true,
) {
  return queryOptions({
    queryKey: [automationMetricsQueryKey],
    queryFn: () => fetchAutomationMetrics(token),
    enabled: token !== null && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const automationRecordsQueryKey =
  "operations.automation-records" as const;

export function automationRecordsQueryOptions(
  token: string | null,
  options: AutomationRecordsQueryOptions = {},
  enabled = true,
) {
  return queryOptions({
    queryKey: [
      automationRecordsQueryKey,
      options.definition ?? null,
      options.trigger ?? null,
      options.status ?? null,
      options.outcome ?? null,
      options.from ?? null,
      options.to ?? null,
      // The paging direction is part of the key: the backend refuses a cursor
      // whose direction does not match, so a page reached backwards must never
      // be served from the forward page's cache entry.
      options.direction ?? null,
      options.limit ?? null,
      options.cursor ?? null,
    ],
    queryFn: () => fetchAutomationRecords(token, options),
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
