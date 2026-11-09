/**
 * Receiving route for one exact prepared Organize work (`/operations/organize/new`).
 *
 * Slice53 RO-3 (`V2-OPS-019`): the Task Center's existing `继续整理` and
 * `查看只读摘要` links still address this stable Organize URL.  The route now
 * mounts the same per-file `ManualOrganizeDialog` the Files page uses, so a
 * continuation or a read-only deep link reopens the exact preparation instead
 * of the retired full creation workspace.
 *
 * The route owns no new admission, choice or execution authority.  It consumes
 * only the bounded preparation identity, the ResourceLibrary identity and the
 * preserved return context from its own URL; opening it is a read of the
 * durable preparation.  Closing returns to that exact context (the selected
 * Task Center run, the exact Files directory, or the ordinary Files entry when
 * the deep link carries no origin); a proved execution admission hands the
 * exact returned Task to the Task Center's existing selected-run/detail route.
 *
 * A generic creation URL keeps the existing guidance state: ResourceLibrary
 * Files is the only normal new-work entry, and visiting this address starts no
 * read and no work.
 */

import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { Button } from "../../shared/ui/Button";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { ManualOrganizeDialog } from "./ManualOrganizeDialog";
import { readFilesReturnContext } from "../../shared/navigation/files-return";
import {
  operationsLandingSearch,
  operationsReturnSearch,
  readOperationsReturnContext,
} from "../../shared/navigation/operations-return";

/** The bounded identity grammar the preparation and library links carry. */
const BOUNDED_ID_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;
const LIBRARY_ID_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;

export function OrganizeCreationPage() {
  const navigate = useNavigate();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const discoveryId =
    typeof searchParams["discoveryId"] === "string" &&
    BOUNDED_ID_TOKEN.test(searchParams["discoveryId"])
      ? searchParams["discoveryId"]
      : "";
  const resourceLibraryId =
    typeof searchParams["resourceLibraryId"] === "string" &&
    LIBRARY_ID_TOKEN.test(searchParams["resourceLibraryId"])
      ? searchParams["resourceLibraryId"]
      : "";
  const filesReturn = readFilesReturnContext(searchParams);
  const operationsReturn = readOperationsReturnContext(searchParams);

  /** Close returns to the exact origin; it never cancels the admitted work. */
  const closeDialog = () => {
    if (operationsReturn !== null) {
      void navigate({
        to: "/operations",
        search: operationsLandingSearch(operationsReturn, null),
      });
      return;
    }
    if (filesReturn !== null) {
      void navigate({
        to: "/resourcelib/files",
        search: {
          resourceLibraryId: filesReturn.resourceLibraryId,
          ...(filesReturn.path === "" ? {} : { path: filesReturn.path }),
          organize: "1",
        },
      });
      return;
    }
    void navigate({
      to: "/resourcelib/files",
      search: {
        ...(resourceLibraryId === "" ? {} : { resourceLibraryId }),
        organize: "1",
      },
    });
  };

  /** The one proved admission uses the Task Center's exact selected run. */
  const handoffToTaskCenter = (taskId: string) => {
    void navigate({
      to: "/operations",
      search: operationsLandingSearch(operationsReturn, taskId),
    });
  };

  // ---- generic creation URL: guide to Files, start nothing -----------------
  if (discoveryId === "") {
    return (
      <div className="mf-dashboard">
        <header className="mf-dashboard-head">
          <div>
            <h2>从资源库文件页开始整理</h2>
            <p className="mf-dashboard-meta">
              整理志愿只能在资源库文件页中明确选定实际存在的文件或文件夹后提交；
              本页没有选库入口，也不会因为访问页面而创建任何工作。
            </p>
          </div>
        </header>
        <StatusBanner variant="info" title="请在资源库文件页选择要整理的文件">
          <p>
            打开资源库文件页，进入目标目录，选择文件或文件夹后使用“整理”提交。
            提交后可在同一页的逐文件弹窗中复核并确认要执行的就绪项。
          </p>
          <div className="mf-actions">
            <Button
              type="button"
              onClick={() =>
                void navigate({
                  to: "/resourcelib/files",
                  search: {
                    ...(resourceLibraryId === "" ? {} : { resourceLibraryId }),
                    ...operationsReturnSearch(operationsReturn),
                  },
                })
              }
            >
              前往资源库文件页
            </Button>
            <Link
              className="mf-button mf-button-secondary"
              to="/operations"
              search={operationsLandingSearch(operationsReturn, null)}
            >
              返回任务中心
            </Link>
          </div>
        </StatusBanner>
      </div>
    );
  }

  // ---- exact prepared work: the same Files per-file dialog -----------------
  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <div>
          <h2>整理所选文件</h2>
          <p className="mf-dashboard-meta">
            {resourceLibraryId === ""
              ? "正在打开本次整理准备"
              : `来源资源库：${resourceLibraryId}`}
          </p>
        </div>
      </header>
      <StatusBanner variant="info" title="逐文件整理准备">
        <p>
          本次整理准备只读取原耐久记录；打开此页不会重新提交准入、重新分析或执行任何文件。
          关闭后会回到发起本次整理的准确上下文。
        </p>
      </StatusBanner>
      <ManualOrganizeDialog
        session={{ phase: "admitted", discoveryId }}
        onClose={closeDialog}
        onHandoff={handoffToTaskCenter}
      />
    </div>
  );
}

export default OrganizeCreationPage;
