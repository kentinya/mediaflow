/**
 * Frontend-owned Job entity for the Operations workspace.
 */

import { normalizeBoundedText, readRecord } from "../shared/normalize";

export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type AutomationCommand =
  | "scan"
  | "preview"
  | "organize"
  | "file-metadata-correction"
  | "recovery-continuation"
  | string;

export interface JobWorkerEvidence {
  readonly workerId: string | null;
  readonly ownerLastHeartbeatAt: string | null;
  readonly ownerStale: boolean;
  readonly ownerStopped: boolean;
}

export interface JobOperationalCondition {
  readonly condition: string;
  readonly stage: string;
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
}

export interface JobSummary {
  readonly jobId: string;
  readonly command: AutomationCommand;
  readonly status: JobStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly startedAt: string | null;
  readonly completedAt: string | null;
  readonly taskId: string | null;
  readonly workerId: string | null;
  readonly error: string | null;
  readonly failureCategory: string | null;
  readonly failureExplanation: string | null;
  readonly definitionId: string | null;
  readonly definitionName: string | null;
  readonly scheduleId: string | null;
  readonly workerEvidence: JobWorkerEvidence | null;
  readonly operationalCondition: JobOperationalCondition | null;
}

export interface JobListPage {
  readonly items: readonly JobSummary[];
  readonly limit: number;
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

function str(source: Record<string, unknown>, field: string): string {
  return normalizeBoundedText(source[field], field);
}

function normalizeJobWorkerEvidence(
  source: Record<string, unknown>,
): JobWorkerEvidence {
  return {
    workerId:
      typeof source["workerId"] === "string"
        ? (source["workerId"] as string)
        : null,
    ownerLastHeartbeatAt:
      typeof source["ownerLastHeartbeatAt"] === "string"
        ? (source["ownerLastHeartbeatAt"] as string)
        : null,
    ownerStale: Boolean(source["ownerStale"]),
    ownerStopped: Boolean(source["ownerStopped"]),
  };
}

function normalizeJobOperationalCondition(
  source: Record<string, unknown>,
): JobOperationalCondition {
  return {
    condition: str(source, "condition"),
    stage: str(source, "stage"),
    durableState: str(source, "durableState"),
    sideEffects: str(source, "sideEffects"),
    retrySafe: Boolean(source["retrySafe"]),
    nextAction: str(source, "nextAction"),
  };
}

function normalizeJobSummary(source: Record<string, unknown>): JobSummary {
  const hasWorkerEvidence =
    source["workerId"] !== undefined ||
    source["ownerLastHeartbeatAt"] !== undefined;
  const opCondition = source["operationalCondition"];
  return {
    jobId: str(source, "job_id"),
    command: str(source, "command"),
    status: str(source, "status") as JobStatus,
    createdAt: str(source, "created_at"),
    updatedAt: str(source, "updated_at"),
    startedAt:
      typeof source["started_at"] === "string"
        ? (source["started_at"] as string)
        : null,
    completedAt:
      typeof source["completed_at"] === "string"
        ? (source["completed_at"] as string)
        : null,
    taskId:
      typeof source["task_id"] === "string"
        ? (source["task_id"] as string)
        : null,
    workerId:
      typeof source["workerId"] === "string"
        ? (source["workerId"] as string)
        : typeof source["worker_id"] === "string"
          ? (source["worker_id"] as string)
          : null,
    error:
      typeof source["error"] === "string" && source["error"].length > 0
        ? (source["error"] as string)
        : null,
    failureCategory: typeof source["failureCategory"] === "string"
      ? (source["failureCategory"] as string)
      : typeof source["failure_category"] === "string"
        ? (source["failure_category"] as string)
        : null,
    failureExplanation:
      typeof source["failureExplanation"] === "string"
        ? (source["failureExplanation"] as string)
        : null,
    definitionId:
      typeof source["definition_id"] === "string"
        ? (source["definition_id"] as string)
        : null,
    definitionName:
      typeof source["definition_name"] === "string"
        ? (source["definition_name"] as string)
        : null,
    scheduleId:
      typeof source["schedule_id"] === "string"
        ? (source["schedule_id"] as string)
        : null,
    workerEvidence: hasWorkerEvidence
      ? normalizeJobWorkerEvidence(source)
      : null,
    operationalCondition:
      opCondition !== null &&
      opCondition !== undefined &&
      typeof opCondition === "object"
        ? normalizeJobOperationalCondition(
            opCondition as Record<string, unknown>,
          )
        : null,
  };
}

export function normalizeJobListPage(payload: unknown): JobListPage {
  const source = readRecord(payload, "job_list");
  const items = source["items"];
  if (!Array.isArray(items)) {
    throw new JobNormalizationError();
  }
  return {
    items: items.map((item) => normalizeJobSummary(readRecord(item, "job"))),
    limit:
      typeof source["limit"] === "number" ? (source["limit"] as number) : 20,
    truncated: Boolean(source["truncated"]),
    previousCursor:
      typeof source["previous_cursor"] === "string"
        ? (source["previous_cursor"] as string)
        : null,
    nextCursor:
      typeof source["next_cursor"] === "string"
        ? (source["next_cursor"] as string)
        : null,
  };
}

export function normalizeJobDetail(payload: unknown): JobSummary {
  const source = readRecord(payload, "job_detail");
  return normalizeJobSummary(source);
}

/**
 * Determine which lifecycle actions the backend currently advertises for
 * a given job state.
 */
export function jobLifecycleActions(job: JobSummary): {
  readonly cancel: boolean;
} {
  return { cancel: job.status === "pending" || job.status === "running" };
}
