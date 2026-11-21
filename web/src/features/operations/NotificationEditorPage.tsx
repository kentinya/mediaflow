/**
 * V2 Webhook definition editor card.
 *
 * The card reads the exact published Active definition with its optimistic
 * version and keeps the saved baseline, unsaved input and the signed-test
 * evidence visibly separate. Applying the tested form validates and publishes
 * one new Active configuration directly; there is no draft save or activation
 * step. Unsaved input is never submitted as if it were the baseline, stale test
 * evidence is discarded when the input or version changes, and a late response
 * never replaces a newer context.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { useAuthGeneration, useAuthToken } from "../../shared/api/auth-context";
import {
  fetchAuthenticatedPrincipal,
  saveWebhookDefinitionDraft,
  testWebhookDefinitionForm,
} from "../../shared/api/api-client";
import { reconcileSystemSettings } from "../../shared/api/configuration-api";
import {
  notificationDraftQueryKey,
  notificationDraftQueryOptions,
  notificationListQueryKey,
} from "./notification-query";
import { useAuthorizedReadAuthorityRecovery } from "../../shared/auth/AuthorizedReadBoundary";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  buildWebhookObject,
  canonicalWebhookForm,
  notificationEventLabel,
  notificationReasonLabel,
  sameWebhookForm,
  webhookFormFromDocument,
  webhookFormIssueFor,
  webhookFormIssues,
  type WebhookFormValues,
  isUnknownCommandResult,
  unknownTestMessage,
} from "./notification-presentation";
import {
  NotificationCard,
  NotificationCardStatus,
  NotificationDiscardPrompt,
  useLastSuccessfulRead,
  useNotificationCardGuard,
} from "./notification-card";
import {
  newNotificationSubmissionId,
  notificationApplyScope,
  readPendingNotificationApply,
  writePendingNotificationApply,
  type PendingNotificationApply,
} from "./notification-publication";

interface SavedDraft {
  readonly revisionId: string;
  readonly version: number;
  readonly status: string;
  readonly values: WebhookFormValues;
}

interface RemoteDraft extends SavedDraft {
  /** Whether the same revision moved or a different draft revision was read. */
  readonly kind: "updated" | "revision";
}

const ALL_FORM_FIELDS = [
  "url",
  "secretEnv",
  "events",
  "timeoutSeconds",
  "maxAttempts",
  "baseRetrySeconds",
  "maxRetrySeconds",
] as const;

const SAVE_BUTTON_ID = "notification-edit-save";

interface ApplyReconciliation {
  readonly state: string;
  readonly committed: boolean;
  readonly committedRevisionId: string | null;
  readonly committedRevisionVersion: number | null;
  readonly currentRevisionId: string | null;
  readonly currentVersion: number | null;
  readonly nextAction: string | null;
}

function optionalNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value)
    ? value
    : null;
}

