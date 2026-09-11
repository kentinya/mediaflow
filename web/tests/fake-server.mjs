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
  "expectedVersion",
  "fileId",
  "itemIds",
  "itemCursor",
  "itemLimit",
  "mode",
  "recognitionTypeId",
  "resourceLibraryId",
  "scopeKind",
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
const ORGANIZE_HOSTILE_PREVIEW_ID = "organize-preview-hostile-e2e-001";
const ORGANIZE_MISBOUND_PREVIEW_ID = "organize-preview-misbound-e2e-001";
const ORGANIZE_EXECUTION_ID = "organize-execution-e2e-001";
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

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  const token = bearerToken(req);
  // One evidence/state bucket per browser session so parallel Playwright
  // workers never erase or observe another test's fake state.
  const session = manualSession(req);
  const recordManualRequestForSession = (entry) =>
    recordManualRequest({ ...entry, session });
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

  if (
    url.pathname ===
      `/api/v1/organize/previews/${ORGANIZE_PREVIEW_ID}/execute` &&
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
        confirmation: fields.confirmation === true,
        expectedIntentVersion: fields.expectedIntentVersion,
        itemIds: Array.isArray(fields.itemIds) ? [...fields.itemIds] : null,
      },
      method: "POST",
      objectId: ORGANIZE_PREVIEW_ID,
      objectType: "organize_execute",
      path: "/api/v1/organize/previews/:previewId/execute",
    });
    if (
      fields.confirmation !== true ||
      !Array.isArray(fields.itemIds) ||
      fields.itemIds.length !== 1 ||
      fields.itemIds[0] !== ORGANIZE_ITEM_ID ||
      fields.expectedIntentVersion !== state.intentVersion
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
