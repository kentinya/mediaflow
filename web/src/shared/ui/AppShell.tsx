import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { AuthControls } from "../auth/AuthControls";
import { destinationForPath } from "../navigation/destination-model";

export interface AppShellProps {
  readonly children: ReactNode;
}

interface ShellDestination {
  readonly id: string;
  readonly label: string;
  readonly accessibleName: string;
  readonly path: string;
  readonly match: "exact" | "prefix";
  readonly migration?: boolean;
}

const shellDestinations: readonly ShellDestination[] = [
  {
    id: "overview",
    label: "首页",
    accessibleName: "Overview",
    path: "/dashboard",
    match: "exact",
  },
  {
    id: "files",
    label: "文件",
    accessibleName: "Files",
    path: "/library/files",
    match: "prefix",
  },
  {
    id: "media-library",
    label: "媒体库",
    accessibleName: "Media library",
    path: "/library/file-index",
    match: "prefix",
  },
  {
    id: "storage",
    label: "存储管理",
    accessibleName: "Library",
    path: "/library",
    match: "exact",
  },
  {
    id: "rules",
    label: "整理规则",
    accessibleName: "Configuration",
    path: "/configuration",
    match: "exact",
    migration: true,
  },
  {
    id: "automation",
    label: "自动化",
    accessibleName: "Automation",
    path: "/operations/automation",
    match: "prefix",
  },
  {
    id: "operations",
    label: "操作与任务",
    accessibleName: "Operations",
    path: "/operations",
    match: "prefix",
  },
  {
    id: "notifications",
    label: "通知",
    accessibleName: "Notifications",
    path: "/operations/notifications",
    match: "prefix",
  },
  {
    id: "review",
    label: "评审与恢复",
    accessibleName: "Review & Recovery",
    path: "/review",
    match: "prefix",
    migration: true,
  },
];

function activeShellDestination(pathname: string): string | null {
  const candidates = shellDestinations
    .filter((item) =>
      item.match === "exact"
        ? pathname === item.path
        : pathname === item.path || pathname.startsWith(`${item.path}/`),
    )
    .sort((left, right) => right.path.length - left.path.length);
  return candidates[0]?.id ?? null;
}

/** Shared feature-independent V2 shell and operator-goal navigation. */
export function AppShell({ children }: AppShellProps) {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const destination = destinationForPath(pathname);
  const [menuOpen, setMenuOpen] = useState(false);
  const pageTitle =
    destination?.title ??
    (pathname === "/" ? "Connect | MediaFlow" : "MediaFlow");
  const activeDestinationId = useMemo(
    () => activeShellDestination(pathname),
    [pathname],
  );

  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);

  return (
    <div className="mf-shell">
      <a className="mf-skip-link" href="#main-content">
        Skip to main content
      </a>

      <aside
        className={`mf-sidebar${menuOpen ? " mf-sidebar-open" : ""}`}
        aria-label="MediaFlow navigation"
      >
        <Link
          className="mf-sidebar-brand"
          to="/dashboard"
          onClick={() => setMenuOpen(false)}
        >
          <span className="mf-brand-mark" aria-hidden="true">
            ▷
          </span>
          <span>
            <strong>MediaFlow</strong>
            <small>影视媒体资源管理系统</small>
          </span>
        </Link>
        <nav id="primary-navigation" className="mf-primary-nav" aria-label="Primary">
          {shellDestinations.map((item) => {
            const active = item.id === activeDestinationId;
            return (
              <Link
                key={item.id}
                to={item.path as string}
                aria-label={item.accessibleName}
                aria-current={active ? "page" : undefined}
                className="mf-nav-link"
                onClick={() => setMenuOpen(false)}
              >
                <span className="mf-nav-icon" aria-hidden="true" />
                <span className="mf-nav-copy">{item.label}</span>
                {item.migration ? (
                  <span className="mf-nav-status">迁移中</span>
                ) : null}
              </Link>
            );
          })}
        </nav>
      </aside>

      {menuOpen ? (
        <button
          type="button"
          className="mf-sidebar-backdrop"
          aria-label="Close menu"
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      <header className="mf-shell-header">
        <button
          className="mf-menu-toggle"
          type="button"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? "×" : "☰"}
        </button>
        <div className="mf-shell-header-spacer" />
        <div className="mf-shell-auth">
          <AuthControls />
        </div>
      </header>

      <main id="main-content" className="mf-shell-main" tabIndex={-1}>
        {destination ? (
          <p className="mf-page-context">{destination.label}</p>
        ) : null}
        {children}
      </main>
    </div>
  );
}
