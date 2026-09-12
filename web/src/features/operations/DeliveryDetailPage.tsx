/**
 * V2 Notification delivery detail and exact recovery.
 *
 * The page reads the bounded delivery detail from the operations projection:
 * durable status, attempts, response category, lease state, known receiver
 * effects, at-least-once implications and the backend-advertised recovery
 * actions. Recovery submits the exact delivery identity plus the observed
 * status/update fence, requires explicit confirmation, and is never retried
 * automatically after stale state, conflict, denial or transport failure —
 * the page refreshes to durable truth instead.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  requeueDeadLetterDelivery,
  resolveStaleDelivery,
} from "../../shared/api/api-client";
import {
  notificationDeliveryQueryKey,
  notificationDeliveryQueryOptions,
} from "./notification-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

export function DeliveryDetailPage() {
  const { deliveryId } = useParams({
    from: "/operations/notifications/deliveries/$deliveryId",
  });
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [confirmRequeue, setConfirmRequeue] = useState(false);
  const [confirmResolve, setConfirmResolve] = useState(false);

  const query = useQuery(notificationDeliveryQueryOptions(token, deliveryId));

  const recoveryMutation = useMutation({
    mutationFn: (input: {
      kind: "requeue" | "resolveStale";
      expectedStatus: string;
      expectedUpdatedAt: string;
    }) => {
      const options = {
        deliveryId,
        expectedStatus: input.expectedStatus,
        expectedUpdatedAt: input.expectedUpdatedAt,
      };
      return input.kind === "requeue"
        ? requeueDeadLetterDelivery(token, options)
        : resolveStaleDelivery(token, options);
    },
    retry: false,
    onMutate: () => {
      setError(null);
      setConfirmRequeue(false);
      setConfirmResolve(false);
    },
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationDeliveryQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: ["operations.notification-deliveries"],
        });
        return;
      }
      setError(
        result.status === 409
          ? "The delivery state is newer than the state you inspected, so no recovery was applied. Refresh the delivery and recover the exact current state again."
          : `The recovery action was rejected (${result.code}). Read the current durable state and try again; nothing is retried automatically.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Notification delivery unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading delivery">
              <p>Reading the exact durable delivery state.</p>
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
                  to="/operations/notifications/deliveries"
                >
                  Back to deliveries
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const model = data.model;
        const delivery = model.delivery;
        const requeue = model.actions.requeue;
        const resolveStale = model.actions.resolveStale;
        const observed = {
          expectedStatus: delivery.status,
          expectedUpdatedAt: delivery.updatedAt,
        };
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Delivery {delivery.deliveryId}</h2>
                <p className="mf-dashboard-meta">
                  One durable notification delivery. Recovery changes only this
                  row and never re-executes, rewrites or rolls back completed
                  media work.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Delivery state</h3>
              <dl>
                <dt>Status</dt>
                <dd>{delivery.status}</dd>
                <dt>Event</dt>
                <dd>
                  {delivery.eventType} ({delivery.eventId})
                </dd>
                <dt>Webhook</dt>
                <dd>{delivery.webhookId}</dd>
                <dt>Attempts</dt>
                <dd>{delivery.attempts}</dd>
                <dt>Response evidence</dt>
                <dd>
                  {delivery.responseStatus !== null
                    ? `HTTP ${delivery.responseStatus}`
                    : "no response recorded"}
                  {delivery.failureCategory !== null
                    ? ` · ${delivery.failureCategory}`
                    : ""}
                </dd>
                <dt>Lease</dt>
                <dd>
                  {model.lease.state}
                  {model.lease.expiresAt !== null
                    ? ` · expires ${model.lease.expiresAt}`
                    : ""}
                </dd>
                <dt>Timeline</dt>
                <dd>
                  created {delivery.createdAt} · updated {delivery.updatedAt}
                  {delivery.deliveredAt !== null
                    ? ` · delivered ${delivery.deliveredAt}`
                    : ""}
                </dd>
                <dt>Next automatic attempt</dt>
                <dd>{delivery.nextAttemptAt}</dd>
              </dl>
            </section>
            <section className="mf-count-section">
              <h3>Known effects and safety</h3>
              <p className="mf-dashboard-meta">{model.knownEffects}</p>
              <p className="mf-dashboard-meta">{model.nextAction}</p>
              <p className="mf-dashboard-meta">
                Delivery bodies, signed request headers and secret values are
                never displayed.
              </p>
            </section>
            <section className="mf-count-section">
              <h3>Recovery</h3>
              <p className="mf-dashboard-meta">{model.recovery.reason}</p>
              {requeue !== null && (
                <>
                  <p className="mf-dashboard-meta">
                    Requeue returns this dead-letter delivery to the pending
                    queue with the same identity; attempts are reset and the
                    worker sends the event again. Receivers must tolerate
                    duplicates (at-least-once).
                  </p>
                  <div className="mf-actions">
                    <label>
                      <input
                        type="checkbox"
                        checked={confirmRequeue}
                        aria-label="Confirm dead-letter requeue"
                        onChange={(event) =>
                          setConfirmRequeue(event.target.checked)
                        }
                      />{" "}
                      I confirm the requeue of this exact delivery
                    </label>
                    <Button
                      type="button"
                      disabled={
                        !requeue.available ||
                        !confirmRequeue ||
                        recoveryMutation.isPending
                      }
                      onClick={() =>
                        recoveryMutation.mutate({
                          kind: "requeue",
                          ...observed,
                        })
                      }
                    >
                      {recoveryMutation.isPending
                        ? "Applying recovery…"
                        : "Requeue dead-letter delivery"}
                    </Button>
                  </div>
                  {!requeue.available && requeue.reason !== null && (
                    <StatusBanner variant="info" title="Requeue unavailable">
                      <p>{requeue.reason}</p>
                    </StatusBanner>
                  )}
                </>
              )}
              {resolveStale !== null && (
                <>
                  <p className="mf-dashboard-meta">
                    Resolving the expired lease returns this delivery to the
                    pending queue with the same identity and attempts. The
                    original attempt may have reached the receiver, so the
                    receiver may process the event more than once
                    (at-least-once).
                  </p>
                  <div className="mf-actions">
                    <label>
                      <input
                        type="checkbox"
                        checked={confirmResolve}
                        aria-label="Confirm stale delivery resolution"
                        onChange={(event) =>
                          setConfirmResolve(event.target.checked)
                        }
                      />{" "}
                      I confirm the resolution of this exact expired lease
                    </label>
                    <Button
                      type="button"
                      disabled={
                        !resolveStale.available ||
                        !confirmResolve ||
                        recoveryMutation.isPending
                      }
                      onClick={() =>
                        recoveryMutation.mutate({
                          kind: "resolveStale",
                          ...observed,
                        })
                      }
                    >
                      {recoveryMutation.isPending
                        ? "Applying recovery…"
                        : "Resolve expired lease"}
                    </Button>
                  </div>
                  {!resolveStale.available && resolveStale.reason !== null && (
                    <StatusBanner
                      variant="info"
                      title="Stale resolution unavailable"
                    >
                      <p>{resolveStale.reason}</p>
                    </StatusBanner>
                  )}
                </>
              )}
              {requeue === null && resolveStale === null && (
                <StatusBanner
                  variant="info"
                  title="No manual recovery advertised"
                >
                  <p>
                    This delivery has no eligible manual recovery action.
                    Automatic retries and completed deliveries never advertise
                    manual recovery.
                  </p>
                </StatusBanner>
              )}
              {error !== null && (
                <StatusBanner variant="error" title="Recovery not applied">
                  <p>{error}</p>
                </StatusBanner>
              )}
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/notifications/deliveries"
              >
                Back to deliveries
              </Link>
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
