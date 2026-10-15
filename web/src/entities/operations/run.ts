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

/**
 * The nine sibling task-center views (RO-1). The first four are lifecycle
 * partitions; the last five are cross-Task recovery lists keyed by current
 * problem type.
 */
export const RUN_VIEWS = [
  "all",
  "running",
  "attention",
  "ended",
  "recognition",
  "metadata",
  "classification",
  "conflict",
  "failure",
] as const;
export type RunView = (typeof RUN_VIEWS)[number];

/** The five cross-Task recovery problem types, in display order. */
export const RUN_PROBLEM_TYPES = [
  "recognition",
  "metadata",
  "classification",
  "conflict",
  "failure",
] as const;
export type RunProblemType = (typeof RUN_PROBLEM_TYPES)[number];

/** Chinese labels for the nine views, in the reference navigation order. */
export const RUN_VIEW_LABELS: Readonly<Record<RunView, string>> = {
  all: "全部任务",
  running: "进行中",
  attention: "需要处理",
  ended: "已结束",
  recognition: "识别恢复",
  metadata: "元数据恢复",
  classification: "分类恢复",
  conflict: "冲突处理",
  failure: "失败恢复",
};

/** Chinese labels for the five recovery problem types. */
export const RUN_PROBLEM_LABELS: Readonly<Record<RunProblemType, string>> = {
  recognition: "识别问题",
  metadata: "元数据问题",
  classification: "分类问题",
  conflict: "冲突问题",
  failure: "失败问题",
};

/** True for one of the five cross-Task recovery views. */
export function isRecoveryView(view: RunView): view is RunProblemType {
  return (RUN_PROBLEM_TYPES as readonly string[]).includes(view);
}

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
  /** The current, real recovery problem types this Task has outstanding. */
  readonly problemTypes: readonly RunProblemType[];
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
  /** The run's durable continuation evidence, or `null` when the run never
   * continued its remaining scope. Only the single-run overview read publishes
   * it; inventory rows carry `null`. */
  readonly continuation: RunContinuation | null;
}

/**
 * Bounded continuation evidence of one run.
 *
 * The backend never publishes the internal scope path, the configuration pin or
 * the actor here, so this projection carries only the durable identifiers the
 * operator needs in order to follow the run that really owns the remaining
 * scope.
 */
export interface RunContinuation {
  readonly continuationId: string;
  readonly status: string;
  readonly command: string;
  readonly jobId: string | null;
  readonly newTaskId: string | null;
  readonly itemLimit: number | null;
  readonly createdAt: string;
  readonly completedAt: string | null;
  readonly attemptCount: number;
  readonly truncated: boolean;
  readonly recoveryKind: "queued_continuation" | "exact_preview" | null;
  readonly recoveryPreviewId: string | null;
  readonly executionId: string | null;
  readonly nextAction: string;
  readonly sideEffects: string;
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
  /** The selected view and problem predicate, echoed by the server. */
  readonly view: RunView | null;
  readonly problem: RunProblemType | null;
  /** The complete-authorized-population summary, or an explicit unavailable
   * shape when the runtime cannot serve it. */
  readonly summary: RunInventorySummary;
  readonly population: string;
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
}

/** The complete-authorized-population summary of the nine views. */
export interface RunInventorySummary {
  readonly available: boolean;
  readonly total: number | null;
  readonly running: number | null;
  readonly attention: number | null;
  readonly ended: number | null;
  readonly problemTasks: Readonly<Record<RunProblemType, number>>;
  readonly problemFiles: Readonly<Record<RunProblemType, number>>;
  /** Distinct durable historical source scopes of the population. */
  readonly sources: readonly {
    readonly value: string;
    readonly label: string;
  }[];
  readonly sourcesTruncated: boolean;
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
  if (recognizedCommand && commandLabel === null) {
    // A run is only "recognized" when the backend supplied its bounded label.
    // A null `command` with a label is a legal run kind whose label comes
    // from its own durable record (the bounded discovery stage), not from a
    // persisted Task command family.
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
  // The current-problem facet and the problem-type list must agree exactly:
  // a run is attention precisely when it currently has at least one real
  // problem.  A server that reports an approximate facet is rejected.
  const problemTypes = normalizeProblemTypes(source["problem_types"]);
  if (attention !== problemTypes.length > 0) {
    fail();
  }
  const jobId = optionalText(source, "job_id");
  const taskId = optionalText(source, "task_id");
  const lifecycle = normalizeRunLifecycle(source["lifecycle"], taskId, jobId);
  const continuation = normalizeRunContinuation(source["continuation"]);
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
    problemTypes,
    configurationSnapshotId: optionalText(source, "configuration_snapshot_id"),
    workerId: optionalText(source, "worker_id"),
    progress:
      source["progress"] === null || source["progress"] === undefined
        ? null
        : normalizeRunProgress(source["progress"]),
    lifecycle,
    continuation,
  };
}

