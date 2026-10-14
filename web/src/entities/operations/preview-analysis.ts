/**
 * Frontend-owned bounded model for one durable exact Preview analysis.
 *
 * The existing exact Preview services walk a definition scope or a manual
 * intent synchronously inside the HTTP request.  A durable analysis admits that
 * same work to the resident Processing Worker and returns a durable identity
 * immediately, so the operator can read bounded progress and pause, resume or
 * cancel at a safe boundary.  This model carries only the durable facts the
 * backend publishes: the immutable pinned context, durable progress, the
 * identity of the Preview it eventually links and the actions the current
 * principal may take.  It grants no execution authority by itself.
 */

import {
  normalizeBoundedCount,
  normalizeEnum,
  normalizeIdentityText,
  normalizeOptionalIdentityText,
  normalizeOptionalText,
  normalizeBoolean,
  readRecord,
} from "../shared/normalize";

export const PREVIEW_ANALYSIS_STATUSES = [
  "queued",
  "running",
  "paused",
  "completed",
  "failed",
  "cancelled",
] as const;
export type PreviewAnalysisStatus = (typeof PREVIEW_ANALYSIS_STATUSES)[number];

const STATUSES: ReadonlySet<string> = new Set(PREVIEW_ANALYSIS_STATUSES);

/**
 * The bounded progress phases the durable analysis service publishes. A phase
 * outside this closed set is malformed data, never a display value.
 */
export const PREVIEW_ANALYSIS_PHASES = [
  "queued",
  "running",
  "paused",
  "completed",
  "failed",
  "cancelled",
] as const;
export type PreviewAnalysisPhase = (typeof PREVIEW_ANALYSIS_PHASES)[number];

const PHASES: ReadonlySet<string> = new Set(PREVIEW_ANALYSIS_PHASES);

const KINDS = ["definition", "manual"] as const;
export type PreviewAnalysisKind = (typeof KINDS)[number];

/**
 * The one path shape a completed analysis may link. It is re-validated here
 * rather than trusted: an arbitrary server string is never rendered as an
 * operator-navigable target.
 */
