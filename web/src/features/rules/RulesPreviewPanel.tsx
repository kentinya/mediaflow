import { useEffect, useMemo, useRef, useState } from "react";
import {
  authorityIdentity,
  ruleCandidateFields,
  type RuleFormAuthority,
  type RuleFormFamily,
} from "../../entities/rules/rules-form";
import {
  runRulesPreview,
  type RulesPreviewKind,
  type RulesPreviewModel,
} from "../../shared/api/api-client";
import type { FormValues } from "./RulesObjectForm";

interface Props {
  readonly token: string;
  readonly family: RuleFormFamily;
  readonly objectId: string | null;
  readonly authority: RuleFormAuthority;
  readonly values: FormValues;
  readonly publicationEpoch?: number;
}

interface SampleFields {
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
  readonly resolution: string;
  readonly source: string;
  readonly videoCodec: string;
  readonly audio: string;
  readonly hdr: string;
  readonly version: string;
  readonly releaseGroup: string;
  readonly extension: string;
  readonly genres: string;
  readonly countries: string;
  readonly languages: string;
  readonly keywords: string;
  readonly overview: string;
}

interface PreviewResult {
  readonly id: number;
  readonly kind: RulesPreviewKind;
  readonly sampleLabel: string;
  readonly submittedKey: string;
  readonly pending: boolean;
  readonly outcome: RulesPreviewModel | null;
  readonly error: string | null;
  readonly failureStage: string | null;
  readonly nextAction: string | null;
  readonly stale: boolean;
}

const INITIAL_SAMPLE: SampleFields = {
  title: "The Matrix",
  originalTitle: "",
  mediaType: "movie",
  recognitionType: "C",
  provider: "offline-preview",
  providerId: "synthetic",
  year: "1999",
  season: "",
  episode: "",
  episodes: "",
  episodeTitle: "",
  resolution: "",
  source: "",
  videoCodec: "",
  audio: "",
  hdr: "",
  version: "",
  releaseGroup: "",
  extension: "mkv",
  genres: "",
  countries: "",
  languages: "",
  keywords: "",
  overview: "",
};

const NAMING_SAMPLE_FIELDS = new Set([
  "path",
  "title",
  "originalTitle",
  "mediaType",
  "recognitionType",
  "provider",
  "providerId",
  "year",
  "season",
  "episode",
  "episodes",
  "episodeTitle",
  "resolution",
  "source",
  "videoCodec",
  "audio",
  "hdr",
  "version",
  "releaseGroup",
  "extension",
]);
const CLASSIFICATION_SAMPLE_FIELDS = new Set([
  "path",
  "title",
  "originalTitle",
  "mediaType",
  "recognitionType",
  "year",
  "genres",
  "countries",
  "languages",
  "keywords",
  "overview",
]);

function sampleForKind(
  kind: RulesPreviewKind,
  sample: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  if (kind === "strategy" || kind === "metadata") return {};
  const allowed =
    kind === "naming"
      ? NAMING_SAMPLE_FIELDS
      : kind === "classification"
        ? CLASSIFICATION_SAMPLE_FIELDS
        : new Set([...NAMING_SAMPLE_FIELDS, ...CLASSIFICATION_SAMPLE_FIELDS]);
  return Object.fromEntries(
    Object.entries(sample).filter(([key]) => allowed.has(key)),
  );
}

function compactList(value: string, maximum: number, label: string): string[] {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (items.length > maximum || items.some((item) => item.length > 200))
    throw new Error(`${label} 最多 ${maximum} 项,每项不超过 200 个字符`);
  return items;
}

function optionalInteger(value: string, label: string): number | undefined {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0 || parsed > 9999)
    throw new Error(`${label} 必须是 0 到 9999 的整数`);
  return parsed;
}

