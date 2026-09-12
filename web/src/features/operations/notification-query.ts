/**
 * TanStack Query boundaries for the V2 Notification journey.
 *
 * Reads are ordinary bounded queries; mutations are owned by the pages that
 * submit them. Every query and mutation disables automatic retry so an
 * ambiguous test, recovery or 401/403 is never replayed silently: the
 * operator reads the current durable state and decides.
 */

import { queryOptions } from "@tanstack/react-query";
import {
  fetchNotificationDefinition,
  fetchNotificationDefinitionDraft,
  fetchNotificationDefinitions,
  fetchNotificationDeliveries,
  fetchNotificationDeliveryDetail,
} from "../../shared/api/api-client";

export const notificationListQueryKey = "operations.notification-list" as const;

export function notificationListQueryOptions(
  token: string | null,
  enabled = true,
) {
  return queryOptions({
    queryKey: [notificationListQueryKey],
    queryFn: () => fetchNotificationDefinitions(token),
    enabled: token !== null && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const notificationDefinitionQueryKey =
  "operations.notification-definition" as const;

export function notificationDefinitionQueryOptions(
  token: string | null,
  webhookId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [notificationDefinitionQueryKey, webhookId],
    queryFn: () => fetchNotificationDefinition(token, webhookId),
    enabled: token !== null && webhookId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const notificationDraftQueryKey =
  "operations.notification-draft" as const;

export function notificationDraftQueryOptions(
  token: string | null,
  webhookId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [notificationDraftQueryKey, webhookId],
    queryFn: () => fetchNotificationDefinitionDraft(token, webhookId),
    enabled: token !== null && webhookId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const notificationDeliveriesQueryKey =
  "operations.notification-deliveries" as const;

export function notificationDeliveriesQueryOptions(
  token: string | null,
  status: string | null,
  cursor: string | null,
  enabled = true,
) {
  return queryOptions({
    queryKey: [notificationDeliveriesQueryKey, status ?? "all", cursor],
    queryFn: () =>
      fetchNotificationDeliveries(token, {
        limit: 20,
        status,
        cursor,
      }),
    enabled: token !== null && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}

export const notificationDeliveryQueryKey =
  "operations.notification-delivery" as const;

export function notificationDeliveryQueryOptions(
  token: string | null,
  deliveryId: string,
  enabled = true,
) {
  return queryOptions({
    queryKey: [notificationDeliveryQueryKey, deliveryId],
    queryFn: () => fetchNotificationDeliveryDetail(token, deliveryId),
    enabled: token !== null && deliveryId.length > 0 && enabled,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 5_000,
  });
}
