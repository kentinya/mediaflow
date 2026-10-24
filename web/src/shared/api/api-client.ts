/**
 * Central typed API client for the V2 frontend's read-only contracts.
 *
 * This is the single server-state boundary of the V2 frontend: requests carry
 * the API-principal Bearer token from runtime memory only, responses are
 * strictly normalized into frontend-owned models, and every failure becomes
 * one bounded, secret-free error category. No other module may call the API
 * directly.
 */

import {
  normalizeDashboard,
  type DashboardModel,
} from "../../entities/dashboard/dashboard";
import {
  normalizeSystemStatus,
  type SystemStorage,
  type SystemStatusModel,
} from "../../entities/library/system-status";
import {
  normalizeStorageFiles,
  type StorageFilesModel,
} from "../../entities/library/storage-files";
import {
  normalizeMediaLibraryFiles,
  normalizeMediaLibraryList,
  type MediaLibraryFilesModel,
  type MediaLibraryListModel,
} from "../../entities/library/media-library-files";
import {
  normalizeResourceLibrarySave,
  type ResourceLibrarySaveModel,
} from "../../entities/library/resource-library";
import {
  MEDIA_LIBRARY_ID,
  normalizeMediaLibraryRemoval,
  normalizeMediaLibraryRemovalPreview,
  normalizeMediaLibrarySave,
  type MediaLibraryRemovalModel,
  type MediaLibraryRemovalPreviewModel,
  type MediaLibrarySaveModel,
} from "../../entities/library/media-library";
import {
  type DirectCommandLibraryKind,
  libraryIdField,
  normalizeDeleteImpact,
  normalizeDirectFileCommandResult,
  normalizeRemovalPreview,
  normalizeRenameEvidence,
  normalizeResourceLibraryRemoval,
  normalizeTextFileDocument,
  normalizeTransferImpact,
  normalizeTransferProjection,
  normalizeTransferResult,
  type DeleteImpactModel,
  type DirectFileCommandResult,
  type RemovalPreviewModel,
  type RenameEvidenceModel,
  type ResourceLibraryRemovalModel,
  type TextFileDocument,
  type TransferConflictMode,
  type TransferImpactModel,
  type TransferOperation,
  type TransferProjectionModel,
  type TransferResultModel,
} from "../../entities/library/direct-files";
import {
  ApiReadError,
  type ApiReadErrorCategory,
  DashboardApiError,
  MediaLibraryFilesApiError,
  StorageFilesApiError,
  SystemStatusApiError,
} from "./api-errors";
import {
  normalizeRulesWorkspace,
  type RuleFamily,
  type RulesWorkspaceModel,
} from "../../entities/rules/rules-workspace";
import {
  normalizeManualRecoveryLink,
  normalizeManualRecoveryPreparation,
  normalizeMetadataSearch,
  normalizeRecoveryBatch,
  normalizeTaskItemRecovery,
  type ManualRecoveryLinkModel,
  type ManualRecoveryPreparationModel,
  type MetadataSearchModel,
  type RecoveryBatchModel,
  type TaskItemRecoveryModel,
} from "../../entities/operations/task-item-recovery";

/**
 * The bounded recentLimit used by the proving route; the existing API accepts
 * 1..50 and defaults to 10.
 */
export const DASHBOARD_RECENT_LIMIT = 10;

export type FetchLike = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

export function dashboardUrl(): string {
  return `/api/v1/dashboard?recentLimit=${DASHBOARD_RECENT_LIMIT}`;
}

interface ErrorEnvelope {
  readonly code?: string;
  readonly details?: unknown;
}

/**
 * Read the stable, secret-free `error.code` / `error.details` envelope once.
 * The response is cloned so the caller keeps its own body stream.
 */
async function readErrorEnvelope(response: Response): Promise<ErrorEnvelope> {
  try {
    const body = (await response.clone().json()) as { error?: ErrorEnvelope };
    return body?.error ?? {};
  } catch {
    return {};
  }
}

export async function fetchDashboard(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<DashboardModel> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl(dashboardUrl(), { method: "GET", headers });
  } catch {
    throw new DashboardApiError("unavailable");
  }
  if (response.status === 401) {
    throw new DashboardApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new DashboardApiError("forbidden");
  }
  if (response.status >= 500) {
    throw new DashboardApiError("unavailable");
  }
  if (!response.ok) {
    throw new DashboardApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new DashboardApiError("malformed");
  }
  try {
    return normalizeDashboard(payload);
  } catch {
    throw new DashboardApiError("malformed");
  }
}

export async function fetchSystemStatus(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<SystemStatusModel> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/system/status", {
      method: "GET",
      headers,
    });
  } catch {
    throw new SystemStatusApiError("unavailable");
  }
  if (response.status === 401) {
    throw new SystemStatusApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new SystemStatusApiError("forbidden");
  }
  if (response.status >= 500) {
    const envelope = await readErrorEnvelope(response);
    if (envelope.code === "configuration_unavailable") {
      throw new SystemStatusApiError("rejected");
    }
    throw new SystemStatusApiError("unavailable");
  }
  if (!response.ok) {
    throw new SystemStatusApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new SystemStatusApiError("malformed");
  }
  try {
    return normalizeSystemStatus(payload);
  } catch {
    throw new SystemStatusApiError("malformed");
  }
}

/**
 * Bounded, secret-free reason a Files read did not return a document.
 *
 * A Storage-provider read/permission failure is explicitly NOT an API-principal
 * RBAC denial: the operator is still authorized, only the provider read
 * failed. Returning it as a result instead of an error keeps the shared
 * boundary from clearing a valid authority, and lets the feature render the
 * backend-supplied bounded next action.
 */
export type StorageFilesFailureKind =
  | "storage_unavailable"
  | "configuration_unavailable"
  | "storage_not_found"
  | "storage_disabled"
  | "invalid_path"
  | "not_found"
  | "not_directory"
  | "invalid_cursor"
  | "resource_library_not_found"
  | "resource_library_mismatch"
  | "rejected";

export interface StorageFilesFailure {
  readonly kind: StorageFilesFailureKind;
  readonly title: string;
  readonly nextAction: string;
}

export type StorageFilesRead =
  | { readonly ok: true; readonly model: StorageFilesModel }
  | { readonly ok: false; readonly failure: StorageFilesFailure };

const STORAGE_FILES_FAILURE_TITLES: Readonly<
  Record<StorageFilesFailureKind, string>
> = {
  storage_unavailable: "Storage read failed",
  configuration_unavailable: "No Active runtime",
  storage_not_found: "Storage not found",
  storage_disabled: "Storage disabled",
  invalid_path: "Invalid Storage-relative path",
  not_found: "Directory not found",
  not_directory: "Not a directory",
  invalid_cursor: "Page continuation no longer valid",
  resource_library_not_found: "ResourceLibrary not available",
  resource_library_mismatch: "ResourceLibrary does not use this Storage",
  rejected: "Request rejected",
};

const PROVIDER_FAILURE_CATEGORIES: readonly string[] = [
  "permission_denied",
  "authentication_failed",
  "connection_failed",
  "timeout",
  "rate_limited",
  "missing_secret",
  "invalid_configuration",
  "symlink_not_traversable",
  "symlink_not_selectable",
  "malformed_response",
  "unknown",
];

const DEFAULT_NEXT_ACTION =
  "Reload the current Active runtime and retry the same browse.";

function envelopeHasKnownStorageFailure(envelope: ErrorEnvelope): boolean {
  if (envelope.code === "configuration_unavailable") {
    return true;
  }
  if (
    typeof envelope.code === "string" &&
    envelope.code.startsWith("storage_browser_")
  ) {
    return true;
  }
  const details =
    envelope.details !== null &&
    typeof envelope.details === "object" &&
    !Array.isArray(envelope.details)
      ? (envelope.details as Record<string, unknown>)
      : {};
  return (
    typeof details.category === "string" &&
    PROVIDER_FAILURE_CATEGORIES.includes(details.category)
  );
}

function failureFromErrorEnvelope(
  code: string | undefined,
  details: unknown,
): StorageFilesFailure {
  const record =
    details !== null && typeof details === "object"
      ? (details as Record<string, unknown>)
      : {};
  const category =
    typeof record.category === "string" ? record.category : undefined;
  const nextAction =
    typeof record.nextAction === "string" && record.nextAction.length > 0
      ? record.nextAction
      : DEFAULT_NEXT_ACTION;
  let kind: StorageFilesFailureKind = "rejected";
  if (category !== undefined) {
    if (PROVIDER_FAILURE_CATEGORIES.includes(category)) {
      kind = "storage_unavailable";
    } else if (category === "storage_not_found") {
      kind = "storage_not_found";
    } else if (category === "disabled") {
      kind = "storage_disabled";
    } else if (category === "invalid_path") {
      kind = "invalid_path";
    } else if (category === "not_found") {
      kind = "not_found";
    } else if (category === "not_directory") {
      kind = "not_directory";
    } else if (category === "cursor_invalid" || category === "cursor_expired") {
      kind = "invalid_cursor";
    } else if (category === "resource_library_not_found") {
      kind = "resource_library_not_found";
    } else if (category === "resource_library_mismatch") {
      kind = "resource_library_mismatch";
    }
  } else if (code === "configuration_unavailable") {
    kind = "configuration_unavailable";
  }
  return { kind, title: STORAGE_FILES_FAILURE_TITLES[kind], nextAction };
}

function isSafeScopedIdentifier(value: string): boolean {
  return (
    value.length > 0 &&
    value.length <= 1024 &&
    !value.includes("/") &&
    !value.includes("\\") &&
    // eslint-disable-next-line no-control-regex
    !/[\u0000-\u001f\u007f]/.test(value)
  );
}

export type StorageFilesQueryOptions = {
  readonly resourceLibraryId: string;
  readonly path?: string;
  readonly cursor?: string | null;
};

export function storageFilesUrl(options: StorageFilesQueryOptions): string {
  const params = new URLSearchParams();
  if (options.path !== undefined && options.path !== "") {
    params.set("path", options.path);
  }
  if (options.cursor !== undefined && options.cursor !== null) {
    params.set("cursor", options.cursor);
  }
  const qs = params.toString();
  return `/api/v1/resource-libraries/${encodeURIComponent(options.resourceLibraryId)}/files${qs ? `?${qs}` : ""}`;
}

