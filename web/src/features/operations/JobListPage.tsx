/**
 * Job list page with backend-submitted filters and cursor paging.
 *
 * Shows command, status, linked Task, worker evidence and operational
 * conditions. The frontend never filters a partial page and never infers a
 * total. All reads are zero-side-effect.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  JOB_COMMANDS,
  JOB_STATUSES,
  type JobCommand,
  type JobStatus,
} from "../../entities/operations/job";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { jobListQueryOptions } from "./job-query";

function readSafeSearchValue(
  search: Record<string, unknown>,
  key: string,
): string | null {
  const value = search[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

/** Submitted collection filters, reflected in the URL so a reconnect resumes them. */
function jobListSearch(
  status: string,
  command: string,
): Record<string, string> | undefined {
  const search: Record<string, string> = {};
  if (status !== "all") search["status"] = status;
  if (command !== "all") search["command"] = command;
  return Object.keys(search).length > 0 ? search : undefined;
}

/** Bounded parent-list context carried into one Job detail route. */
function jobDetailReturnSearch(
  status: string,
  command: string,
): Record<string, string> | undefined {
  const search: Record<string, string> = {};
  if (status !== "all") search["q_status"] = status;
  if (command !== "all") search["q_command"] = command;
  return Object.keys(search).length > 0 ? search : undefined;
}

export function JobListPage() {
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
    jobListQueryOptions(token, {
      status: effectiveStatus as JobStatus | null,
      command: effectiveCommand as JobCommand | null,
      limit: 20,
      cursor,
    }),
  );

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
      to: "/operations/jobs",
      search: jobListSearch(status, command),
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
      unavailableTitle="Job list unavailable"
    >
      {({ data, isFetching, refresh }) => {
        const page = data?.ok === true ? data.model : null;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <h2>Jobs</h2>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <div className="mf-count-section">
              <label htmlFor="job-status-filter">Filter by status</label>
              <select
                id="job-status-filter"
                value={statusFilter}
                onChange={(e) => applyFilters(e.target.value, commandFilter)}
              >
                <option value="all">All statuses</option>
                {JOB_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
              <label htmlFor="job-command-filter">Filter by work kind</label>
              <select
                id="job-command-filter"
                value={commandFilter}
                onChange={(e) => applyFilters(statusFilter, e.target.value)}
              >
                <option value="all">All work kinds</option>
                {JOB_COMMANDS.map((command) => (
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
              <StatusBanner variant="info" title="Loading Jobs">
                <p>Requesting the Job list from the MediaFlow API.</p>
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
                title={filtered ? "No matching Jobs" : "No Jobs yet"}
              >
                <p>
                  {filtered
                    ? "No Job matches the submitted status and work-kind filters. Reset the filters to see every Job this principal may read."
                    : "No Job is admitted or queued. Nothing is waiting for a Worker."}
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
                        <th>Job ID</th>
                        <th>Command</th>
                        <th>Status</th>
                        <th>Linked Task</th>
                        <th>Worker</th>
                        <th>Condition</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {page.items.map((job) => (
                        <tr key={job.jobId}>
                          <td>
                            <Link
                              to="/operations/jobs/$jobId"
                              params={{ jobId: job.jobId }}
                              search={jobDetailReturnSearch(
                                statusFilter,
                                commandFilter,
                              )}
                            >
                              {job.jobId}
                            </Link>
                          </td>
                          <td>{job.command}</td>
                          <td>{job.status}</td>
                          <td>
                            {job.taskId ? (
                              <Link
                                to="/operations/tasks/$taskId"
                                params={{ taskId: job.taskId }}
                              >
                                {job.taskId}
                              </Link>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td>
                            {job.workerEvidence
                              ? `${job.workerEvidence.ownerStatus}`
                              : "—"}
                          </td>
                          <td>{job.operationalCondition?.condition ?? "—"}</td>
                          <td>{job.createdAt}</td>
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
