/**
 * Frontend-owned Worker readiness entity for the Operations workspace.
 *
 * A Worker readiness or list response is only rendered from a fully modelled
 * shape: an unknown readiness condition, a coerced boolean or an unknown
 * supported-command value is malformed data rather than an approximate Worker
 * state. Configuration digests are fingerprints and are deliberately not
 * modelled, so they can never reach the DOM or a browser artifact.
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
import { JOB_COMMANDS, type JobCommand } from "./job";

export const WORKER_READINESS_CONDITIONS = [
  "ready",
  "no_worker",
  "stale_worker",
  "snapshot_mismatch",
  "schema_mismatch",
] as const;
export type WorkerReadinessCondition =
  (typeof WORKER_READINESS_CONDITIONS)[number];

export const WORKER_STATUSES = ["live", "stale", "stopped"] as const;
export type WorkerStatus = (typeof WORKER_STATUSES)[number];

export interface WorkerReadinessModel {
  readonly ready: boolean;
  readonly condition: WorkerReadinessCondition;
  readonly category: string | null;
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string | null;
  readonly activeWorkersCount: number;
  readonly expectedRuntimeSchemaVersion: number | null;
}

export interface WorkerSummary {
  readonly workerId: string;
  readonly label: string;
  readonly status: WorkerStatus;
  readonly lastHeartbeatAt: string | null;
  readonly registeredAt: string | null;
  readonly heartbeatIntervalSeconds: number;
  readonly supportedCommands: readonly JobCommand[];
  readonly runtimeSchemaVersion: number | null;
}

export interface WorkerListModel {
  readonly workers: readonly WorkerSummary[];
  readonly count: number;
}

export class WorkerNormalizationError extends Error {
  constructor() {
    super("worker response did not match the expected contract");
    this.name = "WorkerNormalizationError";
  }
}

function fail(): never {
  throw new WorkerNormalizationError();
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

export function normalizeWorkerReadiness(
  payload: unknown,
): WorkerReadinessModel {
  const source = readRecord(payload, "worker_readiness");
  let condition: WorkerReadinessCondition;
  try {
    condition = normalizeEnum(
      source["condition"],
      "condition",
      WORKER_READINESS_CONDITIONS,
    );
  } catch {
    return fail();
  }
  const ready = flag(source, "ready");
  const activeWorkersCount = optionalCount(source, "activeWorkersCount") ?? 0;
  if (ready !== (condition === "ready")) {
    // The readiness flag and the stated condition must agree.
    fail();
  }
  if (ready && activeWorkersCount < 1) {
    fail();
  }
  const category = optionalText(source, "category");
  if (!ready && category === null) {
    // A not-ready readiness document must name its category.
    fail();
  }
  if (ready && category !== null) {
    fail();
  }
  return {
    ready,
    condition,
    category,
    durableState: text(source, "durableState"),
    sideEffects: text(source, "sideEffects"),
    retrySafe: flag(source, "retrySafe"),
    nextAction: optionalText(source, "nextAction"),
    activeWorkersCount,
    expectedRuntimeSchemaVersion: optionalCount(
      source,
      "expectedRuntimeSchemaVersion",
    ),
  };
}

function normalizeWorkerSummary(
  source: Record<string, unknown>,
): WorkerSummary {
  let status: WorkerStatus;
  let supportedCommands: readonly JobCommand[];
  try {
    status = normalizeEnum(source["status"], "worker.status", WORKER_STATUSES);
    supportedCommands = normalizeEnumArray(
      source["supported_commands"],
      "worker.supported_commands",
      JOB_COMMANDS,
    );
  } catch {
    return fail();
  }
  return {
    workerId: text(source, "worker_id"),
    label: text(source, "label"),
    status,
    lastHeartbeatAt: optionalText(source, "last_heartbeat_at"),
    registeredAt: optionalText(source, "registered_at"),
    heartbeatIntervalSeconds:
      optionalCount(source, "heartbeat_interval_seconds") ?? 0,
    supportedCommands,
    runtimeSchemaVersion: optionalCount(source, "runtime_schema_version"),
  };
}

export function normalizeWorkerList(payload: unknown): WorkerListModel {
  const source = readRecord(payload, "worker_list");
  const workers = source["workers"];
  if (!Array.isArray(workers)) {
    fail();
  }
  const models = workers.map((worker) =>
    normalizeWorkerSummary(readRecord(worker, "worker")),
  );
  if (new Set(models.map((worker) => worker.workerId)).size !== models.length) {
    fail();
  }
  const count = optionalCount(source, "count") ?? models.length;
  if (count < models.length) {
    // A reported total cannot be smaller than the page it describes.
    fail();
  }
  return { workers: models, count };
}