/**
 * Normalize the bounded current-problem type list of one run.
 *
 * Each entry must be one of the five modelled types, appear at most once and
 * keep the canonical display order, so a malformed or duplicated list fails
 * the whole response closed instead of rendering an approximate problem set.
 */
function normalizeProblemTypes(value: unknown): readonly RunProblemType[] {
  if (value === undefined || value === null) {
    return [];
  }
  if (!Array.isArray(value) || value.length > RUN_PROBLEM_TYPES.length) {
    return fail();
  }
  const seen: RunProblemType[] = [];
  for (const entry of value) {
    let problem: RunProblemType;
    try {
      problem = normalizeEnum(entry, "problem_types", RUN_PROBLEM_TYPES);
    } catch {
      return fail();
    }
    if (seen.includes(problem)) {
      return fail();
    }
    seen.push(problem);
  }
  return seen;
}

function normalizeRunContinuation(value: unknown): RunContinuation | null {
  if (value === undefined || value === null) {
    return null;
  }
  const source = readRecord(value, "run.continuation");
  try {
    const attemptCount = normalizeBoundedCount(
      source["attemptCount"],
      "run.continuation.attemptCount",
    );
    const itemLimit =
      source["itemLimit"] === null || source["itemLimit"] === undefined
        ? null
        : normalizeBoundedCount(
            source["itemLimit"],
            "run.continuation.itemLimit",
          );
    return {
      continuationId: normalizeBoundedText(
        source["continuationId"],
        "run.continuation.continuationId",
      ),
      status: normalizeBoundedText(
        source["status"],
        "run.continuation.status",
        64,
      ),
      command: normalizeBoundedText(
        source["command"],
        "run.continuation.command",
        64,
      ),
      jobId:
        source["jobId"] === null || source["jobId"] === undefined
          ? null
          : normalizeBoundedText(source["jobId"], "run.continuation.jobId"),
      newTaskId:
        source["newTaskId"] === null || source["newTaskId"] === undefined
          ? null
          : normalizeBoundedText(
              source["newTaskId"],
              "run.continuation.newTaskId",
            ),
      itemLimit,
      createdAt: normalizeBoundedText(
        source["createdAt"],
        "run.continuation.createdAt",
      ),
      completedAt:
        source["completedAt"] === null || source["completedAt"] === undefined
          ? null
          : normalizeBoundedText(
              source["completedAt"],
              "run.continuation.completedAt",
            ),
      attemptCount,
      truncated: normalizeBoolean(
        source["truncated"],
        "run.continuation.truncated",
      ),
      recoveryKind:
        source["recoveryKind"] === undefined || source["recoveryKind"] === null
          ? null
          : normalizeEnum(
              source["recoveryKind"],
              "run.continuation.recoveryKind",
              ["queued_continuation", "exact_preview"] as const,
            ),
      recoveryPreviewId:
        source["recoveryPreviewId"] === null ||
        source["recoveryPreviewId"] === undefined
          ? null
          : normalizeBoundedText(
              source["recoveryPreviewId"],
              "run.continuation.recoveryPreviewId",
            ),
      executionId:
        source["executionId"] === null || source["executionId"] === undefined
          ? null
          : normalizeBoundedText(
              source["executionId"],
              "run.continuation.executionId",
            ),
      nextAction: normalizeBoundedText(
        source["nextAction"],
        "run.continuation.nextAction",
      ),
      sideEffects: normalizeBoundedText(
        source["sideEffects"],
        "run.continuation.sideEffects",
      ),
    };
  } catch {
    return fail();
  }
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
  const view = normalizeRunViewEcho(source["view"]);
  const problem = normalizeRunProblemEcho(source["problem"]);
  if (view !== null && isRecoveryView(view) && problem !== view) {
    // A recovery view owns its problem predicate; the echoed problem must
    // match it or the population the page describes is ambiguous.
    fail();
  }
  const summary = normalizeRunSummarySummary(source["summary"]);
  // The attention count is the population-scoped current-problem facet. When
  // the facet is applied the whole filtered total IS that population; when it
  // is not, the count may legitimately exceed the returned page.
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
  const boundedTotal = (() => {
    try {
      return normalizeBoundedCount(source["total"], "total");
    } catch {
      return fail();
    }
  })();
  if (attention && reportedAttentionCount !== boundedTotal) {
    // A server that echoes the applied facet must really have applied it: the
    // whole filtered total IS the overlapping attention population.
    fail();
  }
  if (reportedAttentionCount > boundedTotal) {
    // The attention facet is a subset of the filtered population, so its
    // count can never exceed the total it is drawn from.
    fail();
  }
  const pageItems = items.map((item) => normalizeRunSummary(item));
  if (attention && pageItems.some((item) => !item.attention)) {
    // Every returned item must really carry the applied facet.
    fail();
  }
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
    attentionCount: reportedAttentionCount,
    view,
    problem,
    summary,
    population: text(source, "population"),
    previousCursor: optionalText(source, "previous_cursor"),
    nextCursor: optionalText(source, "next_cursor"),
  };
}

