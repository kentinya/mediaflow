/**
 * The shared Automation definition form card (V2-AUTO-014).
 *
 * Creation and saved-definition editing render exactly these fields, this
 * validation display, the bounded directory browser, the backend upcoming-time
 * preview and the explicit enablement choice. There is no second form model or
 * validator: both entries own an `AutomationCreateForm`, initialize it once
 * (create) or backfill it exactly (edit), and receive every change through one
 * `onPatch` callback. The component starts no work and mutates nothing; the
 * backend command remains the only publication path.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  fetchStorageFiles,
  previewAutomationSchedule,
} from "../../shared/api/api-client";
import type { StorageFilesFailure } from "../../shared/api/api-client";
import type { AutomationDefinitionFormAuthorityModel } from "../../entities/operations/automation-lifecycle";
import { Button } from "../../shared/ui/Button";
import {
  buildCreateCandidate,
  browserTimeZone,
  formatPreviewTime,
  scheduleSummary,
  type AutomationCreateForm,
  type CreateFormIssue,
  type CreateScheduleKind,
  type IntervalUnit,
} from "./automation-create-form";

export type DefinitionFormMode = "create" | "edit";

export type PreviewState =
  | { readonly kind: "idle" }
  | { readonly kind: "loading" }
  | {
      readonly kind: "ready";
      readonly timezone: string | null;
      readonly upcoming: readonly string[];
    }
  | { readonly kind: "error"; readonly code: string };

const WEEKDAYS = [
  ["1", "周一"],
  ["2", "周二"],
  ["3", "周三"],
  ["4", "周四"],
  ["5", "周五"],
  ["6", "周六"],
  ["0", "周日"],
] as const;

export function directoryFailureCopy(failure: StorageFilesFailure): {
  readonly title: string;
  readonly message: string;
} {
  switch (failure.kind) {
    case "storage_unavailable":
      return {
        title: "无法读取此目录",
        message: "存储暂时不可用或读取超时。请恢复连接后重试同一目录。",
      };
    case "configuration_unavailable":
      return {
        title: "当前没有可用的配置",
        message: "请先恢复已生效的运行时配置，再重试读取目录。",
      };
    case "storage_not_found":
    case "resource_library_mismatch":
      return {
        title: "资源库的存储不可用",
        message: "所选资源库没有可读取的存储绑定。请检查资源库配置后重试。",
      };
    case "storage_disabled":
      return {
        title: "存储已停用",
        message: "所选资源库的存储已停用。请先启用存储，再重试。",
      };
    case "invalid_path":
      return {
        title: "目录路径无效",
        message: "请使用资源库内的相对路径，不能以斜杠开头或包含 ..。",
      };
    case "not_found":
      return {
        title: "目录不存在",
        message: "该目录可能已被移动或删除。请返回上级目录重新选择。",
      };
    case "not_directory":
      return {
        title: "所选位置不是目录",
        message: "请返回上级目录并选择可遍历的子目录。",
      };
    case "invalid_cursor":
      return {
        title: "目录列表已过期",
        message: "请重新打开目录浏览，再继续加载。",
      };
    case "resource_library_not_found":
      return {
        title: "资源库不可用",
        message: "所选资源库不存在或已停用。请重新选择资源库。",
      };
    case "rejected":
      return {
        title: "目录读取被拒绝",
        message: "当前身份没有读取该目录的权限。请检查权限后重试。",
      };
  }
}

function DirectoryFailure({
  failure,
}: {
  readonly failure: StorageFilesFailure;
}) {
  const copy = directoryFailureCopy(failure);
  return (
    <div className="mf-automation-create-directory-error" role="alert">
      <strong>{copy.title}</strong>
      <p>{copy.message}</p>
    </div>
  );
}

export interface AutomationDefinitionFormFieldsProps {
  readonly mode: DefinitionFormMode;
  readonly form: AutomationCreateForm;
  readonly authority: AutomationDefinitionFormAuthorityModel;
  readonly issues: readonly CreateFormIssue[];
  readonly showIssues: boolean;
  readonly scheduleRejected: boolean;
  readonly onPatch: (patch: Partial<AutomationCreateForm>) => void;
  readonly onScheduleKind: (kind: CreateScheduleKind) => void;
}

export function AutomationDefinitionFormFields({
  mode,
  form,
  authority,
  issues,
  showIssues,
  scheduleRejected,
  onPatch,
  onScheduleKind,
}: AutomationDefinitionFormFieldsProps) {
  const token = useAuthToken();
  const browserZone = useMemo(() => browserTimeZone(), []);
  const previewGeneration = useRef(0);
  const [browserOpen, setBrowserOpen] = useState(false);
  const [browserPath, setBrowserPath] = useState("");
  const [libraryNotice, setLibraryNotice] = useState<string | null>(null);
  const [previewState, setPreviewState] = useState<{
    readonly key: string;
    readonly value: PreviewState;
  }>({ key: "", value: { kind: "idle" } });

  const formKey = useMemo(
    () =>
      JSON.stringify([
        form.id,
        form.name,
        form.resourceLibraryId,
        form.scopeMode,
        form.sourceScope,
        form.itemLimit,
        form.schedule,
        form.intervalValue,
        form.intervalUnit,
        form.dailyTime,
        form.weeklyDay,
        form.weeklyTime,
        form.cron,
        form.timezone,
        form.enabled,
      ]),
    [form],
  );
  const previewReady = form.name.trim().length > 0 && issues.length === 0;

  // Any candidate change immediately invalidates the displayed result. Only a
  // response produced for the exact current form may replace it, so a late
  // response or a previous ResourceLibrary response can never overwrite newer
  // state.
  const preview: PreviewState =
    previewState.key === formKey ? previewState.value : { kind: "idle" };

  useEffect(() => {
    const generation = ++previewGeneration.current;
    if (!previewReady) {
      return;
    }
    const timer = window.setTimeout(() => {
      if (previewGeneration.current !== generation) return;
      const candidate = buildCreateCandidate(form);
      if (candidate === null) {
        setPreviewState({
          key: formKey,
          value: { kind: "error", code: "invalid_candidate" },
        });
        return;
      }
      setPreviewState({ key: formKey, value: { kind: "loading" } });
      void previewAutomationSchedule(token, {
        candidate,
        objectId: mode === "edit" ? form.id : null,
      }).then((result) => {
        if (previewGeneration.current !== generation || !previewReady) {
          return;
        }
        if (result.ok) {
          setPreviewState({
            key: formKey,
            value: {
              kind: "ready",
              timezone: result.model.timezone,
              upcoming: result.model.upcoming,
            },
          });
        } else {
          setPreviewState({
            key: formKey,
            value: { kind: "error", code: result.code },
          });
        }
      });
    }, 400);
    return () => window.clearTimeout(timer);
  }, [form, formKey, previewReady, token, mode]);

  const directoryQuery = useInfiniteQuery({
    queryKey: [
      "operations.automation-create-directory",
      form.resourceLibraryId,
      browserPath,
    ],
    queryFn: ({ pageParam }) =>
      fetchStorageFiles(token, {
        resourceLibraryId: form.resourceLibraryId,
        path: browserPath,
        cursor: pageParam,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) =>
      lastPage.ok && lastPage.model.hasNext ? lastPage.model.nextCursor : null,
    enabled: token !== null && browserOpen && form.resourceLibraryId.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const directoryPages = directoryQuery.data?.pages ?? [];
  const directoryModel =
    directoryPages.length > 0 && directoryPages[0].ok
      ? directoryPages[0].model
      : null;
  const directoryFailure =
    directoryPages
      .map((page) => (page.ok ? null : page.failure))
      .find((failure): failure is StorageFilesFailure => failure !== null) ??
    null;
  const directoryEntries = directoryPages.flatMap((page) =>
    page.ok ? page.model.entries.filter((entry) => entry.isDirectory) : [],
  );

  // The enablement choice's real availability comes from the backend's
  // principal projection, never from browser state. Creation publishes
  // enabled only through the command's explicit choice; editing enables the
  // saved definition through the same checked publication and needs the
  // scheduled execution permission. Disabling an already-enabled definition
  // stays available.
  const enablementBlocked =
    mode === "create"
      ? !authority.actions.createEnabled
      : !form.enabled && !authority.actions.enable;
  const enablementReason = enablementBlocked
    ? mode === "create"
      ? (authority.actionReasons?.createEnabled ?? null)
      : (authority.actionReasons?.enable ?? null)
    : null;

  function updateFields(patch: Partial<AutomationCreateForm>) {
    onPatch(patch);
  }

  function changeLibrary(value: string) {
    onPatch({
      resourceLibraryId: value,
      scopeMode: "root",
      sourceScope: "",
    });
    setBrowserPath("");
    setBrowserOpen(false);
    setLibraryNotice(
      "已切换资源库；原资源子目录已清空，来源范围现在为整个资源库。",
    );
  }

  function openDirectoryBrowser() {
    if (form.resourceLibraryId.length === 0) {
      setLibraryNotice("请先选择资源库，再浏览其中的子目录。");
      return;
    }
    setLibraryNotice(null);
    setBrowserPath(form.sourceScope.trim());
    setBrowserOpen(true);
  }

  function chooseDirectory(path: string) {
    onPatch({
      scopeMode: path === "" ? "root" : "subdirectory",
      sourceScope: path,
    });
    setBrowserOpen(false);
    setLibraryNotice(null);
  }

  const previewMissing = issues
    .slice(0, 3)
    .map((issue) => issue.label)
    .filter((label, index, labels) => labels.indexOf(label) === index);

  const issueFor = (fieldId: string) =>
    showIssues && issues.some((issue) => issue.fieldId === fieldId);

  return (
    <>
      <section
        className="mf-automation-create-section"
        aria-labelledby="automation-create-basic"
      >
        <h3 id="automation-create-basic">基本信息与来源</h3>
        <div className="mf-automation-create-grid">
          <div className="mf-automation-create-field mf-automation-create-field-full">
            <label htmlFor="automation-create-name">
              任务名称 <span aria-hidden="true">*</span>
            </label>
            <input
              id="automation-create-name"
              type="text"
              value={form.name}
              maxLength={authority.limits.name}
              autoComplete="off"
              aria-required="true"
              aria-invalid={issueFor("automation-create-name")}
              aria-describedby={
                issueFor("automation-create-name")
                  ? "automation-create-name-error"
                  : undefined
              }
              onChange={(event) => updateFields({ name: event.target.value })}
            />
            <p className="mf-automation-create-hint">
              用于在任务列表中识别这次自动整理。
            </p>
            {showIssues &&
              issues
                .filter((issue) => issue.fieldId === "automation-create-name")
                .map((issue) => (
                  <p
                    className="mf-automation-create-field-error"
                    id="automation-create-name-error"
                    key={issue.message}
                  >
                    {issue.message}
                  </p>
                ))}
          </div>

          <div className="mf-automation-create-field">
            <label htmlFor="automation-create-library">
              资源库 <span aria-hidden="true">*</span>
            </label>
            <select
              id="automation-create-library"
              value={form.resourceLibraryId}
              aria-required="true"
              aria-invalid={issueFor("automation-create-library")}
              onChange={(event) => changeLibrary(event.target.value)}
            >
              <option value="">请选择资源库</option>
              {authority.resourceLibraries.map((option) => (
                <option
                  key={option.id}
                  value={option.id}
                  disabled={!option.enabled}
                >
                  {option.name ?? option.id}
                  {option.enabled ? "" : "（已停用）"}
                </option>
              ))}
            </select>
            {showIssues &&
              issues
                .filter(
                  (issue) => issue.fieldId === "automation-create-library",
                )
                .map((issue) => (
                  <p
                    className="mf-automation-create-field-error"
                    key={issue.message}
                  >
                    {issue.message}
                  </p>
                ))}
          </div>

          <div className="mf-automation-create-field">
            <label htmlFor="automation-create-scope-mode">来源范围</label>
            <select
              id="automation-create-scope-mode"
              value={form.scopeMode}
              onChange={(event) =>
                updateFields({
                  scopeMode:
                    event.target.value === "subdirectory"
                      ? "subdirectory"
                      : "root",
                  sourceScope:
                    event.target.value === "root" ? "" : form.sourceScope,
                })
              }
            >
              <option value="root">整个资源库</option>
              <option value="subdirectory">指定子目录</option>
            </select>
            <p className="mf-automation-create-hint">
              {form.scopeMode === "root"
                ? "扫描此资源库的整个已保存范围。"
                : "只扫描选定的资源库内子目录。"}
            </p>
          </div>

          {libraryNotice !== null && (
            <p className="mf-automation-create-notice mf-automation-create-field-full">
              {libraryNotice}
            </p>
          )}

          {form.scopeMode === "subdirectory" && (
            <div className="mf-automation-create-field mf-automation-create-field-full">
              <label htmlFor="automation-create-scope">来源子目录</label>
              <div className="mf-automation-create-inline">
                <input
                  id="automation-create-scope"
                  type="text"
                  value={form.sourceScope}
                  placeholder="例如：电影/华语"
                  aria-required="true"
                  aria-invalid={issueFor("automation-create-scope")}
                  onChange={(event) =>
                    updateFields({ sourceScope: event.target.value })
                  }
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={openDirectoryBrowser}
                >
                  浏览目录
                </Button>
              </div>
              <p className="mf-automation-create-hint">
                也可以直接输入资源库内的相对路径；不能以斜杠开头或包含 ..。
              </p>
              {showIssues &&
                issues
                  .filter(
                    (issue) => issue.fieldId === "automation-create-scope",
                  )
                  .map((issue) => (
                    <p
                      className="mf-automation-create-field-error"
                      key={issue.message}
                    >
                      {issue.message}
                    </p>
                  ))}
            </div>
          )}

          {browserOpen && form.scopeMode === "subdirectory" && (
            <div className="mf-automation-create-directory mf-automation-create-field-full">
              <div className="mf-automation-create-directory-head">
                <strong>选择来源子目录</strong>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setBrowserOpen(false)}
                >
                  收起目录
                </Button>
              </div>
              {directoryModel !== null && (
                <nav
                  className="mf-automation-create-breadcrumbs"
                  aria-label="目录位置"
                >
                  {directoryModel.breadcrumbs.map((crumb) => (
                    <button
                      key={crumb.path}
                      type="button"
                      onClick={() => setBrowserPath(crumb.path)}
                    >
                      {crumb.isRoot ? "资源库根目录" : crumb.name}
                    </button>
                  ))}
                </nav>
              )}
              <p className="mf-automation-create-hint">
                当前目录：
                {browserPath === "" ? "资源库根目录" : browserPath}
              </p>
              {directoryQuery.isPending && (
                <p className="mf-automation-create-hint" role="status">
                  正在读取此目录…
                </p>
              )}
              {directoryFailure !== null && (
                <>
                  <DirectoryFailure failure={directoryFailure} />
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      void directoryQuery.refetch();
                    }}
                    disabled={directoryQuery.isFetching}
                  >
                    重试读取此目录
                  </Button>
                </>
              )}
              {directoryFailure === null && !directoryQuery.isPending && (
                <>
                  {directoryEntries.length === 0 ? (
                    <p className="mf-automation-create-hint">
                      此目录没有可遍历的子目录。仍可选择当前目录。
                    </p>
                  ) : (
                    <ul className="mf-automation-create-directory-list">
                      {directoryEntries.map((entry) => (
                        <li key={entry.path}>
                          <span>
                            {entry.name}
                            {entry.isSymlink ? "（符号链接）" : ""}
                          </span>
                          {entry.traversable ? (
                            <span className="mf-automation-create-directory-actions">
                              <Button
                                type="button"
                                variant="secondary"
                                onClick={() => setBrowserPath(entry.path)}
                              >
                                进入
                              </Button>
                              <Button
                                type="button"
                                onClick={() => chooseDirectory(entry.path)}
                              >
                                选择此目录
                              </Button>
                            </span>
                          ) : (
                            <span className="mf-automation-create-hint">
                              不可遍历
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {directoryQuery.hasNextPage && (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={directoryQuery.isFetchingNextPage}
                      onClick={() => {
                        void directoryQuery.fetchNextPage();
                      }}
                    >
                      {directoryQuery.isFetchingNextPage
                        ? "加载中…"
                        : "加载更多目录"}
                    </Button>
                  )}
                </>
              )}
              <div className="mf-actions">
                <Button type="button" onClick={() => chooseDirectory("")}>
                  选择资源库根目录
                </Button>
                {browserPath !== "" && (
                  <Button
                    type="button"
                    onClick={() => chooseDirectory(browserPath)}
                  >
                    选择当前目录
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      <section
        className="mf-automation-create-section"
        id="automation-create-schedule-section"
        aria-labelledby="automation-create-schedule"
      >
        <h3 id="automation-create-schedule">运行时间</h3>
        {scheduleRejected && (
          <div className="mf-automation-create-schedule-error" role="alert">
            <strong>后端拒绝了当前时间计划</strong>
            <p>
              请检查下面“执行频率”对应的 Cron 表达式与 IANA
              时区；输入已保留，修正后可再次明确提交。
            </p>
          </div>
        )}
        <div className="mf-automation-create-grid">
          <div className="mf-automation-create-field">
            <label htmlFor="automation-create-schedule-kind">执行频率</label>
            <select
              id="automation-create-schedule-kind"
              value={form.schedule}
              onChange={(event) =>
                onScheduleKind(event.target.value as CreateScheduleKind)
              }
            >
              <option value="interval">每隔一段时间</option>
              <option value="daily">每天固定时间</option>
              <option value="weekly">每周固定时间</option>
              <option value="cron">高级 Cron</option>
            </select>
          </div>

          {form.schedule === "interval" && (
            <div className="mf-automation-create-field">
              <label htmlFor="automation-create-interval">执行间隔</label>
              <div className="mf-automation-create-inline">
                <input
                  id="automation-create-interval"
                  type="text"
                  inputMode="decimal"
                  value={form.intervalValue}
                  aria-required="true"
                  aria-invalid={issueFor("automation-create-interval")}
                  onChange={(event) =>
                    updateFields({ intervalValue: event.target.value })
                  }
                />
                <select
                  aria-label="间隔单位"
                  value={form.intervalUnit}
                  onChange={(event) =>
                    updateFields({
                      intervalUnit: event.target.value as IntervalUnit,
                    })
                  }
                >
                  <option value="seconds">秒</option>
                  <option value="minutes">分钟</option>
                  <option value="hours">小时</option>
                </select>
              </div>
              <p className="mf-automation-create-hint">
                {mode === "edit"
                  ? "支持小数，例如 1.5 秒；保存的值按秒提交，原值不会被打散或改写。"
                  : "默认每隔 1 小时；支持小数，例如 1.5 小时会转换为 5400 秒。"}
              </p>
              {showIssues &&
                issues
                  .filter(
                    (issue) => issue.fieldId === "automation-create-interval",
                  )
                  .map((issue) => (
                    <p
                      className="mf-automation-create-field-error"
                      key={issue.message}
                    >
                      {issue.message}
                    </p>
                  ))}
            </div>
          )}

          {form.schedule === "daily" && (
            <div className="mf-automation-create-field">
              <label htmlFor="automation-create-daily-time">每天运行时间</label>
              <input
                id="automation-create-daily-time"
                type="time"
                value={form.dailyTime}
                aria-required="true"
                onChange={(event) =>
                  updateFields({ dailyTime: event.target.value })
                }
              />
              {showIssues &&
                issues
                  .filter(
                    (issue) => issue.fieldId === "automation-create-daily-time",
                  )
                  .map((issue) => (
                    <p
                      className="mf-automation-create-field-error"
                      key={issue.message}
                    >
                      {issue.message}
                    </p>
                  ))}
            </div>
          )}

          {form.schedule === "weekly" && (
            <>
              <div className="mf-automation-create-field">
                <label htmlFor="automation-create-weekly-day">每周星期</label>
                <select
                  id="automation-create-weekly-day"
                  value={form.weeklyDay}
                  onChange={(event) =>
                    updateFields({ weeklyDay: event.target.value })
                  }
                >
                  {WEEKDAYS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="mf-automation-create-field">
                <label htmlFor="automation-create-weekly-time">运行时间</label>
                <input
                  id="automation-create-weekly-time"
                  type="time"
                  value={form.weeklyTime}
                  onChange={(event) =>
                    updateFields({ weeklyTime: event.target.value })
                  }
                />
                {showIssues &&
                  issues
                    .filter(
                      (issue) =>
                        issue.fieldId === "automation-create-weekly-time",
                    )
                    .map((issue) => (
                      <p
                        className="mf-automation-create-field-error"
                        key={issue.message}
                      >
                        {issue.message}
                      </p>
                    ))}
              </div>
            </>
          )}

          {form.schedule === "cron" && (
            <div className="mf-automation-create-field mf-automation-create-field-full">
              <label htmlFor="automation-create-cron">Cron 表达式</label>
              <input
                id="automation-create-cron"
                type="text"
                value={form.cron}
                placeholder="0 8 * * *"
                aria-required="true"
                aria-invalid={
                  scheduleRejected || issueFor("automation-create-cron")
                }
                aria-describedby="automation-create-cron-error"
                onChange={(event) => updateFields({ cron: event.target.value })}
              />
              <p className="mf-automation-create-hint">
                使用后端支持的五段
                Cron；这里只检查格式与取值范围，不会自行改写或计算实际触发时间。
              </p>
              {showIssues &&
                issues
                  .filter((issue) => issue.fieldId === "automation-create-cron")
                  .map((issue) => (
                    <p
                      className="mf-automation-create-field-error"
                      id="automation-create-cron-error"
                      key={issue.message}
                    >
                      {issue.message}
                    </p>
                  ))}
            </div>
          )}

          {form.schedule !== "interval" && (
            <div className="mf-automation-create-field">
              <label htmlFor="automation-create-timezone">时区</label>
              <input
                id="automation-create-timezone"
                type="text"
                value={form.timezone}
                placeholder="Asia/Shanghai"
                aria-required="true"
                onChange={(event) =>
                  updateFields({ timezone: event.target.value })
                }
              />
              <p className="mf-automation-create-hint">
                {browserZone.recognized
                  ? `已预填本机时区；可改为其他 IANA 时区。`
                  : "无法识别本机时区，已明确使用 UTC；可填写其他 IANA 时区。"}
              </p>
              {showIssues &&
                issues
                  .filter(
                    (issue) => issue.fieldId === "automation-create-timezone",
                  )
                  .map((issue) => (
                    <p
                      className="mf-automation-create-field-error"
                      key={issue.message}
                    >
                      {issue.message}
                    </p>
                  ))}
            </div>
          )}

          <div className="mf-automation-create-preview mf-automation-create-field-full">
            <p className="mf-automation-create-summary">
              {scheduleSummary(form)}
            </p>
            {!previewReady && (
              <p className="mf-automation-create-hint">
                填写
                {previewMissing.length > 0
                  ? `「${previewMissing.join("、")}」`
                  : "完整信息"}
                后，会按后端规则自动计算即将运行的时间。
              </p>
            )}
            {previewReady && preview.kind === "idle" && (
              <p className="mf-automation-create-hint" role="status">
                正在准备时间预览…
              </p>
            )}
            {preview.kind === "loading" && (
              <p className="mf-automation-create-hint" role="status">
                正在按后端规则计算即将运行的时间…
              </p>
            )}
            {preview.kind === "error" && (
              <p className="mf-automation-create-hint" role="status">
                预览未完成（{preview.code}
                ）；这不阻止提交，提交仍由后端校验。
              </p>
            )}
            {preview.kind === "ready" && (
              <>
                <p className="mf-automation-create-hint">
                  {preview.timezone === null
                    ? `按浏览器本地时区（${browserZone.timeZone}）显示`
                    : `按所选时区 ${preview.timezone} 显示`}
                </p>
                {preview.upcoming.length === 0 ? (
                  <p className="mf-automation-create-hint">
                    后端没有返回即将运行的时间；提交后请核对配置。
                  </p>
                ) : (
                  <ul className="mf-automation-create-upcoming">
                    {preview.upcoming.map((value) => (
                      <li key={value}>
                        {formatPreviewTime(value, preview.timezone)}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
            <p className="mf-automation-create-note">
              {form.enabled
                ? "时间计划将在保存并启用后生效；启用本身不启动任务，也不会立即运行。"
                : "时间计划仅在启用后生效；当前为停用状态，不会自动运行。"}
            </p>
          </div>
        </div>
      </section>

      <section
        className="mf-automation-create-section"
        aria-labelledby="automation-create-limits"
      >
        <h3 id="automation-create-limits">处理限制与启用状态</h3>
        <div className="mf-automation-create-grid">
          <div className="mf-automation-create-field">
            <label htmlFor="automation-create-limit">处理上限</label>
            <input
              id="automation-create-limit"
              type="text"
              inputMode="numeric"
              value={form.itemLimit}
              aria-required="true"
              aria-invalid={issueFor("automation-create-limit")}
              onChange={(event) =>
                updateFields({ itemLimit: event.target.value })
              }
            />
            <p className="mf-automation-create-hint">
              限制单次来源范围最多处理的数量（
              {authority.limits.itemLimitMinimum}–
              {authority.limits.itemLimitMaximum}
              ）。超过上限时需要缩小来源范围；系统不会自动分批，也不会只处理前 N
              个。
            </p>
            {showIssues &&
              issues
                .filter((issue) => issue.fieldId === "automation-create-limit")
                .map((issue) => (
                  <p
                    className="mf-automation-create-field-error"
                    key={issue.message}
                  >
                    {issue.message}
                  </p>
                ))}
          </div>
          <div className="mf-automation-create-field">
            <span className="mf-automation-create-label">启用自动化任务</span>
            <label
              className="mf-automation-create-toggle"
              htmlFor="automation-create-enabled"
            >
              <input
                id="automation-create-enabled"
                type="checkbox"
                role="switch"
                checked={form.enabled}
                disabled={enablementBlocked}
                onChange={(event) =>
                  updateFields({ enabled: event.target.checked })
                }
              />
              <span className="mf-automation-create-toggle-text">
                启用定时计划
              </span>
            </label>
            <p className="mf-automation-create-hint">
              {mode === "create"
                ? form.enabled
                  ? "保存时将同时启用：创建成功后立即按保存的计划定时运行。"
                  : "默认停用。创建后可在任务列表或编辑中随时启用。"
                : form.enabled
                  ? "保存后定义保持启用，按计划定时运行。"
                  : "保存后定义保持停用，不产生定时运行。"}
            </p>
            {enablementReason !== null && (
              <p className="mf-automation-create-field-error" role="alert">
                {enablementReason}
              </p>
            )}
          </div>
        </div>
      </section>
    </>
  );
}
