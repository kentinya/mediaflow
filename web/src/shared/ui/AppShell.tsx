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
import { AboutAttributionCard } from "../../features/about/AboutAttribution";
import { AuthControls } from "../auth/AuthControls";
import {
  destinationForPath,
  shellDestinations,
  shellPageForPath,
  type ShellPageId,
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

/**
 * The Automation inventory and the routes that render it as their background.
 *
 * Create and edit are the same operator surface as the list: they only add a
 * card over it. The shared shell must therefore not print its own English
 * location line above that list, and must not reserve the line's space, so the
 * background never shifts when the card opens or closes.
 */
function isAutomationListSurface(pathname: string): boolean {
  return (
    pathname === "/operations/automation" ||
    pathname === "/operations/automation/new" ||
    pathname === "/operations/automation/lifecycle" ||
    pathname.startsWith("/operations/automation/lifecycle/")
  );
}

const FilesSearchContext = createContext<FilesSearchContextValue>({
  query: "",
  setQuery: () => undefined,
  subscribeToQueryChange: () => () => undefined,
});

export function useFilesSearch(): FilesSearchContextValue {
  return useContext(FilesSearchContext);
}

interface StorageSearchContextValue {
  readonly query: string;
  readonly setQuery: (query: string) => void;
}

const StorageSearchContext = createContext<StorageSearchContextValue>({
  query: "",
  setQuery: () => undefined,
});

export function useStorageSearch(): StorageSearchContextValue {
  return useContext(StorageSearchContext);
}

/**
 * How long the shell entry keeps owning the visual handoff after its one
 * opacity transition starts. Content elements mounting inside this window
 * must not stack a second fade over the page entry (Slice52 RO-3), while a
 * read that resolves later still gets its own single content settle.
 */
const ENTRY_WINDOW_MS = 320;

/**
 * The one persistent main-content surface that plays the shared page
 * transition.
 *
 * The wrapper and the routed subtree inside it stay mounted while only the
 * arrived sidebar identity changes. Keying this wrapper by identity would
 * remount AuthBoundary and the Outlet during a navigation handoff, letting the
 * previous page's mount effects write into the new location and breaking
 * authentication continuation. A same-page child route, query, tab, filter,
 * card or refresh keeps the identity and never starts a new entry.
 *
 * `entryVersion` advances only for a real main-page change. On that render the
 * start class is applied immediately; the next frame removes it and the
 * entering class runs one opacity transition. The start class is never
 * re-added for the same version, so a same-page overlay (which suppresses the
 * transient opacity through `:has(...)` in the stylesheet) cannot replay the
 * entry when it closes. While that one transition plays, the surface also
 * carries `mf-page-surface-entry-active` so a content region mounting in the
 * same handoff (storage and both library settles) is not faded twice.
 */
function ShellPageSurface({
  identity,
  entryVersion,
  children,
}: {
  readonly identity: ShellPageId | undefined;
  readonly entryVersion: number;
  readonly children: ReactNode;
}) {
  const [startedVersion, setStartedVersion] = useState(entryVersion);
  const [starting, setStarting] = useState(false);
  const [entryActive, setEntryActive] = useState(false);
  if (startedVersion !== entryVersion) {
    setStartedVersion(entryVersion);
    setStarting(true);
    setEntryActive(true);
  }
  useEffect(() => {
    if (!starting) return;
    const frame = window.requestAnimationFrame(() => setStarting(false));
    return () => window.cancelAnimationFrame(frame);
  }, [starting]);
  useEffect(() => {
    if (!entryActive) return undefined;
    const clear = window.setTimeout(
      () => setEntryActive(false),
      ENTRY_WINDOW_MS,
    );
    return () => window.clearTimeout(clear);
  }, [entryActive, entryVersion]);
  const entering = entryVersion > 0;
  return (
    <div
      className={[
        "mf-page-surface",
        entering ? "mf-page-surface-entering" : "",
        starting ? "mf-page-surface-enter-start" : "",
        entryActive ? "mf-page-surface-entry-active" : "",
      ]
        .filter((value) => value !== "")
        .join(" ")}
      data-main-page={identity ?? "outside"}
      data-page-transition={entering ? "enter" : "initial"}
    >
      {children}
    </div>
  );
}

/** Shared feature-independent V2 shell and operator-goal navigation. */
export function AppShell({ children }: AppShellProps) {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const destination = destinationForPath(pathname);
  const pageIdentity = shellPageForPath(pathname);
  // The shell and its routed subtree stay mounted across route changes. Only
  // the arrived sidebar identity advances the presentation entry version; a
  // same-page child/query update keeps it unchanged. The update runs during
  // render so the new identity and its start class commit together, while
  // AuthBoundary and the Outlet keep their ordinary Router-managed lifecycle.
  const [pageSurfaceState, setPageSurfaceState] = useState({
    identity: pageIdentity,
    entryVersion: 0,
  });
  if (pageSurfaceState.identity !== pageIdentity) {
    setPageSurfaceState({
      identity: pageIdentity,
      entryVersion: pageSurfaceState.entryVersion + 1,
    });
  }
  const [menuOpen, setMenuOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [filesSearch, setFilesSearch] = useState("");
  const [storageSearch, setStorageSearch] = useState("");
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
  const searchIsFiles =
    pathname === "/resourcelib/files" || pathname === "/medialib/files";
  const searchIsStorage = pathname === "/storage";
  // The task center's eight views have no shared keyword search: its All view
  // owns only the creation-time range, and the other views own their own
  // explicit filters. Account/notification controls stay in the top bar.
  const searchIsOperations = pathname === "/operations";
  const searchIsRules = pathname === "/rules";
  // Explore owns its one labelled workspace region and its own works search.
  // It has no separate visible page title; the shell's read-only file-search
  // field and duplicate location line would only add an unusable placeholder.
  const searchIsExplore = pathname === "/explore";
  const filesSearchContext = useMemo(
    () => ({
      query: filesSearch,
      setQuery: setFilesSearchValue,
      subscribeToQueryChange,
    }),
    [filesSearch, setFilesSearchValue, subscribeToQueryChange],
  );
  const storageSearchContext = useMemo(
    () => ({
      query: storageSearch,
      setQuery: setStorageSearch,
    }),
    [storageSearch],
  );
  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);

  const searchField = (
    <div className="mf-shell-search">
      <Icon name="search" />
      <input
        type="search"
        aria-label={
          searchIsStorage ? "搜索存储、路径" : "搜索文件、文件夹或媒体库"
        }
        placeholder={
          searchIsStorage ? "搜索存储、路径..." : "搜索文件、文件夹或媒体库..."
        }
        value={
          searchIsFiles ? filesSearch : searchIsStorage ? storageSearch : ""
        }
        onChange={(event) => {
          if (searchIsStorage) setStorageSearch(event.target.value);
          else setFilesSearch(event.target.value);
        }}
        readOnly={!searchIsFiles && !searchIsStorage}
      />
    </div>
  );
  const shellActions = (
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
  );

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
            // Shared sidebar destinations are ordinary page navigation.  The
            // task center no longer creates an organizing journey from a
            // filtered list, so its Files link must not manufacture or carry a
            // `returnOps` marker (including when Files already has one).  An
            // explicit task/preparation/organize journey keeps its own bounded
            // return context on its own links; only those links read it.
            return (
              <Link
                key={item.id}
                to={item.path as string}
                search={{}}
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
          <button
            id="about-attribution-entry"
            type="button"
            className="mf-nav-link mf-nav-about"
            aria-haspopup="dialog"
            aria-expanded={aboutOpen}
            onClick={() => setAboutOpen(true)}
          >
            <Icon name="info" />
            <span>关于与鸣谢</span>
          </button>
        </nav>
      </aside>
      <div className="mf-shell-content">
        <header className="mf-shell-topbar">
          {!searchIsOperations &&
            !searchIsRules &&
            !searchIsExplore &&
            searchField}
          {shellActions}
        </header>
        <main id="main-content" className="mf-shell-main" tabIndex={-1}>
          <ShellPageSurface
            identity={pageIdentity}
            entryVersion={pageSurfaceState.entryVersion}
          >
            {destination !== undefined &&
            destination.id !== "operations" &&
            !isAutomationListSurface(pathname) &&
            !searchIsRules &&
            !searchIsExplore ? (
              <p className="mf-page-context">{destination.label}</p>
            ) : null}
            <FilesSearchContext.Provider value={filesSearchContext}>
              <StorageSearchContext.Provider value={storageSearchContext}>
                {children}
              </StorageSearchContext.Provider>
            </FilesSearchContext.Provider>
          </ShellPageSurface>
        </main>
      </div>
      {aboutOpen ? (
        <AboutAttributionCard onClose={() => setAboutOpen(false)} />
      ) : null}
    </div>
  );
}
