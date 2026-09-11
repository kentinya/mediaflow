/**
 * Frontend-owned bounded Preview entity for the Operations workspace.
 *
 * The Python contract (`POST /api/v1/operations/previews`,
 * `GET /api/v1/operations/previews/{previewId}`,
 * `GET /api/v1/operations/previews`) returns one exact bounded preview
 * document produced by `manual_preview_operator_document`: the persisted
 * analysis findings are preserved, while every fingerprint/digest value,
 * occurrence identity, raw executor input and absolute host root is projected
 * away by the backend. Preview is visibly DryRun/analysis, produces no Storage
 * mutation and no execution authority.
 *
 * Normalization is deliberately fail-closed: an unknown aggregate status, a
 * coerced boolean or an inconsistent zero-mutation flag makes the whole
 * response malformed. Optional findings are modelled as `null`, never
 * fabricated.
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

export const PREVIEW_STATUSES = [
  "previewed",
  "partial",
  "blocked",
  "failed",
  "stale",
  "unavailable",
  "cancelled",
] as const;
export type PreviewStatus = (typeof PREVIEW_STATUSES)[number];

export const PREVIEW_SCOPE_KINDS = ["file", "resourceLibrary"] as const;

/** The execution states this Task's backend can truthfully mean. */
export const PREVIEW_EXECUTION_STATES = [
  "not_available_in_this_task",
  "ready_for_explicit_authorization",
] as const;

/** Bounded failure evidence; never a raw durable error string. */
export interface PreviewFailureModel {
  readonly category: string;
  readonly message: string;
  readonly nextAction: string;
}

/** One planned sidecar attachment with a bounded operator label. */
export interface ManualPreviewAttachmentModel {
  readonly type: string | null;
  readonly operation: string | null;
  readonly suffix: string | null;
  readonly language: string | null;
  readonly filename: string | null;
  readonly storageId: string | null;
}

/** One persisted conflict finding. */
export interface ManualPreviewConflictModel {
  readonly type: string | null;
  readonly source: string | null;
  readonly destination: string | null;
  readonly details: string | null;
}

/** The declared/required Storage capability evidence for one plan. */
export interface ManualPreviewCapabilitiesModel {
  readonly verdict: string | null;
  readonly required: readonly string[];
  readonly declared: readonly string[];
  readonly missing: readonly string[];
}

/** The MediaLibrary-relative proposed target. */
export interface ManualPreviewDestinationModel {
  readonly storageId: string | null;
  readonly relativePath: string | null;
  readonly filename: string | null;
}

/** Bounded per-item preview findings. */
export interface ManualPreviewItemModel {
  readonly itemId: string;
  readonly previewItemId: string;
  readonly position: number;
  readonly stage: string;
  readonly status: string;
  readonly current: boolean;
  readonly truncated: boolean;
  readonly zeroMutation: boolean;
  readonly executionState: string | null;
  readonly nextAction: string | null;
  readonly failure: PreviewFailureModel | null;
  readonly sourceStorageId: string | null;
  readonly sourcePath: string | null;
  readonly sourceFilename: string | null;
  readonly resourceLibraryId: string | null;
  readonly recognitionType: string | null;
  readonly title: string | null;
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly targetStorageId: string | null;
  readonly targetPath: string | null;
  readonly organizePolicy: string | null;
  readonly planStatus: string | null;
  readonly destination: ManualPreviewDestinationModel | null;
  readonly attachments: readonly ManualPreviewAttachmentModel[];
  readonly conflicts: readonly ManualPreviewConflictModel[];
  readonly warnings: readonly string[];
  readonly capabilities: ManualPreviewCapabilitiesModel | null;
}

