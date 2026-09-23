import { Link } from "@tanstack/react-router";
import { StatusBanner } from "../../shared/ui/StatusBanner";

/**
 * Manual Organize starts from UI-V2 Files: ResourceLibrary -> live Storage file
 * -> zero-mutation Preview.  This route remains as a compatibility landing
 * page, but it no longer exposes FileIndex catalog selection or durable intent
 * creation as the ordinary UI-V2 admission path.
 */
export function OrganizeNewPage() {
  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <div>
          <h2>Manual organize</h2>
          <p className="mf-dashboard-meta">
            Select a ResourceLibrary file first. Preview decides the exact plan;
            execution uses the reviewed Preview and live Storage revalidation.
          </p>
        </div>
      </header>
      <StatusBanner variant="info" title="Start from Files">
        <p>
          UI-V2 no longer starts manual organize from FileIndex records. Browse
          a ResourceLibrary, select a file, and create a zero-mutation Preview.
        </p>
        <div className="mf-actions">
          <Link className="mf-button" to="/resourcelib/files">
            Open Files
          </Link>
          <Link className="mf-button mf-button-secondary" to="/operations">
            Back to Operations
          </Link>
        </div>
      </StatusBanner>
    </div>
  );
}
