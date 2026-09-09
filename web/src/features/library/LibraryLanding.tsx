import { Link } from "@tanstack/react-router";

/**
 * Library landing: the physical Storage files journey is implemented in V2,
 * while FileIndex remains an honest current-Web continuation until its own
 * Slice 32 Task. No read action here starts work or mutates state.
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
            Durable indexed discovery records are not available in V2 yet. The
            current Web UI remains the supported continuation for FileIndex.
          </p>
          <a className="mf-button mf-button-secondary" href="/ui">
            Open current Web UI
          </a>
        </li>
      </ul>
    </div>
  );
}
