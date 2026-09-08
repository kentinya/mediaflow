/**
 * Frontend-owned Dashboard entity.
 *
 * The Python contract (`GET /api/v1/dashboard`) returns the read-only
 * operational snapshot in snake_case. This module owns the strict frontend
 * model and its normalization: unknown extra fields are ignored, but any
 * missing or wrongly typed required field makes the whole response malformed
 * so the UI never fabricates unavailable counts or details.
 */

export interface DashboardFileCounts {
  readonly total: number;
  readonly ready: number;
  readonly unstable: number;
  readonly missing: number;
  readonly errors: number;
}

export interface DashboardTaskCounts {
  readonly total: number;
  readonly pending: number;
  readonly running: number;
  readonly completed: number;
  readonly partialSuccess: number;
  readonly failed: number;
  readonly cancelled: number;
  readonly paused: number;
}

export interface DashboardJobCounts {
  readonly total: number;
  readonly pending: number;
  readonly running: number;
  readonly completed: number;
  readonly failed: number;
  readonly cancelled: number;
}

export interface DashboardRecentFailure {
  readonly kind: string;
  readonly identifier: string;
  readonly status: string;
  readonly occurredAt: string;
  readonly category: string;
}

export interface DashboardModel {
  readonly asOf: string;
  readonly resourceLibraries: number;
  readonly mediaLibraries: number;
  readonly files: DashboardFileCounts;
  readonly tasks: DashboardTaskCounts;
  readonly jobs: DashboardJobCounts;
  readonly pendingConfirmations: number;
  readonly pendingMetadataReviews: number;
  readonly pendingClassificationReviews: number;
  readonly deadLetterNotifications: number;
  readonly recentFailures: readonly DashboardRecentFailure[];
}

export class DashboardNormalizationError extends Error {
  constructor() {
    super("dashboard response did not match the expected read-only contract");
    this.name = "DashboardNormalizationError";
  }
}

const MAX_TEXT_LENGTH = 1024;

function readRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new DashboardNormalizationError();
  }
  return value as Record<string, unknown>;
}

function readBoundedCount(
  source: Record<string, unknown>,
  field: string,
): number {
  const value = source[field];
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new DashboardNormalizationError();
  }
  return value;
}

function readBoundedText(
  source: Record<string, unknown>,
  field: string,
): string {
  const value = source[field];
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > MAX_TEXT_LENGTH
  ) {
    throw new DashboardNormalizationError();
  }
  return value;
}

function readFileCounts(source: Record<string, unknown>): DashboardFileCounts {
  return {
    total: readBoundedCount(source, "total"),
    ready: readBoundedCount(source, "ready"),
    unstable: readBoundedCount(source, "unstable"),
    missing: readBoundedCount(source, "missing"),
    errors: readBoundedCount(source, "errors"),
  };
}

function readTaskCounts(source: Record<string, unknown>): DashboardTaskCounts {
  return {
    total: readBoundedCount(source, "total"),
    pending: readBoundedCount(source, "pending"),
    running: readBoundedCount(source, "running"),
    completed: readBoundedCount(source, "completed"),
    partialSuccess: readBoundedCount(source, "partial_success"),
    failed: readBoundedCount(source, "failed"),
    cancelled: readBoundedCount(source, "cancelled"),
    paused: readBoundedCount(source, "paused"),
  };
}

function readJobCounts(source: Record<string, unknown>): DashboardJobCounts {
  return {
    total: readBoundedCount(source, "total"),
    pending: readBoundedCount(source, "pending"),
    running: readBoundedCount(source, "running"),
    completed: readBoundedCount(source, "completed"),
    failed: readBoundedCount(source, "failed"),
    cancelled: readBoundedCount(source, "cancelled"),
  };
}

function readRecentFailure(value: unknown): DashboardRecentFailure {
  const source = readRecord(value);
  return {
    kind: readBoundedText(source, "kind"),
    identifier: readBoundedText(source, "identifier"),
    status: readBoundedText(source, "status"),
    occurredAt: readBoundedText(source, "occurred_at"),
    category: readBoundedText(source, "category"),
  };
}

export function normalizeDashboard(payload: unknown): DashboardModel {
  const source = readRecord(payload);
  const failures = source["recent_failures"];
  if (!Array.isArray(failures)) {
    throw new DashboardNormalizationError();
  }
  return {
    asOf: readBoundedText(source, "as_of"),
    resourceLibraries: readBoundedCount(source, "resource_libraries"),
    mediaLibraries: readBoundedCount(source, "media_libraries"),
    files: readFileCounts(readRecord(source["files"])),
    tasks: readTaskCounts(readRecord(source["tasks"])),
    jobs: readJobCounts(readRecord(source["jobs"])),
    pendingConfirmations: readBoundedCount(source, "pending_confirmations"),
    pendingMetadataReviews: readBoundedCount(
      source,
      "pending_metadata_reviews",
    ),
    pendingClassificationReviews: readBoundedCount(
      source,
      "pending_classification_reviews",
    ),
    deadLetterNotifications: readBoundedCount(
      source,
      "dead_letter_notifications",
    ),
    recentFailures: failures.map(readRecentFailure),
  };
}

/**
 * The honest empty state: nothing has been indexed, planned or run yet.
 * The Dashboard never substitutes unavailable details for this state.
 */
export function isDashboardEmpty(model: DashboardModel): boolean {
  return (
    model.files.total === 0 && model.tasks.total === 0 && model.jobs.total === 0
  );
}
