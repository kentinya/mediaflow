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
import {
  isRuleFamily,
  RULES_HEADER_SEARCH_LABEL,
  RULES_HEADER_SEARCH_PLACEHOLDER,
  RULES_OVERVIEW_SEARCH_HINT,
  RULES_OVERVIEW_SEARCH_PLACEHOLDER,
  RULES_WORKSPACE_DESCRIPTION,
  RULES_WORKSPACE_TITLE,
} from "../../entities/rules/rules-workspace";
import {
  operationsReturnContextFromSearch,
  operationsReturnSearch,
  parseOperationsReturnContext,
  readOperationsReturnContext,
} from "../navigation/operations-return";
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

interface RulesSearchContextValue {
  readonly query: string;
  readonly setQuery: (query: string) => void;
  /**
   * True only while the Rules workspace is on its read-only Overview, where the
   * family keyword scope does not exist. The header input is then visibly
   * inapplicable instead of advertising a fabricated global search.
   */
  readonly inapplicable: boolean;
}

const RulesSearchContext = createContext<RulesSearchContextValue>({
  query: "",
  setQuery: () => undefined,
  inapplicable: true,
});

export function useRulesSearch(): RulesSearchContextValue {
  return useContext(RulesSearchContext);
}

/** The Rules workspace owns its own header composition inside the shared shell. */
function rulesSectionOf(searchStr: string): string | null {
  const section = new URLSearchParams(searchStr).get("section");
  return isRuleFamily(section) ? section : null;
}

