import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { RefreshControl } from "../../shared/ui/RefreshControl";

export function NotificationWorkspaceHeader({
  section,
  refresh,
  refreshing,
  children,
}: {
  readonly section: "webhooks" | "deliveries";
  readonly refresh: () => void;
  readonly refreshing: boolean;
  readonly children?: ReactNode;
}) {
  return (
    <>
      <header className="mf-dashboard-head">
        <h2>通知</h2>
        <div className="mf-actions">
          <RefreshControl
            onRefresh={refresh}
            refreshing={refreshing}
            label="刷新"
            refreshingLabel="刷新中…"
          />
          {children}
        </div>
      </header>
      <nav className="mf-run-tabs mf-view-tabs" aria-label="通知分区">
        <Link
          to="/operations/notifications"
          aria-current={section === "webhooks" ? "page" : undefined}
          activeOptions={{ exact: true }}
        >
          Webhook
        </Link>
        <Link
          to="/operations/notifications/deliveries"
          search={{}}
          aria-current={section === "deliveries" ? "page" : undefined}
        >
          投递记录
        </Link>
      </nav>
    </>
  );
}
