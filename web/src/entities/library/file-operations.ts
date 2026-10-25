/**
 * Frontend models for one library's durable ordinary file-operation index.
 *
 * The Files and MediaLibrary pages read the operations that originated in the
 * library they are browsing, from durable Task evidence rather than from a
 * browser hint, a remembered Task ID or a display string.  These models are
 * strict and secret-free: an unexpected shape, an unknown identity field, a
 * mixed kind or a cursor/page whose identity contradicts the read fails closed
 * instead of rendering a guessed operation.
 *
 * Nothing here decides authority.  A control is only ever the backend
 * lifecycle projection of the exact Task the operator selects.
 */

import type { DirectCommandLibraryKind } from "./direct-files";
import type { LifecycleProjection } from "../operations/lifecycle";

/** The ordinary commands a library page can own, as durable identities. */
export const ORDINARY_FILE_OPERATIONS = [
  "create_directory",
  "create_text",
  "rename",
  "save_text",
  "copy",
  "move",
  "delete",
] as const;
export type OrdinaryFileOperation = (typeof ORDINARY_FILE_OPERATIONS)[number];

export class LibraryFileOperationNormalizationError extends Error {
  constructor() {
    super("library file-operation response did not match the contract");
    this.name = "LibraryFileOperationNormalizationError";
  }
}

function fail(): never {
  throw new LibraryFileOperationNormalizationError();
}

function recordOf(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail();
  }
  return value as Record<string, unknown>;
}

function boundedText(value: unknown, max = 512): string {
  if (typeof value !== "string" || value.length === 0 || value.length > max) {
    fail();
  }
  return value;
}

function optionalText(value: unknown, max = 512): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string" || value.length === 0 || value.length > max) {
    fail();
  }
  return value;
}

function boundedCount(value: unknown): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    fail();
  }
  return value;
}

function flag(value: unknown): boolean {
  if (typeof value !== "boolean") fail();
  return value;
}

/** The single identity field of one kind, and the foreign field it must not carry. */
export function libraryOperationsIdField(
  kind: DirectCommandLibraryKind,
): "resourceLibraryId" | "mediaLibraryId" {
  return kind === "media" ? "mediaLibraryId" : "resourceLibraryId";
}

function readIdentity(
  source: Record<string, unknown>,
  kind: DirectCommandLibraryKind,
  libraryId: string,
): void {
  const own = libraryOperationsIdField(kind);
  const foreign = libraryOperationsIdField(
    kind === "media" ? "resource" : "media",
  );
  if (source[foreign] !== undefined) {
    // A document naming both kinds is a split identity: nothing here guesses
    // which authority is real.
    fail();
  }
  if (source[own] !== libraryId) fail();
}

export interface LibraryFileOperationEntry {
  readonly taskId: string;
  readonly operation: OrdinaryFileOperation | null;
  readonly operationLabel: string;
  readonly command: string;
  readonly commandLabel: string;
  readonly status: string;
  readonly terminal: boolean;
  readonly pauseRequested: boolean;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly version: string;
  readonly totalItems: number;
  readonly settledItems: number;
  readonly succeededItems: number;
  readonly failedItems: number;
  readonly skippedItems: number;
  readonly cancelledItems: number;
  readonly pendingItems: number;
  readonly allSucceeded: boolean;
  readonly settled: boolean;
  readonly sourceScope: string | null;
  readonly targetScope: string | null;
  readonly configurationSnapshotId: string | null;
}

/**
 * One item's durable outcome inside a selected operation.
 *
 * This is the evidence an operator needs to identify which selected file
 * failed after a restart: its exact source/destination, disposition, real
 * effect and the one safe next action.  It is never authority — nothing here
 * can be replayed from the dialog.
 */
export interface LibraryFileOperationItem {
  readonly itemId: string;
  readonly path: string;
  readonly destination: string;
  readonly status: string;
  readonly stage: string | null;
  readonly attempts: number;
  readonly effect: string;
  readonly effectCertainty: string;
  readonly knownEffects: readonly string[];
  readonly children: readonly LibraryFileOperationChild[];
  readonly childrenTruncated: boolean;
  readonly failure: LibraryFileOperationFailure | null;
  readonly nextAction: string;
}

