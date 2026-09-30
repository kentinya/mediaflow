/**
 * Frontend-owned unified run inventory entity for the Operations workspace.
 *
 * The Python contract (`GET /api/v1/operations/runs`,
 * `GET /api/v1/operations/runs/{id}`) returns the bounded, secret-free run
 * projection over one deduplicated Job/Task population. Normalization is
 * deliberately fail-closed: an unknown status, trigger or library kind, a
 * coerced boolean or a miscounted progress pair makes the whole response
 * malformed instead of being rendered as an approximate truth. The document
 * carries no digest, fingerprint, host root or raw durable error, and an
 * unknown legacy command keeps its honest `recognizedCommand: false` shape.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";

/** One honest aggregate state derived from actual queue/processing evidence. */
export const RUN_STATUSES = [
  "pending",
  "running",
  "paused",
  "waiting",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
  "unknown",
] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];

/** Statuses that durably end a run's processing. */
export const TERMINAL_RUN_STATUSES: readonly RunStatus[] = [
  "completed",
  "partial_success",
  "failed",
  "cancelled",
];

/**
 * The overlapping attention facet. A run can be in attention and still be
 * counted in its own status partition; `running` is deliberately absent.
 */
export const ATTENTION_RUN_STATUSES: readonly RunStatus[] = [
  "pending",
  "paused",
  "waiting",
  "partial_success",
  "failed",
];

/** What admitted the run, from its durable record alone. */
export const RUN_TRIGGERS = [
  "manual",
  "automation",
  "scheduled",
  "unknown",
] as const;
export type RunTrigger = (typeof RUN_TRIGGERS)[number];

/** Which kind of configured library owns the run's recorded scope. */
export const RUN_LIBRARY_KINDS = ["resource", "media"] as const;
export type RunLibraryKind = (typeof RUN_LIBRARY_KINDS)[number];

/** The backend-submitted status filter values (exactly the modelled set). */
export const RUN_STATUS_FILTERS = RUN_STATUSES;

export interface RunSummary {
  readonly runId: string;
  readonly runKind: string;
  readonly command: string | null;
  readonly commandLabel: string | null;
  readonly recognizedCommand: boolean;
  readonly status: RunStatus;
  readonly trigger: RunTrigger;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly jobId: string | null;
  readonly taskId: string | null;
  readonly scheduleId: string | null;
  readonly definitionId: string | null;
  readonly sourceScope: string | null;
  readonly libraryKind: RunLibraryKind | null;
  readonly totalItems: number | null;
  readonly completedItems: number | null;
  readonly failedItems: number | null;
  readonly pauseRequested: boolean;
  readonly attention: boolean;
  readonly configurationSnapshotId: string | null;
  readonly workerId: string | null;
}

export interface RunInventoryPage {
  readonly items: readonly RunSummary[];
  readonly limit: number;
  readonly status: RunStatus | null;
  readonly command: string | null;
  readonly q: string | null;
  readonly from: string | null;
  readonly to: string | null;
  readonly total: number;
  readonly truncated: boolean;
  readonly statusCounts: Readonly<Record<string, number>>;
  readonly attentionCount: number;
  readonly population: string;
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
}

export class RunNormalizationError extends Error {
  constructor() {
    super("operations run response did not match the expected contract");
    this.name = "RunNormalizationError";
  }
}

