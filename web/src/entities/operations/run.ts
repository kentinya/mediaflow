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
 *
 * Progress honesty is task-kind aware rather than one blanket sum rule: an
 * exact-partition command (`manual_organize`, the bounded Files commands)
 * partitions one item list, so `completed + failed` may never exceed the
 * total, while a scan/preview/organize/retry or unknown legacy run may carry
 * independent scan errors beyond its known items (for example
 * `total=0, completed=0, failed=1`). One such honest production run must
 * render as a row instead of rejecting the whole page — the contradiction
 * checks above the sum rule (required total, non-negative counts and
 * `completed <= total`) still fail closed for every command.
 *
 * The page additionally proves the attention facet it echoes: when
 * `attention` is true the server applied the overlapping facet, so every
 * partition is an attention status and the whole filtered total is that
 * population. A server that echoes the flag without applying it is rejected.
 *
 * The single-run overview read may additionally carry a backend-computed
 * `lifecycle` projection for the exact durable object the run resolves to. It
 * is fail-closed in both directions: an absent or explicitly null projection
 * normalizes to `null` (inventory rows legitimately carry none), while a
 * present projection must name the run's own `task_id` (objectType `task`) or
 * `job_id` (objectType `job`) and its raw state must be one of that object
 * kind's modelled states. A projection for another object, an unknown object
 * type or state, a missing identity or a malformed inner shape makes the whole
 * response malformed — an approximate control is never rendered, and frontend
 * state never grants authority the backend did not advertise.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";
import { normalizeRunProgress, type RunProgress } from "./run-detail";
import {
  normalizeLifecycleProjection,
  type LifecycleProjection,
} from "./lifecycle";

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

/**
 * The raw persistent Task states a linked-Task run lifecycle projection may
 * carry. This is deliberately the *raw* Task state set, never the run's own
 * derived aggregate `status`: the two are not required to be equal (a run may
 * aggregate to `waiting` while its linked Task is `running`, for example), so
 * the projection is validated against the states its object kind can really
 * hold rather than against the aggregate row.
 */
export const RUN_TASK_LIFECYCLE_STATES = [
  "pending",
  "running",
  "paused",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
] as const;

/** The raw Job states a pre-Task run lifecycle projection may carry. */
export const RUN_JOB_LIFECYCLE_STATES = [
  "pending",
  "running",
  "completed",
  "failed",
  "cancelled",
] as const;

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
  /** Bounded/redacted destination-scope evidence (the literal
   * `[redacted-path]` when the raw path may not be published). It is modeled
   * fail-closed but not rendered by this Task. */
  readonly targetScope: string | null;
  readonly libraryKind: RunLibraryKind | null;
  readonly totalItems: number | null;
  readonly completedItems: number | null;
  readonly failedItems: number | null;
  readonly pauseRequested: boolean;
  readonly attention: boolean;
  readonly configurationSnapshotId: string | null;
  readonly workerId: string | null;
  /** The selected-run detail progress projection. Present on the overview
   * read and absent (null) on inventory rows. */
  readonly progress: RunProgress | null;
  /** The backend-advertised lifecycle controls for the durable object this run
   * resolves to, or `null` when the run has neither a linked Task nor a Job.
   * Only the single-run overview read publishes it; inventory rows carry
   * `null`. It is the only source of a rendered control. */
  readonly lifecycle: LifecycleProjection | null;
}

