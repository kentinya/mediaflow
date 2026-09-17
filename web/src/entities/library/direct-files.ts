/**
 * Frontend models for the Files direct file-command journey.
 *
 * The models cover the bounded text open/save evidence, the bounded Delete
 * impact summary and the durable direct-command result.  Every normalizer is
 * strict and secret-free: unexpected shapes fail closed instead of leaking
 * raw server data into the UI.
 */

export const MAX_TEXT_BYTES = 512 * 1024;

/** Allowlisted bounded-text extensions; mirrors the backend admission list. */
export const TEXT_FILE_EXTENSIONS: readonly string[] = [
  ".ass",
  ".csv",
  ".ini",
  ".json",
  ".log",
  ".md",
  ".nfo",
  ".srt",
  ".ssa",
  ".sub",
  ".txt",
  ".vtt",
  ".xml",
  ".yaml",
  ".yml",
];

export function isTextFileName(value: string): boolean {
  if (value.length === 0 || value.startsWith(".")) {
    return false;
  }
  const dot = value.lastIndexOf(".");
  if (dot <= 0) {
    return false;
  }
  const suffix = value.slice(dot).toLowerCase();
  return TEXT_FILE_EXTENSIONS.includes(suffix);
}

export interface TextVersionEvidence {
  readonly size: number;
  readonly modifiedAt: string;
  readonly digest: string;
}

export interface TextFileDocument {
  readonly resourceLibraryId: string;
  readonly path: string;
  readonly content: string;
  readonly evidence: TextVersionEvidence;
}

export class DirectFilesNormalizationError extends Error {}

function expectObject(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new DirectFilesNormalizationError("expected an object payload");
  }
  return value as Record<string, unknown>;
}

function expectString(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  if (typeof value !== "string") {
    throw new DirectFilesNormalizationError(`expected string ${key}`);
  }
  return value;
}

function expectNumber(record: Record<string, unknown>, key: string): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new DirectFilesNormalizationError(
      `expected non-negative number ${key}`,
    );
  }
  return value;
}

export function normalizeTextFileDocument(payload: unknown): TextFileDocument {
  const record = expectObject(payload);
  const evidence = expectObject(record.evidence);
  const document: TextFileDocument = {
    resourceLibraryId: expectString(record, "resourceLibraryId"),
    path: expectString(record, "path"),
    content: expectString(record, "content"),
    evidence: {
      size: expectNumber(evidence, "size"),
      modifiedAt: expectString(evidence, "modifiedAt"),
      digest: expectString(evidence, "digest"),
    },
  };
  if (new TextEncoder().encode(document.content).length > MAX_TEXT_BYTES) {
    throw new DirectFilesNormalizationError(
      "text content exceeds the bounded size",
    );
  }
  return document;
}

export interface RenameEvidenceModel {
  readonly resourceLibraryId: string;
  readonly path: string;
  readonly isDirectory: boolean;
  readonly size: number;
  readonly modifiedAt: string;
  readonly evidence: string;
}

/**
 * The server-issued version evidence one Rename must return.
 *
 * The token is opaque: it never carries provider fingerprints, content
 * digests or host paths into the UI, and the page only echoes it back for the
 * exact entry version the backend observed.
 */
export function normalizeRenameEvidence(payload: unknown): RenameEvidenceModel {
  const record = expectObject(payload);
  const evidence = expectString(record, "evidence");
  if (evidence.length === 0 || evidence.length > 256) {
    throw new DirectFilesNormalizationError("expected bounded rename evidence");
  }
  return {
    resourceLibraryId: expectString(record, "resourceLibraryId"),
    path: expectString(record, "path"),
    isDirectory: record.isDirectory === true,
    size: expectNumber(record, "size"),
    modifiedAt: expectString(record, "modifiedAt"),
    evidence,
  };
}

export interface DeleteImpactEntry {
  readonly path: string;
  readonly isDirectory: boolean;
  readonly size: number;
}

export interface DeleteImpactModel {
  readonly resourceLibraryId: string;
  readonly topLevelPaths: readonly string[];
  readonly entries: readonly DeleteImpactEntry[];
  readonly fileCount: number;
  readonly directoryCount: number;
  readonly totalBytes: number;
  readonly truncated: boolean;
  readonly scopeDigest: string;
}

