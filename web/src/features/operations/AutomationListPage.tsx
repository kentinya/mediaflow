/**
 * V2 Automation workspace — reference-aligned inventory.
 *
 * Two sibling tabs share one shell: `任务列表` (the bounded definition
 * inventory) and `执行记录` (read-only admitted-run records). The three shared
 * runtime settings live in System Settings; an old `?tab=settings` link is
 * redirected there without publishing or admitting work. Every number and row
 * comes from a backend read; nothing is filtered, aggregated or authorized in
 * the browser.
 *
 * The submitted tab, filters, sort, time window and server page cursor live in
 * the route search, so a reload, a reconnect and a return from a definition or
 * Task Center link re-read the same population instead of resetting to a local
 * default.
 *
 * Reading never creates a Draft, a Job, a Task, a grant or a Storage/Provider
 * effect, and no record row offers a recovery command: after a durable formal
 * organizing Task exists, Task Center owns execution recovery.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import {
  AUTOMATION_RETURN_KEY,
  automationReturnSearch,
  readAutomationReturnContext,
} from "../../shared/navigation/automation-return";
import { useAuthGeneration, useAuthToken } from "../../shared/api/auth-context";
import { authStore } from "../../shared/api/auth-store";
import {
  admitAutomationRunOnce,
  reconcileAutomationRunOnce,
} from "../../shared/api/api-client";
import { usePrincipalIdentity } from "./principal-identity-query";
import {
  beginRunOnceSubmission,
  clearRunOnceIntent,
  readRunOnceSession,
  type PendingRunOnceIntent,
} from "./automation-run-once-session";
import {
  automationListQueryKey,
  automationListQueryOptions,
  automationRecordsQueryOptions,
} from "./automation-query";
import {
  AUTOMATION_TABS,
  AUTOMATION_TAB_LABELS,
  AutomationDefinitionRow,
  AutomationMetricCards,
  AutomationRecordRow,
  type AutomationTab,
} from "./AutomationInventory";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { AutomationCreateDialog } from "./AutomationCreateDialog";
import type {
  AutomationDefinitionDocumentModel,
  AutomationDefinitionModel,
  AutomationLatestRunModel,
  AutomationRecordModel,
} from "../../entities/operations/automation";

/** Bounded definition sort options the backend accepts. */
const SORT_OPTIONS = [
  ["name", "名称"],
  ["enabled", "启用状态"],
  ["nextRun", "下次运行"],
  ["latest", "最近结果"],
  ["limit", "单次上限"],
] as const;

const RECORD_STATUS_OPTIONS = [
  ["", "全部结果"],
  // Slice 48 RO-4: the outcome is the Task flow status — "已完成" says the
  // flow ended, never that every file succeeded; a cancellation is its own
  // flow outcome in the records.
  ["completed", "已完成"],
  ["failed", "失败"],
  ["cancelled", "已取消"],
  ["running", "进行中"],
  ["pending", "等待执行"],
  ["paused", "已暂停"],
  ["waiting", "等待中"],
  ["unknown", "状态未知"],
] as const;

const RECORD_TRIGGER_OPTIONS = [
  ["", "全部触发方式"],
  ["scheduled", "定时触发"],
  ["manual", "手动运行一次"],
] as const;

const DEFINITIONS_STATE_OPTIONS = [
  ["", "全部状态"],
  ["active", "已生效"],
  ["draft-only", "仅草稿"],
] as const;

/** The bounded weekday-free date/time input values the backend accepts (UTC). */
const RECORD_TIME_TOKEN = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$/;

function tabFromSearch(value: unknown): AutomationTab {
  return typeof value === "string" &&
    (AUTOMATION_TABS as readonly string[]).includes(value)
    ? (value as AutomationTab)
    : "definitions";
}

/** One route search value that only ever carries a safe, bounded string. */
function searchText(
  searchParams: Record<string, unknown>,
  key: string,
): string {
  const value = searchParams[key];
  return typeof value === "string" ? value : "";
}

/**
 * Normalize a date/datetime input into the UTC instant the records API accepts.
 *
 * The operator's browser `datetime-local` value has no timezone; it is read as
 * UTC (the metric calendar is the *system* timezone, separately published) so
 * the submitted window is unambiguous and the backend's UTC-only grammar is
 * satisfied. An out-of-grammar value is not submitted at all.
 */
function utcBoundary(value: string): string | null {
  const trimmed = value.trim();
  if (trimmed === "" || !RECORD_TIME_TOKEN.test(trimmed)) {
    return null;
  }
  const normalized = trimmed.includes("T") ? trimmed : `${trimmed}T00:00`;
  const withSeconds =
    normalized.length === 16 ? `${normalized}:00` : normalized;
  return `${withSeconds}+00:00`;
}

/** The list search keys a create dialog may preserve on open/close. */
const LIST_SEARCH_KEYS = [
  "tab",
  "q",
  "enabled",
  "state",
  "library",
  "sort",
  "cursor",
  "dir",
  "rstatus",
  "rtrigger",
  "rdefinition",
  "rfrom",
  "rto",
] as const;

/**
 * Values that describe the ordinary list even when they are written into the
 * URL. The create link publishes them explicitly while the operator may have
 * arrived from a URL that omitted them, so both forms must identify the same
 * list for scroll restoration.
 */
const DEFAULT_LIST_SEARCH: Readonly<Record<string, string>> = {
  tab: "definitions",
  sort: "name",
  dir: "next",
};

/**
 * The browser keeps the list DOM while the create route is open, but the
 * route transition remounts the list component. This bounded module memory
 * restores the operator's own scroll position and exact return search after
 * the re-read; it stores no form, token or draft.
 */
let automationListScrollMemory: {
  readonly key: string;
  readonly y: number;
  readonly search: Record<string, string>;
} | null = null;
let focusCreateEntryOnNextList = false;

/** The last create success this browser completed, across the close remount. */
let automationCreatedDefinitionMemory: {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly createdAt: number;
} | null = null;

function listSearchKey(searchParams: Record<string, unknown>): string {
  return JSON.stringify(
    Object.entries(searchParams)
      .filter(
        ([key, value]) =>
          (LIST_SEARCH_KEYS as readonly string[]).includes(key) &&
          typeof value === "string" &&
          value !== "" &&
          DEFAULT_LIST_SEARCH[key] !== value,
      )
      .sort(([left], [right]) => left.localeCompare(right)),
  );
}

function listSearchForClose(
  searchParams: Record<string, unknown>,
): Record<string, string> {
  const search: Record<string, string> = {};
  for (const key of LIST_SEARCH_KEYS) {
    const value = searchParams[key];
    if (typeof value === "string" && value !== "") search[key] = value;
  }
  return search;
}

