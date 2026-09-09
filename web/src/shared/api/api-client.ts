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
  type SystemStatusModel,
} from "../../entities/library/system-status";
import {
  normalizeStorageFiles,
  type StorageFilesModel,
} from "../../entities/library/storage-files";
import {
  DashboardApiError,
  StorageFilesApiError,
  SystemStatusApiError,
} from "./api-errors";

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

export type StorageFilesQueryOptions = {
  readonly storageId: string;
  readonly path?: string;
  readonly cursor?: string | null;
  readonly resourceLibrary?: string | null;
};

export function storageFilesUrl(options: StorageFilesQueryOptions): string {
  const params = new URLSearchParams();
  params.set("storageId", options.storageId);
  if (options.path !== undefined && options.path !== "") {
    params.set("path", options.path);
  }
  if (options.cursor !== undefined && options.cursor !== null) {
    params.set("cursor", options.cursor);
  }
  if (
    options.resourceLibrary !== undefined &&
    options.resourceLibrary !== null
  ) {
    params.set("resourceLibrary", options.resourceLibrary);
  }
  return `/api/v1/storage/files?${params.toString()}`;
}

export async function fetchStorageFiles(
  token: string | null,
  options: StorageFilesQueryOptions,
  fetchImpl: FetchLike = fetch,
): Promise<StorageFilesRead> {
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
