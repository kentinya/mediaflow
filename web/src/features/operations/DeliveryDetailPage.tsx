/**
 * V2 Notification delivery detail and exact recovery card.
 *
 * The card opens over the filtered delivery list and reads the bounded
 * delivery detail: durable status, attempts, response category, lease state,
 * known receiver effects, at-least-once implications and the
 * backend-advertised recovery actions. Recovery submits the exact delivery
 * identity plus the observed status/update fence, requires explicit
 * confirmation, and is never retried automatically after stale state,
 * conflict, denial or transport failure.
 *
 * A successful recovery command keeps its known result even when the
 * follow-up read fails; the page does not claim an unobserved state.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearch,
} from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  requeueDeadLetterDelivery,
  resolveStaleDelivery,
} from "../../shared/api/api-client";
import {
  notificationDeliveryQueryKey,
  notificationDeliveryQueryOptions,
  notificationDeliveriesQueryKey,
} from "./notification-query";
import { NOTIFICATION_DELIVERY_STATUSES } from "../../entities/operations/notification";
import { useAuthorizedReadAuthorityRecovery } from "../../shared/auth/AuthorizedReadBoundary";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  deliveryStatusLabel,
  failureCategoryLabel,
  formatNotificationTime,
  knownNotificationEffects,
  leaseStateLabel,
  notificationEventLabel,
  notificationReasonLabel,
  isUnknownCommandResult,
  unknownCommandMessage,
} from "./notification-presentation";
import {
  NotificationCard,
  NotificationCardStatus,
  NotificationDiscardPrompt,
  useLastSuccessfulRead,
  useNotificationCardGuard,
} from "./notification-card";

function nextStepForStatus(status: string): string {
  switch (status) {
    case "pending":
      return "等待 Notification Worker 领取并发送。";
    case "delivering":
      return "投递正在进行；租约到期后可检查过期租约恢复。";
    case "retry":
      return "等待有界自动重试；也可以核对接收端是否可达。";
    case "delivered":
      return "接收端已确认成功，无需人工恢复。";
    case "dead-letter":
      return "确认接收端可达后，明确恢复所选死信投递；接收端需要容忍重复。";
    default:
      return "读取当前持久状态后再决定下一步。";
  }
}

export function DeliveryDetailPage() {
  const { deliveryId } = useParams({
    from: "/operations/notifications/deliveries/$deliveryId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const rawStatus = searchParams["status"];
  const returnStatus =
    typeof rawStatus === "string" &&
    (NOTIFICATION_DELIVERY_STATUSES as readonly string[]).includes(rawStatus)
      ? rawStatus
      : null;
  const returnSearch = returnStatus === null ? {} : { status: returnStatus };
  const [recoveryError, setRecoveryError] = useState<{
    message: string;
    unknown: boolean;
  } | null>(null);
  const [confirmRequeue, setConfirmRequeue] = useState(false);
  const [confirmResolve, setConfirmResolve] = useState(false);
  const [recoveryOutcome, setRecoveryOutcome] = useState<string | null>(null);

  const query = useQuery(notificationDeliveryQueryOptions(token, deliveryId));
  useAuthorizedReadAuthorityRecovery(query);

  const recoveryMutation = useMutation({
    mutationFn: (input: {
      kind: "requeue" | "resolveStale";
      expectedStatus: string;
      expectedUpdatedAt: string;
    }) => {
      const options = {
        deliveryId,
        expectedStatus: input.expectedStatus,
        expectedUpdatedAt: input.expectedUpdatedAt,
      };
      return input.kind === "requeue"
        ? requeueDeadLetterDelivery(token, options)
        : resolveStaleDelivery(token, options);
    },
    retry: false,
    onMutate: () => {
      setRecoveryError(null);
      setConfirmRequeue(false);
      setConfirmResolve(false);
    },
    onSuccess: (result, input) => {
      if (result.ok) {
        setRecoveryOutcome(
          `${input.kind === "requeue" ? "重新入队" : "过期租约恢复"}已完成：投递状态从 ${deliveryStatusLabel(result.model.previousStatus)} 变为 ${deliveryStatusLabel(result.model.status)}。${result.model.atLeastOnce} 下一步：${result.model.nextAction}`,
        );
        void queryClient.invalidateQueries({
          queryKey: [notificationDeliveryQueryKey],
        });
        void queryClient.invalidateQueries({
          queryKey: [notificationDeliveriesQueryKey],
        });
        return;
      }
      setRecoveryOutcome(null);
      if (isUnknownCommandResult(result.status, result.code)) {
        setRecoveryError({
          message: unknownCommandMessage("所选投递可能已经恢复为待投递"),
          unknown: true,
        });
        return;
      }
      setRecoveryError({
        message:
          result.status === 409
            ? "投递状态比你查看时更新，因此没有应用恢复。重新读取投递后再恢复精确的当前状态。"
            : `恢复动作没有执行（${result.code}）。重新读取当前持久状态后再试；系统没有自动重试。`,
        unknown: false,
      });
    },
  });

  const busy = recoveryMutation.isPending;
  const closeCard = () => {
    void navigate({
      to: "/operations/notifications/deliveries",
      search: returnSearch,
    });
  };
  const guard = useNotificationCardGuard({
    busy,
    dirty: false,
    onClose: closeCard,
    onDiscard: () => {
      setConfirmRequeue(false);
      setConfirmResolve(false);
      setRecoveryError(null);
    },
    firstFieldId: "notification-delivery-close",
    fallbackFocusId: "notification-deliveries-background",
  });

  const liveModel = query.data?.ok === true ? query.data.model : null;
  const model = useLastSuccessfulRead(liveModel);
  const readDegraded = liveModel === null && model !== null;
  const delivery = model?.delivery ?? null;
  const requeue = model?.actions.requeue ?? null;
  const resolveStale = model?.actions.resolveStale ?? null;
  const observed =
    delivery === null
      ? null
      : {
          expectedStatus: delivery.status,
          expectedUpdatedAt: delivery.updatedAt,
        };

  return (
    <NotificationCard
      layerRef={guard.layerRef}
      closing={guard.closing}
      busy={busy}
      title={`投递 ${deliveryId}`}
      titleId="notification-delivery-title"
      description="一条持久通知投递。恢复只改变这一行，不会重新执行、改写或回滚已完成的媒体工作。"
      closeDisabled={busy}
      onRequestClose={guard.attemptClose}
      footer={
        <>
          <Button
            type="button"
            variant="secondary"
            id="notification-delivery-close"
            disabled={busy}
            onClick={guard.attemptClose}
          >
            关闭
          </Button>
          <Link
            className="mf-button mf-button-secondary"
            to="/operations/notifications/deliveries"
            search={returnSearch}
          >
            返回投递列表
          </Link>
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
      {query.isError && model === null && (
        <NotificationCardStatus variant="error" title="投递读取失败">
          <p>没有读取到持久投递状态，因此不会提供恢复动作。</p>
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
        <NotificationCardStatus title="正在读取投递">
          <p>读取精确的持久投递状态和可用恢复动作。</p>
        </NotificationCardStatus>
      )}
      {query.data !== undefined &&
        query.data.ok === false &&
        model === null && (
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
      {model !== null && delivery !== null && (
        <div className="mf-notification-card-scroll">
          {readDegraded && (
            <StatusBanner variant="warning" title="最新读取失败">
              <p>
                显示的是上次成功读取的投递状态。已完成的恢复命令结果仍然有效；恢复读取后再决定新的恢复动作。
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
          {recoveryOutcome !== null && (
            <StatusBanner variant="success" title="恢复命令已完成">
              <p>{recoveryOutcome}</p>
              <p>这是已经完成的命令结果；即使随后的读取失败，它仍然有效。</p>
            </StatusBanner>
          )}

          <div className="mf-notification-detail-badges">
            <span
              className={
                delivery.status === "dead-letter"
                  ? "mf-notification-badge mf-notification-badge-danger"
                  : delivery.status === "delivered"
                    ? "mf-notification-badge mf-notification-badge-active"
                    : "mf-notification-badge"
              }
            >
              {deliveryStatusLabel(delivery.status)}
            </span>
            <span className="mf-notification-badge">
              尝试 {delivery.attempts} 次
            </span>
            <span className="mf-notification-badge">
              {notificationEventLabel(delivery.eventType)}
            </span>
            {!readDegraded && (
              <span className="mf-notification-read-action">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy || query.isFetching}
                  onClick={() => void query.refetch()}
                >
                  {query.isFetching ? "正在读取…" : "读取最新投递"}
                </Button>
              </span>
            )}
          </div>

          <section className="mf-notification-form-section">
            <h3>结论与已知影响</h3>
            <p className="mf-notification-conclusion">
              {failureCategoryLabel(delivery.failureCategory) ??
                (delivery.status === "pending"
                  ? "待投递 · 等待下一次尝试"
                  : deliveryStatusLabel(delivery.status))}
            </p>
            <p className="mf-notification-field-help">
              {nextStepForStatus(delivery.status)}
            </p>
            <dl className="mf-notification-facts">
              <dt>事件</dt>
              <dd>{notificationEventLabel(delivery.eventType)}</dd>
              <dt>Webhook</dt>
              <dd>{delivery.webhookId}</dd>
              <dt>响应证据</dt>
              <dd>
                {delivery.responseStatus !== null
                  ? `HTTP ${delivery.responseStatus}`
                  : "没有记录响应"}
                {failureCategoryLabel(delivery.failureCategory) !== null &&
                delivery.failureCategory !== `http_${delivery.responseStatus}`
                  ? ` · ${failureCategoryLabel(delivery.failureCategory)}`
                  : ""}
              </dd>
              <dt>租约</dt>
              <dd>
                {leaseStateLabel(model.lease.state)}
                {model.lease.expiresAt !== null
                  ? ` · ${formatNotificationTime(model.lease.expiresAt)} 到期`
                  : ""}
              </dd>
              <dt>下次自动尝试</dt>
              <dd>
                <time dateTime={delivery.nextAttemptAt}>
                  {formatNotificationTime(delivery.nextAttemptAt)}
                </time>
              </dd>
              <dt>已知接收效果</dt>
              <dd>
                {knownNotificationEffects(
                  delivery.status,
                  model.lease.state,
                  delivery.failureCategory,
                )}
              </dd>
            </dl>
            <details className="mf-notification-diagnostics">
              <summary>诊断信息</summary>
              <dl>
                <dt>投递标识</dt>
                <dd>{delivery.deliveryId}</dd>
                <dt>事件标识</dt>
                <dd>
                  {delivery.eventType}（{delivery.eventId}）
                </dd>
                <dt>状态</dt>
                <dd>{delivery.status}</dd>
                <dt>失败类别</dt>
                <dd>{delivery.failureCategory ?? "无"}</dd>
                <dt>租约状态</dt>
                <dd>{model.lease.state}</dd>
                <dt>创建时间</dt>
                <dd>{delivery.createdAt}</dd>
                <dt>更新时间</dt>
                <dd>{delivery.updatedAt}</dd>
                <dt>送达时间</dt>
                <dd>{delivery.deliveredAt ?? "未送达"}</dd>
                <dt>重试安全性</dt>
                <dd>{model.retrySafe ? "可安全重试" : "不可安全重试"}</dd>
                <dt>服务端影响证据</dt>
                <dd>{model.knownEffects}</dd>
                <dt>服务端下一步</dt>
                <dd>{model.nextAction}</dd>
              </dl>
            </details>
            <p className="mf-notification-field-help">
              投递正文、签名请求头和密钥值不会显示。
            </p>
          </section>

          <section className="mf-notification-form-section">
            <h3>恢复所选投递</h3>
            <p className="mf-notification-field-help">
              {notificationReasonLabel(
                model.recovery.reason,
                "读取当前持久状态后再决定是否恢复。",
              )}
            </p>
            {requeue !== null && (
              <div className="mf-notification-recovery">
                <p>
                  重新入队会把这条死信投递以相同身份放回待投递队列，重置尝试次数，并由
                  Worker 再次发送。接收端必须容忍重复（至少一次）。
                </p>
                <label className="mf-notification-check">
                  <input
                    type="checkbox"
                    checked={confirmRequeue}
                    onChange={(event) =>
                      setConfirmRequeue(event.target.checked)
                    }
                  />
                  <span>我确认重新入队这条精确的死信投递</span>
                </label>
                <Button
                  type="button"
                  disabled={
                    !requeue.available ||
                    !confirmRequeue ||
                    recoveryMutation.isPending ||
                    readDegraded
                  }
                  onClick={() => {
                    if (observed !== null) {
                      recoveryMutation.mutate({
                        kind: "requeue",
                        ...observed,
                      });
                    }
                  }}
                >
                  {recoveryMutation.isPending
                    ? "正在应用恢复…"
                    : "重新入队死信投递"}
                </Button>
                {!requeue.available && requeue.reason !== null && (
                  <StatusBanner variant="info" title="当前不能重新入队">
                    <p>
                      {notificationReasonLabel(
                        requeue.reason,
                        "当前不能重新入队这条投递。",
                      )}
                    </p>
                  </StatusBanner>
                )}
              </div>
            )}
            {resolveStale !== null && (
              <div className="mf-notification-recovery">
                <p>
                  解决过期租约会以相同身份和尝试次数把投递放回待投递队列。原尝试可能已经到达接收端，因此接收端可能重复处理（至少一次）。
                </p>
                <label className="mf-notification-check">
                  <input
                    type="checkbox"
                    checked={confirmResolve}
                    onChange={(event) =>
                      setConfirmResolve(event.target.checked)
                    }
                  />
                  <span>我确认解决这条精确的过期租约</span>
                </label>
                <Button
                  type="button"
                  disabled={
                    !resolveStale.available ||
                    !confirmResolve ||
                    recoveryMutation.isPending ||
                    readDegraded
                  }
                  onClick={() => {
                    if (observed !== null) {
                      recoveryMutation.mutate({
                        kind: "resolveStale",
                        ...observed,
                      });
                    }
                  }}
                >
                  {recoveryMutation.isPending
                    ? "正在应用恢复…"
                    : "解决过期租约"}
                </Button>
                {!resolveStale.available && resolveStale.reason !== null && (
                  <StatusBanner variant="info" title="当前不能解决过期租约">
                    <p>
                      {notificationReasonLabel(
                        resolveStale.reason,
                        "当前不能解决这条过期租约。",
                      )}
                    </p>
                  </StatusBanner>
                )}
              </div>
            )}
            {requeue === null && resolveStale === null && (
              <StatusBanner variant="info" title="没有可用的人工恢复">
                <p>
                  这条投递没有符合条件的人工恢复动作。自动重试和已完成的投递不会虚构恢复入口。
                </p>
              </StatusBanner>
            )}
          </section>

          {recoveryError !== null && (
            <StatusBanner
              variant={recoveryError.unknown ? "warning" : "error"}
              title={recoveryError.unknown ? "恢复结果未知" : "恢复没有应用"}
            >
              <p>{recoveryError.message}</p>
            </StatusBanner>
          )}
        </div>
      )}
    </NotificationCard>
  );
}
