import { queryOptions } from "@tanstack/react-query";
import {
  fetchStorageFiles,
  type StorageFilesQueryOptions,
} from "../../shared/api/api-client";

/** Query key for one bounded Storage-relative read. */
export const STORAGE_FILES_QUERY_KEY = "storage-files" as const;

export function storageFilesQueryOptions(
  token: string | null,
  options: StorageFilesQueryOptions,
  statusReady = false,
) {
  return queryOptions({
    queryKey: [STORAGE_FILES_QUERY_KEY, options] as const,
    queryFn: () => fetchStorageFiles(token, options),
    enabled: token !== null && options.storageId !== "" && statusReady,
    retry: false,
  });
}
