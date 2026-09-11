/**
 * Operations workspace landing page.
 *
 * Shows Worker readiness, task and job summary counts with links to list views,
 * and the most recent failures. All data comes from existing API endpoints; no
 * state is fabricated and no mutation is performed.
 *
 * For daily manual operations, the landing offers bounded Scan and Preview
 * admission links so the operator can start work directly from Operations.
 * The ResourceLibrary scope is selected on the admission page itself.
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
            <section className="mf-count-section">
              <h3>Manual operations</h3>
              <p className="mf-dashboard-meta">
                Start a bounded Scan or run a zero-mutation Preview from a
                selected ResourceLibrary scope. Scan discovers and indexes
                source files; Preview runs the complete pipeline with zero
                Storage mutation.
              </p>
              <nav className="mf-actions" aria-label="Manual operations">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/scan/new"
                  search={{ scopeKind: "resourceLibrary" }}
                >
                  Start bounded Scan
                </Link>
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/preview/new"
                  search={{ scopeKind: "resourceLibrary" }}
                >
                  Run zero-mutation Preview
                </Link>
              </nav>
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
