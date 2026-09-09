import { useQuery } from "@tanstack/react-query";
import { isDashboardEmpty } from "../../entities/dashboard/dashboard";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { dashboardQueryOptions } from "./dashboard-query";
import { DashboardView } from "./DashboardView";

/**
 * Read-only Dashboard proving route. Every visible state derives from the
 * bounded API result; no state fabricates data and no action creates work,
 * calls a Provider, inspects Storage or mutates media.
 * The shared AuthorizedReadBoundary owns connection, permission and
 * cache-clearing; this page renders only its own loading/empty/success data.
 */
export function DashboardPage() {
  const token = useAuthToken();
  const query = useQuery(dashboardQueryOptions(token));
  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Dashboard unavailable"
    >
      {({ data, isPending, isFetching, refresh }) => {
        if (isPending || data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Dashboard">
              <p>
                Requesting the read-only operational snapshot from the MediaFlow
                API.
              </p>
            </StatusBanner>
          );
        }
        if (isDashboardEmpty(data)) {
          return (
            <StatusBanner variant="info" title="Dashboard is empty">
              <p>
                No files, tasks or jobs are recorded yet on the connected
                MediaFlow instance. This is the live state — nothing is
                estimated or hidden.
              </p>
              <div className="mf-actions">
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        return (
          <DashboardView
            model={data}
            onRefresh={refresh}
            refreshing={isFetching}
          />
        );
      }}
    </AuthorizedReadBoundary>
  );
}
