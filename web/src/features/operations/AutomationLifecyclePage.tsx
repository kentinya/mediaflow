/**
 * Native V2 Automation definition lifecycle page.
 *
 * One typed form and one checked `保存` publish the intended successor: the
 * backend composes it from the exact observed Active, validates the whole
 * document, runs the applicable checks and atomically activates it. The operator
 * never orchestrates Draft/Validate/Activate, and this page never claims a
 * Draft is Active. Enable/disable, copy and removal are separate explicit
 * lifecycle commands with their own durable outcomes; removal evidence and
 * unattended-authority state come from the backend projection. Reads create
 * nothing, and every mutation disables automatic retry so an ambiguous outcome
 * is reconciled by reading durable truth rather than by replaying the request.
 *
 * Form state, retained input and the command target are all bound to the
 * current definition route context, and the candidate carries its own observed
 * authority: navigating between definition routes — including Copy navigation —
 * never applies one definition's unsaved input or observed authority fence to
 * another definition. Refresh never silently repins a retained candidate onto a
 * newer Active identity: the stale candidate must be deliberately re-reviewed
 * before it can publish again.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken, useAuthGeneration } from "../../shared/api/auth-context";
import { newRequestId } from "../../shared/api/request-id";
import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";
import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import {
  admitAutomationRunOnce,
  copyAutomationDefinitionFocused,
  createAutomationDefinitionFocused,
  fetchAutomationCopyCandidate,
  fetchAutomationCopyIntent,
  fetchAutomationEditProjection,
  fetchAutomationFormAuthority,
  fetchAutomationRemovalImpact,
  fetchAuthenticatedPrincipal,
  previewAutomationSchedule,
  removeAutomationDefinitionFocused,
  saveAutomationDefinitionFocused,
  setAutomationDefinitionEnabledFocused,
} from "../../shared/api/api-client";
import { automationListQueryKey } from "./automation-query";
import {
  AUTOMATION_AUTOMATIC_ORGANIZATION_MODE,
  AUTOMATION_RUN_MODES,
  isRecordedAutomationRunMode,
  type AutomationDocumentRunMode,
  type AutomationRunMode,
} from "../../entities/operations/automation";
import type { AutomationEditProjectionModel } from "../../entities/operations/automation-lifecycle";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

interface FormState {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly resourceLibraryId: string;
  readonly mode: AutomationDocumentRunMode;
  readonly sourceScope: string;
  readonly itemLimit: string;
  readonly scheduleType: "interval" | "cron";
  readonly intervalSeconds: string;
  readonly cron: string;
  readonly timezone: string;
}

const NEW_FORM: FormState = {
  id: "",
  name: "",
  enabled: false,
  resourceLibraryId: "",
  mode: AUTOMATION_AUTOMATIC_ORGANIZATION_MODE,
  sourceScope: "",
  itemLimit: "100",
  scheduleType: "interval",
  intervalSeconds: "3600",
  cron: "",
  timezone: "UTC",
};

/**
 * The route context a form instance belongs to. Form state never outlives its
 * context: switching from editing one definition to another (including Copy
 * navigation) discards the previous context's unsaved input instead of
 * letting a Save publish it against the new definition.
 */
type FormContextKey = string;

/**
 * The exact Active identity the retained candidate was composed against. The
 * command fence always comes from this snapshot, never from the latest
 * authority query: a refresh that observed a newer Active must not silently
 * give the old candidate a newer publication fence.
 */
interface CandidateAuthority {
  readonly revisionId: string;
  readonly version: number;
  readonly digest: string;
}

interface FormEntry {
  readonly key: FormContextKey;
  readonly form: FormState;
  readonly authority: CandidateAuthority;
}

/**
 * Typed schedule conveniences. Daily/weekly compile to the exact Cron
 * semantics the Scheduler already consumes; advanced Cron remains available.
 */
type ScheduleConvenience = "interval" | "daily" | "weekly" | "cron";

function convenienceOf(form: FormState): ScheduleConvenience {
  if (form.scheduleType === "interval") return "interval";
  if (form.cron.trim() === "0 8 * * *") return "daily";
  if (form.cron.trim() === "0 8 * * 1") return "weekly";
  return "cron";
}

const DAILY_CRON = "0 8 * * *";
const WEEKLY_CRON = "0 8 * * 1";

function buildCandidate(form: FormState): Record<string, unknown> {
  return {
    id: form.id.trim(),
    name: form.name.trim(),
    enabled: form.enabled,
    resourceLibraryId: form.resourceLibraryId,
    mode: form.mode,
    itemLimit: Number(form.itemLimit),
    // The scope field is always submitted: clearing the input publishes the
    // cleared value (the ResourceLibrary root) instead of silently keeping a
    // previously stored scope.
    sourceScope: form.sourceScope.trim(),
    ...(form.scheduleType === "interval"
      ? {
          intervalSeconds: Number(form.intervalSeconds),
          cron: null,
          timezone: null,
        }
      : {
          intervalSeconds: null,
          cron: form.cron.trim(),
          timezone: form.timezone.trim(),
        }),
  };
}

