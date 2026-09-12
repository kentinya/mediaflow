/**
 * V2 Notification definitions list.
 *
 * The page reads the backend's bounded definitions page: the exact immutable
 * Active identity, the open successor Draft, and one bounded Webhook document
 * per definition with its deployment-owned secret readiness (never a secret
 * value) and backend-advertised actions. A Draft-only definition is visibly
 * distinct from Active and never rendered as runtime truth.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { createNotificationSuccessorDraft } from "../../shared/api/api-client";
import {
  notificationListQueryKey,
  notificationListQueryOptions,
} from "./notification-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

function readinessLabel(
  readiness: readonly { readonly env: string; readonly state: string }[],
): string {
  if (readiness.length === 0) {
    return "no secret reference advertised";
  }
  return readiness.map((item) => `${item.env}: ${item.state}`).join(", ");
}

export function NotificationListPage() {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const query = useQuery(notificationListQueryOptions(token));

  const draftMutation = useMutation({
    mutationFn: (activeRevisionId: string) =>
      createNotificationSuccessorDraft(token, { activeRevisionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        return;
      }
      setError(
        `Starting the successor Draft was rejected (${result.code}). Reload and try again; nothing is retried automatically.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Notification definitions unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner
              variant="info"
              title="Loading Notification definitions"
            >
              <p>Reading the exact Active and Draft Webhook definitions.</p>
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
                  to="/operations"
                >
                  Back to Operations
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const page = data.model;
        const create = page.actions.create;
        const createDraft = page.actions.createDraft;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Notifications</h2>
                <p className="mf-dashboard-meta">
                  Webhook Definitions, signed endpoint tests and durable
                  deliveries. Secret values are never shown.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <div className="mf-actions">
              <Link className="mf-button mf-button-secondary" to="/operations">
                Operations overview
              </Link>
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/notifications/deliveries"
              >
                Open deliveries
              </Link>
            </div>
            <section className="mf-count-section">
              <h3>Configuration</h3>
              <dl>
                <dt>Active configuration</dt>
                <dd>
                  {page.activeConfiguration === null
                    ? "none — complete managed configuration setup first"
                    : `revision ${page.activeConfiguration.revisionId} · version ${page.activeConfiguration.version}`}
                </dd>
                <dt>Open Draft</dt>
                <dd>
                  {page.draftState.present
                    ? `revision ${page.draftState.revisionId} · version ${page.draftState.revisionVersion} · ${page.draftState.revisionStatus}`
                    : (page.draftState.reason ?? "no open Draft")}
                </dd>
                <dt>Definitions</dt>
                <dd>
                  {page.total}
                  {page.truncated ? " (list truncated)" : ""}
                </dd>
              </dl>
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-primary"
                to="/operations/notifications/webhooks/new"
                aria-disabled={!create.available}
              >
                New Webhook definition
              </Link>
              <Button
                type="button"
                disabled={!createDraft.available || draftMutation.isPending}
                onClick={() => {
                  if (page.activeConfiguration !== null) {
                    draftMutation.mutate(page.activeConfiguration.revisionId);
                  }
                }}
              >
                {draftMutation.isPending
                  ? "Starting successor Draft…"
                  : "Start successor Draft"}
              </Button>
            </div>
            {!create.available && create.reason !== null && (
              <StatusBanner variant="info" title="Create unavailable">
                <p>{create.reason}</p>
              </StatusBanner>
            )}
            {error !== null && (
              <StatusBanner variant="error" title="Draft not started">
                <p>{error}</p>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Webhook definitions</h3>
              {page.items.length === 0 ? (
                <p className="mf-dashboard-meta">
                  No Webhook definitions exist yet. Start a successor Draft and
                  create one.
                </p>
              ) : (
                <ul className="mf-failure-list">
                  {page.items.map((item) => (
                    <li key={item.document.id}>
                      <div>
                        <strong>{item.document.id}</strong>{" "}
                        <span className="mf-status-badge">
                          {item.definitionState === "active"
                            ? "Active"
                            : "Draft only"}
                        </span>{" "}
                        <span className="mf-status-badge">
                          {item.document.enabled ? "enabled" : "disabled"}
                        </span>
                        {!item.document.structuralValid && (
                          <span className="mf-status-badge">invalid</span>
                        )}
                      </div>
                      <div className="mf-failure-meta">
                        events: {item.document.events.join(", ")} · endpoint
                        host: {item.document.url} · secret readiness:{" "}
                        {readinessLabel(item.document.secretReadiness)}
                      </div>
                      {item.document.validationError !== null && (
                        <div className="mf-failure-meta">
                          validation finding: {item.document.validationError}
                        </div>
                      )}
                      <div className="mf-actions">
                        <Link
                          className="mf-button mf-button-secondary"
                          to="/operations/notifications/webhooks/$webhookId"
                          params={{ webhookId: item.document.id }}
                        >
                          Open definition
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
