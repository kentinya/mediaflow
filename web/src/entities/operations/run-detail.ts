/**
 * Frontend-owned models for the selected-run detail reads (Slice 42 RO-3).
 *
 * The backend publishes one bounded, secret-free projection per surface:
 * `GET /api/v1/operations/runs/{id}` (overview + progress),
 * `.../items` (server-filtered, server-paged primary items with
 * population totals), `.../records` (the exactly-linked operation-record
 * stream) and `.../items/{itemId}` (one item's durable evidence).
 *
 * Normalization is fail-closed: a disposition outside the modelled set, a
 * partition that does not reconcile to its known total, a success split that
 * does not add up, a cursor outside the bounded grammar or a configuration
 * digest reaching any document makes the whole response malformed instead of
 * being rendered as an approximate truth.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  normalizeTextArray,
  readRecord,
} from "../shared/normalize";
import {
  EFFECT_CERTAINTY_VALUES,
  normalizeTaskItemSummary,
  normalizeTaskResultSummary,
  type TaskItemSummary,
  type TaskResultSummary,
} from "./task";

/** The mutually exclusive primary-item dispositions, in presentation order. */
export const RUN_DISPOSITIONS = [
  "pending",
  "active",
  "waiting",
  "success",
  "skipped",
  "failed_partial",
  "ignored",
  "cancelled",
] as const;
export type RunDisposition = (typeof RUN_DISPOSITIONS)[number];

/** Chinese business labels for the disposition partition. */
export const RUN_DISPOSITION_LABELS: Readonly<Record<RunDisposition, string>> =
  {
    pending: "待处理",
    active: "进行中",
    waiting: "等待中",
    success: "成功",
    skipped: "跳过",
    failed_partial: "失败或部分",
    ignored: "已忽略",
    cancelled: "已取消",
  };

/** Chinese labels for every persisted TaskItemStatus. */
export const RUN_ITEM_STATUS_LABELS: Readonly<Record<string, string>> = {
  pending: "待处理",
  processing: "进行中",
  dry_run: "分析完成",
  success: "成功",
  partial: "部分完成",
  failed: "失败",
  skipped: "跳过",
  cancelled: "已取消",
  waiting_confirm: "等待确认",
  waiting_recognition: "等待识别决策",
  waiting_metadata: "等待元数据决策",
  waiting_metadata_correction: "等待元数据修正",
  waiting_classification: "等待分类决策",
  paused: "已暂停",
  ignored: "已忽略",
};

/** The durable operation-record kinds of the `操作记录` stream. */
export const RUN_RECORD_KINDS = ["result", "evidence", "log", "audit"] as const;
export type RunRecordKind = (typeof RUN_RECORD_KINDS)[number];

export const RUN_RECORD_KIND_LABELS: Readonly<Record<RunRecordKind, string>> = {
  result: "执行结果",
  evidence: "分析与计划",
  log: "运行日志",
  audit: "控制与恢复",
};

/** The bounded cursor grammar a detail URL may carry (mirrors the list). */
export const RUN_DETAIL_CURSOR_TOKEN = /^[A-Za-z0-9._=-]{1,512}$/;
/** One exact persisted item identity. */
export const RUN_DETAIL_ITEM_TOKEN = /^[A-Za-z0-9._:-]{1,256}$/;

function fail(): never {
  throw new Error("operations run detail response did not match the contract");
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

function nullableCount(
  source: Record<string, unknown>,
  field: string,
): number | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  return count(source, field);
}

function nullableFlag(
  source: Record<string, unknown>,
  field: string,
): boolean | null {
  const raw = source[field];
  if (raw === null || raw === undefined) {
    return null;
  }
  return flag(source, field);
}

// -- Progress ---------------------------------------------------------------

export interface RunProgressUnavailable {
  readonly available: false;
  readonly reason: string;
}