/** A supported interval value: any finite positive decimal number. */
const INTERVAL_PATTERN = /^\d+(\.\d+)?$/;

function formIsValid(form: FormState, editing: boolean): boolean {
  const itemLimit = Number(form.itemLimit);
  const intervalValue = Number(form.intervalSeconds);
  return (
    (editing || form.id.trim().length > 0) &&
    // A definition that still records a removed mode stays readable as
    // history, but it cannot be published: the operator must deliberately
    // choose the retained mode first. Nothing is rewritten silently.
    !isRecordedAutomationRunMode(form.mode) &&
    form.name.trim().length > 0 &&
    form.resourceLibraryId.length > 0 &&
    /^\d+$/.test(form.itemLimit) &&
    Number.isFinite(itemLimit) &&
    itemLimit > 0 &&
    (form.scheduleType === "interval"
      ? INTERVAL_PATTERN.test(form.intervalSeconds) &&
        Number.isFinite(intervalValue) &&
        intervalValue > 0
      : form.cron.trim().length > 0 && form.timezone.trim().length > 0)
  );
}

/**
 * The submitted-but-unconfirmed Copy intent, bounded to identity and the
 * observed authority — no token, secret or reusable execution authority is
 * persisted. It survives a real page reload because a lost Copy response is an
 * unknown durable outcome: until it is reconciled, no second Copy is offered.
 * The key is principal-scoped and cleared when the active principal changes,
 * exactly like the existing recovery-batch session context.
 */
interface PendingCopyIntent {
  readonly sourceId: string;
  readonly authority: CandidateAuthority;
}

const COPY_INTENT_SESSION_PREFIX =
  "mediaflow.operations.automation-copy-intent:";

function copyIntentSessionKey(principalId: string): string {
  return `${COPY_INTENT_SESSION_PREFIX}${principalIdStorageSegment(principalId)}`;
}

function readPendingCopyIntent(
  principalId: string | null,
): PendingCopyIntent | null {
  if (principalId === null || typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(
      copyIntentSessionKey(principalId),
    );
    if (raw === null) return null;
    const value = JSON.parse(raw) as unknown;
    if (
      value === null ||
      typeof value !== "object" ||
      typeof (value as Record<string, unknown>).sourceId !== "string"
    ) {
      return null;
    }
    const source = value as Record<string, unknown>;
    const authority = source.authority;
    if (
      authority === null ||
      typeof authority !== "object" ||
      typeof (authority as Record<string, unknown>).revisionId !== "string" ||
      typeof (authority as Record<string, unknown>).version !== "number" ||
      typeof (authority as Record<string, unknown>).digest !== "string"
    ) {
      return null;
    }
    const boundedAuthority = authority as Record<string, unknown>;
    return {
      sourceId: source.sourceId as string,
      authority: {
        revisionId: boundedAuthority.revisionId as string,
        version: boundedAuthority.version as number,
        digest: boundedAuthority.digest as string,
      },
    };
  } catch {
    return null;
  }
}

function writePendingCopyIntent(
  principalId: string | null,
  intent: PendingCopyIntent | null,
): void {
  if (typeof window === "undefined") return;
  try {
    if (principalId === null) return;
    const key = copyIntentSessionKey(principalId);
    if (intent === null) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(
        key,
        JSON.stringify({
          sourceId: intent.sourceId,
          authority: intent.authority,
        }),
      );
    }
  } catch {
    // Persisting the reconciliation context is best-effort: the operator can
    // always reconcile from the durable inventory after a reconnect.
  }
}

registerPrincipalSessionDataCleaner(() => {
  if (typeof window === "undefined") return;
  const storage = window.sessionStorage;
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(COPY_INTENT_SESSION_PREFIX)) keys.push(key);
  }
  for (const key of keys) storage.removeItem(key);
});

