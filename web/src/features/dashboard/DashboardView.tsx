import { Link } from "@tanstack/react-router";
import type {
  DashboardModel,
  DashboardRecentFailure,
} from "../../entities/dashboard/dashboard";
import { CountGrid } from "../../shared/ui/CountGrid";
import { RefreshControl } from "../../shared/ui/RefreshControl";

export interface DashboardViewProps {
  readonly model: DashboardModel;
  readonly onRefresh: () => void;
  readonly refreshing: boolean;
}

/**
 * One actionable destination for a recorded operational failure.
 *
 * Only a bounded, single-segment identity the backend actually supplied becomes
 * a link. Anything else stays plain text, so an unsafe or unexpected identifier
 * can never be turned into a route.
 */
function safeIdentifier(value: string): boolean {
  return (
    value.length > 0 &&
    value.length <= 256 &&
    !value.includes("/") &&
    !value.includes("\\") &&
    // eslint-disable-next-line no-control-regex
    !/[\u0000-\u001f\u007f\s]/.test(value)
  );
}

function FailureTarget({
  failure,
}: {
  readonly failure: DashboardRecentFailure;
}) {
  if (failure.kind === "task" && safeIdentifier(failure.identifier)) {
    return (
      <Link
        to="/operations/tasks/$taskId"
        params={{ taskId: failure.identifier }}
      >
        Open this Task
      </Link>
    );
  }
  if (failure.kind === "job" && safeIdentifier(failure.identifier)) {
    return (
      <Link to="/operations/jobs/$jobId" params={{ jobId: failure.identifier }}>
        Open this Job
      </Link>
    );
  }
  if (failure.kind === "notification") {
    // Per-delivery Notification recovery belongs to a later Slice 33 Task, so
    // the Dashboard links the Operations workspace instead of imitating it.
    return <Link to="/operations">Open Operations</Link>;
  }
  return null;
}

function RecentFailures({ model }: { model: DashboardModel }) {
  if (model.recentFailures.length === 0) {
    return (
      <section className="mf-count-section">
        <h3>Recent failures</h3>
        <p className="mf-dashboard-meta">No recent failures recorded.</p>
      </section>
    );
  }
  return (
    <section className="mf-count-section">
      <h3>Recent failures</h3>
      <ul className="mf-failure-list">
        {model.recentFailures.map((failure) => (
          <li key={`${failure.kind}:${failure.identifier}`}>
            <div>{failure.category}</div>
            <div className="mf-failure-meta">
              {failure.kind} {failure.identifier} — {failure.status} —{" "}
              {failure.occurredAt}
            </div>
            <FailureTarget failure={failure} />
          </li>
        ))}
      </ul>
    </section>
  );
}

interface CountLink {
  readonly label: string;
  readonly value: number;
  readonly status: string | null;
}

/**
 * A count group whose cells submit the exact backend filter that reproduces
 * the count. The count itself is a navigation aid, never permission.
 */
function LinkedCounts({
  title,
  to,
  counts,
}: {
  readonly title: string;
  readonly to: "/operations/tasks" | "/operations/jobs";
  readonly counts: readonly CountLink[];
}) {
  return (
    <section className="mf-count-section">
      <h3>{title}</h3>
      <ul className="mf-count-grid">
        {counts.map((item) => (
          <li key={item.label} className="mf-count-card">
            <Link
              className="mf-count-link"
              to={to}
              search={
                item.status === null ? undefined : { status: item.status }
              }
            >
              <span className="mf-count-value">{item.value}</span>
              <span className="mf-count-label">{item.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Success presentation of the read-only Dashboard snapshot. */
export function DashboardView({
  model,
  onRefresh,
  refreshing,
}: DashboardViewProps) {
  return (
    <div className="mf-dashboard">
      <header className="mf-dashboard-head">
        <h2>Dashboard</h2>
        <RefreshControl onRefresh={onRefresh} refreshing={refreshing} />
      </header>
      <p className="mf-dashboard-meta">Snapshot as of {model.asOf}</p>
      <div className="mf-actions">
        <Link to="/operations/automation">Open Automation workspace</Link>
      </div>
      <CountGrid
        title="Libraries"
        counts={[
          { label: "Resource libraries", value: model.resourceLibraries },
          { label: "Media libraries", value: model.mediaLibraries },
        ]}
      />
      <CountGrid
        title="Files"
        counts={[
          { label: "Total", value: model.files.total },
          { label: "Ready", value: model.files.ready },
          { label: "Unstable", value: model.files.unstable },
          { label: "Missing", value: model.files.missing },
          { label: "Errors", value: model.files.errors },
        ]}
      />
      <LinkedCounts
        title="Tasks"
        to="/operations/tasks"
        counts={[
          { label: "Total", value: model.tasks.total, status: null },
          { label: "Pending", value: model.tasks.pending, status: "pending" },
          { label: "Running", value: model.tasks.running, status: "running" },
          {
            label: "Completed",
            value: model.tasks.completed,
            status: "completed",
          },
          {
            label: "Partial success",
            value: model.tasks.partialSuccess,
            status: "partial_success",
          },
          { label: "Failed", value: model.tasks.failed, status: "failed" },
          {
            label: "Cancelled",
            value: model.tasks.cancelled,
            status: "cancelled",
          },
          { label: "Paused", value: model.tasks.paused, status: "paused" },
        ]}
      />
      <LinkedCounts
        title="Jobs"
        to="/operations/jobs"
        counts={[
          { label: "Total", value: model.jobs.total, status: null },
          { label: "Pending", value: model.jobs.pending, status: "pending" },
          { label: "Running", value: model.jobs.running, status: "running" },
          {
            label: "Completed",
            value: model.jobs.completed,
            status: "completed",
          },
          { label: "Failed", value: model.jobs.failed, status: "failed" },
          {
            label: "Cancelled",
            value: model.jobs.cancelled,
            status: "cancelled",
          },
        ]}
      />
      <CountGrid
        title="Reviews and notifications"
        counts={[
          { label: "Pending confirmations", value: model.pendingConfirmations },
          {
            label: "Pending metadata reviews",
            value: model.pendingMetadataReviews,
          },
          {
            label: "Pending classification reviews",
            value: model.pendingClassificationReviews,
          },
          {
            label: "Dead-letter notifications",
            value: model.deadLetterNotifications,
          },
        ]}
      />
      <RecentFailures model={model} />
    </div>
  );
}
