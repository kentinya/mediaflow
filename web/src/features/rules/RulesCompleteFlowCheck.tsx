import { useState } from "react";
import {
  fetchRuleFormAuthority,
  runRulesCompleteFlow,
  type RulesAnalysisModel,
} from "../../shared/api/api-client";
import {
  authorityIdentity,
  type RuleFormAuthority,
} from "../../entities/rules/rules-form";

/**
 * The separately labelled RO-4 complete-flow check, reached only from Rules
 * Overview.
 *
 * It deliberately reuses the complete Python chain (recognition competition →
 * output type/binding → Metadata identity → Naming → Classification → complete
 * OrganizePlan) instead of one object's local test. Offline identity is
 * explicitly synthetic and performs no Provider call; live Metadata stays a
 * separate explicit choice. It never publishes, activates, creates executable
 * work or mutates media.
 */

interface Props {
  readonly token: string;
  readonly observedActive: {
    readonly version: number;
    readonly sequence: number;
  } | null;
}

interface SubmittedRun {
  readonly inputKey: string;
  readonly input: {
    readonly resourceLibraryId: string;
    readonly syntheticPath: string;
    readonly title: string;
    readonly mediaType: "movie" | "tv";
    readonly year: string;
    readonly liveMetadata: boolean;
  };
  readonly activeKey: string;
  readonly activeVersion: number;
  readonly activeSequence: number;
  readonly observedActiveKey: string;
}

function record(value: unknown): Readonly<Record<string, unknown>> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Readonly<Record<string, unknown>>)
    : null;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function list(value: unknown): readonly unknown[] {
  return Array.isArray(value) ? value : [];
}

function observedIdentityKey(active: Props["observedActive"]): string {
  return active === null ? "no-active" : `${active.version}:${active.sequence}`;
}

function activeSequence(active: Readonly<Record<string, unknown>>): number {
  const value = active.revisionSequence ?? active.sequence ?? active.version;
  return typeof value === "number" && Number.isSafeInteger(value) ? value : 0;
}

function activeVersion(active: Readonly<Record<string, unknown>>): number {
  return typeof active.version === "number" &&
    Number.isSafeInteger(active.version)
    ? active.version
    : 0;
}

function authorityKey(authority: RuleFormAuthority): string {
  return JSON.stringify(authorityIdentity(authority.active));
}

function Blockers({ blockers }: { readonly blockers: readonly unknown[] }) {
  if (blockers.length === 0) return null;
  return (
    <>
      <h4>缺失阶段</h4>
      <ul>
        {blockers.map((item, index) => {
          const entry = record(item);
          return (
            <li key={`${String(entry?.stage)}-${index}`}>
              <strong>{text(entry?.stage) ?? "未知阶段"}</strong>:
              {text(entry?.message) ?? "无说明"}
            </li>
          );
        })}
      </ul>
    </>
  );
}

