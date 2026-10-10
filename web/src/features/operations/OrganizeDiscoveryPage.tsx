/**
 * Bounded ResourceLibrary folder/mixed-selection discovery (Slice 44 RO-6).
 *
 * The page shows only backend-advertised facts: the exact admitted relative
 * scopes, durable progress counters, bounded exclusion/instability/read
 * findings and whether the traversal is complete.  Finalizing freezes the
 * discovered source list and links the existing manual intent; it grants no
 * execution authority, and a separate exact Preview plus a confirmed execution
 * remain required.  Discovery itself never mutates Storage.
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
  controlOrganizeDiscovery,
  finalizeOrganizeDiscovery,
} from "../../shared/api/api-client";
import type { OrganizeDiscoveryModel } from "../../entities/operations/discovery";
import {
  organizeDiscoveryQueryKey,
  organizeDiscoveryQueryOptions,
} from "./discovery-query";
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

const STATUS_LABELS: Readonly<Record<string, string>> = {
  queued: "排队中",
  running: "发现中",
  paused: "已暂停",
  waiting_stability: "等待稳定",
  completed: "发现完成",
  partial_success: "部分完成",
  failed: "失败",
  cancelled: "已取消",
};

const FINDING_LABELS: Readonly<Record<string, string>> = {
  primary: "可整理",
  excluded: "已排除",
  unstable: "等待稳定",
  error: "读取失败",
  truncated: "超出上限",
};

const REASON_LABELS: Readonly<Record<string, string>> = {
  temporary_file: "临时/下载中的文件",
  unsupported_extension: "非媒体扩展名",
  configured_exclude: "命中配置排除规则",
  not_included: "不满足配置包含规则",
  unsupported_entry_type: "不支持的条目类型",
  symbolic_link: "符号链接",
  unreadable_directory: "目录不可读",
  waiting_minimum_age: "未达到最小文件年龄",
  waiting_stable_size: "等待稳定大小",
  source_changed_since_observation: "观察到文件发生变化",
  configured_depth_exceeded: "超出配置深度",
  safety_depth_limit: "超出安全深度上限",
  unsafe_provider_entry: "存储返回了不安全的条目",
  repeated_provider_cursor: "存储返回了重复游标",
  primary_limit: "来源数量达到上限",
  entry_limit: "检查条目数达到上限",
  directory_limit: "打开目录数达到上限",
  page_limit: "分页次数达到上限",
  depth_limit: "深度达到上限",
  time_limit: "活跃时间达到上限",
  read_failure: "读取失败",
  cursor_repeated: "存储返回了重复游标",
  cursor_invalid: "存储返回了无效游标",
};

/**
 * The incomplete reasons that mean a durable budget/safety bound was
 * exhausted, published by the backend through the finalize action's bounded
 * refusal. Such a walk recorded a truncated prefix — never an executable
 * subset — so the page offers the native narrowing action instead of finalize.
 */
function budgetLimited(model: OrganizeDiscoveryModel): boolean {
  return (
    model.progress.incomplete &&
    model.progress.incompleteReason !== null &&
    model.actions.finalize.refusal === "discovery_budget_limited"
  );
}

function label(map: Readonly<Record<string, string>>, value: string): string {
  return map[value] ?? value;
}

