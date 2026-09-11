/**
 * Frontend-owned bounded Preview entity for the Operations workspace.
 *
 * The Python contract (`POST /api/v1/operations/previews`,
 * `GET /api/v1/operations/previews/{previewId}`) returns the bounded,
 * secret-free preview document: no fingerprint, no configuration digest,
 * no raw provider payload. Preview is visibly DryRun/analysis, produces
 * no Storage mutation and no execution authority.
 *
 * Normalization is deliberately fail-closed: an unknown status, a
 * coerced boolean or an inconsistent zero-mutation flag makes the whole
 * response malformed.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

export const PREVIEW_STATUSES = [
  "pending",
  "running",
  "completed",
  "partial",
  "failed",
] as const;
export type PreviewStatus = (typeof PREVIEW_STATUSES)[number];

/** Bounded per-item preview findings. */
export interface ManualPreviewItemModel {
  readonly itemId: string;
  readonly sourceStorageId: string;
  readonly sourcePath: string;
  readonly recognitionType: string | null;
  readonly title: string | null;
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly targetPath: string | null;
  readonly organizePolicy: string | null;
  readonly status: string;
  readonly failure: {
    readonly category: string;
    readonly message: string;
    readonly nextAction: string;
  } | null;
}

/** Bounded preview aggregate document. */
export interface ManualPreviewModel {
  readonly previewId: string;
  readonly intentId: string | null;
  readonly actor: string;
  readonly intentVersion: number | null;
  readonly status: PreviewStatus;
  readonly current: boolean;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly nextAction: string | null;
  readonly sideEffects: string;
  readonly zeroMutation: boolean;
  readonly executionState: string | null;
  readonly truncated: boolean;
  readonly scope: {
    readonly scopeKind: string;
    readonly scopeId: string;
  };
  readonly scopeKind: string;
  readonly scopeId: string;
  readonly selection: string | null;
  readonly configurationSnapshotId: string | null;
  readonly items: readonly ManualPreviewItemModel[];
}

export class PreviewNormalizationError extends Error {
  constructor() {
    super("preview response did not match the expected contract");
    this.name = "PreviewNormalizationError";
  }
}

function fail(): never {
  throw new PreviewNormalizationError();
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

function flag(source: Record<string, unknown>, field: string): boolean {
  try {
    return normalizeBoolean(source[field], field);
  } catch {
    return fail();
  }
}

function normalizePreviewFailure(
  value: unknown,
): ManualPreviewItemModel["failure"] {
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

function normalizePreviewItem(value: unknown): ManualPreviewItemModel {
  const source = readRecord(value, "preview_item");
  try {
    return {
      itemId: text(source, "itemId"),
      sourceStorageId: text(source, "sourceStorageId"),
      sourcePath: text(source, "sourcePath"),
      recognitionType: optionalText(source, "recognitionType"),
      title: optionalText(source, "title"),
      provider: optionalText(source, "provider"),
      providerId: optionalText(source, "providerId"),
      targetPath: optionalText(source, "targetPath"),
      organizePolicy: optionalText(source, "organizePolicy"),
      status: text(source, "status"),
      failure: normalizePreviewFailure(source["failure"]),
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
  try {
    return normalizeBoundedCount(raw, field);
  } catch {
    return fail();
  }
}

export function normalizeManualPreview(payload: unknown): ManualPreviewModel {
  const source = readRecord(payload, "preview");
  let status: PreviewStatus;
  try {
    status = normalizeEnum(source["status"], "status", PREVIEW_STATUSES);
  } catch {
    return fail();
  }

  const rawItems = source["items"];
  if (!Array.isArray(rawItems)) {
    fail();
  }

  try {
    return {
      previewId: text(source, "previewId"),
      intentId: optionalText(source, "intentId"),
      actor: text(source, "actor"),
      intentVersion: optionalCount(source, "intentVersion"),
      status,
      current: flag(source, "current"),
      createdAt: text(source, "createdAt"),
      updatedAt: text(source, "updatedAt"),
      nextAction: optionalText(source, "nextAction"),
      sideEffects: text(source, "sideEffects"),
      zeroMutation: flag(source, "zeroMutation"),
      executionState: optionalText(source, "executionState"),
      truncated: flag(source, "truncated"),
      scope: (() => {
        const scopeRaw = readRecord(source["scope"], "scope");
        return {
          scopeKind: text(scopeRaw, "scopeKind"),
          scopeId: text(scopeRaw, "scopeId"),
        };
      })(),
      scopeKind: text(source, "scopeKind"),
      scopeId: text(source, "scopeId"),
      selection: optionalText(source, "selection"),
      configurationSnapshotId: optionalText(source, "configurationSnapshotId"),
      items: rawItems.map((item) => normalizePreviewItem(item)),
    };
  } catch {
    return fail();
  }
}

export function normalizeManualPreviewItem(
  payload: unknown,
): ManualPreviewItemModel {
  return normalizePreviewItem(payload);
}

/**
 * Bounded preview list page returned by the list endpoint.
 */
export interface ManualPreviewListPage {
  readonly items: readonly ManualPreviewModel[];
  readonly limit: number;
  readonly total: number;
  readonly scopeKind: string;
  readonly scopeId: string;
}

export function normalizeManualPreviewListPage(
  payload: unknown,
): ManualPreviewListPage {
  const source = readRecord(payload, "preview_list");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems)) {
    fail();
  }
  try {
    return {
      items: rawItems.map((item) =>
        normalizeManualPreview(readRecord(item, "preview")),
      ),
      limit: normalizeBoundedCount(source["limit"], "limit"),
      total: normalizeBoundedCount(source["total"], "total"),
      scopeKind: text(source, "scopeKind"),
      scopeId: text(source, "scopeId"),
    };
  } catch {
    return fail();
  }
}