export interface RunProgressAvailable {
  readonly available: true;
  readonly kind: string;
  readonly unit: string;
  readonly unitKey: string;
  readonly basis: string;
  readonly successMeans: string;
  /** The known item total; null when discovery totals are indeterminate. */
  readonly knownTotal: number | null;
  readonly indeterminate: boolean;
  readonly processed: number | null;
  readonly dispositions: Readonly<Record<RunDisposition, number>>;
  readonly confirmedSuccess: number;
  readonly uncertainSuccess: number;
  readonly scanErrors: number | null;
  readonly scanDiscoveryComplete: boolean | null;
  readonly scanProgress: Readonly<Record<string, number>>;
  readonly attachmentSteps: number;
  readonly effectCounts: Readonly<Record<string, number>>;
  readonly resultsTotal: number;
  readonly resultsComplete: boolean;
}

export type RunProgress = RunProgressUnavailable | RunProgressAvailable;

function dispositionCounts(
  source: Record<string, unknown>,
): Record<RunDisposition, number> {
  const raw = source["dispositions"];
  const record = readRecord(raw, "progress.dispositions");
  const counts = {} as Record<RunDisposition, number>;
  for (const disposition of RUN_DISPOSITIONS) {
    counts[disposition] = count(record, disposition);
  }
  if (Object.keys(record).length !== RUN_DISPOSITIONS.length) {
    // The partition is exactly the modelled set: an unknown extra
    // disposition would silently break reconciliation.
    fail();
  }
  return counts;
}

function intMap(
  source: Record<string, unknown>,
  field: string,
): Record<string, number> {
  const record = readRecord(source[field], field);
  const values: Record<string, number> = {};
  for (const [key, value] of Object.entries(record)) {
    if (key.length > 64) {
      fail();
    }
    values[key] = normalizeBoundedCount(value, `${field}.${key}`);
  }
  return values;
}

/**
 * Normalize one run's progress projection and prove its arithmetic.
 *
 * The backend guarantees a mutually exclusive partition that reconciles to
 * the known total (with admitted-but-not-yet-materialized rows published
 * inside `pending`), an honest indeterminate state whose total and processed
 * are null, and a success status count split exactly into confirmed plus
 * uncertain — this guard turns any drift into a malformed read.
 */
export function normalizeRunProgress(payload: unknown): RunProgress {
  const source = readRecord(payload, "progress");
  if (!flag(source, "available")) {
    return {
      available: false,
      reason:
        optionalText(source, "reason") ??
        "durable progress evidence is unavailable for this run",
    };
  }
  const indeterminate = flag(source, "indeterminate");
  const knownTotal = nullableCount(source, "known_total");
  const processed = nullableCount(source, "processed");
  const dispositions = dispositionCounts(source);
  const partitionTotal = RUN_DISPOSITIONS.reduce(
    (sum, disposition) => sum + dispositions[disposition],
    0,
  );
  if (indeterminate) {
    if (knownTotal !== null || processed !== null) {
      fail();
    }
  } else {
    if (knownTotal === null || processed === null) {
      fail();
    }
    if (partitionTotal !== knownTotal) {
      // Beyond one page the partition must still reconcile to the total it
      // is reported against.
      fail();
    }
    const expected = Math.max(
      knownTotal - dispositions.pending - dispositions.active,
      0,
    );
    if (processed !== expected) {
      fail();
    }
  }
  const confirmedSuccess = count(source, "confirmed_success");
  const uncertainSuccess = count(source, "uncertain_success");
  if (confirmedSuccess + uncertainSuccess !== dispositions.success) {
    // Uncertain-effect items are carved out of the success status count,
    // never invented and never double-counted.
    fail();
  }
  const scanProgress = intMap(source, "scan_progress");
  const effectCounts = intMap(source, "effect_counts");
  const kind = text(source, "kind");
  const unit = text(source, "unit");
  if (
    ![
      "scan",
      "analysis",
      "organize",
      "direct",
      "transfer",
      "recovery",
      "task",
    ].includes(kind)
  ) {
    // An unmodelled accounting basis cannot be labelled honestly.
    fail();
  }
  return {
    available: true,
    kind,
    unit,
    unitKey: text(source, "unit_key"),
    basis: text(source, "basis"),
    successMeans: text(source, "success_means"),
    knownTotal,
    indeterminate,
    processed,
    dispositions,
    confirmedSuccess,
    uncertainSuccess,
    scanErrors: nullableCount(source, "scan_errors"),
    scanDiscoveryComplete: nullableFlag(source, "scan_discovery_complete"),
    scanProgress,
    attachmentSteps: count(source, "attachment_steps"),
    effectCounts,
    resultsTotal: count(source, "results_total"),
    resultsComplete: flag(source, "results_complete"),
  };
}

