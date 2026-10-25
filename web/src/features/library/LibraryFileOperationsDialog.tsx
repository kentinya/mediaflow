/**
 * 当前页面操作状态 — the originating library's own ordinary file operations.
 *
 * The Files and MediaLibrary headers open this shared, centered, accessible
 * dialog.  It lists exactly the operations that originated in the library the
 * operator is browsing (from durable Task evidence), lets them select one and
 * read its factual stage, source/destination, effects and permitted next
 * action, and reuses only the backend-advertised lifecycle controls through
 * the normal Task lifecycle route.
 *
 * Closing, polling, refreshing or reopening the dialog never admits a command,
 * never replays a completed or uncertain item and never changes media by
 * itself.  Empty, loading, read-error, denied and unavailable states each have
 * a bounded read/recovery path; a read grant alone can never produce a
 * mutation.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { DirectCommandLibraryKind } from "../../entities/library/direct-files";
import {
  LIBRARY_OPERATION_CERTAINTY_LABELS,
  LIBRARY_OPERATION_EFFECT_LABELS,
  LIBRARY_OPERATION_ITEM_STATUS_LABELS,
  isOlderLibraryOperationSnapshot,
  libraryOperationHasProgress,
  libraryOperationSnapshotKey,
  libraryOperationStateLabel,
  type LibraryFileOperationChild,
  type LibraryFileOperationEntry,
  type LibraryFileOperationItem,
} from "../../entities/library/file-operations";
import {
  fetchLibraryFileOperationDetail,
  fetchLibraryFileOperations,
  fetchLibraryFileOperationOrigins,
  mutateLifecycle,
} from "../../shared/api/api-client";
import { useAuthToken } from "../../shared/api/auth-context";
import { ModalDialog } from "./FileCommandDialogs";

const PAGE_LIMIT = 20;
/** The bounded item page the local detail reads (and continues). */
const ITEM_PAGE_LIMIT = 50;
/** How often a still-running operation's own snapshot is re-read. */
const POLL_INTERVAL_MS = 2000;

/** The bounded copy of one read failure; never raw server text. */
function readFailureMessage(code: string): string {
  switch (code) {
    case "forbidden":
      return "当前账号没有读取文件操作历史所需的权限；本页面没有创建或修改任何任务。";
    case "library_file_operations_unavailable":
      return "暂时无法读取持久操作记录（运行数据库不可用）；没有创建或修改任何任务，请稍后重试。";
    case "invalid_request":
      return "读取参数无效；本次没有查询任何任务，请刷新页面后重试。";
    case "malformed_response":
      return "服务返回了无法理解的操作记录；本页面没有据此执行任何操作，请刷新后重试。";
    case "transport_unavailable":
      return "无法连接服务；本页面没有创建或修改任何任务，请检查连接后重试。";
    default:
      return "读取文件操作记录失败；本页面没有创建或修改任何任务，请稍后重试。";
  }
}

function controlFailureMessage(code: string): string {
  switch (code) {
    case "stale_task_state":
      return "该操作在此之后已改变；暂停/取消/继续未执行任何工作，请刷新后重新确认。";
    case "lifecycle_conflict":
      return "后端按当前持久状态拒绝了这个控制请求；没有执行任何新的工作，请刷新查看当前状态。";
    case "forbidden":
      return "当前账号没有控制该操作的权限；没有执行任何新的工作。";
    case "not_found":
      return "该操作记录已不存在；没有执行任何新的工作。";
    case "transport_unavailable":
      return "控制请求未能到达服务，结果未知；没有自动重试，请刷新后核对当前状态。";
    default:
      return "控制请求被拒绝；没有自动重试，请刷新后核对当前状态。";
  }
}

/** A short bounded label of one read failure cause, for an inline sentence. */
function readFailureLabel(code: string): string {
  switch (code) {
    case "forbidden":
      return "当前账号没有读取权限";
    case "library_file_operations_unavailable":
      return "持久操作记录不可用";
    case "invalid_request":
      return "读取参数无效";
    case "malformed_response":
      return "服务返回了无法理解的记录";
    case "transport_unavailable":
      return "无法连接服务";
    default:
      return "读取失败";
  }
}

