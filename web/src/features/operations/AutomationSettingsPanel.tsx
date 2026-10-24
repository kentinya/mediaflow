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
 *    readback until it is saved or explicitly discarded, and remembered
 *    together with the publication identity editing started from;
 * 3. **adoption** — what each live resident process reports it installed.
 *
 * A background refetch may update the *readback* but never silently re-arms the
 * operator's old input against a newer publication: an edit keeps the identity it
 * was written against, so a concurrent writer's change is refused as stale
 * (with the input retained) instead of being silently reverted by this save.
 *
 * A successful Save therefore says "published, adoption pending" until the
 * consumers' own reports prove otherwise, and an unknown outcome blocks every
 * further save until durable reconciliation proves what happened.  That
 * unresolved submission survives a real reload, principal-scoped.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthGeneration, useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { Button } from "../../shared/ui/Button";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  fetchAutomationSettings,
  fetchAuthenticatedPrincipal,
  reconcileAutomationSettings,
  saveAutomationSettings,
} from "../../shared/api/api-client";
import {
  ADOPTION_STATUS_LABELS,
  AUTOMATION_ENGINE_FIELDS,
  automationSettingsBody,
  automationSettingsReconcileBody,
  type AutomationEngineField,
  type ConsumerAdoptionView,
  type ConsumerInstanceView,
  type PublishedTargetView,
} from "../../entities/operations/automation-settings";
import {
  newSubmissionId,
  readPendingSubmission,
  writePendingSubmission,
  type PendingEngineSettingsSubmission,
} from "./automation-settings-session";

const QUERY_KEY = ["operations", "automation-engine-settings"] as const;
const PRINCIPAL_QUERY_KEY = ["authenticated-principal"] as const;

/** Which backend failure stage/reason copy the operator sees. */
const FAILURE_STAGE_LABELS: Readonly<Record<string, string>> = {
  read: "读取",
  compose: "组装候选配置",
  persist: "保存后继修订",
  validate: "整份候选校验",
  prepare: "准备运行时绑定",
  activate: "发布 Active",
};

type FormState = Readonly<Record<string, string>>;

/** The publication identity one edit was written against. */
type Baseline = Pick<
  PublishedTargetView,
  "revisionId" | "revisionVersion" | "digest"
>;

interface EditState {
  readonly baseline: Baseline;
  readonly input: FormState;
}

function publishValues(target: PublishedTargetView): FormState {
  const next: Record<string, string> = {};
  for (const field of AUTOMATION_ENGINE_FIELDS) {
    const value = target.values[field];
    next[field] = value === undefined ? "" : String(value);
  }
  return next;
}

function sameValues(a: FormState, b: FormState): boolean {
  return AUTOMATION_ENGINE_FIELDS.every((field) => a[field] === b[field]);
}

function baselineOf(target: PublishedTargetView): Baseline {
  return {
    revisionId: target.revisionId,
    revisionVersion: target.revisionVersion,
    digest: target.digest,
  };
}

function sameBaseline(a: Baseline, b: Baseline): boolean {
  return a.revisionId === b.revisionId && a.digest === b.digest;
}

/**
 * The operator's copy for one adoption basis.  The capacity/stale fields are
 * read by the admission/observation boundary itself, so their evidence has a
 * different basis and is never folded into a resident-cadence claim.
 */
function consumerHeading(service: string): string {
  if (service === "worker") return "Worker 轮询";
  if (service === "scheduler") return "调度器轮询";
  if (service === "api") return "准入上限与失效判定";
  return service;
}