export function OrganizeDiscoveryPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { discoveryId } = useParams({
    from: "/operations/organize/discovery/$discoveryId",
  });
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const filesReturn = readFilesReturnContext(searchParams);
  const operationsReturn = readOperationsReturnContext(searchParams);
  const [controlError, setControlError] = useState<string | null>(null);
  const query = useQuery(organizeDiscoveryQueryOptions(token, discoveryId));

  const refresh = () => {
    void queryClient.invalidateQueries({
      queryKey: [organizeDiscoveryQueryKey, discoveryId],
    });
  };

  const controlMutation = useMutation({
    mutationFn: async (action: "pause" | "resume" | "cancel") => {
      const read = query.data;
      if (read === undefined || !read.ok) {
        throw new Error("发现状态尚未就绪。");
      }
      const result = await controlOrganizeDiscovery(token, {
        discoveryId,
        action,
        expectedVersion: read.model.version,
      });
      if (!result.ok) throw new Error(result.code);
      return action;
    },
    onSuccess: () => {
      setControlError(null);
      refresh();
    },
    onError: (error) => {
      setControlError(
        error instanceof Error
          ? `无法更新发现状态（${error.message}），请刷新后重试。`
          : "无法更新发现状态，请刷新后重试。",
      );
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: async () => {
      const read = query.data;
      if (read === undefined || !read.ok) {
        throw new Error("发现状态尚未就绪。");
      }
      const result = await finalizeOrganizeDiscovery(token, {
        discoveryId,
        expectedVersion: read.model.version,
      });
      if (!result.ok) throw new Error(result.code);
      return result.intentId;
    },
    onSuccess: (intentId) => {
      setControlError(null);
      if (intentId === null) {
        refresh();
        return;
      }
      void navigate({
        to: "/operations/organize/intent/$intentId",
        params: { intentId },
        search: {
          ...(filesReturn === null ? {} : filesReturnSearch(filesReturn)),
          ...operationsReturnSearch(operationsReturn),
        },
      });
    },
    onError: (error) => {
      // A budget/safety-limited walk is refused durably by the backend. The
      // page explains the honest refusal instead of a generic transport note.
      if (
        error instanceof Error &&
        error.message === "discovery_budget_limited"
      ) {
        setControlError(
          "发现已达到预算或安全上限,已知来源只是不完整的子集,不能冻结执行;请缩小所选范围后重新开始一次有界发现。",
        );
        return;
      }
      setControlError(
        error instanceof Error
          ? `无法冻结发现结果（${error.message}），请刷新后重试。`
          : "无法冻结发现结果，请刷新后重试。",
      );
    },
  });

  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <div>
          <h2>整理发现</h2>
          <p className="mf-dashboard-meta">
            这里只读取存储元数据，不会移动、复制或删除任何文件。
            冻结来源清单后，仍需在精确预览上单独确认才会执行整理。
          </p>
        </div>
        <RefreshControl onRefresh={refresh} refreshing={query.isFetching} />
      </header>
      <AuthorizedReadBoundary query={query} unavailableTitle="发现不可用">
        {(view) => {
          if (view.data === undefined) {
            return (
              <StatusBanner variant="info" title="正在读取发现状态">
                <p>正在读取当前发现的持久状态。</p>
              </StatusBanner>
            );
          }
          if (!view.data.ok) {
            return (
              <StatusBanner variant="error" title="无法读取发现状态">
                <p>{view.data.nextAction ?? "请刷新后重试。"}</p>
              </StatusBanner>
            );
          }
          const model: OrganizeDiscoveryModel = view.data.model;
          return (
            <div className="mf-dashboard-body">
              <StatusBanner
                variant={
                  model.status === "failed"
                    ? "error"
                    : model.progress.incomplete
                      ? "warning"
                      : "info"
                }
                title={label(STATUS_LABELS, model.status)}
              >
                <p>{model.nextAction}</p>
                {model.progress.message !== "" ? (
                  <p>{model.progress.message}</p>
                ) : null}
                {model.progress.incomplete ? (
                  <p role="status">
                    发现未完整遍历所选范围，已知来源只能作为明确复核的子集，
                    不会自动成为可执行的前 N 项。
                  </p>
                ) : null}
                {budgetLimited(model) ? (
                  <p role="status">
                    本次发现已达到预算或安全上限,已记录的来源是一个被截断的前缀,
                    不能冻结为可执行清单。请缩小所选范围后重新开始一次有界发现。
                  </p>
                ) : null}
              </StatusBanner>

              <section aria-label="已选范围">
                <h3>已选范围（{model.selection.scopeCount}）</h3>
                <ul>
                  {model.selection.scopes.map((scope) => (
                    <li key={scope.path}>
                      {scope.kind === "directory" ? "文件夹 " : "文件 "}
                      <code>{scope.path}</code>
                    </li>
                  ))}
                </ul>
              </section>

              <section aria-label="发现进度">
                <h3>进度</h3>
                <dl>
                  <dt>可整理来源</dt>
                  <dd>{model.progress.primarySources}</dd>
                  <dt>已检查条目</dt>
                  <dd>{model.progress.visitedEntries}</dd>
                  <dt>已打开目录</dt>
                  <dd>{model.progress.visitedDirectories}</dd>
                  <dt>已排除</dt>
                  <dd>{model.progress.excludedEntries}</dd>
                  <dt>等待稳定</dt>
                  <dd>{model.progress.unstableEntries}</dd>
                  <dt>读取失败</dt>
                  <dd>{model.progress.errorEntries}</dd>
                </dl>
                <p>
                  {model.progress.incomplete
                    ? `未完整遍历：${model.progress.incompleteReason ?? "未知原因"}`
                    : "已完整遍历所选范围。"}
                </p>
              </section>

              {model.progress.reasons.length > 0 ? (
                <section aria-label="排除与等待原因">
                  <h3>排除与等待原因</h3>
                  <ul>
                    {model.progress.reasons.map((item) => (
                      <li key={item.reason}>
                        {label(REASON_LABELS, item.reason)} × {item.count}
                        {item.examplePath !== null ? (
                          <>
                            {" "}
                            （例如 <code>{item.examplePath}</code>）
                          </>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <section aria-label="已发现来源">
                <h3>已发现来源（{model.sources.length}）</h3>
                {model.sources.length === 0 ? (
                  <p>当前没有可整理的媒体来源。</p>
                ) : (
                  <ul>
                    {model.sources.map((source) => (
                      <li key={source.path}>
                        <code>{source.path}</code>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {model.progress.findings.length > 0 ? (
                <section aria-label="发现明细">
                  <h3>发现明细</h3>
                  <ul>
                    {model.progress.findings.map((finding, index) => (
                      <li key={`${finding.kind}:${finding.path}:${index}`}>
                        {label(FINDING_LABELS, finding.kind)}{" "}
                        <code>{finding.path}</code> —{" "}
                        {label(REASON_LABELS, finding.reason)}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {model.worker.ready !== true ? (
                <StatusBanner variant="warning" title="处理 Worker 不可用">
                  <p>{model.worker.durableState}</p>
                  <p>{model.worker.nextAction}</p>
                </StatusBanner>
              ) : null}

              {controlError !== null ? (
                <p className="mf-error" role="status">
                  {controlError}
                </p>
              ) : null}

              <div className="mf-dashboard-actions">
                {model.actions.pause.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("pause")}
                    disabled={controlMutation.isPending}
                  >
                    暂停发现
                  </Button>
                ) : null}
                {model.actions.resume.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("resume")}
                    disabled={controlMutation.isPending}
                  >
                    继续发现
                  </Button>
                ) : null}
                {model.actions.cancel.available ? (
                  <Button
                    variant="secondary"
                    onClick={() => controlMutation.mutate("cancel")}
                    disabled={controlMutation.isPending}
                  >
                    取消发现
                  </Button>
                ) : null}
                {model.actions.finalize.available ? (
                  <Button
                    onClick={() => finalizeMutation.mutate()}
                    disabled={finalizeMutation.isPending}
                  >
                    冻结来源并继续整理
                  </Button>
                ) : null}
                {model.intentId !== null ? (
                  <Link
                    to="/operations/organize/intent/$intentId"
                    params={{ intentId: model.intentId }}
                    search={{
                      ...(filesReturn === null
                        ? {}
                        : filesReturnSearch(filesReturn)),
                      ...operationsReturnSearch(operationsReturn),
                    }}
                  >
                    打开整理意图
                  </Link>
                ) : null}
              </div>
            </div>
          );
        }}
      </AuthorizedReadBoundary>
      <nav aria-label="整理来源返回">
        {filesReturn !== null && (
          <Link to={filesReturnHref(filesReturn)}>返回文件</Link>
        )}
        <Link
          to="/operations"
          search={operationsLandingSearch(operationsReturn, null)}
        >
          返回任务中心
        </Link>
      </nav>
    </div>
  );
}
