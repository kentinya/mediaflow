import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { AuthControls } from "../auth/AuthControls";
import {
  destinations,
  destinationForPath,
} from "../navigation/destination-model";

export interface AppShellProps {
  readonly children: ReactNode;
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

  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);

  return (
    <div className="mf-shell">
      <a className="mf-skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="mf-shell-header">
        <div className="mf-brand">
          <span className="mf-eyebrow">MEDIAFLOW</span>
          <p className="mf-shell-title">Operator workspace</p>
        </div>
        <button
          className="mf-menu-toggle"
          type="button"
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? "Close menu" : "Open menu"}
        </button>
        <div className="mf-shell-auth">
          <AuthControls />
        </div>
      </header>
      <nav
        id="primary-navigation"
        className={`mf-primary-nav${menuOpen ? " mf-primary-nav-open" : ""}`}
        aria-label="Primary"
      >
        {destinations.map((item) => (
          <Link
            key={item.id}
            to={item.path}
            activeOptions={{ exact: item.path !== "/library" }}
            activeProps={{ "aria-current": "page" }}
            className="mf-nav-link"
            onClick={() => setMenuOpen(false)}
          >
            <span>{item.label}</span>
            {item.availability === "migration" ? (
              <span className="mf-nav-status">Migration</span>
            ) : null}
          </Link>
        ))}
      </nav>
      <main id="main-content" className="mf-shell-main" tabIndex={-1}>
        {destination ? (
          <p className="mf-page-context">{destination.label}</p>
        ) : null}
        {children}
      </main>
    </div>
  );
}
