/**
 * Shared native Automation engine settings form and adoption readback.
 *
 * One component serves both entrances — the `自动化 → 全局设置` tab and the
 * Automation section reached from System Settings — so the same four fields,
 * the same backend authority and the same readback can never diverge into two
 * stores or two validation paths.
 *
 * The panel keeps three truths visually separate and never promotes one into
 * another:
 *
 * 1. **published target** — the exact Active values and identity;
 * 2. **input** — what the operator has typed, preserved across a background
 *    readback until it is saved or explicitly discarded;
 * 3. **adoption** — what each live resident process reports it installed.
 *
 * A successful Save therefore says "published, adoption pending" until the
 * consumers' own reports prove otherwise, and an unknown outcome blocks every
 * further save until durable reconciliation proves what happened.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { Button } from "../../shared/ui/Button";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  fetchAutomationSettings,
  reconcileAutomationSettings,
  saveAutomationSettings,
} from "../../shared/api/api-client";
import {
  ADOPTION_STATUS_LABELS,
  AUTOMATION_ENGINE_FIELDS,
  automationSettingsBody,
  automationSettingsReconcileBody,
  type AutomationEngineField,
  type AutomationSettingsModel,
  type ConsumerAdoptionView,
  type ConsumerInstanceView,
} from "../../entities/operations/automation-settings";

const QUERY_KEY = ["operations", "automation-engine-settings"] as const;

/** Which backend failure stage/reason copy the operator sees. */
const FAILURE_STAGE_LABELS: Readonly<Record<string, string>> = {
  read: "读取",
  compose: "组装候选配置",
  persist: "保存后继修订",
  validate: "整份候选校验",
  activate: "发布 Active",
};

interface FormState {
  readonly [key: string]: string;
}

function initialForm(model: AutomationSettingsModel): FormState {
  const next: Record<string, string> = {};
  for (const field of AUTOMATION_ENGINE_FIELDS) {
    const value = model.target?.values[field];
    next[field] = value === undefined ? "" : String(value);
  }
  return next;
}

function sameValues(a: FormState, b: FormState): boolean {
  return AUTOMATION_ENGINE_FIELDS.every((field) => a[field] === b[field]);
}

