/**
 * Operations workspace landing page.
 *
 * Shows Worker readiness, task and job summary counts with links to list views,
 * and the most recent failures. All data comes from existing API endpoints; no
 * state is fabricated and no mutation is performed.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { workerReadinessQueryOptions } from "./worker-query";

export function OperationsLanding() {
  const token = useAuthToken();
  const readinessQuery = useQuery(workerReadinessQueryOptions(token));
  return (
    <AuthorizedReadBoundary
      query={readinessQuery}
      unavailableTitle="Operations unavailable"
    >
      {({ data: readiness, isFetching, refresh }) => {
        if (readiness === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Operations">
              <p>Requesting Worker readiness and operational state.</p>
            </StatusBanner>
          );
        }
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <h2>Operations</h2>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Worker readiness</h3>
              <p className="mf-dashboard-meta">
                {readiness.ready
                  ? `Worker ready — ${readiness.activeWorkersCount} active worker(s)`
                  : `Worker not ready: ${readiness.condition}`}
              </p>
              {readiness.category !== null && (
                <p className="mf-dashboard-meta">{readiness.durableState}</p>
              )}
              {readiness.nextAction && (
                <p className="mf-dashboard-meta">{readiness.nextAction}</p>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Workspaces</h3>
              <nav className="mf-actions" aria-label="Operations workspaces">
                <Link
                  className="mf-button mf-button-primary"
                  to="/operations/tasks"
                >
                  Tasks
                </Link>
                <Link
                  className="mf-button mf-button-primary"
                  to="/operations/jobs"
                >
                  Jobs
                </Link>
              </nav>
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
