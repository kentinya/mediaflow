import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { systemStatusQueryOptions } from "./system-status-query";
import { manualActionsQueryOptions } from "../operations/manual-actions-query";

/**
 * Library landing for the ResourceLibrary Files journey. Browsing starts no
 * work, reads no media content and mutates no Storage.
 *
 * A bounded Operations cross-link is offered so an operator in the daily
 * operations flow can reach the Task/Job workspace without copying an
 * identifier, a path or an authority value into a URL.
 *
 * For each ResourceLibrary in the Active runtime, the landing offers a
 * bounded Scan and Preview admission entry only when the backend action
 * matrix advertises that action for the exact principal and scope.  The
 * status read is deferred until the operator indicates intent to start work,
 * so a transient status failure never breaks the core Library navigation, and
 * an unadvertised action renders the backend reason instead of a control.
 */
function ResourceLibraryActions({
  resourceLibraryId,
}: {
  readonly resourceLibraryId: string;
}) {
  const token = useAuthToken();
  const matrixQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind: "resourceLibrary",
      resourceLibraryId,
    }),
  );

  if (matrixQuery.data === undefined) {
    return (
      <p className="mf-dashboard-meta">
        Checking backend action availability for this ResourceLibrary.
      </p>
    );
  }
  if (!matrixQuery.data.ok) {
    return (
      <p className="mf-dashboard-meta">
        Action availability could not be loaded. No action is offered.
      </p>
    );
  }
  const { actions } = matrixQuery.data.model;
  return (
    <div className="mf-actions">
      {actions.scan.available ? (
        <Link
          className="mf-button mf-button-secondary"
          to="/operations/scan/new"
          search={{ scopeKind: "resourceLibrary", resourceLibraryId }}
        >
          Start bounded Scan
        </Link>
      ) : (
        <p className="mf-dashboard-meta">
          Scan unavailable: {actions.scan.reason ?? "not available"}
        </p>
      )}
      {actions.preview.available ? (
        <Link
          className="mf-button mf-button-secondary"
          to="/operations/preview/new"
          search={{ scopeKind: "resourceLibrary", resourceLibraryId }}
        >
          Run zero-mutation Preview
        </Link>
      ) : (
        <p className="mf-dashboard-meta">
          Preview unavailable: {actions.preview.reason ?? "not available"}
        </p>
      )}
    </div>
  );
}
export function LibraryLanding() {
  const token = useAuthToken();
  const [showResourceLibraries, setShowResourceLibraries] = useState(false);
  const statusQuery = useQuery({
    ...systemStatusQueryOptions(token),
    enabled: showResourceLibraries && token !== null,
  });
  const resourceLibraries =
    statusQuery.data?.resourceLibraries.filter((lib) => lib.enabled) ?? [];

  return (
    <div className="mf-library-landing">
      <header className="mf-dashboard-head">
        <div>
          <h2>Library</h2>
          <p className="mf-dashboard-meta">
            Browse live Storage files through ResourceLibrary boundaries.
            FileIndex remains a background/V1 catalog, not a UI-V2 file source.
          </p>
        </div>
        {showResourceLibraries && (
          <RefreshControl
            onRefresh={() => void statusQuery.refetch()}
            refreshing={statusQuery.isFetching}
          />
        )}
      </header>
      <ul className="mf-library-choices">
        <li className="mf-library-choice">
          <h3>Files</h3>
          <p>
            Choose a ResourceLibrary, browse only that library's configured
            root, select files, and create a zero-mutation organize Preview.
          </p>
          <Link className="mf-button mf-button-primary" to="/library/files">
            Open Files
          </Link>
        </li>
      </ul>
      {!showResourceLibraries ? (
        <section className="mf-count-section">
          <h3>ResourceLibrary actions</h3>
          <p className="mf-dashboard-meta">
            Start a bounded Scan or run a zero-mutation Preview for each
            configured ResourceLibrary.
          </p>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => setShowResourceLibraries(true)}
            >
              Show ResourceLibrary actions
            </button>
          </div>
        </section>
      ) : resourceLibraries.length > 0 ? (
        <section className="mf-count-section">
          <h3>ResourceLibrary actions</h3>
          <p>
            Start a bounded Scan or run a zero-mutation Preview for each
            configured ResourceLibrary. Scan discovers and indexes source files;
            Preview runs the complete pipeline with zero Storage mutation.
          </p>
          {resourceLibraries.map((library) => (
            <div key={library.id} className="mf-count-section">
              <h4>{library.name ?? library.id}</h4>
              <dl>
                <dt>ResourceLibrary</dt>
                <dd>{library.id}</dd>
                <dt>Storage</dt>
                <dd>{library.storageId}</dd>
              </dl>
              <ResourceLibraryActions resourceLibraryId={library.id} />
            </div>
          ))}
        </section>
      ) : (
        <section className="mf-count-section">
          <h3>ResourceLibrary actions</h3>
          <p className="mf-dashboard-meta">
            No enabled ResourceLibraries are configured for Scan or Preview.
          </p>
        </section>
      )}
      <section className="mf-count-section">
        <h3>Operations</h3>
        <p>
          Library discovery and processing state is produced by Operations
          Tasks. Use Files to create a Preview, then follow the resulting Task
          or Job in the Operations workspace.
        </p>
        <div className="mf-actions">
          <Link
            className="mf-button mf-button-secondary"
            to="/operations/tasks"
          >
            Open Operations Tasks
          </Link>
          <Link className="mf-button mf-button-secondary" to="/operations/jobs">
            Open Operations Jobs
          </Link>
        </div>
      </section>
    </div>
  );
}
