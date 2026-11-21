/**
 * V2 Webhook definition card.
 *
 * The card opens over the Notification definition list and reads the bounded
 * definition document: exact published Active identity, deployment-owned secret
 * readiness and the backend-advertised test/copy/enable/disable transports.
 * A signed test is bound to the exact displayed revision identity and version
 * while the configuration digest and the resolved secret remain server-side;
 * exactly one request is sent per explicit action and nothing is retried or
 * activated.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  copyWebhookDefinition,
  setWebhookDefinitionEnabled,
  testWebhookDefinition,
} from "../../shared/api/api-client";
import {
  notificationDefinitionQueryKey,
  notificationDefinitionQueryOptions,
  notificationListQueryKey,
} from "./notification-query";
import { useAuthorizedReadAuthorityRecovery } from "../../shared/auth/AuthorizedReadBoundary";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  activeConfigurationSummary,
  notificationEventLabel,
  notificationReasonLabel,
  secretReadinessDetail,
  secretReadinessLabel,
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

interface KnownOutcome {
  readonly title: string;
  readonly message: string;
}

function readCreatedOutcome(
  state: unknown,
  expectedWebhookId: string,
): KnownOutcome | null {
  if (state === null || typeof state !== "object") return null;
  const value = (state as Record<string, unknown>)["notificationCreateOutcome"];
  if (value === null || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  if (
    typeof record["webhookId"] !== "string" ||
    record["webhookId"] !== expectedWebhookId ||
    typeof record["revisionId"] !== "string" ||
    typeof record["version"] !== "number"
  ) {
    return null;
  }
  return {
    title: "定义已发布",
    message: `Webhook ${record["webhookId"]} 已发布为新的生效配置（版本 ${record["version"]}）。页面正在读取真实生效状态。`,
  };
}

function readActivationOutcome(
  state: unknown,
  expectedWebhookId: string,
): KnownOutcome | null {
  if (state === null || typeof state !== "object") return null;
  const value = (state as Record<string, unknown>)[
    "notificationActivationOutcome"
  ];
  if (value === null || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  if (
    typeof record["webhookId"] !== "string" ||
    record["webhookId"] !== expectedWebhookId ||
    typeof record["revisionId"] !== "string" ||
    typeof record["version"] !== "number"
  ) {
    return null;
  }
  return {
    title: "定义已发布为已生效配置",
    message: `Webhook ${record["webhookId"]} 已发布，版本 ${record["version"]}。页面正在读取真实已生效状态；读取失败时这条命令结果仍然有效。`,
  };
}

export function NotificationDetailPage() {
  const { webhookId } = useParams({
    from: "/operations/notifications/webhooks/$webhookId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{
    readonly context: string;
    readonly message: string;
  } | null>(null);

  const query = useQuery(notificationDefinitionQueryOptions(token, webhookId));
  useAuthorizedReadAuthorityRecovery(query);

  const liveDefinition = query.data?.ok === true ? query.data.model : null;
  const definition = useLastSuccessfulRead(liveDefinition);
  const readDegraded = liveDefinition === null && definition !== null;
  const document = definition?.document ?? null;
  const active = definition?.activeConfiguration ?? null;
  const displayedTestContext =
    active === null ? "" : `active:${active.revisionId}:${active.version}`;

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
        const model = result.model;
        if (input.context !== displayedTestContext) return;
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
          ? "显示的修订已经过期，因此没有发送测试请求。重新读取定义，再测试当前精确修订。"
          : `测试没有执行（${result.code}）。重新读取当前持久状态后再试；系统没有自动重试。`,
      );
    },
  });

  const definitionMutation = useMutation({
    mutationFn: (input: {
      kind: "copy" | "enable" | "disable";
      expectedVersion: number;
    }) => {
      const revisionId = definition?.activeConfiguration?.revisionId ?? null;
      if (revisionId === null) {
        return Promise.reject(new Error("no published definition"));
      }
      if (input.kind === "copy") {
        return copyWebhookDefinition(token, {
          revisionId,
          webhookId,
          expectedVersion: input.expectedVersion,
        });
      }
      return setWebhookDefinitionEnabled(token, {
        revisionId,
        webhookId,
        expectedVersion: input.expectedVersion,
        enabled: input.kind === "enable",
      });
    },
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result, input) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [notificationDefinitionQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: [notificationListQueryKey],
        });
        if (input.kind === "copy") {
          guard.guardNavigation(() =>
            navigate({
              to: "/operations/notifications/webhooks/$webhookId",
              params: { webhookId: result.model.id },
            }),
          );
        }
        return;
      }
      if (isUnknownCommandResult(result.status, result.code)) {
        setError(
          unknownCommandMessage(
            `${input.kind === "copy" ? "复制" : input.kind === "enable" ? "启用" : "停用"}可能已经写入定义`,
          ),
        );
        return;
      }
      setError(
        result.status === 409
          ? "定义在动作执行前已经变化。重新读取定义后再试；服务端保留了胜出的版本。"
          : `${input.kind === "copy" ? "复制" : input.kind === "enable" ? "启用" : "停用"}动作没有执行（${result.code}）。重新读取当前持久状态后再试；系统没有自动重试。`,
      );
    },
  });

  const busy = testMutation.isPending || definitionMutation.isPending;
  const closeCard = () => {
    void navigate({ to: "/operations/notifications" });
  };
  const guard = useNotificationCardGuard({
    busy,
    dirty: false,
    onClose: closeCard,
    onDiscard: () => setError(null),
    firstFieldId: "notification-detail-close",
    fallbackFocusId: "notification-definitions-background",
  });

  const knownOutcome =
    readActivationOutcome(location.state, webhookId) ??
    readCreatedOutcome(location.state, webhookId);
  const canEdit = definition?.actions.edit.available ?? false;
  const canCopy = definition?.actions.copy.available ?? false;
  const canEnable = definition?.actions.enable.available ?? false;
  const canDisable = definition?.actions.disable.available ?? false;
  const testContextActive =
    testResult !== null && testResult.context === displayedTestContext;

  return (
    <NotificationCard
      layerRef={guard.layerRef}
      closing={guard.closing}
      busy={busy}
      title={
        document === null ? `Webhook ${webhookId}` : `Webhook ${document.id}`
      }
      titleId="notification-detail-title"
      description={
        definition === null
          ? "读取精确的 Webhook 定义。"
          : "这个定义属于当前不可变的已生效配置。"
      }
      closeDisabled={busy}
      onRequestClose={guard.attemptClose}
      footer={
        <>
          <Button
            type="button"
            variant="secondary"
            id="notification-detail-close"
            disabled={busy}
            onClick={guard.attemptClose}
          >
            关闭
          </Button>
          {canEdit ? (
            <Button
              type="button"
              onClick={() =>
                guard.guardNavigation(() =>
                  navigate({
                    to: "/operations/notifications/editor/$webhookId",
                    params: { webhookId },
                  }),
                )
              }
            >
              编辑定义
            </Button>
          ) : (
            <Button
              type="button"
              variant="secondary"
              disabled
              title={definition?.actions.edit.reason ?? "当前没有可编辑的定义"}
            >
              编辑定义（不可用）
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
      {knownOutcome !== null && (
        <div className="mf-notification-attention">
          <StatusBanner variant="success" title={knownOutcome.title}>
            <p>{knownOutcome.message}</p>
          </StatusBanner>
        </div>
      )}
      {query.isError && definition === null && (
        <NotificationCardStatus variant="error" title="定义读取失败">
          <p>没有读取到精确的定义，因此不会提供测试或修改动作。</p>
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
        <NotificationCardStatus title="正在读取定义">
          <p>读取精确的 Webhook 定义和可用动作。</p>
        </NotificationCardStatus>
      )}
      {query.data !== undefined &&
        query.data.ok === false &&
        definition === null && (
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
      {definition !== null && document !== null && (
        <div className="mf-notification-card-scroll">
          {readDegraded && (
            <StatusBanner variant="warning" title="最新读取失败">
              <p>
                显示的是上次成功读取的定义。已知测试结果仍然有效；恢复读取后再执行新的测试或修改。
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
          <div className="mf-notification-detail-badges">
            <span className="mf-notification-badge mf-notification-badge-active">
              已生效
            </span>
            <span className="mf-notification-badge">
              {document.enabled ? "已启用" : "已停用"}
            </span>
            <span className="mf-notification-badge">
              密钥引用：{secretReadinessLabel(document.secretReadiness)}
            </span>
            {!document.structuralValid && (
              <span className="mf-notification-badge mf-notification-badge-danger">
                定义无效
              </span>
            )}
            {!readDegraded && (
              <span className="mf-notification-read-action">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy || query.isFetching}
                  onClick={() => void query.refetch()}
                >
                  {query.isFetching ? "正在读取…" : "读取最新定义"}
                </Button>
              </span>
            )}
          </div>

          {!document.structuralValid && document.validationError !== null && (
            <StatusBanner variant="error" title="定义无效">
              <p>{document.validationError}</p>
            </StatusBanner>
          )}

          <section className="mf-notification-form-section">
            <h3>定义</h3>
            <dl className="mf-notification-facts">
              <dt>HTTPS 接收地址</dt>
              <dd className="mf-notification-endpoint">{document.url}</dd>
              <dt>密钥引用</dt>
              <dd>{secretReadinessDetail(document.secretReadiness)}</dd>
              <dt>订阅事件</dt>
              <dd>
                {document.events.map((event) => (
                  <span className="mf-notification-event" key={event}>
                    {notificationEventLabel(event)}
                  </span>
                ))}
              </dd>
              <dt>超时与重试</dt>
              <dd>
                超时 {document.timeoutSeconds} 秒 · 最多尝试{" "}
                {document.maxAttempts} 次 · 重试 {document.baseRetrySeconds}–
                {document.maxRetrySeconds} 秒
              </dd>
            </dl>
            <details className="mf-notification-diagnostics">
              <summary>诊断信息</summary>
              <dl>
                <dt>定义状态</dt>
                <dd>当前生效配置</dd>
                <dt>Webhook 标识</dt>
                <dd>{document.id}</dd>
                <dt>事件标识</dt>
                <dd>{document.events.join(", ")}</dd>
                <dt>密钥引用状态</dt>
                <dd>{secretReadinessDetail(document.secretReadiness)}</dd>
                <dt>已生效配置</dt>
                <dd>
                  {activeConfigurationSummary(definition.activeConfiguration)}
                </dd>
                <dt>发布方式</dt>
                <dd>直接校验并发布为生效配置</dd>
              </dl>
            </details>
          </section>

          <section className="mf-notification-form-section">
            <h3>发送一次签名测试</h3>
            <p className="mf-notification-field-help">
              {definition.actions.test.available
                ? "会向接收端发送一次带签名的 HTTPS 请求，绑定当前精确修订。不会创建投递、不会发布配置，也不会自动重试。"
                : `测试不可用：${notificationReasonLabel(
                    definition.actions.test.reason,
                    "服务端未提供测试动作。",
                  )}`}
            </p>
            {definition.actions.test.available && (
              <div className="mf-notification-actions">
                <Button
                  type="button"
                  disabled={busy || readDegraded}
                  onClick={() => {
                    const revisionId = active?.revisionId ?? null;
                    const version = active?.version ?? null;
                    if (revisionId !== null && version !== null) {
                      testMutation.mutate({
                        context: displayedTestContext,
                        expectedRevisionId: revisionId,
                        expectedVersion: version,
                      });
                    }
                  }}
                >
                  {testMutation.isPending
                    ? "正在发送签名测试…"
                    : "发送签名测试"}
                </Button>
              </div>
            )}
            {testContextActive && (
              <StatusBanner variant="info" title="签名测试结果">
                <p>{testResult.message}</p>
                <p>
                  这是对发送时精确修订的测试结论；定义或版本变化后需要重新测试。
                </p>
              </StatusBanner>
            )}
          </section>

          <section className="mf-notification-form-section">
            <h3>定义内动作</h3>
            <p className="mf-notification-field-help">
              复制、启用和停用会直接校验并发布为新的生效配置快照；失败时当前
              Active 保持不变。
            </p>
            <div className="mf-notification-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={!canCopy || busy || readDegraded}
                title={notificationReasonLabel(
                  definition.actions.copy.reason,
                  "当前不能复制定义",
                )}
                onClick={() => {
                  if (
                    active?.version !== null &&
                    active?.version !== undefined
                  ) {
                    definitionMutation.mutate({
                      kind: "copy",
                      expectedVersion: active.version,
                    });
                  }
                }}
              >
                {definitionMutation.isPending ? "正在执行…" : "复制定义"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={!canEnable || busy || readDegraded}
                title={notificationReasonLabel(
                  definition.actions.enable.reason,
                  "当前不能启用定义",
                )}
                onClick={() => {
                  if (
                    active?.version !== null &&
                    active?.version !== undefined
                  ) {
                    definitionMutation.mutate({
                      kind: "enable",
                      expectedVersion: active.version,
                    });
                  }
                }}
              >
                启用定义
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={!canDisable || busy || readDegraded}
                title={notificationReasonLabel(
                  definition.actions.disable.reason,
                  "当前不能停用定义",
                )}
                onClick={() => {
                  if (
                    active?.version !== null &&
                    active?.version !== undefined
                  ) {
                    definitionMutation.mutate({
                      kind: "disable",
                      expectedVersion: active.version,
                    });
                  }
                }}
              >
                停用定义
              </Button>
            </div>
          </section>

          {error !== null && (
            <StatusBanner variant="error" title="动作没有完成">
              <p>{error}</p>
            </StatusBanner>
          )}
        </div>
      )}
    </NotificationCard>
  );
}
