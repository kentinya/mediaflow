/**
 * The Automation creation dialog.
 *
 * It opens over the existing Automation list, presents one ordinary form and
 * submits the existing checked create command against the exact Active
 * authority read for this dialog. It never creates a Draft, enables a schedule,
 * runs work or mutates Storage. A lost create response is retained as an
 * unknown command identity and may only be reconciled from durable evidence;
 * it is never replayed.
 */

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  createAutomationDefinitionFocused,
  fetchAutomationFormAuthority,
  fetchStorageFiles,
  previewAutomationSchedule,
  reconcileAutomationPublicationFocused,
  type AutomationMutationFailureDetails,
} from "../../shared/api/api-client";
import type { AutomationDefinitionDocumentModel } from "../../entities/operations/automation";
import type { AutomationDefinitionFormAuthorityModel } from "../../entities/operations/automation-lifecycle";
import type { StorageFilesFailure } from "../../shared/api/api-client";
import { Button } from "../../shared/ui/Button";
import { usePrincipalIdentity } from "./principal-identity-query";
import {
  buildCandidateFromPublicationForm,
  buildCreateCandidate,
  browserTimeZone,
  compiledSchedule,
  createFormFromPublication,
  enabledResourceLibraries,
  formatPreviewTime,
  initialCreateForm,
  newAutomationDefinitionId,
  publicationFormFromCreateForm,
  scheduleSummary,
  validateCreateForm,
  type AutomationCreateForm,
  type CreateFormIssue,
  type CreateScheduleKind,
  type IntervalUnit,
} from "./automation-create-form";
import {
  readPendingAutomationPublication,
  writePendingAutomationPublication,
  type AutomationPublicationAuthority,
  type PendingAutomationPublication,
} from "./automation-publication-session";

export interface AutomationCreateDialogProps {
  readonly onClose: () => void;
  readonly onCreated: (definition: AutomationDefinitionDocumentModel) => void;
}

type PreviewState =
  | { readonly kind: "idle" }
  | { readonly kind: "loading" }
  | {
      readonly kind: "ready";
      readonly timezone: string | null;
      readonly upcoming: readonly string[];
    }
  | { readonly kind: "error"; readonly code: string };

type CommandError =
  | { readonly kind: "local"; readonly message: string }
  | { readonly kind: "conflict"; readonly code: string }
  | {
      readonly kind: "rejected";
      readonly code: string;
      readonly details: AutomationMutationFailureDetails | undefined;
    }
  | { readonly kind: "unknown"; readonly code: string }
  | { readonly kind: "reconcile-unknown"; readonly code: string | null };

const WEEKDAYS = [
  ["1", "周一"],
  ["2", "周二"],
  ["3", "周三"],
  ["4", "周四"],
  ["5", "周五"],
  ["6", "周六"],
  ["0", "周日"],
] as const;

const EXIT_MS = 160;
const COMMAND_ERROR_ID = "automation-create-command-error";
const DISCARD_CONTINUE_ID = "automation-create-discard-continue";

