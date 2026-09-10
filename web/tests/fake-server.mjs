/**
 * Local fake API + static server for the minimal Playwright browser path.
 *
 * It serves the built V2 artifact from web/dist under /ui-v2/ and fake
 * /api/v1/dashboard, /api/v1/system/status, /api/v1/file-index and
 * /api/v1/storage/files GET
 * documents that mirror the existing Python contracts. Every unsupported
 * method is rejected with 405; no production credentials, media, Storage or
 * external providers are involved, and no token material is ever logged.
 */

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HOST = "127.0.0.1";
const PORT = Number(process.env.FAKE_PORT ?? 4173);
const DIST = fileURLToPath(new URL("../dist", import.meta.url));

const VIEWER_TOKENS = new Set(["e2e-viewer-token"]);
const LIMITED_TOKENS = new Set(["e2e-limited-token"]);
const EXPIRED_TOKENS = new Set(["e2e-expired-token"]);

const DASHBOARD_SNAPSHOT = {
  as_of: "2026-08-22T12:00:00+00:00",
  resource_libraries: 1,
  media_libraries: 1,
  files: { total: 12, ready: 9, unstable: 1, missing: 1, errors: 1 },
  tasks: {
    total: 4,
    pending: 1,
    running: 1,
    completed: 1,
    partial_success: 0,
    failed: 1,
    cancelled: 0,
    paused: 0,
  },
  jobs: {
    total: 2,
    pending: 1,
    running: 0,
    completed: 1,
    failed: 0,
    cancelled: 0,
  },
  pending_confirmations: 0,
  pending_metadata_reviews: 1,
  pending_classification_reviews: 0,
  dead_letter_notifications: 0,
  recent_failures: [
    {
      kind: "job",
      identifier: "job-e2e-1",
      status: "failed",
      occurred_at: "2026-08-22T11:58:00+00:00",
      category: "processing_error",
    },
  ],
};

// --- Operations fake data ---

const TASK_ITEMS = [
  {
    item_id: "item-001",
    task_id: "task-001",
    storage_id: "local-media",
    resource_library_id: "resources",
    source_path: "movies/The Matrix (1999).mkv",
    source_display: "The Matrix (1999).mkv",
    status: "success",
    stage: "organizing",
    attempts: 1,
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:05:00+00:00",
    plan_id: "plan-001",
    destination_storage_id: "local-media",
    destination_path: "Media/Movies/The Matrix (1999)/The Matrix (1999).mkv",
    execution_status: "completed",
    error: null,
    checkpoint: {
      status: "completed",
      stage: "organizing",
      attempts: 1,
      effect_certainty: "verified_complete",
      retry_safety: "safe",
      next_action: null,
      error_category: "none",
    },
  },
  {
    item_id: "item-002",
    task_id: "task-001",
    storage_id: "local-media",
    resource_library_id: "resources",
    source_path: "movies/Inception (2010).mkv",
    source_display: "Inception (2010).mkv",
    status: "failed",
    stage: "metadata",
    attempts: 2,
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:06:00+00:00",
    plan_id: null,
    destination_storage_id: null,
    destination_path: null,
    execution_status: null,
    error: "metadata lookup failed: TMDB timeout",
    checkpoint: {
      status: "failed",
      stage: "metadata",
      attempts: 2,
      effect_certainty: "unknown",
      retry_safety: "safe",
      next_action: "retry metadata lookup",
      error_category: "metadata",
    },
  },
];

const TASK_RESULTS = [
  {
    result_id: "result-001",
    task_id: "task-001",
    item_id: "item-001",
    source_storage_id: "local-media",
    source_path: "movies/The Matrix (1999).mkv",
    destination_storage_id: "local-media",
    destination_path: "Media/Movies/The Matrix (1999)/The Matrix (1999).mkv",
    recognition_type: "Movie",
    provider: "tmdb",
    provider_id: "603",
    metadata_policy_id: "meta-a",
    naming_policy_id: "naming-a",
    classification_policy_id: "class-a",
    organize_policy_id: "organize-move",
    operation: "move",
    status: "completed",
    created_at: "2026-08-22T12:05:00+00:00",
    title: "The Matrix",
    error: null,
    completed_operations: ["move"],
    effect_certainty: "verified_complete",
    uncertain_effects: [],
  },
];

const FAKE_TASKS = [
  {
    task_id: "task-001",
    command: "scan",
    status: "completed",
    execute_authorized: false,
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:06:00+00:00",
    started_at: "2026-08-22T12:00:01+00:00",
    completed_at: "2026-08-22T12:06:00+00:00",
    total_items: 2,
    completed_items: 1,
    failed_items: 1,
    error: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    configuration_snapshot_digest: "digest-1",
  },
  {
    task_id: "task-002",
    command: "scan",
    status: "running",
    execute_authorized: false,
    created_at: "2026-08-22T12:10:00+00:00",
    updated_at: "2026-08-22T12:10:00+00:00",
    started_at: "2026-08-22T12:10:01+00:00",
    completed_at: null,
    total_items: 5,
    completed_items: 2,
    failed_items: 0,
    error: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    configuration_snapshot_digest: "digest-1",
  },
  {
    task_id: "task-003",
    command: "preview",
    status: "pending",
    execute_authorized: false,
    created_at: "2026-08-22T12:15:00+00:00",
    updated_at: "2026-08-22T12:15:00+00:00",
    started_at: null,
    completed_at: null,
    total_items: 0,
    completed_items: 0,
    failed_items: 0,
    error: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    configuration_snapshot_digest: "digest-1",
  },
  {
    task_id: "task-004",
    command: "scan",
    status: "failed",
    execute_authorized: false,
    created_at: "2026-08-22T11:50:00+00:00",
    updated_at: "2026-08-22T11:55:00+00:00",
    started_at: "2026-08-22T11:50:01+00:00",
    completed_at: "2026-08-22T11:55:00+00:00",
    total_items: 3,
    completed_items: 0,
    failed_items: 3,
    error: "storage unavailable",
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    configuration_snapshot_digest: "digest-1",
  },
];

