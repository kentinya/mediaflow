/**
 * TanStack Query boundary for this library's durable organizing work.
 *
 * The Task Center no longer owns the discovery/manual-action sections, so Files
 * reads its own bounded, principal-scoped work list here.  That is what lets the
 * operator reopen several known runs — and each one's exact plan summary — after a
 * close, a reload, a re-login or a service restart.
 *
 * Reads are side-effect-free.  Opening, refreshing or reconnecting never creates,
 * resumes or re-submits work, and a bounded poll only keeps the readback current
 * while real work is still active.
 */

import { queryOptions } from "@tanstack/react-query";
import { fetchFilesOrganizeWork } from "../../shared/api/api-client";

export const filesOrganizeWorkQueryKey = "files.organize-work" as const;

export function filesOrganizeWorkQueryOptions(
  token: string | null,
  resourceLibraryId: string,
) {
  return queryOptions({
    queryKey: [filesOrganizeWorkQueryKey, resourceLibraryId],
    queryFn: () => fetchFilesOrganizeWork(token, { resourceLibraryId }),
    enabled: token !== null && resourceLibraryId !== "",
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 2_000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data === undefined || !data.ok) return false;
      const active = data.items.some(
        (item) =>
          !item.prepared &&
          item.status !== "cancelled" &&
          item.status !== "failed",
      );
      return active ? 5_000 : false;
    },
    refetchIntervalInBackground: false,
  });
}