type RunOnceFeedback =
  | { readonly state: "submitting" }
  | { readonly state: "checking" }
  | { readonly state: "admitted"; readonly taskId: string }
  | {
      readonly state: "rejected";
      readonly reason: string;
      readonly nextAction: string;
    }
  | {
      readonly state: "pending";
      readonly detail: string;
      readonly note: string | null;
    };

interface RejectedRunOnceCopy {
  readonly reason: string;
  readonly nextAction: string;
}

/**
 * A bounded operator explanation for a proved Run-once refusal.
 *
 * Backend error codes and raw exception text are diagnostic only. The list
 * tells the operator which stage refused the command, that no run was admitted
 * by this submission, and the one safe next action. A changed definition is
 * always followed by a fresh read; it is never retried with a new snapshot
 * silently bound in place of the one the operator saw.
 */
function rejectedRunOnceCopy(
  status: number,
  code: string | null,
): RejectedRunOnceCopy {
  if (code === "definition_changed") {
    return {
      reason: "保存的任务或配置已更新，本次提交未受理。",
      nextAction: "列表已刷新；请确认最新保存内容后再运行一次。",
    };
  }
  if (code === "queue_full") {
    return {
      reason: "当前整理任务已满，本次提交未受理。",
      nextAction: "等待正在运行的任务结束后再试，或稍后刷新列表。",
    };
  }
  if (
    code === "scope_root_invalid" ||
    code === "resource_library_unavailable"
  ) {
    return {
      reason: "保存的来源范围或资源库当前不可用，本次提交未受理。",
      nextAction: "先在编辑页修正来源范围或资源库并保存，再运行一次。",
    };
  }
  if (status === 401) {
    return {
      reason: "登录身份已失效，本次提交未受理。",
      nextAction: "重新连接后确认列表内容，再运行一次。",
    };
  }
  if (status === 403) {
    return {
      reason: "当前身份没有运行一次的权限，本次提交未受理。",
      nextAction: "请使用具备手动整理权限的身份，或请管理员调整权限。",
    };
  }
  if (status === 404) {
    return {
      reason: "这个任务在当前保存配置中已不存在，本次提交未受理。",
      nextAction: "刷新列表，确认任务仍然存在后再运行。",
    };
  }
  if (status === 503) {
    return {
      reason: "运行一次服务暂时不可用，本次提交未受理。",
      nextAction: "稍后刷新列表，确认任务状态后再运行。",
    };
  }
  if (status === 400) {
    return {
      reason: "本次提交内容无效，未发送运行请求。",
      nextAction: "刷新列表，确认任务内容后再运行。",
    };
  }
  return {
    reason: "当前保存的任务或配置不允许这次运行，本次提交未受理。",
    nextAction: "刷新列表，确认任务状态和来源后再运行一次。",
  };
}

const PENDING_RUN_ONCE_DETAIL = "任务可能已提交，请先查看提交结果。";