function normalizeRunViewEcho(value: unknown): RunView | null {
  if (value === null || value === undefined) {
    return null;
  }
  try {
    return normalizeEnum(value, "view", RUN_VIEWS);
  } catch {
    return fail();
  }
}

function normalizeRunProblemEcho(value: unknown): RunProblemType | null {
  if (value === null || value === undefined) {
    return null;
  }
  try {
    return normalizeEnum(value, "problem", RUN_PROBLEM_TYPES);
  } catch {
    return fail();
  }
}

function normalizeProblemCounts(
  value: unknown,
  field: string,
): Readonly<Record<RunProblemType, number>> {
  const source = readRecord(value, field);
  const counts: Record<string, number> = {};
  for (const problem of RUN_PROBLEM_TYPES) {
    try {
      counts[problem] = normalizeBoundedCount(
        source[problem],
        `${field}.${problem}`,
      );
    } catch {
      return fail();
    }
  }
  return counts as Readonly<Record<RunProblemType, number>>;
}

function normalizeRunSummarySummary(value: unknown): RunInventorySummary {
  if (value === undefined || value === null) {
    return {
      available: false,
      total: null,
      running: null,
      attention: null,
      ended: null,
      problemTasks: emptyProblemCounts(),
      problemFiles: emptyProblemCounts(),
      sources: [],
      sourcesTruncated: false,
    };
  }
  const source = readRecord(value, "summary");
  const available = flag(source, "available");
  if (!available) {
    return {
      available: false,
      total: null,
      running: null,
      attention: null,
      ended: null,
      problemTasks: emptyProblemCounts(),
      problemFiles: emptyProblemCounts(),
      sources: [],
      sourcesTruncated: false,
    };
  }
  const count = (field: string): number => {
    try {
      return normalizeBoundedCount(source[field], `summary.${field}`);
    } catch {
      return fail();
    }
  };
  return {
    available: true,
    total: count("total"),
    running: count("running"),
    attention: count("attention"),
    ended: count("ended"),
    problemTasks: normalizeProblemCounts(
      source["problem_tasks"],
      "problem_tasks",
    ),
    problemFiles: normalizeProblemCounts(
      source["problem_files"],
      "problem_files",
    ),
    sources: normalizeSourceOptions(source["sources"]),
    sourcesTruncated: flag(source, "sources_truncated"),
  };
}

function normalizeSourceOptions(
  value: unknown,
): readonly { readonly value: string; readonly label: string }[] {
  if (value === undefined || value === null) {
    return [];
  }
  if (!Array.isArray(value) || value.length > 50) {
    return fail();
  }
  return value.map((entry) => {
    const source = readRecord(entry, "summary.sources");
    return {
      value: normalizeBoundedText(
        source["value"],
        "summary.sources.value",
        512,
      ),
      label: normalizeBoundedText(
        source["label"],
        "summary.sources.label",
        512,
      ),
    };
  });
}

function emptyProblemCounts(): Readonly<Record<RunProblemType, number>> {
  return {
    recognition: 0,
    metadata: 0,
    classification: 0,
    conflict: 0,
    failure: 0,
  };
}

export function normalizeRunOverview(payload: unknown): RunSummary {
  return normalizeRunSummary(readRecord(payload, "run"));
}
