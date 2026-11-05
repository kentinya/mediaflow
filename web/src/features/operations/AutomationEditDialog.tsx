/**
 * The Automation saved-definition edit dialog.
 *
 * Row 编辑 and the ordinary saved-definition edit deep link open the same
 * shared Chinese card over the Automation list (Slice49 RO-3): one typed
 * `AutomationCreateForm`, one validator, one checked `保存` that publishes the
 * intended successor and returns to the list. The backend composes it from the
 * exact observed Active, validates the whole document and atomically activates
 * it. The definition's ID is immutable and the exact saved values — including
 * arbitrary legal Cron and fractional intervals — are backfilled without being
 * rewritten into a convenience default. The enablement choice is part of the
 * same card: saving publishes the toggled state through the same checked
 * publication boundary. Enable/disable, copy and removal remain separate
 * explicit lifecycle commands with their own durable outcomes; removal
 * evidence and unattended-authority state come from the backend projection.
 *
 * Form state, retained input and the command target are all bound to the
 * current definition route context, and the candidate carries its own observed
 * authority: switching between definitions never applies one definition's
 * unsaved input or observed authority fence to another. Refresh never silently
 * repins a retained candidate onto a newer Active identity. A proved
 * reconciliation proves what the command did at its own revision; the durable
 * current-state evidence decides whether the merged outcome is still current,
 * was later modified, or cannot be confirmed — a proved publication never
 * poses as the present saved state and never receives a new baseline.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { registerPrincipalSessionDataCleaner } from "../../shared/auth/principal-session-data";
import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { usePrincipalIdentity } from "./principal-identity-query";
import {
  reconcileAutomationPublicationFocused,
  copyAutomationDefinitionFocused,
  fetchAutomationCopyCandidate,
  fetchAutomationCopyIntent,
  fetchAutomationEditProjection,
  fetchAutomationFormAuthority,
  fetchAutomationRemovalImpact,
  removeAutomationDefinitionFocused,
  saveAutomationDefinitionFocused,
  setAutomationDefinitionEnabledFocused,
} from "../../shared/api/api-client";
import { automationListQueryKey } from "./automation-query";
import type {
  AutomationPublicationModel,
  AutomationEditProjectionModel,
} from "../../entities/operations/automation-lifecycle";
import type { AutomationDefinitionDocumentModel } from "../../entities/operations/automation";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  AutomationCardDiscardPrompt,
  AutomationCardShell,
  useAutomationCardExit,
} from "./automation-card-shell";
import { AutomationDefinitionFormFields } from "./AutomationDefinitionFormFields";
import {
  buildCandidateFromPublicationForm,
  buildCreateCandidate,
  browserTimeZone,
  createFormFromPublication,
  editFormFromDefinition,
  publicationFormFromCreateForm,
  scheduleKindPatch,
  validateCreateForm,
  type AutomationCreateForm,
  type CreateScheduleKind,
} from "./automation-create-form";
import {
  readPendingAutomationPublication,
  writePendingAutomationPublication,
  type PendingAutomationPublication,
} from "./automation-publication-session";

const COMMAND_ERROR_ID = "automation-edit-command-error";
const DISCARD_CONTINUE_ID = "automation-edit-discard-continue";

type FormState = AutomationCreateForm;

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

export interface AutomationEditDialogProps {
  readonly definitionId: string;
  readonly onClose: () => void;
  /**
   * One confirmed Save for the list feedback: the list refreshes its real
   * rows/statistics, marks the row and explains a filtered-out result.
   */
  readonly onSaved: (definition: AutomationDefinitionDocumentModel) => void;
}

