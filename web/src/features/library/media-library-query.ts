import { queryOptions } from "@tanstack/react-query";
import {
  fetchMediaLibraryFiles,
  fetchMediaLibraryList,
  type MediaLibraryFilesQueryOptions,
} from "../../shared/api/api-client";

/**
 * Query key for one MediaLibrary-relative live Storage read. The key is fully
 * independent of the ResourceLibrary Files cache: equal IDs, roots or paths on
 * the two kinds never share cache entries.
 */
export const MEDIA_LIBRARY_FILES_QUERY_KEY = "media-library-files" as const;

export function mediaLibraryFilesQueryOptions(
  token: string | null,
  options: MediaLibraryFilesQueryOptions,
  statusReady = false,
) {
  return queryOptions({
    queryKey: [MEDIA_LIBRARY_FILES_QUERY_KEY, options] as const,
    queryFn: () => fetchMediaLibraryFiles(token, options),
    enabled: token !== null && options.mediaLibraryId !== "" && statusReady,
    retry: false,
  });
}

/** Read-only list of enabled MediaLibraries in the Active runtime. */
export const MEDIA_LIBRARY_LIST_QUERY_KEY = ["media-libraries"] as const;

export function mediaLibraryListQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: MEDIA_LIBRARY_LIST_QUERY_KEY,
    queryFn: () => fetchMediaLibraryList(token),
    enabled: token !== null,
    retry: false,
  });
}
