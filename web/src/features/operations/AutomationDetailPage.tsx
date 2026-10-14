/**
 * V2 Automation definition detail page.
 *
 * Shows the exact immutable Active identity, the distinct open successor Draft
 * with its optimistic version, truthful schedule/occurrence state, the
 * unattended grant state with the backend's admission eligibility, and only
 * the cooperative actions the backend advertises for the exact principal.
 * Grant requires an explicit confirmation; revocation is exact-object and
 * never rewrites completed effects. Reading mutates nothing.
 *
 * The durable exact-Preview admission carries a client-generated request
 * identity: a lost or malformed response is an *unknown* durable outcome, so
 * the exact context is retained (principal-scoped) and reconciled by its own
 * request id before any resubmission is offered.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  admitDefinitionPreviewAnalysis,
  reconcilePreviewAnalysis,
  createAutomationSuccessorDraft,
  copyAutomationDefinition,
  grantAutomationAuthority,
  revokeAutomationAuthority,
} from "../../shared/api/api-client";
import { newRequestId } from "../../shared/api/request-id";
import { useAuthGeneration } from "../../shared/api/auth-context";
import { fetchAuthenticatedPrincipal } from "../../shared/api/api-client";
import {
  registerPrincipalSessionDataCleaner,
} from "../../shared/auth/principal-session-data";
import {
  principalIdStorageSegment,
} from "../../shared/auth/principal-identity";
import {
  automationDefinitionQueryKey,
  automationDefinitionQueryOptions,
} from "./automation-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import { describeAutomationRunMode } from "../../entities/operations/automation";

const PREVIEW_ANALYSIS_INTENT_PREFIX =
  "mediaflow.operations.automation-preview-analysis:";

function previewAnalysisIntentSessionKey(principalId: string): string {
  return `${PREVIEW_ANALYSIS_INTENT_PREFIX}${principalIdStorageSegment(principalId)}`;
}

interface PendingPreviewAnalysis {
  readonly definitionId: string;
  readonly requestId: string;
}

function readPendingPreviewAnalysis(
  principalId: string | null,
): PendingPreviewAnalysis | null {
  if (principalId === null || typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(
      previewAnalysisIntentSessionKey(principalId),
    );
    if (raw === null) return null;
    const value = JSON.parse(raw) as unknown;
    if (value === null || typeof value !== "object") return null;
    const source = value as Record<string, unknown>;
    if (
      typeof source.definitionId !== "string" ||
      typeof source.requestId !== "string" ||
      source.requestId.length === 0
    ) {
      return null;
    }
    return {
      definitionId: source.definitionId,
      requestId: source.requestId,
    };
  } catch {
    return null;
  }
}

function writePendingPreviewAnalysis(
  principalId: string | null,
  intent: PendingPreviewAnalysis | null,
): void {
  if (typeof window === "undefined") return;
  try {
    if (principalId === null) return;
    const key = previewAnalysisIntentSessionKey(principalId);
    if (intent === null) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, JSON.stringify(intent));
    }
  } catch {
    // Persisting the reconciliation context is best-effort: the operator can
    // always reconcile from the durable Automation history after a reconnect.
  }
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  const storage = window.sessionStorage;
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(PREVIEW_ANALYSIS_INTENT_PREFIX)) keys.push(key);
  }
  for (const key of keys) storage.removeItem(key);
});

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
  const authGeneration = useAuthGeneration();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmGrant, setConfirmGrant] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The principal identity the backend confirms for this token: the retained
  // exact-Preview intent's session key is scoped to it, so another principal's
  // unknown outcome can never be reconciled as this one's result.
  const principalQuery = useQuery({
    queryKey: ["authenticated-principal", authGeneration],
    queryFn: () => fetchAuthenticatedPrincipal(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 60_000,
  });
  const principalId =
    principalQuery.data !== undefined ? (principalQuery.data.principalId ?? null) : null;

  const [pendingPreviewAnalysisOverride, setPendingPreviewAnalysisState] =
    useState<PendingPreviewAnalysis | null>(null);
  const pendingPreviewAnalysis =
    pendingPreviewAnalysisOverride ??
    readPendingPreviewAnalysis(principalId);
  const setPendingPreviewAnalysis = (intent: PendingPreviewAnalysis | null) => {
    setPendingPreviewAnalysisState(intent);
    writePendingPreviewAnalysis(principalId, intent);
  };

  const detailQuery = useQuery(
    automationDefinitionQueryOptions(token, definitionId),
  );

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: [automationDefinitionQueryKey],
    });
  };

  const previewMutation = useMutation({
    mutationFn: () => {
      const requestId = newRequestId();
      if (requestId !== null) {
        const intent: PendingPreviewAnalysis = { definitionId, requestId };
        writePendingPreviewAnalysis(principalId, intent);
        setPendingPreviewAnalysis(intent);
      }
      return admitDefinitionPreviewAnalysis(token, {
        definitionId,
        admissionRequestId: requestId,
      });
    },
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok && result.model !== undefined) {
        setPendingPreviewAnalysis(null);
        writePendingPreviewAnalysis(principalId, null);
        void navigate({
          to: "/operations/automation/preview-analyses/$analysisId",
          params: { analysisId: result.model.analysisId },
        });
        return;
      }
      const unknown =
        result.status === 0 ||
        result.status >= 500 ||
        result.code === "malformed_response";
      if (unknown && pendingPreviewAnalysis !== null) {
        // The outcome is unknown, not absent: keep the retained intent so the
        // operator can deliberately reconcile it before any resubmission.
        setError(
          "精确预览的响应未能送达或无法解读,无法确定后端是否已经受理。" +
            "已受理的分析是持久的;请先使用“核对上次请求”,不要重复提交。",
        );
        return;
      }
      setPendingPreviewAnalysis(null);
      writePendingPreviewAnalysis(principalId, null);
      setError(
        `Creating the Preview was rejected (${result.code}). Reload the current state and try again; nothing is retried automatically.`,
      );
    },
  });

  // Reconcile the retained unknown exact-Preview admission from durable truth.
  // This never creates work: it reads back the analysis the client's own
  // request id actually produced, or reports a bounded absence.
  const reconcilePreviewMutation = useMutation({
    mutationFn: (intent: PendingPreviewAnalysis) =>
      reconcilePreviewAnalysis(token, { admissionRequestId: intent.requestId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok && result.model !== undefined) {
        setPendingPreviewAnalysis(null);
        writePendingPreviewAnalysis(principalId, null);
        void navigate({
          to: "/operations/automation/preview-analyses/$analysisId",
          params: { analysisId: result.model.analysisId },
        });
        return;
      }
      if (result.code === "preview_analysis_request_not_found") {
        // A proved absence: the original request never became durable work,
        // so the retained intent can be discarded and a fresh request offered.
        setPendingPreviewAnalysis(null);
        writePendingPreviewAnalysis(principalId, null);
        setError(
          "上次精确预览的请求没有在后端形成任何持久工作(响应在受理前丢失)。" +
            "现在可以重新发起精确预览。",
        );
        return;
      }
      setError(
        `核对上次精确预览失败(${result.code ?? "unknown"})。${
          result.nextAction ?? "请稍后重试核对,不要重复提交。"
        }`,
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
                  {definition.definitionState === "historical" && (
                    <>removed · retained history · </>
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
                <dd>{describeAutomationRunMode(doc.mode)}</dd>
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
                {pendingPreviewAnalysis !== null ? (
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={reconcilePreviewMutation.isPending}
                    onClick={() =>
                      reconcilePreviewMutation.mutate(pendingPreviewAnalysis)
                    }
                  >
                    {reconcilePreviewMutation.isPending
                      ? "核对中..."
                      : "核对上次请求"}
                  </Button>
                ) : null}
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
