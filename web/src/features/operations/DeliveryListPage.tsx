/**
 * V2 Notification delivery workspace.
 *
 * The durable delivery list is the background of the delivery-detail card.
 * Its status filter lives in the route search and its cursor stays in this
 * mounted page, so opening one delivery and closing it returns to the same
 * filter, page, scroll position and focus. Statuses, attempts, response
 * categories and due times are shown in operator language; delivery bodies,
 * signed headers, secret values and raw exceptions are never published by the
 * API and never appear here.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { notificationDeliveriesQueryOptions } from "./notification-query";
import {
  NOTIFICATION_DELIVERY_STATUSES,
  type NotificationDeliveryStatus,
} from "../../entities/operations/notification";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { NotificationWorkspaceHeader } from "./NotificationWorkspaceHeader";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  deliveryStatusLabel,
  failureCategoryLabel,
  formatNotificationTime,
  notificationEventLabel,
} from "./notification-presentation";

function readSafeSearchValue(
  search: Record<string, unknown>,
  key: string,
): string | null {
  const value = search[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function deliveriesSearch(
  status: NotificationDeliveryStatus | "all",
): Record<string, string> | undefined {
  return status === "all" ? undefined : { status };
}

export function DeliveryListPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const rawStatus = readSafeSearchValue(searchParams, "status");
  // An unknown status filter is read as "all": the backend rejects arbitrary
  // status tokens, so the UI never sends one.
  const statusFilter: NotificationDeliveryStatus | "all" =
    rawStatus !== null &&
    (NOTIFICATION_DELIVERY_STATUSES as readonly string[]).includes(rawStatus)
      ? (rawStatus as NotificationDeliveryStatus)
      : "all";
  const effectiveStatus = statusFilter === "all" ? null : statusFilter;
  const [cursor, setCursor] = useState<string | null>(null);

  const query = useQuery(
    notificationDeliveriesQueryOptions(token, effectiveStatus, cursor),
  );

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="通知投递记录暂时不可用"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="正在读取投递记录">
              <p>读取持久的通知投递状态。</p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/notifications"
                >
                  返回通知
                </Link>
                <RefreshControl
                  onRefresh={refresh}
                  refreshing={isFetching}
                  label="刷新"
                  refreshingLabel="刷新中…"
                />
              </div>
            </StatusBanner>
          );
        }
        const page = data.model;
        return (
          <div
            className="mf-notifications-page"
            id="notification-deliveries-background"
            tabIndex={-1}
          >
            <NotificationWorkspaceHeader
              section="deliveries"
              refresh={refresh}
              refreshing={isFetching}
            />
            <div className="mf-notification-toolbar">
              <div className="mf-notification-toolbar-primary">
                <label
                  className="mf-notification-filter"
                  htmlFor="delivery-status-filter"
                >
                  投递状态
                  <select
                    id="delivery-status-filter"
                    value={statusFilter}
                    onChange={(event) => {
                      setCursor(null);
                      void navigate({
                        to: "/operations/notifications/deliveries",
                        search: deliveriesSearch(
                          event.target.value as
                            NotificationDeliveryStatus | "all",
                        ),
                      });
                    }}
                  >
                    <option value="all">全部状态</option>
                    {NOTIFICATION_DELIVERY_STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {deliveryStatusLabel(status)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>

            <section
              className="mf-notification-list-section"
              aria-label="投递记录"
            >
              {page.items.length === 0 ? (
                <div className="mf-notification-empty">
                  <p>当前筛选下没有投递记录。</p>
                </div>
              ) : (
                <ul className="mf-notification-cards">
                  {page.items.map((item) => (
                    <li
                      className="mf-notification-list-card"
                      key={item.deliveryId}
                      tabIndex={-1}
                      id={`notification-delivery-${item.deliveryId}`}
                    >
                      <div className="mf-notification-card-head">
                        <div>
                          <strong className="mf-notification-webhook-name">
                            {notificationEventLabel(item.eventType)}
                          </strong>
                          <span
                            className={
                              item.status === "dead-letter"
                                ? "mf-notification-badge mf-notification-badge-danger"
                                : item.status === "delivered"
                                  ? "mf-notification-badge mf-notification-badge-active"
                                  : "mf-notification-badge"
                            }
                          >
                            {deliveryStatusLabel(item.status)}
                          </span>
                          {item.attempts > 0 && (
                            <span className="mf-notification-badge">
                              尝试 {item.attempts} 次
                            </span>
                          )}
                        </div>
                        <span className="mf-notification-secret-state">
                          {formatNotificationTime(item.updatedAt)}
                        </span>
                      </div>
                      <p className="mf-notification-events">
                        {item.responseStatus !== null &&
                          item.failureCategory !==
                            `http_${item.responseStatus}` && (
                            <span className="mf-notification-event">
                              HTTP {item.responseStatus}
                            </span>
                          )}
                        {failureCategoryLabel(item.failureCategory) !==
                          null && (
                          <span className="mf-notification-event mf-notification-event-danger">
                            {failureCategoryLabel(item.failureCategory)}
                          </span>
                        )}
                      </p>
                      <div className="mf-notification-actions">
                        <Link
                          className="mf-button mf-button-secondary"
                          to="/operations/notifications/deliveries/$deliveryId"
                          params={{ deliveryId: item.deliveryId }}
                          search={(previous) => ({
                            ...previous,
                            ...(statusFilter === "all"
                              ? {}
                              : { status: statusFilter }),
                          })}
                        >
                          查看投递
                        </Link>
                      </div>
                      <details className="mf-notification-diagnostics">
                        <summary>诊断信息</summary>
                        <dl>
                          <dt>投递标识</dt>
                          <dd>{item.deliveryId}</dd>
                          <dt>Webhook</dt>
                          <dd>{item.webhookId}</dd>
                          <dt>事件标识</dt>
                          <dd>
                            {item.eventType}（{item.eventId}）
                          </dd>
                          <dt>上次更新</dt>
                          <dd>{item.updatedAt}</dd>
                          <dt>下次自动尝试</dt>
                          <dd>{item.nextAttemptAt}</dd>
                          <dt>失败类别</dt>
                          <dd>{item.failureCategory ?? "无"}</dd>
                        </dl>
                      </details>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <div className="mf-notification-pagination">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={page.previousCursor === null || isFetching}
                onClick={() => setCursor(page.previousCursor)}
              >
                上一页
              </button>
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={page.nextCursor === null || isFetching}
                onClick={() => setCursor(page.nextCursor)}
              >
                下一页
              </button>
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