const FAKE_JOBS = [
  {
    job_id: "job-001",
    command: "scan",
    status: "completed",
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:06:00+00:00",
    started_at: "2026-08-22T12:00:01+00:00",
    completed_at: "2026-08-22T12:06:00+00:00",
    task_id: "task-001",
    worker_id: null,
    error: null,
    failure_category: null,
    failureExplanation: null,
    definition_id: null,
    definition_name: null,
    schedule_id: null,
  },
  {
    job_id: "job-002",
    command: "scan",
    status: "pending",
    created_at: "2026-08-22T12:15:00+00:00",
    updated_at: "2026-08-22T12:15:00+00:00",
    started_at: null,
    completed_at: null,
    task_id: "task-003",
    worker_id: null,
    error: null,
    failure_category: null,
    failureExplanation: null,
    definition_id: null,
    definition_name: null,
    schedule_id: null,
    operationalCondition: {
      condition: "no_worker",
      stage: "pending",
      durableState: "no processing worker is registered",
      sideEffects: "none",
      retrySafe: true,
      nextAction: "start a processing worker",
    },
  },
];

const SYSTEM_STATUS = {
  system: {
    application_version: "2.0.0.dev0",
    configuration_valid: true,
    configuration_authority: "MANAGED",
    configuration_snapshot_id: "rev-e2e-1",
    configuration_snapshot_digest: "digest-e2e-1",
  },
  storages: {
    total: 2,
    truncated: false,
    items: [
      {
        id: "local-media",
        name: "Local media",
        type: "local",
        read_only: true,
      },
      {
        id: "remote-media",
        name: "Remote media",
        type: "openlist",
        read_only: false,
      },
    ],
  },
  resource_libraries: {
    total: 1,
    truncated: false,
    items: [{ id: "resources", storage_id: "local-media", enabled: true }],
  },
  media_libraries: { total: 1, truncated: false, items: [] },
  recognition_types: { total: 3, truncated: false, items: [] },
  recognition_rules: { total: 3, truncated: false, items: [] },
  recognition_type_policies: { total: 3, truncated: false, items: [] },
  metadata_policies: { total: 3, truncated: false, items: [] },
  naming_policies: { total: 3, truncated: false, items: [] },
  classification_policies: { total: 3, truncated: false, items: [] },
  organize_policies: { total: 3, truncated: false, items: [] },
};

const FILE_INDEX_ITEMS = [
  {
    fileId: "file-index-example",
    storageId: "local-media",
    resourceLibraryId: "resources",
    path: "Movies/Example.mkv",
    filename: "Example.mkv",
    extension: "mkv",
    size: 2097152000,
    modifiedAt: "2026-08-22T12:10:00+00:00",
    updatedAt: "2026-08-22T12:10:00+00:00",
    firstSeenAt: "2026-08-22T11:10:00+00:00",
    lastSeenAt: "2026-08-22T12:10:00+00:00",
    stableSince: "2026-08-22T11:30:00+00:00",
    missingSince: null,
    scanStatus: "ready",
    change: "unchanged",
    occurrenceState: "verified",
    currentOccurrence: { state: "verified", current: true },
    processingDisposition: "organized",
    recognitionType: "Movie",
    provider: "tmdb",
    providerId: "101",
    title: "Example",
    year: "2026",
    taskId: "task-example",
    identitySummary: {
      recognitionType: "Movie",
      provider: "tmdb",
      providerId: "101",
      title: "Example",
      year: 2026,
    },
  },
  ...Array.from({ length: 151 }, (_, index) => {
    const number = String(index + 1).padStart(3, "0");
    const dispositions = ["organized", "attention", "unknown"];
    const statuses = ["ready", "unstable", "discovered"];
    return {
      fileId: `file-index-${number}`,
      storageId: "local-media",
      resourceLibraryId: "resources",
      path: `Movies/Title-${number}.mkv`,
      filename: `Title-${number}.mkv`,
      extension: "mkv",
      size: 1048576 + index,
      modifiedAt: "2026-08-22T12:00:00+00:00",
      updatedAt: "2026-08-22T12:00:00+00:00",
      firstSeenAt: "2026-08-22T11:00:00+00:00",
      lastSeenAt: "2026-08-22T12:00:00+00:00",
      stableSince: index % 2 === 0 ? "2026-08-22T11:30:00+00:00" : null,
      missingSince: null,
      scanStatus: statuses[index % statuses.length],
      change: index % 2 === 0 ? "unchanged" : "modified",
      occurrenceState: index % 3 === 0 ? "verified" : "unverified",
      currentOccurrence: {
        state: index % 3 === 0 ? "verified" : "unverified",
        current: true,
      },
      processingDisposition: dispositions[index % dispositions.length],
      recognitionType: index % 2 === 0 ? "Movie" : "TV",
      provider: "tmdb",
      providerId: String(200 + index),
      title: `Title ${number}`,
      year: String(2000 + (index % 25)),
      taskId: `task-${number}`,
      identitySummary:
        index % 2 === 0
          ? {
              recognitionType: index % 2 === 0 ? "Movie" : "TV",
              provider: "tmdb",
              providerId: String(200 + index),
              title: `Title ${number}`,
              year: 2000 + (index % 25),
            }
          : null,
    };
  }),
];

const FILE_INDEX_ALLOWED_QUERY = new Set([
  "resourceLibrary",
  "storage",
  "scanStatus",
  "query",
  "limit",
  "after",
  "before",
  "cursorFileId",
  "recognitionType",
  "provider",
  "providerId",
  "title",
  "taskId",
  "year",
  "processingDisposition",
]);

const FILE_INDEX_SCAN_STATUSES = new Set([
  "discovered",
  "unstable",
  "ready",
  "ignored",
  "missing",
  "error",
]);

const FILE_INDEX_PROCESSING_DISPOSITIONS = new Set([
  "unknown",
  "organized",
  "skipped",
  "attention",
  "conflict",
  "review",
  "partial",
  "failed",
  "unverified",
  "reprocess_requested",
]);

function fileIndexTuple(item) {
  return [Date.parse(item.updatedAt), item.fileId];
}