function buildSample(fields: SampleFields, pathMode: boolean, path: string) {
  if (pathMode) {
    if (!path.trim() || path.length > 4096)
      throw new Error("路径模式需要一个不超过 4096 个字符的来源路径");
    return { path: path.trim() };
  }
  if (!fields.title.trim()) throw new Error("标题不能为空");
  if (!fields.recognitionType.trim())
    throw new Error("RecognitionType 不能为空");
  if (!/^[A-Za-z0-9]{1,16}$/.test(fields.extension))
    throw new Error("扩展名只能包含 1 到 16 个字母或数字");
  const sample: Record<string, unknown> = {
    title: fields.title.trim(),
    mediaType: fields.mediaType,
    recognitionType: fields.recognitionType.trim(),
    extension: fields.extension,
  };
  const textFields = {
    originalTitle: fields.originalTitle,
    provider: fields.provider,
    providerId: fields.providerId,
    episodeTitle: fields.episodeTitle,
    resolution: fields.resolution,
    source: fields.source,
    videoCodec: fields.videoCodec,
    audio: fields.audio,
    hdr: fields.hdr,
    version: fields.version,
    releaseGroup: fields.releaseGroup,
    overview: fields.overview,
  };
  for (const [key, value] of Object.entries(textFields)) {
    if (value.trim()) sample[key] = value.trim();
  }
  for (const [key, value, label] of [
    ["year", fields.year, "年份"],
    ["season", fields.season, "季"],
    ["episode", fields.episode, "集"],
  ] as const) {
    const parsed = optionalInteger(value, label);
    if (parsed !== undefined) sample[key] = parsed;
  }
  const episodes = compactList(fields.episodes, 32, "多集集号").map((item) => {
    const parsed = optionalInteger(item, "集号");
    if (parsed === undefined) throw new Error("集号不能为空");
    return parsed;
  });
  if (episodes.length > 0) sample.episodes = episodes;
  for (const [key, value, label] of [
    ["genres", fields.genres, "类型"],
    ["countries", fields.countries, "国家/地区"],
    ["languages", fields.languages, "语言"],
    ["keywords", fields.keywords, "关键词"],
  ] as const) {
    const items = compactList(value, 64, label);
    if (items.length > 0) sample[key] = items;
  }
  return sample;
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

function ExplanationList({ values }: { readonly values: readonly unknown[] }) {
  if (values.length === 0) return <p>无。</p>;
  return (
    <ul>
      {values.slice(0, 32).map((value, index) => (
        <li key={`${String(value)}-${index}`}>
          {typeof value === "string" ? value : JSON.stringify(value)}
        </li>
      ))}
    </ul>
  );
}

function StrategyExplanation({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  const recognition = record(result.recognition);
  const policy = record(result.policy);
  const metadataPolicy = record(result.effectiveMetadataPolicy);
  const metadata = record(result.metadata);
  const metadataIdentity = record(metadata?.identity);
  const matched = list(recognition?.matchedRules).map(record).filter(Boolean);
  return (
    <div className="mf-rules-preview-explanation">
      <h4>识别结论</h4>
      <dl>
        <dt>RecognitionType</dt>
        <dd>{text(recognition?.recognitionType) ?? "未识别"}</dd>
        <dt>状态 / 规则</dt>
        <dd>
          {text(recognition?.status) ?? "未知"} /{" "}
          {text(recognition?.ruleId) ?? "无"}
        </dd>
        <dt>分数 / 置信度</dt>
        <dd>
          {String(recognition?.score ?? "-")} /{" "}
          {String(recognition?.confidence ?? "-")}
        </dd>
        <dt>身份保持</dt>
        <dd>
          {result.recognitionTypePreserved === true ? "是" : "否或不适用"}
        </dd>
      </dl>
      <h4>匹配规则</h4>
      {matched.length === 0 ? (
        <p>没有匹配规则。</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>规则</th>
              <th>类型</th>
              <th>优先级</th>
              <th>分数</th>
            </tr>
          </thead>
          <tbody>
            {matched.map((item, index) => (
              <tr key={`${text(item?.ruleId) ?? index}`}>
                <td>{text(item?.ruleId) ?? "-"}</td>
                <td>{text(item?.recognitionType) ?? "-"}</td>
                <td>{String(item?.priority ?? "-")}</td>
                <td>{String(item?.score ?? "-")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h4>下游策略</h4>
      <dl>
        <dt>类型绑定</dt>
        <dd>{text(policy?.typePolicyId) ?? "未解析"}</dd>
        <dt>Metadata</dt>
        <dd>{text(policy?.metadataPolicy) ?? "未解析"}</dd>
        <dt>Naming</dt>
        <dd>{text(policy?.namingPolicy) ?? "未解析"}</dd>
        <dt>Classification</dt>
        <dd>{text(policy?.classificationPolicy) ?? "未解析"}</dd>
        <dt>Organize</dt>
        <dd>{text(policy?.organizePolicy) ?? "未解析"}</dd>
      </dl>
      {metadataPolicy || metadata ? (
        <>
          <h4>元数据测试</h4>
          <dl>
            <dt>有效策略 / Provider</dt>
            <dd>
              {text(metadataPolicy?.id) ?? "未解析"} /{" "}
              {text(metadataPolicy?.providerId) ?? "-"}
            </dd>
            <dt>结果状态</dt>
            <dd>{text(metadata?.status) ?? "离线验证"}</dd>
            <dt>作品</dt>
            <dd>
              {text(metadataIdentity?.title) ??
                text(metadataIdentity?.originalTitle) ??
                "未返回身份"}
            </dd>
          </dl>
        </>
      ) : null}
      <h4>原因与警告</h4>
      <ExplanationList
        values={[...list(recognition?.reasons), ...list(recognition?.warnings)]}
      />
    </div>
  );
}

function NamingExplanation({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  const variables = record(result.renderedVariables);
  return (
    <div className="mf-rules-preview-explanation">
      <h4>命名结果</h4>
      <dl>
        <dt>策略 / RecognitionType</dt>
        <dd>
          {text(result.appliedPolicyId) ?? "-"} /{" "}
          {text(result.recognitionType) ?? "-"}
        </dd>
        <dt>目录</dt>
        <dd>{text(result.directory) ?? "根目录"}</dd>
        <dt>文件名</dt>
        <dd>{text(result.filename) ?? "未生成"}</dd>
        <dt>媒体类型</dt>
        <dd>{text(result.mediaType) ?? "-"}</dd>
      </dl>
      <h4>变量</h4>
      {variables ? (
        <dl>
          {Object.entries(variables).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{String(value ?? "")}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p>无。</p>
      )}
      <h4>清理、截断与警告</h4>
      <ExplanationList
        values={[...list(result.sanitizationChanges), ...list(result.warnings)]}
      />
    </div>
  );
}

function ClassificationExplanation({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  return (
    <div className="mf-rules-preview-explanation">
      <h4>分类结果</h4>
      <dl>
        <dt>状态 / 策略</dt>
        <dd>
          {text(result.status) ?? "未知"} /{" "}
          {text(result.appliedPolicyId) ?? "-"}
        </dd>
        <dt>匹配规则</dt>
        <dd>
          {text(result.matchedRuleName) ??
            text(result.matchedRuleId) ??
            "未匹配"}
        </dd>
        <dt>MediaLibrary</dt>
        <dd>{text(result.mediaLibraryId) ?? "未解析"}</dd>
        <dt>相对路径</dt>
        <dd>{text(result.relativePath) ?? "未生成"}</dd>
        <dt>RecognitionType</dt>
        <dd>{text(result.recognitionType) ?? "-"}</dd>
      </dl>
      <h4>匹配证据与警告</h4>
      <ExplanationList
        values={[...list(result.matchEvidence), ...list(result.warnings)]}
      />
    </div>
  );
}

function OrganizeExplanation({
  result,
}: {
  readonly result: Readonly<Record<string, unknown>>;
}) {
  const destination = record(result.destination);
  const conflict = record(destination?.conflictProjection);
  return (
    <div className="mf-rules-preview-explanation">
      <h4>整理权限与目标</h4>
      <dl>
        <dt>操作 / 冲突策略</dt>
        <dd>
          {text(result.operation) ?? "-"} /{" "}
          {text(result.conflictStrategy) ?? "-"}
        </dd>
        <dt>目标路径</dt>
        <dd>
          {text(destination?.destinationPath) ??
            text(destination?.relativeDestination) ??
            "未生成"}
        </dd>
        <dt>目标结论</dt>
        <dd>
          {text(destination?.verdict) ??
            text(result.destinationStatus) ??
            "未知"}
        </dd>
        <dt>冲突预测</dt>
        <dd>{text(conflict?.projectedOutcome) ?? "无"}</dd>
        <dt>执行是否允许</dt>
        <dd>
          {result.executionAllowed === true
            ? "只读检查通过;仍需独立执行授权"
            : "阻止"}
        </dd>
        <dt>执行授权</dt>
        <dd>{text(result.executionAuthorityGranted) ?? "none"}</dd>
      </dl>
      <h4>所需能力</h4>
      <ExplanationList values={list(result.requiredStorageCapabilities)} />
      <h4>允许 / 阻止原因</h4>
      <ExplanationList values={list(result.allowBlockReasons)} />
      <h4>风险警告</h4>
      <ExplanationList values={list(result.warnings)} />
    </div>
  );
}

function PreviewExplanation({
  kind,
  result,
}: {
  readonly kind: RulesPreviewKind;
  readonly result: Readonly<Record<string, unknown>>;
}) {
  if (kind === "strategy" || kind === "metadata")
    return <StrategyExplanation result={result} />;
  if (kind === "naming") return <NamingExplanation result={result} />;
  if (kind === "classification")
    return <ClassificationExplanation result={result} />;
  return <OrganizeExplanation result={result} />;
}

export function RulesPreviewPanel({
  token,
  family,
  objectId,
  authority,
  values,
  publicationEpoch = 0,
}: Props) {
  const [sample, setSample] = useState<SampleFields>(INITIAL_SAMPLE);
  const [pathMode, setPathMode] = useState(false);
  const [syntheticPath, setSyntheticPath] = useState("The Matrix (1999).mkv");
  const [resourceLibraryId, setResourceLibraryId] = useState(
    authority.resourceLibraries.find((item) => item.enabled)?.id ?? "",
  );
  const [liveMetadata, setLiveMetadata] = useState(false);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<readonly PreviewResult[]>([]);
  const nextId = useRef(1);
  const candidate = useMemo(
    () => ruleCandidateFields(family, values),
    [family, values],
  );
  const currentSample = useMemo(() => {
    try {
      return buildSample(sample, pathMode, syntheticPath);
    } catch {
      return null;
    }
  }, [pathMode, sample, syntheticPath]);
  const currentnessKey = JSON.stringify({
    candidate,
    sample,
    pathMode,
    syntheticPath,
    resourceLibraryId,
    liveMetadata,
    publicationEpoch,
  });
  const currentnessKeyRef = useRef(currentnessKey);
  const previousKey = useRef(currentnessKey);

  useEffect(() => {
    currentnessKeyRef.current = currentnessKey;
    if (previousKey.current === currentnessKey) return;
    previousKey.current = currentnessKey;
    setResults((items) =>
      items.map((item) => (item.stale ? item : { ...item, stale: true })),
    );
  }, [currentnessKey]);

  const changeSample = <K extends keyof SampleFields>(
    field: K,
    value: SampleFields[K],
  ) => setSample((current) => ({ ...current, [field]: value }));

  const addInvalidResult = (kind: RulesPreviewKind, message: string) => {
    setResults((items) => [
      ...items,
      {
        id: nextId.current++,
        kind,
        sampleLabel: "当前类型化样本",
        submittedKey: currentnessKey,
        pending: false,
        outcome: null,
        error: "invalid_sample",
        failureStage: "sample",
        nextAction: message,
        stale: false,
      },
    ]);
  };

  const run = async (kind: RulesPreviewKind) => {
    if (
      kind === "metadata" &&
      liveMetadata &&
      !window.confirm("实时元数据测试会访问已配置 Provider。确认继续吗?")
    )
      return;
    let submittedSample: Record<string, unknown>;
    try {
      submittedSample = buildSample(sample, pathMode, syntheticPath);
    } catch (error) {
      addInvalidResult(kind, String(error));
      return;
    }
    const submittedKey = currentnessKey;
    const submittedCandidate = candidate;
    const submittedPath = syntheticPath;
    const submittedLibrary = resourceLibraryId;
    const submittedLiveMetadata = liveMetadata;
    const id = nextId.current++;
    const sampleLabel = pathMode
      ? `${submittedLibrary || "未选择来源库"} · 路径解析 · ${submittedPath}`
      : `${submittedLibrary || "未选择来源库"} · ${String(submittedSample.title)} · ${String(submittedSample.mediaType)} · ${String(submittedSample.recognitionType)}`;
    setResults((items) => [
      ...items,
      {
        id,
        kind,
        sampleLabel,
        submittedKey,
        pending: true,
        outcome: null,
        error: null,
        failureStage: null,
        nextAction: null,
        stale: false,
      },
    ]);
    const identity = authorityIdentity(authority.active);
    const base = {
      ...identity,
      candidate: { family, objectId, values: submittedCandidate },
    };
    const policyId = String(submittedCandidate.id ?? "");
    const recognitionType = String(submittedSample.recognitionType ?? "C");
    const boundedSample = sampleForKind(kind, submittedSample);
    const body: Record<string, unknown> =
      kind === "strategy"
        ? {
            ...base,
            resourceLibraryId: submittedLibrary,
            syntheticPath: submittedPath,
            liveMetadata: false,
          }
        : kind === "metadata"
          ? {
              ...base,
              policyId,
              resourceLibraryId: submittedLibrary,
              syntheticPath: submittedPath,
              liveMetadata: submittedLiveMetadata,
            }
          : kind === "naming" || kind === "classification"
            ? { ...base, policyId, sample: boundedSample }
            : {
                ...base,
                recognitionType,
                resourceLibraryId: submittedLibrary,
                syntheticPath: submittedPath,
                sample: boundedSample,
              };
    setBusy(true);
    const response = await runRulesPreview(token, kind, body);
    setBusy(false);
    setResults((items) =>
      items.map((item) =>
        item.id !== id
          ? item
          : {
              ...item,
              pending: false,
              outcome: response.ok ? response.model : null,
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
    <section className="mf-rules-preview" aria-labelledby="rules-preview-title">
      <h2 id="rules-preview-title">测试与预览</h2>
      <p>
        显式暂存当前表单为非 Active
        候选并运行零突变分析。结果只对应提交时的候选和样本。
      </p>
      <div className="mf-rules-preview-sample-grid">
        <label>
          样本模式
          <select
            aria-label="样本模式"
            value={pathMode ? "path" : "synthetic"}
            onChange={(event) => setPathMode(event.target.value === "path")}
            disabled={busy}
          >
            <option value="synthetic">类型化样本</option>
            <option value="path">从路径解析</option>
          </select>
        </label>
        <label>
          来源资源库
          <select
            aria-label="来源资源库"
            value={resourceLibraryId}
            onChange={(event) => setResourceLibraryId(event.target.value)}
            disabled={busy}
          >
            <option value="">请选择来源资源库</option>
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
            aria-label="合成来源路径"
            value={syntheticPath}
            maxLength={4096}
            onChange={(event) => setSyntheticPath(event.target.value)}
            disabled={busy}
          />
        </label>
        {!pathMode ? (
          <>
            <label>
              标题
              <input
                aria-label="样本标题"
                value={sample.title}
                maxLength={512}
                onChange={(event) => changeSample("title", event.target.value)}
              />
            </label>
            <label>
              媒体类型
              <select
                aria-label="样本媒体类型"
                value={sample.mediaType}
                onChange={(event) =>
                  changeSample(
                    "mediaType",
                    event.target.value as "movie" | "tv",
                  )
                }
              >
                <option value="movie">电影</option>
                <option value="tv">剧集</option>
              </select>
            </label>
            <label>
              RecognitionType
              <input
                aria-label="样本 RecognitionType"
                value={sample.recognitionType}
                maxLength={64}
                onChange={(event) =>
                  changeSample("recognitionType", event.target.value)
                }
              />
            </label>
            <label>
              年份
              <input
                aria-label="样本年份"
                type="number"
                min="0"
                max="9999"
                value={sample.year}
                onChange={(event) => changeSample("year", event.target.value)}
              />
            </label>
            <label>
              扩展名
              <input
                aria-label="样本扩展名"
                value={sample.extension}
                maxLength={16}
                onChange={(event) =>
                  changeSample("extension", event.target.value)
                }
              />
            </label>
            <details className="mf-rules-preview-advanced">
              <summary>更多类型化样本字段</summary>
              <div className="mf-rules-preview-sample-grid">
                <label>
                  原始标题
                  <input
                    aria-label="样本原始标题"
                    value={sample.originalTitle}
                    maxLength={512}
                    onChange={(event) =>
                      changeSample("originalTitle", event.target.value)
                    }
                  />
                </label>
                <label>
                  季
                  <input
                    aria-label="样本季"
                    type="number"
                    min="0"
                    max="9999"
                    value={sample.season}
                    onChange={(event) =>
                      changeSample("season", event.target.value)
                    }
                  />
                </label>
                <label>
                  集
                  <input
                    aria-label="样本集"
                    type="number"
                    min="0"
                    max="9999"
                    value={sample.episode}
                    onChange={(event) =>
                      changeSample("episode", event.target.value)
                    }
                  />
                </label>
                <label>
                  多集集号
                  <input
                    aria-label="样本多集集号"
                    value={sample.episodes}
                    placeholder="1, 2"
                    onChange={(event) =>
                      changeSample("episodes", event.target.value)
                    }
                  />
                </label>
                <label>
                  单集标题
                  <input
                    aria-label="样本单集标题"
                    value={sample.episodeTitle}
                    maxLength={512}
                    onChange={(event) =>
                      changeSample("episodeTitle", event.target.value)
                    }
                  />
                </label>
                <label>
                  Provider
                  <input
                    aria-label="样本 Provider"
                    value={sample.provider}
                    maxLength={64}
                    onChange={(event) =>
                      changeSample("provider", event.target.value)
                    }
                  />
                </label>
                <label>
                  Provider ID
                  <input
                    aria-label="样本 Provider ID"
                    value={sample.providerId}
                    maxLength={128}
                    onChange={(event) =>
                      changeSample("providerId", event.target.value)
                    }
                  />
                </label>
                {(
                  [
                    "resolution",
                    "source",
                    "videoCodec",
                    "audio",
                    "hdr",
                    "version",
                    "releaseGroup",
                  ] as const
                ).map((field) => (
                  <label key={field}>
                    {field}
                    <input
                      aria-label={`样本 ${field}`}
                      value={sample[field]}
                      maxLength={field === "releaseGroup" ? 128 : 64}
                      onChange={(event) =>
                        changeSample(field, event.target.value)
                      }
                    />
                  </label>
                ))}
                {(
                  ["genres", "countries", "languages", "keywords"] as const
                ).map((field) => (
                  <label key={field}>
                    {field}
                    <input
                      aria-label={`样本 ${field}`}
                      value={sample[field]}
                      placeholder="逗号分隔"
                      onChange={(event) =>
                        changeSample(field, event.target.value)
                      }
                    />
                  </label>
                ))}
                <label>
                  简介
                  <textarea
                    aria-label="样本简介"
                    value={sample.overview}
                    maxLength={2000}
                    onChange={(event) =>
                      changeSample("overview", event.target.value)
                    }
                  />
                </label>
              </div>
            </details>
          </>
        ) : null}
      </div>
      <details className="mf-rules-preview-advanced">
        <summary>高级 / 支持：查看当前样本 JSON</summary>
        <pre>{JSON.stringify(currentSample ?? { invalid: true }, null, 2)}</pre>
      </details>
      <label>
        <input
          type="checkbox"
          checked={liveMetadata}
          onChange={(event) => setLiveMetadata(event.target.checked)}
          disabled={busy}
        />
        允许实时 Metadata Provider 测试
      </label>
      <div className="mf-actions">
        {(
          [
            "strategy",
            "metadata",
            "naming",
            "classification",
            "organize",
          ] as const
        ).map((kind) => (
          <button
            key={kind}
            type="button"
            onClick={() => void run(kind)}
            disabled={busy}
          >
            {kind === "strategy"
              ? "测试识别策略"
              : kind === "metadata"
                ? "测试元数据策略"
                : kind === "naming"
                  ? "预览命名"
                  : kind === "classification"
                    ? "预览分类"
                    : "解释整理权限"}
          </button>
        ))}
      </div>
      {results.map((item) => (
        <article
          key={item.id}
          className="mf-rules-preview-result"
          aria-live="polite"
        >
          <h3>{item.kind} 结果</h3>
          <p>样本: {item.sampleLabel}</p>
          {item.pending ? (
            <p role="status">正在测试提交时的候选与样本...</p>
          ) : null}
          {item.stale || item.outcome?.stale ? (
            <p role="status">该结果已过期;当前表单、样本或 Active 已变化。</p>
          ) : null}
          {item.error ? (
            <div role="alert">
              <p>
                测试失败: {item.error}。失败阶段:{item.failureStage ?? "未知"}。
              </p>
              <p>
                候选输入仍保留;下一步:
                {item.nextAction ?? "检查输入与当前 Active 后显式重跑此项"}。
              </p>
            </div>
          ) : null}
          {item.outcome ? (
            <>
              <p>
                状态: {item.outcome.status}。失败阶段:
                {item.outcome.failureCategory ?? "无"}。
              </p>
              <p>
                候选修订 {item.outcome.revisionId.slice(0, 8)}… · 版本{" "}
                {item.outcome.revisionVersion} · 非 Active
              </p>
              {item.outcome.message ? <p>{item.outcome.message}</p> : null}
              {item.outcome.nextAction ? (
                <p>下一步: {item.outcome.nextAction}</p>
              ) : null}
              {item.outcome.result ? (
                <PreviewExplanation
                  kind={item.kind}
                  result={item.outcome.result}
                />
              ) : null}
              <details className="mf-rules-preview-advanced">
                <summary>高级 / 支持：查看完整证据 JSON</summary>
                <pre>{JSON.stringify(item.outcome.result ?? {}, null, 2)}</pre>
              </details>
            </>
          ) : null}
          {!item.pending ? (
            <button
              type="button"
              onClick={() => void run(item.kind)}
              disabled={busy}
            >
              用当前输入重新运行此项
            </button>
          ) : null}
        </article>
      ))}
    </section>
  );
}