export function normalizeDeleteImpact(payload: unknown): DeleteImpactModel {
  const record = expectObject(payload);
  const rawPaths = record.topLevelPaths;
  const rawEntries = record.entries;
  if (!Array.isArray(rawPaths) || !Array.isArray(rawEntries)) {
    throw new DirectFilesNormalizationError("expected bounded impact arrays");
  }
  if (rawEntries.length > 5000) {
    throw new DirectFilesNormalizationError(
      "impact entries exceed the bounded page",
    );
  }
  const entries = rawEntries.map((item) => {
    const entry = expectObject(item);
    const isDirectory = entry.isDirectory;
    return {
      path: expectString(entry, "path"),
      isDirectory: isDirectory === true,
      size: expectNumber(entry, "size"),
    } satisfies DeleteImpactEntry;
  });
  return {
    resourceLibraryId: expectString(record, "resourceLibraryId"),
    topLevelPaths: rawPaths.map((path) => {
      if (typeof path !== "string" || path.length === 0) {
        throw new DirectFilesNormalizationError("invalid top-level path");
      }
      return path;
    }),
    entries,
    fileCount: expectNumber(record, "fileCount"),
    directoryCount: expectNumber(record, "directoryCount"),
    totalBytes: expectNumber(record, "totalBytes"),
    truncated: record.truncated === true,
    scopeDigest: expectString(record, "scopeDigest"),
  };
}

export interface DirectFileItemOutcome {
  readonly path: string;
  readonly status: string;
  readonly errorCategory: string | null;
}

/**
 * The bounded, never-truncated known-effect entry for one confirmed top-level
 * Delete target.  The backend emits exactly one per confirmed target (at most
 * MAX_DELETE_PATHS), so the Web can reconcile selection/tree state even when
 * the per-item diagnostic outcomes are truncated for very large directories.
 */
export interface DirectFileKnownEffect {
  readonly path: string;
  readonly effect: string;
  readonly status: string;
}

export interface DirectFileCommandResult {
  readonly operation: string;
  readonly status: string;
  readonly path?: string;
  readonly target?: string;
  readonly taskId?: string;
  readonly taskStatus?: string;
  readonly effectCertainty?: string;
  readonly errorCategory?: string;
  readonly durableState?: string;
  readonly nextAction?: string;
  readonly topLevelPaths?: readonly string[];
  readonly knownEffects?: readonly DirectFileKnownEffect[];
  readonly totalItems?: number;
  readonly succeededItems?: number;
  readonly failedItems?: number;
  readonly outcomes?: readonly DirectFileItemOutcome[];
  readonly outcomesTruncated?: boolean;
}

export function normalizeDirectFileCommandResult(
  payload: unknown,
): DirectFileCommandResult {
  const record = expectObject(payload);
  const operation = expectString(record, "operation");
  const status = expectString(record, "status");
  const topLevelPaths = Array.isArray(record.topLevelPaths)
    ? record.topLevelPaths.filter(
        (path): path is string => typeof path === "string",
      )
    : undefined;
  const outcomes = Array.isArray(record.outcomes)
    ? record.outcomes.slice(0, 500).map((item) => {
        const outcome = expectObject(item);
        return {
          path: expectString(outcome, "path"),
          status: expectString(outcome, "status"),
          errorCategory:
            typeof outcome.errorCategory === "string"
              ? outcome.errorCategory
              : null,
        } satisfies DirectFileItemOutcome;
      })
    : undefined;
  const knownEffects = Array.isArray(record.knownEffects)
    ? record.knownEffects.map((item) => {
        const effect = expectObject(item);
        return {
          path: expectString(effect, "path"),
          effect: expectString(effect, "effect"),
          status: expectString(effect, "status"),
        } satisfies DirectFileKnownEffect;
      })
    : undefined;
  return {
    operation,
    status,
    ...(typeof record.path === "string" ? { path: record.path } : {}),
    ...(typeof record.target === "string" ? { target: record.target } : {}),
    ...(typeof record.taskId === "string" ? { taskId: record.taskId } : {}),
    ...(typeof record.taskStatus === "string"
      ? { taskStatus: record.taskStatus }
      : {}),
    ...(typeof record.effectCertainty === "string"
      ? { effectCertainty: record.effectCertainty }
      : {}),
    ...(typeof record.errorCategory === "string"
      ? { errorCategory: record.errorCategory }
      : {}),
    ...(typeof record.durableState === "string"
      ? { durableState: record.durableState }
      : {}),
    ...(typeof record.nextAction === "string"
      ? { nextAction: record.nextAction }
      : {}),
    ...(typeof record.totalItems === "number"
      ? { totalItems: record.totalItems }
      : {}),
    ...(typeof record.succeededItems === "number"
      ? { succeededItems: record.succeededItems }
      : {}),
    ...(typeof record.failedItems === "number"
      ? { failedItems: record.failedItems }
      : {}),
    ...(typeof record.outcomesTruncated === "boolean"
      ? { outcomesTruncated: record.outcomesTruncated }
      : {}),
    ...(topLevelPaths === undefined ? {} : { topLevelPaths }),
    ...(knownEffects === undefined ? {} : { knownEffects }),
    ...(outcomes === undefined ? {} : { outcomes }),
  };
}

