import { ApiReadError, type ApiReadErrorCategory } from "./api-errors";

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
}

export class ConfigurationApiError extends ApiReadError {
  readonly status: number | null;
  readonly details: Record<string, unknown> | null;
  constructor(
    category: ApiReadErrorCategory,
    status: number | null = null,
    details: Record<string, unknown> | null = null,
  ) {
    super(
      category,
      category === "forbidden"
        ? "当前账号没有权限管理配置。"
        : category === "unauthorized"
          ? "登录状态已失效,请重新连接。"
          : "配置状态暂时不可用,请刷新后重试。",
    );
    this.name = "ConfigurationApiError";
    this.status = status;
    this.details = details;
  }
}

export class ConfigurationConflictError extends ConfigurationApiError {
  constructor(details: Record<string, unknown>) {
    super("rejected", 409, details);
    this.name = "ConfigurationConflictError";
  }
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

async function request<T>(
  token: string | null,
  path: string,
  init: RequestInit = {},
  fetchImpl: FetchLike = fetch,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  if (token !== null) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetchImpl(path, { ...init, headers });
  } catch {
    throw new ConfigurationApiError("unavailable");
  }
  if (response.status === 401) throw new ConfigurationApiError("unauthorized");
  if (response.status === 403) throw new ConfigurationApiError("forbidden");
  if (response.status === 409) {
    let details: Record<string, unknown> = {};
    try {
      const body = (await response.clone().json()) as {
        error?: { details?: unknown };
      };
      if (
        body.error?.details &&
        typeof body.error.details === "object" &&
        !Array.isArray(body.error.details)
      ) {
        details = body.error.details as Record<string, unknown>;
      }
    } catch {
      /* bounded conflict fallback below */
    }
    throw new ConfigurationConflictError(details);
  }
  if (!response.ok)
    throw new ConfigurationApiError(
      response.status >= 500 ? "unavailable" : "rejected",
    );
  try {
    return (await response.json()) as T;
  } catch {
    throw new ConfigurationApiError("malformed");
  }
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
