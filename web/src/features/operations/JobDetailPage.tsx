/**
 * Job detail page: separates durable admission/queue state from its linked
 * Task. Shows command, definition/schedule context, worker ownership and
 * readiness, cancellation request, bounded failure/recovery evidence and only
 * the lifecycle controls the backend advertises for this exact Job version.
 *
 * A pending Job without a usable Worker and a running Job with a stale owner
 * are distinct durable states with distinct next actions. A rejected control is
 * never replayed automatically.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import type { LifecycleProjection } from "../../entities/operations/lifecycle";
import {
  mutateLifecycle,
  type LifecycleMutationResult,
} from "../../shared/api/api-client";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { jobDetailQueryOptions, jobListQueryKey } from "./job-query";

const LIFECYCLE_REJECTION_COPY: Readonly<Record<string, string>> = {
  stale_job_state:
    "This Job changed after the page was loaded. Reload the Job, review its current state, and submit again deliberately.",
  lifecycle_conflict:
    "The backend refused this control for the current Job state. Reload the Job to read its durable state.",
  forbidden: "The connected API principal may not control Job lifecycle.",
  not_found: "This Job no longer exists.",
  transport_unavailable:
    "The control could not reach the API. Nothing was changed; reload and try again deliberately.",
  malformed_response:
    "The API response for this control could not be understood. Reload the Job before acting again.",
  request_rejected: "The control was rejected by the API as invalid.",
};

function rejectionCopy(result: LifecycleMutationResult): string {
  if (result.ok) return "";
  return (
    LIFECYCLE_REJECTION_COPY[result.code] ??
    "The control was refused. Reload the Job to read its durable state before acting again."
  );
}

function JobLifecycleControls({
  projection,
  pending,
  onCancel,
}: {
  readonly projection: LifecycleProjection;
  readonly pending: boolean;
  readonly onCancel: () => void;
}) {
  const cancel = projection.actions.find((item) => item.action === "cancel");
  return (
    <section className="mf-count-section">
      <h3>Lifecycle controls</h3>
      <p className="mf-dashboard-meta">{projection.knownEffects}</p>
      {cancel?.available ? (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button mf-button-secondary"
            disabled={pending}
            onClick={onCancel}
          >
            {pending ? "Requesting cancellation…" : cancel.label}
          </button>
        </div>
      ) : (
        <p className="mf-dashboard-meta">
          {cancel?.unavailableReason ??
            "The backend advertises no lifecycle action for this Job state and principal."}
        </p>
      )}
      <p className="mf-dashboard-meta">{projection.nextAction}</p>
      {cancel?.available && (
        <p className="mf-dashboard-meta">{cancel.sideEffects}</p>
      )}
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

export function JobDetailPage() {
  const { jobId } = useParams({ strict: false }) as { jobId: string };
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const listReturnSearch = returnSearch(searchParams);
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const [controlResult, setControlResult] =
    useState<LifecycleMutationResult | null>(null);

  const query = useQuery(jobDetailQueryOptions(token, jobId));

  // Exactly one authenticated POST per deliberate operator action, with the
  // exact Job version that was displayed. No retry policy is configured.
  const cancelMutation = useMutation({
    mutationFn: (expectedVersion: string) =>
      mutateLifecycle(token, {
        objectType: "job",
        objectId: jobId,
        action: "cancel",
        expectedVersion,
      }),
    retry: false,
    onSuccess: (result) => {
      setControlResult(result);
      if (result.ok) {
        void queryClient.invalidateQueries({ queryKey: [jobListQueryKey] });
        void query.refetch();
      }
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
              <p>Requesting the Job admission record from the API.</p>
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
                  search={listReturnSearch}
                >
                  Back to Jobs
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const job = data.model;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <h2>Job {job.jobId}</h2>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Admission and queue state</h3>
              <dl>
                <dt>Command</dt>
                <dd>{job.command}</dd>
                <dt>Status</dt>
                <dd>
                  <span className="mf-status-badge">{job.status}</span>
                </dd>
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
                <dt>Cancellation requested</dt>
                <dd>{job.cancellationRequested ? "Yes" : "No"}</dd>
                <dt>Execution authority</dt>
                <dd>
                  {job.executeAuthorized
                    ? "this Job carries persisted execution authorization"
                    : "analysis only — no Storage mutation was authorized"}
                </dd>
                {job.definitionId && (
                  <>
                    <dt>Automation definition</dt>
                    <dd>{job.definitionId}</dd>
                  </>
                )}
                {job.scheduleId && (
                  <>
                    <dt>Schedule</dt>
                    <dd>{job.scheduleId}</dd>
                  </>
                )}
                {job.runMode && (
                  <>
                    <dt>Run mode</dt>
                    <dd>{job.runMode}</dd>
                  </>
                )}
                <dt>Pinned configuration</dt>
                <dd>
                  {job.configurationSnapshotId
                    ? `${job.configurationSnapshotId} (immutable revision identity)`
                    : "no pinned configuration snapshot"}
                </dd>
              </dl>
            </section>
            <section className="mf-count-section">
              <h3>Worker ownership and readiness</h3>
              {job.workerEvidence ? (
                <dl>
                  <dt>Owning Worker</dt>
                  <dd>{job.workerEvidence.workerId}</dd>
                  <dt>Owner status</dt>
                  <dd>{job.workerEvidence.ownerStatus}</dd>
                  <dt>Last heartbeat</dt>
                  <dd>{job.workerEvidence.ownerLastHeartbeatAt}</dd>
                </dl>
              ) : (
                <p className="mf-dashboard-meta">
                  No Worker owns this Job right now.
                </p>
              )}
              {job.operationalCondition ? (
                <div>
                  <p className="mf-dashboard-meta">
                    Condition: {job.operationalCondition.condition} (stage{" "}
                    {job.operationalCondition.stage})
                  </p>
                  <p className="mf-dashboard-meta">
                    {job.operationalCondition.durableState}
                  </p>
                  <p className="mf-dashboard-meta">
                    Known effects: {job.operationalCondition.sideEffects}
                  </p>
                  <p className="mf-dashboard-meta">
                    {job.operationalCondition.nextAction}
                  </p>
                </div>
              ) : (
                <p className="mf-dashboard-meta">
                  No unusable-Worker condition is reported for this Job.
                </p>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Linked work</h3>
              {job.taskId ? (
                <p className="mf-dashboard-meta">
                  Processing Task:{" "}
                  <Link
                    to="/operations/tasks/$taskId"
                    params={{ taskId: job.taskId }}
                  >
                    {job.taskId}
                  </Link>
                </p>
              ) : (
                <p className="mf-dashboard-meta">
                  This Job has not produced a processing Task yet. Its durable
                  admission record above is the authoritative state.
                </p>
              )}
              {job.failure && (
                <div>
                  <p className="mf-dashboard-meta">
                    Failure category: {job.failure.category} —{" "}
                    {job.failure.message}
                  </p>
                  <p className="mf-dashboard-meta">
                    {job.failure.durableState}
                  </p>
                  <p className="mf-dashboard-meta">{job.failure.nextAction}</p>
                </div>
              )}
            </section>
            <JobLifecycleControls
              projection={job.lifecycle}
              pending={cancelMutation.isPending}
              onCancel={() => cancelMutation.mutate(job.lifecycle.version)}
            />
            {controlResult !== null && (
              <StatusBanner
                variant={controlResult.ok ? "success" : "error"}
                title={
                  controlResult.ok
                    ? "Cancellation requested"
                    : "Cancellation was not applied"
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
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/jobs"
                search={listReturnSearch}
              >
                Back to Jobs
              </Link>
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