export function AutomationListPage({
  createDialogOpen = false,
}: {
  readonly createDialogOpen?: boolean;
}) {
  const token = useAuthToken();
  const navigate = useNavigate();
  // The route search is the single source of truth for the submitted tab,
  // filters, sort, time window and server page cursor, so a deep entry, a
  // reload and a reconnect always read the same population.
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const queryClient = useQueryClient();
  const listKey = listSearchKey(searchParams);
  const [createdDefinition, setCreatedDefinition] = useState<{
    readonly id: string;
    readonly name: string;
    readonly enabled: boolean;
  } | null>(() => {
    const memory = automationCreatedDefinitionMemory;
    return memory === null
      ? null
      : { id: memory.id, name: memory.name, enabled: memory.enabled };
  });
  const [highlightedDefinitionId, setHighlightedDefinitionId] = useState<
    string | null
  >(() => {
    const memory = automationCreatedDefinitionMemory;
    return memory !== null && Date.now() - memory.createdAt < 6_000
      ? memory.id
      : null;
  });
  // A Task Center record round trip returns here with the exact `执行记录` list
  // state it left. The marker is consumed once and dropped, so the URL stays
  // the single source of truth and a later reconnect restores the same view.
  useEffect(() => {
    const context = readAutomationReturnContext(searchParams);
    if (context === null) {
      return;
    }
    void navigate({
      to: "/operations/automation",
      search: automationReturnSearch(context),
      replace: true,
    });
    // Restore only on the transition into a context-bearing URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams[AUTOMATION_RETURN_KEY]]);
  // The Automation settings tab was retired in favour of the existing System
  // Settings page.  A bookmarked/deep old link reaches that page directly and
  // produces no publication, admission or media effect here.
  const legacySettingsTab = searchText(searchParams, "tab") === "settings";
  useEffect(() => {
    if (!legacySettingsTab) {
      return;
    }
    void navigate({ to: "/configuration", replace: true });
  }, [legacySettingsTab, navigate]);
  const tab = tabFromSearch(searchText(searchParams, "tab"));
  const cursor = searchText(searchParams, "cursor") || null;
  const direction =
    searchText(searchParams, "dir") === "previous" ? "previous" : "next";
  const search = searchText(searchParams, "q");
  const enabledFilter = searchText(searchParams, "enabled");
  const stateFilter = searchText(searchParams, "state");
  const libraryFilter = searchText(searchParams, "library");
  const sort = searchText(searchParams, "sort") || "name";
  const recordStatus = searchText(searchParams, "rstatus");
  const recordTrigger = searchText(searchParams, "rtrigger");
  const recordDefinition = searchText(searchParams, "rdefinition");
  const recordFrom = searchText(searchParams, "rfrom");
  const recordTo = searchText(searchParams, "rto");

  // Free-text filters are edited locally and submitted explicitly (Enter or
  // blur). Writing every keystroke into the route search would re-read the
  // population per character and reset the input from the newest read.
  const [searchDraft, setSearchDraft] = useState(search);
  const [lastSubmittedSearch, setLastSubmittedSearch] = useState(search);
  if (lastSubmittedSearch !== search) {
    setLastSubmittedSearch(search);
    setSearchDraft(search);
  }
  const [libraryDraft, setLibraryDraft] = useState(libraryFilter);
  const [lastSubmittedLibrary, setLastSubmittedLibrary] =
    useState(libraryFilter);
  if (lastSubmittedLibrary !== libraryFilter) {
    setLastSubmittedLibrary(libraryFilter);
    setLibraryDraft(libraryFilter);
  }
  const [definitionDraft, setDefinitionDraft] = useState(recordDefinition);
  const [lastSubmittedDefinition, setLastSubmittedDefinition] =
    useState(recordDefinition);
  if (lastSubmittedDefinition !== recordDefinition) {
    setLastSubmittedDefinition(recordDefinition);
    setDefinitionDraft(recordDefinition);
  }

  useEffect(() => {
    if (!focusCreateEntryOnNextList) return;
    focusCreateEntryOnNextList = false;
    const timer = window.setTimeout(() => {
      document
        .getElementById("automation-create-entry")
        ?.focus({ preventScroll: true });
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const listQuery = useQuery(
    automationListQueryOptions(
      token,
      {
        q: search.trim() === "" ? null : search.trim(),
        enabled:
          enabledFilter === "true"
            ? true
            : enabledFilter === "false"
              ? false
              : null,
        state: stateFilter === "" ? null : stateFilter,
        library: libraryFilter.trim() === "" ? null : libraryFilter.trim(),
        sort,
        limit: 20,
        cursor,
      },
      tab === "definitions",
    ),
  );

  // The list Run-once command is a submission layer only. It reuses the exact
  // definition/Active snapshot this row was read from, retains the caller's
  // request identity before POST, and after admission leaves all run status to
  // the existing Task Center/records reads.
  const authGeneration = useAuthGeneration();
  const principalIdentity = usePrincipalIdentity();
  const principalId = principalIdentity.resolved
    ? principalIdentity.principalId
    : null;
  const [runOnceSession, setRunOnceSession] = useState(() =>
    readRunOnceSession(null),
  );
  const [runOnceBusy, setRunOnceBusy] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [runOnceChecking, setRunOnceChecking] = useState<string | null>(null);
  const [runOnceAdmitted, setRunOnceAdmitted] = useState<
    Readonly<Record<string, string>>
  >({});
  const [runOnceRejected, setRunOnceRejected] = useState<
    Readonly<Record<string, RejectedRunOnceCopy>>
  >({});
  const [runOnceUnknownNotes, setRunOnceUnknownNotes] = useState<
    Readonly<Record<string, string>>
  >({});
  const runOnceInFlight = useRef<Set<string>>(new Set());
  // A principal change is a hard boundary: pending context is principal-scoped
  // and the old session's async responses must not update or clear the new one.
  // Reading sessionStorage is the external synchronization this effect owns;
  // the state reset is the boundary, not a derived render value.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    setRunOnceSession(readRunOnceSession(principalId));
    setRunOnceBusy(new Set());
    setRunOnceChecking(null);
    setRunOnceAdmitted({});
    setRunOnceRejected({});
    setRunOnceUnknownNotes({});
    runOnceInFlight.current.clear();
  }, [principalId, authGeneration]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const runOnceFeedback = useMemo(() => {
    const feedback: Record<string, RunOnceFeedback> = {};
    for (const definitionId of runOnceBusy) {
      feedback[definitionId] = { state: "submitting" };
    }
    if (runOnceChecking !== null && !feedback[runOnceChecking]) {
      feedback[runOnceChecking] = { state: "checking" };
    }
    for (const [definitionId, taskId] of Object.entries(runOnceAdmitted)) {
      if (!feedback[definitionId]) {
        feedback[definitionId] = { state: "admitted", taskId };
      }
    }
    for (const [definitionId, copy] of Object.entries(runOnceRejected)) {
      if (!feedback[definitionId]) {
        feedback[definitionId] = { state: "rejected", ...copy };
      }
    }
    for (const pending of runOnceSession.pending) {
      if (feedback[pending.definitionId]) continue;
      feedback[pending.definitionId] = {
        state: "pending",
        detail: PENDING_RUN_ONCE_DETAIL,
        note: runOnceUnknownNotes[pending.definitionId] ?? null,
      };
    }
    return feedback;
  }, [
    runOnceAdmitted,
    runOnceBusy,
    runOnceChecking,
    runOnceRejected,
    runOnceSession,
    runOnceUnknownNotes,
  ]);

  // Any change to the admitted map restarts this one bounded display window, so
  // replacing a row's feedback also cancels the timer that belonged to the
  // previous admission. A later submission can therefore never be cleared by
  // the earlier success hint's deadline.
  useEffect(() => {
    if (Object.keys(runOnceAdmitted).length === 0) return;
    const timer = window.setTimeout(() => setRunOnceAdmitted({}), 8_000);
    return () => window.clearTimeout(timer);
  }, [runOnceAdmitted]);

  const refreshDefinitionRead = () => {
    void queryClient.invalidateQueries({ queryKey: [automationListQueryKey] });
    void listQuery.refetch();
  };

  const rememberAdmitted = (
    owner: string,
    definitionId: string,
    taskId: string,
    requestId?: string,
  ) => {
    clearRunOnceIntent(owner, definitionId, requestId);
    setRunOnceSession(readRunOnceSession(owner));
    setRunOnceUnknownNotes((current) => {
      if (current[definitionId] === undefined) return current;
      const next = { ...current };
      delete next[definitionId];
      return next;
    });
    setRunOnceAdmitted((current) => ({ ...current, [definitionId]: taskId }));
    setRunOnceRejected((current) => {
      if (current[definitionId] === undefined) return current;
      const next = { ...current };
      delete next[definitionId];
      return next;
    });
    refreshDefinitionRead();
  };

  /** Drop only this row's displayed result before a new explicit attempt. */
  const clearRunOnceRowFeedback = (definitionId: string) => {
    setRunOnceAdmitted((current) => {
      if (current[definitionId] === undefined) return current;
      const next = { ...current };
      delete next[definitionId];
      return next;
    });
    setRunOnceRejected((current) => {
      if (current[definitionId] === undefined) return current;
      const next = { ...current };
      delete next[definitionId];
      return next;
    });
    setRunOnceUnknownNotes((current) => {
      if (current[definitionId] === undefined) return current;
      const next = { ...current };
      delete next[definitionId];
      return next;
    });
  };

  const submitRunOnce = async (definition: AutomationDefinitionModel) => {
    const definitionId = definition.document.id;
    if (runOnceInFlight.current.has(definitionId)) return;
    if (
      readRunOnceSession(
        principalIdentity.resolved ? principalIdentity.principalId : null,
      ).pending.some((pending) => pending.definitionId === definitionId)
    ) {
      return;
    }
    // This explicit click is a new submission for this row, so the row must
    // stop showing the previous submission's result. Leaving the old
    // "已提交"/Task link in place would present the earlier admission as the
    // outcome of this attempt while it is submitting, refused or unanswered.
    // Other rows and retained request contexts are untouched.
    clearRunOnceRowFeedback(definitionId);
    if (!principalIdentity.resolved || token === null) {
      setRunOnceRejected((current) => ({
        ...current,
        [definitionId]: {
          reason: principalIdentity.resolved
            ? "当前登录状态不可用，本次提交未发送。"
            : "正在确认当前登录身份，本次提交未发送。",
          nextAction: "请稍后刷新列表，身份确认后再运行一次。",
        },
      }));
      return;
    }
    if (!definition.actions.runOnce.available) {
      setRunOnceRejected((current) => ({
        ...current,
        [definitionId]: {
          reason: "当前任务状态不允许运行一次，本次提交未发送。",
          nextAction: "刷新列表，确认任务仍已发布并可执行后再试。",
        },
      }));
      return;
    }
    const authority = definition.activeConfiguration;
    if (
      authority === null ||
      authority.revisionId.trim() === "" ||
      !Number.isInteger(authority.revisionSequence) ||
      authority.revisionSequence < 1
    ) {
      setRunOnceRejected((current) => ({
        ...current,
        [definitionId]: {
          reason: "当前保存的版本信息不可用，本次提交未发送。",
          nextAction: "刷新列表，确认任务仍已发布后再运行一次。",
        },
      }));
      return;
    }

    runOnceInFlight.current.add(definitionId);
    setRunOnceBusy((current) => new Set(current).add(definitionId));
    const generation = authStore.getGeneration();
    const owner = principalIdentity.principalId;
    const begin = beginRunOnceSubmission(owner, definitionId);
    if (!begin.ok) {
      runOnceInFlight.current.delete(definitionId);
      setRunOnceBusy((current) => {
        const next = new Set(current);
        next.delete(definitionId);
        return next;
      });
      setRunOnceRejected((current) => ({
        ...current,
        [definitionId]: {
          reason:
            begin.reason === "request-id-unavailable"
              ? "浏览器暂时无法生成可靠的提交标识，本次提交未发送。"
              : begin.reason === "storage-unavailable"
                ? "浏览器无法保存这次提交的核对信息，本次提交未发送。"
                : begin.reason === "capacity"
                  ? "待核对的一次运行提交过多，本次提交未发送。"
                  : "这次提交已有待核对的结果，本次未再次发送。",
          nextAction:
            begin.reason === "capacity"
              ? "先核对或等待现有待核对提交完成，再运行这个任务。"
              : "刷新页面后确认当前任务状态，再决定是否重新运行。",
        },
      }));
      return;
    }
    setRunOnceSession(readRunOnceSession(owner));

    try {
      const result = await admitAutomationRunOnce(token, {
        definitionId,
        admissionRequestId: begin.intent.requestId,
        // Exactly the row's own read: the Active revision and its sequence.
        // The operator projection deliberately carries no digest/fingerprint.
        expectedRevisionId: authority.revisionId,
        expectedRevisionVersion: authority.revisionSequence,
      });
      if (authStore.getGeneration() !== generation) return;
      if (!result.ok || result.model === undefined) {
        const unknown =
          result.status === 0 ||
          result.status >= 500 ||
          result.code === "malformed_response";
        if (unknown) {
          // Keep the exact retained request. The operator can read it back by
          // identity after refresh/reconnect; this is not a failed Task.
          setRunOnceSession(readRunOnceSession(owner));
          return;
        }
        clearRunOnceIntent(owner, definitionId, begin.intent.requestId);
        setRunOnceSession(readRunOnceSession(owner));
        setRunOnceRejected((current) => ({
          ...current,
          [definitionId]: rejectedRunOnceCopy(
            result.status,
            result.code ?? null,
          ),
        }));
        refreshDefinitionRead();
        return;
      }
      if (result.model.taskId === null) {
        setRunOnceSession(readRunOnceSession(owner));
        return;
      }
      rememberAdmitted(
        owner,
        definitionId,
        result.model.taskId,
        begin.intent.requestId,
      );
    } catch {
      if (authStore.getGeneration() !== generation) return;
      // A transport exception is an unknown durable outcome, never a proved
      // refusal. Retain the exact request context for read-only reconciliation.
      setRunOnceSession(readRunOnceSession(owner));
    } finally {
      // A response from the previous principal must not clear the new
      // principal's independent in-flight marker for the same definition.
      if (authStore.getGeneration() === generation) {
        runOnceInFlight.current.delete(definitionId);
        setRunOnceBusy((current) => {
          if (!current.has(definitionId)) return current;
          const next = new Set(current);
          next.delete(definitionId);
          return next;
        });
      }
    }
  };

  const checkRunOnce = async (definitionId: string) => {
    const pending = readRunOnceSession(principalId).pending.find(
      (item) => item.definitionId === definitionId,
    );
    if (pending === undefined || runOnceChecking !== null) return;
    if (principalId === null || token === null) {
      setRunOnceUnknownNotes((current) => ({
        ...current,
        [definitionId]: "当前登录身份不可用，暂时无法核对；请稍后刷新再试。",
      }));
      return;
    }
    setRunOnceChecking(definitionId);
    const generation = authStore.getGeneration();
    try {
      const result = await reconcileAutomationRunOnce(token, {
        definitionId: pending.definitionId,
        admissionRequestId: pending.requestId,
      });
      if (authStore.getGeneration() !== generation) return;
      if (result.ok && result.model?.taskId) {
        rememberAdmitted(
          principalId,
          pending.definitionId,
          result.model.taskId,
        );
        return;
      }
      setRunOnceUnknownNotes((current) => ({
        ...current,
        [definitionId]:
          result.code === "run_once_request_not_found"
            ? "刚才没有查到这次提交的结果；这不表示任务没有提交。请稍后再核对，或打开执行记录确认。"
            : "暂时无法确认这次提交的结果；任务可能已提交，请不要重复运行，稍后再核对。",
      }));
    } catch {
      if (authStore.getGeneration() !== generation) return;
      setRunOnceUnknownNotes((current) => ({
        ...current,
        [definitionId]:
          "暂时无法确认这次提交的结果；任务可能已提交，请不要重复运行，稍后再核对。",
      }));
    } finally {
      if (authStore.getGeneration() === generation) {
        setRunOnceChecking((current) =>
          current === definitionId ? null : current,
        );
      }
    }
  };

  const recordsQuery = useQuery(
    automationRecordsQueryOptions(
      token,
      {
        definition:
          recordDefinition.trim() === "" ? null : recordDefinition.trim(),
        trigger: recordTrigger === "" ? null : recordTrigger,
        outcome: recordStatus === "" ? null : recordStatus,
        from: utcBoundary(recordFrom),
        to: utcBoundary(recordTo),
        direction,
        limit: 20,
        cursor,
      },
      tab === "records",
    ),
  );

  // Restore the exact list scroll position saved by the create entry. The
  // query must have produced its rows first; the restored position is then the
  // operator's original page, not the top of a loading skeleton.
  useEffect(() => {
    if (!listQuery.isFetched || createDialogOpen) return;
    const memory = automationListScrollMemory;
    if (memory === null || memory.key !== listKey) return;
    automationListScrollMemory = null;
    const timer = window.setTimeout(() => {
      if (!Number.isFinite(memory.y) || memory.y <= 0) return;
      try {
        window.scrollTo({ top: memory.y, left: 0 });
      } catch {
        // A test/DOM environment may not implement scrolling; the list itself
        // is still rendered at its server page and filters.
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [createDialogOpen, listKey, listQuery.isFetched]);

  // The created row is marked briefly. The mount after the close route reads
  // the same memory, so the success banner and mark survive the remount without
  // persisting a draft, token or server state.
  useEffect(() => {
    if (highlightedDefinitionId === null) return;
    const memory = automationCreatedDefinitionMemory;
    const createdAt =
      memory !== null && memory.id === highlightedDefinitionId
        ? memory.createdAt
        : Date.now();
    const remaining = Math.max(0, 6_000 - (Date.now() - createdAt));
    const timer = window.setTimeout(() => {
      setHighlightedDefinitionId(null);
    }, remaining);
    return () => window.clearTimeout(timer);
  }, [highlightedDefinitionId]);

  /**
   * Write one submitted surface state into the route search.
   *
   * Every setter goes through here, so a filter change, a page turn, a tab
   * switch and a return from a detail page all produce a repeatable URL. A new
   * filter always drops the cursor: a cursor minted for another population is
   * never submitted.
   */
  function submitSearch(values: Record<string, string>, replace = true) {
    const next: Record<string, string> = {};
    for (const [key, value] of Object.entries(values)) {
      if (value !== "") {
        next[key] = value;
      }
    }
    void navigate({
      to: "/operations/automation",
      search: Object.keys(next).length > 0 ? next : undefined,
      replace,
    });
  }

  function definitionState(overrides: Record<string, string> = {}) {
    return {
      tab: "definitions",
      q: search,
      enabled: enabledFilter,
      state: stateFilter,
      library: libraryFilter,
      sort,
      cursor: "",
      dir: "",
      ...overrides,
    };
  }

  function recordState(overrides: Record<string, string> = {}) {
    return {
      tab: "records",
      rstatus: recordStatus,
      rtrigger: recordTrigger,
      rdefinition: recordDefinition,
      rfrom: recordFrom,
      rto: recordTo,
      cursor: "",
      dir: "",
      ...overrides,
    };
  }

  function selectedTab(next: AutomationTab) {
    if (next === "definitions") {
      submitSearch(definitionState());
    } else if (next === "records") {
      submitSearch(recordState());
    } else {
      submitSearch({ tab: next });
    }
  }

  /** The exact return context a definition link carries back to this list. */
  function listReturnState(): Record<string, string> {
    if (tab === "records") {
      return recordState({ cursor: cursor ?? "", dir: direction });
    }
    return definitionState({ cursor: cursor ?? "", dir: direction });
  }

  function openCreateDialog() {
    automationListScrollMemory = {
      key: listKey,
      y: Number.isFinite(window.scrollY) ? window.scrollY : 0,
      // Keep the exact URL the operator was reading. The create route adds
      // ordinary defaults to its own search, so deriving the return address
      // from that route would rewrite an omitted-default list into a different
      // URL and lose the saved scroll identity.
      search: listSearchForClose(searchParams),
    };
  }

  function closeCreateDialog() {
    focusCreateEntryOnNextList = true;
    const memory = automationListScrollMemory;
    const search =
      memory !== null && memory.key === listKey
        ? memory.search
        : listSearchForClose(searchParams);
    void navigate({
      to: "/operations/automation",
      search: Object.keys(search).length > 0 ? search : undefined,
      replace: true,
    });
  }

  function handleCreated(definition: AutomationDefinitionDocumentModel) {
    automationCreatedDefinitionMemory = {
      id: definition.id,
      name: definition.name,
      enabled: definition.enabled,
      createdAt: Date.now(),
    };
    setCreatedDefinition({
      id: definition.id,
      name: definition.name,
      enabled: definition.enabled,
    });
    setHighlightedDefinitionId(definition.id);
    void queryClient.invalidateQueries({ queryKey: [automationListQueryKey] });
    void listQuery.refetch();
  }

  function openDefinition(definitionId: string) {
    void navigate({
      to: "/operations/automation/definition/$definitionId",
      params: { definitionId },
      search: { returnTab: tab, ...listReturnState() },
    });
  }

  const definitionsPage =
    listQuery.data?.ok === true ? listQuery.data.model : null;
  // Creation is offered only when this exact principal's backend projection
  // advertises it; the page never infers the permission.
  const createAvailable =
    definitionsPage !== null && definitionsPage.actions.create.available;
  const createdListUnavailable =
    listQuery.data !== undefined && !listQuery.data.ok;
  const createdVisible =
    createdDefinition === null || listQuery.isFetching
      ? null
      : definitionsPage !== null &&
        definitionsPage.items.some(
          (item) => item.document.id === createdDefinition.id,
        );

  // The four cards read full-population backend aggregates. They are never
  // derived from the current page, and a filtered/paged read cannot change
  // them: `inventoryCounts` and the metric document are computed server-side
  // over the complete authorized population.
  const inventoryCounts = definitionsPage?.inventoryCounts ?? null;
  const definitionFiltered =
    search.trim() !== "" ||
    enabledFilter !== "" ||
    stateFilter !== "" ||
    libraryFilter.trim() !== "";
  const recordFiltered =
    recordStatus !== "" ||
    recordTrigger !== "" ||
    recordDefinition.trim() !== "" ||
    recordFrom !== "" ||
    recordTo !== "";

  // The latest admitted run per definition, merged from all durable evidence.
  const latestRuns = useMemo(
    () =>
      (definitionsPage?.latestAdmittedRuns ?? {}) as Readonly<
        Record<string, AutomationLatestRunModel>
      >,
    [definitionsPage],
  );

  return (
    <div className="mf-dashboard mf-automation-workspace">
      <div className="mf-automation-create-background">
        <header className="mf-dashboard-head">
          <div>
            <h2>自动化</h2>
            <p className="mf-dashboard-meta">
              配置和管理自动化任务，定时扫描、识别并整理媒体文件。
            </p>
          </div>
          <div className="mf-actions">
            {createAvailable && (
              <Link
                id="automation-create-entry"
                className="mf-button mf-button-primary"
                to="/operations/automation/lifecycle"
                search={listReturnState()}
                onClick={openCreateDialog}
              >
                新建自动化任务
              </Link>
            )}
            <RefreshControl
              label="刷新"
              refreshingLabel="刷新中…"
              onRefresh={() => {
                void listQuery.refetch();
                void recordsQuery.refetch();
              }}
              refreshing={listQuery.isFetching || recordsQuery.isFetching}
            />
          </div>
        </header>

        {createdDefinition !== null && (
          <StatusBanner
            variant="success"
            title={
              createdDefinition.enabled ? "已创建并启用" : "创建成功，尚未启用"
            }
          >
            <p>
              {createdDefinition.name
                ? createdDefinition.enabled
                  ? `已创建「${createdDefinition.name}」并启用；后续将按保存的计划定时运行。`
                  : `已创建「${createdDefinition.name}」，尚未启用。`
                : createdDefinition.enabled
                  ? "新任务已创建并启用。"
                  : "新任务已创建，尚未启用。"}
              {createdListUnavailable
                ? "当前任务列表暂不可用；刷新后可查看这条新任务。"
                : createdVisible === null
                  ? "正在刷新任务列表…"
                  : createdVisible
                    ? "已在本页标出，可稍后启用或运行一次。"
                    : "当前筛选或分页下未展示该任务；可调整筛选查看。"}
            </p>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => {
                automationCreatedDefinitionMemory = null;
                setCreatedDefinition(null);
              }}
            >
              关闭提示
            </button>
          </StatusBanner>
        )}

        {definitionsPage !== null && (
          <section className="mf-automation-metrics" aria-label="自动化统计">
            <AutomationMetricCards
              metrics={definitionsPage.metrics}
              inventoryCounts={inventoryCounts}
              onOpenDefinitions={() => selectedTab("definitions")}
            />
            {!definitionsPage.metrics.available && (
              <p className="mf-dashboard-meta" role="status">
                指标暂不可用：
                {definitionsPage.metrics.nextAction ?? "请刷新后核对"}
              </p>
            )}
          </section>
        )}

        <nav className="mf-run-tabs mf-view-tabs" aria-label="自动化分区">
          {AUTOMATION_TABS.map((value) => (
            <button
              key={value}
              type="button"
              aria-current={tab === value ? "page" : undefined}
              onClick={() => selectedTab(value)}
            >
              {AUTOMATION_TAB_LABELS[value]}
            </button>
          ))}
        </nav>

        {tab === "definitions" && (
          <AuthorizedReadBoundary
            query={listQuery}
            unavailableTitle="自动化不可用"
          >
            {({ data, isFetching, refresh }) => {
              if (data === undefined) {
                return (
                  <StatusBanner variant="info" title="正在读取自动化任务">
                    <p>正在读取已生效与草稿中的自动化任务。</p>
                  </StatusBanner>
                );
              }
              if (!data.ok) {
                return (
                  <StatusBanner variant="error" title={data.failure.title}>
                    <p>{data.failure.nextAction}</p>
                    <div className="mf-actions">
                      <RefreshControl
                        label="刷新"
                        refreshingLabel="刷新中…"
                        onRefresh={refresh}
                        refreshing={isFetching}
                      />
                    </div>
                  </StatusBanner>
                );
              }
              return (
                <DefinitionsTab
                  page={data.model}
                  latestRuns={latestRuns}
                  search={searchDraft}
                  enabled={enabledFilter}
                  state={stateFilter}
                  library={libraryDraft}
                  sort={sort}
                  filtered={definitionFiltered}
                  highlightedDefinitionId={highlightedDefinitionId}
                  onSearchChange={setSearchDraft}
                  onSearchSubmit={(value) => {
                    setSearchDraft(value);
                    setLastSubmittedSearch(value);
                    submitSearch(definitionState({ q: value }));
                  }}
                  onLibraryChange={setLibraryDraft}
                  onLibrarySubmit={(value) => {
                    setLibraryDraft(value);
                    setLastSubmittedLibrary(value);
                    submitSearch(definitionState({ library: value }));
                  }}
                  onEnabled={(value) =>
                    submitSearch(definitionState({ enabled: value }))
                  }
                  onState={(value) =>
                    submitSearch(definitionState({ state: value }))
                  }
                  onSort={(value) =>
                    submitSearch(definitionState({ sort: value }))
                  }
                  onOpen={openDefinition}
                  onEdit={(definitionId) =>
                    void navigate({
                      to: "/operations/automation/lifecycle/$definitionId",
                      params: { definitionId },
                      search: listReturnState(),
                    })
                  }
                  onRunOnce={(definition) => void submitRunOnce(definition)}
                  onCheckRunOnce={(definitionId) =>
                    void checkRunOnce(definitionId)
                  }
                  runOnceFeedback={runOnceFeedback}
                  runOncePending={runOnceSession.pending}
                  runOnceInvalidLegacy={runOnceSession.invalidLegacy}
                  onNext={(next) =>
                    submitSearch(
                      definitionState({ cursor: next, dir: "next" }),
                      false,
                    )
                  }
                  onPrevious={(previous) =>
                    submitSearch(
                      definitionState({ cursor: previous, dir: "previous" }),
                      false,
                    )
                  }
                  onReset={() => submitSearch({ tab: "definitions" })}
                />
              );
            }}
          </AuthorizedReadBoundary>
        )}

        {tab === "records" && (
          <AuthorizedReadBoundary
            query={recordsQuery}
            unavailableTitle="执行记录不可用"
          >
            {({ data, isFetching, refresh }) => {
              if (data === undefined) {
                return (
                  <StatusBanner variant="info" title="正在读取执行记录">
                    <p>正在读取已受理的自动化执行记录。</p>
                  </StatusBanner>
                );
              }
              if (!data.ok) {
                return (
                  <StatusBanner variant="error" title={data.failure.title}>
                    <p>{data.failure.nextAction}</p>
                    <div className="mf-actions">
                      {recordFiltered && (
                        <button
                          type="button"
                          className="mf-button mf-button-secondary"
                          onClick={() => submitSearch({ tab: "records" })}
                        >
                          清除筛选
                        </button>
                      )}
                      <RefreshControl
                        label="刷新"
                        refreshingLabel="刷新中…"
                        onRefresh={refresh}
                        refreshing={isFetching}
                      />
                    </div>
                  </StatusBanner>
                );
              }
              return (
                <RecordsTab
                  page={data.model}
                  status={recordStatus}
                  trigger={recordTrigger}
                  definition={definitionDraft}
                  from={recordFrom}
                  to={recordTo}
                  filtered={recordFiltered}
                  onStatus={(value) =>
                    submitSearch(recordState({ rstatus: value }))
                  }
                  onTrigger={(value) =>
                    submitSearch(recordState({ rtrigger: value }))
                  }
                  onDefinitionChange={setDefinitionDraft}
                  onDefinitionSubmit={(value) => {
                    setDefinitionDraft(value);
                    setLastSubmittedDefinition(value);
                    submitSearch(recordState({ rdefinition: value }));
                  }}
                  onFrom={(value) =>
                    submitSearch(recordState({ rfrom: value }))
                  }
                  onTo={(value) => submitSearch(recordState({ rto: value }))}
                  onReset={() => submitSearch({ tab: "records" })}
                  onNext={(next) =>
                    submitSearch(
                      recordState({ cursor: next, dir: "next" }),
                      false,
                    )
                  }
                  onPrevious={(previous) =>
                    submitSearch(
                      recordState({ cursor: previous, dir: "previous" }),
                      false,
                    )
                  }
                />
              );
            }}
          </AuthorizedReadBoundary>
        )}
      </div>

      {createDialogOpen && (
        <AutomationCreateDialog
          onClose={closeCreateDialog}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}

function DefinitionsTab({
  page,
  latestRuns,
  search,
  enabled,
  state,
  library,
  sort,
  filtered,
  highlightedDefinitionId,
  onSearchChange,
  onSearchSubmit,
  onEnabled,
  onState,
  onLibraryChange,
  onLibrarySubmit,
  onSort,
  onOpen,
  onEdit,
  onRunOnce,
  onCheckRunOnce,
  runOnceFeedback,
  runOncePending,
  runOnceInvalidLegacy,
  onNext,
  onPrevious,
  onReset,
}: {
  readonly page: {
    readonly items: readonly AutomationDefinitionModel[];
    readonly total: number;
    readonly truncated: boolean;
    readonly itemsTruncatedByCap: boolean;
    readonly nextCursor: string | null;
    readonly previousCursor: string | null;
    readonly draftState: {
      readonly reason: string | null;
      readonly present: boolean;
    };
  } | null;
  readonly latestRuns: Readonly<Record<string, AutomationLatestRunModel>>;
  readonly search: string;
  readonly enabled: string;
  readonly state: string;
  readonly library: string;
  readonly sort: string;
  readonly filtered: boolean;
  readonly highlightedDefinitionId: string | null;
  readonly onSearchChange: (value: string) => void;
  readonly onSearchSubmit: (value: string) => void;
  readonly onEnabled: (value: string) => void;
  readonly onState: (value: string) => void;
  readonly onLibraryChange: (value: string) => void;
  readonly onLibrarySubmit: (value: string) => void;
  readonly onSort: (value: string) => void;
  readonly onOpen: (definitionId: string) => void;
  readonly onEdit: (definitionId: string) => void;
  readonly onRunOnce: (definition: AutomationDefinitionModel) => void;
  readonly onCheckRunOnce: (definitionId: string) => void;
  readonly runOnceFeedback: Readonly<Record<string, RunOnceFeedback>>;
  readonly runOncePending: readonly PendingRunOnceIntent[];
  readonly runOnceInvalidLegacy: boolean;
  readonly onNext: (cursor: string) => void;
  readonly onPrevious: (cursor: string) => void;
  readonly onReset: () => void;
}) {
  if (page === null) {
    return null;
  }
  const visibleDefinitionIds = new Set(
    page.items.map((item) => item.document.id),
  );
  const hiddenPending = runOncePending.filter(
    (pending) => !visibleDefinitionIds.has(pending.definitionId),
  );
  const hiddenAdmitted = Object.entries(runOnceFeedback).filter(
    ([definitionId, feedback]) =>
      !visibleDefinitionIds.has(definitionId) && feedback.state === "admitted",
  );
  const hasHiddenRunOnce =
    hiddenPending.length > 0 || hiddenAdmitted.length > 0;
  return (
    <section className="mf-count-section" aria-label="自动化任务列表">
      <div className="mf-actions mf-automation-filters">
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-search">搜索</label>
          <input
            id="automation-search"
            type="search"
            value={search}
            placeholder="名称、来源库或范围"
            onChange={(event) => onSearchChange(event.target.value)}
            onBlur={(event) => onSearchSubmit(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onSearchSubmit(event.currentTarget.value);
              }
            }}
          />
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-enabled">启用状态</label>
          <select
            id="automation-enabled"
            value={enabled}
            onChange={(event) => onEnabled(event.target.value)}
          >
            <option value="">全部</option>
            <option value="true">已启用</option>
            <option value="false">未启用</option>
          </select>
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-state">发布状态</label>
          <select
            id="automation-state"
            value={state}
            onChange={(event) => onState(event.target.value)}
          >
            {DEFINITIONS_STATE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-library">来源库</label>
          <input
            id="automation-library"
            type="text"
            value={library}
            onChange={(event) => onLibraryChange(event.target.value)}
            onBlur={(event) => onLibrarySubmit(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onLibrarySubmit(event.currentTarget.value);
              }
            }}
          />
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="automation-sort">排序</label>
          <select
            id="automation-sort"
            value={sort}
            onChange={(event) => onSort(event.target.value)}
          >
            {SORT_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        {filtered && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onReset}
          >
            清除筛选
          </button>
        )}
      </div>

      {hasHiddenRunOnce && (
        <StatusBanner
          variant="info"
          title={hiddenPending.length > 0 ? "有提交结果待核对" : "已提交"}
        >
          {hiddenPending.length > 0 && (
            <p>
              下面的任务不在当前筛选或分页中，但那次提交的结果仍可安全核对。
              核对只读取原提交结果，不会再次运行。
            </p>
          )}
          {hiddenPending.map((pending) => {
            const feedback = runOnceFeedback[pending.definitionId];
            return (
              <div
                key={pending.definitionId}
                className="mf-automation-hidden-pending"
              >
                <strong>一个自动化任务</strong>
                {feedback?.state === "checking" ? (
                  <span className="mf-dashboard-meta">正在确认…</span>
                ) : (
                  <button
                    type="button"
                    className="mf-button mf-button-secondary"
                    onClick={() => onCheckRunOnce(pending.definitionId)}
                  >
                    查看提交结果
                  </button>
                )}
                {feedback?.state === "pending" && feedback.note !== null && (
                  <p className="mf-dashboard-meta">{feedback.note}</p>
                )}
              </div>
            );
          })}
          {hiddenAdmitted.map(([definitionId, feedback]) => (
            <div key={definitionId} className="mf-automation-hidden-pending">
              <strong>一个自动化任务</strong>
              <span className="mf-dashboard-meta">任务已受理，尚未完成。</span>
              {feedback.state === "admitted" && (
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/tasks/$taskId"
                  params={{ taskId: feedback.taskId }}
                >
                  查看任务
                </Link>
              )}
            </div>
          ))}
        </StatusBanner>
      )}
      {runOnceInvalidLegacy && (
        <StatusBanner variant="info" title="之前保存的提交信息无法识别">
          <p>
            编辑页留下的一次运行提交信息已损坏，无法自动核对。它不会被当成新的
            运行请求；请打开执行记录确认实际结果，不要重复提交。
          </p>
        </StatusBanner>
      )}
      {page.items.length === 0 ? (
        <StatusBanner
          variant="info"
          title={filtered ? "没有匹配的自动化任务" : "还没有自动化任务"}
        >
          <p>
            {filtered
              ? "当前筛选条件下没有自动化任务。清除筛选可查看全部已授权任务。"
              : "创建后任务默认停用；可在列表中启用或运行一次，创建本身不会扫描或整理媒体文件。"}
          </p>
          {!filtered && page.draftState.reason && (
            <p>{page.draftState.reason}</p>
          )}
        </StatusBanner>
      ) : (
        <>
          <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
            <table className="mf-automation-table" aria-label="自动化任务">
              <thead>
                <tr>
                  <th scope="col">名称</th>
                  <th scope="col">状态</th>
                  <th scope="col">运行模式</th>
                  <th scope="col">资源库</th>
                  <th scope="col">调度</th>
                  <th scope="col">单次上限</th>
                  <th scope="col">下次运行</th>
                  <th scope="col">最近结果</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((definition) => (
                  <AutomationDefinitionRow
                    key={definition.document.id}
                    definition={definition}
                    latestRun={latestRuns[definition.document.id] ?? null}
                    onOpen={() => onOpen(definition.document.id)}
                    onEdit={() => onEdit(definition.document.id)}
                    onRunOnce={
                      definition.actions.runOnce.available
                        ? () => onRunOnce(definition)
                        : null
                    }
                    onCheckRunOnce={() =>
                      onCheckRunOnce(definition.document.id)
                    }
                    runOnceFeedback={
                      runOnceFeedback[definition.document.id] ?? null
                    }
                    highlighted={
                      highlightedDefinitionId === definition.document.id
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
          <p className="mf-dashboard-meta" role="status">
            共 {page.total} 个自动化任务
            {page.truncated ? "（还有更多，请翻页）" : ""}
            {page.itemsTruncatedByCap
              ? "；超出安全上限的任务未显示，请缩小筛选范围"
              : ""}
          </p>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.previousCursor === null}
              onClick={() => {
                if (page.previousCursor !== null) {
                  onPrevious(page.previousCursor);
                }
              }}
            >
              上一页
            </button>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.nextCursor === null}
              onClick={() => {
                if (page.nextCursor !== null) {
                  onNext(page.nextCursor);
                }
              }}
            >
              下一页
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function RecordsTab({
  page,
  status,
  trigger,
  definition,
  from,
  to,
  filtered,
  onStatus,
  onTrigger,
  onDefinitionChange,
  onDefinitionSubmit,
  onFrom,
  onTo,
  onReset,
  onNext,
  onPrevious,
}: {
  readonly page: {
    readonly items: readonly AutomationRecordModel[];
    readonly total: number;
    readonly truncated: boolean;
    readonly historyBasis: string;
    readonly nextCursor: string | null;
    readonly previousCursor: string | null;
  } | null;
  readonly status: string;
  readonly trigger: string;
  readonly definition: string;
  readonly from: string;
  readonly to: string;
  readonly filtered: boolean;
  readonly onStatus: (value: string) => void;
  readonly onTrigger: (value: string) => void;
  readonly onDefinitionChange: (value: string) => void;
  readonly onDefinitionSubmit: (value: string) => void;
  readonly onFrom: (value: string) => void;
  readonly onTo: (value: string) => void;
  readonly onReset: () => void;
  readonly onNext: (cursor: string) => void;
  readonly onPrevious: (cursor: string) => void;
}) {
  if (page === null) {
    return null;
  }
  return (
    <section className="mf-count-section" aria-label="自动化执行记录">
      <div className="mf-actions mf-automation-filters">
        <div className="mf-automation-filter-field">
          <label htmlFor="record-definition">定义</label>
          <input
            id="record-definition"
            type="text"
            value={definition}
            onChange={(event) => onDefinitionChange(event.target.value)}
            onBlur={(event) => onDefinitionSubmit(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onDefinitionSubmit(event.currentTarget.value);
              }
            }}
          />
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="record-trigger">触发方式</label>
          <select
            id="record-trigger"
            value={trigger}
            onChange={(event) => onTrigger(event.target.value)}
          >
            {RECORD_TRIGGER_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="record-status">结果</label>
          <select
            id="record-status"
            value={status}
            onChange={(event) => onStatus(event.target.value)}
          >
            {status !== "" &&
              !RECORD_STATUS_OPTIONS.some(([value]) => value === status) && (
                <option value={status}>无效结果筛选</option>
              )}
            {RECORD_STATUS_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="record-from">起始时间（UTC）</label>
          <input
            id="record-from"
            type="datetime-local"
            value={from}
            onChange={(event) => onFrom(event.target.value)}
          />
        </div>
        <div className="mf-automation-filter-field">
          <label htmlFor="record-to">结束时间（UTC）</label>
          <input
            id="record-to"
            type="datetime-local"
            value={to}
            onChange={(event) => onTo(event.target.value)}
          />
        </div>
        {filtered && (
          <button
            type="button"
            className="mf-button mf-button-secondary"
            onClick={onReset}
          >
            清除筛选
          </button>
        )}
      </div>
      {page.items.length === 0 ? (
        <StatusBanner
          variant="info"
          title={filtered ? "没有匹配的执行记录" : "还没有执行记录"}
        >
          <p>
            {filtered
              ? "当前筛选条件下没有执行记录。清除定义、触发方式、结果与时间筛选可查看全部记录。"
              : "定时任务尚未到达执行时间，也没有手动运行一次；执行后会在这里显示原始结果。"}
          </p>
        </StatusBanner>
      ) : (
        <>
          <div className="mf-run-table-wrap" style={{ overflowX: "auto" }}>
            <table className="mf-automation-table" aria-label="自动化执行记录">
              <thead>
                <tr>
                  <th scope="col">定义</th>
                  <th scope="col">结果</th>
                  <th scope="col">开始（本地时间）</th>
                  <th scope="col">结束（本地时间）</th>
                  <th scope="col">条目</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((record) => (
                  <AutomationRecordRow key={record.recordId} record={record} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="mf-dashboard-meta" role="status">
            共 {page.total} 条执行记录
            {page.truncated ? "（还有更多，请翻页）" : ""}
          </p>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.previousCursor === null}
              onClick={() => {
                if (page.previousCursor !== null) {
                  onPrevious(page.previousCursor);
                }
              }}
            >
              上一页
            </button>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              disabled={page.nextCursor === null}
              onClick={() => {
                if (page.nextCursor !== null) {
                  onNext(page.nextCursor);
                }
              }}
            >
              下一页
            </button>
          </div>
        </>
      )}
    </section>
  );
}