/** The one field that owns the current schedule choice when it is rejected. */
function scheduleFieldId(schedule: CreateScheduleKind): string {
  switch (schedule) {
    case "interval":
      return "automation-create-interval";
    case "daily":
      return "automation-create-daily-time";
    case "weekly":
      return "automation-create-weekly-time";
    case "cron":
      return "automation-create-cron";
  }
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function activeAuthority(
  authority: AutomationDefinitionFormAuthorityModel,
): AutomationPublicationAuthority {
  return {
    revisionId: authority.active.revisionId,
    version: authority.active.revisionSequence,
    digest: authority.active.digest,
  };
}

function failureStageLabel(stage: string | undefined): string | null {
  switch (stage) {
    case "read":
      return "读取当前配置";
    case "compose":
      return "组合候选";
    case "validate":
      return "校验输入";
    case "persist":
      return "保存配置";
    case "prepare":
      return "准备发布";
    case "activate":
      return "激活配置";
    default:
      return null;
  }
}

function commandErrorMessage(error: CommandError): {
  readonly title: string;
  readonly body: string;
} {
  switch (error.kind) {
    case "local":
      return { title: "无法创建", body: error.message };
    case "conflict":
      return {
        title: "创建未生效",
        body:
          error.code === "automation_definition_duplicate"
            ? "内部 ID 已存在，配置没有被修改。输入已保留；请在诊断信息中重新生成 ID 后再创建。"
            : "当前配置已被其他操作更新，创建命令没有生效。输入和创建 ID 已保留；请先重新核对当前配置，再明确创建。",
      };
    case "rejected": {
      const stage = failureStageLabel(error.details?.stage);
      const body =
        error.code === "automation_definition_invalid_field"
          ? "后端在组合候选时拒绝了这次输入，当前 Active 没有被改写。请先检查“运行时间”中的 Cron 表达式与 IANA 时区；如果仍然失败，再检查名称、来源范围与处理上限。输入和内部 ID 已保留；修正后可再次明确创建。"
          : `${
              stage === null ? "后端拒绝了这次创建" : `在“${stage}”阶段被拒绝`
            }，当前 Active 没有被这次命令改写。输入和内部 ID 已保留，请按提示修正后再次明确创建。`;
      return { title: "创建未生效", body };
    }
    case "unknown":
      return {
        title: "创建结果待核对",
        body: "响应没有送达或无法解读，创建命令可能已经生效。系统不会自动重发；请使用“核对本次创建”读取真实持久结果。",
      };
    case "reconcile-unknown":
      return {
        title: "本次创建仍未证实",
        body: "核对没有找到可确认的发布结果，但也不能证明创建未发生。请保留当前页面稍后再次核对，或关闭后重新打开继续核对；不会重新创建。",
      };
  }
}

function directoryFailureCopy(failure: StorageFilesFailure): {
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

export function AutomationCreateDialog({
  onClose,
  onCreated,
}: AutomationCreateDialogProps) {
  const token = useAuthToken();
  const principalIdentity = usePrincipalIdentity();
  const principalId = principalIdentity.resolved
    ? principalIdentity.principalId
    : null;
  const browserZone = useMemo(() => browserTimeZone(), []);
  const layerRef = useRef<HTMLDivElement | null>(null);
  const diagnosticsRef = useRef<HTMLDetailsElement | null>(null);
  const invokerRef = useRef<Element | null>(
    typeof document === "undefined" ? null : document.activeElement,
  );
  const mountedRef = useRef(true);
  const submittingRef = useRef(false);
  const bypassBlockerRef = useRef(false);
  const blockersResetRef = useRef<(() => void) | null>(null);
  const discardReturnFocusRef = useRef<HTMLElement | null>(null);
  const lastFieldFocusRef = useRef<HTMLElement | null>(null);
  const exitTimerRef = useRef<number | null>(null);
  const previewGeneration = useRef(0);
  const initializedRef = useRef(false);

  const [form, setForm] = useState<AutomationCreateForm | null>(null);
  const [observedAuthority, setObservedAuthority] =
    useState<AutomationPublicationAuthority | null>(null);
  const [idGenerationFailed, setIdGenerationFailed] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [showIssues, setShowIssues] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const [closing, setClosing] = useState(false);
  const [discardArmed, setDiscardArmed] = useState(false);
  const [commandError, setCommandError] = useState<CommandError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [previewState, setPreviewState] = useState<{
    readonly key: string;
    readonly value: PreviewState;
  }>({ key: "", value: { kind: "idle" } });
  const [browserOpen, setBrowserOpen] = useState(false);
  const [browserPath, setBrowserPath] = useState("");
  const [libraryNotice, setLibraryNotice] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);

  // The submitted-but-unconfirmed create command is read during render so a
  // reopened dialog restores the exact identity before the first interactive
  // frame. It is scoped to the confirmed principal and to create commands, so
  // an edit/toggle outcome can never be rendered or reconciled here.
  const [pendingOverride, setPendingOverride] = useState<{
    readonly owner: string | null;
    readonly value: PendingAutomationPublication | null;
  } | null>(null);
  const pendingPublication =
    pendingOverride?.owner === principalId
      ? pendingOverride.value
      : readPendingAutomationPublication(principalId, "create");
  const setPendingPublication = (
    value: PendingAutomationPublication | null,
  ) => {
    setPendingOverride({ owner: principalId, value });
    writePendingAutomationPublication(principalId, "create", value);
  };

  const authorityQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-authority"],
    queryFn: () => fetchAutomationFormAuthority(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnMount: "always",
  });
  const authorityResult = authorityQuery.data;
  const authorityModel =
    authorityResult !== undefined && authorityResult.ok
      ? authorityResult.model
      : null;
  const authorityFailed =
    authorityResult !== undefined && !authorityResult.ok
      ? authorityResult
      : null;

  // Initialize exactly once: a pending command restores its submitted form and
  // fence, while a fresh session generates one cryptographically random ID and
  // prefills the browser's IANA timezone (or the explicit UTC fallback).
  useEffect(() => {
    if (initializedRef.current) return;
    if (
      !authorityQuery.isFetchedAfterMount ||
      authorityModel === null ||
      !principalIdentity.resolved
    ) {
      return;
    }
    initializedRef.current = true;
    queueMicrotask(() => {
      if (!mountedRef.current) return;
      if (pendingPublication !== null) {
        setForm(
          createFormFromPublication(pendingPublication, browserZone.timeZone),
        );
        setObservedAuthority(pendingPublication.authority);
        return;
      }
      const id = newAutomationDefinitionId();
      if (id === null) {
        setIdGenerationFailed(true);
      }
      setForm(
        initialCreateForm({
          id: id ?? "",
          timeZone: browserZone.timeZone,
        }),
      );
      setObservedAuthority(activeAuthority(authorityModel));
    });
  }, [
    authorityModel,
    authorityQuery.isFetchedAfterMount,
    browserZone.timeZone,
    pendingPublication,
    principalIdentity.resolved,
  ]);

  // The dialog owns the viewport while open: background scrolling and
  // interaction stop, and the sibling list surface is inert. Cleanup restores
  // exactly the previous state so an interrupted close cannot leave a lock.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    const parent = layer?.parentElement;
    if (layer === null || parent === null || parent === undefined) return;
    const siblings = Array.from(parent.children).filter(
      (child): child is HTMLElement =>
        child !== layer && child instanceof HTMLElement,
    );
    const previous = siblings.map((child) => child.hasAttribute("inert"));
    for (const sibling of siblings) sibling.setAttribute("inert", "");
    return () => {
      siblings.forEach((sibling, index) => {
        if (!previous[index]) sibling.removeAttribute("inert");
      });
    };
  }, []);

  useEffect(
    () => () => {
      mountedRef.current = false;
      previewGeneration.current += 1;
      if (exitTimerRef.current !== null) {
        window.clearTimeout(exitTimerRef.current);
      }
    },
    [],
  );

  const validationIssues: readonly CreateFormIssue[] = useMemo(
    () =>
      form !== null && authorityModel !== null
        ? validateCreateForm(form, authorityModel)
        : [],
    [form, authorityModel],
  );
  const previewReady =
    form !== null &&
    authorityModel !== null &&
    form.name.trim().length > 0 &&
    validationIssues.length === 0;

  const formKey = useMemo(
    () =>
      form === null
        ? ""
        : JSON.stringify([
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
          ]),
    [form],
  );

  // Any candidate change immediately invalidates the displayed result. Only a
  // response produced for the exact current form and this dialog generation may
  // replace it, so a late response, a closed-dialog response or a previous
  // ResourceLibrary response can never overwrite newer state.
  const preview: PreviewState =
    previewState.key === formKey ? previewState.value : { kind: "idle" };

  useEffect(() => {
    const generation = ++previewGeneration.current;
    if (form === null || authorityModel === null || !previewReady) {
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
        objectId: null,
      }).then((result) => {
        if (
          !mountedRef.current ||
          previewGeneration.current !== generation ||
          !previewReady
        ) {
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
  }, [form, formKey, authorityModel, previewReady, token]);

  const directoryQuery = useInfiniteQuery({
    queryKey: [
      "operations.automation-create-directory",
      form?.resourceLibraryId ?? "",
      browserPath,
    ],
    queryFn: ({ pageParam }) =>
      fetchStorageFiles(token, {
        resourceLibraryId: form?.resourceLibraryId ?? "",
        path: browserPath,
        cursor: pageParam,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) =>
      lastPage.ok && lastPage.model.hasNext ? lastPage.model.nextCursor : null,
    enabled:
      token !== null &&
      browserOpen &&
      form !== null &&
      form.resourceLibraryId.length > 0,
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

  // A submitted create command blocks route and browser-back navigation until
  // the response arrives, so an in-flight command cannot be silently abandoned
  // by an accidental leave. Unsaved input keeps its own discard choice.
  const blocker = useBlocker({
    shouldBlockFn: () =>
      !bypassBlockerRef.current &&
      (submittingRef.current || (dirty && pendingPublication === null)),
    withResolver: true,
  });
  useEffect(() => {
    blockersResetRef.current =
      blocker.status === "blocked" ? blocker.reset : null;
  }, [blocker]);
  const submitBlocked = submitting && blocker.status === "blocked";

  function releaseBlockedNavigation() {
    const reset = blockersResetRef.current;
    blockersResetRef.current = null;
    if (reset !== null) reset();
  }

  function focusCommandError() {
    window.requestAnimationFrame(() => {
      document.getElementById(COMMAND_ERROR_ID)?.focus();
    });
  }

  const beginExit = (after: (() => void) | null) => {
    if (closing) return;
    setClosing(true);
    const finish = () => {
      if (after !== null) after();
      else onClose();
    };
    if (prefersReducedMotion()) {
      finish();
      return;
    }
    exitTimerRef.current = window.setTimeout(finish, EXIT_MS);
  };

  const commitClose = () => {
    if (submittingRef.current) return;
    setDiscardArmed(false);
    setDirty(false);
    discardReturnFocusRef.current = null;
    bypassBlockerRef.current = true;
    if (blocker.status === "blocked") {
      const proceed = blocker.proceed;
      beginExit(() => proceed());
      return;
    }
    beginExit(onClose);
  };

  const attemptClose = () => {
    if (submittingRef.current || closing) return;
    if (discardArmed) {
      // A second close gesture while the choice is open keeps the input and
      // returns to the field the operator was editing.
      cancelDiscard();
      return;
    }
    if (blocker.status === "blocked") {
      setDiscardArmed(true);
      return;
    }
    if (dirty && pendingPublication === null) {
      setDiscardArmed(true);
      return;
    }
    commitClose();
  };
  const attemptCloseRef = useRef(attemptClose);
  useEffect(() => {
    attemptCloseRef.current = attemptClose;
  });
  const discardPromptOpen =
    !submitting && (discardArmed || blocker.status === "blocked");

  // The discard choice is always visible and focusable: it is rendered above
  // the scrolling fields, the safe "keep editing" action receives focus, and
  // cancelling restores the exact field the operator was editing.
  function cancelDiscard() {
    setDiscardArmed(false);
    if (blocker.status === "blocked") blocker.reset();
    const previous = discardReturnFocusRef.current;
    discardReturnFocusRef.current = null;
    window.requestAnimationFrame(() => {
      if (previous !== null && document.contains(previous)) {
        previous.focus();
        return;
      }
      document.getElementById("automation-create-name")?.focus();
    });
  }

  // Any pending leave - a close gesture, a blocked route or a blocked browser
  // back - shows the same pinned decision and moves focus to the safe action.
  useEffect(() => {
    if (!discardPromptOpen) return;
    const active = document.activeElement;
    // Prefer the last field the operator edited, so both the close button and a
    // backdrop click return to the same input rather than to a dismissed button.
    discardReturnFocusRef.current =
      lastFieldFocusRef.current ??
      (active instanceof HTMLElement && active !== document.body
        ? active
        : null);
    const timer = window.requestAnimationFrame(() => {
      document.getElementById(DISCARD_CONTINUE_ID)?.focus();
    });
    return () => window.cancelAnimationFrame(timer);
  }, [discardPromptOpen]);

  // Escape, Tab trapping and the first focus belong to the dialog. The invoker
  // is captured at mount; focus returns to it when the dialog unmounts, or to
  // the list's create entry after a route-level open/close.
  useEffect(() => {
    const layer = layerRef.current;
    const focusables = () =>
      Array.from(
        layer?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((element) => element.offsetParent !== null);
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        attemptCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !layer?.contains(active))) {
        event.preventDefault();
        last.focus();
        return;
      }
      if (!event.shiftKey && (active === last || !layer?.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKey, true);
    const handleFocusIn = (event: FocusEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)
      ) {
        lastFieldFocusRef.current = target;
      }
    };
    layer?.addEventListener("focusin", handleFocusIn);
    return () => {
      document.removeEventListener("keydown", handleKey, true);
      layer?.removeEventListener("focusin", handleFocusIn);
    };
  }, []);

  useEffect(
    () => () => {
      const invoker = invokerRef.current;
      if (invoker instanceof HTMLElement && document.contains(invoker)) {
        invoker.focus();
      } else {
        window.setTimeout(() => {
          document.getElementById("automation-create-entry")?.focus();
        }, 0);
      }
    },
    [],
  );

  useEffect(() => {
    if (form === null) return;
    const target =
      pendingPublication !== null
        ? layerRef.current?.querySelector<HTMLElement>(
            '[data-automation-create-primary="true"]',
          )
        : document.getElementById("automation-create-name");
    target?.focus();
  }, [form === null]); // eslint-disable-line react-hooks/exhaustive-deps

  function updateFields(patch: Partial<AutomationCreateForm>) {
    setForm((current) =>
      current === null ? current : { ...current, ...patch },
    );
    setDirty(true);
    setNotice(null);
    setCommandError((current) =>
      current !== null &&
      (current.kind === "conflict" ||
        current.kind === "rejected" ||
        current.kind === "local")
        ? null
        : current,
    );
  }

  function updateSchedule(schedule: CreateScheduleKind) {
    if (form === null) return;
    if (schedule === "cron") {
      const compiled = compiledSchedule(form);
      updateFields({
        schedule,
        cron: form.cron.trim() || compiled?.cron || "0 8 * * *",
      });
      return;
    }
    updateFields({ schedule });
  }

  function changeLibrary(value: string) {
    if (form === null) return;
    updateFields({
      resourceLibraryId: value,
      scopeMode: "root",
      sourceScope: "",
    });
    setBrowserPath("");
    setLibraryNotice(
      "已切换资源库；原资源子目录已清空，来源范围现在为整个资源库。",
    );
  }

  function openDirectoryBrowser() {
    if (form === null) return;
    if (form.resourceLibraryId.length === 0) {
      setNotice("请先选择资源库，再浏览其中的子目录。");
      return;
    }
    setNotice(null);
    setBrowserPath(form.sourceScope.trim());
    setBrowserOpen(true);
  }

  function chooseDirectory(path: string) {
    if (form === null) return;
    updateFields({
      scopeMode: path === "" ? "root" : "subdirectory",
      sourceScope: path,
    });
    setBrowserOpen(false);
    setLibraryNotice(null);
  }

  function regenerateId() {
    if (pendingPublication !== null || submitting) return;
    const id = newAutomationDefinitionId();
    if (id === null) {
      setIdGenerationFailed(true);
      setCommandError({
        kind: "local",
        message:
          "当前浏览器无法提供安全的随机源，因此不能生成内部 ID。系统不会使用弱随机或时间戳代替；请刷新页面后重试。",
      });
      focusCommandError();
      return;
    }
    setIdGenerationFailed(false);
    setForm((current) => (current === null ? current : { ...current, id }));
    setCommandError(null);
    setNotice("已生成新的内部 ID。");
  }

  async function recheckAuthority() {
    if (rechecking) return;
    setRechecking(true);
    setCommandError(null);
    const result = await authorityQuery.refetch();
    if (!mountedRef.current) return;
    setRechecking(false);
    if (result.data !== undefined && result.data.ok) {
      setObservedAuthority(activeAuthority(result.data.model));
      setNotice(
        "已重新读取当前配置。输入和创建 ID 保持不变；请确认后再次明确创建。",
      );
    } else {
      setCommandError({
        kind: "local",
        message:
          "仍无法读取当前配置，因此没有更新创建所依据的 Active。请稍后重试；输入已保留。",
      });
      focusCommandError();
    }
  }

  function focusFirstIssue(issues: readonly CreateFormIssue[]) {
    const first = issues[0];
    if (first === undefined) return;
    if (first.fieldId === "automation-create-id") {
      if (diagnosticsRef.current !== null) diagnosticsRef.current.open = true;
    }
    window.requestAnimationFrame(() => {
      document.getElementById(first.fieldId)?.focus();
    });
  }

  function raiseLocalError(message: string) {
    setCommandError({ kind: "local", message });
    focusCommandError();
  }

  function submit() {
    if (
      form === null ||
      authorityModel === null ||
      submittingRef.current ||
      closing ||
      pendingPublication !== null
    ) {
      return;
    }
    setShowIssues(true);
    if (validationIssues.length > 0) {
      setCommandError(null);
      focusFirstIssue(validationIssues);
      return;
    }
    if (!principalIdentity.resolved) {
      raiseLocalError(
        principalIdentity.reason === "loading"
          ? "正在确认当前登录身份；确认后才能安全保留未决创建命令。请稍后重试。"
          : "当前登录身份暂不可用，暂时不能创建。请稍后刷新重试；输入已保留。",
      );
      return;
    }
    if (!authorityModel.actions.create) {
      raiseLocalError(
        "当前登录身份没有创建自动化任务的权限。没有提交任何配置修改；请使用有权限的身份重试。",
      );
      return;
    }
    if (observedAuthority === null) {
      raiseLocalError("当前 Active 配置尚未读取完成，不能创建。请刷新后重试。");
      return;
    }
    const candidate = buildCreateCandidate(form);
    if (candidate === null) {
      raiseLocalError("时间计划无法转换为现有字段，请检查后重试。");
      return;
    }
    const submittedForm = publicationFormFromCreateForm(form);
    const submittedAuthority = observedAuthority;
    setDiscardArmed(false);
    setPendingPublication({
      definitionId: form.id.trim(),
      action: "create",
      form: submittedForm,
      authority: submittedAuthority,
    });
    submittingRef.current = true;
    setSubmitting(true);
    setCommandError(null);
    setNotice(null);
    void createAutomationDefinitionFocused(token, {
      object: candidate,
      authority: {
        expectedRevisionId: submittedAuthority.revisionId,
        expectedVersion: submittedAuthority.version,
        expectedDigest: submittedAuthority.digest,
      },
    }).then((result) => {
      if (!mountedRef.current) return;
      submittingRef.current = false;
      setSubmitting(false);
      // A leave attempted while the command was still in flight is released
      // together with the result, so the operator sees the real outcome first.
      releaseBlockedNavigation();
      if (result.ok) {
        const definition = result.model.definition;
        setPendingPublication(null);
        setNotice("创建成功，尚未启用。");
        setDirty(false);
        bypassBlockerRef.current = true;
        if (definition !== null) onCreated(definition);
        beginExit(onClose);
        return;
      }
      if (
        result.status === 0 ||
        result.status >= 500 ||
        result.code === "malformed_response"
      ) {
        setCommandError({ kind: "unknown", code: result.code });
        focusCommandError();
        return;
      }
      // A proved rejection releases the retained command; the input and ID stay
      // exactly as submitted so a correction never masquerades as a retry.
      setPendingPublication(null);
      if (result.status === 409) {
        setCommandError({ kind: "conflict", code: result.code });
        focusCommandError();
        return;
      }
      setCommandError({
        kind: "rejected",
        code: result.code,
        details: result.details,
      });
      if (result.code === "automation_definition_invalid_field") {
        // The time plan is the only candidate part the ordinary controls do not
        // fully validate for the backend, so the correction is located there.
        const fieldId = scheduleFieldId(form.schedule);
        window.requestAnimationFrame(() => {
          const field = document.getElementById(fieldId);
          (field ?? document.getElementById(COMMAND_ERROR_ID))?.focus();
        });
        return;
      }
      focusCommandError();
    });
  }

  function reconcile() {
    if (
      pendingPublication === null ||
      reconciling ||
      submittingRef.current ||
      !principalIdentity.resolved
    ) {
      return;
    }
    setReconciling(true);
    setCommandError(null);
    void reconcileAutomationPublicationFocused(
      token,
      pendingPublication.definitionId,
      {
        action: pendingPublication.action,
        object: buildCandidateFromPublicationForm(pendingPublication.form),
        expectedRevisionId: pendingPublication.authority.revisionId,
        expectedVersion: pendingPublication.authority.version,
        expectedDigest: pendingPublication.authority.digest,
      },
    ).then((result) => {
      if (!mountedRef.current) return;
      setReconciling(false);
      if (
        result.ok &&
        result.model.state === "published" &&
        result.model.publication !== null
      ) {
        const definition = result.model.publication.definition;
        setPendingPublication(null);
        setNotice("已核对本次创建；结果已持久发布。");
        setDirty(false);
        bypassBlockerRef.current = true;
        if (definition !== null) onCreated(definition);
        beginExit(onClose);
        return;
      }
      if (result.ok) {
        setCommandError({ kind: "reconcile-unknown", code: null });
        focusCommandError();
        return;
      }
      setCommandError({ kind: "reconcile-unknown", code: result.code });
      focusCommandError();
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  const libraryOptions =
    authorityModel === null ? [] : enabledResourceLibraries(authorityModel);
  const inFlight = submitting || reconciling;
  const createDisabledReason =
    authorityModel === null
      ? "正在读取当前配置权限…"
      : !principalIdentity.resolved
        ? principalIdentity.reason === "loading"
          ? "正在确认当前登录身份…"
          : "当前登录身份暂不可用，暂时不能创建。"
        : !authorityModel.actions.create
          ? "当前登录身份没有创建自动化任务的权限。"
          : submitting
            ? "正在创建，请稍候；系统不会自动重发创建命令。"
            : pendingPublication !== null
              ? "请先核对上次创建结果；系统不会自动重发创建命令。"
              : idGenerationFailed
                ? "无法生成安全的内部 ID；系统不会使用弱随机或时间戳代替。"
                : libraryOptions.length === 0
                  ? "没有已启用的资源库。请先在资源库设置中启用一个资源库。"
                  : null;
  const scheduleRejected =
    commandError !== null &&
    commandError.kind === "rejected" &&
    commandError.code === "automation_definition_invalid_field";
  const commandErrorCopy =
    commandError === null ? null : commandErrorMessage(commandError);
  const hasAttention =
    submitting ||
    pendingPublication !== null ||
    discardPromptOpen ||
    commandError !== null ||
    notice !== null ||
    (showIssues && validationIssues.length > 0);

  const previewMissing = validationIssues
    .slice(0, 3)
    .map((issue) => issue.label)
    .filter((label, index, labels) => labels.indexOf(label) === index);

  return (
    <div
      ref={layerRef}
      className={
        closing
          ? "mf-automation-create-layer mf-automation-create-layer-exiting"
          : "mf-automation-create-layer"
      }
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) attemptClose();
      }}
      data-automation-create-dialog="true"
    >
      <div
        className="mf-automation-create-backdrop"
        aria-hidden="true"
        onMouseDown={(event) => {
          event.stopPropagation();
          attemptClose();
        }}
      />
      <section
        className="mf-automation-create-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="automation-create-title"
        aria-busy={submitting || reconciling}
      >
        <header className="mf-automation-create-header">
          <div>
            <h2 id="automation-create-title">新建自动化任务</h2>
            <p>
              设置来源与运行时间，创建后默认停用；不会扫描、整理或运行媒体文件。
            </p>
          </div>
          <button
            type="button"
            className="mf-automation-create-close"
            aria-label="关闭新建自动化任务"
            disabled={submitting || closing}
            onClick={attemptClose}
          >
            ×
          </button>
        </header>

        <div className="mf-automation-create-body">
          {authorityFailed !== null && (
            <div className="mf-automation-create-alert" role="alert">
              <strong>无法读取创建权限</strong>
              <p>
                {authorityFailed.status === 401
                  ? "登录已失效，请重新登录后再创建。"
                  : authorityFailed.status === 403
                    ? "当前身份没有读取或创建自动化任务的权限。"
                    : `读取当前配置失败（${authorityFailed.code}）。请刷新后重试；没有提交任何修改。`}
              </p>
            </div>
          )}
          {authorityQuery.isPending && (
            <p className="mf-automation-create-hint" role="status">
              正在读取当前配置与创建权限…
            </p>
          )}
          {authorityModel !== null && !principalIdentity.resolved && (
            <p className="mf-automation-create-hint" role="status">
              {principalIdentity.reason === "loading"
                ? "正在确认当前登录身份…"
                : "当前登录身份暂不可用。为避免未决结果归属不明，暂时不能创建；你仍可关闭此卡片。"}
            </p>
          )}

          {hasAttention && (
            <div
              className="mf-automation-create-attention"
              data-automation-create-attention="true"
            >
              {submitting && (
                <div className="mf-automation-create-pending" role="status">
                  <strong>正在创建…</strong>
                  <p>
                    创建命令已提交，正在等待后端确认。请稍候；系统不会自动重发。
                  </p>
                  {submitBlocked && (
                    <p>
                      已暂时阻止离开本页；收到结果后会在这里显示并解除这一限制。
                    </p>
                  )}
                </div>
              )}
              {pendingPublication !== null && !submitting && (
                <div className="mf-automation-create-pending" role="status">
                  <strong>上次创建结果待核对</strong>
                  <p>
                    创建命令可能已经生效。系统不会自动重发；请使用底部的“核对本次创建”读取真实持久结果。
                    关闭后再次打开会继续保留这次命令身份。
                  </p>
                </div>
              )}
              {discardPromptOpen && (
                <div
                  className="mf-automation-create-discard"
                  role="alertdialog"
                  aria-labelledby="automation-create-discard-question"
                  aria-describedby="automation-create-discard-detail"
                >
                  <p id="automation-create-discard-question">
                    表单中有未保存的输入；关闭会丢弃这些修改。
                  </p>
                  <p
                    className="mf-automation-create-hint"
                    id="automation-create-discard-detail"
                  >
                    选择「继续填写」保留当前输入并回到原字段；选择「放弃修改」返回自动化列表。
                  </p>
                  <div className="mf-actions">
                    <Button
                      type="button"
                      variant="secondary"
                      id={DISCARD_CONTINUE_ID}
                      onClick={cancelDiscard}
                    >
                      继续填写
                    </Button>
                    <Button type="button" onClick={commitClose}>
                      放弃修改
                    </Button>
                  </div>
                </div>
              )}
              {commandError !== null && commandErrorCopy !== null && (
                <div
                  className="mf-automation-create-alert"
                  id={COMMAND_ERROR_ID}
                  role="alert"
                  tabIndex={-1}
                >
                  <strong>{commandErrorCopy.title}</strong>
                  <p>{commandErrorCopy.body}</p>
                  {commandError.kind === "rejected" && (
                    <p className="mf-automation-create-hint">
                      后端返回码：{commandError.code}（仅用于诊断）
                    </p>
                  )}
                  {commandError.kind === "reconcile-unknown" &&
                    commandError.code !== null && (
                      <p className="mf-automation-create-hint">
                        核对返回：{commandError.code}
                      </p>
                    )}
                  {scheduleRejected && form !== null && (
                    <div className="mf-actions">
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() => {
                          window.requestAnimationFrame(() => {
                            document
                              .getElementById(scheduleFieldId(form.schedule))
                              ?.focus();
                          });
                        }}
                      >
                        检查时间计划
                      </Button>
                    </div>
                  )}
                  {commandError.kind === "conflict" &&
                    commandError.code !== "automation_definition_duplicate" && (
                      <div className="mf-actions">
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={rechecking || closing}
                          onClick={() => {
                            void recheckAuthority();
                          }}
                        >
                          {rechecking ? "重新核对中…" : "重新核对当前配置"}
                        </Button>
                      </div>
                    )}
                  {commandError.kind === "conflict" &&
                    commandError.code === "automation_definition_duplicate" && (
                      <div className="mf-actions">
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={regenerateId}
                        >
                          重新生成内部 ID
                        </Button>
                      </div>
                    )}
                </div>
              )}
              {notice !== null && (
                <p className="mf-automation-create-notice" role="status">
                  {notice}
                </p>
              )}
              {showIssues &&
                validationIssues.length > 0 &&
                commandError === null && (
                  <div className="mf-automation-create-alert" role="alert">
                    <strong>有 {validationIssues.length} 处输入需要修正</strong>
                    <ul>
                      {validationIssues.map((issue) => (
                        <li key={`${issue.fieldId}:${issue.message}`}>
                          {issue.label}：{issue.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
            </div>
          )}

          {form !== null && authorityModel !== null && (
            <form
              className="mf-automation-create-form"
              onSubmit={handleSubmit}
              noValidate
            >
              <div className="mf-automation-create-scroll">
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
                        maxLength={authorityModel.limits.name}
                        autoComplete="off"
                        aria-required="true"
                        aria-invalid={
                          showIssues &&
                          validationIssues.some(
                            (issue) =>
                              issue.fieldId === "automation-create-name",
                          )
                        }
                        aria-describedby={
                          showIssues &&
                          validationIssues.some(
                            (issue) =>
                              issue.fieldId === "automation-create-name",
                          )
                            ? "automation-create-name-error"
                            : undefined
                        }
                        onChange={(event) =>
                          updateFields({ name: event.target.value })
                        }
                      />
                      <p className="mf-automation-create-hint">
                        用于在任务列表中识别这次自动整理。
                      </p>
                      {showIssues &&
                        validationIssues
                          .filter(
                            (issue) =>
                              issue.fieldId === "automation-create-name",
                          )
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
                        aria-invalid={
                          showIssues &&
                          validationIssues.some(
                            (issue) =>
                              issue.fieldId === "automation-create-library",
                          )
                        }
                        onChange={(event) => changeLibrary(event.target.value)}
                      >
                        <option value="">请选择资源库</option>
                        {authorityModel.resourceLibraries.map((option) => (
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
                        validationIssues
                          .filter(
                            (issue) =>
                              issue.fieldId === "automation-create-library",
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
                      <label htmlFor="automation-create-scope-mode">
                        来源范围
                      </label>
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
                              event.target.value === "root"
                                ? ""
                                : form.sourceScope,
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
                        <label htmlFor="automation-create-scope">
                          来源子目录
                        </label>
                        <div className="mf-automation-create-inline">
                          <input
                            id="automation-create-scope"
                            type="text"
                            value={form.sourceScope}
                            placeholder="例如：电影/华语"
                            aria-required="true"
                            aria-invalid={
                              showIssues &&
                              validationIssues.some(
                                (issue) =>
                                  issue.fieldId === "automation-create-scope",
                              )
                            }
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
                          也可以直接输入资源库内的相对路径；不能以斜杠开头或包含
                          ..。
                        </p>
                        {showIssues &&
                          validationIssues
                            .filter(
                              (issue) =>
                                issue.fieldId === "automation-create-scope",
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
                          <p
                            className="mf-automation-create-hint"
                            role="status"
                          >
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
                        {directoryFailure === null &&
                          !directoryQuery.isPending && (
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
                                            onClick={() =>
                                              setBrowserPath(entry.path)
                                            }
                                          >
                                            进入
                                          </Button>
                                          <Button
                                            type="button"
                                            onClick={() =>
                                              chooseDirectory(entry.path)
                                            }
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
                          <Button
                            type="button"
                            onClick={() => chooseDirectory("")}
                          >
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
                    <div
                      className="mf-automation-create-schedule-error"
                      role="alert"
                    >
                      <strong>后端拒绝了当前时间计划</strong>
                      <p>
                        请检查下面“执行频率”对应的 Cron 表达式与 IANA
                        时区；输入和内部 ID 已保留，修正后可再次明确创建。
                      </p>
                    </div>
                  )}
                  <div className="mf-automation-create-grid">
                    <div className="mf-automation-create-field">
                      <label htmlFor="automation-create-schedule-kind">
                        执行频率
                      </label>
                      <select
                        id="automation-create-schedule-kind"
                        value={form.schedule}
                        onChange={(event) =>
                          updateSchedule(
                            event.target.value as CreateScheduleKind,
                          )
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
                        <label htmlFor="automation-create-interval">
                          执行间隔
                        </label>
                        <div className="mf-automation-create-inline">
                          <input
                            id="automation-create-interval"
                            type="text"
                            inputMode="decimal"
                            value={form.intervalValue}
                            aria-required="true"
                            aria-invalid={
                              showIssues &&
                              validationIssues.some(
                                (issue) =>
                                  issue.fieldId ===
                                  "automation-create-interval",
                              )
                            }
                            onChange={(event) =>
                              updateFields({
                                intervalValue: event.target.value,
                              })
                            }
                          />
                          <select
                            aria-label="间隔单位"
                            value={form.intervalUnit}
                            onChange={(event) =>
                              updateFields({
                                intervalUnit: event.target
                                  .value as IntervalUnit,
                              })
                            }
                          >
                            <option value="seconds">秒</option>
                            <option value="minutes">分钟</option>
                            <option value="hours">小时</option>
                          </select>
                        </div>
                        <p className="mf-automation-create-hint">
                          默认每隔 1 小时；支持小数，例如 1.5 小时会转换为 5400
                          秒。
                        </p>
                        {showIssues &&
                          validationIssues
                            .filter(
                              (issue) =>
                                issue.fieldId === "automation-create-interval",
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
                        <label htmlFor="automation-create-daily-time">
                          每天运行时间
                        </label>
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
                          validationIssues
                            .filter(
                              (issue) =>
                                issue.fieldId ===
                                "automation-create-daily-time",
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
                          <label htmlFor="automation-create-weekly-day">
                            每周星期
                          </label>
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
                          <label htmlFor="automation-create-weekly-time">
                            运行时间
                          </label>
                          <input
                            id="automation-create-weekly-time"
                            type="time"
                            value={form.weeklyTime}
                            onChange={(event) =>
                              updateFields({ weeklyTime: event.target.value })
                            }
                          />
                          {showIssues &&
                            validationIssues
                              .filter(
                                (issue) =>
                                  issue.fieldId ===
                                  "automation-create-weekly-time",
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
                        <label htmlFor="automation-create-cron">
                          Cron 表达式
                        </label>
                        <input
                          id="automation-create-cron"
                          type="text"
                          value={form.cron}
                          placeholder="0 8 * * *"
                          aria-required="true"
                          aria-invalid={
                            scheduleRejected ||
                            (showIssues &&
                              validationIssues.some(
                                (issue) =>
                                  issue.fieldId === "automation-create-cron",
                              ))
                          }
                          aria-describedby="automation-create-cron-error"
                          onChange={(event) =>
                            updateFields({ cron: event.target.value })
                          }
                        />
                        <p className="mf-automation-create-hint">
                          使用后端支持的五段
                          Cron；这里只检查格式与取值范围，不会自行计算实际触发时间。
                        </p>
                        {showIssues &&
                          validationIssues
                            .filter(
                              (issue) =>
                                issue.fieldId === "automation-create-cron",
                            )
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
                          validationIssues
                            .filter(
                              (issue) =>
                                issue.fieldId === "automation-create-timezone",
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
                          ）；这不阻止创建，创建仍由后端校验。
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
                              后端没有返回即将运行的时间；创建后请核对配置。
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
                        时间计划仅在启用后生效；当前创建为未启用状态，不会自动运行。
                      </p>
                    </div>
                  </div>
                </section>

                <section
                  className="mf-automation-create-section"
                  aria-labelledby="automation-create-limits"
                >
                  <h3 id="automation-create-limits">处理限制</h3>
                  <div className="mf-automation-create-grid">
                    <div className="mf-automation-create-field">
                      <label htmlFor="automation-create-limit">处理上限</label>
                      <input
                        id="automation-create-limit"
                        type="text"
                        inputMode="numeric"
                        value={form.itemLimit}
                        aria-required="true"
                        aria-invalid={
                          showIssues &&
                          validationIssues.some(
                            (issue) =>
                              issue.fieldId === "automation-create-limit",
                          )
                        }
                        onChange={(event) =>
                          updateFields({ itemLimit: event.target.value })
                        }
                      />
                      <p className="mf-automation-create-hint">
                        限制单次来源范围最多处理的数量（
                        {authorityModel.limits.itemLimitMinimum}–
                        {authorityModel.limits.itemLimitMaximum}
                        ）。超过上限时需要缩小来源范围；系统不会自动分批，也不会只处理前
                        N 个。
                      </p>
                      {showIssues &&
                        validationIssues
                          .filter(
                            (issue) =>
                              issue.fieldId === "automation-create-limit",
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
                      <span className="mf-automation-create-label">
                        创建后的状态
                      </span>
                      <p className="mf-automation-create-status">未启用</p>
                      <p className="mf-automation-create-hint">
                        创建后可在任务列表中启用或运行一次；创建本身不会启用、运行或授权。
                      </p>
                    </div>
                  </div>
                </section>

                <details
                  className="mf-automation-create-diagnostics"
                  ref={diagnosticsRef}
                >
                  <summary>诊断信息（内部 ID 与发布机制）</summary>
                  <dl>
                    <dt>内部 ID</dt>
                    <dd>
                      <code id="automation-create-id" tabIndex={-1}>
                        {form.id.length > 0 ? form.id : "未生成"}
                      </code>{" "}
                      {pendingPublication === null && (
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={submitting || closing}
                          onClick={regenerateId}
                        >
                          重新生成 ID
                        </Button>
                      )}
                    </dd>
                    <dt>创建依据的 Active</dt>
                    <dd>
                      <code>{observedAuthority?.revisionId ?? "尚未读取"}</code>
                      {observedAuthority !== null && (
                        <>
                          {" "}
                          · 版本 {observedAuthority.version} · digest{" "}
                          <code className="mf-automation-create-digest">
                            {observedAuthority.digest}
                          </code>
                        </>
                      )}
                    </dd>
                    <dt>发布机制</dt>
                    <dd>
                      一次明确创建直接提交经过后端校验的候选并原子发布；不创建
                      Draft，不单独启用或运行。
                    </dd>
                  </dl>
                </details>
              </div>

              <footer className="mf-automation-create-footer">
                <div className="mf-automation-create-footer-note">
                  {createDisabledReason !== null && (
                    <span role="status">{createDisabledReason}</span>
                  )}
                  {createDisabledReason === null &&
                    pendingPublication === null && (
                      <span>创建后未启用，可在列表中启用或运行一次。</span>
                    )}
                </div>
                <div className="mf-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={inFlight || closing}
                    onClick={attemptClose}
                  >
                    {pendingPublication !== null && !submitting
                      ? "关闭"
                      : "取消"}
                  </Button>
                  {submitting ? (
                    <Button
                      type="button"
                      data-automation-create-primary="true"
                      disabled
                    >
                      创建中…
                    </Button>
                  ) : pendingPublication !== null ? (
                    <Button
                      type="button"
                      data-automation-create-primary="true"
                      disabled={
                        reconciling || closing || !principalIdentity.resolved
                      }
                      onClick={reconcile}
                    >
                      {reconciling ? "核对中…" : "核对本次创建"}
                    </Button>
                  ) : (
                    <Button
                      type="submit"
                      data-automation-create-primary="true"
                      disabled={
                        createDisabledReason !== null || submitting || closing
                      }
                    >
                      创建任务
                    </Button>
                  )}
                </div>
              </footer>
            </form>
          )}

          {form === null && (
            <div className="mf-automation-create-footer">
              <Button
                type="button"
                variant="secondary"
                disabled={closing}
                onClick={attemptClose}
              >
                关闭
              </Button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
