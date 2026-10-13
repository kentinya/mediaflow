/**
 * TanStack Query boundary for one durable exact Preview analysis.
 *
 * Reads are ordinary bounded queries with automatic retry disabled: an
 * ambiguous or denied read is never replayed silently, and the operator decides
 * from the current durable state.  Polling is deliberately modest and stops as
 * soon as the analysis is no longer progressing, so a settled record is never
 * re-read on a timer.
 */

import { queryOptions } from "@tanstack/react-query";
import { fetchPreviewAnalysis } from "../../shared/api/api-client";

export const previewAnalysisQueryKey =
  "operations.automation-preview-analysis" as const;

export function previewAnalysisQueryOptions(
  token: string | null,
  analysisId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [previewAnalysisQueryKey, analysisId],
    queryFn: () => fetchPreviewAnalysis(token, { analysisId }),
    enabled: token !== null && analysisId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 1_000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data === undefined || !data.ok || data.model === undefined) {
        return false;
      }
      // Durable work is polled only while it is genuinely still progressing.
      return data.model.status === "queued" || data.model.status === "running"
        ? 2_000
        : false;
    },
  });
}
