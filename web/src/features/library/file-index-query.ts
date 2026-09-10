import { queryOptions } from "@tanstack/react-query";
import {
  fetchFileIndex,
  type FileIndexQueryOptions,
} from "../../shared/api/api-client";

export const FILE_INDEX_QUERY_KEY = "file-index-catalog" as const;

export interface FileIndexCatalogSearchState {
  readonly resourceLibrary: string | null;
  readonly storage: string | null;
  readonly scanStatus: string | null;
  readonly query: string | null;
  readonly processingDisposition: string | null;
  readonly recognitionType: string | null;
  readonly provider: string | null;
  readonly providerId: string | null;
  readonly title: string | null;
  readonly taskId: string | null;
  readonly year: string | null;
  readonly after: string | null;
  readonly cursorFileId: string | null;
  readonly before: string | null;
}

const PAGE_LIMIT = 50;
const MAX_ROUTE_VALUE_LENGTH = 512;

const SEARCH_KEYS = [
  "resourceLibrary",
  "storage",
  "scanStatus",
  "query",
  "processingDisposition",
  "recognitionType",
  "provider",
  "providerId",
  "title",
  "taskId",
  "year",
  "after",
  "cursorFileId",
  "before",
] as const;

function safeRouteValue(value: string | null): string | null {
  if (
    value === null ||
    value === "" ||
    value.length > MAX_ROUTE_VALUE_LENGTH ||
    // eslint-disable-next-line no-control-regex
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    return null;
  }
  return value;
}

export function fileIndexQueryOptions(
  token: string | null,
  search: FileIndexCatalogSearchState,
  statusReady = false,
) {
  const opts: FileIndexQueryOptions = {
    limit: PAGE_LIMIT,
    resourceLibrary: search.resourceLibrary,
    storage: search.storage,
    scanStatus: search.scanStatus,
    query: search.query,
    processingDisposition: search.processingDisposition,
    recognitionType: search.recognitionType,
    provider: search.provider,
    providerId: search.providerId,
    title: search.title,
    taskId: search.taskId,
    year: search.year,
    after: search.after,
    cursorFileId: search.cursorFileId,
    before: search.before,
  };
  return queryOptions({
    queryKey: [FILE_INDEX_QUERY_KEY, opts] as const,
    queryFn: () => fetchFileIndex(token, opts),
    enabled: token !== null && statusReady,
    retry: false,
  });
}

export function parseFileIndexSearch(
  search: URLSearchParams,
): FileIndexCatalogSearchState {
  const get = (key: string) => safeRouteValue(search.get(key));
  return {
    resourceLibrary: get("resourceLibrary"),
    storage: get("storage"),
    scanStatus: get("scanStatus"),
    query: get("query"),
    processingDisposition: get("processingDisposition"),
    recognitionType: get("recognitionType"),
    provider: get("provider"),
    providerId: get("providerId"),
    title: get("title"),
    taskId: get("taskId"),
    year: get("year"),
    after: get("after"),
    cursorFileId: get("cursorFileId"),
    before: get("before"),
  };
}

/** Serialize only the safe, backend-supported catalog view state for a route. */
export function serializeFileIndexSearch(
  search: FileIndexCatalogSearchState,
): string {
  const params = new URLSearchParams();
  for (const key of SEARCH_KEYS) {
    const value = safeRouteValue(search[key]);
    if (value !== null) {
      params.set(key, value);
    }
  }
  return params.toString();
}

/**
 * Serialize the submitted catalog view state as bounded `q_`-prefixed return
 * context for the FileIndex detail route. Only backend-supported catalog
 * query names travel; no credentials or mutation authority are ever included.
 */
export function serializeCatalogReturnContext(
  search: FileIndexCatalogSearchState,
): string {
  const params = new URLSearchParams();
  for (const key of SEARCH_KEYS) {
    const value = safeRouteValue(search[key]);
    if (value !== null) {
      params.set(`q_${key}`, value);
    }
  }
  return params.toString();
}

/** Reconstruct the submitted catalog query from detail-route return context. */
export function parseCatalogReturnContext(
  params: URLSearchParams,
): FileIndexCatalogSearchState {
  const state = emptyFileIndexSearch();
  for (const key of SEARCH_KEYS) {
    const value = params.get(`q_${key}`);
    if (value !== null) {
      const safe = safeRouteValue(value);
      if (safe !== null) {
        (state as unknown as Record<string, string | null>)[key] = safe;
      }
    }
  }
  return state;
}

export function emptyFileIndexSearch(): FileIndexCatalogSearchState {
  return {
    resourceLibrary: null,
    storage: null,
    scanStatus: null,
    query: null,
    processingDisposition: null,
    recognitionType: null,
    provider: null,
    providerId: null,
    title: null,
    taskId: null,
    year: null,
    after: null,
    cursorFileId: null,
    before: null,
  };
}