export interface RunInventoryPage {
  readonly items: readonly RunSummary[];
  readonly limit: number;
  readonly status: RunStatus | null;
  readonly command: string | null;
  readonly q: string | null;
  readonly from: string | null;
  readonly to: string | null;
  /** True only when the submitted `attention=true` facet restricted this
   * page's population to the overlapping attention statuses. */
  readonly attention: boolean;
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

/**
 * The MediaLibrary-owned command prefix the backend's own label derivation
 * strips before reading the family (`media_<family>[:<identity>]`).
 */
const MEDIA_LIBRARY_COMMAND_PREFIX = "media_";

/**
 * Commands whose items form one exact partition of `total_items`: a completed
 * or failed item is one of the listed items, so `completed + failed` may never
 * exceed the total. Every other family (scan, preview, organize, retry,
 * continuations, unknown legacy) may legally carry independent errors — a
 * production Scan reports scan errors next to a zero item list.
 */
const EXACT_PARTITION_COMMAND_FAMILIES: ReadonlySet<string> = new Set([
  "manual_organize",
  "files_direct_command",
  "files_delete",
  "files_transfer",
]);

/**
 * The command family, derived with the backend's own rules (strip a leading
 * `media_` prefix, take the segment before `:` — mirroring
 * `known_command_label` in `mediaflow/domain/operations_run.py`). A run
 * without a command has no family and therefore no exact-partition claim.
 */
function commandFamily(command: string | null): string | null {
  if (command === null || command.length === 0) {
    return null;
  }
  const withoutPrefix = command.startsWith(MEDIA_LIBRARY_COMMAND_PREFIX)
    ? command.slice(MEDIA_LIBRARY_COMMAND_PREFIX.length)
    : command;
  const family = withoutPrefix.split(":", 1)[0];
  return family.length > 0 ? family : null;
}

/**
 * Normalize one run's optional lifecycle projection against the run's own
 * durable identities.
 *
 * The projection must describe exactly the object this run resolves to: a
 * linked Task (`objectType: "task"`, matching `taskId`) or a Job
 * (`objectType: "job"`, matching `jobId`). A run that does not carry the
 * identity the projection names cannot own that projection at all, so the
 * whole response fails closed instead of attaching a control to an approximate
 * object. The raw `state` is validated against the closed set of states its
 * own object kind can hold; an unknown state or a malformed inner shape fails
 * the whole response closed.
 */
function normalizeRunLifecycle(
  value: unknown,
  taskId: string | null,
  jobId: string | null,
): LifecycleProjection | null {
  if (value === null || value === undefined) {
    return null;
  }
  try {
    // The projection claims its own object type; the run must really carry
    // that identity, otherwise the control would target another object.
    const source = readRecord(value, "run.lifecycle");
    const rawObjectType = source["objectType"];
    if (rawObjectType === "task") {
      if (taskId === null) {
        return fail();
      }
      return normalizeLifecycleProjection(value, {
        objectType: "task",
        objectId: taskId,
        state: RUN_TASK_LIFECYCLE_STATES,
      });
    }
    if (rawObjectType === "job") {
      if (jobId === null) {
        return fail();
      }
      return normalizeLifecycleProjection(value, {
        objectType: "job",
        objectId: jobId,
        state: RUN_JOB_LIFECYCLE_STATES,
      });
    }
    // An unknown object type can never supply a run control.
    return fail();
  } catch {
    return fail();
  }
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
  const reportedProgress = completedItems !== null || failedItems !== null;
  // R1: progress that cannot name its own population is contradictory, not
  // rounded — a completed/failed count always requires the item total.
  if (reportedProgress && totalItems === null) {
    fail();
  }
  // R2: every count is a non-negative integer (optionalCount above).
  // R3: a run can never complete more items than it has, for every command.
  if (
    totalItems !== null &&
    completedItems !== null &&
    completedItems > totalItems
  ) {
    fail();
  }
  // R4: only an exact-partition command must fit inside its total. Scan and
  // pipeline runs may carry independent scan errors beyond the known items,
  // so their sum is display evidence, never a malformedness claim.
  const family = commandFamily(command);
  if (
    totalItems !== null &&
    family !== null &&
    EXACT_PARTITION_COMMAND_FAMILIES.has(family) &&
    (completedItems ?? 0) + (failedItems ?? 0) > totalItems
  ) {
    fail();
  }
  const attention = flag(source, "attention");
  if (attention !== isAttentionRun(status)) {
    // The backend attention facet and the modelled facet must agree exactly.
    fail();
  }
  const jobId = optionalText(source, "job_id");
  const taskId = optionalText(source, "task_id");
  const lifecycle = normalizeRunLifecycle(source["lifecycle"], taskId, jobId);
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
    jobId,
    taskId,
    scheduleId: optionalText(source, "schedule_id"),
    definitionId: optionalText(source, "definition_id"),
    sourceScope: optionalText(source, "source_scope"),
    targetScope: optionalText(source, "target_scope"),
    libraryKind,
    totalItems,
    completedItems,
    failedItems,
    pauseRequested: flag(source, "pause_requested"),
    attention,
    configurationSnapshotId: optionalText(source, "configuration_snapshot_id"),
    workerId: optionalText(source, "worker_id"),
    progress:
      source["progress"] === null || source["progress"] === undefined
        ? null
        : normalizeRunProgress(source["progress"]),
    lifecycle,
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
  // The submitted attention facet echo is a required boolean: an omitted or
  // coerced flag is malformed data, never an implicit "no filter".
  const attention = flag(source, "attention");
  // The attention count is the overlapping facet over the same population:
  // it must equal the sum of the modelled attention partitions, never an
  // invented separate total.
  const modelledAttention = ATTENTION_RUN_STATUSES.reduce(
    (sum, value) => sum + (statusCounts[value] ?? 0),
    0,
  );
  const reportedAttentionCount = (() => {
    try {
      return normalizeBoundedCount(
        source["attention_count"],
        "attention_count",
      );
    } catch {
      return fail();
    }
  })();
  if (reportedAttentionCount !== modelledAttention) {
    fail();
  }
  const boundedTotal = (() => {
    try {
      return normalizeBoundedCount(source["total"], "total");
    } catch {
      return fail();
    }
  })();
  if (attention) {
    // A server that echoes the applied facet must really have applied it:
    // every partition belongs to the overlapping attention population and the
    // whole filtered total IS that population. Echoing `attention: true` over
    // an unfiltered page would advertise a filter the table did not apply.
    for (const key of Object.keys(statusCounts)) {
      if (!(ATTENTION_RUN_STATUSES as readonly string[]).includes(key)) {
        fail();
      }
    }
    if (reportedAttentionCount !== boundedTotal) {
      fail();
    }
  }
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
    attention,
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
