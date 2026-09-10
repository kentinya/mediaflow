import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import type {
  FileIndexCatalogRecord,
  FileIndexCatalogPage as FileIndexPageModel,
} from "../../entities/library/file-index-catalog";
import type { SystemStatusModel } from "../../entities/library/system-status";
import type { FileIndexRead } from "../../shared/api/api-client";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { Button } from "../../shared/ui/Button";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  emptyFileIndexSearch,
  fileIndexQueryOptions,
  parseFileIndexSearch,
  serializeCatalogReturnContext,
  serializeFileIndexSearch,
  type FileIndexCatalogSearchState,
} from "./file-index-query";
import { systemStatusQueryOptions } from "./system-status-query";

const SCAN_STATUS_OPTIONS = [
  ["discovered", "Discovered"],
  ["unstable", "Unstable"],
  ["ready", "Ready"],
  ["ignored", "Ignored"],
  ["missing", "Missing"],
  ["error", "Error"],
] as const;

const PROCESSING_OPTIONS = [
  ["unknown", "Unknown"],
  ["organized", "Organized"],
  ["skipped", "Skipped"],
  ["attention", "Attention"],
  ["conflict", "Conflict"],
  ["review", "Review"],
  ["partial", "Partial"],
  ["failed", "Failed"],
  ["unverified", "Unverified"],
  ["reprocess_requested", "Reprocess requested"],
] as const;

const FILTER_KEYS = [
  "resourceLibrary",
  "storage",
  "scanStatus",
  "query",
  "processingDisposition",
  "recognitionType",
  "provider",
  "providerId",
  "title",
  "taskId",
  "year",
] as const;

type FilterKey = (typeof FILTER_KEYS)[number];

function valueOrNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function filterSignature(value: FileIndexCatalogSearchState): string {
  return FILTER_KEYS.map((key) => `${key}:${value[key] ?? ""}`).join("|");
}

function hasSubmittedFilters(value: FileIndexCatalogSearchState): boolean {
  return FILTER_KEYS.some((key) => value[key] !== null && value[key] !== "");
}

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "Unavailable / not verified" : value;
}