// -- Item pages -------------------------------------------------------------

export interface RunItemsPage {
  readonly runId: string;
  readonly taskId: string | null;
  readonly statusFilter: RunDisposition | null;
  readonly limit: number;
  readonly items: readonly TaskItemSummary[];
  /** The whole authorized population (page-independent). */
  readonly total: number;
  /** The population matching the submitted filter (page-independent). */
  readonly matchingTotal: number;
  readonly dispositions: Readonly<Record<RunDisposition, number>>;
  readonly uncertainSuccess: number;
  readonly truncated: boolean;
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
  /** Explicit pre-Task unavailability, never a fabricated empty success. */
  readonly unavailable: string | null;
}

export function normalizeRunItemsPage(payload: unknown): RunItemsPage {
  const source = readRecord(payload, "run items");
  const rawFilter = source["filter"];
  const filterRecord = readRecord(rawFilter, "items.filter");
  const rawStatus = filterRecord["status"];
  let statusFilter: RunDisposition | null = null;
  if (rawStatus !== null && rawStatus !== undefined) {
    statusFilter = normalizeEnum(
      rawStatus,
      "items.filter.status",
      RUN_DISPOSITIONS,
    );
  }
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    fail();
  }
  const items = rawItems.map((item) =>
    normalizeTaskItemSummary(readRecord(item, "item")),
  );
  const dispositions = dispositionCounts(source);
  const total = count(source, "total");
  const matchingTotal = count(source, "matching_total");
  const partitionTotal = RUN_DISPOSITIONS.reduce(
    (sum, disposition) => sum + dispositions[disposition],
    0,
  );
  if (partitionTotal !== total) {
    fail();
  }
  if (matchingTotal > total) {
    fail();
  }
  if (statusFilter === null && matchingTotal !== total) {
    fail();
  }
  if (statusFilter !== null && items.length > matchingTotal) {
    fail();
  }
  return {
    runId: text(source, "run_id"),
    taskId: optionalText(source, "task_id"),
    statusFilter,
    limit: count(source, "limit"),
    items,
    total,
    matchingTotal,
    dispositions,
    uncertainSuccess: count(source, "uncertain_success"),
    truncated: flag(source, "truncated"),
    previousCursor: optionalText(source, "previous_cursor"),
    nextCursor: optionalText(source, "next_cursor"),
    unavailable: optionalText(source, "unavailable"),
  };
}

// -- Operation records ------------------------------------------------------

export interface RunRecordEvidenceSummary {
  readonly evidenceId: string;
  readonly attempts: number;
  readonly outcome: string;
  readonly capturedAt: string;
  readonly truncated: boolean;
  readonly sectionsAvailable: readonly string[];
}

export interface RunRecord {
  readonly recordId: string;
  readonly kind: RunRecordKind;
  readonly kindLabel: string;
  readonly occurredAt: string;
  readonly itemId: string | null;
  /** Log records. */
  readonly level: string | null;
  readonly event: string | null;
  readonly component: string | null;
  readonly status: string | null;
  readonly planId: string | null;
  /** Audit records. */
  readonly action: string | null;
  readonly state: string | null;
  readonly actor: string | null;
  readonly parentId: string | null;
  /** Result/evidence payloads. */
  readonly result: TaskResultSummary | null;
  readonly evidence: RunRecordEvidenceSummary | null;
}

