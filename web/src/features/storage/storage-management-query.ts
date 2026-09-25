import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import {
  fetchStorageInventory,
  type StorageInventoryQuery,
} from "../../shared/api/api-client";
import type { StorageFamily } from "../../entities/storage/storage-management";
/** Query key for the bounded exact-Active Storage inventory read. */
export const STORAGE_INVENTORY_QUERY_KEY =
  "storage-management-inventory" as const;

/**
 * The operator-visible inventory selection.
 *
 * Search and the provider family filter are applied by the backend over the
 * complete Active object set rather than over one already-truncated page, so a
 * legal over-limit configuration can never hide a configured Storage from the
 * shared top-bar search or the provider cards.
 */
export interface StorageInventorySelection {
  readonly query: string;
  readonly family: StorageFamily | null;
  /** Stable ID cursor for explicit continuation to the next bounded page. */
  readonly after: string | null;
}

export function storageInventoryQueryOptions(
  token: string | null,
  selection: StorageInventorySelection,
) {
  const request: StorageInventoryQuery = {
    query: selection.query,
    family: selection.family,
    after: selection.after,
  };
  return queryOptions({
    queryKey: [STORAGE_INVENTORY_QUERY_KEY, selection] as const,
    queryFn: () => fetchStorageInventory(token, request),
    enabled: token !== null,
    retry: false,
    // The previous page stays visible while the next bounded search/filter
    // resolves, so typing never flashes an empty table.
    placeholderData: keepPreviousData,
  });
}
