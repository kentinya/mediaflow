import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { systemStatusQueryOptions } from "./system-status-query";

/**
 * Library landing for the two deliberately separate read journeys. Neither
 * choice starts work, reads media content or mutates Storage.
 *
 * A bounded Operations cross-link is offered so an operator in the daily
 * operations flow can reach the Task/Job workspace without copying an
 * identifier, a path or an authority value into a URL.
 *
 * For each ResourceLibrary in the Active runtime, the landing offers
 * bounded Scan and Preview admission links so the operator can start
 * work directly from the Library.  The status read is deferred until the
 * operator indicates intent to start work, so a transient status failure
 * never breaks the core Library navigation.
 */
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
            Choose whether to inspect the configured Active Storage directly or
            the durable FileIndex records MediaFlow keeps about discovered
            files.
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
          <h3>Storage files</h3>
          <p>
            Browse the selected Active Storage root and its immediate
            directories, one bounded page at a time, and see FileIndex
            membership where it is available.
          </p>
          <Link className="mf-button mf-button-primary" to="/library/files">
            Open Storage files
          </Link>
        </li>
        <li className="mf-library-choice">
          <h3>FileIndex</h3>
          <p>
            Search and filter durable indexed discovery records separately from
            the live Storage view. Discovery, occurrence and processing facts
            remain distinct and read-only.
          </p>
          <Link
            className="mf-button mf-button-secondary"
            to="/library/file-index"
          >
            Open FileIndex catalog
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
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/scan/new"
                  search={{
                    scopeKind: "resourceLibrary",
                    resourceLibraryId: library.id,
                  }}
                >
                  Start bounded Scan
                </Link>
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/preview/new"
                  search={{
                    scopeKind: "resourceLibrary",
                    resourceLibraryId: library.id,
                  }}
                >
                  Run zero-mutation Preview
                </Link>
              </div>
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
          Tasks. Follow the exact Task or Job behind a FileIndex record in the
          Operations workspace; this page reads state only and starts no work.
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