export function NotificationEditorPage() {
  const { webhookId } = useParams({
    from: "/operations/notifications/editor/$webhookId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<WebhookFormValues | null>(null);
  const [baseline, setBaseline] = useState<SavedDraft | null>(null);
  const [remote, setRemote] = useState<RemoteDraft | null>(null);
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const [showIssues, setShowIssues] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [savePermissionDenied, setSavePermissionDenied] = useState(false);
  const [testResult, setTestResult] = useState<{
    readonly context: string;
    readonly success: boolean;
    readonly evidenceId: string | null;
    readonly message: string;
  } | null>(null);
  const [pendingApply, setPendingApply] =
    useState<PendingNotificationApply | null>(null);
  const [awaitingVerification, setAwaitingVerification] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [reconciliation, setReconciliation] =
    useState<ApplyReconciliation | null>(null);

  const formRef = useRef(form);
  const baselineRef = useRef(baseline);
  const submittedValuesRef = useRef<WebhookFormValues | null>(null);
  const formScrollRef = useRef<HTMLFormElement | null>(null);
  const verifiedSubmissionRef = useRef<string | null>(null);
  const verificationInFlightRef = useRef(false);
  const verifyOutcomeRef = useRef<(pending: PendingNotificationApply) => void>(
    () => {},
  );
  useEffect(() => {
    formRef.current = form;
  }, [form]);
  useEffect(() => {
    baselineRef.current = baseline;
  }, [baseline]);

  const authGeneration = useAuthGeneration();
  const principalQuery = useQuery({
    queryKey: ["authenticated-principal", authGeneration],
    queryFn: () => fetchAuthenticatedPrincipal(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });
  const principalId = principalQuery.data?.principalId ?? null;
  const applyScope = notificationApplyScope("editor", webhookId);

  const draftQuery = useQuery(notificationDraftQueryOptions(token, webhookId));
  useAuthorizedReadAuthorityRecovery(draftQuery);

  const liveDraftModel =
    draftQuery.data?.ok === true ? draftQuery.data.model : null;
  const loadedDraft = useLastSuccessfulRead(liveDraftModel);
  const readDegraded = liveDraftModel === null && loadedDraft !== null;
  const draft = loadedDraft?.draft ?? null;
  const serverValues =
    draft === null ? null : webhookFormFromDocument(draft.webhook);
  const currentForm = form ?? (serverValues !== null ? serverValues : null);
  const saveAvailable = loadedDraft?.actions.save.available === true;
  const readOnlyDraft =
    draft !== null && (!saveAvailable || savePermissionDenied);
  const testContext =
    currentForm === null
      ? ""
      : `${currentForm.url}\u0000${currentForm.secretEnv}`;
  const dirty =
    currentForm !== null &&
    baseline !== null &&
    !sameWebhookForm(currentForm, baseline.values);
  const clean = currentForm !== null && baseline !== null && !dirty;
  const clearEvidence = () => {
    setTestResult(null);
  };

  // Reconcile the durable draft into the local saved baseline. A version or
  // status move with no local edits is adopted directly. A move while local
  // input exists is held as an explicit remote choice; the old input is never
  // silently paired with the new version. Losing the open draft (another
  // administrator published it) and reading a different draft revision must
  // preserve unsaved input instead of clearing or replacing it.
  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    if (loadedDraft === null) return;
    const server = loadedDraft.draft;
    const previous = baselineRef.current;
    const local = formRef.current;
    const hasLocalEdits =
      previous !== null &&
      local !== null &&
      !sameWebhookForm(local, previous.values);

    if (server === null) {
      setRemote(null);
      if (hasLocalEdits) {
        // The read proves there is no open draft, but the operator still owns
        // input made against the old revision. Keep both local input and its
        // original baseline; never bind them to an unread successor draft.
        setSavedNotice(null);
        clearEvidence();
        return;
      }
      setBaseline(null);
      setForm(null);
      return;
    }

    const values = webhookFormFromDocument(server.webhook);
    if (previous === null) {
      setBaseline({
        revisionId: server.revisionId,
        version: server.revisionVersion,
        status: server.revisionStatus,
        values,
      });
      setForm(values);
      setRemote(null);
      setSavedNotice(null);
      clearEvidence();
      return;
    }
    if (previous.revisionId !== server.revisionId) {
      if (hasLocalEdits) {
        setSavedNotice(null);
        clearEvidence();
        setRemote({
          revisionId: server.revisionId,
          version: server.revisionVersion,
          status: server.revisionStatus,
          values,
          kind: "revision",
        });
        return;
      }
      setBaseline({
        revisionId: server.revisionId,
        version: server.revisionVersion,
        status: server.revisionStatus,
        values,
      });
      setForm(values);
      setRemote(null);
      setSavedNotice(null);
      clearEvidence();
      return;
    }
    if (server.revisionVersion < previous.version) {
      // An older durable snapshot cannot replace the version this card has
      // already saved or read; wait for the current read instead.
      return;
    }
    if (
      previous.version === server.revisionVersion &&
      previous.status === server.revisionStatus
    ) {
      return;
    }
    if (!hasLocalEdits) {
      const versionChanged = previous.version !== server.revisionVersion;
      setBaseline({
        revisionId: server.revisionId,
        version: server.revisionVersion,
        status: server.revisionStatus,
        values,
      });
      setForm(values);
      setRemote(null);
      if (versionChanged) {
        setTestResult(null);
      }
      return;
    }
    setTestResult(null);
    setRemote({
      revisionId: server.revisionId,
      version: server.revisionVersion,
      status: server.revisionStatus,
      values,
      kind: "updated",
    });
  }, [
    loadedDraft?.draft?.revisionId,
    loadedDraft?.draft?.revisionVersion,
    loadedDraft?.draft?.revisionStatus,
  ]);
  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  // A fresh successful read is the authority for whether saving is available
  // again. A failed read leaves the 403 state in place so the card cannot
  // present an executable form that the server just denied.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (savePermissionDenied && loadedDraft?.actions.save.available === true) {
      setSavePermissionDenied(false);
    }
  }, [
    draftQuery.dataUpdatedAt,
    loadedDraft?.actions.save.available,
    savePermissionDenied,
  ]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const saveMutation = useMutation({
    mutationFn: (input: {
      revisionId: string;
      expectedVersion: number;
      object: Record<string, unknown>;
      values: WebhookFormValues;
      testEvidenceId: string;
      submissionId: string;
    }) =>
      saveWebhookDefinitionDraft(token, {
        revisionId: input.revisionId,
        webhookId,
        expectedVersion: input.expectedVersion,
        object: input.object,
        testEvidenceId: input.testEvidenceId,
        submissionId: input.submissionId,
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setSavedNotice(null);
      setReconciliation(null);
    },
    onSuccess: (result, input) => {
      if (result.ok) {
        const saved = {
          revisionId: result.model.revisionId,
          version: result.model.version,
          status: "validated",
          values: input.values,
        };
        const local = formRef.current;
        const editedDuringSave =
          local !== null && !sameWebhookForm(local, input.values);
        setBaseline(saved);
        setRemote(null);
        if (!editedDuringSave) setForm(input.values);
        setSavedNotice(
          editedDuringSave
            ? `已应用提交时的内容并发布新的生效快照；保存请求处理期间你继续输入的内容仍保留为未保存修改。`
            : `更改已通过检查并发布为新的生效配置；需要重启的字段会在重启后采用。`,
        );
        clearEvidence();
        setPendingApply(null);
        setAwaitingVerification(false);
        setReconciliation(null);
        submittedValuesRef.current = null;
        verifiedSubmissionRef.current = input.submissionId;
        writePendingNotificationApply(principalId, applyScope, null);
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        const pending: PendingNotificationApply = {
          submissionId: input.submissionId,
          webhookId,
          baselineRevisionId: input.revisionId,
          baselineVersion: input.expectedVersion,
        };
        submittedValuesRef.current = input.values;
        setPendingApply(pending);
        setAwaitingVerification(true);
        setReconciliation(null);
        writePendingNotificationApply(principalId, applyScope, pending);
        setError(
          "应用结果待核实：本次请求没有收到可确认的回包。系统不会重复发布；正在用同一请求身份只读核对本次结果和当前生效定义。",
        );
        return;
      }
      setPendingApply(null);
      setAwaitingVerification(false);
      writePendingNotificationApply(principalId, applyScope, null);
      if (result.status === 403) {
        setShowIssues(false);
        setSavePermissionDenied(true);
        setError(
          "应用没有执行（403）：当前账号没有管理配置的权限。读取最新定义以核对服务端提供的动作；如果仍无权限，请联系配置管理员。系统没有自动重试。",
        );
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        return;
      }
      setShowIssues(true);
      setError(
        result.status === 409
          ? "应用没有执行：配置在你编辑期间已经变化，或签名测试证据与当前表单不一致。重新读取并对当前表单完成一次签名测试后再应用；服务端保留了胜出的版本。"
          : `更改没有发布（${result.code}）。服务端校验拒绝了表单或配置版本已过期；重新读取后修正，系统没有自动重试。`,
      );
    },
  });

  const testMutation = useMutation({
    mutationFn: (input: {
      context: string;
      webhook: Record<string, unknown>;
      revisionId: string;
      revisionVersion: number;
    }) =>
      testWebhookDefinitionForm(token, {
        webhookId,
        webhook: input.webhook,
        expectedRevisionId: input.revisionId,
        expectedVersion: input.revisionVersion,
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setTestResult(null);
    },
    onSuccess: (result, input) => {
      if (result.ok) {
        if (input.context !== testContext) return;
        const model = result.model;
        setTestResult({
          context: input.context,
          success: model.outcome === "success",
          evidenceId: model.testEvidenceId,
          message:
            model.outcome === "success"
              ? `签名测试成功。${model.message} 下一步：${model.nextAction}`
              : `签名测试失败。${model.message} 下一步：${model.nextAction}`,
        });
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        setError(unknownTestMessage());
        return;
      }
      setError(
        result.status === 409
          ? "显示的修订已经过期，因此没有发送测试请求。重新读取定义，再测试当前精确版本。"
          : `测试没有执行（${result.code}）。重新读取当前持久状态后再试；系统没有自动重试。`,
      );
    },
  });

  const busy = saveMutation.isPending || testMutation.isPending || verifying;
  const activateInFlight = saveMutation.isPending;

  const verifyApplicationOutcome = async (
    pending: PendingNotificationApply,
  ) => {
    if (verificationInFlightRef.current) return;
    verificationInFlightRef.current = true;
    verifiedSubmissionRef.current = pending.submissionId;
    setVerifying(true);
    setAwaitingVerification(true);
    setError(null);
    try {
      const result = await reconcileSystemSettings(token, pending.submissionId);
      const state =
        typeof result.state === "string" ? result.state : "UNRESOLVED";
      let refreshed = await draftQuery.refetch();
      let model = refreshed.data?.ok === true ? refreshed.data.model : null;
      let current = model?.draft ?? null;
      if (
        (state === "COMMITTED" || state === "SUPERSEDED") &&
        (current === null || current.revisionId === pending.baselineRevisionId)
      ) {
        // The reconciler proves this exact request published; a read still
        // showing the pre-request baseline is a stale read, so take one fresh
        // read before presenting the current effective definition.
        refreshed = await draftQuery.refetch();
        model = refreshed.data?.ok === true ? refreshed.data.model : null;
        current = model?.draft ?? null;
      }
      const currentValues =
        current === null ? null : webhookFormFromDocument(current.webhook);
      const currentRevisionId = current?.revisionId ?? null;
      const currentVersion = current?.revisionVersion ?? null;
      const committedVersion = optionalNumber(result.committedRevisionVersion);
      const readShowsCommittedRevision =
        current !== null && current.revisionId !== pending.baselineRevisionId;
      const reportedCurrentVersion =
        state === "COMMITTED" &&
        !readShowsCommittedRevision &&
        committedVersion !== null
          ? committedVersion
          : currentVersion;
      setReconciliation({
        state,
        committed: result.committed === true,
        committedRevisionId:
          typeof result.committedRevisionId === "string"
            ? result.committedRevisionId
            : null,
        committedRevisionVersion: optionalNumber(
          result.committedRevisionVersion,
        ),
        currentRevisionId,
        currentVersion: reportedCurrentVersion,
        nextAction:
          typeof result.nextAction === "string" ? result.nextAction : null,
      });
      if (state === "UNRESOLVED") {
        setError(
          "无法证明本次请求的持久结果；应用保持阻止，系统没有重新发布。当前生效定义已按真实读回显示；恢复连接后可再次自动核实。",
        );
        return;
      }
      setAwaitingVerification(false);
      setPendingApply(null);
      writePendingNotificationApply(principalId, applyScope, null);
      const submitted = submittedValuesRef.current;
      const local = formRef.current;
      const editedDuringRequest =
        submitted !== null &&
        local !== null &&
        !sameWebhookForm(local, submitted);
      if (state === "COMMITTED" || state === "SUPERSEDED") {
        // The exact baseline moved; an earlier probe cannot authorize a later
        // form again, so require a fresh test before any next apply.
        clearEvidence();
        const readCaughtUp =
          current !== null &&
          currentValues !== null &&
          current.revisionId !== pending.baselineRevisionId;
        if (readCaughtUp && current !== null && currentValues !== null) {
          setBaseline({
            revisionId: current.revisionId,
            version: current.revisionVersion,
            status: current.revisionStatus,
            values: currentValues,
          });
          if (editedDuringRequest) {
            setRemote({
              revisionId: current.revisionId,
              version: current.revisionVersion,
              status: current.revisionStatus,
              values: currentValues,
              kind: "updated",
            });
          } else {
            setForm(currentValues);
            setRemote(null);
          }
        } else if (submitted !== null) {
          // The reconciler proved this request published; a read still showing
          // the pre-request baseline has not caught up. Keep the applied input
          // as the local baseline instead of reverting it to the old values.
          const committedRevisionId =
            typeof result.committedRevisionId === "string"
              ? result.committedRevisionId
              : pending.baselineRevisionId;
          setBaseline({
            revisionId: committedRevisionId,
            version: committedVersion ?? pending.baselineVersion,
            status: "validated",
            values: submitted,
          });
          setForm(submitted);
          setRemote(null);
        }
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        setSavedNotice(
          state === "COMMITTED"
            ? `本次应用已通过同一请求身份确认发布；当前生效定义版本为 ${reportedCurrentVersion ?? "未知"}。页面未再次发送发布请求。`
            : `本次应用已确认曾经发布，之后的发布已替换为当前生效定义版本 ${reportedCurrentVersion ?? "未知"}。页面未再次发送发布请求。`,
        );
        submittedValuesRef.current = null;
      } else {
        setSavedNotice(
          `已通过同一请求身份的持久证据确认本次没有发布；当前生效定义版本为 ${reportedCurrentVersion ?? "未知"}，你的输入仍保留在表单中。`,
        );
      }
    } catch {
      setError(
        "无法完成只读核实；应用保持阻止。请确认服务可用后再次核实，系统不会自动重发发布请求。",
      );
    } finally {
      verificationInFlightRef.current = false;
      setVerifying(false);
    }
  };

  useEffect(() => {
    verifyOutcomeRef.current = (pending) => {
      void verifyApplicationOutcome(pending);
    };
  });

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (principalId === null) return;
    const stored = readPendingNotificationApply(principalId, applyScope);
    if (stored === null) return;
    setPendingApply((previous) => previous ?? stored);
    setAwaitingVerification(true);
    setReconciliation(null);
  }, [principalId, applyScope]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (!awaitingVerification || pendingApply === null || busy) return;
    if (verifiedSubmissionRef.current === pendingApply.submissionId) return;
    void verifyApplicationOutcome(pendingApply);
    // The exact retained request is verified once; reconnect/return and the
    // manual fallback retry an unreadable reconciliation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [awaitingVerification, pendingApply, busy]);

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "hidden") return;
      if (awaitingVerification && pendingApply !== null) {
        verifyOutcomeRef.current(pendingApply);
        return;
      }
      void draftQuery.refetch();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    window.addEventListener("online", refresh);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("online", refresh);
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [awaitingVerification, pendingApply, draftQuery.refetch]);

  const closeCard = () => {
    const reconciled = reconciliation?.committed === true;
    void navigate({ to: "/operations/notifications" }).then(() => {
      if (reconciled) {
        // A reconciled apply changed the published identity while the list was
        // mounted behind the editor. Re-read it after the transition so the
        // list presents the same current definition the editor just reported.
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
      }
    });
  };
  const guard = useNotificationCardGuard({
    busy,
    dirty,
    onClose: closeCard,
    onDiscard: () => {
      if (baseline !== null) {
        setForm(baseline.values);
      }
      setRemote(null);
      setTouched(new Set());
      setShowIssues(false);
      setError(null);
      setSavedNotice(null);
      setTestResult(null);
    },
    firstFieldId: "notification-edit-url",
    fallbackFocusId: "notification-definitions-background",
  });

  const issues = currentForm === null ? [] : webhookFormIssues(currentForm);
  const fieldIssue = (field: string): string | null =>
    showIssues || touched.has(field)
      ? webhookFormIssueFor(issues, field as (typeof ALL_FORM_FIELDS)[number])
      : null;
  const markTouched = (field: string) =>
    setTouched((previous) => new Set(previous).add(field));

  const updateForm = (patch: Partial<WebhookFormValues>) => {
    if (currentForm === null) return;
    const next = { ...currentForm, ...patch };
    // Keep the latest operator input available synchronously so a save result
    // that arrives before the next effect cannot restore the submitted value.
    formRef.current = next;
    setForm(next);
    setError(null);
    setSavedNotice(null);
    clearEvidence();
  };

  const adoptRemote = () => {
    if (remote === null) return;
    setBaseline(remote);
    setForm(remote.values);
    setRemote(null);
    setTouched(new Set());
    setShowIssues(false);
    setError(null);
    setSavedNotice(null);
    clearEvidence();
  };

  const keepLocalAgainstRemote = () => {
    if (remote === null) return;
    // Explicit choice: keep the local input but bind subsequent saves to the
    // newest durable version. Test/validate/publish still refuse until the
    // input is saved; nothing is silently submitted.
    setBaseline(remote);
    setRemote(null);
    setSavedNotice(null);
    clearEvidence();
  };

  const discardRetainedLocalInput = () => {
    // Explicit choice after the open draft disappeared: discard only the card
    // input. Nothing is written; the background list and Active stay as read.
    setForm(null);
    setBaseline(null);
    setRemote(null);
    setTouched(new Set());
    setShowIssues(false);
    setError(null);
    setSavedNotice(null);
    clearEvidence();
  };

  const canTest =
    currentForm !== null &&
    baseline !== null &&
    webhookFormIssues(currentForm).length === 0 &&
    loadedDraft?.actions.test.available === true;
  const testedForCurrentForm =
    testResult !== null &&
    testResult.success &&
    testResult.evidenceId !== null &&
    testResult.context === testContext;
  const title =
    draft === null
      ? "编辑 Webhook 定义"
      : readOnlyDraft
        ? `查看 Webhook ${draft.webhook.id}`
        : `编辑 Webhook ${draft.webhook.id}`;
  const titleId = "notification-edit-title";
  const retainedLocalInput =
    draft === null && currentForm !== null && baseline !== null;
  const baselineIsOpenDraft =
    draft !== null &&
    baseline !== null &&
    draft.revisionId === baseline.revisionId;

  useEffect(() => {
    // The retained-input explanation and its explicit choices grow above the
    // existing form. Bring the card body back to its top so the operator sees
    // why the read changed state and what happens next.
    const element = formScrollRef.current;
    if (retainedLocalInput && element !== null) element.scrollTop = 0;
  }, [retainedLocalInput]);
  const saveDisabled =
    busy ||
    readDegraded ||
    remote !== null ||
    draft === null ||
    baseline === null ||
    currentForm === null ||
    readOnlyDraft ||
    !saveAvailable ||
    !dirty ||
    !testedForCurrentForm ||
    awaitingVerification ||
    pendingApply !== null ||
    issues.length > 0;

  return (
    <NotificationCard
      layerRef={guard.layerRef}
      closing={guard.closing}
      busy={busy}
      title={title}
      titleId={titleId}
      description={
        retainedLocalInput
          ? "当前没有可编辑的 Webhook 定义；你尚未保存的输入仍保留在此卡片中，不会写入服务端。"
          : draft === null
            ? "当前生效配置不包含这个 Webhook 定义。"
            : readOnlyDraft
              ? "当前账号只能查看这个定义，不能应用修改或发送测试。"
              : "点击「应用更改」后，后端会校验并原子发布新的生效配置。"
      }
      closeDisabled={busy}
      onRequestClose={guard.attemptClose}
      size="form"
      footer={
        <>
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={guard.attemptClose}
          >
            关闭
          </Button>
          {draft !== null && !readOnlyDraft && saveAvailable && (
            <Button
              type="submit"
              form="notification-edit-form"
              id={SAVE_BUTTON_ID}
              disabled={saveDisabled}
            >
              {saveMutation.isPending ? "正在应用…" : "应用更改"}
            </Button>
          )}
        </>
      }
    >
      {guard.discardPromptOpen && (
        <NotificationDiscardPrompt
          mode={guard.promptMode}
          onContinue={guard.cancelDiscard}
          onDiscard={guard.commitDiscard}
        />
      )}
      {draftQuery.isError && loadedDraft === null && (
        <NotificationCardStatus variant="error" title="当前定义读取失败">
          <p>没有读取到当前 Webhook 定义，因此不能安全编辑或应用。</p>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void draftQuery.refetch()}
              disabled={draftQuery.isFetching}
            >
              {draftQuery.isFetching ? "正在重试…" : "重试读取"}
            </Button>
          </div>
        </NotificationCardStatus>
      )}
      {draftQuery.data === undefined && !draftQuery.isError && (
        <NotificationCardStatus title="正在读取定义">
          <p>读取当前生效配置中的 Webhook 定义。</p>
        </NotificationCardStatus>
      )}
      {draftQuery.data !== undefined &&
        draftQuery.data.ok === false &&
        loadedDraft === null && (
          <NotificationCardStatus
            variant="error"
            title={draftQuery.data.failure.title}
          >
            <p>{draftQuery.data.failure.nextAction}</p>
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => void draftQuery.refetch()}
                disabled={draftQuery.isFetching}
              >
                {draftQuery.isFetching ? "正在重试…" : "重试读取"}
              </Button>
            </div>
          </NotificationCardStatus>
        )}
      {loadedDraft !== null && draft === null && !retainedLocalInput && (
        <div className="mf-notification-card-scroll">
          <StatusBanner variant="info" title="没有可编辑的定义">
            <p>
              当前生效配置不包含这个 Webhook
              定义；没有渲染可填写的表单，也不会发送测试。
            </p>
          </StatusBanner>
          <div className="mf-notification-actions">
            <Button type="button" variant="secondary" onClick={closeCard}>
              返回通知列表
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy || draftQuery.isFetching}
              onClick={() => void draftQuery.refetch()}
            >
              {draftQuery.isFetching ? "正在读取…" : "读取当前定义"}
            </Button>
          </div>
          {error !== null && (
            <StatusBanner variant="error" title="操作没有完成">
              <p>{error}</p>
            </StatusBanner>
          )}
        </div>
      )}
      {readOnlyDraft && serverValues !== null && draft !== null && (
        <div className="mf-notification-card-scroll">
          {readDegraded && (
            <StatusBanner variant="warning" title="最新读取失败">
              <p>
                显示的是上次成功读取的当前定义版本 {draft.revisionVersion}
                。恢复读取后再核对当前权限和当前定义内容。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void draftQuery.refetch()}
                  disabled={draftQuery.isFetching}
                >
                  {draftQuery.isFetching ? "正在重试…" : "重试读取"}
                </Button>
              </div>
            </StatusBanner>
          )}
          <StatusBanner variant="warning" title="只能查看这个当前定义">
            <p>
              {notificationReasonLabel(
                loadedDraft?.actions.save.reason ?? null,
                "当前账号没有保存这个当前定义的权限。",
              )}
            </p>
            <p>
              你仍可查看下列持久当前定义内容。要修改、检查或发布，请联系具备配置管理权限的管理员；此页面不会写入当前定义、发送测试或发布配置。
            </p>
            <div className="mf-notification-actions">
              <Button
                type="button"
                onClick={() =>
                  void navigate({
                    to: "/operations/notifications/webhooks/$webhookId",
                    params: { webhookId },
                  })
                }
              >
                查看定义
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={guard.attemptClose}
              >
                返回通知列表
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={busy || draftQuery.isFetching}
                onClick={() => void draftQuery.refetch()}
              >
                {draftQuery.isFetching ? "正在读取…" : "读取最新当前定义"}
              </Button>
            </div>
          </StatusBanner>
          {error !== null && (
            <StatusBanner variant="error" title="当前定义操作没有完成">
              <p>{error}</p>
            </StatusBanner>
          )}
          <div className="mf-notification-detail-badges">
            <span className="mf-notification-badge">
              只读当前定义 · 版本 {draft.revisionVersion}
            </span>
            <span className="mf-notification-badge">
              {draft.revisionStatus === "validated" ? "已检查" : "当前定义"}
            </span>
            <span className="mf-notification-badge">已生效配置不变</span>
          </div>
          <section className="mf-notification-form-section">
            <h3>当前定义内容（只读）</h3>
            <dl className="mf-notification-facts">
              <dt>HTTPS 接收地址</dt>
              <dd className="mf-notification-endpoint">{serverValues.url}</dd>
              <dt>密钥环境变量引用</dt>
              <dd>{serverValues.secretEnv}</dd>
              <dt>订阅事件</dt>
              <dd>
                {serverValues.events.map((event) => (
                  <span className="mf-notification-event" key={event}>
                    {notificationEventLabel(event)}
                  </span>
                ))}
              </dd>
              <dt>启用状态</dt>
              <dd>{serverValues.enabled ? "已启用" : "已停用"}</dd>
              <dt>超时与重试</dt>
              <dd>
                超时 {serverValues.timeoutSeconds} 秒 · 最多尝试{" "}
                {serverValues.maxAttempts} 次 · 重试{" "}
                {serverValues.baseRetrySeconds}–{serverValues.maxRetrySeconds}{" "}
                秒
              </dd>
            </dl>
            <details className="mf-notification-diagnostics">
              <summary>诊断信息</summary>
              <dl>
                <dt>Webhook 标识</dt>
                <dd>{draft.webhook.id}</dd>
                <dt>当前定义修订</dt>
                <dd>{draft.revisionId}</dd>
                <dt>当前定义版本</dt>
                <dd>{draft.revisionVersion}</dd>
                <dt>事件标识</dt>
                <dd>{serverValues.events.join(", ")}</dd>
              </dl>
            </details>
          </section>
        </div>
      )}
      {!readOnlyDraft && currentForm !== null && baseline !== null && (
        <form
          id="notification-edit-form"
          ref={formScrollRef}
          className="mf-notification-card-scroll"
          onSubmit={(event) => {
            event.preventDefault();
            if (
              busy ||
              readDegraded ||
              draft === null ||
              remote !== null ||
              !dirty ||
              awaitingVerification ||
              pendingApply !== null ||
              testResult?.evidenceId === null ||
              testResult?.evidenceId === undefined
            ) {
              return;
            }
            setShowIssues(true);
            setTouched(new Set(ALL_FORM_FIELDS));
            if (issues.length > 0) {
              setError("请修正标有说明的字段后再保存。");
              return;
            }
            const submissionId = newNotificationSubmissionId();
            if (submissionId === null) {
              setError(
                "无法生成安全的请求标识；本次没有发送写入，请更新浏览器后重试。",
              );
              return;
            }
            const values = canonicalWebhookForm(currentForm);
            setError(null);
            setSavedNotice(null);
            saveMutation.mutate({
              revisionId: baseline.revisionId,
              expectedVersion: baseline.version,
              object: buildWebhookObject(webhookId, values),
              values,
              testEvidenceId: testResult.evidenceId,
              submissionId,
            });
          }}
        >
          {awaitingVerification && pendingApply !== null && (
            <StatusBanner variant="error" title="应用结果待核实">
              <p>
                本次请求没有收到可确认的回包，可能已经发布，也可能没有。
                正在用同一请求身份只读核对本次结果和当前生效定义；核实期间不会再次发布。系统不会自动重发发布请求。
              </p>
              <p>
                请求身份 {pendingApply.submissionId.slice(0, 8)}…
                {pendingApply.baselineRevisionId !== baseline.revisionId
                  ? "；当前显示的生效基线已变化，核实会同时给出本次请求结果与当前生效定义。"
                  : "。"}
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={verifying || busy || saveMutation.isPending}
                  onClick={() => void verifyApplicationOutcome(pendingApply)}
                >
                  {verifying ? "核实中…" : "核实当前状态"}
                </Button>
              </div>
            </StatusBanner>
          )}
          {reconciliation !== null && (
            <StatusBanner
              variant={reconciliation.committed ? "success" : "warning"}
              title="本次应用结果"
            >
              <p>
                {reconciliation.state === "COMMITTED"
                  ? "本次请求已确认发布，并且是当前生效值。"
                  : reconciliation.state === "SUPERSEDED"
                    ? "本次请求已确认发布，之后的发布已成为当前生效值。"
                    : reconciliation.state === "NOT_COMMITTED"
                      ? "已通过同一请求身份的持久证据确认本次没有发布。"
                      : "当前仍无法证明本次请求的持久结果；应用保持阻止。"}
              </p>
              <p>
                当前生效定义版本：
                {reconciliation.currentVersion ?? "不可用"}
                。本次请求结果与当前生效值分别依据各自证据显示，页面没有重新发布。
              </p>
            </StatusBanner>
          )}
          {readDegraded && (
            <StatusBanner variant="warning" title="最新读取失败">
              <p>
                显示的是上次成功读取的当前定义版本 {baseline.version}
                。已知保存结果仍然有效；恢复读取后再进行测试、检查或发布。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void draftQuery.refetch()}
                  disabled={draftQuery.isFetching}
                >
                  {draftQuery.isFetching ? "正在重试…" : "重试读取"}
                </Button>
              </div>
            </StatusBanner>
          )}
          {retainedLocalInput && (
            <StatusBanner
              variant="warning"
              title="当前定义已不再打开，本地输入已保留"
            >
              <p>
                读取显示这份打开的当前定义已经不存在，通常表示另一位管理员已经保存并发布。
                你尚未保存的输入仍显示在下方；系统没有写入服务端，也没有把本地输入静默绑定到新的当前定义修订。
              </p>
              <p>
                已生效配置可能已经变化。重新读取当前定义后，再明确选择保留本地输入或采用服务端值；也可以直接放弃本地输入。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={busy || draftQuery.isFetching}
                  onClick={() => void draftQuery.refetch()}
                >
                  {draftQuery.isFetching ? "正在读取…" : "重新读取当前定义"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={discardRetainedLocalInput}
                >
                  放弃本地输入
                </Button>
              </div>
            </StatusBanner>
          )}
          <div className="mf-notification-state-strip">
            {retainedLocalInput ? (
              <>
                <span className="mf-notification-badge">
                  原当前定义 · 版本 {baseline.version} · 已不再打开
                </span>
                <span className="mf-notification-badge mf-notification-badge-warn">
                  本地未保存输入已保留
                </span>
                <span className="mf-notification-badge mf-notification-badge-warn">
                  已生效配置可能已变化
                </span>
              </>
            ) : baselineIsOpenDraft ? (
              <>
                <span className="mf-notification-badge">
                  已保存当前定义 · 版本 {baseline.version} ·{" "}
                  {baseline.status === "validated" ? "已检查" : "当前定义"}
                </span>
                {dirty && (
                  <span className="mf-notification-badge mf-notification-badge-warn">
                    有未保存修改
                  </span>
                )}
                {clean && (
                  <span className="mf-notification-badge mf-notification-badge-active">
                    当前输入与已保存当前定义一致
                  </span>
                )}
                <span className="mf-notification-badge">已生效配置不变</span>
              </>
            ) : (
              <>
                <span className="mf-notification-badge">
                  原当前定义 · 版本 {baseline.version}
                </span>
                <span className="mf-notification-badge mf-notification-badge-warn">
                  读取到新的当前定义修订
                </span>
                <span className="mf-notification-badge mf-notification-badge-warn">
                  未写入服务端
                </span>
              </>
            )}
            {!readDegraded && (
              <span className="mf-notification-read-action">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy || draftQuery.isFetching}
                  onClick={() => void draftQuery.refetch()}
                >
                  {draftQuery.isFetching ? "正在读取…" : "读取最新当前定义"}
                </Button>
              </span>
            )}
          </div>

          {savedNotice !== null && (
            <StatusBanner variant="success" title="已保存到当前定义">
              <p>{savedNotice}</p>
            </StatusBanner>
          )}
          {remote !== null && (
            <StatusBanner
              variant="warning"
              title={
                remote.kind === "revision"
                  ? "读取到另一个当前定义修订"
                  : "当前定义已在其他位置更新"
              }
            >
              <p>
                {remote.kind === "revision"
                  ? `打开的是另一个当前定义修订（版本 ${remote.version}）。`
                  : `耐久当前定义现在是版本 ${remote.version}。`}
                你还有未保存的输入；系统没有把本地输入静默绑定到新版本。
              </p>
              <div className="mf-actions">
                <Button type="button" variant="secondary" onClick={adoptRemote}>
                  采用服务端值
                </Button>
                <Button type="button" onClick={keepLocalAgainstRemote}>
                  保留本地输入并重新保存
                </Button>
              </div>
            </StatusBanner>
          )}
          {dirty && remote === null && !retainedLocalInput && (
            <StatusBanner variant="info" title="有未保存的修改">
              <p>
                测试、检查和发布只针对已保存的当前定义版本。先保存当前输入，或明确放弃修改后再操作已保存版本。
              </p>
            </StatusBanner>
          )}
          {error !== null && (
            <StatusBanner variant="error" title="当前定义操作没有完成">
              <p>{error}</p>
            </StatusBanner>
          )}
          {draft !== null && draft.validationErrors.length > 0 && (
            <StatusBanner variant="error" title="当前定义检查发现">
              <ul>
                {draft.validationErrors.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </StatusBanner>
          )}

          <section className="mf-notification-form-section">
            <h3>基本设置</h3>
            <div className="mf-notification-form-grid">
              <div className="mf-notification-field mf-notification-field-full">
                <label htmlFor="notification-edit-url">HTTPS 接收地址</label>
                <input
                  id="notification-edit-url"
                  value={currentForm.url}
                  disabled={activateInFlight}
                  maxLength={2048}
                  inputMode="url"
                  autoCapitalize="off"
                  spellCheck={false}
                  aria-invalid={fieldIssue("url") !== null}
                  onChange={(event) => updateForm({ url: event.target.value })}
                  onBlur={() => markTouched("url")}
                />
                <p className="mf-notification-field-help">
                  只接受 HTTPS；不能包含用户名、密码、查询字符串或片段。
                </p>
                {fieldIssue("url") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("url")}
                  </p>
                )}
              </div>
              <div className="mf-notification-field mf-notification-field-full">
                <label htmlFor="notification-edit-secret">
                  密钥环境变量引用
                </label>
                <input
                  id="notification-edit-secret"
                  value={currentForm.secretEnv}
                  disabled={activateInFlight}
                  maxLength={128}
                  autoCapitalize="off"
                  spellCheck={false}
                  aria-invalid={fieldIssue("secretEnv") !== null}
                  onChange={(event) =>
                    updateForm({ secretEnv: event.target.value })
                  }
                  onBlur={() => markTouched("secretEnv")}
                />
                <p className="mf-notification-field-help">
                  只保存环境变量名；密钥值始终由部署环境提供。
                </p>
                {fieldIssue("secretEnv") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("secretEnv")}
                  </p>
                )}
              </div>
            </div>
          </section>

          <section className="mf-notification-form-section">
            <h3>事件与启用</h3>
            <div className="mf-notification-form-grid">
              <fieldset className="mf-notification-field mf-notification-field-full">
                <legend>订阅事件</legend>
                <div className="mf-notification-event-options">
                  {loadedDraft?.supportedEvents.map((event) => (
                    <label key={event} className="mf-notification-check">
                      <input
                        type="checkbox"
                        disabled={activateInFlight}
                        checked={currentForm.events.includes(event)}
                        onChange={(changeEvent) => {
                          const events = changeEvent.target.checked
                            ? [...currentForm.events, event]
                            : currentForm.events.filter(
                                (item) => item !== event,
                              );
                          updateForm({ events });
                          markTouched("events");
                        }}
                      />
                      <span>{notificationEventLabel(event)}</span>
                      <code>{event}</code>
                    </label>
                  ))}
                </div>
                {fieldIssue("events") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("events")}
                  </p>
                )}
              </fieldset>
              <label className="mf-notification-switch">
                <input
                  type="checkbox"
                  disabled={activateInFlight}
                  checked={currentForm.enabled}
                  onChange={(event) =>
                    updateForm({ enabled: event.target.checked })
                  }
                />
                <span>
                  <strong>启用这个 Webhook</strong>
                  <small>
                    发布后才会使用；当前定义内修改不影响当前已生效配置。
                  </small>
                </span>
              </label>
            </div>
          </section>

          <section className="mf-notification-form-section">
            <h3>超时与重试</h3>
            <div className="mf-notification-form-grid">
              <div className="mf-notification-field">
                <label htmlFor="notification-edit-timeout">
                  请求超时（秒）
                </label>
                <input
                  id="notification-edit-timeout"
                  value={currentForm.timeoutSeconds}
                  disabled={activateInFlight}
                  inputMode="decimal"
                  aria-invalid={fieldIssue("timeoutSeconds") !== null}
                  onChange={(event) =>
                    updateForm({ timeoutSeconds: event.target.value })
                  }
                />
                <p className="mf-notification-field-help">0.1–120 秒。</p>
                {fieldIssue("timeoutSeconds") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("timeoutSeconds")}
                  </p>
                )}
              </div>
              <div className="mf-notification-field">
                <label htmlFor="notification-edit-attempts">最大尝试次数</label>
                <input
                  id="notification-edit-attempts"
                  value={currentForm.maxAttempts}
                  disabled={activateInFlight}
                  inputMode="numeric"
                  aria-invalid={fieldIssue("maxAttempts") !== null}
                  onChange={(event) =>
                    updateForm({ maxAttempts: event.target.value })
                  }
                />
                <p className="mf-notification-field-help">1–20 次。</p>
                {fieldIssue("maxAttempts") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("maxAttempts")}
                  </p>
                )}
              </div>
              <div className="mf-notification-field">
                <label htmlFor="notification-edit-base-retry">
                  基础重试间隔（秒）
                </label>
                <input
                  id="notification-edit-base-retry"
                  value={currentForm.baseRetrySeconds}
                  disabled={activateInFlight}
                  inputMode="decimal"
                  aria-invalid={fieldIssue("baseRetrySeconds") !== null}
                  onChange={(event) =>
                    updateForm({ baseRetrySeconds: event.target.value })
                  }
                />
                {fieldIssue("baseRetrySeconds") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("baseRetrySeconds")}
                  </p>
                )}
              </div>
              <div className="mf-notification-field">
                <label htmlFor="notification-edit-max-retry">
                  最大重试间隔（秒）
                </label>
                <input
                  id="notification-edit-max-retry"
                  value={currentForm.maxRetrySeconds}
                  disabled={activateInFlight}
                  inputMode="decimal"
                  aria-invalid={fieldIssue("maxRetrySeconds") !== null}
                  onChange={(event) =>
                    updateForm({ maxRetrySeconds: event.target.value })
                  }
                />
                {fieldIssue("maxRetrySeconds") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("maxRetrySeconds")}
                  </p>
                )}
              </div>
            </div>
          </section>

          {currentForm !== null && baseline !== null && (
            <section className="mf-notification-form-section">
              <h3>签名测试</h3>
              <p className="mf-notification-field-help">
                针对当前表单中的接收地址和签名密钥引用发送一次带签名的请求；不会创建投递、不会自动重试，也不会改变配置。修改地址或密钥引用后需重新测试。
              </p>
              <div className="mf-notification-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!canTest || busy}
                  title={notificationReasonLabel(
                    loadedDraft?.actions.test.reason ?? null,
                    "当前不能发送签名测试",
                  )}
                  onClick={() => {
                    if (currentForm === null) return;
                    if (baseline === null) return;
                    testMutation.mutate({
                      context: testContext,
                      webhook: buildWebhookObject(webhookId, currentForm),
                      revisionId: baseline.revisionId,
                      revisionVersion: baseline.version,
                    });
                  }}
                >
                  {testMutation.isPending
                    ? "正在发送签名测试…"
                    : "发送签名测试"}
                </Button>
              </div>
              {testResult !== null && testResult.context === testContext && (
                <StatusBanner
                  variant={testResult.success ? "success" : "error"}
                  title="签名测试结果"
                >
                  <p>{testResult.message}</p>
                  <p>
                    结论只对当前地址和签名引用有效；修改后需重新测试才能应用。
                  </p>
                </StatusBanner>
              )}
              {!testedForCurrentForm && (
                <p className="mf-notification-inline-reason">
                  应用前必须对当前表单成功完成一次签名测试。
                </p>
              )}
            </section>
          )}
        </form>
      )}
    </NotificationCard>
  );
}
