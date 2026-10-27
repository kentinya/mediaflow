/**
 * The closed legacy V2 Task/Job entry points (Slice46 RO-4 / B46.4-04).
 *
 * Before the center contraction these two routes were an independent mixed
 * administrative collection: they read `/api/v1/tasks` and `/api/v1/jobs`
 * directly, so an ordinary Files/MediaLibrary command (for example a directory
 * create) kept appearing in what looked like the Task Center's list. The Task
 * Center is now the single organizing surface, and the ordinary work it must
 * not list already owns its own library-local history.
 *
 * Every visit is therefore closed without guessing and without executing
 * anything:
 *
 * - an **admitted organizing** identity redirects to the exact Task Center
 *   context (`/operations?run=…`), so the operator lands on the same durable
 *   run the center lists, with its own filters, view and detail tabs;
 * - an **ordinary** Task identity resolves its proven persistent origin and
 *   redirects to that exact kind/library/source on the local Files page, where
 *   the existing "当前页面操作状态" shows the real work;
 * - anything else (missing, retired, unsupported, denied, unreadable context)
 *   remains one bounded read-only explanation with no command, no library guess
 *   and no generic failure recovery.
 *
 * None of these routes submits a command, retries a failed step, replays an
 * execution or filters a page client-side. They only resolve an identity that
 * the backend already decided, and they reuse the shared authorized read
 * boundary so 401/403/read-error keep their normal meaning.
 */

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearch,
} from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  fetchLibraryFileOperationOrigin,
  fetchRunOverview,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import {
  OPERATIONS_RETURN_KEY,
  operationsReturnContextFromSearch,
} from "../../shared/navigation/operations-return";

/** The bounded next action shown when the identity cannot be resolved. */
const UNAVAILABLE_COPY: Readonly<Record<string, string>> = {
  not_found:
    "该记录不存在，或不属于当前账号可读的任务中心整理总体。没有提交任何命令。",
  forbidden: "当前账号无权查看该记录。没有提交任何命令。",
  unavailable:
    "无法联系服务端确认该记录的归属。没有提交任何命令；请恢复连接后重新打开。",
  rejected: "服务端拒绝了这次只读归属查询。没有提交任何命令。",
  malformed:
    "服务端返回的归属信息无法确认。没有提交任何命令，也不会猜测来源库。",
};

function unavailableCopy(code: string | null): string {
  if (code === null) {
    return "正在确认该记录的归属；确认前不会提交任何命令。";
  }
  return (
    UNAVAILABLE_COPY[code] ??
    "无法确认该记录的归属。没有提交任何命令，也不会猜测来源库或恢复旧流程。"
  );
}

/**
 * Carry the list context a legacy deep link may still hold into the center
 * URL, so an old bookmark keeps the filters the operator originally submitted.
 */
function legacyListContext(search: Record<string, unknown>): string | null {
  const status = typeof search["status"] === "string" ? search["status"] : "";
  const command =
    typeof search["command"] === "string" ? search["command"] : "";
  if (status === "" && command === "") return null;
  return operationsReturnContextFromSearch({
    q_status: status,
    q_command: command,
  });
}

/** One bounded, read-only explanation for an unresolvable legacy identity. */
function LegacyUnavailable({
  title,
  code,
  onRefresh,
  refreshing,
}: {
  readonly title: string;
  readonly code: string | null;
  readonly onRefresh: () => void;
  readonly refreshing: boolean;
}) {
  return (
    <StatusBanner variant="warning" title={title}>
      <p>{unavailableCopy(code)}</p>
      <div className="mf-actions">
        <Link className="mf-button mf-button-primary" to="/operations">
          打开任务中心
        </Link>
        <Link className="mf-button mf-button-secondary" to="/resourcelib/files">
          打开资源库文件页
        </Link>
        <Link className="mf-button mf-button-secondary" to="/medialib/files">
          打开媒体库文件页
        </Link>
        <RefreshControl onRefresh={onRefresh} refreshing={refreshing} />
      </div>
    </StatusBanner>
  );
}

/**
 * The shared read state of one legacy identity.
 *
 * The bounded GETs answer honestly:
 *
 * - `/api/v1/operations/runs/{id}` answers only for Task Center organizing
 *   work (a 404 is the bounded non-match, not a failure);
 * - `/api/v1/files/operation-origin/{id}` answers only for proven ordinary
 *   library work.
 *
 * `settled` becomes true only when both reads finished, so the redirect never
 * fires from a partial view. The result is a plain data value, so the shared
 * authorized boundary owns the 401/403/read-error contract exactly as it does
 * for every other Operations page: a rejected identity is an explicit
 * authorization state, never an empty success.
 */
type LegacyResolution =
  | { readonly kind: "organizing"; readonly runId: string }
  | {
      readonly kind: "ordinary";
      readonly libraryKind: "media" | "resource";
      readonly libraryId: string;
      readonly path: string | null;
      readonly taskId: string;
    }
  | { readonly kind: "unavailable" };