const PREVIEW_PATH =
  /^\/operations\/organize\/preview\/[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;
const DEFINITION_PREVIEW_ID = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;

export interface PreviewAnalysisAction {
  readonly available: boolean;
}

export interface PreviewAnalysisProgressModel {
  readonly phase: PreviewAnalysisPhase;
  readonly message: string;
  readonly visitedEntries: number;
  readonly analysedItems: number;
  readonly totalItems: number;
}

export interface PreviewAnalysisModel {
  readonly analysisId: string;
  readonly kind: PreviewAnalysisKind;
  readonly actor: string;
  readonly configurationSnapshotId: string;
  readonly configurationSnapshotDigest: string;
  readonly status: PreviewAnalysisStatus;
  readonly version: number;
  readonly progress: PreviewAnalysisProgressModel;
  readonly definitionId: string | null;
  readonly definitionFingerprint: string | null;
  readonly intentId: string | null;
  readonly intentVersion: number | null;
  readonly previewId: string | null;
  readonly error: string | null;
  readonly cancelRequested: boolean;
  readonly pauseRequested: boolean;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly admissionRequestId: string | null;
  readonly zeroMutation: boolean;
  readonly sideEffects: "none";
  readonly previewPath: string | null;
  readonly actions: {
    readonly pause: PreviewAnalysisAction;
    readonly resume: PreviewAnalysisAction;
    readonly cancel: PreviewAnalysisAction;
    readonly preview: PreviewAnalysisAction;
  };
}

function fail(field: string): never {
  throw new Error(`malformed preview analysis response: ${field}`);
}

function boundedText(record: Record<string, unknown>, field: string): string {
  return normalizeIdentityText(record[field], field);
}

function optionalText(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function optionalCount(value: unknown, field: string): number | null {
  if (value === null || value === undefined) return null;
  return normalizeBoundedCount(value, field);
}

function action(
  record: Record<string, unknown>,
  key: string,
): PreviewAnalysisAction {
  const value = record[key];
  if (value === undefined) return { available: false };
  const entry = readRecord(value, `actions.${key}`);
  return { available: entry["available"] === true };
}

/**
 * The linked Preview path, or null.
 *
 * Definition and manual analyses use distinct Preview authorities and routes.
 * Anything outside the route for the stated kind — including a foreign,
 * absolute or path-traversing value — degrades to "no link".
 */
function previewPath(
  value: unknown,
  kind: PreviewAnalysisKind,
  definitionId: string | null,
  expectedPreviewId: string | null,
): string | null {
  if (typeof value !== "string" || expectedPreviewId === null) return null;
  if (kind === "manual") {
    return value === `/operations/organize/preview/${expectedPreviewId}` &&
      PREVIEW_PATH.test(value)
      ? value
      : null;
  }
  if (definitionId === null || !DEFINITION_PREVIEW_ID.test(definitionId))
    return null;
  const prefix = `/operations/automation/preview/${encodeURIComponent(definitionId)}/`;
  const previewId = value.startsWith(prefix) ? value.slice(prefix.length) : "";
  return previewId === expectedPreviewId &&
    DEFINITION_PREVIEW_ID.test(previewId)
    ? value
    : null;
}

export function normalizePreviewAnalysis(
  payload: unknown,
): PreviewAnalysisModel {
  const record = readRecord(payload, "previewAnalysis");
  const status = boundedText(record, "status");
  if (!STATUSES.has(status)) fail("status");
  const progress = readRecord(record["progress"], "progress");
  const phase = boundedText(progress, "phase");
  if (!PHASES.has(phase)) fail("progress.phase");
  const actions = readRecord(record["actions"], "actions");
  const kind = normalizeEnum(record["kind"], "kind", KINDS);
  const definitionId = normalizeOptionalIdentityText(
    record["definitionId"],
    "definitionId",
  );
  return {
    analysisId: boundedText(record, "analysisId"),
    kind,
    actor: boundedText(record, "actor"),
    configurationSnapshotId: boundedText(record, "configurationSnapshotId"),
    configurationSnapshotDigest: boundedText(
      record,
      "configurationSnapshotDigest",
    ),
    status: status as PreviewAnalysisStatus,
    version: normalizeBoundedCount(record["version"], "version"),
    progress: {
      phase: phase as PreviewAnalysisPhase,
      message: optionalText(progress["message"]) ?? "",
      visitedEntries: normalizeBoundedCount(
        progress["visitedEntries"],
        "progress.visitedEntries",
      ),
      analysedItems: normalizeBoundedCount(
        progress["analysedItems"],
        "progress.analysedItems",
      ),
      totalItems: normalizeBoundedCount(
        progress["totalItems"],
        "progress.totalItems",
      ),
    },
    definitionId,
    definitionFingerprint: normalizeOptionalIdentityText(
      record["definitionFingerprint"],
      "definitionFingerprint",
    ),
    intentId: normalizeOptionalIdentityText(record["intentId"], "intentId"),
    intentVersion: optionalCount(record["intentVersion"], "intentVersion"),
    previewId: normalizeOptionalIdentityText(record["previewId"], "previewId"),
    error: normalizeOptionalText(record["error"], "error"),
    cancelRequested: normalizeBoolean(
      record["cancelRequested"],
      "cancelRequested",
    ),
    pauseRequested: normalizeBoolean(
      record["pauseRequested"],
      "pauseRequested",
    ),
    createdAt: boundedText(record, "createdAt"),
    updatedAt: boundedText(record, "updatedAt"),
    admissionRequestId: normalizeOptionalIdentityText(
      record["admissionRequestId"],
      "admissionRequestId",
    ),
    zeroMutation: normalizeBoolean(record["zeroMutation"], "zeroMutation"),
    sideEffects: normalizeEnum(record["sideEffects"], "sideEffects", [
      "none",
    ] as const),
    previewPath: previewPath(
      record["previewPath"],
      kind,
      definitionId,
      normalizeOptionalIdentityText(record["previewId"], "previewId"),
    ),
    actions: {
      pause: action(actions, "pause"),
      resume: action(actions, "resume"),
      cancel: action(actions, "cancel"),
      preview: action(actions, "preview"),
    },
  };
}
