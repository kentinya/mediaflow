import { queryOptions } from "@tanstack/react-query";
import { fetchStorageInventory } from "../../shared/api/api-client";

/** Query key for the bounded exact-Active Storage inventory read. */
export const STORAGE_INVENTORY_QUERY_KEY =
  "storage-management-inventory" as const;

export function storageInventoryQueryOptions(token: string | null) {
  return queryOptions({
    queryKey: [STORAGE_INVENTORY_QUERY_KEY] as const,
    queryFn: () => fetchStorageInventory(token),
    enabled: token !== null,
    retry: false,
  });
}
