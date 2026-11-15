import { ApiReadError, type ApiReadErrorCategory } from "./api-errors";
import type { RuleReadiness } from "../../entities/rules/rules-readiness";

export interface ConfigurationStatus {
  readonly [key: string]: unknown;
  readonly authority?: string | null;
  readonly setupRequired?: boolean;
  readonly emptyActive?: boolean;
  readonly active?: Record<string, unknown> | null;
  readonly setupDraft?: Record<string, unknown> | null;
  readonly nextAction?: string | null;
  readonly canManageConfiguration?: boolean;
  readonly canActivateConfiguration?: boolean;
  readonly commandReadiness?: Record<string, unknown>;
  /**
   * The rule-family readiness derived server-side from the exact Active
   * authority the rules workspace inventory reads. It stays `unknown` until the
   * entity normalizer accepts it, so a malformed document can never be rendered
   * as zero-count Active readiness.
   */
  readonly ruleReadiness?: unknown;
}

export type { RuleReadiness };

/**
 * Bounded failure of one configuration read or write.
 *
 * The rendered copy stays a fixed, project-authored category message; the
 * backend's own bounded `code` and structured `details` are preserved as data
 * so the Settings page can present the durable state and the explicit next
 * action without ever echoing raw exception or provider text.
 */
export class ConfigurationApiError extends ApiReadError {
  readonly status: number | null;
  readonly code: string | null;
  readonly details: Record<string, unknown> | null;
  readonly nextAction: string | null;
  readonly durableState: string | null;

  constructor(
    category: ApiReadErrorCategory,
    status: number | null = null,
    details: Record<string, unknown> | null = null,
    code: string | null = null,
  ) {
    super(category);
    this.name = "ConfigurationApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.nextAction =
      typeof details?.nextAction === "string" ? details.nextAction : null;
    this.durableState =
      typeof details?.durableState === "string" ? details.durableState : null;
  }
}

/** A known 409 rejection: the server answered and refused the change. */
export class ConfigurationConflictError extends ConfigurationApiError {
  constructor(details: Record<string, unknown>, code: string | null = null) {
    super("rejected", 409, details, code);
    this.name = "ConfigurationConflictError";
  }
}

/**
 * The write request did not produce a trustworthy answer.
 *
 * A transport abort, an unreadable success body or an unexplained server
 * failure cannot prove whether the publication committed. The outcome must be
 * verified from durable state and never replayed automatically.
 */
export class ConfigurationUnknownOutcomeError extends ConfigurationApiError {
  constructor() {
    super("unavailable", null, null, "unknown_outcome");
    this.name = "ConfigurationUnknownOutcomeError";
  }
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

const ERROR_BODY_LIMIT = 4_096;

async function boundedErrorBody(response: Response): Promise<{
  readonly code: string | null;
  readonly details: Record<string, unknown> | null;
  readonly parsed: boolean;
}> {
  try {
    const text = await response.clone().text();
    if (text.length > ERROR_BODY_LIMIT) {
      return { code: null, details: null, parsed: false };
    }
    const body = JSON.parse(text) as {
      error?: { code?: unknown; details?: unknown };
    };
    if (!body || typeof body !== "object" || !body.error) {
      return { code: null, details: null, parsed: false };
    }
    const code = typeof body.error.code === "string" ? body.error.code : null;
    const raw = body.error.details;
    const details =
      raw && typeof raw === "object" && !Array.isArray(raw)
        ? (raw as Record<string, unknown>)
        : null;
    return { code, details, parsed: true };
  } catch {
    return { code: null, details: null, parsed: false };
  }
}

async function request<T>(
  token: string | null,
  path: string,
  init: RequestInit = {},
  fetchImpl: FetchLike = fetch,
): Promise<T> {
  const method = init.method ?? "GET";
  const isMutation = method !== "GET" && method !== "HEAD";
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  if (token !== null) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetchImpl(path, { ...init, headers });
  } catch {
    // No answer at all. A mutation may still have committed, so a write must
    // verify durable state instead of claiming the change did not happen.
    if (isMutation) throw new ConfigurationUnknownOutcomeError();
    throw new ConfigurationApiError("unavailable");
  }
  if (response.status === 401) throw new ConfigurationApiError("unauthorized");
  if (response.status === 403) throw new ConfigurationApiError("forbidden");
  if (response.ok) {
    try {
      return (await response.json()) as T;
    } catch {
      // A 2xx means the server accepted the write, but the unreadable result
      // still cannot be reported as a verified success.
      if (isMutation) throw new ConfigurationUnknownOutcomeError();
      throw new ConfigurationApiError("malformed");
    }
  }
  const { code, details, parsed } = await boundedErrorBody(response);
  if (response.status === 409) {
    throw new ConfigurationConflictError(details ?? {}, code);
  }
  if (isMutation && response.status >= 500) {
    // A server error without an explicit durable-state statement may have
    // failed before or after committing; the operator must verify.
    const durable = typeof details?.durableState === "string";
    if (!parsed || !durable || code === "internal_error") {
      throw new ConfigurationUnknownOutcomeError();
    }
  }
  throw new ConfigurationApiError(
    response.status >= 500 ? "unavailable" : "rejected",
    response.status,
    details,
    code,
  );
}

