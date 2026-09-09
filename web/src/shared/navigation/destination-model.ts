export type DestinationAvailability = "implemented" | "migration";

/**
 * The canonical typed set of operator-route paths. `destinations` below is
 * checked against this union, and `destinationPaths` / `isDestinationPath`
 * derive the runtime allowlist from the same contract, so no second list can
 * drift from the navigation model.
 */
export type DestinationPath =
  "/dashboard" | "/library" | "/operations" | "/review" | "/configuration";

export interface Destination {
  readonly id: string;
  readonly label: string;
  readonly path: DestinationPath;
  readonly title: string;
  readonly availability: DestinationAvailability;
  readonly description: string;
  readonly v1Path?: "/ui";
}

/** The single operator-goal navigation contract consumed by routes and shell. */
export const destinations: readonly Destination[] = [
  {
    id: "overview",
    label: "Overview",
    path: "/dashboard",
    title: "Overview | MediaFlow",
    availability: "implemented",
    description:
      "Read-only operational snapshot for the connected MediaFlow instance.",
  },
  {
    id: "library",
    label: "Library",
    path: "/library",
    title: "Library | MediaFlow",
    availability: "migration",
    description:
      "Library and Files journeys are moving to V2 in a later release.",
    v1Path: "/ui",
  },
  {
    id: "operations",
    label: "Operations",
    path: "/operations",
    title: "Operations | MediaFlow",
    availability: "migration",
    description:
      "Tasks, Jobs and automation workspace migration is not available yet.",
    v1Path: "/ui",
  },
  {
    id: "review",
    label: "Review & Recovery",
    path: "/review",
    title: "Review & Recovery | MediaFlow",
    availability: "migration",
    description:
      "Recognition, metadata, conflict and recovery journeys remain in the current Web UI.",
    v1Path: "/ui",
  },
  {
    id: "configuration",
    label: "Configuration",
    path: "/configuration",
    title: "Configuration | MediaFlow",
    availability: "migration",
    description:
      "Managed configuration administration is not yet migrated to this V2 surface.",
    v1Path: "/ui",
  },
];

/**
 * Every operator route path, derived from the single destination contract so
 * continuation allowlisting can never drift from the typed navigation model.
 */
export const destinationPaths: readonly DestinationPath[] = destinations.map(
  (destination) => destination.path,
);

const destinationPathSet: ReadonlySet<string> = new Set(destinationPaths);

/** Type guard for a path that exists in the centralized destination model. */
export function isDestinationPath(value: string): value is DestinationPath {
  return destinationPathSet.has(value);
}

export function destinationForPath(pathname: string): Destination | undefined {
  const path = pathname.replace(/\/$/, "") || "/";
  return destinations.find((destination) => destination.path === path);
}
