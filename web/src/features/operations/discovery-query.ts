/**
 * TanStack Query boundary for one bounded discovery (Slice 44 RO-6).
 *
 * Reads are ordinary bounded queries with automatic retry disabled: an
 * ambiguous or denied read is never replayed silently, and the operator
 * decides from the current durable state.
 */

import { queryOptions } from "@tanstack/react-query";
import { fetchOrganizeDiscovery } from "../../shared/api/api-client";

export const organizeDiscoveryQueryKey =
  "operations.organize-discovery" as const;

export function organizeDiscoveryQueryOptions(
  token: string | null,
  discoveryId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [organizeDiscoveryQueryKey, discoveryId],
    queryFn: () => fetchOrganizeDiscovery(token, discoveryId),
    enabled: token !== null && discoveryId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 2_000,
  });
}
