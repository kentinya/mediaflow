import { queryOptions } from "@tanstack/react-query";
import {
  DASHBOARD_RECENT_LIMIT,
  fetchDashboard,
} from "../../shared/api/api-client";

/**
 * The single Dashboard server-state query. It is read-only and bounded:
 * no automatic retries or window-focus refetches exist, so the only way the
 * request repeats is the explicit bounded refresh action.
 */
export const DASHBOARD_QUERY_KEY = [
  "dashboard",
  DASHBOARD_RECENT_LIMIT,
] as const;

export function dashboardQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: () => fetchDashboard(token),
    enabled: token !== null,
    retry: false,
  });
}