export const fetchConfigurationStatus = (
  token: string | null,
  fetchImpl?: FetchLike,
) =>
  request<ConfigurationStatus>(
    token,
    "/api/v1/configuration/status",
    {},
    fetchImpl,
  );

export const createFirstDraft = (token: string | null, fetchImpl?: FetchLike) =>
  request<Record<string, unknown>>(
    token,
    "/api/v1/configuration/drafts/first",
    { method: "POST", body: "{}" },
    fetchImpl,
  );

export const fetchRevision = (
  token: string | null,
  revisionId: string,
  fetchImpl?: FetchLike,
) =>
  request<Record<string, unknown>>(
    token,
    `/api/v1/configuration/revisions/${encodeURIComponent(revisionId)}`,
    {},
    fetchImpl,
  );

export const fetchSystemSettings = (
  token: string | null,
  revisionId?: string,
  fetchImpl?: FetchLike,
) =>
  request<Record<string, unknown>>(
    token,
    `/api/v1/system/settings${revisionId ? `?revisionId=${encodeURIComponent(revisionId)}` : ""}`,
    {},
    fetchImpl,
  );

export const saveSystemSettings = (
  token: string | null,
  body: Record<string, unknown>,
  fetchImpl?: FetchLike,
) =>
  request<Record<string, unknown>>(
    token,
    "/api/v1/system/settings",
    { method: "PUT", body: JSON.stringify(body) },
    fetchImpl,
  );

export const validateRevision = (
  token: string | null,
  revisionId: string,
  fetchImpl?: FetchLike,
) =>
  request<Record<string, unknown>>(
    token,
    `/api/v1/configuration/revisions/${encodeURIComponent(revisionId)}/validate`,
    { method: "POST", body: "{}" },
    fetchImpl,
  );

export const activateRevision = (
  token: string | null,
  revisionId: string,
  expectedVersion: number,
  fetchImpl?: FetchLike,
) =>
  request<Record<string, unknown>>(
    token,
    `/api/v1/configuration/revisions/${encodeURIComponent(revisionId)}/activate`,
    {
      method: "POST",
      body: JSON.stringify({ expectedVersion, checked: true }),
    },
    fetchImpl,
  );

export const exportConfigurationPackage = (
  token: string | null,
  revisionId?: string,
  fetchImpl?: FetchLike,
) =>
  request<Record<string, unknown>>(
    token,
    `/api/v1/configuration/packages/export/configuration${revisionId ? `?revisionId=${encodeURIComponent(revisionId)}` : ""}`,
    {},
    fetchImpl,
  );

export const fetchManagementReadiness = (token: string | null) =>
  request<Record<string, unknown>>(token, "/api/v1/management/readiness", {});
