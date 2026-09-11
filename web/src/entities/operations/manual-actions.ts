/**
 * Frontend-owned manual action matrix entity.
 *
 * The backend computes action availability for the exact authenticated
 * principal, current source/scope and runtime readiness. The frontend
 * never infers authority, source validity, capability or Active
 * configuration from route state alone.
 *
 * Normalization is fail-closed: an unknown availability flag, a missing
 * action or an inconsistent matrix is malformed data.
 */

import {
  normalizeBoundedText,
  normalizeBoolean,
  normalizeEnum,
  normalizeOptionalText,
  normalizeBoundedCount,
  readRecord,
} from "../shared/normalize";

export const MANUAL_ACTION_SCOPES = ["file", "resourceLibrary"] as const;
export type ManualActionScope = (typeof MANUAL_ACTION_SCOPES)[number];

export interface ManualAction {
  readonly available: boolean;
  readonly reason: string | null;
  readonly method: string | null;
  readonly path: string | null;
  readonly nextAction: string | null;
}

export interface ManualActionSource {
  readonly fileId: string | null;
  readonly storageId: string | null;
  readonly resourceLibraryId: string | null;
  readonly path: string | null;
  readonly filename: string | null;
  readonly extension: string | null;
  readonly sizeBytes: number | null;
  readonly occurrenceState: string | null;
  readonly scanStatus: string | null;
}

export interface ManualActionMatrixModel {
  readonly scopeKind: ManualActionScope;
  readonly fileId: string | null;
  readonly resourceLibraryId: string | null;
  readonly source: ManualActionSource;
  readonly runtime: {
    readonly ready: boolean;
    readonly condition: string;
    readonly nextAction: string | null;
  };
  readonly actions: {
    readonly scan: ManualAction;
    readonly preview: ManualAction;
  };
  readonly limits: {
    readonly previewMaxItems: number | null;
  };
}

export class ManualActionsNormalizationError extends Error {
  constructor() {
    super("manual actions response did not match the expected contract");
    this.name = "ManualActionsNormalizationError";
  }
}

function fail(): never {
  throw new ManualActionsNormalizationError();
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

function normalizeAction(value: unknown): ManualAction {
  const source = readRecord(value, "action");
  try {
    return {
      available: flag(source, "available"),
      reason: optionalText(source, "reason"),
      method: optionalText(source, "method"),
      path: optionalText(source, "path"),
      nextAction: optionalText(source, "nextAction"),
    };
  } catch {
    return fail();
  }
}

function normalizeActionSource(value: unknown): ManualActionSource {
  const source = readRecord(value, "source");
  try {
    return {
      fileId: optionalText(source, "fileId"),
      storageId: optionalText(source, "storageId"),
      resourceLibraryId: optionalText(source, "resourceLibraryId"),
      path: optionalText(source, "path"),
      filename: optionalText(source, "filename"),
      extension: optionalText(source, "extension"),
      sizeBytes: optionalCount(source, "sizeBytes"),
      occurrenceState: optionalText(source, "occurrenceState"),
      scanStatus: optionalText(source, "scanStatus"),
    };
  } catch {
    return fail();
  }
}

export function normalizeManualActionMatrix(
  payload: unknown,
): ManualActionMatrixModel {
  const source = readRecord(payload, "manual_action_matrix");
  let scopeKind: ManualActionScope;
  try {
    scopeKind = normalizeEnum(
      source["scopeKind"],
      "scopeKind",
      MANUAL_ACTION_SCOPES,
    );
  } catch {
    return fail();
  }

  const actionsRaw = readRecord(source["actions"], "actions");
  const scan = normalizeAction(actionsRaw["scan"]);
  const preview = normalizeAction(actionsRaw["preview"]);

  const runtimeRaw = readRecord(source["runtime"], "runtime");
  let runtimeCondition: string;
  try {
    runtimeCondition = text(runtimeRaw, "condition");
  } catch {
    return fail();
  }

  const limitsRaw = readRecord(source["limits"], "limits");

  try {
    return {
      scopeKind,
      fileId: optionalText(source, "fileId"),
      resourceLibraryId: optionalText(source, "resourceLibraryId"),
      source: normalizeActionSource(source["source"]),
      runtime: {
        ready: flag(runtimeRaw, "ready"),
        condition: runtimeCondition,
        nextAction: optionalText(runtimeRaw, "nextAction"),
      },
      actions: { scan, preview },
      limits: {
        previewMaxItems: optionalCount(limitsRaw, "previewMaxItems"),
      },
    };
  } catch {
    return fail();
  }
}
