/**
 * V2 Notification definitions workspace.
 *
 * The inventory reads the backend's bounded definitions page: the exact
 * immutable Active identity, the open successor Draft, and one bounded Webhook
 * document per definition with deployment-owned secret readiness (never a
 * secret value) and backend-advertised actions. A Draft-only definition stays
 * visibly distinct from Active and is never rendered as runtime truth.
 *
 * The page is always the background of the Notification cards: creating,
 * viewing and editing open over this list, so the route/browser-back journey
 * preserves its filter, scroll and focus.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { notificationListQueryOptions } from "./notification-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { useReadReveal } from "../../shared/ui/read-reveal";
import {
  activeConfigurationSummary,
  definitionStateLabel,
  notificationEventLabel,
  notificationReasonLabel,
  secretReadinessDetail,
  secretReadinessLabel,
} from "./notification-presentation";

export function NotificationListPage() {
  const token = useAuthToken();

  const query = useQuery(notificationListQueryOptions(token));
  // A fast or cached read presents the inventory directly instead of swapping
  // a short loading banner for the whole page.
  const showLoadingWait = useReadReveal(
    query.data === undefined && !query.isError,
  );

  return (
    <AuthorizedReadBoundary query={query} unavailableTitle="通知定义暂时不可用">
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return showLoadingWait ? (
            <StatusBanner variant="info" title="正在读取通知定义">
              <p>读取当前已生效的 Webhook 定义。</p>
            </StatusBanner>
          ) : null;
        }
        if (!data.ok) {
          return (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                >
                  返回运维总览
                </Link>
                <RefreshControl
                  onRefresh={refresh}
                  refreshing={isFetching}
                  label="刷新"
                  refreshingLabel="刷新中…"
                />
              </div>
            </StatusBanner>
          );
        }
        const page = data.model;
        const create = page.actions.create;
        return (
          <div
            className="mf-notifications-page"
            id="notification-definitions-background"
            tabIndex={-1}
          >
            <header className="mf-notifications-head">
              <div>
                <h2>通知</h2>
                <p>
                  管理签名
                  Webhook、定义事件与投递记录。密钥值不会显示；这里只保存部署提供的密钥引用。
                </p>
              </div>
              <RefreshControl
                onRefresh={refresh}
                refreshing={isFetching}
                label="刷新"
                refreshingLabel="刷新中…"
              />
            </header>

            <div
              className="mf-notification-summary"
              role="group"
              aria-label="配置状态"
            >
              <div className="mf-notification-summary-item">
                <span>已生效配置</span>
                <strong>
                  {activeConfigurationSummary(page.activeConfiguration)}
                </strong>
              </div>
              <div className="mf-notification-summary-item">
                <span>发布方式</span>
                <strong>直接发布</strong>
              </div>
              <div className="mf-notification-summary-item">
                <span>定义数量</span>
                <strong>{page.total}</strong>
                <span className="mf-notification-technical">
                  {page.truncated ? "列表已截断" : "完整列表"}
                </span>
              </div>
            </div>

            <div className="mf-notification-toolbar">
              <div className="mf-notification-toolbar-primary">
                {create.available ? (
                  <Link
                    className="mf-button mf-button-primary"
                    to="/operations/notifications/webhooks/new"
                  >
                    新建 Webhook
                  </Link>
                ) : (
                  <button
                    type="button"
                    className="mf-button mf-button-secondary"
                    disabled
                    title={create.reason ?? "当前不能新建 Webhook"}
                  >
                    新建 Webhook（不可用）
                  </button>
                )}
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/notifications/deliveries"
                >
                  查看投递记录
                </Link>
              </div>
              {!create.available && create.reason !== null && (
                <p className="mf-notification-inline-reason">
                  {notificationReasonLabel(
                    create.reason,
                    "当前不能新建 Webhook；请先处理权限或完成配置初始化。",
                  )}
                </p>
              )}
            </div>

            <section className="mf-notification-list-section">
              <h3>Webhook 定义</h3>
              {page.items.length === 0 ? (
                <div className="mf-notification-empty">
                  <p>还没有 Webhook 定义。</p>
                  <p>应用后会直接发布为新的生效配置。</p>
                </div>
              ) : (
                <ul className="mf-notification-cards">
                  {page.items.map((item) => {
                    const document = item.document;
                    return (
                      <li
                        className="mf-notification-list-card"
                        key={document.id}
                        tabIndex={-1}
                        id={`notification-definition-${document.id}`}
                      >
                        <div className="mf-notification-card-head">
                          <div>
                            <strong className="mf-notification-webhook-name">
                              {document.id}
                            </strong>
                            <span
                              className={
                                item.definitionState === "active"
                                  ? "mf-notification-badge mf-notification-badge-active"
                                  : "mf-notification-badge"
                              }
                            >
                              {definitionStateLabel(item.definitionState)}
                            </span>
                            <span className="mf-notification-badge">
                              {document.enabled ? "已启用" : "已停用"}
                            </span>
                            {!document.structuralValid && (
                              <span className="mf-notification-badge mf-notification-badge-danger">
                                定义无效
                              </span>
                            )}
                          </div>
                          <span className="mf-notification-secret-state">
                            密钥引用：
                            {secretReadinessLabel(document.secretReadiness)}
                          </span>
                        </div>
                        <p
                          className="mf-notification-endpoint"
                          title={document.url}
                        >
                          {document.url}
                        </p>
                        <p className="mf-notification-events">
                          {document.events.map((event) => (
                            <span className="mf-notification-event" key={event}>
                              {notificationEventLabel(event)}
                            </span>
                          ))}
                        </p>
                        <div className="mf-notification-actions">
                          <Link
                            className="mf-button mf-button-secondary"
                            to="/operations/notifications/webhooks/$webhookId"
                            params={{ webhookId: document.id }}
                          >
                            查看定义
                          </Link>
                          {item.actions.edit.available ? (
                            <Link
                              className="mf-button mf-button-secondary"
                              to="/operations/notifications/editor/$webhookId"
                              params={{ webhookId: document.id }}
                            >
                              编辑定义
                            </Link>
                          ) : (
                            <button
                              type="button"
                              className="mf-button mf-button-secondary"
                              disabled
                              title={notificationReasonLabel(
                                item.actions.edit.reason,
                                "当前没有可编辑的定义",
                              )}
                            >
                              编辑定义（不可用）
                            </button>
                          )}
                        </div>
                        {document.validationError !== null && (
                          <p className="mf-notification-card-error">
                            {document.validationError}
                          </p>
                        )}
                        <details className="mf-notification-diagnostics">
                          <summary>诊断信息</summary>
                          <dl>
                            <dt>定义状态</dt>
                            <dd>{item.definitionState}</dd>
                            <dt>事件标识</dt>
                            <dd>{document.events.join(", ")}</dd>
                            <dt>密钥引用</dt>
                            <dd>
                              {secretReadinessDetail(document.secretReadiness)}
                            </dd>
                            <dt>已生效修订</dt>
                            <dd>
                              {item.activeConfiguration === null
                                ? "无"
                                : `${item.activeConfiguration.revisionId} · 版本 ${item.activeConfiguration.version}`}
                            </dd>
                            <dt>发布方式</dt>
                            <dd>校验并直接发布为生效配置</dd>
                            <dt>投递边界</dt>
                            <dd>
                              超时 {document.timeoutSeconds} 秒 · 最大尝试{" "}
                              {document.maxAttempts} 次 · 重试{" "}
                              {document.baseRetrySeconds}–
                              {document.maxRetrySeconds} 秒
                            </dd>
                          </dl>
                        </details>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
