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
// Read-only principals hold `read` but not `cancel_job`, so their Operations
// projections must advertise no actionable control.
const READ_ONLY_TOKENS = new Set(["e2e-readonly-token"]);
const OPERATOR_TOKENS = new Set([...VIEWER_TOKENS]);
// Principals that may read every surface but hold no lifecycle permission.
const READABLE_TOKENS = new Set([...VIEWER_TOKENS, ...READ_ONLY_TOKENS]);
const KNOWN_TOKENS = new Set([
  ...VIEWER_TOKENS,
  ...LIMITED_TOKENS,
  ...EXPIRED_TOKENS,
  ...READ_ONLY_TOKENS,
]);

const KNOWN_TASK_STATUSES = new Set([
  "pending",
  "running",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
  "paused",
]);
const TERMINAL_TASK_STATUSES = new Set([
  "completed",
  "partial_success",
  "failed",
  "cancelled",
]);
const CANCELLABLE_TASK_STATUSES = new Set(["pending", "running", "paused"]);
const KNOWN_JOB_STATUSES = new Set([
  "pending",
  "running",
  "completed",
  "failed",
  "cancelled",
]);
const TERMINAL_JOB_STATUSES = new Set(["completed", "failed", "cancelled"]);
const KNOWN_JOB_COMMANDS = new Set([
  "scan",
  "preview",
  "organize",
  "file-metadata-correction",
  "recovery-continuation",
]);
const SAFE_COMMAND_FILTER = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/;

// Safe test-observable metadata only: method, normalized object identity,
// action and whether the submitted version matched. No Bearer value, body
// payload or authority material is ever recorded.
const RECORDED_MUTATIONS = [];

function bumpTimestamp(value) {
  const parsed = Date.parse(value);
  const base = Number.isNaN(parsed) ? Date.now() : parsed;
  return new Date(base + 60_000).toISOString();
}

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
      identifier: "job-005",
      status: "failed",
      occurred_at: "2026-08-22T11:58:00+00:00",
      category: "processing_error",
    },
    {
      kind: "task",
      identifier: "task-004",
      status: "failed",
      occurred_at: "2026-08-22T11:57:00+00:00",
      category: "task_failed",
    },
    {
      kind: "notification",
      identifier: "delivery-e2e-1",
      status: "dead-letter",
      occurred_at: "2026-08-22T11:56:00+00:00",
      category: "delivery_failed",
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
    status: "success",
    stage: "organizing",
    attempts: 1,
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:05:00+00:00",
    destination_storage_id: "local-media",
    destination_path: "Media/Movies/The Matrix (1999)/The Matrix (1999).mkv",
    execution_status: "completed",
    failure: null,
    checkpoint: {
      status: "completed",
      stage: "organizing",
      raw_stage: "organizing",
      blocker_kind: null,
      blocker_id: null,
      effect_certainty: "verified_complete",
      retry_safety: "safe",
      refusal_reason: null,
      checkpoint_version: "checkpoint-item-001",
      permitted_action_ids: [],
    },
  },
  {
    item_id: "item-002",
    task_id: "task-001",
    storage_id: "local-media",
    resource_library_id: "resources",
    source_path: "movies/Inception (2010).mkv",
    status: "failed",
    stage: "metadata",
    attempts: 2,
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:06:00+00:00",
    destination_storage_id: null,
    destination_path: null,
    execution_status: null,
    failure: {
      category: "provider_failure",
      message: "Provider failure: metadata lookup did not complete",
      durableState: "TaskItem and Result are durable with a failed outcome",
      sideEffects: "none",
      retrySafe: true,
      nextAction:
        "inspect Provider availability and explicitly retry metadata analysis",
    },
    checkpoint: {
      status: "failed",
      stage: "metadata",
      raw_stage: "metadata",
      blocker_kind: null,
      blocker_id: null,
      effect_certainty: "unknown",
      retry_safety: "safe",
      refusal_reason: null,
      checkpoint_version: "checkpoint-item-002",
      permitted_action_ids: [],
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
    failure: null,
    completed_operations: ["move"],
    effect_certainty: "verified_complete",
    uncertain_effects: [],
  },
];

