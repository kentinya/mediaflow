/**
 * V2 Automation definition detail page.
 *
 * Shows the exact immutable Active identity, the distinct open successor Draft
 * with its optimistic version, truthful schedule/occurrence state, the
 * unattended grant state with the backend's admission eligibility, and only
 * the cooperative actions the backend advertises for the exact principal.
 * Grant requires an explicit confirmation; revocation is exact-object and
 * never rewrites completed effects. Reading mutates nothing.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  createAutomationPreview,
  createAutomationSuccessorDraft,
  copyAutomationDefinition,
  grantAutomationAuthority,
  revokeAutomationAuthority,
} from "../../shared/api/api-client";
import {
  automationDefinitionQueryKey,
  automationDefinitionQueryOptions,
} from "./automation-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function AutomationDetailPage() {
  const { definitionId } = useParams({
    from: "/operations/automation/definition/$definitionId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmGrant, setConfirmGrant] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const detailQuery = useQuery(
    automationDefinitionQueryOptions(token, definitionId),
  );

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: [automationDefinitionQueryKey],
    });
  };

  const previewMutation = useMutation({
    mutationFn: () => createAutomationPreview(token, { definitionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void navigate({
          to: "/operations/automation/preview/$definitionId/$previewId",
          params: { definitionId, previewId: result.model.previewId },
        });
        return;
      }
      setError(
        `Creating the Preview was rejected (${result.code}). Reload the current state and try again; nothing is retried automatically.`,
      );
    },
  });

  const draftMutation = useMutation({
    mutationFn: (activeRevisionId: string) =>
      createAutomationSuccessorDraft(token, { activeRevisionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        invalidate();
        return;
      }
      setError(
        `Starting the successor Draft was rejected (${result.code}). Reload and try again; nothing is retried automatically.`,
      );
    },
  });

  const copyMutation = useMutation({
    mutationFn: (input: { revisionId: string; expectedVersion: number }) =>
      copyAutomationDefinition(token, {
        definitionId,
        revisionId: input.revisionId,
        expectedVersion: input.expectedVersion,
      }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        if (result.model.id) {
          void navigate({
            to: "/operations/automation/definition/$definitionId",
            params: { definitionId: result.model.id },
          });
        }
        return;
      }
      setError(
        `Copying the definition was rejected (${result.code}). Reload and try again; nothing is retried automatically.`,
      );
    },
  });

  const grantMutation = useMutation({
    mutationFn: (previewId: string) =>
      grantAutomationAuthority(token, { definitionId, previewId }),
    retry: false,
    onMutate: () => {
      setError(null);
      setConfirmGrant(false);
    },
    onSuccess: (result) => {
      if (result.ok) {
        invalidate();
        return;
      }
      setError(
        `The grant was rejected (${result.code}). Read the current eligibility and try again; nothing is retried automatically.`,
      );
    },
  });

  const revokeMutation = useMutation({
    mutationFn: () => revokeAutomationAuthority(token, { definitionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        invalidate();
        return;
      }
      setError(
        `The revocation was rejected (${result.code}). Reload the durable grant state and try again.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={detailQuery}
      unavailableTitle="Automation definition unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading definition">
              <p>Reading the durable definition and its state.</p>
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
                  to="/operations/automation"
                >
                  Back to Automation
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const definition = data.model;
        const doc = definition.document;
        const grant = definition.grant;
        const eligibility = definition.grantEligibility;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Automation definition {doc.name}</h2>
                <p className="mf-dashboard-meta">
                  {doc.id} ·{" "}
                  {definition.definitionState === "draft-only" && (
                    <>draft-only · </>
                  )}
                  {definition.activeConfiguration
                    ? `Active revision ${definition.activeConfiguration.revisionId} · version ${definition.activeConfiguration.version}`
                    : "no Active configuration"}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {definition.draftState.present && (
              <StatusBanner variant="info" title="Open successor Draft">
                <p>
                  Draft revision {definition.draftState.revisionId} (version{" "}
                  {definition.draftState.revisionVersion},{" "}
                  {definition.draftState.revisionStatus}) contains this
                  definition. The Active configuration is unchanged until an
                  explicit checked activation.
                </p>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Definition</h3>
              <dl>
                <dt>State</dt>
                <dd>{doc.enabled ? "enabled" : "disabled"}</dd>
                <dt>Mode</dt>
                <dd>{displayEnum(doc.mode)}</dd>
                <dt>Schedule</dt>
                <dd>
                  {doc.scheduleType === "interval"
                    ? `interval: every ${doc.intervalSeconds} seconds`
                    : `cron: ${doc.cron} (${doc.timezone})`}
                </dd>
                <dt>ResourceLibrary</dt>
                <dd>{doc.resourceLibraryId}</dd>
                <dt>Source scope</dt>
                <dd>{doc.sourceScope ?? "ResourceLibrary root"}</dd>
                <dt>Item limit</dt>
                <dd>{doc.itemLimit}</dd>
              </dl>
            </section>
            <section className="mf-count-section">
              <h3>Schedule and occurrence state</h3>
              <dl>
                <dt>Next run</dt>
                <dd>{definition.nextRunAt ?? "not scheduled"}</dd>
                <dt>Last occurrence</dt>
                <dd>{definition.lastOccurrenceAt ?? "none"}</dd>
                <dt>Last outcome</dt>
                <dd>{definition.lastOutcome ?? "none"}</dd>
                {definition.lastReason && (
                  <>
                    <dt>Last reason</dt>
                    <dd>{definition.lastReason}</dd>
                  </>
                )}
                {definition.lastTaskId && (
                  <>
                    <dt>Last Task</dt>
                    <dd>
                      <Link
                        to="/operations/tasks/$taskId"
                        params={{ taskId: definition.lastTaskId }}
                      >
                        {definition.lastTaskId}
                      </Link>
                    </dd>
                  </>
                )}
              </dl>
              {definition.outcomeSummary && (
                <>
                  <p className="mf-dashboard-meta">
                    {definition.outcomeSummary.boundStatement}
                  </p>
                  {definition.outcomeSummary.attention.length > 0 && (
                    <ul>
                      {definition.outcomeSummary.attention.map((item) => (
                        <li key={`${item.taskId}-${item.itemId}`}>
                          <Link
                            to="/operations/tasks/$taskId"
                            params={{ taskId: item.taskId }}
                          >
                            item {item.itemId}
                          </Link>{" "}
                          · {displayEnum(item.status)}
                          {item.nextAction ? ` · ${item.nextAction}` : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/automation/occurrences/$definitionId"
                  params={{ definitionId }}
                >
                  Occurrence history
                </Link>
              </div>
            </section>
            <section className="mf-count-section">
              <h3>Unattended authority</h3>
              {grant.status === "none" ? (
                <p className="mf-dashboard-meta">
                  No unattended execution grant exists for this definition.
                </p>
              ) : (
                <dl>
                  <dt>Grant state</dt>
                  <dd>{displayEnum(grant.status)}</dd>
                  <dt>Bound Preview</dt>
                  <dd>{grant.previewId ?? "unknown"}</dd>
                  <dt>Max items per run</dt>
                  <dd>{grant.maxItemsPerRun ?? "unbounded"}</dd>
                  <dt>Definition changed since grant</dt>
                  <dd>{grant.definitionChangedSinceGrant ? "yes" : "no"}</dd>
                  {grant.currentPermission && (
                    <>
                      <dt>Granting principal permission</dt>
                      <dd>
                        {displayEnum(grant.currentPermission.status)} ·{" "}
                        {grant.currentPermission.allowed
                          ? "allowed"
                          : "not allowed"}
                      </dd>
                    </>
                  )}
                </dl>
              )}
              <p className="mf-dashboard-meta">{grant.nextAction}</p>
              {eligibility !== null && (
                <p className="mf-dashboard-meta">
                  {eligibility.eligible
                    ? "Grant eligibility: the exact current Preview and current permission satisfy the persisted bounds."
                    : `Grant eligibility: ${eligibility.explanation}`}
                </p>
              )}
              {eligibility !== null &&
                eligibility.eligible &&
                definition.actions.grant.available && (
                  <div className="mf-actions">
                    <label>
                      <input
                        type="checkbox"
                        checked={confirmGrant}
                        aria-label="Confirm unattended execution grant"
                        onChange={(event) =>
                          setConfirmGrant(event.target.checked)
                        }
                      />{" "}
                      I confirm the exact bounded unattended authority
                    </label>
                    <Button
                      type="button"
                      disabled={
                        !confirmGrant ||
                        grantMutation.isPending ||
                        (eligibility.previewId === null &&
                          grant.previewId === null)
                      }
                      onClick={() => {
                        const previewId =
                          grant.status === "active"
                            ? grant.previewId
                            : eligibility.previewId;
                        if (previewId) {
                          grantMutation.mutate(previewId);
                        }
                      }}
                    >
                      {grantMutation.isPending
                        ? "Granting…"
                        : "Grant unattended authority"}
                    </Button>
                  </div>
                )}
              {grant.status === "active" &&
                definition.actions.revoke.available && (
                  <div className="mf-actions">
                    <Button
                      type="button"
                      disabled={revokeMutation.isPending}
                      onClick={() => revokeMutation.mutate()}
                    >
                      {revokeMutation.isPending ? "Revoking…" : "Revoke grant"}
                    </Button>
                  </div>
                )}
              {!definition.actions.grant.available &&
                definition.actions.grant.reason && (
                  <p className="mf-dashboard-meta">
                    {definition.actions.grant.reason}
                  </p>
                )}
            </section>
            <section className="mf-count-section">
              <h3>Definition actions</h3>
              <p className="mf-dashboard-meta">
                {definition.actions.preview.available
                  ? "Create an exact zero-mutation Preview of the Active definition."
                  : `Preview unavailable: ${definition.actions.preview.reason ?? "not advertised"}`}
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={
                    !definition.actions.preview.available ||
                    previewMutation.isPending
                  }
                  onClick={() => previewMutation.mutate()}
                >
                  {previewMutation.isPending
                    ? "Creating Preview…"
                    : "Create exact Preview"}
                </Button>
                {definition.draftState.present ? (
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations/automation/editor/$definitionId"
                    params={{ definitionId }}
                  >
                    Edit successor Draft
                  </Link>
                ) : (
                  <Button
                    type="button"
                    disabled={
                      !definition.actions.draftCreate.available ||
                      draftMutation.isPending
                    }
                    onClick={() => {
                      if (definition.activeConfiguration !== null) {
                        draftMutation.mutate(
                          definition.activeConfiguration.revisionId,
                        );
                      }
                    }}
                  >
                    {draftMutation.isPending
                      ? "Starting successor Draft…"
                      : "Start successor Draft"}
                  </Button>
                )}
                <Button
                  type="button"
                  disabled={
                    !definition.actions.copy.available ||
                    copyMutation.isPending ||
                    definition.draftState.revisionId === null
                  }
                  onClick={() => {
                    if (definition.draftState.revisionId !== null) {
                      copyMutation.mutate({
                        revisionId: definition.draftState.revisionId,
                        expectedVersion:
                          definition.draftState.revisionVersion ?? 0,
                      });
                    }
                  }}
                >
                  {copyMutation.isPending ? "Copying…" : "Copy into Draft"}
                </Button>
                {!definition.actions.copy.available &&
                  definition.actions.copy.reason && (
                    <span className="mf-dashboard-meta">
                      {definition.actions.copy.reason}
                    </span>
                  )}
              </div>
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/automation"
              >
                Back to Automation
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
