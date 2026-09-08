import type { DashboardModel } from "../../entities/dashboard/dashboard";
import { CountGrid } from "../../shared/ui/CountGrid";
import { RefreshControl } from "../../shared/ui/RefreshControl";

export interface DashboardViewProps {
  readonly model: DashboardModel;
  readonly onRefresh: () => void;
  readonly refreshing: boolean;
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
          <li key={failure.identifier}>
            <div>{failure.category}</div>
            <div className="mf-failure-meta">
              {failure.kind} {failure.identifier} — {failure.status} —{" "}
              {failure.occurredAt}
            </div>
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
      <CountGrid
        title="Tasks"
        counts={[
          { label: "Total", value: model.tasks.total },
          { label: "Pending", value: model.tasks.pending },
          { label: "Running", value: model.tasks.running },
          { label: "Completed", value: model.tasks.completed },
          { label: "Partial success", value: model.tasks.partialSuccess },
          { label: "Failed", value: model.tasks.failed },
          { label: "Cancelled", value: model.tasks.cancelled },
          { label: "Paused", value: model.tasks.paused },
        ]}
      />
      <CountGrid
        title="Jobs"
        counts={[
          { label: "Total", value: model.jobs.total },
          { label: "Pending", value: model.jobs.pending },
          { label: "Running", value: model.jobs.running },
          { label: "Completed", value: model.jobs.completed },
          { label: "Failed", value: model.jobs.failed },
          { label: "Cancelled", value: model.jobs.cancelled },
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
