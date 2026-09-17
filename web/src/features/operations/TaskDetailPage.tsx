/**
 * Task detail page: separates the Task aggregate from independently paged
 * TaskItems and Results, shows pinned configuration and bounded
 * source/effect/failure facts, and renders only the lifecycle controls the
 * backend advertises for this exact Task version and principal.
 *
 * Successful siblings remain visible and terminal; an uncertain effect is
 * never labelled safe to repeat, and a rejected control is never replayed.
 */

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { isTerminalTaskStatus } from "../../entities/operations/task";
import {
  availableLifecycleAction,
  type LifecycleAction,
  type LifecycleProjection,
} from "../../entities/operations/lifecycle";
import {
  mutateLifecycle,
  type LifecycleMutationResult,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { taskDetailQueryOptions, taskListQueryKey } from "./task-query";

/** Bounded operator copy per normalized lifecycle rejection reason. */
const LIFECYCLE_REJECTION_COPY: Readonly<Record<string, string>> = {
  stale_task_state:
    "This Task changed after the page was loaded. Reload the Task, review its current state, and submit again deliberately.",
  lifecycle_conflict:
    "The backend refused this control for the current Task state. Reload the Task to read its durable state.",
  forbidden: "The connected API principal may not control Task lifecycle.",
  not_found: "This Task no longer exists.",
  transport_unavailable:
    "The control could not reach the API. Nothing was changed; reload and try again deliberately.",
  malformed_response:
    "The API response for this control could not be understood. Reload the Task before acting again.",
  request_rejected: "The control was rejected by the API as invalid.",
};

function rejectionCopy(result: LifecycleMutationResult): string {
  if (result.ok) return "";
  return (
    LIFECYCLE_REJECTION_COPY[result.code] ??
    "The control was refused. Reload the Task to read its durable state before acting again."
  );
}

function StatusBadge({ status }: { readonly status: string }) {
  return <span className="mf-status-badge">{status}</span>;
}

function LifecycleControls({
  projection,
  pendingAction,
  onInvoke,
}: {
  readonly projection: LifecycleProjection;
  readonly pendingAction: string | null;
  readonly onInvoke: (action: LifecycleAction) => void;
}) {
  const available = projection.actions.filter((item) => item.available);
  return (
    <section className="mf-count-section">
      <h3>Lifecycle controls</h3>
      <p className="mf-dashboard-meta">{projection.knownEffects}</p>
      {available.length === 0 ? (
        <div>
          <p className="mf-dashboard-meta">
            The backend advertises no lifecycle action for this Task state and
            principal.
          </p>
          <ul className="mf-dashboard-meta">
            {projection.actions
              .filter((item) => item.unavailableReason !== null)
              .map((item) => (
                <li key={item.action}>
                  {item.label}: {item.unavailableReason}
                </li>
              ))}
          </ul>
        </div>
      ) : (
        <div className="mf-actions">
          {available.map((item) => (
            <button
              key={item.action}
              type="button"
              className="mf-button mf-button-secondary"
              disabled={pendingAction !== null}
              onClick={() => onInvoke(item)}
            >
              {pendingAction === item.action ? "Working…" : item.label}
            </button>
          ))}
        </div>
      )}
      <p className="mf-dashboard-meta">{projection.nextAction}</p>
    </section>
  );
}

/** Read the bounded parent-list filter context this detail was opened from. */
function returnSearch(
  search: Record<string, unknown>,
): Record<string, string> | undefined {
  const value: Record<string, string> = {};
  for (const [source, target] of [
    ["q_status", "status"],
    ["q_command", "command"],
  ] as const) {
    const raw = search[source];
    if (typeof raw === "string" && raw.length > 0 && raw.length <= 64) {
      value[target] = raw;
    }
  }
  return Object.keys(value).length > 0 ? value : undefined;
}

export function TaskDetailPage() {
  const { taskId } = useParams({ strict: false }) as { taskId: string };
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const listReturnSearch = returnSearch(searchParams);
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
  const [controlResult, setControlResult] =
    useState<LifecycleMutationResult | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const query = useQuery(
    taskDetailQueryOptions(token, {
      taskId,
      itemLimit: 20,
      resultLimit: 20,
      itemCursor,
      resultCursor,
    }),
  );

  // A lifecycle mutation is submitted at most once per deliberate click. There
  // is no retry policy: a rejected, stale, 401 or 403 control requires the
  // operator to reload and act again.
  const lifecycleMutation = useMutation({
    mutationFn: (request: {
      readonly action: LifecycleAction;
      readonly expectedVersion: string;
    }) =>
      mutateLifecycle(token, {
        objectType: "task",
        objectId: taskId,
        action: request.action.action,
        expectedVersion: request.expectedVersion,
      }),
    retry: false,
    onMutate: (request) => {
      setPendingAction(request.action.action);
      setControlResult(null);
    },
    onSuccess: (result) => {
      setControlResult(result);
      if (result.ok) {
        void queryClient.invalidateQueries({ queryKey: [taskListQueryKey] });
        void query.refetch();
      }
    },
    onSettled: () => setPendingAction(null),
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
                  search={listReturnSearch}
                >
                  Back to Tasks
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const { task, lifecycle, items, results } = data.model;
        const resumeWithheld = lifecycle.actions.find(
          (item) => item.action === "resume",
        );
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <h2>Task {task.taskId}</h2>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Task aggregate</h3>
              <dl>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={task.status} />
                </dd>
                <dt>Work kind</dt>
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
                <dt>Execution authority</dt>
                <dd>
                  {task.executeAuthorized
                    ? "execution was authorized for this Task"
                    : "analysis only — no Storage mutation was authorized"}
                </dd>
                <dt>Pinned configuration</dt>
                <dd>
                  {task.configurationSnapshotId
                    ? `${task.configurationSnapshotId} (immutable revision identity)`
                    : "no pinned configuration snapshot"}
                </dd>
                {task.failure && (
                  <>
                    <dt>Failure evidence</dt>
                    <dd>
                      {task.failure.category}: {task.failure.message} —{" "}
                      {task.failure.durableState} — {task.failure.nextAction}
                    </dd>
                  </>
                )}
                {task.pauseRequested && (
                  <>
                    <dt>Pause requested</dt>
                    <dd>
                      Yes — cooperative pause pending at the next supported item
                      boundary
                    </dd>
                  </>
                )}
                {isTerminalTaskStatus(task.status) && (
                  <>
                    <dt>Terminal</dt>
                    <dd>
                      This Task has reached a durable terminal outcome. No
                      lifecycle control is available.
                    </dd>
                  </>
                )}
              </dl>
            </section>
            <LifecycleControls
              projection={lifecycle}
              pendingAction={pendingAction}
              onInvoke={(action) =>
                lifecycleMutation.mutate({
                  action,
                  expectedVersion: lifecycle.version,
                })
              }
            />
            {resumeWithheld?.unavailableReason && (
              <section className="mf-count-section">
                <h3>Resume</h3>
                <p className="mf-dashboard-meta">
                  {resumeWithheld.unavailableReason}
                </p>
                <p className="mf-dashboard-meta">{resumeWithheld.nextAction}</p>
              </section>
            )}
            {controlResult !== null && (
              <StatusBanner
                variant={controlResult.ok ? "success" : "error"}
                title={
                  controlResult.ok
                    ? "Control accepted"
                    : "Control was not applied"
                }
              >
                {controlResult.ok ? (
                  <p>
                    Durable state: {controlResult.state} (version{" "}
                    {controlResult.version}).{" "}
                    {controlResult.durableOutcome ?? ""}
                    {controlResult.nextAction
                      ? ` Next: ${controlResult.nextAction}`
                      : ""}
                  </p>
                ) : (
                  <p>{rejectionCopy(controlResult)}</p>
                )}
                <div className="mf-actions">
                  <RefreshControl onRefresh={refresh} refreshing={isFetching} />
                </div>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>TaskItems ({items.length} on this page)</h3>
              {items.length === 0 ? (
                <p className="mf-dashboard-meta">
                  No TaskItem is visible in this page window.
                </p>
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
                          <th>Failure evidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((item) => (
                          <tr key={item.itemId}>
                            <td>{item.itemId}</td>
                            <td>
                              {item.storageId}:{item.sourcePath}
                            </td>
                            <td>
                              <StatusBadge status={item.status} />
                            </td>
                            <td>{item.stage}</td>
                            <td>{item.attempts}</td>
                            <td>{item.destinationPath ?? "—"}</td>
                            <td>
                              {item.failure
                                ? `${item.failure.category}: ${item.failure.nextAction}`
                                : "—"}
                            </td>
                          </tr>
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
                      disabled={
                        itemDirection === "forward"
                          ? !data.model.itemsTruncated
                          : !data.model.nextItemCursor
                      }
                      onClick={goItemsForward}
                    >
                      Next items
                    </button>
                  </div>
                </>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Results ({results.length} on this page)</h3>
              <p className="mf-dashboard-meta">
                Effect certainty: {lifecycle.effectCertainty ?? "unknown"}
                {lifecycle.resultsComplete === false
                  ? " (a partial Result view; MediaFlow does not claim the remaining effects are safe to repeat)"
                  : ""}
              </p>
              {results.length === 0 ? (
                <p className="mf-dashboard-meta">
                  No Result is visible in this page window.
                </p>
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
                          <th>Cleanup</th>
                          <th>Destination</th>
                          <th>Failure evidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.map((result) => (
                          <tr key={result.resultId}>
                            <td>{result.resultId}</td>
                            <td>{result.sourcePath}</td>
                            <td>
                              <StatusBadge status={result.status} />
                            </td>
                            <td>{result.operation ?? "—"}</td>
                            <td>{result.effectCertainty}</td>
                            <td>{result.cleanupStatus ?? "—"}</td>
                            <td>{result.destinationPath ?? "—"}</td>
                            <td>
                              {result.failure
                                ? `${result.failure.category}: ${result.failure.nextAction}`
                                : "—"}
                            </td>
                          </tr>
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
                      disabled={
                        resultDirection === "forward"
                          ? !data.model.resultsTruncated
                          : !data.model.nextResultCursor
                      }
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
                search={listReturnSearch}
              >
                Back to Tasks
              </Link>
              {task.configurationSnapshotId && (
                <Link
                  className="mf-button mf-button-secondary"
                  to="/configuration"
                >
                  Configuration handoff
                </Link>
              )}
              {availableLifecycleAction(lifecycle, "cancel") === null &&
                items.some((item) => item.status === "failed") && (
                  <Link className="mf-button mf-button-secondary" to="/review">
                    Review &amp; Recovery handoff
                  </Link>
                )}
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
