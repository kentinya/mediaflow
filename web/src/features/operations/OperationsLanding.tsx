/**
 * Operations workspace landing page.
 *
 * Shows Worker readiness, task and job summary counts with links to list views,
 * and the most recent failures. All data comes from existing API endpoints; no
 * state is fabricated and no mutation is performed.
 *
 * For daily manual operations, the landing asks the backend action matrix for
 * the ResourceLibrary scopes this principal may use and offers a Scan/Preview
 * entry only for the exact scope the backend advertises as actionable. A
 * disabled or unadvertised library shows the backend reason instead of a
 * control.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { workerReadinessQueryOptions } from "./worker-query";
import { manualActionsQueryOptions } from "./manual-actions-query";
import type { ManualActionMatrixModel } from "../../entities/operations/manual-actions";

function ManualOperationsSection({
  matrix,
}: {
  readonly matrix: ManualActionMatrixModel;
}) {
  const navigate = useNavigate();
  const [selected, setSelected] = useState("");
  const choices = matrix.resourceLibraries;
  const actionable =
    matrix.actions.scan.available || matrix.actions.preview.available;

  return (
    <section className="mf-count-section">
      <h3>Manual operations</h3>
      <p className="mf-dashboard-meta">
        Start a bounded Scan or run a zero-mutation Preview from one exact
        ResourceLibrary scope. Scan discovers and indexes source files; Preview
        runs the complete pipeline with zero Storage mutation.
      </p>
      {choices.length === 0 ? (
        <p className="mf-dashboard-meta">
          The Active configuration exposes no ResourceLibrary this principal may
          scan or preview.
        </p>
      ) : (
        <p>
          <label htmlFor="operations-resource-library">
            ResourceLibrary scope
          </label>{" "}
          <select
            id="operations-resource-library"
            aria-label="ResourceLibrary scope"
            value={selected}
            onChange={(event) => {
              const chosen = event.target.value;
              setSelected(chosen);
              if (chosen) {
                void navigate({
                  to: "/operations",
                  search: {
                    scopeKind: "resourceLibrary",
                    resourceLibraryId: chosen,
                  },
                  replace: true,
                });
              }
            }}
          >
            <option value="">Choose a ResourceLibrary</option>
            {choices.map((library) => (
              <option
                key={library.resourceLibraryId}
                value={library.resourceLibraryId}
                disabled={!library.enabled}
              >
                {library.resourceLibraryId}
                {library.enabled ? "" : " (disabled)"}
              </option>
            ))}
          </select>
        </p>
      )}
      {selected !== "" && !actionable && (
        <p className="mf-dashboard-meta">
          No manual action is available for this scope:{" "}
          {matrix.actions.scan.reason ??
            matrix.actions.preview.reason ??
            "the backend does not advertise one"}
        </p>
      )}
      {actionable && (
        <nav className="mf-actions" aria-label="Manual operations">
          {matrix.actions.scan.available && (
            <Link
              className="mf-button mf-button-secondary"
              to="/operations/scan/new"
              search={{
                scopeKind: "resourceLibrary",
                resourceLibraryId: matrix.resourceLibraryId ?? undefined,
              }}
            >
              Start bounded Scan
            </Link>
          )}
          {matrix.actions.preview.available && (
            <Link
              className="mf-button mf-button-secondary"
              to="/operations/preview/new"
              search={{
                scopeKind: "resourceLibrary",
                resourceLibraryId: matrix.resourceLibraryId ?? undefined,
              }}
            >
              Run zero-mutation Preview
            </Link>
          )}
          {matrix.actions.organize.available && (
            <Link
              className="mf-button mf-button-secondary"
              to="/operations/organize/new"
              search={{
                scopeKind: "resourceLibrary",
                resourceLibraryId: matrix.resourceLibraryId ?? undefined,
              }}
            >
              Prepare manual organize
            </Link>
          )}
        </nav>
      )}
    </section>
  );
}

export function OperationsLanding() {
  const token = useAuthToken();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const chosenLibraryId = searchParams.resourceLibraryId
    ? String(searchParams.resourceLibraryId)
    : null;
  const readinessQuery = useQuery(workerReadinessQueryOptions(token));
  const matrixQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind: chosenLibraryId ? "resourceLibrary" : null,
      resourceLibraryId: chosenLibraryId,
    }),
  );

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
                <Link
                  className="mf-button mf-button-primary"
                  to="/operations/automation"
                >
                  Automation
                </Link>
                <Link
                  className="mf-button mf-button-primary"
                  to="/operations/notifications"
                >
                  Notifications
                </Link>
              </nav>
            </section>
            {matrixQuery.data?.ok === true ? (
              <ManualOperationsSection matrix={matrixQuery.data.model} />
            ) : (
              <section className="mf-count-section">
                <h3>Manual operations</h3>
                <p className="mf-dashboard-meta">
                  {matrixQuery.data === undefined
                    ? "Loading the ResourceLibrary scopes the backend advertises."
                    : "The backend action matrix could not be read, so no manual action is offered."}
                </p>
              </section>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