/**
 * One recorded child entry of an item, e.g. a file inside a transferred or
 * deleted directory.
 *
 * A directly selected directory is expanded into one admitted item per child,
 * and a started transfer records each child's own destination, status and
 * completed executor checkpoints.  Exposing them keeps a paused or partially
 * executed folder Move truthful locally instead of collapsing it into one
 * opaque directory row.
 */
export interface LibraryFileOperationChild {
  readonly path: string;
  readonly destination: string;
  readonly status: string;
  readonly effect: string;
  readonly checkpoints: readonly string[];
  readonly failure: LibraryFileOperationFailure | null;
}

/** The bounded, secret-free failure explanation of one item. */
export interface LibraryFileOperationFailure {
  readonly category: string;
  readonly message: string;
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
  readonly retryCategory: string | null;
}

export interface LibraryFileOperationPage {
  readonly libraryKind: DirectCommandLibraryKind;
  readonly libraryId: string;
  readonly items: readonly LibraryFileOperationEntry[];
  readonly limit: number;
  readonly total: number;
  readonly hasNext: boolean;
  readonly hasPrevious: boolean;
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
}

function readEntry(
  value: unknown,
  kind: DirectCommandLibraryKind,
  libraryId: string,
): LibraryFileOperationEntry {
  const source = recordOf(value);
  readIdentity(source, kind, libraryId);
  const rawOperation = source["operation"];
  let operation: OrdinaryFileOperation | null = null;
  if (rawOperation !== null && rawOperation !== undefined) {
    if (
      typeof rawOperation !== "string" ||
      !(ORDINARY_FILE_OPERATIONS as readonly string[]).includes(rawOperation)
    ) {
      // An ordinary read that publishes an unknown operation identity is
      // malformed: the page never renders a guessed command meaning.
      fail();
    }
    operation = rawOperation as OrdinaryFileOperation;
  }
  return {
    taskId: boundedText(source["taskId"], 128),
    operation,
    operationLabel: boundedText(source["operationLabel"], 64),
    command: boundedText(source["command"], 128),
    commandLabel: boundedText(source["commandLabel"], 64),
    status: boundedText(source["status"], 32),
    terminal: flag(source["terminal"]),
    pauseRequested: flag(source["pauseRequested"]),
    createdAt: boundedText(source["createdAt"], 64),
    updatedAt: boundedText(source["updatedAt"], 64),
    version: boundedText(source["version"], 128),
    totalItems: boundedCount(source["totalItems"]),
    settledItems: boundedCount(source["settledItems"]),
    succeededItems: boundedCount(source["succeededItems"]),
    failedItems: boundedCount(source["failedItems"]),
    skippedItems: boundedCount(source["skippedItems"]),
    cancelledItems: boundedCount(source["cancelledItems"]),
    pendingItems: boundedCount(source["pendingItems"]),
    allSucceeded: flag(source["allSucceeded"]),
    settled: flag(source["settled"]),
    sourceScope: optionalText(source["sourceScope"], 1024),
    targetScope: optionalText(source["targetScope"], 1024),
    configurationSnapshotId: optionalText(
      source["configurationSnapshotId"],
      128,
    ),
  };
}

/** Normalize one bounded page of a library's own ordinary work. */
export function normalizeLibraryFileOperationPage(
  payload: unknown,
  kind: DirectCommandLibraryKind,
  libraryId: string,
): LibraryFileOperationPage {
  const source = recordOf(payload);
  if (source["libraryKind"] !== kind) fail();
  readIdentity(source, kind, libraryId);
  const items = source["items"];
  if (!Array.isArray(items)) fail();
  if (source["sideEffects"] !== "none") fail();
  return {
    libraryKind: kind,
    libraryId,
    items: items.map((item) => readEntry(item, kind, libraryId)),
    limit: boundedCount(source["limit"]),
    total: boundedCount(source["total"]),
    hasNext: flag(source["hasNext"]),
    hasPrevious: flag(source["hasPrevious"]),
    previousCursor: optionalText(source["previousCursor"], 512),
    nextCursor: optionalText(source["nextCursor"], 512),
  };
}