export interface RunRecordsPage {
  readonly runId: string;
  readonly taskId: string | null;
  readonly jobId: string | null;
  readonly kindFilter: RunRecordKind | null;
  readonly limit: number;
  readonly records: readonly RunRecord[];
  readonly matchingTotal: number;
  readonly kindCounts: Readonly<Record<RunRecordKind, number>>;
  readonly truncated: boolean;
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
}

function normalizeRunRecord(payload: unknown): RunRecord {
  const source = readRecord(payload, "record");
  const kind = normalizeEnum(source["kind"], "record.kind", RUN_RECORD_KINDS);
  const itemId = optionalText(source, "item_id");
  let result: TaskResultSummary | null = null;
  let evidence: RunRecordEvidenceSummary | null = null;
  if (kind === "result") {
    result = normalizeTaskResultSummary(
      readRecord(source["result"], "record.result"),
    );
    if (result.itemId !== itemId) {
      // The row's linkage and payload must name the same item.
      fail();
    }
  } else if (kind === "evidence") {
    const raw = readRecord(source["evidence"], "record.evidence");
    evidence = {
      evidenceId: text(raw, "evidence_id"),
      attempts: count(raw, "attempts"),
      outcome: text(raw, "outcome"),
      capturedAt: text(raw, "captured_at"),
      truncated: flag(raw, "truncated"),
      sectionsAvailable: normalizeTextArray(
        raw["sections_available"],
        "record.evidence.sections_available",
        32,
      ),
    };
    if (
      evidence.sectionsAvailable.length === 0 &&
      evidence.outcome.length === 0
    ) {
      fail();
    }
  }
  return {
    recordId: text(source, "record_id"),
    kind,
    kindLabel: text(source, "kind_label"),
    occurredAt: text(source, "occurred_at"),
    itemId,
    level: optionalText(source, "level"),
    event: optionalText(source, "event"),
    component: optionalText(source, "component"),
    status: optionalText(source, "status"),
    planId: optionalText(source, "plan_id"),
    action: optionalText(source, "action"),
    state: optionalText(source, "state"),
    actor: optionalText(source, "actor"),
    parentId: optionalText(source, "parent_id"),
    result,
    evidence,
  };
}

export function normalizeRunRecordsPage(payload: unknown): RunRecordsPage {
  const source = readRecord(payload, "run records");
  const filterRecord = readRecord(source["filter"], "records.filter");
  const rawKind = filterRecord["kind"];
  let kindFilter: RunRecordKind | null = null;
  if (rawKind !== null && rawKind !== undefined) {
    kindFilter = normalizeEnum(
      rawKind,
      "records.filter.kind",
      RUN_RECORD_KINDS,
    );
  }
  const rawRecords = source["records"];
  if (!Array.isArray(rawRecords) || rawRecords.length > 100) {
    fail();
  }
  const records = rawRecords.map((record) => normalizeRunRecord(record));
  const countsSource = readRecord(source["kind_counts"], "records.kind_counts");
  const kindCounts = {} as Record<RunRecordKind, number>;
  let countSum = 0;
  for (const kind of RUN_RECORD_KINDS) {
    kindCounts[kind] = count(countsSource, kind);
    countSum += kindCounts[kind];
  }
  if (Object.keys(countsSource).length !== RUN_RECORD_KINDS.length) {
    fail();
  }
  const matchingTotal = count(source, "matching_total");
  if (kindFilter === null) {
    if (countSum !== matchingTotal) {
      fail();
    }
  } else if (kindCounts[kindFilter] !== matchingTotal) {
    // A filtered total must equal that kind's whole-population count.
    fail();
  }
  if (records.length > matchingTotal) {
    fail();
  }
  return {
    runId: text(source, "run_id"),
    taskId: optionalText(source, "task_id"),
    jobId: optionalText(source, "job_id"),
    kindFilter,
    limit: count(source, "limit"),
    records,
    matchingTotal,
    kindCounts,
    truncated: flag(source, "truncated"),
    previousCursor: optionalText(source, "previous_cursor"),
    nextCursor: optionalText(source, "next_cursor"),
  };
}

