/**
 * `新建整理任务` — the native bounded live-file Organize entry (Slice 42 RO-4).
 *
 * The task center links here with the exact ResourceLibrary scope it was
 * showing (when one was chosen) plus its preserved list context. The page
 * offers only backend-advertised facts: the enabled ResourceLibrary choices
 * from the bounded manual-action matrix, re-read at each explicitly chosen
 * scope so availability, permission and the library's own state come from the
 * same authority the rest of the workspace uses. Choosing a library enters the
 * existing Files live-selection authority — this page never lists files
 * itself, never creates an intent, never admits work and never mutates.
 *
 * A deleted or unknown direct scope never silently becomes another library's
 * scope: it is stated and the remaining enabled choices stay available. A
 * missing permission, unavailable library, unready runtime or missing Active
 * configuration explains its named prerequisite instead of pretending the
 * journey can continue. The preserved Operations return context rides along
 * into Files so the whole journey can come back to the same task-center view.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import { manualActionsQueryOptions } from "./manual-actions-query";
import {
  operationsLandingSearch,
  operationsReturnSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";

/** The bounded direct-scope grammar a new-task URL may carry. */
const LIBRARY_ID_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;

export function OrganizeNewPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const requestedLibraryId =
    typeof searchParams["resourceLibraryId"] === "string" &&
    LIBRARY_ID_TOKEN.test(searchParams["resourceLibraryId"])
      ? searchParams["resourceLibraryId"]
      : "";
  const operationsReturn = readOperationsReturnContext(searchParams);
  // An operator-selected library replaces the URL scope; the URL scope only
  // preselects, so a deleted direct scope degrades to an explicit choice.
  const [chosenLibraryId, setChosenLibraryId] = useState("");
  const effectiveLibraryId =
    chosenLibraryId !== "" ? chosenLibraryId : requestedLibraryId;

  const discoveryQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind: null,
      fileId: null,
      resourceLibraryId: null,
    }),
  );
  // The chosen scope is re-read from the same bounded matrix: availability,
  // permission and the library's own state are backend facts, never a
  // frontend guess, and the discovery projection alone cannot prove them.
  const scopedQuery = useQuery(
    manualActionsQueryOptions(
      token,
      {
        scopeKind: "resourceLibrary",
        fileId: null,
        resourceLibraryId: effectiveLibraryId,
      },
      effectiveLibraryId !== "",
    ),
  );

  const discovery =
    discoveryQuery.data?.ok === true ? discoveryQuery.data.model : undefined;
  const scoped =
    scopedQuery.data?.ok === true ? scopedQuery.data.model : undefined;

  const startWith = (libraryId: string) => {
    void navigate({
      to: "/resourcelib/files",
      search: {
        resourceLibraryId: libraryId,
        organize: "1",
        ...operationsReturnSearch(operationsReturn),
      },
    });
  };

  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <div>
          <h2>新建整理任务</h2>
          <p className="mf-dashboard-meta">
            从资源库中选择当前存在的媒体文件,系统将生成零变更的精确预览;
            只有在预览上明确确认后才会执行整理。本页不会自行枚举文件或创建任务。
          </p>
        </div>
        <RefreshControl
          onRefresh={() => {
            void discoveryQuery.refetch();
            if (effectiveLibraryId !== "") void scopedQuery.refetch();
          }}
          refreshing={discoveryQuery.isFetching || scopedQuery.isFetching}
        />
      </header>
      <AuthorizedReadBoundary
        query={discoveryQuery}
        unavailableTitle="整理入口暂不可用"
      >
        {() => {
          if (discovery === undefined) {
            return (
              <StatusBanner variant="info" title="正在读取整理可用性">
                <p>正在读取当前配置、资源库与处理 Worker 状态。</p>
              </StatusBanner>
            );
          }
          const choices = discovery.resourceLibraries;
          const enabled = choices.filter((choice) => choice.enabled);
          // Discovery is not a permission statement: it only means no scope
          // was chosen yet, and the enabled choices above are the honest
          // scope selector. A refusal of the discovery projection *itself*
          // (an unavailable runtime, a missing permission for the whole
          // action family) is the backend's exact named prerequisite.
          const discoveryRefusal =
            !discovery.selectionRequired &&
            !discovery.actions.organize.available
              ? discovery.actions.organize
              : null;
          if (discoveryRefusal !== null) {
            return (
              <StatusBanner variant="warning" title="暂不能新建整理任务">
                <p>
                  {discoveryRefusal.reason ??
                    "后端未公告可执行的整理操作,当前状态没有创建任何工作。"}
                </p>
                {discoveryRefusal.nextAction && (
                  <p className="mf-dashboard-meta">
                    {discoveryRefusal.nextAction}
                  </p>
                )}
                <div className="mf-actions">
                  <Link
                    className="mf-button"
                    to="/operations"
                    search={operationsLandingSearch(operationsReturn, null)}
                  >
                    返回操作与任务
                  </Link>
                </div>
              </StatusBanner>
            );
          }
          if (enabled.length === 0) {
            return (
              <StatusBanner variant="warning" title="没有可用的资源库">
                <p>
                  当前配置没有启用的资源库作为整理来源;媒体库只作为整理目标,
                  不会成为新的整理来源。本页没有创建任何工作。
                </p>
                {!discovery.runtime.ready && discovery.runtime.nextAction && (
                  <p className="mf-dashboard-meta">
                    {discovery.runtime.nextAction}
                  </p>
                )}
                <div className="mf-actions">
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/configuration"
                  >
                    前往设置补充资源库
                  </Link>
                </div>
              </StatusBanner>
            );
          }
          const requestedKnown =
            requestedLibraryId !== "" &&
            choices.some(
              (choice) => choice.resourceLibraryId === requestedLibraryId,
            );
          const requestedEnabled =
            requestedKnown &&
            choices.some(
              (choice) =>
                choice.resourceLibraryId === requestedLibraryId &&
                choice.enabled,
            );
          return (
            <>
              {requestedLibraryId !== "" && !requestedKnown && (
                <StatusBanner variant="warning" title="所选资源库不可用">
                  <p>
                    请求中的资源库范围不在当前可用配置内。本页没有选择任何库,
                    也没有创建任何工作;请从下方可用资源库中重新选择。
                  </p>
                </StatusBanner>
              )}
              {requestedLibraryId !== "" &&
                requestedKnown &&
                !requestedEnabled && (
                  <StatusBanner variant="warning" title="所选资源库未启用">
                    <p>
                      “{requestedLibraryId}”当前未启用。请从下方可用资源库中重新
                      选择;本页没有创建任何工作。
                    </p>
                  </StatusBanner>
                )}
              <section className="mf-count-section" aria-label="选择资源库">
                <h3>选择资源库</h3>
                <p className="mf-dashboard-meta">
                  整理来源是资源库中的实际文件;文件浏览、可整理资格与单次上限
                  由后端权威给出。
                </p>
                <div
                  className="mf-run-filter-bar"
                  role="radiogroup"
                  aria-label="可整理的资源库"
                >
                  {enabled.map((choice) => (
                    <label key={choice.resourceLibraryId}>
                      <input
                        type="radio"
                        name="organize-source-library"
                        value={choice.resourceLibraryId}
                        checked={
                          choice.resourceLibraryId === effectiveLibraryId
                        }
                        onChange={(event) =>
                          setChosenLibraryId(event.target.value)
                        }
                      />{" "}
                      {choice.resourceLibraryId}
                    </label>
                  ))}
                  {choices
                    .filter((choice) => !choice.enabled)
                    .map((choice) => (
                      <span
                        className="mf-dashboard-meta"
                        key={`disabled-${choice.resourceLibraryId}`}
                      >
                        {choice.resourceLibraryId}(未启用
                        {choice.reason ? `:${choice.reason}` : ""})
                      </span>
                    ))}
                </div>
                <div className="mf-actions">
                  {effectiveLibraryId === "" ? (
                    <span className="mf-dashboard-meta">
                      请先选择一个资源库;未选择时本页不创建任何工作。
                    </span>
                  ) : scoped === undefined ? (
                    <span className="mf-dashboard-meta">
                      {scopedQuery.isError || scopedQuery.data?.ok === false
                        ? "该范围的可用性暂时无法读取;未确认前不能开始选择文件。"
                        : "正在读取该范围的整理可用性…"}
                    </span>
                  ) : scoped.actions.organize.available ? (
                    <Button
                      type="button"
                      onClick={() => startWith(effectiveLibraryId)}
                    >
                      选择文件并开始整理
                    </Button>
                  ) : (
                    <span
                      className="mf-dashboard-meta"
                      role="status"
                      data-testid="organize-scope-refusal"
                    >
                      {scoped.actions.organize.reason ??
                        "后端未在该范围公告可执行的整理操作"}
                      {scoped.actions.organize.nextAction
                        ? `;${scoped.actions.organize.nextAction}`
                        : ""}
                    </span>
                  )}
                </div>
              </section>
            </>
          );
        }}
      </AuthorizedReadBoundary>
      <nav className="mf-actions" aria-label="整理入口返回">
        <Link
          className="mf-button mf-button-secondary"
          to="/operations"
          search={operationsLandingSearch(operationsReturn, null)}
        >
          返回操作与任务
        </Link>
      </nav>
    </div>
  );
}