/** One consumer's per-instance adoption rows, each independently truthful. */
function ConsumerAdoption({
  consumer,
}: {
  readonly consumer: ConsumerAdoptionView;
}) {
  const label = consumerHeading(consumer.service);
  const cadence = consumer.basis !== "api_local";
  return (
    <section className="mf-panel" aria-label={`${label}采用情况`}>
      <h3>{label}</h3>
      <p className="mf-dashboard-meta">
        {cadence
          ? "每个正在运行的进程在自己的安全边界读取并采用发布值,并在采用之后写入自己的报告。只有全部实例都报告采用当前发布值时,才视为该服务已采用。"
          : (consumer.explanation ??
            "这些值由准入/观察边界各自读取当前 Active,不是常驻进程的轮询值。")}
      </p>
      {cadence && consumer.instances.length === 0 ? (
        <p className="mf-dashboard-meta">
          当前没有该服务的注册实例,因此没有进程可以报告采用情况。启动该服务后无需重启即可采用发布值。
        </p>
      ) : null}
      {cadence && consumer.instances.length > 0 ? (
        <div className="mf-automation-settings-table">
          <table className="mf-table">
            <caption>{label}实例采用情况</caption>
            <thead>
              <tr>
                <th scope="col">实例</th>
                <th scope="col">状态</th>
                <th scope="col">实际使用值</th>
                <th scope="col">下一步</th>
                <th scope="col">诊断标识</th>
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
                    {instance.overrideSource === "cli"
                      ? "(命令行覆盖)"
                      : instance.overrideSource === "deployment"
                        ? "(部署覆盖)"
                        : ""}
                  </td>
                  <td>{instance.nextAction}</td>
                  <td>
                    <details className="mf-automation-settings-diagnostics">
                      <summary>展开</summary>
                      <dl>
                        <dt>发布的修订</dt>
                        <dd>
                          <code>{instance.publishedRevisionId ?? "—"}</code>
                        </dd>
                        <dt>进程报告的修订</dt>
                        <dd>
                          <code>{instance.reportedRevisionId ?? "—"}</code>
                        </dd>
                        <dt>报告时间</dt>
                        <dd>{instance.reportedAt ?? "—"}</dd>
                        <dt>状态代码</dt>
                        <dd>{instance.durableState || "—"}</dd>
                      </dl>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {cadence ? (
        <p className="mf-dashboard-meta">
          {consumer.adopted
            ? "该服务的全部实例都已采用当前发布值。"
            : "该服务尚未达到整体采用;上表逐实例说明真实状态。"}
        </p>
      ) : null}
    </section>
  );
}

export function AutomationSettingsPanel() {
  const token = useAuthToken();
  const authGeneration = useAuthGeneration();
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
  // The backend-authenticated identity scopes the retained unknown submission.
  // It is a read only; it never admits work or grants authority.
  const principalQuery = useQuery({
    queryKey: [...PRINCIPAL_QUERY_KEY, authGeneration],
    queryFn: () => fetchAuthenticatedPrincipal(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });
  const principalId = principalQuery.data?.principalId ?? null;
  const model = query.data?.ok === true ? query.data.model : null;
  // `null` means "no edits": the form then reads the current published target.
  // Once edited, the input *and the identity it was written against* are kept,
  // so a background readback can never silently re-arm old input for a newer
  // publication.
  const [edit, setEdit] = useState<EditState | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<{
    readonly stage: string;
    readonly durableState: string;
    readonly nextAction: string;
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // A freshly-minted unknown submission in this tab, or the one restored after a
  // reload.  Either way it blocks further saves until it is reconciled.
  const [unresolved, setUnresolved] =
    useState<PendingEngineSettingsSubmission | null>(null);
  const [lastPublished, setLastPublished] = useState<{
    readonly revisionId: string;
    readonly revisionVersion: number | null;
    readonly values: FormState;
  } | null>(null);

  // Restore a retained unknown submission exactly once per authenticated
  // principal.  React's documented "adjust state when an input changes" pattern
  // is used deliberately: the retained value is *derived state* of the principal
  // identity, so it is recomputed during render rather than synchronised in an
  // effect that would cascade an extra render.
  const restoredKey = `${authGeneration}:${principalId ?? ""}`;
  const [restored, setRestored] = useState<{
    readonly key: string;
    readonly value: PendingEngineSettingsSubmission | null;
  } | null>(null);
  let pendingFromStorage = restored?.value ?? null;
  if (principalId !== null && restored?.key !== restoredKey) {
    const retained = readPendingSubmission(principalId);
    pendingFromStorage = retained.available ? retained.value : null;
    setRestored({ key: restoredKey, value: pendingFromStorage });
    setUnresolved(pendingFromStorage);
    if (pendingFromStorage !== null) {
      setEdit({
        baseline: {
          revisionId: pendingFromStorage.baselineRevisionId,
          revisionVersion: pendingFromStorage.baselineRevisionVersion,
          digest: pendingFromStorage.baselineDigest,
        },
        input: pendingFromStorage.input,
      });
    }
  }

  const pendingSubmission = unresolved;
  const reloadedSubmission = pendingFromStorage;
  const published = model?.target ?? null;
  const baseline = published === null ? null : baselineOf(published);
  const publishedValues = published === null ? {} : publishValues(published);
  const form = edit?.input ?? publishedValues;
  const dirty = edit !== null && !sameValues(edit.input, publishedValues);
  // A Save is offered only while the input is still written against the current
  // publication; a changed target requires an explicit review/refresh.
  const staleBaseline =
    edit !== null &&
    baseline !== null &&
    !sameBaseline(edit.baseline, baseline);
  const canSave =
    model !== null &&
    model.canManage &&
    dirty &&
    !staleBaseline &&
    !submitting &&
    pendingSubmission === null;

  const visibleMessage = useMemo(() => {
    if (message !== null) return message;
    if (staleBaseline) {
      return "已发布的设置在此期间被其他保存改变。你输入的值仍保留在表单中;请先查看新的发布目标,再决定是否放弃修改后重新填写。";
    }
    if (pendingSubmission !== null) {
      return "上一次保存的结果未知:请求未收到服务器确认,本次保存可能已生效也可能未生效。系统不会自动重试;请先用下方的核实操作确认结果。";
    }
    return null;
  }, [message, staleBaseline, pendingSubmission]);

  const submit = async () => {
    if (model === null || model.target === null || edit === null) return;
    const submissionId = newSubmissionId();
    if (submissionId === null || principalId === null) {
      setMessage(
        "当前浏览器或账号身份不足以安全标识本次提交,因此不会发送保存。请刷新后重试。",
      );
      return;
    }
    const submittedValues = automationSettingsBody(edit.input, {
      ...model.target,
      ...edit.baseline,
    }).settings as Record<string, number>;
    const retained: PendingEngineSettingsSubmission = {
      submissionId,
      input: edit.input,
      submittedValues,
      baselineRevisionId: edit.baseline.revisionId,
      baselineRevisionVersion: edit.baseline.revisionVersion,
      baselineDigest: edit.baseline.digest,
      submittedAt: new Date().toISOString(),
    };
    // The retained context is written *before* the mutation, so a lost response
    // (or a reload mid-flight) can never leave an unreconcilable submission.
    writePendingSubmission(principalId, retained);
    setSubmitting(true);
    setMessage(null);
    setFailure(null);
    try {
      const result = await saveAutomationSettings(
        token,
        automationSettingsBody(
          edit.input,
          {
            ...model.target,
            ...edit.baseline,
          },
          submissionId,
        ),
      );
      if (result.ok) {
        writePendingSubmission(principalId, null);
        setUnresolved(null);
        setRestored({ key: restoredKey, value: null });
        setEdit(null);
        setLastPublished({
          revisionId: result.revisionId ?? edit.baseline.revisionId,
          revisionVersion: result.readback.target?.revisionVersion ?? null,
          values: edit.input,
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
        // Retain the exact submission; only its own durable evidence may clear it.
        setUnresolved(retained);
        setMessage(null);
        await query.refetch();
        return;
      }
      // A *known* rejection did not publish, so its retained context is cleared.
      writePendingSubmission(principalId, null);
      setUnresolved(null);
      setRestored({ key: restoredKey, value: null });
      setFailure({
        stage: FAILURE_STAGE_LABELS[result.details?.stage ?? ""] ?? "",
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
    const pendingContext = pendingSubmission;
    if (pendingContext === null || principalId === null) return;
    setSubmitting(true);
    try {
      const result = await reconcileAutomationSettings(
        token,
        automationSettingsReconcileBody(
          pendingContext.submittedValues,
          pendingContext.submissionId,
        ),
      );
      if (!result.ok) {
        setMessage(
          "核对读取失败:本次提交的结果仍然未知,请不要再次保存。稍后刷新页面再核对。",
        );
        return;
      }
      if (result.state === "unresolved") {
        setMessage(
          `核对结果仍不确定:无法证明本次提交已经发布或已经失败。${result.nextAction ?? ""}`,
        );
        return;
      }
      writePendingSubmission(principalId, null);
      setUnresolved(null);
      setRestored({ key: restoredKey, value: null });
      if (result.committed) {
        setEdit(null);
        setMessage(
          result.state === "superseded"
            ? `核对完成:本次提交已发布为 ${result.evidenceRevisionId ?? "一个修订"},但之后又被新的发布取代。请查看当前发布目标。`
            : `核对完成:本次提交已发布为 ${result.evidenceRevisionId ?? "当前 Active"},无需再次保存。`,
        );
      } else {
        // A terminal non-publication: keep the operator's input for correction
        // and state the exact next action.
        setMessage(
          `核对完成:本次提交没有发布(保存失败或未生效)。${result.nextAction ?? "请修正后再次保存。"}`,
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
        const target = model.target;
        return (
          <div className="mf-automation-settings">
            <div className="mf-automation-settings-grid">
              <section className="mf-panel" aria-label="自动化引擎设置">
                <header className="mf-panel-header">
                  <div>
                    <h2>自动化引擎设置</h2>
                    <p className="mf-dashboard-meta">
                      这些设置控制整个自动化执行引擎,不属于任何一个具体任务。一次保存只发布这四个字段;
                      其他设置、定义与草稿保持不变。
                    </p>
                  </div>
                  <span className="mf-automation-settings-refresh">
                    <RefreshControl
                      onRefresh={refresh}
                      refreshing={isFetching}
                    />
                  </span>
                </header>
                {!model.canManage && (
                  <StatusBanner variant="info" title="只读">
                    <p>当前账号没有管理配置的权限,只能查看发布值与采用情况。</p>
                  </StatusBanner>
                )}
                {(pendingSubmission !== null ||
                  reloadedSubmission !== null) && (
                  <StatusBanner variant="error" title="上一次保存结果未知">
                    <p>
                      请求未收到服务器确认,本次保存可能已生效也可能未生效。系统不会自动重试;
                      请先核实该次提交的持久化结果,再决定下一步。
                    </p>
                    <div className="mf-actions">
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={submitting || principalId === null}
                        onClick={() => void reconcile()}
                      >
                        核实上次提交
                      </Button>
                    </div>
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
                      <div className="mf-form-control">
                        <input
                          id={`automation-setting-${field.fieldPath}`}
                          name={field.fieldPath}
                          inputMode="decimal"
                          value={
                            form[field.fieldPath] ??
                            publishedValues[field.fieldPath] ??
                            ""
                          }
                          disabled={
                            !model.canManage || pendingSubmission !== null
                          }
                          onChange={(event) => {
                            const input = {
                              ...(edit?.input ?? publishedValues),
                              [field.fieldPath]: event.target.value,
                            };
                            setEdit({
                              baseline: edit?.baseline ?? baselineOf(target),
                              input,
                            });
                            setMessage(null);
                          }}
                        />
                        <span className="mf-form-unit">{field.unit}</span>
                      </div>
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
                    <Button type="submit" disabled={!canSave}>
                      {submitting ? "保存中…" : "保存设置"}
                    </Button>
                    {edit !== null &&
                      !submitting &&
                      pendingSubmission === null && (
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => {
                            setEdit(null);
                            setMessage(null);
                            setFailure(null);
                          }}
                        >
                          {staleBaseline
                            ? "放弃修改并采用最新发布值"
                            : "放弃修改"}
                        </Button>
                      )}
                  </div>
                </form>
                {visibleMessage !== null && (
                  <p className="mf-dashboard-meta" role="status">
                    {visibleMessage}
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
                <dl className="mf-detail-grid mf-automation-settings-target">
                  <div>
                    <dt>已发布目标</dt>
                    <dd>版本 {target.revisionVersion ?? "—"} · Active</dd>
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
                        : "尚未整体采用;下方逐进程显示真实状态"}
                    </dd>
                  </div>
                  {lastPublished !== null && (
                    <div>
                      <dt>最近一次成功发布</dt>
                      <dd>
                        版本 {lastPublished.revisionVersion ?? "—"} · 已发布
                      </dd>
                    </div>
                  )}
                </dl>
                {/* Diagnostic identities stay folded: they are for diagnosis,
                    not the primary content of an operator decision. */}
                <details className="mf-automation-settings-diagnostics">
                  <summary>诊断标识</summary>
                  <dl>
                    <dt>Active 修订</dt>
                    <dd>
                      <code>{target.revisionId}</code>
                    </dd>
                    <dt>Active 摘要</dt>
                    <dd>
                      <code>{target.digest}</code>
                    </dd>
                    {lastPublished !== null && (
                      <>
                        <dt>最近一次成功发布的修订</dt>
                        <dd>
                          <code>{lastPublished.revisionId}</code>
                        </dd>
                      </>
                    )}
                  </dl>
                </details>
                <p className="mf-dashboard-meta">
                  配置复检上限:{model.configRecheckSeconds}
                  秒。复检只更新配置与报告,不会提前领取工作或提前触发调度。
                </p>
              </section>
              <aside className="mf-panel mf-automation-settings-help">
                <h2>关于自动化引擎</h2>
                <p>
                  自动化引擎负责按任务的调度计划定时触发扫描、识别和整理流程。
                  它会根据系统资源情况控制并发任务数量,并监控任务的执行状态。
                  这些设置是全局性的,所有自动化任务都会受到这些参数的影响。
                </p>
                <p className="mf-automation-settings-warning">
                  注意事项:发布设置与常驻进程真正生效是两个独立结果。发布成功后,
                  每个常驻进程会在自己的安全边界采用新值,无需重启;停止、心跳过期、
                  版本不一致或使用命令行/部署覆盖的进程会单独显示真实状态与下一步。
                </p>
                <p>
                  建议值仅作参考,不是额外范围:默认并发 100、失效判定 3600
                  秒、Worker 2 秒、调度器 5 秒。
                </p>
              </aside>
            </div>
            <section className="mf-panel" aria-label="调度与时区说明">
              <h2>调度与时区说明</h2>
              <div className="mf-automation-settings-grid">
                <div>
                  <h3>任务调度方式</h3>
                  <p>每个自动化任务可以选择以下一种调度方式:</p>
                  <ul>
                    <li>固定间隔:按设定的秒数循环执行(intervalSeconds)。</li>
                    <li>Cron 表达式:使用标准的 Cron 表达式(cron)。</li>
                    <li>Cron 任务必须指定时区(timezone),用于确定执行时间。</li>
                  </ul>
                  <p>
                    这里的两个轮询间隔只决定常驻进程多久检查一次,不会改变任何任务的间隔、Cron
                    表达式或时区。
                  </p>
                </div>
                <div>
                  <h3>配置示例(全局设置)</h3>
                  <pre className="mf-automation-settings-example">
                    {`{
  "automation": {
    "maximumActiveJobs": ${form["automation.maximumActiveJobs"] ?? "100"},
    "staleJobAgeSeconds": ${form["automation.staleJobAgeSeconds"] ?? "3600"},
    "workerPollSeconds": ${form["automation.workerPollSeconds"] ?? "2"},
    "schedulerPollSeconds": ${form["automation.schedulerPollSeconds"] ?? "5"}
  }
}`}
                  </pre>
                </div>
              </div>
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