// -- One item's evidence ----------------------------------------------------

export interface RunEvidenceAudit {
  readonly auditId: string;
  readonly kind: string;
  readonly occurredAt: string;
  readonly actor: string | null;
}

export interface RunItemCheckpoint {
  readonly status: string;
  readonly stage: string;
  readonly rawStage: string;
  readonly planId: string | null;
  readonly snapshotId: string | null;
  readonly snapshotResolvable: boolean;
  readonly effectCertainty: string;
  readonly retrySafety: string;
  readonly errorCategory: string | null;
  readonly refusalReason: string | null;
  readonly nextAction: string | null;
  readonly blockerKind: string | null;
  readonly blockerId: string | null;
  readonly failureCategory: string | null;
  readonly audits: readonly RunEvidenceAudit[];
  readonly permittedActionIds: readonly string[];
  readonly checkpointVersion: string | null;
}

export interface RunEvidenceSection {
  readonly name: string;
  readonly available: boolean;
  readonly unavailableReason: string | null;
  readonly truncated: boolean;
}

export interface RunEvidenceDocument {
  readonly evidenceId: string;
  readonly attempts: number;
  readonly outcome: string;
  readonly capturedAt: string;
  readonly truncated: boolean;
  readonly sections: readonly RunEvidenceSection[];
}

export interface RunItemEvidence {
  readonly runId: string;
  readonly taskId: string;
  readonly itemId: string;
  readonly item: TaskItemSummary;
  readonly checkpoint: RunItemCheckpoint;
  readonly results: readonly TaskResultSummary[];
  readonly evidence: readonly RunEvidenceDocument[];
  readonly logs: readonly RunRecord[];
}

function normalizeCheckpoint(payload: unknown): RunItemCheckpoint {
  const source = readRecord(payload, "checkpoint");
  const configuration = readRecord(
    source["configuration"],
    "checkpoint.configuration",
  );
  if ("snapshot_digest" in configuration) {
    // The configuration snapshot digest is a fingerprint and must never
    // reach the browser; its presence is a contract violation, not data.
    fail();
  }
  const effects = readRecord(source["effects"], "checkpoint.effects");
  const failure = source["failureExplanation"];
  let failureCategory: string | null = null;
  if (failure !== null && failure !== undefined) {
    failureCategory = text(
      readRecord(failure, "checkpoint.failureExplanation"),
      "category",
    );
  }
  const rawAudits = source["audits"];
  if (!Array.isArray(rawAudits) || rawAudits.length > 200) {
    fail();
  }
  const audits = rawAudits.map((value): RunEvidenceAudit => {
    const record = readRecord(value, "checkpoint.audits[]");
    return {
      auditId: text(record, "audit_id"),
      kind: text(record, "kind"),
      occurredAt: text(record, "occurred_at"),
      actor: optionalText(record, "actor"),
    };
  });
  const blocker = source["blocker"];
  let blockerKind: string | null = null;
  let blockerId: string | null = null;
  if (blocker !== null && blocker !== undefined) {
    const record = readRecord(blocker, "checkpoint.blocker");
    blockerKind = optionalText(record, "kind");
    blockerId = optionalText(record, "id");
  }
  return {
    status: text(source, "status"),
    stage: text(source, "stage"),
    rawStage: text(source, "raw_stage"),
    planId: optionalText(source, "plan_id"),
    snapshotId: optionalText(configuration, "snapshot_id"),
    snapshotResolvable: flag(configuration, "resolvable"),
    effectCertainty: text(effects, "certainty"),
    retrySafety: text(source, "retry_safety"),
    errorCategory: optionalText(source, "error_category"),
    refusalReason: optionalText(source, "refusal_reason"),
    nextAction: optionalText(source, "nextAction"),
    blockerKind,
    blockerId,
    failureCategory,
    audits,
    permittedActionIds: normalizeTextArray(
      source["permitted_action_ids"] ?? [],
      "checkpoint.permitted_action_ids",
      32,
    ),
    checkpointVersion: optionalText(source, "checkpoint_version"),
  };
}

