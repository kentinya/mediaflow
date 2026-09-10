/**
 * Task list page with backend-submitted filters, cursor-paged, deterministic
 * order.
 *
 * Both filters and page cursors are submitted to the API: the frontend never
 * filters a partial page and never infers a total. Empty and filtered-empty
 * states are distinct. All reads are zero-side-effect.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  TASK_COMMAND_FILTERS,
  TASK_STATUSES,
  type TaskStatus,
} from "../../entities/operations/task";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { taskListQueryOptions } from "./task-query";

const TASK_STATUS_LABELS: Readonly<Record<TaskStatus, string>> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  partial_success: "Partial success",
  failed: "Failed",
  cancelled: "Cancelled",
  paused: "Paused",
};

function readSafeSearchValue(
  search: Record<string, unknown>,
  key: string,
): string | null {
  const value = search[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

/** Submitted collection filters, reflected in the URL so a reconnect resumes them. */
function taskListSearch(
  status: string,
  command: string,
): Record<string, string> | undefined {
  const search: Record<string, string> = {};
  if (status !== "all") search["status"] = status;
  if (command !== "all") search["command"] = command;
  return Object.keys(search).length > 0 ? search : undefined;
}

/** Bounded parent-list context carried into one Task detail route. */
function taskDetailReturnSearch(
  status: string,
  command: string,
): Record<string, string> | undefined {
  const search: Record<string, string> = {};
  if (status !== "all") search["q_status"] = status;
  if (command !== "all") search["q_command"] = command;
  return Object.keys(search).length > 0 ? search : undefined;
}

export function TaskListPage() {
  const token = useAuthToken();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  // The URL search is the single source of truth for the submitted backend
  // filters, so a deep entry, a reconnect continuation and the rendered page
  // can never disagree about which collection was requested.
  const statusFilter = readSafeSearchValue(searchParams, "status") ?? "all";
  const commandFilter = readSafeSearchValue(searchParams, "command") ?? "all";
  const [cursor, setCursor] = useState<string | null>(null);
  const [direction, setDirection] = useState<"forward" | "backward">("forward");

  const effectiveStatus = statusFilter === "all" ? null : statusFilter;
  const effectiveCommand = commandFilter === "all" ? null : commandFilter;

  const query = useQuery(
    taskListQueryOptions(token, {
      status: effectiveStatus as TaskStatus | null,
      command: effectiveCommand,
      limit: 20,
      cursor,
    }),
  );

  // A page cursor is only ever taken from the response to the exact submitted
  // filter state, so it can never be replayed against different filters.
  const goForward = () => {
    if (query.data?.ok === true && query.data.model.nextCursor) {
      setCursor(query.data.model.nextCursor);
      setDirection("forward");
    }
  };

  const goBackward = () => {
    if (query.data?.ok === true && query.data.model.previousCursor) {
      setCursor(query.data.model.previousCursor);
      setDirection("backward");
    }
  };

  const applyFilters = (status: string, command: string) => {
    setCursor(null);
    setDirection("forward");
    void navigate({
      to: "/operations/tasks",
      search: taskListSearch(status, command),
      replace: true,
    });
  };

  const resetFilters = () => {
    applyFilters("all", "all");
  };

  const filtered = effectiveStatus !== null || effectiveCommand !== null;

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Task list unavailable"
    >
      {({ data, isFetching, refresh }) => {
        const page = data?.ok === true ? data.model : null;
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
                onChange={(e) => applyFilters(e.target.value, commandFilter)}
              >
                <option value="all">All statuses</option>
                {TASK_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {TASK_STATUS_LABELS[status]}
                  </option>
                ))}
              </select>
              <label htmlFor="task-command-filter">Filter by work kind</label>
              <select
                id="task-command-filter"
                value={commandFilter}
                onChange={(e) => applyFilters(statusFilter, e.target.value)}
              >
                <option value="all">All work kinds</option>
                {TASK_COMMAND_FILTERS.map((command) => (
                  <option key={command} value={command}>
                    {command}
                  </option>
                ))}
              </select>
              {filtered && (
                <button
                  type="button"
                  className="mf-button mf-button-secondary"
                  onClick={resetFilters}
                >
                  Reset filters
                </button>
              )}
            </div>
            {data === undefined ? (
              <StatusBanner variant="info" title="Loading Tasks">
                <p>Requesting the Task list from the MediaFlow API.</p>
              </StatusBanner>
            ) : !data.ok ? (
              <StatusBanner variant="error" title={data.failure.title}>
                <p>{data.failure.nextAction}</p>
                <div className="mf-actions">
                  <RefreshControl onRefresh={refresh} refreshing={isFetching} />
                  <button
                    type="button"
                    className="mf-button mf-button-secondary"
                    onClick={resetFilters}
                  >
                    Reset filters
                  </button>
                </div>
              </StatusBanner>
            ) : page === null ? null : page.items.length === 0 ? (
              <StatusBanner
                variant="info"
                title={filtered ? "No matching Tasks" : "No Tasks yet"}
              >
                <p>
                  {filtered
                    ? "No Task matches the submitted status and work-kind filters. Reset the filters to see every Task this principal may read."
                    : "No Task has been created yet. Nothing is pending, running or failed."}
                </p>
                {filtered && (
                  <div className="mf-actions">
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      onClick={resetFilters}
                    >
                      Reset filters
                    </button>
                  </div>
                )}
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
                        <tr key={task.taskId}>
                          <td>
                            <Link
                              to="/operations/tasks/$taskId"
                              params={{ taskId: task.taskId }}
                              search={taskDetailReturnSearch(
                                statusFilter,
                                commandFilter,
                              )}
                            >
                              {task.taskId}
                            </Link>
                          </td>
                          <td>{task.command}</td>
                          <td>{TASK_STATUS_LABELS[task.status]}</td>
                          <td>{task.totalItems}</td>
                          <td>{task.completedItems}</td>
                          <td>{task.failedItems}</td>
                          <td>{task.createdAt}</td>
                        </tr>
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
                    disabled={
                      direction === "forward"
                        ? !page.truncated
                        : !page.nextCursor
                    }
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
