/**
 * Frontend-owned Task entity for the Operations workspace.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  readRecord,
} from "../shared/normalize";

export type TaskStatus =
  | "pending"
  | "running"
  | "completed"
  | "partial_success"
  | "failed"
  | "cancelled"
  | "paused";

export type TaskItemStatus =
  | "pending"
  | "processing"
  | "dry_run"
  | "success"
  | "partial"
  | "failed"
  | "skipped"
  | "cancelled"
  | "waiting_confirm"
  | "waiting_recognition"
  | "waiting_metadata"
  | "waiting_metadata_correction"
  | "waiting_classification"
  | "paused"
  | "ignored";

export interface TaskSummary {
  readonly taskId: string;
  readonly command: string;
  readonly status: TaskStatus;
  readonly executeAuthorized: boolean;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly totalItems: number;
  readonly completedItems: number;
  readonly failedItems: number;
  readonly error: string | null;
  readonly pauseRequested: boolean;
  readonly configurationSnapshotId: string | null;
  readonly configurationSnapshotDigest: string | null;
}

export interface TaskItemSummary {
  readonly itemId: string;
  readonly taskId: string;
  readonly storageId: string;
  readonly resourceLibraryId: string;
  readonly sourcePath: string;
  readonly sourceDisplay: string;
  readonly status: TaskItemStatus;
  readonly stage: string;
  readonly attempts: number;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly planId: string | null;
  readonly destinationStorageId: string | null;
  readonly destinationPath: string | null;
  readonly executionStatus: string | null;
  readonly error: string | null;
  readonly checkpoint: TaskItemCheckpoint | null;
}

export interface TaskItemCheckpoint {
  readonly status: string;
  readonly stage: string;
  readonly attempts: number;
  readonly effectCertainty: string;
  readonly retrySafety: string;
  readonly nextAction: string | null;
  readonly errorCategory: string;
}

export interface TaskResultSummary {
  readonly resultId: string;
  readonly taskId: string;
  readonly itemId: string;
  readonly sourceStorageId: string;
  readonly sourcePath: string;
  readonly destinationStorageId: string | null;
  readonly destinationPath: string | null;
  readonly recognitionType: string | null;
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly metadataPolicyId: string | null;
  readonly namingPolicyId: string | null;
  readonly classificationPolicyId: string | null;
  readonly organizePolicyId: string | null;
  readonly operation: string | null;
  readonly status: string;
  readonly createdAt: string;
  readonly title: string | null;
  readonly error: string | null;
  readonly completedOperations: readonly string[];
  readonly effectCertainty: string;
  readonly uncertainEffects: readonly string[];
}

export interface TaskDetailPage {
  readonly task: TaskSummary;
  readonly items: readonly TaskItemSummary[];
  readonly results: readonly TaskResultSummary[];
  readonly itemLimit: number;
  readonly resultLimit: number;
  readonly itemsTruncated: boolean;
  readonly resultsTruncated: boolean;
  readonly previousItemCursor: string | null;
  readonly previousResultCursor: string | null;
  readonly nextItemCursor: string | null;
  readonly nextResultCursor: string | null;
}

export interface TaskListPage {
  readonly items: readonly TaskSummary[];
  readonly limit: number;
  readonly truncated: boolean;
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
}

export class TaskNormalizationError extends Error {
  constructor() {
    super("task response did not match the expected contract");
    this.name = "TaskNormalizationError";
  }
}

function str(
  source: Record<string, unknown>,
  field: string,
): string {
  return normalizeBoundedText(source[field], field);
}

function optStr(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const v = source[field];
  return typeof v === "string" && v.length > 0 ? v : null;
}

function num(
  source: Record<string, unknown>,
  field: string,
): number {
  return normalizeBoundedCount(source[field], field);
}

function normalizeTaskSummary(source: Record<string, unknown>): TaskSummary {
  return {
    taskId: str(source, "task_id"),
    command: str(source, "command"),
    status: str(source, "status") as TaskStatus,
    executeAuthorized: Boolean(source["execute_authorized"]),
    createdAt: str(source, "created_at"),
    updatedAt: str(source, "updated_at"),
    startedAt: typeof source["started_at"] === "string" ? (source["started_at"] as string) : null,
    completedAt: typeof source["completed_at"] === "string" ? (source["completed_at"] as string) : null,
    totalItems: num(source, "total_items"),
    completedItems: num(source, "completed_items"),
    failedItems: num(source, "failed_items"),
    error:
      typeof source["error"] === "string" && (source["error"] as string).length > 0
        ? (source["error"] as string)
        : null,
    pauseRequested: Boolean(source["pause_requested"]),
    configurationSnapshotId: optStr(source, "configuration_snapshot_id"),
    configurationSnapshotDigest: optStr(source, "configuration_snapshot_digest"),
  };
}

function normalizeTaskItemCheckpoint(
  value: unknown,
): TaskItemCheckpoint | null {
  if (value === null || value === undefined) return null;
  const s = readRecord(value, "checkpoint");
  return {
    status: str(s, "status"),
    stage: str(s, "stage"),
    attempts: num(s, "attempts"),
    effectCertainty: str(s, "effect_certainty"),
    retrySafety: str(s, "retry_safety"),
    nextAction: typeof s["nextAction"] === "string"
      ? (s["nextAction"] as string)
      : typeof s["next_action"] === "string"
        ? (s["next_action"] as string)
        : null,
    errorCategory: str(s, "error_category"),
  };
}

function normalizeTaskItemSummary(
  source: Record<string, unknown>,
): TaskItemSummary {
  return {
    itemId: str(source, "item_id"),
    taskId: str(source, "task_id"),
    storageId: str(source, "storage_id"),
    resourceLibraryId: str(source, "resource_library_id"),
    sourcePath: str(source, "source_path"),
    sourceDisplay: str(source, "source_display"),
    status: str(source, "status") as TaskItemStatus,
    stage: str(source, "stage"),
    attempts: num(source, "attempts"),
    createdAt: str(source, "created_at"),
    updatedAt: str(source, "updated_at"),
    planId: optStr(source, "plan_id"),
    destinationStorageId: optStr(source, "destination_storage_id"),
    destinationPath: optStr(source, "destination_path"),
    executionStatus: optStr(source, "execution_status"),
    error:
      typeof source["error"] === "string" && (source["error"] as string).length > 0
        ? (source["error"] as string)
        : null,
    checkpoint: normalizeTaskItemCheckpoint(source["checkpoint"]),
  };
}

function normalizeTaskResultSummary(
  source: Record<string, unknown>,
): TaskResultSummary {
  const completedOps = source["completed_operations"];
  const uncertain = source["uncertain_effects"];
  return {
    resultId: str(source, "result_id"),
    taskId: str(source, "task_id"),
    itemId: str(source, "item_id"),
    sourceStorageId: str(source, "source_storage_id"),
    sourcePath: str(source, "source_path"),
    destinationStorageId: optStr(source, "destination_storage_id"),
    destinationPath: optStr(source, "destination_path"),
    recognitionType: optStr(source, "recognition_type"),
    provider: optStr(source, "provider"),
    providerId: optStr(source, "provider_id"),
    metadataPolicyId: optStr(source, "metadata_policy_id"),
    namingPolicyId: optStr(source, "naming_policy_id"),
    classificationPolicyId: optStr(source, "classification_policy_id"),
    organizePolicyId: optStr(source, "organize_policy_id"),
    operation: optStr(source, "operation"),
    status: str(source, "status"),
    createdAt: str(source, "created_at"),
    title: optStr(source, "title"),
    error:
      typeof source["error"] === "string" && (source["error"] as string).length > 0
        ? (source["error"] as string)
        : null,
    completedOperations: Array.isArray(completedOps)
      ? (completedOps as unknown[]).map((v) => String(v))
      : [],
    effectCertainty: str(source, "effect_certainty"),
    uncertainEffects: Array.isArray(uncertain)
      ? (uncertain as unknown[]).map((v) => String(v))
      : [],
  };
}

export function normalizeTaskListPage(payload: unknown): TaskListPage {
  const source = readRecord(payload, "task_list");
  const items = source["items"];
  if (!Array.isArray(items)) {
    throw new TaskNormalizationError();
  }
  return {
    items: items.map((item) => normalizeTaskSummary(readRecord(item, "task"))),
    limit: typeof source["limit"] === "number" ? (source["limit"] as number) : 20,
    truncated: Boolean(source["truncated"]),
    previousCursor: typeof source["previous_cursor"] === "string" ? (source["previous_cursor"] as string) : null,
    nextCursor: typeof source["next_cursor"] === "string" ? (source["next_cursor"] as string) : null,
  };
}

export function normalizeTaskDetailPage(payload: unknown): TaskDetailPage {
  const source = readRecord(payload, "task_detail");
  const items = source["items"];
  const results = source["results"];
  if (!Array.isArray(items) || !Array.isArray(results)) {
    throw new TaskNormalizationError();
  }
  return {
    task: normalizeTaskSummary(source),
    items: items.map((item) =>
      normalizeTaskItemSummary(readRecord(item, "task_item")),
    ),
    results: results.map((result) =>
      normalizeTaskResultSummary(readRecord(result, "task_result")),
    ),
    itemLimit: num(source, "item_limit"),
    resultLimit: num(source, "result_limit"),
    itemsTruncated: Boolean(source["items_truncated"]),
    resultsTruncated: Boolean(source["results_truncated"]),
    previousItemCursor: typeof source["previous_item_cursor"] === "string" ? (source["previous_item_cursor"] as string) : null,
    previousResultCursor: typeof source["previous_result_cursor"] === "string" ? (source["previous_result_cursor"] as string) : null,
    nextItemCursor: typeof source["next_item_cursor"] === "string" ? (source["next_item_cursor"] as string) : null,
    nextResultCursor: typeof source["next_result_cursor"] === "string" ? (source["next_result_cursor"] as string) : null,
  };
}

/**
 * Determine which lifecycle actions the backend currently advertises for
 * a given task state.
 */
export function taskLifecycleActions(task: TaskSummary): {
  readonly cancel: boolean;
  readonly pause: boolean;
  readonly resume: boolean;
} {
  const st = task.status;
  const pauseable = st === "running" && !task.pauseRequested;
  const resumable = st === "paused";
  const cancelable = st === "pending" || st === "running" || st === "paused";
  return { cancel: cancelable, pause: pauseable, resume: resumable };
}