/** One consumer's per-instance adoption rows, each independently truthful. */
function ConsumerAdoption({
  consumer,
}: {
  readonly consumer: ConsumerAdoptionView;
}) {
  const label =
    consumer.service === "worker"
      ? "Worker 轮询"
      : consumer.service === "scheduler"
        ? "调度器轮询"
        : consumer.service === "api"
          ? "准入/失效判定"
          : consumer.service;
  return (
    <section className="mf-panel" aria-label={`${label}采用情况`}>
      <h3>{label}</h3>
      {consumer.basis === "api_local" ? (
        <p className="mf-dashboard-meta">
          {consumer.explanation ??
            "这些值由准入/观察边界各自读取当前 Active,不是常驻进程轮询值。"}
        </p>
      ) : (
        <p className="mf-dashboard-meta">
          每个正在运行的进程在自己的安全边界读取并采用发布值,并在采用之后写入自己的报告。
          只有全部实例都报告采用当前发布值时,才视为部署整体已采用。
        </p>
      )}
      {consumer.instances.length === 0 ? (
        <p className="mf-dashboard-meta">
          {consumer.basis === "api_local"
            ? "此处不列举进程实例。"
            : "当前没有该服务的注册实例;尚未有进程可以报告采用情况。"}
        </p>
      ) : (
        <table className="mf-table">
          <caption>{label}实例采用情况</caption>
          <thead>
            <tr>
              <th scope="col">实例</th>
              <th scope="col">状态</th>
              <th scope="col">实际值</th>
              <th scope="col">所属发布</th>
              <th scope="col">下一步</th>
            </tr>
          </thead>
          <tbody>
            {consumer.instances.map((instance: ConsumerInstanceView) => (
              <tr key={instance.instanceId}>
                <td>
                  <code>{instance.instanceId}</code>
                </td>
                <td>{ADOPTION_STATUS_LABELS[instance.status]}</td>
                <td>
                  {instance.effectiveValue === null
                    ? "—"
                    : String(instance.effectiveValue)}
                  {instance.overrideSource === "cli" ? "(命令行覆盖)" : ""}
                </td>
                <td>
                  {instance.reportedRevisionId === null
                    ? "—"
                    : instance.reportedRevisionId}
                </td>
                <td>{instance.nextAction}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {consumer.adopted ? (
        <p className="mf-dashboard-meta">
          该服务的全部实例都已采用当前发布值。
        </p>
      ) : (
        <p className="mf-dashboard-meta">
          该服务尚未达到整体采用;上表逐实例说明真实状态。
        </p>
      )}
    </section>
  );
}

export function AutomationSettingsPanel() {
  const token = useAuthToken();
  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => fetchAutomationSettings(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    // The readback must show real adoption movement, so it is re-read on a
    // bounded interval while this surface is open.  A read has no side effect.
    refetchInterval: 5_000,
  });
  const model = query.data?.ok === true ? query.data.model : null;
  // The operator's in-progress input lives in its own state. `null` means "no
  // edits": the form then reads the current published target, so a background
  // readback refreshes it. Once edited, the input is preserved verbatim across
  // every refetch until it is saved or explicitly discarded.
  const [edited, setEdited] = useState<FormState | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<{
    readonly stage: string;
    readonly durableState: string;
    readonly nextAction: string;
  } | null>(null);
  const [awaitingReconciliation, setAwaitingReconciliation] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [lastPublished, setLastPublished] = useState<{
    readonly revisionId: string;
    readonly values: string;
  } | null>(null);

  const baseline = useMemo(
    () => (model === null ? {} : initialForm(model)),
    [model],
  );
  const form = edited ?? baseline;
  const dirty = edited !== null && !sameValues(edited, baseline);
  const pending = dirty;

  const submit = async () => {
    if (model === null || model.target === null) return;
    setSubmitting(true);
    setMessage(null);
    setFailure(null);
    try {
      const result = await saveAutomationSettings(
        token,
        automationSettingsBody(form, model.target),
      );
      if (result.ok) {
        setEdited(null);
        setLastPublished({
          revisionId: result.revisionId ?? model.target.revisionId,
          values: JSON.stringify(form),
        });
        setMessage(
          result.unchanged
            ? "提交值与已发布目标相同,未产生新的发布。"
            : "已发布新的目标值。常驻进程会在各自的安全边界采用;下方逐实例显示真实采用情况。",
        );
        await query.refetch();
        return;
      }
      if (result.unknownOutcome) {
        setAwaitingReconciliation(true);
        setMessage(
          "提交结果未知:请求未收到服务器确认,本次保存可能已生效也可能未生效。系统不会自动重试,请先核实下方已发布目标。",
        );
        await query.refetch();
        return;
      }
      const stage = result.details?.durableState ?? "";
      setFailure({
        stage: FAILURE_STAGE_LABELS[stage] ?? stage,
        durableState: result.details?.durableState ?? "",
        nextAction: result.details?.nextAction ?? "刷新后再决定下一步。",
      });
      setMessage(`保存未生效(${result.code})。您输入的值仍保留在表单中。`);
      await query.refetch();
    } finally {
      setSubmitting(false);
    }
  };

  const reconcile = async () => {
    setSubmitting(true);
    try {
      const result = await reconcileAutomationSettings(
        token,
        automationSettingsReconcileBody(form),
      );
      if (!result.ok) {
        setMessage("无法读取核对结果,请稍后刷新页面再判断。");
        return;
      }
      if (result.committed) {
        setAwaitingReconciliation(false);
        setEdited(null);
        setMessage(
          `核对完成:本次提交已发布为 ${result.evidenceRevisionId ?? "新的 Active"}。无需再次保存。`,
        );
      } else {
        setAwaitingReconciliation(false);
        setMessage(
          `核对完成:未发现本次提交的持久化证据,当前发布值未包含它。${result.nextAction ?? ""}`,
        );
      }
      await query.refetch();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="自动化引擎设置不可用"
    >
      {({ isFetching, refresh }) => {
        if (query.isPending) {
          return (
            <StatusBanner variant="info" title="正在读取引擎设置">
              <p>
                读取已发布目标与各常驻进程的采用情况;这不会创建 Draft
                或启动工作。
              </p>
            </StatusBanner>
          );
        }
        if (model === null) {
          return (
            <StatusBanner variant="error" title="引擎设置暂不可用">
              <p>
                后端没有返回可理解的设置文档。请刷新;此页面不会猜测任何发布值。
              </p>
            </StatusBanner>
          );
        }
        if (model.target === null) {
          return (
            <section className="mf-panel">
              <h2>自动化引擎设置</h2>
              <StatusBanner variant="info" title="尚无已发布的设置">
                <p>
                  {model.unavailable?.nextAction ??
                    "需要先完成首次设置并激活配置,才能发布引擎设置。"}
                </p>
              </StatusBanner>
              <div className="mf-actions">
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </section>
          );
        }
        return (
          <div className="mf-automation-settings">
            <section className="mf-panel" aria-label="自动化引擎设置">
              <header className="mf-panel-header">
                <div>
                  <h2>自动化引擎设置</h2>
                  <p className="mf-dashboard-meta">
                    一次保存只发布这四个字段;其他设置、定义与草稿保持不变。
                  </p>
                </div>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </header>
              <dl className="mf-detail-grid">
                <div>
                  <dt>已发布目标</dt>
                  <dd>
                    <code>{model.target.revisionId}</code>
                    {model.target.revisionVersion === null
                      ? ""
                      : ` · 版本 ${model.target.revisionVersion}`}
                  </dd>
                </div>
                <div>
                  <dt>读取时间</dt>
                  <dd>{model.asOf ?? "—"}</dd>
                </div>
                <div>
                  <dt>部署整体采用</dt>
                  <dd>
                    {model.adoption.allAdopted
                      ? "全部相关常驻进程都已采用当前发布值"
                      : "尚未整体采用;以下逐进程显示真实状态"}
                  </dd>
                </div>
              </dl>
              {!model.canManage && (
                <StatusBanner variant="info" title="只读">
                  <p>当前账号没有管理配置的权限,只能查看发布值与采用情况。</p>
                </StatusBanner>
              )}
              <form
                className="mf-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  void submit();
                }}
              >
                {model.fields.map((field) => (
                  <div className="mf-form-field" key={field.fieldPath}>
                    <label htmlFor={`automation-setting-${field.fieldPath}`}>
                      {field.label}
                      {field.unit ? `(${field.unit})` : ""}
                    </label>
                    <input
                      id={`automation-setting-${field.fieldPath}`}
                      name={field.fieldPath}
                      inputMode="decimal"
                      value={form[field.fieldPath] ?? ""}
                      disabled={!model.canManage || awaitingReconciliation}
                      onChange={(event) => {
                        setEdited({
                          ...form,
                          [field.fieldPath]: event.target.value,
                        });
                      }}
                    />
                    <p className="mf-field-help">
                      {field.meaning}
                      {field.notMeaning ? ` ${field.notMeaning}` : ""}
                      {field.minimum !== null && field.maximum !== null
                        ? ` 允许范围 ${field.minimum}–${field.maximum}。`
                        : " 必须是有限正数。"}
                    </p>
                  </div>
                ))}
                <div className="mf-actions">
                  <Button
                    type="submit"
                    disabled={
                      !model.canManage ||
                      submitting ||
                      awaitingReconciliation ||
                      !pending
                    }
                  >
                    {submitting ? "保存中…" : "保存引擎设置"}
                  </Button>
                  {awaitingReconciliation && (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={submitting}
                      onClick={() => void reconcile()}
                    >
                      核实上次提交
                    </Button>
                  )}
                  {dirty && !awaitingReconciliation && (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={submitting}
                      onClick={() => {
                        setEdited(null);
                        setMessage(null);
                        setFailure(null);
                      }}
                    >
                      放弃修改
                    </Button>
                  )}
                </div>
              </form>
              {message !== null && (
                <p className="mf-dashboard-meta" role="status">
                  {message}
                </p>
              )}
              {lastPublished !== null && (
                <p className="mf-dashboard-meta">
                  最近一次成功发布:<code>{lastPublished.revisionId}</code>
                </p>
              )}
              {failure !== null && (
                <StatusBanner variant="error" title="保存未生效">
                  <p>
                    失败阶段:{failure.stage || "未知"}。持久化状态:
                    {failure.durableState || "上一份 Active 保持不变"}。
                  </p>
                  <p>下一步:{failure.nextAction}</p>
                </StatusBanner>
              )}
              <section className="mf-panel" aria-label="保存与采用的区别">
                <h3>发布与生效是两个独立结果</h3>
                <p>
                  保存只会发布新的目标值。常驻进程在自己的安全边界(而不是收到通知时)
                  采用新值,并在采用之后写入自己的报告。发布成功不代表部署整体已生效;
                  停止、心跳过期、版本不一致或使用命令行覆盖的进程都会单独显示真实状态与下一步。
                </p>
                <p>配置复检上限:{model.configRecheckSeconds} 秒。</p>
              </section>
            </section>
            {model.consumers.map((consumer) => (
              <ConsumerAdoption key={consumer.service} consumer={consumer} />
            ))}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}

export type { AutomationEngineField };
