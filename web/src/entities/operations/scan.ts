/**
 * Frontend-owned bounded Scan entity for the Operations workspace.
 *
 * The Python contract (`POST /api/v1/operations/scans`,
 * `GET /api/v1/operations/scans/{taskId}`) returns the bounded, secret-free
 * scan document: no fingerprint, no configuration digest, no raw provider
 * payload. Normalization is deliberately fail-closed: a status outside the
 * modelled set, a coerced boolean or a progress pair that cannot describe
 * one Scan document makes the whole response malformed.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

export const SCAN_STATUSES = [
  "pending",
  "running",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
] as const;
export type ScanStatus = (typeof SCAN_STATUSES)[number];

export const SCAN_MODES = ["full", "incremental"] as const;
export type ScanMode = (typeof SCAN_MODES)[number];

/** Bounded per-item scan outcome. */
export interface ManualScanItemModel {
  readonly itemId: string;
  readonly storageId: string;
  readonly resourceLibraryId: string;
  readonly sourcePath: string;
  readonly status: string;
  readonly stage: string;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly failure: {
    readonly category: string;
    readonly message: string;
    readonly nextAction: string;
  } | null;
}

/** Bounded scan aggregate document. */
export interface ManualScanModel {
  readonly taskId: string;
  readonly scopeKind: string;
  readonly scopeId: string;
  readonly resourceLibraryId: string;
  readonly fileId: string | null;
  readonly storageId: string;
  readonly sourcePath: string;
  readonly mode: ScanMode | null;
  readonly status: ScanStatus;
  readonly configurationSnapshotId: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly cancellationRequested: boolean;
  readonly progress: {
    readonly total: number;
    readonly completed: number;
    readonly failed: number;
  };
  readonly errors: readonly string[];
  readonly reconciliationComplete: boolean;
  readonly failureStage: string | null;
  readonly knownEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string | null;
  readonly sideEffects: string;
  readonly items: readonly ManualScanItemModel[];
  readonly itemLimit: number | null;
  readonly itemCursor: string | null;
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

function normalizeScanFailure(value: unknown): ManualScanItemModel["failure"] {
  if (value === null || value === undefined) {
    return null;
  }
  const source = readRecord(value, "item.failure");
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

function normalizeScanItem(value: unknown): ManualScanItemModel {
  const source = readRecord(value, "scan_item");
  try {
    return {
      itemId: text(source, "itemId"),
      storageId: text(source, "storageId"),
      resourceLibraryId: text(source, "resourceLibraryId"),
      sourcePath: text(source, "sourcePath"),
      status: text(source, "status"),
      stage: text(source, "stage"),
      createdAt: text(source, "createdAt"),
      updatedAt: text(source, "updatedAt"),
      failure: normalizeScanFailure(source["failure"]),
    };
  } catch {
    return fail();
  }
}

export function normalizeManualScan(payload: unknown): ManualScanModel {
  const source = readRecord(payload, "scan");
  let status: ScanStatus;
  try {
    status = normalizeEnum(source["status"], "status", SCAN_STATUSES);
  } catch {
    return fail();
  }

  const progressRaw = readRecord(source["progress"], "progress");
  const total = count(progressRaw, "total");
  const completed = count(progressRaw, "completed");
  const failed = count(progressRaw, "failed");
  if (completed + failed > total) {
    fail();
  }

  let mode: ScanMode | null = null;
  if (source["mode"] !== null && source["mode"] !== undefined) {
    try {
      mode = normalizeEnum(source["mode"], "mode", SCAN_MODES);
    } catch {
      return fail();
    }
  }

  const rawItems = source["items"];
  if (!Array.isArray(rawItems)) {
    fail();
  }

  const errors = source["errors"];
  if (!Array.isArray(errors)) {
    fail();
  }

  try {
    return {
      taskId: text(source, "taskId"),
      scopeKind: text(source, "scopeKind"),
      scopeId: text(source, "scopeId"),
      resourceLibraryId: text(source, "resourceLibraryId"),
      fileId: optionalText(source, "fileId"),
      storageId: text(source, "storageId"),
      sourcePath: text(source, "sourcePath"),
      mode,
      status,
      configurationSnapshotId: optionalText(source, "configurationSnapshotId"),
      createdAt: text(source, "createdAt"),
      updatedAt: text(source, "updatedAt"),
      cancellationRequested: flag(source, "cancellationRequested"),
      progress: { total, completed, failed },
      errors: errors.map((e) => {
        if (typeof e !== "string") return fail();
        return e;
      }),
      reconciliationComplete: flag(source, "reconciliationComplete"),
      failureStage: optionalText(source, "failureStage"),
      knownEffects: text(source, "knownEffects"),
      retrySafe: flag(source, "retrySafe"),
      nextAction: optionalText(source, "nextAction"),
      sideEffects: text(source, "sideEffects"),
      items: rawItems.map((item) => normalizeScanItem(item)),
      itemLimit: optionalCount(source, "itemLimit"),
      itemCursor: optionalText(source, "itemCursor"),
    };
  } catch {
    return fail();
  }
}

export function normalizeManualScanItem(payload: unknown): ManualScanItemModel {
  return normalizeScanItem(payload);
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
