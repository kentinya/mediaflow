import { useEffect, useMemo, useRef, useState } from "react";
import {
  authorityIdentity,
  ruleCandidateFields,
  type RuleFormAuthority,
  type RuleFormFamily,
} from "../../entities/rules/rules-form";
import {
  runRulesObjectAnalysis,
  type RulesAnalysisModel,
} from "../../shared/api/api-client";
import type { FormValues } from "./RulesObjectForm";

/**
 * RO-4 object-scoped local test.
 *
 * Every Add/copy/Edit form tests the exact unsaved object it is editing using
 * only that object's own necessary inputs. This panel never submits on open,
 * edit, navigation, refresh or reconnect: only the explicit button does, and it
 * always sends the current form values, sample and observed Active identity.
 *
 * A local conclusion is deliberately kept separate from runtime eligibility and
 * complete-flow readiness, and it never claims publication or execution
 * authority.
 */

type AnalysisInput =
  /** No extra input: a definition/reference/effect check. */
  | "none"
  /** One bounded synthetic source path, optionally with a resource library. */
  | "path"
  /** A typed identity sample (movie/TV metadata, naming or classification). */
  | "identity";

interface FamilyAnalysisSpec {
  readonly input: AnalysisInput;
  readonly action: string;
  readonly summary: string;
  readonly liveMetadata: boolean;
}

const FAMILY_ANALYSIS: Readonly<Record<RuleFormFamily, FamilyAnalysisSpec>> = {
  recognitionTypes: {
    input: "path",
    action: "测试该识别类型",
    summary:
      "校验类型定义本身;如已有关联规则,可选用一个合成路径测试它们。不需要绑定或下游策略。",
    liveMetadata: false,
  },
  recognitionRules: {
    input: "path",
    action: "测试该识别规则",
    summary:
      "只用该规则自身的条件求值一个合成路径,显示逐条件/分组的期望、实际与真假。",
    liveMetadata: false,
  },
  typeBindings: {
    input: "none",
    action: "检查该类型绑定",
    summary:
      "只检查类型、启用唯一性与四项策略引用是否可解析,不执行任何策略引擎。",
    liveMetadata: false,
  },
  metadataPolicies: {
    input: "identity",
    action: "测试该元数据策略",
    summary:
      "离线校验本策略自身的 Provider/查询/语言/请求/匹配设置,不需要凭据;实时测试必须显式勾选。",
    liveMetadata: true,
  },
  namingPolicies: {
    input: "identity",
    action: "测试该命名策略",
    summary:
      "用提交的 Movie/TV 样本渲染本策略的真实模板,显示变量与缺失/不安全取值证据。",
    liveMetadata: false,
  },
  classificationPolicies: {
    input: "identity",
    action: "测试该分类策略",
    summary:
      "只用本策略的规则与提交的类型化身份求值,并解析引用的 MediaLibrary 与安全相对路径。",
    liveMetadata: false,
  },
  organizePolicies: {
    input: "none",
    action: "解释该整理策略",
    summary:
      "解释本策略的操作、冲突、附件、去重、回滚、清理与回退,并列出显式高风险权限。物理就绪保持未检查。",
    liveMetadata: false,
  },
};

interface AnalysisRun {
  readonly id: number;
  readonly submittedKey: string;
  readonly sampleLabel: string;
  readonly pending: boolean;
  readonly model: RulesAnalysisModel | null;
  readonly error: string | null;
  readonly failureStage: string | null;
  readonly nextAction: string | null;
  readonly stale: boolean;
}

interface IdentitySample {
  readonly title: string;
  readonly originalTitle: string;
  readonly mediaType: "movie" | "tv";
  readonly recognitionType: string;
  readonly provider: string;
  readonly providerId: string;
  readonly year: string;
  readonly season: string;
  readonly episode: string;
  readonly episodes: string;
  readonly episodeTitle: string;
  readonly extension: string;
  readonly resolution: string;
  readonly source: string;
  readonly videoCodec: string;
  readonly audio: string;
  readonly hdr: string;
  readonly version: string;
  readonly releaseGroup: string;
  readonly genres: string;
  readonly countries: string;
  readonly languages: string;
  readonly keywords: string;
  readonly overview: string;
}

