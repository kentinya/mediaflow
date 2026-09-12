/**
 * V2 Notification delivery list.
 *
 * The page composes the existing durable delivery listing with the shared
 * backend status filter and directional cursors. Statuses, attempts, response
 * categories and due times are shown; delivery bodies, signed headers, secret
 * values and raw exceptions never appear because the API never publishes
 * them. Recovery always happens on the exact delivery detail page.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { notificationDeliveriesQueryOptions } from "./notification-query";
import { NOTIFICATION_DELIVERY_STATUSES } from "../../entities/operations/notification";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";

const STATUS_LABELS: Readonly<Record<string, string>> = {
  pending: "Pending",
  delivering: "Delivering",
  retry: "Retry scheduled",
  delivered: "Delivered",
  "dead-letter": "Dead letter",
};

function readSafeSearchValue(
  search: Record<string, unknown>,
  key: string,
): string | null {
  const value = search[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function deliveriesSearch(status: string): Record<string, string> | undefined {
  return status === "all" ? undefined : { status };
}

export function DeliveryListPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const rawStatus = readSafeSearchValue(searchParams, "status");
  // An unknown status filter is read as "all": the backend rejects arbitrary
  // status tokens, so the UI never sends one.
  const statusFilter =
    rawStatus !== null &&
    (NOTIFICATION_DELIVERY_STATUSES as readonly string[]).includes(rawStatus)
      ? rawStatus
      : "all";
  const effectiveStatus = statusFilter === "all" ? null : statusFilter;
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const query = useQuery(
    notificationDeliveriesQueryOptions(token, effectiveStatus, cursor),
  );

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Notification deliveries unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading deliveries">
              <p>Reading the durable Notification delivery state.</p>
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
                  Back to Notifications
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const page = data.model;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Notification deliveries</h2>
                <p className="mf-dashboard-meta">
                  Durable per-delivery outcomes. Each delivery keeps its own
                  state, attempts and recovery eligibility.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/notifications"
              >
                Back to Notifications
              </Link>
            </div>
            <section className="mf-count-section">
              <div className="mf-actions">
                <label htmlFor="delivery-status-filter">Filter by status</label>
                <select
                  id="delivery-status-filter"
                  value={statusFilter}
                  onChange={(event) => {
                    setCursor(null);
                    setError(null);
                    void navigate({
                      to: "/operations/notifications/deliveries",
                      search: deliveriesSearch(event.target.value),
                    });
                  }}
                >
                  <option value="all">All statuses</option>
                  {NOTIFICATION_DELIVERY_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {STATUS_LABELS[status] ?? status}
                    </option>
                  ))}
                </select>
              </div>
              {page.items.length === 0 ? (
                <p className="mf-dashboard-meta">
                  No deliveries match this filter. Deliveries are created by
                  events; testing a Webhook never creates one.
                </p>
              ) : (
                <ul className="mf-failure-list">
                  {page.items.map((item) => (
                    <li key={item.deliveryId}>
                      <div>
                        <strong>{item.eventType}</strong>{" "}
                        <span className="mf-status-badge">
                          {STATUS_LABELS[item.status] ?? item.status}
                        </span>
                        {item.attempts > 0 && (
                          <span className="mf-status-badge">
                            attempts: {item.attempts}
                          </span>
                        )}
                      </div>
                      <div className="mf-failure-meta">
                        updated {item.updatedAt}
                        {item.responseStatus !== null
                          ? ` · last response HTTP ${item.responseStatus}`
                          : ""}
                        {item.failureCategory !== null
                          ? ` · ${item.failureCategory}`
                          : ""}{" "}
                        · next attempt {item.nextAttemptAt}
                      </div>
                      <div className="mf-actions">
                        <Link
                          className="mf-button mf-button-secondary"
                          to="/operations/notifications/deliveries/$deliveryId"
                          params={{ deliveryId: item.deliveryId }}
                        >
                          Open delivery
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <div className="mf-actions">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={page.previousCursor === null || isFetching}
                onClick={() => {
                  setError(null);
                  setCursor(page.previousCursor);
                }}
              >
                Previous page
              </button>
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={page.nextCursor === null || isFetching}
                onClick={() => {
                  setError(null);
                  setCursor(page.nextCursor);
                }}
              >
                Next page
              </button>
            </div>
            {error !== null && (
              <StatusBanner variant="error" title="Page not changed">
                <p>{error}</p>
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