export function AutomationLifecyclePage() {
  const token = useAuthToken();
  const authGeneration = useAuthGeneration();
  // The principal identity the backend confirms for this token: the pending
  // Copy intent's session key is scoped to it, so another principal's unknown
  // outcome can never be reconciled as this one's result.
  const principalQuery = useQuery({
    queryKey: ["authenticated-principal", authGeneration],
    queryFn: () => fetchAuthenticatedPrincipal(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const principalId = principalQuery.data?.principalId ?? null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const params = useParams({ strict: false }) as { definitionId?: string };
  const definitionId = params.definitionId;
  const editing = typeof definitionId === "string" && definitionId.length > 0;
  // The exact route context this page's form and commands belong to.
  const formContextKey: FormContextKey = definitionId ?? "__new__";

  const authorityQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-authority"],
    queryFn: () => fetchAutomationFormAuthority(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const editQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-edit", definitionId ?? ""],
    queryFn: () => fetchAutomationEditProjection(token, definitionId ?? ""),
    enabled: token !== null && editing,
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Form state carries its context key AND the authority snapshot its candidate
  // was composed against. A retained form whose key does not match the current
  // route context is invisible stale input, never the candidate a Save would
  // publish, and its command fence is always its own snapshot.
  const [formEntry, setFormEntry] = useState<FormEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  // One submitted-but-unconfirmed Copy command: while its outcome is unknown,
  // no second Copy is offered until it is reconciled from durable evidence.
  // The intent survives a real page reload (identity + observed authority
  // only, no token or secret), scoped to the confirmed principal. The durable
  // context is read during render from the confirmed principal — an effect
  // cannot guarantee the storage read happens before the first blocked render.
  const [pendingCopyIntentOverride, setPendingCopyIntentState] =
    useState<PendingCopyIntent | null>(null);
  const pendingCopyIntent =
    pendingCopyIntentOverride ?? readPendingCopyIntent(principalId);
  const setPendingCopyIntent = (intent: PendingCopyIntent | null) => {
    setPendingCopyIntentState(intent);
    writePendingCopyIntent(principalId, intent);
  };
  // The reconciliation read for an unknown Copy outcome. A pending intent from
  // any context keeps blocking Copy until it is reconciled deliberately; the
  // stale read key is derived away instead of reset by an effect.
  const [reconcileCopyForState, setReconcileCopyFor] = useState<string | null>(
    null,
  );
  const reconcileCopyFor =
    reconcileCopyForState !== null &&
    pendingCopyIntent !== null &&
    reconcileCopyForState === pendingCopyIntent.sourceId
      ? reconcileCopyForState
      : null;

  const authority = authorityQuery.data;
  const editQueryResult = editQuery.data;
  const authorityModel =
    authority !== undefined && authority.ok ? authority.model : null;
  const editFailed = editQueryResult !== undefined && !editQueryResult.ok;
  const loaded =
    editQueryResult !== undefined && editQueryResult.ok
      ? editQueryResult.model.definition
      : null;
  // A loaded edit projection belongs to this route only when its definition
  // matches the route identity.
  const loadedForRoute =
    loaded !== null &&
    loaded.id === (definitionId ?? "") &&
    formContextKey === (definitionId ?? "")
      ? loaded
      : null;

  const retainedForm: FormState | null =
    formEntry !== null && formEntry.key === formContextKey
      ? formEntry.form
      : null;

  const currentForm: FormState | null =
    retainedForm !== null
      ? retainedForm
      : loadedForRoute !== null
        ? {
            id: loadedForRoute.id,
            name: loadedForRoute.name,
            enabled: loadedForRoute.enabled,
            resourceLibraryId: loadedForRoute.resourceLibraryId,
            mode: loadedForRoute.mode,
            sourceScope: loadedForRoute.sourceScope ?? "",
            itemLimit: String(loadedForRoute.itemLimit),
            scheduleType: loadedForRoute.scheduleType,
            intervalSeconds:
              loadedForRoute.intervalSeconds !== null
                ? String(loadedForRoute.intervalSeconds)
                : "",
            cron: loadedForRoute.cron ?? "",
            timezone: loadedForRoute.timezone ?? "UTC",
          }
        : editing
          ? null
          : NEW_FORM;

  const activeIdentity = authorityModel?.active ?? null;
  const latestAuthority: CandidateAuthority | null =
    activeIdentity !== null
      ? {
          revisionId: activeIdentity.revisionId,
          version: activeIdentity.revisionSequence,
          digest: activeIdentity.digest,
        }
      : null;
  // The command fence: exactly the authority snapshot the retained candidate
  // was composed against. When the operator has not touched the form, the
  // candidate is the freshly loaded definition and its snapshot is the latest
  // observed authority. Once input is retained, the snapshot is pinned to that
  // retained input — a refresh must never silently repin it.
  const candidateAuthority: CandidateAuthority | null =
    formEntry !== null && formEntry.key === formContextKey
      ? formEntry.authority
      : latestAuthority;
  // The retained candidate is stale when the Active moved after this input was
  // observed. It is surfaced truthfully instead of silently repinned: the
  // operator reviews the current values and re-adopts them deliberately.
  const candidateIsStale =
    formEntry !== null &&
    formEntry.key === formContextKey &&
    latestAuthority !== null &&
    (formEntry.authority.revisionId !== latestAuthority.revisionId ||
      formEntry.authority.digest !== latestAuthority.digest);
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: [automationListQueryKey] });
    void queryClient.invalidateQueries({
      queryKey: ["operations.automation-lifecycle-authority"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["operations.automation-lifecycle-edit", definitionId ?? ""],
    });
  };

  const saveMutation = useMutation({
    mutationFn: (input: {
      readonly form: FormState;
      readonly authority: CandidateAuthority;
      readonly targetId: string;
    }) =>
      editing
        ? saveAutomationDefinitionFocused(token, {
            // The route's definition identity is the command target. A
            // retained form can never retarget a Save at another definition,
            // even after Copy navigation changed the route.
            definitionId: input.targetId,
            object: buildCandidate({ ...input.form, id: input.targetId }),
            authority: {
              expectedRevisionId: input.authority.revisionId,
              expectedVersion: input.authority.version,
              expectedDigest: input.authority.digest,
            },
          })
        : createAutomationDefinitionFocused(token, {
            object: buildCandidate(input.form),
            authority: {
              expectedRevisionId: input.authority.revisionId,
              expectedVersion: input.authority.version,
              expectedDigest: input.authority.digest,
            },
          }),
    retry: false,
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (result) => {
      if (result.ok) {
        setNotice(
          result.model.action === "remove"
            ? "The definition was removed and its future unattended authority was revoked."
            : "The published definition is the Active configuration consumed by runtime.",
        );
        invalidate();
        if (result.model.definition?.id) {
          void navigate({
            to: "/operations/automation/lifecycle/$definitionId",
            params: { definitionId: result.model.definition.id },
          });
        }
        return;
      }
      setError(
        result.status === 409
          ? "The command was rejected because the Active configuration changed. Refresh and review durable state before submitting again; nothing is retried automatically."
          : `The command was rejected (${result.code}). Read the current durable state and try again.`,
      );
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly enabled: boolean;
      readonly authority: CandidateAuthority;
    }) =>
      setAutomationDefinitionEnabledFocused(token, {
        definitionId: input.id,
        enabled: input.enabled,
        authority: {
          expectedRevisionId: input.authority.revisionId,
          expectedVersion: input.authority.version,
          expectedDigest: input.authority.digest,
        },
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (result) => {
      if (result.ok) {
        setNotice(
          result.model.definition?.enabled
            ? "The definition is enabled and eligible for future Scheduler evaluation; no work was started."
            : "The definition is disabled; future scheduled emission stops at the checked boundary and admitted work is unchanged.",
        );
        invalidate();
        return;
      }
      setError(
        `The state change was rejected (${result.code}). Refresh and review state.`,
      );
    },
  });

  const copyMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly authority: CandidateAuthority;
    }) =>
      copyAutomationDefinitionFocused(token, {
        definitionId: input.id,
        authority: {
          expectedRevisionId: input.authority.revisionId,
          expectedVersion: input.authority.version,
          expectedDigest: input.authority.digest,
        },
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (result, input) => {
      if (result.ok) {
        setNotice(
          "The copy was published as a new, disabled definition without authority.",
        );
        setPendingCopyIntent(null);
        invalidate();
        if (result.model.definition?.id) {
          void navigate({
            to: "/operations/automation/lifecycle/$definitionId",
            params: { definitionId: result.model.definition.id },
          });
        }
        return;
      }
      if (result.status === 0 || result.code === "transport_unavailable") {
        // The response was lost: the command may or may not have committed.
        // This is an unknown outcome, never a rejection. Keep the submitted
        // intent — including the exact authority it was submitted against —
        // and require reconciliation before any resubmission.
        setPendingCopyIntent({
          sourceId: input.id,
          authority: input.authority,
        });
        setError(
          "Copying the definition returned no confirmed outcome (transport_unavailable). The copy may or may not have been published; reconcile before submitting Copy again.",
        );
        return;
      }
      setError(`Copying the definition was rejected (${result.code}).`);
    },
  });

  const copyIntentQuery = useQuery({
    queryKey: [
      "operations.automation-lifecycle-copy-intent",
      reconcileCopyFor ?? "",
    ],
    queryFn: () => {
      const intent = pendingCopyIntent;
      const params = new URLSearchParams();
      if (intent !== null && intent.sourceId === reconcileCopyFor) {
        params.set("expectedRevisionId", intent.authority.revisionId);
        params.set("expectedVersion", String(intent.authority.version));
        params.set("expectedDigest", intent.authority.digest);
      }
      const query = params.toString();
      return fetchAutomationCopyIntent(
        token,
        reconcileCopyFor ?? "",
        fetch,
        query.length > 0 ? `?${query}` : "",
      );
    },
    enabled: token !== null && reconcileCopyFor !== null,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const removeMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly authority: CandidateAuthority;
    }) =>
      removeAutomationDefinitionFocused(token, {
        definitionId: input.id,
        authority: {
          expectedRevisionId: input.authority.revisionId,
          expectedVersion: input.authority.version,
          expectedDigest: input.authority.digest,
        },
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setNotice(null);
      setConfirmRemove(false);
    },
    onSuccess: (result) => {
      if (result.ok) {
        setNotice(
          "The definition was removed; grants, audits and run history were retained and future unattended authority was revoked.",
        );
        invalidate();
        void navigate({ to: "/operations/automation" });
        return;
      }
      setError(
        `Removal was rejected (${result.code}). The Active definition and its authority state are reported above.`,
      );
    },
  });

  const previewMutation = useMutation({
    mutationFn: (candidate: Record<string, unknown>) =>
      previewAutomationSchedule(token, {
        candidate,
        objectId: definitionId ?? null,
      }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (!result.ok) {
        setError(`Schedule preview was rejected (${result.code}).`);
      }
    },
  });

  const removalQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-removal", definitionId ?? ""],
    queryFn: () => fetchAutomationRemovalImpact(token, definitionId ?? ""),
    enabled: token !== null && editing,
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Definition-bound Run once.  The published definition itself supplies the
  // ResourceLibrary and source sub-scope, so this action sends no file
  // selection: the backend discovers and freezes the complete bounded manifest.
  // It never enables the schedule, grants authority or mutates Storage.
  const runOnceMutation = useMutation({
    mutationFn: (id: string) =>
      admitAutomationRunOnce(token, {
        definitionId: id,
        admissionRequestId: newRequestId(),
      }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result, id) => {
      if (!result.ok || result.model === undefined) {
        setError(
          `Run once was rejected (${result.code ?? "unknown"}). ${result.nextAction ?? "Reload the current state and review the definition bounds."}`,
        );
        return;
      }
      void navigate({
        to: "/operations/automation/run-once/$discoveryId",
        params: { discoveryId: result.model.discoveryId },
      });
      void id;
    },
  });

  const copyCandidateQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-copy", definitionId ?? ""],
    queryFn: () => fetchAutomationCopyCandidate(token, definitionId ?? ""),
    enabled: false,
    retry: false,
  });

  const canManage =
    authorityModel !== null &&
    activeIdentity !== null &&
    activeIdentity.digest.length > 0;
  // The command target for this route's definition-bound commands.
  const routeTargetId = definitionId ?? "";
  const copyBlocked = pendingCopyIntent !== null;

  const convenience =
    currentForm === null ? "interval" : convenienceOf(currentForm);

  return (
    <AuthorizedReadBoundary
      query={authorityQuery}
      unavailableTitle="Automation lifecycle unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined || currentForm === null) {
          if (editing && editFailed) {
            return (
              <StatusBanner
                variant="error"
                title="The definition could not be read"
              >
                <p>
                  {editQueryResult !== undefined && !editQueryResult.ok
                    ? editQueryResult.code === "not_found"
                      ? "This definition is not present in the current Active configuration. Refresh the Automation inventory to find its current identity or history."
                      : `Reading the definition failed (${editQueryResult.code}). Refresh after the Active configuration is available; no input was lost.`
                    : "Reading the definition failed. Refresh after the Active configuration is available."}
                </p>
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
          return (
            <StatusBanner variant="info" title="Loading the definition">
              <p>
                Reading the exact Active Automation authority and typed form.
              </p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner
              variant="error"
              title="Automation authority unavailable"
            >
              <p>
                {data.details?.nextAction ??
                  "Refresh after the Active configuration is available."}
              </p>
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
        const valid = formIsValid(currentForm, editing);
        const update = (patch: Partial<FormState>) =>
          setFormEntry({
            key: formContextKey,
            form: { ...currentForm, ...patch },
            authority:
              candidateAuthority ??
              ({
                revisionId: "",
                version: 0,
                digest: "",
              } as CandidateAuthority),
          });
        // Deliberate re-adoption: replace the stale retained candidate with the
        // current durable values and the authority those exact values were read
        // with. Re-adoption always re-reads the definition first: a cached
        // edit projection may be older than the publication the latest
        // authority reports, and joining cached values to a newer fence would
        // silently overwrite a peer's concurrent edit. The re-read resolves the
        // definition and its own Active identity together, so the offered
        // fence always belongs to the values the operator actually reviewed.
        // Nothing is published by this action; it only makes the reviewed
        // current state the next Save's candidate.
        const adoptCurrentValues = () => {
          void queryClient
            .refetchQueries({
              queryKey: [
                "operations.automation-lifecycle-edit",
                definitionId ?? "",
              ],
              exact: true,
            })
            .then(() => {
              const fresh = queryClient.getQueryData<
                | {
                    readonly ok: true;
                    readonly model: AutomationEditProjectionModel;
                  }
                | { readonly ok: false }
              >(["operations.automation-lifecycle-edit", definitionId ?? ""]);
              if (
                fresh === undefined ||
                !fresh.ok ||
                fresh.model.definition.id !== (definitionId ?? "")
              ) {
                // The definition cannot be re-read right now: discard the
                // stale input instead of repinning it with a fence its
                // values were never read against.
                setFormEntry(null);
                setError(null);
                return;
              }
              const projection = fresh.model;
              const projected = projection.definition;
              setFormEntry({
                key: formContextKey,
                form: {
                  id: projected.id,
                  name: projected.name,
                  enabled: projected.enabled,
                  resourceLibraryId: projected.resourceLibraryId,
                  mode: projected.mode,
                  sourceScope: projected.sourceScope ?? "",
                  itemLimit: String(projected.itemLimit),
                  scheduleType: projected.scheduleType,
                  intervalSeconds:
                    projected.intervalSeconds !== null
                      ? String(projected.intervalSeconds)
                      : "",
                  cron: projected.cron ?? "",
                  timezone: projected.timezone ?? "UTC",
                },
                authority: {
                  revisionId: projection.active.revisionId,
                  version: projection.active.revisionSequence,
                  digest: projection.active.digest,
                },
              });
            });
        };
        const preview = previewMutation.data;
        const previewModel =
          preview !== undefined && preview.ok ? preview.model : null;
        const removal =
          removalQuery.data !== undefined && removalQuery.data.ok
            ? removalQuery.data.model
            : null;
        const copyCandidate =
          copyCandidateQuery.data !== undefined && copyCandidateQuery.data.ok
            ? copyCandidateQuery.data.model
            : null;
        const copyIntent =
          copyIntentQuery.data !== undefined && copyIntentQuery.data.ok
            ? copyIntentQuery.data.model
            : null;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>
                  {editing
                    ? "Edit Automation definition"
                    : "Create Automation definition"}
                </h2>
                <p className="mf-dashboard-meta">
                  One checked 保存 composes the focused successor from the exact
                  Active configuration, validates the whole document and
                  atomically activates it. No separate Draft/Validate/Activate
                  step is required, and unrelated changes never ride along.
                </p>
                {activeIdentity !== null && (
                  <p className="mf-dashboard-meta">
                    Active revision {activeIdentity.revisionId} · version{" "}
                    {activeIdentity.revisionSequence}
                  </p>
                )}
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {candidateIsStale && (
              <StatusBanner
                variant="error"
                title="Your unsaved edits are based on an older configuration"
              >
                <p>
                  The Active configuration changed after this form was filled in
                  (another writer published a change). Saving would use the
                  older identity and be rejected — the current values are never
                  silently replaced by this page. Review the current durable
                  values, then deliberately re-adopt them as your next
                  candidate, or discard your edits.
                </p>
                <div className="mf-actions">
                  <Button type="button" onClick={adoptCurrentValues}>
                    Review current values and re-adopt them
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setFormEntry(null)}
                  >
                    Discard my unsaved edits
                  </Button>
                </div>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Definition</h3>
              {!editing && (
                <>
                  <p className="mf-label">
                    <label htmlFor="lifecycle-id">Definition ID</label>
                  </p>
                  <input
                    id="lifecycle-id"
                    value={currentForm.id}
                    onChange={(event) => update({ id: event.target.value })}
                    maxLength={64}
                  />
                </>
              )}
              <p className="mf-label">
                <label htmlFor="lifecycle-name">Name</label>
              </p>
              <input
                id="lifecycle-name"
                value={currentForm.name}
                onChange={(event) => update({ name: event.target.value })}
                maxLength={120}
              />
              <p className="mf-label">
                <label htmlFor="lifecycle-library">ResourceLibrary</label>
              </p>
              <select
                id="lifecycle-library"
                value={currentForm.resourceLibraryId}
                onChange={(event) =>
                  update({ resourceLibraryId: event.target.value })
                }
              >
                <option value="">select one ResourceLibrary</option>
                {authorityModel?.resourceLibraries.map((option) => (
                  <option
                    key={option.id}
                    value={option.id}
                    disabled={!option.enabled}
                  >
                    {option.name ?? option.id}
                    {option.enabled ? "" : " (disabled)"}
                  </option>
                ))}
              </select>
              <p className="mf-label">
                <label htmlFor="lifecycle-scope">Relative source scope</label>
              </p>
              <input
                id="lifecycle-scope"
                value={currentForm.sourceScope}
                onChange={(event) =>
                  update({ sourceScope: event.target.value })
                }
                placeholder="empty for the ResourceLibrary root"
                maxLength={1024}
              />
              <p className="mf-dashboard-meta">
                Clearing this field and saving publishes the cleared scope: the
                definition then covers the ResourceLibrary root.
              </p>
              <p className="mf-label">
                <label htmlFor="lifecycle-mode">Run mode</label>
              </p>
              <select
                id="lifecycle-mode"
                value={currentForm.mode}
                onChange={(event) =>
                  update({ mode: event.target.value as AutomationRunMode })
                }
              >
                {isRecordedAutomationRunMode(currentForm.mode) && (
                  <option value={currentForm.mode} disabled>
                    {currentForm.mode} (unsupported historical mode)
                  </option>
                )}
                {AUTOMATION_RUN_MODES.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode}
                  </option>
                ))}
              </select>
              {isRecordedAutomationRunMode(currentForm.mode) && (
                <StatusBanner
                  variant="info"
                  title="Unsupported historical run mode"
                >
                  <p>
                    This definition records the removed mode{" "}
                    <strong>{currentForm.mode}</strong>. It is displayed as
                    history only and is never selectable. Choose{" "}
                    {AUTOMATION_AUTOMATIC_ORGANIZATION_MODE} before saving;
                    nothing is rewritten automatically.
                  </p>
                </StatusBanner>
              )}
              <p className="mf-label">
                <label htmlFor="lifecycle-limit">Item limit</label>
              </p>
              <input
                id="lifecycle-limit"
                value={currentForm.itemLimit}
                onChange={(event) => update({ itemLimit: event.target.value })}
                inputMode="numeric"
              />
              <p className="mf-label">
                <label htmlFor="lifecycle-enabled">Enabled</label>
              </p>
              <select
                id="lifecycle-enabled"
                value={currentForm.enabled ? "yes" : "no"}
                onChange={(event) =>
                  update({ enabled: event.target.value === "yes" })
                }
              >
                <option value="no">disabled</option>
                <option value="yes">enabled</option>
              </select>
              {!editing && (
                <p className="mf-dashboard-meta">
                  A new definition is published disabled. Enable it as a
                  separate explicit action after it exists.
                </p>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Schedule</h3>
              <p className="mf-label">
                <label htmlFor="lifecycle-schedule-convenience">Schedule</label>
              </p>
              <select
                id="lifecycle-schedule-convenience"
                value={convenience}
                onChange={(event) => {
                  const value = event.target.value as ScheduleConvenience;
                  if (value === "daily") {
                    update({
                      scheduleType: "cron",
                      cron: DAILY_CRON,
                    });
                    return;
                  }
                  if (value === "weekly") {
                    update({
                      scheduleType: "cron",
                      cron: WEEKLY_CRON,
                    });
                    return;
                  }
                  update({
                    scheduleType: value === "interval" ? "interval" : "cron",
                    cron:
                      value === "cron" &&
                      currentForm.scheduleType === "interval"
                        ? ""
                        : currentForm.cron,
                  });
                }}
              >
                <option value="interval">interval (seconds)</option>
                <option value="daily">daily at 08:00</option>
                <option value="weekly">Mondays at 08:00</option>
                <option value="cron">advanced Cron with IANA timezone</option>
              </select>
              {currentForm.scheduleType === "interval" ? (
                <>
                  <p className="mf-label">
                    <label htmlFor="lifecycle-interval">Interval seconds</label>
                  </p>
                  <input
                    id="lifecycle-interval"
                    value={currentForm.intervalSeconds}
                    onChange={(event) =>
                      update({ intervalSeconds: event.target.value })
                    }
                    inputMode="decimal"
                  />
                  <p className="mf-dashboard-meta">
                    Any positive number of seconds, including fractional values
                    such as 1.5.
                  </p>
                </>
              ) : (
                <>
                  {convenience !== "cron" && (
                    <p className="mf-dashboard-meta">
                      This convenience schedule compiles to the Cron expression
                      below; edit it as advanced Cron for exact control.
                    </p>
                  )}
                  <p className="mf-label">
                    <label htmlFor="lifecycle-cron">Cron expression</label>
                  </p>
                  <input
                    id="lifecycle-cron"
                    value={currentForm.cron}
                    onChange={(event) => update({ cron: event.target.value })}
                    placeholder="0 8 * * *"
                    maxLength={64}
                  />
                  <p className="mf-label">
                    <label htmlFor="lifecycle-timezone">Timezone</label>
                  </p>
                  <input
                    id="lifecycle-timezone"
                    value={currentForm.timezone}
                    onChange={(event) =>
                      update({ timezone: event.target.value })
                    }
                    maxLength={64}
                  />
                </>
              )}
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={!valid || previewMutation.isPending}
                  onClick={() =>
                    previewMutation.mutate(buildCandidate(currentForm))
                  }
                >
                  {previewMutation.isPending
                    ? "Calculating..."
                    : "Preview upcoming times"}
                </Button>
              </div>
              {previewModel !== null && (
                <>
                  <p className="mf-dashboard-meta">
                    {previewModel.scheduleType} schedule · zero mutation ·{" "}
                    {previewModel.timezone ?? "no timezone"}
                  </p>
                  {previewModel.upcoming.length > 0 && (
                    <ul>
                      {previewModel.upcoming.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                  {previewModel.notes.map((note) => (
                    <p className="mf-dashboard-meta" key={note}>
                      {note}
                    </p>
                  ))}
                </>
              )}
            </section>
            <div className="mf-actions">
              <Button
                type="button"
                disabled={
                  !valid ||
                  !canManage ||
                  saveMutation.isPending ||
                  candidateIsStale
                }
                onClick={() =>
                  candidateAuthority !== null &&
                  saveMutation.mutate({
                    form: currentForm,
                    authority: candidateAuthority,
                    targetId: routeTargetId,
                  })
                }
              >
                {saveMutation.isPending ? "Publishing..." : "保存"}
              </Button>
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/automation"
              >
                Back to Automation
              </Link>
            </div>
            {!canManage && (
              <StatusBanner variant="info" title="Save unavailable">
                <p>
                  The exact Active authority could not be read, so no Save is
                  offered. Refresh after Active configuration is available.
                </p>
              </StatusBanner>
            )}
            {editing && (
              <section className="mf-count-section">
                <h3>Lifecycle actions</h3>
                <div className="mf-actions">
                  <Button
                    type="button"
                    disabled={runOnceMutation.isPending}
                    onClick={() => runOnceMutation.mutate(routeTargetId)}
                  >
                    {runOnceMutation.isPending ? "Starting..." : "运行一次"}
                  </Button>
                  <Button
                    type="button"
                    disabled={!canManage || toggleMutation.isPending}
                    onClick={() =>
                      candidateAuthority !== null &&
                      toggleMutation.mutate({
                        id: routeTargetId,
                        enabled: !currentForm.enabled,
                        authority: candidateAuthority,
                      })
                    }
                  >
                    {toggleMutation.isPending
                      ? "Updating..."
                      : currentForm.enabled
                        ? "Disable schedule"
                        : "Enable schedule"}
                  </Button>
                  <Button
                    type="button"
                    disabled={
                      !canManage || copyMutation.isPending || copyBlocked
                    }
                    onClick={() =>
                      candidateAuthority !== null &&
                      copyMutation.mutate({
                        id: routeTargetId,
                        authority: candidateAuthority,
                      })
                    }
                  >
                    {copyMutation.isPending
                      ? "Copying..."
                      : "Copy as disabled definition"}
                  </Button>
                </div>
                {copyCandidate !== null && (
                  <p className="mf-dashboard-meta">
                    Copy candidate {copyCandidate.definition.id} (
                    {copyCandidate.definition.enabled ? "enabled" : "disabled"})
                  </p>
                )}
                {copyBlocked && (
                  <StatusBanner variant="error" title="Copy outcome unknown">
                    <p>
                      The last Copy command for {pendingCopyIntent?.sourceId}{" "}
                      returned no confirmed outcome. It may have been published
                      durably; reconciling allocates no new copy and replays
                      nothing.
                    </p>
                    <div className="mf-actions">
                      {!reconcileCopyFor && (
                        <Button
                          type="button"
                          onClick={() => {
                            setReconcileCopyFor(
                              pendingCopyIntent?.sourceId ?? null,
                            );
                          }}
                        >
                          Reconcile the submitted Copy
                        </Button>
                      )}
                      <Link
                        className="mf-button mf-button-secondary"
                        to="/operations/automation"
                      >
                        Refresh the Automation inventory
                      </Link>
                    </div>
                    {reconcileCopyFor !== null && (
                      <p className="mf-dashboard-meta">
                        {copyIntent === null
                          ? "Reading the durable copy evidence..."
                          : copyIntent.committed
                            ? `The copy committed durably as ${copyIntent.committedDefinitionId}. Refresh the inventory; no second copy is created.`
                            : !copyIntent.evidenceComplete
                              ? "The durable command evidence could not be read completely, so the submitted copy's outcome is still unknown. Reconcile from the current inventory; do not submit another copy for this intent."
                              : copyIntent.observedCommands > 0
                                ? "No durable publication evidence exists for the submitted copy; after refreshing the inventory you may deliberately submit the copy again."
                                : "No submitted copy command was observed in durable evidence; the outcome is genuinely unpublished."}
                      </p>
                    )}
                    {copyIntent?.committed === true && (
                      <div className="mf-actions">
                        <Button
                          type="button"
                          onClick={() => {
                            setPendingCopyIntent(null);
                            setReconcileCopyFor(null);
                            setError(null);
                            if (copyIntent.committedDefinitionId) {
                              void navigate({
                                to: "/operations/automation/lifecycle/$definitionId",
                                params: {
                                  definitionId:
                                    copyIntent.committedDefinitionId,
                                },
                              });
                            }
                          }}
                        >
                          Open the committed copy
                        </Button>
                      </div>
                    )}
                    {copyIntent !== null &&
                      copyIntent.committed === false &&
                      // A genuinely unpublished outcome is proven only when the
                      // durable evidence read was complete: no submitted
                      // command was ever observed for this intent, so the
                      // resubmission block is released. A located command
                      // whose publication could not be proven — or an
                      // incomplete/unavailable evidence read — stays an unknown
                      // outcome: the block holds and the operator reconciles
                      // from the durable inventory instead.
                      copyIntent.evidenceComplete &&
                      copyIntent.observedCommands === 0 && (
                        <div className="mf-actions">
                          <Button
                            type="button"
                            onClick={() => {
                              setPendingCopyIntent(null);
                              setReconcileCopyFor(null);
                              setError(null);
                            }}
                          >
                            Reconciled: no copy was published
                          </Button>
                        </div>
                      )}
                  </StatusBanner>
                )}
                <h3>Reference-safe removal</h3>
                {removal === null ? (
                  <p className="mf-dashboard-meta">
                    Reading removal evidence...
                  </p>
                ) : (
                  <>
                    <p className="mf-dashboard-meta">
                      {removal.referenceTotal} configuration reference(s) ·
                      unattended authority {removal.authorityStatus}
                    </p>
                    <p className="mf-label">
                      <label htmlFor="lifecycle-confirm-removal">
                        Confirm definition removal
                      </label>
                    </p>
                    <label htmlFor="lifecycle-confirm-removal">
                      <input
                        id="lifecycle-confirm-removal"
                        type="checkbox"
                        checked={confirmRemove}
                        onChange={(event) =>
                          setConfirmRemove(event.target.checked)
                        }
                      />{" "}
                      I confirm removing this definition; future scheduling and
                      unattended mutation stop while grants, audits and history
                      are retained
                    </label>
                    <div className="mf-actions">
                      <Button
                        type="button"
                        disabled={
                          !confirmRemove ||
                          !canManage ||
                          removeMutation.isPending
                        }
                        onClick={() =>
                          candidateAuthority !== null &&
                          removeMutation.mutate({
                            id: routeTargetId,
                            authority: candidateAuthority,
                          })
                        }
                      >
                        {removeMutation.isPending
                          ? "Removing..."
                          : "Remove definition"}
                      </Button>
                    </div>
                  </>
                )}
              </section>
            )}
            {notice !== null && (
              <StatusBanner variant="success" title="Published">
                <p>{notice}</p>
              </StatusBanner>
            )}
            {error !== null && (
              <StatusBanner variant="error" title="Command not completed">
                <p>{error}</p>
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
