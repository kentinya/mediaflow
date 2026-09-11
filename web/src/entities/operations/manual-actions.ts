/**
 * Frontend-owned manual action matrix entity.
 *
 * The backend computes action availability for the exact authenticated
 * principal, current source/scope and runtime readiness, and it is also the
 * bounded discovery surface for the ResourceLibrary choices an operator may
 * select. The frontend never infers authority, source validity, capability or
 * Active configuration from route state alone.
 *
 * Normalization is fail-closed: an unknown availability flag, a missing action
 * or an inconsistent matrix is malformed data.
 */

import {
  normalizeBoundedText,
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeEnum,
  normalizeEnumArray,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";
import { SCAN_MODES, type ScanMode } from "./scan";

export const MANUAL_ACTION_SCOPES = ["file", "resourceLibrary"] as const;
export type ManualActionScope = (typeof MANUAL_ACTION_SCOPES)[number];

export interface ManualAction {
  readonly available: boolean;
  readonly reason: string | null;
  readonly method: string | null;
  readonly path: string | null;
  readonly nextAction: string | null;
  readonly modes: readonly ScanMode[];
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

/** One bounded ResourceLibrary choice the operator may select. */
export interface ManualResourceLibraryChoice {
  readonly resourceLibraryId: string;
  readonly storageId: string | null;
  readonly scanMode: string | null;
  readonly enabled: boolean;
  readonly reason: string | null;
}

export interface ManualActionMatrixModel {
  readonly scopeKind: ManualActionScope | null;
  readonly scopeId: string | null;
  readonly fileId: string | null;
  readonly resourceLibraryId: string | null;
  readonly selectionRequired: boolean;
  readonly source: ManualActionSource | null;
  readonly resourceLibraries: readonly ManualResourceLibraryChoice[];
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

function normalizeAction(value: unknown, field: string): ManualAction {
  const source = readRecord(value, field);
  const rawModes = source["modes"] ?? [];
  if (!Array.isArray(rawModes)) {
    fail();
  }
  try {
    return {
      available: flag(source, "available"),
      reason: optionalText(source, "reason"),
      method: optionalText(source, "method"),
      path: optionalText(source, "path"),
      nextAction: optionalText(source, "nextAction"),
      modes: normalizeEnumArray(rawModes, `${field}.modes`, SCAN_MODES),
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

function normalizeResourceLibraryChoice(
  value: unknown,
): ManualResourceLibraryChoice {
  const source = readRecord(value, "resourceLibraries[]");
  try {
    return {
      resourceLibraryId: text(source, "resourceLibraryId"),
      storageId: optionalText(source, "storageId"),
      scanMode: optionalText(source, "scanMode"),
      enabled: flag(source, "enabled"),
      reason: optionalText(source, "reason"),
    };
  } catch {
    return fail();
  }
}

export function normalizeManualActionMatrix(
  payload: unknown,
): ManualActionMatrixModel {
  const source = readRecord(payload, "manual_action_matrix");
  let scopeKind: ManualActionScope | null;
  try {
    scopeKind =
      source["scopeKind"] === null || source["scopeKind"] === undefined
        ? null
        : normalizeEnum(source["scopeKind"], "scopeKind", MANUAL_ACTION_SCOPES);
  } catch {
    return fail();
  }

  const actionsRaw = readRecord(source["actions"], "actions");
  const rawLibraries = source["resourceLibraries"] ?? [];
  if (!Array.isArray(rawLibraries)) {
    fail();
  }

  try {
    return {
      scopeKind,
      scopeId: optionalText(source, "scopeId"),
      fileId: optionalText(source, "fileId"),
      resourceLibraryId: optionalText(source, "resourceLibraryId"),
      selectionRequired: flag(source, "selectionRequired"),
      source:
        source["source"] === null || source["source"] === undefined
          ? null
          : normalizeActionSource(source["source"]),
      resourceLibraries: rawLibraries.map((item) =>
        normalizeResourceLibraryChoice(item),
      ),
      runtime: (() => {
        const runtimeRaw = readRecord(source["runtime"], "runtime");
        return {
          ready: flag(runtimeRaw, "ready"),
          condition: text(runtimeRaw, "condition"),
          nextAction: optionalText(runtimeRaw, "nextAction"),
        };
      })(),
      actions: {
        scan: normalizeAction(actionsRaw["scan"], "actions.scan"),
        preview: normalizeAction(actionsRaw["preview"], "actions.preview"),
      },
      limits: (() => {
        const limitsRaw = readRecord(source["limits"], "limits");
        return { previewMaxItems: optionalCount(limitsRaw, "previewMaxItems") };
      })(),
    };
  } catch {
    return fail();
  }
}
