/**
 * Central Explore read contract (Slice 51 / Task 51.1).
 *
 * One bounded boundary between the Explore feature and the Python API:
 * requests carry the in-memory Bearer token only, every response is strictly
 * normalized by the Explore entity, and every failure — a rejected local
 * principal or an upstream provider family — becomes one secret-free kind
 * with a fixed message. An upstream 401/403 from the provider keeps its HTTP
 * status but is classified as a provider failure, never as an unauthorized
 * principal, so the shared auth recovery never clears a valid token for an
 * upstream credential problem.
 */

import {
  normalizeExploreDetail,
  normalizeExploreOptions,
  normalizeExplorePage,
  isExploreMediaType,
  type ExploreDetailModel,
  type ExploreMediaType,
  type ExploreOptionsModel,
  type ExplorePageModel,
} from "../../entities/explore/explore";
import { ApiReadError, type ApiReadErrorCategory } from "./api-errors";
import type { FetchLike } from "./api-client";

export type ExploreFailureKind =
  | "unauthorized"
  | "forbidden"
  | "invalid"
  | "not_found"
  | "provider_auth"
  | "provider_permission"
  | "provider_rate_limited"
  | "provider_timeout"
  | "provider_unavailable"
  | "provider_malformed"
  | "provider_not_configured"
  | "network"
  | "malformed";

/** Fixed, secret-free, operator-facing copy per failure kind. */
const EXPLORE_FAILURE_MESSAGES: Readonly<Record<ExploreFailureKind, string>> = {
  unauthorized:
    "API 令牌缺失、无效或已过期。重新输入有效的 API 主令牌后可继续本次探索。",
  forbidden: "当前 API 主令牌没有读取探索的权限。",
  invalid: "本次请求的参数不被探索接口接受,请调整筛选或关键词后重试。",
  not_found: "该作品在数据源中不存在,可返回列表选择其他作品。",
  provider_auth:
    "数据源拒绝了服务配置的凭据,读取未产生任何媒体或任务效果。服务端修复凭据前请稍后重试。",
  provider_permission:
    "数据源拒绝了服务配置凭据的访问权限,读取未产生任何媒体或任务效果。",
  provider_rate_limited:
    "数据源正在限流,本次读取未产生任何媒体或任务效果。稍等片刻后可重试同一页。",
  provider_timeout:
    "数据源超时未响应,已保留当前列表,读取未产生任何媒体或任务效果。可重试同一页。",
  provider_unavailable:
    "数据源暂时不可用,已保留当前列表,读取未产生任何媒体或任务效果。稍后可重试同一页。",
  provider_malformed:
    "数据源返回了无法使用的内容,已保留当前列表。可重试同一次读取。",
  provider_not_configured:
    "此部署尚未配置探索读取所需的数据源,请按下一步提示完成后重试。",
  network: "无法连接到 MediaFlow 接口。确认服务运行后可重试本次读取。",
  malformed: "接口返回内容与探索契约不符,未据此渲染任何数据。",
};

function categoryFor(kind: ExploreFailureKind): ApiReadErrorCategory {
  switch (kind) {
    case "unauthorized":
      return "unauthorized";
    case "forbidden":
      return "forbidden";
    case "invalid":
    case "not_found":
      return "rejected";
    case "malformed":
      return "malformed";
    default:
      // Every provider family keeps the authenticated principal: only this
      // API's own `unauthorized`/`forbidden` answers may drive auth recovery.
      return "unavailable";
  }
}

export class ExploreApiError extends ApiReadError {
  readonly kind: ExploreFailureKind;
  /** The backend's own bounded next action, when it sent one. */
  readonly nextAction: string | null;

  constructor(kind: ExploreFailureKind, nextAction?: string | null) {
    super(categoryFor(kind), EXPLORE_FAILURE_MESSAGES[kind]);
    this.name = "ExploreApiError";
    this.kind = kind;
    this.nextAction = nextAction ?? null;
  }
}

interface ExploreErrorEnvelope {
  readonly code?: string;
  readonly nextAction?: string;
}

async function readExploreEnvelope(
  response: Response,
): Promise<ExploreErrorEnvelope> {
  try {
    const body = (await response.clone().json()) as {
      error?: { code?: unknown; details?: { nextAction?: unknown } };
    };
    const error = body?.error;
    const code = typeof error?.code === "string" ? error.code : undefined;
    const nextAction =
      typeof error?.details?.nextAction === "string"
        ? error.details.nextAction
        : undefined;
    return { code, nextAction };
  } catch {
    return {};
  }
}

export function exploreKindForStatus(status: number): ExploreFailureKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status >= 500) return "provider_unavailable";
  return "invalid";
}

