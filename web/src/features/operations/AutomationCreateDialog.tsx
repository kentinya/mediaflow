/**
 * The Automation creation dialog.
 *
 * It opens over the existing Automation list and renders the shared Chinese
 * definition card (V2-AUTO-013/014): one form submission carries the explicit
 * optional enablement choice — default off — and submits the existing checked
 * create command against the exact Active authority read for this dialog. It
 * never creates a Draft, runs work or mutates Storage. A lost create response
 * is retained as an unknown command identity and may only be reconciled from
 * durable evidence; it is never replayed.
 *
 * A proved reconciliation proves what the create command did at its own
 * revision; it never proves what the definition looks like now. The durable
 * current-state evidence read from the current Active decides whether the
 * feedback says "still current", "succeeded but later modified",
 * "no longer present" or "current state unconfirmable".
 */

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  createAutomationDefinitionFocused,
  fetchAutomationFormAuthority,
  reconcileAutomationPublicationFocused,
  type AutomationMutationFailureDetails,
} from "../../shared/api/api-client";
import type { AutomationDefinitionDocumentModel } from "../../entities/operations/automation";
import type {
  AutomationCurrentDefinitionState,
  AutomationDefinitionFormAuthorityModel,
} from "../../entities/operations/automation-lifecycle";
import { Button } from "../../shared/ui/Button";
import { usePrincipalIdentity } from "./principal-identity-query";
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
  initialCreateForm,
  newAutomationDefinitionId,
  publicationFormFromCreateForm,
  scheduleKindPatch,
  validateCreateForm,
  type AutomationCreateForm,
  type CreateFormIssue,
  type CreateScheduleKind,
} from "./automation-create-form";
import {
  readPendingAutomationPublication,
  writePendingAutomationPublication,
  type AutomationPublicationAuthority,
  type PendingAutomationPublication,
} from "./automation-publication-session";

export interface AutomationCreateOutcomeMeta {
  readonly reconciled: true;
  readonly publishedEnabled: boolean;
  readonly currentState: AutomationCurrentDefinitionState;
}

export interface AutomationCreateDialogProps {
  readonly onClose: () => void;
  /**
   * One confirmed create (or its reconciliation) for the list feedback. The
   * definition is the definition the list should present: the proved
   * publication's own document only while it is still current, the current
   * saved document when a later command modified it, and `null` when the
   * current state cannot be named.
   */
  readonly onCreated: (
    definition: AutomationDefinitionDocumentModel | null,
    meta?: AutomationCreateOutcomeMeta,
  ) => void;
}

type CommandError =
  | { readonly kind: "local"; readonly message: string }
  | { readonly kind: "conflict"; readonly code: string }
  | {
      readonly kind: "rejected";
      readonly code: string;
      readonly details: AutomationMutationFailureDetails | undefined;
    }
  | { readonly kind: "unknown"; readonly code: string }
  | { readonly kind: "reconcile-unknown"; readonly code: string | null };

const COMMAND_ERROR_ID = "automation-create-command-error";
const DISCARD_CONTINUE_ID = "automation-create-discard-continue";

/** The one field that owns the current schedule choice when it is rejected. */
function scheduleFieldId(schedule: CreateScheduleKind): string {
  switch (schedule) {
    case "interval":
      return "automation-create-interval";
    case "daily":
      return "automation-create-daily-time";
    case "weekly":
      return "automation-create-weekly-time";
    case "cron":
      return "automation-create-cron";
  }
}

function activeAuthority(
  authority: AutomationDefinitionFormAuthorityModel,
): AutomationPublicationAuthority {
  return {
    revisionId: authority.active.revisionId,
    version: authority.active.revisionSequence,
    digest: authority.active.digest,
  };
}

function failureStageLabel(stage: string | undefined): string | null {
  switch (stage) {
    case "read":
      return "读取当前配置";
    case "compose":
      return "组合候选";
    case "validate":
      return "校验输入";
    case "persist":
      return "保存配置";
    case "prepare":
      return "准备发布";
    case "activate":
      return "激活配置";
    default:
      return null;
  }
}

