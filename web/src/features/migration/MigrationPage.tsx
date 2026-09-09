import { Link, useRouterState } from "@tanstack/react-router";
import { destinationForPath } from "../../shared/navigation/destination-model";
import { StatusBanner } from "../../shared/ui/StatusBanner";

/** Honest in-shell landing state for product areas owned by later Slices. */
export function MigrationPage() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const destination = destinationForPath(pathname);

  if (destination === undefined) {
    return null;
  }

  return (
    <StatusBanner
      variant="info"
      title={`${destination.label} is not available in V2 yet`}
    >
      <p>{destination.description}</p>
      <p>
        This area will be added through the planned MediaFlow migration. The
        current Web UI remains the supported continuation for this journey.
      </p>
      <div className="mf-actions">
        <a
          className="mf-button mf-button-primary"
          href={destination.v1Path ?? "/ui"}
        >
          Open current Web UI
        </a>
        <Link className="mf-button mf-button-secondary" to="/dashboard">
          Return to Overview
        </Link>
      </div>
    </StatusBanner>
  );
}