/** The two explicitly supported transfer operations; no implicit third value. */
export type TransferOperation = "copy" | "move";

/**
 * The explicit destination-conflict choices.  Replace is deliberately absent:
 * it would require one destination-bound destructive confirmation and is not
 * implemented.  The backend default is no-overwrite.
 */
export type TransferConflictMode = "fail" | "skip" | "keep_both";

export interface TransferManifestEntry {
  readonly path: string;
  readonly isDirectory: boolean;
  readonly size: number;
  readonly modifiedAt: string;
}

export interface TransferDestination {
  readonly path: string;
  readonly destination: string;
}

export interface TransferConflict {
  readonly path: string;
  readonly destination: string;
  readonly resolution: string;
}

export interface TransferCheckpointEntry {
  readonly path: string;
  readonly destination: string;
  readonly checkpoints: readonly string[];
  readonly status: string;
}

/**
 * The zero-mutation impact summary one Copy/Move confirmation holds.  The
 * manifest digest is opaque server-side evidence: the page only echoes it back
 * and never learns host roots, fingerprints or provider payloads.
 */
export interface TransferImpactModel {
  readonly resourceLibraryId: string;
  readonly destinationResourceLibraryId: string;
  readonly operation: TransferOperation;
  readonly conflictMode: TransferConflictMode;
  readonly sameStorage: boolean;
  readonly sourceLibraryRoot: string;
  readonly destinationDirectory: string;
  readonly capability: string;
  readonly topLevelPaths: readonly string[];
  readonly destinations: readonly TransferDestination[];
  readonly entries: readonly TransferManifestEntry[];
  readonly fileCount: number;
  readonly directoryCount: number;
  readonly totalBytes: number;
  readonly conflicts: readonly TransferConflict[];
  readonly manifestDigest: string;
}

export function normalizeTransferImpact(payload: unknown): TransferImpactModel {
  const record = expectObject(payload);
  const operation = expectString(record, "operation");
  if (operation !== "copy" && operation !== "move") {
    throw new DirectFilesNormalizationError("unsupported transfer operation");
  }
  const conflictMode = expectString(record, "conflictMode");
  if (
    conflictMode !== "fail" &&
    conflictMode !== "skip" &&
    conflictMode !== "keep_both"
  ) {
    throw new DirectFilesNormalizationError(
      "unsupported transfer conflict mode",
    );
  }
  const rawPaths = record.topLevelPaths;
  const rawDestinations = record.destinations;
  const rawEntries = record.entries;
  const rawConflicts = record.conflicts;
  if (
    !Array.isArray(rawPaths) ||
    !Array.isArray(rawDestinations) ||
    !Array.isArray(rawEntries) ||
    !Array.isArray(rawConflicts)
  ) {
    throw new DirectFilesNormalizationError("expected bounded transfer arrays");
  }
  if (rawEntries.length > 5000) {
    throw new DirectFilesNormalizationError(
      "transfer entries exceed the bounded page",
    );
  }
  const digest = expectString(record, "manifestDigest");
  if (digest.length === 0 || digest.length > 128) {
    throw new DirectFilesNormalizationError(
      "expected bounded transfer manifest evidence",
    );
  }
  return {
    resourceLibraryId: expectString(record, "resourceLibraryId"),
    destinationResourceLibraryId: expectString(
      record,
      "destinationResourceLibraryId",
    ),
    operation,
    conflictMode,
    sameStorage: record.sameStorage === true,
    sourceLibraryRoot: expectString(record, "sourceLibraryRoot"),
    destinationDirectory: expectString(record, "destinationDirectory"),
    capability: expectString(record, "capability"),
    topLevelPaths: rawPaths.map((path) => {
      if (typeof path !== "string" || path.length === 0) {
        throw new DirectFilesNormalizationError("invalid top-level path");
      }
      return path;
    }),
    destinations: rawDestinations.map((item) => {
      const destination = expectObject(item);
      return {
        path: expectString(destination, "path"),
        destination: expectString(destination, "destination"),
      } satisfies TransferDestination;
    }),
    entries: rawEntries.map((item) => {
      const entry = expectObject(item);
      return {
        path: expectString(entry, "path"),
        isDirectory: entry.isDirectory === true,
        size: expectNumber(entry, "size"),
        modifiedAt: expectString(entry, "modifiedAt"),
      } satisfies TransferManifestEntry;
    }),
    fileCount: expectNumber(record, "fileCount"),
    directoryCount: expectNumber(record, "directoryCount"),
    totalBytes: expectNumber(record, "totalBytes"),
    conflicts: rawConflicts.map((item) => {
      const conflict = expectObject(item);
      return {
        path: expectString(conflict, "path"),
        destination: expectString(conflict, "destination"),
        resolution: expectString(conflict, "resolution"),
      } satisfies TransferConflict;
    }),
    manifestDigest: digest,
  };
}

