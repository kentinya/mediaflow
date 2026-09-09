import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isDashboardEmpty } from "../../entities/dashboard/dashboard";
import { DashboardApiError } from "../../shared/api/api-errors";
import { useAuthToken, useRejected } from "../../shared/api/auth-context";
import { authStore } from "../../shared/api/auth-store";
import { AuthStateBanner, UnavailableBanner } from "../auth/AuthStateBanner";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { dashboardQueryOptions } from "./dashboard-query";
import { DashboardView } from "./DashboardView";

function errorOf(error: unknown): DashboardApiError {
  return error instanceof DashboardApiError
    ? error
    : new DashboardApiError("unavailable");
}

/**
 * Read-only Dashboard proving route. Every visible state derives from the
 * bounded API result; no state fabricates data and no action creates work,
 * calls a Provider, inspects Storage or mutates media.
 *
 * The shared auth/permission/recovery boundary lives here: a backend 401
 * clears the rejected in-memory principal and the authenticated Query cache
 * while preserving the intended route, so the operator can re-enter a valid
 * principal and continue to the same safe route without hidden replay.
 */
export function DashboardPage() {
  const token = useAuthToken();
  const rejected = useRejected();
  const queryClient = useQueryClient();
  const query = useQuery(dashboardQueryOptions(token));

  useEffect(() => {
    if (!query.isError) {
      return;
    }
    const error = errorOf(query.error);
    if (error.category !== "unauthorized") {
      return;
    }
    // A rejected principal: clear the rejected authority and its authenticated
    // cache, but keep the intended route so the operator can continue there
    // after explicit re-entry. The store marks the principal rejected so the
    // page can present the bounded unauthorized state. No automatic replay
    // occurs: the query never auto-retries and a cleared token disables it.
    if (authStore.getToken() !== null) {
      authStore.clearRejectedAuthority();
    }
    queryClient.clear();
  }, [query.isError, query.error, queryClient]);

  const onRefresh = () => {
    void query.refetch();
  };
  const refreshing = query.isFetching;

  if (token === null) {
    if (rejected) {
      return (
        <AuthStateBanner
          variant="unauthorized"
          title="Not authorized"
          message="The API token was rejected. Enter a valid API principal token to continue."
        />
      );
    }
    return (
      <AuthStateBanner
        variant="not-connected"
        title="Not connected"
        message="Enter an API principal token to view the Dashboard."
      />
    );
  }

  if (query.isPending) {
    return (
      <StatusBanner variant="info" title="Loading Dashboard">
        <p>
          Requesting the read-only operational snapshot from the MediaFlow API.
        </p>
      </StatusBanner>
    );
  }

  if (query.isError) {
    const error = errorOf(query.error);
    if (error.category === "unauthorized") {
      // Should not normally re-render after the effect clears the token, but
      // keep the distinct bounded outcome available.
      return (
        <AuthStateBanner
          variant="unauthorized"
          title="Not authorized"
          message="The API token was rejected. Enter a valid API principal token to continue."
        />
      );
    }
    if (error.category === "forbidden") {
      // The principal is still authenticated; only its permission is missing.
      // No access is granted and no silent fallback occurs.
      return (
        <AuthStateBanner
          variant="forbidden"
          title="Forbidden"
          message="The connected API principal does not have permission to read the Dashboard."
        />
      );
    }
    return (
      <section className="mf-dashboard-unavailable" role="alert">
        <UnavailableBanner
          title="Dashboard unavailable"
          description={error.message}
          onRetry={onRefresh}
          retrying={refreshing}
        />
      </section>
    );
  }

  const model = query.data;
  if (isDashboardEmpty(model)) {
    return (
      <StatusBanner variant="info" title="Dashboard is empty">
        <p>
          No files, tasks or jobs are recorded yet on the connected MediaFlow
          instance. This is the live state — nothing is estimated or hidden.
        </p>
        <div className="mf-actions">
          <RefreshControl onRefresh={onRefresh} refreshing={refreshing} />
        </div>
      </StatusBanner>
    );
  }
  return (
    <DashboardView
      model={model}
      onRefresh={onRefresh}
      refreshing={refreshing}
    />
  );
}
