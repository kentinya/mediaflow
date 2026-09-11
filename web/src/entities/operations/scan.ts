/**
 * Frontend-owned bounded Scan entity for the Operations workspace.
 *
 * The Python contract (`POST /api/v1/operations/scans`,
 * `GET /api/v1/operations/scans/{taskId}`) returns one exact bounded scan
 * document produced by `manual_scan_operator_document`: no fingerprint, no
 * occurrence identity, no configuration digest, no absolute host path and no
 * raw durable error text. Both the admission response and the refreshable
 * detail use this same document shape, so a reload cannot see a different
 * contract than the submission.
 *
 * Normalization is deliberately fail-closed: an unknown status or mode, a
 * coerced boolean or a progress counter that is not a non-negative integer
 * makes the whole response malformed.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeEnumArray,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

export const SCAN_STATUSES = [
  "pending",
  "running",
  "paused",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
] as const;
export type ScanStatus = (typeof SCAN_STATUSES)[number];

export const SCAN_MODES = ["full", "incremental"] as const;
export type ScanMode = (typeof SCAN_MODES)[number];

export const SCAN_SCOPE_KINDS = ["file", "resourceLibrary"] as const;
export type ScanScopeKind = (typeof SCAN_SCOPE_KINDS)[number];

/** The per-file discovery states the scanner can durably record. */
export const SCAN_ITEM_STATUSES = [
  "discovered",
  "unstable",
  "ready",
  "ignored",
  "missing",
  "error",
] as const;
export type ScanItemStatus = (typeof SCAN_ITEM_STATUSES)[number];

/** The discovery change the scanner observed for one file. */
export const SCAN_ITEM_CHANGES = [
  "new",
  "modified",
  "unchanged",
  "missing",
] as const;

/** Bounded failure evidence; never a raw durable error string. */
export interface ScanFailureModel {
  readonly category: string;
  readonly message: string;
  readonly nextAction: string;
}

/** One bounded per-file Scan discovery error. */
export interface ScanErrorModel {
  readonly code: string;
  readonly path: string | null;
  readonly operation: string | null;
}

/** Bounded per-item scan outcome. */
export interface ManualScanItemModel {
  readonly itemId: string;
  readonly taskId: string;
  readonly storageId: string;
  readonly resourceLibraryId: string;
  readonly sourcePath: string;
  readonly fileId: string | null;
  readonly status: ScanItemStatus;
  readonly change: string | null;
  readonly stage: string;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly knownEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string | null;
  readonly failure: ScanFailureModel | null;
}

/** The real discovery counters the scanner durably records. */
export interface ManualScanProgressModel {
  readonly directoriesVisited: number;
  readonly filesVisited: number;
  readonly mediaCandidates: number;
  readonly ignored: number;
  readonly unstable: number;
  readonly errors: number;
}

/** One backend-advertised cooperative control for the exact durable state. */
export interface ManualScanCancelActionModel {
  readonly action: string;
  readonly label: string;
  readonly method: string;
  readonly path: string;
  readonly available: boolean;
  readonly unavailableReason: string | null;
  readonly nextAction: string | null;
  readonly durableOutcome: string;
  readonly sideEffects: string;
  readonly cooperative: boolean;
  readonly confirmationRequired: boolean;
  readonly retrySafe: boolean;
}

/** Bounded scan aggregate document. */
export interface ManualScanModel {
  readonly taskId: string;
  readonly scopeKind: ScanScopeKind;
  readonly scopeId: string;
  readonly resourceLibraryId: string;
  readonly fileId: string | null;
  readonly storageId: string | null;
  readonly sourcePath: string | null;
  readonly mode: ScanMode;
  readonly status: ScanStatus;
  readonly configurationSnapshotId: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly cancellationRequested: boolean;
  readonly progress: ManualScanProgressModel;
  readonly errors: readonly ScanErrorModel[];
  readonly reconciliationComplete: boolean;
  readonly failureStage: string | null;
  readonly knownEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string | null;
  readonly failure: ScanFailureModel | null;
  readonly sideEffects: string;
  readonly actions: {
    readonly cancel: ManualScanCancelActionModel;
  };
  readonly itemLimit: number | null;
  readonly itemsTruncated: boolean;
  readonly nextItemCursor: string | null;
  readonly previousItemCursor: string | null;
  readonly items: readonly ManualScanItemModel[];
}

export class ScanNormalizationError extends Error {
  constructor() {
    super("scan response did not match the expected contract");
    this.name = "ScanNormalizationError";
  }
}

