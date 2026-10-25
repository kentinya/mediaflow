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
  readonly pendingItems: number;
  readonly allSucceeded: boolean;
  readonly settled: boolean;
  readonly sourceScope: string | null;
  readonly targetScope: string | null;
  readonly configurationSnapshotId: string | null;
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
  readonly lifecycle: LifecycleProjection | null;
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
  return {
    ...entry,
    libraryKind: kind,
    libraryId,
    nextAction: optionalText(source["nextAction"], 1024),
    durableState: optionalText(source["durableState"], 128),
    lifecycle: optionalLifecycle(source["lifecycle"]),
  };
}

/** The proven ordinary origin of one Task deep link. */
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
  kind: DirectCommandLibraryKind,
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
  if (source["libraryKind"] !== kind) fail();
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
