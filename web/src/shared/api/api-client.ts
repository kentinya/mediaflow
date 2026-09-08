/**
 * Central typed API client for the existing `GET /api/v1/dashboard` contract.
 *
 * This is the single server-state boundary of the V2 frontend: requests carry
 * the API-principal Bearer token from runtime memory only, responses are
 * strictly normalized into the frontend-owned Dashboard model, and every
 * failure becomes one bounded, secret-free error category. No other module
 * may call the API directly.
 */

import {
  normalizeDashboard,
  type DashboardModel,
} from "../../entities/dashboard/dashboard";
import { DashboardApiError } from "./api-errors";

/**
 * The bounded recentLimit used by the proving route; the existing API accepts
 * 1..50 and defaults to 10.
 */
export const DASHBOARD_RECENT_LIMIT = 10;

export type FetchLike = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

export function dashboardUrl(): string {
  return `/api/v1/dashboard?recentLimit=${DASHBOARD_RECENT_LIMIT}`;
}

export async function fetchDashboard(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<DashboardModel> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl(dashboardUrl(), { method: "GET", headers });
  } catch {
    throw new DashboardApiError("unavailable");
  }
  if (response.status === 401) {
    throw new DashboardApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new DashboardApiError("forbidden");
  }
  if (response.status >= 500) {
    throw new DashboardApiError("unavailable");
  }
  if (!response.ok) {
    throw new DashboardApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new DashboardApiError("malformed");
  }
  try {
    return normalizeDashboard(payload);
  } catch {
    throw new DashboardApiError("malformed");
  }
}
