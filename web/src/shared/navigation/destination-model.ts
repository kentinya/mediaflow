/**
 * One operator-oriented route contract for the V2 product areas.
 *
 * `destinationData` below is the single literal source of truth. The typed
 * `DestinationPath` union, the runtime allowlist (`destinationPaths`) and its
 * guard (`isDestinationPath`) are all derived from that literal, so no second
 * enumeration can drift from the navigation model: a path that is not present
 * in the data is neither a valid type nor an allowed continuation target.
 */
const destinationData = [
  {
    id: "overview",
    label: "Overview",
    path: "/dashboard",
    title: "Overview | MediaFlow",
    availability: "implemented" as const,
    description:
      "Read-only operational snapshot for the connected MediaFlow instance.",
  },
  {
    id: "library",
    label: "Library",
    path: "/library",
    title: "Library | MediaFlow",
    availability: "implemented" as const,
    description:
      "Browse the configured Active Storage and its FileIndex membership in V2.",
  },
  {
    id: "operations",
    label: "Operations",
    path: "/operations",
    title: "Operations | MediaFlow",
    availability: "migration" as const,
    description:
      "Tasks, Jobs and automation workspace migration is not available yet.",
    v1Path: "/ui" as const,
  },
  {
    id: "review",
    label: "Review & Recovery",
    path: "/review",
    title: "Review & Recovery | MediaFlow",
    availability: "migration" as const,
    description:
      "Recognition, metadata, conflict and recovery journeys remain in the current Web UI.",
    v1Path: "/ui" as const,
  },
  {
    id: "configuration",
    label: "Configuration",
    path: "/configuration",
    title: "Configuration | MediaFlow",
    availability: "migration" as const,
    description:
      "Managed configuration administration is not yet migrated to this V2 surface.",
    v1Path: "/ui" as const,
  },
] as const;

/**
 * Typed supported child routes inside top-level product destinations. They
 * participate in titles/continuation allowlisting without becoming primary
 * navigation items.
 */
const childDestinationData = [
  {
    id: "library-files",
    label: "Storage files",
    path: "/library/files",
    title: "Storage files | MediaFlow",
    availability: "implemented" as const,
    description: "Browse the configured Active Storage.",
  },
] as const;

export type DestinationAvailability = "implemented" | "migration";

/**
 * The canonical typed set of operator-route paths, derived from the single
 * `destinationData` literal so the continuation allowlist and its runtime
 * validator can never disagree with the navigation model.
 */
export type DestinationPath =
  | (typeof destinationData)[number]["path"]
  | (typeof childDestinationData)[number]["path"];

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
export const destinations: readonly Destination[] = destinationData;

/** Supported child routes are typed and allowlisted but not top-level nav items. */
export const childDestinations: readonly Destination[] = childDestinationData;

/**
 * Every operator route path, derived from the single destination contract so
 * continuation allowlisting can never drift from the typed navigation model.
 */
export const destinationPaths: readonly DestinationPath[] = destinations.map(
  (destination) => destination.path,
);

export const allDestinationPaths: readonly DestinationPath[] = [
  ...destinationPaths,
  ...childDestinations.map((destination) => destination.path),
];

const destinationPathSet: ReadonlySet<string> = new Set(allDestinationPaths);

/** Type guard for a path that exists in the centralized destination model. */
export function isDestinationPath(value: string): value is DestinationPath {
  return destinationPathSet.has(value);
}

export function destinationForPath(pathname: string): Destination | undefined {
  const path = pathname.replace(/\/$/, "") || "/";
  return (
    destinations.find((destination) => destination.path === path) ??
    childDestinations.find((destination) => destination.path === path)
  );
}