function formatSize(value: number): string {
  if (value === 0) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function activeResourceLibraries(
  status: SystemStatusModel,
): SystemStatusModel["resourceLibraries"] {
  const storageIds = new Set(status.storages.map((storage) => storage.id));
  return status.resourceLibraries.filter(
    (library) => library.enabled && storageIds.has(library.storageId),
  );
}

function AppliedFilters({
  value,
}: {
  readonly value: FileIndexCatalogSearchState;
}) {
  const entries = FILTER_KEYS.flatMap((key) => {
    const current = value[key];
    return current === null || current === "" ? [] : [[key, current] as const];
  });
  return (
    <section className="mf-applied-filters" aria-label="Submitted filters">
      <h3>Submitted filters</h3>
      {entries.length === 0 ? (
        <p className="mf-dashboard-meta">None — showing the bounded catalog.</p>
      ) : (
        <ul>
          {entries.map(([key, current]) => (
            <li key={key}>
              <span>{filterLabel(key)}:</span> {current}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function filterLabel(key: FilterKey): string {
  const labels: Record<FilterKey, string> = {
    resourceLibrary: "ResourceLibrary",
    storage: "Storage",
    scanStatus: "Discovery status",
    query: "Path or filename",
    processingDisposition: "Processing disposition",
    recognitionType: "Recognition type",
    provider: "Provider",
    providerId: "Provider ID",
    title: "Identity title",
    taskId: "Task ID",
    year: "Year",
  };
  return labels[key];
}

function CatalogFilters({
  status,
  draft,
  applied,
  onChange,
  onSubmit,
  onReset,
}: {
  readonly status: SystemStatusModel;
  readonly draft: FileIndexCatalogSearchState;
  readonly applied: FileIndexCatalogSearchState;
  readonly onChange: (key: FilterKey, value: string) => void;
  readonly onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  readonly onReset: () => void;
}) {
  const libraries = activeResourceLibraries(status);
  const dirty = filterSignature(draft) !== filterSignature(applied);
  return (
    <section
      className="mf-catalog-filters"
      aria-labelledby="catalog-filters-title"
    >
      <div className="mf-section-head">
        <div>
          <h3 id="catalog-filters-title">Search and filters</h3>
          <p className="mf-dashboard-meta">
            Edit the draft, then submit it to query the authoritative bounded
            catalog. Paging never changes these submitted filters.
          </p>
        </div>
        {dirty ? (
          <span className="mf-draft-state" role="status">
            Draft changes not submitted
          </span>
        ) : null}
      </div>
      <form onSubmit={onSubmit}>
        <div className="mf-filter-grid">
          <label className="mf-filter-field" htmlFor="file-index-query">
            Path or filename
            <input
              id="file-index-query"
              value={draft.query ?? ""}
              onChange={(event) => onChange("query", event.target.value)}
              placeholder="Search path or filename"
            />
          </label>
          <label
            className="mf-filter-field"
            htmlFor="file-index-resource-library"
          >
            ResourceLibrary
            <select
              id="file-index-resource-library"
              value={draft.resourceLibrary ?? ""}
              onChange={(event) =>
                onChange("resourceLibrary", event.target.value)
              }
            >
              <option value="">All managed ResourceLibraries</option>
              {libraries.map((library) => (
                <option key={library.id} value={library.id}>
                  {library.name ?? library.id}
                  {library.name === null ? "" : ` (${library.id})`}
                </option>
              ))}
            </select>
          </label>
          <label className="mf-filter-field" htmlFor="file-index-storage">
            Storage
            <select
              id="file-index-storage"
              value={draft.storage ?? ""}
              onChange={(event) => onChange("storage", event.target.value)}
            >
              <option value="">All managed Storages</option>
              {status.storages.map((storage) => (
                <option key={storage.id} value={storage.id}>
                  {storage.name} ({storage.type})
                </option>
              ))}
            </select>
          </label>
          <label className="mf-filter-field" htmlFor="file-index-scan-status">
            Discovery status
            <select
              id="file-index-scan-status"
              value={draft.scanStatus ?? ""}
              onChange={(event) => onChange("scanStatus", event.target.value)}
            >
              <option value="">All discovery statuses</option>
              {SCAN_STATUS_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label
            className="mf-filter-field"
            htmlFor="file-index-processing-disposition"
          >
            Processing disposition
            <select
              id="file-index-processing-disposition"
              value={draft.processingDisposition ?? ""}
              onChange={(event) =>
                onChange("processingDisposition", event.target.value)
              }
            >
              <option value="">All processing dispositions</option>
              {PROCESSING_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label
            className="mf-filter-field"
            htmlFor="file-index-recognition-type"
          >
            Recognition type
            <input
              id="file-index-recognition-type"
              value={draft.recognitionType ?? ""}
              onChange={(event) =>
                onChange("recognitionType", event.target.value)
              }
              placeholder="e.g. Movie"
            />
          </label>
          <label className="mf-filter-field" htmlFor="file-index-provider">
            Provider
            <input
              id="file-index-provider"
              value={draft.provider ?? ""}
              onChange={(event) => onChange("provider", event.target.value)}
              placeholder="e.g. tmdb"
            />
          </label>
          <label className="mf-filter-field" htmlFor="file-index-provider-id">
            Provider ID
            <input
              id="file-index-provider-id"
              value={draft.providerId ?? ""}
              onChange={(event) => onChange("providerId", event.target.value)}
            />
          </label>
          <label className="mf-filter-field" htmlFor="file-index-title">
            Identity title
            <input
              id="file-index-title"
              value={draft.title ?? ""}
              onChange={(event) => onChange("title", event.target.value)}
            />
          </label>
          <label className="mf-filter-field" htmlFor="file-index-task-id">
            Task ID
            <input
              id="file-index-task-id"
              value={draft.taskId ?? ""}
              onChange={(event) => onChange("taskId", event.target.value)}
            />
          </label>
          <label className="mf-filter-field" htmlFor="file-index-year">
            Year
            <input
              id="file-index-year"
              type="number"
              inputMode="numeric"
              min="1870"
              max="2100"
              value={draft.year ?? ""}
              onChange={(event) => onChange("year", event.target.value)}
            />
          </label>
        </div>
        <div className="mf-actions">
          <Button type="submit">Apply filters</Button>
          <Button type="button" variant="secondary" onClick={onReset}>
            Reset filters
          </Button>
        </div>
      </form>
      <AppliedFilters value={applied} />
    </section>
  );
}

function CatalogRecord({
  record,
  returnContext,
}: {
  readonly record: FileIndexCatalogRecord;
  readonly returnContext: FileIndexCatalogSearchState;
}) {
  const identity = record.identitySummary;
  const returnQuery = serializeCatalogReturnContext(returnContext);
  return (
    <li className="mf-catalog-record">
      <article>
        <header className="mf-catalog-record-head">
          <div>
            <h3>
              <Link
                to="/library/file-index/$fileId"
                params={{ fileId: record.fileId }}
                search={
                  returnQuery.length > 0
                    ? (Object.fromEntries(
                        new URLSearchParams(returnQuery),
                      ) as Record<string, string>)
                    : undefined
                }
              >
                {record.filename}
              </Link>
            </h3>
            <p className="mf-dashboard-meta">
              Storage-relative path: {record.path}
            </p>
          </div>
          <span className="mf-record-id">FileIndex record</span>
        </header>
        <div className="mf-catalog-groups">
          <section aria-labelledby={`discovery-${record.fileId}`}>
            <h4 id={`discovery-${record.fileId}`}>Discovery and stability</h4>
            <dl>
              <dt>Discovery status</dt>
              <dd>{displayEnum(record.scanStatus)}</dd>
              <dt>Change evidence</dt>
              <dd>{displayEnum(record.change)}</dd>
              <dt>Size</dt>
              <dd>{formatSize(record.size)}</dd>
              <dt>Modified</dt>
              <dd>{record.modifiedAt}</dd>
              <dt>First seen</dt>
              <dd>{record.firstSeenAt}</dd>
              <dt>Stable since</dt>
              <dd>{safeValue(record.stableSince)}</dd>
              <dt>Last seen</dt>
              <dd>{record.lastSeenAt}</dd>
              <dt>Missing since</dt>
              <dd>{safeValue(record.missingSince)}</dd>
            </dl>
          </section>
          <section aria-labelledby={`occurrence-${record.fileId}`}>
            <h4 id={`occurrence-${record.fileId}`}>Current occurrence</h4>
            <dl>
              <dt>Occurrence state</dt>
              <dd>{displayEnum(record.occurrenceState)}</dd>
              <dt>Current source facts</dt>
              <dd>
                {record.occurrenceState === "verified"
                  ? "Verified for this indexed occurrence"
                  : record.occurrenceState === "legacy"
                    ? "Legacy occurrence; current linkage is unverified"
                    : "Current occurrence is not verified"}
              </dd>
              <dt>Updated</dt>
              <dd>{record.updatedAt}</dd>
            </dl>
          </section>
          <section aria-labelledby={`processing-${record.fileId}`}>
            <h4 id={`processing-${record.fileId}`}>Processing disposition</h4>
            <dl>
              <dt>Disposition</dt>
              <dd>{displayEnum(record.processingDisposition)}</dd>
              <dt>Processing facts</dt>
              <dd>
                Separate from discovery; a list record does not establish
                current Result relevance.
              </dd>
            </dl>
          </section>
          <section aria-labelledby={`identity-${record.fileId}`}>
            <h4 id={`identity-${record.fileId}`}>Identity summary</h4>
            {identity === null ? (
              <p>Identity is unavailable in this bounded catalog result.</p>
            ) : (
              <dl>
                <dt>Title</dt>
                <dd>{safeValue(identity.title)}</dd>
                <dt>Recognition type</dt>
                <dd>{safeValue(identity.recognitionType)}</dd>
                <dt>Provider</dt>
                <dd>{safeValue(identity.provider)}</dd>
                <dt>Provider ID</dt>
                <dd>{safeValue(identity.providerId)}</dd>
                <dt>Year</dt>
                <dd>
                  {identity.year === null
                    ? "Unavailable / not verified"
                    : identity.year}
                </dd>
              </dl>
            )}
          </section>
        </div>
      </article>
    </li>
  );
}

function PageControls({
  applied,
  model,
  onNavigate,
}: {
  readonly applied: FileIndexCatalogSearchState;
  readonly model: FileIndexPageModel;
  readonly onNavigate: (value: FileIndexCatalogSearchState) => void;
}) {
  const first = model.items[0];
  const last = model.items[model.items.length - 1];
  return (
    <div className="mf-actions mf-page-controls" aria-label="FileIndex paging">
      <Button
        type="button"
        variant="secondary"
        disabled={!model.hasPrevious || first === undefined}
        onClick={() => {
          if (first === undefined) return;
          onNavigate({
            ...applied,
            after: null,
            before: first.updatedAt,
            cursorFileId: first.fileId,
          });
        }}
      >
        Previous page
      </Button>
      <Button
        type="button"
        disabled={!model.hasNext || last === undefined}
        onClick={() => {
          if (last === undefined) return;
          onNavigate({
            ...applied,
            after: last.updatedAt,
            before: null,
            cursorFileId: last.fileId,
          });
        }}
      >
        Next page
      </Button>
      <Link className="mf-button mf-button-secondary" to="/library">
        Back to Library
      </Link>
    </div>
  );
}

function CatalogFailure({
  failure,
  onRetry,
  onReset,
  onResetPage,
  onBack,
  retrying,
}: {
  readonly failure: NonNullable<
    Extract<FileIndexRead, { readonly ok: false }>["failure"]
  >;
  readonly onRetry: () => void;
  readonly onReset: () => void;
  readonly onResetPage: () => void;
  readonly onBack: () => void;
  readonly retrying: boolean;
}) {
  const isCursor = failure.kind === "invalid_cursor";
  const isFilter = failure.kind === "invalid_filter";
  return (
    <section className="mf-status mf-status-error" role="alert">
      <h2>{failure.title}</h2>
      <p>
        {isCursor
          ? "This FileIndex page continuation is no longer valid for the submitted query. No work or mutation was started."
          : isFilter
            ? "One or more submitted FileIndex filters are not supported by the authoritative catalog."
            : "The bounded FileIndex read did not complete. No work or mutation was started."}
      </p>
      <p>
        <strong>Next action:</strong> {failure.nextAction}
      </p>
      <div className="mf-actions">
        {isFilter || isCursor ? (
          <Button type="button" onClick={isCursor ? onResetPage : onReset}>
            {isCursor ? "Return to first page" : "Reset filters"}
          </Button>
        ) : (
          <Button type="button" onClick={onRetry} disabled={retrying}>
            {retrying ? "Retrying…" : "Retry read"}
          </Button>
        )}
        <Button type="button" variant="secondary" onClick={onBack}>
          Back to Library
        </Button>
        <a className="mf-button mf-button-secondary" href="/ui">
          Open current Web UI
        </a>
      </div>
    </section>
  );
}

export interface FileIndexCatalogViewProps {
  readonly status: SystemStatusModel;
  readonly applied: FileIndexCatalogSearchState;
  readonly draft: FileIndexCatalogSearchState;
  readonly catalog: FileIndexRead | undefined;
  readonly catalogPending: boolean;
  readonly catalogFetching: boolean;
  readonly onDraftChange: (key: FilterKey, value: string) => void;
  readonly onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  readonly onReset: () => void;
  readonly onResetPage: () => void;
  readonly onRetry: () => void;
  readonly onNavigate: (value: FileIndexCatalogSearchState) => void;
  readonly onRefresh: () => void;
  readonly onBack: () => void;
}

export function FileIndexCatalogView({
  status,
  applied,
  draft,
  catalog,
  catalogPending,
  catalogFetching,
  onDraftChange,
  onSubmit,
  onReset,
  onResetPage,
  onRetry,
  onNavigate,
  onRefresh,
  onBack,
}: FileIndexCatalogViewProps) {
  const libraries = activeResourceLibraries(status);
  if (!status.configurationActive) {
    return (
      <StatusBanner variant="warning" title="No Active runtime">
        <p>
          FileIndex filters use only the exact managed Active runtime. Draft,
          JSON and stale configuration rows are not filter authority.
        </p>
        <div className="mf-actions">
          <Link className="mf-button mf-button-secondary" to="/library">
            Back to Library
          </Link>
          <a className="mf-button mf-button-secondary" href="/ui">
            Open current Web UI
          </a>
        </div>
      </StatusBanner>
    );
  }
  if (libraries.length === 0) {
    return (
      <StatusBanner variant="warning" title="No managed FileIndex scope">
        <p>
          The Active runtime has no enabled ResourceLibrary bound to a
          configured Storage, so there is no honest FileIndex scope to query.
          Configuration changes belong to the current Web UI.
        </p>
        <div className="mf-actions">
          <Link className="mf-button mf-button-secondary" to="/library">
            Back to Library
          </Link>
          <a className="mf-button mf-button-secondary" href="/ui">
            Open current Web UI
          </a>
        </div>
      </StatusBanner>
    );
  }

  return (
    <div className="mf-file-index">
      <header className="mf-dashboard-head">
        <div>
          <h2>FileIndex catalog</h2>
          <p className="mf-dashboard-meta">
            Durable discovery records · read-only · bounded pages
          </p>
        </div>
        <RefreshControl onRefresh={onRefresh} refreshing={catalogFetching} />
      </header>
      <p className="mf-dashboard-meta">
        Storage files answers what is physically present now. FileIndex answers
        what MediaFlow has durably discovered; neither view starts work.
      </p>
      <CatalogFilters
        status={status}
        draft={draft}
        applied={applied}
        onChange={onDraftChange}
        onSubmit={onSubmit}
        onReset={onReset}
      />
      {catalogPending || catalog === undefined ? (
        <StatusBanner variant="info" title="Loading FileIndex catalog">
          <p>
            Requesting one bounded authenticated GET from the FileIndex
            authority.
          </p>
        </StatusBanner>
      ) : !catalog.ok ? (
        <CatalogFailure
          failure={catalog.failure}
          onRetry={onRetry}
          onReset={onReset}
          onResetPage={onResetPage}
          onBack={onBack}
          retrying={catalogFetching}
        />
      ) : catalog.model.items.length === 0 ? (
        <StatusBanner
          variant="info"
          title={
            hasSubmittedFilters(applied)
              ? "No FileIndex records match"
              : applied.after !== null || applied.before !== null
                ? "No records on this page"
                : "FileIndex is empty"
          }
        >
          <p>
            {hasSubmittedFilters(applied)
              ? "The authoritative catalog returned no record for the submitted filters. Reset or narrow the draft and submit again."
              : "No durable discovery records are available in the selected Active scope yet."}
          </p>
          <div className="mf-actions">
            {applied.after !== null || applied.before !== null ? (
              <Button type="button" onClick={onResetPage}>
                Return to first page
              </Button>
            ) : null}
            <Button type="button" onClick={onReset}>
              Reset filters and page
            </Button>
            <Link className="mf-button mf-button-secondary" to="/library">
              Back to Library
            </Link>
          </div>
        </StatusBanner>
      ) : (
        <>
          <ul className="mf-catalog-list" aria-label="FileIndex records">
            {catalog.model.items.map((record) => (
              <CatalogRecord
                key={record.fileId}
                record={record}
                returnContext={applied}
              />
            ))}
          </ul>
          <PageControls
            applied={applied}
            model={catalog.model}
            onNavigate={onNavigate}
          />
        </>
      )}
    </div>
  );
}

export function FileIndexCatalogPage() {
  const navigate = useNavigate();
  const location = useRouterState({ select: (state) => state.location });
  const token = useAuthToken();
  const search = useMemo(
    () => parseFileIndexSearch(new URLSearchParams(location.searchStr ?? "")),
    [location.searchStr],
  );
  const routeSearchKey = serializeFileIndexSearch(search);
  const [draftOverride, setDraftOverride] = useState<{
    readonly routeSearchKey: string;
    readonly value: FileIndexCatalogSearchState;
  } | null>(null);
  const draft =
    draftOverride?.routeSearchKey === routeSearchKey
      ? draftOverride.value
      : search;

  const status = useQuery(systemStatusQueryOptions(token));
  const statusReady =
    status.data?.configurationActive === true &&
    activeResourceLibraries(status.data).length > 0;
  const catalog = useQuery(fileIndexQueryOptions(token, search, statusReady));

  const goToSearch = (next: FileIndexCatalogSearchState) => {
    const encoded = serializeFileIndexSearch(next);
    void navigate({
      to:
        encoded.length > 0
          ? `/library/file-index?${encoded}`
          : "/library/file-index",
    });
  };
  const updateDraft = (key: FilterKey, value: string) => {
    setDraftOverride({
      routeSearchKey,
      value: { ...draft, [key]: valueOrNull(value) },
    });
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    goToSearch({
      ...draft,
      after: null,
      before: null,
      cursorFileId: null,
    });
  };
  const reset = () => {
    const empty = emptyFileIndexSearch();
    setDraftOverride({ routeSearchKey, value: empty });
    goToSearch(empty);
  };
  const resetPage = () => {
    const firstPage = {
      ...search,
      after: null,
      before: null,
      cursorFileId: null,
    };
    setDraftOverride({ routeSearchKey, value: firstPage });
    goToSearch(firstPage);
  };
  const navigatePage = (next: FileIndexCatalogSearchState) => {
    goToSearch(next);
  };

  return (
    <AuthorizedReadBoundary
      query={status}
      unavailableTitle="Library unavailable"
    >
      {({
        data: statusData,
        isPending: statusPending,
        refresh: refreshStatus,
      }) => {
        if (statusPending || statusData === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Library">
              <p>Loading the exact managed Active runtime filter authority.</p>
            </StatusBanner>
          );
        }
        if (
          !statusData.configurationActive ||
          activeResourceLibraries(statusData).length === 0
        ) {
          return (
            <FileIndexCatalogView
              status={statusData}
              applied={search}
              draft={draft}
              catalog={undefined}
              catalogPending={false}
              catalogFetching={false}
              onDraftChange={updateDraft}
              onSubmit={submit}
              onReset={reset}
              onResetPage={resetPage}
              onRetry={() => undefined}
              onNavigate={navigatePage}
              onRefresh={refreshStatus}
              onBack={() => void navigate({ to: "/library" })}
            />
          );
        }
        return (
          <AuthorizedReadBoundary
            query={catalog}
            unavailableTitle="FileIndex unavailable"
          >
            {({ data, isPending, isFetching, refresh }) => (
              <FileIndexCatalogView
                status={statusData}
                applied={search}
                draft={draft}
                catalog={data}
                catalogPending={isPending}
                catalogFetching={isFetching}
                onDraftChange={updateDraft}
                onSubmit={submit}
                onReset={reset}
                onResetPage={resetPage}
                onRetry={refresh}
                onNavigate={navigatePage}
                onRefresh={() => {
                  refreshStatus();
                  refresh();
                }}
                onBack={() => void navigate({ to: "/library" })}
              />
            )}
          </AuthorizedReadBoundary>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