function normalizeEvidenceDocument(payload: unknown): RunEvidenceDocument {
  const source = readRecord(payload, "evidence");
  if ("configurationSnapshotDigest" in source) {
    // Same privacy contract as the checkpoint: no fingerprint values.
    fail();
  }
  const sections = readRecord(source["sections"], "evidence.sections");
  const values: RunEvidenceSection[] = [];
  for (const [name, raw] of Object.entries(sections)) {
    const record = readRecord(raw, "evidence.sections[]");
    values.push({
      name,
      available: flag(record, "available"),
      unavailableReason: optionalText(record, "unavailableReason"),
      truncated: flag(record, "truncated"),
    });
  }
  if (values.length > 32) {
    fail();
  }
  return {
    evidenceId: text(source, "evidenceId"),
    attempts: count(source, "attempts"),
    outcome: text(source, "outcome"),
    capturedAt: text(source, "capturedAt"),
    truncated: flag(source, "truncated"),
    sections: values,
  };
}

export function normalizeRunItemEvidence(payload: unknown): RunItemEvidence {
  const source = readRecord(payload, "run item evidence");
  const rawLogs = source["logs"];
  if (!Array.isArray(rawLogs) || rawLogs.length > 100) {
    fail();
  }
  const logs = rawLogs.map((value) => {
    const record = normalizeRunRecord(value);
    if (record.kind !== "log") {
      fail();
    }
    return record;
  });
  const itemId = text(source, "item_id");
  const item = normalizeTaskItemSummary(
    readRecord(source["item"], "evidence.item"),
  );
  const checkpoint = normalizeCheckpoint(source["checkpoint"]);
  if (item.itemId !== itemId || checkpoint.status.length === 0) {
    fail();
  }
  const rawResults = source["results"];
  if (!Array.isArray(rawResults) || rawResults.length > 100) {
    fail();
  }
  const results = rawResults.map((value) =>
    normalizeTaskResultSummary(readRecord(value, "evidence.results[]")),
  );
  const rawEvidence = source["evidence"];
  if (!Array.isArray(rawEvidence) || rawEvidence.length > 100) {
    fail();
  }
  const evidence = rawEvidence.map((value) => normalizeEvidenceDocument(value));
  return {
    runId: text(source, "run_id"),
    taskId: text(source, "task_id"),
    itemId,
    item,
    checkpoint,
    results,
    evidence,
    logs,
  };
}

// -- Result package export --------------------------------------------------

export interface RunExportPackage {
  readonly packageKind: string;
  readonly packageSchemaVersion: number;
  readonly taskId: string;
  readonly taskCommand: string;
  readonly limit: number;
  readonly ordering: string;
  readonly truncated: boolean;
  readonly warningCodes: readonly string[];
  readonly resultCount: number;
  readonly packageDigest: string;
}

/** The committed result-package interchange kind and schema. */
const RESULT_PACKAGE_KIND = "mediaflow.results.v1";
const RESULT_PACKAGE_SCHEMA_VERSION = 1;

/**
 * Validate one `mediaflow.results.v1` result row.
 *
 * The package is the committed public interchange format: its rows are
 * camelCase (`resultId`, `effectCertainty`, `uncertainEffects`, ...) and NOT
 * the snake_case operator documents the detail reads publish. The row is
 * validated structurally — closed effect certainty, the same
 * uncertain-effects ⇔ attempted_unverified agreement the TaskItem Result
 * model enforces, bounded arrays and exact item linkage — but its payload is
 * handed to the download untouched, so the saved file stays byte-faithful to
 * the package contract.
 */
