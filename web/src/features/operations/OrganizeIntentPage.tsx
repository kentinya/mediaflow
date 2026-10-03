/**
 * Durable manual intent detail: optimistic choice editing and exact Preview.
 *
 * Every control comes from the backend document: the enabled pinned options,
 * per-item ``version`` values and the advertised ``actions`` availability.
 * A choice edit submits the intent and item versions the operator actually
 * saw, so a concurrent change is rejected atomically instead of silently
 * overwriting another edit. Editing a choice invalidates earlier Preview
 * evidence, and the page never treats a Preview as execution authority.
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
  submitOrganizePreview,
  updateOrganizeChoice,
} from "../../shared/api/api-client";
import type {
  OrganizeChoiceModel,
  OrganizeIntentItemModel,
} from "../../entities/operations/organize";
import {
  organizeIntentQueryKey,
  organizeIntentQueryOptions,
} from "./organize-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  filesReturnHref,
  filesReturnSearch,
  readFilesReturnContext,
} from "../../shared/navigation/files-return";
import {
  operationsLandingSearch,
  operationsReturnSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";

function displayEnum(value: string): string {
  const labels: Readonly<Record<string, string>> = {
    blocked: "受阻",
    cancelled: "已取消",
    completed: "已完成",
    failed: "失败",
    pending: "等待中",
    previewed: "预览完成",
    ready: "就绪",
    running: "处理中",
    unknown: "未知",
  };
  return labels[value.toLowerCase()] ?? value;
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

function ChoiceEditor({
  intentId,
  intentVersion,
  item,
  options,
  onSaved,
  onReload,
}: {
  readonly intentId: string;
  readonly intentVersion: number;
  readonly item: OrganizeIntentItemModel;
  readonly options: {
    readonly recognitionTypes: readonly {
      readonly id: string;
      readonly name: string | null;
      readonly metadataPolicyId: string | null;
      readonly namingPolicyId: string | null;
      readonly classificationPolicyId: string | null;
      readonly organizePolicyId: string | null;
      readonly enabled: boolean;
    }[];
  };
  readonly onSaved: (message: string) => void;
  readonly onReload: () => void;
}) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const recognitionTypes = options.recognitionTypes.filter(
    (value) => value.enabled,
  );
  // RecognitionType is the single operator-facing choice source. The three
  // downstream policies are never editable on their own; they are always the
  // exact pinned mapping of the selected RecognitionType, so the normal journey
  // can never submit an `incompatible_choice`.
  const [recognitionTypeId, setRecognitionTypeId] = useState<string>(
    item.choice.recognitionTypeId ?? "",
  );
  const [result, setResult] = useState<string | null>(null);

  const editable = Boolean(item.nextAction) && item.status === "ready";
  const hasSelection = recognitionTypeId !== "";
  const selected = hasSelection
    ? recognitionTypes.find((value) => value.id === recognitionTypeId)
    : undefined;
  // A selected RecognitionType that is missing from the current pinned options
  // (disabled or removed), or whose downstream mapping is incomplete, must fail
  // closed: the editor shows an actionable reload state and submits nothing.
  const selectionUnavailable = hasSelection && selected === undefined;
  const mappingComplete =
    selected !== undefined &&
    selected.namingPolicyId !== null &&
    selected.classificationPolicyId !== null &&
    selected.organizePolicyId !== null;
  const mappingIncomplete = selected !== undefined && !mappingComplete;
  const failClosed = selectionUnavailable || mappingIncomplete;

  // The submitted choice is always projected from the pinned mapping, so an
  // initial render with a stale stored downstream policy is normalized to the
  // RecognitionType's exact policies before any save.
  const projectedChoice: OrganizeChoiceModel | null =
    selected !== undefined && mappingComplete
      ? {
          metadata: item.choice.metadata,
          recognitionTypeId: selected.id,
          namingPolicyId: selected.namingPolicyId,
          classificationPolicyId: selected.classificationPolicyId,
          organizePolicyId: selected.organizePolicyId,
        }
      : null;

  const mutation = useMutation({
    mutationFn: (next: OrganizeChoiceModel) =>
      updateOrganizeChoice(token, {
        intentId,
        itemId: item.itemId,
        expectedVersion: intentVersion,
        expectedItemVersion: item.version,
        ...(next.recognitionTypeId
          ? { recognitionTypeId: next.recognitionTypeId }
          : {}),
        ...(next.namingPolicyId ? { namingPolicyId: next.namingPolicyId } : {}),
        ...(next.classificationPolicyId
          ? { classificationPolicyId: next.classificationPolicyId }
          : {}),
        ...(next.organizePolicyId
          ? { organizePolicyId: next.organizePolicyId }
          : {}),
      }),
    retry: false,
    onSuccess: (value) => {
      if (value.ok) {
        setResult(null);
        onSaved(
          "选择已持久保存；此意图此前生成的预览已成为历史证据。执行前请生成新的预览。",
        );
        void queryClient.invalidateQueries({
          queryKey: [organizeIntentQueryKey],
        });
        return;
      }
      setResult(
        value.status === 409
          ? "其他更改已先保存；本次编辑未覆盖它。请刷新意图后重新选择。"
          : `选择被拒绝（${value.code}），没有保存任何更改。`,
      );
    },
  });

  return (
    <section className="mf-count-section">
      <h3>{item.filename ?? item.itemId}</h3>
      <dl>
        <dt>来源身份</dt>
        <dd>{safeValue(item.sourceFileId)}</dd>
        <dt>Storage 相对路径</dt>
        <dd>{safeValue(item.sourcePath)}</dd>
        <dt>资源库 / Storage</dt>
        <dd>
          {safeValue(item.resourceLibraryId)} /{" "}
          {safeValue(item.sourceStorageId)}
        </dd>
        <dt>扫描状态 / 文件版本</dt>
        <dd>
          {displayEnum(item.scanStatus ?? "unknown")} /{" "}
          {displayEnum(item.occurrenceState ?? "unknown")}
        </dd>
        <dt>条目状态 / 版本</dt>
        <dd>
          {displayEnum(item.status)} / {item.version}
        </dd>
      </dl>
      {item.failure !== null && (
        <StatusBanner variant="error" title="条目问题">
          <p>{item.failure.message}</p>
          <p className="mf-dashboard-meta">{item.failure.nextAction}</p>
        </StatusBanner>
      )}
      <div className="mf-field-group">
        <label>
          识别类型（RecognitionType）
          <select
            aria-label={`识别类型 ${item.itemId}`}
            value={recognitionTypeId}
            disabled={!editable}
            onChange={(event) => {
              setResult(null);
              setRecognitionTypeId(event.target.value);
            }}
          >
            <option value="">选择识别类型</option>
            {recognitionTypes.map((value) => (
              <option key={value.id} value={value.id}>
                {value.name ?? value.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          命名策略
          <select
            aria-label={`命名策略 ${item.itemId}`}
            value={projectedChoice?.namingPolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.namingPolicyId !== undefined &&
              projectedChoice?.namingPolicyId !== null && (
                <option value={projectedChoice.namingPolicyId}>
                  {projectedChoice.namingPolicyId}
                </option>
              )}
          </select>
        </label>
        <label>
          分类策略
          <select
            aria-label={`分类策略 ${item.itemId}`}
            value={projectedChoice?.classificationPolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.classificationPolicyId !== undefined &&
              projectedChoice?.classificationPolicyId !== null && (
                <option value={projectedChoice.classificationPolicyId}>
                  {projectedChoice.classificationPolicyId}
                </option>
              )}
          </select>
        </label>
        <label>
          整理策略
          <select
            aria-label={`整理策略 ${item.itemId}`}
            value={projectedChoice?.organizePolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.organizePolicyId !== undefined &&
              projectedChoice?.organizePolicyId !== null && (
                <option value={projectedChoice.organizePolicyId}>
                  {projectedChoice.organizePolicyId}
                </option>
              )}
          </select>
        </label>
        <p className="mf-dashboard-meta">
          识别类型决定命名、分类和整理策略。选择识别类型后会应用当前预览固定的精确策略映射，不能单独修改下游策略。
        </p>
      </div>
      {failClosed && (
        <StatusBanner variant="error" title="识别类型策略映射不可用">
          <p>
            {selectionUnavailable
              ? `当前固定配置中没有识别类型“${recognitionTypeId}”，无法应用其策略。`
              : `当前固定配置中，识别类型“${recognitionTypeId}”缺少命名、分类或整理策略。`}
          </p>
          <p className="mf-dashboard-meta">
            请刷新意图并从当前可用选项中重新选择。本次没有提交任何选择。
          </p>
          <div className="mf-actions">
            <Button type="button" variant="secondary" onClick={onReload}>
              刷新选项
            </Button>
          </div>
        </StatusBanner>
      )}
      <div className="mf-actions">
        <Button
          type="button"
          disabled={
            mutation.isPending ||
            !editable ||
            !hasSelection ||
            failClosed ||
            projectedChoice === null
          }
          onClick={() => {
            if (projectedChoice !== null) {
              mutation.mutate(projectedChoice);
            }
          }}
        >
          {mutation.isPending ? "正在保存选择…" : "保存选择"}
        </Button>
      </div>
      {result !== null && (
        <StatusBanner variant="error" title="选择未保存">
          <p>{result}</p>
        </StatusBanner>
      )}
    </section>
  );
}

export function OrganizeIntentPage() {
  const { intentId } = useParams({
    from: "/operations/organize/intent/$intentId",
  });
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const filesReturn = readFilesReturnContext(searchParams);
  const operationsReturn = readOperationsReturnContext(searchParams);
  const token = useAuthToken();
  const navigate = useNavigate();
  const [notice, setNotice] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const intentQuery = useQuery(organizeIntentQueryOptions(token, intentId));

  const previewMutation = useMutation({
    mutationFn: (expectedVersion: number) =>
      submitOrganizePreview(token, { intentId, expectedVersion }),
    retry: false,
    onMutate: () => setPreviewError(null),
    onSuccess: (value) => {
      if (value.ok) {
        void navigate({
          to: "/operations/organize/preview/$previewId",
          params: { previewId: value.model.previewId },
          search: {
            ...(filesReturn === null ? {} : filesReturnSearch(filesReturn)),
            ...operationsReturnSearch(operationsReturn),
          },
        });
        return;
      }
      setPreviewError(
        `精确预览被拒绝（${value.code}），没有保存更改。请刷新意图后重新生成预览。`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={intentQuery}
      unavailableTitle="整理意图不可用"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="正在读取持久整理意图">
              <p>正在读取当前整理意图。</p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                  search={
                    operationsReturn === null
                      ? {}
                      : operationsLandingSearch(operationsReturn, null)
                  }
                >
                  返回操作与任务
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const intent = data.model;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>整理意图</h2>
                <p className="mf-dashboard-meta">
                  意图 {intent.intentId} · 版本 {intent.version} ·{" "}
                  {displayEnum(intent.status)} · 配置{" "}
                  {safeValue(intent.configurationSnapshotId)}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <p className="mf-dashboard-meta">
              此意图不会修改
              Storage。更改选择会使此前预览失效；执行前必须使用与当前选择一致的预览。
            </p>
            {notice !== null && (
              <StatusBanner variant="info" title="选择已更新">
                <p>{notice}</p>
              </StatusBanner>
            )}
            {intent.failure !== null && (
              <StatusBanner variant="error" title="意图问题">
                <p>{intent.failure.message}</p>
                <p className="mf-dashboard-meta">{intent.failure.nextAction}</p>
              </StatusBanner>
            )}
            {intent.items.map((item) => (
              <ChoiceEditor
                key={item.itemId}
                intentId={intent.intentId}
                intentVersion={intent.version}
                item={item}
                options={intent.options}
                onSaved={setNotice}
                onReload={refresh}
              />
            ))}
            <section className="mf-count-section">
              <h3>精确预览</h3>
              <p className="mf-dashboard-meta">
                {intent.actions.preview.available
                  ? "后端已提供针对当前选择的零变更预览。"
                  : `暂不可用：${intent.actions.preview.reason ?? "后端未提供预览操作"}`}
              </p>
              {intent.actions.preview.durableOutcome && (
                <p className="mf-dashboard-meta">
                  {intent.actions.preview.durableOutcome}
                </p>
              )}
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={
                    !intent.actions.preview.available ||
                    previewMutation.isPending
                  }
                  onClick={() => previewMutation.mutate(intent.version)}
                >
                  {previewMutation.isPending
                    ? "正在生成精确预览…"
                    : "生成精确预览"}
                </Button>
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                  search={
                    operationsReturn === null
                      ? {}
                      : operationsLandingSearch(operationsReturn, null)
                  }
                >
                  返回操作与任务
                </Link>
                {filesReturn !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to={filesReturnHref(filesReturn)}
                  >
                    返回文件
                  </Link>
                )}
                {operationsReturn !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations"
                    search={operationsLandingSearch(operationsReturn, null)}
                  >
                    返回任务中心
                  </Link>
                )}
              </div>
              {previewError !== null && (
                <StatusBanner variant="error" title="预览未生成">
                  <p>{previewError}</p>
                </StatusBanner>
              )}
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