/**
 * The exact `source`/`destination` facts of one selected operation.
 *
 * A direct command has one source identity (and, for a creation, the created
 * entry as its target); a Copy/Move names both endpoints; a Delete has no
 * destination to invent.  Only recorded evidence is published — a missing
 * value stays `null` and is surfaced as unavailable rather than guessed.
 */
export interface LibraryFileOperationDetail extends LibraryFileOperationEntry {
  readonly libraryKind: DirectCommandLibraryKind;
  readonly libraryId: string;
  readonly nextAction: string | null;
  readonly durableState: string | null;
  readonly effectCertainty: string | null;
  readonly items: readonly LibraryFileOperationItem[];
  /** How many admitted items this operation really owns (all pages). */
  readonly itemTotal: number;
  readonly itemsTruncated: boolean;
  /** The exact durable position of the next item page, when one exists. */
  readonly nextCursor: string | null;
  readonly lifecycle: LifecycleProjection | null;
}

const OPERATION_EFFECT_CERTAINTIES = [
  "none",
  "verified_complete",
  "uncertain",
  "unknown",
  "partial",
] as const;

/** The closed set of recorded child-entry statuses. */
const CHILD_STATUSES: Readonly<Record<string, true>> = {
  SUCCESS: true,
  PARTIAL: true,
  FAILED: true,
  SKIPPED: true,
  CANCELLED: true,
  UNCERTAIN: true,
  PAUSED: true,
  RUNNING: true,
  QUEUED: true,
};

/** The closed set of recorded child-entry effects. */
const CHILD_EFFECTS: Readonly<Record<string, true>> = {
  transferred: true,
  skipped: true,
  partial: true,
  uncertain: true,
  retained: true,
  in_progress: true,
};

const OPERATION_DURABLE_STATES = [
  "mutation_effect_uncertain",
  "task_completed",
  "task_partial_success",
  "task_failed",
  "task_cancelled",
  "task_paused",
  "task_in_progress",
  "no_admitted_item",
] as const;

function optionalEnum(
  value: unknown,
  allowed: readonly string[],
): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string" || !allowed.includes(value)) fail();
  return value;
}

function readFailureEvidence(
  value: unknown,
): LibraryFileOperationFailure | null {
  if (value === null || value === undefined) return null;
  const source = recordOf(value);
  return {
    category: boundedText(source["category"], 64),
    message: boundedText(source["message"], 256),
    durableState: boundedText(source["durableState"], 256),
    sideEffects: boundedText(source["sideEffects"], 256),
    retrySafe: flag(source["retrySafe"]),
    nextAction: boundedText(source["nextAction"], 256),
    retryCategory: optionalText(source["retryCategory"], 64),
  };
}

/**
 * One recorded child entry.
 *
 * The vocabulary is closed on purpose: an unknown child status or effect means
 * the document is malformed, and the dialog must not invent a meaning for an
 * entry whose real effect it cannot name.
 */
function readChild(value: unknown): LibraryFileOperationChild {
  const source = recordOf(value);
  const status = boundedText(source["status"], 32);
  if (!(status in CHILD_STATUSES)) fail();
  const effect = boundedText(source["effect"], 32);
  if (!(effect in CHILD_EFFECTS)) fail();
  const checkpoints = source["checkpoints"];
  if (!Array.isArray(checkpoints) || checkpoints.length > 16) fail();
  return {
    path: boundedText(source["path"], 4096),
    destination: optionalText(source["destination"], 4096) ?? "",
    status,
    effect,
    checkpoints: checkpoints.map((checkpoint) => boundedText(checkpoint, 256)),
    failure: readFailureEvidence(source["failure"]),
  };
}

function readChildren(value: unknown): readonly LibraryFileOperationChild[] {
  if (value === null || value === undefined) return [];
  if (!Array.isArray(value) || value.length > 512) fail();
  return value.map(readChild);
}

