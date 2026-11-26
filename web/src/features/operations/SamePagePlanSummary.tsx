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
import {
  ItemFindings,
  OrganizeHistoryReminder,
  displayEnum,
  safeValue,
} from "./organize-summary";
import { TaskRefreshControl as RefreshControl } from "./TaskRefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import type { ManualPreviewItemModel } from "../../entities/operations/preview";

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
  /**
   * Task Center recovery renders the same exact selection in the approved
   * compact source/target rows; the Files and paused-run surfaces keep the
   * reviewed full findings.
   */
  readonly compact?: boolean;
  readonly confirmationPhase?: "submitting" | "admitted";
  /** Operator-facing confirm verb, defaulting to the recovery copy. */
  readonly confirmLabel?: (count: number) => string;
  /**
   * Whether this component renders its own confirm button.  The bounded batch
   * journey aggregates several independent summaries under one explicit
   * confirmation, so it renders the reviewed facts and selection here while
   * the parent owns the single aggregate confirm action.
   */
  readonly showConfirm?: boolean;
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
  const compact = props.compact === true;
  const confirmationPhase = props.confirmationPhase;
  const fileNameOf = (item: ManualPreviewItemModel): string =>
    item.sourceFilename ?? item.itemId;
  const sourceEffect = (item: ManualPreviewItemModel): string => {
    const effects: string[] = [];
    switch (item.operation) {
      case "MOVE":
        effects.push("成功后原位置移除");
        break;
      case "COPY":
      case "LINK":
        effects.push("原文件保留");
        break;
      case "NOOP":
      case "SKIP":
        effects.push("不执行文件操作");
        break;
      default:
        effects.push("来源影响见精确方案");
        break;
    }
    if (item.destructiveImplications?.overwriteRequired) {
      effects.push("确认时需覆盖授权");
    }
    if (item.destructiveImplications?.sourceCleanupRequired) {
      effects.push("确认时需来源清理授权");
    }
    return effects.join(" · ");
  };
  return (
    <section
      className={compact ? "mf-recovery-plan" : "mf-count-section"}
      aria-label="新计划摘要"
    >
      <div className={compact ? "mf-recovery-plan-head" : "mf-run-items-head"}>
        <h6>{props.heading}</h6>
        {compact ? (
          preview?.current &&
          executableIds.length > 0 && (
            <span>
              {confirmationPhase === "admitted"
                ? "已受理"
                : confirmationPhase === "submitting"
                  ? "提交中"
                  : "等待明确确认"}
            </span>
          )
        ) : (
          <RefreshControl
            onRefresh={() => previewQuery.refetch({ cancelRefetch: false })}
          />
        )}
      </div>
      {previewQuery.data === undefined ? (
        <StatusBanner variant="info" title="正在读取计划摘要">
          <p>只读取已保存的零变更计划，不会创建任务或修改存储。</p>
        </StatusBanner>
      ) : previewQuery.data.ok !== true ? (
        <StatusBanner variant="warning" title={previewQuery.data.failure.title}>
          <p>{previewQuery.data.failure.nextAction}</p>
          {compact && previewQuery.data.failure.kind === "unavailable" && (
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={previewQuery.isFetching}
              onClick={() =>
                void previewQuery.refetch({ cancelRefetch: false })
              }
            >
              重新读取计划
            </button>
          )}
        </StatusBanner>
      ) : preview === undefined ? null : compact ? (
        <>
          {preview.current && executableIds.length > 0 ? (
            <StatusBanner variant="success" title="方案已更新">
              <p>
                {preview.items
                  .filter((item) => executableIds.includes(item.itemId))
                  .map(fileNameOf)
                  .join("、")}{" "}
                已生成可确认的新方案。
                {confirmationPhase === "admitted"
                  ? "整理已受理。"
                  : confirmationPhase === "submitting"
                    ? "正在提交。"
                    : "整理尚未提交。"}
              </p>
            </StatusBanner>
          ) : !preview.current ? (
            <StatusBanner variant="warning" title="当前方案已失效">
              <p>{preview.nextAction ?? "请核对原条目的当前状态。"}</p>
            </StatusBanner>
          ) : executableIds.length === 0 ? (
            <StatusBanner variant="warning" title="当前方案没有可确认文件">
              <p>
                {preview.nextAction ??
                  "按当前方案逐项核对原因，处理后再生成新的精确方案。"}
              </p>
            </StatusBanner>
          ) : null}
          <OrganizeHistoryReminder items={preview.items} />
          <div className="mf-recovery-plan-head">
            <h6>来源与目标</h6>
            <span>按当前方案</span>
          </div>
          <ul className="mf-recovery-plan-list" aria-label="可确认文件">
            {preview.items.map((item) => {
              const isExecutable = executableIds.includes(item.itemId);
              const target =
                item.targetPath ??
                item.destination?.relativePath ??
                item.destination?.storageRelativePath ??
                null;
              return (
                <li
                  className={
                    isExecutable
                      ? "mf-recovery-plan-row"
                      : "mf-recovery-plan-row mf-recovery-plan-row-blocked"
                  }
                  key={item.itemId}
                >
                  <label className="mf-recovery-plan-choice">
                    <input
                      type="checkbox"
                      aria-label={`选择 ${fileNameOf(item)}`}
                      checked={activeSelection.includes(item.itemId)}
                      disabled={!preview.current || !isExecutable || props.busy}
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
                  </label>
                  <div className="mf-recovery-plan-copy">
                    <p className="mf-recovery-plan-name">{fileNameOf(item)}</p>
                    <p>
                      <span className="mf-recovery-plan-label">来源</span>
                      <span className="mf-exact-identity">
                        {safeValue(item.sourcePath)}
                      </span>
                    </p>
                    <p>
                      <span className="mf-recovery-plan-label">目标</span>
                      <span className="mf-exact-identity">
                        {target === null ? "—" : target}
                      </span>
                    </p>
                    <p className="mf-recovery-plan-effect">
                      {isExecutable
                        ? sourceEffect(item)
                        : `不可执行 · ${
                            item.nextAction ?? displayEnum(item.status)
                          }`}
                      {item.attachments.length > 0
                        ? ` · 附件 ${item.attachments.length} 个`
                        : ""}
                    </p>
                  </div>
                  <span
                    className={`mf-recovery-plan-operation${item.operation === "MOVE" ? " mf-recovery-plan-operation-move" : ""}`}
                  >
                    {displayEnum(safeValue(item.operation))}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      ) : (
        <>
          <p className="mf-dashboard-meta">
            计划 {preview.previewId} · {displayEnum(preview.status)} ·{" "}
            {preview.current ? "当前" : "历史"} · 不会修改 Storage
          </p>
          {preview.nextAction && (
            <p className="mf-dashboard-meta">{preview.nextAction}</p>
          )}
          <OrganizeHistoryReminder items={preview.items} />
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
        </>
      )}
      {requiresOverwrite && (
        <label className={compact ? "mf-recovery-plan-consent" : undefined}>
          <input
            type="checkbox"
            checked={props.allowOverwrite}
            disabled={props.busy || (compact && !preview?.current)}
            onChange={(event) => props.onAllowOverwrite(event.target.checked)}
          />
          {compact
            ? `按已审阅的方案替换 ${
                preview?.items.filter(
                  (item) =>
                    activeSelection.includes(item.itemId) &&
                    item.destructiveImplications?.overwriteRequired === true,
                ).length ?? 0
              } 个已有目标`
            : "我确认允许按此精确摘要替换现有目标文件"}
        </label>
      )}
      {requiresCleanup && (
        <label className={compact ? "mf-recovery-plan-consent" : undefined}>
          <input
            type="checkbox"
            checked={props.allowCleanup}
            disabled={props.busy || (compact && !preview?.current)}
            onChange={(event) => props.onAllowCleanup(event.target.checked)}
          />
          {compact
            ? "允许清理整理后为空的来源目录"
            : "我确认允许删除整理后为空的来源目录"}
        </label>
      )}
      {compact && preview?.current && !destructiveConfirmed && !props.busy && (
        <p className="mf-dashboard-meta">
          勾选上方对应的授权后，才能提交这份方案。
        </p>
      )}
      <div className="mf-actions">
        {props.showConfirm === false ? (
          <p className="mf-dashboard-meta">
            已选 {activeSelection.length} 项；请在下方统一确认所选就绪项。
          </p>
        ) : (
          <button
            type="button"
            className="mf-button"
            disabled={
              props.busy ||
              (compact && !preview?.current) ||
              activeSelection.length === 0 ||
              !destructiveConfirmed
            }
            onClick={props.onConfirm}
          >
            {props.busy
              ? compact
                ? confirmationPhase === "admitted"
                  ? "正在读取结果…"
                  : "正在提交…"
                : "正在受理…"
              : confirmLabel(activeSelection.length)}
          </button>
        )}
      </div>
      {!compact && (
        <p className="mf-dashboard-meta">
          确认只会准入所选就绪子集；未选项保留自己的准备状态，不会被自动执行。
        </p>
      )}
    </section>
  );
}