/** The durable selection state of one Preview. */
export interface ManualPreviewSelectionModel {
  readonly selectedItemIds: readonly string[];
  readonly unselectedItemIds: readonly string[];
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
  readonly failure: PreviewFailureModel | null;
  readonly sideEffects: string;
  readonly zeroMutation: boolean;
  readonly executionState: string | null;
  readonly truncated: boolean;
  readonly scope: {
    readonly scopeKind: string;
    readonly scopeId: string;
    readonly itemCount: number;
  } | null;
  readonly scopeKind: string | null;
  readonly scopeId: string | null;
  readonly selection: ManualPreviewSelectionModel;
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

function stringList(source: Record<string, unknown>, field: string): string[] {
  try {
    return [...normalizeTextArray(source[field], field, 100)];
  } catch {
    return fail();
  }
}

function optionalRecord(
  value: unknown,
  field: string,
): Record<string, unknown> | null {
  if (value === null || value === undefined) {
    return null;
  }
  return readRecord(value, field);
}

function normalizePreviewFailure(value: unknown): PreviewFailureModel | null {
  const source = optionalRecord(value, "failure");
  if (source === null) {
    return null;
  }
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

function normalizeExecutionState(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  try {
    return normalizeEnum(raw, field, PREVIEW_EXECUTION_STATES);
  } catch {
    return fail();
  }
}

function normalizeAttachment(value: unknown): ManualPreviewAttachmentModel {
  const source = readRecord(value, "plan.attachments[]");
  try {
    return {
      type: optionalText(source, "type"),
      operation: optionalText(source, "operation"),
      suffix: optionalText(source, "suffix"),
      language: optionalText(source, "language"),
      filename: optionalText(source, "filename"),
      storageId: optionalText(source, "storageId"),
    };
  } catch {
    return fail();
  }
}

function normalizeConflict(value: unknown): ManualPreviewConflictModel {
  const source = readRecord(value, "plan.conflicts[]");
  try {
    return {
      type: optionalText(source, "type"),
      source: optionalText(source, "source"),
      destination: optionalText(source, "destination"),
      details: optionalText(source, "details"),
    };
  } catch {
    return fail();
  }
}

function normalizeCapabilities(
  value: unknown,
): ManualPreviewCapabilitiesModel | null {
  const source = optionalRecord(value, "plan.capabilities");
  if (source === null) {
    return null;
  }
  try {
    return {
      verdict: optionalText(source, "verdict"),
      required: stringList(source, "required"),
      declared: stringList(source, "declared"),
      missing: stringList(source, "missing"),
    };
  } catch {
    return fail();
  }
}

function normalizeDestination(
  value: unknown,
): ManualPreviewDestinationModel | null {
  const source = optionalRecord(value, "plan.destination");
  if (source === null) {
    return null;
  }
  try {
    return {
      storageId: optionalText(source, "storageId"),
      relativePath: optionalText(source, "relativePath"),
      filename: optionalText(source, "filename"),
    };
  } catch {
    return fail();
  }
}

function normalizePreviewItem(value: unknown): ManualPreviewItemModel {
  const source = readRecord(value, "preview_item");
  const sourceRecord = readRecord(source["source"], "item.source");
  readRecord(source["choice"], "item.choice");
  const plan = optionalRecord(source["plan"], "item.plan");

  const rawAttachments = plan?.["attachments"] ?? [];
  if (!Array.isArray(rawAttachments)) {
    fail();
  }
  const rawConflicts = plan?.["conflicts"] ?? [];
  if (!Array.isArray(rawConflicts)) {
    fail();
  }
  const rawWarnings = plan?.["warnings"] ?? [];
  if (!Array.isArray(rawWarnings)) {
    fail();
  }

  try {
    const destination = normalizeDestination(plan?.["destination"] ?? null);
    const policies = optionalRecord(
      plan?.["policies"] ?? null,
      "plan.policies",
    );
    const mediaIdentity = optionalRecord(
      plan?.["mediaIdentity"] ?? null,
      "plan.mediaIdentity",
    );
    return {
      itemId: text(source, "itemId"),
      previewItemId: text(source, "previewItemId"),
      position: normalizeBoundedCount(source["position"], "position"),
      stage: text(source, "stage"),
      status: text(source, "status"),
      current: flag(source, "current"),
      truncated: flag(source, "truncated"),
      zeroMutation: flag(source, "zeroMutation"),
      executionState: normalizeExecutionState(source, "executionState"),
      nextAction: optionalText(source, "nextAction"),
      failure: normalizePreviewFailure(source["failure"]),
      sourceStorageId: optionalText(sourceRecord, "storageId"),
      sourcePath: optionalText(sourceRecord, "path"),
      sourceFilename: optionalText(sourceRecord, "filename"),
      resourceLibraryId: optionalText(sourceRecord, "resourceLibraryId"),
      recognitionType:
        plan === null ? null : optionalText(plan, "recognitionType"),
      title:
        mediaIdentity === null ? null : optionalText(mediaIdentity, "title"),
      provider:
        mediaIdentity === null ? null : optionalText(mediaIdentity, "provider"),
      providerId:
        mediaIdentity === null
          ? null
          : optionalText(mediaIdentity, "providerId"),
      targetStorageId: destination?.storageId ?? null,
      targetPath: destination?.relativePath ?? null,
      organizePolicy:
        policies === null ? null : optionalText(policies, "organizePolicyId"),
      planStatus: plan === null ? null : optionalText(plan, "planStatus"),
      destination,
      attachments: rawAttachments.map((item) => normalizeAttachment(item)),
      conflicts: rawConflicts.map((item) => normalizeConflict(item)),
      warnings: rawWarnings.map((item, index) =>
        normalizeBoundedText(item, `plan.warnings[${index}]`),
      ),
      capabilities: normalizeCapabilities(plan?.["capabilities"] ?? null),
    };
  } catch {
    return fail();
  }
}

function normalizeSelection(value: unknown): ManualPreviewSelectionModel {
  const source = readRecord(value, "selection");
  return {
    selectedItemIds: stringList(source, "selectedItemIds"),
    unselectedItemIds: stringList(source, "unselectedItemIds"),
  };
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
  const scope = optionalRecord(source["scope"] ?? null, "scope");
  const scopeKind = optionalText(source, "scopeKind");
  const scopeId = optionalText(source, "scopeId");
  if ((scopeKind === null) !== (scopeId === null)) {
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
      failure: normalizePreviewFailure(source["failure"]),
      sideEffects: text(source, "sideEffects"),
      zeroMutation: flag(source, "zeroMutation"),
      executionState: normalizeExecutionState(source, "executionState"),
      truncated: flag(source, "truncated"),
      scope:
        scope === null
          ? null
          : {
              scopeKind: text(scope, "scopeKind"),
              scopeId: text(scope, "scopeId"),
              itemCount: normalizeBoundedCount(scope["itemCount"], "itemCount"),
            },
      scopeKind,
      scopeId,
      selection: normalizeSelection(source["selection"]),
      configurationSnapshotId: optionalText(source, "configurationSnapshotId"),
      items: rawItems.map((item) => normalizePreviewItem(item)),
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
      items: rawItems.map((item) => normalizeManualPreview(item)),
      limit: normalizeBoundedCount(source["limit"], "limit"),
      total: normalizeBoundedCount(source["total"], "total"),
      scopeKind: text(source, "scopeKind"),
      scopeId: text(source, "scopeId"),
    };
  } catch {
    return fail();
  }
}