function fail(): never {
  throw new RunNormalizationError();
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

function flag(source: Record<string, unknown>, field: string): boolean {
  try {
    return normalizeBoolean(source[field], field);
  } catch {
    return fail();
  }
}

/** Chinese business labels for the modelled aggregate states. */
export const RUN_STATUS_LABELS: Readonly<Record<RunStatus, string>> = {
  pending: "待处理",
  running: "进行中",
  paused: "已暂停",
  waiting: "等待处理",
  completed: "已完成",
  partial_success: "部分成功",
  failed: "失败",
  cancelled: "已取消",
  unknown: "未知",
};

/** Chinese business labels for the admission triggers. */
export const RUN_TRIGGER_LABELS: Readonly<Record<RunTrigger, string>> = {
  manual: "手动",
  automation: "自动化",
  scheduled: "计划任务",
  unknown: "未知",
};

/** Type icons for the two library kinds; a run without evidence shows none. */
export const RUN_LIBRARY_KIND_LABELS: Readonly<Record<RunLibraryKind, string>> =
  {
    resource: "资源库",
    media: "媒体库",
  };

export function isAttentionRun(status: RunStatus): boolean {
  return ATTENTION_RUN_STATUSES.includes(status);
}

export function normalizeRunSummary(payload: unknown): RunSummary {
  const source = readRecord(payload, "run");
  let status: RunStatus;
  let trigger: RunTrigger;
  let libraryKind: RunLibraryKind | null;
  try {
    status = normalizeEnum(source["status"], "run.status", RUN_STATUSES);
    trigger = normalizeEnum(source["trigger"], "run.trigger", RUN_TRIGGERS);
    libraryKind =
      source["library_kind"] === null || source["library_kind"] === undefined
        ? null
        : normalizeEnum(
            source["library_kind"],
            "run.library_kind",
            RUN_LIBRARY_KINDS,
          );
  } catch {
    return fail();
  }
  const command = optionalText(source, "command");
  const commandLabel = optionalText(source, "command_label");
  const recognizedCommand = flag(source, "recognized_command");
  if (recognizedCommand && (command === null || commandLabel === null)) {
    // A run is only "recognized" when the backend supplied its bounded label.
    fail();
  }
  const totalItems = optionalCount(source, "total_items");
  const completedItems = optionalCount(source, "completed_items");
  const failedItems = optionalCount(source, "failed_items");
  if (
    (completedItems !== null || failedItems !== null) &&
    (totalItems === null ||
      (completedItems ?? 0) + (failedItems ?? 0) > totalItems)
  ) {
    // Progress that cannot describe one run is contradictory, not rounded.
    fail();
  }
  const attention = flag(source, "attention");
  if (attention !== isAttentionRun(status)) {
    // The backend attention facet and the modelled facet must agree exactly.
    fail();
  }
  return {
    runId: text(source, "run_id"),
    runKind: text(source, "run_kind"),
    command,
    commandLabel,
    recognizedCommand,
    status,
    trigger,
    createdAt: text(source, "created_at"),
    updatedAt: text(source, "updated_at"),
    jobId: optionalText(source, "job_id"),
    taskId: optionalText(source, "task_id"),
    scheduleId: optionalText(source, "schedule_id"),
    definitionId: optionalText(source, "definition_id"),
    sourceScope: optionalText(source, "source_scope"),
    libraryKind,
    totalItems,
    completedItems,
    failedItems,
    pauseRequested: flag(source, "pause_requested"),
    attention,
    configurationSnapshotId: optionalText(source, "configuration_snapshot_id"),
    workerId: optionalText(source, "worker_id"),
  };
}

function normalizeRunFilterEcho(
  source: Record<string, unknown>,
  field: string,
): string | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  return text(source, field);
}

function normalizeRunStatusCounts(
  source: Record<string, unknown>,
): Readonly<Record<string, number>> {
  const raw = source["status_counts"];
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return fail();
  }
  const counts: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    try {
      counts[key] = normalizeBoundedCount(value, "status_counts");
    } catch {
      return fail();
    }
  }
  return counts;
}

export function normalizeRunInventoryPage(payload: unknown): RunInventoryPage {
  const source = readRecord(payload, "run_list");
  const items = source["items"];
  if (!Array.isArray(items)) {
    fail();
  }
  const rawStatus = normalizeRunFilterEcho(source, "status");
  let status: RunStatus | null = null;
  if (rawStatus !== null) {
    try {
      status = normalizeEnum(rawStatus, "status", RUN_STATUSES);
    } catch {
      return fail();
    }
  }
  const statusCounts = normalizeRunStatusCounts(source);
  // The attention count is the overlapping facet over the same population:
  // it must equal the sum of the modelled attention partitions, never an
  // invented separate total.
  const modelledAttention = ATTENTION_RUN_STATUSES.reduce(
    (sum, value) => sum + (statusCounts[value] ?? 0),
    0,
  );
  if (
    normalizeBoundedCount(source["attention_count"], "attention_count") !==
    modelledAttention
  ) {
    fail();
  }
  const boundedTotal = (() => {
    try {
      return normalizeBoundedCount(source["total"], "total");
    } catch {
      return fail();
    }
  })();
  const pageItems = items.map((item) => normalizeRunSummary(item));
  // The filtered total is at least the current page size, never below it.
  if (boundedTotal < pageItems.length) {
    fail();
  }
  return {
    items: pageItems,
    limit: (() => {
      try {
        return normalizeBoundedCount(source["limit"], "limit");
      } catch {
        return fail();
      }
    })(),
    status,
    command: normalizeRunFilterEcho(source, "command"),
    q: normalizeRunFilterEcho(source, "q"),
    from: normalizeRunFilterEcho(source, "from"),
    to: normalizeRunFilterEcho(source, "to"),
    total: boundedTotal,
    truncated: flag(source, "truncated"),
    statusCounts,
    attentionCount: modelledAttention,
    population: text(source, "population"),
    previousCursor: optionalText(source, "previous_cursor"),
    nextCursor: optionalText(source, "next_cursor"),
  };
}

export function normalizeRunOverview(payload: unknown): RunSummary {
  return normalizeRunSummary(readRecord(payload, "run"));
}
