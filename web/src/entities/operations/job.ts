/**
 * Frontend-owned Job entity for the Operations workspace.
 *
 * The Python contract (`GET /api/v1/operations/jobs`,
 * `GET /api/v1/operations/jobs/{id}`) returns the bounded, secret-free
 * admission projection with worker-ownership evidence and the
 * backend-computed lifecycle projection. A Job command, status or condition
 * outside the modelled set is malformed data, never a coerced string, and the
 * document carries no definition fingerprint, raw source scope, configuration
 * digest or raw durable error.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";
import {
  normalizeLifecycleProjection,
  type LifecycleProjection,
} from "./lifecycle";

export const JOB_STATUSES = [
  "pending",
  "running",
  "completed",
  "failed",
  "cancelled",
] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export const JOB_COMMANDS = [
  "scan",
  "preview",
  "organize",
  "file-metadata-correction",
  "recovery-continuation",
] as const;
export type JobCommand = (typeof JOB_COMMANDS)[number];

export const JOB_RUN_MODES = [
  "scan-only",
  "scan-and-plan",
  "automatic-organization",
] as const;
export type JobRunMode = (typeof JOB_RUN_MODES)[number];

export const JOB_OWNER_STATUSES = ["live", "stale", "stopped"] as const;
export type JobOwnerStatus = (typeof JOB_OWNER_STATUSES)[number];

export const JOB_CONDITIONS = [
  "ready",
  "no_worker",
  "stale_worker",
  "snapshot_mismatch",
  "schema_mismatch",
] as const;
export type JobCondition = (typeof JOB_CONDITIONS)[number];

export interface JobWorkerEvidence {
  readonly workerId: string;
  readonly ownerStatus: JobOwnerStatus;
  readonly ownerLastHeartbeatAt: string;
}

export interface JobOperationalCondition {
  readonly condition: JobCondition;
  readonly stage: string;
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
}

/** Bounded, secret-free failure evidence; never a raw durable error string. */
export interface JobFailureExplanation {
  readonly category: string;
  readonly message: string;
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
}

export interface JobSummary {
  readonly jobId: string;
  readonly command: JobCommand;
  readonly status: JobStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly taskId: string | null;
  readonly cancellationRequested: boolean;
  readonly executeAuthorized: boolean;
  readonly scheduleId: string | null;
  readonly definitionId: string | null;
  readonly definitionVersion: number | null;
  readonly runMode: JobRunMode | null;
  readonly resourceLibraryId: string | null;
  /** Pinned managed configuration revision identity; never a digest. */
  readonly configurationSnapshotId: string | null;
  readonly failure: JobFailureExplanation | null;
  readonly workerEvidence: JobWorkerEvidence | null;
  readonly operationalCondition: JobOperationalCondition | null;
  readonly lifecycle: LifecycleProjection;
}

export interface JobListPage {
  readonly items: readonly JobSummary[];
  readonly limit: number;
  readonly status: JobStatus | null;
  readonly command: JobCommand | null;
  readonly truncated: boolean;
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
}

export class JobNormalizationError extends Error {
  constructor() {
    super("job response did not match the expected contract");
    this.name = "JobNormalizationError";
  }
}

