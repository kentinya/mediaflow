/**
 * V2 Webhook definition create form.
 *
 * The form composes the existing managed configuration object route: the
 * bounded document is stored inside the exact open successor Draft at its
 * advertised optimistic version. Only canonical Webhook fields are submitted;
 * the server's canonical validator rejects unknown fields, literal secrets,
 * unsafe schemes and credential-bearing endpoint components, so the client
 * mirrors those bounds for friction-free input but never becomes the
 * authority. A created definition stays a Draft until checked activation.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { createWebhookDefinition } from "../../shared/api/api-client";
import {
  notificationListQueryKey,
  notificationListQueryOptions,
} from "./notification-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

const SECRET_ENV_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;

function unsafeUrlReason(value: string): string | null {
  if (!value.startsWith("https://")) {
    return "the endpoint must be an HTTPS URL";
  }
  try {
    const parsed = new URL(value);
    if (parsed.username || parsed.password) {
      return "the endpoint must not include userinfo credentials";
    }
    if (parsed.search) {
      return "the endpoint must not include a query string";
    }
    if (parsed.hash) {
      return "the endpoint must not include a fragment";
    }
    return null;
  } catch {
    return "the endpoint must be a valid HTTPS URL";
  }
}

export function NotificationNewPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [webhookId, setWebhookId] = useState("");
  const [url, setUrl] = useState("");
  const [secretEnv, setSecretEnv] = useState("");
  const [events, setEvents] = useState<readonly string[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [timeoutSeconds, setTimeoutSeconds] = useState("10");
  const [maxAttempts, setMaxAttempts] = useState("5");
  const [baseRetrySeconds, setBaseRetrySeconds] = useState("5");
  const [maxRetrySeconds, setMaxRetrySeconds] = useState("300");
  const [error, setError] = useState<string | null>(null);

  const query = useQuery(notificationListQueryOptions(token));

  const createMutation = useMutation({
    mutationFn: (input: {
      revisionId: string;
      expectedVersion: number;
      object: Record<string, unknown>;
    }) =>
      createWebhookDefinition(token, {
        revisionId: input.revisionId,
        expectedVersion: input.expectedVersion,
        object: input.object,
      }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        // The bound model is the exact created identity; it never falls back
        // to a local value when the response carries no created definition.
        void navigate({
          to: "/operations/notifications/webhooks/$webhookId",
          params: { webhookId: result.model.id },
        });
        return;
      }
      setError(
        result.status === 409
          ? "The Draft changed before the definition was stored. Reload and apply the change again; the winning revision was preserved."
          : `Creating the Webhook definition was rejected (${result.code}). Correct the form and try again; nothing is retried automatically.`,
      );
    },
  });

  const formIssues: string[] = [];
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(webhookId)) {
    formIssues.push("the identifier must be 1-64 URI-safe characters");
  }
  const urlProblem = unsafeUrlReason(url.trim());
  if (urlProblem !== null) {
    formIssues.push(urlProblem);
  }
  if (!SECRET_ENV_PATTERN.test(secretEnv)) {
    formIssues.push(
      "the secret reference must be a valid environment variable name",
    );
  }
  if (events.length === 0) {
    formIssues.push("select at least one supported event");
  }
  const timeout = Number(timeoutSeconds);
  if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 120) {
    formIssues.push("the timeout must be between 0.1 and 120 seconds");
  }
  const attempts = Number(maxAttempts);
  if (!Number.isInteger(attempts) || attempts < 1 || attempts > 20) {
    formIssues.push("max attempts must be between 1 and 20");
  }
  const baseRetry = Number(baseRetrySeconds);
  const maxRetry = Number(maxRetrySeconds);
  if (
    !Number.isFinite(baseRetry) ||
    baseRetry <= 0 ||
    baseRetry > 86400 ||
    !Number.isFinite(maxRetry) ||
    maxRetry <= 0 ||
    maxRetry > 86400 ||
    maxRetry < baseRetry
  ) {
    formIssues.push(
      "the retry bounds must be positive seconds and the maximum at least the base",
    );
  }

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Notification definitions unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading definitions">
              <p>Reading the open successor Draft state.</p>
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
        const create = page.actions.create;
        const draft = page.draftState;
        const draftReady = draft.present && create.available;
        const buildObject = (): Record<string, unknown> => ({
          id: webhookId.trim(),
          url: url.trim(),
          secretEnv: secretEnv.trim(),
          events: [...events],
          enabled,
          timeoutSeconds: timeout,
          maxAttempts: attempts,
          baseRetrySeconds: baseRetry,
          maxRetrySeconds: maxRetry,
        });
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>New Webhook definition</h2>
                <p className="mf-dashboard-meta">
                  The definition is stored inside the open successor Draft and
                  stays a Draft until checked activation. Only the
                  deployment-owned secret reference is stored — never a secret
                  value.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {!draftReady && (
              <StatusBanner variant="info" title="No editable Draft">
                <p>
                  {create.reason ??
                    "an open successor Draft is required to add a Webhook definition"}
                </p>
                <div className="mf-actions">
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations/notifications"
                  >
                    Back to Notifications
                  </Link>
                </div>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Bounded Webhook form</h3>
              <p className="mf-label">
                <label htmlFor="notification-new-id">Identifier</label>
              </p>
              <input
                id="notification-new-id"
                value={webhookId}
                onChange={(event) => setWebhookId(event.target.value)}
                maxLength={64}
              />
              <p className="mf-label">
                <label htmlFor="notification-new-url">HTTPS endpoint</label>
              </p>
              <input
                id="notification-new-url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                maxLength={2048}
                placeholder="https://example.invalid/hooks/mediaflow"
              />
              <p className="mf-label">
                <label htmlFor="notification-new-secret">
                  Secret environment reference
                </label>
              </p>
              <input
                id="notification-new-secret"
                value={secretEnv}
                onChange={(event) => setSecretEnv(event.target.value)}
                maxLength={128}
                placeholder="MEDIAFLOW_WEBHOOK_SECRET"
              />
              <fieldset>
                <legend>Supported events</legend>
                {page.supportedEvents.map((event) => (
                  <label key={event} style={{ display: "block" }}>
                    <input
                      type="checkbox"
                      checked={events.includes(event)}
                      aria-label={`Event ${event}`}
                      onChange={(changeEvent) => {
                        if (changeEvent.target.checked) {
                          setEvents([...events, event]);
                        } else {
                          setEvents(events.filter((item) => item !== event));
                        }
                      }}
                    />{" "}
                    {event}
                  </label>
                ))}
              </fieldset>
              <p className="mf-label">
                <label htmlFor="notification-new-enabled">Enabled</label>
              </p>
              <select
                id="notification-new-enabled"
                value={enabled ? "yes" : "no"}
                onChange={(event) => setEnabled(event.target.value === "yes")}
              >
                <option value="yes">enabled</option>
                <option value="no">disabled</option>
              </select>
              <p className="mf-label">
                <label htmlFor="notification-new-timeout">
                  Timeout seconds (0.1–120)
                </label>
              </p>
              <input
                id="notification-new-timeout"
                value={timeoutSeconds}
                onChange={(event) => setTimeoutSeconds(event.target.value)}
                inputMode="decimal"
              />
              <p className="mf-label">
                <label htmlFor="notification-new-attempts">
                  Max attempts (1–20)
                </label>
              </p>
              <input
                id="notification-new-attempts"
                value={maxAttempts}
                onChange={(event) => setMaxAttempts(event.target.value)}
                inputMode="numeric"
              />
              <p className="mf-label">
                <label htmlFor="notification-new-base-retry">
                  Base retry seconds
                </label>
              </p>
              <input
                id="notification-new-base-retry"
                value={baseRetrySeconds}
                onChange={(event) => setBaseRetrySeconds(event.target.value)}
                inputMode="decimal"
              />
              <p className="mf-label">
                <label htmlFor="notification-new-max-retry">
                  Max retry seconds
                </label>
              </p>
              <input
                id="notification-new-max-retry"
                value={maxRetrySeconds}
                onChange={(event) => setMaxRetrySeconds(event.target.value)}
                inputMode="decimal"
              />
            </section>
            <div className="mf-actions">
              <Button
                type="button"
                disabled={
                  !draftReady ||
                  formIssues.length > 0 ||
                  createMutation.isPending
                }
                onClick={() => {
                  if (draft.revisionId !== null) {
                    createMutation.mutate({
                      revisionId: draft.revisionId,
                      expectedVersion: draft.revisionVersion ?? 0,
                      object: buildObject(),
                    });
                  }
                }}
              >
                {createMutation.isPending
                  ? "Creating definition…"
                  : "Create definition in Draft"}
              </Button>
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/notifications"
              >
                Back to Notifications
              </Link>
            </div>
            {formIssues.length > 0 && (
              <StatusBanner variant="info" title="Form incomplete">
                <ul>
                  {formIssues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              </StatusBanner>
            )}
            {error !== null && (
              <StatusBanner variant="error" title="Definition not created">
                <p>{error}</p>
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
