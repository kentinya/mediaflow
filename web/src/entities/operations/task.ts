/**
 * Frontend-owned Task entity for the Operations workspace.
 *
 * The Python contract (`GET /api/v1/tasks`, `GET /api/v1/tasks/{id}`) returns
 * snake_case records. Normalization is deliberately fail-closed: a status
 * outside the modelled set, a coerced boolean, a miscounted progress pair or a
 * lifecycle projection that contradicts its own state makes the whole response
 * malformed instead of being rendered as an approximate truth.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  normalizeTextArray,
  readRecord,
} from "../shared/normalize";
import {
  normalizeLifecycleProjection,
  type LifecycleProjection,
} from "./lifecycle";

export const TASK_STATUSES = [
  "pending",
  "running",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
  "paused",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

/** Task statuses that durably end the Task aggregate. */
export const TERMINAL_TASK_STATUSES: readonly TaskStatus[] = [
  "completed",
  "partial_success",
  "failed",
  "cancelled",
];

export const TASK_ITEM_STATUSES = [
  "pending",
  "processing",
  "dry_run",
  "success",
  "partial",
  "failed",
  "skipped",
  "cancelled",
  "waiting_confirm",
  "waiting_recognition",
  "waiting_metadata",
  "waiting_metadata_correction",
  "waiting_classification",
  "paused",
  "ignored",
] as const;
export type TaskItemStatus = (typeof TASK_ITEM_STATUSES)[number];

/** Bounded backend Task command families offered as an operator filter. */
export const TASK_COMMAND_FILTERS = [
  "scan",
  "preview",
  "organize",
  "retry",
  "retry-failed",
  "metadata-correction-continuation",
  "recovery-continuation",
  "file-metadata-correction",
] as const;

export const EFFECT_CERTAINTY_VALUES = [
  "none",
  "verified_complete",
  "attempted_unverified",
  "unknown",
] as const;
export type ResultEffectCertainty = (typeof EFFECT_CERTAINTY_VALUES)[number];

/**
 * Bounded, secret-free failure evidence. The backend supplies this only when it
 * can decode its own bounded envelope, so a raw adapter exception never reaches
 * the model.
 */
export interface TaskFailureExplanation {
  readonly category: string;
  readonly message: string;
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
}

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
  readonly failureExplanation: TaskFailureExplanation | null;
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
  readonly effectCertainty: ResultEffectCertainty;
  readonly uncertainEffects: readonly string[];
}

