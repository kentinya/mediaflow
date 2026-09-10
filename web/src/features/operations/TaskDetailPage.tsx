/**
 * Task detail page: separates aggregate progress from independent TaskItems
 * and Results. Shows pinned configuration, source/effect/failure facts and
 * lifecycle controls.
 *
 * Items and Results are independently paged. Successful siblings remain visible
 * and terminal. Uncertain effects are never labelled safe to retry.
 */

import { useCallback, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import type { TaskItemStatus } from "../../entities/operations/task";
import { taskLifecycleActions } from "../../entities/operations/task";
import {
  mutateTaskCancel,
  mutateTaskPause,
  mutateTaskResume,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { taskDetailQueryOptions, taskListQueryKey } from "./task-query";

function StatusBadge({ status }: { readonly status: string }) {
  return <span className="mf-status-badge">{status}</span>;
}

function TaskItemRow({
  item,
}: {
  readonly item: {
    itemId: string;
    sourceDisplay: string;
    status: TaskItemStatus;
    stage: string;
    attempts: number;
    error: string | null;
    destinationPath: string | null;
  };
}) {
  return (
    <tr>
      <td>{item.itemId}</td>
      <td>{item.sourceDisplay}</td>
      <td>
        <StatusBadge status={item.status} />
      </td>
      <td>{item.stage}</td>
      <td>{item.attempts}</td>
      <td>{item.destinationPath ?? "—"}</td>
      <td>{item.error ?? "—"}</td>
    </tr>
  );
}

function TaskResultRow({
  result,
}: {
  readonly result: {
    resultId: string;
    sourcePath: string;
    status: string;
    operation: string | null;
    effectCertainty: string;
    destinationPath: string | null;
    error: string | null;
  };
}) {
  return (
    <tr>
      <td>{result.resultId}</td>
      <td>{result.sourcePath}</td>
      <td>
        <StatusBadge status={result.status} />
      </td>
      <td>{result.operation ?? "—"}</td>
      <td>{result.effectCertainty}</td>
      <td>{result.destinationPath ?? "—"}</td>
      <td>{result.error ?? "—"}</td>
    </tr>
  );
}

export function TaskDetailPage() {
  const { taskId } = useParams({ strict: false }) as { taskId: string };
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const [itemCursor, setItemCursor] = useState<string | null>(null);
  const [resultCursor, setResultCursor] = useState<string | null>(null);
  const [itemDirection, setItemDirection] = useState<"forward" | "backward">(
    "forward",
  );
  const [resultDirection, setResultDirection] = useState<
    "forward" | "backward"
  >("forward");

  const query = useQuery(
    taskDetailQueryOptions(token, {
      taskId,
      itemLimit: 20,
      resultLimit: 20,
      itemCursor: itemDirection === "forward" ? itemCursor : undefined,
      resultCursor: resultDirection === "forward" ? resultCursor : undefined,
    }),
  );

  const cancelMutation = useMutation({
    mutationFn: () => mutateTaskCancel(token, taskId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [taskListQueryKey],
      });
      void query.refetch();
    },
  });

  const pauseMutation = useMutation({
    mutationFn: () => mutateTaskPause(token, taskId),
    onSuccess: () => void query.refetch(),
  });

  const resumeMutation = useMutation({
    mutationFn: () => mutateTaskResume(token, taskId),
    onSuccess: () => void query.refetch(),
  });

  const goItemsForward = useCallback(() => {
    if (query.data?.ok === true && query.data.model.nextItemCursor) {
      setItemCursor(query.data.model.nextItemCursor);
      setItemDirection("forward");
    }
  }, [query.data]);

  const goItemsBackward = useCallback(() => {
    if (query.data?.ok === true && query.data.model.previousItemCursor) {
      setItemCursor(query.data.model.previousItemCursor);
      setItemDirection("backward");
    }
  }, [query.data]);

  const goResultsForward = useCallback(() => {
    if (query.data?.ok === true && query.data.model.nextResultCursor) {
      setResultCursor(query.data.model.nextResultCursor);
      setResultDirection("forward");
    }
  }, [query.data]);

  const goResultsBackward = useCallback(() => {
    if (query.data?.ok === true && query.data.model.previousResultCursor) {
      setResultCursor(query.data.model.previousResultCursor);
      setResultDirection("backward");
    }
  }, [query.data]);

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Task detail unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Task detail">
              <p>Requesting the Task and its items/results from the API.</p>
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
                  to="/operations/tasks"
                >
                  Back to Tasks
                </Link>
              </div>
            </StatusBanner>
          );
        }
        const { task, items, results } = data.model;
        const actions = taskLifecycleActions(task);
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <h2>Task {task.taskId}</h2>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Task overview</h3>
              <dl>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={task.status} />
                </dd>
                <dt>Command</dt>
                <dd>{task.command}</dd>
                <dt>Items</dt>
                <dd>
                  {task.completedItems} / {task.totalItems} completed
                  {task.failedItems > 0 ? ` (${task.failedItems} failed)` : ""}
                </dd>
                <dt>Created</dt>
                <dd>{task.createdAt}</dd>
                {task.startedAt && (
                  <>
                    <dt>Started</dt>
                    <dd>{task.startedAt}</dd>
                  </>
                )}
                {task.completedAt && (
                  <>
                    <dt>Completed</dt>
                    <dd>{task.completedAt}</dd>
                  </>
                )}
                {task.configurationSnapshotId && (
                  <>
                    <dt>Configuration snapshot</dt>
                    <dd>{task.configurationSnapshotId}</dd>
                  </>
                )}
                {task.error && (
                  <>
                    <dt>Error</dt>
                    <dd>{task.error}</dd>
                  </>
                )}
                {task.pauseRequested && (
                  <>
                    <dt>Pause requested</dt>
                    <dd>
                      Yes — cooperative pause pending at next item boundary
                    </dd>
                  </>
                )}
              </dl>
            </section>
            <section className="mf-count-section">
              <h3>Lifecycle controls</h3>
              <div className="mf-actions">
                {actions.cancel && (
                  <button
                    type="button"
                    className="mf-button mf-button-secondary"
                    disabled={cancelMutation.isPending}
                    onClick={() => cancelMutation.mutate()}
                  >
                    {cancelMutation.isPending ? "Cancelling…" : "Cancel"}
                  </button>
                )}
                {actions.pause && (
                  <button
                    type="button"
                    className="mf-button mf-button-secondary"
                    disabled={pauseMutation.isPending}
                    onClick={() => pauseMutation.mutate()}
                  >
                    {pauseMutation.isPending ? "Requesting pause…" : "Pause"}
                  </button>
                )}
                {actions.resume && (
                  <button
                    type="button"
                    className="mf-button mf-button-primary"
                    disabled={resumeMutation.isPending}
                    onClick={() => resumeMutation.mutate()}
                  >
                    {resumeMutation.isPending ? "Resuming…" : "Resume"}
                  </button>
                )}
                {!actions.cancel && !actions.pause && !actions.resume && (
                  <p className="mf-dashboard-meta">
                    No lifecycle controls available for this task state.
                  </p>
                )}
              </div>
              {cancelMutation.isError && (
                <StatusBanner variant="error" title="Cancel failed">
                  <p>The cancel request was rejected. Reload and try again.</p>
                </StatusBanner>
              )}
              {pauseMutation.isError && (
                <StatusBanner variant="error" title="Pause failed">
                  <p>The pause request was rejected. Reload and try again.</p>
                </StatusBanner>
              )}
              {resumeMutation.isError && (
                <StatusBanner variant="error" title="Resume failed">
                  <p>The resume request was rejected. Reload and try again.</p>
                </StatusBanner>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Task items ({items.length})</h3>
              {items.length === 0 ? (
                <p className="mf-dashboard-meta">No items on this page.</p>
              ) : (
                <>
                  <div style={{ overflowX: "auto" }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Item ID</th>
                          <th>Source</th>
                          <th>Status</th>
                          <th>Stage</th>
                          <th>Attempts</th>
                          <th>Destination</th>
                          <th>Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((item) => (
                          <TaskItemRow key={item.itemId} item={item} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mf-actions">
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={!data.model.previousItemCursor}
                      onClick={goItemsBackward}
                    >
                      Previous items
                    </button>
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={!data.model.itemsTruncated}
                      onClick={goItemsForward}
                    >
                      Next items
                    </button>
                  </div>
                </>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Results ({results.length})</h3>
              {results.length === 0 ? (
                <p className="mf-dashboard-meta">No results on this page.</p>
              ) : (
                <>
                  <div style={{ overflowX: "auto" }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Result ID</th>
                          <th>Source</th>
                          <th>Status</th>
                          <th>Operation</th>
                          <th>Effect certainty</th>
                          <th>Destination</th>
                          <th>Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.map((result) => (
                          <TaskResultRow
                            key={result.resultId}
                            result={result}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mf-actions">
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={!data.model.previousResultCursor}
                      onClick={goResultsBackward}
                    >
                      Previous results
                    </button>
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={!data.model.resultsTruncated}
                      onClick={goResultsForward}
                    >
                      Next results
                    </button>
                  </div>
                </>
              )}
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/tasks"
              >
                Back to Tasks
              </Link>
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