export function AutomationEditDialog({
  definitionId,
  onClose,
  onSaved,
}: AutomationEditDialogProps) {
  const token = useAuthToken();
  const browserZone = useMemo(() => browserTimeZone(), []);
  const principalIdentity = usePrincipalIdentity();
  const principalId = principalIdentity.resolved
    ? principalIdentity.principalId
    : null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const editing = definitionId.length > 0;
  // The exact route context this page's form and commands belong to.
  const formContextKey: FormContextKey = definitionId;

  const [publicationOverride, setPublicationOverride] = useState<{
    owner: string | null;
    value: PendingAutomationPublication | null;
  } | null>(null);
  const pendingPublication =
    publicationOverride?.owner === principalId
      ? publicationOverride.value
      : readPendingAutomationPublication(principalId, "definition");
  const setPendingPublication = (
    value: PendingAutomationPublication | null,
  ) => {
    setPublicationOverride({ owner: principalId, value });
    writePendingAutomationPublication(principalId, "definition", value);
  };

  const authorityQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-authority"],
    queryFn: () => fetchAutomationFormAuthority(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const editQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-edit", definitionId],
    queryFn: () => fetchAutomationEditProjection(token, definitionId),
    enabled: token !== null && editing,
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Form state carries its context key AND the authority snapshot its candidate
  // was composed against. A retained form whose key does not match the current
  // route context is invisible stale input, never the candidate a Save would
  // publish, and its command fence is always its own snapshot.
  const [formEntry, setFormEntry] = useState<FormEntry | null>(null);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showIssues, setShowIssues] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  // One submitted-but-unconfirmed Copy command: while its outcome is unknown,
  // no second Copy is offered until it is reconciled from durable evidence.
  const [pendingCopyIntentOverride, setPendingCopyIntentState] =
    useState<PendingCopyIntent | null>(null);
  const pendingCopyIntent =
    pendingCopyIntentOverride ?? readPendingCopyIntent(principalId);
  const setPendingCopyIntent = (intent: PendingCopyIntent | null) => {
    setPendingCopyIntentState(intent);
    writePendingCopyIntent(principalId, intent);
  };
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
  // matches the route identity. The backfill is exact: the saved values —
  // including arbitrary legal Cron and fractional intervals — are restored
  // without being rewritten into a convenience default, and the ID stays
  // immutable.
  const loadedForRoute =
    loaded !== null && loaded.id === definitionId ? loaded : null;

  const retainedForm: FormState | null =
    formEntry !== null && formEntry.key === formContextKey
      ? formEntry.form
      : null;

  const currentForm: FormState | null =
    retainedForm !== null
      ? retainedForm
      : loadedForRoute !== null
        ? editFormFromDefinition(loadedForRoute, browserZone.timeZone)
        : null;

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
      queryKey: ["operations.automation-lifecycle-edit", definitionId],
    });
  };

  // Only a confirmed command may advance retained input's publication fence.
  // Merge against what was submitted so typing during the request survives.
  // The merged fence comes from the CURRENT Active evidence: a proved
  // publication whose definition has since been modified never hands its own
  // revision to the retained input as a new baseline. Retyped input stays
  // unsaved: dirty is never cleared by a merge alone.
  const acceptPublication = (
    model: AutomationPublicationModel,
    submitted: FormState,
    submittedAuthority: CandidateAuthority,
    key: FormContextKey,
    nextAuthority: CandidateAuthority | null,
    toggleOnly = false,
  ) => {
    const saved = model.definition;
    if (saved === null || nextAuthority === null) return;
    const published: FormState = editFormFromDefinition(
      saved,
      browserZone.timeZone,
    );
    setFormEntry((entry) => {
      if (
        entry !== null &&
        (entry.key !== key ||
          entry.authority.revisionId !== submittedAuthority.revisionId ||
          entry.authority.digest !== submittedAuthority.digest)
      )
        return entry;
      const retained = entry?.form ?? submitted;
      const merged = { ...retained };
      for (const field of Object.keys(published) as (keyof FormState)[]) {
        if (
          (!toggleOnly || field === "enabled") &&
          retained[field] === submitted[field]
        ) {
          Object.assign(merged, { [field]: published[field] });
        }
      }
      return { key, form: merged, authority: nextAuthority };
    });
    queryClient.setQueryData(
      ["operations.automation-lifecycle-authority"],
      (previous: typeof authority) =>
        previous?.ok &&
        previous.model.active.revisionSequence <= nextAuthority.version
          ? {
              ...previous,
              model: { ...previous.model, active: nextAuthority },
            }
          : previous,
    );
  };

  const updateAuthorityCache = (active: {
    readonly revisionId: string;
    readonly revisionSequence: number;
    readonly digest: string;
  }) => {
    queryClient.setQueryData(
      ["operations.automation-lifecycle-authority"],
      (previous: typeof authority) =>
        previous?.ok &&
        previous.model.active.revisionSequence <= active.revisionSequence
          ? { ...previous, model: { ...previous.model, active } }
          : previous,
    );
  };

  const saveMutation = useMutation({
    mutationFn: (input: {
      readonly form: FormState;
      readonly authority: CandidateAuthority;
      readonly targetId: string;
    }) =>
      saveAutomationDefinitionFocused(token, {
        // The route's definition identity is the command target. A retained
        // form can never retarget a Save at another definition, even after
        // Copy navigation changed the route.
        definitionId: input.targetId,
        object: buildCreateCandidate({
          ...input.form,
          id: input.targetId,
        }) as Record<string, unknown>,
        authority: {
          expectedRevisionId: input.authority.revisionId,
          expectedVersion: input.authority.version,
          expectedDigest: input.authority.digest,
        },
      }),
    retry: false,
    onMutate: (input) => {
      setPendingPublication({
        definitionId: input.targetId,
        action: "edit",
        form: publicationFormFromCreateForm({
          ...input.form,
          id: input.targetId,
        }),
        authority: input.authority,
      });
      setError(null);
      setNotice(null);
    },
    onSuccess: (result, input) => {
      if (result.ok) {
        const saved = result.model.definition;
        setPendingPublication(null);
        if (saved === null) {
          setError("保存结果缺少定义内容；请刷新核对当前持久状态。");
          return;
        }
        // Typing made while the command was in flight is preserved: the
        // confirmed outcome merges only the fields the operator has not since
        // retyped, and the card stays open for a deliberate next Save against
        // the new fence. Without post-submit changes the confirmed Save
        // returns to the original list.
        const liveForm = currentFormRef.current;
        const changedAfterSubmit =
          liveForm !== null &&
          JSON.stringify({ ...liveForm, id: input.targetId }) !==
            JSON.stringify({ ...input.form, id: input.targetId });
        if (changedAfterSubmit) {
          acceptPublication(
            result.model,
            input.form,
            input.authority,
            input.targetId,
            {
              revisionId: result.model.active.revisionId,
              version: result.model.active.revisionSequence,
              digest: result.model.active.digest,
            },
          );
          setNotice(
            saved.enabled
              ? "已保存并保持启用：按保存的计划定时运行；你在提交后的新输入已保留，可再次明确保存。"
              : "已保存，当前为停用状态；你在提交后的新输入已保留，可再次明确保存。",
          );
          invalidate();
          return;
        }
        // The confirmed Save returns to the original list: the list refreshes
        // its real rows/statistics and the card closes. Nothing is replayed.
        // The observed Active identity advances to the confirmed publication
        // so an immediate re-open never fences against the older snapshot.
        updateAuthorityCache(result.model.active);
        card.bypassBlockerRef.current = true;
        card.releaseBlockedNavigation();
        onSaved(saved);
        beginExit(onClose);
        return;
      }
      if (
        result.status === 0 ||
        result.status >= 500 ||
        result.code === "malformed_response"
      ) {
        setError("保存结果尚未确认。先核对本次发布；不会自动重发命令。");
        return;
      }
      setPendingPublication(null);
      setError(
        result.status === 409
          ? "当前配置已被其他操作更新，保存命令没有生效。请先核对当前配置再明确重试；不会自动重试。"
          : `保存被拒绝（${result.code}）。请核对当前持久状态后修正重试。`,
      );
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly form: FormState;
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
    onMutate: (input) => {
      setPendingPublication({
        definitionId: input.id,
        action: input.enabled ? "enable" : "disable",
        form: publicationFormFromCreateForm(input.form),
        authority: input.authority,
      });
      setError(null);
      setNotice(null);
    },
    onSuccess: (result, input) => {
      if (result.ok) {
        setPendingPublication(null);
        acceptPublication(
          result.model,
          input.form,
          input.authority,
          input.id,
          {
            revisionId: result.model.active.revisionId,
            version: result.model.active.revisionSequence,
            digest: result.model.active.digest,
          },
          true,
        );
        setNotice(
          result.model.definition?.enabled
            ? "已启用：后续按保存的计划定时运行；启用本身没有启动任务。"
            : "已停用：后续定时准入停止，已受理的工作保持不变。",
        );
        invalidate();
        return;
      }
      if (
        result.status === 0 ||
        result.status >= 500 ||
        result.code === "malformed_response"
      ) {
        setError("启停结果尚未确认。先核对本次发布；不会自动重发命令。");
        return;
      }
      setPendingPublication(null);
      setError(`启停命令被拒绝（${result.code}）。请刷新核对当前状态。`);
    },
  });

  const reconcilePublication = useMutation({
    mutationFn: (pending: PendingAutomationPublication) =>
      reconcileAutomationPublicationFocused(token, pending.definitionId, {
        action: pending.action,
        object: buildCandidateFromPublicationForm(pending.form),
        expectedRevisionId: pending.authority.revisionId,
        expectedVersion: pending.authority.version,
        expectedDigest: pending.authority.digest,
      }),
    retry: false,
    onSuccess: (result, pending) => {
      if (
        result.ok &&
        result.model.state === "published" &&
        result.model.publication !== null
      ) {
        const currentState = result.model.currentState ?? "unreadable";
        const currentActive = result.model.currentActive;
        const published = result.model.publication;
        if (currentState === "current" && currentActive !== null) {
          // The proved publication is still the saved state: the reviewed
          // candidate may adopt the current Active as its exact baseline.
          acceptPublication(
            published,
            createFormFromPublication(pending, browserZone.timeZone),
            pending.authority,
            pending.definitionId,
            {
              revisionId: currentActive.revisionId,
              version: currentActive.revisionSequence,
              digest: currentActive.digest,
            },
            pending.action === "enable" || pending.action === "disable",
          );
          setPendingPublication(null);
          setError(null);
          setNotice(
            "已从持久审计核对本次发布；当前保存状态与之一致。没有重发保存或启停命令。",
          );
          invalidate();
          return;
        }
        // The publication succeeded but the definition has since been
        // modified, is gone, or the current state cannot be read: the old
        // reviewed candidate keeps its own observed authority (never a new
        // baseline), later input is preserved, and the operator decides.
        setPendingPublication(null);
        setError(null);
        setNotice(
          currentState === "modified"
            ? `已从持久审计核对本次发布：命令曾持久发布（当时${published.definition?.enabled ? "启用" : "停用"}）；该定义之后被再次修改，当前保存值与本次发布不同。你的后续输入已保留；请核对当前值后再明确继续。没有重发命令。`
            : currentState === "absent"
              ? "已从持久审计核对本次发布：命令曾持久发布；该定义当前已不在生效配置中（可能已被移除）。你的输入已保留。没有重发命令。"
              : "已从持久审计核对本次发布：命令曾持久发布；当前保存状态暂时无法确认。你的输入已保留；请刷新核对实际状态。没有重发命令。",
        );
        invalidate();
        return;
      }
      setError(
        "本次发布仍未证实。保留输入和未决身份，稍后继续核对；不会自动重发。",
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
        setNotice("副本已发布为新的停用定义，不继承任何授权。");
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
          "复制命令没有收到确认结果（transport_unavailable）。副本可能已经发布，也可能没有；请先核对，再决定是否再次复制。",
        );
        return;
      }
      setError(`复制命令被拒绝（${result.code}）。`);
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
        card.bypassBlockerRef.current = true;
        card.releaseBlockedNavigation();
        beginExit(onClose);
        return;
      }
      setError(
        `移除命令被拒绝（${result.code}）。当前定义与授权状态已在上方显示。`,
      );
    },
  });

  const removalQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-removal", definitionId],
    queryFn: () => fetchAutomationRemovalImpact(token, definitionId),
    enabled: token !== null && editing,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const copyCandidateQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-copy", definitionId],
    queryFn: () => fetchAutomationCopyCandidate(token, definitionId),
    enabled: false,
    retry: false,
  });

  const currentFormRef = useRef<FormState | null>(null);
  useEffect(() => {
    currentFormRef.current = currentForm;
  });

  const card = useAutomationCardExit({
    onClose,
    shouldBlockLeave: () =>
      (dirty && pendingPublication === null) ||
      saveMutation.isPending ||
      toggleMutation.isPending ||
      reconcilePublication.isPending ||
      copyMutation.isPending ||
      removeMutation.isPending,
    isSubmitting: () =>
      saveMutation.isPending ||
      toggleMutation.isPending ||
      copyMutation.isPending ||
      removeMutation.isPending ||
      reconcilePublication.isPending,
    hasUnsavedInput: () => dirty && pendingPublication === null,
    onDiscardCommitted: () => {
      setDirty(false);
      setFormEntry(null);
    },
    firstFieldId: "automation-create-name",
    discardContinueId: DISCARD_CONTINUE_ID,
    focusReturnId: "automation-create-entry",
  });
  const { attemptClose, commitClose, cancelDiscard, beginExit } = card;
  const discardPromptOpen = card.discardPromptOpen;

  // A Copy navigation keeps this card instance mounted under a new definition
  // context: the exit state of the abandoned context must not disable the
  // next one.
  useEffect(() => {
    card.resetExit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formContextKey]);

  const canManage =
    pendingPublication === null &&
    principalId !== null &&
    authorityModel !== null &&
    activeIdentity !== null &&
    activeIdentity.digest.length > 0;
  // The command target for this route's definition-bound commands.
  const routeTargetId = definitionId;
  const copyBlocked = pendingCopyIntent !== null;
  const busy =
    saveMutation.isPending ||
    toggleMutation.isPending ||
    reconcilePublication.isPending ||
    copyMutation.isPending ||
    removeMutation.isPending;

  return (
    <AuthorizedReadBoundary
      query={authorityQuery}
      unavailableTitle="Automation lifecycle unavailable"
    >
      {({ data, isFetching, refresh }) => {
        // The authority read's availability comes first: without it no command
        // can be fenced, so no form is offered even when a definition read.
        if (data !== undefined && !data.ok) {
          return (
            <AutomationCardShell
              layerRef={card.layerRef}
              closing={card.closing}
              busy={false}
              title="自动化编辑暂不可用"
              titleId="automation-edit-title"
              description="无法读取当前配置授权；未提交任何修改。"
              closeLabel="关闭编辑自动化任务"
              closeDisabled={card.closing}
              onRequestClose={attemptClose}
            >
              <StatusBanner variant="error" title="自动化配置不可用">
                <p>
                  {data.details?.nextAction ?? "请在 Active 配置可用后刷新。"}
                </p>
                <div className="mf-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={attemptClose}
                  >
                    返回自动化
                  </Button>
                  <RefreshControl
                    label="刷新"
                    refreshingLabel="刷新中…"
                    onRefresh={refresh}
                    refreshing={isFetching}
                  />
                </div>
              </StatusBanner>
            </AutomationCardShell>
          );
        }
        if (
          data === undefined ||
          currentForm === null ||
          authorityModel === null
        ) {
          if (editing && editFailed) {
            return (
              <AutomationCardShell
                layerRef={card.layerRef}
                closing={card.closing}
                busy={false}
                title="无法打开编辑"
                titleId="automation-edit-title"
                description="未提交任何修改。"
                closeLabel="关闭编辑自动化任务"
                closeDisabled={card.closing}
                onRequestClose={attemptClose}
              >
                <StatusBanner variant="error" title="无法读取该定义">
                  <p>
                    {editQueryResult !== undefined && !editQueryResult.ok
                      ? editQueryResult.code === "not_found"
                        ? "该定义不在当前 Active 配置中。请刷新自动化清单查看其当前身份或历史。"
                        : `读取定义失败（${editQueryResult.code}）。请在 Active 配置可用后刷新；输入没有丢失。`
                      : "读取定义失败。请在 Active 配置可用后刷新。"}
                  </p>
                  <div className="mf-actions">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={attemptClose}
                    >
                      返回自动化
                    </Button>
                    <RefreshControl
                      label="刷新"
                      refreshingLabel="刷新中…"
                      onRefresh={refresh}
                      refreshing={isFetching}
                    />
                  </div>
                </StatusBanner>
              </AutomationCardShell>
            );
          }
          return (
            <AutomationCardShell
              layerRef={card.layerRef}
              closing={card.closing}
              busy={false}
              title="正在读取自动化编辑"
              titleId="automation-edit-title"
              description="正在读取当前的自动化配置与表单授权。"
              closeLabel="关闭编辑自动化任务"
              closeDisabled={card.closing}
              onRequestClose={attemptClose}
            >
              <StatusBanner variant="info" title="正在读取定义">
                <p>正在读取当前的自动化配置与表单授权。</p>
              </StatusBanner>
            </AutomationCardShell>
          );
        }
        const validationIssues = validateCreateForm(
          currentForm,
          authorityModel,
        );
        const valid = validationIssues.length === 0;
        const candidate = buildCreateCandidate(currentForm);
        const scheduleRejected =
          error !== null &&
          error.includes("automation_definition_invalid_field");
        const update = (patch: Partial<FormState>) => {
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
          setDirty(true);
          setNotice(null);
        };
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
              queryKey: ["operations.automation-lifecycle-edit", definitionId],
              exact: true,
            })
            .then(() => {
              const fresh = queryClient.getQueryData<
                | {
                    readonly ok: true;
                    readonly model: AutomationEditProjectionModel;
                  }
                | { readonly ok: false }
              >(["operations.automation-lifecycle-edit", definitionId]);
              if (
                fresh === undefined ||
                !fresh.ok ||
                fresh.model.definition.id !== definitionId
              ) {
                // The definition cannot be re-read right now: discard the
                // stale input instead of repinning it with a fence its
                // values were never read against.
                setFormEntry(null);
                setDirty(false);
                setError(null);
                return;
              }
              const projection = fresh.model;
              setFormEntry({
                key: formContextKey,
                form: editFormFromDefinition(
                  projection.definition,
                  browserZone.timeZone,
                ),
                authority: {
                  revisionId: projection.active.revisionId,
                  version: projection.active.revisionSequence,
                  digest: projection.active.digest,
                },
              });
              setDirty(false);
              setError(null);
            });
        };
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
          <AutomationCardShell
            layerRef={card.layerRef}
            closing={card.closing}
            busy={busy}
            title="编辑自动化任务"
            titleId="automation-edit-title"
            description="修改来源、运行时间与启用状态；保存发布一次经过校验的后继配置，不会扫描或运行媒体文件。运行一次请在任务列表发起。"
            closeLabel="关闭编辑自动化任务"
            closeDisabled={busy || card.closing}
            onRequestClose={attemptClose}
          >
            {pendingPublication !== null && (
              <StatusBanner variant="warning" title="发布结果待核对">
                <p>
                  保留了 {pendingPublication.definitionId}{" "}
                  的本次命令身份。核对只读取审计，不会重新发布。
                </p>
                <Button
                  type="button"
                  disabled={reconcilePublication.isPending || busy}
                  onClick={() =>
                    reconcilePublication.mutate(pendingPublication)
                  }
                >
                  核对本次发布
                </Button>
              </StatusBanner>
            )}
            <div
              className="mf-automation-create-attention"
              data-automation-edit-attention="true"
            >
              {discardPromptOpen && (
                <AutomationCardDiscardPrompt
                  questionId="automation-edit-discard-question"
                  detailId="automation-edit-discard-detail"
                  continueId={DISCARD_CONTINUE_ID}
                  question="表单中有未保存的输入；关闭会丢弃这些修改。"
                  detail="选择「继续填写」保留当前输入并回到原字段；选择「放弃修改」返回自动化列表。"
                  onContinue={cancelDiscard}
                  onDiscard={commitClose}
                />
              )}
              {notice !== null && (
                <p className="mf-automation-create-notice" role="status">
                  {notice}
                </p>
              )}
              {error !== null && (
                <div
                  className="mf-automation-create-alert"
                  id={COMMAND_ERROR_ID}
                  role="alert"
                  tabIndex={-1}
                >
                  <strong>命令未完成</strong>
                  <p>{error}</p>
                </div>
              )}
              {showIssues && validationIssues.length > 0 && (
                <div className="mf-automation-create-alert" role="alert">
                  <strong>有 {validationIssues.length} 处输入需要修正</strong>
                  <ul>
                    {validationIssues.map((issue) => (
                      <li key={`${issue.fieldId}:${issue.message}`}>
                        {issue.label}：{issue.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {candidateIsStale && (
                <StatusBanner
                  variant="error"
                  title="未保存的修改基于较旧的配置"
                >
                  <p>
                    在填写此表单后，Active
                    配置已被其他操作更新。按旧身份提交会被拒绝；本页不会悄悄替换当前值。请先核对当前持久值，再明确采用为下一次候选，或放弃未保存的修改。
                  </p>
                  <div className="mf-actions">
                    <Button type="button" onClick={adoptCurrentValues}>
                      核对当前值并采用
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        setFormEntry(null);
                        setDirty(false);
                      }}
                    >
                      放弃未保存的修改
                    </Button>
                  </div>
                </StatusBanner>
              )}
              {!canManage && (
                <StatusBanner variant="info" title="保存暂不可用">
                  <p>
                    无法读取确切的 Active 授权，因此暂不提供保存。请在 Active
                    配置可用后刷新。
                  </p>
                </StatusBanner>
              )}
            </div>
            <form
              className="mf-automation-create-form"
              onSubmit={(event) => {
                event.preventDefault();
                setShowIssues(true);
                if (
                  !valid ||
                  candidate === null ||
                  !canManage ||
                  candidateIsStale ||
                  candidateAuthority === null
                ) {
                  if (!valid) {
                    const first = validationIssues[0];
                    if (first !== undefined) {
                      window.requestAnimationFrame(() => {
                        document.getElementById(first.fieldId)?.focus();
                      });
                    }
                  }
                  return;
                }
                saveMutation.mutate({
                  form: currentForm,
                  authority: candidateAuthority,
                  targetId: routeTargetId,
                });
              }}
              noValidate
            >
              <div className="mf-automation-create-scroll">
                <AutomationDefinitionFormFields
                  mode="edit"
                  form={currentForm}
                  authority={authorityModel}
                  issues={validationIssues}
                  showIssues={showIssues}
                  scheduleRejected={scheduleRejected}
                  onPatch={update}
                  onScheduleKind={(kind: CreateScheduleKind) =>
                    update(scheduleKindPatch(currentForm, kind))
                  }
                />

                <details className="mf-automation-create-diagnostics">
                  <summary>诊断信息（内部 ID 与发布机制）</summary>
                  <dl>
                    <dt>内部 ID</dt>
                    <dd>
                      <code id="automation-edit-id" tabIndex={-1}>
                        {currentForm.id}
                      </code>{" "}
                      （固定不变）
                    </dd>
                    <dt>保存依据的 Active</dt>
                    <dd>
                      <code>
                        {candidateAuthority?.revisionId ?? "尚未读取"}
                      </code>
                      {candidateAuthority !== null && (
                        <>
                          {" "}
                          · 版本 {candidateAuthority.version} · digest{" "}
                          <code className="mf-automation-create-digest">
                            {candidateAuthority.digest}
                          </code>
                        </>
                      )}
                    </dd>
                    <dt>发布机制</dt>
                    <dd>
                      一次「保存」从当前读取的 Active
                      组合出精确后继并原子发布，无需单独的
                      Draft/验证/激活步骤，无关修改也不会捎带发布。
                    </dd>
                    {authorityModel.executionEffects && (
                      <>
                        <dt>已保存策略的可用效果</dt>
                        <dd>
                          {authorityModel.executionEffects.operations.join(
                            "、",
                          )}
                          。
                          {authorityModel.executionEffects.overwrite
                            ? "策略允许的覆盖仍需已有明确许可。"
                            : "不允许覆盖现有目标。"}
                          {authorityModel.executionEffects.sourceCleanup
                            ? "包含策略明确允许的源目录清理。"
                            : "不清理源目录。"}
                        </dd>
                      </>
                    )}
                  </dl>
                </details>

                <section className="mf-count-section">
                  <h3>生命周期操作</h3>
                  <div className="mf-actions">
                    <Button
                      type="button"
                      disabled={!canManage || toggleMutation.isPending}
                      onClick={() =>
                        candidateAuthority !== null &&
                        toggleMutation.mutate({
                          id: routeTargetId,
                          form: currentForm,
                          enabled: !currentForm.enabled,
                          authority: candidateAuthority,
                        })
                      }
                    >
                      {toggleMutation.isPending
                        ? "更新中…"
                        : currentForm.enabled
                          ? "停用定时计划"
                          : "启用定时计划"}
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
                      {copyMutation.isPending ? "复制中…" : "复制为停用定义"}
                    </Button>
                    <RefreshControl
                      label="刷新"
                      refreshingLabel="刷新中…"
                      onRefresh={refresh}
                      refreshing={isFetching}
                    />
                  </div>
                  {copyCandidate !== null && (
                    <p className="mf-dashboard-meta">
                      副本候选 {copyCandidate.definition.id}（
                      {copyCandidate.definition.enabled ? "已启用" : "已停用"}）
                    </p>
                  )}
                  {copyBlocked && (
                    <StatusBanner variant="error" title="复制结果未知">
                      <p>
                        最近一次对 {pendingCopyIntent?.sourceId}{" "}
                        的复制命令没有确认结果，可能已经持久发布。核对不会创建新副本，也不会重放命令。
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
                            核对已提交的复制
                          </Button>
                        )}
                      </div>
                      {reconcileCopyFor !== null && (
                        <p className="mf-dashboard-meta">
                          {copyIntent === null
                            ? "正在读取持久复制证据…"
                            : copyIntent.committed
                              ? `副本已持久发布为 ${copyIntent.committedDefinitionId}。请刷新清单；不会创建第二个副本。`
                              : !copyIntent.evidenceComplete
                                ? "持久命令证据无法完整读取，因此已提交副本的结果仍未知。请从当前清单核对；不要为这次意图再提交复制。"
                                : copyIntent.observedCommands > 0
                                  ? "持久证据中不存在已提交副本的发布证明；刷新清单后可以明确再次提交复制。"
                                  : "持久证据中没有观察到已提交的复制命令；结果确为未发布。"}
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
                            打开已发布的副本
                          </Button>
                        </div>
                      )}
                      {copyIntent !== null &&
                        copyIntent.committed === false &&
                        // A genuinely unpublished outcome is proven only when
                        // the durable evidence read was complete: no submitted
                        // command was ever observed for this intent, so the
                        // resubmission block is released. A located command
                        // whose publication could not be proven — or an
                        // incomplete/unavailable evidence read — stays unknown:
                        // the block holds and the operator reconciles from the
                        // durable inventory instead.
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
                              已核对：未发布副本
                            </Button>
                          </div>
                        )}
                    </StatusBanner>
                  )}
                  <h3>引用安全的移除</h3>
                  {removal === null ? (
                    <p className="mf-dashboard-meta">正在读取移除影响证据…</p>
                  ) : (
                    <>
                      <p className="mf-dashboard-meta">
                        {removal.referenceTotal} 个配置引用
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
                        我确认移除此定义；后续定时与剩余定时效果在安全边界停止；审计与历史保留
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
                          {removeMutation.isPending ? "移除中…" : "移除定义"}
                        </Button>
                      </div>
                    </>
                  )}
                </section>
              </div>

              <footer className="mf-automation-create-footer">
                <div className="mf-automation-create-footer-note">
                  {saveMutation.isPending ? (
                    <span role="status">
                      正在保存，请稍候；系统不会自动重发保存命令。
                    </span>
                  ) : pendingPublication !== null ? (
                    <span role="status">
                      请先核对上次发布结果；系统不会自动重发命令。
                    </span>
                  ) : (
                    <span>
                      保存发布后返回自动化列表；运行一次请在任务列表对已保存的定义发起。
                    </span>
                  )}
                </div>
                <div className="mf-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy || card.closing}
                    onClick={attemptClose}
                  >
                    {pendingPublication !== null && !busy ? "关闭" : "取消"}
                  </Button>
                  {saveMutation.isPending ? (
                    <Button
                      type="button"
                      data-automation-edit-primary="true"
                      disabled
                    >
                      保存中…
                    </Button>
                  ) : (
                    <Button
                      type="submit"
                      data-automation-edit-primary="true"
                      disabled={
                        !valid ||
                        candidate === null ||
                        !canManage ||
                        saveMutation.isPending ||
                        candidateIsStale ||
                        card.closing
                      }
                    >
                      保存
                    </Button>
                  )}
                </div>
              </footer>
            </form>
          </AutomationCardShell>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
