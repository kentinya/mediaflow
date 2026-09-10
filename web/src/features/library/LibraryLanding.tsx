import { Link } from "@tanstack/react-router";

/**
 * Library landing for the two deliberately separate read journeys. Neither
 * choice starts work, reads media content or mutates Storage.
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
    </div>
  );
}