function CompleteFlowEvidence({
  model,
}: {
  readonly model: RulesAnalysisModel;
}) {
  const result = model.result;
  const recognition = record(result.recognition);
  const policy = record(result.policy);
  const naming = record(result.naming);
  const classification = record(result.classification);
  const plan = record(result.plan);
  const conflicts = list(plan?.conflicts).map(record).filter(Boolean);
  return (
    <>
      <h4>识别竞争</h4>
      <dl>
        <dt>状态</dt>
        <dd>{text(recognition?.status) ?? "未知"}</dd>
        <dt>RecognitionType</dt>
        <dd>{text(recognition?.recognitionType) ?? "未识别"}</dd>
        <dt>胜出规则</dt>
        <dd>{text(recognition?.ruleId) ?? "无"}</dd>
      </dl>
      <h4>已解析策略</h4>
      {policy ? (
        <ul>
          <li>Metadata: {text(policy.metadataPolicy) ?? "-"}</li>
          <li>Naming: {text(policy.namingPolicy) ?? "-"}</li>
          <li>Classification: {text(policy.classificationPolicy) ?? "-"}</li>
          <li>Organize: {text(policy.organizePolicy) ?? "-"}</li>
        </ul>
      ) : (
        <p>没有可解析的下游绑定。</p>
      )}
      <h4>命名与分类</h4>
      <dl>
        <dt>命名阶段</dt>
        <dd>{text(naming?.status) ?? "未到达"}</dd>
        <dt>命名目录</dt>
        <dd>{text(naming?.directory) ?? text(naming?.message) ?? "未生成"}</dd>
        <dt>命名文件</dt>
        <dd>{text(naming?.filename) ?? text(naming?.message) ?? "未生成"}</dd>
        <dt>分类阶段</dt>
        <dd>{text(classification?.status) ?? "未到达"}</dd>
        <dt>分类库</dt>
        <dd>
          {text(classification?.mediaLibraryId) ??
            text(classification?.message) ??
            "未生成"}
        </dd>
        <dt>分类相对路径</dt>
        <dd>
          {text(classification?.relativePath) ??
            text(classification?.message) ??
            "未生成"}
        </dd>
      </dl>
      <h4>完整整理计划</h4>
      {plan ? (
        <>
          <dl>
            <dt>目标路径</dt>
            <dd>{text(plan.target) ?? "-"}</dd>
            <dt>操作</dt>
            <dd>{text(plan.operation) ?? "-"}</dd>
            <dt>计划状态</dt>
            <dd>{text(plan.status) ?? "-"}</dd>
          </dl>
          {conflicts.length > 0 ? (
            <>
              <h5>冲突</h5>
              <ul>
                {conflicts.map((item, index) => (
                  <li key={index}>
                    {text(item?.type) ?? "冲突"}: {text(item?.message) ?? "-"}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </>
      ) : (
        <p>尚未生成完整整理计划。</p>
      )}
    </>
  );
}

export function RulesCompleteFlowCheck({ token, observedActive }: Props) {
  // The complete-flow authority is read only when the operator deliberately
  // opens this entry, so merely landing on Rules Overview stays a single
  // read-only inventory request and never prepares or submits an analysis.
  const [authority, setAuthority] = useState<RuleFormAuthority | null>(null);
  const [opening, setOpening] = useState(false);
  const [resourceLibraryId, setResourceLibraryId] = useState("");
  const [syntheticPath, setSyntheticPath] = useState(
    "电影/Example.Movie.2024.mkv",
  );
  const [title, setTitle] = useState("Example Movie");
  const [mediaType, setMediaType] = useState<"movie" | "tv">("movie");
  const [year, setYear] = useState("2024");
  const [liveMetadata, setLiveMetadata] = useState(false);
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState<RulesAnalysisModel | null>(null);
  const [submitted, setSubmitted] = useState<SubmittedRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nextAction, setNextAction] = useState<string | null>(null);

  const currentInput = {
    resourceLibraryId,
    syntheticPath,
    title,
    mediaType,
    year,
    liveMetadata,
  };
  const currentInputKey = JSON.stringify(currentInput);
  const currentAuthorityKey =
    authority === null ? null : authorityKey(authority);
  const currentObservedActiveKey = observedIdentityKey(observedActive);
  const authorityStale =
    authority !== null &&
    (observedActive === null ||
      observedActive.sequence > activeSequence(authority.active) ||
      observedActive.version > activeVersion(authority.active));
  const resultStale =
    model !== null &&
    submitted !== null &&
    (model.stale ||
      submitted.inputKey !== currentInputKey ||
      submitted.activeKey !== currentAuthorityKey ||
      submitted.observedActiveKey !== currentObservedActiveKey ||
      observedActive === null ||
      observedActive.sequence > submitted.activeSequence ||
      observedActive.version > submitted.activeVersion);

  const readAuthority = async () => {
    setOpening(true);
    setError(null);
    setNextAction(null);
    const response = await fetchRuleFormAuthority(token);
    setOpening(false);
    if (!response.ok) {
      setError(response.code);
      setNextAction(response.details?.nextAction ?? null);
      return;
    }
    setAuthority(response.model);
    // Initialize the sample once. Refreshing authority must retain the
    // operator's selected source; a removed/disabled source stays visible as
    // the prior input until the operator deliberately chooses a current one.
    if (authority === null) {
      setResourceLibraryId(
        response.model.resourceLibraries.find((item) => item.enabled)?.id ?? "",
      );
    }
  };

  const open = async () => {
    await readAuthority();
  };

  const refreshAuthority = async () => {
    // Keep every submitted input and the old result. A fresh authority read is
    // explicit; it never replays the complete-flow request.
    await readAuthority();
  };

  const run = async () => {
    if (authority === null) {
      setError("not_opened");
      setNextAction("请先打开完整流程检查以读取当前 Active 与来源资源库");
      return;
    }
    if (authorityStale) {
      setError("active_changed");
      setNextAction("刷新当前 Active 权限后,再显式重新运行完整流程检查");
      return;
    }
    if (!resourceLibraryId) {
      setError("invalid_input");
      setNextAction("请选择一个已启用的 ResourceLibrary");
      return;
    }
    const selectedResourceLibrary = authority.resourceLibraries.find(
      (item) => item.id === resourceLibraryId,
    );
    if (!selectedResourceLibrary?.enabled) {
      setError("invalid_input");
      setNextAction("请选择当前 Active 中已启用的来源资源库");
      return;
    }
    if (!syntheticPath.trim() || syntheticPath.length > 4096) {
      setError("invalid_input");
      setNextAction("需要一个不超过 4096 个字符的合成路径");
      return;
    }
    if (
      liveMetadata &&
      !window.confirm("实时完整流程会访问已配置 Provider。确认继续吗?")
    )
      return;
    const input = { ...currentInput };
    const inputKey = JSON.stringify(input);
    const submittedAuthorityKey =
      currentAuthorityKey ?? authorityKey(authority);
    const submittedObservationKey = currentObservedActiveKey;
    const parsedYear = Number(input.year);
    const opened = authority;
    setBusy(true);
    setError(null);
    setNextAction(null);
    const response = await runRulesCompleteFlow(token, {
      ...authorityIdentity(opened.active),
      resourceLibraryId: input.resourceLibraryId,
      syntheticPath: input.syntheticPath.trim(),
      liveMetadata: input.liveMetadata,
      syntheticIdentity: input.liveMetadata
        ? null
        : {
            title: input.title.trim() || "Example Movie",
            mediaType: input.mediaType,
            ...(Number.isInteger(parsedYear) ? { year: parsedYear } : {}),
          },
    });
    setBusy(false);
    if (response.ok) {
      setModel(response.model);
      setSubmitted({
        inputKey,
        input,
        activeKey: submittedAuthorityKey,
        activeVersion: activeVersion(opened.active),
        activeSequence: activeSequence(opened.active),
        observedActiveKey: submittedObservationKey,
      });
      return;
    }
    setModel(null);
    setError(response.code);
    setNextAction(response.details?.nextAction ?? null);
  };

  return (
    <section
      className="mf-rules-complete-flow"
      aria-labelledby="rules-complete-flow-title"
    >
      <h3 id="rules-complete-flow-title">完整流程检查</h3>
      <p>
        这是独立的完整流程检查:它按当前 Active
        真实运行识别竞争、策略解析、元数据、命名、分类与整理计划,并如实报告缺失阶段。
        它与单个对象的本地测试分开,且不发布、不激活、不产生可执行工作。
      </p>
      {authority === null ? (
        <div className="mf-actions">
          <button type="button" onClick={() => void open()} disabled={opening}>
            {opening ? "正在读取当前 Active..." : "打开完整流程检查"}
          </button>
        </div>
      ) : null}
      {authority !== null ? (
        <div className="mf-rules-complete-flow-inputs">
          <label>
            来源资源库
            <select
              aria-label="完整流程来源资源库"
              value={resourceLibraryId}
              onChange={(event) => setResourceLibraryId(event.target.value)}
            >
              <option value="">请选择来源资源库</option>
              {resourceLibraryId !== "" &&
              !authority.resourceLibraries.some(
                (item) => item.id === resourceLibraryId,
              ) ? (
                <option value={resourceLibraryId} disabled>
                  {resourceLibraryId} (当前 Active 中不可用)
                </option>
              ) : null}
              {authority.resourceLibraries.map((item) => (
                <option key={item.id} value={item.id} disabled={!item.enabled}>
                  {item.name} ({item.id}){item.enabled ? "" : " - 已停用"}
                </option>
              ))}
            </select>
          </label>
          <label>
            合成来源路径
            <input
              aria-label="完整流程合成路径"
              value={syntheticPath}
              maxLength={4096}
              onChange={(event) => setSyntheticPath(event.target.value)}
            />
          </label>
          <label>
            合成身份标题
            <input
              aria-label="完整流程合成身份标题"
              value={title}
              maxLength={512}
              onChange={(event) => setTitle(event.target.value)}
              disabled={liveMetadata}
            />
          </label>
          <label>
            合成身份媒体类型
            <select
              aria-label="完整流程合成身份媒体类型"
              value={mediaType}
              onChange={(event) =>
                setMediaType(event.target.value as "movie" | "tv")
              }
              disabled={liveMetadata}
            >
              <option value="movie">电影</option>
              <option value="tv">剧集</option>
            </select>
          </label>
          <label>
            合成身份年份
            <input
              aria-label="完整流程合成身份年份"
              value={year}
              maxLength={4}
              onChange={(event) => setYear(event.target.value)}
              disabled={liveMetadata}
            />
          </label>
        </div>
      ) : null}
      {authority !== null ? (
        <label>
          <input
            type="checkbox"
            aria-label="完整流程允许实时元数据"
            checked={liveMetadata}
            onChange={(event) => setLiveMetadata(event.target.checked)}
          />
          使用实时 Metadata Provider(默认使用明确标注的离线合成身份)
        </label>
      ) : null}
      {authority !== null ? (
        <div className="mf-actions">
          <button
            type="button"
            onClick={() => void refreshAuthority()}
            disabled={busy || opening}
          >
            {opening ? "正在刷新当前 Active..." : "刷新当前 Active"}
          </button>
          <button
            type="button"
            onClick={() => void run()}
            disabled={busy || opening || authorityStale}
          >
            {busy
              ? "正在运行完整流程..."
              : model
                ? "显式重新运行完整流程检查"
                : "运行完整流程检查"}
          </button>
          {authorityStale ? (
            <p role="status">
              Overview 已观察到更新的 Active。请刷新当前 Active 权限后显式重跑。
            </p>
          ) : null}
        </div>
      ) : null}
      {error ? (
        <div role="alert">
          <p>完整流程检查未能提交: {error}。</p>
          <p>下一步:{nextAction ?? "刷新当前 Active 后显式重跑"}。</p>
        </div>
      ) : null}
      {model ? (
        <article className="mf-rules-complete-flow-result" aria-live="polite">
          <h4>
            {resultStale ? "过期结果 · " : ""}
            {model.conclusion}
          </h4>
          <dl>
            <dt>结果类别</dt>
            <dd>{model.outcome}</dd>
            <dt>完整流程就绪</dt>
            <dd>
              {model.readiness === "complete_plan_ready"
                ? resultStale
                  ? "提交时完整计划就绪(已过期)"
                  : "完整计划就绪"
                : model.readiness === "blocked"
                  ? "受阻"
                  : "未知"}
            </dd>
            <dt>身份来源</dt>
            <dd>
              {model.identityStatus === "live_provider"
                ? "实时 Provider"
                : model.identityStatus === "synthetic_offline"
                  ? "离线合成身份(未验证)"
                  : "未到达"}
            </dd>
            <dt>执行权限</dt>
            <dd>{model.executionAuthorityGranted ?? "无"}</dd>
            <dt>Provider 调用</dt>
            <dd>{model.providerCalls}</dd>
          </dl>
          {resultStale ? (
            <p role="status">
              该结果已过期,仅代表提交时输入与 Active
              的证据;它不表示当前输入/Active 已就绪。 请刷新当前 Active
              权限并显式重新运行。当前输入会保留,不会自动重提。
            </p>
          ) : null}
          {submitted ? (
            <details className="mf-rules-complete-flow-submitted-input">
              <summary>查看本次提交的输入与 Active 摘要</summary>
              <dl>
                <dt>来源资源库</dt>
                <dd>{submitted.input.resourceLibraryId}</dd>
                <dt>来源路径</dt>
                <dd>{submitted.input.syntheticPath}</dd>
                <dt>身份</dt>
                <dd>
                  {submitted.input.title} · {submitted.input.mediaType} ·{" "}
                  {submitted.input.year || "未提供年份"}
                </dd>
                <dt>Metadata 模式</dt>
                <dd>
                  {submitted.input.liveMetadata
                    ? "显式实时 Provider"
                    : "离线合成身份"}
                </dd>
                <dt>Active</dt>
                <dd>
                  版本 {submitted.activeVersion} · 序号{" "}
                  {submitted.activeSequence}
                </dd>
              </dl>
            </details>
          ) : null}
          {model.message ? <p>{model.message}</p> : null}
          {model.nextAction ? <p>下一步: {model.nextAction}</p> : null}
          <Blockers blockers={model.blockers} />
          <CompleteFlowEvidence model={model} />
          <details className="mf-rules-complete-flow-advanced">
            <summary>高级 / 支持:查看完整证据 JSON</summary>
            <pre>{JSON.stringify(model.result, null, 2)}</pre>
          </details>
        </article>
      ) : null}
    </section>
  );
}