function commandErrorMessage(error: CommandError): {
  readonly title: string;
  readonly body: string;
} {
  switch (error.kind) {
    case "local":
      return { title: "无法创建", body: error.message };
    case "conflict":
      return {
        title: "创建未生效",
        body:
          error.code === "automation_definition_duplicate"
            ? "内部 ID 已存在，配置没有被修改。输入已保留；请在诊断信息中重新生成 ID 后再创建。"
            : "当前配置已被其他操作更新，创建命令没有生效。输入、创建 ID 和启用选择已保留；请先重新核对当前配置，再明确创建。",
      };
    case "rejected": {
      const stage = failureStageLabel(error.details?.stage);
      const body =
        error.code === "automation_definition_invalid_field"
          ? "后端在组合候选时拒绝了这次输入，当前 Active 没有被改写。请先检查“运行时间”中的 Cron 表达式与 IANA 时区；如果仍然失败，再检查名称、来源范围与处理上限。输入和内部 ID 已保留；修正后可再次明确创建。"
          : error.code === "automation_execution_permission_required"
            ? "当前身份没有定时执行权限，创建并启用没有生效，当前 Active 没有被这次命令改写。输入、内部 ID 和启用选择已保留；可以先创建为停用，或改用有定时执行权限的身份提交。"
            : `${
                stage === null ? "后端拒绝了这次创建" : `在“${stage}”阶段被拒绝`
              }，当前 Active 没有被这次命令改写。输入和内部 ID 已保留，请按提示修正后再次明确创建。`;
      return { title: "创建未生效", body };
    }
    case "unknown":
      return {
        title: "创建结果待核对",
        body: "响应没有送达或无法解读，创建命令可能已经生效（包括启用）。系统不会自动重发；请使用“核对本次创建”读取真实持久结果。",
      };
    case "reconcile-unknown":
      return {
        title: "本次创建仍未证实",
        body: "核对没有找到可确认的发布结果，但也不能证明创建未发生。请保留当前页面稍后再次核对，或关闭后重新打开继续核对；不会重新创建。",
      };
  }
}

/**
 * The reconciliation feedback separates what the command did at its own
 * revision from the definition's current saved state; it never reports the
 * published outcome as the present one.
 */
export function reconciliationOutcomeCopy(
  publishedEnabled: boolean,
  currentState: AutomationCurrentDefinitionState,
  currentDefinition: AutomationDefinitionDocumentModel | null,
): string {
  const publishedFact = publishedEnabled ? "创建当时已启用" : "创建当时未启用";
  switch (currentState) {
    case "current":
      return publishedEnabled
        ? "已核对本次创建；已创建并启用，当前保存状态与之一致。"
        : "已核对本次创建；结果已持久发布，当前保存状态与之一致。";
    case "modified": {
      const currentEnabled = currentDefinition?.enabled === true;
      return `已核对本次创建：${publishedFact}；该定义之后被再次修改，当前为${
        currentEnabled ? "启用" : "停用"
      }状态。列表显示的是当前实际状态。`;
    }
    case "absent":
      return `已核对本次创建：${publishedFact}；该定义当前已不在生效配置中（可能已被移除）。`;
    case "unreadable":
      return `已核对本次创建：${publishedFact}；当前保存状态暂时无法确认。请刷新列表核对实际状态；不会重新创建或自动启停。`;
  }
}