export async function fetchStorageFiles(
  token: string | null,
  options: StorageFilesQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<StorageFilesRead> {
  if (!isSafeScopedIdentifier(options.resourceLibraryId)) {
    return {
      ok: false,
      failure: failureFromErrorEnvelope(
        "storage_browser_resource_library_not_found",
        {
          category: "resource_library_not_found",
        },
      ),
    };
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl(storageFilesUrl(options), {
      method: "GET",
      headers,
    });
  } catch {
    throw new StorageFilesApiError("unavailable");
  }
  // Authentication rejection is owned by the shared authorized-read boundary,
  // which clears the rejected authority and cache exactly once.
  if (response.status === 401) {
    throw new StorageFilesApiError("unauthorized");
  }
  // A 403 is either an API-principal RBAC denial (stable code "forbidden") or
  // a Storage-provider permission failure (stable code
  // "storage_browser_permission_denied"). Only the former may clear a valid
  // authority; the latter is a bounded read failure with Storage-specific
  // recovery.
  if (response.status === 403) {
    const envelope = await readErrorEnvelope(response);
    if (envelope.code === "forbidden") {
      throw new StorageFilesApiError("forbidden");
    }
    return {
      ok: false,
      failure: failureFromErrorEnvelope(envelope.code, envelope.details),
    };
  }
  if (response.status >= 500) {
    const envelope = await readErrorEnvelope(response);
    if (envelopeHasKnownStorageFailure(envelope)) {
      return {
        ok: false,
        failure: failureFromErrorEnvelope(envelope.code, envelope.details),
      };
    }
    throw new StorageFilesApiError("unavailable");
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      failure: failureFromErrorEnvelope(envelope.code, envelope.details),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new StorageFilesApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeStorageFiles(payload) };
  } catch {
    throw new StorageFilesApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// MediaLibrary read-only browse API (Slice 38)
// ---------------------------------------------------------------------------

export type MediaLibraryFilesFailureKind =
  | "storage_unavailable"
  | "configuration_unavailable"
  | "storage_not_found"
  | "storage_disabled"
  | "invalid_path"
  | "not_found"
  | "not_directory"
  | "invalid_cursor"
  | "media_library_not_found"
  | "rejected";

export interface MediaLibraryFilesFailure {
  readonly kind: MediaLibraryFilesFailureKind;
  readonly title: string;
  readonly nextAction: string;
}

export type MediaLibraryFilesRead =
  | { readonly ok: true; readonly model: MediaLibraryFilesModel }
  | { readonly ok: false; readonly failure: MediaLibraryFilesFailure };

const MEDIA_LIBRARY_FILES_FAILURE_TITLES: Readonly<
  Record<MediaLibraryFilesFailureKind, string>
> = {
  storage_unavailable: "Storage read failed",
  configuration_unavailable: "No Active runtime",
  storage_not_found: "Storage not found",
  storage_disabled: "Storage disabled",
  invalid_path: "Invalid MediaLibrary-relative path",
  not_found: "Directory not found",
  not_directory: "Not a directory",
  invalid_cursor: "Page continuation no longer valid",
  media_library_not_found: "MediaLibrary not available",
  rejected: "Request rejected",
};

const DEFAULT_MEDIA_NEXT_ACTION =
  "Reload the current Active runtime and retry the same browse.";

function mediaFailureFromErrorEnvelope(
  code: string | undefined,
  details: unknown,
): MediaLibraryFilesFailure {
  const record =
    details !== null && typeof details === "object"
      ? (details as Record<string, unknown>)
      : {};
  const category =
    typeof record.category === "string" ? record.category : undefined;
  const nextAction =
    typeof record.nextAction === "string" && record.nextAction.length > 0
      ? record.nextAction
      : DEFAULT_MEDIA_NEXT_ACTION;
  let kind: MediaLibraryFilesFailureKind = "rejected";
  if (category !== undefined) {
    if (PROVIDER_FAILURE_CATEGORIES.includes(category)) {
      kind = "storage_unavailable";
    } else if (category === "storage_not_found") {
      kind = "storage_not_found";
    } else if (category === "disabled") {
      kind = "storage_disabled";
    } else if (category === "invalid_path") {
      kind = "invalid_path";
    } else if (category === "not_found") {
      kind = "not_found";
    } else if (category === "not_directory") {
      kind = "not_directory";
    } else if (category === "cursor_invalid" || category === "cursor_expired") {
      kind = "invalid_cursor";
    } else if (category === "media_library_not_found") {
      kind = "media_library_not_found";
    }
  } else if (code === "configuration_unavailable") {
    kind = "configuration_unavailable";
  }
  return {
    kind,
    title: MEDIA_LIBRARY_FILES_FAILURE_TITLES[kind],
    nextAction,
  };
}

export type MediaLibraryFilesQueryOptions = {
  readonly mediaLibraryId: string;
  readonly path?: string;
  readonly cursor?: string | null;
};

export function mediaLibraryFilesUrl(
  options: MediaLibraryFilesQueryOptions,
): string {
  const params = new URLSearchParams();
  if (options.path !== undefined && options.path !== "") {
    params.set("path", options.path);
  }
  if (options.cursor !== undefined && options.cursor !== null) {
    params.set("cursor", options.cursor);
  }
  const qs = params.toString();
  return `/api/v1/media-libraries/${encodeURIComponent(options.mediaLibraryId)}/files${qs ? `?${qs}` : ""}`;
}

export async function fetchMediaLibraryFiles(
  token: string | null,
  options: MediaLibraryFilesQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<MediaLibraryFilesRead> {
  if (!isSafeScopedIdentifier(options.mediaLibraryId)) {
    return {
      ok: false,
      failure: mediaFailureFromErrorEnvelope(
        "storage_browser_media_library_not_found",
        {
          category: "media_library_not_found",
        },
      ),
    };
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl(mediaLibraryFilesUrl(options), {
      method: "GET",
      headers,
    });
  } catch {
    throw new MediaLibraryFilesApiError("unavailable");
  }
  // Authentication rejection is owned by the shared authorized-read boundary,
  // which clears the rejected authority and cache exactly once.
  if (response.status === 401) {
    throw new MediaLibraryFilesApiError("unauthorized");
  }
  // A 403 is either an API-principal RBAC denial (stable code "forbidden") or
  // a Storage-provider permission failure; only the former may clear a valid
  // authority.
  if (response.status === 403) {
    const envelope = await readErrorEnvelope(response);
    if (envelope.code === "forbidden") {
      throw new MediaLibraryFilesApiError("forbidden");
    }
    return {
      ok: false,
      failure: mediaFailureFromErrorEnvelope(envelope.code, envelope.details),
    };
  }
  if (response.status >= 500) {
    const envelope = await readErrorEnvelope(response);
    if (envelopeHasKnownStorageFailure(envelope)) {
      return {
        ok: false,
        failure: mediaFailureFromErrorEnvelope(envelope.code, envelope.details),
      };
    }
    throw new MediaLibraryFilesApiError("unavailable");
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      failure: mediaFailureFromErrorEnvelope(envelope.code, envelope.details),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new MediaLibraryFilesApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeMediaLibraryFiles(payload) };
  } catch {
    throw new MediaLibraryFilesApiError("malformed");
  }
}

export async function fetchMediaLibraryList(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<MediaLibraryListModel> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/media-libraries", {
      method: "GET",
      headers,
    });
  } catch {
    throw new MediaLibraryFilesApiError("unavailable");
  }
  if (response.status === 401) {
    throw new MediaLibraryFilesApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new MediaLibraryFilesApiError("forbidden");
  }
  if (response.status >= 500) {
    throw new MediaLibraryFilesApiError("unavailable");
  }
  if (!response.ok) {
    throw new MediaLibraryFilesApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new MediaLibraryFilesApiError("malformed");
  }
  try {
    return normalizeMediaLibraryList(payload);
  } catch {
    throw new MediaLibraryFilesApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// Operations workspace API functions
// ---------------------------------------------------------------------------

import {
  normalizeTaskListPage,
  normalizeTaskDetailPage,
  normalizeTaskRecord,
  TASK_COMMAND_FILTERS,
  TASK_STATUSES,
  type TaskListPage,
  type TaskDetailPage,
  type TaskStatus,
} from "../../entities/operations/task";
import {
  normalizeJobListPage,
  normalizeJobDetail,
  JOB_COMMANDS,
  JOB_STATUSES,
  type JobListPage,
  type JobSummary,
  type JobCommand,
  type JobStatus,
} from "../../entities/operations/job";
import {
  normalizeWorkerReadiness,
  normalizeWorkerList,
  type WorkerReadinessModel,
  type WorkerListModel,
} from "../../entities/operations/worker";
import {
  normalizeRunInventoryPage,
  normalizeRunOverview,
  RUN_STATUSES,
  type RunInventoryPage,
  type RunProblemType,
  type RunStatus,
  type RunSummary,
  type RunView,
} from "../../entities/operations/run";
import {
  normalizeRunItemsPage,
  normalizeRunRecordsPage,
  normalizeRunItemEvidence,
  normalizeRunProblemItemsPage,
  normalizeRunExportPackage,
  type RunExportPackage,
  type RunItemEvidence,
  type RunItemsPage,
  type RunProblemItemsPage,
  type RunRecordsPage,
} from "../../entities/operations/run-detail";
import {
  normalizeLifecycleProjection,
  type LifecycleActionName,
  type LifecycleProjection,
} from "../../entities/operations/lifecycle";
import { OperationsApiError } from "./api-errors";

export type OperationsReadErrorCategory =
  | "unauthorized"
  | "forbidden"
  | "unavailable"
  | "rejected"
  | "malformed"
  | "not_found";

export interface OperationsFailure {
  readonly kind: OperationsReadErrorCategory;
  readonly title: string;
  readonly nextAction: string;
}

export type OperationsRead<T> =
  | { readonly ok: true; readonly model: T }
  | { readonly ok: false; readonly failure: OperationsFailure };

const OPERATIONS_FAILURES: Readonly<
  Record<OperationsReadErrorCategory, OperationsFailure>
> = {
  unauthorized: {
    kind: "unauthorized",
    title: "Not authorized",
    nextAction: "Enter a valid API principal token to continue.",
  },
  forbidden: {
    kind: "forbidden",
    title: "Forbidden",
    nextAction:
      "The connected API principal does not have permission to view Operations.",
  },
  unavailable: {
    kind: "unavailable",
    title: "Operations unavailable",
    nextAction: "Reload the current Active runtime and retry the same read.",
  },
  rejected: {
    kind: "rejected",
    title: "Request rejected",
    nextAction:
      "The submitted filter or page cursor is not valid for this collection. Reset the filters and reload.",
  },
  malformed: {
    kind: "malformed",
    title: "Response could not be understood",
    nextAction: "Reload and retry the same read.",
  },
  not_found: {
    kind: "not_found",
    title: "Record not found",
    nextAction: "Return to the Operations list.",
  },
};

function operationsFailure(
  kind: OperationsReadErrorCategory,
): OperationsFailure {
  return OPERATIONS_FAILURES[kind];
}

function operationsHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function operationsMutationHeaders(
  token: string | null,
): Record<string, string> {
  return {
    ...operationsHeaders(token),
    "Content-Type": "application/json",
  };
}

const SAFE_IDENTIFIER = /^[A-Za-z0-9._:-]{1,256}$/;

function isSafeIdentifier(value: string): boolean {
  return SAFE_IDENTIFIER.test(value);
}

// --- Task list ---

export interface TaskListQueryOptions {
  readonly status?: TaskStatus | null;
  readonly command?: string | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export function taskListUrl(options: TaskListQueryOptions): string {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.command) params.set("command", options.command);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const qs = params.toString();
  return `/api/v1/operations/tasks${qs ? `?${qs}` : ""}`;
}

export async function fetchTaskList(
  token: string | null,
  options: TaskListQueryOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<TaskListPage>> {
  let response: Response;
  try {
    response = await fetchImpl(taskListUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeTaskListPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

/** The bounded Task status and command filter values the backend accepts. */
export const TASK_FILTER_VALUES = {
  statuses: TASK_STATUSES,
  commands: TASK_COMMAND_FILTERS,
} as const;

/** The bounded Job status and command filter values the backend accepts. */
export const JOB_FILTER_VALUES = {
  statuses: JOB_STATUSES,
  commands: JOB_COMMANDS,
} as const;

// --- Task detail ---

export interface TaskDetailQueryOptions {
  readonly taskId: string;
  readonly itemLimit?: number;
  readonly resultLimit?: number;
  readonly itemCursor?: string | null;
  readonly resultCursor?: string | null;
}

export function taskDetailUrl(options: TaskDetailQueryOptions): string {
  const params = new URLSearchParams();
  if (options.itemLimit !== undefined)
    params.set("itemLimit", String(options.itemLimit));
  if (options.resultLimit !== undefined)
    params.set("resultLimit", String(options.resultLimit));
  if (options.itemCursor) params.set("itemCursor", options.itemCursor);
  if (options.resultCursor) params.set("resultCursor", options.resultCursor);
  const qs = params.toString();
  return `/api/v1/operations/tasks/${encodeURIComponent(options.taskId)}${qs ? `?${qs}` : ""}`;
}

export type TaskDetailRead =
  | { readonly ok: true; readonly model: TaskDetailPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchTaskDetail(
  token: string | null,
  options: TaskDetailQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<TaskDetailRead> {
  if (!isSafeIdentifier(options.taskId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(taskDetailUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeTaskDetailPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Operations lifecycle mutations ---

/**
 * Bounded outcome of one deliberate lifecycle control.
 *
 * A failure carries only the backend's normalized reason token and HTTP status:
 * raw response bodies, exception text and protocol detail never reach the DOM,
 * console or a retry decision. Nothing here is ever replayed automatically.
 */
export interface LifecycleSuccess {
  readonly ok: true;
  readonly status: number;
  readonly action: LifecycleActionName;
  readonly objectId: string;
  readonly state: string;
  readonly version: string;
  readonly lifecycle: LifecycleProjection;
  readonly durableOutcome: string | null;
  readonly nextAction: string | null;
}

export interface LifecycleFailure {
  readonly ok: false;
  readonly status: number;
  readonly code: string;
}

export type LifecycleMutationResult = LifecycleSuccess | LifecycleFailure;

const SAFE_REASON = /^[a-z][a-z0-9_]{0,63}$/;

function readSafeReason(value: unknown): string | null {
  return typeof value === "string" && SAFE_REASON.test(value) ? value : null;
}

function lifecycleFailure(status: number, body: unknown): LifecycleFailure {
  let code = status === 0 ? "transport_unavailable" : "request_rejected";
  if (typeof body === "object" && body !== null && !Array.isArray(body)) {
    const error = (body as Record<string, unknown>)["error"];
    if (typeof error === "object" && error !== null && !Array.isArray(error)) {
      const detail = error as Record<string, unknown>;
      // The backend distinguishes a stale/duplicate refusal from a state
      // refusal through its own normalized reason token, so the operator copy
      // can name the real cause without receiving free-form server text.
      const details = detail["details"];
      const reason =
        typeof details === "object" &&
        details !== null &&
        !Array.isArray(details)
          ? readSafeReason((details as Record<string, unknown>)["reason"])
          : null;
      code = reason ?? readSafeReason(detail["code"]) ?? code;
    }
  }
  return { ok: false, status, code };
}

/**
 * The single mutation boundary for every Operations lifecycle control.
 *
 * It always sends exactly one authenticated POST with exactly the version the
 * operator saw; a rejected, stale, 401 or 403 response is returned as a bounded
 * failure and is never retried by this client or by TanStack Query.
 */
export async function mutateLifecycle(
  token: string | null,
  options: {
    readonly objectType: "task" | "job";
    readonly objectId: string;
    readonly action: LifecycleActionName;
    readonly expectedVersion: string;
  },
  fetchImpl: FetchLike = fetch,
): Promise<LifecycleMutationResult> {
  if (
    !isSafeIdentifier(options.objectId) ||
    options.expectedVersion.length > 128
  ) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  const collection = options.objectType === "task" ? "tasks" : "jobs";
  const url = `/api/v1/${collection}/${encodeURIComponent(options.objectId)}/${options.action}`;
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify({ expectedUpdatedAt: options.expectedVersion }),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    return lifecycleFailure(response.status, body);
  }
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  const document = body as Record<string, unknown>;
  try {
    if (options.objectType === "job") {
      const job: JobSummary = normalizeJobDetail(document);
      return {
        ok: true,
        status: response.status,
        action: options.action,
        objectId: job.jobId,
        state: job.status,
        version: job.lifecycle.version,
        lifecycle: job.lifecycle,
        durableOutcome:
          job.lifecycle.actions.find((item) => item.action === options.action)
            ?.durableOutcome ?? null,
        nextAction: job.lifecycle.nextAction,
      };
    }
    const task = normalizeTaskRecord(document["task"]);
    const lifecycle = normalizeLifecycleProjection(document["lifecycle"], {
      objectType: "task",
      objectId: task.taskId,
      state: task.status,
    });
    if (task.taskId !== options.objectId) {
      return { ok: false, status: response.status, code: "malformed_response" };
    }
    const durableOutcome = document["durableOutcome"];
    return {
      ok: true,
      status: response.status,
      action: options.action,
      objectId: task.taskId,
      state: task.status,
      version: lifecycle.version,
      lifecycle,
      durableOutcome:
        typeof durableOutcome === "string" && durableOutcome.length <= 1024
          ? durableOutcome
          : null,
      nextAction: lifecycle.nextAction,
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

// --- Job list ---

export interface JobListQueryOptions {
  readonly status?: JobStatus | null;
  readonly command?: JobCommand | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export function jobListUrl(options: JobListQueryOptions): string {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.command) params.set("command", options.command);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const qs = params.toString();
  return `/api/v1/operations/jobs${qs ? `?${qs}` : ""}`;
}

export async function fetchJobList(
  token: string | null,
  options: JobListQueryOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<JobListPage>> {
  let response: Response;
  try {
    response = await fetchImpl(jobListUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeJobListPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Job detail ---

export type JobDetailRead =
  | { readonly ok: true; readonly model: JobSummary }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchJobDetail(
  token: string | null,
  jobId: string,
  fetchImpl: FetchLike = fetch,
): Promise<JobDetailRead> {
  if (!isSafeIdentifier(jobId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/jobs/${encodeURIComponent(jobId)}`,
      {
        method: "GET",
        headers: operationsHeaders(token),
      },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeJobDetail(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Worker readiness ---

export async function fetchWorkerReadiness(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<WorkerReadinessModel> {
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/workers/readiness", {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    throw new OperationsApiError("unavailable");
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    throw new OperationsApiError("unavailable");
  }
  if (!response.ok) {
    throw new OperationsApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return normalizeWorkerReadiness(payload);
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Unified run inventory (Slice 42 RO-1/RO-2) ---

export interface RunInventoryQueryOptions {
  readonly status?: RunStatus | null;
  readonly command?: string | null;
  readonly q?: string | null;
  readonly from?: string | null;
  readonly to?: string | null;
  /** Exact bounded historical source scope; cursor-bound with all filters. */
  readonly source?: string | null;
  /** Submit the overlapping attention facet (`attention=true`); a null or
   * absent value reads the unfiltered population. */
  readonly attention?: boolean | null;
  /** One of the nine sibling views; null/absent reads the full population. */
  readonly view?: RunView | null;
  /** One cross-Task recovery problem type; null/absent applies no problem
   * filter beyond the selected view's own predicate. */
  readonly problem?: RunProblemType | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export function runInventoryUrl(options: RunInventoryQueryOptions): string {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.command) params.set("command", options.command);
  if (options.q) params.set("q", options.q);
  if (options.from) params.set("from", options.from);
  if (options.to) params.set("to", options.to);
  if (options.source) params.set("source", options.source);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  // The facet is a boolean server parameter: only `attention=true` restricts
  // the population, so an unfiltered read keeps its exact original URL.
  if (options.attention) params.set("attention", "true");
  if (options.view) params.set("view", options.view);
  if (options.problem) params.set("problem", options.problem);
  const qs = params.toString();
  return `/api/v1/operations/runs${qs ? `?${qs}` : ""}`;
}

export type RunInventoryRead =
  | { readonly ok: true; readonly model: RunInventoryPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchRunInventory(
  token: string | null,
  options: RunInventoryQueryOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<RunInventoryRead> {
  let response: Response;
  try {
    response = await fetchImpl(runInventoryUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeRunInventoryPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type RunOverviewRead =
  | { readonly ok: true; readonly model: RunSummary }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchRunOverview(
  token: string | null,
  runId: string,
  fetchImpl: FetchLike = fetch,
): Promise<RunOverviewRead> {
  if (!isSafeIdentifier(runId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/runs/${encodeURIComponent(runId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeRunOverview(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// --- Selected-run detail reads (Slice 42 RO-3) ---

export interface RunItemsQueryOptions {
  readonly runId: string;
  /** One modelled disposition filter, or null for the whole population. */
  readonly status?: string | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export interface RunRecordsQueryOptions {
  readonly runId: string;
  /** One modelled record-kind filter, or null for the whole stream. */
  readonly kind?: string | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

function runDetailBase(runId: string): string {
  return `/api/v1/operations/runs/${encodeURIComponent(runId)}`;
}

export function runItemsUrl(options: RunItemsQueryOptions): string {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const qs = params.toString();
  return `${runDetailBase(options.runId)}/items${qs ? `?${qs}` : ""}`;
}

export function runRecordsUrl(options: RunRecordsQueryOptions): string {
  const params = new URLSearchParams();
  if (options.kind) params.set("kind", options.kind);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const qs = params.toString();
  return `${runDetailBase(options.runId)}/records${qs ? `?${qs}` : ""}`;
}

export function runItemEvidenceUrl(runId: string, itemId: string): string {
  return `${runDetailBase(runId)}/items/${encodeURIComponent(itemId)}`;
}

/**
 * One problem-type file page of a recovery list entry (Slice 45 RO-3).
 *
 * The problem type is a closed backend token; the page is server-filtered and
 * server-paged on the same durable predicate the recovery list uses.
 */
export interface RunProblemItemsQueryOptions {
  readonly runId: string;
  readonly problem: RunProblemType;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export function runProblemItemsUrl(
  options: RunProblemItemsQueryOptions,
): string {
  const params = new URLSearchParams();
  params.set("problem", options.problem);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  return `${runDetailBase(options.runId)}/problem-items?${params.toString()}`;
}

export function runExportUrl(runId: string, limit: number): string {
  return `${runDetailBase(runId)}/export?limit=${String(limit)}`;
}

/** One generic bounded parse of a selected-run detail sub-resource response. */
async function parseRunDetailResponse<T>(
  response: Response,
  normalize: (payload: unknown) => T,
): Promise<OperationsRead<T>> {
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalize(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type RunItemsRead = OperationsRead<RunItemsPage>;

export type RunProblemItemsRead = OperationsRead<RunProblemItemsPage>;

export async function fetchRunProblemItems(
  token: string | null,
  options: RunProblemItemsQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<RunProblemItemsRead> {
  if (!isSafeIdentifier(options.runId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(runProblemItemsUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  return parseRunDetailResponse(response, normalizeRunProblemItemsPage);
}

export async function fetchRunItems(
  token: string | null,
  options: RunItemsQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<RunItemsRead> {
  if (!isSafeIdentifier(options.runId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(runItemsUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  return parseRunDetailResponse(response, normalizeRunItemsPage);
}

export type RunRecordsRead = OperationsRead<RunRecordsPage>;

export async function fetchRunRecords(
  token: string | null,
  options: RunRecordsQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<RunRecordsRead> {
  if (!isSafeIdentifier(options.runId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(runRecordsUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  return parseRunDetailResponse(response, normalizeRunRecordsPage);
}

export type RunItemEvidenceRead = OperationsRead<RunItemEvidence>;

export async function fetchRunItemEvidence(
  token: string | null,
  runId: string,
  itemId: string,
  fetchImpl: FetchLike = fetch,
): Promise<RunItemEvidenceRead> {
  if (!isSafeIdentifier(runId) || !isSafeIdentifier(itemId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(runItemEvidenceUrl(runId, itemId), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  return parseRunDetailResponse(response, normalizeRunItemEvidence);
}

export async function fetchTaskItemRecovery(
  token: string | null,
  taskId: string,
  itemId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<TaskItemRecoveryModel>> {
  if (!isSafeIdentifier(taskId) || !isSafeIdentifier(itemId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/tasks/${encodeURIComponent(taskId)}/items/${encodeURIComponent(itemId)}/recovery`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  return parseRunDetailResponse(response, normalizeTaskItemRecovery);
}

export async function fetchTaskRecoveryBatch(
  token: string | null,
  taskId: string,
  batchId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<RecoveryBatchModel>> {
  if (!isSafeIdentifier(taskId) || !/^[a-f0-9-]{36}$/i.test(batchId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/tasks/${encodeURIComponent(taskId)}/recovery-batches/${encodeURIComponent(batchId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  return parseRunDetailResponse(response, normalizeRecoveryBatch);
}

export interface AuthenticatedPrincipalModel {
  readonly principalId: string;
}

/** Read the principal identity confirmed by the current backend token. */
export async function fetchAuthenticatedPrincipal(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<AuthenticatedPrincipalModel> {
  if (token === null) throw new OperationsApiError("unauthorized");
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/auth/principal", {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    throw new OperationsApiError("unavailable");
  }
  const result = await parseRunDetailResponse(response, (payload) => {
    if (
      typeof payload !== "object" ||
      payload === null ||
      Array.isArray(payload)
    ) {
      throw new Error("authenticated principal response is malformed");
    }
    const principalId = (payload as Record<string, unknown>)["principal_id"];
    const validatedPrincipalId = normalizePrincipalId(principalId);
    return { principalId: validatedPrincipalId };
  });
  if (!result.ok) {
    throw new OperationsApiError(
      result.failure.kind === "unavailable" ? "unavailable" : "rejected",
    );
  }
  return result.model;
}

/**
 * The run-scoped result package download read.  The backend's bounded error
 * code travels with the failure so the UI can distinguish "no linked Task
 * yet" (409) from a rejected limit (422) or an unavailable export (503)
 * instead of offering an empty download.
 */
export type RunExportRead =
  | {
      readonly ok: true;
      readonly model: RunExportPackage;
      /** The validated raw package exactly as received, kept for the
       * browser-side file download (the normalized model alone would drop
       * the result rows the file must contain). */
      readonly payload: unknown;
    }
  | {
      readonly ok: false;
      readonly failure: OperationsFailure;
      readonly code: string | null;
    };

const EXPORT_CODE_TOKEN = /^[a-z][a-z0-9_]{0,47}$/;

async function exportErrorCode(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { error?: { code?: unknown } };
    const code = payload?.error?.code;
    return typeof code === "string" && EXPORT_CODE_TOKEN.test(code)
      ? code
      : null;
  } catch {
    return null;
  }
}

export async function fetchRunExportPackage(
  token: string | null,
  runId: string,
  limit = 100,
  fetchImpl: FetchLike = fetch,
): Promise<RunExportRead> {
  if (!isSafeIdentifier(runId)) {
    return {
      ok: false,
      failure: operationsFailure("not_found"),
      code: null,
    };
  }
  let response: Response;
  try {
    response = await fetchImpl(runExportUrl(runId, limit), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return {
      ok: false,
      failure: operationsFailure("unavailable"),
      code: null,
    };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return {
      ok: false,
      failure: operationsFailure("unavailable"),
      code: await exportErrorCode(response),
    };
  }
  if (!response.ok) {
    return {
      ok: false,
      failure: operationsFailure(
        response.status === 404 ? "not_found" : "rejected",
      ),
      code: await exportErrorCode(response),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeRunExportPackage(payload), payload };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

/** The bounded run-inventory status filter values the backend accepts. */
export const RUN_FILTER_VALUES = {
  statuses: RUN_STATUSES,
} as const;

// --- Worker list ---

export async function fetchWorkerList(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<WorkerListModel> {
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/workers", {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    throw new OperationsApiError("unavailable");
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    throw new OperationsApiError("unavailable");
  }
  if (!response.ok) {
    throw new OperationsApiError("rejected");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return normalizeWorkerList(payload);
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// Manual Scan / Preview API functions
// ---------------------------------------------------------------------------

import {
  normalizeManualActionMatrix,
  type ManualActionMatrixModel,
} from "../../entities/operations/manual-actions";

import {
  normalizeOrganizeAdmissionOutcome,
  normalizeOrganizeExecution,
  normalizeOrganizeExecutionList,
  normalizeOrganizeIntent,
  normalizeOrganizePreview,
  type OrganizeAdmissionOutcomeModel,
  type OrganizeExecutionListPage,
  type OrganizeExecutionModel,
  type OrganizeIntentModel,
  type OrganizePreviewModel,
} from "../../entities/operations/organize";
import {
  normalizeOrganizeDiscovery,
  type OrganizeDiscoveryModel,
} from "../../entities/operations/discovery";
import {
  normalizeAutomationActivation,
  normalizeAutomationDefinition,
  normalizeAutomationDefinitionsPage,
  normalizeAutomationDraftDocument,
  normalizeAutomationGrantState,
  normalizeAutomationMetrics,
  normalizeAutomationOccurrencesPage,
  normalizeAutomationPreview,
  normalizeAutomationRecordsPage,
  normalizeAutomationPreviewItemsPage,
  type AutomationActivationModel,
  type AutomationDefinitionModel,
  type AutomationDefinitionsPage,
  type AutomationDraftDocumentModel,
  type AutomationGrantStateModel,
  type AutomationMetricsModel,
  type AutomationOccurrencesPage,
  type AutomationRecordsPage,
  type AutomationPreviewItemsPage,
  type AutomationPreviewModel,
} from "../../entities/operations/automation";
import {
  normalizeAutomationSettings,
  type AutomationSettingsModel,
} from "../../entities/operations/automation-settings";
import {
  normalizeAutomationFormAuthority,
  normalizeAutomationCopyCandidate,
  normalizeAutomationCopyIntent,
  normalizeAutomationEditProjection,
  normalizeAutomationPublication,
  normalizeAutomationRemovalImpact,
  normalizeAutomationSchedulePreview,
  type AutomationDefinitionFormAuthorityModel,
  type AutomationCopyCandidateModel,
  type AutomationCopyIntentModel,
  type AutomationEditProjectionModel,
  type AutomationPublicationModel,
  type AutomationRemovalImpactModel,
  type AutomationSchedulePreviewModel,
} from "../../entities/operations/automation-lifecycle";
import {
  normalizeAutomationRunOnce,
  type AutomationRunOnceModel,
} from "../../entities/operations/run-once";
import {
  NOTIFICATION_URI_SAFE_SEGMENT,
  normalizeNotificationActivation,
  normalizeNotificationDeliveriesPage,
  normalizeNotificationDeliveryDetail,
  normalizeNotificationDefinitionsPage,
  normalizeNotificationDraftDocument,
  normalizeNotificationRecoveryResult,
  normalizeWebhookDefinition,
  normalizeWebhookDefinitionMutation,
  normalizeWebhookTestResult,
  type NotificationActivationModel,
  type NotificationDeliveriesPage,
  type NotificationDeliveryDetailModel,
  type NotificationDefinitionsPage,
  type NotificationDraftDocumentModel,
  type NotificationRecoveryResultModel,
  type WebhookDefinitionModel,
  type WebhookDefinitionMutationModel,
  type WebhookTestResultModel,
} from "../../entities/operations/notification";
import {
  normalizeBoundedText,
  normalizeIdentityText,
  readRecord,
} from "../../entities/shared/normalize";
import { normalizePrincipalId } from "../auth/principal-identity";

// --- Manual action matrix ---

export interface ManualActionMatrixQueryOptions {
  /** Omitted for the bounded ResourceLibrary discovery read. */
  readonly scopeKind?: "file" | "resourceLibrary" | null;
  readonly fileId?: string | null;
  readonly resourceLibraryId?: string | null;
}

export function manualActionMatrixUrl(
  options: ManualActionMatrixQueryOptions,
): string {
  const params = new URLSearchParams();
  if (options.scopeKind) params.set("scopeKind", options.scopeKind);
  if (options.fileId) params.set("fileId", options.fileId);
  if (options.resourceLibraryId)
    params.set("resourceLibraryId", options.resourceLibraryId);
  const query = params.toString();
  return `/api/v1/operations/manual-actions${query ? `?${query}` : ""}`;
}

export async function fetchManualActionMatrix(
  token: string | null,
  options: ManualActionMatrixQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<ManualActionMatrixModel>> {
  let response: Response;
  try {
    response = await fetchImpl(manualActionMatrixUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeManualActionMatrix(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// Manual Organize: durable intent, exact Preview, one Execute action, outcome
// ---------------------------------------------------------------------------

/**
 * Bounded mutation outcome. Every mutation in this journey returns the exact
 * status and the backend `error.code` so the page can render a truthful
 * recovery action; nothing is retried automatically.
 */
export type OrganizeMutationResult<T> =
  | { readonly ok: true; readonly status: number; readonly model: T }
  | { readonly ok: false; readonly status: number; readonly code: string };

async function readErrorCode(response: Response): Promise<string> {
  try {
    const body = (await response.clone().json()) as {
      error?: { code?: unknown };
    };
    const code = body?.error?.code;
    return typeof code === "string" && code.length > 0
      ? code
      : "request_rejected";
  } catch {
    return "request_rejected";
  }
}

async function submitOrganizeMutation<T>(
  token: string | null,
  url: string,
  body: Record<string, unknown>,
  normalize: (payload: unknown) => T,
  fetchImpl: FetchLike,
): Promise<OrganizeMutationResult<T>> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      code: await readErrorCode(response),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, status: response.status, model: normalize(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export interface RecoveryCommandAck {
  readonly identity: string;
  readonly sideEffects: "none";
  readonly nextAction: string;
}

function normalizeRecoveryCommandAck(payload: unknown): RecoveryCommandAck {
  const source = readRecord(payload, "recoveryCommand");
  if (source["sideEffects"] !== "none") {
    throw new Error("recovery command side effects did not match the contract");
  }
  const identity =
    source["continuation_id"] ??
    source["continuationId"] ??
    source["requestId"] ??
    source["batch_id"];
  return {
    identity: normalizeBoundedText(identity, "recovery identity"),
    sideEffects: "none",
    nextAction: normalizeBoundedText(
      source["next_action"] ?? source["nextAction"],
      "next_action",
    ),
  };
}

function taskItemRecoveryBase(taskId: string, itemId: string): string {
  return `/api/v1/tasks/${encodeURIComponent(taskId)}/items/${encodeURIComponent(itemId)}/recovery`;
}

export async function submitTaskItemRecoveryDecision(
  token: string | null,
  taskId: string,
  itemId: string,
  body: Record<string, unknown>,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<TaskItemRecoveryModel>> {
  if (!isSafeIdentifier(taskId) || !isSafeIdentifier(itemId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `${taskItemRecoveryBase(taskId, itemId)}/decision`,
    body,
    normalizeTaskItemRecovery,
    fetchImpl,
  );
}

export async function searchTaskItemMetadata(
  token: string | null,
  taskId: string,
  itemId: string,
  body: {
    readonly expectedCheckpointVersion: string;
    readonly query: string;
    readonly mediaType: string;
  },
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<MetadataSearchModel>> {
  if (!isSafeIdentifier(taskId) || !isSafeIdentifier(itemId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `${taskItemRecoveryBase(taskId, itemId)}/metadata-search`,
    body,
    normalizeMetadataSearch,
    fetchImpl,
  );
}

export async function ignoreTaskItemReview(
  token: string | null,
  taskId: string,
  itemId: string,
  body: { readonly expectedCheckpointVersion: string; readonly note?: string },
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<RecoveryCommandAck>> {
  if (!isSafeIdentifier(taskId) || !isSafeIdentifier(itemId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    taskItemRecoveryBase(taskId, itemId),
    { actionId: "ignore", ...body },
    normalizeRecoveryCommandAck,
    fetchImpl,
  );
}

export async function continueTaskItemAnalysis(
  token: string | null,
  taskId: string,
  itemId: string,
  expectedCheckpointVersion: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<RecoveryCommandAck>> {
  if (!isSafeIdentifier(taskId) || !isSafeIdentifier(itemId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `${taskItemRecoveryBase(taskId, itemId)}/continue`,
    { expectedCheckpointVersion },
    normalizeRecoveryCommandAck,
    fetchImpl,
  );
}

export async function submitTaskRecoveryBatch(
  token: string | null,
  taskId: string,
  batchId: string,
  items: readonly {
    readonly itemId: string;
    readonly expectedCheckpointVersion: string;
  }[],
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<RecoveryBatchModel>> {
  if (!isSafeIdentifier(taskId) || !/^[a-f0-9-]{36}$/i.test(batchId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/tasks/${encodeURIComponent(taskId)}/recovery/continue-batch`,
    { batchId, items: items.map((item) => ({ ...item })) },
    normalizeRecoveryBatch,
    fetchImpl,
  );
}

export async function authorizeTaskItemRecoveryOrganize(
  token: string | null,
  options: {
    readonly taskId: string;
    readonly itemId: string;
    readonly expectedCheckpointVersion: string;
    readonly allowOverwrite: boolean;
    readonly allowSourceCleanup: boolean;
  },
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<ManualRecoveryLinkModel>> {
  if (!isSafeIdentifier(options.taskId) || !isSafeIdentifier(options.itemId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/tasks/${encodeURIComponent(options.taskId)}/items/${encodeURIComponent(options.itemId)}/recovery/authorize-organize`,
    {
      expectedCheckpointVersion: options.expectedCheckpointVersion,
      confirmation: true,
      allowOverwrite: options.allowOverwrite,
      allowSourceCleanup: options.allowSourceCleanup,
    },
    normalizeManualRecoveryLink,
    fetchImpl,
  );
}

export async function executeTaskItemRecoveryOrganize(
  token: string | null,
  linkId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<ManualRecoveryLinkModel>> {
  if (!isSafeIdentifier(linkId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/manual-recovery-links/${encodeURIComponent(linkId)}/execute`,
    { confirmation: true },
    normalizeManualRecoveryLink,
    fetchImpl,
  );
}

/**
 * Publish one non-authorizing plan summary of a recovery source item.
 *
 * This is a read/prepare action: it creates no execution authority and
 * performs no Storage mutation.  The operator still has to explicitly confirm
 * a ready subset through `confirmTaskItemRecoveryPreparation`.
 */
export async function prepareTaskItemRecoverySummary(
  token: string | null,
  taskId: string,
  itemId: string,
  expectedCheckpointVersion: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<ManualRecoveryPreparationModel>> {
  if (!isSafeIdentifier(taskId) || !isSafeIdentifier(itemId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `${taskItemRecoveryBase(taskId, itemId)}/prepare-summary`,
    { expectedCheckpointVersion },
    normalizeManualRecoveryPreparation,
    fetchImpl,
  );
}

/**
 * Confirm an exact ready subset of one prepared recovery summary.
 *
 * Only the explicitly selected ready items are admitted; the linked execution
 * is the durable result of that confirmation.  A repeated or concurrent call
 * resolves to the same durable execution instead of admitting a second one.
 */
export async function confirmTaskItemRecoveryPreparation(
  token: string | null,
  preparationId: string,
  options: {
    readonly itemIds: readonly string[];
    readonly allowOverwrite: boolean;
    readonly allowSourceCleanup: boolean;
  },
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<ManualRecoveryConfirmationModel>> {
  if (!isSafeIdentifier(preparationId) || options.itemIds.length === 0) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/manual-recovery-preparations/${encodeURIComponent(preparationId)}/confirm`,
    {
      itemIds: [...options.itemIds],
      confirmation: true,
      allowOverwrite: options.allowOverwrite,
      allowSourceCleanup: options.allowSourceCleanup,
    },
    normalizeManualRecoveryConfirmation,
    fetchImpl,
  );
}

/** One bounded, secret-free confirmation result: the admitted execution. */
export interface ManualRecoveryConfirmationModel {
  readonly executionId: string;
  readonly taskId: string;
  readonly status: string;
  readonly selectedItemIds: readonly string[];
  readonly nextAction: string;
}

export function normalizeManualRecoveryConfirmation(
  payload: unknown,
): ManualRecoveryConfirmationModel {
  const source = readRecord(payload, "manualRecoveryConfirmation");
  const rawItems = source["selectedItemIds"];
  if (!Array.isArray(rawItems) || rawItems.length === 0) {
    throw new Error(
      "manual recovery confirmation response did not match its contract",
    );
  }
  return {
    executionId: normalizeIdentityText(
      source["executionId"],
      "executionId",
      200,
    ),
    taskId: normalizeIdentityText(source["taskId"], "taskId", 200),
    status: normalizeBoundedText(source["status"], "status"),
    selectedItemIds: rawItems.map((value) =>
      normalizeIdentityText(value, "selectedItemId", 200),
    ),
    nextAction: normalizeBoundedText(source["nextAction"], "nextAction"),
  };
}

export interface SubmitOrganizeIntentOptions {
  readonly scopeKind: "file" | "resourceLibrary";
  readonly fileId?: string | null;
  readonly resourceLibraryId?: string | null;
  /** Current FileIndex identities for a ResourceLibrary-scoped selection. */
  readonly itemIds?: readonly string[] | null;
}

export async function submitOrganizeIntent(
  token: string | null,
  options: SubmitOrganizeIntentOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizeIntentModel>> {
  const body: Record<string, unknown> = { scopeKind: options.scopeKind };
  if (options.fileId) {
    body.fileId = options.fileId;
  }
  if (options.resourceLibraryId) {
    body.resourceLibraryId = options.resourceLibraryId;
  }
  if (options.itemIds && options.itemIds.length > 0) {
    body.itemIds = [...options.itemIds];
  }
  return submitOrganizeMutation(
    token,
    "/api/v1/operations/organize/intents",
    body,
    normalizeOrganizeIntent,
    fetchImpl,
  );
}

export type OrganizeIntentRead =
  | { readonly ok: true; readonly model: OrganizeIntentModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchOrganizeIntent(
  token: string | null,
  intentId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeIntentRead> {
  if (!isSafeIdentifier(intentId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/intents/${encodeURIComponent(intentId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizeIntent(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface UpdateOrganizeChoiceOptions {
  readonly intentId: string;
  readonly itemId: string;
  readonly expectedVersion: number;
  readonly expectedItemVersion: number;
  readonly recognitionTypeId?: string;
  readonly namingPolicyId?: string;
  readonly classificationPolicyId?: string;
  readonly organizePolicyId?: string;
  /**
   * The pinned metadata identity already carried by the intent item.  The
   * backend validates it against durable source-linked evidence; it is not a
   * free-form provider payload.
   */
  readonly metadata?: {
    readonly provider: string | null;
    readonly providerId: string | null;
    readonly mediaType: string | null;
    readonly title: string | null;
    readonly year: number | null;
  };
}

export async function updateOrganizeChoice(
  token: string | null,
  options: UpdateOrganizeChoiceOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizeIntentModel>> {
  if (
    !isSafeIdentifier(options.intentId) ||
    !isSafeIdentifier(options.itemId)
  ) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {
    expectedVersion: options.expectedVersion,
    expectedItemVersion: options.expectedItemVersion,
  };
  for (const field of [
    "recognitionTypeId",
    "namingPolicyId",
    "classificationPolicyId",
    "organizePolicyId",
  ] as const) {
    const value = options[field];
    if (value !== undefined) {
      body[field] = value;
    }
  }
  if (options.metadata !== undefined) {
    body["metadata"] = {
      provider: options.metadata.provider,
      providerId: options.metadata.providerId,
      mediaType: options.metadata.mediaType,
      title: options.metadata.title,
      year: options.metadata.year,
    };
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/operations/organize/intents/${encodeURIComponent(options.intentId)}/items/${encodeURIComponent(options.itemId)}/choice`,
    body,
    normalizeOrganizeIntent,
    fetchImpl,
  );
}

export interface SubmitOrganizePreviewOptions {
  readonly intentId: string;
  readonly expectedVersion: number;
}

/**
 * Request the durable organize analysis of one intent's own organize run.
 *
 * The request only records one versioned durable stage: the resident Worker
 * runs the complete zero-mutation analysis and links the exact plan on the
 * same run.  The response is the refreshed durable intent document, whose
 * `analysis` projection carries the real stage and whose `latestPlan` names
 * the plan once the Worker has linked it.
 */
export async function submitOrganizePreview(
  token: string | null,
  options: SubmitOrganizePreviewOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizeIntentModel>> {
  if (!isSafeIdentifier(options.intentId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/operations/organize/intents/${encodeURIComponent(options.intentId)}/previews`,
    { expectedVersion: options.expectedVersion },
    normalizeOrganizeIntent,
    fetchImpl,
  );
}

export type OrganizePreviewRead =
  | { readonly ok: true; readonly model: OrganizePreviewModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

/**
 * Admit the native exact Preview of one paused run's remaining scope.
 *
 * This is the RO-5 recovery entry the backend advertises alongside a withheld
 * Continue. The browser sends nothing but the run identity: the scope, the
 * historical pin and every source identity are resolved server-side, and the
 * backend durably admits one bounded remaining-scope observation.  The resident
 * Worker proves the configured stability interval, freezes the remaining
 * sources and links the ordinary zero-mutation organize Preview the operator
 * then reviews and explicitly executes.  The response is therefore the
 * discovery projection, not a finished Preview.
 */
export async function submitRemainingScopePreview(
  token: string | null,
  options: { readonly taskId: string },
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizeDiscoveryModel>> {
  if (!isSafeIdentifier(options.taskId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  return submitOrganizeMutation(
    token,
    `/api/v1/tasks/${encodeURIComponent(options.taskId)}/remaining-scope-previews`,
    {},
    normalizeOrganizeDiscovery,
    fetchImpl,
  );
}

export async function fetchOrganizePreviewDetail(
  token: string | null,
  previewId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizePreviewRead> {
  if (!isSafeIdentifier(previewId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/previews/${encodeURIComponent(previewId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizePreview(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface ExecuteOrganizePreviewOptions {
  readonly previewId: string;
  readonly itemIds: readonly string[];
  readonly expectedIntentVersion: number;
  readonly allowOverwrite?: boolean;
  readonly allowSourceCleanup?: boolean;
}

/**
 * The one meaningful Web Execute action.
 *
 * The browser sends only the reviewed selection, its optimistic intent
 * version, the explicit confirmation and the destructive choices the operator
 * actually made. Everything else (short-lived one-shot authority, digests,
 * tokens and plans) stays on the server.
 */
export async function executeOrganizePreview(
  token: string | null,
  options: ExecuteOrganizePreviewOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeMutationResult<OrganizeExecutionModel>> {
  if (!isSafeIdentifier(options.previewId)) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {
    confirmation: true,
    itemIds: [...options.itemIds],
    expectedIntentVersion: options.expectedIntentVersion,
    // Keep both effect decisions explicit in the bounded request. `false` is
    // meaningful evidence that this exact selection did not request that
    // authority; omission would make it impossible for a caller/test to prove
    // the submitted selection was not broader than the reviewed effects.
    allowOverwrite: options.allowOverwrite === true,
    allowSourceCleanup: options.allowSourceCleanup === true,
  };
  return submitOrganizeMutation(
    token,
    `/api/v1/operations/organize/previews/${encodeURIComponent(options.previewId)}/execute`,
    body,
    normalizeOrganizeExecution,
    fetchImpl,
  );
}

export type OrganizeExecutionRead =
  | { readonly ok: true; readonly model: OrganizeExecutionModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export interface OrganizeAdmissionReconciliationOptions {
  readonly previewId: string;
  readonly itemIds: readonly string[];
  readonly expectedIntentVersion: number;
  readonly allowOverwrite: boolean;
  readonly allowSourceCleanup: boolean;
}

export type OrganizeAdmissionOutcomeRead =
  | { readonly ok: true; readonly model: OrganizeAdmissionOutcomeModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

/**
 * The one bounded admission-outcome reconciliation read for a submitted
 * Execute whose response was lost, malformed or never arrived.
 *
 * The browser re-submits only the reviewed selection it already submitted
 * (never authority material), and the server answers strictly from durable
 * admission records bound to the reading principal. This read admits no work,
 * mints or reissues no authority and never replays a mutation: it exists so a
 * transport failure is never answered with an unproven "nothing was
 * submitted" claim or an automatic second Execute.
 */
export async function fetchOrganizeAdmissionOutcome(
  token: string | null,
  options: OrganizeAdmissionReconciliationOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeAdmissionOutcomeRead> {
  if (
    !isSafeIdentifier(options.previewId) ||
    options.itemIds.length === 0 ||
    options.itemIds.length > 100 ||
    options.itemIds.some((itemId) => !isSafeIdentifier(itemId)) ||
    !Number.isInteger(options.expectedIntentVersion) ||
    options.expectedIntentVersion < 1
  ) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  const params = new URLSearchParams();
  params.set("itemIds", [...options.itemIds].join(","));
  params.set("expectedIntentVersion", String(options.expectedIntentVersion));
  params.set("allowOverwrite", options.allowOverwrite ? "true" : "false");
  params.set(
    "allowSourceCleanup",
    options.allowSourceCleanup ? "true" : "false",
  );
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/previews/${encodeURIComponent(
        options.previewId,
      )}/admission?${params.toString()}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizeAdmissionOutcome(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export async function fetchOrganizeExecution(
  token: string | null,
  executionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeExecutionRead> {
  if (!isSafeIdentifier(executionId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/executions/${encodeURIComponent(executionId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizeExecution(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface OrganizeExecutionListQueryOptions {
  readonly previewId?: string | null;
  readonly intentId?: string | null;
  readonly limit?: number;
}

export async function fetchOrganizeExecutions(
  token: string | null,
  options: OrganizeExecutionListQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OperationsRead<OrganizeExecutionListPage>> {
  const params = new URLSearchParams();
  if (options.previewId) {
    params.set("previewId", options.previewId);
  }
  if (options.intentId) {
    params.set("intentId", options.intentId);
  }
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (params.toString().length === 0) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/executions?${params.toString()}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status >= 500) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("rejected") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeOrganizeExecutionList(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

// ---------------------------------------------------------------------------
// Operations Automation: bounded operator projections over the managed
// configuration and automation services. Reads are the digest-free operator
// documents; mutations reuse the existing backend routes and never retry
// automatically.
// ---------------------------------------------------------------------------

export type AutomationMutationResult<T> =
  | { readonly ok: true; readonly status: number; readonly model: T }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    };

/**
 * The small, secret-free recovery projection shared by authenticated mutation
 * responses.  Only stable state fields cross the API client boundary; raw
 * server messages are deliberately discarded.
 */
export interface AutomationMutationFailureDetails {
  readonly durableState?: string;
  readonly candidateState?: string;
  readonly sideEffects?: string;
  readonly retrySafe?: boolean;
  readonly nextAction?: string;
  readonly reason?: string;
  readonly failureCategory?: string;
  readonly affectedStorageId?: string;
  readonly affectedStorageName?: string;
  readonly currentRevisionId?: string;
  readonly currentVersion?: number;
}

function normalizeAutomationMutationFailureDetails(
  value: unknown,
): AutomationMutationFailureDetails | undefined {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  const record = value as Record<string, unknown>;
  const details: AutomationMutationFailureDetails = {
    ...(typeof record.durableState === "string" &&
    record.durableState.length <= 128
      ? { durableState: record.durableState }
      : {}),
    ...(typeof record.candidateState === "string" &&
    record.candidateState.length <= 128
      ? { candidateState: record.candidateState }
      : {}),
    ...(typeof record.sideEffects === "string" &&
    record.sideEffects.length <= 256
      ? { sideEffects: record.sideEffects }
      : {}),
    ...(typeof record.retrySafe === "boolean"
      ? { retrySafe: record.retrySafe }
      : {}),
    ...(typeof record.nextAction === "string" && record.nextAction.length <= 256
      ? { nextAction: record.nextAction }
      : {}),
    ...(typeof record.reason === "string" && record.reason.length <= 128
      ? { reason: record.reason }
      : {}),
    ...(typeof record.failureCategory === "string" &&
    record.failureCategory.length <= 128
      ? { failureCategory: record.failureCategory }
      : {}),
    ...(typeof record.affectedStorageId === "string" &&
    record.affectedStorageId.length <= 128
      ? { affectedStorageId: record.affectedStorageId }
      : {}),
    ...(typeof record.affectedStorageName === "string" &&
    record.affectedStorageName.length <= 120
      ? { affectedStorageName: record.affectedStorageName }
      : {}),
    ...(typeof record.currentRevisionId === "string" &&
    record.currentRevisionId.length <= 128
      ? { currentRevisionId: record.currentRevisionId }
      : {}),
    ...(typeof record.currentVersion === "number" &&
    Number.isSafeInteger(record.currentVersion)
      ? { currentVersion: record.currentVersion }
      : {}),
  };
  return Object.keys(details).length > 0 ? details : undefined;
}

function failureDetailsSpread(value: unknown): {
  details?: AutomationMutationFailureDetails;
} {
  const details = normalizeAutomationMutationFailureDetails(value);
  return details === undefined ? {} : { details };
}

async function fetchAutomationDocument<T>(
  token: string | null,
  url: string,
  normalize: (payload: unknown) => T,
  fetchImpl: FetchLike,
): Promise<AutomationMutationResult<T>> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (response.status === 401) {
    return { ok: false, status: 401, code: "unauthorized" };
  }
  if (response.status === 403) {
    return { ok: false, status: 403, code: "forbidden" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    const code =
      typeof envelope.code === "string" && envelope.code.length > 0
        ? envelope.code
        : "request_rejected";
    const details = normalizeAutomationMutationFailureDetails(envelope.details);
    return {
      ok: false,
      status: response.status,
      code,
      ...(details === undefined ? {} : { details }),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, status: response.status, model: normalize(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

async function submitAutomationMutation<T>(
  token: string | null,
  method: "POST" | "PUT" | "DELETE",
  url: string,
  body: Record<string, unknown>,
  normalize: (payload: unknown) => T,
  fetchImpl: FetchLike,
): Promise<AutomationMutationResult<T>> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method,
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    const code =
      typeof envelope.code === "string" && envelope.code.length > 0
        ? envelope.code
        : "request_rejected";
    const details = normalizeAutomationMutationFailureDetails(envelope.details);
    return {
      ok: false,
      status: response.status,
      code,
      ...(details === undefined ? {} : { details }),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, status: response.status, model: normalize(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/**
 * The supported ResourceLibrary include/exclude/stability policy.
 *
 * A rule is either a bounded glob/path string or an explicit
 * `{kind, pattern}` object, exactly the shape the backend validates and the
 * production runtime loader consumes. Omitting the whole policy preserves the
 * exact legacy defaults and every unexposed field of an existing object.
 */
export interface ResourceLibraryScanRule {
  readonly kind?: string;
  readonly pattern: string;
}

export interface ResourceLibraryStabilityPolicy {
  readonly minimumAgeSeconds?: number;
  readonly modifiedThresholdSeconds?: number;
  readonly stableSizeDurationSeconds?: number;
}

export interface SaveResourceLibraryOptions {
  readonly resourceLibraryId: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly storageId: string;
  readonly storagePath: string;
  readonly includeRules?: readonly (string | ResourceLibraryScanRule)[];
  readonly excludeRules?: readonly (string | ResourceLibraryScanRule)[];
  readonly stability?: ResourceLibraryStabilityPolicy;
}

const RESOURCE_LIBRARY_SAVE_ID = /^[a-z0-9][a-z0-9-]{0,63}$/;

export async function saveResourceLibrary(
  token: string | null,
  options: SaveResourceLibraryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<ResourceLibrarySaveModel>> {
  if (
    !RESOURCE_LIBRARY_SAVE_ID.test(options.resourceLibraryId) ||
    options.name.trim().length === 0 ||
    options.name.length > 120 ||
    typeof options.enabled !== "boolean" ||
    options.storageId.trim().length === 0 ||
    options.storageId.length > 64 ||
    options.storageId.includes("/") ||
    options.storageId.includes("\\") ||
    options.storagePath.length > 4096 ||
    options.name.includes("\u0000") ||
    options.storagePath.includes("\u0000")
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    "/api/v1/resource-libraries",
    {
      resourceLibraryId: options.resourceLibraryId,
      name: options.name,
      enabled: options.enabled,
      storageId: options.storageId,
      storagePath: options.storagePath,
      ...resourceLibraryPolicyBody(options),
    },
    normalizeResourceLibrarySave,
    fetchImpl,
  );
}

/**
 * The optional policy fields of one Save/edit body.
 *
 * Only fields the caller actually supplied are sent, so a legacy caller keeps
 * its exact current request body and an edit never rewrites policy it did not
 * intend to change.
 */
function resourceLibraryPolicyBody(
  options: SaveResourceLibraryOptions,
): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (options.includeRules !== undefined) {
    body["includeRules"] = [...options.includeRules];
  }
  if (options.excludeRules !== undefined) {
    body["excludeRules"] = [...options.excludeRules];
  }
  if (options.stability !== undefined) {
    body["stability"] = { ...options.stability };
  }
  return body;
}

export interface LibraryEditProjection<T> {
  readonly library: T;
  readonly storages: readonly SystemStorage[];
  readonly activeRevisionId: string;
  readonly activeVersion: number;
  readonly activeDigest: string;
}

async function fetchLibraryEditProjection<T>(
  token: string | null,
  path: string,
  fetchImpl: FetchLike,
  key: string,
  normalize: (value: unknown) => T,
): Promise<AutomationMutationResult<LibraryEditProjection<T>>> {
  let response: Response;
  try {
    response = await fetchImpl(path, {
      headers: directFilesReadHeaders(token),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" ? envelope.code : "request_rejected",
    };
  }
  try {
    const source = (await response.json()) as Record<string, unknown>;
    const active = source.active as Record<string, unknown>;
    if (!Array.isArray(source.storages)) {
      throw new Error("missing edit Storage projection");
    }
    const storages = source.storages.map((value) => {
      const storage = value as Record<string, unknown>;
      if (
        typeof storage.id !== "string" ||
        typeof storage.name !== "string" ||
        typeof storage.type !== "string" ||
        typeof storage.readOnly !== "boolean" ||
        storage.enabled !== true
      ) {
        throw new Error("invalid edit Storage projection");
      }
      return {
        id: storage.id,
        name: storage.name,
        type: storage.type,
        readOnly: storage.readOnly,
        enabled: true,
      } satisfies SystemStorage;
    });
    return {
      ok: true,
      status: response.status,
      model: {
        library: normalize(source[key]),
        storages,
        activeRevisionId: String(active.revisionId),
        activeVersion: Number(active.revisionSequence),
        activeDigest: String(active.digest),
      },
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export function fetchResourceLibraryEdit(
  token: string | null,
  id: string,
  fetchImpl: FetchLike = fetch,
) {
  return fetchLibraryEditProjection(
    token,
    `/api/v1/resource-libraries/${encodeURIComponent(id)}/edit`,
    fetchImpl,
    "resourceLibrary",
    (value) => {
      const item = value as Record<string, unknown>;
      return {
        resourceLibraryId: String(item.id),
        name: String(item.name),
        enabled: item.enabled === true,
        storageId: String(item.storageId),
        storagePath:
          typeof item.storagePath === "string" ? item.storagePath : "",
        ...(Array.isArray(item.includeRules)
          ? {
              includeRules: item.includeRules as readonly (
                string | ResourceLibraryScanRule
              )[],
            }
          : {}),
        ...(Array.isArray(item.excludeRules)
          ? {
              excludeRules: item.excludeRules as readonly (
                string | ResourceLibraryScanRule
              )[],
            }
          : {}),
        ...(typeof item.stability === "object" && item.stability !== null
          ? { stability: item.stability as ResourceLibraryStabilityPolicy }
          : {}),
      } satisfies SaveResourceLibraryOptions;
    },
  );
}

export function editResourceLibrary(
  token: string | null,
  options: SaveResourceLibraryOptions & {
    readonly expectedRevisionId: string;
    readonly expectedVersion: number;
    readonly expectedDigest: string;
  },
  fetchImpl: FetchLike = fetch,
) {
  return submitAutomationMutation(
    token,
    "PUT",
    `/api/v1/resource-libraries/${encodeURIComponent(options.resourceLibraryId)}`,
    { ...options },
    normalizeResourceLibrarySave,
    fetchImpl,
  );
}

export type DirectFileCommandOptions =
  | {
      readonly operation: "create_directory";
      readonly parentPath: string;
      readonly name: string;
    }
  | {
      readonly operation: "create_text";
      readonly parentPath: string;
      readonly name: string;
      readonly content: string;
    }
  | {
      readonly operation: "rename";
      readonly path: string;
      readonly name: string;
      readonly expected: {
        readonly size: number;
        readonly modifiedAt: string;
        readonly evidence: string;
      };
    }
  | {
      readonly operation: "save_text";
      readonly path: string;
      readonly content: string;
      readonly expected: { readonly size: number; readonly digest: string };
    }
  | {
      readonly operation: "delete";
      readonly paths: readonly string[];
      readonly confirmationDigest: string;
      readonly requestId?: string;
    };

/**
 * Result of one bounded direct-command read (text open, Delete impact, Rename
 * evidence).  Shared by both library kinds.
 */
export type DirectCommandRead<T> =
  | { readonly ok: true; readonly model: T }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    };

/**
 * Runs one bounded direct Files command.  The command result union carries
 * both the success and durable execution outcome; HTTP failures become the
 * bounded AutomationMutationResult failure shape.
 *
 * Slice 38 RO-7: the ResourceLibrary and MediaLibrary journeys share one
 * implementation (`submitDirectCommandThrough`, `readDirectTextThrough`,
 * `readDeleteImpactThrough`, `readRenameEvidenceThrough`) that differs only in
 * the URL namespace it is given.  Same request contract, same permissions, same
 * result model — and one kind's library ID is never addressed into the other
 * kind's namespace.
 */
async function submitDirectCommandThrough(
  token: string | null,
  commandUrl: string,
  options: DirectFileCommandOptions,
  fetchImpl: FetchLike,
): Promise<AutomationMutationResult<DirectFileCommandResult>> {
  const body: Record<string, unknown> = { operation: options.operation };
  if (options.operation === "create_directory") {
    body.parentPath = options.parentPath;
    body.name = options.name;
  } else if (options.operation === "create_text") {
    body.parentPath = options.parentPath;
    body.name = options.name;
    body.content = options.content;
  } else if (options.operation === "rename") {
    body.path = options.path;
    body.name = options.name;
    body.expected = {
      size: options.expected.size,
      modifiedAt: options.expected.modifiedAt,
      evidence: options.expected.evidence,
    };
  } else if (options.operation === "save_text") {
    body.path = options.path;
    body.content = options.content;
    body.expected = {
      size: options.expected.size,
      digest: options.expected.digest,
    };
  } else {
    body.paths = [...options.paths];
    body.confirmationDigest = options.confirmationDigest;
    if (options.requestId !== undefined) body.requestId = options.requestId;
  }
  return submitAutomationMutation(
    token,
    "POST",
    commandUrl,
    body,
    normalizeDirectFileCommandResult,
    fetchImpl,
  );
}

/** The bounded library-identity check shared by both command kinds. */
function directCommandLibraryGuard(libraryId: string): boolean {
  return libraryId.trim().length > 0 && libraryId.length <= 128;
}

export async function submitDirectFileCommand(
  token: string | null,
  resourceLibraryId: string,
  options: DirectFileCommandOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<DirectFileCommandResult>> {
  if (!directCommandLibraryGuard(resourceLibraryId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitDirectCommandThrough(
    token,
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}/files/commands`,
    options,
    fetchImpl,
  );
}

/**
 * The MediaLibrary twin of {@link submitDirectFileCommand}: the identical
 * command admitted and executed under the exact Active MediaLibrary authority.
 */
export async function submitMediaLibraryDirectCommand(
  token: string | null,
  mediaLibraryId: string,
  options: DirectFileCommandOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<DirectFileCommandResult>> {
  if (!directCommandLibraryGuard(mediaLibraryId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitDirectCommandThrough(
    token,
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}/files/commands`,
    options,
    fetchImpl,
  );
}

function directFilesReadHeaders(token: string | null): HeadersInit {
  return token === null
    ? { Accept: "application/json" }
    : { Accept: "application/json", Authorization: `Bearer ${token}` };
}

export interface FilesOrganizeAdmissionOptions {
  readonly resourceLibraryId: string;
  readonly paths: readonly string[];
  /**
   * The caller's own identity for this exact admission request.  The backend
   * resolves the immutable Active pin at admission time, so this value — not a
   * rendered pin — is the proof a lost response reconciles against.  Omitted
   * when the runtime has no cryptographic random source.
   */
  readonly requestId?: string;
  /**
   * Whether this admission is a full same-page preparation (RO-2): after the
   * bounded walk the resident Worker freezes the reviewed sources and links
   * one exact zero-mutation plan summary.  Omitted (false) keeps the explicit
   * Finalize discovery contract.
   */
  readonly autoPrepare?: boolean;
}

export type FilesDiscoveryAdmissionResult =
  | {
      readonly ok: true;
      readonly discoveryId: string;
      readonly scopeCount: number;
      /** The admission request identity the backend durably recorded. */
      readonly admissionRequestId: string | null;
    }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly nextAction: string | null;
    };

/**
 * Admit one bounded folder/mixed selection as a durable discovery (Slice 44
 * RO-6).  The browser submits only the ResourceLibrary identity and exact
 * ResourceLibrary-relative folder/file paths; the backend resolves real entry
 * types, the pinned immutable Active revision and every concrete budget, and
 * returns promptly.  No directory is enumerated and nothing is mutated here.
 */
export async function submitFilesDiscovery(
  token: string | null,
  options: FilesOrganizeAdmissionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<FilesDiscoveryAdmissionResult> {
  if (
    options.resourceLibraryId.trim().length === 0 ||
    options.paths.length === 0
  ) {
    return {
      ok: false,
      status: 400,
      code: "invalid_request",
      nextAction: null,
    };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/resource-libraries/${encodeURIComponent(options.resourceLibraryId)}/files/discoveries`,
      {
        method: "POST",
        headers: {
          ...operationsMutationHeaders(token),
        },
        body: JSON.stringify({
          paths: [...options.paths],
          ...(options.autoPrepare === true ? { autoPrepare: true } : {}),
          ...(options.requestId === undefined
            ? {}
            : { requestId: options.requestId }),
        }),
      },
    );
  } catch {
    return {
      ok: false,
      status: 0,
      code: "transport_unavailable",
      nextAction: null,
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
  if (!response.ok) {
    const record = readRecord(payload, "discoveryError");
    const error = readRecord(record["error"], "discoveryError.error");
    return {
      ok: false,
      status: response.status,
      code:
        typeof error["code"] === "string"
          ? error["code"]
          : "discovery_rejected",
      nextAction:
        typeof error["nextAction"] === "string" ? error["nextAction"] : null,
    };
  }
  const record = readRecord(payload, "discovery");
  const discoveryId = record["discoveryId"];
  if (typeof discoveryId !== "string" || discoveryId.length === 0) {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
  const selection = readRecord(record["selection"], "discovery.selection");
  const echoed = record["admissionRequestId"];
  return {
    ok: true,
    discoveryId,
    scopeCount:
      typeof selection["scopeCount"] === "number" ? selection["scopeCount"] : 0,
    admissionRequestId: typeof echoed === "string" ? echoed : null,
  };
}

export type OrganizeDiscoveryReadResult =
  | { readonly ok: true; readonly model: OrganizeDiscoveryModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly nextAction: string | null;
    };

export interface OrganizeDiscoveryListResult {
  readonly ok: boolean;
  readonly status: number;
  readonly code: string | null;
  readonly items: readonly OrganizeDiscoveryModel[];
}

/**
 * Read this principal's bounded recent discovery list.
 *
 * The unknown-admission reconciliation uses this read: when a discovery
 * admission response was lost, the durable record is located here instead of
 * being re-admitted, so no duplicate walk is created.
 */
export async function fetchOrganizeDiscoveries(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeDiscoveryListResult> {
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/organize/discoveries", {
      headers: { ...operationsHeaders(token) },
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable", items: [] };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      items: [],
    };
  }
  if (!response.ok) {
    const failure = discoveryErrorResult(response.status, payload);
    return {
      ok: false,
      status: response.status,
      code: failure.code,
      items: [],
    };
  }
  try {
    const record = readRecord(payload, "discoveryList");
    const items = record["items"];
    if (!Array.isArray(items)) {
      return {
        ok: false,
        status: response.status,
        code: "malformed_response",
        items: [],
      };
    }
    return {
      ok: true,
      status: response.status,
      code: null,
      items: items.map((item) => normalizeOrganizeDiscovery(item)),
    };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      items: [],
    };
  }
}

/** Read one bounded discovery projection. */
export async function fetchOrganizeDiscovery(
  token: string | null,
  discoveryId: string,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeDiscoveryReadResult> {
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/discoveries/${encodeURIComponent(discoveryId)}`,
      { headers: { ...operationsHeaders(token) } },
    );
  } catch {
    return {
      ok: false,
      status: 0,
      code: "transport_unavailable",
      nextAction: null,
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
  if (!response.ok) {
    return discoveryErrorResult(response.status, payload);
  }
  try {
    return { ok: true, model: normalizeOrganizeDiscovery(payload) };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
}

export interface OrganizeDiscoveryControlOptions {
  readonly discoveryId: string;
  readonly action: "pause" | "resume" | "cancel";
  readonly expectedVersion: number;
}

export type OrganizeDiscoveryControlResult =
  | { readonly ok: true; readonly model: OrganizeDiscoveryModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly nextAction: string | null;
    };

/**
 * Submit one cooperative, versioned discovery control.  Pause and cancel only
 * record a request the resident Worker honours at its next safe boundary; they
 * never grant execution authority.
 */
export async function controlOrganizeDiscovery(
  token: string | null,
  options: OrganizeDiscoveryControlOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeDiscoveryControlResult> {
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/discoveries/${encodeURIComponent(
        options.discoveryId,
      )}/${options.action}`,
      {
        method: "POST",
        headers: { ...operationsMutationHeaders(token) },
        body: JSON.stringify({ expectedVersion: options.expectedVersion }),
      },
    );
  } catch {
    return {
      ok: false,
      status: 0,
      code: "transport_unavailable",
      nextAction: null,
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
  if (!response.ok) {
    return discoveryErrorResult(response.status, payload);
  }
  try {
    return { ok: true, model: normalizeOrganizeDiscovery(payload) };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
}

export interface OrganizeDiscoveryFinalizeOptions {
  readonly discoveryId: string;
  readonly expectedVersion: number;
}

export type OrganizeDiscoveryFinalizeResult =
  | { readonly ok: true; readonly intentId: string | null }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly nextAction: string | null;
    };

export interface OrganizeDiscoveryAnalysisOptions {
  readonly discoveryId: string;
  readonly expectedVersion: number;
}

/**
 * Re-enter the durable analysis stage of a full preparation after the operator
 * saved a legal correction on its linked intent.
 *
 * This records one versioned request only: the resident Worker re-runs the
 * complete zero-mutation analysis under the same pinned configuration and
 * links a new exact Preview.  It grants no execution authority.
 */
export async function requestOrganizeDiscoveryAnalysis(
  token: string | null,
  options: OrganizeDiscoveryAnalysisOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeDiscoveryControlResult> {
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/discoveries/${encodeURIComponent(
        options.discoveryId,
      )}/analyze`,
      {
        method: "POST",
        headers: { ...operationsMutationHeaders(token) },
        body: JSON.stringify({ expectedVersion: options.expectedVersion }),
      },
    );
  } catch {
    return {
      ok: false,
      status: 0,
      code: "transport_unavailable",
      nextAction: null,
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
  if (!response.ok) {
    return discoveryErrorResult(response.status, payload);
  }
  try {
    return { ok: true, model: normalizeOrganizeDiscovery(payload) };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
}

/**
 * Freeze the discovered source list and link the existing durable manual
 * intent.  It grants no execution authority: a separate exact Preview and a
 * confirmed execution remain required.
 */
export async function finalizeOrganizeDiscovery(
  token: string | null,
  options: OrganizeDiscoveryFinalizeOptions,
  fetchImpl: FetchLike = fetch,
): Promise<OrganizeDiscoveryFinalizeResult> {
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/organize/discoveries/${encodeURIComponent(
        options.discoveryId,
      )}/finalize`,
      {
        method: "POST",
        headers: { ...operationsMutationHeaders(token) },
        body: JSON.stringify({ expectedVersion: options.expectedVersion }),
      },
    );
  } catch {
    return {
      ok: false,
      status: 0,
      code: "transport_unavailable",
      nextAction: null,
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
  if (!response.ok) {
    return discoveryErrorResult(response.status, payload);
  }
  try {
    const model = normalizeOrganizeDiscovery(payload);
    return { ok: true, intentId: model.intentId };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
}

/**
 * A tolerant record reader for a bounded error envelope: an absent, non-object
 * or array field is absence, never an exception, so reading a failure response
 * can never destroy the HTTP status that classifies it.
 */
function optionalRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function discoveryErrorResult(status: number, payload: unknown) {
  // The bounded error envelope may omit `details` (the backend does so for
  // 401/403 and other auth errors) or arrive as a non-envelope body from a
  // proxy. Reading it must never throw the HTTP status away: that status is
  // the truthful, bounded classification the read consumer needs to explain
  // the failure and offer its explicit recovery.
  const record = optionalRecord(payload);
  const error = optionalRecord(record?.["error"]);
  const details = optionalRecord(error?.["details"]);
  return {
    ok: false as const,
    status,
    code:
      typeof error?.["code"] === "string"
        ? error["code"]
        : "discovery_rejected",
    nextAction:
      typeof details?.["nextAction"] === "string"
        ? details["nextAction"]
        : typeof error?.["nextAction"] === "string"
          ? error["nextAction"]
          : null,
  };
}

export type FilesOrganizeAdmissionResult =
  | {
      readonly ok: true;
      readonly intentId: string;
      readonly itemCount: number;
    }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly nextAction: string | null;
    };

/**
 * Admit one bounded Files selection as the existing durable manual Organize
 * intent.  The browser submits only the ResourceLibrary identity and
 * ResourceLibrary-relative paths; every source identity is derived
 * server-side from the pinned Active Storage.
 */
export async function submitFilesOrganizeIntent(
  token: string | null,
  options: FilesOrganizeAdmissionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<FilesOrganizeAdmissionResult> {
  if (
    options.resourceLibraryId.trim().length === 0 ||
    options.paths.length === 0
  ) {
    return {
      ok: false,
      status: 400,
      code: "invalid_request",
      nextAction: null,
    };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/resource-libraries/${encodeURIComponent(options.resourceLibraryId)}/files/organize`,
      {
        method: "POST",
        headers: {
          ...operationsMutationHeaders(token),
        },
        body: JSON.stringify({ paths: [...options.paths] }),
      },
    );
  } catch {
    return {
      ok: false,
      status: 0,
      code: "transport_unavailable",
      nextAction: null,
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const record =
      payload !== null && typeof payload === "object" && !Array.isArray(payload)
        ? (payload as Record<string, unknown>)
        : {};
    const error = record.error;
    const envelope =
      error !== null && typeof error === "object" && !Array.isArray(error)
        ? (error as Record<string, unknown>)
        : {};
    const details =
      envelope.details !== null &&
      typeof envelope.details === "object" &&
      !Array.isArray(envelope.details)
        ? (envelope.details as Record<string, unknown>)
        : {};
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" ? envelope.code : "request_rejected",
      nextAction:
        typeof details.nextAction === "string" ? details.nextAction : null,
    };
  }
  const document =
    payload !== null && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : null;
  const intentId = document?.intentId;
  if (typeof intentId !== "string" || intentId.length === 0) {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
      nextAction: null,
    };
  }
  const items = Array.isArray(document?.items) ? document.items : [];
  return { ok: true, intentId, itemCount: items.length };
}

/** Bounded zero-mutation open of one allowlisted text file. */
async function readDirectTextThrough(
  token: string | null,
  textUrl: string,
  path: string,
  kind: DirectCommandLibraryKind,
  fetchImpl: FetchLike,
): Promise<DirectCommandRead<TextFileDocument>> {
  if (path.trim().length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  let response: Response;
  try {
    response = await fetchImpl(`${textUrl}?path=${encodeURIComponent(path)}`, {
      headers: directFilesReadHeaders(token),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  try {
    return {
      ok: true,
      model: normalizeTextFileDocument(await response.json(), kind),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export async function fetchTextFile(
  token: string | null,
  resourceLibraryId: string,
  path: string,
  fetchImpl: FetchLike = fetch,
): Promise<DirectCommandRead<TextFileDocument>> {
  if (resourceLibraryId.trim().length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readDirectTextThrough(
    token,
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}/files/text`,
    path,
    "resource",
    fetchImpl,
  );
}

/** The MediaLibrary twin of {@link fetchTextFile}. */
export async function fetchMediaLibraryTextFile(
  token: string | null,
  mediaLibraryId: string,
  path: string,
  fetchImpl: FetchLike = fetch,
): Promise<DirectCommandRead<TextFileDocument>> {
  if (mediaLibraryId.trim().length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readDirectTextThrough(
    token,
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}/files/text`,
    path,
    "media",
    fetchImpl,
  );
}

/** Bounded zero-mutation impact enumeration for one Delete selection. */
async function readDeleteImpactThrough(
  token: string | null,
  impactUrl: string,
  paths: readonly string[],
  kind: DirectCommandLibraryKind,
  fetchImpl: FetchLike,
): Promise<DirectCommandRead<DeleteImpactModel>> {
  if (paths.length === 0 || paths.length > 50) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const query = paths
    .map((path) => `path=${encodeURIComponent(path)}`)
    .join("&");
  let response: Response;
  try {
    response = await fetchImpl(`${impactUrl}?${query}`, {
      headers: directFilesReadHeaders(token),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  try {
    return {
      ok: true,
      model: normalizeDeleteImpact(await response.json(), kind),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export async function fetchDeleteImpact(
  token: string | null,
  resourceLibraryId: string,
  paths: readonly string[],
  fetchImpl: FetchLike = fetch,
): Promise<DirectCommandRead<DeleteImpactModel>> {
  if (resourceLibraryId.trim().length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readDeleteImpactThrough(
    token,
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}/files/delete-impact`,
    paths,
    "resource",
    fetchImpl,
  );
}

/** The MediaLibrary twin of {@link fetchDeleteImpact}. */
export async function fetchMediaLibraryDeleteImpact(
  token: string | null,
  mediaLibraryId: string,
  paths: readonly string[],
  fetchImpl: FetchLike = fetch,
): Promise<DirectCommandRead<DeleteImpactModel>> {
  if (mediaLibraryId.trim().length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readDeleteImpactThrough(
    token,
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}/files/delete-impact`,
    paths,
    "media",
    fetchImpl,
  );
}

async function readDeleteStatusThrough(
  token: string | null,
  url: string,
  kind: DirectCommandLibraryKind,
  libraryId: string,
  taskId: string,
  fetchImpl: FetchLike,
): Promise<DirectCommandRead<DirectFileCommandResult>> {
  let response: Response;
  try {
    response = await fetchImpl(url, { headers: directFilesReadHeaders(token) });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  try {
    const payload: unknown = await response.json();
    if (
      payload === null ||
      typeof payload !== "object" ||
      Array.isArray(payload)
    ) {
      throw new TypeError("malformed Delete status");
    }
    const record = payload as Record<string, unknown>;
    const identityField = libraryIdField(kind);
    const foreignIdentityField = libraryIdField(
      kind === "media" ? "resource" : "media",
    );
    if (
      record.operation !== "delete" ||
      record.taskId !== taskId ||
      record[identityField] !== libraryId ||
      record[foreignIdentityField] !== undefined
    ) {
      throw new TypeError("Delete status identity does not match its route");
    }
    return {
      ok: true,
      model: normalizeDirectFileCommandResult(payload),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/** Read the durable Delete result for one ResourceLibrary Task. */
export function fetchDeleteStatus(
  token: string | null,
  resourceLibraryId: string,
  taskId: string,
  fetchImpl: FetchLike = fetch,
): Promise<DirectCommandRead<DirectFileCommandResult>> {
  if (
    !directCommandLibraryGuard(resourceLibraryId) ||
    taskId.trim().length === 0 ||
    taskId.length > 128
  ) {
    return Promise.resolve({ ok: false, status: 400, code: "invalid_request" });
  }
  return readDeleteStatusThrough(
    token,
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}/files/deletes/${encodeURIComponent(taskId)}`,
    "resource",
    resourceLibraryId,
    taskId,
    fetchImpl,
  );
}

/** The kind-isolated MediaLibrary twin of {@link fetchDeleteStatus}. */
export function fetchMediaLibraryDeleteStatus(
  token: string | null,
  mediaLibraryId: string,
  taskId: string,
  fetchImpl: FetchLike = fetch,
): Promise<DirectCommandRead<DirectFileCommandResult>> {
  if (
    !directCommandLibraryGuard(mediaLibraryId) ||
    taskId.trim().length === 0 ||
    taskId.length > 128
  ) {
    return Promise.resolve({ ok: false, status: 400, code: "invalid_request" });
  }
  return readDeleteStatusThrough(
    token,
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}/files/deletes/${encodeURIComponent(taskId)}`,
    "media",
    mediaLibraryId,
    taskId,
    fetchImpl,
  );
}

/**
 * Zero-mutation version evidence one Rename command must return.
 *
 * The backend observes the exact entry version and issues an opaque token; the
 * page only echoes it back, so a source replaced after the evidence was issued
 * is refused stale instead of renamed.
 */
async function readRenameEvidenceThrough(
  token: string | null,
  evidenceUrl: string,
  path: string,
  kind: DirectCommandLibraryKind,
  fetchImpl: FetchLike,
): Promise<DirectCommandRead<RenameEvidenceModel>> {
  if (path.length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `${evidenceUrl}?path=${encodeURIComponent(path)}`,
      { headers: directFilesReadHeaders(token) },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  try {
    return {
      ok: true,
      model: normalizeRenameEvidence(await response.json(), kind),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export async function fetchRenameEvidence(
  token: string | null,
  resourceLibraryId: string,
  path: string,
  fetchImpl: FetchLike = fetch,
): Promise<DirectCommandRead<RenameEvidenceModel>> {
  if (resourceLibraryId.trim().length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readRenameEvidenceThrough(
    token,
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}/files/rename-evidence`,
    path,
    "resource",
    fetchImpl,
  );
}

/** The MediaLibrary twin of {@link fetchRenameEvidence}. */
export async function fetchMediaLibraryRenameEvidence(
  token: string | null,
  mediaLibraryId: string,
  path: string,
  fetchImpl: FetchLike = fetch,
): Promise<DirectCommandRead<RenameEvidenceModel>> {
  if (mediaLibraryId.trim().length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readRenameEvidenceThrough(
    token,
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}/files/rename-evidence`,
    path,
    "media",
    fetchImpl,
  );
}

/** One confirmed bounded Copy/Move request the backend validates as a unit. */
export interface TransferRequestOptions {
  readonly operation: TransferOperation;
  readonly paths: readonly string[];
  readonly destinationResourceLibraryId: string;
  readonly destinationDirectory: string;
  readonly conflictMode: TransferConflictMode;
  readonly manifestDigest: string;
}

/**
 * Bounded zero-mutation impact/admission read for one proposed Copy/Move.
 * The paths are encoded as repeated `path` values; the response carries the
 * opaque manifest digest the later execution must return.
 */
export async function fetchTransferImpact(
  token: string | null,
  resourceLibraryId: string,
  options: {
    readonly operation: TransferOperation;
    readonly paths: readonly string[];
    readonly destinationResourceLibraryId: string;
    readonly destinationDirectory: string;
    readonly conflictMode: TransferConflictMode;
  },
  fetchImpl: FetchLike = fetch,
): Promise<
  | { readonly ok: true; readonly model: TransferImpactModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (
    resourceLibraryId.trim().length === 0 ||
    options.paths.length === 0 ||
    options.paths.length > 50 ||
    options.destinationResourceLibraryId.trim().length === 0
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readTransferImpactThrough(
    token,
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}`,
    "resource",
    options,
    fetchImpl,
  );
}

/**
 * The MediaLibrary twin of {@link fetchTransferImpact}.
 *
 * The same bounded zero-mutation admission read reaches the media-scoped route
 * and is normalized as media evidence only: a ResourceLibrary document (or a
 * ResourceLibrary ID supplied here) is simply not this kind's authority and
 * fails closed.
 */
export async function fetchMediaLibraryTransferImpact(
  token: string | null,
  mediaLibraryId: string,
  options: {
    readonly operation: TransferOperation;
    readonly paths: readonly string[];
    readonly destinationMediaLibraryId: string;
    readonly destinationDirectory: string;
    readonly conflictMode: TransferConflictMode;
  },
  fetchImpl: FetchLike = fetch,
): Promise<
  | { readonly ok: true; readonly model: TransferImpactModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (
    mediaLibraryId.trim().length === 0 ||
    options.paths.length === 0 ||
    options.paths.length > 50 ||
    options.destinationMediaLibraryId.trim().length === 0
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readTransferImpactThrough(
    token,
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}`,
    "media",
    {
      operation: options.operation,
      paths: options.paths,
      destinationResourceLibraryId: options.destinationMediaLibraryId,
      destinationDirectory: options.destinationDirectory,
      conflictMode: options.conflictMode,
    },
    fetchImpl,
  );
}

async function readTransferImpactThrough(
  token: string | null,
  libraryBasePath: string,
  kind: DirectCommandLibraryKind,
  options: {
    readonly operation: TransferOperation;
    readonly paths: readonly string[];
    readonly destinationResourceLibraryId: string;
    readonly destinationDirectory: string;
    readonly conflictMode: TransferConflictMode;
  },
  fetchImpl: FetchLike,
): Promise<
  | { readonly ok: true; readonly model: TransferImpactModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  const query = [
    ...options.paths.map((path) => `path=${encodeURIComponent(path)}`),
    `to=${encodeURIComponent(options.destinationResourceLibraryId)}`,
    `toPath=${encodeURIComponent(options.destinationDirectory)}`,
    `operation=${encodeURIComponent(options.operation)}`,
    `conflict=${encodeURIComponent(options.conflictMode)}`,
  ].join("&");
  let response: Response;
  try {
    response = await fetchImpl(
      `${libraryBasePath}/files/transfer-impact?${query}`,
      {
        headers: directFilesReadHeaders(token),
      },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  try {
    return {
      ok: true,
      model: normalizeTransferImpact(await response.json(), kind),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/**
 * Reads the durable bounded projection of one admitted transfer Task.
 * Polling this read is how the dialog follows queued/running/paused progress
 * with the backend-advertised lifecycle actions; the projection never
 * contains a claim token, lease value or raw Task-ID ceremony.
 */
export async function fetchTransferProjection(
  token: string | null,
  resourceLibraryId: string,
  taskId: string,
  fetchImpl: FetchLike = fetch,
): Promise<
  | { readonly ok: true; readonly model: TransferProjectionModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (resourceLibraryId.trim().length === 0 || !isSafeIdentifier(taskId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readTransferProjectionThrough(
    token,
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}`,
    "resource",
    taskId,
    fetchImpl,
  );
}

/**
 * The MediaLibrary twin of {@link fetchTransferProjection}.
 *
 * The media projection is read from the media-scoped route and normalized as
 * media evidence only, so an equal ResourceLibrary ID can never read a media
 * transfer's durable state through this page (or the reverse).
 */
export async function fetchMediaLibraryTransferProjection(
  token: string | null,
  mediaLibraryId: string,
  taskId: string,
  fetchImpl: FetchLike = fetch,
): Promise<
  | { readonly ok: true; readonly model: TransferProjectionModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (mediaLibraryId.trim().length === 0 || !isSafeIdentifier(taskId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return readTransferProjectionThrough(
    token,
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}`,
    "media",
    taskId,
    fetchImpl,
  );
}

async function readTransferProjectionThrough(
  token: string | null,
  libraryBasePath: string,
  kind: DirectCommandLibraryKind,
  taskId: string,
  fetchImpl: FetchLike,
): Promise<
  | { readonly ok: true; readonly model: TransferProjectionModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  let response: Response;
  try {
    response = await fetchImpl(
      `${libraryBasePath}/files/transfers/${encodeURIComponent(taskId)}`,
      { headers: directFilesReadHeaders(token) },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  try {
    return {
      ok: true,
      model: normalizeTransferProjection(await response.json(), kind),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/**
 * One advertised transfer lifecycle action (pause/cancel/resume) submitted
 * through the normal authenticated Task lifecycle API.  The projection's
 * version travels as the optimistic-concurrency value, so a control against
 * changed state is refused stale.
 */
export async function mutateTransferLifecycle(
  token: string | null,
  taskId: string,
  action: "pause" | "cancel" | "resume",
  expectedVersion: string,
  fetchImpl: FetchLike = fetch,
  kind: DirectCommandLibraryKind = "resource",
): Promise<
  | {
      readonly ok: true;
      readonly status: number;
      readonly model?: TransferProjectionModel;
      readonly nextAction?: string;
    }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (!isSafeIdentifier(taskId) || expectedVersion.length > 128) {
    return { ok: false, status: 0, code: "invalid_request" };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/tasks/${encodeURIComponent(taskId)}/${action}`,
      {
        method: "POST",
        headers: operationsMutationHeaders(token),
        body: JSON.stringify({ expectedUpdatedAt: expectedVersion }),
      },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const envelope =
      body !== null && typeof body === "object" && !Array.isArray(body)
        ? (body as Record<string, unknown>)
        : {};
    const error =
      envelope.error !== null && typeof envelope.error === "object"
        ? (envelope.error as Record<string, unknown>)
        : {};
    return {
      ok: false,
      status: response.status,
      code: typeof error.code === "string" ? error.code : "request_rejected",
      ...failureDetailsSpread(error.details),
    };
  }
  if (action === "resume" && body !== null && typeof body === "object") {
    try {
      return {
        ok: true,
        status: response.status,
        model: normalizeTransferProjection(body, kind),
      };
    } catch {
      return { ok: false, status: response.status, code: "malformed_response" };
    }
  }
  return { ok: true, status: response.status };
}

/**
 * Executes the confirmed bounded Copy/Move.  The opaque manifest digest binds
 * the execution to the exact impact the operator confirmed; a changed scope is
 * refused stale and never mutated.  Submission only *admits* the durable
 * transfer: the response is the queued projection and the resident Worker
 * executes it off the request stack.
 */
export async function submitTransfer(
  token: string | null,
  resourceLibraryId: string,
  options: TransferRequestOptions,
  fetchImpl: FetchLike = fetch,
): Promise<
  | { readonly ok: true; readonly model: TransferResultModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (
    resourceLibraryId.trim().length === 0 ||
    options.paths.length === 0 ||
    options.paths.length > 50 ||
    options.destinationResourceLibraryId.trim().length === 0 ||
    options.manifestDigest.trim().length === 0
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}/files/transfers`,
    {
      operation: options.operation,
      paths: [...options.paths],
      destinationResourceLibraryId: options.destinationResourceLibraryId,
      destinationDirectory: options.destinationDirectory,
      conflictMode: options.conflictMode,
      manifestDigest: options.manifestDigest,
    },
    normalizeTransferResult,
    fetchImpl,
  );
}

/** One confirmed bounded MediaLibrary Copy/Move request. */
export interface MediaTransferRequestOptions {
  readonly operation: TransferOperation;
  readonly paths: readonly string[];
  readonly destinationMediaLibraryId: string;
  readonly destinationDirectory: string;
  readonly conflictMode: TransferConflictMode;
  readonly manifestDigest: string;
}

/**
 * The MediaLibrary twin of {@link submitTransfer}.
 *
 * The same single explicit submission admits one durable media transfer Task
 * through the media-scoped route; the response is the queued durable
 * projection and no Storage mutation happens on this request's stack.  The
 * media document is normalized as media evidence only.
 */
export async function submitMediaLibraryTransfer(
  token: string | null,
  mediaLibraryId: string,
  options: MediaTransferRequestOptions,
  fetchImpl: FetchLike = fetch,
): Promise<
  | { readonly ok: true; readonly model: TransferResultModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (
    mediaLibraryId.trim().length === 0 ||
    options.paths.length === 0 ||
    options.paths.length > 50 ||
    options.destinationMediaLibraryId.trim().length === 0 ||
    options.manifestDigest.trim().length === 0
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}/files/transfers`,
    {
      operation: options.operation,
      paths: [...options.paths],
      destinationMediaLibraryId: options.destinationMediaLibraryId,
      destinationDirectory: options.destinationDirectory,
      conflictMode: options.conflictMode,
      manifestDigest: options.manifestDigest,
    },
    (payload) => normalizeTransferResult(payload, "media"),
    fetchImpl,
  );
}

/** Bounded secret-free removal preview from the current Active snapshot. */
export async function fetchResourceLibraryRemovalPreview(
  token: string | null,
  resourceLibraryId: string,
  fetchImpl: FetchLike = fetch,
): Promise<
  | { readonly ok: true; readonly model: RemovalPreviewModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (resourceLibraryId.trim().length === 0) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}/removal-preview`,
      { headers: directFilesReadHeaders(token) },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  try {
    return { ok: true, model: normalizeRemovalPreview(await response.json()) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/**
 * Removes one unreferenced ResourceLibrary from managed configuration.  The
 * request binds the exact previewed Active revision and selected library
 * identity; the backend rejects stale, mismatched or disabled confirmations
 * and publishes the validated successor atomically, never touching Storage
 * content.
 */
export async function removeResourceLibrary(
  token: string | null,
  resourceLibraryId: string,
  expected: {
    readonly revisionId: string;
    readonly version: number;
    readonly digest: string;
    readonly libraryId: string;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<ResourceLibraryRemovalModel>> {
  if (
    resourceLibraryId.trim().length === 0 ||
    resourceLibraryId.length > 128 ||
    expected.libraryId !== resourceLibraryId ||
    expected.revisionId.trim().length === 0 ||
    expected.revisionId.length > 128 ||
    expected.digest.trim().length === 0 ||
    expected.digest.length > 128 ||
    !Number.isSafeInteger(expected.version) ||
    expected.version < 0
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "DELETE",
    `/api/v1/resource-libraries/${encodeURIComponent(resourceLibraryId)}`,
    {
      expectedRevisionId: expected.revisionId,
      expectedVersion: expected.version,
      expectedDigest: expected.digest,
      expectedLibraryId: expected.libraryId,
    },
    normalizeResourceLibraryRemoval,
    fetchImpl,
  );
}

export interface SaveMediaLibraryOptions {
  readonly mediaLibraryId: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly storageId: string;
  readonly rootPath: string;
}

/**
 * Saves one MediaLibrary-page candidate through the exact checked Active
 * boundary.  Client-side validation mirrors the backend admission contract so
 * an obviously invalid candidate never reaches the mutation, and the strict
 * response normalizer fails a malformed or split-identity success closed.
 */
export async function saveMediaLibrary(
  token: string | null,
  options: SaveMediaLibraryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<MediaLibrarySaveModel>> {
  if (
    !MEDIA_LIBRARY_ID.test(options.mediaLibraryId) ||
    options.name.trim().length === 0 ||
    options.name.length > 120 ||
    typeof options.enabled !== "boolean" ||
    options.storageId.trim().length === 0 ||
    options.storageId.length > 64 ||
    options.storageId.includes("/") ||
    options.storageId.includes("\\") ||
    options.rootPath.length > 4096 ||
    options.name.includes("\u0000") ||
    options.rootPath.includes("\u0000")
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    "/api/v1/media-libraries",
    {
      mediaLibraryId: options.mediaLibraryId,
      name: options.name,
      enabled: options.enabled,
      storageId: options.storageId,
      rootPath: options.rootPath,
    },
    normalizeMediaLibrarySave,
    fetchImpl,
  );
}

export function fetchMediaLibraryEdit(
  token: string | null,
  id: string,
  fetchImpl: FetchLike = fetch,
) {
  return fetchLibraryEditProjection(
    token,
    `/api/v1/media-libraries/${encodeURIComponent(id)}/edit`,
    fetchImpl,
    "mediaLibrary",
    (value) => {
      const item = value as Record<string, unknown>;
      return {
        mediaLibraryId: String(item.id),
        name: String(item.name),
        enabled: item.enabled === true,
        storageId: String(item.storageId),
        rootPath: typeof item.rootPath === "string" ? item.rootPath : "",
      } satisfies SaveMediaLibraryOptions;
    },
  );
}

export function editMediaLibrary(
  token: string | null,
  options: SaveMediaLibraryOptions & {
    readonly expectedRevisionId: string;
    readonly expectedVersion: number;
    readonly expectedDigest: string;
  },
  fetchImpl: FetchLike = fetch,
) {
  return submitAutomationMutation(
    token,
    "PUT",
    `/api/v1/media-libraries/${encodeURIComponent(options.mediaLibraryId)}`,
    { ...options },
    normalizeMediaLibrarySave,
    fetchImpl,
  );
}

export async function fetchMediaLibraryRemovalPreview(
  token: string | null,
  mediaLibraryId: string,
  fetchImpl: FetchLike = fetch,
): Promise<
  | { readonly ok: true; readonly model: MediaLibraryRemovalPreviewModel }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: AutomationMutationFailureDetails;
    }
> {
  if (!MEDIA_LIBRARY_ID.test(mediaLibraryId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}/removal-preview`,
      { headers: directFilesReadHeaders(token) },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  try {
    return {
      ok: true,
      model: normalizeMediaLibraryRemovalPreview(await response.json()),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/**
 * Removes one unreferenced MediaLibrary from managed configuration.  The
 * request binds the exact previewed Active revision and selected library
 * identity; the backend rejects stale, mismatched, disabled or referenced
 * confirmations and publishes the validated successor atomically, never
 * deleting the MediaLibrary root or any Storage content.
 */
export async function removeMediaLibrary(
  token: string | null,
  mediaLibraryId: string,
  expected: {
    readonly revisionId: string;
    readonly version: number;
    readonly digest: string;
    readonly libraryId: string;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<MediaLibraryRemovalModel>> {
  if (
    !MEDIA_LIBRARY_ID.test(mediaLibraryId) ||
    expected.libraryId !== mediaLibraryId ||
    expected.revisionId.trim().length === 0 ||
    expected.revisionId.length > 128 ||
    expected.digest.trim().length === 0 ||
    expected.digest.length > 128 ||
    !Number.isSafeInteger(expected.version) ||
    expected.version < 0
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "DELETE",
    `/api/v1/media-libraries/${encodeURIComponent(mediaLibraryId)}`,
    {
      expectedRevisionId: expected.revisionId,
      expectedVersion: expected.version,
      expectedDigest: expected.digest,
      expectedLibraryId: expected.libraryId,
    },
    normalizeMediaLibraryRemoval,
    fetchImpl,
  );
}

export type AutomationDefinitionsRead =
  | { readonly ok: true; readonly model: AutomationDefinitionsPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

/**
 * The submitted Automation inventory read basis.
 *
 * Every filter is a server-side query parameter: the page never filters a
 * partial list in the browser and never derives a total or a metric from the
 * rows it happens to hold. The cursor is only ever taken from the response to
 * the identical filter state.
 */
export interface AutomationInventoryQueryOptions {
  readonly q?: string | null;
  readonly enabled?: boolean | null;
  readonly library?: string | null;
  readonly state?: string | null;
  readonly sort?: string | null;
  readonly direction?: string | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export function automationDefinitionsUrl(
  options: AutomationInventoryQueryOptions = {},
): string {
  const params = new URLSearchParams();
  if (options.q) params.set("q", options.q);
  if (options.enabled !== null && options.enabled !== undefined) {
    params.set("enabled", options.enabled ? "true" : "false");
  }
  if (options.library) params.set("library", options.library);
  if (options.state) params.set("state", options.state);
  if (options.sort) params.set("sort", options.sort);
  if (options.direction) params.set("direction", options.direction);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const qs = params.toString();
  return `/api/v1/operations/automation/task-definitions${qs ? `?${qs}` : ""}`;
}

// --- Focused Automation engine settings (Task 43.4) ----------------------

/** The one shared engine-settings read/command URL. */
export const automationSettingsUrl = "/api/v1/operations/automation/settings";

export type AutomationSettingsRead =
  | { readonly ok: true; readonly model: AutomationSettingsModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export type AutomationSettingsSave =
  | {
      readonly ok: true;
      readonly status: number;
      readonly published: boolean;
      readonly unchanged: boolean;
      readonly revisionId: string | null;
      readonly readback: AutomationSettingsModel;
    }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly unknownOutcome: boolean;
      readonly details?: AutomationMutationFailureDetails;
    };

export type AutomationSettingsReconcile =
  | {
      readonly ok: true;
      readonly committed: boolean;
      readonly nextAction: string | null;
      readonly evidenceRevisionId: string | null;
    }
  | { readonly ok: false; readonly status: number; readonly code: string };

/**
 * Read the published target plus each live consumer's own adoption.
 *
 * A read never mutates: it creates no Draft, admits no work and grants no
 * authority, which is why the page can poll it freely.
 */
export async function fetchAutomationSettings(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationSettingsRead> {
  let response: Response;
  try {
    response = await fetchImpl(automationSettingsUrl, {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    return { ok: false, failure: operationsFailure("unauthorized") };
  }
  if (response.status === 403) {
    return { ok: false, failure: operationsFailure("forbidden") };
  }
  if (!response.ok) {
    return {
      ok: false,
      failure: operationsFailure(
        response.status >= 500 ? "unavailable" : "rejected",
      ),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, failure: operationsFailure("malformed") };
  }
  try {
    return { ok: true, model: normalizeAutomationSettings(payload) };
  } catch {
    return { ok: false, failure: operationsFailure("malformed") };
  }
}

/**
 * Publish exactly the four engine fields through one checked Save.
 *
 * A transport failure or an unexplained 5xx is reported as an *unknown*
 * outcome: the browser must reconcile from durable evidence instead of
 * re-submitting, and this function never retries on its own.
 */
export async function saveAutomationSettings(
  token: string | null,
  body: Record<string, unknown>,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationSettingsSave> {
  let response: Response;
  try {
    response = await fetchImpl(automationSettingsUrl, {
      method: "PUT",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return {
      ok: false,
      status: 0,
      code: "transport_unavailable",
      unknownOutcome: true,
    };
  }
  if (response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      return {
        ok: false,
        status: response.status,
        code: "malformed_response",
        unknownOutcome: true,
      };
    }
    const record =
      typeof payload === "object" && payload !== null && !Array.isArray(payload)
        ? (payload as Record<string, unknown>)
        : null;
    if (record === null) {
      return {
        ok: false,
        status: response.status,
        code: "malformed_response",
        unknownOutcome: true,
      };
    }
    let readback: AutomationSettingsModel;
    try {
      readback = normalizeAutomationSettings(record["readback"] ?? payload);
    } catch {
      return {
        ok: false,
        status: response.status,
        code: "malformed_response",
        unknownOutcome: true,
      };
    }
    return {
      ok: true,
      status: response.status,
      published: record["published"] === true,
      unchanged: record["unchanged"] === true,
      revisionId:
        typeof record["revisionId"] === "string" ? record["revisionId"] : null,
      readback,
    };
  }
  const envelope = await readErrorEnvelope(response);
  const code =
    typeof envelope.code === "string" && envelope.code.length > 0
      ? envelope.code
      : "request_rejected";
  const details = normalizeAutomationMutationFailureDetails(envelope.details);
  // Only an explicit durable-state statement makes a 5xx a *known* failure. An
  // internal error may have failed before or after committing, so it stays
  // unknown and blocks an automatic retry.
  const unknownOutcome =
    response.status >= 500 &&
    (details?.durableState === undefined || code === "internal_error");
  return {
    ok: false,
    status: response.status,
    code,
    unknownOutcome,
    ...(details === undefined ? {} : { details }),
  };
}

/** Read back whether one lost submission actually published. */
export async function reconcileAutomationSettings(
  token: string | null,
  body: Record<string, unknown>,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationSettingsReconcile> {
  let response: Response;
  try {
    response = await fetchImpl(automationSettingsUrl, {
      method: "PUT",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  const record =
    typeof payload === "object" && payload !== null && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : null;
  if (record === null) {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  const evidence =
    typeof record["evidence"] === "object" &&
    record["evidence"] !== null &&
    !Array.isArray(record["evidence"])
      ? (record["evidence"] as Record<string, unknown>)
      : null;
  return {
    ok: true,
    committed: record["committed"] === true,
    nextAction:
      typeof record["nextAction"] === "string" ? record["nextAction"] : null,
    evidenceRevisionId:
      evidence !== null && typeof evidence["revisionId"] === "string"
        ? evidence["revisionId"]
        : null,
  };
}

export async function fetchAutomationDefinitions(
  token: string | null,
  options: AutomationInventoryQueryOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<AutomationDefinitionsRead> {
  let response: Response;
  try {
    response = await fetchImpl(automationDefinitionsUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationDefinitionsPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationDefinitionRead =
  | { readonly ok: true; readonly model: AutomationDefinitionModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationDefinition(
  token: string | null,
  definitionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationDefinitionRead> {
  if (!isSafeIdentifier(definitionId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    const source = payload as { definition?: unknown };
    return {
      ok: true,
      model: normalizeAutomationDefinition(source?.definition, "definition", {
        withEligibility: true,
      }),
    };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationMetricsRead =
  | { readonly ok: true; readonly model: AutomationMetricsModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationMetrics(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMetricsRead> {
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/automation/metrics", {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationMetrics(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface AutomationRecordsQueryOptions {
  readonly definition?: string | null;
  readonly trigger?: string | null;
  readonly status?: string | null;
  readonly from?: string | null;
  readonly to?: string | null;
  readonly limit?: number;
  readonly cursor?: string | null;
  /**
   * The paging direction of the submitted cursor.
   *
   * The backend refuses a cursor whose direction does not match, so the client
   * must carry it: a "previous" turn that submitted only the cursor was
   * rejected, and backwards paging through the real UI never worked.
   */
  readonly direction?: "next" | "previous" | null;
}

export function automationRecordsUrl(
  options: AutomationRecordsQueryOptions = {},
): string {
  const params = new URLSearchParams();
  if (options.definition) params.set("definition", options.definition);
  if (options.trigger) params.set("trigger", options.trigger);
  if (options.status) params.set("status", options.status);
  if (options.from) params.set("from", options.from);
  if (options.to) params.set("to", options.to);
  if (options.direction) params.set("direction", options.direction);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor) params.set("cursor", options.cursor);
  const qs = params.toString();
  return `/api/v1/operations/automation/records${qs ? `?${qs}` : ""}`;
}

export type AutomationRecordsRead =
  | { readonly ok: true; readonly model: AutomationRecordsPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationRecords(
  token: string | null,
  options: AutomationRecordsQueryOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<AutomationRecordsRead> {
  let response: Response;
  try {
    response = await fetchImpl(automationRecordsUrl(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationRecordsPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationDraftRead =
  | { readonly ok: true; readonly model: AutomationDraftDocumentModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationDefinitionDraft(
  token: string | null,
  definitionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationDraftRead> {
  if (!isSafeIdentifier(definitionId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}/draft`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationDraftDocument(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationPreviewRead =
  | { readonly ok: true; readonly model: AutomationPreviewModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationPreview(
  token: string | null,
  definitionId: string,
  previewId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationPreviewRead> {
  if (!isSafeIdentifier(definitionId) || !isSafeIdentifier(previewId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}/previews/${encodeURIComponent(previewId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationPreview(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationPreviewItemsRead =
  | { readonly ok: true; readonly model: AutomationPreviewItemsPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationPreviewItems(
  token: string | null,
  definitionId: string,
  previewId: string,
  options: { readonly limit?: number; readonly after?: number | null } = {},
  fetchImpl: FetchLike = fetch,
): Promise<AutomationPreviewItemsRead> {
  if (!isSafeIdentifier(definitionId) || !isSafeIdentifier(previewId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 100));
  if (options.after !== null && options.after !== undefined) {
    params.set("after", String(options.after));
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}/previews/${encodeURIComponent(previewId)}/items?${params.toString()}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationPreviewItemsPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type AutomationOccurrencesRead =
  | { readonly ok: true; readonly model: AutomationOccurrencesPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchAutomationOccurrences(
  token: string | null,
  definitionId: string,
  options: {
    readonly limit?: number;
    readonly cursor?: string | null;
    readonly direction?: "previous" | "next";
  } = {},
  fetchImpl: FetchLike = fetch,
): Promise<AutomationOccurrencesRead> {
  if (!isSafeIdentifier(definitionId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 20));
  const cursor = options.cursor ?? null;
  if (cursor !== null) {
    if (options.direction === "previous") {
      params.set("before", cursor);
    } else {
      params.set("after", cursor);
    }
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/automation/task-definitions/${encodeURIComponent(definitionId)}/occurrences?${params.toString()}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeAutomationOccurrencesPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface CreateAutomationSuccessorDraftOptions {
  readonly activeRevisionId: string;
}

export async function createAutomationSuccessorDraft(
  token: string | null,
  options: CreateAutomationSuccessorDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly revisionId: string }>> {
  if (!isSafeIdentifier(options.activeRevisionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.activeRevisionId)}/successor`,
    { expectedActiveRevisionId: options.activeRevisionId },
    (payload) => {
      const source = readRecord(payload, "successor_draft");
      return { revisionId: String(source["revisionId"] ?? "") };
    },
    fetchImpl,
  );
}

export interface CreateAutomationDefinitionOptions {
  readonly revisionId: string;
  readonly expectedVersion: number;
  readonly object: Record<string, unknown>;
}

export async function createAutomationDefinition(
  token: string | null,
  options: CreateAutomationDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly id: string | null }>> {
  if (!isSafeIdentifier(options.revisionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    "/api/v1/automation/task-definitions",
    {
      revisionId: options.revisionId,
      expectedVersion: options.expectedVersion,
      object: options.object,
    },
    (payload) => {
      const source = readRecord(payload, "automation_definition_mutation");
      const value = source["automationTaskDefinition"];
      const id =
        value !== null && typeof value === "object" && !Array.isArray(value)
          ? (value as Record<string, unknown>)["id"]
          : null;
      return { id: typeof id === "string" ? id : null };
    },
    fetchImpl,
  );
}

export interface SaveAutomationDefinitionDraftOptions {
  readonly revisionId: string;
  readonly definitionId: string;
  readonly expectedVersion: number;
  readonly object: Record<string, unknown>;
}

export async function saveAutomationDefinitionDraft(
  token: string | null,
  options: SaveAutomationDefinitionDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly version: number }>> {
  if (
    !isSafeIdentifier(options.revisionId) ||
    !isSafeIdentifier(options.definitionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "PUT",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/automationTaskDefinitions/${encodeURIComponent(options.definitionId)}`,
    { object: options.object, expectedVersion: options.expectedVersion },
    (payload) => {
      const source = readRecord(payload, "automation_definition_mutation");
      const version = source["version"];
      return { version: typeof version === "number" ? version : 0 };
    },
    fetchImpl,
  );
}

export interface CopyAutomationDefinitionOptions {
  readonly definitionId: string;
  readonly revisionId: string;
  readonly expectedVersion: number;
  readonly newName?: string | null;
}

export async function copyAutomationDefinition(
  token: string | null,
  options: CopyAutomationDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly id: string | null }>> {
  if (
    !isSafeIdentifier(options.definitionId) ||
    !isSafeIdentifier(options.revisionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {
    revisionId: options.revisionId,
    expectedVersion: options.expectedVersion,
  };
  if (options.newName) {
    body.newName = options.newName;
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/automation/task-definitions/${encodeURIComponent(options.definitionId)}/copy`,
    body,
    (payload) => {
      const source = readRecord(payload, "automation_definition_mutation");
      const value = source["automationTaskDefinition"];
      const id =
        value !== null && typeof value === "object" && !Array.isArray(value)
          ? (value as Record<string, unknown>)["id"]
          : null;
      return { id: typeof id === "string" ? id : null };
    },
    fetchImpl,
  );
}

export interface ValidateAutomationDraftOptions {
  readonly revisionId: string;
}

export async function validateAutomationDraft(
  token: string | null,
  options: ValidateAutomationDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<
  AutomationMutationResult<{ readonly validationErrors: readonly string[] }>
> {
  if (!isSafeIdentifier(options.revisionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/validate`,
    {},
    (payload) => {
      const source = readRecord(payload, "automation_draft_validation");
      const errors = source["validationErrors"];
      const list = Array.isArray(errors)
        ? errors.filter((item): item is string => typeof item === "string")
        : [];
      return { validationErrors: list };
    },
    fetchImpl,
  );
}

export interface ActivateAutomationDraftOptions {
  readonly definitionId: string;
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
}

export async function activateAutomationDraft(
  token: string | null,
  options: ActivateAutomationDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationActivationModel>> {
  if (
    !isSafeIdentifier(options.definitionId) ||
    !isSafeIdentifier(options.expectedRevisionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/operations/automation/task-definitions/${encodeURIComponent(options.definitionId)}/activate-draft`,
    {
      expectedRevisionId: options.expectedRevisionId,
      expectedVersion: options.expectedVersion,
    },
    normalizeAutomationActivation,
    fetchImpl,
  );
}

export interface CreateAutomationPreviewOptions {
  readonly definitionId: string;
}

export async function createAutomationPreview(
  token: string | null,
  options: CreateAutomationPreviewOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly previewId: string }>> {
  if (!isSafeIdentifier(options.definitionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/automation/task-definitions/${encodeURIComponent(options.definitionId)}/preview`,
    {},
    (payload) => {
      const source = readRecord(payload, "automation_preview_created");
      return { previewId: String(source["previewId"] ?? "") };
    },
    fetchImpl,
  );
}

export interface GrantAutomationAuthorityOptions {
  /** The exact published revision whose definition bounds this authority. */
  readonly definitionId: string;
  readonly revisionId?: string | null;
  readonly expectedVersion?: number | null;
  readonly reason?: string | null;
}

export async function grantAutomationAuthority(
  token: string | null,
  options: GrantAutomationAuthorityOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationGrantStateModel>> {
  if (!isSafeIdentifier(options.definitionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const body: Record<string, unknown> = { confirmation: true };
  if (options.revisionId !== null && options.revisionId !== undefined) {
    body.revisionId = options.revisionId;
  }
  if (
    options.expectedVersion !== null &&
    options.expectedVersion !== undefined
  ) {
    body.expectedVersion = options.expectedVersion;
  }
  if (options.reason) {
    body.reason = options.reason;
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/automation/task-definitions/${encodeURIComponent(options.definitionId)}/grant`,
    body,
    (value) =>
      normalizeAutomationGrantState(
        readRecord(value, "grant_result")["grant"],
        "grant",
      ),
    fetchImpl,
  );
}

export interface RevokeAutomationAuthorityOptions {
  readonly definitionId: string;
  readonly reason?: string | null;
}

export async function revokeAutomationAuthority(
  token: string | null,
  options: RevokeAutomationAuthorityOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationGrantStateModel>> {
  if (!isSafeIdentifier(options.definitionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const body: Record<string, unknown> = {};
  if (options.reason) {
    body.reason = options.reason;
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/automation/task-definitions/${encodeURIComponent(options.definitionId)}/revoke`,
    body,
    (value) =>
      normalizeAutomationGrantState(
        readRecord(value, "revoke_result")["grant"],
        "grant",
      ),
    fetchImpl,
  );
}

// ---------------------------------------------------------------------------
// V2 Notification journey (Webhook definitions, signed tests, deliveries).
//
// The definition reads use the bounded operations projections; definition
// mutations reuse the existing managed configuration object routes whose
// optimistic versions remain authoritative; delivery list/recovery reuse the
// existing notification routes whose exact status/update fences remain
// authoritative. Nothing here submits or accepts a revision digest, a secret
// value or a delivery body.

export type NotificationDefinitionsRead =
  | { readonly ok: true; readonly model: NotificationDefinitionsPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDefinitions(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDefinitionsRead> {
  let response: Response;
  try {
    response = await fetchImpl("/api/v1/operations/notifications/webhooks", {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeNotificationDefinitionsPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type NotificationDefinitionRead =
  | { readonly ok: true; readonly model: WebhookDefinitionModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDefinition(
  token: string | null,
  webhookId: string,
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDefinitionRead> {
  if (!isSafeIdentifier(webhookId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/notifications/webhooks/${encodeURIComponent(webhookId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    const source = payload as { webhook?: unknown };
    return {
      ok: true,
      model: normalizeWebhookDefinition(source?.webhook, "webhook"),
    };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type NotificationDraftRead =
  | { readonly ok: true; readonly model: NotificationDraftDocumentModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDefinitionDraft(
  token: string | null,
  webhookId: string,
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDraftRead> {
  if (!isSafeIdentifier(webhookId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/notifications/webhooks/${encodeURIComponent(webhookId)}/draft`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeNotificationDraftDocument(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface NotificationDeliveriesQuery {
  readonly status?: string | null;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export type NotificationDeliveriesRead =
  | { readonly ok: true; readonly model: NotificationDeliveriesPage }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDeliveries(
  token: string | null,
  options: NotificationDeliveriesQuery = {},
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDeliveriesRead> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 20));
  if (options.status !== null && options.status !== undefined) {
    params.set("status", options.status);
  }
  if (options.cursor !== null && options.cursor !== undefined) {
    params.set("cursor", options.cursor);
  }
  let response: Response;
  try {
    response = await fetchImpl(`/api/v1/notifications?${params.toString()}`, {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeNotificationDeliveriesPage(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export type NotificationDeliveryDetailRead =
  | { readonly ok: true; readonly model: NotificationDeliveryDetailModel }
  | { readonly ok: false; readonly failure: OperationsFailure };

export async function fetchNotificationDeliveryDetail(
  token: string | null,
  deliveryId: string,
  fetchImpl: FetchLike = fetch,
): Promise<NotificationDeliveryDetailRead> {
  if (!isSafeIdentifier(deliveryId)) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `/api/v1/operations/notifications/deliveries/${encodeURIComponent(deliveryId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  if (response.status === 401) {
    throw new OperationsApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new OperationsApiError("forbidden");
  }
  if (response.status === 404) {
    return { ok: false, failure: operationsFailure("not_found") };
  }
  if (!response.ok) {
    return { ok: false, failure: operationsFailure("unavailable") };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new OperationsApiError("malformed");
  }
  try {
    return { ok: true, model: normalizeNotificationDeliveryDetail(payload) };
  } catch {
    throw new OperationsApiError("malformed");
  }
}

export interface CreateWebhookDefinitionOptions {
  readonly revisionId: string;
  readonly expectedVersion: number;
  readonly object: Record<string, unknown>;
}

export async function createWebhookDefinition(
  token: string | null,
  options: CreateWebhookDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookDefinitionMutationModel>> {
  const created = options.object["id"];
  if (
    !isSafeIdentifier(options.revisionId) ||
    typeof created !== "string" ||
    !NOTIFICATION_URI_SAFE_SEGMENT.test(created)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/webhooks`,
    { object: options.object, expectedVersion: options.expectedVersion },
    (payload) =>
      normalizeWebhookDefinitionMutation(payload, {
        revisionId: options.revisionId,
        expectedVersion: options.expectedVersion,
        documentField: "webhook",
        expectedId: created,
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: null,
      }),
    fetchImpl,
  );
}

export interface SaveWebhookDefinitionDraftOptions {
  readonly revisionId: string;
  readonly webhookId: string;
  readonly expectedVersion: number;
  readonly object: Record<string, unknown>;
}

export async function saveWebhookDefinitionDraft(
  token: string | null,
  options: SaveWebhookDefinitionDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookDefinitionMutationModel>> {
  if (
    !isSafeIdentifier(options.revisionId) ||
    !isSafeIdentifier(options.webhookId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "PUT",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/webhooks/${encodeURIComponent(options.webhookId)}`,
    { object: options.object, expectedVersion: options.expectedVersion },
    (payload) =>
      normalizeWebhookDefinitionMutation(payload, {
        revisionId: options.revisionId,
        expectedVersion: options.expectedVersion,
        documentField: "webhook",
        expectedId: options.webhookId,
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: null,
      }),
    fetchImpl,
  );
}

export interface CopyWebhookDefinitionOptions {
  readonly revisionId: string;
  readonly webhookId: string;
  readonly expectedVersion: number;
  readonly newId?: string;
}

/**
 * Pin the copy identity before submission so the response can be bound to
 * this exact mutation. This mirrors the managed configuration allocator:
 * "{source}-copy", truncated to leave room for the suffix when necessary.
 */
export function webhookCopyId(webhookId: string): string {
  const base = `${webhookId}-copy`;
  return base.length > 64 ? `${webhookId.slice(0, 58)}-copy` : base;
}

export async function copyWebhookDefinition(
  token: string | null,
  options: CopyWebhookDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookDefinitionMutationModel>> {
  if (
    !isSafeIdentifier(options.revisionId) ||
    !isSafeIdentifier(options.webhookId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  if (options.newId !== undefined && !isSafeIdentifier(options.newId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  const requestedNewId = options.newId ?? webhookCopyId(options.webhookId);
  const body: Record<string, unknown> = {
    expectedVersion: options.expectedVersion,
    newId: requestedNewId,
  };
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/webhooks/${encodeURIComponent(options.webhookId)}/copy`,
    body,
    (payload) =>
      normalizeWebhookDefinitionMutation(payload, {
        revisionId: options.revisionId,
        expectedVersion: options.expectedVersion,
        documentField: "object",
        expectedId: null,
        copySourceId: options.webhookId,
        copyNewId: requestedNewId,
        // The managed copy stores a new, disabled Draft definition.
        expectedEnabled: false,
      }),
    fetchImpl,
  );
}

export interface SetWebhookDefinitionEnabledOptions {
  readonly revisionId: string;
  readonly webhookId: string;
  readonly expectedVersion: number;
  readonly enabled: boolean;
}

export async function setWebhookDefinitionEnabled(
  token: string | null,
  options: SetWebhookDefinitionEnabledOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookDefinitionMutationModel>> {
  if (
    !isSafeIdentifier(options.revisionId) ||
    !isSafeIdentifier(options.webhookId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.revisionId)}/objects/webhooks/${encodeURIComponent(options.webhookId)}/${options.enabled ? "enable" : "disable"}`,
    { expectedVersion: options.expectedVersion },
    (payload) =>
      normalizeWebhookDefinitionMutation(payload, {
        revisionId: options.revisionId,
        expectedVersion: options.expectedVersion,
        documentField: "object",
        expectedId: options.webhookId,
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: options.enabled,
      }),
    fetchImpl,
  );
}

export interface TestWebhookDefinitionOptions {
  readonly webhookId: string;
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
}

export async function testWebhookDefinition(
  token: string | null,
  options: TestWebhookDefinitionOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<WebhookTestResultModel>> {
  if (
    !isSafeIdentifier(options.webhookId) ||
    !isSafeIdentifier(options.expectedRevisionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/operations/notifications/webhooks/${encodeURIComponent(options.webhookId)}/test`,
    {
      expectedRevisionId: options.expectedRevisionId,
      expectedVersion: options.expectedVersion,
    },
    (payload) =>
      normalizeWebhookTestResult(payload, {
        webhookId: options.webhookId,
        revisionId: options.expectedRevisionId,
        version: options.expectedVersion,
      }),
    fetchImpl,
  );
}

export interface ActivateWebhookDraftOptions {
  readonly webhookId: string;
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
}

export async function activateWebhookDraft(
  token: string | null,
  options: ActivateWebhookDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<NotificationActivationModel>> {
  if (
    !isSafeIdentifier(options.webhookId) ||
    !isSafeIdentifier(options.expectedRevisionId)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/operations/notifications/webhooks/${encodeURIComponent(options.webhookId)}/activate-draft`,
    {
      expectedRevisionId: options.expectedRevisionId,
      expectedVersion: options.expectedVersion,
    },
    (payload) =>
      normalizeNotificationActivation(payload, {
        webhookId: options.webhookId,
        revisionId: options.expectedRevisionId,
        version: options.expectedVersion,
      }),
    fetchImpl,
  );
}

export interface RecoverDeliveryOptions {
  readonly deliveryId: string;
  readonly expectedStatus: string;
  readonly expectedUpdatedAt: string;
}

export async function requeueDeadLetterDelivery(
  token: string | null,
  options: RecoverDeliveryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<NotificationRecoveryResultModel>> {
  if (!isSafeIdentifier(options.deliveryId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/notifications/${encodeURIComponent(options.deliveryId)}/requeue`,
    {
      expectedStatus: options.expectedStatus,
      expectedUpdatedAt: options.expectedUpdatedAt,
    },
    (payload) =>
      normalizeNotificationRecoveryResult(payload, {
        deliveryId: options.deliveryId,
        action: "requeue-dead-letter",
        previousStatus: "dead-letter",
      }),
    fetchImpl,
  );
}

export async function resolveStaleDelivery(
  token: string | null,
  options: RecoverDeliveryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<NotificationRecoveryResultModel>> {
  if (!isSafeIdentifier(options.deliveryId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/notifications/${encodeURIComponent(options.deliveryId)}/resolve-stale`,
    {
      expectedStatus: options.expectedStatus,
      expectedUpdatedAt: options.expectedUpdatedAt,
    },
    (payload) =>
      normalizeNotificationRecoveryResult(payload, {
        deliveryId: options.deliveryId,
        action: "resolve-stale",
        previousStatus: "delivering",
      }),
    fetchImpl,
  );
}

export interface CreateNotificationSuccessorDraftOptions {
  readonly activeRevisionId: string;
}

export async function createNotificationSuccessorDraft(
  token: string | null,
  options: CreateNotificationSuccessorDraftOptions,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<{ readonly revisionId: string }>> {
  if (!isSafeIdentifier(options.activeRevisionId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `/api/v1/configuration/revisions/${encodeURIComponent(options.activeRevisionId)}/successor`,
    { expectedActiveRevisionId: options.activeRevisionId },
    (payload) => {
      const source = readRecord(payload, "notification_successor_draft");
      return { revisionId: String(source["revisionId"] ?? "") };
    },
    fetchImpl,
  );
}

// ---------------------------------------------------------------------------
// V2 Storage management journey (Slice 39, Task 39.1).
//
// The reads use the bounded exact-Active operator projections under
// /api/v1/operations/storage-management/; the explicit Connection/Read check
// reuses the existing zero-mutation Storage check service bound to the exact
// Active revision the operator inspected. Nothing here submits or accepts a
// revision digest, a secret value or a write probe.

import {
  normalizeStorageCheckResult,
  normalizeStorageDetail,
  normalizeStorageInventory,
  type StorageCheckResultModel,
  type StorageDetailModel,
  type StorageFamily,
  type StorageInventoryModel,
} from "../../entities/storage/storage-management";

const STORAGE_API_ERROR_MESSAGES: Readonly<
  Record<ApiReadErrorCategory, string>
> = {
  unauthorized:
    "The API token is missing, invalid or expired. Enter a valid API principal token to continue.",
  forbidden:
    "The connected API principal does not have permission to view Storage management.",
  unavailable:
    "The MediaFlow API is currently unavailable. Check that the application is running, then refresh.",
  rejected:
    "The Storage management request was rejected by the API as invalid.",
  malformed:
    "The Storage management response could not be understood as the expected read-only contract.",
};

/** Typed boundary error for the Storage management reads. */
export class StorageManagementApiError extends ApiReadError {
  constructor(category: ApiReadErrorCategory) {
    super(category, STORAGE_API_ERROR_MESSAGES[category]);
    this.name = "StorageManagementApiError";
  }
}

export class RulesWorkspaceApiError extends ApiReadError {
  constructor(category: ApiReadErrorCategory) {
    super(category);
    this.name = "RulesWorkspaceApiError";
  }
}

export interface RulesInventoryQuery {
  readonly family?: RuleFamily | null;
  readonly query?: string;
  readonly enabled?: boolean | null;
}

export function rulesInventoryPath(options: RulesInventoryQuery = {}): string {
  const params = new URLSearchParams();
  if (options.family) params.set("family", options.family);
  const query = options.query?.trim() ?? "";
  if (query) params.set("q", query.slice(0, 256));
  if (typeof options.enabled === "boolean")
    params.set("enabled", String(options.enabled));
  const encoded = params.toString();
  return `/api/v1/operations/rules/inventory${encoded ? `?${encoded}` : ""}`;
}

export async function fetchRulesInventory(
  token: string | null,
  options: RulesInventoryQuery = {},
  fetchImpl: FetchLike = fetch,
): Promise<RulesWorkspaceModel> {
  let response: Response;
  try {
    response = await fetchImpl(rulesInventoryPath(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    throw new RulesWorkspaceApiError("unavailable");
  }
  if (response.status === 401) throw new RulesWorkspaceApiError("unauthorized");
  if (response.status === 403) throw new RulesWorkspaceApiError("forbidden");
  if (!response.ok)
    throw new RulesWorkspaceApiError(
      response.status >= 500 ? "unavailable" : "rejected",
    );
  try {
    return normalizeRulesWorkspace(await response.json());
  } catch {
    throw new RulesWorkspaceApiError("malformed");
  }
}

const STORAGE_BASE = "/api/v1/operations/storage-management";

/** The bounded, server-applied Storage inventory search/filter/page request. */
export interface StorageInventoryQuery {
  readonly query?: string;
  readonly family?: StorageFamily | null;
  readonly limit?: number;
  readonly after?: string | null;
}

/** Build the bounded inventory query string; unset fields are simply absent. */
function storageInventoryPath(options: StorageInventoryQuery): string {
  const params = new URLSearchParams();
  const query = options.query?.trim() ?? "";
  if (query !== "") {
    params.set("q", query.slice(0, 256));
  }
  if (options.family !== undefined && options.family !== null) {
    params.set("family", options.family);
  }
  if (options.limit !== undefined) {
    const limit = Math.max(1, Math.min(Math.trunc(options.limit), 100));
    params.set("limit", String(limit));
  }
  if (
    options.after !== undefined &&
    options.after !== null &&
    options.after !== ""
  ) {
    params.set("after", options.after);
  }
  const encoded = params.toString();
  return encoded === ""
    ? `${STORAGE_BASE}/inventory`
    : `${STORAGE_BASE}/inventory?${encoded}`;
}

/**
 * Read one bounded page of the exact-Active Storage inventory.
 *
 * Search and provider filtering are applied by the backend over the complete
 * Active object set, so a configuration with more Storage objects than one
 * page never hides a configured Storage from the operator's search.
 */
export async function fetchStorageInventory(
  token: string | null,
  options: StorageInventoryQuery = {},
  fetchImpl: FetchLike = fetch,
): Promise<StorageInventoryModel> {
  let response: Response;
  try {
    response = await fetchImpl(storageInventoryPath(options), {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    throw new StorageManagementApiError("unavailable");
  }
  if (response.status === 401) {
    throw new StorageManagementApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new StorageManagementApiError("forbidden");
  }
  if (!response.ok) {
    throw new StorageManagementApiError("unavailable");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new StorageManagementApiError("malformed");
  }
  try {
    return normalizeStorageInventory(payload);
  } catch {
    throw new StorageManagementApiError("malformed");
  }
}

export async function fetchStorageDetail(
  token: string | null,
  storageId: string,
  fetchImpl: FetchLike = fetch,
): Promise<StorageDetailModel> {
  if (!isSafeIdentifier(storageId)) {
    throw new StorageManagementApiError("rejected");
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `${STORAGE_BASE}/storage/${encodeURIComponent(storageId)}`,
      { method: "GET", headers: operationsHeaders(token) },
    );
  } catch {
    throw new StorageManagementApiError("unavailable");
  }
  if (response.status === 401) {
    throw new StorageManagementApiError("unauthorized");
  }
  if (response.status === 403) {
    throw new StorageManagementApiError("forbidden");
  }
  if (response.status === 404) {
    throw new StorageManagementApiError("rejected");
  }
  if (!response.ok) {
    throw new StorageManagementApiError("unavailable");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new StorageManagementApiError("malformed");
  }
  try {
    return normalizeStorageDetail(payload);
  } catch {
    throw new StorageManagementApiError("malformed");
  }
}

export interface StorageCheckRunOptions {
  readonly storageId: string;
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
}

/**
 * Explicitly runs one bounded zero-mutation Connection/Read check against the
 * exact Active revision the operator inspected. The body carries only the
 * advertised revision identity and optimistic version; no digest, secret or
 * write probe travels from or to the browser.
 */
export async function fetchStorageCheckRun(
  token: string | null,
  options: StorageCheckRunOptions,
  fetchImpl: FetchLike = fetch,
): Promise<
  | {
      readonly ok: true;
      readonly status: number;
      readonly model: StorageCheckResultModel;
    }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
    }
> {
  if (
    !isSafeIdentifier(options.storageId) ||
    !isSafeIdentifier(options.expectedRevisionId) ||
    !Number.isSafeInteger(options.expectedVersion) ||
    options.expectedVersion < 0
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `${STORAGE_BASE}/storage/${encodeURIComponent(options.storageId)}/check`,
      {
        method: "POST",
        headers: operationsMutationHeaders(token),
        body: JSON.stringify({
          expectedRevisionId: options.expectedRevisionId,
          expectedVersion: options.expectedVersion,
        }),
      },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return {
      ok: true,
      status: response.status,
      model: normalizeStorageCheckResult(payload),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

// ---------------------------------------------------------------------------
// V2 Storage Add/Edit command (Slice 39, Task 39.2).
//
// The typed Storage form reads one exact-Active edit projection and publishes
// one page-local Save through the same checked successor boundary the Python
// application proves in tests/test_storage_page_local_save.py. The browser
// never receives or submits a secret value; provider credentials travel only
// as approved deployment-owned environment-variable names, and an optimistic
// Active identity is carried solely as backend-managed concurrency evidence.

import {
  STORAGE_ID,
  normalizeStorageEditProjection,
  normalizeStorageSave,
  type StorageFormModel,
  type StorageProviderType,
  type StorageSaveCandidate,
  type StorageSaveModel,
} from "../../entities/storage/storage-form";

const STORAGE_COMMAND_BASE = "/api/v1/storages";

function storageOptionFields(
  options: StorageSaveCandidate["options"],
): boolean {
  return (
    typeof options === "object" && options !== null && !Array.isArray(options)
  );
}

function validateStorageCandidate(
  candidate: StorageSaveCandidate,
  editing: boolean,
): boolean {
  return (
    // On Add the ID must satisfy the backend identifier rule; on Edit it is
    // the already-validated immutable identity.
    (editing || STORAGE_ID.test(candidate.storageId)) &&
    candidate.name.trim().length > 0 &&
    candidate.name.length <= 120 &&
    candidate.rootPath.length <= 4096 &&
    typeof candidate.readOnly === "boolean" &&
    typeof candidate.enabled === "boolean" &&
    storageOptionFields(candidate.options)
  );
}

/** Read the edit-safe typed projection of one exact Active Storage. */
export async function fetchStorageEdit(
  token: string | null,
  storageId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<StorageFormModel>> {
  if (!isSafeIdentifier(storageId)) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `${STORAGE_COMMAND_BASE}/${encodeURIComponent(storageId)}/edit`,
      { method: "GET", headers: directFilesReadHeaders(token) },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    return {
      ok: false,
      status: response.status,
      code:
        typeof envelope.code === "string" && envelope.code.length > 0
          ? envelope.code
          : "request_rejected",
      ...failureDetailsSpread(envelope.details),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return {
      ok: true,
      status: response.status,
      model: normalizeStorageEditProjection(payload),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export interface StorageSaveAuthority {
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
  readonly expectedDigest: string;
}

/** Capture the exact Active for Add or explicit Save-outcome verification. */
export async function fetchStorageAuthority(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<StorageSaveAuthority>> {
  let response: Response;
  try {
    response = await fetchImpl(STORAGE_COMMAND_BASE, {
      method: "GET",
      headers: directFilesReadHeaders(token),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      code: "configuration_unavailable",
    };
  }
  try {
    const payload = await response.json();
    const active = payload.active;
    if (
      payload.sideEffects !== "none" ||
      active.status !== "active" ||
      !isSafeIdentifier(active.revisionId) ||
      !isSafeIdentifier(active.digest) ||
      !Number.isSafeInteger(active.revisionSequence) ||
      active.revisionSequence < 1
    ) {
      throw new Error("invalid Active identity");
    }
    return {
      ok: true,
      status: response.status,
      model: {
        expectedRevisionId: active.revisionId,
        expectedVersion: active.revisionSequence,
        expectedDigest: active.digest,
      },
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/** Publish one new Storage through the checked successor boundary. */
export async function saveStorage(
  token: string | null,
  candidate: StorageSaveCandidate,
  expected: StorageSaveAuthority,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<StorageSaveModel>> {
  if (
    !validateStorageCandidate(candidate, false) ||
    !isSafeIdentifier(expected.expectedRevisionId) ||
    !isSafeIdentifier(expected.expectedDigest) ||
    !Number.isSafeInteger(expected.expectedVersion) ||
    expected.expectedVersion < 1
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    STORAGE_COMMAND_BASE,
    {
      storageId: candidate.storageId,
      name: candidate.name,
      type: candidate.type as StorageProviderType,
      rootPath: candidate.rootPath,
      readOnly: candidate.readOnly,
      enabled: candidate.enabled,
      options: candidate.options,
      ...expected,
    },
    normalizeStorageSave,
    fetchImpl,
  );
}

/** Edit one existing Storage; the ID is immutable and the Active identity fences. */
export async function editStorage(
  token: string | null,
  candidate: StorageSaveCandidate,
  expected: {
    readonly expectedRevisionId: string;
    readonly expectedVersion: number;
    readonly expectedDigest: string;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<StorageSaveModel>> {
  if (
    !isSafeIdentifier(candidate.storageId) ||
    !STORAGE_ID.test(candidate.storageId) ||
    !validateStorageCandidate(candidate, true) ||
    !isSafeIdentifier(expected.expectedRevisionId) ||
    !Number.isSafeInteger(expected.expectedVersion) ||
    expected.expectedVersion < 0 ||
    !isSafeIdentifier(expected.expectedDigest)
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "PUT",
    `${STORAGE_COMMAND_BASE}/${encodeURIComponent(candidate.storageId)}`,
    {
      storageId: candidate.storageId,
      name: candidate.name,
      type: candidate.type as StorageProviderType,
      rootPath: candidate.rootPath,
      readOnly: candidate.readOnly,
      enabled: candidate.enabled,
      options: candidate.options,
      expectedRevisionId: expected.expectedRevisionId,
      expectedVersion: expected.expectedVersion,
      expectedDigest: expected.expectedDigest,
    },
    normalizeStorageSave,
    fetchImpl,
  );
}

export interface StorageLifecycleCommandOptions {
  readonly storageId: string;
  readonly authority: StorageSaveAuthority;
}

export async function copyStorage(
  token: string | null,
  options: StorageLifecycleCommandOptions & {
    readonly newStorageId: string;
    readonly name: string;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<StorageSaveModel>> {
  if (
    !isSafeIdentifier(options.storageId) ||
    !STORAGE_ID.test(options.newStorageId) ||
    options.name.trim() === ""
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `${STORAGE_COMMAND_BASE}/${encodeURIComponent(options.storageId)}/copy`,
    {
      newStorageId: options.newStorageId,
      name: options.name,
      ...options.authority,
    },
    normalizeStorageSave,
    fetchImpl,
  );
}

export async function setStorageEnabled(
  token: string | null,
  options: StorageLifecycleCommandOptions & { readonly enabled: boolean },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<StorageSaveModel>> {
  if (
    !isSafeIdentifier(options.storageId) ||
    typeof options.enabled !== "boolean"
  ) {
    return { ok: false, status: 400, code: "invalid_request" };
  }
  return submitAutomationMutation(
    token,
    "POST",
    `${STORAGE_COMMAND_BASE}/${encodeURIComponent(options.storageId)}/${options.enabled ? "enable" : "disable"}`,
    {
      enabled: options.enabled,
      ...options.authority,
    },
    normalizeStorageSave,
    fetchImpl,
  );
}

export async function removeStorage(
  token: string | null,
  options: StorageLifecycleCommandOptions,
  fetchImpl: FetchLike = fetch,
): Promise<
  AutomationMutationResult<{ readonly removed: { readonly id: string } }>
> {
  if (!isSafeIdentifier(options.storageId))
    return { ok: false, status: 400, code: "invalid_request" };
  return submitAutomationMutation(
    token,
    "DELETE",
    `${STORAGE_COMMAND_BASE}/${encodeURIComponent(options.storageId)}`,
    { ...options.authority },
    (payload) => ({
      removed: {
        id: String(
          (payload as Record<string, unknown>).removed &&
            (
              (payload as Record<string, unknown>).removed as Record<
                string,
                unknown
              >
            ).id,
        ),
      },
    }),
    fetchImpl,
  );
}

// ---------------------------------------------------------------------------
// V2 rules-workspace typed object command (Slice 41, Task 41.2).
//
// The five independently creatable rule families are published through
// /api/v1/operations/rules/*, which reuses the exact managed application
// service the V1 configuration UI, `/api/v1/configuration/*` and the CLI drive:
// one explicit Save composes the focused successor from the captured exact
// Active, validates the whole document, runs the applicable read-only checks and
// atomically activates it. The browser therefore never performs a separate
// Draft-save/validate/activate ceremony and never treats a revision token as
// operator workflow; the observed Active identity it sends is optimistic
// concurrency evidence managed by the backend, and no secret value travels in
// either direction.

import {
  authorityIdentity,
  normalizeRuleFormAuthority,
  normalizeRuleObjectProjection,
  RULE_FORM_FAMILIES,
  type ActiveAuthorityIdentity,
  type RuleFormAuthority,
  type RuleFormFamily,
  type RuleFormValue,
  type RuleObjectProjection,
} from "../../entities/rules/rules-form";

const RULES_BASE = "/api/v1/operations/rules";

export type { ActiveAuthorityIdentity } from "../../entities/rules/rules-form";

const RULE_FORM_FAMILIES_SET: ReadonlySet<string> = new Set(RULE_FORM_FAMILIES);

function isRuleFormFamily(value: string): value is RuleFormFamily {
  return RULE_FORM_FAMILIES_SET.has(value);
}

/**
 * The exact identifier contract the backend rules command authority accepts
 * (`RulesWorkspaceCommandService._SAFE_IDENTIFIER`): the same characters
 * including ``+``, ``@``, internal spaces and dots, and the same 64-character
 * boundary. The generic task/job identifier guard above stays untouched; this
 * narrower check exists only so the browser never rejects an ID the backend
 * already publishes, and it never widens any other surface.
 */
const RULES_OBJECT_ID = /^[A-Za-z0-9][A-Za-z0-9_.:@+ -]{0,63}$/;

export function isRulesObjectId(value: string): boolean {
  return RULES_OBJECT_ID.test(value);
}

/**
 * The bounded, secret-free recovery projection of one rules command failure.
 * Only stable state fields cross this boundary; raw server prose is discarded
 * and the page presents its own fixed copy plus these safe fields.
 */
export interface RulesFailureDetails {
  readonly objectKind?: string;
  readonly objectId?: string;
  readonly stage?: string;
  readonly durableState?: string;
  readonly candidateState?: string;
  readonly sideEffects?: string;
  readonly retrySafe?: boolean;
  readonly nextAction?: string;
  readonly currentRevisionId?: string;
  readonly referenceItems?: readonly {
    readonly section: string;
    readonly id: string;
    readonly label: string;
  }[];
}

function bounded(value: unknown, maximum: number): string | undefined {
  return typeof value === "string" &&
    value.length > 0 &&
    value.length <= maximum
    ? value
    : undefined;
}

function normalizeRulesFailureDetails(
  value: unknown,
): RulesFailureDetails | undefined {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  const record = value as Record<string, unknown>;
  const details: RulesFailureDetails = {
    ...(bounded(record.objectKind, 64) !== undefined
      ? { objectKind: bounded(record.objectKind, 64) }
      : {}),
    ...(bounded(record.objectId, 128) !== undefined
      ? { objectId: bounded(record.objectId, 128) }
      : {}),
    ...(bounded(record.stage, 64) !== undefined
      ? { stage: bounded(record.stage, 64) }
      : {}),
    ...(bounded(record.durableState, 128) !== undefined
      ? { durableState: bounded(record.durableState, 128) }
      : {}),
    ...(bounded(record.candidateState, 128) !== undefined
      ? { candidateState: bounded(record.candidateState, 128) }
      : {}),
    ...(bounded(record.sideEffects, 256) !== undefined
      ? { sideEffects: bounded(record.sideEffects, 256) }
      : {}),
    ...(typeof record.retrySafe === "boolean"
      ? { retrySafe: record.retrySafe }
      : {}),
    ...(bounded(record.nextAction, 512) !== undefined
      ? { nextAction: bounded(record.nextAction, 512) }
      : {}),
    ...(bounded(record.currentRevisionId, 128) !== undefined
      ? { currentRevisionId: bounded(record.currentRevisionId, 128) }
      : {}),
    ...(Array.isArray(record.referenceItems)
      ? {
          referenceItems: (
            record.referenceItems as readonly Record<string, unknown>[]
          )
            .slice(0, 32)
            .map((item) => ({
              section: bounded(item.section, 128) ?? "",
              id: bounded(item.id, 128) ?? "",
              label: bounded(item.label, 128) ?? "",
            })),
        }
      : {}),
  };
  return Object.keys(details).length > 0 ? details : undefined;
}

/** A typed rules read result: bounded data, or one safe failure category. */
export type RulesRead<T> =
  | { readonly ok: true; readonly status: number; readonly model: T }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: RulesFailureDetails;
    };

async function rulesReadFailure(response: Response): Promise<RulesRead<never>> {
  const envelope = await readErrorEnvelope(response);
  const details = normalizeRulesFailureDetails(envelope.details);
  return {
    ok: false,
    status: response.status,
    code: bounded(envelope.code, 128) ?? "request_rejected",
    ...(details === undefined ? {} : { details }),
  };
}

export type RulesPreviewKind =
  "strategy" | "metadata" | "naming" | "classification" | "organize";

export interface RulesPreviewModel {
  readonly revisionId: string;
  readonly revisionVersion: number;
  readonly revisionDigest: string;
  readonly status: string;
  readonly stale: boolean;
  readonly result: Readonly<Record<string, unknown>> | null;
  readonly message: string | null;
  readonly nextAction: string | null;
  readonly failureCategory: string | null;
}

function normalizeRulesPreview(value: unknown): RulesPreviewModel {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    throw new Error("invalid rules preview");
  const source = value as Record<string, unknown>;
  const revisionId = bounded(source.revisionId, 128);
  const digest = bounded(source.revisionDigest, 128);
  const status = bounded(source.status, 64);
  if (
    !revisionId ||
    !digest ||
    !status ||
    typeof source.revisionVersion !== "number" ||
    !Number.isInteger(source.revisionVersion) ||
    source.revisionVersion < 1
  )
    throw new Error("invalid rules preview identity");
  const result = source.result;
  if (result !== null && (typeof result !== "object" || Array.isArray(result)))
    throw new Error("invalid rules preview result");
  return {
    revisionId,
    revisionVersion: source.revisionVersion,
    revisionDigest: digest,
    status,
    stale: source.stale === true,
    result: result as Readonly<Record<string, unknown>> | null,
    message: bounded(source.message, 512) ?? null,
    nextAction: bounded(source.nextAction, 512) ?? null,
    failureCategory: bounded(source.failureCategory, 128) ?? null,
  };
}

/** Run one explicit V2 rules preview against an exact revision identity. */
export async function runRulesPreview(
  token: string | null,
  kind: RulesPreviewKind,
  body: Readonly<Record<string, unknown>>,
  fetchImpl: FetchLike = fetch,
): Promise<RulesRead<RulesPreviewModel>> {
  let response: Response;
  try {
    response = await fetchImpl(`${RULES_BASE}/previews/${kind}`, {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) return rulesReadFailure(response);
  try {
    return {
      ok: true,
      status: response.status,
      model: normalizeRulesPreview(await response.json()),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

export type RulesAnalysisOutcome =
  | "valid"
  | "matched"
  | "not_matched"
  | "not_applicable"
  | "invalid_input"
  | "failed";

export interface RulesAnalysisBlocker {
  readonly stage: string;
  readonly message: string;
}

/**
 * One object-scoped local test result, or the separately labelled complete-flow
 * analysis. `localOnly` distinguishes a single-object local test from the
 * combined complete-flow check so the UI never presents local success as
 * publication, runtime eligibility or execution authority.
 */
export interface RulesAnalysisModel {
  readonly family: string;
  readonly objectId: string | null;
  readonly outcome: RulesAnalysisOutcome;
  readonly conclusion: string;
  readonly applicability: string;
  readonly runtimeEligibility: string;
  readonly readiness: string | null;
  readonly result: Readonly<Record<string, unknown>>;
  readonly message: string | null;
  readonly nextAction: string | null;
  readonly failureCategory: string | null;
  readonly revisionId: string;
  readonly revisionVersion: number;
  readonly revisionDigest: string;
  readonly testedAt: string;
  readonly stale: boolean;
  readonly localOnly: boolean;
  readonly candidateState: string;
  readonly providerCalls: number;
  readonly storageReads: number;
  readonly identityStatus: string | null;
  readonly syntheticIdentity: boolean;
  readonly blockers: readonly RulesAnalysisBlocker[];
  readonly executionAuthorityGranted: string | null;
}

const RULES_ANALYSIS_OUTCOMES: readonly RulesAnalysisOutcome[] = [
  "valid",
  "matched",
  "not_matched",
  "not_applicable",
  "invalid_input",
  "failed",
];

function normalizeRulesAnalysis(value: unknown): RulesAnalysisModel {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    throw new Error("invalid rules analysis");
  const source = value as Record<string, unknown>;
  const family = bounded(source.family, 64);
  const conclusion = bounded(source.conclusion, 512);
  const outcome = bounded(source.outcome, 32);
  const revisionId = bounded(source.revisionId, 128);
  const revisionDigest = bounded(source.revisionDigest, 128);
  if (
    !family ||
    !conclusion ||
    !outcome ||
    !RULES_ANALYSIS_OUTCOMES.includes(outcome as RulesAnalysisOutcome) ||
    !revisionId ||
    !revisionDigest ||
    typeof source.revisionVersion !== "number" ||
    !Number.isInteger(source.revisionVersion) ||
    source.revisionVersion < 1
  )
    throw new Error("invalid rules analysis identity");
  const result = source.result;
  if (result === null || typeof result !== "object" || Array.isArray(result))
    throw new Error("invalid rules analysis result");
  const blockers = Array.isArray(source.blockers)
    ? source.blockers.flatMap((item) => {
        if (item === null || typeof item !== "object" || Array.isArray(item))
          return [];
        const entry = item as Record<string, unknown>;
        const stage = bounded(entry.stage, 64);
        const message = bounded(entry.message, 512);
        return stage && message ? [{ stage, message }] : [];
      })
    : [];
  return {
    family,
    objectId: bounded(source.objectId, 128) ?? null,
    outcome: outcome as RulesAnalysisOutcome,
    conclusion,
    applicability: bounded(source.applicability, 64) ?? "applicable",
    runtimeEligibility: bounded(source.runtimeEligibility, 64) ?? "separate",
    readiness: bounded(source.readiness, 64) ?? null,
    result: result as Readonly<Record<string, unknown>>,
    message: bounded(source.message, 512) ?? null,
    nextAction: bounded(source.nextAction, 512) ?? null,
    failureCategory: bounded(source.failureCategory, 128) ?? null,
    revisionId,
    revisionVersion: source.revisionVersion,
    revisionDigest,
    testedAt: bounded(source.testedAt, 64) ?? "",
    stale: source.stale === true,
    localOnly: source.localOnly === true,
    candidateState:
      bounded(source.candidateState, 64) ?? "validated_non_active",
    providerCalls:
      typeof source.providerCalls === "number" ? source.providerCalls : 0,
    storageReads:
      typeof source.storageReads === "number" ? source.storageReads : 0,
    identityStatus: bounded(source.identityStatus, 64) ?? null,
    syntheticIdentity: source.syntheticIdentity === true,
    blockers,
    executionAuthorityGranted:
      bounded(source.executionAuthorityGranted, 64) ?? null,
  };
}

/**
 * Run one explicit object-scoped local test for the exact submitted candidate.
 *
 * The caller owns the sample, the requested live-Metadata flag and the exact
 * observed Active identity; nothing is remembered or replayed automatically.
 */
export async function runRulesObjectAnalysis(
  token: string | null,
  family: string,
  body: Readonly<Record<string, unknown>>,
  fetchImpl: FetchLike = fetch,
): Promise<RulesRead<RulesAnalysisModel>> {
  let response: Response;
  try {
    response = await fetchImpl(`${RULES_BASE}/analysis/${family}`, {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) return rulesReadFailure(response);
  try {
    return {
      ok: true,
      status: response.status,
      model: normalizeRulesAnalysis(await response.json()),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/** Run the separately labelled complete-flow check against the exact Active. */
export async function runRulesCompleteFlow(
  token: string | null,
  body: Readonly<Record<string, unknown>>,
  fetchImpl: FetchLike = fetch,
): Promise<RulesRead<RulesAnalysisModel>> {
  let response: Response;
  try {
    response = await fetchImpl(`${RULES_BASE}/complete-flow`, {
      method: "POST",
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) return rulesReadFailure(response);
  try {
    return {
      ok: true,
      status: response.status,
      model: normalizeRulesAnalysis(await response.json()),
    };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

async function readRulesDocument<T>(
  url: string,
  token: string | null,
  normalize: (payload: unknown) => T,
  fetchImpl: FetchLike,
): Promise<RulesRead<T>> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "GET",
      headers: operationsHeaders(token),
    });
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) return rulesReadFailure(response);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return { ok: true, status: response.status, model: normalize(payload) };
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/** The typed form authority: real fields, enums, references and secret readiness. */
export async function fetchRuleFormAuthority(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<RulesRead<RuleFormAuthority>> {
  return readRulesDocument(
    `${RULES_BASE}/form-authority`,
    token,
    normalizeRuleFormAuthority,
    fetchImpl,
  );
}

/** One object's typed edit prefill with its real reference impact. */
export async function fetchRuleEdit(
  token: string | null,
  family: string,
  objectId: string,
  fetchImpl: FetchLike = fetch,
): Promise<RulesRead<RuleObjectProjection>> {
  if (!isRuleFormFamily(family) || !isRulesObjectId(objectId))
    return { ok: false, status: 400, code: "invalid_request" };
  return readRulesDocument(
    `${RULES_BASE}/objects/${encodeURIComponent(family)}/${encodeURIComponent(objectId)}`,
    token,
    normalizeRuleObjectProjection,
    fetchImpl,
  );
}

/** One new-ID copy candidate computed from the backend field authority. */
export async function fetchRuleCopy(
  token: string | null,
  family: string,
  objectId: string,
  fetchImpl: FetchLike = fetch,
): Promise<RulesRead<RuleObjectProjection>> {
  if (!isRuleFormFamily(family) || !isRulesObjectId(objectId))
    return { ok: false, status: 400, code: "invalid_request" };
  return readRulesDocument(
    `${RULES_BASE}/objects/${encodeURIComponent(family)}/${encodeURIComponent(objectId)}/copy`,
    token,
    normalizeRuleObjectProjection,
    fetchImpl,
  );
}

/** Actual reference impact that decides whether a removal is safe. */
export async function fetchRuleImpact(
  token: string | null,
  family: string,
  objectId: string,
  fetchImpl: FetchLike = fetch,
): Promise<RulesRead<RuleObjectProjection>> {
  if (!isRuleFormFamily(family) || !isRulesObjectId(objectId))
    return { ok: false, status: 400, code: "invalid_request" };
  return readRulesDocument(
    `${RULES_BASE}/objects/${encodeURIComponent(family)}/${encodeURIComponent(objectId)}/impact`,
    token,
    normalizeRuleObjectProjection,
    fetchImpl,
  );
}

/**
 * Re-read the current Active identity. This is the safe first step after an
 * unknown Save outcome: it proves what is durable now, before any manual retry.
 */
export async function fetchRuleActiveAuthority(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<RulesRead<ActiveAuthorityIdentity>> {
  return readRulesDocument(
    `${RULES_BASE}/form-authority`,
    token,
    (payload) => authorityIdentity(normalizeRuleFormAuthority(payload).active),
    fetchImpl,
  );
}

/** One typed rules command outcome. */
export type RulesCommandResult =
  | {
      readonly ok: true;
      readonly status: number;
      readonly model: RuleObjectProjection;
    }
  | {
      readonly ok: false;
      readonly status: number;
      readonly code: string;
      readonly details?: RulesFailureDetails;
    };

async function submitRuleCommand(
  token: string | null,
  method: "POST" | "PUT" | "DELETE",
  url: string,
  body: Record<string, unknown>,
  fetchImpl: FetchLike,
): Promise<RulesCommandResult> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method,
      headers: operationsMutationHeaders(token),
      body: JSON.stringify(body),
    });
  } catch {
    // The browser cannot tell whether the command reached the backend: this is
    // a state-verification problem, never an automatic replay.
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  if (!response.ok) {
    const envelope = await readErrorEnvelope(response);
    const details = normalizeRulesFailureDetails(envelope.details);
    return {
      ok: false,
      status: response.status,
      code: bounded(envelope.code, 128) ?? "request_rejected",
      ...(details === undefined ? {} : { details }),
    };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  try {
    return {
      ok: true,
      status: response.status,
      model: normalizeRuleObjectProjection(payload),
    };
  } catch {
    // A success body the client cannot parse is an UNKNOWN outcome: publishing
    // may have happened. Never assume failure and re-send.
    return { ok: false, status: response.status, code: "malformed_response" };
  }
}

/** One explicit `保存` for a new object: validate + activate atomically. */
export async function saveRuleObject(
  token: string | null,
  family: string,
  value: Readonly<Record<string, RuleFormValue>>,
  authority: ActiveAuthorityIdentity,
  fetchImpl: FetchLike = fetch,
): Promise<RulesCommandResult> {
  if (!isRuleFormFamily(family))
    return { ok: false, status: 400, code: "invalid_request" };
  return submitRuleCommand(
    token,
    "POST",
    `${RULES_BASE}/objects/${encodeURIComponent(family)}`,
    { object: value, ...authority },
    fetchImpl,
  );
}

/** One explicit `保存` for an existing object; its ID stays immutable. */
export async function editRuleObject(
  token: string | null,
  family: string,
  objectId: string,
  value: Readonly<Record<string, RuleFormValue>>,
  authority: ActiveAuthorityIdentity,
  fetchImpl: FetchLike = fetch,
): Promise<RulesCommandResult> {
  if (
    !isRuleFormFamily(family) ||
    !isRulesObjectId(objectId) ||
    value.id !== objectId
  )
    return { ok: false, status: 400, code: "invalid_request" };
  return submitRuleCommand(
    token,
    "PUT",
    `${RULES_BASE}/objects/${encodeURIComponent(family)}/${encodeURIComponent(objectId)}`,
    { object: value, ...authority },
    fetchImpl,
  );
}

/** List-level enable/disable: one explicit final intent, one successor. */
export async function setRuleObjectEnabled(
  token: string | null,
  family: string,
  objectId: string,
  enabled: boolean,
  authority: ActiveAuthorityIdentity,
  fetchImpl: FetchLike = fetch,
): Promise<RulesCommandResult> {
  if (
    !isRuleFormFamily(family) ||
    !isRulesObjectId(objectId) ||
    typeof enabled !== "boolean"
  )
    return { ok: false, status: 400, code: "invalid_request" };
  return submitRuleCommand(
    token,
    "POST",
    `${RULES_BASE}/objects/${encodeURIComponent(family)}/${encodeURIComponent(objectId)}/state/${enabled ? "enable" : "disable"}`,
    { enabled, ...authority },
    fetchImpl,
  );
}

/** Reference-safe removal; the backend refuses a still-referenced object. */
export async function removeRuleObject(
  token: string | null,
  family: string,
  objectId: string,
  authority: ActiveAuthorityIdentity,
  fetchImpl: FetchLike = fetch,
): Promise<RulesCommandResult> {
  if (!isRuleFormFamily(family) || !isRulesObjectId(objectId))
    return { ok: false, status: 400, code: "invalid_request" };
  return submitRuleCommand(
    token,
    "DELETE",
    `${RULES_BASE}/objects/${encodeURIComponent(family)}/${encodeURIComponent(objectId)}`,
    { ...authority },
    fetchImpl,
  );
}

// --- Focused Automation definition lifecycle -----------------------------

const AUTOMATION_DEFINITIONS_BASE = "/api/v1/operations/automation/definitions";

export interface AutomationDefinitionAuthority {
  readonly expectedRevisionId: string;
  readonly expectedVersion: number;
  readonly expectedDigest: string;
}

async function submitAutomationDefinitionCommand<T>(
  token: string | null,
  method: "POST" | "PUT" | "DELETE",
  url: string,
  body: Record<string, unknown>,
  normalize: (payload: unknown) => T,
  fetchImpl: FetchLike,
): Promise<AutomationMutationResult<T>> {
  return submitAutomationMutation(
    token,
    method,
    url,
    body,
    normalize,
    fetchImpl,
  );
}

export async function fetchAutomationFormAuthority(
  token: string | null,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationDefinitionFormAuthorityModel>> {
  return fetchAutomationDocument(
    token,
    AUTOMATION_DEFINITIONS_BASE,
    normalizeAutomationFormAuthority,
    fetchImpl,
  );
}

export async function fetchAutomationEditProjection(
  token: string | null,
  definitionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationEditProjectionModel>> {
  if (!isSafeIdentifier(definitionId))
    return { ok: false, status: 400, code: "invalid_request" };
  return fetchAutomationDocument(
    token,
    `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(definitionId)}`,
    normalizeAutomationEditProjection,
    fetchImpl,
  );
}

export async function fetchAutomationCopyCandidate(
  token: string | null,
  definitionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationCopyCandidateModel>> {
  if (!isSafeIdentifier(definitionId))
    return { ok: false, status: 400, code: "invalid_request" };
  return fetchAutomationDocument(
    token,
    `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(definitionId)}/copy-candidate`,
    normalizeAutomationCopyCandidate,
    fetchImpl,
  );
}

/**
 * Reconcile one submitted-but-unconfirmed Copy command from durable truth.
 * A transport-lost Copy response is an unknown outcome, not a rejection; this
 * read resolves whether the command actually published before any deliberate
 * resubmission is allowed.
 */
export async function fetchAutomationCopyIntent(
  token: string | null,
  definitionId: string,
  fetchImpl: FetchLike = fetch,
  query = "",
): Promise<AutomationMutationResult<AutomationCopyIntentModel>> {
  if (!isSafeIdentifier(definitionId))
    return { ok: false, status: 400, code: "invalid_request" };
  // The optional query binds the reconciliation to the exact submitted intent:
  // the observed Active identity the lost Copy command was submitted against.
  // Without it the read still resolves durable evidence, but a later
  // submission's copy is never named as this intent's result.
  return fetchAutomationDocument(
    token,
    `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(definitionId)}/copy-intent${query}`,
    normalizeAutomationCopyIntent,
    fetchImpl,
  );
}

export async function fetchAutomationRemovalImpact(
  token: string | null,
  definitionId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationRemovalImpactModel>> {
  if (!isSafeIdentifier(definitionId))
    return { ok: false, status: 400, code: "invalid_request" };
  return fetchAutomationDocument(
    token,
    `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(definitionId)}/removal-impact`,
    normalizeAutomationRemovalImpact,
    fetchImpl,
  );
}

/** Zero-mutation upcoming-run calculation; it persists nothing. */
export async function previewAutomationSchedule(
  token: string | null,
  options: {
    readonly candidate: Record<string, unknown>;
    readonly objectId: string | null;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationSchedulePreviewModel>> {
  return submitAutomationDefinitionCommand(
    token,
    "POST",
    `${AUTOMATION_DEFINITIONS_BASE}/schedule-preview`,
    { candidate: options.candidate, objectId: options.objectId },
    normalizeAutomationSchedulePreview,
    fetchImpl,
  );
}

/** One checked create Save; the backend validates and activates atomically. */
export async function createAutomationDefinitionFocused(
  token: string | null,
  options: {
    readonly object: Record<string, unknown>;
    readonly authority: AutomationDefinitionAuthority;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationPublicationModel>> {
  return submitAutomationDefinitionCommand(
    token,
    "POST",
    AUTOMATION_DEFINITIONS_BASE,
    { object: options.object, ...options.authority },
    normalizeAutomationPublication,
    fetchImpl,
  );
}

/** One checked edit Save for the definition the route opened. */
export async function saveAutomationDefinitionFocused(
  token: string | null,
  options: {
    readonly definitionId: string;
    readonly object: Record<string, unknown>;
    readonly authority: AutomationDefinitionAuthority;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationPublicationModel>> {
  if (!isSafeIdentifier(options.definitionId))
    return { ok: false, status: 400, code: "invalid_request" };
  return submitAutomationDefinitionCommand(
    token,
    "PUT",
    `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(options.definitionId)}`,
    { object: options.object, ...options.authority },
    normalizeAutomationPublication,
    fetchImpl,
  );
}

export async function copyAutomationDefinitionFocused(
  token: string | null,
  options: {
    readonly definitionId: string;
    readonly authority: AutomationDefinitionAuthority;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationPublicationModel>> {
  if (!isSafeIdentifier(options.definitionId))
    return { ok: false, status: 400, code: "invalid_request" };
  return submitAutomationDefinitionCommand(
    token,
    "POST",
    `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(options.definitionId)}/copy`,
    { ...options.authority },
    normalizeAutomationPublication,
    fetchImpl,
  );
}

export async function setAutomationDefinitionEnabledFocused(
  token: string | null,
  options: {
    readonly definitionId: string;
    readonly enabled: boolean;
    readonly authority: AutomationDefinitionAuthority;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationPublicationModel>> {
  if (
    !isSafeIdentifier(options.definitionId) ||
    typeof options.enabled !== "boolean"
  )
    return { ok: false, status: 400, code: "invalid_request" };
  return submitAutomationDefinitionCommand(
    token,
    "POST",
    `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(options.definitionId)}/${options.enabled ? "enable" : "disable"}`,
    { ...options.authority },
    normalizeAutomationPublication,
    fetchImpl,
  );
}

/** One checked removal; future unattended authority is revoked first. */
export async function removeAutomationDefinitionFocused(
  token: string | null,
  options: {
    readonly definitionId: string;
    readonly authority: AutomationDefinitionAuthority;
    readonly reason?: string | null;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationMutationResult<AutomationPublicationModel>> {
  if (!isSafeIdentifier(options.definitionId))
    return { ok: false, status: 400, code: "invalid_request" };
  const body: Record<string, unknown> = { ...options.authority };
  if (options.reason) {
    body.reason = options.reason;
  }
  return submitAutomationDefinitionCommand(
    token,
    "DELETE",
    `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(options.definitionId)}`,
    body,
    normalizeAutomationPublication,
    fetchImpl,
  );
}

// --- Definition-bound Run once --------------------------------------------

const AUTOMATION_RUN_ONCE_BASE = "/api/v1/operations/automation/run-once";

export interface AutomationRunOnceReadResult {
  readonly ok: boolean;
  readonly status: number;
  readonly code: string | null;
  readonly model?: AutomationRunOnceModel;
  readonly nextAction?: string | null;
}

function runOnceFailure(
  status: number,
  payload: unknown,
): AutomationRunOnceReadResult {
  const failure = discoveryErrorResult(status, payload);
  return {
    ok: false,
    status,
    code: failure.code,
    nextAction: failure.nextAction,
  };
}

/**
 * Admit one definition-bound Run once.
 *
 * The published definition itself supplies the ResourceLibrary and source
 * sub-scope, so no file picker and no hand-selected subset is sent. The
 * response is the prompt durable discovery identity; the bounded walk happens
 * in the resident Processing Worker. A caller-supplied `admissionRequestId`
 * lets a lost response reconcile to the actual admission instead of starting a
 * duplicate run.
 */
export async function admitAutomationRunOnce(
  token: string | null,
  options: {
    readonly definitionId: string;
    readonly admissionRequestId?: string | null;
    /**
     * The exact published definition/configuration the operator observed. The
     * backend treats these as a fence: a changed definition fingerprint or a
     * repinned Active revision refuses the stale request instead of silently
     * binding today's Active to an intent the operator never saw.
     */
    readonly expectedDefinitionFingerprint?: string | null;
    readonly expectedRevisionId?: string | null;
    readonly expectedRevisionVersion?: number | null;
    readonly expectedRevisionDigest?: string | null;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationRunOnceReadResult> {
  if (!isSafeIdentifier(options.definitionId))
    return { ok: false, status: 400, code: "invalid_request" };
  const body: Record<string, unknown> = {};
  if (options.admissionRequestId) {
    body.admissionRequestId = options.admissionRequestId;
  }
  if (options.expectedDefinitionFingerprint) {
    body.expectedDefinitionFingerprint = options.expectedDefinitionFingerprint;
  }
  if (options.expectedRevisionId) {
    body.expectedRevisionId = options.expectedRevisionId;
    body.expectedRevisionVersion = options.expectedRevisionVersion ?? 0;
    body.expectedRevisionDigest = options.expectedRevisionDigest ?? "";
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(options.definitionId)}/run-once`,
      {
        method: "POST",
        headers: { ...operationsMutationHeaders(token) },
        body: JSON.stringify(body),
      },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  if (!response.ok) return runOnceFailure(response.status, payload);
  try {
    return {
      ok: true,
      status: response.status,
      code: null,
      model: normalizeAutomationRunOnce(payload),
    };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
    };
  }
}

/** Read one durable Run once by its discovery identity. */
export async function fetchAutomationRunOnce(
  token: string | null,
  discoveryId: string,
  fetchImpl: FetchLike = fetch,
): Promise<AutomationRunOnceReadResult> {
  if (!isSafeIdentifier(discoveryId))
    return { ok: false, status: 400, code: "invalid_request" };
  let response: Response;
  try {
    response = await fetchImpl(
      `${AUTOMATION_RUN_ONCE_BASE}/${encodeURIComponent(discoveryId)}`,
      { headers: { ...operationsHeaders(token) } },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  if (!response.ok) return runOnceFailure(response.status, payload);
  try {
    return {
      ok: true,
      status: response.status,
      code: null,
      model: normalizeAutomationRunOnce(payload),
    };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
    };
  }
}

/**
 * Reconcile one lost Run-once admission response by the client's own request
 * identity.
 *
 * The request id is generated before the POST, so it proves the *actual*
 * admission however the Active pin changed while the response was in flight.
 * A proved absence is a bounded `run_once_request_not_found`, never a guessed
 * latest run.
 */
export async function reconcileAutomationRunOnce(
  token: string | null,
  options: {
    readonly definitionId: string;
    readonly admissionRequestId: string;
  },
  fetchImpl: FetchLike = fetch,
): Promise<AutomationRunOnceReadResult> {
  if (
    !isSafeIdentifier(options.definitionId) ||
    !isSafeIdentifier(options.admissionRequestId)
  )
    return { ok: false, status: 400, code: "invalid_request" };
  let response: Response;
  try {
    response = await fetchImpl(
      `${AUTOMATION_DEFINITIONS_BASE}/${encodeURIComponent(options.definitionId)}/run-once` +
        `?admissionRequestId=${encodeURIComponent(options.admissionRequestId)}`,
      { headers: { ...operationsHeaders(token) } },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  if (!response.ok) return runOnceFailure(response.status, payload);
  try {
    return {
      ok: true,
      status: response.status,
      code: null,
      model: normalizeAutomationRunOnce(payload),
    };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
    };
  }
}

/**
 * Control or freeze one durable Run once.
 *
 * Pause/cancel/resume only record a cooperative request the resident Worker
 * honours at its next safe boundary. Finalize freezes the complete bounded
 * manifest and creates its exact zero-mutation Preview; a budget/safety-limited
 * walk is refused instead of being frozen as a truncated prefix.
 */
export async function controlAutomationRunOnce(
  token: string | null,
  options: {
    readonly discoveryId: string;
    readonly action: "pause" | "cancel" | "resume" | "finalize";
    readonly expectedVersion: number;
  },
  fetchImpl: FetchLike = fetch,
): Promise<
  AutomationRunOnceReadResult & {
    readonly previewId?: string | null;
    readonly analysisId?: string | null;
  }
> {
  if (!isSafeIdentifier(options.discoveryId))
    return { ok: false, status: 400, code: "invalid_request" };
  let response: Response;
  try {
    response = await fetchImpl(
      `${AUTOMATION_RUN_ONCE_BASE}/${encodeURIComponent(options.discoveryId)}/${options.action}`,
      {
        method: "POST",
        headers: { ...operationsMutationHeaders(token) },
        body: JSON.stringify({ expectedVersion: options.expectedVersion }),
      },
    );
  } catch {
    return { ok: false, status: 0, code: "transport_unavailable" };
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return { ok: false, status: response.status, code: "malformed_response" };
  }
  if (!response.ok) return runOnceFailure(response.status, payload);
  try {
    const model = normalizeAutomationRunOnce(payload);
    const record = readRecord(payload, "runOnce");
    const previewId =
      typeof record["previewId"] === "string" ? record["previewId"] : null;
    // A finalize whose exact analysis was deferred to the resident Worker
    // returns a durable analysis identity instead of a completed Preview.
    const analysisId =
      typeof record["analysisId"] === "string" ? record["analysisId"] : null;
    return {
      ok: true,
      status: response.status,
      code: null,
      model,
      previewId,
      analysisId,
    };
  } catch {
    return {
      ok: false,
      status: response.status,
      code: "malformed_response",
    };
  }
}