/** Shared feature-independent V2 shell and operator-goal navigation. */
export function AppShell({ children }: AppShellProps) {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const searchStr = useRouterState({
    select: (state) => state.location.searchStr ?? "",
  });
  const destination = destinationForPath(pathname);
  const [menuOpen, setMenuOpen] = useState(false);
  const [filesSearch, setFilesSearch] = useState("");
  const [storageSearch, setStorageSearch] = useState("");
  const [rulesSearch, setRulesSearch] = useState("");
  const filesSearchListeners = useRef(new Set<() => void>());
  const setFilesSearchValue = useCallback((value: string) => {
    setFilesSearch(value);
    for (const listener of filesSearchListeners.current) listener();
  }, []);
  const subscribeToQueryChange = useCallback((listener: () => void) => {
    filesSearchListeners.current.add(listener);
    return () => filesSearchListeners.current.delete(listener);
  }, []);
  // RO-2: ResourceLibrary Files is the only normal entry for a new
  // file-selection-based organizing request.  A journey that began in the task
  // center must therefore keep that exact bounded return context when the
  // operator continues through the shell instead of the removed creation CTA:
  // on the task-center route the current, already-validated list filters become
  // the context, and everywhere else the context this journey already carries is
  // preserved.  Only grammar-validated keys travel, so a tampered value degrades
  // to the default list view rather than another page or population.
  const filesJourneyReturnContext = useMemo(() => {
    // One consistent source of truth: the router's own committed search.  The
    // router publishes the new location state as soon as it renders the target
    // route, while the browser's address bar is only updated when that history
    // action flushes; reading ``window.location`` here therefore raced the very
    // filter submission this link must carry and produced an empty context.
    // The router search is also the only value a route's own validation has
    // already admitted, so this memo cannot pick up an unvalidated key.
    const search = Object.fromEntries(new URLSearchParams(searchStr));
    const existing = readOperationsReturnContext(search);
    if (pathname !== "/operations") return existing;
    return operationsReturnContextFromSearch({
      ...parseOperationsReturnContext(existing),
      ...search,
    });
  }, [pathname, searchStr]);
  const pageTitle =
    destination?.title ??
    (pathname === "/" ? "Connect | MediaFlow" : "MediaFlow");
  const searchIsFiles =
    pathname === "/resourcelib/files" || pathname === "/medialib/files";
  const searchIsStorage = pathname === "/storage";
  // Only the Rules workspace route gets the Rules header. The dedicated Edit
  // route is a distinct full-page state with its own subject heading, so the
  // shared shell must not add a second Rules title above it.
  const searchIsRules = pathname === "/rules";
  const rulesSection = searchIsRules ? rulesSectionOf(searchStr) : null;
  const rulesSearchInapplicable = searchIsRules && rulesSection === null;
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
  const rulesSearchContext = useMemo(
    () => ({
      query: rulesSearch,
      setQuery: setRulesSearch,
      inapplicable: rulesSearchInapplicable,
    }),
    [rulesSearch, rulesSearchInapplicable],
  );

  useEffect(() => {
    document.title = pageTitle;
  }, [pageTitle]);

  // The functional keyword input is one shared element for every route; the
  // Rules header places it inside its own title row, other routes keep the
  // existing right-aligned top bar.
  const searchField = (
    <div className="mf-shell-search">
      <Icon name="search" />
      <input
        type="search"
        aria-label={
          searchIsRules
            ? RULES_HEADER_SEARCH_LABEL
            : searchIsStorage
              ? "搜索存储、路径"
              : "搜索文件、文件夹或媒体库"
        }
        placeholder={
          searchIsRules
            ? rulesSearchInapplicable
              ? RULES_OVERVIEW_SEARCH_PLACEHOLDER
              : RULES_HEADER_SEARCH_PLACEHOLDER
            : searchIsStorage
              ? "搜索存储、路径..."
              : "搜索文件、文件夹或媒体库..."
        }
        title={rulesSearchInapplicable ? RULES_OVERVIEW_SEARCH_HINT : undefined}
        value={
          searchIsFiles
            ? filesSearch
            : searchIsStorage
              ? storageSearch
              : searchIsRules
                ? rulesSearch
                : ""
        }
        onChange={(event) => {
          if (searchIsStorage) setStorageSearch(event.target.value);
          else if (searchIsRules) setRulesSearch(event.target.value);
          else setFilesSearch(event.target.value);
        }}
        readOnly={!searchIsFiles && !searchIsStorage && !searchIsRules}
        disabled={rulesSearchInapplicable}
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
            // RO-2: ResourceLibrary Files is the only normal entry for a new
            // file-selection-based organizing request, so a journey that began in
            // the task center must keep that exact bounded return context when the
            // operator continues through the shell instead of a removed creation
            // CTA.  Only the already-parsed, grammar-validated context is carried;
            // every other destination keeps its plain link, and a tampered context
            // degrades to no context (never to another page or population).
            const carried =
              item.id === "files"
                ? operationsReturnSearch(filesJourneyReturnContext)
                : {};
            return (
              <Link
                key={item.id}
                to={item.path as string}
                search={carried}
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
      </aside>
      <div className="mf-shell-content">
        <header
          className={`mf-shell-topbar${searchIsRules ? " mf-shell-topbar-rules" : ""}`}
        >
          {searchIsRules ? (
            // The reference row hierarchy: title, functional keyword search and
            // the existing account/notification controls on one row, then the
            // business description as a separate full-width line below it.
            <div className="mf-rules-topbar">
              <div className="mf-rules-topbar-row">
                <h1>{RULES_WORKSPACE_TITLE}</h1>
                {searchField}
                {shellActions}
              </div>
              <p className="mf-rules-topbar-description">
                {RULES_WORKSPACE_DESCRIPTION}
              </p>
            </div>
          ) : (
            <>
              {searchField}
              {shellActions}
            </>
          )}
        </header>
        <main id="main-content" className="mf-shell-main" tabIndex={-1}>
          {destination ? (
            <p className="mf-page-context">{destination.label}</p>
          ) : null}
          <FilesSearchContext.Provider value={filesSearchContext}>
            <StorageSearchContext.Provider value={storageSearchContext}>
              <RulesSearchContext.Provider value={rulesSearchContext}>
                {children}
              </RulesSearchContext.Provider>
            </StorageSearchContext.Provider>
          </FilesSearchContext.Provider>
        </main>
      </div>
    </div>
  );
}