const INITIAL_IDENTITY: IdentitySample = {
  title: "The Matrix",
  originalTitle: "",
  mediaType: "movie",
  recognitionType: "",
  provider: "",
  providerId: "",
  year: "1999",
  season: "",
  episode: "",
  episodes: "",
  episodeTitle: "",
  extension: "mkv",
  resolution: "",
  source: "",
  videoCodec: "",
  audio: "",
  hdr: "",
  version: "",
  releaseGroup: "",
  genres: "",
  countries: "",
  languages: "",
  keywords: "",
  overview: "",
};

function optionalInteger(value: string, label: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0 || parsed > 9999)
    throw new Error(`${label} 必须是 0 到 9999 的整数`);
  return parsed;
}

function compactList(value: string, label: string): string[] {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (items.length > 64 || items.some((item) => item.length > 200))
    throw new Error(`${label} 最多 64 项,每项不超过 200 个字符`);
  return items;
}

function boundedText(
  value: string,
  label: string,
  maxLength: number,
): string | undefined {
  const normalized = value.trim();
  if (normalized.length > maxLength || normalized.includes("\0"))
    throw new Error(`${label} 不能超过 ${maxLength} 个字符`);
  return normalized || undefined;
}

function buildIdentitySample(
  fields: IdentitySample,
  recognitionType: string,
  family: RuleFormFamily,
): Record<string, unknown> {
  if (!fields.title.trim()) throw new Error("样本标题不能为空");
  const sample: Record<string, unknown> = {
    title: fields.title.trim(),
    mediaType: fields.mediaType,
  };
  const selectedRecognitionType =
    recognitionType.trim() || fields.recognitionType.trim();
  if (selectedRecognitionType) sample.recognitionType = selectedRecognitionType;
  for (const [key, value, label] of [["year", fields.year, "年份"]] as const) {
    const parsed = optionalInteger(value, label);
    if (parsed !== undefined) sample[key] = parsed;
  }
  if (family === "namingPolicies") {
    for (const [key, value, label] of [
      ["season", fields.season, "季"],
      ["episode", fields.episode, "集"],
    ] as const) {
      const parsed = optionalInteger(value, label);
      if (parsed !== undefined) sample[key] = parsed;
    }
    const episodes = fields.episodes.trim()
      ? fields.episodes.split(",").map((item) => {
          const parsed = Number(item.trim());
          if (!Number.isInteger(parsed) || parsed < 0 || parsed > 9999)
            throw new Error("多集编号须为逗号分隔的 0 到 9999 整数");
          return parsed;
        })
      : [];
    if (episodes.length > 32) throw new Error("多集编号最多 32 项");
    if (episodes.length > 0) sample.episodes = episodes;
    for (const [key, value, label, maxLength] of [
      ["originalTitle", fields.originalTitle, "原始标题", 512],
      ["provider", fields.provider, "Provider", 64],
      ["providerId", fields.providerId, "Provider ID", 128],
      ["episodeTitle", fields.episodeTitle, "剧集标题", 512],
      ["extension", fields.extension, "扩展名", 16],
      ["resolution", fields.resolution, "分辨率标签", 64],
      ["source", fields.source, "来源标签", 64],
      ["videoCodec", fields.videoCodec, "视频编码标签", 64],
      ["audio", fields.audio, "音频标签", 64],
      ["hdr", fields.hdr, "HDR 标签", 64],
      ["version", fields.version, "版本标签", 64],
      ["releaseGroup", fields.releaseGroup, "发布组", 128],
    ] as const) {
      const normalized = boundedText(value, label, maxLength);
      if (normalized) sample[key] = normalized;
    }
  } else {
    for (const [key, value, label] of [
      ["genres", fields.genres, "类型"],
      ["countries", fields.countries, "国家/地区"],
      ["languages", fields.languages, "语言"],
      ["keywords", fields.keywords, "关键词"],
    ] as const) {
      const items = compactList(value, label);
      if (items.length > 0) sample[key] = items;
    }
    for (const [key, value, label, maxLength] of [
      ["originalTitle", fields.originalTitle, "原始标题", 512],
      ["overview", fields.overview, "简介", 2048],
    ] as const) {
      const normalized = boundedText(value, label, maxLength);
      if (normalized) sample[key] = normalized;
    }
  }
  return sample;
}

const NAMING_TEXT_FIELDS = [
  ["originalTitle", "原始标题", 512],
  ["provider", "Provider", 64],
  ["providerId", "Provider ID", 128],
  ["episodeTitle", "剧集标题", 512],
  ["extension", "扩展名", 16],
  ["resolution", "分辨率标签", 64],
  ["source", "来源标签", 64],
  ["videoCodec", "视频编码标签", 64],
  ["audio", "音频标签", 64],
  ["hdr", "HDR 标签", 64],
  ["version", "版本标签", 64],
  ["releaseGroup", "发布组", 128],
] as const satisfies readonly (readonly [
  keyof IdentitySample,
  string,
  number,
])[];

