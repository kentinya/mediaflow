/**
 * V2 Webhook definition create card.
 *
 * The card opens over the Notification definition list. It composes the
 * existing managed configuration object route: the bounded document is stored
 * inside the exact open successor Draft at its advertised optimistic version.
 * Only canonical Webhook fields are submitted; the server's canonical
 * validator rejects unknown fields, literal secrets, unsafe schemes and
 * credential-bearing endpoint components, so the client mirrors those bounds
 * for friction-free input but never becomes the authority.
 *
 * No editable Draft means no fillable form: the card explains the exact next
 * action and never lets pointer or keyboard reach an invalid submission.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useAuthGeneration, useAuthToken } from "../../shared/api/auth-context";
import {
  createWebhookDefinition,
  fetchAuthenticatedPrincipal,
  testWebhookDefinitionForm,
} from "../../shared/api/api-client";
import { reconcileSystemSettings } from "../../shared/api/configuration-api";
import {
  notificationListQueryKey,
  notificationListQueryOptions,
} from "./notification-query";
import { useAuthorizedReadAuthorityRecovery } from "../../shared/auth/AuthorizedReadBoundary";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  buildWebhookObject,
  draftStatusLabel,
  notificationEventLabel,
  notificationReasonLabel,
  sameWebhookForm,
  webhookFormIssueFor,
  webhookFormIssues,
  type WebhookFormValues,
  isUnknownCommandResult,
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

const INITIAL_FORM: WebhookFormValues = {
  url: "",
  secretEnv: "",
  events: [],
  enabled: true,
  timeoutSeconds: "10",
  maxAttempts: "5",
  baseRetrySeconds: "5",
  maxRetrySeconds: "300",
};

const ALL_FORM_FIELDS = [
  "url",
  "secretEnv",
  "events",
  "timeoutSeconds",
  "maxAttempts",
  "baseRetrySeconds",
  "maxRetrySeconds",
] as const;

export function NotificationNewPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [webhookId, setWebhookId] = useState("");
  const [form, setForm] = useState<WebhookFormValues>(INITIAL_FORM);
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const [showIssues, setShowIssues] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
  const [reconciliation, setReconciliation] = useState<string | null>(null);
  const [reconciledVersion, setReconciledVersion] = useState<number | null>(
    null,
  );
  const verifiedSubmissionRef = useRef<string | null>(null);
  const verificationInFlightRef = useRef(false);
  const verifyOutcomeRef = useRef<(pending: PendingNotificationApply) => void>(
    () => {},
  );

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

  const query = useQuery(notificationListQueryOptions(token));
  useAuthorizedReadAuthorityRecovery(query);

  const createMutation = useMutation({
    mutationFn: (input: {
      revisionId: string;
      expectedVersion: number;
      object: Record<string, unknown>;
      webhookId: string;
      testEvidenceId: string;
      submissionId: string;
    }) =>
      createWebhookDefinition(token, {
        revisionId: input.revisionId,
        expectedVersion: input.expectedVersion,
        object: input.object,
        testEvidenceId: input.testEvidenceId,
        submissionId: input.submissionId,
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setReconciliation(null);
    },
    onSuccess: (result, input) => {
      if (result.ok) {
        setPendingApply(null);
        setAwaitingVerification(false);
        writePendingNotificationApply(
          principalId,
          notificationApplyScope("create", input.webhookId),
          null,
        );
        verifiedSubmissionRef.current = input.submissionId;
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        const createdId = result.model.id;
        // The bound model is the exact created identity; the known result is
        // delivered to the detail card even if its follow-up read is slow.
        guard.guardNavigation(() =>
          navigate({
            to: "/operations/notifications/webhooks/$webhookId",
            params: { webhookId: createdId },
            state: {
              notificationCreateOutcome: {
                webhookId: createdId,
                revisionId: input.revisionId,
                version: result.model.version,
              },
            } as never,
          }),
        );
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        const pending: PendingNotificationApply = {
          submissionId: input.submissionId,
          webhookId: input.webhookId,
          baselineRevisionId: input.revisionId,
          baselineVersion: input.expectedVersion,
        };
        setPendingApply(pending);
        setAwaitingVerification(true);
        writePendingNotificationApply(
          principalId,
          notificationApplyScope("create", input.webhookId),
          pending,
        );
        setError(
          "应用结果待核实：本次请求没有收到可确认的回包。系统不会重复发布；正在用同一请求身份只读核对本次结果和当前生效配置。",
        );
        return;
      }
      setPendingApply(null);
      setAwaitingVerification(false);
      setShowIssues(true);
      setError(
        result.status === 409
          ? "定义没有发布：配置在你编辑期间已经变化，或签名测试证据与当前表单不一致。重新读取并对当前表单成功测试后再提交；服务端保留了胜出的版本。"
          : `定义没有发布（${result.code}）。修正表单后重试；系统没有自动重试。`,
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
        webhookId: webhookId.trim(),
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
        setTestResult({
          context: input.context,
          success: result.model.outcome === "success",
          evidenceId: result.model.testEvidenceId,
          message:
            result.model.outcome === "success"
              ? `签名测试成功。${result.model.message} 下一步：${result.model.nextAction}`
              : `签名测试失败。${result.model.message} 下一步：${result.model.nextAction}`,
        });
        return;
      }
      setError(
        result.status === 409
          ? "当前表单已变化，因此没有发送测试请求；请核对后重试。"
          : `测试没有执行（${result.code}）。系统没有自动重试。`,
      );
    },
  });

  const busy = createMutation.isPending || testMutation.isPending || verifying;
  const closeCard = () => {
    void navigate({ to: "/operations/notifications" });
  };
  const dirty =
    webhookId.trim().length > 0 || !sameWebhookForm(form, INITIAL_FORM);
  const createInFlight = createMutation.isPending;
  const guard = useNotificationCardGuard({
    busy,
    dirty,
    onClose: closeCard,
    onDiscard: () => {
      setWebhookId("");
      setForm(INITIAL_FORM);
      setTouched(new Set());
      setShowIssues(false);
      setError(null);
    },
    firstFieldId: "notification-new-id",
    fallbackFocusId: "notification-definitions-background",
  });

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
      const refreshed = await query.refetch();
      const model = refreshed.data?.ok === true ? refreshed.data.model : null;
      const currentVersion =
        typeof model?.activeConfiguration?.version === "number"
          ? model.activeConfiguration.version
          : null;
      const state =
        typeof result.state === "string" ? result.state : "UNRESOLVED";
      const committedVersion =
        typeof result.committedRevisionVersion === "number"
          ? result.committedRevisionVersion
          : null;
      const readShowsCommitted =
        currentVersion !== null && currentVersion !== pending.baselineVersion;
      setReconciledVersion(
        state === "COMMITTED" &&
          !readShowsCommitted &&
          committedVersion !== null
          ? committedVersion
          : currentVersion,
      );
      if (state === "UNRESOLVED") {
        setReconciliation("待核实");
        setError(
          "无法证明本次请求的持久结果；应用保持阻止，系统没有重新发布。恢复连接后可再次自动核实。",
        );
        return;
      }
      setAwaitingVerification(false);
      setPendingApply(null);
      writePendingNotificationApply(
        principalId,
        notificationApplyScope("create", pending.webhookId),
        null,
      );
      if (state === "COMMITTED" || state === "SUPERSEDED") {
        setReconciliation(
          state === "COMMITTED"
            ? "本次创建已确认发布"
            : "本次创建已确认发布，之后的发布已成为当前生效值",
        );
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        guard.guardNavigation(() =>
          navigate({
            to: "/operations/notifications/webhooks/$webhookId",
            params: { webhookId: pending.webhookId },
            state: {
              notificationCreateOutcome: {
                webhookId: pending.webhookId,
                revisionId: pending.baselineRevisionId,
                version: currentVersion,
              },
            } as never,
          }),
        );
      } else {
        setReconciliation("本次创建未发布");
        setError(
          `已通过同一请求身份的持久证据确认本次没有发布；当前生效配置版本为 ${currentVersion ?? "未知"}，表单输入仍保留。`,
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
    const scope = notificationApplyScope("create", "");
    const stored = readPendingNotificationApply(principalId, scope);
    if (stored === null) return;
    setWebhookId(stored.webhookId);
    setPendingApply((previous) => previous ?? stored);
    setAwaitingVerification(true);
    setReconciliation(null);
  }, [principalId]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (!awaitingVerification || pendingApply === null || busy) return;
    if (verifiedSubmissionRef.current === pendingApply.submissionId) return;
    void verifyApplicationOutcome(pendingApply);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [awaitingVerification, pendingApply, busy]);

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "hidden") return;
      if (awaitingVerification && pendingApply !== null) {
        verifyOutcomeRef.current(pendingApply);
        return;
      }
      void query.refetch();
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
  }, [awaitingVerification, pendingApply, query.refetch]);

  const issues = webhookFormIssues(form);
  const testContext = `${form.url}\u0000${form.secretEnv}`;
  const testedForCurrentForm =
    testResult !== null &&
    testResult.success &&
    testResult.evidenceId !== null &&
    testResult.context === testContext &&
    webhookId.trim().length > 0;
  const fieldIssue = (field: string): string | null =>
    showIssues || touched.has(field)
      ? webhookFormIssueFor(issues, field as (typeof ALL_FORM_FIELDS)[number])
      : null;
  const markTouched = (field: string) =>
    setTouched((previous) => new Set(previous).add(field));

  const livePage = query.data?.ok === true ? query.data.model : null;
  const page = useLastSuccessfulRead(livePage);
  const readDegraded = livePage === null && page !== null;
  const create = page?.actions.create ?? null;
  const draft = page?.draftState ?? null;
  const activeConfiguration = page?.activeConfiguration ?? null;
  const draftReady =
    page !== null &&
    create?.available === true &&
    (draft?.present === true || activeConfiguration !== null);
  const revisionId = draft?.present
    ? draft.revisionId
    : (activeConfiguration?.revisionId ?? null);
  const revisionVersion = draft?.present
    ? draft.revisionVersion
    : (activeConfiguration?.version ?? null);

  const title = "新建 Webhook";
  const titleId = "notification-new-title";

  return (
    <NotificationCard
      layerRef={guard.layerRef}
      closing={guard.closing}
      busy={busy}
      title={title}
      titleId={titleId}
      description="点击「应用更改」后，后端会校验并原子发布为新的生效配置。"
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
          {draftReady && (
            <Button
              type="submit"
              form="notification-new-form"
              disabled={
                busy ||
                awaitingVerification ||
                pendingApply !== null ||
                !testedForCurrentForm
              }
            >
              {createMutation.isPending ? "正在应用…" : "应用更改"}
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
      {query.isError && page === null && (
        <NotificationCardStatus variant="error" title="配置状态读取失败">
          <p>没有读取到当前生效配置，因此不能安全创建定义。</p>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void query.refetch()}
              disabled={query.isFetching}
            >
              {query.isFetching ? "正在重试…" : "重试读取"}
            </Button>
          </div>
        </NotificationCardStatus>
      )}
      {query.data === undefined && !query.isError && (
        <NotificationCardStatus title="正在读取配置状态">
          <p>读取当前生效的 Webhook 定义与配置身份。</p>
        </NotificationCardStatus>
      )}
      {query.data !== undefined && query.data.ok === false && page === null && (
        <NotificationCardStatus
          variant="error"
          title={query.data.failure.title}
        >
          <p>{query.data.failure.nextAction}</p>
          <div className="mf-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void query.refetch()}
              disabled={query.isFetching}
            >
              {query.isFetching ? "正在重试…" : "重试读取"}
            </Button>
          </div>
        </NotificationCardStatus>
      )}
      {page !== null && !draftReady && (
        <div className="mf-notification-card-scroll">
          <StatusBanner variant="info" title="当前不能新建 Webhook">
            <p>
              {notificationReasonLabel(
                create?.reason ?? draft?.reason ?? null,
                "需要当前生效配置才能发布 Webhook 定义。",
              )}
            </p>
            <p>
              当前没有可安全采用的配置身份；页面不会渲染可填写的表单，也不会提交任何内容。
            </p>
          </StatusBanner>
          <div className="mf-notification-actions">
            <Button type="button" variant="secondary" onClick={closeCard}>
              返回通知列表
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy || query.isFetching}
              onClick={() => void query.refetch()}
            >
              {query.isFetching ? "正在读取…" : "读取当前配置状态"}
            </Button>
          </div>
          {error !== null && (
            <StatusBanner variant="error" title="操作没有完成">
              <p>{error}</p>
            </StatusBanner>
          )}
        </div>
      )}
      {draftReady && revisionId !== null && (
        <form
          id="notification-new-form"
          className="mf-notification-card-scroll"
          onSubmit={(event) => {
            event.preventDefault();
            if (
              busy ||
              readDegraded ||
              awaitingVerification ||
              pendingApply !== null
            ) {
              return;
            }
            if (principalId === null) {
              setError(
                "还没有读到当前账号身份，无法保存可核实的请求标识；稍后重试。",
              );
              return;
            }
            setShowIssues(true);
            setTouched(new Set(ALL_FORM_FIELDS));
            if (issues.length > 0 && webhookId.trim().length === 0) {
              setError("请补全标有说明的字段后再保存。");
              return;
            }
            if (issues.length > 0) {
              setError("请修正标有说明的字段后再保存。");
              return;
            }
            if (!testedForCurrentForm) {
              setError("应用前必须对当前地址和签名引用成功完成一次签名测试。");
              return;
            }
            if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(webhookId.trim())) {
              setError("标识符必须是以字母或数字开头的 1–64 个 URI 安全字符。");
              return;
            }
            if (revisionId === null || revisionVersion === null) {
              setError("当前配置缺少精确版本，不能安全保存。重新读取后再试。");
              return;
            }
            const submissionId = newNotificationSubmissionId();
            if (submissionId === null) {
              setError(
                "无法生成安全的请求标识；本次没有发送写入，请更新浏览器后重试。",
              );
              return;
            }
            setError(null);
            setReconciliation(null);
            createMutation.mutate({
              revisionId,
              expectedVersion: revisionVersion,
              object: buildWebhookObject(webhookId.trim(), form),
              webhookId: webhookId.trim(),
              testEvidenceId: testResult.evidenceId,
              submissionId,
            });
          }}
        >
          {awaitingVerification && pendingApply !== null && (
            <StatusBanner variant="error" title="应用结果待核实">
              <p>
                本次请求没有收到可确认的回包，可能已经发布，也可能没有。
                正在用同一请求身份只读核对本次结果和当前生效配置；核实期间不会再次发布，系统不会自动重发发布请求。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={verifying || busy}
                  onClick={() => void verifyApplicationOutcome(pendingApply)}
                >
                  {verifying ? "核实中…" : "核实当前状态"}
                </Button>
              </div>
            </StatusBanner>
          )}
          {reconciliation !== null && (
            <StatusBanner
              variant={
                reconciliation.includes("已确认") ? "success" : "warning"
              }
              title="本次创建结果"
            >
              <p>
                {reconciliation}；当前生效配置版本：
                {reconciledVersion ?? "不可用"}。页面没有重新发布。
              </p>
            </StatusBanner>
          )}
          {readDegraded && (
            <StatusBanner variant="warning" title="最新读取失败">
              <p>
                显示的是上次成功读取的配置状态，已知命令结果仍然有效。恢复读取后再提交新的内容。
              </p>
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void query.refetch()}
                  disabled={query.isFetching}
                >
                  {query.isFetching ? "正在重试…" : "重试读取"}
                </Button>
              </div>
            </StatusBanner>
          )}
          {!readDegraded && (
            <div className="mf-notification-state-strip">
              <span className="mf-notification-badge">
                生效配置 · 版本 {revisionVersion ?? "未知"} ·{" "}
                {draftStatusLabel(
                  draft?.present ? draft.revisionStatus : "active",
                )}
              </span>
              <span className="mf-notification-badge">已生效配置不变</span>
              <span className="mf-notification-read-action">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy || query.isFetching}
                  onClick={() => void query.refetch()}
                >
                  {query.isFetching ? "正在读取…" : "读取最新配置状态"}
                </Button>
              </span>
            </div>
          )}
          <StatusBanner variant="info" title="先测试，再应用">
            <p>
              定义将发布为新的生效快照（当前版本 {revisionVersion ?? "未知"}）
              。已生效配置在明确发布前保持不变。
            </p>
          </StatusBanner>
          <section className="mf-notification-form-section">
            <h3>签名测试</h3>
            <p className="mf-notification-field-help">
              针对当前表单中的接收地址和签名密钥引用发送一次带签名的请求；不会创建投递、不会自动重试，也不会改变配置。修改地址或密钥引用后需重新测试。
            </p>
            <div className="mf-notification-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={
                  busy ||
                  issues.length > 0 ||
                  webhookId.trim().length === 0 ||
                  revisionId === null ||
                  revisionVersion === null
                }
                onClick={() => {
                  if (revisionId === null || revisionVersion === null) return;
                  testMutation.mutate({
                    context: testContext,
                    webhook: buildWebhookObject(webhookId.trim(), form),
                    revisionId,
                    revisionVersion,
                  });
                }}
              >
                {testMutation.isPending ? "正在发送签名测试…" : "发送签名测试"}
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
          {error !== null && (
            <StatusBanner variant="error" title="定义没有创建">
              <p>{error}</p>
            </StatusBanner>
          )}

          <section className="mf-notification-form-section">
            <h3>基本设置</h3>
            <div className="mf-notification-form-grid">
              <div className="mf-notification-field">
                <label htmlFor="notification-new-id">标识符</label>
                <input
                  id="notification-new-id"
                  value={webhookId}
                  disabled={createInFlight}
                  maxLength={64}
                  autoCapitalize="off"
                  spellCheck={false}
                  aria-invalid={
                    (showIssues || touched.has("id")) &&
                    !/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(webhookId.trim())
                  }
                  onChange={(event) => {
                    setWebhookId(event.target.value);
                    markTouched("id");
                  }}
                  onBlur={() => markTouched("id")}
                />
                <p className="mf-notification-field-help">
                  1–64 个字母、数字、点、下划线或连字符；创建后不能修改。
                </p>
                {(showIssues || touched.has("id")) &&
                  !/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(
                    webhookId.trim(),
                  ) && (
                    <p className="mf-notification-field-error">
                      标识符必须是以字母或数字开头的 1–64 个 URI 安全字符。
                    </p>
                  )}
              </div>
              <div className="mf-notification-field mf-notification-field-full">
                <label htmlFor="notification-new-url">HTTPS 接收地址</label>
                <input
                  id="notification-new-url"
                  value={form.url}
                  disabled={createInFlight}
                  maxLength={2048}
                  inputMode="url"
                  autoCapitalize="off"
                  spellCheck={false}
                  placeholder="https://example.invalid/hooks/mediaflow"
                  aria-invalid={fieldIssue("url") !== null}
                  aria-describedby="notification-new-url-help"
                  onChange={(event) => {
                    setForm({ ...form, url: event.target.value });
                    markTouched("url");
                  }}
                  onBlur={() => markTouched("url")}
                />
                <p
                  className="mf-notification-field-help"
                  id="notification-new-url-help"
                >
                  只接受 HTTPS；不能包含用户名、密码、查询字符串或片段。
                </p>
                {fieldIssue("url") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("url")}
                  </p>
                )}
              </div>
              <div className="mf-notification-field mf-notification-field-full">
                <label htmlFor="notification-new-secret">
                  密钥环境变量引用
                </label>
                <input
                  id="notification-new-secret"
                  value={form.secretEnv}
                  disabled={createInFlight}
                  maxLength={128}
                  autoCapitalize="off"
                  spellCheck={false}
                  placeholder="MEDIAFLOW_WEBHOOK_SECRET"
                  aria-invalid={fieldIssue("secretEnv") !== null}
                  onChange={(event) => {
                    setForm({ ...form, secretEnv: event.target.value });
                    markTouched("secretEnv");
                  }}
                  onBlur={() => markTouched("secretEnv")}
                />
                <p className="mf-notification-field-help">
                  部署环境提供这个变量的值；页面只保存变量名，从不读取或显示密钥值。
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
                  {page.supportedEvents.map((event) => (
                    <label key={event} className="mf-notification-check">
                      <input
                        type="checkbox"
                        disabled={createInFlight}
                        checked={form.events.includes(event)}
                        onChange={(changeEvent) => {
                          const events = changeEvent.target.checked
                            ? [...form.events, event]
                            : form.events.filter((item) => item !== event);
                          setForm({ ...form, events });
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
                  disabled={createInFlight}
                  checked={form.enabled}
                  onChange={(event) =>
                    setForm({ ...form, enabled: event.target.checked })
                  }
                />
                <span>
                  <strong>启用这个 Webhook</strong>
                  <small>应用后会发布到当前生效配置。</small>
                </span>
              </label>
            </div>
          </section>

          <section className="mf-notification-form-section">
            <h3>超时与重试</h3>
            <div className="mf-notification-form-grid">
              <div className="mf-notification-field">
                <label htmlFor="notification-new-timeout">请求超时（秒）</label>
                <input
                  id="notification-new-timeout"
                  value={form.timeoutSeconds}
                  disabled={createInFlight}
                  inputMode="decimal"
                  aria-invalid={fieldIssue("timeoutSeconds") !== null}
                  onChange={(event) => {
                    setForm({ ...form, timeoutSeconds: event.target.value });
                    markTouched("timeoutSeconds");
                  }}
                />
                <p className="mf-notification-field-help">0.1–120 秒。</p>
                {fieldIssue("timeoutSeconds") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("timeoutSeconds")}
                  </p>
                )}
              </div>
              <div className="mf-notification-field">
                <label htmlFor="notification-new-attempts">最大尝试次数</label>
                <input
                  id="notification-new-attempts"
                  value={form.maxAttempts}
                  disabled={createInFlight}
                  inputMode="numeric"
                  aria-invalid={fieldIssue("maxAttempts") !== null}
                  onChange={(event) => {
                    setForm({ ...form, maxAttempts: event.target.value });
                    markTouched("maxAttempts");
                  }}
                />
                <p className="mf-notification-field-help">1–20 次。</p>
                {fieldIssue("maxAttempts") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("maxAttempts")}
                  </p>
                )}
              </div>
              <div className="mf-notification-field">
                <label htmlFor="notification-new-base-retry">
                  基础重试间隔（秒）
                </label>
                <input
                  id="notification-new-base-retry"
                  value={form.baseRetrySeconds}
                  disabled={createInFlight}
                  inputMode="decimal"
                  aria-invalid={fieldIssue("baseRetrySeconds") !== null}
                  onChange={(event) => {
                    setForm({
                      ...form,
                      baseRetrySeconds: event.target.value,
                    });
                    markTouched("baseRetrySeconds");
                  }}
                />
                {fieldIssue("baseRetrySeconds") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("baseRetrySeconds")}
                  </p>
                )}
              </div>
              <div className="mf-notification-field">
                <label htmlFor="notification-new-max-retry">
                  最大重试间隔（秒）
                </label>
                <input
                  id="notification-new-max-retry"
                  value={form.maxRetrySeconds}
                  disabled={createInFlight}
                  inputMode="decimal"
                  aria-invalid={fieldIssue("maxRetrySeconds") !== null}
                  onChange={(event) => {
                    setForm({
                      ...form,
                      maxRetrySeconds: event.target.value,
                    });
                    markTouched("maxRetrySeconds");
                  }}
                />
                {fieldIssue("maxRetrySeconds") !== null && (
                  <p className="mf-notification-field-error">
                    {fieldIssue("maxRetrySeconds")}
                  </p>
                )}
              </div>
            </div>
            <p className="mf-notification-field-help">
              暂时失败会按有界退避重试；其他 4xx
              会进入死信。测试请求不会创建投递。
            </p>
          </section>
        </form>
      )}
    </NotificationCard>
  );
}
