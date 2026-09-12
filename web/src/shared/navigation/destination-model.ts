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
    availability: "implemented" as const,
    description: "Tasks, Jobs and Worker workspace for daily operations.",
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
 * navigation items. A child with `dynamicPrefix` additionally accepts
 * concrete one-segment instances of itself (e.g. a parameterized detail
 * route), so deep links and post-reconnect continuations resolve against the
 * same navigation contract as the static routes.
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
  {
    id: "library-file-index",
    label: "FileIndex",
    path: "/library/file-index",
    title: "FileIndex | MediaFlow",
    availability: "implemented" as const,
    description: "Browse the durable indexed discovery records.",
  },
  {
    id: "library-file-index-detail",
    label: "FileIndex detail",
    path: "/library/file-index/$fileId",
    title: "FileIndex detail | MediaFlow",
    availability: "implemented" as const,
    description: "Read-only detail for one indexed FileIndex discovery record.",
    dynamicPrefix: "/library/file-index/" as const,
  },
  {
    id: "operations-tasks",
    label: "Task list",
    path: "/operations/tasks",
    title: "Tasks | MediaFlow",
    availability: "implemented" as const,
    description: "List, filter and page durable Tasks.",
  },
  {
    id: "operations-task-detail",
    label: "Task detail",
    path: "/operations/tasks/$taskId",
    title: "Task detail | MediaFlow",
    availability: "implemented" as const,
    description: "Task aggregate, independent TaskItems and Results.",
    dynamicPrefix: "/operations/tasks/" as const,
  },
  {
    id: "operations-jobs",
    label: "Job list",
    path: "/operations/jobs",
    title: "Jobs | MediaFlow",
    availability: "implemented" as const,
    description: "List and page durable Jobs.",
  },
  {
    id: "operations-job-detail",
    label: "Job detail",
    path: "/operations/jobs/$jobId",
    title: "Job detail | MediaFlow",
    availability: "implemented" as const,
    description: "Job admission state, linked Task and Worker ownership.",
    dynamicPrefix: "/operations/jobs/" as const,
  },
  {
    id: "operations-scan-new",
    label: "Start Scan",
    path: "/operations/scan/new",
    title: "Start Scan | MediaFlow",
    availability: "implemented" as const,
    description: "Submit a bounded server-bound Scan admission.",
  },
  {
    id: "operations-scan-detail",
    label: "Scan detail",
    path: "/operations/scan/$taskId",
    title: "Scan detail | MediaFlow",
    availability: "implemented" as const,
    description: "Bounded scan document, progress and per-item findings.",
    dynamicPrefix: "/operations/scan/" as const,
  },
  {
    id: "operations-preview-new",
    label: "Start Preview",
    path: "/operations/preview/new",
    title: "Start Preview | MediaFlow",
    availability: "implemented" as const,
    description: "Submit a bounded zero-mutation Preview admission.",
  },
  {
    id: "operations-preview-detail",
    label: "Preview detail",
    path: "/operations/preview/$previewId",
    title: "Preview detail | MediaFlow",
    availability: "implemented" as const,
    description: "Bounded preview document, items and zero-mutation evidence.",
    dynamicPrefix: "/operations/preview/" as const,
  },
  {
    id: "operations-organize-new",
    label: "Manual organize",
    path: "/operations/organize/new",
    title: "Manual organize | MediaFlow",
    availability: "implemented" as const,
    description:
      "Create a durable manual organize intent from one exact scope.",
  },
  {
    id: "operations-organize-intent",
    label: "Manual intent",
    path: "/operations/organize/intent/$intentId",
    title: "Manual intent | MediaFlow",
    availability: "implemented" as const,
    description:
      "Durable manual intent choices, previews and refresh-safe continuation.",
    dynamicPrefix: "/operations/organize/intent/" as const,
  },
  {
    id: "operations-organize-preview",
    label: "Exact organize Preview",
    path: "/operations/organize/preview/$previewId",
    title: "Exact organize Preview | MediaFlow",
    availability: "implemented" as const,
    description:
      "Exact reviewed items, destructive implications and one Execute action.",
    dynamicPrefix: "/operations/organize/preview/" as const,
  },
  {
    id: "operations-organize-execution",
    label: "Organize execution",
    path: "/operations/organize/execution/$executionId",
    title: "Organize execution | MediaFlow",
    availability: "implemented" as const,
    description:
      "Durable admitted execution, Worker outcome and independent item results.",
    dynamicPrefix: "/operations/organize/execution/" as const,
  },
  {
    id: "operations-automation",
    label: "Automation",
    path: "/operations/automation",
    title: "Automation | MediaFlow",
    availability: "implemented" as const,
    description:
      "Scheduled Automation Task Definitions, unattended authority and occurrences.",
  },
  {
    id: "operations-automation-new",
    label: "Create Automation definition",
    path: "/operations/automation/new",
    title: "Create Automation definition | MediaFlow",
    availability: "implemented" as const,
    description:
      "Bounded successor-Draft form for one scheduled Automation definition.",
  },
  {
    id: "operations-automation-definition",
    label: "Automation definition",
    path: "/operations/automation/definition/$definitionId",
    title: "Automation definition | MediaFlow",
    availability: "implemented" as const,
    description:
      "Active and Draft identity, schedule state, grant authority and actions.",
    dynamicPrefix: "/operations/automation/definition/" as const,
  },
  {
    id: "operations-automation-editor",
    label: "Automation Draft editor",
    path: "/operations/automation/editor/$definitionId",
    title: "Automation Draft editor | MediaFlow",
    availability: "implemented" as const,
    description:
      "Bounded Draft form, explicit validation and checked activation.",
    dynamicPrefix: "/operations/automation/editor/" as const,
  },
  {
    id: "operations-automation-preview",
    label: "Automation Preview",
    path: "/operations/automation/preview/$definitionId/$previewId",
    title: "Automation Preview | MediaFlow",
    availability: "implemented" as const,
    description:
      "Exact zero-mutation Preview evidence, paged items and grant eligibility.",
    dynamicPrefix: "/operations/automation/preview/" as const,
  },
  {
    id: "operations-automation-occurrences",
    label: "Automation occurrences",
    path: "/operations/automation/occurrences/$definitionId",
    title: "Automation occurrences | MediaFlow",
    availability: "implemented" as const,
    description:
      "Bounded occurrence history with pinned snapshots and linked work.",
    dynamicPrefix: "/operations/automation/occurrences/" as const,
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
  /** Present only for parameterized routes. A concrete instance is exactly
   * one non-empty path segment after this prefix. */
  readonly dynamicPrefix?: string;
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

/** True only for a concrete one-segment instance of a dynamic destination. */
/**
 * One bounded, URI-safe concrete identity segment of a dynamic destination
 * instance. The journey identifiers are server-shaped durable identities;
 * anything else (empty, traversal, placeholder or oversized) never resolves
 * to a supported destination.
 */
const INSTANCE_SEGMENT = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

function dynamicInstancePath(value: string): Destination | undefined {
  for (const destination of childDestinations) {
    const prefix = destination.dynamicPrefix;
    if (prefix === undefined || !value.startsWith(prefix)) {
      continue;
    }
    // The concrete instance must carry exactly the declared number of bounded
    // identity segments, so an unknown deeper route stays the shell's
    // not-found responsibility instead of borrowing a nearby destination.
    const declared = destination.path
      .split("/")
      .filter((segment) => segment.startsWith("$")).length;
    const rest = value.slice(prefix.length);
    if (rest.length === 0 || rest.startsWith("$")) {
      continue;
    }
    const segments = rest.split("/");
    if (
      segments.length !== declared ||
      segments.some(
        (segment) =>
          segment === "" || segment === ".." || !INSTANCE_SEGMENT.test(segment),
      )
    ) {
      continue;
    }
    return destination;
  }
  return undefined;
}

/** Type guard for a path that exists in the centralized destination model.
 * Concrete one-segment instances of dynamic destinations also pass. */
export function isDestinationPath(value: string): value is DestinationPath {
  return (
    destinationPathSet.has(value) || dynamicInstancePath(value) !== undefined
  );
}

/** A backend-submitted Operations status filter is a bounded lowercase token. */
const STATUS_FILTER_TOKEN = /^[a-z][a-z0-9_]{0,31}$/;
/** A backend-submitted Operations command filter is a bounded work-kind token. */
const COMMAND_FILTER_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/;

/**
 * Return only the first safe values of allowlisted query keys for the
 * given destination. Arbitrary or credential-like keys are dropped so a
 * rejected 401 can never replay unknown state on reconnect.
 */
export function allowlistedDestinationSearch(
  path: DestinationPath,
  search: string,
): string | null {
  const setSafe = (
    target: URLSearchParams,
    key: string,
    value: string | null,
  ) => {
    if (
      value !== null &&
      value.length <= 512 &&
      // eslint-disable-next-line no-control-regex
      !/[\u0000-\u001f\u007f]/.test(value)
    ) {
      target.set(key, value);
    }
  };
  /**
   * A value must satisfy one closed shape to enter an Operations URL: a filter
   * value that does not match the backend's bounded token grammar (including
   * anything credential-like, path-like or free-form) is dropped instead.
   */
  const setFilterToken = (
    target: URLSearchParams,
    key: string,
    value: string | null,
    pattern: RegExp,
  ) => {
    if (value !== null && pattern.test(value)) {
      target.set(key, value);
    }
  };
  if (path === "/library/files") {
    const allowed = new URLSearchParams();
    const current = new URLSearchParams(search);
    for (const key of [
      "storage",
      "resourceLibrary",
      "path",
      "cursor",
    ] as const) {
      const value = current.get(key);
      setSafe(allowed, key, value);
    }
    return allowed.toString().length > 0 ? allowed.toString() : null;
  }
  if (path === "/library/file-index") {
    const allowed = new URLSearchParams();
    const current = new URLSearchParams(search);
    for (const key of [
      "resourceLibrary",
      "storage",
      "scanStatus",
      "query",
      "processingDisposition",
      "recognitionType",
      "provider",
      "providerId",
      "title",
      "taskId",
      "year",
      "after",
      "before",
      "cursorFileId",
    ] as const) {
      const value = current.get(key);
      setSafe(allowed, key, value);
    }
    return allowed.toString().length > 0 ? allowed.toString() : null;
  }
  if (path === "/library/file-index/$fileId") {
    // A detail link only carries the catalog return context back, and that
    // context uses `q_`-prefixed keys exclusively. Anything else
    // (credentials, unknown state) is dropped before reconnect replay.
    const allowed = new URLSearchParams();
    const current = new URLSearchParams(search);
    const detailKeys = new Set([
      "q_resourceLibrary",
      "q_storage",
      "q_scanStatus",
      "q_query",
      "q_processingDisposition",
      "q_recognitionType",
      "q_provider",
      "q_providerId",
      "q_title",
      "q_taskId",
      "q_year",
      "q_after",
      "q_cursorFileId",
      "q_before",
    ]);
    for (const key of current.keys()) {
      if (!detailKeys.has(key)) {
        continue;
      }
      const value = current.get(key);
      if (value !== null && !allowed.has(key)) {
        setSafe(allowed, key, value);
      }
    }
    return allowed.toString().length > 0 ? allowed.toString() : null;
  }
  if (path === "/operations/tasks" || path === "/operations/jobs") {
    // Only the backend-submitted filter values travel in the URL, so a
    // reconnect resumes the same bounded collection read and never replays
    // credential-like, authority-bearing or arbitrary state.
    const allowed = new URLSearchParams();
    const current = new URLSearchParams(search);
    setFilterToken(
      allowed,
      "status",
      current.get("status"),
      STATUS_FILTER_TOKEN,
    );
    setFilterToken(
      allowed,
      "command",
      current.get("command"),
      COMMAND_FILTER_TOKEN,
    );
    return allowed.toString().length > 0 ? allowed.toString() : null;
  }
  if (
    path === "/operations/tasks/$taskId" ||
    path === "/operations/jobs/$jobId"
  ) {
    // A detail route carries only its bounded parent-list filter context back.
    const allowed = new URLSearchParams();
    const current = new URLSearchParams(search);
    setFilterToken(
      allowed,
      "q_status",
      current.get("q_status"),
      STATUS_FILTER_TOKEN,
    );
    setFilterToken(
      allowed,
      "q_command",
      current.get("q_command"),
      COMMAND_FILTER_TOKEN,
    );
    return allowed.toString().length > 0 ? allowed.toString() : null;
  }
  if (path === "/operations/scan/new" || path === "/operations/preview/new") {
    // Admission routes carry only their bounded scope parameters.
    const allowed = new URLSearchParams();
    const current = new URLSearchParams(search);
    setSafe(allowed, "scopeKind", current.get("scopeKind"));
    setSafe(allowed, "fileId", current.get("fileId"));
    setSafe(allowed, "resourceLibraryId", current.get("resourceLibraryId"));
    return allowed.toString().length > 0 ? allowed.toString() : null;
  }
  if (path === "/operations/organize/new") {
    // The manual Organize entry carries only its bounded scope parameters.
    const allowed = new URLSearchParams();
    const current = new URLSearchParams(search);
    setSafe(allowed, "scopeKind", current.get("scopeKind"));
    setSafe(allowed, "fileId", current.get("fileId"));
    setSafe(allowed, "resourceLibraryId", current.get("resourceLibraryId"));
    return allowed.toString().length > 0 ? allowed.toString() : null;
  }
  if (
    path === "/operations/scan/$taskId" ||
    path === "/operations/preview/$previewId" ||
    path === "/operations/organize/intent/$intentId" ||
    path === "/operations/organize/preview/$previewId" ||
    path === "/operations/organize/execution/$executionId" ||
    path === "/operations/automation/new" ||
    path === "/operations/automation/definition/$definitionId" ||
    path === "/operations/automation/editor/$definitionId" ||
    path === "/operations/automation/preview/$definitionId/$previewId" ||
    path === "/operations/automation/occurrences/$definitionId"
  ) {
    // Detail routes carry no search state.
    return null;
  }
  return null;
}

export function destinationForPath(pathname: string): Destination | undefined {
  const path = pathname.replace(/\/$/, "") || "/";
  const exact =
    destinations.find((destination) => destination.path === path) ??
    childDestinations.find((destination) => destination.path === path);
  if (exact) {
    return exact;
  }
  const dynamic = dynamicInstancePath(path);
  return dynamic === undefined
    ? undefined
    : childDestinations.find((destination) => destination.id === dynamic.id);
}