export interface TransferItemOutcome {
  readonly path: string;
  readonly destination: string;
  readonly status: string;
  readonly checkpoints: readonly string[];
  readonly errorCategory?: string;
  readonly durableState?: string;
}

/**
 * The durable bounded transfer result.  Every top-level selection keeps its own
 * known effect and per-entry checkpoints, so a verified-copy/source-retained
 * item or one failed item among successful siblings is never hidden.
 */
export interface TransferResultModel {
  readonly operation: TransferOperation;
  readonly conflictMode: TransferConflictMode;
  readonly sameStorage: boolean;
  readonly status: string;
  readonly taskId: string;
  readonly taskStatus: string;
  readonly resourceLibraryId: string;
  readonly destinationResourceLibraryId: string;
  readonly topLevelPaths: readonly string[];
  readonly destinations: readonly TransferDestination[];
  readonly knownEffects: readonly DirectFileKnownEffect[];
  readonly checkpoints: readonly TransferCheckpointEntry[];
  readonly checkpointsTruncated: boolean;
  readonly totalItems: number;
  readonly succeededItems: number;
  readonly failedItems: number;
  readonly outcomes: readonly TransferItemOutcome[];
  readonly outcomesTruncated: boolean;
  readonly nextAction: string;
  readonly durableState?: string;
}

export function normalizeTransferResult(payload: unknown): TransferResultModel {
  const record = expectObject(payload);
  const operation = expectString(record, "operation");
  if (operation !== "copy" && operation !== "move") {
    throw new DirectFilesNormalizationError("unsupported transfer operation");
  }
  const conflictMode = expectString(record, "conflictMode");
  if (
    conflictMode !== "fail" &&
    conflictMode !== "skip" &&
    conflictMode !== "keep_both"
  ) {
    throw new DirectFilesNormalizationError(
      "unsupported transfer conflict mode",
    );
  }
  const arrays = {
    topLevelPaths: record.topLevelPaths,
    destinations: record.destinations,
    knownEffects: record.knownEffects,
    checkpoints: record.checkpoints,
    outcomes: record.outcomes,
  };
  for (const [name, value] of Object.entries(arrays)) {
    if (!Array.isArray(value)) {
      throw new DirectFilesNormalizationError(`expected bounded ${name}`);
    }
  }
  const outcomes = (arrays.outcomes as unknown[]).slice(0, 3200).map((item) => {
    const outcome = expectObject(item);
    return {
      path: expectString(outcome, "path"),
      destination: expectString(outcome, "destination"),
      status: expectString(outcome, "status"),
      checkpoints: Array.isArray(outcome.checkpoints)
        ? outcome.checkpoints.filter(
            (value): value is string => typeof value === "string",
          )
        : [],
      errorCategory:
        typeof outcome.errorCategory === "string"
          ? outcome.errorCategory
          : undefined,
      durableState:
        typeof outcome.durableState === "string"
          ? outcome.durableState
          : undefined,
    } satisfies TransferItemOutcome;
  });
  const checkpoints = (arrays.checkpoints as unknown[])
    .slice(0, 5000)
    .map((item) => {
      const checkpoint = expectObject(item);
      return {
        path: expectString(checkpoint, "path"),
        destination: expectString(checkpoint, "destination"),
        status: expectString(checkpoint, "status"),
        checkpoints: Array.isArray(checkpoint.checkpoints)
          ? checkpoint.checkpoints.filter(
              (value): value is string => typeof value === "string",
            )
          : [],
      } satisfies TransferCheckpointEntry;
    });
  return {
    operation,
    conflictMode,
    sameStorage: record.sameStorage === true,
    status: expectString(record, "status"),
    taskId: expectString(record, "taskId"),
    taskStatus: expectString(record, "taskStatus"),
    resourceLibraryId: expectString(record, "resourceLibraryId"),
    destinationResourceLibraryId: expectString(
      record,
      "destinationResourceLibraryId",
    ),
    topLevelPaths: (arrays.topLevelPaths as unknown[]).map((path) => {
      if (typeof path !== "string" || path.length === 0) {
        throw new DirectFilesNormalizationError("invalid top-level path");
      }
      return path;
    }),
    destinations: (arrays.destinations as unknown[]).map((item) => {
      const destination = expectObject(item);
      return {
        path: expectString(destination, "path"),
        destination: expectString(destination, "destination"),
      } satisfies TransferDestination;
    }),
    knownEffects: (arrays.knownEffects as unknown[]).map((item) => {
      const effect = expectObject(item);
      return {
        path: expectString(effect, "path"),
        effect: expectString(effect, "effect"),
        status: expectString(effect, "status"),
      } satisfies DirectFileKnownEffect;
    }),
    checkpoints,
    checkpointsTruncated: record.checkpointsTruncated === true,
    totalItems: expectNumber(record, "totalItems"),
    succeededItems: expectNumber(record, "succeededItems"),
    failedItems: expectNumber(record, "failedItems"),
    outcomes,
    outcomesTruncated: record.outcomesTruncated === true,
    nextAction: expectString(record, "nextAction"),
    ...(typeof record.durableState === "string"
      ? { durableState: record.durableState }
      : {}),
  };
}