function normalizePackageResultRow(value: unknown): readonly [string, string] {
  const source = readRecord(value, "package.results[]");
  let effectCertainty: string;
  try {
    effectCertainty = normalizeEnum(
      source["effectCertainty"],
      "package.results[].effectCertainty",
      EFFECT_CERTAINTY_VALUES,
    );
  } catch {
    return fail();
  }
  let uncertainEffects: readonly string[];
  let completedOperations: readonly string[];
  try {
    uncertainEffects = normalizeTextArray(
      source["uncertainEffects"] ?? [],
      "package.results[].uncertainEffects",
      32,
    );
    completedOperations = normalizeTextArray(
      source["completedOperations"] ?? [],
      "package.results[].completedOperations",
      32,
    );
  } catch {
    return fail();
  }
  if (
    uncertainEffects.length > 0 !==
    (effectCertainty === "attempted_unverified")
  ) {
    // Unverified effect evidence and its explicit effect list must agree,
    // exactly as the operator Result model requires.
    fail();
  }
  if (!Array.isArray(completedOperations)) {
    fail();
  }
  const attachmentCount = count(source, "attachmentCount");
  const retryAttempts = count(source, "retryAttempts");
  const cleanupStepCount = count(source, "cleanupStepCount");
  if (
    attachmentCount > 10_000 ||
    retryAttempts > 10_000 ||
    cleanupStepCount > 10_000
  ) {
    fail();
  }
  return [text(source, "taskId"), text(source, "itemId")];
}

/**
 * Normalize one exported result package.  The download is offered only when
 * this contract holds, so a failed or malformed export can never become an
 * empty "successful" download.
 */
export function normalizeRunExportPackage(payload: unknown): RunExportPackage {
  const source = readRecord(payload, "export package");
  const packageKind = text(source, "packageKind");
  if (packageKind !== RESULT_PACKAGE_KIND) {
    // A different package kind is not the result package this action names.
    fail();
  }
  const packageSchemaVersion = count(source, "packageSchemaVersion");
  if (packageSchemaVersion !== RESULT_PACKAGE_SCHEMA_VERSION) {
    fail();
  }
  const rawResults = source["results"];
  if (!Array.isArray(rawResults) || rawResults.length > 500) {
    fail();
  }
  const rows = rawResults.map((value) => normalizePackageResultRow(value));
  const redaction = readRecord(source["redaction"], "package.redaction");
  const redactionCount = count(redaction, "entryCount");
  if (redactionCount > 256) {
    fail();
  }
  const rawWarnings = source["warning"];
  if (!Array.isArray(rawWarnings) || rawWarnings.length > 8) {
    fail();
  }
  const warningCodes = rawWarnings.map((value) =>
    text(readRecord(value, "package.warning[]"), "code"),
  );
  const truncated = flag(source, "truncated");
  if (truncated && !warningCodes.includes("results_truncated")) {
    // A truncated package must say so.
    fail();
  }
  const sourceScope = readRecord(source["source"], "package.source");
  const ordering = text(sourceScope, "ordering");
  if (ordering !== "created_at_asc,result_id_asc") {
    fail();
  }
  const taskId = text(sourceScope, "taskId");
  for (const [rowTaskId, rowItemId] of rows) {
    if (rowTaskId !== taskId || rowItemId.length === 0) {
      // Every row must belong to the exact scoped Task the package claims.
      fail();
    }
  }
  return {
    packageKind,
    packageSchemaVersion,
    taskId,
    taskCommand: text(sourceScope, "taskCommand"),
    limit: count(sourceScope, "limit"),
    ordering,
    truncated,
    warningCodes,
    resultCount: rows.length,
    packageDigest: text(source, "packageDigest"),
  };
}
