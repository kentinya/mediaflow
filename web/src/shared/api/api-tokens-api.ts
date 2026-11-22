/**
 * Scoped API token administration.
 *
 * The browser session only ever receives the plaintext token in the one issue
 * response; list reads carry stable metadata and status.  A lost mutation
 * answer is reported as unverified and the durable list is re-read, never
 * replayed automatically.
 */

export type ApiTokenScope = "read_only" | "read_and_analysis";
export type ApiTokenStatus = "active" | "expired" | "revoked";

export interface ApiTokenSummary {
  readonly tokenId: string;
  readonly name: string;
  readonly scope: ApiTokenScope;
  readonly permissions: readonly string[];
  readonly createdAt: string;
  readonly expiresAt: string;
  readonly lastUsedAt: string | null;
  readonly revokedAt: string | null;
  readonly status: ApiTokenStatus;
}

export interface IssuedApiToken extends ApiTokenSummary {
  readonly token: string;
  readonly plaintextShownOnce: true;
}

export type ApiTokensFailureCategory =
  "unauthorized" | "forbidden" | "rejected" | "unavailable" | "malformed";

export class ApiTokensApiError extends Error {
  readonly category: ApiTokensFailureCategory;
  readonly status: number | null;
  readonly code: string | null;
  readonly nextAction: string | null;
  readonly durableState: string | null;

  constructor(
    category: ApiTokensFailureCategory,
    status: number | null = null,
    details: Record<string, unknown> | null = null,
    code: string | null = null,
  ) {
    super(category);
    this.name = "ApiTokensApiError";
    this.category = category;
    this.status = status;
    this.code = code;
    this.nextAction =
      typeof details?.nextAction === "string" ? details.nextAction : null;
    this.durableState =
      typeof details?.durableState === "string" ? details.durableState : null;
  }
}

export class ApiTokensUnknownOutcomeError extends ApiTokensApiError {
  constructor() {
    super("unavailable", null, null, "unknown_outcome");
    this.name = "ApiTokensUnknownOutcomeError";
  }
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

const SCOPES: readonly ApiTokenScope[] = ["read_only", "read_and_analysis"];
const STATUSES: readonly ApiTokenStatus[] = ["active", "expired", "revoked"];

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function summaryOf(value: unknown): ApiTokenSummary {
  const item = record(value);
  if (item === null) throw new Error("API token item is malformed");
  const tokenId = item.tokenId;
  const name = item.name;
  const scope = item.scope;
  const permissions = item.permissions;
  const createdAt = item.createdAt;
  const expiresAt = item.expiresAt;
  const lastUsedAt = item.lastUsedAt;
  const revokedAt = item.revokedAt;
  const status = item.status;
  if (
    typeof tokenId !== "string" ||
    tokenId.length === 0 ||
    typeof name !== "string" ||
    name.length === 0 ||
    !SCOPES.includes(scope as ApiTokenScope) ||
    !Array.isArray(permissions) ||
    !permissions.every((value) => typeof value === "string") ||
    typeof createdAt !== "string" ||
    typeof expiresAt !== "string" ||
    !(lastUsedAt === null || typeof lastUsedAt === "string") ||
    !(revokedAt === null || typeof revokedAt === "string") ||
    !STATUSES.includes(status as ApiTokenStatus)
  ) {
    throw new Error("API token item is malformed");
  }
  return {
    tokenId,
    name,
    scope: scope as ApiTokenScope,
    permissions,
    createdAt,
    expiresAt,
    lastUsedAt,
    revokedAt,
    status: status as ApiTokenStatus,
  };
}

async function errorEnvelope(response: Response): Promise<{
  readonly code: string | null;
  readonly details: Record<string, unknown> | null;
}> {
  try {
    const body = (await response.clone().json()) as {
      error?: { code?: unknown; details?: unknown };
    };
    return {
      code: typeof body?.error?.code === "string" ? body.error.code : null,
      details: record(body?.error?.details),
    };
  } catch {
    return { code: null, details: null };
  }
}

async function request<T>(
  path: string,
  init: RequestInit,
  parse: (payload: unknown) => T,
  mutation: boolean,
  fetchImpl: FetchLike,
): Promise<T> {
  let response: Response;
  try {
    response = await fetchImpl(path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body === undefined
          ? {}
          : { "Content-Type": "application/json" }),
      },
    });
  } catch {
    if (mutation) throw new ApiTokensUnknownOutcomeError();
    throw new ApiTokensApiError("unavailable");
  }
  if (response.ok) {
    try {
      return parse(await response.json());
    } catch {
      if (mutation) throw new ApiTokensUnknownOutcomeError();
      throw new ApiTokensApiError("malformed");
    }
  }
  const { code, details } = await errorEnvelope(response);
  if (response.status === 401) throw new ApiTokensApiError("unauthorized", 401);
  if (response.status === 403) throw new ApiTokensApiError("forbidden", 403);
  throw new ApiTokensApiError(
    response.status >= 500 ? "unavailable" : "rejected",
    response.status,
    details,
    code,
  );
}

export async function fetchApiTokens(
  fetchImpl: FetchLike = fetch,
): Promise<readonly ApiTokenSummary[]> {
  return request(
    "/api/auth/tokens",
    { method: "GET" },
    (payload) => {
      const body = record(payload);
      if (!Array.isArray(body?.items))
        throw new Error("token list is malformed");
      return body.items.map(summaryOf);
    },
    false,
    fetchImpl,
  ).catch((error: unknown) => {
    if (error instanceof ApiTokensApiError) throw error;
    throw new ApiTokensApiError("malformed");
  });
}

export async function issueApiToken(
  input: {
    readonly name: string;
    readonly scope: ApiTokenScope;
    readonly expiresInDays: number;
  },
  fetchImpl: FetchLike = fetch,
): Promise<IssuedApiToken> {
  return request(
    "/api/auth/tokens",
    { method: "POST", body: JSON.stringify(input) },
    (payload) => {
      const summary = summaryOf(payload);
      const body = record(payload);
      if (
        typeof body?.token !== "string" ||
        body.token.length === 0 ||
        body.plaintextShownOnce !== true
      ) {
        throw new Error("issued API token is malformed");
      }
      return {
        ...summary,
        token: body.token,
        plaintextShownOnce: true,
      };
    },
    true,
    fetchImpl,
  );
}

export async function revokeApiToken(
  tokenId: string,
  fetchImpl: FetchLike = fetch,
): Promise<ApiTokenSummary> {
  return request(
    `/api/auth/tokens/${encodeURIComponent(tokenId)}/revoke`,
    { method: "POST", body: JSON.stringify({}) },
    summaryOf,
    true,
    fetchImpl,
  );
}
