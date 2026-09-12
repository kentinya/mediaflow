/**
 * V2 Webhook definition detail.
 *
 * The page reads the backend's bounded definition document: the exact
 * Active/Draft identity, deployment-owned secret readiness and the
 * backend-advertised test/copy/enable/disable transports. The signed test is
 * bound to the exact displayed revision identity and version while the
 * configuration digest and the resolved secret remain server-side; exactly
 * one request is sent per explicit action and nothing is retried or activated.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  copyWebhookDefinition,
  setWebhookDefinitionEnabled,
  testWebhookDefinition,
} from "../../shared/api/api-client";
import {
  notificationDefinitionQueryKey,
  notificationDefinitionQueryOptions,
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

export function NotificationDetailPage() {
  const { webhookId } = useParams({
    from: "/operations/notifications/webhooks/$webhookId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  const query = useQuery(notificationDefinitionQueryOptions(token, webhookId));

  const testMutation = useMutation({
    mutationFn: (input: {
      expectedRevisionId: string;
      expectedVersion: number;
    }) =>
      testWebhookDefinition(token, {
        webhookId,
        expectedRevisionId: input.expectedRevisionId,
        expectedVersion: input.expectedVersion,
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setTestResult(null);
    },
    onSuccess: (result) => {
      if (result.ok) {
        const model = result.model;
        setTestResult(
          `${model.outcome === "success" ? "Test succeeded" : "Test failed"} (${model.category}${model.responseStatus !== null ? `, HTTP ${model.responseStatus}` : ""}). ${model.message} ${model.nextAction}`,
        );
        return;
      }
      setError(
        result.status === 409
          ? "The displayed revision is stale, so no test request was sent. Refresh the definition and test the exact current revision again."
          : `The test was rejected (${result.code}). Read the current durable state and try again; nothing is retried automatically.`,
      );
    },
  });

  const draftMutation = useMutation({
    mutationFn: (input: {
      kind: "copy" | "enable" | "disable";
      expectedVersion: number;
    }) => {
      const revisionId = query.data?.ok
        ? query.data.model.draftState.revisionId
        : null;
      if (revisionId === null) {
        return Promise.reject(new Error("no draft"));
      }
      if (input.kind === "copy") {
        return copyWebhookDefinition(token, {
          revisionId,
          webhookId,
          expectedVersion: input.expectedVersion,
        });
      }
      return setWebhookDefinitionEnabled(token, {
        revisionId,
        webhookId,
        expectedVersion: input.expectedVersion,
        enabled: input.kind === "enable",
      });
    },
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result, input) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationDefinitionQueryKey],
        });
        if (input.kind === "copy") {
          // The bound model is the exact copied identity derived from this
          // mutation; no local or unrelated id is ever navigated to.
          void navigate({
            to: "/operations/notifications/webhooks/$webhookId",
            params: { webhookId: result.model.id },
          });
        }
        return;
      }
      setError(
        result.status === 409
          ? "The Draft changed before the action was applied. Refresh the definition and try again; the winning revision was preserved."
          : `The ${input.kind} action was rejected (${result.code}). Read the current durable state and try again; nothing is retried automatically.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Webhook definition unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading definition">
              <p>Reading the exact bounded Webhook definition.</p>
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
        const definition = data.model;
        const document = definition.document;
        const test = definition.actions.test;
        const draft = definition.draftState;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Webhook {document.id}</h2>
                <p className="mf-dashboard-meta">
                  {definition.definitionState === "active"
                    ? "This definition is part of the immutable Active configuration."
                    : "This definition exists only inside an open successor Draft; activate the Draft to make it Active."}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Definition</h3>
              <dl>
                <dt>State</dt>
                <dd>
                  {definition.definitionState === "active"
                    ? "Active"
                    : "Draft only"}
                  {" · "}
                  {document.enabled ? "enabled" : "disabled"}
                </dd>
                <dt>HTTPS endpoint</dt>
                <dd>{document.url}</dd>
                <dt>Secret reference readiness</dt>
                <dd>{readinessLabel(document.secretReadiness)}</dd>
                <dt>Events</dt>
                <dd>{document.events.join(", ")}</dd>
                <dt>Delivery bounds</dt>
                <dd>
                  timeout {document.timeoutSeconds}s · max attempts{" "}
                  {document.maxAttempts} · retry {document.baseRetrySeconds}s–
                  {document.maxRetrySeconds}s
                </dd>
                <dt>Active configuration</dt>
                <dd>
                  {definition.activeConfiguration === null
                    ? "none"
                    : `revision ${definition.activeConfiguration.revisionId} · version ${definition.activeConfiguration.version}`}
                </dd>
                <dt>Open Draft</dt>
                <dd>
                  {draft.present
                    ? `revision ${draft.revisionId} · version ${draft.revisionVersion} · ${draft.revisionStatus}`
                    : (draft.reason ?? "no open Draft")}
                </dd>
              </dl>
              {!document.structuralValid &&
                document.validationError !== null && (
                  <StatusBanner variant="error" title="Invalid definition">
                    <p>{document.validationError}</p>
                  </StatusBanner>
                )}
            </section>
            <section className="mf-count-section">
              <h3>Explicit endpoint test</h3>
              <p className="mf-dashboard-meta">
                {test.available
                  ? "Sends exactly one signed test request to the exact displayed revision. No delivery is created, nothing is activated and nothing is retried."
                  : `Test unavailable: ${test.reason ?? "not advertised"}`}
              </p>
              {test.available && (
                <div className="mf-actions">
                  <Button
                    type="button"
                    disabled={testMutation.isPending}
                    onClick={() => {
                      const revisionId =
                        definition.definitionState === "active"
                          ? (definition.activeConfiguration?.revisionId ?? null)
                          : draft.revisionId;
                      const version =
                        definition.definitionState === "active"
                          ? (definition.activeConfiguration?.version ?? null)
                          : draft.revisionVersion;
                      if (revisionId !== null && version !== null) {
                        testMutation.mutate({
                          expectedRevisionId: revisionId,
                          expectedVersion: version,
                        });
                      }
                    }}
                  >
                    {testMutation.isPending
                      ? "Sending signed test…"
                      : "Test this exact revision"}
                  </Button>
                </div>
              )}
              {testResult !== null && (
                <StatusBanner variant="info" title="Signed test outcome">
                  <p>{testResult}</p>
                </StatusBanner>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Draft definition actions</h3>
              <p className="mf-dashboard-meta">
                {draft.present
                  ? "Copy, enable and disable are stored inside the open successor Draft and never change the Active configuration until checked activation."
                  : "An open successor Draft is required to copy, enable or disable this definition."}
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={
                    !definition.actions.copy.available ||
                    !draft.present ||
                    draftMutation.isPending
                  }
                  onClick={() => {
                    if (draft.revisionVersion !== null) {
                      draftMutation.mutate({
                        kind: "copy",
                        expectedVersion: draft.revisionVersion,
                      });
                    }
                  }}
                >
                  {draftMutation.isPending ? "Working…" : "Copy into Draft"}
                </Button>
                <Button
                  type="button"
                  disabled={
                    !definition.actions.enable.available ||
                    !draft.present ||
                    draftMutation.isPending
                  }
                  onClick={() => {
                    if (draft.revisionVersion !== null) {
                      draftMutation.mutate({
                        kind: "enable",
                        expectedVersion: draft.revisionVersion,
                      });
                    }
                  }}
                >
                  Enable in Draft
                </Button>
                <Button
                  type="button"
                  disabled={
                    !definition.actions.disable.available ||
                    !draft.present ||
                    draftMutation.isPending
                  }
                  onClick={() => {
                    if (draft.revisionVersion !== null) {
                      draftMutation.mutate({
                        kind: "disable",
                        expectedVersion: draft.revisionVersion,
                      });
                    }
                  }}
                >
                  Disable in Draft
                </Button>
              </div>
              {draftMutation.isError && error === null && (
                <StatusBanner variant="error" title="Action not completed">
                  <p>The action could not be applied. Refresh and try again.</p>
                </StatusBanner>
              )}
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-primary"
                to="/operations/notifications/editor/$webhookId"
                params={{ webhookId: document.id }}
              >
                Open Draft editor
              </Link>
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/notifications/deliveries"
              >
                Open deliveries
              </Link>
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/notifications"
              >
                Back to Notifications
              </Link>
            </div>
            {error !== null && (
              <StatusBanner variant="error" title="Action not completed">
                <p>{error}</p>
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