function readItem(value: unknown): LibraryFileOperationItem {
  const source = recordOf(value);
  const effects = source["knownEffects"];
  if (!Array.isArray(effects) || effects.length > 64) fail();
  return {
    itemId: boundedText(source["itemId"], 128),
    path: boundedText(source["path"], 4096),
    destination: optionalText(source["destination"], 4096) ?? "",
    status: boundedText(source["status"], 32),
    stage: optionalText(source["stage"], 64),
    attempts: boundedCount(source["attempts"]),
    effect: boundedText(source["effect"], 32),
    effectCertainty: boundedText(source["effectCertainty"], 32),
    knownEffects: effects.map((effect) => boundedText(effect, 256)),
    children: readChildren(source["children"]),
    childrenTruncated: source["childrenTruncated"] === true,
    failure: readFailureEvidence(source["failure"]),
    nextAction: boundedText(source["nextAction"], 256),
  };
}

function optionalLifecycle(value: unknown): LifecycleProjection | null {
  // The lifecycle projection is normalized by its own module against the exact
  // Task; this read passes it through untouched so a malformed projection is
  // rejected there rather than being silently dropped here.
  if (value === null || value === undefined) return null;
  return value as LifecycleProjection;
}

export function normalizeLibraryFileOperationDetail(
  payload: unknown,
  kind: DirectCommandLibraryKind,
  libraryId: string,
  taskId: string,
): LibraryFileOperationDetail {
  const source = recordOf(payload);
  const entry = readEntry(source, kind, libraryId);
  if (entry.taskId !== taskId) fail();
  const rawItems = source["items"];
  if (rawItems !== undefined && !Array.isArray(rawItems)) fail();
  const items = (rawItems ?? []).map(readItem);
  if (items.length > 100) fail();
  const rawTotal = source["itemTotal"];
  const itemTotal =
    rawTotal === undefined ? entry.totalItems : boundedCount(rawTotal);
  if (itemTotal < items.length) fail();
  if (itemTotal !== entry.totalItems) {
    // The item population is the durable TaskItem count the operation itself
    // reports; a page that contradicts it is malformed, never a truncation.
    fail();
  }
  return {
    ...entry,
    libraryKind: kind,
    libraryId,
    nextAction: optionalText(source["nextAction"], 1024),
    durableState: optionalEnum(
      source["durableState"],
      OPERATION_DURABLE_STATES,
    ),
    effectCertainty: optionalEnum(
      source["effectCertainty"],
      OPERATION_EFFECT_CERTAINTIES,
    ),
    items,
    itemTotal,
    itemsTruncated: source["itemsTruncated"] === true,
    nextCursor: optionalText(source["nextCursor"], 512),
    lifecycle: optionalLifecycle(source["lifecycle"]),
  };
}

/**
 * The proven ordinary origin of one Task deep link.
 *
 * The backend resolves the originating *kind* from the Task's own durable
 * command, so one read answers for either library kind and the caller never
 * has to guess which page to open.  The published kind is therefore part of
 * the result rather than an input the frontend asserts.
 */
export type LibraryFileOperationOrigin =
  | {
      readonly matched: true;
      readonly taskId: string;
      readonly libraryKind: DirectCommandLibraryKind;
      readonly libraryId: string;
      readonly path: string | null;
    }
  | {
      readonly matched: false;
      readonly taskId: string;
      readonly reason: string;
      readonly nextAction: string | null;
    };

export function normalizeLibraryFileOperationOrigin(
  payload: unknown,
): LibraryFileOperationOrigin {
  const source = recordOf(payload);
  if (source["sideEffects"] !== "none") fail();
  const taskId = boundedText(source["taskId"], 128);
  if (source["matched"] === false) {
    return {
      matched: false,
      taskId,
      reason: boundedText(source["reason"], 64),
      nextAction: optionalText(source["nextAction"], 512),
    };
  }
  if (source["matched"] !== true) fail();
  const kind = source["libraryKind"];
  if (kind !== "resource" && kind !== "media") fail();
  const libraryId = boundedText(source["libraryId"], 256);
  readIdentity(source, kind, libraryId);
  return {
    matched: true,
    taskId,
    libraryKind: kind,
    libraryId,
    path: optionalText(source["path"], 4096),
  };
}

export interface LibraryFileOperationOriginEntry {
  readonly libraryKind: DirectCommandLibraryKind;
  readonly libraryId: string;
}

export interface LibraryFileOperationOrigins {
  readonly libraryKind: DirectCommandLibraryKind;
  readonly items: readonly LibraryFileOperationOriginEntry[];
  readonly total: number;
  readonly truncated: boolean;
}