function compareFileIndexTuples(left, right) {
  const [leftTime, leftId] = fileIndexTuple(left);
  const [rightTime, rightId] = fileIndexTuple(right);
  if (leftTime !== rightTime) return leftTime - rightTime;
  return leftId.localeCompare(rightId);
}

function fileIndexCursor(url, timestampKey) {
  const timestamp = url.searchParams.get(timestampKey);
  if (timestamp === null) return null;
  const fileId = url.searchParams.get("cursorFileId");
  if ((timestamp === null) !== (fileId === null)) {
    return { error: "cursor" };
  }
  if (timestamp === null || fileId === null) return null;
  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed) || fileId.length === 0) {
    return { error: "cursor" };
  }
  return { updatedAt: new Date(parsed).toISOString(), fileId };
}

function fileIndexDocument(url) {
  const values = new Map();
  for (const [key, value] of url.searchParams.entries()) {
    if (!FILE_INDEX_ALLOWED_QUERY.has(key) || values.has(key)) {
      return { status: 400, payload: { error: { code: "invalid_filter" } } };
    }
    values.set(key, value);
  }
  const limit = Number(values.get("limit") ?? "100");
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    return { status: 400, payload: { error: { code: "invalid_filter" } } };
  }
  if (
    values.has("scanStatus") &&
    !FILE_INDEX_SCAN_STATUSES.has(values.get("scanStatus"))
  ) {
    return { status: 400, payload: { error: { code: "invalid_filter" } } };
  }
  if (
    values.has("processingDisposition") &&
    !FILE_INDEX_PROCESSING_DISPOSITIONS.has(values.get("processingDisposition"))
  ) {
    return { status: 400, payload: { error: { code: "invalid_filter" } } };
  }
  if (values.has("after") && values.has("before")) {
    return { status: 400, payload: { error: { code: "invalid_cursor" } } };
  }
  if (
    values.has("cursorFileId") &&
    !values.has("after") &&
    !values.has("before")
  ) {
    return { status: 400, payload: { error: { code: "invalid_cursor" } } };
  }
  const after = fileIndexCursor(url, "after");
  const before = fileIndexCursor(url, "before");
  if (after?.error || before?.error) {
    return { status: 400, payload: { error: { code: "invalid_cursor" } } };
  }
  const query = (values.get("query") ?? "").toLowerCase();
  const items = FILE_INDEX_ITEMS.filter((item) => {
    if (
      values.has("resourceLibrary") &&
      item.resourceLibraryId !== values.get("resourceLibrary")
    ) {
      return false;
    }
    if (values.has("storage") && item.storageId !== values.get("storage")) {
      return false;
    }
    if (
      values.has("scanStatus") &&
      item.scanStatus !== values.get("scanStatus")
    ) {
      return false;
    }
    if (
      values.has("processingDisposition") &&
      item.processingDisposition !== values.get("processingDisposition")
    ) {
      return false;
    }
    if (
      query !== "" &&
      !item.path.toLowerCase().includes(query) &&
      !item.filename.toLowerCase().includes(query)
    ) {
      return false;
    }
    if (
      values.has("recognitionType") &&
      item.recognitionType !== values.get("recognitionType")
    ) {
      return false;
    }
    if (values.has("provider") && item.provider !== values.get("provider")) {
      return false;
    }
    if (
      values.has("providerId") &&
      item.providerId !== values.get("providerId")
    ) {
      return false;
    }
    if (
      values.has("title") &&
      !item.title.toLowerCase().includes(values.get("title").toLowerCase())
    ) {
      return false;
    }
    if (values.has("taskId") && item.taskId !== values.get("taskId")) {
      return false;
    }
    if (values.has("year") && item.year !== values.get("year")) {
      return false;
    }
    if (after && compareFileIndexTuples(item, after) >= 0) {
      return false;
    }
    if (before && compareFileIndexTuples(item, before) <= 0) {
      return false;
    }
    return true;
  }).sort((left, right) => compareFileIndexTuples(right, left));
  const pageItems = before ? items.slice(-limit) : items.slice(0, limit);
  return {
    status: 200,
    payload: {
      surface: "file_index",
      fileIndexSurface: "/api/v1/file-index",
      filesSurface: "/api/v1/storage/files",
      items: pageItems,
      limit,
    },
  };
}