const CLASSIFICATION_TEXT_FIELDS = [
  ["originalTitle", "原始标题", 512],
  ["overview", "简介", 2048],
] as const satisfies readonly (readonly [
  keyof IdentitySample,
  string,
  number,
])[];

const CLASSIFICATION_LIST_FIELDS = [
  ["genres", "类型"],
  ["countries", "国家/地区"],
  ["languages", "语言"],
  ["keywords", "关键词"],
] as const satisfies readonly (readonly [keyof IdentitySample, string])[];

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

const OUTCOME_LABEL: Readonly<Record<string, string>> = {
  valid: "有效",
  matched: "匹配",
  not_matched: "不匹配",
  not_applicable: "不适用",
  invalid_input: "输入/配置无效",
  failed: "技术失败",
};

const APPLICABILITY_LABEL: Readonly<Record<string, string>> = {
  applicable: "适用",
  optional: "可选",
  not_applicable: "不适用",
};

/** One bounded condition/group trace, including nested AND/OR/NOT groups. */
function ConditionTraceView({
  trace,
  depth = 0,
}: {
  readonly trace: Readonly<Record<string, unknown>>;
  readonly depth?: number;
}) {
  const children = list(trace.children).map(record).filter(Boolean);
  const kind = text(trace.kind) ?? "atomic";
  const truth = trace.truth === true;
  return (
    <li className={`mf-rules-trace mf-rules-trace-${kind}`}>
      <span className="mf-rules-trace-truth" aria-hidden="true">
        {truth ? "✓" : "✗"}
      </span>{" "}
      {kind === "logical" ? (
        <>
          <strong>{text(trace.operator) ?? "?"}</strong> 分组 ·{" "}
          {truth ? "真" : "假"}
        </>
      ) : (
        <>
          <code>{text(trace.field) ?? "?"}</code> {text(trace.operator) ?? "?"}{" "}
          <code>{text(trace.expected) ?? "—"}</code> → 实际{" "}
          <code>{text(trace.actual) ?? "—"}</code> · {truth ? "真" : "假"}
        </>
      )}
      {children.length > 0 ? (
        <ul>
          {children.map((child, index) => (
            <ConditionTraceView
              key={`${depth}-${index}`}
              trace={child as Readonly<Record<string, unknown>>}
              depth={depth + 1}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
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

function RecognitionTypeEvidence({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  const definition = record(result.definition);
  const rules = list(result.associatedRules).map(record).filter(Boolean);
  return (
    <>
      <h4>类型定义</h4>
      <dl>
        <dt>ID</dt>
        <dd>{text(definition?.id) ?? "-"}</dd>
        <dt>名称</dt>
        <dd>{text(definition?.name) ?? "-"}</dd>
        <dt>启用</dt>
        <dd>{definition?.enabled === false ? "否" : "是"}</dd>
      </dl>
      <h4>关联规则试识别</h4>
      {rules.length === 0 ? (
        <p>该类型当前没有关联识别规则,因此试识别不适用。</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>规则</th>
              <th>启用状态</th>
              <th>匹配</th>
              <th>结论</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((item, index) => (
              <tr key={`${text(item?.id) ?? index}`}>
                <td>{text(item?.id) ?? "-"}</td>
                <td>{text(item?.eligibility) ?? "-"}</td>
                <td>
                  {item?.matched === true
                    ? "匹配"
                    : item?.matched === false
                      ? "不匹配"
                      : "未求值"}
                </td>
                <td>{text(item?.conclusion) ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {result.competition ? <p>{String(result.competition)}</p> : null}
    </>
  );
}

function RecognitionRuleEvidence({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  const parsed = record(result.parsed);
  const condition = record(result.condition);
  const evidence = list(result.evidence).map(record).filter(Boolean);
  return (
    <>
      <h4>解析结果</h4>
      <dl>
        <dt>提交路径</dt>
        <dd>{text(result.testedPath) ?? "-"}</dd>
        <dt>输出类型</dt>
        <dd>{text(result.outputRecognitionType) ?? "-"}</dd>
        <dt>标题候选</dt>
        <dd>{text(parsed?.titleCandidate) ?? "-"}</dd>
        <dt>季 / 集</dt>
        <dd>
          {String(parsed?.season ?? "-")} / {String(parsed?.episode ?? "-")}
        </dd>
      </dl>
      <h4>条件求值</h4>
      {condition ? (
        <ul className="mf-rules-condition-trace">
          <ConditionTraceView trace={condition} />
        </ul>
      ) : (
        <p>该规则已停用,条件未求值。</p>
      )}
      {evidence.length > 0 ? (
        <>
          <h4>条件证据</h4>
          <ul>
            {evidence.map((item, index) => (
              <li key={`${text(item?.field)}-${index}`}>
                <code>{text(item?.field) ?? "-"}</code>{" "}
                {text(item?.operator) ?? ""} 期望{" "}
                <code>{text(item?.expected) ?? "—"}</code> 实际{" "}
                <code>{text(item?.actual) ?? "—"}</code>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {result.competition ? <p>{String(result.competition)}</p> : null}
    </>
  );
}

function BindingEvidence({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  const policies = record(result.resolvedPolicies);
  return (
    <>
      <dl>
        <dt>RecognitionType</dt>
        <dd>
          {text(result.recognitionType) ?? "-"} (身份保持:
          {text(result.recognitionTypeIdentity) ?? "-"})
        </dd>
        <dt>类型启用</dt>
        <dd>{result.recognitionTypeEnabled === false ? "否" : "是"}</dd>
        <dt>绑定启用</dt>
        <dd>{result.enabled === false ? "否" : "是"}</dd>
      </dl>
      <h4>四项策略引用</h4>
      <ul>
        {Object.entries(policies ?? {}).map(([name, value]) => {
          const entry = record(value);
          return (
            <li key={name}>
              {name}: {text(entry?.id) ?? "未配置"} ·{" "}
              {entry?.resolved === true ? "可解析" : "不可解析"}
              {entry?.enabled === false ? " · 已停用" : ""}
            </li>
          );
        })}
      </ul>
      {list(result.duplicateEnabledBindings).length > 0 ? (
        <p role="alert">
          同一 RecognitionType 存在多个已启用绑定:
          {list(result.duplicateEnabledBindings).join(", ")}
        </p>
      ) : null}
    </>
  );
}

function MetadataEvidence({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  const settings = record(result.effectiveSettings);
  const readiness = record(result.credentialReadiness);
  const identity = record(result.identity);
  return (
    <>
      <dl>
        <dt>模式</dt>
        <dd>{text(result.mode) === "live" ? "实时测试" : "离线校验"}</dd>
        <dt>Provider</dt>
        <dd>{text(settings?.providerId) ?? "-"}</dd>
        <dt>查询类型</dt>
        <dd>{text(result.queryType) ?? "-"}</dd>
        <dt>已验证</dt>
        <dd>{result.verified === true ? "是" : "否"}</dd>
      </dl>
      <h4>凭据就绪(不含取值)</h4>
      <ul>
        {list(readiness?.fields)
          .map(record)
          .filter(Boolean)
          .map((item, index) => (
            <li key={`${text(item?.field)}-${index}`}>
              {text(item?.field) ?? "-"}: {text(item?.state) ?? "-"}
            </li>
          ))}
      </ul>
      {identity ? (
        <>
          <h4>识别身份</h4>
          <dl>
            <dt>标题</dt>
            <dd>{text(identity.title) ?? "-"}</dd>
            <dt>Provider ID</dt>
            <dd>{text(identity.providerId) ?? "-"}</dd>
          </dl>
        </>
      ) : null}
    </>
  );
}

function NamingEvidence({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  const variables = record(result.renderedVariables);
  const decisions = list(result.missingVariableDecisions)
    .map(record)
    .filter(Boolean);
  return (
    <>
      <dl>
        <dt>目录</dt>
        <dd>{text(result.directory) ?? "-"}</dd>
        <dt>文件名</dt>
        <dd>{text(result.filename) ?? "-"}</dd>
        <dt>缺失变量策略</dt>
        <dd>{text(result.missingVariableStrategy) ?? "-"}</dd>
      </dl>
      <h4>模板变量</h4>
      <ul>
        {Object.entries(variables ?? {}).map(([name, value]) => (
          <li key={name}>
            <code>{name}</code> = {String(value)}
          </li>
        ))}
      </ul>
      {decisions.length > 0 ? (
        <>
          <h4>缺失变量取值</h4>
          <ul>
            {decisions.map((item, index) => (
              <li key={`${text(item?.variable)}-${index}`}>
                {text(item?.variable) ?? "-"} → {text(item?.decision) ?? "-"}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </>
  );
}

function ClassificationEvidence({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  return (
    <>
      <dl>
        <dt>状态</dt>
        <dd>{text(result.status) ?? "-"}</dd>
        <dt>匹配规则</dt>
        <dd>{text(result.matchedRuleId) ?? "无"}</dd>
        <dt>MediaLibrary</dt>
        <dd>
          {text(result.mediaLibraryId) ?? "无"} ·{" "}
          {result.mediaLibraryResolved === true ? "可解析" : "不可解析"}
        </dd>
        <dt>相对路径</dt>
        <dd>{text(result.relativePath) ?? "无"}</dd>
        <dt>目标契约</dt>
        <dd>
          {text(result.destinationContract) === "legacy_library_prefix"
            ? "旧版库前缀"
            : "MediaLibrary 路径"}
        </dd>
      </dl>
      {list(result.matchEvidence).length > 0 ? (
        <>
          <h4>匹配证据</h4>
          <ul>
            {list(result.matchEvidence).map((item, index) => (
              <li key={index}>{String(item)}</li>
            ))}
          </ul>
        </>
      ) : null}
    </>
  );
}

function OrganizeEvidence({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  return (
    <>
      <dl>
        <dt>操作</dt>
        <dd>{text(result.operation) ?? "-"}</dd>
        <dt>冲突策略</dt>
        <dd>{text(result.conflictStrategy) ?? "-"}</dd>
        <dt>覆盖授权</dt>
        <dd>{result.overwriteAuthorized === true ? "是(高风险)" : "否"}</dd>
        <dt>删除授权</dt>
        <dd>{result.deleteAuthorized === true ? "是(高风险)" : "否"}</dd>
        <dt>物理就绪</dt>
        <dd>{text(result.physicalReadiness) ?? "未检查"}</dd>
        <dt>执行就绪</dt>
        <dd>{text(result.executionReadiness) ?? "未检查"}</dd>
      </dl>
      <h4>所需存储能力</h4>
      <ul>
        {list(result.requiredStorageCapabilities).map((item, index) => (
          <li key={index}>{String(item)}</li>
        ))}
      </ul>
      {list(result.warnings).length > 0 ? (
        <>
          <h4>风险警告</h4>
          <ul>
            {list(result.warnings).map((item, index) => (
              <li key={index}>{String(item)}</li>
            ))}
          </ul>
        </>
      ) : null}
    </>
  );
}

function AnalysisEvidence({
  family,
  result,
}: {
  readonly family: RuleFormFamily;
  readonly result: Readonly<Record<string, unknown>>;
}) {
  if (family === "recognitionTypes")
    return <RecognitionTypeEvidence result={result} />;
  if (family === "recognitionRules")
    return <RecognitionRuleEvidence result={result} />;
  if (family === "typeBindings") return <BindingEvidence result={result} />;
  if (family === "metadataPolicies")
    return <MetadataEvidence result={result} />;
  if (family === "namingPolicies") return <NamingEvidence result={result} />;
  if (family === "classificationPolicies")
    return <ClassificationEvidence result={result} />;
  return <OrganizeEvidence result={result} />;
}

interface Props {
  readonly token: string;
  readonly family: RuleFormFamily;
  readonly objectId: string | null;
  readonly authority: RuleFormAuthority;
  readonly values: FormValues;
  readonly publicationEpoch?: number;
}

export function RulesObjectTestPanel({
  token,
  family,
  objectId,
  authority,
  values,
  publicationEpoch = 0,
}: Props) {
  const spec = FAMILY_ANALYSIS[family];
  const [identity, setIdentity] = useState<IdentitySample>(INITIAL_IDENTITY);
  const [syntheticPath, setSyntheticPath] = useState(
    "电影/Example.Movie.2024.mkv",
  );
  const [resourceLibraryId, setResourceLibraryId] = useState(
    authority.resourceLibraries.find((item) => item.enabled)?.id ?? "",
  );
  const [testAssociatedRules, setTestAssociatedRules] = useState(false);
  const [liveMetadata, setLiveMetadata] = useState(false);
  const [busy, setBusy] = useState(false);
  const [runs, setRuns] = useState<readonly AnalysisRun[]>([]);
  const nextId = useRef(1);
  const candidate = useMemo(
    () => ruleCandidateFields(family, values),
    [family, values],
  );
  const boundRecognitionType =
    family === "recognitionTypes"
      ? String(candidate.id ?? "")
      : family === "typeBindings"
        ? String(candidate.recognitionType ?? "")
        : "";
  const currentnessKey = JSON.stringify({
    candidate,
    sampleInput:
      spec.input === "none"
        ? null
        : spec.input === "path"
          ? family === "recognitionTypes" && !testAssociatedRules
            ? { testAssociatedRules: false }
            : { testAssociatedRules, syntheticPath, resourceLibraryId }
          : family === "metadataPolicies" && !liveMetadata
            ? { liveMetadata: false }
            : { identity, liveMetadata },
    publicationEpoch,
  });
  const currentnessKeyRef = useRef(currentnessKey);
  const previousKey = useRef(currentnessKey);

  useEffect(() => {
    currentnessKeyRef.current = currentnessKey;
    if (previousKey.current === currentnessKey) return;
    previousKey.current = currentnessKey;
    // A relevant edit or Active change invalidates currency; the operator must
    // explicitly rerun. Nothing is resubmitted automatically.
    setRuns((items) =>
      items.map((item) => (item.stale ? item : { ...item, stale: true })),
    );
  }, [currentnessKey]);

  const changeIdentity = <K extends keyof IdentitySample>(
    field: K,
    value: IdentitySample[K],
  ) => setIdentity((current) => ({ ...current, [field]: value }));

  const run = async () => {
    if (
      spec.liveMetadata &&
      liveMetadata &&
      !window.confirm("实时元数据测试会访问已配置 Provider。确认继续吗?")
    )
      return;
    let sample: Record<string, unknown> | null = null;
    try {
      if (spec.input === "path") {
        if (family !== "recognitionTypes" || testAssociatedRules) {
          if (!syntheticPath.trim() || syntheticPath.length > 4096)
            throw new Error("需要一个不超过 4096 个字符的合成路径");
          sample = { path: syntheticPath.trim() };
          if (resourceLibraryId) sample.resourceLibraryId = resourceLibraryId;
        }
      } else if (spec.input === "identity") {
        if (family !== "metadataPolicies" || liveMetadata)
          sample = buildIdentitySample(identity, boundRecognitionType, family);
      }
    } catch (error) {
      setRuns((items) => [
        ...items,
        {
          id: nextId.current++,
          submittedKey: currentnessKey,
          sampleLabel: "当前输入",
          pending: false,
          model: null,
          error: "invalid_sample",
          failureStage: "sample",
          nextAction: String(error),
          stale: false,
        },
      ]);
      return;
    }
    const submittedKey = currentnessKey;
    const id = nextId.current++;
    const sampleLabel =
      spec.input === "none"
        ? "对象定义/引用"
        : sample === null
          ? "离线本地配置(无身份样本)"
          : spec.input === "path"
            ? `${resourceLibraryId || "未选择来源库"} · ${syntheticPath}`
            : `${String(sample?.title ?? "")} · ${String(sample?.mediaType ?? "")}`;
    setRuns((items) => [
      ...items,
      {
        id,
        submittedKey,
        sampleLabel,
        pending: true,
        model: null,
        error: null,
        failureStage: null,
        nextAction: null,
        stale: false,
      },
    ]);
    setBusy(true);
    const response = await runRulesObjectAnalysis(token, family, {
      ...authorityIdentity(authority.active),
      candidate: { family, objectId, values: candidate },
      sample,
      liveMetadata: spec.liveMetadata ? liveMetadata : false,
    });
    setBusy(false);
    setRuns((items) =>
      items.map((item) =>
        item.id !== id
          ? item
          : {
              ...item,
              pending: false,
              model: response.ok ? response.model : null,
              error: response.ok ? null : response.code,
              failureStage: response.ok
                ? null
                : (response.details?.stage ?? "request"),
              nextAction: response.ok
                ? null
                : (response.details?.nextAction ?? null),
              stale: item.stale || submittedKey !== currentnessKeyRef.current,
            },
      ),
    );
  };

  return (
    <section
      className="mf-rules-object-test"
      aria-labelledby="rules-object-test-title"
    >
      <h2 id="rules-object-test-title">测试与预览</h2>
      <p>{spec.summary}</p>
      <p className="mf-rules-object-test-scope">
        测试对象:{family}
        {objectId ? ` · ${objectId}` : " · 新建/复制候选"}
        。打开、编辑、导航、刷新或重连都不会自动提交测试。
      </p>
      {family === "recognitionTypes" ? (
        <label>
          <input
            type="checkbox"
            aria-label="试识别关联规则"
            checked={testAssociatedRules}
            onChange={(event) => setTestAssociatedRules(event.target.checked)}
          />
          可选测试当前类型的关联规则(需要合成路径)
        </label>
      ) : null}
      {spec.input !== "none" ? (
        <div className="mf-rules-object-test-inputs">
          {spec.input === "path" &&
          (family !== "recognitionTypes" || testAssociatedRules) ? (
            <>
              <label>
                来源资源库
                <select
                  aria-label="测试来源资源库"
                  value={resourceLibraryId}
                  onChange={(event) => setResourceLibraryId(event.target.value)}
                >
                  <option value="">不指定来源库</option>
                  {authority.resourceLibraries.map((item) => (
                    <option
                      key={item.id}
                      value={item.id}
                      disabled={!item.enabled}
                    >
                      {item.name} ({item.id}){item.enabled ? "" : " - 已停用"}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                合成来源路径
                <input
                  aria-label="测试合成路径"
                  value={syntheticPath}
                  maxLength={4096}
                  onChange={(event) => setSyntheticPath(event.target.value)}
                />
              </label>
            </>
          ) : spec.input === "identity" &&
            (family !== "metadataPolicies" || liveMetadata) ? (
            <>
              <p>
                {family === "metadataPolicies"
                  ? "实时测试只在明确启用后提交查询标题;离线校验不需要身份样本。"
                  : "填写当前策略会消费的合成字段;未用到的字段可以留空。"}
              </p>
              <label>
                {family === "metadataPolicies" ? "实时查询标题" : "样本标题"}
                <input
                  aria-label="测试样本标题"
                  value={identity.title}
                  maxLength={512}
                  onChange={(event) =>
                    changeIdentity("title", event.target.value)
                  }
                />
              </label>
              <label>
                媒体类型
                <select
                  aria-label="测试样本媒体类型"
                  value={identity.mediaType}
                  onChange={(event) =>
                    changeIdentity(
                      "mediaType",
                      event.target.value as "movie" | "tv",
                    )
                  }
                >
                  <option value="movie">电影</option>
                  <option value="tv">剧集</option>
                </select>
              </label>
              {family === "metadataPolicies" ? null : (
                <>
                  {family === "namingPolicies" ? (
                    <>
                      <label>
                        识别类型样本
                        <input
                          aria-label="测试样本识别类型"
                          value={
                            boundRecognitionType || identity.recognitionType
                          }
                          maxLength={64}
                          onChange={(event) =>
                            changeIdentity(
                              "recognitionType",
                              event.target.value,
                            )
                          }
                          readOnly={Boolean(boundRecognitionType)}
                        />
                      </label>
                      {(["year", "season", "episode"] as const).map((field) => (
                        <label key={field}>
                          {{ year: "年份", season: "季", episode: "集" }[field]}
                          <input
                            aria-label={`测试样本${{ year: "年份", season: "季", episode: "集" }[field]}`}
                            value={identity[field]}
                            maxLength={4}
                            inputMode="numeric"
                            onChange={(event) =>
                              changeIdentity(field, event.target.value)
                            }
                          />
                        </label>
                      ))}
                      <label>
                        多集编号
                        <input
                          aria-label="测试样本多集编号"
                          value={identity.episodes}
                          placeholder="逗号分隔,如 1,2,3"
                          onChange={(event) =>
                            changeIdentity("episodes", event.target.value)
                          }
                        />
                      </label>
                      {NAMING_TEXT_FIELDS.map(([field, label, maxLength]) => (
                        <label key={field}>
                          {label}
                          <input
                            aria-label={`测试样本${label}`}
                            value={identity[field]}
                            maxLength={maxLength}
                            onChange={(event) =>
                              changeIdentity(field, event.target.value)
                            }
                          />
                        </label>
                      ))}
                    </>
                  ) : (
                    <>
                      <label>
                        识别类型样本
                        <input
                          aria-label="测试样本识别类型"
                          value={identity.recognitionType}
                          maxLength={64}
                          onChange={(event) =>
                            changeIdentity(
                              "recognitionType",
                              event.target.value,
                            )
                          }
                        />
                      </label>
                      <label>
                        年份
                        <input
                          aria-label="测试样本年份"
                          value={identity.year}
                          maxLength={4}
                          inputMode="numeric"
                          onChange={(event) =>
                            changeIdentity("year", event.target.value)
                          }
                        />
                      </label>
                      {CLASSIFICATION_LIST_FIELDS.map(([field, label]) => (
                        <label key={field}>
                          {label}
                          <input
                            aria-label={`测试样本${label}`}
                            value={identity[field]}
                            placeholder="逗号分隔"
                            onChange={(event) =>
                              changeIdentity(field, event.target.value)
                            }
                          />
                        </label>
                      ))}
                      {CLASSIFICATION_TEXT_FIELDS.map(
                        ([field, label, maxLength]) => (
                          <label key={field}>
                            {label}
                            <input
                              aria-label={`测试样本${label}`}
                              value={identity[field]}
                              maxLength={maxLength}
                              onChange={(event) =>
                                changeIdentity(field, event.target.value)
                              }
                            />
                          </label>
                        ),
                      )}
                    </>
                  )}
                </>
              )}
            </>
          ) : null}
        </div>
      ) : null}
      {spec.liveMetadata ? (
        <label>
          <input
            type="checkbox"
            aria-label="允许实时元数据测试"
            checked={liveMetadata}
            onChange={(event) => setLiveMetadata(event.target.checked)}
          />
          允许实时 Metadata Provider 测试(离线校验不需要凭据)
        </label>
      ) : null}
      <div className="mf-actions">
        <button type="button" onClick={() => void run()} disabled={busy}>
          {spec.action}
        </button>
      </div>
      {runs.map((item) => (
        <article
          key={item.id}
          className="mf-rules-object-test-result"
          aria-live="polite"
        >
          <h3>{family} 本地测试结果</h3>
          <p>样本/上下文: {item.sampleLabel}</p>
          {item.pending ? (
            <p role="status">正在测试提交时的未保存对象...</p>
          ) : null}
          {item.stale || item.model?.stale ? (
            <p role="status">
              该结果已过期;当前表单、样本或 Active 已变化,请显式重新运行。
            </p>
          ) : null}
          {item.error ? (
            <div role="alert">
              <p>
                测试失败: {item.error}。失败阶段:{item.failureStage ?? "未知"}。
              </p>
              <p>
                输入仍保留;下一步:
                {item.nextAction ?? "检查相关输入与当前 Active 后显式重跑"}。
              </p>
            </div>
          ) : null}
          {item.model ? (
            <>
              <dl className="mf-rules-object-test-outcome">
                <dt>结论</dt>
                <dd>{item.model.conclusion}</dd>
                <dt>结果类别</dt>
                <dd>
                  {OUTCOME_LABEL[item.model.outcome] ?? item.model.outcome}
                </dd>
                <dt>适用性</dt>
                <dd>
                  {APPLICABILITY_LABEL[item.model.applicability] ??
                    item.model.applicability}
                </dd>
                <dt>运行时资格</dt>
                <dd>
                  {item.model.runtimeEligibility === "separate"
                    ? "与本次本地结论分开判定"
                    : item.model.runtimeEligibility}
                </dd>
                <dt>完整流程就绪</dt>
                <dd>
                  {item.model.readiness === null
                    ? "不适用(本地测试不判定完整流程)"
                    : item.model.readiness === "complete_plan_ready"
                      ? "完整计划就绪"
                      : "受阻"}
                </dd>
                <dt>Provider 调用 / Storage 读取</dt>
                <dd>
                  {item.model.providerCalls} / {item.model.storageReads}
                </dd>
              </dl>
              <p>
                候选修订 {item.model.revisionId.slice(0, 8)}… · 版本{" "}
                {item.model.revisionVersion} · {item.model.candidateState}
              </p>
              <p>本地测试不发布、不激活、不产生可执行工作,也不授予执行权限。</p>
              {item.model.message ? <p>{item.model.message}</p> : null}
              {item.model.nextAction ? (
                <p>下一步: {item.model.nextAction}</p>
              ) : null}
              <Blockers blockers={item.model.blockers} />
              <AnalysisEvidence family={family} result={item.model.result} />
              <details className="mf-rules-object-test-advanced">
                <summary>高级 / 支持:查看完整证据 JSON</summary>
                <pre>{JSON.stringify(item.model.result, null, 2)}</pre>
              </details>
            </>
          ) : null}
          {!item.pending ? (
            <button type="button" onClick={() => void run()} disabled={busy}>
              用当前输入重新运行此项
            </button>
          ) : null}
        </article>
      ))}
    </section>
  );
}
