import { queryOptions } from "@tanstack/react-query";
import { fetchSystemStatus } from "../../shared/api/api-client";

/** Single read-only query for the managed Active runtime snapshot. */
export const SYSTEM_STATUS_QUERY_KEY = ["system-status"] as const;

export function systemStatusQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: SYSTEM_STATUS_QUERY_KEY,
    queryFn: () => fetchSystemStatus(token),
    enabled: token !== null,
    retry: false,
  });
}
