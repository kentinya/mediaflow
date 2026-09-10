/**
 * Task list page with backend-filtered, cursor-paged, deterministic order.
 *
 * Provides status filter controls, forward/backward paging, and links to
 * individual task detail. Empty and filtered-empty states are distinct.
 * All reads are zero-side-effect.
 */

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import type { TaskStatus } from "../../entities/operations/task";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { taskListQueryOptions } from "./task-query";

const STATUS_FILTERS: readonly (TaskStatus | "all")[] = [
  "all",
  "pending",
  "running",
  "completed",
  "partial_success",
  "failed",
  "cancelled",
  "paused",
];

function StatusLabel({ status }: { readonly status: TaskStatus }) {
  const map: Record<TaskStatus, string> = {
    pending: "Pending",
    running: "Running",
    completed: "Completed",
    partial_success: "Partial success",
    failed: "Failed",
    cancelled: "Cancelled",
    paused: "Paused",
  };
  return <span>{map[status] ?? status}</span>;
}

function TaskRow({
  task,
}: {
  readonly task: {
    taskId: string;
    command: string;
    status: TaskStatus;
    createdAt: string;
    totalItems: number;
    completedItems: number;
    failedItems: number;
  };
}) {
  return (
    <tr>
      <td>
        <Link to="/operations/tasks/$taskId" params={{ taskId: task.taskId }}>
          {task.taskId}
        </Link>
      </td>
      <td>{task.command}</td>
      <td>
        <StatusLabel status={task.status} />
      </td>
      <td>{task.totalItems}</td>
      <td>{task.completedItems}</td>
      <td>{task.failedItems}</td>
      <td>{task.createdAt}</td>
    </tr>
  );
}

export function TaskListPage() {
  const token = useAuthToken();
  const searchParams = useSearch({ strict: false }) as Record<string, string>;
  const [statusFilter, setStatusFilter] = useState<string>(
    searchParams.status ?? "all",
  );
  const [cursor, setCursor] = useState<string | null>(null);
  const [direction, setDirection] = useState<"forward" | "backward">("forward");

  const effectiveStatus = statusFilter === "all" ? null : statusFilter;
  const cursorParam = direction === "forward" ? cursor : undefined;
  const prevCursorParam = direction === "backward" ? cursor : undefined;

  const query = useQuery(
    taskListQueryOptions(token, {
      status: effectiveStatus,
      limit: 20,
      cursor: direction === "forward" ? cursorParam : prevCursorParam,
    }),
  );

  const goForward = useCallback(() => {
    if (query.data?.ok === true && query.data.model.nextCursor) {
      setCursor(query.data.model.nextCursor);
      setDirection("forward");
    }
  }, [query.data]);

  const goBackward = useCallback(() => {
    if (query.data?.ok === true && query.data.model.previousCursor) {
      setCursor(query.data.model.previousCursor);
      setDirection("backward");
    }
  }, [query.data]);

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Task list unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Tasks">
              <p>Requesting the Task list from the MediaFlow API.</p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const page = data.model;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <h2>Tasks</h2>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <div className="mf-count-section">
              <label htmlFor="task-status-filter">Filter by status</label>
              <select
                id="task-status-filter"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setCursor(null);
                  setDirection("forward");
                }}
              >
                {STATUS_FILTERS.map((s) => (
                  <option key={s} value={s}>
                    {s === "all" ? "All statuses" : s}
                  </option>
                ))}
              </select>
            </div>
            {page.items.length === 0 ? (
              <StatusBanner variant="info" title="No tasks found">
                <p>
                  {effectiveStatus
                    ? `No tasks match the selected status filter.`
                    : `No tasks have been created yet.`}
                </p>
              </StatusBanner>
            ) : (
              <>
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Task ID</th>
                        <th>Command</th>
                        <th>Status</th>
                        <th>Items</th>
                        <th>Completed</th>
                        <th>Failed</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {page.items.map((task) => (
                        <TaskRow key={task.taskId} task={task} />
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mf-actions">
                  <button
                    type="button"
                    className="mf-button mf-button-secondary"
                    disabled={!page.previousCursor}
                    onClick={goBackward}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="mf-button mf-button-secondary"
                    disabled={!page.truncated}
                    onClick={goForward}
                  >
                    Next
                  </button>
                </div>
              </>
            )}
            <div className="mf-actions">
              <Link className="mf-button mf-button-secondary" to="/operations">
                Back to Operations
              </Link>
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