/**
 * The bounded failure code of one read, from its answered document or its throw.
 *
 * A read that *threw* (rather than answering with a bounded failure document)
 * only means "no read arrived"; a answered-and-failed read keeps its own code
 * so the operator sees the real cause instead of a generic one.
 */
function readFailureCodeOf(
  isError: boolean,
  data: { readonly ok: boolean; readonly code?: string } | undefined,
): string | null {
  if (data !== undefined) {
    return data.ok ? null : (data.code ?? "malformed_response");
  }
  return isError ? "transport_unavailable" : null;
}

const ACTION_LABELS: Record<string, string> = {
  pause: "请求暂停",
  cancel: "取消",
  resume: "继续",
};

function StageList({
  entry,
  selected,
  onSelect,
}: {
  readonly entry: LibraryFileOperationEntry;
  readonly selected: boolean;
  readonly onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        className={
          selected
            ? "mf-operation-entry mf-operation-entry-selected"
            : "mf-operation-entry"
        }
        aria-pressed={selected}
        aria-label={`操作 ${entry.operationLabel} ${entry.taskId}`}
        onClick={onSelect}
      >
        <span className="mf-operation-entry-title">
          <strong>{entry.operationLabel}</strong>
          <span className="mf-status-badge">
            {libraryOperationStateLabel(entry)}
          </span>
        </span>
        <span className="mf-operation-entry-meta">
          {entry.sourceScope ?? "来源记录不可用"}
          {entry.targetScope !== null && entry.targetScope !== entry.sourceScope
            ? ` → ${entry.targetScope}`
            : ""}
        </span>
        <span className="mf-operation-entry-meta">
          成功 {entry.succeededItems} / 失败 {entry.failedItems} / 共{" "}
          {entry.totalItems} 项
        </span>
      </button>
    </li>
  );
}

function ChildEvidence({
  child,
}: {
  readonly child: LibraryFileOperationChild;
}) {
  const statusLabel =
    LIBRARY_OPERATION_ITEM_STATUS_LABELS[child.status] ?? child.status;
  const effectLabel =
    LIBRARY_OPERATION_EFFECT_LABELS[child.effect] ?? child.effect;
  return (
    <li className="mf-operation-child">
      <span className="mf-operation-entry-title">
        <strong>{child.path}</strong>
        <span className="mf-status-badge">{statusLabel}</span>
      </span>
      {child.destination !== "" && child.destination !== child.path && (
        <span className="mf-operation-entry-meta">
          目标：{child.destination}
        </span>
      )}
      <span className="mf-operation-entry-meta">效果：{effectLabel}</span>
      {child.checkpoints.length > 0 && (
        <span className="mf-operation-entry-meta">
          已完成步骤：{child.checkpoints.join("、")}
        </span>
      )}
      {child.failure !== null && (
        <span className="mf-operation-item-failure">
          {child.failure.message}
        </span>
      )}
    </li>
  );
}

function ItemEvidence({ item }: { readonly item: LibraryFileOperationItem }) {
  const statusLabel =
    LIBRARY_OPERATION_ITEM_STATUS_LABELS[item.status] ?? item.status;
  const effectLabel =
    LIBRARY_OPERATION_EFFECT_LABELS[item.effect] ?? item.effect;
  const certaintyLabel =
    LIBRARY_OPERATION_CERTAINTY_LABELS[item.effectCertainty] ??
    item.effectCertainty;
  return (
    <li className="mf-operation-item">
      <span className="mf-operation-entry-title">
        <strong>{item.path}</strong>
        <span className="mf-status-badge">{statusLabel}</span>
      </span>
      {item.destination !== "" && item.destination !== item.path && (
        <span className="mf-operation-entry-meta">
          目标：{item.destination}
        </span>
      )}
      <span className="mf-operation-entry-meta">
        效果：{effectLabel}（{certaintyLabel}）
        {item.stage === null ? "" : ` · 阶段：${item.stage}`}
      </span>
      {item.knownEffects.length > 0 && (
        <span className="mf-operation-entry-meta">
          已记录影响：{item.knownEffects.join("、")}
        </span>
      )}
      {item.failure !== null && (
        <span className="mf-operation-item-failure">
          {item.failure.message}
        </span>
      )}
      {item.children.length > 0 && (
        <>
          <span className="mf-operation-entry-meta">
            已记录的子项（{item.children.length} 项）：
          </span>
          <ul className="mf-operation-child-list">
            {item.children.map((child) => (
              <ChildEvidence
                key={`${item.itemId}:${child.path}`}
                child={child}
              />
            ))}
          </ul>
          {item.childrenTruncated && (
            <span className="mf-operation-entry-meta">
              该条目的子项记录已按上限截断。
            </span>
          )}
        </>
      )}
      <span className="mf-operation-entry-meta">下一步：{item.nextAction}</span>
    </li>
  );
}