function filesDocument(path, cursor, storageId) {
  const storage =
    storageId === "remote-media"
      ? { id: "remote-media", name: "Remote media", type: "openlist" }
      : { id: "local-media", name: "Local media", type: "local" };
  const isRoot = path === "";
  const segments = path === "" ? [] : path.split("/");
  const breadcrumbs = [
    { name: "Storage root", path: "", isRoot: true },
    ...segments.map((segment, index) => ({
      name: segment,
      path: segments.slice(0, index + 1).join("/"),
      isRoot: false,
    })),
  ];
  const entries =
    storage.id === "remote-media"
      ? isRoot
        ? [
            {
              name: "remote.mkv",
              path: "remote.mkv",
              type: "file",
              entryType: "file",
              size: 1024,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: false,
                memberships: [],
                total: 0,
                truncated: false,
              },
            },
          ]
        : []
      : isRoot
        ? [
            {
              name: "movies",
              path: "movies",
              type: "directory",
              entryType: "directory",
              size: 0,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: true,
              isSymlink: false,
              traversable: true,
              selectable: true,
              indexMembership: {
                available: true,
                indexed: false,
                memberships: [],
                total: 0,
                truncated: false,
              },
            },
            {
              name: "show.mkv",
              path: "show.mkv",
              type: "file",
              entryType: "file",
              size: 1572864000,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: true,
                memberships: [
                  {
                    fileId: "file-index-example",
                    resourceLibraryId: "resources",
                  },
                ],
                total: 1,
                truncated: false,
              },
            },
            {
              name: "ambiguous.mkv",
              path: "ambiguous.mkv",
              type: "file",
              entryType: "file",
              size: 1572864000,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: true,
                memberships: [
                  {
                    fileId: "file-index-example",
                    resourceLibraryId: "resources",
                  },
                ],
                total: 1,
                truncated: false,
              },
            },
            {
              name: "unavailable.mkv",
              path: "unavailable.mkv",
              type: "file",
              entryType: "file",
              size: 1572864000,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: true,
                memberships: [
                  {
                    fileId: "file-index-example",
                    resourceLibraryId: "resources",
                  },
                ],
                total: 1,
                truncated: false,
              },
            },
            {
              name: "missing-link.mkv",
              path: "missing-link.mkv",
              type: "file",
              entryType: "file",
              size: 1572864000,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: true,
                memberships: [
                  {
                    fileId: "file-index-example",
                    resourceLibraryId: "resources",
                  },
                ],
                total: 1,
                truncated: false,
              },
            },
            {
              name: "malformed.mkv",
              path: "malformed.mkv",
              type: "file",
              entryType: "file",
              size: 1572864000,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: true,
                memberships: [
                  {
                    fileId: "file-index-example",
                    resourceLibraryId: "resources",
                  },
                ],
                total: 1,
                truncated: false,
              },
            },
            {
              name: "draft.mkv",
              path: "draft.mkv",
              type: "file",
              entryType: "file",
              size: 524288000,
              modifiedAt: "2026-08-22T12:00:00+00:00",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: false,
              indexMembership: {
                available: true,
                indexed: false,
                memberships: [],
                total: 0,
                truncated: false,
              },
            },
          ]
        : path === "movies"
          ? [
              {
                name: "movie.mkv",
                path: "movies/movie.mkv",
                type: "file",
                entryType: "file",
                size: 2097152000,
                modifiedAt: "2026-08-22T12:00:00+00:00",
                isDirectory: false,
                isSymlink: false,
                traversable: false,
                selectable: false,
                indexMembership: {
                  available: false,
                  indexed: false,
                  memberships: [],
                  total: 0,
                  truncated: false,
                },
              },
            ]
          : [];
  const hasNext =
    storage.id === "local-media" && (path === "" || Boolean(cursor));
  return {
    revisionId: "rev-e2e-1",
    revision: { revisionId: "rev-e2e-1", version: 1, digest: "digest-e2e-1" },
    configuration: {
      authority: "MANAGED",
      revisionId: "rev-e2e-1",
      version: 1,
      digest: "digest-e2e-1",
    },
    storage,
    storageId: storage.id,
    storageName: storage.name,
    storageType: storage.type,
    pathScope: "storage_relative",
    root: "",
    rootPath: "",
    canonicalPath: path,
    path,
    breadcrumbs,
    entries,
    limit: 50,
    nextCursor: hasNext ? "cursor-page-2" : null,
    hasNext,
    exhausted: !hasNext,
    continuation: {
      hasNext,
      exhausted: !hasNext,
      cursorBoundTo: "revision/storage/path/limit",
    },
    sideEffects: "none",
    retrySafe: true,
  };
}

function detailUnavailableSections(reason) {
  return Object.fromEntries(
    [
      "parse",
      "recognition",
      "metadata",
      "policies",
      "naming",
      "classification",
      "plan",
      "operation",
      "capabilities",
    ].map((name) => [
      name,
      {
        available: false,
        value: null,
        items: [],
        warnings: [],
        truncated: false,
        unavailableReason: reason,
      },
    ]),
  );
}

function detailEvidenceSections(truncated = false) {
  const section = (value, items = [], warnings = []) => ({
    available: true,
    value,
    items,
    warnings,
    truncated,
  });
  return {
    parse: section(
      {
        titleCandidate: "Example",
        year: 2026,
        season: 1,
        episode: 1,
        episodes: ["1"],
        resolutionTag: "1080p",
        sourceTag: "WEB-DL",
        videoCodecTag: "H265",
        audioTag: "AAC",
        hdrTag: "HDR",
        versionTag: "v1",
        releaseGroup: "Group",
        extension: "mkv",
        nfoMediaType: "movie",
        nfoPath: "NFO/Example.nfo",
        languageTags: ["en"],
      },
      [
        {
          field: "titleCandidate",
          value: "Example",
          source: "filename",
          confidence: "high",
        },
      ],
      ["The parser used bounded filename facts."],
    ),
    recognition: section(
      {
        status: "matched",
        recognitionTypeId: "Movie",
        ruleId: "rule-movie",
        confidence: 0.98,
        score: 98,
        matchedRules: [
          {
            ruleId: "rule-movie",
            recognitionTypeId: "Movie",
            priority: 1,
            score: 98,
          },
        ],
        alternatives: [],
      },
      [
        {
          ruleId: "rule-movie",
          field: "extension",
          operator: "equals",
          expected: "mkv",
          actual: "mkv",
        },
      ],
    ),
    metadata: section({
      status: "matched",
      recognitionTypeId: "Movie",
      query: "Example",
      provider: "tmdb",
      providerId: "101",
      mediaType: "movie",
      title: "Example",
      originalTitle: "Example Original",
      year: 2026,
      confidence: 0.97,
      matchedBy: "title_year",
      matchStatus: "matched",
      matchReasons: ["exact title and year"],
      matchWarnings: [],
      candidateCount: 1,
      bestCandidate: {
        provider: "tmdb",
        providerId: "101",
        mediaType: "movie",
        title: "Example",
        originalTitle: "Example Original",
        year: 2026,
        score: 0.97,
        exactTitle: true,
        exactYear: true,
        matchedLocalTitle: "Example",
        matchedProviderTitle: "Example",
        matchedTitleSource: "title",
        scoreComponents: [{ name: "title", score: 1, reason: "exact" }],
      },
    }),
    policies: section({
      recognitionTypeId: "Movie",
      recognitionTypePolicyId: "movie-default",
      metadataPolicyId: "meta-a",
      namingPolicyId: "naming-a",
      classificationPolicyId: "class-a",
      organizePolicyId: "organize-move",
    }),
    naming: section({
      policyId: "naming-a",
      recognitionTypeId: "Movie",
      mediaType: "movie",
      directory: "Example (2026)",
      filename: "Example (2026).mkv",
      directorySegments: ["Example (2026)"],
      sanitizationChanges: [],
      renderedVariables: [["title", "Example"]],
    }),
    classification: section({
      policyId: "class-a",
      recognitionTypeId: "Movie",
      status: "classified",
      mediaLibraryId: "media-library",
      relativePath: "Movies",
      matchedRuleId: "rule-movies",
      matchedRuleName: "Movies",
      library: "Movies",
      category: "movie",
      subcategory: "feature",
      confidence: 1,
      matchEvidence: ["media type movie"],
    }),
    plan: section({
      planId: "plan-example",
      sourceStorageId: "local-media",
      targetStorageId: "local-media",
      target: "Media/Movies/Example (2026)/Example (2026).mkv",
      relativeDestination: "Movies/Example (2026)/Example (2026).mkv",
      operation: "move",
      status: "ready",
      overwriteAuthorized: false,
      configuredPolicy: {
        policyId: "organize-move",
        configuredConflictStrategy: "manual",
      },
      nextAction: "Review the bounded plan.",
      warnings: [],
      conflicts: [],
      attachments: [],
      duplicateDetection: {
        status: "not_found",
        mode: "exact",
        reason: "no duplicate matched",
      },
    }),
    operation: section({
      status: "completed",
      operation: "move",
      destination: "Media/Movies/Example (2026)/Example (2026).mkv",
      planId: "plan-example",
      createdDirectories: ["Media/Movies"],
      completedOperations: ["move"],
      effectCertainty: "verified_complete",
      uncertainEffects: [],
      cleanupStatus: "not_required",
      rollbackStatus: "not_required",
    }),
    capabilities: section({
      required: ["CanMove"],
      declared: ["CanMove", "CanRead"],
      missing: [],
      verdict: "satisfied",
      operation: "move",
      sourceStorageId: "local-media",
      targetStorageId: "local-media",
    }),
  };
}