export interface RemovalReferenceItem {
  readonly section: string;
  readonly id: string;
  readonly field: string;
}

export interface RemovalActiveIdentity {
  readonly revisionId: string;
  readonly version: number;
  readonly digest: string;
}

export interface RemovalPreviewModel {
  readonly resourceLibrary: {
    readonly id: string;
    readonly name: string;
    readonly storageId: string;
    readonly storagePath: string;
    readonly enabled: boolean;
  };
  readonly storage: {
    readonly id: string;
    readonly name: string;
    readonly type: string;
    readonly enabled: boolean;
  } | null;
  readonly references: {
    readonly total: number;
    readonly items: readonly RemovalReferenceItem[];
    readonly truncated: boolean;
  };
  /** The exact Active revision this preview was computed against. */
  readonly active: RemovalActiveIdentity;
}

export function normalizeRemovalPreview(payload: unknown): RemovalPreviewModel {
  const record = expectObject(payload);
  const library = expectObject(record.resourceLibrary);
  const rawReferences = expectObject(record.references);
  const rawItems = rawReferences.items;
  if (!Array.isArray(rawItems)) {
    throw new DirectFilesNormalizationError("expected reference items");
  }
  const rawStorage = record.storage;
  const storage =
    rawStorage === null || rawStorage === undefined
      ? null
      : (() => {
          const storageRecord = expectObject(rawStorage);
          return {
            id: expectString(storageRecord, "id"),
            name: expectString(storageRecord, "name"),
            type: expectString(storageRecord, "type"),
            enabled: storageRecord.enabled !== false,
          };
        })();
  // The confirmation must bind to the exact previewed Active revision, so the
  // active identity is mandatory in the preview document.
  const active = expectObject(record.active);
  return {
    resourceLibrary: {
      id: expectString(library, "id"),
      name: expectString(library, "name"),
      storageId: expectString(library, "storageId"),
      storagePath: expectString(library, "storagePath"),
      enabled: library.enabled !== false,
    },
    storage,
    references: {
      total: expectNumber(rawReferences, "total"),
      items: rawItems.slice(0, 64).map((item) => {
        const reference = expectObject(item);
        return {
          section: expectString(reference, "section"),
          id: expectString(reference, "id"),
          field: expectString(reference, "field"),
        };
      }),
      truncated: rawReferences.truncated === true,
    },
    active: {
      revisionId: expectString(active, "revisionId"),
      version: expectNumber(active, "version"),
      digest: expectString(active, "digest"),
    },
  };
}

export interface ResourceLibraryRemovalModel {
  readonly removedId: string;
  readonly activeRevisionId: string;
}

export function normalizeResourceLibraryRemoval(
  payload: unknown,
): ResourceLibraryRemovalModel {
  const record = expectObject(payload);
  const removed = expectObject(record.removed);
  const active = expectObject(record.active);
  const model: ResourceLibraryRemovalModel = {
    removedId: expectString(removed, "id"),
    activeRevisionId: expectString(active, "revisionId"),
  };
  return model;
}