/** One only-reads resolver behind the shared authorized read boundary. */
function LegacyResolutionBoundary({
  identity,
  title,
}: {
  readonly identity: string;
  readonly title: string;
}) {
  const token = useAuthToken();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const listContext = legacyListContext(searchParams);
  const query = useQuery({
    queryKey: ["legacy-identity", identity],
    queryFn: async (): Promise<LegacyResolution> => {
      const run = await fetchRunOverview(token, identity);
      if (run.ok) {
        return { kind: "organizing", runId: run.model.runId };
      }
      const origin = await fetchLibraryFileOperationOrigin(token, identity);
      if (origin.ok && origin.model.matched) {
        return {
          kind: "ordinary",
          libraryKind: origin.model.libraryKind,
          libraryId: origin.model.libraryId,
          path: origin.model.path,
          taskId: origin.model.taskId,
        };
      }
      return { kind: "unavailable" };
    },
    enabled: token !== null && identity.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: 10_000,
  });
  return (
    <AuthorizedReadBoundary query={query} unavailableTitle="该记录暂时无法读取">
      {({ refresh, isFetching }) => {
        if (identity.length === 0) {
          return (
            <LegacyUnavailable
              title={title}
              code="not_found"
              onRefresh={refresh}
              refreshing={isFetching}
            />
          );
        }
        return (
          <ResolvedLegacyIdentity
            title={title}
            listContext={listContext}
            resolution={query.data ?? null}
            onRefresh={refresh}
            refreshing={isFetching}
          />
        );
      }}
    </AuthorizedReadBoundary>
  );
}

/**
 * The settled redirect / bounded unavailable state of one identity.
 *
 * A settled organizing/ordinary identity is painted as one bounded "opening its
 * own durable context" state while the router navigation commits, so no effect
 * ever calls setState: the redirect itself is the only side effect, and a
 * missing identity keeps the read-only explanation.
 */
function ResolvedLegacyIdentity({
  title,
  listContext,
  resolution,
  onRefresh,
  refreshing,
}: {
  readonly title: string;
  readonly listContext: string | null;
  readonly resolution: LegacyResolution | null;
  readonly onRefresh: () => void;
  readonly refreshing: boolean;
}) {
  const navigate = useNavigate();

  useEffect(() => {
    if (resolution === null) return;
    if (resolution.kind === "organizing") {
      void navigate({
        to: "/operations",
        search: {
          run: resolution.runId,
          ...(listContext === null
            ? {}
            : { [OPERATIONS_RETURN_KEY]: listContext }),
        },
        replace: true,
      });
      return;
    }
    if (resolution.kind === "ordinary") {
      void navigate({
        to:
          resolution.libraryKind === "media"
            ? "/medialib/files"
            : "/resourcelib/files",
        search: {
          ...(resolution.libraryId === ""
            ? {}
            : resolution.libraryKind === "media"
              ? { mediaLibraryId: resolution.libraryId }
              : { resourceLibraryId: resolution.libraryId }),
          ...(resolution.path === null ? {} : { path: resolution.path }),
          operationTaskId: resolution.taskId,
        },
        replace: true,
      });
    }
  }, [listContext, navigate, resolution]);

  if (resolution === null) {
    return (
      <StatusBanner variant="info" title={title}>
        <p>{unavailableCopy(null)}</p>
        <div className="mf-actions">
          <RefreshControl onRefresh={onRefresh} refreshing={refreshing} />
        </div>
      </StatusBanner>
    );
  }
  if (resolution.kind !== "unavailable") {
    return (
      <StatusBanner variant="info" title={title}>
        <p>
          已确认该记录的归属，正在打开它自己的持久上下文；不会提交任何命令。
        </p>
      </StatusBanner>
    );
  }
  return (
    <LegacyUnavailable
      title={title}
      code="not_found"
      onRefresh={onRefresh}
      refreshing={refreshing}
    />
  );
}

/** The closed `/operations/tasks` entry: no second, mixed Task collection. */
export function LegacyTaskListPage() {
  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <h2>任务中心</h2>
      </header>
      <StatusBanner variant="info" title="任务列表已并入任务中心">
        <p>
          旧的 Task
          列表会同时显示普通文件维护等非整理工作，因此已不再提供独立列表；
          任务中心只列出已受理的整理工作及其合法续作，普通文件操作在它自己的库文件页查看。
          这里没有自动提交、重试或跳转到通用失败恢复。
        </p>
        <div className="mf-actions">
          <Link className="mf-button mf-button-primary" to="/operations">
            打开任务中心
          </Link>
          <Link
            className="mf-button mf-button-secondary"
            to="/resourcelib/files"
          >
            打开资源库文件页
          </Link>
          <Link className="mf-button mf-button-secondary" to="/medialib/files">
            打开媒体库文件页
          </Link>
        </div>
      </StatusBanner>
    </div>
  );
}

/** The closed `/operations/jobs` entry: same rule, admission-shaped records. */
export function LegacyJobListPage() {
  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <h2>任务中心</h2>
      </header>
      <StatusBanner variant="info" title="Job 列表已并入任务中心">
        <p>
          旧的 Job
          列表会同时显示普通文件维护等非整理工作，因此已不再提供独立列表；
          同一个整理工作仍按真实关联在任务中心去重显示，排队中或尚未生成 Task
          的整理
          记录也仍可在“全部任务”中查看。这里没有自动提交、重试或跳转到通用失败恢复。
        </p>
        <div className="mf-actions">
          <Link className="mf-button mf-button-primary" to="/operations">
            打开任务中心
          </Link>
          <Link
            className="mf-button mf-button-secondary"
            to="/resourcelib/files"
          >
            打开资源库文件页
          </Link>
          <Link className="mf-button mf-button-secondary" to="/medialib/files">
            打开媒体库文件页
          </Link>
        </div>
      </StatusBanner>
    </div>
  );
}

/** The closed `/operations/tasks/$taskId` deep link. */
export function LegacyTaskDetailPage() {
  const { taskId } = useParams({ strict: false }) as { taskId: string };
  return (
    <LegacyResolutionBoundary
      identity={taskId}
      title="正在确认该 Task 的归属"
    />
  );
}

/** The closed `/operations/jobs/$jobId` deep link. */
export function LegacyJobDetailPage() {
  const { jobId } = useParams({ strict: false }) as { jobId: string };
  return (
    <LegacyResolutionBoundary identity={jobId} title="正在确认该 Job 的归属" />
  );
}