/**
 * Normalize the bounded index of one kind's durable ordinary-work origins.
 *
 * A document claiming the other kind, a split identity or an item outside the
 * kind's own single identity field fails closed: the page must never offer a
 * selector entry that would inspect a foreign kind's work.
 */
export function normalizeLibraryFileOperationOrigins(
  payload: unknown,
  kind: DirectCommandLibraryKind,
): LibraryFileOperationOrigins {
  const source = recordOf(payload);
  if (source["sideEffects"] !== "none") fail();
  if (source["libraryKind"] !== kind) fail();
  const raw = source["items"];
  if (!Array.isArray(raw) || raw.length > 200) fail();
  const items = raw.map((value) => {
    const entry = recordOf(value);
    if (entry["libraryKind"] !== kind) fail();
    const libraryId = boundedText(entry["libraryId"], 256);
    readIdentity(entry, kind, libraryId);
    return { libraryKind: kind, libraryId } as const;
  });
  return {
    libraryKind: kind,
    items,
    total: boundedCount(source["total"]),
    truncated: flag(source["truncated"]),
  };
}

/**
 * The honest presentation of one entry's progress and outcome.
 *
 * Only a terminal Task whose every admitted item really succeeded says
 * "completed"; anything else names what is known, what is still pending and
 * what is uncertain.  Successful siblings are never hidden behind a failed one.
 */
export function libraryOperationStateLabel(
  entry: LibraryFileOperationEntry,
): string {
  if (entry.settled && entry.allSucceeded) return "已完成";
  if (!entry.terminal) {
    if (entry.pauseRequested) {
      return `暂停请求已记录，等待安全边界（已结算 ${entry.settledItems}/${entry.totalItems} 项）`;
    }
    if (entry.status === "paused") {
      return `已暂停（已结算 ${entry.settledItems}/${entry.totalItems} 项）`;
    }
    if (entry.status === "pending") {
      return `排队等待 Worker（已结算 ${entry.settledItems}/${entry.totalItems} 项）`;
    }
    return `执行中（已结算 ${entry.settledItems}/${entry.totalItems} 项）`;
  }
  switch (entry.status) {
    case "completed":
      // A terminal Task with a non-successful item is not "completed".
      return entry.allSucceeded ? "已完成" : "已完成，但存在未成功项目";
    case "partial_success":
      return `部分成功（成功 ${entry.succeededItems} 项，失败 ${entry.failedItems} 项）`;
    case "failed":
      return `未完成（失败 ${entry.failedItems} 项）`;
    case "cancelled":
      return "已取消";
    default:
      return entry.status;
  }
}

/** Whether this entry still has independently reviewable per-item outcomes. */
export function libraryOperationHasProgress(
  entry: LibraryFileOperationEntry,
): boolean {
  return !entry.terminal || entry.failedItems > 0 || entry.pendingItems > 0;
}

/** Bounded operator wording for one item's factual disposition. */
export const LIBRARY_OPERATION_ITEM_STATUS_LABELS: Readonly<
  Record<string, string>
> = {
  SUCCESS: "成功",
  PARTIAL: "部分完成",
  FAILED: "失败",
  SKIPPED: "已跳过",
  CANCELLED: "已取消",
  PAUSED: "已暂停",
  RUNNING: "执行中",
  QUEUED: "排队中",
  UNCERTAIN: "效果不确定",
};

/** Bounded operator wording for one item's known net effect. */
export const LIBRARY_OPERATION_EFFECT_LABELS: Readonly<Record<string, string>> =
  {
    transferred: "已完成变更",
    skipped: "未修改",
    partial: "部分完成",
    uncertain: "效果不确定",
    retained: "来源保留",
    in_progress: "尚未完成",
  };

/** Bounded operator wording for a bounded effect-certainty value. */
export const LIBRARY_OPERATION_CERTAINTY_LABELS: Readonly<
  Record<string, string>
> = {
  verified_complete: "已核实完成",
  partial: "部分已变更（其余尚未完成）",
  uncertain: "效果不确定",
  none: "无变更",
  unknown: "效果未知",
};