const FAKE_TASKS = [
  {
    // This first fixture deliberately also carries the historical legacy fields
    // a real row may still hold (a raw durable error carrying a credential, a
    // private endpoint, absolute host directories and a Windows adapter root,
    // plus a configured snapshot fingerprint and a display root). They are not
    // part of the bounded Operations projection the V2 client models, so the
    // browser proof can assert they never reach the DOM or the console.
    task_id: "task-001",
    error:
      "Authorization: Bearer topsecret /home/alice/private.mkv " +
      "https://private.example/api /mnt/private-library " +
      "C:\\Users\\alice\\media",
    failureExplanation: {
      category: "storage",
      message: "the source Storage became unavailable",
      durableState: "the source Storage became unavailable",
      sideEffects: "none",
      retrySafe: true,
      nextAction: "restore the source Storage, then re-run the Scan",
    },
    configuration_snapshot_digest:
      "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    source_display: "/srv/media/private.mkv",
    source_fingerprint: "fingerprint-value",
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
    failure: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    item_limit: null,
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
    failure: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    item_limit: null,
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
    failure: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    item_limit: null,
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
    failure: {
      category: "storage",
      message: "the source Storage became unavailable",
      durableState: "the source Storage became unavailable",
      sideEffects: "none",
      retrySafe: true,
      nextAction: "restore the source Storage, then re-run the Scan",
    },
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    item_limit: null,
  },
  {
    task_id: "task-005",
    command: "retry-failed:task-004",
    status: "running",
    execute_authorized: false,
    created_at: "2026-08-22T12:20:00+00:00",
    updated_at: "2026-08-22T12:21:00+00:00",
    started_at: "2026-08-22T12:20:01+00:00",
    completed_at: null,
    total_items: 2,
    completed_items: 0,
    failed_items: 0,
    failure: null,
    pause_requested: true,
    configuration_snapshot_id: "snap-1",
    item_limit: null,
  },
  {
    task_id: "task-006",
    command: "organize",
    status: "paused",
    execute_authorized: true,
    created_at: "2026-08-22T12:25:00+00:00",
    updated_at: "2026-08-22T12:30:00+00:00",
    started_at: "2026-08-22T12:25:01+00:00",
    completed_at: null,
    total_items: 4,
    completed_items: 2,
    failed_items: 0,
    failure: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    item_limit: null,
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
    cancellation_requested: false,
    execute_authorized: false,
    failure: null,
    failure_category: null,
    definition_id: null,
    schedule_id: null,
    run_mode: null,
    configuration_snapshot_id: "snap-1",
  },
  {
    job_id: "job-002",
    command: "scan",
    status: "pending",
    created_at: "2026-08-22T12:15:00+00:00",
    updated_at: "2026-08-22T12:15:00+00:00",
    started_at: null,
    completed_at: null,
    task_id: null,
    cancellation_requested: false,
    execute_authorized: false,
    failure: null,
    failure_category: null,
    definition_id: null,
    schedule_id: null,
    run_mode: null,
    configuration_snapshot_id: "snap-1",
    operationalCondition: {
      condition: "no_worker",
      stage: "pending",
      durableState: "no processing worker is registered",
      sideEffects: "none",
      retrySafe: true,
      nextAction: "start a processing worker",
    },
  },
  {
    job_id: "job-003",
    command: "preview",
    status: "running",
    created_at: "2026-08-22T12:16:00+00:00",
    updated_at: "2026-08-22T12:18:00+00:00",
    started_at: "2026-08-22T12:16:05+00:00",
    completed_at: null,
    task_id: "task-005",
    cancellation_requested: false,
    execute_authorized: false,
    failure: null,
    failure_category: null,
    definition_id: null,
    schedule_id: null,
    run_mode: null,
    configuration_snapshot_id: "snap-1",
    worker_id: "worker-e2e-1",
    workerId: "worker-e2e-1",
    ownerStatus: "live",
    ownerLastHeartbeatAt: "2026-08-22T12:18:00+00:00",
  },
  {
    job_id: "job-004",
    command: "organize",
    status: "running",
    created_at: "2026-08-22T12:19:00+00:00",
    updated_at: "2026-08-22T12:19:30+00:00",
    started_at: "2026-08-22T12:19:05+00:00",
    completed_at: null,
    task_id: "task-006",
    cancellation_requested: false,
    execute_authorized: true,
    failure: null,
    failure_category: null,
    definition_id: null,
    schedule_id: null,
    run_mode: null,
    configuration_snapshot_id: "snap-1",
    worker_id: "worker-e2e-stale",
    workerId: "worker-e2e-stale",
    ownerStatus: "stale",
    ownerLastHeartbeatAt: "2026-08-22T11:00:00+00:00",
    operationalCondition: {
      condition: "stale_worker",
      stage: "running",
      durableState: "the owning processing worker has a stale heartbeat",
      sideEffects: "none",
      retrySafe: true,
      nextAction:
        "restart the resident worker, then inspect or explicitly requeue the stale Job",
    },
  },
  {
    job_id: "job-005",
    command: "preview",
    status: "failed",
    created_at: "2026-08-22T12:22:00+00:00",
    updated_at: "2026-08-22T12:24:00+00:00",
    started_at: "2026-08-22T12:22:05+00:00",
    completed_at: "2026-08-22T12:24:00+00:00",
    task_id: "task-004",
    cancellation_requested: false,
    execute_authorized: false,
    failure: {
      category: "processing_error",
      message: "the queued workflow failed before completing",
      durableState: "the queued workflow failed before completing",
      sideEffects: "none",
      retrySafe: false,
      nextAction: "inspect the linked Task results before re-running anything",
    },
    failure_category: "processing_error",
    failure_durable_state: "the queued workflow failed before completing",
    failure_side_effects: "none",
    failure_retry_safe: false,
    failure_next_action:
      "inspect the linked Task results before re-running anything",
    definition_id: null,
    schedule_id: null,
    run_mode: null,
    configuration_snapshot_id: "snap-1",
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
    total: 3,
    truncated: false,
    items: [
      {
        id: "local-media",
        name: "Local media",
        type: "local",
        read_only: true,
        enabled: true,
      },
      {
        id: "remote-media",
        name: "Remote media",
        type: "openlist",
        read_only: false,
        enabled: true,
      },
      {
        id: "source-storage",
        name: "source-storage",
        type: "local",
        read_only: true,
        enabled: true,
      },
    ],
  },
  resource_libraries: {
    total: 2,
    truncated: false,
    items: [
      {
        id: "resources",
        name: "Resources",
        storage_id: "local-media",
        root_path: "",
        enabled: true,
      },
      {
        id: "source",
        name: "source",
        storage_id: "source-storage",
        root_path: "media/incoming",
        enabled: true,
      },
    ],
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

const RESOURCE_LIBRARY_STATES = new Map();

function resourceLibraryState(session) {
  const key = session ?? "shared";
  let value = RESOURCE_LIBRARY_STATES.get(key);
  if (value === undefined) {
    value = {
      saved: false,
      failOnce: false,
      failed: false,
      candidate: null,
      extra: [],
      removedIds: [],
      emptied: false,
      textStale: false,
      commandLog: [],
    };
    RESOURCE_LIBRARY_STATES.set(key, value);
  }
  return value;
}

function resourceLibrarySystemStatus(session) {
  const state = resourceLibraryState(session);
  if (!state.saved && state.extra.length === 0 && !state.emptied) {
    return SYSTEM_STATUS;
  }
  const document = JSON.parse(JSON.stringify(SYSTEM_STATUS));
  document.system.configuration_snapshot_id = "rev-e2e-2";
  document.system.configuration_snapshot_digest = "digest-e2e-2";
  if (state.emptied) {
    document.resource_libraries.items = [];
    document.resource_libraries.total = 0;
    return document;
  }
  if (state.extra.length > 0) {
    // The libraries fixture replaces the base list so strip journeys run
    // against one deterministic, fully named set.
    document.resource_libraries.items = state.extra.filter(
      (item) => !state.removedIds.includes(item.id),
    );
    document.resource_libraries.total =
      document.resource_libraries.items.length;
    return document;
  }
  const candidate = state.candidate ?? {};
  if (state.saved) {
    document.resource_libraries.items.push({
      id: candidate.resourceLibraryId ?? "new-e2e-library",
      name: candidate.name ?? "E2E 新资源库",
      storage_id: candidate.storageId ?? "local-media",
      root_path: candidate.storagePath ?? "",
      enabled: candidate.enabled === true,
    });
  }
  for (const item of state.extra) {
    if (!state.removedIds.includes(item.id)) {
      document.resource_libraries.items.push(item);
    }
  }
  document.resource_libraries.items = document.resource_libraries.items.filter(
    (item) => item.id !== "source" || !state.removedIds.includes("source"),
  );
  document.resource_libraries.total = document.resource_libraries.items.length;
  return document;
}

const E2E_FAKE_REFERENCES = new Map([["source", 1]]);

function removalPreviewDocument(resourceLibraryId, state) {
  const total = E2E_FAKE_REFERENCES.get(resourceLibraryId) ?? 0;
  const extra = state.extra.find((item) => item.id === resourceLibraryId);
  const displayName = extra
    ? extra.name
    : resourceLibraryId === "source"
      ? "source"
      : resourceLibraryId;
  const displayRoot = extra
    ? extra.root_path
    : resourceLibraryId === "source"
      ? "media/incoming"
      : "";
  return {
    resourceLibrary: {
      id: resourceLibraryId,
      name: displayName,
      storageId:
        resourceLibraryId === "source" ? "source-storage" : "local-media",
      storagePath: displayRoot,
      enabled: true,
    },
    storage:
      resourceLibraryId === "source"
        ? {
            id: "source-storage",
            name: "Source storage",
            type: "local",
            enabled: true,
          }
        : {
            id: "local-media",
            name: "Local media",
            type: "local",
            enabled: true,
          },
    references:
      total === 0
        ? { total: 0, items: [], truncated: false }
        : {
            total,
            items: [
              {
                section: "recognitionRules",
                id: "movie-library",
                field: "resourceLibraryId",
              },
            ],
            truncated: false,
          },
    active: {
      status: "active",
      revisionId: "rev-e2e-2",
      version: 2,
      digest: "digest-e2e-2",
    },
    sideEffects: "none",
  };
}

const FAKE_DELETE_IMPACT_ENTRIES = new Map([
  [
    "Movies",
    [
      { path: "Movies", isDirectory: true, size: 0 },
      { path: "Movies/Avatar (2009)", isDirectory: true, size: 0 },
      {
        path: "Movies/Avatar (2009)/Avatar.2009.1080p.mkv",
        isDirectory: false,
        size: 1024,
      },
    ],
  ],
]);

function deleteImpactDocument(resourceLibraryId, paths) {
  const entries = [];
  for (const path of paths) {
    const nested = FAKE_DELETE_IMPACT_ENTRIES.get(path);
    if (nested) {
      entries.push(...nested);
    } else {
      entries.push({ path, isDirectory: false, size: 32 });
    }
  }
  const fileCount = entries.filter((entry) => !entry.isDirectory).length;
  const directoryCount = entries.length - fileCount;
  return {
    resourceLibraryId,
    topLevelPaths: [...paths],
    entries,
    fileCount,
    directoryCount,
    totalBytes: entries.reduce((sum, entry) => sum + entry.size, 0),
    truncated: false,
    scopeDigest: "fake-scope-digest-" + paths.join(","),
  };
}

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

// Deterministic reference-shaped Files fixtures (Slice 37). Directories use
// backend `selectable` semantics (directory = selectable Organize scope).
// Every entry stays secret-free and time-fixed so browser evidence is stable.
const REFERENCE_MODIFIED_LATEST = "2024-01-15T10:30:00+00:00";
const REFERENCE_MODIFIED_OLDER = "2024-01-14T08:20:00+00:00";

function fileEntry(name, path, size, modifiedAt, options = {}) {
  return {
    name,
    path,
    type: "file",
    entryType: "file",
    size,
    modifiedAt,
    isDirectory: false,
    isSymlink: false,
    traversable: false,
    selectable: options.selectable === true,
    ...(options.selectable === true ? { selectKind: "file" } : {}),
    ...(options.recognitionResult !== undefined
      ? { recognitionResult: options.recognitionResult }
      : {}),
    ...(options.businessStatus !== undefined
      ? { businessStatus: options.businessStatus }
      : {}),
  };
}

function directoryEntry(name, path, modifiedAt) {
  return {
    name,
    path,
    type: "directory",
    entryType: "directory",
    size: 0,
    modifiedAt,
    isDirectory: true,
    isSymlink: false,
    traversable: true,
    selectable: true,
    selectKind: "directory",
  };
}

function referenceDirectoryEntries(path) {
  if (path === "") {
    return [
      directoryEntry("Movies", "Movies", REFERENCE_MODIFIED_LATEST),
      directoryEntry("TV", "TV", REFERENCE_MODIFIED_LATEST),
      directoryEntry("Anime", "Anime", REFERENCE_MODIFIED_LATEST),
      directoryEntry("Others", "Others", REFERENCE_MODIFIED_LATEST),
      fileEntry("readme.txt", "readme.txt", 1024, REFERENCE_MODIFIED_LATEST),
      fileEntry(
        "sample.mkv",
        "sample.mkv",
        1_572_864_000,
        REFERENCE_MODIFIED_LATEST,
        {
          selectable: true,
          recognitionResult: "Sample",
          businessStatus: "pending",
        },
      ),
      fileEntry(
        "Avatar.2009.1080p.mkv",
        "Avatar.2009.1080p.mkv",
        13_314_394_726,
        REFERENCE_MODIFIED_LATEST,
        {
          selectable: true,
          recognitionResult: "Avatar (2009)",
          businessStatus: "pending",
        },
      ),
    ];
  }
  if (path === "Movies") {
    return [
      directoryEntry(
        "Avatar (2009)",
        "Movies/Avatar (2009)",
        REFERENCE_MODIFIED_LATEST,
      ),
      directoryEntry(
        "Inception (2010)",
        "Movies/Inception (2010)",
        REFERENCE_MODIFIED_LATEST,
      ),
      directoryEntry(
        "Interstellar (2014)",
        "Movies/Interstellar (2014)",
        REFERENCE_MODIFIED_LATEST,
      ),
      directoryEntry(
        "Dune (2021)",
        "Movies/Dune (2021)",
        REFERENCE_MODIFIED_LATEST,
      ),
      fileEntry(
        "Behind.The.Scenes.mkv",
        "Movies/Behind.The.Scenes.mkv",
        2_255_329_280,
        REFERENCE_MODIFIED_OLDER,
        { selectable: true, businessStatus: "pending" },
      ),
    ];
  }
  if (path === "Movies/Avatar (2009)") {
    return [
      fileEntry(
        "Avatar.2009.1080p.mkv",
        "Movies/Avatar (2009)/Avatar.2009.1080p.mkv",
        13_314_394_726,
        REFERENCE_MODIFIED_LATEST,
        {
          selectable: true,
          recognitionResult: "Avatar (2009)",
          businessStatus: "pending",
        },
      ),
      fileEntry(
        "Avatar.2009.nfo",
        "Movies/Avatar (2009)/Avatar.2009.nfo",
        4096,
        REFERENCE_MODIFIED_LATEST,
        { businessStatus: "skipped" },
      ),
      fileEntry(
        "sample.jpg",
        "Movies/Avatar (2009)/sample.jpg",
        1_258_291,
        REFERENCE_MODIFIED_LATEST,
        { businessStatus: "skipped" },
      ),
      directoryEntry(
        "Subtitles",
        "Movies/Avatar (2009)/Subtitles",
        REFERENCE_MODIFIED_LATEST,
      ),
      fileEntry(
        "Behind.The.Scenes.mkv",
        "Movies/Avatar (2009)/Behind.The.Scenes.mkv",
        2_255_329_280,
        REFERENCE_MODIFIED_OLDER,
        { selectable: true, businessStatus: "pending" },
      ),
      fileEntry(
        "Poster.jpg",
        "Movies/Avatar (2009)/Poster.jpg",
        876_544,
        REFERENCE_MODIFIED_OLDER,
        { businessStatus: "skipped" },
      ),
      fileEntry(
        "fanart.jpg",
        "Movies/Avatar (2009)/fanart.jpg",
        1_572_864,
        REFERENCE_MODIFIED_OLDER,
        { businessStatus: "skipped" },
      ),
    ];
  }
  return [];
}

function filesDocument(
  path,
  cursor,
  storageId,
  resourceLibraryId = null,
  savedCandidate = null,
  extraLibrary = null,
) {
  const isReferenceLibrary = resourceLibraryId === "source";
  const isSavedResourceLibrary = resourceLibraryId === "new-e2e-library";
  const snapshotId = isSavedResourceLibrary ? "rev-e2e-2" : "rev-e2e-1";
  const storage =
    storageId === "remote-media"
      ? { id: "remote-media", name: "Remote media", type: "openlist" }
      : isReferenceLibrary
        ? { id: "source-storage", name: "source-storage", type: "local" }
        : { id: "local-media", name: "Local media", type: "local" };
  const isRoot = path === "";
  const segments = path === "" ? [] : path.split("/");
  const breadcrumbs = [
    { name: "ResourceLibrary root", path: "", isRoot: true },
    ...segments.map((segment, index) => ({
      name: segment,
      path: segments.slice(0, index + 1).join("/"),
      isRoot: false,
    })),
  ];
  // Remote Storage keeps a tiny bounded fixture for unavailable-provider
  // browsing evidence; reference-shaped directories live on local-media.
  const entries =
    storage.id === "remote-media"
      ? isRoot
        ? [
            fileEntry(
              "remote.mkv",
              "remote.mkv",
              1024,
              REFERENCE_MODIFIED_LATEST,
            ),
          ]
        : []
      : referenceDirectoryEntries(path);
  const hasNext =
    storage.id !== "remote-media" && (path === "" || Boolean(cursor));
  return {
    revisionId: snapshotId,
    revision: {
      revisionId: snapshotId,
      version: isSavedResourceLibrary ? 2 : 1,
      digest: isSavedResourceLibrary ? "digest-e2e-2" : "digest-e2e-1",
    },
    configuration: {
      authority: "MANAGED",
      revisionId: snapshotId,
      version: isSavedResourceLibrary ? 2 : 1,
      digest: isSavedResourceLibrary ? "digest-e2e-2" : "digest-e2e-1",
    },
    resourceLibrary: resourceLibraryId
      ? {
          // The Files page renders the projection's bounded ResourceLibrary
          // identity. The fake keeps the Active runtime identity coherent with
          // the SYSTEM_STATUS fixture other frozen-page specs assert on.
          id: resourceLibraryId,
          name: isReferenceLibrary
            ? "source"
            : extraLibrary
              ? extraLibrary.name
              : (savedCandidate?.name ?? "Resources"),
          enabled: extraLibrary ? true : (savedCandidate?.enabled ?? true),
          rootPath: isReferenceLibrary
            ? "media/incoming"
            : extraLibrary
              ? extraLibrary.root_path
              : (savedCandidate?.storagePath ?? ""),
          storage: { ...storage, readOnly: false },
          ...(isReferenceLibrary
            ? { fileCount: 1248, totalSize: 324 * 1024 * 1024 * 1024 }
            : {}),
        }
      : undefined,
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

// --- Manual Scan / Preview fake state ---
//
// The V2 Operations workspace reads the bounded /api/v1/operations/* alias for
// the manual action matrix, the bounded Scan admission/detail/cancel routes and
// the zero-mutation Preview routes. The fake keeps deterministic, internally
// consistent state (`scan-e2e-001`, `preview-e2e-001`) whose documents mirror
// the committed `manual-operations.json` fixture field names and value types
// exactly. Only bounded, secret-free request metadata is recorded for the
// browser proof; no Bearer value, fingerprint or raw body is ever stored.

const MANUAL_SCAN_TASK_ID = "scan-e2e-001";
const MANUAL_PREVIEW_ID = "preview-e2e-001";
const MANUAL_LIBRARY_ID = "resources";
const MANUAL_STORAGE_ID = "local-media";
const MANUAL_RECORDED_AT = "2026-09-04T12:00:00+00:00";
const MANUAL_CONFIGURATION_SNAPSHOT_ID = "active-1";
const MANUAL_PREVIEW_MAX_ITEMS = 100;
const MANUAL_ITEM_LIMIT_MAX = 100;
const MANUAL_CURSOR_MAX_LENGTH = 256;
const MANUAL_REQUEST_FIELD_MAX_LENGTH = 256;
const MANUAL_REQUEST_BODY_MAX_BYTES = 4096;
const MANUAL_SCAN_MODES = ["full", "incremental"];
const MANUAL_SCAN_ACTION_PATH = "/api/v1/operations/scans";
const MANUAL_PREVIEW_ACTION_PATH = "/api/v1/operations/previews";
const MANUAL_FILE_SCOPE = {
  fileId: "file-index-example",
  resourceLibraryId: MANUAL_LIBRARY_ID,
};
const MANUAL_UNKNOWN_SOURCE_REASON =
  "the current FileIndex source was not found";
const MANUAL_UNKNOWN_LIBRARY_REASON =
  "the ResourceLibrary is not enabled in the Active configuration";
const MANUAL_TERMINAL_SCAN_STATUSES = new Set([
  "completed",
  "partial_success",
  "failed",
  "cancelled",
]);
// The bounded, secret-free request metadata a browser test may read back.
//
// Evidence is recorded per browser session: every Playwright test runs in its
// own browser context, so the session cookie set by
// `POST /__test__/reset-organize` gives each test exactly one bucket. Two
// parallel workers therefore can never erase or observe another test's
// evidence, which is what made the earlier shared-array design flaky under
// `fullyParallel`. Requests without a session cookie still land in the shared
// bucket so existing serial Scan journeys keep their deliberate shared state.
const RECORDED_MANUAL_REQUESTS = [];
const RECORDED_MANUAL_REQUESTS_BY_SESSION = new Map();
const MANUAL_SESSION_COOKIE = "mf-e2e-session";
const MANUAL_REQUEST_BODY_FIELDS = [
  "allowOverwrite",
  "allowSourceCleanup",
  "confirmation",
  "expectedIntentVersion",
  "expectedItemVersion",
  "expectedRevisionId",
  "expectedVersion",
  "fileId",
  "itemIds",
  "itemCursor",
  "itemLimit",
  "mode",
  "object",
  "previewId",
  "reason",
  "recognitionTypeId",
  "resourceLibraryId",
  "scopeKind",
  "action",
  "deliveryId",
  "expectedStatus",
  "expectedUpdatedAt",
  "webhookId",
];

const MANUAL_RESOURCE_LIBRARY_CHOICES = [
  {
    enabled: true,
    reason: null,
    resourceLibraryId: MANUAL_LIBRARY_ID,
    scanMode: "full",
    storageId: MANUAL_STORAGE_ID,
  },
];

function boundedManualBody(fields) {
  const body = {};
  for (const key of MANUAL_REQUEST_BODY_FIELDS) {
    const value = fields[key];
    if (value === null || value === undefined || value === "") {
      continue;
    }
    body[key] = value;
  }
  return body;
}

function recordManualRequest({
  body,
  method,
  objectId,
  objectType,
  path,
  session,
}) {
  const entry = { method, path, objectType };
  if (objectId !== null && objectId !== undefined) {
    entry.objectId = objectId;
  }
  const bounded = boundedManualBody(body ?? {});
  if (Object.keys(bounded).length > 0) {
    entry.body = bounded;
  }
  if (session !== null && session !== undefined) {
    const bucket = RECORDED_MANUAL_REQUESTS_BY_SESSION.get(session);
    if (bucket !== undefined) {
      bucket.push(entry);
      return;
    }
  }
  RECORDED_MANUAL_REQUESTS.push(entry);
}

function readBoundedQuery(url, allowedFields) {
  const values = {};
  for (const key of url.searchParams.keys()) {
    if (!allowedFields.includes(key)) {
      return null;
    }
    if (url.searchParams.getAll(key).length !== 1) {
      return null;
    }
    values[key] = url.searchParams.get(key);
  }
  return values;
}

function boundedManualRequestFields(document, allowedFields) {
  const fields = {};
  for (const [key, value] of Object.entries(document)) {
    if (!allowedFields.includes(key)) {
      return null;
    }
    if (
      typeof value !== "string" ||
      value.length === 0 ||
      value.length > MANUAL_REQUEST_FIELD_MAX_LENGTH
    ) {
      return null;
    }
    fields[key] = value;
  }
  return fields;
}

function parseBoundedItemLimit(raw) {
  if (raw === undefined) {
    return { itemLimit: null, ok: true };
  }
  const parsed = Number(raw);
  if (
    !Number.isInteger(parsed) ||
    parsed < 1 ||
    parsed > MANUAL_ITEM_LIMIT_MAX ||
    raw.trim() !== String(parsed)
  ) {
    return { ok: false };
  }
  return { itemLimit: parsed, ok: true };
}

function readBoundedJsonBody(req, res) {
  let raw = "";
  let overflow = false;
  req.on("data", (chunk) => {
    if (raw.length + chunk.length > MANUAL_REQUEST_BODY_MAX_BYTES) {
      overflow = true;
      return;
    }
    raw += String(chunk);
  });
  return new Promise((resolve) => {
    req.on("end", () => {
      let document = null;
      if (!overflow && raw.length > 0) {
        try {
          document = JSON.parse(raw);
        } catch {
          document = null;
        }
      }
      if (
        document === null ||
        typeof document !== "object" ||
        Array.isArray(document)
      ) {
        sendJson(res, 400, { error: { code: "invalid_request" } });
        resolve({ ok: false });
        return;
      }
      resolve({ document, ok: true });
    });
  });
}

function manualActionDocument({ available, modes, nextAction, path, reason }) {
  return {
    available,
    method: "POST",
    modes,
    nextAction,
    path,
    reason,
  };
}

function manualPermissionReason(permission) {
  return `the connected API principal does not hold the permission required to ${permission}`;
}

function manualActionMatrixDocument(request, permitted) {
  const discovery = request.resourceLibraryId === null;
  const fileScope = request.scopeKind === "file";
  const knownFileSource =
    request.fileId === MANUAL_FILE_SCOPE.fileId &&
    request.resourceLibraryId === MANUAL_FILE_SCOPE.resourceLibraryId;
  const knownLibrary = request.resourceLibraryId === MANUAL_LIBRARY_ID;

  let stateReason = null;
  let source = null;
  if (fileScope) {
    if (knownFileSource) {
      source = {
        extension: "mkv",
        fileId: MANUAL_FILE_SCOPE.fileId,
        filename: "One.2001.mkv",
        occurrenceState: "verified",
        path: "Movies/One.2001.mkv",
        resourceLibraryId: MANUAL_FILE_SCOPE.resourceLibraryId,
        scanStatus: "ready",
        sizeBytes: 12,
        storageId: MANUAL_STORAGE_ID,
      };
    } else {
      stateReason = MANUAL_UNKNOWN_SOURCE_REASON;
    }
  } else if (!discovery && !knownLibrary) {
    stateReason = MANUAL_UNKNOWN_LIBRARY_REASON;
  }

  const selectReason =
    "select an exact ResourceLibrary scope before submitting a Scan";
  const selectPreviewReason =
    "select an exact ResourceLibrary scope before running a Preview";
  const scanReason = discovery
    ? selectReason
    : permitted
      ? stateReason
      : manualPermissionReason("submit a bounded Scan");
  const previewReason = discovery
    ? selectPreviewReason
    : permitted
      ? stateReason
      : manualPermissionReason("run a zero-mutation Preview");
  const scanAvailable = permitted && stateReason === null && !discovery;
  const previewAvailable = permitted && stateReason === null && !discovery;

  return {
    actions: {
      organize: manualActionDocument({
        available: permitted && stateReason === null && !discovery,
        modes: [],
        nextAction:
          permitted && stateReason === null && !discovery
            ? "create a durable manual intent, then request an exact Preview"
            : (previewReason ?? "the Organize action is not available"),
        path: "/api/v1/operations/organize/intents",
        reason: permitted ? stateReason : previewReason,
      }),
      preview: manualActionDocument({
        available: previewAvailable,
        modes: [],
        nextAction:
          previewAvailable || discovery
            ? "run a zero-mutation Preview"
            : (previewReason ?? "the Preview action is not available"),
        path: MANUAL_PREVIEW_ACTION_PATH,
        reason: previewReason,
      }),
      scan: manualActionDocument({
        available: scanAvailable,
        modes: MANUAL_SCAN_MODES,
        nextAction:
          scanAvailable || discovery
            ? "submit a bounded Scan"
            : (scanReason ?? "the Scan action is not available"),
        path: MANUAL_SCAN_ACTION_PATH,
        reason: scanReason,
      }),
    },
    fileId: fileScope ? request.fileId : null,
    limits: { previewMaxItems: MANUAL_PREVIEW_MAX_ITEMS },
    resourceLibraries: MANUAL_RESOURCE_LIBRARY_CHOICES,
    resourceLibraryId: discovery ? null : request.resourceLibraryId,
    runtime: {
      condition: "configuration_active",
      nextAction: null,
      ready: true,
    },
    scopeId: discovery
      ? null
      : fileScope
        ? request.fileId
        : request.resourceLibraryId,
    scopeKind: discovery ? "resourceLibrary" : request.scopeKind,
    selectionRequired: discovery,
    source: discovery ? null : source,
  };
}

// --- V2 manual Organize bounded fixtures ----------------------------------
//
// One deterministic, secret-free intent -> exact Preview -> admitted execution
// journey. The fake owns no authority material: it never issues, echoes or
// records a token, digest, fingerprint or raw plan, and one repeated Execute
// resolves to the same durable execution identity.

const ORGANIZE_INTENT_ID = "organize-intent-e2e-001";
const ORGANIZE_ITEM_ID = "organize-item-e2e-001";
const ORGANIZE_PREVIEW_ID = "organize-preview-e2e-001";
const ORGANIZE_DESTRUCTIVE_PREVIEW_ID = "organize-preview-destructive-e2e-001";
const ORGANIZE_HOSTILE_PREVIEW_ID = "organize-preview-hostile-e2e-001";
const ORGANIZE_MISBOUND_PREVIEW_ID = "organize-preview-misbound-e2e-001";
const ORGANIZE_SUFFIX_PREVIEW_ID = "organize-preview-suffix-e2e-001";
const ORGANIZE_EXECUTION_ID = "organize-execution-e2e-001";
const ORGANIZE_FAILED_EXECUTION_ID = "organize-execution-failed-e2e-001";
const ORGANIZE_TASK_ID = "organize-task-e2e-001";
// One mutable organize state per browser session: every Playwright test owns
// exactly one context, so two parallel workers can never observe or advance
// another test's intent/item versions.
const ORGANIZE_STATES = new Map();

function organizeState(session) {
  const key = session ?? "shared";
  let value = ORGANIZE_STATES.get(key);
  if (value === undefined) {
    value = { executed: false, intentVersion: 1, itemVersion: 1 };
    ORGANIZE_STATES.set(key, value);
  }
  return value;
}

function organizeChoice(recognitionTypeId = "A") {
  return {
    classificationPolicyId: "A",
    metadata: null,
    namingPolicyId: "A",
    organizePolicyId: "A",
    recognitionTypeId,
  };
}

function organizeIntentDocument(state) {
  return {
    actions: {
      choice: {
        available: true,
        durableOutcome:
          "a durable optimistic choice revision is stored and every earlier Preview of this intent becomes historical evidence",
        method: "POST",
        nextAction:
          "edit one item choice with its current intent and item versions",
        path: `/api/v1/operations/organize/intents/${ORGANIZE_INTENT_ID}/items/{itemId}/choice`,
        reason: null,
        sideEffects: "none",
      },
      execute: {
        available: false,
        durableOutcome: null,
        method: null,
        nextAction: "create a fresh exact Preview after the last choice change",
        path: null,
        reason:
          "exact execution is only offered from a current, complete Preview",
        sideEffects: "none",
      },
      preview: {
        available: true,
        durableOutcome: "a durable zero-mutation Preview revision is stored",
        method: "POST",
        nextAction: "create a fresh exact Preview of the reviewed choices",
        path: `/api/v1/operations/organize/intents/${ORGANIZE_INTENT_ID}/previews`,
        reason: null,
        sideEffects: "none",
      },
    },
    actor: "e2e-operator",
    configurationSnapshotId: MANUAL_CONFIGURATION_SNAPSHOT_ID,
    createdAt: MANUAL_RECORDED_AT,
    execution: "not_available_in_this_task",
    failure: null,
    intentId: ORGANIZE_INTENT_ID,
    items: [
      {
        choice: organizeChoice(),
        createdAt: MANUAL_RECORDED_AT,
        failure: null,
        itemId: ORGANIZE_ITEM_ID,
        nextAction: "continue to a later manual Preview",
        position: 0,
        source: {
          extension: "mkv",
          fileId: MANUAL_FILE_SCOPE.fileId,
          filename: "One.2001.mkv",
          occurrenceState: "verified",
          path: "Movies/One.2001.mkv",
          resourceLibraryId: MANUAL_FILE_SCOPE.resourceLibraryId,
          scanStatus: "ready",
          size: 12,
          storageId: MANUAL_STORAGE_ID,
        },
        status: "ready",
        updatedAt: MANUAL_RECORDED_AT,
        version: state.itemVersion,
      },
    ],
    journey: "organize",
    nextAction: "continue to a later manual Preview",
    optionLimit: 100,
    options: {
      classificationPolicies: [
        { enabled: true, id: "A", name: "Movie classification" },
      ],
      configurationSnapshotId: MANUAL_CONFIGURATION_SNAPSHOT_ID,
      metadataPolicies: [
        {
          enabled: true,
          id: "A",
          mediaType: "movie",
          name: "Movie metadata",
          providerId: "tmdb",
        },
      ],
      namingPolicies: [
        { enabled: true, id: "A", mediaType: "movie", name: "Movie naming" },
      ],
      organizePolicies: [
        {
          conflictStrategy: "manual",
          enabled: true,
          id: "A",
          name: "Move",
          operation: "move",
        },
      ],
      recognitionTypes: [
        {
          classificationPolicyId: "A",
          description: "",
          enabled: true,
          id: "A",
          metadataPolicyId: "A",
          name: "Movie",
          namingPolicyId: "A",
          organizePolicyId: "A",
        },
      ],
    },
    sideEffects: "none",
    status: "open",
    updatedAt: MANUAL_RECORDED_AT,
    version: state.intentVersion,
    zeroMutation: true,
  };
}

function organizePreviewDocument(state) {
  const base = manualPreviewDocument({
    fileId: MANUAL_FILE_SCOPE.fileId,
    resourceLibraryId: MANUAL_FILE_SCOPE.resourceLibraryId,
    scopeId: MANUAL_FILE_SCOPE.fileId,
    scopeKind: "file",
  });
  return {
    ...base,
    actions: {
      execute: {
        available: true,
        durableOutcome:
          "one durable admitted execution and its Processing Worker outcome are stored; only OrganizerExecutor may then mutate Storage",
        method: "POST",
        nextAction: "confirm one Execute action for the selected exact items",
        path: `/api/v1/operations/organize/previews/${ORGANIZE_PREVIEW_ID}/execute`,
        reason: null,
        requiresConfirmation: true,
        sideEffects: "reported_per_item",
      },
      intent: {
        available: true,
        durableOutcome: null,
        method: "GET",
        nextAction: "reopen the durable intent to change a choice",
        path: `/api/v1/operations/organize/intents/${ORGANIZE_INTENT_ID}`,
        reason: null,
        sideEffects: "none",
      },
    },
    blockedItemCount: 0,
    executionCandidateItemIds: [ORGANIZE_ITEM_ID],
    intentId: ORGANIZE_INTENT_ID,
    intentVersion: state.intentVersion,
    selection: {
      selectedItemIds: [ORGANIZE_ITEM_ID],
      unselectedItemIds: [],
    },
    items: base.items.map((item) => ({
      ...item,
      itemId: ORGANIZE_ITEM_ID,
      plan: {
        ...item.plan,
        destructiveImplications: {
          overwriteRequired: false,
          sourceCleanupRequired: false,
          statement:
            "this exact plan replaces and deletes nothing; source media is preserved by the reviewed operation",
        },
      },
    })),
    journey: "organize",
    previewId: ORGANIZE_PREVIEW_ID,
    worker: {
      condition: "ready",
      durableState:
        "resident processing worker is live and can claim the admitted manual execution queue",
      nextAction: "none",
      ready: true,
    },
  };
}

function organizeDestructivePreviewDocument(state) {
  const value = organizePreviewDocument(state);
  value.previewId = ORGANIZE_DESTRUCTIVE_PREVIEW_ID;
  value.actions.execute.path = `/api/v1/operations/organize/previews/${ORGANIZE_DESTRUCTIVE_PREVIEW_ID}/execute`;
  value.items = value.items.map((item) => ({
    ...item,
    plan: {
      ...item.plan,
      operation: "COPY",
      destructiveImplications: {
        overwriteRequired: true,
        sourceCleanupRequired: true,
        statement:
          "this exact plan would replace an existing destination file and delete the emptied source directories; both require separate explicit authority",
      },
    },
  }));
  return value;
}

function organizeExecutionDocument(status, state) {
  const finished = status !== "admitted";
  return {
    actions: {
      detail: {
        available: true,
        durableOutcome: null,
        method: "GET",
        nextAction: finished
          ? "inspect the verified per-item Results; no replay is required"
          : "the reviewed work is durably admitted and waits for the resident Processing Worker to claim it",
        path: `/api/v1/operations/organize/executions/${ORGANIZE_EXECUTION_ID}`,
        reason: null,
        sideEffects: "none",
      },
      recovery: {
        available: false,
        durableOutcome: null,
        method: null,
        nextAction:
          "open Review & Recovery to inspect the failed item; MediaFlow never replays an uncertain mutation automatically",
        path: null,
        reason: "recovery is only offered for an execution with a failed item",
        sideEffects: "none",
      },
      task: {
        available: true,
        durableOutcome: null,
        method: "GET",
        nextAction: "inspect the durable Task and its per-item Results",
        path: `/api/v1/operations/tasks/${ORGANIZE_TASK_ID}`,
        reason: null,
        sideEffects: "none",
      },
    },
    actor: "e2e-operator",
    allowOverwrite: false,
    allowSourceCleanup: false,
    completedAt: finished ? MANUAL_RECORDED_AT : null,
    completedItemCount: finished ? 1 : 0,
    createdAt: MANUAL_RECORDED_AT,
    durableState: status,
    executionId: ORGANIZE_EXECUTION_ID,
    failedItemCount: 0,
    failure: null,
    intentId: ORGANIZE_INTENT_ID,
    intentVersion: state.intentVersion,
    itemCount: 1,
    items: [
      {
        completedOperations: finished ? ["CREATE_DIRECTORY", "MOVE"] : [],
        effectCertainty: finished ? "verified_complete" : "unknown",
        effects: finished
          ? [
              {
                action: "MOVE",
                certainty: "verified_complete",
                destinationLocation: "One (2001)/One (2001).mkv",
                operation: null,
                sourceLocation: "One.2001.mkv",
                verified: true,
              },
            ]
          : [],
        failure: null,
        itemId: ORGANIZE_ITEM_ID,
        nextAction: finished
          ? "inspect the verified Result; no recovery replay is required"
          : "wait for the Processing Worker to claim this exact execution",
        position: 0,
        resultId: finished ? "result-e2e-001" : null,
        stage: finished ? "completed" : "admitted",
        status: finished ? "success" : "admitted",
        taskId: ORGANIZE_TASK_ID,
        taskItemId: "organize-task-item-e2e-001",
        uncertainEffects: [],
      },
    ],
    journey: "organize",
    knownEffects: {
      failedWithoutEffectCount: 0,
      statement: finished
        ? "every recorded effect is verified and no item requires automatic replay"
        : "no Storage effect has been recorded yet",
      uncertainItemCount: 0,
      verifiedItemCount: finished ? 1 : 0,
    },
    nextAction: finished
      ? "inspect the verified per-item Results; no replay is required"
      : "the reviewed work is durably admitted and waits for the resident Processing Worker to claim it",
    previewId: ORGANIZE_PREVIEW_ID,
    selectedItemCount: 1,
    selectedItemIds: [ORGANIZE_ITEM_ID],
    status,
    taskId: ORGANIZE_TASK_ID,
    unselectedItemCount: 0,
    unselectedItemIds: [],
    updatedAt: MANUAL_RECORDED_AT,
  };
}

// The exact failed-execution document the real backend publishes for a
// terminal failure: aggregate and per-item bounded evidence, and the recovery
// handoff offered without any transport (available, no method, no route, no
// reason) — never an API mutation of its own.
function organizeFailedExecutionDocument() {
  const failure = {
    category: "destination_collision",
    durableState: "TaskItem and Result are durable with a failed outcome",
    message: "destination collision: the configured destination already exists",
    nextAction:
      "inspect the destination and resolve the collision before explicitly retrying this item",
    retrySafe: false,
    sideEffects: "none",
  };
  const nextAction =
    "inspect each failed item, repair the cause and request a fresh Preview; " +
    "uncertain effects are never replayed automatically";
  return {
    actions: {
      detail: {
        available: true,
        durableOutcome: null,
        method: "GET",
        nextAction,
        path: `/api/v1/operations/organize/executions/${ORGANIZE_FAILED_EXECUTION_ID}`,
        reason: null,
        sideEffects: "none",
      },
      recovery: {
        available: true,
        durableOutcome: null,
        method: null,
        nextAction:
          "open Review & Recovery to inspect the failed item; MediaFlow never " +
          "replays an uncertain mutation automatically",
        path: null,
        reason: null,
        sideEffects: "none",
      },
      task: {
        available: true,
        durableOutcome: null,
        method: "GET",
        nextAction: "inspect the durable Task and its per-item Results",
        path: `/api/v1/operations/tasks/${ORGANIZE_TASK_ID}`,
        reason: null,
        sideEffects: "none",
      },
    },
    actor: "e2e-operator",
    allowOverwrite: false,
    allowSourceCleanup: false,
    completedAt: MANUAL_RECORDED_AT,
    completedItemCount: 0,
    createdAt: MANUAL_RECORDED_AT,
    durableState: "terminal_failure",
    executionId: ORGANIZE_FAILED_EXECUTION_ID,
    failedItemCount: 1,
    failure,
    intentId: ORGANIZE_INTENT_ID,
    intentVersion: 1,
    itemCount: 1,
    items: [
      {
        completedOperations: [],
        effectCertainty: "none",
        effects: [],
        failure,
        itemId: ORGANIZE_ITEM_ID,
        nextAction:
          "inspect the pre-mutation failure, repair it, then request a fresh Preview",
        position: 0,
        resultId: "result-e2e-failed-001",
        stage: "failed",
        status: "failed",
        taskId: ORGANIZE_TASK_ID,
        taskItemId: "organize-task-item-e2e-001",
        uncertainEffects: [],
      },
    ],
    journey: "organize",
    knownEffects: {
      failedWithoutEffectCount: 1,
      statement:
        "one or more items require investigation; MediaFlow never replays an " +
        "uncertain mutation automatically",
      uncertainItemCount: 0,
      verifiedItemCount: 0,
    },
    nextAction,
    previewId: ORGANIZE_PREVIEW_ID,
    selectedItemCount: 1,
    selectedItemIds: [ORGANIZE_ITEM_ID],
    status: "failed",
    taskId: ORGANIZE_TASK_ID,
    unselectedItemCount: 0,
    unselectedItemIds: [],
    updatedAt: MANUAL_RECORDED_AT,
  };
}

function manualScanItems(count) {
  return Array.from({ length: count }, (_, index) => {
    const number = String(index + 1).padStart(3, "0");
    return {
      change: "unchanged",
      createdAt: MANUAL_RECORDED_AT,
      failure: null,
      fileId: `file-index-${number}`,
      itemId: `scan-item-${number}`,
      knownEffects: "file_index_discovery_refreshed",
      nextAction: "inspect the refreshed FileIndex item",
      resourceLibraryId: MANUAL_LIBRARY_ID,
      retrySafe: true,
      sideEffects: "none",
      sourcePath: `Movies/Title-${number}.mkv`,
      stage: "manual_scan_discovery",
      status: "ready",
      storageId: MANUAL_STORAGE_ID,
      taskId: MANUAL_SCAN_TASK_ID,
      updatedAt: MANUAL_RECORDED_AT,
    };
  });
}

// Enough durable discovery items that any bounded itemLimit (1..100) leaves a
// real second page for the browser paging proof.
const MANUAL_SCAN_LIBRARY_ITEMS = manualScanItems(101);

function manualScanLibraryRecord() {
  return {
    cancellationRequested: false,
    configurationSnapshotId: MANUAL_CONFIGURATION_SNAPSHOT_ID,
    createdAt: MANUAL_RECORDED_AT,
    errors: [],
    failure: null,
    failureStage: null,
    fileId: null,
    items: MANUAL_SCAN_LIBRARY_ITEMS,
    knownEffects: "file_index_discovery_refreshed",
    mode: "full",
    progress: {
      directoriesVisited: 1,
      errors: 0,
      filesVisited: MANUAL_SCAN_LIBRARY_ITEMS.length,
      ignored: 0,
      mediaCandidates: MANUAL_SCAN_LIBRARY_ITEMS.length,
      unstable: 0,
    },
    reconciliationComplete: true,
    resourceLibraryId: MANUAL_LIBRARY_ID,
    retrySafe: true,
    scopeId: MANUAL_LIBRARY_ID,
    scopeKind: "resourceLibrary",
    sourcePath: null,
    status: "completed",
    storageId: MANUAL_STORAGE_ID,
    taskId: MANUAL_SCAN_TASK_ID,
    updatedAt: MANUAL_RECORDED_AT,
  };
}

function manualScanRunningRecord({
  scopeKind,
  fileId,
  resourceLibraryId,
  mode,
}) {
  if (scopeKind === "resourceLibrary") {
    return {
      ...manualScanLibraryRecord(),
      knownEffects: "none",
      mode,
      reconciliationComplete: false,
      resourceLibraryId,
      scopeId: resourceLibraryId,
      status: "running",
    };
  }
  return {
    cancellationRequested: false,
    configurationSnapshotId: MANUAL_CONFIGURATION_SNAPSHOT_ID,
    createdAt: MANUAL_RECORDED_AT,
    errors: [],
    failure: null,
    failureStage: null,
    fileId,
    items: [
      {
        change: "unchanged",
        createdAt: MANUAL_RECORDED_AT,
        failure: null,
        fileId,
        itemId: "scan-item-001",
        knownEffects: "file_index_discovery_refreshed",
        nextAction: "inspect the refreshed FileIndex item",
        resourceLibraryId,
        retrySafe: true,
        sideEffects: "none",
        sourcePath: "Movies/Example.mkv",
        stage: "manual_scan_discovery",
        status: "ready",
        storageId: MANUAL_STORAGE_ID,
        taskId: MANUAL_SCAN_TASK_ID,
        updatedAt: MANUAL_RECORDED_AT,
      },
    ],
    knownEffects: "none",
    mode,
    progress: {
      directoriesVisited: 0,
      errors: 0,
      filesVisited: 1,
      ignored: 0,
      mediaCandidates: 1,
      unstable: 0,
    },
    reconciliationComplete: false,
    resourceLibraryId,
    retrySafe: true,
    scopeId: fileId,
    scopeKind: "file",
    sourcePath: "Movies/Example.mkv",
    status: "running",
    storageId: MANUAL_STORAGE_ID,
    taskId: MANUAL_SCAN_TASK_ID,
    updatedAt: MANUAL_RECORDED_AT,
  };
}

// The deterministic durable Scan the deep-link proof reads before any admission
// replaces it with the exact admitted scope and mode.
const MANUAL_SCANS = new Map([
  [MANUAL_SCAN_TASK_ID, manualScanLibraryRecord()],
]);
const MANUAL_PREVIEWS = new Map();

function encodeManualItemCursor(taskId, itemLimit, offset) {
  return Buffer.from(
    JSON.stringify({ itemLimit, offset, taskId, version: 1 }),
    "utf8",
  ).toString("base64url");
}

// A cursor is opaque to the browser and bound to one exact task, page size and
// page boundary. An unknown, foreign, stale-page-size, non-boundary or
// out-of-range cursor is rejected with 400 instead of silently returning a
// different page window.
function decodeManualItemCursor(raw, taskId, itemLimit, totalItems) {
  if (
    typeof raw !== "string" ||
    raw.length === 0 ||
    raw.length > MANUAL_CURSOR_MAX_LENGTH
  ) {
    return null;
  }
  try {
    const document = JSON.parse(Buffer.from(raw, "base64url").toString("utf8"));
    if (
      document === null ||
      typeof document !== "object" ||
      document.version !== 1 ||
      document.taskId !== taskId ||
      document.itemLimit !== itemLimit ||
      !Number.isInteger(document.offset) ||
      document.offset < 0 ||
      document.offset >= totalItems ||
      document.offset % itemLimit !== 0
    ) {
      return null;
    }
    return document.offset;
  } catch {
    return null;
  }
}

function manualScanPage(record, itemLimit, itemCursor) {
  if (itemLimit === null) {
    return {
      itemLimit: null,
      items: record.items,
      itemsTruncated: false,
      nextItemCursor: null,
      previousItemCursor: null,
    };
  }
  let offset = 0;
  if (itemCursor !== null) {
    offset = decodeManualItemCursor(
      itemCursor,
      record.taskId,
      itemLimit,
      record.items.length,
    );
    if (offset === null) {
      return null;
    }
  }
  const next =
    offset + itemLimit < record.items.length ? offset + itemLimit : null;
  const previous = offset > 0 ? Math.max(0, offset - itemLimit) : null;
  return {
    itemLimit,
    items: record.items.slice(offset, offset + itemLimit),
    itemsTruncated: next !== null,
    nextItemCursor:
      next === null
        ? null
        : encodeManualItemCursor(record.taskId, itemLimit, next),
    previousItemCursor:
      previous === null
        ? null
        : encodeManualItemCursor(record.taskId, itemLimit, previous),
  };
}

function manualScanCancelAction(record, permitted = true) {
  const terminal = MANUAL_TERMINAL_SCAN_STATUSES.has(record.status);
  const requested = record.cancellationRequested === true;
  let unavailableReason = null;
  if (!permitted) {
    unavailableReason =
      "the connected API principal does not hold the cancel_job permission required for this control";
  } else if (terminal) {
    unavailableReason =
      "a task in this state no longer accepts a cancellation request";
  } else if (requested) {
    unavailableReason =
      "a durable cancellation request is already stored; the Scan reaches cancelled at its own cooperative boundary";
  }
  return {
    action: "cancel",
    available: permitted && !terminal && !requested,
    confirmationRequired: false,
    cooperative: true,
    durableOutcome:
      "a durable cancellation request is stored; the Scan stops at the next cooperative discovery boundary, an already running Storage read is not interrupted and every recorded item outcome is kept",
    label: "Request cancel",
    method: "POST",
    nextAction: terminal
      ? "refresh the Scan; a terminal or already cancelled Scan keeps its recorded item outcomes"
      : "request cancellation, then refresh the Scan to read the durable outcome",
    path: `/api/v1/operations/scans/${record.taskId}/cancel`,
    retrySafe: false,
    sideEffects: "none",
    unavailableReason,
  };
}

function manualScanNextAction(record) {
  if (record.status === "cancelled") {
    return "the Scan is cancelled and every recorded item outcome is kept";
  }
  if (record.status === "completed") {
    return "inspect refreshed FileIndex state and choose a current item for Preview";
  }
  return "inspect the persisted Scan Task while discovery is running";
}

function manualScanDocument(record, page, permitted = true) {
  return {
    actions: { cancel: manualScanCancelAction(record, permitted) },
    cancellationRequested: record.cancellationRequested,
    configurationSnapshotId: record.configurationSnapshotId,
    createdAt: record.createdAt,
    errors: record.errors,
    failure: record.failure,
    failureStage: record.failureStage,
    fileId: record.fileId,
    itemLimit: page.itemLimit,
    items: page.items,
    itemsTruncated: page.itemsTruncated,
    knownEffects: record.knownEffects,
    mode: record.mode,
    nextAction: manualScanNextAction(record),
    nextItemCursor: page.nextItemCursor,
    previousItemCursor: page.previousItemCursor,
    progress: record.progress,
    reconciliationComplete: record.reconciliationComplete,
    resourceLibraryId: record.resourceLibraryId,
    retrySafe: record.retrySafe,
    scopeId: record.scopeId,
    scopeKind: record.scopeKind,
    sideEffects: "none",
    sourcePath: record.sourcePath,
    status: record.status,
    storageId: record.storageId,
    taskId: record.taskId,
    updatedAt: record.updatedAt,
  };
}

function manualScanAdmissionDocument(record, permitted = true) {
  return manualScanDocument(
    record,
    {
      itemLimit: null,
      items: [],
      itemsTruncated: false,
      nextItemCursor: null,
      previousItemCursor: null,
    },
    permitted,
  );
}

function manualPreviewIdentity() {
  return {
    countries: ["JP"],
    episode: null,
    episodeTitle: null,
    episodes: [],
    genres: ["Animation"],
    languages: [],
    matchedBy: "candidate_matcher",
    mediaType: "movie",
    originalTitle: null,
    provider: "tmdb",
    providerId: "129",
    recognitionTypeId: "A",
    season: null,
    title: "One",
    year: 2001,
  };
}

// The persisted findings of one zero-mutation plan: the complete parse,
// recognition, metadata, naming and classification analysis, bounded to
// operator-facing values. No executor input, fingerprint, digest, occurrence
// identity or host path is part of this document.
function manualPreviewPlan() {
  return {
    analysis: {
      classification: {
        available: true,
        evidence: ["media_type=movie", "genre=Animation", "country=JP"],
        matchedRuleId: "anime-movie",
        matchedRuleName: "Japanese Animation",
        mediaLibraryId: "movies",
        policyId: "A",
        reason: null,
        recognitionTypeId: "A",
        relativePath: "Anime",
        status: "classified",
        warnings: [],
      },
      metadata: {
        available: true,
        identity: manualPreviewIdentity(),
        match: {
          candidateCount: 1,
          candidates: [
            {
              exactTitle: true,
              exactYear: true,
              mediaType: "movie",
              provider: "tmdb",
              providerId: "129",
              score: 100.0,
              title: "One",
              year: 2001,
            },
          ],
          reasons: ["Candidate reached automatic threshold"],
          score: 100.0,
          status: "matched",
          warnings: [],
        },
        query: "One",
        status: "matched",
      },
      naming: {
        available: true,
        directory: "One (2001)",
        directorySegments: ["One (2001)"],
        filename: "One (2001).mkv",
        policyId: "A",
        reason: null,
        recognitionTypeId: "A",
        sanitizationChanges: [],
        warnings: [],
      },
      parse: {
        audio: null,
        episode: null,
        episodes: [],
        evidence: [
          {
            confidence: "high",
            field: "title_candidate",
            source: "filename",
            value: "One",
          },
          {
            confidence: "high",
            field: "year",
            source: "filename",
            value: "2001",
          },
        ],
        hdr: null,
        releaseGroup: null,
        resolution: null,
        season: null,
        source: null,
        titleCandidate: "One",
        version: null,
        videoCodec: null,
        warnings: [],
        year: 2001,
      },
      recognition: {
        confidence: "1.0",
        reasons: [
          { code: "MANUAL_PREVIEW", message: "Pinned by manual Preview" },
        ],
        recognitionTypeId: "A",
        ruleId: "manual-preview",
        score: 100,
        status: "matched",
        warnings: [],
      },
    },
    attachments: [],
    bounded: true,
    capabilities: {
      declared: ["can_copy", "can_delete"],
      missing: [],
      required: ["can_copy", "can_delete"],
      verdict: "ok",
    },
    conflicts: [],
    destination: {
      filename: "One (2001).mkv",
      relativePath: "Anime/One (2001)/One (2001).mkv",
      storageId: "target",
    },
    deterministic: true,
    executionState: "ready_for_explicit_authorization",
    mediaIdentity: manualPreviewIdentity(),
    operation: "MOVE",
    operationPolicy: "move",
    planStatus: "ready",
    policies: {
      classificationPolicyId: "A",
      metadataPolicyId: "A",
      namingPolicyId: "A",
      organizePolicyId: "A",
      recognitionTypePolicyId: "type-A",
    },
    recognitionType: "A",
    warnings: [],
    zeroMutation: true,
  };
}

function manualPreviewDocument({
  fileId,
  resourceLibraryId,
  scopeId,
  scopeKind,
}) {
  const itemId = "preview-item-e2e-001";
  return {
    actor: "e2e-operator",
    configurationSnapshotId: MANUAL_CONFIGURATION_SNAPSHOT_ID,
    createdAt: MANUAL_RECORDED_AT,
    current: true,
    executionState: "ready_for_explicit_authorization",
    failure: null,
    intentId: "preview-intent-e2e-001",
    intentVersion: 1,
    items: [
      {
        choice: {
          classificationPolicyId: "A",
          namingPolicyId: "A",
          organizePolicyId: "A",
          recognitionTypeId: "A",
        },
        configurationSnapshotId: MANUAL_CONFIGURATION_SNAPSHOT_ID,
        current: true,
        executionState: "ready_for_explicit_authorization",
        failure: null,
        itemId,
        nextAction:
          "inspect this exact zero-mutation plan; authorize selected items for execution",
        plan: manualPreviewPlan(),
        position: 0,
        previewItemId: itemId,
        sideEffects: "none",
        source: {
          extension: "mkv",
          fileId: fileId ?? MANUAL_FILE_SCOPE.fileId,
          filename: "One.2001.mkv",
          occurrenceState: "verified",
          path: "Movies/One.2001.mkv",
          resourceLibraryId,
          scanStatus: "ready",
          size: 12,
          storageId: MANUAL_STORAGE_ID,
        },
        stage: "planning",
        status: "previewed",
        truncated: false,
        zeroMutation: true,
      },
    ],
    nextAction:
      "inspect each exact plan; authorize selected items for execution",
    previewId: MANUAL_PREVIEW_ID,
    scope: { itemCount: 1, scopeId, scopeKind },
    scopeId,
    scopeKind,
    selection: { selectedItemIds: [itemId], unselectedItemIds: [] },
    sideEffects: "none",
    status: "previewed",
    truncated: false,
    updatedAt: MANUAL_RECORDED_AT,
    zeroMutation: true,
  };
}

function manualPreviewListDocument({ limit, scopeId, scopeKind }) {
  const items = [...MANUAL_PREVIEWS.values()].filter(
    (preview) => preview.scopeKind === scopeKind && preview.scopeId === scopeId,
  );
  return {
    items: items.slice(0, limit),
    limit,
    scopeId,
    scopeKind,
    total: items.length,
  };
}

function bearerToken(req) {
  const header = req.headers.authorization ?? "";
  return header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";
}

/** Read the per-test session id the browser context carries as a cookie. */
function manualSession(req) {
  const header = req.headers.cookie;
  if (typeof header !== "string" || header.length === 0) {
    return null;
  }
  for (const part of header.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === MANUAL_SESSION_COOKIE) {
      const value = decodeURIComponent(rest.join("="));
      return /^[A-Za-z0-9_-]{8,128}$/.test(value) ? value : null;
    }
  }
  return null;
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

// ---------------------------------------------------------------------------
// Automation journey fake state
//
// Mirrors the bounded, digest-free operator documents the real Python API
// publishes under /api/v1/operations/automation/* (proved by
// tests/test_v2_automation_operations.py). Mutations reuse the existing
// backend routes and are optimistic-version bound; the browser never sends or
// receives a revision digest, fingerprint or plan.
// ---------------------------------------------------------------------------

const AUTOMATION_DEFINITION_ID = "automation-def-e2e-001";
const AUTOMATION_ACTIVE_REVISION = "automation-active-rev-e2e-001";
const AUTOMATION_DRAFT_REVISION = "automation-draft-rev-e2e-001";
const AUTOMATION_PREVIEW_ID = "automation-preview-e2e-001";
const AUTOMATION_HOSTILE_PREVIEW_ID = "automation-preview-hostile-e2e-001";
const AUTOMATION_MISBOUND_PREVIEW_ID = "automation-preview-misbound-e2e-001";
const AUTOMATION_OCCURRENCE_ID = "automation-occurrence-e2e-001";
const AUTOMATION_JOB_ID = "automation-job-e2e-001";
const AUTOMATION_TASK_ID = "automation-task-e2e-001";
const AUTOMATION_GRANT_ID = "automation-grant-e2e-001";

const AUTOMATION_STATES = new Map();

function automationState(session) {
  const key = session ?? "shared";
  let value = AUTOMATION_STATES.get(key);
  if (value === undefined) {
    value = {
      draftCreated: false,
      draftVersion: 2,
      draftStatus: "draft",
      previewCreated: false,
      previewStale: false,
      granted: false,
      activated: false,
      createdDefinition: null,
      copiedDefinition: null,
    };
    AUTOMATION_STATES.set(key, value);
  }
  return value;
}

function automationAction(overrides = {}) {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: "/api/v1/automation/task-definitions",
    requiresConfirmation: false,
    sideEffects: "none",
    durableOutcome: null,
    nextAction: null,
    ...overrides,
  };
}

function automationPermissions(token) {
  const operator = VIEWER_TOKENS.has(token);
  return {
    operator,
    manage: operator,
    activate: operator,
    grant: operator,
    dryRun: operator,
  };
}

// ---------------------------------------------------------------------------
// Deterministic Notification fake state (V2 Webhook / delivery journey).

const NOTIFICATION_WEBHOOK_ID = "ops-webhook";
const NOTIFICATION_ACTIVE_REVISION = "notification-active-rev-e2e-001";
const NOTIFICATION_DRAFT_REVISION = "notification-draft-rev-e2e-001";
const NOTIFICATION_DELIVERY_ID = "delivery-e2e-001";
const NOTIFICATION_DELIVERY_ID_2 = "delivery-e2e-002";

const NOTIFICATION_STATES = new Map();

function notificationState(session) {
  const key = session ?? "shared";
  let value = NOTIFICATION_STATES.get(key);
  if (value === undefined) {
    value = {
      draftCreated: false,
      draftVersion: 4,
      draftStatus: "validated",
      tested: false,
      activated: false,
      createdWebhook: null,
      copiedWebhook: null,
      requeued: false,
      hostile: false,
    };
    NOTIFICATION_STATES.set(key, value);
  }
  return value;
}

function notificationAction(overrides = {}) {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: `/api/v1/operations/notifications/webhooks/${NOTIFICATION_WEBHOOK_ID}/test`,
    requiresConfirmation: false,
    sideEffects: "none",
    durableOutcome: null,
    nextAction: null,
    ...overrides,
  };
}

function notificationPermissions(token) {
  const operator = VIEWER_TOKENS.has(token);
  return {
    operator,
    manage: operator,
    activate: operator,
  };
}

function webhookDocument(state, token, overrides = {}) {
  const id = overrides.id ?? NOTIFICATION_WEBHOOK_ID;
  const document = {
    id,
    url: "https://example.invalid/hooks/mediaflow",
    secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
    events: ["job.completed", "job.failed"],
    enabled: true,
    timeoutSeconds: 10,
    maxAttempts: 5,
    baseRetrySeconds: 5,
    maxRetrySeconds: 300,
    secretReadiness: [
      { field: "secretEnv", env: "MEDIAFLOW_WEBHOOK_SECRET", state: "SET" },
    ],
    structuralValid: true,
    validationError: null,
    definitionState: "active",
    activeConfiguration: {
      revisionId: NOTIFICATION_ACTIVE_REVISION,
      version: state.activated ? 5 : 3,
      revisionSequence: state.activated ? 4 : 2,
      status: "active",
    },
    draftState: state.draftCreated
      ? {
          present: true,
          reason: null,
          revisionId: NOTIFICATION_DRAFT_REVISION,
          revisionVersion: state.draftVersion,
          revisionStatus: state.draftStatus,
          baseActiveRevisionId: NOTIFICATION_ACTIVE_REVISION,
          updatedAt: MANUAL_RECORDED_AT,
          validatedAt:
            state.draftStatus === "validated" ? MANUAL_RECORDED_AT : null,
          validationErrors: [],
        }
      : {
          present: false,
          reason:
            "no open successor Draft contains this Webhook definition; create one to edit it",
          revisionId: null,
          revisionVersion: null,
          revisionStatus: null,
          baseActiveRevisionId: null,
          updatedAt: null,
          validatedAt: null,
          validationErrors: [],
        },
    actions: webhookActions(state, token, id),
  };
  if (overrides.definitionState !== undefined) {
    document.definitionState = overrides.definitionState;
  }
  if (overrides.enabled !== undefined) {
    document.enabled = overrides.enabled;
  }
  return document;
}

function webhookActions(state, token, webhookId = NOTIFICATION_WEBHOOK_ID) {
  const { manage, activate } = notificationPermissions(token);
  const operationsRoute = `/api/v1/operations/notifications/webhooks/${webhookId}`;
  const editPath = state.draftCreated
    ? `/api/v1/configuration/revisions/${NOTIFICATION_DRAFT_REVISION}/objects/webhooks/${webhookId}`
    : null;
  const noDraft =
    "an open successor Draft is required to edit this Webhook definition";
  return {
    detail: notificationAction({
      available: true,
      method: "GET",
      path: operationsRoute,
      durableOutcome: null,
      nextAction: "inspect the exact bounded Webhook definition state",
    }),
    test: notificationAction({
      available: manage,
      reason: manage
        ? null
        : "the connected API principal cannot manage Webhook Definitions (required permission: manage_configuration)",
      path: `${operationsRoute}/test`,
      sideEffects: "one_signed_test_request",
      durableOutcome:
        "no durable change; only the bounded test outcome category is returned",
      nextAction:
        "test the exact displayed revision after reviewing its endpoint and secret readiness",
    }),
    edit: notificationAction({
      available: manage && state.draftCreated,
      reason: manage
        ? state.draftCreated
          ? null
          : noDraft
        : "the connected API principal cannot manage Webhook Definitions (required permission: manage_configuration)",
      method: "PUT",
      path: editPath,
      durableOutcome:
        "the bounded definition form is stored in the open successor Draft at a new optimistic revision version",
      nextAction:
        "save the bounded form, then validate and explicitly activate",
    }),
    copy: notificationAction({
      available: manage && state.draftCreated,
      reason: manage
        ? state.draftCreated
          ? null
          : noDraft
        : "the connected API principal cannot manage Webhook Definitions (required permission: manage_configuration)",
      path: editPath === null ? null : `${editPath}/copy`,
      durableOutcome:
        "a copied, disabled Webhook definition is stored inside the open successor Draft",
      nextAction:
        "open the copied definition, edit it, then validate and activate",
    }),
    enable: notificationAction({
      available: manage && state.draftCreated,
      reason: manage
        ? state.draftCreated
          ? null
          : noDraft
        : "the connected API principal cannot manage Webhook Definitions (required permission: manage_configuration)",
      path: editPath === null ? null : `${editPath}/enable`,
      durableOutcome:
        "the definition is enabled inside the open successor Draft only",
      nextAction: "review the Draft, validate it, then explicitly activate",
    }),
    disable: notificationAction({
      available: manage && state.draftCreated,
      reason: manage
        ? state.draftCreated
          ? null
          : noDraft
        : "the connected API principal cannot manage Webhook Definitions (required permission: manage_configuration)",
      path: editPath === null ? null : `${editPath}/disable`,
      durableOutcome:
        "the definition is disabled inside the open successor Draft only",
      nextAction: "review the Draft, validate it, then explicitly activate",
    }),
    draftCreate: notificationAction({
      available: manage,
      reason: manage
        ? null
        : "the connected API principal cannot manage Webhook Definitions (required permission: manage_configuration)",
      path: `/api/v1/configuration/revisions/${NOTIFICATION_ACTIVE_REVISION}/successor`,
      durableOutcome:
        "a successor Draft seeded from the immutable Active configuration is stored",
      nextAction:
        "create or open the successor Draft, then add or edit Webhook definitions inside it",
    }),
    activate: notificationAction({
      available: activate && state.draftCreated,
      reason: activate
        ? state.draftCreated
          ? null
          : noDraft
        : "the connected API principal cannot activate configuration (required permission: activate_configuration)",
      path: `${operationsRoute}/activate-draft`,
      requiresConfirmation: true,
      durableOutcome:
        "the exact reviewed Webhook-only Draft change becomes the immutable Active configuration; no delivery is created",
      nextAction:
        "activate the reviewed Draft after validating it; the resulting Active identity is reported without a digest",
    }),
  };
}

function notificationDraftActions(state, token) {
  const definitionActions = webhookActions(state, token);
  return {
    createDraft: definitionActions.draftCreate,
    save: definitionActions.edit,
    validate: notificationAction({
      available: notificationPermissions(token).manage && state.draftCreated,
      reason: notificationPermissions(token).manage
        ? null
        : "the connected API principal cannot validate configuration (required permission: manage_configuration)",
      path: `/api/v1/configuration/revisions/${NOTIFICATION_DRAFT_REVISION}/validate`,
      durableOutcome:
        "the open Draft is validated without any runtime or Storage effect",
      nextAction: "validate the Draft, then review the validation evidence",
    }),
    activate: definitionActions.activate,
    test: definitionActions.test,
  };
}

function notificationListDocument(state, token) {
  return {
    activeConfiguration: {
      revisionId: NOTIFICATION_ACTIVE_REVISION,
      version: state.activated ? 5 : 3,
      revisionSequence: state.activated ? 4 : 2,
      status: "active",
    },
    items: [
      webhookDocument(state, token),
      ...(state.createdWebhook
        ? [
            webhookDocument(state, token, {
              id: state.createdWebhook,
              enabled: false,
              definitionState: "draft-only",
            }),
          ]
        : []),
      ...(state.copiedWebhook
        ? [
            webhookDocument(state, token, {
              id: state.copiedWebhook,
              enabled: false,
              definitionState: "draft-only",
            }),
          ]
        : []),
    ],
    total: 1 + (state.createdWebhook ? 1 : 0) + (state.copiedWebhook ? 1 : 0),
    truncated: false,
    draftState: state.draftCreated
      ? {
          present: true,
          reason: null,
          revisionId: NOTIFICATION_DRAFT_REVISION,
          revisionVersion: state.draftVersion,
          revisionStatus: state.draftStatus,
          baseActiveRevisionId: NOTIFICATION_ACTIVE_REVISION,
          updatedAt: MANUAL_RECORDED_AT,
          validatedAt:
            state.draftStatus === "validated" ? MANUAL_RECORDED_AT : null,
          validationErrors: [],
        }
      : {
          present: false,
          reason:
            "no open successor Draft exists; create one to add or edit Webhook definitions",
          revisionId: null,
          revisionVersion: null,
          revisionStatus: null,
          baseActiveRevisionId: null,
          updatedAt: null,
          validatedAt: null,
          validationErrors: [],
        },
    supportedEvents: [
      "job.completed",
      "job.failed",
      "job.cancelled",
      "schedule.emitted",
    ],
    actions: {
      create: notificationAction({
        available: notificationPermissions(token).manage && state.draftCreated,
        reason:
          notificationPermissions(token).manage && state.draftCreated
            ? null
            : "an open successor Draft is required to add a Webhook definition",
        method: "POST",
        path: state.draftCreated
          ? `/api/v1/configuration/revisions/${NOTIFICATION_DRAFT_REVISION}/objects/webhooks`
          : null,
        durableOutcome:
          "the bounded Webhook definition is stored inside the open successor Draft",
        nextAction:
          "start or open a successor Draft, then create the definition inside it",
      }),
      createDraft: notificationAction({
        available: notificationPermissions(token).manage,
        reason: notificationPermissions(token).manage
          ? null
          : "the connected API principal cannot create a successor Draft (required permission: manage_configuration)",
        path: `/api/v1/configuration/revisions/${NOTIFICATION_ACTIVE_REVISION}/successor`,
        durableOutcome:
          "a successor Draft seeded from the immutable Active configuration is stored",
        nextAction:
          "create or open the successor Draft, then add or edit Webhook definitions inside it",
      }),
    },
  };
}

function notificationDetailDocument(state, token, webhookId) {
  const id = webhookId ?? NOTIFICATION_WEBHOOK_ID;
  return {
    webhook: webhookDocument(
      state,
      token,
      id === NOTIFICATION_WEBHOOK_ID
        ? {}
        : { id, enabled: false, definitionState: "draft-only" },
    ),
    activeConfiguration: {
      revisionId: NOTIFICATION_ACTIVE_REVISION,
      version: state.activated ? 5 : 3,
      revisionSequence: state.activated ? 4 : 2,
      status: "active",
    },
  };
}

function notificationDraftDocument(state, token) {
  return {
    webhookId: NOTIFICATION_WEBHOOK_ID,
    activeConfiguration: {
      revisionId: NOTIFICATION_ACTIVE_REVISION,
      version: state.activated ? 5 : 3,
      revisionSequence: state.activated ? 4 : 2,
      status: "active",
    },
    webhook: webhookDocument(state, token),
    draft: state.draftCreated
      ? {
          revisionId: NOTIFICATION_DRAFT_REVISION,
          revisionVersion: state.draftVersion,
          revisionStatus: state.draftStatus,
          baseActiveRevisionId: NOTIFICATION_ACTIVE_REVISION,
          updatedAt: MANUAL_RECORDED_AT,
          validatedAt:
            state.draftStatus === "validated" ? MANUAL_RECORDED_AT : null,
          validationErrors: [],
          webhook: webhookDocument(state, token),
        }
      : null,
    supportedEvents: [
      "job.completed",
      "job.failed",
      "job.cancelled",
      "schedule.emitted",
    ],
    actions: notificationDraftActions(state, token),
  };
}

function notificationDeliveryItem(state, deliveryId) {
  const requeued = state.requeued && deliveryId === NOTIFICATION_DELIVERY_ID;
  return {
    deliveryId,
    webhookId: NOTIFICATION_WEBHOOK_ID,
    eventId: `event-${deliveryId}`,
    eventType: "job.completed",
    status: requeued ? "pending" : "dead-letter",
    attempts: requeued ? 0 : 3,
    nextAttemptAt: MANUAL_RECORDED_AT,
    createdAt: MANUAL_RECORDED_AT,
    updatedAt: MANUAL_RECORDED_AT,
    deliveredAt: null,
    failureCategory: requeued ? null : "http_400",
    responseStatus: requeued ? null : 400,
  };
}

function notificationDeliveryDetailDocument(state, token, deliveryId) {
  const item = notificationDeliveryItem(state, deliveryId);
  const { manage } = notificationPermissions(token);
  const expiredLease =
    deliveryId === NOTIFICATION_DELIVERY_ID_2 && !state.requeued;
  return {
    ...item,
    lease: expiredLease
      ? {
          state: "expired",
          leaseSeconds: 300,
          claimedAt: MANUAL_RECORDED_AT,
          expiresAt: MANUAL_RECORDED_AT,
        }
      : { state: "not_leased" },
    knownEffects: expiredLease
      ? "the delivery lease expired without a durable terminal outcome; the receiver may have processed the original request before the worker stopped (at-least-once)"
      : "the receiver never confirmed success after the configured attempts (last failure: http_400); whether an earlier request was processed is unknown",
    retrySafe: true,
    nextAction: expiredLease
      ? "resolve the stale delivery to return it to the pending queue, or refresh if the worker is only slow"
      : "confirm the endpoint is reachable and healthy, then explicitly requeue this delivery",
    recovery: expiredLease
      ? {
          availableActions: ["resolve-stale"],
          reason: "The delivery lease expired without a terminal outcome.",
          actions: [
            {
              name: "resolve-stale",
              durableState:
                "the delivery stays one row with the same identity and attempts; the queue state returns to pending",
              sideEffects:
                "no new delivery and no media, Task, Job, schedule or Storage change; the notification worker will send the event again",
              retrySafe: true,
              duplicateImplication:
                "the receiver may process the event more than once (at-least-once)",
              nextAction:
                "explicitly resolve the stale delivery, then refresh; the worker reclaims it automatically",
            },
          ],
        }
      : {
          availableActions:
            item.status === "dead-letter" ? ["requeue-dead-letter"] : [],
          reason:
            item.status === "dead-letter"
              ? "The delivery reached the terminal dead-letter state."
              : "This delivery is pending automatic delivery.",
          actions:
            item.status === "dead-letter"
              ? [
                  {
                    name: "requeue-dead-letter",
                    durableState:
                      "the delivery stays one row with the same identity; attempts are reset and the queue state returns to pending",
                    sideEffects:
                      "no new delivery and no media, Task, Job, schedule or Storage change; the notification worker will send the event again",
                    retrySafe: true,
                    duplicateImplication:
                      "under at-least-once semantics a receiver that processed an unconfirmed request may still see the event again",
                    nextAction:
                      "explicitly requeue this delivery, then refresh; the worker delivers it automatically",
                  },
                ]
              : [],
        },
    actions:
      item.status === "dead-letter" && !expiredLease
        ? {
            requeue: notificationAction({
              available: manage,
              reason: manage
                ? null
                : "the connected API principal cannot recover notification deliveries (required permission: manage_configuration)",
              method: "POST",
              path: `/api/v1/notifications/${deliveryId}/requeue`,
              requiresConfirmation: true,
              sideEffects: "delivery_queue_state_only",
              durableOutcome:
                "the dead-letter delivery returns to pending with the same identity; attempts are reset",
              nextAction:
                "confirm the requeue, then refresh this delivery to watch the worker reclaim it",
            }),
          }
        : expiredLease
          ? {
              resolveStale: notificationAction({
                available: manage,
                reason: manage
                  ? null
                  : "the connected API principal cannot recover notification deliveries (required permission: manage_configuration)",
                method: "POST",
                path: `/api/v1/notifications/${deliveryId}/resolve-stale`,
                requiresConfirmation: true,
                sideEffects: "delivery_queue_state_only",
                durableOutcome:
                  "the expired-lease delivery returns to pending with the same identity and attempts",
                nextAction:
                  "confirm the stale resolution, then refresh this delivery to watch the worker reclaim it",
              }),
            }
          : {},
  };
}

function automationDefinitionActions(state, token) {
  const { manage, grant, dryRun } = automationPermissions(token);
  return {
    detail: automationAction({
      available: true,
      method: "GET",
      path: `/api/v1/operations/automation/task-definitions/${AUTOMATION_DEFINITION_ID}`,
      durableOutcome: null,
      nextAction:
        "inspect the durable definition, schedule and occurrence state",
    }),
    occurrences: automationAction({
      available: true,
      method: "GET",
      path: `/api/v1/operations/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/occurrences`,
      durableOutcome: null,
      nextAction: "inspect the bounded occurrence history and its linked work",
    }),
    preview: automationAction({
      available: dryRun,
      reason: dryRun
        ? null
        : "the connected API principal cannot run a zero-mutation Automation Preview",
      path: `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/preview`,
      durableOutcome:
        "a durable zero-mutation Preview of the exact Active definition is stored",
      nextAction:
        "create the exact Preview after reviewing the schedule and scope",
    }),
    grantState: automationAction({
      available: true,
      method: "GET",
      path: `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/grant-state`,
      durableOutcome: null,
      nextAction: "read the current unattended grant state and its eligibility",
    }),
    grant: automationAction({
      available: grant,
      reason: grant
        ? null
        : "the connected API principal cannot grant unattended execution authority",
      path: `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/grant`,
      requiresConfirmation: true,
      durableOutcome:
        "a persistent scoped unattended execution grant is stored and audited",
      nextAction:
        "run a fresh exact Preview, review its eligibility and explicitly confirm the unattended grant",
    }),
    revoke: automationAction({
      available: grant,
      reason: grant
        ? null
        : "the connected API principal cannot revoke unattended execution authority",
      path: `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/revoke`,
      durableOutcome:
        "the grant is revoked; future unattended mutation is prevented without rewriting completed effects",
      nextAction: "revoke the grant when its exact bounds are no longer wanted",
    }),
    copy: automationAction({
      available: manage && state.draftCreated,
      reason: manage
        ? state.draftCreated
          ? null
          : "an open successor Draft is required to copy this definition"
        : "the connected API principal cannot copy Automation Task Definitions",
      path: `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/copy`,
      durableOutcome:
        "a copied definition is stored inside the open successor Draft",
      nextAction:
        "create or open a successor Draft, then copy the definition inside it",
    }),
    draftCreate: automationAction({
      available: manage,
      reason: manage
        ? null
        : "the connected API principal cannot create a successor Draft",
      path: `/api/v1/configuration/revisions/${AUTOMATION_ACTIVE_REVISION}/successor`,
      durableOutcome:
        "a successor Draft seeded from the immutable Active configuration is stored",
      nextAction:
        "create or open the successor Draft, edit the definition, then validate and explicitly activate",
    }),
  };
}

function automationDefinitionDocument(state, token) {
  const eligible =
    state.previewCreated && !state.previewStale && !state.granted;
  const draftState = state.draftCreated
    ? {
        present: true,
        reason: null,
        revisionId: AUTOMATION_DRAFT_REVISION,
        revisionVersion: state.draftVersion,
        revisionStatus: state.draftStatus,
        baseActiveRevisionId: AUTOMATION_ACTIVE_REVISION,
        updatedAt: MANUAL_RECORDED_AT,
        validatedAt:
          state.draftStatus === "validated" ? MANUAL_RECORDED_AT : null,
        validationErrors: [],
      }
    : {
        present: false,
        reason: "no open successor Draft contains this definition",
        revisionId: null,
        revisionVersion: null,
        revisionStatus: null,
        baseActiveRevisionId: null,
        updatedAt: null,
        validatedAt: null,
        validationErrors: [],
      };
  const grant = state.granted
    ? {
        status: "active",
        active: true,
        grantId: AUTOMATION_GRANT_ID,
        definitionId: AUTOMATION_DEFINITION_ID,
        definitionChangedSinceGrant: false,
        nextAction:
          "inspect the next occurrence or revoke this grant before changing its exact bounds",
        maxItemsPerRun: 12,
        previewId: AUTOMATION_PREVIEW_ID,
        grantingPrincipal: "e2e-operator",
        grantedAt: MANUAL_RECORDED_AT,
        revokedAt: null,
        reason: null,
        currentPermission: {
          principalId: "e2e-operator",
          status: "valid",
          allowed: true,
        },
      }
    : {
        status: "none",
        active: false,
        grantId: null,
        definitionId: AUTOMATION_DEFINITION_ID,
        definitionChangedSinceGrant: false,
        nextAction:
          "review the exact definition bounds and explicitly grant unattended execution",
      };
  return {
    id: AUTOMATION_DEFINITION_ID,
    name: "Nightly automation",
    definitionState: "active",
    enabled: true,
    resourceLibraryId: "source",
    mode: "automatic-organization",
    itemLimit: 12,
    sourceScope: null,
    intervalSeconds: 3600,
    occurrence: {
      enabled: true,
      nextRunAt: "2026-01-02T08:00:00+00:00",
      lastOccurrenceAt: MANUAL_RECORDED_AT,
      lastJobId: AUTOMATION_JOB_ID,
      lastTaskId: AUTOMATION_TASK_ID,
      lastOutcome: "completed",
      lastReason: null,
      nextAction:
        "inspect the verified per-item Results; no replay is required",
      lastFailureCategory: null,
      outcomeSummary: {
        taskId: AUTOMATION_TASK_ID,
        totalItems: 2,
        statusCounts: { completed: 2 },
        bound: {
          configuredItemLimit: 12,
          reached: false,
          statement:
            "2 item(s) completed; the configured item bound was not reached.",
        },
        attention: [],
        attentionTruncated: false,
      },
    },
    unattendedExecutionGrant: grant,
    activeConfiguration: {
      revisionId: state.activated
        ? AUTOMATION_DRAFT_REVISION
        : AUTOMATION_ACTIVE_REVISION,
      version: state.activated ? 4 : 3,
      revisionSequence: state.activated ? 3 : 2,
      status: "active",
    },
    draftState,
    grantEligibility: {
      eligible,
      status: eligible ? "eligible" : "ineligible",
      previewId: AUTOMATION_PREVIEW_ID,
      previewStatus: "previewed",
      current: state.previewCreated && !state.previewStale,
      zeroMutation: true,
      maxItemsPerRun: 12,
      currentPermission: {
        principalId: "e2e-operator",
        status: "valid",
        allowed: true,
      },
      explanation:
        state.previewCreated && !state.previewStale
          ? "the exact current Preview and current permission satisfy the persisted grant bounds"
          : "no current exact Preview supports unattended authority; run a fresh exact Preview",
      durableState: "no grant or media mutation has been created",
      retrySafe: true,
      nextAction:
        "review the exact bounds and explicitly confirm the unattended grant",
      error: eligible
        ? null
        : {
            code: "unattended_execution_preview_required",
            status: 409,
            message:
              "no current exact Preview supports unattended authority; run a fresh exact Preview",
            durableState: "no grant or media mutation has been created",
            retrySafe: true,
            nextAction: "run a fresh exact Preview",
          },
    },
    actions: automationDefinitionActions(state, token),
  };
}

/**
 * A definition that exists only inside the open successor Draft (newly
 * created or copied): truthful draft-only state, empty occurrence history,
 * no grant and no Active-definition actions until checked activation.
 */
function automationDraftOnlyDefinitionDocument(state, token, definition) {
  const { manage } = automationPermissions(token);
  const notActiveReason =
    "this definition exists only inside an open successor Draft; " +
    "activate the Draft to make it the Active definition";
  return {
    id: definition.id,
    name: definition.name,
    definitionState: "draft-only",
    enabled: definition.enabled === true,
    resourceLibraryId: definition.resourceLibraryId,
    mode: definition.mode,
    itemLimit: definition.itemLimit,
    sourceScope: null,
    intervalSeconds: definition.intervalSeconds ?? null,
    cron: definition.cron ?? null,
    timezone: definition.timezone ?? null,
    occurrence: {
      enabled: definition.enabled === true,
      nextRunAt: null,
      lastOccurrenceAt: null,
      lastJobId: null,
      lastTaskId: null,
      lastOutcome: null,
      lastReason: null,
      nextAction: null,
      lastFailureCategory: null,
      outcomeSummary: null,
    },
    unattendedExecutionGrant: {
      status: "none",
      active: false,
      grantId: null,
      definitionId: definition.id,
      definitionChangedSinceGrant: false,
      nextAction:
        "review the exact definition bounds and explicitly grant unattended execution",
    },
    activeConfiguration: {
      revisionId: state.activated
        ? AUTOMATION_DRAFT_REVISION
        : AUTOMATION_ACTIVE_REVISION,
      version: state.activated ? 4 : 3,
      revisionSequence: state.activated ? 3 : 2,
      status: "active",
    },
    draftState: {
      present: true,
      reason: null,
      revisionId: AUTOMATION_DRAFT_REVISION,
      revisionVersion: state.draftVersion,
      revisionStatus: state.draftStatus,
      baseActiveRevisionId: AUTOMATION_ACTIVE_REVISION,
      updatedAt: MANUAL_RECORDED_AT,
      validatedAt:
        state.draftStatus === "validated" ? MANUAL_RECORDED_AT : null,
      validationErrors: [],
    },
    actions: {
      detail: automationAction({
        available: true,
        method: "GET",
        path: `/api/v1/operations/automation/task-definitions/${definition.id}`,
        durableOutcome: null,
        nextAction:
          "inspect the durable definition, schedule and occurrence state",
      }),
      occurrences: automationAction({
        available: true,
        method: "GET",
        path: `/api/v1/operations/automation/task-definitions/${definition.id}/occurrences`,
        durableOutcome: null,
        nextAction:
          "inspect the bounded occurrence history and its linked work",
      }),
      preview: automationAction({
        available: false,
        reason: notActiveReason,
        path: `/api/v1/automation/task-definitions/${definition.id}/preview`,
        durableOutcome:
          "a durable zero-mutation Preview of the exact Active definition is stored",
        nextAction: "activate the Draft, then create the exact Preview",
      }),
      grantState: automationAction({
        available: true,
        method: "GET",
        path: `/api/v1/automation/task-definitions/${definition.id}/grant-state`,
        durableOutcome: null,
        nextAction:
          "read the current unattended grant state and its eligibility",
      }),
      grant: automationAction({
        available: false,
        reason: notActiveReason,
        path: `/api/v1/automation/task-definitions/${definition.id}/grant`,
        requiresConfirmation: true,
        durableOutcome:
          "a persistent scoped unattended execution grant is stored and audited",
        nextAction: "activate the Draft before granting unattended authority",
      }),
      revoke: automationAction({
        available: false,
        reason: notActiveReason,
        path: `/api/v1/automation/task-definitions/${definition.id}/revoke`,
        durableOutcome:
          "the grant is revoked; future unattended mutation is prevented without rewriting completed effects",
        nextAction: "activate the Draft before granting unattended authority",
      }),
      copy: automationAction({
        available: manage && state.draftCreated,
        reason: manage
          ? state.draftCreated
            ? null
            : "an open successor Draft is required to copy this definition"
          : "the connected API principal cannot copy Automation Task Definitions",
        path: `/api/v1/automation/task-definitions/${definition.id}/copy`,
        durableOutcome:
          "a copied definition is stored inside the open successor Draft",
        nextAction: "copy the definition inside the open successor Draft",
      }),
      draftCreate: automationAction({
        available: manage,
        reason: manage
          ? null
          : "the connected API principal cannot create a successor Draft",
        path: `/api/v1/configuration/revisions/${AUTOMATION_ACTIVE_REVISION}/successor`,
        durableOutcome:
          "a successor Draft seeded from the immutable Active configuration is stored",
        nextAction:
          "create or open the successor Draft, then edit this definition inside it",
      }),
    },
  };
}

function automationListDocument(state, token) {
  const { manage } = automationPermissions(token);
  const items = [automationDefinitionDocument(state, token)];
  // Newly created or copied definitions live only inside the open Draft
  // until activation; the list mirrors the real backend projection by
  // serving them as draft-only items.
  for (const definition of [state.createdDefinition, state.copiedDefinition]) {
    if (definition !== null && definition !== undefined) {
      items.push(
        automationDraftOnlyDefinitionDocument(state, token, definition),
      );
    }
  }
  return {
    activeConfiguration: {
      revisionId: state.activated
        ? AUTOMATION_DRAFT_REVISION
        : AUTOMATION_ACTIVE_REVISION,
      version: state.activated ? 4 : 3,
      revisionSequence: state.activated ? 3 : 2,
      status: "active",
    },
    items,
    total: items.length,
    truncated: false,
    draftState: state.draftCreated
      ? {
          present: true,
          reason: null,
          revisionId: AUTOMATION_DRAFT_REVISION,
          revisionVersion: state.draftVersion,
          revisionStatus: state.draftStatus,
          baseActiveRevisionId: AUTOMATION_ACTIVE_REVISION,
          updatedAt: MANUAL_RECORDED_AT,
          validatedAt:
            state.draftStatus === "validated" ? MANUAL_RECORDED_AT : null,
          validationErrors: [],
        }
      : {
          present: false,
          reason:
            "no open successor Draft exists; create one to add or edit definitions",
          revisionId: null,
          revisionVersion: null,
          revisionStatus: null,
          baseActiveRevisionId: null,
          updatedAt: null,
          validatedAt: null,
          validationErrors: [],
        },
    resourceLibraryOptions: [{ id: "source", name: "Source", enabled: true }],
    actions: {
      create: automationAction({
        available: manage,
        reason: manage
          ? null
          : "the connected API principal cannot create Automation Task Definitions",
        path: "/api/v1/automation/task-definitions",
        durableOutcome:
          "the bounded definition is stored inside the open successor Draft",
        nextAction:
          "start or open a successor Draft, then create the definition inside it",
      }),
      createDraft: automationAction({
        available: manage,
        reason: manage
          ? null
          : "the connected API principal cannot create a successor Draft",
        path: `/api/v1/configuration/revisions/${AUTOMATION_ACTIVE_REVISION}/successor`,
        durableOutcome:
          "a successor Draft seeded from the immutable Active configuration is stored",
        nextAction:
          "create or open the successor Draft, then add or edit definitions inside it",
      }),
    },
  };
}

function automationDraftDocument(state, token, definitionOverride = null) {
  const { manage, activate } = automationPermissions(token);
  const definitionId =
    definitionOverride !== null
      ? definitionOverride.id
      : AUTOMATION_DEFINITION_ID;
  const draft = state.draftCreated
    ? {
        revisionId: AUTOMATION_DRAFT_REVISION,
        revisionVersion: state.draftVersion,
        revisionStatus: state.draftStatus,
        baseActiveRevisionId: AUTOMATION_ACTIVE_REVISION,
        updatedAt: MANUAL_RECORDED_AT,
        validatedAt:
          state.draftStatus === "validated" ? MANUAL_RECORDED_AT : null,
        validationErrors: [],
        definition:
          definitionOverride !== null
            ? {
                id: definitionOverride.id,
                name: definitionOverride.name,
                enabled: definitionOverride.enabled === true,
                resourceLibraryId: definitionOverride.resourceLibraryId,
                mode: definitionOverride.mode,
                itemLimit: definitionOverride.itemLimit,
                sourceScope: null,
                intervalSeconds: definitionOverride.intervalSeconds ?? null,
                cron: definitionOverride.cron ?? null,
                timezone: definitionOverride.timezone ?? null,
              }
            : {
                id: AUTOMATION_DEFINITION_ID,
                name: "Nightly automation",
                enabled: true,
                resourceLibraryId: "source",
                mode: "automatic-organization",
                itemLimit: 12,
                sourceScope: null,
                intervalSeconds: 3600,
                cron: null,
                timezone: null,
              },
      }
    : null;
  return {
    definitionId,
    activeConfiguration: {
      revisionId: state.activated
        ? AUTOMATION_DRAFT_REVISION
        : AUTOMATION_ACTIVE_REVISION,
      version: state.activated ? 4 : 3,
      revisionSequence: state.activated ? 3 : 2,
      status: "active",
    },
    draft,
    resourceLibraryOptions: [{ id: "source", name: "Source", enabled: true }],
    actions: {
      createDraft: automationAction({
        available: manage,
        reason: manage
          ? null
          : "the connected API principal cannot create a successor Draft",
        path: `/api/v1/configuration/revisions/${AUTOMATION_ACTIVE_REVISION}/successor`,
        durableOutcome:
          "a successor Draft seeded from the immutable Active configuration is stored",
        nextAction:
          "create the successor Draft, then edit this definition inside it",
      }),
      save: automationAction({
        available: manage && state.draftCreated,
        reason: manage
          ? state.draftCreated
            ? null
            : "an open successor Draft is required to edit this definition"
          : "the connected API principal cannot edit Automation Task Definitions",
        method: "PUT",
        path: `/api/v1/configuration/revisions/${AUTOMATION_DRAFT_REVISION}/objects/automationTaskDefinitions/${definitionId}`,
        durableOutcome:
          "the bounded definition form is stored in the open successor Draft at a new optimistic revision version",
        nextAction:
          "save the bounded form, then validate and explicitly activate",
      }),
      validate: automationAction({
        available: manage && state.draftCreated,
        reason: manage
          ? state.draftCreated
            ? null
            : "an open successor Draft is required before validation"
          : "the connected API principal cannot validate configuration",
        path: `/api/v1/configuration/revisions/${AUTOMATION_DRAFT_REVISION}/validate`,
        durableOutcome:
          "the open Draft is validated without any runtime or Storage effect",
        nextAction: "validate the Draft, then review the validation evidence",
      }),
      activate: automationAction({
        available: activate && state.draftCreated,
        reason: activate
          ? state.draftCreated
            ? null
            : "an open successor Draft is required before activation"
          : "the connected API principal cannot activate configuration",
        path: `/api/v1/operations/automation/task-definitions/${definitionId}/activate-draft`,
        requiresConfirmation: true,
        durableOutcome:
          "the exact Draft becomes the immutable Active configuration after the exact-revision binding and Automation-only boundary checks; no Scan, Job, Task or occurrence is started",
        nextAction: "confirm one explicit activation of the validated Draft",
      }),
    },
  };
}

function automationPreviewItem() {
  return {
    previewItemId: "automation-preview-item-e2e-001",
    previewId: AUTOMATION_PREVIEW_ID,
    definitionId: AUTOMATION_DEFINITION_ID,
    position: 0,
    source: {
      storageId: "source-storage",
      resourceLibraryId: "source",
      path: "Media/电影/One.2001.mkv",
      filename: "One.2001.mkv",
      extension: "mkv",
      size: 32,
      stability: "stable",
      scanStatus: "discovered",
    },
    status: "previewed",
    recognition: {
      status: "matched",
      ruleId: "movie-library",
      recognitionTypeId: "A",
    },
    recognitionTypePolicy: {
      recognitionTypePolicyId: "A",
      metadataPolicyId: "A",
      namingPolicyId: "A",
      classificationPolicyId: "A",
      organizePolicyId: "A",
    },
    metadata: {
      provider: "tmdb",
      providerId: "129",
      mediaType: "movie",
      status: "resolved",
      title: "One",
      year: 2001,
    },
    naming: {
      directory: "One (2001) [tmdbid-129]",
      filename: "One (2001) [tmdbid-129].mkv",
    },
    classification: {
      mediaLibraryId: "movies",
      relativePath: "One (2001)/One (2001) [tmdbid-129].mkv",
    },
    destination: {
      storageId: "media-target",
      path: "One (2001)/One (2001) [tmdbid-129].mkv",
    },
    operation: null,
    attachments: [],
    capabilities: { required: [], declared: [], verdict: "ok" },
    conflictStrategy: null,
    conflicts: [],
    warnings: [],
    blocker: null,
    nextAction: null,
    sideEffects: "none",
    zeroMutation: true,
    executionState: "not_available_in_this_task",
    current: true,
    createdAt: MANUAL_RECORDED_AT,
    updatedAt: MANUAL_RECORDED_AT,
  };
}

function automationPreviewActions(state, token, previewId) {
  const { grant } = automationPermissions(token);
  const current = state.previewCreated && !state.previewStale;
  const base = `/api/v1/operations/automation/task-definitions/${AUTOMATION_DEFINITION_ID}`;
  return {
    detail: automationAction({
      available: true,
      method: "GET",
      path: `${base}/previews/${previewId}`,
      durableOutcome: null,
      nextAction: "inspect the exact Preview evidence and its items",
    }),
    items: automationAction({
      available: true,
      method: "GET",
      path: `${base}/previews/${previewId}/items`,
      durableOutcome: null,
      nextAction: "page the bounded Preview item evidence",
    }),
    definition: automationAction({
      available: true,
      method: "GET",
      path: base,
      durableOutcome: null,
      nextAction: "reopen the durable definition behind this Preview",
    }),
    grantState: automationAction({
      available: true,
      method: "GET",
      path: `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/grant-state`,
      durableOutcome: null,
      nextAction: "read the current unattended grant state and its eligibility",
    }),
    grant: automationAction({
      available: grant && current,
      reason: grant
        ? current
          ? null
          : "this Preview is historical, truncated or incomplete and cannot support unattended authority; run a fresh exact Preview"
        : "the connected API principal cannot grant unattended execution authority",
      path: `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/grant`,
      requiresConfirmation: true,
      durableOutcome:
        "a persistent scoped unattended execution grant bound to this exact Preview is stored and audited",
      nextAction:
        "review the grant eligibility and explicitly confirm the unattended grant",
    }),
  };
}

function automationPreviewDocument(state, token, previewId) {
  const current = state.previewCreated && !state.previewStale;
  const eligible = current && !state.granted;
  return {
    previewId,
    definitionId: AUTOMATION_DEFINITION_ID,
    configurationRevisionId: AUTOMATION_ACTIVE_REVISION,
    configurationRevisionVersion: 3,
    configurationStatus: "active",
    resourceLibraryId: "source",
    sourceScope: null,
    runMode: "automatic-organization",
    effectiveItemLimit: 12,
    counts: {
      discovered: 2,
      selected: 2,
      permitted: 2,
      excludedIgnored: 0,
      unstable: 0,
      truncatedByLimit: 0,
    },
    status: current ? "previewed" : "stale",
    items:
      current || previewId !== AUTOMATION_PREVIEW_ID
        ? [automationPreviewItem()]
        : [],
    boundaryErrors: [],
    nextAction: "review the exact Preview evidence and its items",
    error: null,
    sideEffects: "none",
    zeroMutation: true,
    executionState: "not_available_in_this_task",
    current,
    staleReason: current
      ? null
      : "the pinned definition changed after this Preview was created",
    truncated: false,
    createdAt: MANUAL_RECORDED_AT,
    updatedAt: MANUAL_RECORDED_AT,
    itemTotal: 1,
    itemsTruncated: false,
    grantEligibility: {
      eligible,
      status: eligible ? "eligible" : "ineligible",
      previewId,
      previewStatus: current ? "previewed" : "stale",
      current,
      zeroMutation: true,
      maxItemsPerRun: 12,
      currentPermission: {
        principalId: "e2e-operator",
        status: "valid",
        allowed: true,
      },
      explanation: current
        ? "the exact current Preview and current granting-principal permission satisfy the persisted grant bounds"
        : "no current exact Preview supports unattended authority; run a fresh exact Preview",
      durableState: "no grant or media mutation has been created",
      retrySafe: true,
      nextAction: eligible
        ? "review the exact bounds and explicitly confirm the unattended grant"
        : "run a fresh exact Preview",
      error: eligible
        ? null
        : {
            code: "unattended_execution_preview_required",
            status: 409,
            message:
              "no current exact Preview supports unattended authority; run a fresh exact Preview",
            durableState: "no grant or media mutation has been created",
            retrySafe: true,
            nextAction: "run a fresh exact Preview",
          },
    },
    actions: automationPreviewActions(state, token, previewId),
  };
}

function automationOccurrenceDocument() {
  return {
    occurrenceId: AUTOMATION_OCCURRENCE_ID,
    definitionId: AUTOMATION_DEFINITION_ID,
    occurrenceAt: MANUAL_RECORDED_AT,
    emittedAt: MANUAL_RECORDED_AT,
    jobId: AUTOMATION_JOB_ID,
    definitionVersion: 3,
    configurationRevisionId: AUTOMATION_ACTIVE_REVISION,
    configurationRevisionVersion: 3,
    runMode: "automatic-organization",
    resourceLibraryId: "source",
    sourceScope: null,
    itemLimit: 12,
    outcome: "completed",
    reason: null,
    nextAction: "inspect the verified per-item Results; no replay is required",
    taskId: AUTOMATION_TASK_ID,
    failureCategory: null,
    outcomeSummary: {
      taskId: AUTOMATION_TASK_ID,
      totalItems: 2,
      statusCounts: { completed: 2 },
      bound: {
        configuredItemLimit: 12,
        reached: false,
        statement:
          "2 item(s) completed; the configured item bound was not reached.",
      },
      attention: [],
      attentionTruncated: false,
    },
    actions: {
      job: automationAction({
        available: true,
        method: "GET",
        path: `/api/v1/operations/jobs/${AUTOMATION_JOB_ID}`,
        durableOutcome: null,
        nextAction: "inspect the durable admission Job",
      }),
      task: automationAction({
        available: true,
        method: "GET",
        path: `/api/v1/operations/tasks/${AUTOMATION_TASK_ID}`,
        durableOutcome: null,
        nextAction: "inspect the durable Task and its per-item Results",
      }),
    },
  };
}

function automationActivationDocument(state) {
  return {
    activatedRevisionId: AUTOMATION_DRAFT_REVISION,
    activatedVersion: state.draftVersion,
    revisionSequence: 3,
    activeConfiguration: {
      revisionId: AUTOMATION_DRAFT_REVISION,
      version: 4,
      revisionSequence: 3,
      status: "active",
    },
    definition: null,
  };
}

const AUTOMATION_MUTATION_BODY_FIELDS = [
  "confirmation",
  "expectedVersion",
  "expectedRevisionId",
  "previewId",
  "reason",
];

function boundedAutomationBody(fields) {
  const body = {};
  for (const key of AUTOMATION_MUTATION_BODY_FIELDS) {
    const value = fields[key];
    if (value === null || value === undefined || value === "") {
      continue;
    }
    body[key] = value;
  }
  if (fields.object !== null && fields.object !== undefined) {
    const object = fields.object;
    body.object = {
      enabled: object.enabled === true,
      id: typeof object.id === "string" ? object.id : null,
      itemLimit: typeof object.itemLimit === "number" ? object.itemLimit : null,
      mode: typeof object.mode === "string" ? object.mode : null,
      name: typeof object.name === "string" ? object.name : null,
      resourceLibraryId:
        typeof object.resourceLibraryId === "string"
          ? object.resourceLibraryId
          : null,
      intervalSeconds:
        typeof object.intervalSeconds === "number"
          ? object.intervalSeconds
          : null,
      cron: typeof object.cron === "string" ? object.cron : null,
      timezone: typeof object.timezone === "string" ? object.timezone : null,
    };
  }
  return body;
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  const token = bearerToken(req);
  // One evidence/state bucket per browser session so parallel Playwright
  // workers never erase or observe another test's fake state.
  const session = manualSession(req);
  const recordManualRequestForSession = (entry) =>
    recordManualRequest({ ...entry, session });
  // The checked activation is served ONLY on the exact dedicated operations
  // route the real backend publishes, before the generic operations alias
  // rewrite: a non-operations spelling or a mismatched Draft revision must
  // never activate anything.
  const activateDraftMatch = url.pathname.match(
    /^\/api\/v1\/operations\/automation\/task-definitions\/([^/]+)\/activate-draft$/,
  );
  if (activateDraftMatch && req.method === "POST") {
    // Inline the operations guard: this handler runs before the server
    // callback's const declarations, so the hoisted guard is not usable yet.
    if (EXPIRED_TOKENS.has(token) || !KNOWN_TOKENS.has(token)) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return;
    }
    if (LIMITED_TOKENS.has(token)) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const fields = parsed.document;
    const state = automationState(session);
    if (
      !state.draftCreated ||
      state.draftStatus !== "validated" ||
      fields.expectedRevisionId !== AUTOMATION_DRAFT_REVISION ||
      fields.expectedVersion !== state.draftVersion
    ) {
      sendJson(res, 409, { error: { code: "configuration_version_conflict" } });
      return;
    }
    state.activated = true;
    state.draftCreated = false;
    recordManualRequestForSession({
      method: "POST",
      objectId: activateDraftMatch[1],
      objectType: "automation_activate_draft",
      path: "/api/v1/operations/automation/task-definitions/:definitionId/activate-draft",
      body: boundedAutomationBody(fields),
    });
    sendJson(res, 200, automationActivationDocument(state));
    return;
  }
  // The V2 Operations workspace reads the bounded /api/v1/operations/* alias;
  // the fake mirrors the authoritative Python contract by serving the same
  // bounded documents for both spellings.
  if (url.pathname.startsWith("/api/v1/operations/")) {
    url.pathname = url.pathname.replace("/api/v1/operations/", "/api/v1/");
  }

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
    if (!READABLE_TOKENS.has(token)) {
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
    if (!READABLE_TOKENS.has(token)) {
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
    sendJson(res, 200, resourceLibrarySystemStatus(session));
    return;
  }
  if (url.pathname === "/api/v1/resource-libraries" && req.method === "POST") {
    if (!KNOWN_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message:
            "principal lacks configuration management and activation authority",
        },
      });
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) return;
    const fields = parsed.document;
    const allowed = new Set([
      "resourceLibraryId",
      "name",
      "enabled",
      "storageId",
      "storagePath",
    ]);
    if (
      Object.keys(fields).some((key) => !allowed.has(key)) ||
      allowed.size !== Object.keys(fields).length ||
      typeof fields.resourceLibraryId !== "string" ||
      typeof fields.name !== "string" ||
      typeof fields.enabled !== "boolean" ||
      typeof fields.storageId !== "string" ||
      typeof fields.storagePath !== "string"
    ) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const state = resourceLibraryState(session);
    if (state.saved || fields.resourceLibraryId === "resources") {
      sendJson(res, 409, {
        error: {
          code: "resource_library_duplicate",
          details: {
            durableState: "active_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction: "choose a different ResourceLibrary ID, then retry",
          },
        },
      });
      return;
    }
    if (state.failOnce && !state.failed) {
      state.failed = true;
      sendJson(res, 409, {
        error: {
          code: "resource_library_storage_check_failed",
          details: {
            durableState: "active_preserved",
            sideEffects: "read-only evidence only; Storage unchanged",
            retrySafe: true,
            nextAction: "correct Storage availability, then retry Save",
          },
        },
      });
      return;
    }
    state.saved = true;
    state.candidate = { ...fields };
    sendJson(res, 200, {
      resourceLibrary: {
        id: fields.resourceLibraryId,
        name: fields.name,
        storageId: fields.storageId,
        storagePath: fields.storagePath,
        enabled: fields.enabled,
      },
      active: {
        revisionId: "rev-e2e-2",
        status: "active",
        version: 2,
      },
      configuration: {
        authority: "MANAGED",
        revisionId: "rev-e2e-2",
        version: 2,
      },
      sideEffects: "configuration_only",
      nextAction:
        "refresh the Active ResourceLibrary list and browse the selected library",
    });
    return;
  }
  const directCommandMatch = url.pathname.match(
    /^\/api\/v1\/resource-libraries\/([^/]+)\/files\/(commands|text|delete-impact)$/,
  );
  if (directCommandMatch) {
    if (!KNOWN_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    if (!READABLE_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: { code: "forbidden", message: "principal lacks permission" },
      });
      return;
    }
    const resourceLibraryId = decodeURIComponent(directCommandMatch[1]);
    const action = directCommandMatch[2];
    const state = resourceLibraryState(session);
    if (action === "commands" && req.method === "POST") {
      const parsed = await readBoundedJsonBody(req, res);
      if (!parsed.ok) return;
      const fields = parsed.document;
      state.commandLog.push({ ...fields });
      if (fields.operation === "delete") {
        const digest = `fake-scope-digest-${(fields.paths ?? []).join(",")}`;
        if (fields.confirmationDigest !== digest) {
          sendJson(res, 409, {
            error: {
              code: "files_direct_stale_confirmation",
              details: {
                category: "stale_confirmation",
                durableState: "storage_unchanged",
                sideEffects: "none",
                retrySafe: true,
                nextAction:
                  "review the refreshed impact summary and confirm again",
              },
            },
          });
          return;
        }
        const outcomes = (fields.paths ?? []).map((path) => ({
          path,
          status: "SUCCESS",
          errorCategory: null,
        }));
        sendJson(res, 200, {
          operation: "delete",
          status: "SUCCESS",
          taskId: "task-e2e-delete",
          taskStatus: "completed",
          topLevelPaths: fields.paths ?? [],
          totalItems: outcomes.length,
          succeededItems: outcomes.length,
          failedItems: 0,
          outcomes,
          sideEffects: "storage_mutations",
        });
        return;
      }
      if (fields.operation === "save_text" && state.textStale) {
        sendJson(res, 409, {
          error: {
            code: "files_direct_stale_content",
            details: {
              category: "stale_changed",
              durableState: "storage_unchanged",
              sideEffects: "none",
              retrySafe: true,
              nextAction:
                "reload the current content, reapply the edits and save again",
            },
          },
        });
        return;
      }
      const target =
        fields.operation === "rename" || fields.operation === "save_text"
          ? fields.operation === "rename"
            ? fields.name
            : fields.path
          : (fields.name ?? "");
      sendJson(res, 200, {
        operation: fields.operation,
        status: "SUCCESS",
        path: fields.path ?? "",
        target,
        effectCertainty: "verified_complete",
        sideEffects: "storage_mutations",
      });
      return;
    }
    if (action === "text" && req.method === "GET") {
      const path = url.searchParams.get("path") ?? "";
      if (state.textStale) {
        // A stale marker does not affect the read; the Save compares digests.
      }
      sendJson(res, 200, {
        resourceLibraryId,
        path,
        content: "fake bounded text\nline two\n",
        evidence: {
          size: 24,
          modifiedAt: "2026-08-23T11:15:00Z",
          digest: state.textStale ? "digest-stale" : "digest-e2e-1",
        },
        sideEffects: "none",
        retrySafe: true,
      });
      return;
    }
    if (action === "delete-impact" && req.method === "GET") {
      const paths = url.searchParams.getAll("path");
      sendJson(res, 200, deleteImpactDocument(resourceLibraryId, paths));
      return;
    }
  }
  const removalPreviewMatch = url.pathname.match(
    /^\/api\/v1\/resource-libraries\/([^/]+)\/removal-preview$/,
  );
  if (removalPreviewMatch && req.method === "GET") {
    if (!READABLE_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    sendJson(
      res,
      200,
      removalPreviewDocument(
        decodeURIComponent(removalPreviewMatch[1]),
        resourceLibraryState(session),
      ),
    );
    return;
  }
  const removalMatch = url.pathname.match(
    /^\/api\/v1\/resource-libraries\/([^/]+)$/,
  );
  if (removalMatch && req.method === "GET") {
    if (!READABLE_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    sendJson(
      res,
      200,
      removalPreviewDocument(
        decodeURIComponent(removalMatch[1]),
        resourceLibraryState(session),
      ),
    );
    return;
  }
  if (removalMatch && req.method === "DELETE") {
    if (!KNOWN_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    if (!VIEWER_TOKENS.has(token)) {
      sendJson(res, 403, {
        error: {
          code: "forbidden",
          message:
            "principal lacks configuration management and activation authority",
        },
      });
      return;
    }
    const resourceLibraryId = decodeURIComponent(removalMatch[1]);
    const state = resourceLibraryState(session);
    // The real backend rejects a confirmation that is not bound to the exact
    // previewed Active revision and the selected library identity.
    const confirmation = await readBoundedJsonBody(req, res);
    if (
      !confirmation.ok ||
      confirmation.document.expectedRevisionId !== "rev-e2e-2" ||
      confirmation.document.expectedVersion !== 2 ||
      confirmation.document.expectedDigest !== "digest-e2e-2" ||
      confirmation.document.expectedLibraryId !== resourceLibraryId
    ) {
      sendJson(res, 409, {
        error: {
          code: "resource_library_removal_stale",
          message:
            "the confirmed removal was previewed against a different Active configuration",
          details: {
            durableState: "active_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "refresh the current Active configuration, re-open the removal preview and confirm again",
          },
        },
      });
      return;
    }
    if ((E2E_FAKE_REFERENCES.get(resourceLibraryId) ?? 0) > 0) {
      sendJson(res, 409, {
        error: {
          code: "configuration_object_referenced",
          message: "Configuration resource_library has references",
          details: {
            objectKind: "resource_library",
            objectId: resourceLibraryId,
            referenceCount: 1,
            references: ["recognitionRules:movie-library.resourceLibraryId"],
            durableState: "active_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction: "update the references or cancel deletion",
          },
        },
      });
      return;
    }
    state.removedIds.push(resourceLibraryId);
    state.extra = state.extra.filter((item) => item.id !== resourceLibraryId);
    sendJson(res, 200, {
      removed: { id: resourceLibraryId },
      active: { status: "active", revisionId: "rev-e2e-3", version: 3 },
      configuration: {
        authority: "MANAGED",
        revisionId: "rev-e2e-3",
        version: 3,
      },
      sideEffects: "configuration_only",
      nextAction:
        "refresh the Active ResourceLibrary list and select another enabled library",
    });
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
    if (!READABLE_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
      sendJson(res, 401, {
        error: { code: "unauthorized", message: "bearer token required" },
      });
      return;
    }
    const document = fileIndexDocument(url);
    sendJson(res, document.status, document.payload);
    return;
  }
  if (
    url.pathname === "/api/v1/storage/files" ||
    /^\/api\/v1\/resource-libraries\/[^/]+\/files$/.test(url.pathname)
  ) {
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
    if (!READABLE_TOKENS.has(token)) {
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
    const resourceMatch = url.pathname.match(
      /^\/api\/v1\/resource-libraries\/([^/]+)\/files$/,
    );
    const resourceLibraryId = resourceMatch
      ? decodeURIComponent(resourceMatch[1])
      : null;
    const stateForFiles = resourceLibraryState(session);
    const savedResourceLibrary = stateForFiles.saved;
    const extraLibrary = stateForFiles.extra.find(
      (item) => item.id === resourceLibraryId,
    );
    const storageId = resourceLibraryId
      ? resourceLibraryId === "source"
        ? "source-storage"
        : "local-media"
      : url.searchParams.get("storageId");
    if (
      resourceLibraryId !== null &&
      ![
        "resources",
        "source",
        ...(savedResourceLibrary ? ["new-e2e-library"] : []),
        ...stateForFiles.extra.map((item) => item.id),
      ].includes(resourceLibraryId)
    ) {
      sendJson(res, 404, {
        error: {
          code: "storage_browser_resource_library_not_found",
          message: "requested ResourceLibrary not available",
          details: {
            category: "resource_library_not_found",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction:
              "reload the current Active runtime and choose an enabled ResourceLibrary",
          },
        },
      });
      return;
    }
    if (
      !["local-media", "remote-media", "source-storage"].includes(storageId)
    ) {
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
    if (path === "malformed") {
      sendJson(res, 200, { malformed: true });
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
    if (path === "unavailable") {
      sendJson(res, 503, {
        error: {
          code: "storage_browser_provider_unavailable",
          message: "Storage provider read failed",
          details: {
            category: "connection_failed",
            durableState: "active_runtime_preserved",
            sideEffects: "none",
            retrySafe: true,
            nextAction: "restore the Storage provider connection and retry",
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
    sendJson(
      res,
      200,
      filesDocument(
        path,
        cursor,
        extraLibrary ? extraLibrary.storage_id : storageId,
        resourceLibraryId,
        resourceLibraryState(session).candidate,
        extraLibrary ?? null,
      ),
    );
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
    if (!READABLE_TOKENS.has(token) || EXPIRED_TOKENS.has(token)) {
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
    if (!READABLE_TOKENS.has(token)) {
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
  // --- Operations fake API routes ---
  //
  // These routes mirror the authoritative Python contract: bounded
  // status/command filters with filter-bound cursors, a backend-computed
  // lifecycle projection per principal and exact object version, durable
  // cooperative controls with optimistic rejection, and no fabricated
  // capability the real API does not have. Only safe request metadata
  // (method, normalized path, submitted filter, version match) is recorded.

  const operationsPrincipal = (() => {
    if (EXPIRED_TOKENS.has(token) || !KNOWN_TOKENS.has(token)) {
      return null;
    }
    if (LIMITED_TOKENS.has(token)) {
      return { permitted: false, readable: false };
    }
    return {
      permitted: OPERATOR_TOKENS.has(token),
      readable: true,
    };
  })();

  function operationsGuard(res) {
    if (operationsPrincipal === null) {
      sendJson(res, 401, { error: { code: "unauthorized" } });
      return false;
    }
    if (!operationsPrincipal.readable) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return false;
    }
    return true;
  }

  function boundedText(value, fallback) {
    return typeof value === "string" && value.length > 0 && value.length <= 512
      ? value
      : fallback;
  }

  function taskScope(status, command) {
    return `status=${status ?? "all"};command=${command ?? "all"}`;
  }

  function encodeCollectionCursor(kind, scope, index) {
    return Buffer.from(
      JSON.stringify({ index, kind, scope, version: 2 }),
      "utf8",
    ).toString("base64url");
  }

  function decodeCollectionCursor(raw, kind, scope) {
    if (typeof raw !== "string" || raw.length === 0 || raw.length > 512) {
      return null;
    }
    try {
      const document = JSON.parse(
        Buffer.from(raw, "base64url").toString("utf8"),
      );
      if (
        document === null ||
        typeof document !== "object" ||
        document.kind !== kind ||
        document.scope !== scope ||
        document.version !== 2 ||
        !Number.isInteger(document.index) ||
        document.index < 0
      ) {
        return null;
      }
      return document.index;
    } catch {
      return null;
    }
  }

  function collectionPage(items, limit, cursor) {
    const start = cursor ?? 0;
    const page = items.slice(start, start + limit);
    const next = start + limit < items.length ? start + limit : null;
    const previous = start > 0 ? Math.max(0, start - limit) : null;
    return { next, page, previous };
  }

  function taskAction(action, label, available, unavailableReason, extra) {
    return {
      action,
      label,
      method: "POST",
      path: `/api/v1/tasks/{id}/${action}`,
      available,
      unavailableReason,
      confirmationRequired: false,
      cooperative: true,
      durableOutcome:
        extra?.durableOutcome ??
        "a durable request is stored and acknowledged at the next supported item boundary",
      sideEffects:
        extra?.sideEffects ??
        "no Storage mutation; an in-flight Provider/Storage call is not interrupted",
      retrySafe: false,
      nextAction:
        extra?.nextAction ?? "refresh the Task to read its durable state",
    };
  }

  function taskLifecycle(task, results) {
    const permitted = operationsPrincipal.permitted;
    const permissionReason = permitted
      ? null
      : "the connected API principal does not hold the cancel_job permission required for this control";
    const terminal = TERMINAL_TASK_STATUSES.has(task.status);
    const cancellable = CANCELLABLE_TASK_STATUSES.has(task.status);
    const uncertain = results.some(
      (result) => result.effect_certainty === "attempted_unverified",
    );
    const verified = results.some(
      (result) => result.effect_certainty === "verified_complete",
    );
    let cancelReason = permissionReason;
    if (cancelReason === null && !cancellable) {
      cancelReason = `a ${task.status} Task cannot be cancelled`;
    }
    let pauseReason = permissionReason;
    if (pauseReason === null && task.pause_requested) {
      pauseReason =
        "a durable pause request is already stored and is acknowledged at the next supported item boundary";
    } else if (pauseReason === null && task.status !== "running") {
      pauseReason = `only a running Task accepts a pause request; this Task is ${task.status}`;
    }
    return {
      objectType: "task",
      objectId: task.task_id,
      state: task.status,
      version: task.updated_at,
      executionPath: "operator_workflow",
      terminal,
      permitted,
      permission: "cancel_job",
      pauseRequested: task.pause_requested,
      effectCertainty: uncertain
        ? "uncertain"
        : verified
          ? "verified_complete"
          : results.length > 0
            ? "unknown"
            : "none",
      resultsObserved: results.length,
      resultsComplete: true,
      uncertainResults: results.filter(
        (result) => result.effect_certainty === "attempted_unverified",
      ).length,
      knownEffects: uncertain
        ? "an item result carries an unverified Storage effect; MediaFlow never replays an uncertain effect automatically"
        : "Storage effects are reported only from recorded item results",
      nextAction: terminal
        ? "this Task is terminal; no lifecycle control is available"
        : "refresh the Task to read the durable state",
      actions: [
        taskAction(
          "cancel",
          "Cancel Task",
          permitted && cancellable,
          cancelReason,
          {
            durableOutcome:
              "the Task and its non-terminal items are durably marked cancelled; no further item is admitted, an item that is already in flight is not interrupted and records its own outcome, and its source lock is released only when that outcome is recorded",
            nextAction:
              "refresh the Task to read the durable cancelled state and the independent item outcomes",
          },
        ),
        taskAction(
          "pause",
          "Request pause",
          permitted && task.status === "running" && !task.pause_requested,
          pauseReason,
        ),
        taskAction(
          "resume",
          "Resume Task",
          false,
          permissionReason ??
            "continuing one exact paused Task scope with its pinned configuration and successful-item exclusions is currently an operator CLI workflow; no durable queued command reproduces it, so MediaFlow does not advertise resume here",
          {
            durableOutcome:
              "not offered: no durable queued continuation of this exact paused scope exists",
            sideEffects: "none",
            nextAction:
              "continue the paused Task from the operator terminal (mediaflow tasks resume <task-id>), or leave it paused",
          },
        ),
      ],
    };
  }

  function jobLifecycle(job) {
    const permitted = operationsPrincipal.permitted;
    const permissionReason = permitted
      ? null
      : "the connected API principal does not hold the cancel_job permission required for this control";
    const terminal = TERMINAL_JOB_STATUSES.has(job.status);
    const cancellable = job.status === "pending" || job.status === "running";
    let reason = permissionReason;
    if (reason === null && job.cancellation_requested === true) {
      reason =
        "cancellation is already durably requested; the Job reaches cancelled at its own cooperative boundary";
    } else if (reason === null && !cancellable) {
      reason = `a ${job.status} Job cannot be cancelled`;
    }
    return {
      objectType: "job",
      objectId: job.job_id,
      state: job.status,
      version: job.updated_at,
      terminal,
      permitted,
      permission: "cancel_job",
      cancellationRequested: job.cancellation_requested === true,
      commandKind: "source discovery",
      knownEffects:
        "the Job owns admission and queue state; Storage effects, if any, belong to its linked Task and its per-item Results",
      nextAction: terminal
        ? "this Job is terminal; no lifecycle control is available"
        : "refresh the Job to read the durable state",
      actions: [
        {
          action: "cancel",
          label: "Cancel Job",
          method: "POST",
          path: `/api/v1/jobs/{id}/cancel`,
          available:
            permitted && cancellable && job.cancellation_requested !== true,
          unavailableReason: reason,
          confirmationRequired: false,
          cooperative: true,
          durableOutcome:
            "a durable cancellation request is stored; a pending Job becomes cancelled immediately and a running Job reaches cancelled at its next cooperative boundary",
          sideEffects:
            "no Storage mutation; an in-flight Provider/Storage call is not interrupted and completed effects are not undone",
          retrySafe: false,
          nextAction: "refresh the Job to read the durable cancellation state",
        },
      ],
    };
  }

  function taskDocument(task) {
    return {
      ...task,
      lifecycle: taskLifecycle(
        task,
        TASK_RESULTS.filter((result) => result.task_id === task.task_id),
      ),
    };
  }

  function jobDocument(job) {
    return { ...job, lifecycle: jobLifecycle(job) };
  }

  function readExpectedVersion(req, res) {
    let raw = "";
    req.on("data", (chunk) => {
      if (raw.length < 4096) {
        raw += String(chunk);
      }
    });
    return new Promise((resolve) => {
      req.on("end", () => {
        if (raw.length === 0) {
          resolve({ ok: true, version: null });
          return;
        }
        let document;
        try {
          document = JSON.parse(raw);
        } catch {
          sendJson(res, 400, { error: { code: "invalid_request" } });
          resolve({ ok: false });
          return;
        }
        if (
          document === null ||
          typeof document !== "object" ||
          Array.isArray(document) ||
          Object.keys(document).length !== 1 ||
          typeof document.expectedUpdatedAt !== "string" ||
          document.expectedUpdatedAt.length === 0 ||
          document.expectedUpdatedAt.length > 128
        ) {
          sendJson(res, 400, { error: { code: "invalid_request" } });
          resolve({ ok: false });
          return;
        }
        resolve({ ok: true, version: document.expectedUpdatedAt });
      });
    });
  }

  if (url.pathname === "/api/v1/tasks" && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const rawStatus = url.searchParams.get("status");
    const status =
      rawStatus === null || rawStatus === "" || rawStatus === "all"
        ? null
        : rawStatus;
    if (status !== null && !KNOWN_TASK_STATUSES.has(status)) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const rawCommand = url.searchParams.get("command");
    const command =
      rawCommand === null || rawCommand === "" || rawCommand === "all"
        ? null
        : rawCommand;
    if (command !== null && !SAFE_COMMAND_FILTER.test(command)) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const rawLimit = url.searchParams.get("limit");
    const limit = rawLimit === null ? 20 : Number(rawLimit);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const scope = taskScope(status, command);
    const rawCursor = url.searchParams.get("cursor");
    let offset = null;
    if (rawCursor !== null) {
      offset = decodeCollectionCursor(rawCursor, "tasks", scope);
      if (offset === null) {
        sendJson(res, 400, { error: { code: "invalid_request" } });
        return;
      }
    }
    let items = [...FAKE_TASKS].sort((left, right) =>
      left.created_at === right.created_at
        ? right.task_id.localeCompare(left.task_id)
        : right.created_at.localeCompare(left.created_at),
    );
    if (status !== null) {
      items = items.filter((task) => task.status === status);
    }
    if (command !== null) {
      const family = `${command}:`;
      items = items.filter(
        (task) => task.command === command || task.command.startsWith(family),
      );
    }
    const page = collectionPage(items, limit, offset);
    sendJson(res, 200, {
      items: page.page.map((task) => taskDocument(task)),
      limit,
      status,
      command,
      truncated: page.next !== null,
      previous_cursor:
        page.previous === null
          ? null
          : encodeCollectionCursor("tasks", scope, page.previous),
      next_cursor:
        page.next === null
          ? null
          : encodeCollectionCursor("tasks", scope, page.next),
    });
    return;
  }

  const taskDetailMatch = url.pathname.match(/^\/api\/v1\/tasks\/([^/]+)$/);
  if (taskDetailMatch && req.method === "GET") {
    if (!operationsGuard(res)) {
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
      ...taskDocument(task),
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

  const taskControlMatch = url.pathname.match(
    /^\/api\/v1\/tasks\/([^/]+)\/(cancel|pause|resume)$/,
  );
  if (taskControlMatch && req.method === "POST") {
    if (!operationsGuard(res)) {
      return;
    }
    const action = taskControlMatch[2];
    if (!operationsPrincipal.permitted) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const taskId = decodeURIComponent(taskControlMatch[1]);
    const task = FAKE_TASKS.find((t) => t.task_id === taskId);
    if (!task) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    const expected = await readExpectedVersion(req, res);
    if (!expected.ok) {
      return;
    }
    RECORDED_MUTATIONS.push({
      action,
      method: "POST",
      objectId: taskId,
      objectType: "task",
      versionMatches: expected.version === task.updated_at,
    });
    if (expected.version !== null && expected.version !== task.updated_at) {
      sendJson(res, 409, {
        error: { code: "lifecycle_conflict" },
      });
      return;
    }
    if (action === "resume") {
      sendJson(res, 409, { error: { code: "lifecycle_conflict" } });
      return;
    }
    if (action === "pause") {
      if (task.status !== "running" || task.pause_requested === true) {
        sendJson(res, 409, { error: { code: "lifecycle_conflict" } });
        return;
      }
      task.pause_requested = true;
      task.updated_at = bumpTimestamp(task.updated_at);
      sendJson(res, 200, {
        action,
        taskId: task.task_id,
        task,
        lifecycle: taskLifecycle(task, []),
        durableOutcome:
          "a durable pause request is stored; the Task becomes paused only at a supported item boundary",
        sideEffects: "none",
        retrySafe: false,
        nextAction:
          "refresh the Task to see whether the pause was acknowledged at an item boundary",
      });
      return;
    }
    if (!CANCELLABLE_TASK_STATUSES.has(task.status)) {
      sendJson(res, 409, { error: { code: "lifecycle_conflict" } });
      return;
    }
    task.status = "cancelled";
    task.completed_at = bumpTimestamp(task.updated_at);
    task.updated_at = task.completed_at;
    sendJson(res, 200, {
      action,
      taskId: task.task_id,
      task,
      lifecycle: taskLifecycle(task, []),
      durableOutcome:
        "the Task and its non-terminal items are durably marked cancelled; no further item is admitted, an item that is already in flight is not interrupted and records its own outcome, and its source lock is released only when that outcome is recorded",
      sideEffects: "none",
      retrySafe: false,
      nextAction:
        "refresh the Task to read the durable cancelled state and the independent item outcomes",
    });
    return;
  }

  if (url.pathname === "/api/v1/jobs" && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const rawStatus = url.searchParams.get("status");
    const status =
      rawStatus === null || rawStatus === "" || rawStatus === "all"
        ? null
        : rawStatus;
    if (status !== null && !KNOWN_JOB_STATUSES.has(status)) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const rawCommand = url.searchParams.get("command");
    const command =
      rawCommand === null || rawCommand === "" || rawCommand === "all"
        ? null
        : rawCommand;
    if (command !== null && !KNOWN_JOB_COMMANDS.has(command)) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const rawLimit = url.searchParams.get("limit");
    const limit = rawLimit === null ? 20 : Number(rawLimit);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const scope = taskScope(status, command);
    const rawCursor = url.searchParams.get("cursor");
    let offset = null;
    if (rawCursor !== null) {
      offset = decodeCollectionCursor(rawCursor, "jobs", scope);
      if (offset === null) {
        sendJson(res, 400, { error: { code: "invalid_request" } });
        return;
      }
    }
    let items = [...FAKE_JOBS].sort((left, right) =>
      left.created_at === right.created_at
        ? right.job_id.localeCompare(left.job_id)
        : right.created_at.localeCompare(left.created_at),
    );
    if (status !== null) {
      items = items.filter((job) => job.status === status);
    }
    if (command !== null) {
      items = items.filter((job) => job.command === command);
    }
    const page = collectionPage(items, limit, offset);
    sendJson(res, 200, {
      items: page.page.map((job) => jobDocument(job)),
      limit,
      status,
      command,
      truncated: page.next !== null,
      previous_cursor:
        page.previous === null
          ? null
          : encodeCollectionCursor("jobs", scope, page.previous),
      next_cursor:
        page.next === null
          ? null
          : encodeCollectionCursor("jobs", scope, page.next),
    });
    return;
  }

  const jobDetailMatch = url.pathname.match(/^\/api\/v1\/jobs\/([^/]+)$/);
  if (jobDetailMatch && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const jobId = decodeURIComponent(jobDetailMatch[1]);
    const job = FAKE_JOBS.find((j) => j.job_id === jobId);
    if (!job) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    sendJson(res, 200, jobDocument(job));
    return;
  }

  const jobCancelMatch = url.pathname.match(
    /^\/api\/v1\/jobs\/([^/]+)\/cancel$/,
  );
  if (jobCancelMatch && req.method === "POST") {
    if (!operationsGuard(res)) {
      return;
    }
    if (!operationsPrincipal.permitted) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const jobId = decodeURIComponent(jobCancelMatch[1]);
    const job = FAKE_JOBS.find((j) => j.job_id === jobId);
    if (!job) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    const expected = await readExpectedVersion(req, res);
    if (!expected.ok) {
      return;
    }
    RECORDED_MUTATIONS.push({
      action: "cancel",
      method: "POST",
      objectId: jobId,
      objectType: "job",
      versionMatches: expected.version === job.updated_at,
    });
    if (expected.version !== null && expected.version !== job.updated_at) {
      sendJson(res, 409, { error: { code: "lifecycle_conflict" } });
      return;
    }
    if (job.status !== "pending" && job.status !== "running") {
      sendJson(res, 409, { error: { code: "lifecycle_conflict" } });
      return;
    }
    job.cancellation_requested = true;
    if (job.status === "pending") {
      job.status = "cancelled";
      job.completed_at = bumpTimestamp(job.updated_at);
      job.updated_at = job.completed_at;
    } else {
      job.updated_at = bumpTimestamp(job.updated_at);
    }
    sendJson(res, 200, jobDocument(job));
    return;
  }

  if (url.pathname === "/api/v1/workers/readiness" && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    sendJson(res, 200, {
      ready: true,
      condition: "ready",
      category: null,
      durableState: "resident processing worker is live and ready",
      sideEffects: "none",
      retrySafe: true,
      nextAction: "none",
      activeWorkersCount: 1,
      activeSnapshotId: "snap-1",
      expectedRuntimeSchemaVersion: 33,
    });
    return;
  }

  if (url.pathname === "/api/v1/workers" && req.method === "GET") {
    if (!operationsGuard(res)) {
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
          heartbeat_interval_seconds: 5,
          supported_commands: ["scan", "preview", "organize"],
          configuration_snapshot_id: "snap-1",
          runtime_schema_version: 33,
        },
      ],
      count: 1,
    });
    return;
  }

  // --- V2 manual Organize bounded routes ---
  if (url.pathname === "/api/v1/organize/intents" && req.method === "POST") {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const fields = parsed.document;
    const scopeKind = fields.scopeKind ?? null;
    const resourceLibraryId = fields.resourceLibraryId ?? null;
    if (
      (scopeKind !== "file" && scopeKind !== "resourceLibrary") ||
      typeof resourceLibraryId !== "string"
    ) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    recordManualRequestForSession({
      body: {
        fileId: fields.fileId,
        itemIds: Array.isArray(fields.itemIds) ? [...fields.itemIds] : null,
        resourceLibraryId,
        scopeKind,
      },
      method: "POST",
      objectId: ORGANIZE_INTENT_ID,
      objectType: "organize_intent",
      path: "/api/v1/organize/intents",
    });
    state.intentVersion = 1;
    state.itemVersion = 1;
    sendJson(res, 201, organizeIntentDocument(state));
    return;
  }

  if (
    url.pathname === `/api/v1/organize/intents/${ORGANIZE_INTENT_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: ORGANIZE_INTENT_ID,
      objectType: "organize_intent",
      path: "/api/v1/organize/intents/:intentId",
    });
    sendJson(res, 200, organizeIntentDocument(state));
    return;
  }

  if (
    url.pathname ===
      `/api/v1/organize/intents/${ORGANIZE_INTENT_ID}/items/${ORGANIZE_ITEM_ID}/choice` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const fields = parsed.document;
    recordManualRequestForSession({
      body: {
        expectedItemVersion: fields.expectedItemVersion,
        expectedVersion: fields.expectedVersion,
        recognitionTypeId: fields.recognitionTypeId,
      },
      method: "POST",
      objectId: ORGANIZE_ITEM_ID,
      objectType: "organize_choice",
      path: "/api/v1/organize/intents/:intentId/items/:itemId/choice",
    });
    if (
      fields.expectedVersion !== state.intentVersion ||
      fields.expectedItemVersion !== state.itemVersion
    ) {
      sendJson(res, 409, {
        error: {
          code: "manual_intent_conflict",
          message: "manual intent version is stale; no choice was changed",
        },
      });
      return;
    }
    state.intentVersion += 1;
    state.itemVersion += 1;
    sendJson(res, 200, organizeIntentDocument(state));
    return;
  }

  if (
    url.pathname ===
      `/api/v1/organize/intents/${ORGANIZE_INTENT_ID}/previews` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    recordManualRequestForSession({
      body: { expectedVersion: parsed.document.expectedVersion },
      method: "POST",
      objectId: ORGANIZE_INTENT_ID,
      objectType: "organize_preview",
      path: "/api/v1/organize/intents/:intentId/previews",
    });
    if (parsed.document.expectedVersion !== state.intentVersion) {
      sendJson(res, 409, {
        error: {
          code: "manual_intent_conflict",
          message: "manual intent version is stale; no Preview was created",
        },
      });
      return;
    }
    sendJson(res, 201, organizePreviewDocument(state));
    return;
  }

  if (
    url.pathname === `/api/v1/organize/previews/${ORGANIZE_PREVIEW_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: ORGANIZE_PREVIEW_ID,
      objectType: "organize_preview",
      path: "/api/v1/organize/previews/:previewId",
    });
    sendJson(res, 200, organizePreviewDocument(state));
    return;
  }

  if (
    url.pathname ===
      `/api/v1/organize/previews/${ORGANIZE_DESTRUCTIVE_PREVIEW_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: ORGANIZE_DESTRUCTIVE_PREVIEW_ID,
      objectType: "organize_preview",
      path: "/api/v1/organize/previews/:previewId",
    });
    sendJson(res, 200, organizeDestructivePreviewDocument(state));
    return;
  }

  // A deliberately malformed bounded document: it mirrors the real contract's
  // shape but carries an unmodelled action transport and an unknown item
  // status, so the built artifact must render no Execute control and no
  // hostile value anywhere in the DOM.
  if (
    url.pathname ===
      `/api/v1/organize/previews/${ORGANIZE_HOSTILE_PREVIEW_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: ORGANIZE_HOSTILE_PREVIEW_ID,
      objectType: "organize_preview",
      path: "/api/v1/organize/previews/:previewId",
    });
    const hostile = organizePreviewDocument(state);
    hostile["previewId"] = ORGANIZE_HOSTILE_PREVIEW_ID;
    hostile["actions"]["execute"]["available"] = true;
    hostile["actions"]["execute"]["reason"] = null;
    hostile["actions"]["execute"]["method"] = "DELETE";
    hostile["actions"]["execute"]["path"] = "https://attacker.example/execute";
    hostile["items"][0]["status"] = "hacked";
    sendJson(res, 200, hostile);
    return;
  }

  // A contract-shaped document whose Execute action names a *safe* method and
  // a route belonging to another Preview. Both are malformed transports, so
  // the built artifact must render no Execute control and submit nothing.
  if (
    url.pathname ===
      `/api/v1/organize/previews/${ORGANIZE_MISBOUND_PREVIEW_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: ORGANIZE_MISBOUND_PREVIEW_ID,
      objectType: "organize_preview",
      path: "/api/v1/organize/previews/:previewId",
    });
    const misbound = organizePreviewDocument(state);
    misbound["previewId"] = ORGANIZE_MISBOUND_PREVIEW_ID;
    misbound["actions"]["execute"]["available"] = true;
    misbound["actions"]["execute"]["reason"] = null;
    misbound["actions"]["execute"]["method"] = "GET";
    misbound["actions"]["execute"]["requiresConfirmation"] = true;
    misbound["actions"]["execute"]["path"] =
      `/api/v1/organize/previews/another-preview/execute`;
    sendJson(res, 200, misbound);
    return;
  }

  // A contract-shaped document whose Execute action carries the mutating POST
  // method and the Preview's own *read* route — the same path, without the
  // exact `/execute` suffix. The route is not this action's transport, so the
  // built artifact must fail closed instead of rendering the Execute control.
  if (
    url.pathname ===
      `/api/v1/organize/previews/${ORGANIZE_SUFFIX_PREVIEW_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: ORGANIZE_SUFFIX_PREVIEW_ID,
      objectType: "organize_preview",
      path: "/api/v1/organize/previews/:previewId",
    });
    const suffix = organizePreviewDocument(state);
    suffix["previewId"] = ORGANIZE_SUFFIX_PREVIEW_ID;
    suffix["actions"]["execute"]["available"] = true;
    suffix["actions"]["execute"]["reason"] = null;
    suffix["actions"]["execute"]["path"] =
      `/api/v1/operations/organize/previews/${ORGANIZE_SUFFIX_PREVIEW_ID}`;
    sendJson(res, 200, suffix);
    return;
  }

  const organizeExecuteMatch = url.pathname.match(
    /^\/api\/v1\/organize\/previews\/([^/]+)\/execute$/,
  );
  if (
    organizeExecuteMatch &&
    [ORGANIZE_PREVIEW_ID, ORGANIZE_DESTRUCTIVE_PREVIEW_ID].includes(
      organizeExecuteMatch[1],
    ) &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    const executePreviewId = organizeExecuteMatch[1];
    const destructive = executePreviewId === ORGANIZE_DESTRUCTIVE_PREVIEW_ID;
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const fields = parsed.document;
    recordManualRequestForSession({
      body: {
        confirmation: fields.confirmation === true,
        expectedIntentVersion: fields.expectedIntentVersion,
        itemIds: Array.isArray(fields.itemIds) ? [...fields.itemIds] : null,
        allowOverwrite: fields.allowOverwrite === true,
        allowSourceCleanup: fields.allowSourceCleanup === true,
      },
      method: "POST",
      objectId: executePreviewId,
      objectType: "organize_execute",
      path: "/api/v1/organize/previews/:previewId/execute",
    });
    if (
      fields.confirmation !== true ||
      !Array.isArray(fields.itemIds) ||
      fields.itemIds.length !== 1 ||
      fields.itemIds[0] !== ORGANIZE_ITEM_ID ||
      fields.expectedIntentVersion !== state.intentVersion ||
      typeof fields.allowOverwrite !== "boolean" ||
      typeof fields.allowSourceCleanup !== "boolean" ||
      fields.allowOverwrite !== destructive ||
      fields.allowSourceCleanup !== destructive
    ) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    // One repeated submission resolves to the same durable execution.
    const first = state.executed === false;
    state.executed = true;
    sendJson(
      res,
      first ? 202 : 200,
      organizeExecutionDocument(first ? "admitted" : "completed", state),
    );
    return;
  }

  if (
    url.pathname === `/api/v1/organize/executions/${ORGANIZE_EXECUTION_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = organizeState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: ORGANIZE_EXECUTION_ID,
      objectType: "organize_execution",
      path: "/api/v1/organize/executions/:executionId",
    });
    sendJson(
      res,
      200,
      organizeExecutionDocument(
        state.executed ? "completed" : "admitted",
        state,
      ),
    );
    return;
  }

  // The durable failed outcome of a real terminal execution: per-item bounded
  // evidence plus the recovery handoff the backend offers without transport.
  if (
    url.pathname ===
      `/api/v1/organize/executions/${ORGANIZE_FAILED_EXECUTION_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    recordManualRequestForSession({
      method: "GET",
      objectId: ORGANIZE_FAILED_EXECUTION_ID,
      objectType: "organize_execution",
      path: "/api/v1/organize/executions/:executionId",
    });
    sendJson(res, 200, organizeFailedExecutionDocument());
    return;
  }

  // --- Manual Scan / Preview bounded routes ---
  //
  // These mirror the authoritative Python contract: one bounded action matrix
  // for the exact principal and scope, a bounded Scan admission with
  // deterministic durable state, cooperative cancellation, and a zero-mutation
  // Preview. Only bounded, secret-free request metadata is recorded for the
  // built-artifact browser proof. The optional `scope` request field and the
  // Preview `snapshotId`/`snapshotDigest` fields are accepted but never change
  // the bounded scope this fake binds from the explicit identifiers, and no
  // digest value is ever echoed back into a response document.

  // --- Automation operator projections (read) and existing-route mutations ---
  if (
    url.pathname === "/api/v1/automation/task-definitions" &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = automationState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: null,
      objectType: "automation_definitions",
      path: "/api/v1/automation/task-definitions",
      body: null,
    });
    sendJson(res, 200, automationListDocument(state, token));
    return;
  }
  if (
    url.pathname === "/api/v1/automation/task-definitions" &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const state = automationState(session);
    if (!state.draftCreated) {
      sendJson(res, 409, { error: { code: "configuration_conflict" } });
      return;
    }
    const object = parsed.document.object ?? {};
    const created = {
      id:
        typeof object.id === "string" && object.id
          ? object.id
          : "automation-def-e2e-created",
      name:
        typeof object.name === "string" && object.name
          ? object.name
          : "Created automation",
      enabled: object.enabled === true,
      resourceLibraryId:
        typeof object.resourceLibraryId === "string" && object.resourceLibraryId
          ? object.resourceLibraryId
          : "source",
      mode: typeof object.mode === "string" ? object.mode : "scan-only",
      itemLimit: typeof object.itemLimit === "number" ? object.itemLimit : 100,
      intervalSeconds:
        typeof object.intervalSeconds === "number"
          ? object.intervalSeconds
          : null,
      cron: typeof object.cron === "string" ? object.cron : null,
      timezone: typeof object.timezone === "string" ? object.timezone : null,
    };
    state.createdDefinition = created;
    recordManualRequestForSession({
      method: "POST",
      objectId: AUTOMATION_DRAFT_REVISION,
      objectType: "automation_definition_create",
      path: "/api/v1/automation/task-definitions",
      body: boundedAutomationBody(parsed.document),
    });
    sendJson(res, 200, {
      revisionId: AUTOMATION_DRAFT_REVISION,
      version: state.draftVersion,
      status: "draft",
      revisionSequence: 3,
      schemaVersion: 1,
      digest: "stored",
      createdAt: MANUAL_RECORDED_AT,
      updatedAt: MANUAL_RECORDED_AT,
      validatedAt: null,
      activatedAt: null,
      validationErrors: [],
      configurationRevisionId: AUTOMATION_DRAFT_REVISION,
      automationTaskDefinition: created,
    });
    return;
  }
  const automationDefinitionMatch = url.pathname.match(
    /^\/api\/v1\/automation\/task-definitions\/([^/]+)$/,
  );
  if (automationDefinitionMatch && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const state = automationState(session);
    const requestedId = decodeURIComponent(automationDefinitionMatch[1]);
    const createdOrCopied = [
      state.createdDefinition,
      state.copiedDefinition,
    ].find((definition) => definition && definition.id === requestedId);
    if (createdOrCopied) {
      recordManualRequestForSession({
        method: "GET",
        objectId: requestedId,
        objectType: "automation_definition",
        path: "/api/v1/automation/task-definitions/:definitionId",
        body: null,
      });
      sendJson(res, 200, {
        definition: automationDraftOnlyDefinitionDocument(
          state,
          token,
          createdOrCopied,
        ),
      });
      return;
    }
    if (requestedId !== AUTOMATION_DEFINITION_ID) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    recordManualRequestForSession({
      method: "GET",
      objectId: AUTOMATION_DEFINITION_ID,
      objectType: "automation_definition",
      path: "/api/v1/automation/task-definitions/:definitionId",
      body: null,
    });
    sendJson(res, 200, {
      definition: automationDefinitionDocument(state, token),
    });
    return;
  }
  const automationDraftMatch = url.pathname.match(
    /^\/api\/v1\/automation\/task-definitions\/([^/]+)\/draft$/,
  );
  if (automationDraftMatch && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const state = automationState(session);
    const requestedId = decodeURIComponent(automationDraftMatch[1]);
    const createdOrCopied = [
      state.createdDefinition,
      state.copiedDefinition,
    ].find((definition) => definition && definition.id === requestedId);
    if (requestedId !== AUTOMATION_DEFINITION_ID && !createdOrCopied) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    recordManualRequestForSession({
      method: "GET",
      objectId: requestedId,
      objectType: "automation_draft",
      path: "/api/v1/automation/task-definitions/:definitionId/draft",
      body: null,
    });
    sendJson(res, 200, automationDraftDocument(state, token, createdOrCopied));
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/occurrences` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = automationState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: AUTOMATION_DEFINITION_ID,
      objectType: "automation_occurrences",
      path: "/api/v1/automation/task-definitions/:definitionId/occurrences",
      body: null,
    });
    sendJson(res, 200, {
      definitionId: AUTOMATION_DEFINITION_ID,
      activeConfiguration: {
        revisionId: state.activated
          ? AUTOMATION_DRAFT_REVISION
          : AUTOMATION_ACTIVE_REVISION,
        version: state.activated ? 4 : 3,
        revisionSequence: state.activated ? 3 : 2,
        status: "active",
      },
      items: [automationOccurrenceDocument()],
      limit: 20,
      truncated: false,
      next_cursor: null,
      previous_cursor: null,
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/previews/${AUTOMATION_HOSTILE_PREVIEW_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    // The hostile fixture advertises a grant transport whose identity segment
    // is not URI-safe, so the frontend must render the bounded malformed
    // state and never a control.
    const state = automationState(session);
    const document = automationPreviewDocument(
      state,
      token,
      AUTOMATION_HOSTILE_PREVIEW_ID,
    );
    document.actions.grant = automationAction({
      path: "/api/v1/automation/task-definitions/<task>/grant",
      requiresConfirmation: true,
      durableOutcome:
        "a persistent scoped unattended execution grant is stored",
      nextAction: "review the grant eligibility",
    });
    sendJson(res, 200, document);
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/previews/${AUTOMATION_MISBOUND_PREVIEW_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    sendJson(res, 404, { error: { code: "not_found" } });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/previews/${AUTOMATION_PREVIEW_ID}` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = automationState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: AUTOMATION_PREVIEW_ID,
      objectType: "automation_preview",
      path: "/api/v1/automation/task-definitions/:definitionId/previews/:previewId",
      body: null,
    });
    sendJson(
      res,
      200,
      automationPreviewDocument(state, token, AUTOMATION_PREVIEW_ID),
    );
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/previews/${AUTOMATION_PREVIEW_ID}/items` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = automationState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: AUTOMATION_PREVIEW_ID,
      objectType: "automation_preview_items",
      path: "/api/v1/automation/task-definitions/:definitionId/previews/:previewId/items",
      body: null,
    });
    const items =
      state.previewCreated && !state.previewStale
        ? [automationPreviewItem()]
        : [];
    sendJson(res, 200, {
      previewId: AUTOMATION_PREVIEW_ID,
      items,
      total: items.length,
      nextAfter: null,
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/preview` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const state = automationState(session);
    state.previewCreated = true;
    state.previewStale = false;
    recordManualRequestForSession({
      method: "POST",
      objectId: AUTOMATION_DEFINITION_ID,
      objectType: "automation_preview_create",
      path: "/api/v1/automation/task-definitions/:definitionId/preview",
      body: {},
    });
    sendJson(res, 201, {
      previewId: AUTOMATION_PREVIEW_ID,
      definitionId: AUTOMATION_DEFINITION_ID,
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/grant` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const fields = parsed.document;
    const state = automationState(session);
    if (fields.confirmation !== true) {
      sendJson(res, 400, {
        error: { code: "unattended_execution_grant_invalid" },
      });
      return;
    }
    if (
      fields.previewId !== AUTOMATION_PREVIEW_ID ||
      !state.previewCreated ||
      state.previewStale
    ) {
      sendJson(res, 409, {
        error: { code: "unattended_execution_preview_required" },
      });
      return;
    }
    state.granted = true;
    recordManualRequestForSession({
      method: "POST",
      objectId: AUTOMATION_DEFINITION_ID,
      objectType: "automation_grant",
      path: "/api/v1/automation/task-definitions/:definitionId/grant",
      body: boundedAutomationBody(fields),
    });
    sendJson(res, 201, {
      grant: {
        status: "active",
        active: true,
        grantId: AUTOMATION_GRANT_ID,
        definitionId: AUTOMATION_DEFINITION_ID,
        definitionChangedSinceGrant: false,
        nextAction:
          "inspect the next occurrence or revoke this grant before changing its exact bounds",
        maxItemsPerRun: 12,
        previewId: AUTOMATION_PREVIEW_ID,
        grantingPrincipal: "e2e-operator",
        grantedAt: MANUAL_RECORDED_AT,
        revokedAt: null,
        reason: null,
        currentPermission: {
          principalId: "e2e-operator",
          status: "valid",
          allowed: true,
        },
      },
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/revoke` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const state = automationState(session);
    state.granted = false;
    recordManualRequestForSession({
      method: "POST",
      objectId: AUTOMATION_DEFINITION_ID,
      objectType: "automation_revoke",
      path: "/api/v1/automation/task-definitions/:definitionId/revoke",
      body: boundedAutomationBody(parsed.document),
    });
    sendJson(res, 200, {
      grant: {
        status: "revoked",
        active: false,
        grantId: AUTOMATION_GRANT_ID,
        definitionId: AUTOMATION_DEFINITION_ID,
        definitionChangedSinceGrant: false,
        nextAction:
          "review the exact definition bounds and explicitly grant unattended execution again",
        maxItemsPerRun: 12,
        previewId: AUTOMATION_PREVIEW_ID,
        grantingPrincipal: "e2e-operator",
        grantedAt: MANUAL_RECORDED_AT,
        revokedAt: MANUAL_RECORDED_AT,
        reason: null,
        currentPermission: {
          principalId: "e2e-operator",
          status: "valid",
          allowed: true,
        },
      },
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/copy` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const state = automationState(session);
    if (!state.draftCreated) {
      sendJson(res, 409, { error: { code: "configuration_conflict" } });
      return;
    }
    recordManualRequestForSession({
      method: "POST",
      objectId: AUTOMATION_DEFINITION_ID,
      objectType: "automation_copy",
      path: "/api/v1/automation/task-definitions/:definitionId/copy",
      body: boundedAutomationBody(parsed.document),
    });
    const copied = {
      id: "automation-def-e2e-copy",
      name: "Nightly automation copy",
      enabled: true,
      resourceLibraryId: "source",
      mode: "automatic-organization",
      itemLimit: 12,
      intervalSeconds: 3600,
      cron: null,
      timezone: null,
    };
    state.copiedDefinition = copied;
    sendJson(res, 200, {
      revisionId: AUTOMATION_DRAFT_REVISION,
      version: state.draftVersion,
      automationTaskDefinition: copied,
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/automation/task-definitions/${AUTOMATION_DEFINITION_ID}/activate-draft` &&
    req.method === "POST"
  ) {
    // The real backend serves the checked activation only on the dedicated
    // /api/v1/operations/automation route; mirror that 404 exactly.
    sendJson(res, 404, { error: { code: "not_found" } });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/configuration/revisions/${AUTOMATION_ACTIVE_REVISION}/successor` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    await readBoundedJsonBody(req, res);
    const state = automationState(session);
    state.draftCreated = true;
    state.draftVersion = 2;
    state.draftStatus = "draft";
    recordManualRequestForSession({
      method: "POST",
      objectId: AUTOMATION_ACTIVE_REVISION,
      objectType: "automation_successor_draft",
      path: "/api/v1/configuration/revisions/:revisionId/successor",
      body: {},
    });
    sendJson(res, 201, {
      revisionId: AUTOMATION_DRAFT_REVISION,
      version: 2,
      status: "draft",
      revisionSequence: 3,
      schemaVersion: 1,
      createdAt: MANUAL_RECORDED_AT,
      updatedAt: MANUAL_RECORDED_AT,
      validatedAt: null,
      activatedAt: null,
      validationErrors: [],
      created: true,
      nextAction:
        "open the successor Draft, edit configuration objects, validate, and activate",
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/configuration/revisions/${AUTOMATION_DRAFT_REVISION}/validate` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    await readBoundedJsonBody(req, res);
    const state = automationState(session);
    state.draftStatus = "validated";
    recordManualRequestForSession({
      method: "POST",
      objectId: AUTOMATION_DRAFT_REVISION,
      objectType: "automation_draft_validate",
      path: "/api/v1/configuration/revisions/:revisionId/validate",
      body: {},
    });
    sendJson(res, 200, {
      revisionId: AUTOMATION_DRAFT_REVISION,
      version: state.draftVersion,
      status: "validated",
      validationErrors: [],
    });
    return;
  }
  const automationSaveMatch = url.pathname.match(
    /^\/api\/v1\/configuration\/revisions\/([^/]+)\/objects\/automationTaskDefinitions\/([^/]+)$/,
  );
  if (
    automationSaveMatch &&
    automationSaveMatch[1] === AUTOMATION_DRAFT_REVISION &&
    req.method === "PUT"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const fields = parsed.document;
    const state = automationState(session);
    const savedId = decodeURIComponent(automationSaveMatch[2]);
    if (!state.draftCreated || fields.expectedVersion !== state.draftVersion) {
      sendJson(res, 409, { error: { code: "configuration_version_conflict" } });
      return;
    }
    state.draftVersion += 1;
    state.draftStatus = "draft";
    recordManualRequestForSession({
      method: "PUT",
      objectId: savedId,
      objectType: "automation_draft_save",
      path: "/api/v1/configuration/revisions/:revisionId/objects/automationTaskDefinitions/:definitionId",
      body: boundedAutomationBody(fields),
    });
    sendJson(res, 200, {
      revisionId: AUTOMATION_DRAFT_REVISION,
      version: state.draftVersion,
      automationTaskDefinition: { id: savedId },
    });
    return;
  }
  // --- End Automation operator projections ---

  if (url.pathname === "/api/v1/manual-actions" && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const query = readBoundedQuery(url, [
      "scopeKind",
      "scope",
      "fileId",
      "resourceLibraryId",
    ]);
    if (query === null) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const scopeKind = query.scopeKind ?? null;
    if (
      scopeKind !== null &&
      scopeKind !== "file" &&
      scopeKind !== "resourceLibrary"
    ) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const fileId = query.fileId ?? null;
    const resourceLibraryId = query.resourceLibraryId ?? null;
    if (
      scopeKind === "file" &&
      (fileId === null || resourceLibraryId === null)
    ) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    recordManualRequestForSession({
      body: { fileId, resourceLibraryId, scopeKind },
      method: "GET",
      objectId: fileId ?? resourceLibraryId,
      objectType: "manual_action_matrix",
      path: "/api/v1/manual-actions",
    });
    const matrix = manualActionMatrixDocument(
      { fileId, resourceLibraryId, scopeKind },
      operationsPrincipal.permitted,
    );
    // Deliberately hostile fixture for the browser boundary proof. The
    // frontend must reject this source before any credential-shaped value,
    // absolute path or digest can be rendered; the fake never records it as
    // request evidence.
    if (fileId === "hostile-source") {
      matrix.source = {
        digest: "a".repeat(64),
        extension: "mkv",
        fileId: "file-1",
        filename: "Bearer hidden-token.mkv",
        occurrenceState: "verified",
        path: "/private/media/Bearer hidden-token.mkv",
        resourceLibraryId: MANUAL_LIBRARY_ID,
        scanStatus: "ready",
        sizeBytes: 12,
        storageId: MANUAL_STORAGE_ID,
      };
    }
    sendJson(res, 200, matrix);
    return;
  }

  if (url.pathname === "/api/v1/scans" && req.method === "POST") {
    if (!operationsGuard(res)) {
      return;
    }
    if (!operationsPrincipal.permitted) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const body = await readBoundedJsonBody(req, res);
    if (!body.ok) {
      return;
    }
    const fields = boundedManualRequestFields(body.document, [
      "scopeKind",
      "scope",
      "fileId",
      "resourceLibraryId",
      "mode",
    ]);
    if (fields === null) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const scopeKind = fields.scopeKind;
    const mode = fields.mode;
    const fileId = fields.fileId ?? null;
    const resourceLibraryId = fields.resourceLibraryId ?? null;
    if (
      (scopeKind !== "file" && scopeKind !== "resourceLibrary") ||
      (mode !== "full" && mode !== "incremental") ||
      (scopeKind === "resourceLibrary" && fileId !== null) ||
      (scopeKind === "file" &&
        (fileId === null || resourceLibraryId === null)) ||
      (scopeKind === "resourceLibrary" && resourceLibraryId === null)
    ) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    if (
      scopeKind === "file" &&
      (fileId !== MANUAL_FILE_SCOPE.fileId ||
        resourceLibraryId !== MANUAL_FILE_SCOPE.resourceLibraryId)
    ) {
      recordManualRequestForSession({
        body: { fileId, mode, resourceLibraryId, scopeKind },
        method: "POST",
        objectId: fileId,
        objectType: "scan",
        path: "/api/v1/scans",
      });
      sendJson(res, 409, {
        details: { fileId, resourceLibraryId, scopeKind },
        error: {
          code: "source_not_found",
          message: MANUAL_UNKNOWN_SOURCE_REASON,
        },
      });
      return;
    }
    if (
      scopeKind === "resourceLibrary" &&
      resourceLibraryId !== MANUAL_LIBRARY_ID
    ) {
      recordManualRequestForSession({
        body: { mode, resourceLibraryId, scopeKind },
        method: "POST",
        objectId: resourceLibraryId,
        objectType: "scan",
        path: "/api/v1/scans",
      });
      sendJson(res, 409, {
        details: { resourceLibraryId, scopeKind },
        error: {
          code: "resource_library_not_found",
          message: MANUAL_UNKNOWN_LIBRARY_REASON,
        },
      });
      return;
    }
    const record = manualScanRunningRecord({
      fileId,
      mode,
      resourceLibraryId,
      scopeKind,
    });
    MANUAL_SCANS.set(record.taskId, record);
    recordManualRequestForSession({
      body: { fileId, mode, resourceLibraryId, scopeKind },
      method: "POST",
      objectId: record.taskId,
      objectType: "scan",
      path: "/api/v1/scans",
    });
    sendJson(
      res,
      202,
      manualScanAdmissionDocument(record, operationsPrincipal.permitted),
    );
    return;
  }

  const manualScanCancelMatch = url.pathname.match(
    /^\/api\/v1\/scans\/([^/]+)\/cancel$/,
  );
  if (manualScanCancelMatch && req.method === "POST") {
    if (!operationsGuard(res)) {
      return;
    }
    if (!operationsPrincipal.permitted) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const taskId = decodeURIComponent(manualScanCancelMatch[1]);
    const record = MANUAL_SCANS.get(taskId);
    if (record === undefined) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    recordManualRequestForSession({
      method: "POST",
      objectId: taskId,
      objectType: "scan",
      path: `/api/v1/scans/${taskId}/cancel`,
    });
    if (
      MANUAL_TERMINAL_SCAN_STATUSES.has(record.status) ||
      record.cancellationRequested === true
    ) {
      sendJson(res, 409, { error: { code: "lifecycle_conflict" } });
      return;
    }
    record.status = "cancelled";
    record.cancellationRequested = true;
    record.updatedAt = bumpTimestamp(record.updatedAt);
    sendJson(
      res,
      200,
      manualScanDocument(
        record,
        manualScanPage(record, null, null),
        operationsPrincipal.permitted,
      ),
    );
    return;
  }

  const manualScanDetailMatch = url.pathname.match(
    /^\/api\/v1\/scans\/([^/]+)$/,
  );
  if (manualScanDetailMatch && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const taskId = decodeURIComponent(manualScanDetailMatch[1]);
    const query = readBoundedQuery(url, ["itemLimit", "itemCursor"]);
    if (query === null) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const parsedLimit = parseBoundedItemLimit(query.itemLimit);
    if (!parsedLimit.ok) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const record = MANUAL_SCANS.get(taskId);
    if (record === undefined) {
      recordManualRequestForSession({
        method: "GET",
        objectId: taskId,
        objectType: "scan",
        path: `/api/v1/scans/${taskId}`,
      });
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    const page = manualScanPage(
      record,
      parsedLimit.itemLimit,
      query.itemCursor ?? null,
    );
    if (page === null) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    recordManualRequestForSession({
      body: { itemCursor: query.itemCursor, itemLimit: parsedLimit.itemLimit },
      method: "GET",
      objectId: taskId,
      objectType: "scan",
      path: `/api/v1/scans/${taskId}`,
    });
    sendJson(
      res,
      200,
      manualScanDocument(record, page, operationsPrincipal.permitted),
    );
    return;
  }

  if (url.pathname === "/api/v1/previews" && req.method === "POST") {
    if (!operationsGuard(res)) {
      return;
    }
    if (!operationsPrincipal.permitted) {
      sendJson(res, 403, { error: { code: "forbidden" } });
      return;
    }
    const body = await readBoundedJsonBody(req, res);
    if (!body.ok) {
      return;
    }
    const fields = boundedManualRequestFields(body.document, [
      "scopeKind",
      "scope",
      "fileId",
      "resourceLibraryId",
      "snapshotId",
      "snapshotDigest",
    ]);
    if (fields === null) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const scopeKind = fields.scopeKind;
    const fileId = fields.fileId ?? null;
    const resourceLibraryId = fields.resourceLibraryId ?? null;
    if (
      (scopeKind !== "file" && scopeKind !== "resourceLibrary") ||
      (scopeKind === "resourceLibrary" && fileId !== null) ||
      (scopeKind === "file" &&
        (fileId === null || resourceLibraryId === null)) ||
      (scopeKind === "resourceLibrary" && resourceLibraryId === null)
    ) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    if (
      scopeKind === "file" &&
      (fileId !== MANUAL_FILE_SCOPE.fileId ||
        resourceLibraryId !== MANUAL_FILE_SCOPE.resourceLibraryId)
    ) {
      recordManualRequestForSession({
        body: { fileId, resourceLibraryId, scopeKind },
        method: "POST",
        objectId: fileId,
        objectType: "preview",
        path: "/api/v1/previews",
      });
      sendJson(res, 409, {
        details: { fileId, resourceLibraryId, scopeKind },
        error: {
          code: "source_not_found",
          message: MANUAL_UNKNOWN_SOURCE_REASON,
        },
      });
      return;
    }
    if (
      scopeKind === "resourceLibrary" &&
      resourceLibraryId !== MANUAL_LIBRARY_ID
    ) {
      recordManualRequestForSession({
        body: { resourceLibraryId, scopeKind },
        method: "POST",
        objectId: resourceLibraryId,
        objectType: "preview",
        path: "/api/v1/previews",
      });
      sendJson(res, 409, {
        details: { resourceLibraryId, scopeKind },
        error: {
          code: "resource_library_not_found",
          message: MANUAL_UNKNOWN_LIBRARY_REASON,
        },
      });
      return;
    }
    const document = manualPreviewDocument({
      fileId,
      resourceLibraryId,
      scopeId: scopeKind === "file" ? fileId : resourceLibraryId,
      scopeKind,
    });
    // Persisting the bounded preview document is the fake's read-back state;
    // Preview itself performs no Storage or media mutation.
    MANUAL_PREVIEWS.set(document.previewId, document);
    recordManualRequestForSession({
      body: { fileId, resourceLibraryId, scopeKind },
      method: "POST",
      objectId: document.previewId,
      objectType: "preview",
      path: "/api/v1/previews",
    });
    sendJson(res, 201, document);
    return;
  }

  if (url.pathname === "/api/v1/previews" && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const query = readBoundedQuery(url, [
      "limit",
      "resourceLibraryId",
      "scopeId",
      "scopeKind",
    ]);
    if (query === null) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const parsedLimit = parseBoundedItemLimit(query.limit);
    if (!parsedLimit.ok) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    let scopeKind = query.scopeKind ?? null;
    let scopeId = query.scopeId ?? null;
    if (scopeId === null && query.resourceLibraryId !== undefined) {
      scopeKind = "resourceLibrary";
      scopeId = query.resourceLibraryId;
    }
    if (
      scopeId === null ||
      (scopeKind !== "file" && scopeKind !== "resourceLibrary")
    ) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const limit = parsedLimit.itemLimit ?? 20;
    recordManualRequestForSession({
      body: { scopeKind },
      method: "GET",
      objectId: scopeId,
      objectType: "preview_list",
      path: "/api/v1/previews",
    });
    sendJson(
      res,
      200,
      manualPreviewListDocument({ limit, scopeId, scopeKind }),
    );
    return;
  }

  const manualPreviewDetailMatch = url.pathname.match(
    /^\/api\/v1\/previews\/([^/]+)$/,
  );
  if (manualPreviewDetailMatch && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const previewId = decodeURIComponent(manualPreviewDetailMatch[1]);
    recordManualRequestForSession({
      method: "GET",
      objectId: previewId,
      objectType: "preview",
      path: `/api/v1/previews/${previewId}`,
    });
    const document = MANUAL_PREVIEWS.get(previewId);
    if (document === undefined) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    sendJson(res, 200, document);
    return;
  }

  // -------------------------------------------------------------------------
  // V2 Notification journey (bounded Webhook definitions, tests, deliveries).

  if (
    url.pathname === "/api/v1/notifications/webhooks" &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = notificationState(session);
    recordManualRequestForSession({
      method: "GET",
      objectId: null,
      objectType: "notification_definitions",
      path: "/api/v1/operations/notifications/webhooks",
      body: null,
    });
    sendJson(res, 200, notificationListDocument(state, token));
    return;
  }
  const notificationWebhookMatch = url.pathname.match(
    /^\/api\/v1\/notifications\/webhooks\/([^/]+)$/,
  );
  if (notificationWebhookMatch && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const webhookId = notificationWebhookMatch[1];
    const state = notificationState(session);
    if (
      webhookId !== NOTIFICATION_WEBHOOK_ID &&
      webhookId !== state.createdWebhook &&
      webhookId !== state.copiedWebhook
    ) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    sendJson(res, 200, notificationDetailDocument(state, token, webhookId));
    return;
  }
  if (
    url.pathname ===
      `/api/v1/notifications/webhooks/${NOTIFICATION_WEBHOOK_ID}/draft` &&
    req.method === "GET"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const state = notificationState(session);
    sendJson(res, 200, notificationDraftDocument(state, token));
    return;
  }
  if (
    url.pathname ===
      `/api/v1/notifications/webhooks/${NOTIFICATION_WEBHOOK_ID}/test` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const state = notificationState(session);
    const document = parsed.document ?? {};
    const expectedRevisionId = document.expectedRevisionId;
    const expectedVersion = document.expectedVersion;
    if (typeof expectedRevisionId !== "string" || !expectedRevisionId) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    if (!Number.isInteger(expectedVersion)) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    if (
      expectedRevisionId !== NOTIFICATION_DRAFT_REVISION &&
      expectedRevisionId !== NOTIFICATION_ACTIVE_REVISION
    ) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    const currentVersion =
      expectedRevisionId === NOTIFICATION_DRAFT_REVISION
        ? state.draftVersion
        : state.activated
          ? 5
          : 3;
    if (expectedVersion !== currentVersion) {
      sendJson(res, 409, {
        error: {
          code: "configuration_version_conflict",
          details: { durableState: "no test request was sent" },
        },
      });
      return;
    }
    state.tested += 1;
    recordManualRequestForSession({
      method: "POST",
      objectId: NOTIFICATION_WEBHOOK_ID,
      objectType: "notification_webhook_test",
      path: "/api/v1/operations/notifications/webhooks/:webhookId/test",
      body: {
        expectedRevisionId: expectedRevisionId,
        expectedVersion: expectedVersion,
      },
    });
    if (state.hostile) {
      // Wrong-object contract probe: a success document about another
      // Webhook must never render as this test's outcome.
      sendJson(res, 200, {
        testId: `webhook-test-hostile-${state.tested}`,
        webhook: {
          id: "another-webhook",
          url: "https://example.invalid/hooks/other",
          events: ["job.completed"],
          enabled: true,
          secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
        },
        revision: {
          revisionId: expectedRevisionId,
          version: currentVersion,
          status:
            expectedRevisionId === NOTIFICATION_DRAFT_REVISION
              ? state.draftStatus
              : "active",
        },
        outcome: "success",
        category: "http_204",
        responseStatus: 204,
        message: "the Webhook endpoint returned HTTP 204",
        durableState: "no_delivery_created_no_configuration_change",
        sideEffects: "none",
        retrySafe: true,
        nextAction:
          "no further action required; the endpoint accepted the signed test",
      });
      return;
    }
    sendJson(res, 200, {
      testId: `webhook-test-e2e-${state.tested}`,
      webhook: {
        id: NOTIFICATION_WEBHOOK_ID,
        url: "https://example.invalid/hooks/mediaflow",
        events: ["job.completed", "job.failed"],
        enabled: true,
        secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
      },
      revision: {
        revisionId: expectedRevisionId,
        version: currentVersion,
        status:
          expectedRevisionId === NOTIFICATION_DRAFT_REVISION
            ? state.draftStatus
            : "active",
      },
      outcome: "success",
      category: "http_204",
      responseStatus: 204,
      message: "the Webhook endpoint returned HTTP 204",
      durableState: "no_delivery_created_no_configuration_change",
      sideEffects: "none",
      retrySafe: true,
      nextAction:
        "no further action required; the endpoint accepted the signed test",
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/notifications/webhooks/${NOTIFICATION_WEBHOOK_ID}/activate-draft` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const state = notificationState(session);
    const document = parsed.document ?? {};
    if (
      document.expectedRevisionId !== NOTIFICATION_DRAFT_REVISION ||
      document.expectedVersion !== state.draftVersion
    ) {
      sendJson(res, 409, { error: { code: "configuration_version_conflict" } });
      return;
    }
    if (!state.draftCreated) {
      sendJson(res, 409, { error: { code: "notification_draft_required" } });
      return;
    }
    state.activated = true;
    recordManualRequestForSession({
      method: "POST",
      objectId: NOTIFICATION_WEBHOOK_ID,
      objectType: "notification_webhook_activation",
      path: "/api/v1/operations/notifications/webhooks/:webhookId/activate-draft",
      body: {
        expectedRevisionId: document.expectedRevisionId,
        expectedVersion: document.expectedVersion,
      },
    });
    if (state.hostile) {
      // Split-identity contract probe: an activated identity that differs
      // from the exact reviewed Draft identity must never render as success.
      sendJson(res, 200, {
        activatedRevisionId: NOTIFICATION_ACTIVE_REVISION,
        activatedVersion: state.draftVersion,
        revisionSequence: 4,
        publishedFromRevisionId: NOTIFICATION_DRAFT_REVISION,
        publishedFromVersion: state.draftVersion,
        activeConfiguration: {
          revisionId: NOTIFICATION_ACTIVE_REVISION,
          version: state.draftVersion,
          revisionSequence: 4,
          status: "active",
        },
        webhook: webhookDocument(state, token),
      });
      return;
    }
    sendJson(res, 200, {
      activatedRevisionId: NOTIFICATION_DRAFT_REVISION,
      activatedVersion: state.draftVersion,
      revisionSequence: 4,
      publishedFromRevisionId: NOTIFICATION_DRAFT_REVISION,
      publishedFromVersion: state.draftVersion,
      activeConfiguration: {
        revisionId: NOTIFICATION_DRAFT_REVISION,
        version: state.draftVersion,
        revisionSequence: 4,
        status: "active",
      },
      webhook: webhookDocument(state, token),
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/configuration/revisions/${NOTIFICATION_ACTIVE_REVISION}/successor` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    await readBoundedJsonBody(req, res);
    const state = notificationState(session);
    state.draftCreated = true;
    state.draftVersion = 4;
    state.draftStatus = "draft";
    recordManualRequestForSession({
      method: "POST",
      objectId: NOTIFICATION_ACTIVE_REVISION,
      objectType: "notification_successor_draft",
      path: "/api/v1/configuration/revisions/:revisionId/successor",
      body: {},
    });
    sendJson(res, 201, {
      revisionId: NOTIFICATION_DRAFT_REVISION,
      version: 4,
      status: "draft",
      revisionSequence: 3,
      schemaVersion: 1,
      createdAt: MANUAL_RECORDED_AT,
      updatedAt: MANUAL_RECORDED_AT,
      validatedAt: null,
      activatedAt: null,
      validationErrors: [],
      created: true,
      nextAction:
        "open the successor Draft, edit configuration objects, validate, and activate",
    });
    return;
  }
  if (
    url.pathname ===
      `/api/v1/configuration/revisions/${NOTIFICATION_DRAFT_REVISION}/validate` &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    await readBoundedJsonBody(req, res);
    const state = notificationState(session);
    state.draftStatus = "validated";
    recordManualRequestForSession({
      method: "POST",
      objectId: NOTIFICATION_DRAFT_REVISION,
      objectType: "notification_draft_validate",
      path: "/api/v1/configuration/revisions/:revisionId/validate",
      body: {},
    });
    sendJson(res, 200, {
      revisionId: NOTIFICATION_DRAFT_REVISION,
      version: state.draftVersion,
      status: "validated",
      validationErrors: [],
    });
    return;
  }
  const notificationCreateMatch = url.pathname.match(
    /^\/api\/v1\/configuration\/revisions\/([^/]+)\/objects\/webhooks$/,
  );
  if (
    notificationCreateMatch &&
    notificationCreateMatch[1] === NOTIFICATION_DRAFT_REVISION &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const document = parsed.document ?? {};
    const state = notificationState(session);
    if (document.expectedVersion !== state.draftVersion) {
      sendJson(res, 409, { error: { code: "configuration_version_conflict" } });
      return;
    }
    const object = document.object ?? {};
    const createdId =
      typeof object.id === "string" && object.id
        ? object.id
        : "created-webhook";
    if (createdId === NOTIFICATION_WEBHOOK_ID) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    state.createdWebhook = createdId;
    state.draftVersion += 1;
    recordManualRequestForSession({
      method: "POST",
      objectId: createdId,
      objectType: "notification_webhook_create",
      path: "/api/v1/configuration/revisions/:revisionId/objects/webhooks",
      body: { id: createdId, expectedVersion: document.expectedVersion },
    });
    if (state.hostile) {
      // Wrong-revision contract probe: a success document answering for
      // another revision must never render as this create's outcome.
      sendJson(res, 200, {
        revisionId: NOTIFICATION_ACTIVE_REVISION,
        version: state.draftVersion,
        status: state.draftStatus,
        webhook: { id: createdId, enabled: false },
      });
      return;
    }
    sendJson(res, 200, {
      revisionId: NOTIFICATION_DRAFT_REVISION,
      version: state.draftVersion,
      status: state.draftStatus,
      webhook: { id: createdId, enabled: false },
    });
    return;
  }
  const notificationEditMatch = url.pathname.match(
    /^\/api\/v1\/configuration\/revisions\/([^/]+)\/objects\/webhooks\/([^/]+)$/,
  );
  if (
    notificationEditMatch &&
    notificationEditMatch[1] === NOTIFICATION_DRAFT_REVISION &&
    req.method === "PUT"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const document = parsed.document ?? {};
    const state = notificationState(session);
    if (document.expectedVersion !== state.draftVersion) {
      sendJson(res, 409, { error: { code: "configuration_version_conflict" } });
      return;
    }
    state.draftVersion += 1;
    recordManualRequestForSession({
      method: "PUT",
      objectId: notificationEditMatch[2],
      objectType: "notification_webhook_save",
      path: "/api/v1/configuration/revisions/:revisionId/objects/webhooks/:webhookId",
      body: {
        webhookId: notificationEditMatch[2],
        expectedVersion: document.expectedVersion,
      },
    });
    if (state.hostile) {
      // Missing-definition contract probe: a success document without the
      // saved definition must never render as this save's outcome.
      sendJson(res, 200, {
        revisionId: NOTIFICATION_DRAFT_REVISION,
        version: state.draftVersion,
        status: state.draftStatus,
      });
      return;
    }
    sendJson(res, 200, {
      revisionId: NOTIFICATION_DRAFT_REVISION,
      version: state.draftVersion,
      status: state.draftStatus,
      webhook: { id: notificationEditMatch[2] },
    });
    return;
  }
  const notificationObjectActionMatch = url.pathname.match(
    /^\/api\/v1\/configuration\/revisions\/([^/]+)\/objects\/webhooks\/([^/]+)\/(copy|enable|disable)$/,
  );
  if (
    notificationObjectActionMatch &&
    notificationObjectActionMatch[1] === NOTIFICATION_DRAFT_REVISION &&
    req.method === "POST"
  ) {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const document = parsed.document ?? {};
    const state = notificationState(session);
    const action = notificationObjectActionMatch[3];
    if (document.expectedVersion !== state.draftVersion) {
      sendJson(res, 409, { error: { code: "configuration_version_conflict" } });
      return;
    }
    state.draftVersion += 1;
    let objectId = notificationObjectActionMatch[2];
    if (action === "copy") {
      objectId = `${notificationObjectActionMatch[2]}-copy`;
      state.copiedWebhook = objectId;
    }
    recordManualRequestForSession({
      method: "POST",
      objectId,
      objectType: `notification_webhook_${action}`,
      path: "/api/v1/configuration/revisions/:revisionId/objects/webhooks/:webhookId/:action",
      body: {
        webhookId: notificationObjectActionMatch[2],
        action,
        expectedVersion: document.expectedVersion,
        ...(action === "copy" ? { newId: document.newId } : {}),
      },
    });
    if (state.hostile) {
      if (action === "copy") {
        // Same-prefix wrong-object contract probe: only the exact requested
        // newId is bound to this copy mutation.
        sendJson(res, 200, {
          revisionId: NOTIFICATION_DRAFT_REVISION,
          version: state.draftVersion,
          status: state.draftStatus,
          object: { id: "operations-webhook-copy-malicious", enabled: false },
        });
      } else {
        // Contradictory-toggle contract probe: a success document whose
        // enabled state contradicts the submitted toggle is malformed
        // evidence, never this toggle's outcome.
        sendJson(res, 200, {
          revisionId: NOTIFICATION_DRAFT_REVISION,
          version: state.draftVersion,
          status: state.draftStatus,
          object: {
            id: notificationObjectActionMatch[2],
            enabled: action !== "enable",
          },
        });
      }
      return;
    }
    // The managed copy stores a disabled Draft definition; enable/disable
    // stores the submitted toggle state.
    sendJson(res, 200, {
      revisionId: NOTIFICATION_DRAFT_REVISION,
      version: state.draftVersion,
      status: state.draftStatus,
      object: {
        id: objectId,
        enabled: action === "enable" ? true : false,
      },
    });
    return;
  }
  if (url.pathname === "/api/v1/notifications" && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const state = notificationState(session);
    const status = url.searchParams.get("status");
    if (status !== null && !/^[a-z][a-z0-9-]{0,31}$/.test(status)) {
      sendJson(res, 400, { error: { code: "invalid_request" } });
      return;
    }
    const all = [
      notificationDeliveryItem(state, NOTIFICATION_DELIVERY_ID),
      notificationDeliveryItem(state, NOTIFICATION_DELIVERY_ID_2),
    ];
    const items =
      status === null || status === "all"
        ? all
        : all.filter((item) => item.status === status);
    sendJson(res, 200, {
      limit: 20,
      status: status === "all" ? null : status,
      previous_cursor: null,
      next_cursor: null,
      items,
    });
    return;
  }
  const notificationDeliveryMatch = url.pathname.match(
    /^\/api\/v1\/notifications\/deliveries\/([^/]+)$/,
  );
  if (notificationDeliveryMatch && req.method === "GET") {
    if (!operationsGuard(res)) {
      return;
    }
    const deliveryId = notificationDeliveryMatch[1];
    if (
      deliveryId !== NOTIFICATION_DELIVERY_ID &&
      deliveryId !== NOTIFICATION_DELIVERY_ID_2
    ) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    const state = notificationState(session);
    sendJson(
      res,
      200,
      notificationDeliveryDetailDocument(state, token, deliveryId),
    );
    return;
  }
  const notificationRecoveryMatch = url.pathname.match(
    /^\/api\/v1\/notifications\/([^/]+)\/(requeue|resolve-stale)$/,
  );
  if (notificationRecoveryMatch && req.method === "POST") {
    if (!operationsGuard(res)) {
      return;
    }
    const parsed = await readBoundedJsonBody(req, res);
    if (!parsed.ok) {
      return;
    }
    const document = parsed.document ?? {};
    const state = notificationState(session);
    const deliveryId = notificationRecoveryMatch[1];
    const action = notificationRecoveryMatch[2];
    if (
      deliveryId !== NOTIFICATION_DELIVERY_ID &&
      deliveryId !== NOTIFICATION_DELIVERY_ID_2
    ) {
      sendJson(res, 404, { error: { code: "not_found" } });
      return;
    }
    const item = notificationDeliveryItem(state, deliveryId);
    if (
      document.expectedStatus !== item.status ||
      document.expectedUpdatedAt !== item.updatedAt
    ) {
      sendJson(res, 409, { error: { code: "notification_delivery_conflict" } });
      return;
    }
    state.requeued = true;
    recordManualRequestForSession({
      method: "POST",
      objectId: deliveryId,
      objectType: "notification_delivery_recovery",
      path: "/api/v1/notifications/:deliveryId/:action",
      body: {
        deliveryId,
        action,
        expectedStatus: document.expectedStatus,
        expectedUpdatedAt: document.expectedUpdatedAt,
      },
    });
    if (state.hostile) {
      // Wrong-object contract probe: a success result about another delivery
      // must never render as this recovery's outcome.
      sendJson(res, 200, {
        action: action === "requeue" ? "requeue-dead-letter" : "resolve-stale",
        outcome: "success",
        deliveryId:
          deliveryId === NOTIFICATION_DELIVERY_ID
            ? NOTIFICATION_DELIVERY_ID_2
            : NOTIFICATION_DELIVERY_ID,
        previousStatus: item.status,
        status: "pending",
        attempts: action === "requeue" ? 0 : item.attempts,
        durableState:
          action === "requeue"
            ? "dead_letter_requeued_same_identity"
            : "stale_delivery_returned_to_queue_same_identity",
        sideEffects: "delivery_queue_state_only_no_new_row_no_media_change",
        retrySafe: true,
        atLeastOnce:
          "recovery preserves the stable delivery identity; the worker sends the event again, so receivers must tolerate duplicates",
        duplicateImplication:
          "receivers must tolerate duplicates (at-least-once)",
        nextAction: "the delivery is pending again; refresh this delivery",
      });
      return;
    }
    sendJson(res, 200, {
      action: action === "requeue" ? "requeue-dead-letter" : "resolve-stale",
      outcome: "success",
      deliveryId,
      previousStatus: item.status,
      status: "pending",
      attempts: action === "requeue" ? 0 : item.attempts,
      durableState:
        action === "requeue"
          ? "dead_letter_requeued_same_identity"
          : "stale_delivery_returned_to_queue_same_identity",
      sideEffects: "delivery_queue_state_only_no_new_row_no_media_change",
      retrySafe: true,
      atLeastOnce:
        "recovery preserves the stable delivery identity; the worker sends the event again, so receivers must tolerate duplicates",
      duplicateImplication:
        "receivers must tolerate duplicates (at-least-once)",
      nextAction: "the delivery is pending again; refresh this delivery",
      delivery: notificationDeliveryDetailDocument(state, token, deliveryId),
    });
    return;
  }

  if (url.pathname === "/__test__/manual-operations" && req.method === "GET") {
    // Session-scoped evidence keeps each test's assertions independent even
    // while two workers drive the same fake server.
    sendJson(res, 200, {
      items: [
        ...RECORDED_MANUAL_REQUESTS,
        ...(session === null
          ? []
          : (RECORDED_MANUAL_REQUESTS_BY_SESSION.get(session) ?? [])),
      ],
    });
    return;
  }

  // Deterministic per-test reset for the manual Organize fake state so the
  // journey proof never depends on another test having run first. The reset is
  // strictly scoped to the calling browser session: another test's evidence and
  // state are never erased, so parallel workers stay isolated.
  if (url.pathname === "/__test__/reset-organize" && req.method === "POST") {
    const sessionId =
      session ?? `shared-${Math.random().toString(36).slice(2, 12)}`;
    RECORDED_MANUAL_REQUESTS_BY_SESSION.set(sessionId, []);
    ORGANIZE_STATES.set(sessionId, {
      executed: false,
      intentVersion: 1,
      itemVersion: 1,
    });
    res.setHeader(
      "Set-Cookie",
      `${MANUAL_SESSION_COOKIE}=${encodeURIComponent(sessionId)}; Path=/; SameSite=Lax`,
    );
    sendJson(res, 200, { ok: true, session: sessionId });
    return;
  }

  if (
    url.pathname === "/__test__/reset-resource-library" &&
    req.method === "POST"
  ) {
    const sessionId =
      session ?? `shared-${Math.random().toString(36).slice(2, 12)}`;
    const libraries = Number(url.searchParams.get("libraries") ?? "0");
    RESOURCE_LIBRARY_STATES.set(sessionId, {
      saved: false,
      failOnce: url.searchParams.get("failOnce") === "1",
      failed: false,
      candidate: null,
      extra: ["a", "b", "c", "d", "e"]
        .slice(0, Number.isNaN(libraries) ? 0 : libraries)
        .map((suffix) => ({
          id: `lib-${suffix}`,
          name: `资源库${suffix.toUpperCase()}`,
          storage_id: "local-media",
          root_path: `library-${suffix}`,
          enabled: true,
        })),
      removedIds: [],
      emptied: url.searchParams.get("empty") === "1",
      textStale: url.searchParams.get("textStale") === "1",
      commandLog: [],
    });
    res.setHeader(
      "Set-Cookie",
      `${MANUAL_SESSION_COOKIE}=${encodeURIComponent(sessionId)}; Path=/; SameSite=Lax`,
    );
    sendJson(res, 200, { ok: true, session: sessionId });
    return;
  }

  if (url.pathname === "/__test__/reset-automation" && req.method === "POST") {
    const sessionId =
      session ?? `shared-${Math.random().toString(36).slice(2, 12)}`;
    RECORDED_MANUAL_REQUESTS_BY_SESSION.set(sessionId, []);
    AUTOMATION_STATES.set(sessionId, {
      draftCreated: false,
      draftVersion: 2,
      draftStatus: "draft",
      previewCreated: false,
      previewStale: false,
      granted: false,
      activated: false,
      createdDefinition: null,
      copiedDefinition: null,
    });
    res.setHeader(
      "Set-Cookie",
      `${MANUAL_SESSION_COOKIE}=${encodeURIComponent(sessionId)}; Path=/; SameSite=Lax`,
    );
    sendJson(res, 200, { ok: true, session: sessionId });
    return;
  }

  if (
    url.pathname === "/__test__/reset-notifications" &&
    req.method === "POST"
  ) {
    const sessionId =
      session ?? `shared-${Math.random().toString(36).slice(2, 12)}`;
    RECORDED_MANUAL_REQUESTS_BY_SESSION.set(sessionId, []);
    NOTIFICATION_STATES.set(sessionId, {
      draftCreated: false,
      draftVersion: 4,
      draftStatus: "validated",
      tested: false,
      activated: false,
      createdWebhook: null,
      copiedWebhook: null,
      requeued: false,
      // `?hostile=1` turns the fake into a wrong-object contract probe: the
      // truthful mutations still happen, but the success documents answer for
      // another Webhook/delivery, so the V2 client must refuse to render them.
      hostile: url.searchParams.get("hostile") === "1",
    });
    res.setHeader(
      "Set-Cookie",
      `${MANUAL_SESSION_COOKIE}=${encodeURIComponent(sessionId)}; Path=/; SameSite=Lax`,
    );
    sendJson(res, 200, { ok: true, session: sessionId });
    return;
  }

  if (url.pathname === "/__test__/mutations" && req.method === "GET") {
    sendJson(res, 200, { items: RECORDED_MUTATIONS });
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
