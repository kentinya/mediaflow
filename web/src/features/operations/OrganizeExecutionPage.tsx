/**
 * Durable manual Organize execution outcome.
 *
 * The page shows the aggregate admission/worker/terminal state, every selected
 * and unselected item identity, known completed effects, effect certainty, the
 * linked Task/TaskItem/Result identities and the current next action. It never
 * replays uncertain work automatically: a failure links to the Task and to
 * Review & Recovery/V1 instead.
 */

import { useState } from "react";
import { Link, useParams, useSearch } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { reconcileOrganizeExecutionFileIndex } from "../../shared/api/api-client";
import { organizeExecutionQueryOptions } from "./organize-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import {
  filesReturnHref,
  readFilesReturnContext,
} from "../../shared/navigation/files-return";
import type { OrganizeFileIndexReconciliationState } from "../../entities/operations/organize";

const RECONCILIATION_STATE_LABELS: Readonly<
  Record<OrganizeFileIndexReconciliationState, string>
> = {
  synchronized: "已同步",
  no_matching_occurrence: "索引中没有匹配的当前条目",
  attention_required: "需要人工核对",
  pending: "等待结果",
};

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

export function OrganizeExecutionPage() {
  const { executionId } = useParams({
    from: "/operations/organize/execution/$executionId",
  });
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const filesReturn = readFilesReturnContext(searchParams);
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const [reconciliationNotice, setReconciliationNotice] = useState<
    string | null
  >(null);
  const executionQuery = useQuery(
    organizeExecutionQueryOptions(token, executionId),
  );
  const reconciliationMutation = useMutation({
    mutationFn: (itemId: string) =>
      reconcileOrganizeExecutionFileIndex(token, { executionId, itemId }),
    retry: false,
    onMutate: () => setReconciliationNotice(null),
    onSuccess: (value) => {
      if (value.ok) {
        setReconciliationNotice(
          `索引核对已重试（${value.state}）。整理结果不会重放。`,
        );
        void queryClient.invalidateQueries({
          queryKey: organizeExecutionQueryOptions(token, executionId).queryKey,
        });
        return;
      }
      setReconciliationNotice(
        value.nextAction ??
          `索引核对未完成（${value.code}）；已完成的整理结果保持不变。`,
      );
    },
    onError: () => {
      setReconciliationNotice("索引核对未完成；已完成的整理结果保持不变。");
    },
  });

  return (
    <AuthorizedReadBoundary
      query={executionQuery}
      unavailableTitle="Execution unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading durable execution">
              <p>Reading the admitted exact execution and its outcomes.</p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                >
                  Back to Operations
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const execution = data.model;
        const terminal = [
          "completed",
          "partial_success",
          "failed",
          "cancelled",
        ].includes(execution.status);
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Manual organize execution</h2>
                <p className="mf-dashboard-meta">
                  Execution {execution.executionId} ·{" "}
                  {displayEnum(execution.status)} · Task {execution.taskId}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Admission and Worker state</h3>
              <dl>
                <dt>Durable state</dt>
                <dd>{displayEnum(execution.durableState)}</dd>
                <dt>Items</dt>
                <dd>
                  {execution.selectedItemCount} selected ·{" "}
                  {execution.unselectedItemCount} unselected ·{" "}
                  {execution.completedItemCount} verified ·{" "}
                  {execution.failedItemCount} failed
                </dd>
                <dt>Destructive authority</dt>
                <dd>
                  overwrite{" "}
                  {execution.allowOverwrite ? "authorized" : "not authorized"} ·
                  source cleanup{" "}
                  {execution.allowSourceCleanup
                    ? "authorized"
                    : "not authorized"}
                </dd>
                <dt>Admitted</dt>
                <dd>{execution.createdAt}</dd>
                <dt>Last update</dt>
                <dd>{execution.updatedAt}</dd>
              </dl>
              <p className="mf-dashboard-meta">{execution.nextAction}</p>
              <p className="mf-dashboard-meta">
                {execution.knownEffects.statement}
              </p>
            </section>
            {execution.failure !== null && (
              <StatusBanner variant="error" title="Execution finding">
                <p>{execution.failure.message}</p>
                <p className="mf-dashboard-meta">
                  {execution.failure.nextAction}
                </p>
              </StatusBanner>
            )}
            {execution.items.map((item) => (
              <section className="mf-count-section" key={item.itemId}>
                <h3>
                  {item.itemId}{" "}
                  <span className="mf-status-badge">
                    {displayEnum(item.status)}
                  </span>
                </h3>
                <dl>
                  <dt>Stage</dt>
                  <dd>{displayEnum(item.stage ?? "unknown")}</dd>
                  <dt>Effect certainty</dt>
                  <dd>{displayEnum(item.effectCertainty ?? "unknown")}</dd>
                  <dt>Completed operations</dt>
                  <dd>
                    {item.completedOperations.length === 0
                      ? "none"
                      : item.completedOperations.join(", ")}
                  </dd>
                  <dt>Uncertain effects</dt>
                  <dd>
                    {item.uncertainEffects.length === 0
                      ? "none"
                      : item.uncertainEffects.join(", ")}
                  </dd>
                  <dt>Result</dt>
                  <dd>{safeValue(item.resultId)}</dd>
                  <dt>TaskItem</dt>
                  <dd>{safeValue(item.taskItemId)}</dd>
                </dl>
                {item.effects.length > 0 && (
                  <ul>
                    {item.effects.map((effect, position) => (
                      <li key={`${item.itemId}-${position}`}>
                        {displayEnum(effect.action ?? "effect")} ·{" "}
                        {effect.verified ? "verified" : "unverified"} ·{" "}
                        {safeValue(effect.sourceLocation)} →{" "}
                        {safeValue(effect.destinationLocation)}
                      </li>
                    ))}
                  </ul>
                )}
                {item.failure !== null && (
                  <StatusBanner variant="error" title="Item finding">
                    <p>{item.failure.message}</p>
                    <p className="mf-dashboard-meta">
                      {item.failure.nextAction}
                    </p>
                  </StatusBanner>
                )}
                {item.nextAction && (
                  <p className="mf-dashboard-meta">{item.nextAction}</p>
                )}
                {item.fileIndexReconciliation !== null && (
                  <div className="mf-reconciliation">
                    <p className="mf-dashboard-meta">
                      文件索引核对：
                      {
                        RECONCILIATION_STATE_LABELS[
                          item.fileIndexReconciliation.state
                        ]
                      }
                    </p>
                    {item.fileIndexReconciliation.nextAction && (
                      <p className="mf-dashboard-meta">
                        {item.fileIndexReconciliation.nextAction}
                      </p>
                    )}
                    {item.fileIndexReconciliation.action?.available ===
                      true && (
                      <Button
                        type="button"
                        disabled={reconciliationMutation.isPending}
                        onClick={() =>
                          reconciliationMutation.mutate(item.itemId)
                        }
                      >
                        {reconciliationMutation.isPending
                          ? "正在核对索引…"
                          : "重新核对文件索引"}
                      </Button>
                    )}
                  </div>
                )}
              </section>
            ))}
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/tasks/$taskId"
                params={{ taskId: execution.taskId }}
              >
                Open the durable Task
              </Link>
              {execution.actions.recovery.available && (
                <Link className="mf-button mf-button-secondary" to="/review">
                  Open Review &amp; Recovery
                </Link>
              )}
              {execution.previewId && (
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/organize/preview/$previewId"
                  params={{ previewId: execution.previewId }}
                >
                  Back to the reviewed Preview
                </Link>
              )}
              {filesReturn !== null && (
                <Link
                  className="mf-button mf-button-secondary"
                  to={filesReturnHref(filesReturn)}
                >
                  返回文件
                </Link>
              )}
              <Link className="mf-button mf-button-secondary" to="/operations">
                Back to Operations
              </Link>
            </div>
            {reconciliationNotice !== null && (
              <StatusBanner variant="info" title="文件索引核对">
                <p>{reconciliationNotice}</p>
              </StatusBanner>
            )}
            {!terminal && (
              <p className="mf-dashboard-meta">
                This execution is not terminal yet. Refresh to read the current
                durable state; no action is replayed automatically.
              </p>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
