/**
 * V2 Webhook successor-Draft editor card.
 *
 * The card reads the exact open Draft with its optimistic version and keeps
 * three states visibly separate:
 *
 * - saved Draft: the durable revision/version and its stored form;
 * - unsaved input: local values that are not the saved revision;
 * - checked/published: validation evidence and an explicit publish decision.
 *
 * Save, validate, signed test and checked activation are separate explicit
 * actions bound to the exact saved revision identity and version. Unsaved
 * input is never submitted as if it were the saved revision, stale test or
 * validation evidence is discarded when the input or version changes, and a
 * late response never replaces a newer context.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  activateWebhookDraft,
  createNotificationSuccessorDraft,
  saveWebhookDefinitionDraft,
  testWebhookDefinition,
  validateAutomationDraft,
} from "../../shared/api/api-client";
import {
  notificationDefinitionQueryKey,
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
  unknownCommandMessage,
  unknownTestMessage,
} from "./notification-presentation";
import {
  NotificationCard,
  NotificationCardStatus,
  NotificationDiscardPrompt,
  useLastSuccessfulRead,
  useNotificationCardGuard,
} from "./notification-card";

interface SavedDraft {
  readonly revisionId: string;
  readonly version: number;
  readonly status: string;
  readonly values: WebhookFormValues;
}

interface RemoteDraft extends SavedDraft {
  /** Whether the same revision moved or a different Draft revision was read. */
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
  const [confirmActivate, setConfirmActivate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [savePermissionDenied, setSavePermissionDenied] = useState(false);
  const [validationNotice, setValidationNotice] = useState<{
    readonly context: string;
    readonly message: string;
  } | null>(null);
  const [testResult, setTestResult] = useState<{
    readonly context: string;
    readonly message: string;
  } | null>(null);

  const formRef = useRef(form);
  const baselineRef = useRef(baseline);
  const formScrollRef = useRef<HTMLFormElement | null>(null);
  useEffect(() => {
    formRef.current = form;
  }, [form]);
  useEffect(() => {
    baselineRef.current = baseline;
  }, [baseline]);

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
  const displayedContext =
    baseline === null ? "" : `${baseline.revisionId}:${baseline.version}`;
  const dirty =
    currentForm !== null &&
    baseline !== null &&
    !sameWebhookForm(currentForm, baseline.values);
  const clean = currentForm !== null && baseline !== null && !dirty;
  const canUseSavedVersion =
    clean &&
    remote === null &&
    draft !== null &&
    baseline !== null &&
    !readDegraded;

  const clearEvidence = () => {
    setTestResult(null);
    setValidationNotice(null);
    setConfirmActivate(false);
  };

  // Reconcile the durable Draft into the local saved baseline. A version or
  // status move with no local edits is adopted directly. A move while local
  // input exists is held as an explicit remote choice; the old input is never
  // silently paired with the new version. Losing the open Draft (another
  // administrator published it) and reading a different Draft revision must
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
        // The read proves there is no open Draft, but the operator still owns
        // input made against the old revision. Keep both local input and its
        // original baseline; never bind them to an unread successor Draft.
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
        setConfirmActivate(false);
        setValidationNotice(null);
      }
      return;
    }
    setTestResult(null);
    setValidationNotice(null);
    setConfirmActivate(false);
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
        void queryClient.invalidateQueries({
          queryKey: [notificationDefinitionQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        setSavedNotice(null);
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        setError(unknownCommandMessage("后继草稿可能已经创建"));
        return;
      }
      setError(
        result.status === 409
          ? "后继草稿没有创建：已生效配置在读取后已经变化。重新读取后再试。"
          : `后继草稿没有创建（${result.code}）。重新读取后再试。`,
      );
    },
  });

  const saveMutation = useMutation({
    mutationFn: (input: {
      revisionId: string;
      expectedVersion: number;
      object: Record<string, unknown>;
      values: WebhookFormValues;
    }) =>
      saveWebhookDefinitionDraft(token, {
        revisionId: input.revisionId,
        webhookId,
        expectedVersion: input.expectedVersion,
        object: input.object,
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setSavedNotice(null);
    },
    onSuccess: (result, input) => {
      if (result.ok) {
        const saved = {
          revisionId: result.model.revisionId,
          version: result.model.version,
          status: "draft",
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
            ? `已保存提交时的内容到草稿版本 ${result.model.version}；保存请求处理期间你继续输入的内容仍保留为未保存修改，尚未写入草稿。明确再次保存后才会写入新版本。`
            : `已保存到草稿版本 ${result.model.version}；尚未生效。检查并发布后，已生效配置才会改变。`,
        );
        clearEvidence();
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        setError(unknownCommandMessage("草稿可能已经保存"));
        return;
      }
      if (result.status === 403) {
        setShowIssues(false);
        setSavePermissionDenied(true);
        setError(
          "保存没有执行（403）：当前账号没有保存这个草稿的权限。读取最新草稿以核对服务端提供的动作；如果仍无权限，请联系具备配置管理权限的管理员。系统没有自动重试。",
        );
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        return;
      }
      setShowIssues(true);
      setError(
        result.status === 409
          ? "保存没有应用：草稿在你编辑期间已经变化。重新读取草稿后再提交；服务端保留了胜出的版本。"
          : `草稿没有保存（${result.code}）。服务端校验拒绝了表单或草稿版本已过期；重新读取后修正，系统没有自动重试。`,
      );
    },
  });

  const validateMutation = useMutation({
    mutationFn: (input: { context: string; revisionId: string }) =>
      validateAutomationDraft(token, { revisionId: input.revisionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result, input) => {
      if (result.ok) {
        if (input.context !== displayedContext) return;
        setValidationNotice({
          context: input.context,
          message: "草稿检查通过，零写入。明确发布后才会生效。",
        });
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        setError(
          unknownCommandMessage("草稿可能已经检查完成；检查本身不写入配置"),
        );
        return;
      }
      setError(
        `检查没有完成（${result.code}）。重新读取草稿后再试；检查本身不写入任何内容。`,
      );
    },
  });

  const testMutation = useMutation({
    mutationFn: (input: {
      context: string;
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
    onSuccess: (result, input) => {
      if (result.ok) {
        if (input.context !== displayedContext) return;
        const model = result.model;
        setTestResult({
          context: input.context,
          message:
            model.outcome === "success"
              ? `测试成功。${model.message} 下一步：${model.nextAction}`
              : `测试失败。${model.message} 下一步：${model.nextAction}`,
        });
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        setError(unknownTestMessage());
        return;
      }
      setError(
        result.status === 409
          ? "显示的修订已经过期，因此没有发送测试请求。重新读取草稿，再测试当前精确版本。"
          : `测试没有执行（${result.code}）。重新读取当前持久状态后再试；系统没有自动重试。`,
      );
    },
  });

  const activateMutation = useMutation({
    mutationFn: (input: {
      context: string;
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
    onSuccess: (result, input) => {
      if (result.ok) {
        if (input.context !== displayedContext) return;
        void queryClient.invalidateQueries({
          queryKey: [notificationDraftQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: [notificationDefinitionQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        guard.guardNavigation(() =>
          navigate({
            to: "/operations/notifications/webhooks/$webhookId",
            params: { webhookId },
            state: {
              notificationActivationOutcome: {
                webhookId,
                revisionId: result.model.activatedRevisionId,
                version: result.model.activatedVersion,
              },
            } as never,
          }),
        );
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        setError(unknownCommandMessage("草稿可能已经发布为已生效配置"));
        return;
      }
      setError(
        result.status === 409
          ? "发布没有执行：草稿已变化、包含其他 Webhook 定义或配置区段变化，或者已生效基线已移动。没有发布任何内容；重新读取草稿后重新准备只含本次 Webhook 的变更。"
          : `发布没有执行（${result.code}）。重新读取当前持久状态后再试；系统没有自动重试。`,
      );
    },
  });

  const busy =
    draftMutation.isPending ||
    saveMutation.isPending ||
    validateMutation.isPending ||
    testMutation.isPending ||
    activateMutation.isPending;

  const closeCard = () => {
    void navigate({ to: "/operations/notifications" });
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
      setConfirmActivate(false);
      setError(null);
      setSavedNotice(null);
      setValidationNotice(null);
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
    setForm({ ...currentForm, ...patch });
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
    setConfirmActivate(false);
    clearEvidence();
  };

  const discardRetainedLocalInput = () => {
    // Explicit choice after the open Draft disappeared: discard only the card
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
    canUseSavedVersion && loadedDraft?.actions.test.available === true;
  const canValidate =
    canUseSavedVersion && loadedDraft?.actions.validate.available === true;
  const canActivate =
    canUseSavedVersion &&
    draft !== null &&
    baseline !== null &&
    draft.revisionVersion === baseline.version &&
    draft.revisionStatus === "validated" &&
    loadedDraft?.actions.activate.available === true &&
    confirmActivate;

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
          ? "当前没有打开的草稿；你尚未保存的输入仍保留在此卡片中，不会写入服务端。"
          : draft === null
            ? "没有打开的草稿包含这个 Webhook 定义。"
            : readOnlyDraft
              ? "当前账号只能查看这个草稿，不能保存修改、检查或发布。"
              : "修改只写入打开的草稿；已生效配置在明确发布前保持不变。"
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
              {saveMutation.isPending ? "正在保存到草稿…" : "保存到草稿"}
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
        <NotificationCardStatus variant="error" title="草稿读取失败">
          <p>没有读取到打开的草稿，因此不能安全编辑或发布。</p>
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
        <NotificationCardStatus title="正在读取草稿">
          <p>读取打开的草稿及其精确版本。</p>
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
          <StatusBanner variant="info" title="没有可编辑的草稿">
            <p>
              {notificationReasonLabel(
                loadedDraft.actions.createDraft.reason,
                "需要一个打开的后继草稿，才能保存这个 Webhook 定义。",
              )}
            </p>
            <p>
              当前没有渲染可填写的表单；直接打开此地址不会写入配置，也不会发送测试。
            </p>
          </StatusBanner>
          <div className="mf-notification-actions">
            <Button
              type="button"
              disabled={
                !loadedDraft.actions.createDraft.available ||
                draftMutation.isPending
              }
              onClick={() => {
                if (loadedDraft.activeConfiguration !== null) {
                  draftMutation.mutate(
                    loadedDraft.activeConfiguration.revisionId,
                  );
                }
              }}
            >
              {draftMutation.isPending ? "正在创建后继草稿…" : "创建后继草稿"}
            </Button>
            <Button type="button" variant="secondary" onClick={closeCard}>
              返回通知列表
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy || draftQuery.isFetching}
              onClick={() => void draftQuery.refetch()}
            >
              {draftQuery.isFetching ? "正在读取…" : "读取最新草稿"}
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
                显示的是上次成功读取的草稿版本 {draft.revisionVersion}
                。恢复读取后再核对当前权限和草稿内容。
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
          <StatusBanner variant="warning" title="只能查看这个草稿">
            <p>
              {notificationReasonLabel(
                loadedDraft?.actions.save.reason ?? null,
                "当前账号没有保存这个草稿的权限。",
              )}
            </p>
            <p>
              你仍可查看下列持久草稿内容。要修改、检查或发布，请联系具备配置管理权限的管理员；此页面不会写入草稿、发送测试或发布配置。
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
                {draftQuery.isFetching ? "正在读取…" : "读取最新草稿"}
              </Button>
            </div>
          </StatusBanner>
          {error !== null && (
            <StatusBanner variant="error" title="草稿操作没有完成">
              <p>{error}</p>
            </StatusBanner>
          )}
          <div className="mf-notification-detail-badges">
            <span className="mf-notification-badge">
              只读草稿 · 版本 {draft.revisionVersion}
            </span>
            <span className="mf-notification-badge">
              {draft.revisionStatus === "validated" ? "已检查" : "草稿"}
            </span>
            <span className="mf-notification-badge">已生效配置不变</span>
          </div>
          <section className="mf-notification-form-section">
            <h3>草稿内容（只读）</h3>
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
                <dt>草稿修订</dt>
                <dd>{draft.revisionId}</dd>
                <dt>草稿版本</dt>
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
              !dirty
            ) {
              return;
            }
            setShowIssues(true);
            setTouched(new Set(ALL_FORM_FIELDS));
            if (issues.length > 0) {
              setError("请修正标有说明的字段后再保存。");
              return;
            }
            const values = canonicalWebhookForm(currentForm);
            setError(null);
            saveMutation.mutate({
              revisionId: baseline.revisionId,
              expectedVersion: baseline.version,
              object: buildWebhookObject(webhookId, values),
              values,
            });
          }}
        >
          {readDegraded && (
            <StatusBanner variant="warning" title="最新读取失败">
              <p>
                显示的是上次成功读取的草稿版本 {baseline.version}
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
              title="草稿已不再打开，本地输入已保留"
            >
              <p>
                读取显示这份打开的草稿已经不存在，通常表示另一位管理员已经保存并发布。
                你尚未保存的输入仍显示在下方；系统没有写入服务端，也没有把本地输入静默绑定到新的草稿修订。
              </p>
              <p>
                已生效配置可能已经变化。创建后继草稿后，再明确选择保留本地输入或采用服务端值；也可以直接放弃本地输入。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={!loadedDraft?.actions.createDraft.available || busy}
                  onClick={() => {
                    if (loadedDraft?.activeConfiguration != null) {
                      draftMutation.mutate(
                        loadedDraft.activeConfiguration.revisionId,
                      );
                    }
                  }}
                >
                  {draftMutation.isPending
                    ? "正在创建后继草稿…"
                    : "创建后继草稿"}
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
                  原草稿 · 版本 {baseline.version} · 已不再打开
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
                  已保存草稿 · 版本 {baseline.version} ·{" "}
                  {baseline.status === "validated" ? "已检查" : "草稿"}
                </span>
                {dirty && (
                  <span className="mf-notification-badge mf-notification-badge-warn">
                    有未保存修改
                  </span>
                )}
                {clean && (
                  <span className="mf-notification-badge mf-notification-badge-active">
                    当前输入与已保存草稿一致
                  </span>
                )}
                <span className="mf-notification-badge">已生效配置不变</span>
              </>
            ) : (
              <>
                <span className="mf-notification-badge">
                  原草稿 · 版本 {baseline.version}
                </span>
                <span className="mf-notification-badge mf-notification-badge-warn">
                  读取到新的草稿修订
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
                  {draftQuery.isFetching ? "正在读取…" : "读取最新草稿"}
                </Button>
              </span>
            )}
          </div>

          {savedNotice !== null && (
            <StatusBanner variant="success" title="已保存到草稿">
              <p>{savedNotice}</p>
            </StatusBanner>
          )}
          {remote !== null && (
            <StatusBanner
              variant="warning"
              title={
                remote.kind === "revision"
                  ? "读取到另一个草稿修订"
                  : "草稿已在其他位置更新"
              }
            >
              <p>
                {remote.kind === "revision"
                  ? `打开的是另一个草稿修订（版本 ${remote.version}）。`
                  : `耐久草稿现在是版本 ${remote.version}。`}
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
                测试、检查和发布只针对已保存的草稿版本。先保存当前输入，或明确放弃修改后再操作已保存版本。
              </p>
            </StatusBanner>
          )}
          {error !== null && (
            <StatusBanner variant="error" title="草稿操作没有完成">
              <p>{error}</p>
            </StatusBanner>
          )}
          {draft !== null && draft.validationErrors.length > 0 && (
            <StatusBanner variant="error" title="草稿检查发现">
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
                  checked={currentForm.enabled}
                  onChange={(event) =>
                    updateForm({ enabled: event.target.checked })
                  }
                />
                <span>
                  <strong>启用这个 Webhook</strong>
                  <small>
                    发布后才会使用；草稿内修改不影响当前已生效配置。
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

          {draft !== null && (
            <>
              <section className="mf-notification-form-section">
                <h3>检查与签名测试</h3>
                <p className="mf-notification-field-help">
                  检查和测试只针对已保存的草稿版本，两者都不会发布配置。
                </p>
                {!canUseSavedVersion && (
                  <p className="mf-notification-inline-reason">
                    {remote !== null
                      ? "先处理上面的并发变更。"
                      : "有未保存的修改：先保存，或放弃修改后再操作已保存版本。"}
                  </p>
                )}
                <div className="mf-notification-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!canValidate || busy}
                    title={notificationReasonLabel(
                      loadedDraft?.actions.validate.reason ?? null,
                      "当前不能检查草稿",
                    )}
                    onClick={() => {
                      if (baseline !== null) {
                        validateMutation.mutate({
                          context: displayedContext,
                          revisionId: baseline.revisionId,
                        });
                      }
                    }}
                  >
                    {validateMutation.isPending ? "正在检查…" : "检查草稿"}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!canTest || busy}
                    title={notificationReasonLabel(
                      loadedDraft?.actions.test.reason ?? null,
                      "当前不能发送签名测试",
                    )}
                    onClick={() => {
                      if (baseline !== null) {
                        testMutation.mutate({
                          context: displayedContext,
                          expectedRevisionId: baseline.revisionId,
                          expectedVersion: baseline.version,
                        });
                      }
                    }}
                  >
                    {testMutation.isPending
                      ? "正在发送签名测试…"
                      : "发送签名测试"}
                  </Button>
                </div>
                <p className="mf-notification-field-help">
                  发送签名测试会向接收端发送一次带签名的请求；不会创建投递，也不会自动重试。
                </p>
                {validationNotice !== null &&
                  validationNotice.context === displayedContext && (
                    <StatusBanner variant="success" title="草稿检查通过">
                      <p>{validationNotice.message}</p>
                    </StatusBanner>
                  )}
                {testResult !== null &&
                  testResult.context === displayedContext &&
                  canUseSavedVersion && (
                    <StatusBanner variant="info" title="签名测试结果">
                      <p>{testResult.message}</p>
                      <p>
                        结论只对发送时的已保存版本有效；输入或版本变化后需要重新测试。
                      </p>
                    </StatusBanner>
                  )}
              </section>

              <section className="mf-notification-form-section">
                <h3>发布已检查草稿</h3>
                <p className="mf-notification-field-help">
                  {loadedDraft?.actions.activate.available
                    ? "发布只在草稿的唯一变更就是这个已检查的 Webhook 定义时成功。任何兄弟定义或无关配置变化都会拒绝发布，并保留已生效配置和草稿。"
                    : `当前不能发布：${notificationReasonLabel(
                        loadedDraft?.actions.activate.reason ?? null,
                        "服务端未提供发布动作。",
                      )}`}
                </p>
                {dirty && (
                  <p className="mf-notification-inline-reason">
                    有未保存的修改，发布确认已失效。先保存并重新检查。
                  </p>
                )}
                {loadedDraft?.actions.activate.available && (
                  <div className="mf-notification-actions">
                    <label className="mf-notification-check">
                      <input
                        type="checkbox"
                        checked={confirmActivate}
                        disabled={!canUseSavedVersion || busy}
                        onChange={(event) => {
                          setConfirmActivate(event.target.checked);
                          if (!event.target.checked) {
                            setError(null);
                          }
                        }}
                      />
                      <span>我确认把当前已检查的草稿发布为新的已生效配置</span>
                    </label>
                    <Button
                      type="button"
                      disabled={!canActivate || busy}
                      onClick={() => {
                        if (baseline !== null) {
                          activateMutation.mutate({
                            context: displayedContext,
                            expectedRevisionId: baseline.revisionId,
                            expectedVersion: baseline.version,
                          });
                        }
                      }}
                    >
                      {activateMutation.isPending
                        ? "正在发布草稿…"
                        : "发布已检查草稿"}
                    </Button>
                  </div>
                )}
              </section>
            </>
          )}
        </form>
      )}
    </NotificationCard>
  );
}
