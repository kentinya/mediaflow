/**
 * Job detail page: separates durable admission/queue state from its linked
 * Task. Shows command, source/definition/schedule context, worker
 * ownership/readiness, cancellation request and bounded failure/recovery
 * evidence.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import type { JobSummary } from "../../entities/operations/job";
import { jobLifecycleActions } from "../../entities/operations/job";
import { mutateJobCancel } from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { jobDetailQueryOptions, jobListQueryKey } from "./job-query";

function StatusBadge({ status }: { readonly status: string }) {
  return <span className="mf-status-badge">{status}</span>;
}

function WorkerEvidenceSection({ job }: { readonly job: JobSummary }) {
  if (job.status !== "running" || !job.workerId) {
    return null;
  }
  return (
    <section className="mf-count-section">
      <h3>Worker ownership</h3>
      <dl>
        <dt>Worker ID</dt>
        <dd>{job.workerId}</dd>
        {job.workerEvidence?.ownerLastHeartbeatAt && (
          <>
            <dt>Last heartbeat</dt>
            <dd>{job.workerEvidence.ownerLastHeartbeatAt}</dd>
          </>
        )}
        {job.workerEvidence?.ownerStale && (
          <>
            <dt>Stale</dt>
            <dd>Owner heartbeat is stale</dd>
          </>
        )}
        {job.workerEvidence?.ownerStopped && (
          <>
            <dt>Stopped</dt>
            <dd>Owner worker has stopped</dd>
          </>
        )}
      </dl>
    </section>
  );
}

function OperationalConditionSection({ job }: { readonly job: JobSummary }) {
  if (!job.operationalCondition) {
    return null;
  }
  const oc = job.operationalCondition;
  return (
    <section className="mf-count-section">
      <h3>Operational condition</h3>
      <dl>
        <dt>Condition</dt>
        <dd>{oc.condition}</dd>
        <dt>Durable state</dt>
        <dd>{oc.durableState}</dd>
        <dt>Retry safe</dt>
        <dd>{oc.retrySafe ? "Yes" : "No"}</dd>
        <dt>Next action</dt>
        <dd>{oc.nextAction}</dd>
      </dl>
    </section>
  );
}

export function JobDetailPage() {
  const { jobId } = useParams({ strict: false }) as { jobId: string };
  const token = useAuthToken();
  const queryClient = useQueryClient();

  const query = useQuery(jobDetailQueryOptions(token, jobId));

  const cancelMutation = useMutation({
    mutationFn: () => mutateJobCancel(token, jobId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [jobListQueryKey] });
      void query.refetch();
    },
  });

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Job detail unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Job detail">
              <p>Requesting the Job from the API.</p>
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
                  to="/operations/jobs"
                >
                  Back to Jobs
                </Link>
              </div>
            </StatusBanner>
          );
        }
        const job = data.model;
        const actions = jobLifecycleActions(job);
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <h2>Job {job.jobId}</h2>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Job overview</h3>
              <dl>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={job.status} />
                </dd>
                <dt>Command</dt>
                <dd>{job.command}</dd>
                {job.taskId && (
                  <>
                    <dt>Linked Task</dt>
                    <dd>
                      <Link
                        to="/operations/tasks/$taskId"
                        params={{ taskId: job.taskId }}
                      >
                        {job.taskId}
                      </Link>
                    </dd>
                  </>
                )}
                {job.definitionId && (
                  <>
                    <dt>Automation definition</dt>
                    <dd>{job.definitionName ?? job.definitionId}</dd>
                  </>
                )}
                {job.scheduleId && (
                  <>
                    <dt>Schedule</dt>
                    <dd>{job.scheduleId}</dd>
                  </>
                )}
                <dt>Created</dt>
                <dd>{job.createdAt}</dd>
                {job.startedAt && (
                  <>
                    <dt>Started</dt>
                    <dd>{job.startedAt}</dd>
                  </>
                )}
                {job.completedAt && (
                  <>
                    <dt>Completed</dt>
                    <dd>{job.completedAt}</dd>
                  </>
                )}
              </dl>
            </section>
            <WorkerEvidenceSection job={job} />
            <OperationalConditionSection job={job} />
            {job.error && (
              <section className="mf-count-section">
                <h3>Failure evidence</h3>
                <dl>
                  <dt>Error</dt>
                  <dd>{job.error}</dd>
                  {job.failureCategory && (
                    <>
                      <dt>Category</dt>
                      <dd>{job.failureCategory}</dd>
                    </>
                  )}
                  {job.failureExplanation && (
                    <>
                      <dt>Explanation</dt>
                      <dd>{job.failureExplanation}</dd>
                    </>
                  )}
                </dl>
              </section>
            )}
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
                {!actions.cancel && (
                  <p className="mf-dashboard-meta">
                    No lifecycle controls available for this job state.
                  </p>
                )}
              </div>
              {cancelMutation.isError && (
                <StatusBanner variant="error" title="Cancel failed">
                  <p>The cancel request was rejected. Reload and try again.</p>
                </StatusBanner>
              )}
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/jobs"
              >
                Back to Jobs
              </Link>
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
