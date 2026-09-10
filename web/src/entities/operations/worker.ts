/**
 * Frontend-owned Worker readiness entity for the Operations workspace.
 */

import { normalizeBoundedText, readRecord } from "../shared/normalize";

export type WorkerReadinessCondition =
  | "ready"
  | "no_worker"
  | "stale_worker"
  | "snapshot_mismatch"
  | "schema_mismatch";

export interface WorkerReadinessModel {
  readonly ready: boolean;
  readonly condition: WorkerReadinessCondition;
  readonly category: string | null;
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
  readonly activeWorkersCount: number;
  readonly activeSnapshotId: string;
  readonly activeSnapshotDigest: string;
}

export interface WorkerSummary {
  readonly workerId: string;
  readonly label: string;
  readonly status: string;
  readonly lastHeartbeatAt: string | null;
  readonly registeredAt: string | null;
  readonly supportedCommands: readonly string[];
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

function str(source: Record<string, unknown>, field: string): string {
  return normalizeBoundedText(source[field], field);
}

export function normalizeWorkerReadiness(
  payload: unknown,
): WorkerReadinessModel {
  const source = readRecord(payload, "worker_readiness");
  const rawNextAction = source["nextAction"];
  return {
    ready: Boolean(source["ready"]),
    condition: str(source, "condition") as WorkerReadinessCondition,
    category:
      typeof source["category"] === "string"
        ? (source["category"] as string)
        : null,
    durableState: str(source, "durableState"),
    sideEffects: str(source, "sideEffects"),
    retrySafe: Boolean(source["retrySafe"]),
    nextAction:
      typeof rawNextAction === "string" ? rawNextAction.trimEnd() : "",
    activeWorkersCount:
      typeof source["activeWorkersCount"] === "number"
        ? (source["activeWorkersCount"] as number)
        : 0,
    activeSnapshotId: str(source, "activeSnapshotId"),
    activeSnapshotDigest: str(source, "activeSnapshotDigest"),
  };
}

function normalizeWorkerSummary(
  source: Record<string, unknown>,
): WorkerSummary {
  const cmds = source["supported_commands"];
  return {
    workerId: str(source, "worker_id"),
    label:
      typeof source["label"] === "string" && source["label"].length > 0
        ? (source["label"] as string)
        : str(source, "worker_id"),
    status: str(source, "status"),
    lastHeartbeatAt:
      typeof source["last_heartbeat_at"] === "string"
        ? (source["last_heartbeat_at"] as string)
        : null,
    registeredAt:
      typeof source["registered_at"] === "string"
        ? (source["registered_at"] as string)
        : null,
    supportedCommands: Array.isArray(cmds)
      ? (cmds as unknown[]).map((v) => String(v))
      : [],
  };
}

export function normalizeWorkerList(payload: unknown): WorkerListModel {
  const source = readRecord(payload, "worker_list");
  const workers = source["workers"];
  if (!Array.isArray(workers)) {
    throw new WorkerNormalizationError();
  }
  return {
    workers: workers.map((w) =>
      normalizeWorkerSummary(readRecord(w, "worker")),
    ),
    count:
      typeof source["count"] === "number"
        ? (source["count"] as number)
        : workers.length,
  };
}
