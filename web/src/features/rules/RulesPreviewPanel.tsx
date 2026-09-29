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

interface PreviewResult {
  readonly id: number;
  readonly kind: RulesPreviewKind;
  readonly sampleLabel: string;
  readonly outcome: RulesPreviewModel | null;
  readonly error: string | null;
  readonly failureStage: string | null;
  readonly nextAction: string | null;
  readonly stale: boolean;
}

const DEFAULT_SAMPLE = JSON.stringify(
  {
    title: "The Matrix",
    mediaType: "movie",
    recognitionType: "C",
    year: 1999,
    extension: "mkv",
  },
  null,
  2,
);

export function RulesPreviewPanel({
  token,
  family,
  objectId,
  authority,
  values,
  publicationEpoch = 0,
}: Props) {
  const [sampleInput, setSampleInput] = useState(DEFAULT_SAMPLE);
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
  const currentnessKey = JSON.stringify({
    candidate,
    sampleInput,
    syntheticPath,
    resourceLibraryId,
    liveMetadata,
    publicationEpoch,
  });
  const previousKey = useRef(currentnessKey);

  useEffect(() => {
    if (previousKey.current === currentnessKey) return;
    previousKey.current = currentnessKey;
    setResults((items) =>
      items.map((item) => (item.stale ? item : { ...item, stale: true })),
    );
  }, [currentnessKey]);

  const run = async (kind: RulesPreviewKind) => {
    if (
      kind === "metadata" &&
      liveMetadata &&
      !window.confirm("实时元数据测试会访问已配置 Provider。确认继续吗?")
    )
      return;
    let sample: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(sampleInput);
      if (
        parsed === null ||
        typeof parsed !== "object" ||
        Array.isArray(parsed)
      )
        throw new Error("样本必须是对象");
      sample = parsed as Record<string, unknown>;
    } catch (error) {
      setResults((items) => [
        ...items,
        {
          id: nextId.current++,
          kind,
          sampleLabel: sampleInput.slice(0, 160),
          outcome: null,
          error: String(error),
          failureStage: "sample",
          nextAction: "修正 JSON 样本后显式重新运行此项",
          stale: false,
        },
      ]);
      return;
    }
    const identity = authorityIdentity(authority.active);
    const base = {
      ...identity,
      candidate: { family, objectId, values: candidate },
    };
    const policyId = String(candidate.id ?? "");
    const recognitionType = String(sample.recognitionType ?? "C");
    const body: Record<string, unknown> =
      kind === "strategy"
        ? {
            ...base,
            resourceLibraryId,
            syntheticPath,
            liveMetadata: false,
          }
        : kind === "metadata"
          ? {
              ...base,
              policyId,
              resourceLibraryId,
              syntheticPath,
              liveMetadata,
            }
          : kind === "naming" || kind === "classification"
            ? { ...base, policyId, sample }
            : {
                ...base,
                recognitionType,
                resourceLibraryId,
                syntheticPath,
                sample,
              };
    const sampleLabel = `${resourceLibraryId || "未选择来源库"} · ${syntheticPath} · ${sampleInput.replace(/\s+/g, " ").slice(0, 120)}`;
    setBusy(true);
    const result = await runRulesPreview(token, kind, body);
    setBusy(false);
    setResults((items) => [
      ...items,
      {
        id: nextId.current++,
        kind,
        sampleLabel,
        outcome: result.ok ? result.model : null,
        error: result.ok ? null : result.code,
        failureStage: result.ok ? null : (result.details?.stage ?? "request"),
        nextAction: result.ok ? null : (result.details?.nextAction ?? null),
        stale: false,
      },
    ]);
  };

  return (
    <section className="mf-rules-preview" aria-labelledby="rules-preview-title">
      <h2 id="rules-preview-title">测试与预览</h2>
      <p>
        显式暂存当前表单为非 Active
        候选并运行零突变分析;修改表单、样本或发布后，已有结果会标记为过期。
      </p>
      <label htmlFor="rules-preview-resource-library">来源资源库</label>
      <select
        id="rules-preview-resource-library"
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
      <label htmlFor="rules-preview-path">合成来源路径</label>
      <input
        id="rules-preview-path"
        value={syntheticPath}
        onChange={(event) => setSyntheticPath(event.target.value)}
        disabled={busy}
      />
      <label htmlFor="rules-preview-sample">命名、分类与目标样本 JSON</label>
      <textarea
        id="rules-preview-sample"
        value={sampleInput}
        onChange={(event) => setSampleInput(event.target.value)}
        disabled={busy}
        rows={7}
      />
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
              {item.outcome.message ? <p>{item.outcome.message}</p> : null}
              {item.outcome.nextAction ? (
                <p>下一步: {item.outcome.nextAction}</p>
              ) : null}
              <pre>{JSON.stringify(item.outcome.result ?? {}, null, 2)}</pre>
            </>
          ) : null}
          <button
            type="button"
            onClick={() => void run(item.kind)}
            disabled={busy}
          >
            用当前输入重新运行此项
          </button>
        </article>
      ))}
    </section>
  );
}
