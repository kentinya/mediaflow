/**
 * V2 Webhook successor-Draft editor.
 *
 * The editor reads the backend's Draft document: the exact open Draft with its
 * optimistic version, the bounded definition form and the backend-advertised
 * save/validate/activate/test transports. Saving, validation, signed testing
 * and checked activation are separate explicit actions bound to the exact
 * Draft revision identity and version; a stale revision is rejected atomically
 * and the page refreshes to durable truth without replaying anything.
 * Activation never creates a delivery or starts any work.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  activateWebhookDraft,
  createNotificationSuccessorDraft,
  saveWebhookDefinitionDraft,
  testWebhookDefinition,
  validateAutomationDraft,
} from "../../shared/api/api-client";
import {
  notificationDraftQueryKey,
  notificationDraftQueryOptions,
} from "./notification-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

interface WebhookFormState {
  readonly revisionId: string;
  readonly url: string;
  readonly secretEnv: string;
  readonly events: readonly string[];
  readonly enabled: boolean;
  readonly timeoutSeconds: string;
  readonly maxAttempts: string;
  readonly baseRetrySeconds: string;
  readonly maxRetrySeconds: string;
}

function formIssues(form: WebhookFormState): readonly string[] {
  const issues: string[] = [];
  if (!form.url.trim().startsWith("https://")) {
    issues.push("the endpoint must be an HTTPS URL");
  }
  try {
    const parsed = new URL(form.url.trim());
    if (parsed.username || parsed.password) {
      issues.push("the endpoint must not include userinfo credentials");
    }
    if (parsed.search) {
      issues.push("the endpoint must not include a query string");
    }
    if (parsed.hash) {
      issues.push("the endpoint must not include a fragment");
    }
  } catch {
    issues.push("the endpoint must be a valid HTTPS URL");
  }
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(form.secretEnv.trim())) {
    issues.push(
      "the secret reference must be a valid environment variable name",
    );
  }
  if (form.events.length === 0) {
    issues.push("select at least one supported event");
  }
  const timeout = Number(form.timeoutSeconds);
  if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 120) {
    issues.push("the timeout must be between 0.1 and 120 seconds");
  }
  const attempts = Number(form.maxAttempts);
  if (!Number.isInteger(attempts) || attempts < 1 || attempts > 20) {
    issues.push("max attempts must be between 1 and 20");
  }
  const baseRetry = Number(form.baseRetrySeconds);
  const maxRetry = Number(form.maxRetrySeconds);
  if (
    !Number.isFinite(baseRetry) ||
    baseRetry <= 0 ||
    baseRetry > 86400 ||
    !Number.isFinite(maxRetry) ||
    maxRetry <= 0 ||
    maxRetry > 86400 ||
    maxRetry < baseRetry
  ) {
    issues.push(
      "the retry bounds must be positive seconds and the maximum at least the base",
    );
  }
  return issues;
}

export function NotificationEditorPage() {
  const { webhookId } = useParams({
    from: "/operations/notifications/editor/$webhookId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<WebhookFormState | null>(null);
  const [confirmActivate, setConfirmActivate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  const draftQuery = useQuery(notificationDraftQueryOptions(token, webhookId));

  const draftData = draftQuery.data;
  const loadedDraft =
    draftData !== undefined && draftData.ok ? draftData.model.draft : null;
  // The form state is derived per Draft revision: the first render of a given
  // revision seeds the bounded form from the durable document, and every edit
  // updates that exact revision's form. No effect re-seeds it.
  const currentForm: WebhookFormState | null =
    form !== null &&
    loadedDraft !== null &&
    form.revisionId === loadedDraft.revisionId
      ? form
      : loadedDraft !== null
        ? {
            revisionId: loadedDraft.revisionId,
            url: loadedDraft.webhook.url,
            secretEnv: loadedDraft.webhook.secretEnv,
            events: loadedDraft.webhook.events,
            enabled: loadedDraft.webhook.enabled,
            timeoutSeconds: String(loadedDraft.webhook.timeoutSeconds),
            maxAttempts: String(loadedDraft.webhook.maxAttempts),
            baseRetrySeconds: String(loadedDraft.webhook.baseRetrySeconds),
            maxRetrySeconds: String(loadedDraft.webhook.maxRetrySeconds),
          }
        : null;
  const updateForm = (patch: Partial<WebhookFormState>) => {
    if (currentForm !== null) {
      setForm({ ...currentForm, ...patch });
    }
  };

  const draftMutation = useMutation({
    mutationFn: (activeRevisionId: string) =>
      createNotificationSuccessorDraft(token, { activeRevisionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        return;
      }
      setError(
        `Starting the successor Draft was rejected (${result.code}). Reload and try again; nothing is retried automatically.`,
      );
    },
  });

  const saveMutation = useMutation({
    mutationFn: (input: {
      revisionId: string;
      expectedVersion: number;
      object: Record<string, unknown>;
    }) =>
      saveWebhookDefinitionDraft(token, {
        revisionId: input.revisionId,
        webhookId,
        expectedVersion: input.expectedVersion,
        object: input.object,
      }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        setConfirmActivate(false);
        return;
      }
      setError(
        result.status === 409
          ? "The Draft changed before the save was applied. Refresh the Draft and apply the change again; the winning revision was preserved."
          : `Saving the Draft was rejected (${result.code}). The server validator rejected the form or the Draft is stale. Reload and try again; nothing is retried automatically.`,
      );
    },
  });

  const validateMutation = useMutation({
    mutationFn: (revisionId: string) =>
      validateAutomationDraft(token, { revisionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        return;
      }
      setError(
        `Validation was rejected (${result.code}). Reload the Draft and try again; validation is zero-mutation.`,
      );
    },
  });

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
          ? "The displayed revision is stale, so no test request was sent. Refresh the Draft and test the exact current revision again."
          : `The test was rejected (${result.code}). Read the current durable state and try again; nothing is retried automatically.`,
      );
    },
  });

  const activateMutation = useMutation({
    mutationFn: (input: {
      expectedRevisionId: string;
      expectedVersion: number;
    }) =>
      activateWebhookDraft(token, {
        webhookId,
        expectedRevisionId: input.expectedRevisionId,
        expectedVersion: input.expectedVersion,
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setConfirmActivate(false);
    },
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        void navigate({
          to: "/operations/notifications/webhooks/$webhookId",
          params: { webhookId },
        });
        return;
      }
      setError(
        result.status === 409
          ? "Activation was rejected: the Draft changed, another Webhook definition or another configuration section changed, or the Active base moved. Nothing was activated; reload the Draft and stage a fresh, Webhook-only change."
          : `Activation was rejected (${result.code}). Read the current durable state and try again; nothing is retried automatically.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={draftQuery}
      unavailableTitle="Webhook Draft unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Draft">
              <p>Reading the open successor Draft and its exact version.</p>
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
                  to="/operations/notifications/webhooks/$webhookId"
                  params={{ webhookId }}
                >
                  Back to the definition
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const draftDocument = data.model;
        const draft = draftDocument.draft;
        if (draft === null) {
          const createDraft = draftDocument.actions.createDraft;
          return (
            <div className="mf-dashboard">
              <header className="mf-dashboard-head">
                <div>
                  <h2>Edit Webhook definition</h2>
                  <p className="mf-dashboard-meta">
                    No open successor Draft contains this Webhook definition.
                  </p>
                </div>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </header>
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={!createDraft.available || draftMutation.isPending}
                  onClick={() => {
                    if (draftDocument.activeConfiguration !== null) {
                      draftMutation.mutate(
                        draftDocument.activeConfiguration.revisionId,
                      );
                    }
                  }}
                >
                  {draftMutation.isPending
                    ? "Starting successor Draft…"
                    : "Start successor Draft"}
                </Button>
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/notifications/webhooks/$webhookId"
                  params={{ webhookId }}
                >
                  Back to the definition
                </Link>
              </div>
              {!createDraft.available && createDraft.reason && (
                <StatusBanner variant="info" title="Draft start unavailable">
                  <p>{createDraft.reason}</p>
                </StatusBanner>
              )}
              {error !== null && (
                <StatusBanner variant="error" title="Draft not started">
                  <p>{error}</p>
                </StatusBanner>
              )}
            </div>
          );
        }
        const save = draftDocument.actions.save;
        const validate = draftDocument.actions.validate;
        const activate = draftDocument.actions.activate;
        const test = draftDocument.actions.test;
        const issues = currentForm === null ? [] : formIssues(currentForm);
        const buildObject = (): Record<string, unknown> => ({
          id: draft.webhook.id,
          url: currentForm?.url.trim() ?? draft.webhook.url,
          secretEnv: currentForm?.secretEnv.trim() ?? draft.webhook.secretEnv,
          events: currentForm?.events ?? draft.webhook.events,
          enabled: currentForm?.enabled ?? draft.webhook.enabled,
          timeoutSeconds: Number(currentForm?.timeoutSeconds ?? 10),
          maxAttempts: Number(currentForm?.maxAttempts ?? 5),
          baseRetrySeconds: Number(currentForm?.baseRetrySeconds ?? 5),
          maxRetrySeconds: Number(currentForm?.maxRetrySeconds ?? 300),
        });
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Edit Webhook definition</h2>
                <p className="mf-dashboard-meta">
                  Draft revision {draft.revisionId} · version{" "}
                  {draft.revisionVersion} · {draft.revisionStatus} · the Active
                  configuration is unchanged until checked activation.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {draft.validationErrors.length > 0 && (
              <StatusBanner variant="error" title="Draft validation findings">
                <ul>
                  {draft.validationErrors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Bounded Webhook form</h3>
              <p className="mf-label">
                <label htmlFor="notification-edit-url">HTTPS endpoint</label>
              </p>
              <input
                id="notification-edit-url"
                value={currentForm?.url ?? ""}
                onChange={(event) => updateForm({ url: event.target.value })}
                maxLength={2048}
              />
              <p className="mf-label">
                <label htmlFor="notification-edit-secret">
                  Secret environment reference
                </label>
              </p>
              <input
                id="notification-edit-secret"
                value={currentForm?.secretEnv ?? ""}
                onChange={(event) =>
                  updateForm({ secretEnv: event.target.value })
                }
                maxLength={128}
              />
              <fieldset>
                <legend>Supported events</legend>
                {draftDocument.supportedEvents.map((event) => (
                  <label key={event} style={{ display: "block" }}>
                    <input
                      type="checkbox"
                      checked={(currentForm?.events ?? []).includes(event)}
                      aria-label={`Event ${event}`}
                      onChange={(changeEvent) => {
                        const existing = currentForm?.events ?? [];
                        if (changeEvent.target.checked) {
                          updateForm({ events: [...existing, event] });
                        } else {
                          updateForm({
                            events: existing.filter((item) => item !== event),
                          });
                        }
                      }}
                    />{" "}
                    {event}
                  </label>
                ))}
              </fieldset>
              <p className="mf-label">
                <label htmlFor="notification-edit-enabled">Enabled</label>
              </p>
              <select
                id="notification-edit-enabled"
                value={(currentForm?.enabled ?? false) ? "yes" : "no"}
                onChange={(event) =>
                  updateForm({ enabled: event.target.value === "yes" })
                }
              >
                <option value="no">disabled</option>
                <option value="yes">enabled</option>
              </select>
              <p className="mf-label">
                <label htmlFor="notification-edit-timeout">
                  Timeout seconds (0.1–120)
                </label>
              </p>
              <input
                id="notification-edit-timeout"
                value={currentForm?.timeoutSeconds ?? ""}
                onChange={(event) =>
                  updateForm({ timeoutSeconds: event.target.value })
                }
                inputMode="decimal"
              />
              <p className="mf-label">
                <label htmlFor="notification-edit-attempts">
                  Max attempts (1–20)
                </label>
              </p>
              <input
                id="notification-edit-attempts"
                value={currentForm?.maxAttempts ?? ""}
                onChange={(event) =>
                  updateForm({ maxAttempts: event.target.value })
                }
                inputMode="numeric"
              />
              <p className="mf-label">
                <label htmlFor="notification-edit-base-retry">
                  Base retry seconds
                </label>
              </p>
              <input
                id="notification-edit-base-retry"
                value={currentForm?.baseRetrySeconds ?? ""}
                onChange={(event) =>
                  updateForm({ baseRetrySeconds: event.target.value })
                }
                inputMode="decimal"
              />
              <p className="mf-label">
                <label htmlFor="notification-edit-max-retry">
                  Max retry seconds
                </label>
              </p>
              <input
                id="notification-edit-max-retry"
                value={currentForm?.maxRetrySeconds ?? ""}
                onChange={(event) =>
                  updateForm({ maxRetrySeconds: event.target.value })
                }
                inputMode="decimal"
              />
            </section>
            <div className="mf-actions">
              <Button
                type="button"
                disabled={
                  !save.available || issues.length > 0 || saveMutation.isPending
                }
                onClick={() => {
                  if (draft !== null && currentForm !== null) {
                    saveMutation.mutate({
                      revisionId: draft.revisionId,
                      expectedVersion: draft.revisionVersion,
                      object: buildObject(),
                    });
                  }
                }}
              >
                {saveMutation.isPending ? "Saving Draft…" : "Save into Draft"}
              </Button>
              <Button
                type="button"
                disabled={!validate.available || validateMutation.isPending}
                onClick={() => validateMutation.mutate(draft.revisionId)}
              >
                {validateMutation.isPending
                  ? "Validating Draft…"
                  : "Validate Draft"}
              </Button>
            </div>
            {issues.length > 0 && (
              <StatusBanner variant="info" title="Form incomplete">
                <ul>
                  {issues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              </StatusBanner>
            )}
            {validateMutation.isSuccess && validateMutation.data.ok && (
              <StatusBanner variant="success" title="Draft validated">
                <p>
                  The Draft validated with no findings and zero mutation.
                  Activate explicitly to publish this exact change.
                </p>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Explicit endpoint test</h3>
              <p className="mf-dashboard-meta">
                {test.available
                  ? "Sends exactly one signed test request bound to the displayed revision identity and version. The configuration digest and the resolved secret stay server-side; no delivery is created."
                  : `Test unavailable: ${test.reason ?? "not advertised"}`}
              </p>
              {test.available && (
                <div className="mf-actions">
                  <Button
                    type="button"
                    disabled={testMutation.isPending}
                    onClick={() =>
                      testMutation.mutate({
                        expectedRevisionId: draft.revisionId,
                        expectedVersion: draft.revisionVersion,
                      })
                    }
                  >
                    {testMutation.isPending
                      ? "Sending signed test…"
                      : "Test this exact Draft revision"}
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
              <h3>Checked activation</h3>
              <p className="mf-dashboard-meta">
                {activate.available
                  ? "Activation publishes this exact Draft only when its sole change is this reviewed Webhook definition. Any sibling definition or unrelated configuration change rejects the activation and preserves Active and Draft. No delivery is created."
                  : `Activation unavailable: ${activate.reason ?? "not advertised"}`}
              </p>
              {activate.available && (
                <div className="mf-actions">
                  <label>
                    <input
                      type="checkbox"
                      checked={confirmActivate}
                      aria-label="Confirm checked activation"
                      onChange={(event) =>
                        setConfirmActivate(event.target.checked)
                      }
                    />{" "}
                    I confirm this exact Webhook-only Draft as the new Active
                    configuration
                  </label>
                  <Button
                    type="button"
                    disabled={
                      !confirmActivate ||
                      activateMutation.isPending ||
                      draft.revisionStatus !== "validated"
                    }
                    onClick={() =>
                      activateMutation.mutate({
                        expectedRevisionId: draft.revisionId,
                        expectedVersion: draft.revisionVersion,
                      })
                    }
                  >
                    {activateMutation.isPending
                      ? "Activating Draft…"
                      : "Activate checked Draft"}
                  </Button>
                </div>
              )}
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/notifications/webhooks/$webhookId"
                params={{ webhookId }}
              >
                Back to the definition
              </Link>
            </div>
            {error !== null && (
              <StatusBanner variant="error" title="Draft action not completed">
                <p>{error}</p>
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
