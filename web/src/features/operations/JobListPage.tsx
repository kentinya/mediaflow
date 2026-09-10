/**
 * Job list page with backend-filtered, cursor-paged, deterministic order.
 *
 * Shows command, status, linked task, worker evidence and operational
 * conditions. All reads are zero-side-effect.
 */

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import type { JobStatus } from "../../entities/operations/job";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { jobListQueryOptions } from "./job-query";

function StatusLabel({ status }: { readonly status: JobStatus }) {
  const map: Record<JobStatus, string> = {
    pending: "Pending",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
  };
  return <span>{map[status] ?? status}</span>;
}

function OperationalConditionBadge({
  condition,
}: {
  readonly condition: string;
}) {
  return (
    <span className="mf-status-badge" style={{ marginLeft: "0.5rem" }}>
      {condition}
    </span>
  );
}

function JobRow({
  job,
}: {
  readonly job: {
    jobId: string;
    command: string;
    status: JobStatus;
    taskId: string | null;
    createdAt: string;
    workerId: string | null;
    operationalCondition: { condition: string } | null;
  };
}) {
  return (
    <tr>
      <td>
        <Link to="/operations/jobs/$jobId" params={{ jobId: job.jobId }}>
          {job.jobId}
        </Link>
      </td>
      <td>{job.command}</td>
      <td>
        <StatusLabel status={job.status} />
        {job.operationalCondition && (
          <OperationalConditionBadge
            condition={job.operationalCondition.condition}
          />
        )}
      </td>
      <td>
        {job.taskId ? (
          <Link to="/operations/tasks/$taskId" params={{ taskId: job.taskId }}>
            {job.taskId}
          </Link>
        ) : (
          "—"
        )}
      </td>
      <td>{job.workerId ?? "—"}</td>
      <td>{job.createdAt}</td>
    </tr>
  );
}

export function JobListPage() {
  const token = useAuthToken();
  const [cursor, setCursor] = useState<string | null>(null);
  const [direction, setDirection] = useState<"forward" | "backward">("forward");

  const query = useQuery(
    jobListQueryOptions(token, {
      limit: 20,
      cursor: direction === "forward" ? cursor : undefined,
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
      unavailableTitle="Job list unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Jobs">
              <p>Requesting the Job list from the MediaFlow API.</p>
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
              <h2>Jobs</h2>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {page.items.length === 0 ? (
              <StatusBanner variant="info" title="No jobs found">
                <p>No jobs have been created yet.</p>
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
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {page.items.map((job) => (
                        <JobRow key={job.jobId} job={job} />
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