function OperationDetail({
  kind,
  libraryId,
  taskId,
  token,
  onRefreshList,
}: {
  readonly kind: DirectCommandLibraryKind;
  readonly libraryId: string;
  readonly taskId: string;
  readonly token: string | null;
  readonly onRefreshList: () => void;
}) {
  const queryClient = useQueryClient();
  const [controlError, setControlError] = useState<string | null>(null);
  // The *operation snapshot*: one page-independent read of the selected
  // operation that owns its stage, whole-operation counts, effect certainty,
  // next action, Task version and therefore its lifecycle controls.  The
  // backend folds those facts over every admitted item, so any page of this
  // read reports the same aggregate at the same durable state.
  //
  // It polls on its own: a live operation therefore converges here even when
  // the item evidence below was read earlier (and would otherwise keep saying
  // 排队等待 Worker after the real work finished).  Polling is decided by *this*
  // read's own terminal flag, never by a page of item evidence.
  const snapshotQueryKey = useMemo(
    () => ["library-file-operation-snapshot", kind, libraryId, taskId] as const,
    [kind, libraryId, taskId],
  );
  const snapshotQuery = useQuery({
    queryKey: snapshotQueryKey,
    queryFn: async () => {
      const read = await fetchLibraryFileOperationDetail(
        token,
        kind,
        libraryId,
        taskId,
        { limit: 1 },
      );
      // Two reads of one operation can resolve out of order.  A Task that
      // already reported a terminal outcome cannot become unfinished again, and
      // its admitted population cannot shrink, so such an answer is older and
      // must not overwrite the state the operator already saw.  The guard lives
      // in the read itself, so no render path and no control can be fed a
      // regressed snapshot.
      const cached =
        queryClient.getQueryData<
          Awaited<ReturnType<typeof fetchLibraryFileOperationDetail>>
        >(snapshotQueryKey);
      const accepted = cached !== undefined && cached.ok ? cached.model : null;
      if (read.ok && isOlderLibraryOperationSnapshot(accepted, read.model)) {
        return cached as NonNullable<typeof cached>;
      }
      return read;
    },
    enabled: token !== null && libraryId !== "" && taskId !== "",
    retry: false,
    refetchInterval: (query) => {
      const data = query.state.data;
      // Only a still-running operation is polled; a terminal Task is final, so
      // re-reading it forever would only repeat a settled answer.
      if (data !== undefined && data.ok && data.model.terminal) return false;
      return POLL_INTERVAL_MS;
    },
  });
  const detail =
    snapshotQuery.data !== undefined && snapshotQuery.data.ok
      ? snapshotQuery.data.model
      : null;
  // One bounded item page at a time, over the backend's own exact continuation
  // position: a legitimate directory Delete owns one admitted item per child,
  // so the operator must be able to reach every recorded result — including a
  // refused child that settled after the first page — without leaving the
  // local dialog.  Each page is a separate read; loading more never re-runs or
  // replays any operation.  This read does not poll: the snapshot above owns
  // progress, so a background read can never cancel the operator's continuation.
  const itemPages = useInfiniteQuery({
    queryKey: ["library-file-operation-detail", kind, libraryId, taskId],
    queryFn: ({ pageParam }) =>
      fetchLibraryFileOperationDetail(token, kind, libraryId, taskId, {
        limit: ITEM_PAGE_LIMIT,
        cursor: pageParam,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) =>
      last.ok ? (last.model.nextCursor ?? undefined) : undefined,
    enabled: token !== null && libraryId !== "" && taskId !== "",
    retry: false,
  });
  const pages = useMemo(() => itemPages.data?.pages ?? [], [itemPages.data]);
  const firstPage = pages.length > 0 ? pages[0] : undefined;
  const lastPage = pages.length > 0 ? pages[pages.length - 1] : undefined;
  // The pages are consecutive continuations of one operation, so the item list
  // is their exact concatenation; a failed continuation keeps the evidence that
  // was already read.
  const items = useMemo(
    () => pages.flatMap((page) => (page.ok ? page.model.items : [])),
    [pages],
  );
  const lastDetail =
    lastPage !== undefined && lastPage.ok ? lastPage.model : null;
  const lifecycle = detail?.lifecycle ?? null;
  // Read failures are kept apart, and none of them is ever rendered as "nothing
  // happened":
  //
  // * the *snapshot* read owns stage/counts/certainty/controls.  When it fails
  //   while an earlier answer is still on screen, that earlier answer is
  //   disclosed as an older state instead of being silently reused as current.
  // * the *item evidence* read is independent: a failed first page or a failed
  //   continuation keeps the items already read and offers one explicit re-read.
  const snapshotFailureCode = readFailureCodeOf(
    snapshotQuery.isError,
    snapshotQuery.data,
  );
  const evidenceFailureCode = readFailureCodeOf(
    itemPages.isError,
    itemPages.data === undefined ? undefined : firstPage,
  );
  // Nothing readable at all: the operator must see the bounded failure and be
  // able to read the same selected operation again.
  const readFailureCode =
    detail === null ? (snapshotFailureCode ?? evidenceFailureCode) : null;
  const staleSnapshotFailureCode = detail === null ? null : snapshotFailureCode;
  const evidenceReadFailureCode = detail === null ? null : evidenceFailureCode;
  const continuationFailure =
    pages.length > 1 && lastPage !== undefined && !lastPage.ok
      ? lastPage.code
      : null;
  // The operation snapshot and the already-read item evidence are two reads of
  // the same durable operation, taken at different times.  A real Worker run
  // between them leaves the item evidence describing an older state, and a
  // continuation page can equally reveal a newer one.  When they describe
  // different states both are re-read once (each read is guarded against
  // regressing), so an open panel converges without closing or reopening it;
  // after two bounded attempts the disagreement is disclosed instead of
  // re-reading forever.
  const snapshotKey =
    detail === null ? null : libraryOperationSnapshotKey(detail);
  const evidenceKey =
    lastDetail === null ? null : libraryOperationSnapshotKey(lastDetail);
  const evidenceBehind =
    snapshotKey !== null && evidenceKey !== null && snapshotKey !== evidenceKey;
  const refetchItems = itemPages.refetch;
  const refetchSnapshot = snapshotQuery.refetch;
  const coordinated = useRef<{ key: string; attempts: number }>({
    key: "",
    attempts: 0,
  });
  // The left-hand list summarises each operation with the same durable counts.
  // When those facts change (the Worker finished an item, a control settled),
  // the summary is re-read once so the selected row cannot keep advertising an
  // older state than the panel beside it.
  const listedSnapshotKey = useRef<string | null>(null);
  useEffect(() => {
    if (snapshotKey === null) return;
    if (listedSnapshotKey.current === snapshotKey) return;
    listedSnapshotKey.current = snapshotKey;
    onRefreshList();
  }, [snapshotKey, onRefreshList]);
  useEffect(() => {
    if (!evidenceBehind || snapshotKey === null || evidenceKey === null) return;
    const key = `${snapshotKey}|${evidenceKey}`;
    const attempts =
      coordinated.current.key === key ? coordinated.current.attempts : 0;
    if (attempts >= 2) return;
    coordinated.current = { key, attempts: attempts + 1 };
    void refetchSnapshot();
    void refetchItems();
  }, [evidenceBehind, snapshotKey, evidenceKey, refetchSnapshot, refetchItems]);
  const available = useMemo(
    () => (lifecycle?.actions ?? []).filter((item) => item.available),
    [lifecycle],
  );
  const controlMutation = useMutation({
    mutationFn: (request: {
      readonly action: string;
      readonly expectedVersion: string;
    }) =>
      mutateLifecycle(token, {
        objectType: "task",
        objectId: taskId,
        action: request.action as "pause" | "cancel" | "resume",
        expectedVersion: request.expectedVersion,
      }),
    retry: false,
    onMutate: () => setControlError(null),
    onSuccess: (result) => {
      if (!result.ok) {
        setControlError(controlFailureMessage(result.code));
        void snapshotQuery.refetch();
        void itemPages.refetch();
        return;
      }
      // A refused or accepted control never repeats itself: the snapshot read
      // reconciles the durable state (and the evidence behind it) while the
      // page refreshes its live files.
      void snapshotQuery.refetch();
      void itemPages.refetch();
      onRefreshList();
      void queryClient.invalidateQueries({ queryKey: ["storage-files"] });
      void queryClient.invalidateQueries({ queryKey: ["media-library-files"] });
    },
    onError: () => {
      setControlError(controlFailureMessage("transport_unavailable"));
    },
  });

  if (readFailureCode !== null) {
    // A *completed* read that failed is not a read still in progress: the
    // operator must be told what happened and be able to read the same
    // selected operation again.  The selection, the library identity and all
    // durable work stay untouched — this only re-runs a read.
    return (
      <>
        <p className="mf-dialog-error" role="alert">
          {readFailureMessage(readFailureCode)}
        </p>
        <p className="mf-dialog-hint">
          <button
            type="button"
            className="mf-link-button"
            disabled={snapshotQuery.isFetching || itemPages.isFetching}
            onClick={() => {
              void snapshotQuery.refetch();
              void itemPages.refetch();
            }}
          >
            {snapshotQuery.isFetching || itemPages.isFetching
              ? "正在重新读取该操作…"
              : "重新读取该操作"}
          </button>
        </p>
      </>
    );
  }
  if (detail === null) {
    return (
      <p className="mf-dialog-hint" role="status">
        正在读取该操作的持久状态…
      </p>
    );
  }
  // The operation-level facts are the page-independent snapshot: stage, counts,
  // certainty, next action and controls always describe the operation's current
  // durable state, never the item page that happened to be read first.
  const aggregate = detail;
  const uncertain = aggregate.durableState === "mutation_effect_uncertain";
  return (
    <>
      <dl className="mf-operation-facts">
        <div>
          <dt>操作</dt>
          <dd>{detail.operationLabel}</dd>
        </div>
        <div>
          <dt>阶段</dt>
          <dd>{libraryOperationStateLabel(detail)}</dd>
        </div>
        <div>
          <dt>来源</dt>
          <dd>{detail.sourceScope ?? "不可用（未记录来源范围）"}</dd>
        </div>
        <div>
          <dt>目标</dt>
          <dd>
            {detail.targetScope ??
              (detail.operation === "delete"
                ? "无（删除操作没有目标）"
                : "不可用（未记录目标范围）")}
          </dd>
        </div>
        <div>
          <dt>项目结果</dt>
          <dd>
            成功 {aggregate.succeededItems} / 失败 {aggregate.failedItems} /
            跳过 {aggregate.skippedItems} / 取消 {aggregate.cancelledItems} /
            待处理 {aggregate.pendingItems} / 共 {aggregate.totalItems} 项
          </dd>
        </div>
        <div>
          <dt>已记录影响</dt>
          <dd>
            {aggregate.effectCertainty === null
              ? "不可用（未记录影响确定性）"
              : (LIBRARY_OPERATION_CERTAINTY_LABELS[
                  aggregate.effectCertainty
                ] ?? aggregate.effectCertainty)}
          </dd>
        </div>
        <div>
          <dt>配置版本</dt>
          <dd>
            {detail.configurationSnapshotId ?? "不可用（未记录固定版本）"}
          </dd>
        </div>
      </dl>
      {uncertain && (
        <p className="mf-dialog-error" role="alert">
          该操作存在结果不确定的项目；系统不会自动重试。请刷新来源与目标目录核实实际状态后再决定下一步。
        </p>
      )}
      {aggregate.nextAction !== null && (
        <p className="mf-dialog-hint">{aggregate.nextAction}</p>
      )}
      {staleSnapshotFailureCode !== null && (
        <p className="mf-dialog-error" role="alert">
          暂时无法重新读取该操作的当前状态（
          {readFailureLabel(staleSnapshotFailureCode)}
          ）；下方是上一次成功读取的结果，请核对后再决定下一步。
        </p>
      )}
      {evidenceReadFailureCode !== null && (
        <p className="mf-dialog-error" role="alert">
          {readFailureMessage(evidenceReadFailureCode)}
        </p>
      )}
      {items.length > 0 && (
        <div className="mf-operation-items">
          <h5>逐项结果</h5>
          <ul className="mf-operation-item-list">
            {items.map((item) => (
              <ItemEvidence key={item.itemId} item={item} />
            ))}
          </ul>
          <p className="mf-dialog-hint" role="status">
            已显示 {items.length} / {aggregate.itemTotal} 项逐项证据。
          </p>
          {itemPages.hasNextPage && (
            <p className="mf-dialog-hint">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                disabled={itemPages.isFetchingNextPage}
                onClick={() => void itemPages.fetchNextPage()}
              >
                加载更多逐项结果
              </button>
            </p>
          )}
          {!itemPages.hasNextPage && lastDetail?.itemsTruncated === true && (
            <p className="mf-dialog-hint">
              仍有逐项证据未显示；请重新读取该操作以继续。
            </p>
          )}
          {evidenceBehind && !itemPages.isFetching && (
            <p className="mf-dialog-hint" role="status">
              逐项证据仍早于该操作的当前状态；可继续“加载更多”或重新读取逐项结果。
            </p>
          )}
          {(evidenceReadFailureCode !== null ||
            continuationFailure !== null) && (
            <p className="mf-dialog-hint">
              已读取的逐项证据保留在下方；
              <button
                type="button"
                className="mf-link-button"
                disabled={itemPages.isFetching || itemPages.isFetchingNextPage}
                onClick={() =>
                  evidenceReadFailureCode === null
                    ? void itemPages.fetchNextPage()
                    : void itemPages.refetch()
                }
              >
                {evidenceReadFailureCode === null
                  ? "重新读取后续逐项结果"
                  : "重新读取逐项结果"}
              </button>
            </p>
          )}
          {continuationFailure !== null && (
            <p className="mf-dialog-error" role="alert">
              {readFailureMessage(continuationFailure)}
            </p>
          )}
        </div>
      )}
      {items.length === 0 && (
        <p className="mf-dialog-hint">
          该操作尚未记录任何逐项结果；这不代表它已成功。
        </p>
      )}
      {libraryOperationHasProgress(aggregate) && !aggregate.terminal && (
        <p className="mf-dialog-hint" role="status">
          该操作仍在进行；关闭本窗口不会取消或重放它。
        </p>
      )}
      {available.length > 0 ? (
        <div className="mf-actions">
          {available.map((action) => (
            <button
              key={action.action}
              type="button"
              className={
                action.action === "cancel"
                  ? "mf-button mf-button-danger"
                  : "mf-button mf-button-secondary"
              }
              disabled={controlMutation.isPending}
              onClick={() =>
                controlMutation.mutate({
                  action: action.action,
                  expectedVersion: lifecycle?.version ?? aggregate.version,
                })
              }
            >
              {ACTION_LABELS[action.action] ?? action.label}
            </button>
          ))}
        </div>
      ) : (
        <p className="mf-dialog-hint">
          {lifecycle === null
            ? "当前无法读取该操作的控制投影，因此未提供暂停/取消/继续按钮。"
            : "后端未对该操作和当前账号提供任何可用的暂停/取消/继续控制。"}
        </p>
      )}
      {(lifecycle?.actions ?? []).some((action) => !action.available) && (
        <ul className="mf-dialog-hint">
          {(lifecycle?.actions ?? [])
            .filter((action) => !action.available)
            .map((action) => (
              <li key={action.action}>
                {ACTION_LABELS[action.action] ?? action.label}：{" "}
                {action.unavailableReason}
              </li>
            ))}
        </ul>
      )}
      {controlError !== null && (
        <p className="mf-dialog-error" role="alert">
          {controlError}
        </p>
      )}
    </>
  );
}

export function LibraryFileOperationsDialog({
  kind,
  libraryId,
  libraryName,
  initialTaskId = null,
  onClose,
  onSelectOrigin,
}: {
  readonly kind: DirectCommandLibraryKind;
  /**
   * The exact origin this page is inspecting.  It may be a library the current
   * Active configuration no longer enables: the read is durable, so an origin
   * the operator created work in stays inspectable without re-enabling it.
   */
  readonly libraryId: string;
  readonly libraryName: string | null;
  /**
   * The exact operation the page already admitted (from an immediately
   * preceding result dialog).  It is only a *selection hint*: the detail is
   * still read from durable evidence under this library's authority, so a
   * stale or foreign hint simply fails closed.
   */
  readonly initialTaskId?: string | null;
  readonly onClose: () => void;
  /**
   * Select a different durable origin from the bounded index.
   *
   * This never inspects a *live* library; the page passes the exact selected
   * historical library back so the same durable read runs under that origin's
   * own kind/ID authority.  Closing/selecting never admits a command.
   */
  readonly onSelectOrigin?: (libraryId: string) => void;
}) {
  const token = useAuthToken();
  const [cursor, setCursor] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(initialTaskId);
  // The selected operation belongs to one exact library/kind; a change of
  // either drops the selection rather than rebinding it.
  const identity = `${kind}:${libraryId}`;
  const identityRef = useRef(identity);
  useEffect(() => {
    if (identityRef.current !== identity) {
      identityRef.current = identity;
      setSelected(null);
      setCursor(null);
    }
  }, [identity]);

  // The bounded index of origins this kind still owns.  It is what keeps a
  // disabled/removed/unavailable origin reachable: the page's live library list
  // only contains *enabled* libraries, so without this the header entry would
  // silently inspect today's first enabled library instead of the historical
  // scope whose work the operator is looking for.
  const originsQuery = useQuery({
    queryKey: ["library-file-operation-origins", kind],
    queryFn: () => fetchLibraryFileOperationOrigins(token, kind, { limit: 50 }),
    enabled: token !== null,
    retry: false,
  });
  const origins =
    originsQuery.data !== undefined && originsQuery.data.ok
      ? originsQuery.data.model
      : null;
  const currentOriginKnown =
    origins === null ||
    origins.items.length === 0 ||
    origins.items.some((item) => item.libraryId === libraryId);

  const listQuery = useQuery({
    queryKey: ["library-file-operations", kind, libraryId, cursor],
    queryFn: () =>
      fetchLibraryFileOperations(token, {
        kind,
        libraryId,
        limit: PAGE_LIMIT,
        cursor,
      }),
    enabled: token !== null && libraryId !== "",
    retry: false,
  });
  const list =
    listQuery.data !== undefined && listQuery.data.ok
      ? listQuery.data.model
      : null;
  const listFailure =
    listQuery.data !== undefined && !listQuery.data.ok
      ? listQuery.data.code
      : null;
  const entries = useMemo(() => {
    const all = list?.items ?? [];
    const needle = search.trim().toLocaleLowerCase();
    if (needle === "") return all;
    return all.filter((entry) =>
      `${entry.operationLabel} ${entry.commandLabel} ${entry.sourceScope ?? ""} ${
        entry.targetScope ?? ""
      } ${entry.taskId}`
        .toLocaleLowerCase()
        .includes(needle),
    );
  }, [list, search]);
  const selectedEntry =
    entries.find((entry) => entry.taskId === selected) ?? null;
  const title =
    libraryName === null
      ? "当前页面操作状态"
      : `当前页面操作状态 · ${libraryName}`;

  return (
    <ModalDialog
      title={title}
      onClose={onClose}
      wide
      footer={
        <button
          type="button"
          className="mf-button mf-button-primary"
          onClick={onClose}
        >
          关闭
        </button>
      }
    >
      <p className="mf-dialog-hint">
        这里只列出本库中发起的文件操作（新建、重命名、编辑、复制、移动、删除）。
        关闭本窗口不会取消或重放任何操作；刷新或重启后仍可在此找回。
      </p>
      {!currentOriginKnown && (
        <p className="mf-dialog-error" role="alert">
          当前所选库不在现有操作记录中；下方列出的是历史记录里的实际库。
          浏览新的库不会丢弃其它库的记录，也不会改写它们的历史归属。
        </p>
      )}
      {origins !== null &&
        (origins.items.length > 1 || !currentOriginKnown) && (
          <>
            <label className="mf-dialog-field" htmlFor="mf-operation-origin">
              历史操作所属库
            </label>
            <select
              id="mf-operation-origin"
              value={
                origins.items.some((item) => item.libraryId === libraryId)
                  ? libraryId
                  : ""
              }
              onChange={(event) => {
                const next = event.target.value;
                if (next === "" || next === libraryId) return;
                onSelectOrigin?.(next);
              }}
            >
              {!origins.items.some((item) => item.libraryId === libraryId) && (
                <option value="">请选择要查看的历史库（当前库没有记录）</option>
              )}
              {origins.items.map((item) => (
                <option key={item.libraryId} value={item.libraryId}>
                  {item.libraryId}
                </option>
              ))}
            </select>
          </>
        )}
      <label className="mf-dialog-field" htmlFor="mf-operation-search">
        筛选
      </label>
      <input
        id="mf-operation-search"
        type="search"
        value={search}
        placeholder="按操作、路径或任务标识筛选本页记录"
        onChange={(event) => setSearch(event.target.value)}
      />
      {listQuery.isFetching && list === null && (
        <p className="mf-dialog-hint" role="status">
          正在读取本库的文件操作记录…
        </p>
      )}
      {listFailure !== null && (
        <>
          <p className="mf-dialog-error" role="alert">
            {readFailureMessage(listFailure)}
          </p>
          <p className="mf-dialog-hint">
            <button
              type="button"
              className="mf-link-button"
              onClick={() => void listQuery.refetch()}
            >
              重新读取操作记录
            </button>
          </p>
        </>
      )}
      {list !== null && list.total === 0 && (
        <p className="mf-dialog-hint" role="status">
          本库还没有任何文件操作记录。执行一次新建、重命名、编辑、复制、移动或删除后，
          它们的真实结果会出现在这里。
        </p>
      )}
      {list !== null && list.total > 0 && entries.length === 0 && (
        <p className="mf-dialog-hint" role="status">
          当前筛选条件下没有匹配的记录，共 {list.total}{" "}
          条记录；清空筛选即可查看。
        </p>
      )}
      {entries.length > 0 && (
        <ul className="mf-operation-list" aria-label="本库文件操作">
          {entries.map((entry) => (
            <StageList
              key={entry.taskId}
              entry={entry}
              selected={entry.taskId === selected}
              onSelect={() => setSelected(entry.taskId)}
            />
          ))}
        </ul>
      )}
      {list !== null && (
        <div className="mf-operation-pager">
          <button
            type="button"
            className="mf-page-button"
            aria-label="上一页操作"
            disabled={list.previousCursor === null || listQuery.isFetching}
            onClick={() => {
              setSelected(null);
              setCursor(list.previousCursor);
            }}
          >
            ‹
          </button>
          <span className="mf-dashboard-meta">
            共 {list.total} 条记录
            {list.hasNext ? "（还有更早的记录）" : ""}
          </span>
          <button
            type="button"
            className="mf-page-button"
            aria-label="下一页操作"
            disabled={list.nextCursor === null || listQuery.isFetching}
            onClick={() => {
              setSelected(null);
              setCursor(list.nextCursor);
            }}
          >
            ›
          </button>
        </div>
      )}
      {selected !== null && (
        <section className="mf-operation-detail" aria-label="所选操作状态">
          <h4>
            所选操作
            {selectedEntry === null && list !== null
              ? "（不在当前页记录中）"
              : ""}
          </h4>
          <OperationDetail
            kind={kind}
            libraryId={libraryId}
            taskId={selected}
            token={token}
            onRefreshList={() => void listQuery.refetch()}
          />
        </section>
      )}
      {selected === null && entries.length > 0 && (
        <p className="mf-dialog-hint">
          选择上方任一操作即可查看它的阶段、来源、目标、已知影响和可执行的安全控制。
        </p>
      )}
    </ModalDialog>
  );
}
