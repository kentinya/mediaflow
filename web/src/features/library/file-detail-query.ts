import { queryOptions } from "@tanstack/react-query";
import {
  fetchFileBySource,
  fetchFileDetail,
  type FileBySourceQueryOptions,
} from "../../shared/api/api-client";

export const FILE_DETAIL_QUERY_KEY = "file-index-detail" as const;
export const FILE_BY_SOURCE_QUERY_KEY = "file-index-by-source" as const;

/** Authenticated bounded GET for one FileIndex detail document. */
export function fileDetailQueryOptions(
  token: string | null,
  fileId: string,
  resourceLibrary: string | null = null,
  enabled = true,
) {
  return queryOptions({
    queryKey: [FILE_DETAIL_QUERY_KEY, fileId, resourceLibrary] as const,
    queryFn: () => fetchFileDetail(token, { fileId, resourceLibrary }),
    enabled: token !== null && fileId !== "" && enabled,
    retry: false,
  });
}

/**
 * Authenticated bounded GET for the explicit unique-link check. Pass an
 * empty-storage/path target until the operator asks to open the indexed
 * destination; the query stays disabled until a real target is selected.
 */
export function fileBySourceQueryOptions(
  token: string | null,
  options: FileBySourceQueryOptions,
  enabled = true,
) {
  return queryOptions({
    queryKey: [FILE_BY_SOURCE_QUERY_KEY, options] as const,
    queryFn: () => fetchFileBySource(token, options),
    enabled:
      token !== null &&
      enabled &&
      options.storageId !== "" &&
      options.path !== "",
    retry: false,
  });
}
