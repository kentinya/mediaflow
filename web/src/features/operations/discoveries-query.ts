/**
 * TanStack Query boundary for this principal's bounded discovery list
 * (Slice 44 RO-6).
 *
 * The Operations task center reads the same principal-scoped discovery
 * projection the Files journey publishes, so an admitted discovery whose
 * admission response was lost is recoverable here without raw identifiers.
 * Reads are side-effect-free and never replay a command.
 */

import { queryOptions } from "@tanstack/react-query";
import { fetchOrganizeDiscoveries } from "../../shared/api/api-client";

export const organizeDiscoveriesQueryKey =
  "operations.organize-discoveries" as const;

export function organizeDiscoveriesQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: [organizeDiscoveriesQueryKey],
    queryFn: () => fetchOrganizeDiscoveries(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 2_000,
    // Admitted discoveries are active work while open; a bounded poll keeps
    // the readback current without replaying anything.
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data === undefined || !data.ok) return false;
      const active = data.items.some(
        (item) =>
          !item.frozen &&
          item.intentId === null &&
          item.status !== "cancelled" &&
          item.status !== "failed",
      );
      return active ? 5_000 : false;
    },
    refetchIntervalInBackground: false,
  });
}
