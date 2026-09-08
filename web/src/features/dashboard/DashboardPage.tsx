import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { isDashboardEmpty } from "../../entities/dashboard/dashboard";
import { DashboardApiError } from "../../shared/api/api-errors";
import { useAuthToken } from "../../shared/api/auth-context";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { dashboardQueryOptions } from "./dashboard-query";
import { DashboardView } from "./DashboardView";

export interface DashboardActions {
  readonly onRefresh: () => void;
  readonly refreshing: boolean;
}

function errorOf(error: unknown): DashboardApiError {
  return error instanceof DashboardApiError
    ? error
    : new DashboardApiError("unavailable");
}

/**
 * Read-only Dashboard proving route. Every visible state derives from the
 * bounded API result; no state fabricates data and no action creates work,
 * calls a Provider, inspects Storage or mutates media.
 */
export function DashboardPage() {
  const token = useAuthToken();
  const query = useQuery(dashboardQueryOptions(token));

  const onRefresh = () => {
    void query.refetch();
  };
  const refreshing = query.isFetching;

  if (token === null) {
    return (
      <StatusBanner variant="warning" title="Not connected">
        <p>Enter an API principal token to view the Dashboard.</p>
        <div className="mf-actions">
          <Link to="/">Go to the V2 entry</Link>
        </div>
      </StatusBanner>
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
      return (
        <StatusBanner variant="error" title="Not authorized">
          <p>{error.message}</p>
          <div className="mf-actions">
            <Link to="/">Enter an API principal token</Link>
          </div>
        </StatusBanner>
      );
    }
    if (error.category === "forbidden") {
      return (
        <StatusBanner variant="error" title="Forbidden">
          <p>{error.message}</p>
          <div className="mf-actions">
            <Link to="/">Connect a principal with read permission</Link>
          </div>
        </StatusBanner>
      );
    }
    return (
      <StatusBanner variant="error" title="Dashboard unavailable">
        <p>{error.message}</p>
        <div className="mf-actions">
          <RefreshControl onRefresh={onRefresh} refreshing={refreshing} />
        </div>
      </StatusBanner>
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