function fail(): never {
  throw new ScanNormalizationError();
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

function normalizeScanFailure(value: unknown): ScanFailureModel | null {
  if (value === null || value === undefined) {
    return null;
  }
  const source = readRecord(value, "failure");
  try {
    return {
      category: text(source, "category"),
      message: text(source, "message"),
      nextAction: text(source, "nextAction"),
    };
  } catch {
    return fail();
  }
}

function normalizeScanError(value: unknown): ScanErrorModel {
  const source = readRecord(value, "scan_error");
  try {
    return {
      code: text(source, "code"),
      path: optionalText(source, "path"),
      operation: optionalText(source, "operation"),
    };
  } catch {
    return fail();
  }
}

function normalizeScanItem(value: unknown): ManualScanItemModel {
  const source = readRecord(value, "scan_item");
  let status: ScanItemStatus;
  let change: string | null;
  try {
    status = normalizeEnum(source["status"], "item.status", SCAN_ITEM_STATUSES);
    change =
      source["change"] === null || source["change"] === undefined
        ? null
        : normalizeEnum(source["change"], "item.change", SCAN_ITEM_CHANGES);
  } catch {
    return fail();
  }
  try {
    return {
      itemId: text(source, "itemId"),
      taskId: text(source, "taskId"),
      storageId: text(source, "storageId"),
      resourceLibraryId: text(source, "resourceLibraryId"),
      sourcePath: text(source, "sourcePath"),
      fileId: optionalText(source, "fileId"),
      status,
      change,
      stage: text(source, "stage"),
      createdAt: text(source, "createdAt"),
      updatedAt: text(source, "updatedAt"),
      knownEffects: text(source, "knownEffects"),
      retrySafe: flag(source, "retrySafe"),
      nextAction: optionalText(source, "nextAction"),
      failure: normalizeScanFailure(source["failure"]),
    };
  } catch {
    return fail();
  }
}

function normalizeCancelAction(value: unknown): ManualScanCancelActionModel {
  const source = readRecord(value, "actions.cancel");
  try {
    return {
      action: text(source, "action"),
      label: text(source, "label"),
      method: normalizeEnum(source["method"], "actions.cancel.method", [
        "POST",
      ] as const),
      path: text(source, "path"),
      available: flag(source, "available"),
      unavailableReason: optionalText(source, "unavailableReason"),
      nextAction: optionalText(source, "nextAction"),
      durableOutcome: text(source, "durableOutcome"),
      sideEffects: text(source, "sideEffects"),
      cooperative: flag(source, "cooperative"),
      confirmationRequired: flag(source, "confirmationRequired"),
      retrySafe: flag(source, "retrySafe"),
    };
  } catch {
    return fail();
  }
}

function optionalCount(
  source: Record<string, unknown>,
  field: string,
): number | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  return count(source, field);
}

export function normalizeManualScan(payload: unknown): ManualScanModel {
  const source = readRecord(payload, "scan");
  let status: ScanStatus;
  let scopeKind: ScanScopeKind;
  let mode: ScanMode;
  try {
    status = normalizeEnum(source["status"], "status", SCAN_STATUSES);
    scopeKind = normalizeEnum(
      source["scopeKind"],
      "scopeKind",
      SCAN_SCOPE_KINDS,
    );
    mode = normalizeEnum(source["mode"], "mode", SCAN_MODES);
  } catch {
    return fail();
  }

  const progressRaw = readRecord(source["progress"], "progress");
  const progress: ManualScanProgressModel = {
    directoriesVisited: count(progressRaw, "directoriesVisited"),
    filesVisited: count(progressRaw, "filesVisited"),
    mediaCandidates: count(progressRaw, "mediaCandidates"),
    ignored: count(progressRaw, "ignored"),
    unstable: count(progressRaw, "unstable"),
    errors: count(progressRaw, "errors"),
  };
  if (progress.mediaCandidates > progress.filesVisited) {
    fail();
  }

  const rawItems = source["items"];
  if (!Array.isArray(rawItems)) {
    fail();
  }
  const rawErrors = source["errors"];
  if (!Array.isArray(rawErrors)) {
    fail();
  }
  const actionsRaw = readRecord(source["actions"], "actions");

  try {
    return {
      taskId: text(source, "taskId"),
      scopeKind,
      scopeId: text(source, "scopeId"),
      resourceLibraryId: text(source, "resourceLibraryId"),
      fileId: optionalText(source, "fileId"),
      storageId: optionalText(source, "storageId"),
      sourcePath: optionalText(source, "sourcePath"),
      mode,
      status,
      configurationSnapshotId: optionalText(source, "configurationSnapshotId"),
      createdAt: text(source, "createdAt"),
      updatedAt: text(source, "updatedAt"),
      cancellationRequested: flag(source, "cancellationRequested"),
      progress,
      errors: rawErrors.map((error) => normalizeScanError(error)),
      reconciliationComplete: flag(source, "reconciliationComplete"),
      failureStage: optionalText(source, "failureStage"),
      knownEffects: text(source, "knownEffects"),
      retrySafe: flag(source, "retrySafe"),
      nextAction: optionalText(source, "nextAction"),
      failure: normalizeScanFailure(source["failure"]),
      sideEffects: text(source, "sideEffects"),
      actions: { cancel: normalizeCancelAction(actionsRaw["cancel"]) },
      itemLimit: optionalCount(source, "itemLimit"),
      itemsTruncated: flag(source, "itemsTruncated"),
      nextItemCursor: optionalText(source, "nextItemCursor"),
      previousItemCursor: optionalText(source, "previousItemCursor"),
      items: rawItems.map((item) => normalizeScanItem(item)),
    };
  } catch {
    return fail();
  }
}

export function normalizeManualScanItem(payload: unknown): ManualScanItemModel {
  return normalizeScanItem(payload);
}

/** The Scan item statuses the backend can publish, for display fallbacks. */
export function isTerminalScanStatus(status: ScanStatus): boolean {
  return (
    status === "completed" ||
    status === "partial_success" ||
    status === "failed" ||
    status === "cancelled"
  );
}

export function scanModesOf(payload: unknown): readonly ScanMode[] {
  try {
    return normalizeEnumArray(payload, "modes", SCAN_MODES);
  } catch {
    return [];
  }
}