export interface TaskDetailPage {
  readonly task: TaskSummary;
  readonly lifecycle: LifecycleProjection;
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
  readonly status: TaskStatus | null;
  readonly command: string | null;
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

function fail(): never {
  throw new TaskNormalizationError();
}

function text(source: Record<string, unknown>, field: string): string {
  try {
    return normalizeBoundedText(source[field], field);
  } catch {
    return fail();
  }
}

function optionalText(
  source: Record<string, unknown>,
  field: string,
): string | null {
  try {
    return normalizeOptionalText(source[field], field);
  } catch {
    return fail();
  }
}

function count(source: Record<string, unknown>, field: string): number {
  try {
    return normalizeBoundedCount(source[field], field);
  } catch {
    return fail();
  }
}

function flag(source: Record<string, unknown>, field: string): boolean {
  try {
    return normalizeBoolean(source[field], field);
  } catch {
    return fail();
  }
}

function normalizeTaskSummary(source: Record<string, unknown>): TaskSummary {
  let status: TaskStatus;
  try {
    status = normalizeEnum(source["status"], "status", TASK_STATUSES);
  } catch {
    return fail();
  }
  const totalItems = count(source, "total_items");
  const completedItems = count(source, "completed_items");
  const failedItems = count(source, "failed_items");
  if (completedItems + failedItems > totalItems) {
    // Progress that cannot describe one Task is contradictory, not rounded.
    fail();
  }
  const startedAt = optionalText(source, "started_at");
  const completedAt = optionalText(source, "completed_at");
  const pauseRequested = flag(source, "pause_requested");
  const terminal = TERMINAL_TASK_STATUSES.includes(status);
  if (terminal !== (completedAt !== null)) {
    fail();
  }
  if (pauseRequested && status !== "running") {
    // A pending pause request can only belong to a running Task: an
    // acknowledged pause clears it and a terminal Task cannot hold one.
    fail();
  }
  return {
    taskId: text(source, "task_id"),
    command: text(source, "command"),
    status,
    executeAuthorized: flag(source, "execute_authorized"),
    createdAt: text(source, "created_at"),
    updatedAt: text(source, "updated_at"),
    startedAt,
    completedAt,
    totalItems,
    completedItems,
    failedItems,
    error: optionalText(source, "error"),
    failureExplanation:
      source["failureExplanation"] === null ||
      source["failureExplanation"] === undefined
        ? null
        : normalizeTaskFailureExplanation(source["failureExplanation"]),
    pauseRequested,
    configurationSnapshotId: optionalText(source, "configuration_snapshot_id"),
    configurationSnapshotDigest: optionalText(
      source,
      "configuration_snapshot_digest",
    ),
  };
}

function normalizeTaskFailureExplanation(
  value: unknown,
): TaskFailureExplanation {
  const source = readRecord(value, "failureExplanation");
  try {
    return {
      category: text(source, "category"),
      message: text(source, "message"),
      durableState: text(source, "durableState"),
      sideEffects: text(source, "sideEffects"),
      retrySafe: flag(source, "retrySafe"),
      nextAction: text(source, "nextAction"),
    };
  } catch {
    return fail();
  }
}

function normalizeTaskItemCheckpoint(
  value: unknown,
): TaskItemCheckpoint | null {
  if (value === null || value === undefined) return null;
  const source = readRecord(value, "checkpoint");
  return {
    status: text(source, "status"),
    stage: text(source, "stage"),
    attempts: count(source, "attempts"),
    effectCertainty: text(source, "effect_certainty"),
    retrySafety: text(source, "retry_safety"),
    nextAction:
      optionalText(source, "nextAction") ?? optionalText(source, "next_action"),
    errorCategory: text(source, "error_category"),
  };
}

function normalizeTaskItemSummary(
  source: Record<string, unknown>,
): TaskItemSummary {
  let status: TaskItemStatus;
  try {
    status = normalizeEnum(source["status"], "item.status", TASK_ITEM_STATUSES);
  } catch {
    return fail();
  }
  return {
    itemId: text(source, "item_id"),
    taskId: text(source, "task_id"),
    storageId: text(source, "storage_id"),
    resourceLibraryId: text(source, "resource_library_id"),
    sourcePath: text(source, "source_path"),
    sourceDisplay: text(source, "source_display"),
    status,
    stage: text(source, "stage"),
    attempts: count(source, "attempts"),
    createdAt: text(source, "created_at"),
    updatedAt: text(source, "updated_at"),
    planId: optionalText(source, "plan_id"),
    destinationStorageId: optionalText(source, "destination_storage_id"),
    destinationPath: optionalText(source, "destination_path"),
    executionStatus: optionalText(source, "execution_status"),
    error: optionalText(source, "error"),
    checkpoint: normalizeTaskItemCheckpoint(source["checkpoint"]),
  };
}

function normalizeTaskResultSummary(
  source: Record<string, unknown>,
): TaskResultSummary {
  let effectCertainty: ResultEffectCertainty;
  let uncertainEffects: readonly string[];
  let completedOperations: readonly string[];
  try {
    effectCertainty = normalizeEnum(
      source["effect_certainty"],
      "result.effect_certainty",
      EFFECT_CERTAINTY_VALUES,
    );
    uncertainEffects = normalizeTextArray(
      source["uncertain_effects"],
      "result.uncertain_effects",
    );
    completedOperations = normalizeTextArray(
      source["completed_operations"],
      "result.completed_operations",
    );
  } catch {
    return fail();
  }
  if (
    uncertainEffects.length > 0 !==
    (effectCertainty === "attempted_unverified")
  ) {
    // Unverified effect evidence and its explicit effect list must agree.
    fail();
  }
  return {
    resultId: text(source, "result_id"),
    taskId: text(source, "task_id"),
    itemId: text(source, "item_id"),
    sourceStorageId: text(source, "source_storage_id"),
    sourcePath: text(source, "source_path"),
    destinationStorageId: optionalText(source, "destination_storage_id"),
    destinationPath: optionalText(source, "destination_path"),
    recognitionType: optionalText(source, "recognition_type"),
    provider: optionalText(source, "provider"),
    providerId: optionalText(source, "provider_id"),
    metadataPolicyId: optionalText(source, "metadata_policy_id"),
    namingPolicyId: optionalText(source, "naming_policy_id"),
    classificationPolicyId: optionalText(source, "classification_policy_id"),
    organizePolicyId: optionalText(source, "organize_policy_id"),
    operation: optionalText(source, "operation"),
    status: text(source, "status"),
    createdAt: text(source, "created_at"),
    title: optionalText(source, "title"),
    error: optionalText(source, "error"),
    completedOperations,
    effectCertainty,
    uncertainEffects,
  };
}

function normalizeFilterEcho(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  return text(source, field);
}

export function normalizeTaskListPage(payload: unknown): TaskListPage {
  const source = readRecord(payload, "task_list");
  const items = source["items"];
  if (!Array.isArray(items)) {
    fail();
  }
  const rawStatus = normalizeFilterEcho(source, "status");
  let status: TaskStatus | null = null;
  if (rawStatus !== null) {
    try {
      status = normalizeEnum(rawStatus, "status", TASK_STATUSES);
    } catch {
      return fail();
    }
  }
  return {
    items: items.map((item) => normalizeTaskSummary(readRecord(item, "task"))),
    limit: count(source, "limit"),
    status,
    command: normalizeFilterEcho(source, "command"),
    truncated: flag(source, "truncated"),
    previousCursor: optionalText(source, "previous_cursor"),
    nextCursor: optionalText(source, "next_cursor"),
  };
}

export function normalizeTaskDetailPage(payload: unknown): TaskDetailPage {
  const source = readRecord(payload, "task_detail");
  const items = source["items"];
  const results = source["results"];
  if (!Array.isArray(items) || !Array.isArray(results)) {
    fail();
  }
  const task = normalizeTaskSummary(source);
  const lifecycle = normalizeLifecycleProjection(source["lifecycle"], {
    objectType: "task",
    objectId: task.taskId,
    state: task.status,
  });
  return {
    task,
    lifecycle,
    items: items.map((item) =>
      normalizeTaskItemSummary(readRecord(item, "task_item")),
    ),
    results: results.map((result) =>
      normalizeTaskResultSummary(readRecord(result, "task_result")),
    ),
    itemLimit: count(source, "item_limit"),
    resultLimit: count(source, "result_limit"),
    itemsTruncated: flag(source, "items_truncated"),
    resultsTruncated: flag(source, "results_truncated"),
    previousItemCursor: optionalText(source, "previous_item_cursor"),
    previousResultCursor: optionalText(source, "previous_result_cursor"),
    nextItemCursor: optionalText(source, "next_item_cursor"),
    nextResultCursor: optionalText(source, "next_result_cursor"),
  };
}

/** True only for a Task status that durably ends the aggregate. */
export function isTerminalTaskStatus(status: TaskStatus): boolean {
  return TERMINAL_TASK_STATUSES.includes(status);
}

/** Normalize one Task record (for example the Task returned by a control). */
export function normalizeTaskRecord(payload: unknown): TaskSummary {
  return normalizeTaskSummary(readRecord(payload, "task"));
}
