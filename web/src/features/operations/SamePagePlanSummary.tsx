/**
 * Shared same-page plan summary for the native recovery journeys (Slice 45 RO-3).
 *
 * One durable, zero-mutation exact Preview is rendered with the reviewed
 * source -> target plan, attachment steps, conflicts and destructive
 * implications the backend advertised.  The operator selects a ready subset
 * and the caller confirms it.  This component decides nothing about authority:
 * it renders only the backend's own candidate list and never invents an
 * executable item.
 *
 * It is used by the per-item recovery panel and by the paused-run remaining
 * scope continuation, so both journeys show exactly the same facts.
 */

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { organizePreviewQueryOptions } from "./organize-query";
import { ItemFindings, displayEnum } from "./organize-summary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";

export interface SamePagePlanSummaryProps {
  readonly token: string | null;
  readonly previewId: string;
  readonly selected: readonly string[] | null;
  readonly onSelected: (value: readonly string[]) => void;
  readonly allowOverwrite: boolean;
  readonly onAllowOverwrite: (value: boolean) => void;
  readonly allowCleanup: boolean;
  readonly onAllowCleanup: (value: boolean) => void;
  readonly busy: boolean;
  readonly onConfirm: () => void;
  /** Operator-facing heading, so each journey names its own scope. */
  readonly heading: string;
  /** Operator-facing confirm verb, defaulting to the recovery copy. */
  readonly confirmLabel?: (count: number) => string;
}

export function SamePagePlanSummary(props: SamePagePlanSummaryProps) {
  const previewQuery = useQuery(
    organizePreviewQueryOptions(props.token, props.previewId),
  );
  const preview =
    previewQuery.data?.ok === true ? previewQuery.data.model : undefined;
  const executableIds = useMemo(
    () =>
      preview
        ? ([...preview.executionCandidateItemIds] as readonly string[])
        : [],
    [preview],
  );
  const selected = props.selected ?? executableIds;
  const activeSelection = executableIds.filter((id) => selected.includes(id));
  // The default confirmation set is the ready subset the backend advertised;
  // surface it to the caller so its Confirm action binds the exact same items.
  useEffect(() => {
    if (props.selected === null && executableIds.length > 0) {
      props.onSelected([...executableIds]);
    }
  }, [props, executableIds]);
  const requiresOverwrite =
    (preview?.items ?? []).some(
      (item) =>
        activeSelection.includes(item.itemId) &&
        item.destructiveImplications?.overwriteRequired === true,
    ) ?? false;
  const requiresCleanup =
    (preview?.items ?? []).some(
      (item) =>
        activeSelection.includes(item.itemId) &&
        item.destructiveImplications?.sourceCleanupRequired === true,
    ) ?? false;
  const destructiveConfirmed =
    (!requiresOverwrite || props.allowOverwrite) &&
    (!requiresCleanup || props.allowCleanup);
  const confirmLabel =
    props.confirmLabel ?? ((count: number) => `确认继续整理 ${count} 项`);
  return (
    <section className="mf-count-section" aria-label="新计划摘要">
      <div className="mf-run-items-head">
        <h6>{props.heading}</h6>
        <RefreshControl
          onRefresh={() => void previewQuery.refetch()}
          refreshing={previewQuery.isFetching}
        />
      </div>
      {previewQuery.data === undefined ? (
        <StatusBanner variant="info" title="正在读取计划摘要">
          <p>只读取已保存的零变更计划，不会创建任务或修改存储。</p>
        </StatusBanner>
      ) : previewQuery.data.ok !== true ? (
        <StatusBanner variant="warning" title={previewQuery.data.failure.title}>
          <p>{previewQuery.data.failure.nextAction}</p>
        </StatusBanner>
      ) : preview === undefined ? null : (
        <>
          <p className="mf-dashboard-meta">
            预览 {preview.previewId} · {displayEnum(preview.status)} ·{" "}
            {preview.current ? "当前" : "历史"} · 不会修改 Storage
          </p>
          {preview.nextAction && (
            <p className="mf-dashboard-meta">{preview.nextAction}</p>
          )}
          {preview.items.map((item) => {
            const isExecutable = executableIds.includes(item.itemId);
            return (
              <div className="mf-count-section" key={item.itemId}>
                <label className="mf-list-choice">
                  <input
                    type="checkbox"
                    aria-label={`选择 ${item.sourceFilename ?? item.itemId}`}
                    checked={activeSelection.includes(item.itemId)}
                    disabled={!isExecutable || props.busy}
                    onChange={(event) =>
                      props.onSelected(
                        event.target.checked
                          ? [...activeSelection, item.itemId]
                          : activeSelection.filter(
                              (value) => value !== item.itemId,
                            ),
                      )
                    }
                  />
                  {item.sourceFilename ?? item.itemId}
                  {isExecutable ? "" : "（不可执行）"}
                </label>
                <ItemFindings item={item} />
              </div>
            );
          })}
          {requiresOverwrite && (
            <label>
              <input
                type="checkbox"
                checked={props.allowOverwrite}
                disabled={props.busy}
                onChange={(event) =>
                  props.onAllowOverwrite(event.target.checked)
                }
              />
              我确认允许按此精确摘要替换现有目标文件
            </label>
          )}
          {requiresCleanup && (
            <label>
              <input
                type="checkbox"
                checked={props.allowCleanup}
                disabled={props.busy}
                onChange={(event) => props.onAllowCleanup(event.target.checked)}
              />
              我确认允许删除整理后为空的来源目录
            </label>
          )}
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button"
              disabled={
                props.busy ||
                activeSelection.length === 0 ||
                !destructiveConfirmed
              }
              onClick={props.onConfirm}
            >
              {props.busy ? "正在受理…" : confirmLabel(activeSelection.length)}
            </button>
          </div>
          <p className="mf-dashboard-meta">
            确认只会准入所选就绪子集；未选项保留自己的准备状态，不会被自动执行。
          </p>
        </>
      )}
    </section>
  );
}
