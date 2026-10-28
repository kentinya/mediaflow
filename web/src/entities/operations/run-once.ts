/** Typed organizing admission and retained historical analysis readback.
 * The backend owns execution authority, exact pins and independent results.
 */

import {
  normalizeBoundedCount,
  normalizeIdentityText,
  readRecord,
} from "../shared/normalize";

export const RUN_ONCE_PHASES = [
  "discovering",
  "executing",
  "completed",
  "analyzing",
  // A durable pause was requested (``pausing``) and then acknowledged by the
  // resident Worker at its safe boundary (``paused``); both stop advertising a
  // confirmable plan for the interrupted analysis.
  "pausing",
  "paused",
  "ready",
  "frozen",
  "refused",
  "no_work",
  "failed",
  // The operator cancelled the run: a terminal outcome, never a recoverable
  // analysis or a confirmable plan.
  "cancelled",
] as const;
export type AutomationRunOncePhase = (typeof RUN_ONCE_PHASES)[number];

const PHASES: ReadonlySet<string> = new Set(RUN_ONCE_PHASES);

const STATUSES: ReadonlySet<string> = new Set([
  "queued",
  "running",
  "paused",
  "waiting_stability",
  // The frozen manifest's durable analysis stage: the exact plan is being
  // produced by the resident Worker on this same run.
  "analyzing",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
]);

export interface AutomationRunOnceAction {
  readonly available: boolean;
}

export interface AutomationRunOnceModel {
  readonly executionKind: "organizing" | "analysis";
  readonly taskId: string | null;
  readonly jobId: string | null;
  readonly discoveryId: string;
  readonly definitionId: string;
  readonly definitionName: string;
  readonly resourceLibraryId: string;
  readonly sourceScope: string | null;
  readonly runMode: string;
  readonly definitionItemLimit: number;
  readonly effectivePrimaryLimit: number;
  readonly phase: AutomationRunOncePhase;
  readonly status: string;
  readonly version: number;
  readonly primarySourceCount: number;
  readonly visitedEntries: number;
  readonly excludedEntries: number;
  readonly unstableEntries: number;
  readonly errorEntries: number;
  readonly incomplete: boolean;
  readonly incompleteReason: string | null;
  readonly refusalReason: string | null;
  readonly frozen: boolean;
  readonly frozenAt: string | null;
  readonly intentId: string | null;
  /**
   * The exact durable shared-plan identity this frozen manifest produced, when
   * one exists. It carries no authority: it only lets the same page re-read the
   * plan it already created after a reload, reconnect or restart.
   */
  readonly previewId: string | null;
  readonly nextAction: string;
  readonly message: string;
  readonly error: string | null;
  readonly actions: {
    readonly pause: AutomationRunOnceAction;
    readonly cancel: AutomationRunOnceAction;
    readonly resume: AutomationRunOnceAction;
    readonly finalize: AutomationRunOnceAction;
    readonly narrowScope: AutomationRunOnceAction;
    readonly preview: AutomationRunOnceAction;
  };
}

function fail(field: string): never {
  throw new Error(`malformed run-once response: ${field}`);
}

function boundedText(record: Record<string, unknown>, field: string): string {
  return normalizeIdentityText(record[field], field);
}

function boundedCount(value: unknown, field: string): number {
  return normalizeBoundedCount(value, field);
}

function optionalText(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function action(
  record: Record<string, unknown>,
  key: string,
): AutomationRunOnceAction {
  const value = record[key];
  if (value === undefined) return { available: false };
  const entry = readRecord(value, `actions.${key}`);
  return { available: entry["available"] === true };
}

export function normalizeAutomationRunOnce(
  payload: unknown,
): AutomationRunOnceModel {
  const record = readRecord(payload, "runOnce");
  const phase = boundedText(record, "phase");
  if (!PHASES.has(phase)) fail("phase");
  const status = boundedText(record, "status");
  if (!STATUSES.has(status)) fail("status");
  const progress = readRecord(record["progress"], "progress");
  const organizing = record["executionKind"] === "organizing";
  const counters = organizing
    ? {
        visitedEntries: 0,
        excludedEntries: 0,
        unstableEntries: 0,
        errorEntries: 0,
      }
    : readRecord(progress["counters"], "progress.counters");
  const actions = readRecord(record["actions"], "actions");
  return {
    executionKind: organizing ? "organizing" : "analysis",
    taskId: organizing ? boundedText(record, "taskId") : null,
    jobId: organizing ? boundedText(record, "jobId") : null,
    discoveryId: boundedText(record, "discoveryId"),
    definitionId: boundedText(record, "definitionId"),
    definitionName: boundedText(record, "definitionName"),
    resourceLibraryId: boundedText(record, "resourceLibraryId"),
    sourceScope: optionalText(record["sourceScope"]),
    runMode: boundedText(record, "runMode"),
    definitionItemLimit: boundedCount(
      record["definitionItemLimit"],
      "definitionItemLimit",
    ),
    effectivePrimaryLimit: boundedCount(
      record["effectivePrimaryLimit"],
      "effectivePrimaryLimit",
    ),
    phase: phase as AutomationRunOncePhase,
    status,
    version: boundedCount(record["version"], "version"),
    primarySourceCount: boundedCount(
      record["primarySourceCount"],
      "primarySourceCount",
    ),
    visitedEntries: boundedCount(counters["visitedEntries"], "visitedEntries"),
    excludedEntries: boundedCount(
      counters["excludedEntries"],
      "excludedEntries",
    ),
    unstableEntries: boundedCount(
      counters["unstableEntries"],
      "unstableEntries",
    ),
    errorEntries: boundedCount(counters["errorEntries"], "errorEntries"),
    incomplete:
      progress["incompleteReason"] !== null &&
      progress["incompleteReason"] !== undefined &&
      progress["incompleteReason"] !== "none",
    incompleteReason: optionalText(progress["incompleteReason"]),
    refusalReason: optionalText(record["refusalReason"]),
    frozen: record["frozen"] === true,
    frozenAt: optionalText(record["frozenAt"]),
    intentId: optionalText(record["intentId"]),
    previewId: optionalText(record["previewId"]),
    nextAction: boundedText(record, "nextAction"),
    message: optionalText(progress["message"]) ?? "",
    error: optionalText(record["error"]),
    actions: {
      pause: action(actions, "pause"),
      cancel: action(actions, "cancel"),
      resume: action(actions, "resume"),
      finalize: action(actions, "finalize"),
      narrowScope: action(actions, "narrowScope"),
      preview: action(actions, "preview"),
    },
  };
}