function detailCheckpoint(fileId) {
  return {
    status: "completed",
    raw_stage: "organizing",
    stage: "organizing",
    attempts: 1,
    plan_id: "plan-" + fileId,
    destination_storage_id: "local-media",
    destination_path: "Media/Movies/Example (2026)/Example (2026).mkv",
    configuration: {
      snapshot_id: "snapshot-e2e-1",
      snapshot_digest: "digest-e2e-1",
      resolvable: true,
      reason: null,
    },
    blocker: null,
    blockers: [],
    effects: {
      certainty: "verified_complete",
      completed_operations: ["move"],
      uncertain_effects: [],
    },
    error_category: "none",
    failureExplanation: null,
    nextAction: null,
    retry_safety: "safe",
    actions: [],
    permitted_action_ids: [],
    refusal_reason: null,
    checkpoint_version: "checkpoint-e2e-1",
    updated_at: "2026-08-22T12:04:00+00:00",
  };
}

function fileDetailDocument(fileId) {
  const indexedBase = FILE_INDEX_ITEMS.find((item) => item.fileId === fileId);
  const specialIds = new Set([
    "file-index-legacy",
    "file-index-missing-evidence",
    "file-index-truncated",
    "file-index-mismatched",
  ]);
  if (indexedBase === undefined && !specialIds.has(fileId)) {
    return null;
  }
  const template = indexedBase ?? FILE_INDEX_ITEMS[0];
  const isLegacy = fileId === "file-index-legacy";
  const isMissingEvidence = fileId === "file-index-missing-evidence";
  const isTruncated = fileId === "file-index-truncated";
  const isMismatched = fileId === "file-index-mismatched";
  const base = {
    ...template,
    fileId,
    resourceLibraryId: isMismatched
      ? "orphaned-resources"
      : template.resourceLibraryId,
    path: isMismatched ? "Movies/Mismatched.mkv" : template.path,
    filename: isMismatched ? "Mismatched.mkv" : template.filename,
    occurrenceState: isLegacy ? "legacy" : template.occurrenceState,
    currentOccurrence: isLegacy
      ? { state: "legacy", current: false }
      : template.currentOccurrence,
    processingDisposition:
      isLegacy || isMissingEvidence
        ? "unknown"
        : template.processingDisposition,
    identitySummary: isLegacy ? null : template.identitySummary,
  };
  const resultId = "result-" + fileId;
  const priorResultId = resultId + "-prior";
  const itemId = "item-" + fileId;
  const reviewId = "review-" + fileId;
  const destinationPath =
    "Library/Movies/" + base.title + " (" + base.year + ")";
  const standardResult = {
    resultId,
    status: "completed",
    createdAt: "2026-08-22T12:05:00+00:00",
    recognitionType: base.recognitionType,
    provider: "tmdb",
    providerId: base.providerId,
    title: base.title,
    metadataPolicyId: "meta-a",
    namingPolicyId: "naming-a",
    classificationPolicyId: "class-a",
    organizePolicyId: "organize-move",
    operation: "move",
    destinationPath,
    effectCertainty: "verified_complete",
    error: null,
    relevance: "current",
    current: true,
  };
  const historicalResult = {
    resultId: priorResultId,
    status: "superseded",
    createdAt: "2026-08-01T09:00:00+00:00",
    recognitionType: base.recognitionType,
    provider: "tmdb",
    providerId: base.providerId,
    title: base.title,
    metadataPolicyId: "meta-a",
    namingPolicyId: "naming-a",
    classificationPolicyId: "class-a",
    organizePolicyId: "organize-move",
    operation: "move",
    destinationPath: null,
    effectCertainty: "attempted_unverified",
    error: null,
    relevance: "historical_different_occurrence",
    current: false,
  };
  const standardOccurrence = {
    occurrenceId: "occ-" + fileId,
    state: base.occurrenceState,
    current: !isLegacy,
    firstSeenAt: "2026-08-22T11:10:00+00:00",
    lastSeenAt: "2026-08-22T12:10:00+00:00",
    supersededAt: null,
  };
  const priorOccurrence = {
    occurrenceId: "occ-" + fileId + "-prior",
    state: "verified",
    current: false,
    firstSeenAt: "2026-08-01T09:00:00+00:00",
    lastSeenAt: "2026-08-21T10:00:00+00:00",
    supersededAt: "2026-08-22T11:10:00+00:00",
  };
  const standardEvidence = {
    outcome: "completed",
    capturedAt: "2026-08-22T12:06:00+00:00",
    error: null,
    truncated: isTruncated,
    warnings: ["One bounded evidence warning."],
    sections: detailEvidenceSections(isTruncated),
  };
  const standardCheckpoint = detailCheckpoint(fileId);
  if (isLegacy) {
    return {
      ...base,
      currentOccurrence: {
        state: "legacy",
        current: false,
        occurrenceId: null,
        fingerprintAlgorithm: null,
      },
      occurrenceHistory: [priorOccurrence],
      priorResultRelevance: {
        currentResultId: null,
        current: false,
        historicalOnly: true,
      },
      reprocess: { eligible: false, reason: "legacy evidence is unavailable" },
      reprocessRequests: [],
      processing: {
        resultId: null,
        effectCertainty: "unknown",
        retrySafety: "unknown",
        nextAction: "review this legacy record",
        updatedAt: "2026-08-22T12:05:00+00:00",
      },
      latestResult: null,
      results: [historicalResult],
      items: [
        {
          taskId: base.taskId,
          itemId,
          status: "unknown",
          stage: "unknown",
          updatedAt: "2026-08-22T12:05:00+00:00",
          relevance: "unverified_legacy",
          current: false,
          checkpoint: null,
        },
      ],
      relatedReviews: [],
      evidence: [
        {
          outcome: "legacy",
          capturedAt: null,
          error: null,
          truncated: false,
          warnings: [],
          sections: detailUnavailableSections(
            "legacy evidence was not captured",
          ),
        },
      ],
      evidenceAvailability: "unavailable",
      currentActions: [],
      truncated: {
        occurrenceHistory: false,
        reviews: false,
        evidence: false,
        items: false,
        results: false,
      },
    };
  }
  if (isMissingEvidence) {
    return {
      ...base,
      currentOccurrence: {
        ...base.currentOccurrence,
        occurrenceId: "occ-" + fileId,
        fingerprintAlgorithm: "sha256-v2",
      },
      occurrenceHistory: [],
      priorResultRelevance: {
        currentResultId: null,
        current: false,
        historicalOnly: false,
      },
      reprocess: { eligible: false, reason: "evidence is unavailable" },
      reprocessRequests: [],
      processing: {
        resultId: null,
        effectCertainty: "unknown",
        retrySafety: "unknown",
        nextAction: null,
        updatedAt: null,
      },
      latestResult: null,
      results: [],
      items: [],
      relatedReviews: [],
      evidence: [],
      evidenceAvailability: "unavailable",
      currentActions: [],
      truncated: {
        occurrenceHistory: false,
        reviews: false,
        evidence: false,
        items: false,
        results: false,
      },
    };
  }
  return {
    ...base,
    currentOccurrence: {
      ...base.currentOccurrence,
      occurrenceId: "occ-" + fileId,
      fingerprintAlgorithm: "sha256-v2",
    },
    occurrenceHistory: [standardOccurrence, priorOccurrence],
    priorResultRelevance: {
      currentResultId: resultId,
      current: true,
      historicalOnly: false,
    },
    reprocess: {
      eligible: base.processingDisposition === "attention",
      reason:
        base.processingDisposition === "attention"
          ? "record is in the attention disposition"
          : "only attention records are reprocessable",
    },
    reprocessRequests:
      base.processingDisposition === "attention"
        ? [
            {
              requestId: "reprocess-" + fileId,
              status: "pending_confirmation",
              nextAction: "confirm in the current Web UI",
            },
          ]
        : [],
    processing: {
      resultId,
      effectCertainty:
        base.processingDisposition === "organized"
          ? "verified_complete"
          : "attempted_unverified",
      retrySafety: "safe",
      nextAction:
        base.processingDisposition === "organized" ? null : "review the record",
      updatedAt: "2026-08-22T12:05:00+00:00",
    },
    latestResult: standardResult,
    results: [historicalResult],
    items: [
      {
        taskId: base.taskId,
        itemId,
        status: "completed",
        stage: "organizing",
        updatedAt: "2026-08-22T12:05:00+00:00",
        relevance: "current",
        current: true,
        checkpoint: standardCheckpoint,
      },
    ],
    relatedReviews: [
      {
        kind: "organize",
        reviewId,
        status: "resolved",
      },
    ],
    evidence: [standardEvidence],
    evidenceAvailability: "available",
    currentActions: [
      {
        label: "Reprocess this record",
        confirmationRequired: true,
        admissible: base.processingDisposition === "attention",
      },
    ],
    truncated: {
      occurrenceHistory: isTruncated,
      reviews: isTruncated,
      evidence: isTruncated,
      items: isTruncated,
      results: isTruncated,
    },
  };
}