export function exploreKindForCode(
  code: string | undefined,
  status: number,
): ExploreFailureKind {
  switch (code) {
    case "unauthorized":
      return "unauthorized";
    case "forbidden":
      return "forbidden";
    case "invalid_request":
      return "invalid";
    case "not_found":
      return "not_found";
    case "provider_authentication_failed":
      return "provider_auth";
    case "provider_permission_denied":
      return "provider_permission";
    case "provider_rate_limited":
      return "provider_rate_limited";
    case "provider_timeout":
      return "provider_timeout";
    case "provider_unavailable":
      return "provider_unavailable";
    case "provider_malformed":
      return "provider_malformed";
    case "provider_not_configured":
      return "provider_not_configured";
    default:
      return exploreKindForStatus(status);
  }
}

function exploreHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token !== null) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function exploreRead(
  url: string,
  token: string | null,
  fetchImpl: FetchLike,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetchImpl(url, {
      method: "GET",
      headers: exploreHeaders(token),
    });
  } catch {
    throw new ExploreApiError("network");
  }
  if (!response.ok) {
    const envelope = await readExploreEnvelope(response);
    throw new ExploreApiError(
      exploreKindForCode(envelope.code, response.status),
      envelope.nextAction ?? null,
    );
  }
  try {
    return await response.json();
  } catch {
    throw new ExploreApiError("malformed");
  }
}

const WORK_ID = /^[1-9][0-9]{0,9}$/;
const KEYWORD = /^[\s\S]{1,200}$/;

export interface ExploreBrowseRequest {
  readonly mediaType: ExploreMediaType;
  readonly sort?: "popular" | "rating" | "date";
  readonly genreId?: number | null;
  readonly originalLanguage?: string | null;
  readonly year?: number | null;
  readonly minRating?: number | null;
  readonly minVotes?: number | null;
  readonly page?: number;
}

/** The exact browse query string; unset filters are simply absent. */
export function exploreBrowseQuery(request: ExploreBrowseRequest): string {
  const params = new URLSearchParams();
  params.set("mediaType", request.mediaType);
  if (request.sort !== undefined) params.set("sort", request.sort);
  if (request.genreId != null) params.set("genreId", String(request.genreId));
  if (request.originalLanguage != null) {
    params.set("originalLanguage", request.originalLanguage);
  }
  if (request.year != null) params.set("year", String(request.year));
  if (request.minRating != null)
    params.set("minRating", String(request.minRating));
  if (request.minVotes != null)
    params.set("minVotes", String(request.minVotes));
  if (request.page !== undefined) params.set("page", String(request.page));
  return params.toString();
}

export async function fetchExploreBrowse(
  token: string | null,
  request: ExploreBrowseRequest,
  fetchImpl: FetchLike = fetch,
): Promise<ExplorePageModel> {
  const payload = await exploreRead(
    `/api/v1/explore/browse?${exploreBrowseQuery(request)}`,
    token,
    fetchImpl,
  );
  try {
    return normalizeExplorePage(payload);
  } catch {
    throw new ExploreApiError("malformed");
  }
}

export interface ExploreSearchRequest {
  readonly mediaType: ExploreMediaType;
  readonly query: string;
  readonly page?: number;
}

export async function fetchExploreSearch(
  token: string | null,
  request: ExploreSearchRequest,
  fetchImpl: FetchLike = fetch,
): Promise<ExplorePageModel> {
  if (!KEYWORD.test(request.query) || request.query.trim().length === 0) {
    throw new ExploreApiError("invalid");
  }
  const params = new URLSearchParams();
  params.set("mediaType", request.mediaType);
  params.set("query", request.query);
  if (request.page !== undefined) params.set("page", String(request.page));
  const payload = await exploreRead(
    `/api/v1/explore/search?${params.toString()}`,
    token,
    fetchImpl,
  );
  try {
    return normalizeExplorePage(payload);
  } catch {
    throw new ExploreApiError("malformed");
  }
}

export async function fetchExploreOptions(
  token: string | null,
  mediaType: ExploreMediaType,
  fetchImpl: FetchLike = fetch,
): Promise<ExploreOptionsModel> {
  const payload = await exploreRead(
    `/api/v1/explore/options?mediaType=${mediaType}`,
    token,
    fetchImpl,
  );
  try {
    return normalizeExploreOptions(payload);
  } catch {
    throw new ExploreApiError("malformed");
  }
}

export async function fetchExploreDetail(
  token: string | null,
  mediaType: ExploreMediaType,
  providerId: string,
  fetchImpl: FetchLike = fetch,
): Promise<ExploreDetailModel> {
  if (!isExploreMediaType(mediaType) || !WORK_ID.test(providerId)) {
    throw new ExploreApiError("invalid");
  }
  const payload = await exploreRead(
    `/api/v1/explore/${mediaType}/${providerId}`,
    token,
    fetchImpl,
  );
  try {
    return normalizeExploreDetail(payload);
  } catch {
    throw new ExploreApiError("malformed");
  }
}
