import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { AuthControls } from "../auth/AuthControls";
import {
  destinationForPath,
  shellDestinations,
} from "../navigation/destination-model";
import { Icon } from "./Icons";

export interface AppShellProps {
  readonly children: ReactNode;
}

interface FilesSearchContextValue {
  readonly query: string;
  readonly setQuery: (query: string) => void;
  readonly subscribeToQueryChange: (listener: () => void) => () => void;
}

const FilesSearchContext = createContext<FilesSearchContextValue>({
  query: "",
  setQuery: () => undefined,
  subscribeToQueryChange: () => () => undefined,
});

export function useFilesSearch(): FilesSearchContextValue {
  return useContext(FilesSearchContext);
}

/** Shared feature-independent V2 shell and operator-goal navigation. */
export function AppShell({ children }: AppShellProps) {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const destination = destinationForPath(pathname);
  const [menuOpen, setMenuOpen] = useState(false);
  const [filesSearch, setFilesSearch] = useState("");
  const filesSearchListeners = useRef(new Set<() => void>());
  const setFilesSearchValue = useCallback((value: string) => {
    setFilesSearch(value);
    for (const listener of filesSearchListeners.current) listener();
  }, []);
  const subscribeToQueryChange = useCallback((listener: () => void) => {
    filesSearchListeners.current.add(listener);
    return () => filesSearchListeners.current.delete(listener);
  }, []);
  const pageTitle =
    destination?.title ??
    (pathname === "/" ? "Connect | MediaFlow" : "MediaFlow");
  const searchIsFiles = pathname === "/library/files";
  const searchContext = useMemo(
    () => ({
      query: filesSearch,
      setQuery: setFilesSearchValue,
      subscribeToQueryChange,
    }),
    [filesSearch, setFilesSearchValue, subscribeToQueryChange],
  );

  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);

  return (
    <div className="mf-shell">
      <a className="mf-skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="mf-shell-sidebar">
        <div className="mf-brand">
          <span className="mf-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 36">
              <path d="M4 3.5 27.5 18 4 32.5z" fill="none" />
            </svg>
          </span>
          <div>
            <span className="mf-eyebrow">MediaFlow</span>
            <span className="mf-brand-subtitle">影视媒体资源管理系统</span>
          </div>
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
        <nav
          id="primary-navigation"
          className={`mf-primary-nav${menuOpen ? " mf-primary-nav-open" : ""}`}
          aria-label="Primary"
        >
          {shellDestinations.map((item) => {
            const active = item.isActive(pathname);
            return (
              <Link
                key={item.id}
                to={item.path as string}
                aria-label={item.ariaLabel}
                aria-current={active ? "page" : undefined}
                className={`mf-nav-link${active ? " is-active" : ""}`}
                onClick={() => setMenuOpen(false)}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mf-storage-status" aria-label="系统存储">
          <strong>系统存储</strong>
          <div className="mf-storage-meter" aria-hidden="true">
            <span />
          </div>
          <div className="mf-storage-status-meta">
            <span>12.4 TB / 20 TB</span>
            <span>62%</span>
          </div>
        </div>
      </aside>
      <div className="mf-shell-content">
        <header className="mf-shell-topbar">
          <div className="mf-shell-search">
            <Icon name="search" />
            <input
              type="search"
              aria-label="搜索文件、文件夹或媒体库"
              placeholder="搜索文件、文件夹或媒体库..."
              value={searchIsFiles ? filesSearch : ""}
              onChange={(event) => setFilesSearch(event.target.value)}
              readOnly={!searchIsFiles}
            />
          </div>
          <div className="mf-shell-actions">
            <button
              type="button"
              className="mf-notification-button"
              aria-label="通知"
              title="通知"
            >
              <Icon name="bell" />
            </button>
            <AuthControls />
          </div>
        </header>
        <main id="main-content" className="mf-shell-main" tabIndex={-1}>
          {destination ? (
            <p className="mf-page-context">{destination.label}</p>
          ) : null}
          <FilesSearchContext.Provider value={searchContext}>
            {children}
          </FilesSearchContext.Provider>
        </main>
      </div>
    </div>
  );
}
