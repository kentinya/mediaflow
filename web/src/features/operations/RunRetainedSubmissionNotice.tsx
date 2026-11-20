/**
 * One-line, read-only reconciliation feedback inside a Task detail.
 *
 * The former "原整理提交" card listed every accepted submission and required a
 * manual admission read per record. The durable record still exists, but the
 * Task detail now only speaks when this browser actually holds a retained
 * confirmation for this Task's own Files preparation. In that case it resumes
 * the bounded, deduplicated read automatically and shows one line; opening any
 * ordinary Task performs no per-submission query.
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { operationsLandingSearch } from "../../shared/navigation/operations-return";
import type { OrganizeAdmissionOutcomeRead } from "../../shared/api/api-client";
import type { RunSummary } from "../../entities/operations/run";
import { usePrincipalIdentity } from "./principal-identity-query";
import {
  useOrganizeAdmissionWatchGroup,
  type OrganizeAdmissionWatchEntry,
} from "./organize-admission-watch";
import {
  clearOrganizeConfirmation,
  organizeConfirmationKey,
  readOrganizeConfirmations,
  type OrganizeConfirmationWork,
  type RetainedOrganizeConfirmation,
} from "./organize-confirmation-session";

export function RunRetainedSubmissionNotice({
  run,
}: {
  readonly run: RunSummary;
}) {
  const token = useAuthToken();
  const principalIdentity = usePrincipalIdentity();
  const principalId =
    principalIdentity.resolved === true ? principalIdentity.principalId : null;
  const discoveryId = run.filesPreparation?.discoveryId ?? null;
  const [retained, setRetained] = useState<
    readonly RetainedOrganizeConfirmation[]
  >([]);
  const [proven, setProven] = useState<{
    readonly taskId: string | null;
    readonly status: string | null;
  } | null>(null);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    // This is a read of browser-retained external state after the exact
    // principal/work context changed, not derived render state.
    if (principalId === null || discoveryId === null) {
      setRetained([]);
      return;
    }
    setRetained(
      readOrganizeConfirmations(principalId, {
        kind: "files",
        discoveryId,
      }),
    );
    setProven(null);
  }, [principalId, discoveryId]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const work: OrganizeConfirmationWork | null =
    discoveryId === null ? null : { kind: "files", discoveryId };
  const entries: readonly OrganizeAdmissionWatchEntry[] = useMemo(
    () =>
      retained.map((entry) => ({
        key: organizeConfirmationKey(entry.work, entry.submission),
        submission: entry.submission,
        workId: discoveryId ?? "",
      })),
    [retained, discoveryId],
  );
  const handleOutcome = (
    entry: OrganizeAdmissionWatchEntry,
    outcome: OrganizeAdmissionOutcomeRead,
  ) => {
    if (principalId === null || work === null) return;
    if (!outcome.ok) return;
    const model = outcome.model;
    if (model.outcome === "known") {
      if (model.taskId !== null && model.taskId !== "") {
        clearOrganizeConfirmation(principalId, work, entry.submission);
        setRetained(readOrganizeConfirmations(principalId, work));
        setProven({ taskId: model.taskId, status: model.status });
        return;
      }
      // Admitted, but this answer cannot prove the Task identity. Keep the
      // retained request and never guess a run.
      setProven({ taskId: null, status: model.status });
    }
  };
  const watch = useOrganizeAdmissionWatchGroup({
    enabled:
      principalId !== null &&
      discoveryId !== null &&
      entries.length > 0 &&
      proven === null,
    token,
    principalId,
    entries,
    onOutcome: handleOutcome,
  });

  if (proven !== null) {
    if (proven.taskId === null) {
      return (
        <p className="mf-run-flow-line" role="status">
          原整理提交已受理，但本次读取未携带可核对的任务身份；未跳转或选择其他任务。
        </p>
      );
    }
    return (
      <p className="mf-run-flow-line" role="status">
        已受理 ·{" "}
        <Link
          className="mf-link"
          to="/operations"
          search={operationsLandingSearch(null, proven.taskId)}
        >
          查看任务
        </Link>
        {proven.status === null ? "（执行状态待读取）" : ""}
      </p>
    );
  }
  if (entries.length === 0) return null;

  const state = watch.states.get(entries[0]?.key ?? "");
  const text =
    state === undefined
      ? "正在自动核对原整理提交是否受理…"
      : state.phase === "checking"
        ? "正在自动核对原整理提交是否受理…"
        : state.phase === "known"
          ? "原整理提交已受理，但本次读取未携带任务身份；请稍后重新打开任务核对。"
          : state.phase === "not_equivalent"
            ? "原整理提交的受理证据不一致；本页没有重发提交，请核对持久记录。"
            : state.phase === "failed"
              ? state.exhausted
                ? "原整理提交暂未确认；恢复连接或重新打开任务后会继续只读核对。"
                : "原整理提交暂未确认；读取暂时失败，本页会继续只读核对。"
              : state.exhausted
                ? "原整理提交暂未确认；恢复连接或重新打开任务后会继续只读核对。"
                : "原整理提交暂未确认；本页会继续只读核对，不会重发。";
  return (
    <p className="mf-run-flow-line" role="status">
      {text}
    </p>
  );
}
