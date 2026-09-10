import { Link } from "@tanstack/react-router";

/**
 * Library landing for the two deliberately separate read journeys. Neither
 * choice starts work, reads media content or mutates Storage.
 *
 * A bounded Operations cross-link is offered so an operator in the daily
 * operations flow can reach the Task/Job workspace without copying an
 * identifier, a path or an authority value into a URL.
 */
export function LibraryLanding() {
  return (
    <div className="mf-library-landing">
      <h2>Library</h2>
      <p>
        Choose whether to inspect the configured Active Storage directly or the
        durable FileIndex records MediaFlow keeps about discovered files. The
        two are different views of MediaFlow state: Storage files is a live,
        bounded read of the configured Storage; FileIndex is the discovery
        record.
      </p>
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