export function AutomationCreateDialog({
  onClose,
  onCreated,
}: AutomationCreateDialogProps) {
  const token = useAuthToken();
  const principalIdentity = usePrincipalIdentity();
  const principalId = principalIdentity.resolved
    ? principalIdentity.principalId
    : null;
  const browserZone = useMemo(() => browserTimeZone(), []);
  const diagnosticsRef = useRef<HTMLDetailsElement | null>(null);
  const mountedRef = useRef(true);
  const submittingRef = useRef(false);
  const previewGeneration = useRef(0);
  const initializedRef = useRef(false);

  const [form, setForm] = useState<AutomationCreateForm | null>(null);
  const [observedAuthority, setObservedAuthority] =
    useState<AutomationPublicationAuthority | null>(null);
  const [idGenerationFailed, setIdGenerationFailed] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [showIssues, setShowIssues] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const [commandError, setCommandError] = useState<CommandError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);

  // The submitted-but-unconfirmed create command is read during render so a
  // reopened dialog restores the exact identity before the first interactive
  // frame. It is scoped to the confirmed principal and to create commands, so
  // an edit/toggle outcome can never be rendered or reconciled here.
  const [pendingOverride, setPendingOverride] = useState<{
    readonly owner: string | null;
    readonly value: PendingAutomationPublication | null;
  } | null>(null);
  const pendingPublication =
    pendingOverride?.owner === principalId
      ? pendingOverride.value
      : readPendingAutomationPublication(principalId, "create");
  const setPendingPublication = (
    value: PendingAutomationPublication | null,
  ) => {
    setPendingOverride({ owner: principalId, value });
    writePendingAutomationPublication(principalId, "create", value);
  };

  const card = useAutomationCardExit({
    onClose,
    shouldBlockLeave: () =>
      submittingRef.current || (dirty && pendingPublication === null),
    isSubmitting: () => submittingRef.current,
    hasUnsavedInput: () => dirty && pendingPublication === null,
    onDiscardCommitted: () => setDirty(false),
    firstFieldId: "automation-create-name",
    discardContinueId: DISCARD_CONTINUE_ID,
    focusReturnId: "automation-create-entry",
  });

  const authorityQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-authority"],
    queryFn: () => fetchAutomationFormAuthority(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnMount: "always",
  });
  const authorityResult = authorityQuery.data;
  const authorityModel =
    authorityResult !== undefined && authorityResult.ok
      ? authorityResult.model
      : null;
  const authorityFailed =
    authorityResult !== undefined && !authorityResult.ok
      ? authorityResult
      : null;

  // Initialize exactly once: a pending command restores its submitted form and
  // fence, while a fresh session generates one cryptographically random ID and
  // prefills the browser's IANA timezone (or the explicit UTC fallback).
  useEffect(() => {
    if (initializedRef.current) return;
    if (
      !authorityQuery.isFetchedAfterMount ||
      authorityModel === null ||
      !principalIdentity.resolved
    ) {
      return;
    }
    initializedRef.current = true;
    queueMicrotask(() => {
      if (!mountedRef.current) return;
      if (pendingPublication !== null) {
        setForm(
          createFormFromPublication(pendingPublication, browserZone.timeZone),
        );
        setObservedAuthority(pendingPublication.authority);
        return;
      }
      const id = newAutomationDefinitionId();
      if (id === null) {
        setIdGenerationFailed(true);
      }
      setForm(
        initialCreateForm({
          id: id ?? "",
          timeZone: browserZone.timeZone,
        }),
      );
      setObservedAuthority(activeAuthority(authorityModel));
    });
  }, [
    authorityModel,
    authorityQuery.isFetchedAfterMount,
    browserZone.timeZone,
    pendingPublication,
    principalIdentity.resolved,
  ]);

  useEffect(
    () => () => {
      mountedRef.current = false;
      previewGeneration.current += 1;
    },
    [],
  );

  const validationIssues: readonly CreateFormIssue[] = useMemo(
    () =>
      form !== null && authorityModel !== null
        ? validateCreateForm(form, authorityModel)
        : [],
    [form, authorityModel],
  );
  const submitBlocked = submitting && card.routeBlocked;

  function focusCommandError() {
    window.requestAnimationFrame(() => {
      document.getElementById(COMMAND_ERROR_ID)?.focus();
    });
  }

  const { attemptClose, commitClose, cancelDiscard, beginExit } = card;

  // Any pending leave - a close gesture, a blocked route or a blocked browser
  // back - shows the same pinned decision and moves focus to the safe action.
  const discardPromptOpen = card.discardPromptOpen;

  useEffect(() => {
    if (form === null) return;
    const target =
      pendingPublication !== null
        ? card.layerRef.current?.querySelector<HTMLElement>(
            '[data-automation-create-primary="true"]',
          )
        : document.getElementById("automation-create-name");
    target?.focus();
  }, [form === null]); // eslint-disable-line react-hooks/exhaustive-deps

  function updateFields(patch: Partial<AutomationCreateForm>) {
    setForm((current) =>
      current === null ? current : { ...current, ...patch },
    );
    setDirty(true);
    setNotice(null);
    setCommandError((current) =>
      current !== null &&
      (current.kind === "conflict" ||
        current.kind === "rejected" ||
        current.kind === "local")
        ? null
        : current,
    );
  }

  function updateSchedule(schedule: CreateScheduleKind) {
    if (form === null) return;
    updateFields(scheduleKindPatch(form, schedule));
  }

  function regenerateId() {
    if (pendingPublication !== null || submitting) return;
    const id = newAutomationDefinitionId();
    if (id === null) {
      setIdGenerationFailed(true);
      setCommandError({
        kind: "local",
        message:
          "当前浏览器无法提供安全的随机源，因此不能生成内部 ID。系统不会使用弱随机或时间戳代替；请刷新页面后重试。",
      });
      focusCommandError();
      return;
    }
    setIdGenerationFailed(false);
    setForm((current) => (current === null ? current : { ...current, id }));
    setCommandError(null);
    setNotice("已生成新的内部 ID。");
  }

  async function recheckAuthority() {
    if (rechecking) return;
    setRechecking(true);
    setCommandError(null);
    const result = await authorityQuery.refetch();
    if (!mountedRef.current) return;
    setRechecking(false);
    if (result.data !== undefined && result.data.ok) {
      setObservedAuthority(activeAuthority(result.data.model));
      setNotice(
        "已重新读取当前配置。输入和创建 ID 保持不变；请确认后再次明确创建。",
      );
    } else {
      setCommandError({
        kind: "local",
        message:
          "仍无法读取当前配置，因此没有更新创建所依据的 Active。请稍后重试；输入已保留。",
      });
      focusCommandError();
    }
  }

  function focusFirstIssue(issues: readonly CreateFormIssue[]) {
    const first = issues[0];
    if (first === undefined) return;
    if (first.fieldId === "automation-create-id") {
      if (diagnosticsRef.current !== null) diagnosticsRef.current.open = true;
    }
    window.requestAnimationFrame(() => {
      document.getElementById(first.fieldId)?.focus();
    });
  }

  function raiseLocalError(message: string) {
    setCommandError({ kind: "local", message });
    focusCommandError();
  }

  function submit() {
    if (
      form === null ||
      authorityModel === null ||
      submittingRef.current ||
      card.closing ||
      pendingPublication !== null
    ) {
      return;
    }
    setShowIssues(true);
    if (validationIssues.length > 0) {
      setCommandError(null);
      focusFirstIssue(validationIssues);
      return;
    }
    if (!principalIdentity.resolved) {
      raiseLocalError(
        principalIdentity.reason === "loading"
          ? "正在确认当前登录身份；确认后才能安全保留未决创建命令。请稍后重试。"
          : "当前登录身份暂不可用，暂时不能创建。请稍后刷新重试；输入已保留。",
      );
      return;
    }
    if (!authorityModel.actions.create) {
      raiseLocalError(
        "当前登录身份没有创建自动化任务的权限。没有提交任何配置修改；请使用有权限的身份重试。",
      );
      return;
    }
    if (form.enabled && !authorityModel.actions.createEnabled) {
      raiseLocalError(
        authorityModel.actionReasons?.createEnabled ??
          "当前身份没有定时执行权限，不能创建并启用。没有提交任何配置修改；可以先创建为停用。",
      );
      return;
    }
    if (observedAuthority === null) {
      raiseLocalError("当前 Active 配置尚未读取完成，不能创建。请刷新后重试。");
      return;
    }
    const candidate = buildCreateCandidate(form);
    if (candidate === null) {
      raiseLocalError("时间计划无法转换为现有字段，请检查后重试。");
      return;
    }
    const submittedForm = publicationFormFromCreateForm(form);
    const submittedAuthority = observedAuthority;
    setPendingPublication({
      definitionId: form.id.trim(),
      action: "create",
      form: submittedForm,
      authority: submittedAuthority,
    });
    submittingRef.current = true;
    setSubmitting(true);
    setCommandError(null);
    setNotice(null);
    void createAutomationDefinitionFocused(token, {
      object: candidate,
      authority: {
        expectedRevisionId: submittedAuthority.revisionId,
        expectedVersion: submittedAuthority.version,
        expectedDigest: submittedAuthority.digest,
      },
      // The explicit enablement choice rides beside the candidate; omitting
      // it keeps a disabled create, and only a true selection is ever sent.
      enabled: form.enabled === true ? true : undefined,
    }).then((result) => {
      if (!mountedRef.current) return;
      submittingRef.current = false;
      setSubmitting(false);
      // A leave attempted while the command was still in flight is released
      // together with the result, so the operator sees the real outcome first.
      card.releaseBlockedNavigation();
      if (result.ok) {
        const definition = result.model.definition;
        setPendingPublication(null);
        // The feedback reads the durable publication, never the local toggle:
        // what was actually published enabled is what this notice says.
        setNotice(
          definition !== null && definition.enabled
            ? "已创建并启用。"
            : "创建成功，尚未启用。",
        );
        setDirty(false);
        card.bypassBlockerRef.current = true;
        if (definition !== null) onCreated(definition);
        beginExit(onClose);
        return;
      }
      if (
        result.status === 0 ||
        result.status >= 500 ||
        result.code === "malformed_response"
      ) {
        setCommandError({ kind: "unknown", code: result.code });
        focusCommandError();
        return;
      }
      // A proved rejection releases the retained command; the input and ID stay
      // exactly as submitted so a correction never masquerades as a retry.
      setPendingPublication(null);
      if (result.status === 409) {
        setCommandError({ kind: "conflict", code: result.code });
        focusCommandError();
        return;
      }
      setCommandError({
        kind: "rejected",
        code: result.code,
        details: result.details,
      });
      if (result.code === "automation_definition_invalid_field") {
        // The time plan is the only candidate part the ordinary controls do not
        // fully validate for the backend, so the correction is located there.
        const fieldId = scheduleFieldId(form.schedule);
        window.requestAnimationFrame(() => {
          const field = document.getElementById(fieldId);
          (field ?? document.getElementById(COMMAND_ERROR_ID))?.focus();
        });
        return;
      }
      focusCommandError();
    });
  }

  function reconcile() {
    if (
      pendingPublication === null ||
      reconciling ||
      submittingRef.current ||
      !principalIdentity.resolved
    ) {
      return;
    }
    setReconciling(true);
    setCommandError(null);
    void reconcileAutomationPublicationFocused(
      token,
      pendingPublication.definitionId,
      {
        action: pendingPublication.action,
        object: buildCandidateFromPublicationForm(pendingPublication.form),
        expectedRevisionId: pendingPublication.authority.revisionId,
        expectedVersion: pendingPublication.authority.version,
        expectedDigest: pendingPublication.authority.digest,
      },
    ).then((result) => {
      if (!mountedRef.current) return;
      setReconciling(false);
      if (
        result.ok &&
        result.model.state === "published" &&
        result.model.publication !== null
      ) {
        const publishedEnabled =
          result.model.publication.definition?.enabled === true;
        const currentState = result.model.currentState ?? "unreadable";
        const currentDefinition = result.model.currentDefinition;
        setPendingPublication(null);
        setNotice(
          reconciliationOutcomeCopy(
            publishedEnabled,
            currentState,
            currentDefinition,
          ),
        );
        setDirty(false);
        card.bypassBlockerRef.current = true;
        // The list feedback presents the definition the list should show:
        // the proved publication only while it is still current, the current
        // saved document after a later modification, and nothing it cannot
        // name. It never re-creates or re-toggles anything.
        onCreated(
          currentState === "current" || currentState === "modified"
            ? (currentDefinition ?? null)
            : null,
          {
            reconciled: true,
            publishedEnabled,
            currentState,
          },
        );
        beginExit(onClose);
        return;
      }
      if (result.ok) {
        setCommandError({ kind: "reconcile-unknown", code: null });
        focusCommandError();
        return;
      }
      setCommandError({ kind: "reconcile-unknown", code: result.code });
      focusCommandError();
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  const libraryOptions =
    authorityModel === null
      ? []
      : authorityModel.resourceLibraries.filter((item) => item.enabled);
  const inFlight = submitting || reconciling;
  const createDisabledReason =
    authorityModel === null
      ? "正在读取当前配置权限…"
      : !principalIdentity.resolved
        ? principalIdentity.reason === "loading"
          ? "正在确认当前登录身份…"
          : "当前登录身份暂不可用，暂时不能创建。"
        : !authorityModel.actions.create
          ? "当前登录身份没有创建自动化任务的权限。"
          : submitting
            ? "正在创建，请稍候；系统不会自动重发创建命令。"
            : pendingPublication !== null
              ? "请先核对上次创建结果；系统不会自动重发创建命令。"
              : idGenerationFailed
                ? "无法生成安全的内部 ID；系统不会使用弱随机或时间戳代替。"
                : libraryOptions.length === 0
                  ? "没有已启用的资源库。请先在资源库设置中启用一个资源库。"
                  : null;
  const scheduleRejected =
    commandError !== null &&
    commandError.kind === "rejected" &&
    commandError.code === "automation_definition_invalid_field";
  const commandErrorCopy =
    commandError === null ? null : commandErrorMessage(commandError);
  const hasAttention =
    submitting ||
    pendingPublication !== null ||
    discardPromptOpen ||
    commandError !== null ||
    notice !== null ||
    (showIssues && validationIssues.length > 0);

  return (
    <AutomationCardShell
      layerRef={card.layerRef}
      closing={card.closing}
      busy={submitting || reconciling}
      title="新建自动化任务"
      titleId="automation-create-title"
      description="设置来源、运行时间与启用状态；创建本身不会扫描、整理或运行媒体文件。"
      closeLabel="关闭新建自动化任务"
      closeDisabled={submitting || card.closing}
      onRequestClose={attemptClose}
    >
      {authorityFailed !== null && (
        <div className="mf-automation-create-alert" role="alert">
          <strong>无法读取创建权限</strong>
          <p>
            {authorityFailed.status === 401
              ? "登录已失效，请重新登录后再创建。"
              : authorityFailed.status === 403
                ? "当前身份没有读取或创建自动化任务的权限。"
                : `读取当前配置失败（${authorityFailed.code}）。请刷新后重试；没有提交任何修改。`}
          </p>
        </div>
      )}
      {hasAttention && (
        <div
          className="mf-automation-create-attention"
          data-automation-create-attention="true"
        >
          {submitting && (
            <div className="mf-automation-create-pending" role="status">
              <strong>正在创建…</strong>
              <p>
                创建命令已提交，正在等待后端确认。请稍候；系统不会自动重发。
              </p>
              {submitBlocked && (
                <p>
                  已暂时阻止离开本页；收到结果后会在这里显示并解除这一限制。
                </p>
              )}
            </div>
          )}
          {pendingPublication !== null && !submitting && (
            <div className="mf-automation-create-pending" role="status">
              <strong>上次创建结果待核对</strong>
              <p>
                创建命令可能已经生效。系统不会自动重发；请使用底部的“核对本次创建”读取真实持久结果。
                关闭后再次打开会继续保留这次命令身份。
              </p>
            </div>
          )}
          {discardPromptOpen && (
            <AutomationCardDiscardPrompt
              questionId="automation-create-discard-question"
              detailId="automation-create-discard-detail"
              continueId={DISCARD_CONTINUE_ID}
              question="表单中有未保存的输入；关闭会丢弃这些修改。"
              detail="选择「继续填写」保留当前输入并回到原字段；选择「放弃修改」返回自动化列表。"
              onContinue={cancelDiscard}
              onDiscard={commitClose}
            />
          )}
          {commandError !== null && commandErrorCopy !== null && (
            <div
              className="mf-automation-create-alert"
              id={COMMAND_ERROR_ID}
              role="alert"
              tabIndex={-1}
            >
              <strong>{commandErrorCopy.title}</strong>
              <p>{commandErrorCopy.body}</p>
              {commandError.kind === "rejected" && (
                <p className="mf-automation-create-hint">
                  后端返回码：{commandError.code}（仅用于诊断）
                </p>
              )}
              {commandError.kind === "reconcile-unknown" &&
                commandError.code !== null && (
                  <p className="mf-automation-create-hint">
                    核对返回：{commandError.code}
                  </p>
                )}
              {scheduleRejected && form !== null && (
                <div className="mf-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      window.requestAnimationFrame(() => {
                        document
                          .getElementById(scheduleFieldId(form.schedule))
                          ?.focus();
                      });
                    }}
                  >
                    检查时间计划
                  </Button>
                </div>
              )}
              {commandError.kind === "conflict" &&
                commandError.code !== "automation_definition_duplicate" && (
                  <div className="mf-actions">
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={rechecking || card.closing}
                      onClick={() => {
                        void recheckAuthority();
                      }}
                    >
                      {rechecking ? "重新核对中…" : "重新核对当前配置"}
                    </Button>
                  </div>
                )}
              {commandError.kind === "conflict" &&
                commandError.code === "automation_definition_duplicate" && (
                  <div className="mf-actions">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={regenerateId}
                    >
                      重新生成内部 ID
                    </Button>
                  </div>
                )}
            </div>
          )}
          {notice !== null && (
            <p className="mf-automation-create-notice" role="status">
              {notice}
            </p>
          )}
          {showIssues &&
            validationIssues.length > 0 &&
            commandError === null && (
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
        </div>
      )}

      {form !== null && authorityModel !== null && (
        <form
          className="mf-automation-create-form"
          onSubmit={handleSubmit}
          noValidate
        >
          <div className="mf-automation-create-scroll">
            <AutomationDefinitionFormFields
              mode="create"
              form={form}
              authority={authorityModel}
              issues={validationIssues}
              showIssues={showIssues}
              scheduleRejected={scheduleRejected}
              onPatch={updateFields}
              onScheduleKind={updateSchedule}
            />

            <details
              className="mf-automation-create-diagnostics"
              ref={diagnosticsRef}
            >
              <summary>诊断信息（内部 ID 与发布机制）</summary>
              <dl>
                <dt>内部 ID</dt>
                <dd>
                  <code id="automation-create-id" tabIndex={-1}>
                    {form.id.length > 0 ? form.id : "未生成"}
                  </code>{" "}
                  {pendingPublication === null && (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={submitting || card.closing}
                      onClick={regenerateId}
                    >
                      重新生成 ID
                    </Button>
                  )}
                </dd>
                <dt>创建依据的 Active</dt>
                <dd>
                  <code>{observedAuthority?.revisionId ?? "尚未读取"}</code>
                  {observedAuthority !== null && (
                    <>
                      {" "}
                      · 版本 {observedAuthority.version} · digest{" "}
                      <code className="mf-automation-create-digest">
                        {observedAuthority.digest}
                      </code>
                    </>
                  )}
                </dd>
                <dt>发布机制</dt>
                <dd>
                  一次明确创建直接提交经过后端校验的候选并原子发布；不创建
                  Draft，不运行任务。选择“启用定时计划”后，同一次创建会按共享的发布链路完成启用。
                </dd>
              </dl>
            </details>
          </div>

          <footer className="mf-automation-create-footer">
            <div className="mf-automation-create-footer-note">
              {createDisabledReason !== null && (
                <span role="status">{createDisabledReason}</span>
              )}
              {createDisabledReason === null && pendingPublication === null && (
                <span>
                  {form.enabled
                    ? "将创建并启用：保存后按计划定时运行；运行一次请在任务列表发起。"
                    : "创建后未启用，可在列表中启用或运行一次。"}
                </span>
              )}
            </div>
            <div className="mf-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={inFlight || card.closing}
                onClick={attemptClose}
              >
                {pendingPublication !== null && !submitting ? "关闭" : "取消"}
              </Button>
              {submitting ? (
                <Button
                  type="button"
                  data-automation-create-primary="true"
                  disabled
                >
                  创建中…
                </Button>
              ) : pendingPublication !== null ? (
                <Button
                  type="button"
                  data-automation-create-primary="true"
                  disabled={
                    reconciling || card.closing || !principalIdentity.resolved
                  }
                  onClick={reconcile}
                >
                  {reconciling ? "核对中…" : "核对本次创建"}
                </Button>
              ) : (
                <Button
                  type="submit"
                  data-automation-create-primary="true"
                  disabled={
                    createDisabledReason !== null || submitting || card.closing
                  }
                >
                  {form.enabled ? "创建并启用" : "创建任务"}
                </Button>
              )}
            </div>
          </footer>
        </form>
      )}

      {form === null && authorityFailed === null && (
        <div className="mf-automation-create-loading" role="status">
          <p>
            {authorityModel === null || authorityQuery.isFetching
              ? "正在读取当前配置与创建权限…"
              : !principalIdentity.resolved
                ? principalIdentity.reason === "loading"
                  ? "正在确认当前登录身份…"
                  : "当前登录身份暂不可用。为避免未决结果归属不明，暂时不能创建；你仍可关闭此卡片。"
                : "正在准备创建表单…"}
          </p>
          {(authorityModel === null ||
            authorityQuery.isFetching ||
            (!principalIdentity.resolved &&
              principalIdentity.reason === "loading")) && (
            <>
              <span className="mf-automation-create-loading-line" />
              <span className="mf-automation-create-loading-line" />
              <span className="mf-automation-create-loading-line" />
              <span className="mf-automation-create-loading-line" />
            </>
          )}
        </div>
      )}

      {form === null && (
        <div className="mf-automation-create-footer">
          <Button
            type="button"
            variant="secondary"
            disabled={card.closing}
            onClick={attemptClose}
          >
            关闭
          </Button>
        </div>
      )}
    </AutomationCardShell>
  );
}