function fileBySourceDocument(storageId, path) {
  if (storageId === "local-media" && path === "show.mkv") {
    return {
      available: true,
      fileId: "file-index-example",
      resourceLibraryId: "resources",
      reason: null,
    };
  }
  if (storageId === "local-media" && path === "draft.mkv") {
    return {
      available: false,
      fileId: null,
      resourceLibraryId: null,
      reason: "missing",
    };
  }
  if (storageId === "local-media" && path === "ambiguous.mkv") {
    return {
      available: false,
      fileId: null,
      resourceLibraryId: null,
      reason: "ambiguous",
    };
  }
  if (storageId === "local-media" && path === "missing-link.mkv") {
    return {
      available: false,
      fileId: null,
      resourceLibraryId: null,
      reason: "missing",
    };
  }
  return null;
}

function bearerToken(req) {
  const header = req.headers.authorization ?? "";
  return header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";
}

function sendJson(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.length,
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  res.end(body);
}

function sendFile(res, body, contentType) {
  res.writeHead(200, {
    "Content-Type": contentType,
    "Content-Length": body.length,
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  res.end(body);
}

async function readArtifact(path) {
  const resolved = normalize(join(DIST, path));
  if (!resolved.startsWith(normalize(DIST + sep))) {
    return null;
  }
  try {
    return await readFile(resolved);
  } catch {
    return null;
  }
}

const CONTENT_TYPES = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
};

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  const token = bearerToken(req);

  if (url.pathname === "/api/v1/dashboard") {
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message: "principal lacks read permission",
        },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    if (EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    sendJson(res, 200, DASHBOARD_SNAPSHOT);
    return;
  }
  if (url.pathname === "/api/v1/system/status") {
    if (req.method !== "GET") {
      res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("GET required");
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message: "principal lacks read permission",
        },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    if (EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    sendJson(res, 200, SYSTEM_STATUS);
    return;
  }
  if (url.pathname === "/api/v1/file-index") {
    if (req.method !== "GET") {
      res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("GET required");
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message: "principal lacks read permission",
        },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    const document = fileIndexDocument(url);
    sendJson(res, document.status, document.payload);
    return;
  }
  if (url.pathname === "/api/v1/storage/files") {
    if (req.method !== "GET") {
      res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("GET required");
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message: "principal lacks read permission",
        },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    if (EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    const storageId = url.searchParams.get("storageId");
    if (!["local-media", "remote-media"].includes(storageId)) {
      sendJson(res, 404, {
        error: {
          code: "storage_browser_storage_not_found",
          message: "configured Storage was not found",
          details: {
            category: "storage_not_found",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "reload the configuration revision and choose one configured Storage",
          },
        },
      });
      return;
    }
    const path = url.searchParams.get("path") ?? "";
    if (path.includes("..") || path.startsWith("/") || path.includes("\\")) {
      sendJson(res, 400, {
        error: {
          code: "storage_browser_invalid_path",
          message: "Storage-relative path is invalid",
          details: {
            category: "invalid_path",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "use the displayed Storage-relative breadcrumb or enter a safe relative path",
          },
        },
      });
      return;
    }
    if (path === "missing") {
      sendJson(res, 404, {
        error: {
          code: "storage_browser_not_found",
          message: "Storage directory was not found",
          details: {
            category: "not_found",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "make the configured directory available, reload, and retry",
          },
        },
      });
      return;
    }
    if (path === "blocked") {
      sendJson(res, 403, {
        error: {
          code: "storage_browser_permission_denied",
          message: "Storage read permission was denied",
          details: {
            category: "permission_denied",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "grant MediaFlow read/list permission, reload, and retry",
          },
        },
      });
      return;
    }
    // No Active runtime fixture
    if (
      url.searchParams.has("fixture") &&
      url.searchParams.get("fixture") === "no-active"
    ) {
      sendJson(res, 200, {
        system: {
          application_version: "2.0.0.dev0",
          configuration_valid: false,
          configuration_authority: null,
        },
        storages: { total: 0, truncated: false, items: [] },
        resource_libraries: { total: 0, truncated: false, items: [] },
      });
      return;
    }
    // Invalid/stale cursor fixture
    const cursor = url.searchParams.get("cursor");
    if (cursor === "stale-cursor") {
      sendJson(res, 400, {
        error: {
          code: "storage_browser_cursor_invalid",
          message: "page continuation is no longer valid",
          details: {
            category: "cursor_invalid",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "reload the current revision and restart browsing from the directory root",
          },
        },
      });
      return;
    }
    sendJson(res, 200, filesDocument(path, cursor, storageId));
    return;
  }
  const detailMatch = url.pathname.match(
    /^\/api\/v1\/files\/(?!by-source$)(.+)$/,
  );
  if (detailMatch !== null) {
    if (req.method !== "GET") {
      res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("GET required");
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message: "principal lacks read permission",
        },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    const encodedFileId = detailMatch[1];
    let fileId;
    try {
      fileId = decodeURIComponent(encodedFileId);
    } catch {
      sendJson(res, 400, {
        error: { code: "rejected", message: "fileId encoding is invalid" },
      });
      return;
    }
    if (fileId === "file-index-malformed") {
      sendJson(res, 200, {
        some_json: 42,
        missing_the_required_file_detail_document_structure: true,
      });
      return;
    }
    if (fileId === "file-index-unavailable") {
      sendJson(res, 503, {
        error: {
          code: "service_unavailable",
          message: "detail backend unavailable",
        },
      });
      return;
    }
    if (fileId === "file-index-unauthorized") {
      sendJson(res, 401, {
        error: {
          code: "unauthorized",
          message: "detail authorization expired",
        },
      });
      return;
    }
    if (fileId === "file-index-forbidden") {
      sendJson(res, 403, {
        error: { code: "forbidden", message: "detail permission denied" },
      });
      return;
    }
    const document = fileDetailDocument(fileId);
    if (document === null) {
      sendJson(res, 404, {
        error: { code: "not_found", message: "FileIndex record was not found" },
      });
      return;
    }
    sendJson(res, 200, document);
    return;
  }
  if (url.pathname === "/api/v1/files/by-source") {
    if (req.method !== "GET") {
      res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("GET required");
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message: "principal lacks read permission",
        },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    if (EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    const storageId = url.searchParams.get("storageId");
    const path = url.searchParams.get("path");
    if (storageId === null || path === null) {
      sendJson(res, 400, {
        error: { code: "rejected", message: "storageId and path are required" },
      });
      return;
    }
    if (path === "unavailable.mkv") {
      sendJson(res, 503, {
        error: {
          code: "service_unavailable",
          message: "source resolver unavailable",
        },
      });
      return;
    }
    if (path === "malformed.mkv") {
      sendJson(res, 200, { available: "yes", fileId: "file-index-example" });
      return;
    }
    const document = fileBySourceDocument(storageId, path);
    if (document === null) {
      sendJson(res, 404, {
        error: { code: "not_found", message: "by-source path was not found" },
      });
      return;
    }
    sendJson(res, 200, document);
    return;
  }

  // --- Operations fake API routes ---

  if (url.pathname === "/api/v1/tasks" && req.method === "GET") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const statusFilter = url.searchParams.get("status");
    let items = FAKE_TASKS;
    if (statusFilter) {
      items = items.filter((t) => t.status === statusFilter);
    }
    sendJson(res, 200, {
      items,
      limit: 20,
      truncated: false,
      previous_cursor: null,
      next_cursor: null,
    });
    return;
  }

  const taskDetailMatch = url.pathname.match(/^\/api\/v1\/tasks\/([^/]+)$/);
  if (taskDetailMatch && req.method === "GET") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const taskId = decodeURIComponent(taskDetailMatch[1]);
    const task = FAKE_TASKS.find((t) => t.task_id === taskId);
    if (!task) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    const taskItems = TASK_ITEMS.filter((i) => i.task_id === taskId);
    const taskResults = TASK_RESULTS.filter((r) => r.task_id === taskId);
    sendJson(res, 200, {
      ...task,
      items: taskItems,
      results: taskResults,
      item_limit: 20,
      result_limit: 20,
      items_truncated: false,
      results_truncated: false,
      previous_item_cursor: null,
      previous_result_cursor: null,
      next_item_cursor: null,
      next_result_cursor: null,
    });
    return;
  }

  const taskCancelMatch = url.pathname.match(
    /^\/api\/v1\/tasks\/([^/]+)\/cancel$/,
  );
  if (taskCancelMatch && req.method === "POST") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const taskId = decodeURIComponent(taskCancelMatch[1]);
    const task = FAKE_TASKS.find((t) => t.task_id === taskId);
    if (!task) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    sendJson(res, 200, { ...task, status: "cancelled" });
    return;
  }

  const taskPauseMatch = url.pathname.match(
    /^\/api\/v1\/tasks\/([^/]+)\/pause$/,
  );
  if (taskPauseMatch && req.method === "POST") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const taskId = decodeURIComponent(taskPauseMatch[1]);
    const task = FAKE_TASKS.find((t) => t.task_id === taskId);
    if (!task) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    if (task.status !== "running") {
      sendJson(res, 409, {
        error: { code: "conflict", message: "task is not running" },
      });
      return;
    }
    sendJson(res, 200, { ...task, status: "paused", pause_requested: true });
    return;
  }

  const taskResumeMatch = url.pathname.match(
    /^\/api\/v1\/tasks\/([^/]+)\/resume$/,
  );
  if (taskResumeMatch && req.method === "POST") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const taskId = decodeURIComponent(taskResumeMatch[1]);
    const task = FAKE_TASKS.find((t) => t.task_id === taskId);
    if (!task) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    if (task.status !== "paused") {
      sendJson(res, 409, {
        error: { code: "conflict", message: "task is not paused" },
      });
      return;
    }
    sendJson(res, 200, { ...task, status: "running", pause_requested: false });
    return;
  }

  if (url.pathname === "/api/v1/jobs" && req.method === "GET") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    sendJson(res, 200, {
      items: FAKE_JOBS,
      limit: 20,
      truncated: false,
      previous_cursor: null,
      next_cursor: null,
    });
    return;
  }

  const jobDetailMatch = url.pathname.match(/^\/api\/v1\/jobs\/([^/]+)$/);
  if (jobDetailMatch && req.method === "GET") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const jobId = decodeURIComponent(jobDetailMatch[1]);
    const job = FAKE_JOBS.find((j) => j.job_id === jobId);
    if (!job) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    sendJson(res, 200, job);
    return;
  }

  const jobCancelMatch = url.pathname.match(
    /^\/api\/v1\/jobs\/([^/]+)\/cancel$/,
  );
  if (jobCancelMatch && req.method === "POST") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const jobId = decodeURIComponent(jobCancelMatch[1]);
    const job = FAKE_JOBS.find((j) => j.job_id === jobId);
    if (!job) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    sendJson(res, 200, { ...job, status: "cancelled" });
    return;
  }

  if (url.pathname === "/api/v1/workers/readiness" && req.method === "GET") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    sendJson(res, 200, {
      ready: true,
      condition: "ready",
      category: null,
      durableState: "processing worker is active",
      sideEffects: "none",
      retrySafe: true,
      nextAction: "",
      activeWorkersCount: 1,
      activeSnapshotId: "snap-1",
      activeSnapshotDigest: "digest-1",
    });
    return;
  }

  if (url.pathname === "/api/v1/workers" && req.method === "GET") {
    if (!VIEWER_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    sendJson(res, 200, {
      workers: [
        {
          worker_id: "worker-e2e-1",
          label: "e2e-worker",
          status: "live",
          last_heartbeat_at: "2026-08-22T12:10:00+00:00",
          registered_at: "2026-08-22T12:00:00+00:00",
          supported_commands: ["scan", "preview", "organize"],
        },
      ],
      count: 1,
    });
    return;
  }

  if (req.method !== "GET") {
    res.writeHead(405, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("GET required");
    return;
  }
  if (url.pathname === "/ui") {
    const body = Buffer.from(`<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>MediaFlow V1 Web UI</title></head>
  <body><main><h1>MediaFlow V1 Web UI</h1><p>Current Web continuation.</p></main></body>
</html>`);
    sendFile(res, body, CONTENT_TYPES[".html"]);
    return;
  }
  if (url.pathname === "/ui-v2" || url.pathname === "/ui-v2/") {
    const index = await readArtifact("index.html");
    if (index === null) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("V2 artifact is not built; run npm --prefix web run build");
      return;
    }
    sendFile(res, index, CONTENT_TYPES[".html"]);
    return;
  }
  if (url.pathname.startsWith("/ui-v2/")) {
    const relative = url.pathname.slice("/ui-v2/".length);
    const hasFileSuffix = Boolean(extname(relative));
    const body = await readArtifact(relative);
    if (body !== null && Object.hasOwn(CONTENT_TYPES, extname(relative))) {
      sendFile(res, body, CONTENT_TYPES[extname(relative)]);
      return;
    }
    if (hasFileSuffix) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("not found");
      return;
    }
    const index = await readArtifact("index.html");
    if (index === null) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("V2 artifact is not built; run npm --prefix web run build");
      return;
    }
    sendFile(res, index, CONTENT_TYPES[".html"]);
    return;
  }
  res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
  res.end("not found");
});

server.listen(PORT, HOST, () => {
  console.log(`fake V2 server listening on http://${HOST}:${PORT}/ui-v2/`);
});