function fail(): never {
  throw new JobNormalizationError();
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

function normalizeOperationalCondition(
  value: unknown,
): JobOperationalCondition {
  const source = readRecord(value, "operationalCondition");
  try {
    return {
      condition: normalizeEnum(
        source["condition"],
        "operationalCondition.condition",
        JOB_CONDITIONS,
      ),
      stage: text(source, "stage"),
      durableState: text(source, "durableState"),
      sideEffects: text(source, "sideEffects"),
      retrySafe: flag(source, "retrySafe"),
      nextAction: text(source, "nextAction"),
    };
  } catch {
    return fail();
  }
}

function normalizeFailureExplanation(value: unknown): JobFailureExplanation {
  const source = readRecord(value, "failure");
  try {
    return {
      category: text(source, "category"),
      message: text(source, "message"),
      durableState: text(source, "durableState"),
      sideEffects: text(source, "sideEffects"),
      retrySafe: flag(source, "retrySafe"),
      nextAction: text(source, "nextAction"),
    };
  } catch {
    return fail();
  }
}

function normalizeWorkerEvidence(
  source: Record<string, unknown>,
): JobWorkerEvidence {
  try {
    return {
      workerId: text(source, "workerId"),
      ownerStatus: normalizeEnum(
        source["ownerStatus"],
        "ownerStatus",
        JOB_OWNER_STATUSES,
      ),
      ownerLastHeartbeatAt: text(source, "ownerLastHeartbeatAt"),
    };
  } catch {
    return fail();
  }
}

function normalizeJobSummary(source: Record<string, unknown>): JobSummary {
  let command: JobCommand;
  let status: JobStatus;
  try {
    command = normalizeEnum(source["command"], "command", JOB_COMMANDS);
    status = normalizeEnum(source["status"], "status", JOB_STATUSES);
  } catch {
    return fail();
  }
  const startedAt = optionalText(source, "started_at");
  const completedAt = optionalText(source, "completed_at");
  const cancellationRequested = flag(source, "cancellation_requested");
  const terminal =
    status === "completed" || status === "failed" || status === "cancelled";
  if (status === "pending" && startedAt !== null) {
    fail();
  }
  if (!terminal && completedAt !== null) {
    fail();
  }
  if (terminal && status !== "cancelled" && completedAt === null) {
    fail();
  }
  if (status === "cancelled" && completedAt === null && startedAt !== null) {
    fail();
  }
  const workerId = optionalText(source, "workerId");
  const ownerStatus = source["ownerStatus"];
  const ownerHeartbeat = source["ownerLastHeartbeatAt"];
  const hasWorkerEvidence =
    workerId !== null ||
    ownerStatus !== undefined ||
    ownerHeartbeat !== undefined;
  let workerEvidence: JobWorkerEvidence | null = null;
  if (hasWorkerEvidence) {
    if (
      workerId === null ||
      ownerStatus === undefined ||
      ownerHeartbeat === undefined
    ) {
      fail();
    }
    workerEvidence = normalizeWorkerEvidence(source);
  }
  if (workerEvidence !== null && status !== "running") {
    // Worker ownership evidence describes exactly one claimed, running Job.
    fail();
  }
  const rawCondition = source["operationalCondition"];
  const operationalCondition =
    rawCondition === null || rawCondition === undefined
      ? null
      : normalizeOperationalCondition(rawCondition);
  const rawFailure = source["failure"];
  const failure =
    rawFailure === null || rawFailure === undefined
      ? null
      : normalizeFailureExplanation(rawFailure);
  const rawRunMode = source["run_mode"];
  let runMode: JobRunMode | null = null;
  if (rawRunMode !== null && rawRunMode !== undefined) {
    try {
      runMode = normalizeEnum(rawRunMode, "run_mode", JOB_RUN_MODES);
    } catch {
      return fail();
    }
  }
  const jobId = text(source, "job_id");
  const createdAt = text(source, "created_at");
  const updatedAt = text(source, "updated_at");
  const taskId = optionalText(source, "task_id");
  const lifecycle = normalizeLifecycleProjection(source["lifecycle"], {
    objectType: "job",
    objectId: jobId,
    state: status,
  });
  if (
    lifecycle.cancellationRequested !== null &&
    lifecycle.cancellationRequested !== cancellationRequested
  ) {
    fail();
  }
  return {
    jobId,
    command,
    status,
    createdAt,
    updatedAt,
    startedAt,
    completedAt,
    taskId,
    cancellationRequested,
    executeAuthorized: flag(source, "execute_authorized"),
    scheduleId: optionalText(source, "schedule_id"),
    definitionId: optionalText(source, "definition_id"),
    definitionVersion: (() => {
      const raw = source["definition_version"];
      return raw === null || raw === undefined
        ? null
        : count(source, "definition_version");
    })(),
    runMode,
    resourceLibraryId: optionalText(source, "resource_library_id"),
    configurationSnapshotId: optionalText(source, "configuration_snapshot_id"),
    failure,
    workerEvidence,
    operationalCondition,
    lifecycle,
  };
}

function normalizeFilterEcho(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  return text(source, field);
}

export function normalizeJobListPage(payload: unknown): JobListPage {
  const source = readRecord(payload, "job_list");
  const items = source["items"];
  if (!Array.isArray(items)) {
    fail();
  }
  const rawStatus = normalizeFilterEcho(source, "status");
  let status: JobStatus | null = null;
  if (rawStatus !== null) {
    try {
      status = normalizeEnum(rawStatus, "status", JOB_STATUSES);
    } catch {
      return fail();
    }
  }
  const rawCommand = normalizeFilterEcho(source, "command");
  let command: JobCommand | null = null;
  if (rawCommand !== null) {
    try {
      command = normalizeEnum(rawCommand, "command", JOB_COMMANDS);
    } catch {
      return fail();
    }
  }
  return {
    items: items.map((item) => normalizeJobSummary(readRecord(item, "job"))),
    limit: count(source, "limit"),
    status,
    command,
    truncated: flag(source, "truncated"),
    previousCursor: optionalText(source, "previous_cursor"),
    nextCursor: optionalText(source, "next_cursor"),
  };
}

export function normalizeJobDetail(payload: unknown): JobSummary {
  const source = readRecord(payload, "job_detail");
  return normalizeJobSummary(source);
}
