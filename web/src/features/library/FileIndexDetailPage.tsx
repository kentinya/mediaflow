import { Link, useParams, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import type {
  FileDetailCheckpoint,
  FileDetailEvidenceRecord,
  FileDetailEvidenceSection,
  FileDetailEvidenceValue,
  FileDetailModel,
  FileDetailResult,
} from "../../entities/library/file-detail";
import type { SystemStatusModel } from "../../entities/library/system-status";
import type { FileDetailRead } from "../../shared/api/api-client";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { Button } from "../../shared/ui/Button";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import {
  parseCatalogReturnContext,
  serializeFileIndexSearch,
  type FileIndexCatalogSearchState,
} from "./file-index-query";
import { fileDetailQueryOptions } from "./file-detail-query";
import { systemStatusQueryOptions } from "./system-status-query";
import { manualActionsQueryOptions } from "../operations/manual-actions-query";
import type { ManualActionMatrixModel } from "../../entities/operations/manual-actions";

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

function storageParentDir(path: string): string {
  const index = path.lastIndexOf("/");
  return index === -1 ? "" : path.slice(0, index);
}

function catalogReturnUrl(context: FileIndexCatalogSearchState): string {
  const encoded = serializeFileIndexSearch(context);
  return encoded.length > 0
    ? `/library/file-index?${encoded}`
    : "/library/file-index";
}

/**
 * The physical-context link is offered only when the record's Storage is part
 * of the current managed Active runtime, so the destination can honestly open
 * the directory. A stale or draft Storage id never produces a browse link.
 */
function StorageBackLink({
  status,
  model,
}: {
  readonly status: SystemStatusModel;
  readonly model: FileDetailModel;
}) {
  const activeStorage = status.storages.some(
    (storage) => storage.id === model.record.storageId,
  );
  const activeResourceLibrary = status.resourceLibraries.some(
    (library) =>
      library.id === model.record.resourceLibraryId &&
      library.enabled &&
      library.storageId === model.record.storageId,
  );
  if (!status.configurationActive || !activeStorage || !activeResourceLibrary) {
    return (
      <p className="mf-dashboard-meta">
        The recorded Storage and ResourceLibrary are not a matching enabled pair
        in the current managed Active runtime, so no physical location is
        offered.
      </p>
    );
  }
  const parent = storageParentDir(model.record.path);
  return (
    <Link
      className="mf-button mf-button-secondary"
      to="/library/files"
      search={{
        storage: model.record.storageId,
        resourceLibrary: model.record.resourceLibraryId,
        path: parent === "" ? undefined : parent,
      }}
    >
      Open physical location
    </Link>
  );
}

function TruncatedNote({
  section,
  label = section,
  truncated,
}: {
  readonly section: string;
  readonly label?: string;
  readonly truncated: Readonly<Record<string, boolean>>;
}) {
  if (truncated[section] !== true) {
    return null;
  }
  return (
    <p className="mf-dashboard-meta">
      More {label} records exist for this entry; they are not loaded by this
      bounded read.
    </p>
  );
}

function relevanceSentence(model: FileDetailModel): string {
  if (model.priorResultRelevance.current) {
    return "The current Result is linked to the present occurrence.";
  }
  if (model.priorResultRelevance.historicalOnly) {
    return "Only historical Results are available; they do not describe the present occurrence.";
  }
  return "Result relevance is not established for this entry.";
}

function evidenceKeyLabel(key: string): string {
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase())
    .replace(/\bId\b/g, "ID");
}

function evidenceValueText(value: FileDetailEvidenceValue): string {
  if (value === null) {
    return "Unavailable / not verified";
  }
  if (Array.isArray(value)) {
    return value.map((entry) => evidenceValueText(entry)).join(", ");
  }
  if (typeof value === "object") {
    return Object.entries(value)
      .map(
        ([key, entry]) =>
          `${evidenceKeyLabel(key)}: ${evidenceValueText(entry)}`,
      )
      .join("; ");
  }
  return String(value);
}

function EvidenceFacts({
  facts,
  emptyLabel = "No additional bounded facts were captured.",
}: {
  readonly facts: FileDetailEvidenceRecord | null;
  readonly emptyLabel?: string;
}) {
  if (facts === null || Object.keys(facts).length === 0) {
    return <p>{emptyLabel}</p>;
  }
  return (
    <dl>
      {Object.entries(facts).map(([key, value]) => (
        <div key={key}>
          <dt>{evidenceKeyLabel(key)}</dt>
          <dd>{evidenceValueText(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function EvidenceItemFacts({
  items,
}: {
  readonly items: readonly FileDetailEvidenceRecord[];
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <>
      <p>Bounded item evidence ({items.length}):</p>
      <ul>
        {items.map((item, index) => (
          <li key={index}>
            <EvidenceFacts
              facts={item}
              emptyLabel="No named item facts were captured."
            />
          </li>
        ))}
      </ul>
    </>
  );
}

function EvidenceSectionView({
  section,
}: {
  readonly section: FileDetailEvidenceSection;
}) {
  return (
    <div>
      <h5>{displayEnum(section.name)} evidence</h5>
      {section.available ? (
        <>
          <EvidenceFacts facts={section.value} />
          <EvidenceItemFacts items={section.items} />
          {section.warnings.length === 0 ? null : (
            <>
              <p>Warnings:</p>
              <ul>
                {section.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </>
          )}
        </>
      ) : (
        <p>
          Unavailable —{" "}
          {section.unavailableReason ?? "this section was not captured"}
        </p>
      )}
      {section.truncated ? (
        <p className="mf-dashboard-meta">
          More bounded facts exist for this section; they were not loaded.
        </p>
      ) : null}
    </div>
  );
}

function CheckpointFacts({
  checkpoint,
}: {
  readonly checkpoint: FileDetailCheckpoint;
}) {
  return (
    <div>
      <dl>
        <dt>Checkpoint status</dt>
        <dd>{displayEnum(checkpoint.status)}</dd>
        <dt>Checkpoint stage</dt>
        <dd>{displayEnum(checkpoint.stage)}</dd>
        <dt>Attempts</dt>
        <dd>
          {checkpoint.attempts === null
            ? "Unavailable / not verified"
            : checkpoint.attempts}
        </dd>
        <dt>Effect certainty</dt>
        <dd>{displayEnum(checkpoint.effects.certainty)}</dd>
        <dt>Retry safety</dt>
        <dd>{displayEnum(checkpoint.retrySafety)}</dd>
        <dt>Configuration availability</dt>
        <dd>
          {checkpoint.configuration.resolvable === null
            ? "Not checked"
            : checkpoint.configuration.resolvable
              ? "Resolvable"
              : `Unavailable${checkpoint.configuration.reason === null ? "" : ` — ${displayEnum(checkpoint.configuration.reason)}`}`}
        </dd>
        <dt>Checkpoint updated</dt>
        <dd>{checkpoint.updatedAt}</dd>
      </dl>
      {checkpoint.blocker === null &&
      checkpoint.blockers.length === 0 ? null : (
        <p>
          Blocker:{" "}
          {displayEnum(
            checkpoint.blocker?.kind ??
              checkpoint.blockers[0]?.kind ??
              "unknown",
          )}{" "}
          ·{" "}
          {displayEnum(
            checkpoint.blocker?.status ??
              checkpoint.blockers[0]?.status ??
              "unknown",
          )}
        </p>
      )}
      {checkpoint.effects.completedOperations.length === 0 ? null : (
        <p>
          Completed operations:{" "}
          {checkpoint.effects.completedOperations.join(", ")}
        </p>
      )}
      {checkpoint.effects.uncertainEffects.length === 0 ? null : (
        <p>
          Uncertain effects: {checkpoint.effects.uncertainEffects.join(", ")}
        </p>
      )}
      {checkpoint.failure === null ? null : (
        <div>
          <p>Checkpoint failure explanation: {checkpoint.failure.message}</p>
          <p>
            Durable state: {checkpoint.failure.durableState} · side effects:{" "}
            {checkpoint.failure.sideEffects} · safe to retry:{" "}
            {checkpoint.failure.retrySafe ? "yes" : "no"}
          </p>
          <p>Next action: {checkpoint.failure.nextAction}</p>
        </div>
      )}
      {checkpoint.failure === null && checkpoint.nextAction !== null ? (
        <p>Next action: {checkpoint.nextAction}</p>
      ) : null}
      {checkpoint.actions.length === 0 ? null : (
        <ul>
          {checkpoint.actions.map((action, index) => (
            <li key={index}>
              {action.label} —{" "}
              {action.admissible
                ? "available in the current workflow"
                : "not admissible"}
              ;{" "}
              {action.confirmationRequired
                ? "confirmation required"
                : "no confirmation required"}
              ; V2 does not execute it.
            </li>
          ))}
        </ul>
      )}
      {checkpoint.refusalReason === null ? null : (
        <p>Continuation unavailable: {checkpoint.refusalReason}</p>
      )}
    </div>
  );
}

function DetailResultLine({
  result,
  caption,
}: {
  readonly result: FileDetailResult;
  readonly caption: string;
}) {
  return (
    <p>
      {caption} {result.resultId} · {displayEnum(result.status)} ·{" "}
      {result.createdAt} · recognition {safeValue(result.recognitionType)} ·{" "}
      {safeValue(result.provider)}
      {result.providerId === null ? "" : ` #${result.providerId}`} ·{" "}
      {safeValue(result.title)} · metadata {safeValue(result.metadataPolicyId)}{" "}
      · naming {safeValue(result.namingPolicyId)} · classification{" "}
      {safeValue(result.classificationPolicyId)} · organize{" "}
      {safeValue(result.organizePolicyId)} · operation{" "}
      {safeValue(result.operation)} · destination{" "}
      {safeValue(result.destinationPath)} · effect{" "}
      {result.effectCertainty === null
        ? "not recorded"
        : displayEnum(result.effectCertainty)}{" "}
      ·{" "}
      {result.current
        ? "current occurrence"
        : result.relevance === null
          ? "relevance not established"
          : displayEnum(result.relevance)}
      {result.errorPresent ? " · a bounded failure was recorded" : ""}
    </p>
  );
}

export function FileIndexDetailSections({
  model,
}: {
  readonly model: FileDetailModel;
}) {
  const record = model.record;
  const identity = record.identitySummary;
  const resultLines = (
    <>
      {model.latestResult === null ? null : (
        <DetailResultLine result={model.latestResult} caption="Latest Result" />
      )}
      {model.results.map((result) => (
        <DetailResultLine
          key={result.resultId}
          result={result}
          caption="Result"
        />
      ))}
    </>
  );
  return (
    <div className="mf-catalog-groups">
      <section aria-labelledby="detail-source">
        <h4 id="detail-source">Source and library</h4>
        <dl>
          <dt>Storage-relative path</dt>
          <dd>{record.path}</dd>
          <dt>Filename</dt>
          <dd>{record.filename}</dd>
          <dt>Extension</dt>
          <dd>{safeValue(record.extension)}</dd>
          <dt>Size</dt>
          <dd>{formatSize(record.size)}</dd>
          <dt>Storage</dt>
          <dd>{record.storageId}</dd>
          <dt>ResourceLibrary</dt>
          <dd>{record.resourceLibraryId}</dd>
        </dl>
      </section>
      <section aria-labelledby="detail-discovery">
        <h4 id="detail-discovery">Discovery and stability</h4>
        <dl>
          <dt>Discovery status</dt>
          <dd>{displayEnum(record.scanStatus)}</dd>
          <dt>Change evidence</dt>
          <dd>{displayEnum(record.change)}</dd>
          <dt>First seen</dt>
          <dd>{record.firstSeenAt}</dd>
          <dt>Last seen</dt>
          <dd>{record.lastSeenAt}</dd>
          <dt>Stable since</dt>
          <dd>{safeValue(record.stableSince)}</dd>
          <dt>Missing since</dt>
          <dd>{safeValue(record.missingSince)}</dd>
          <dt>Modified</dt>
          <dd>{record.modifiedAt}</dd>
          <dt>Record updated</dt>
          <dd>{record.updatedAt}</dd>
        </dl>
      </section>
      <section aria-labelledby="detail-occurrence">
        <h4 id="detail-occurrence">Current occurrence</h4>
        <dl>
          <dt>Occurrence state</dt>
          <dd>{displayEnum(record.occurrenceState)}</dd>
          <dt>Occurrence identifier</dt>
          <dd>{safeValue(model.occurrenceId)}</dd>
          <dt>Fingerprint provenance</dt>
          <dd>
            {safeValue(model.fingerprintAlgorithm)} — only the algorithm name is
            displayed; fingerprint values are never exposed to this page.
          </dd>
        </dl>
        <TruncatedNote
          section="occurrenceHistory"
          truncated={model.truncated}
        />
        {model.occurrenceHistory.length === 0 ? (
          <p>No bounded occurrence history was returned.</p>
        ) : (
          <ul>
            {model.occurrenceHistory.map((occurrence, index) => (
              <li key={`${occurrence.occurrenceId ?? "legacy"}-${index}`}>
                {occurrence.current ? "Current" : "Historical"} ·{" "}
                {displayEnum(occurrence.state)} · identifier{" "}
                {safeValue(occurrence.occurrenceId)} · first seen{" "}
                {safeValue(occurrence.firstSeenAt)} · last seen{" "}
                {safeValue(occurrence.lastSeenAt)} · superseded{" "}
                {safeValue(occurrence.supersededAt)}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="detail-processing">
        <h4 id="detail-processing">Processing state</h4>
        <dl>
          <dt>Disposition</dt>
          <dd>{displayEnum(record.processingDisposition)}</dd>
          <dt>Effect certainty</dt>
          <dd>{displayEnum(model.processing.effectCertainty)}</dd>
          <dt>Retry safety</dt>
          <dd>{displayEnum(model.processing.retrySafety)}</dd>
          <dt>Recorded next action</dt>
          <dd>{safeValue(model.processing.nextAction)}</dd>
          <dt>Processing result</dt>
          <dd>{safeValue(model.processing.resultId)}</dd>
          <dt>Processing updated</dt>
          <dd>{safeValue(model.processing.updatedAt)}</dd>
        </dl>
        <p className="mf-dashboard-meta">
          These are durable facts recorded by the organizer. This page never
          starts, continues or replays processing.
        </p>
      </section>
      <section aria-labelledby="detail-identity">
        <h4 id="detail-identity">Identity and policy evidence</h4>
        {identity === null ? (
          <p>Identity is unavailable in this detail record.</p>
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
        <p>
          <strong>Result relevance:</strong> {relevanceSentence(model)}
        </p>
        <TruncatedNote section="results" truncated={model.truncated} />
        {model.latestResult === null && model.results.length === 0 ? (
          <p>No organize Result records are attached to this entry.</p>
        ) : (
          <div>{resultLines}</div>
        )}
      </section>
      <section aria-labelledby="detail-items">
        <h4 id="detail-items">Task items</h4>
        <TruncatedNote section="items" truncated={model.truncated} />
        {model.items.length === 0 ? (
          <p>No bounded task-item records reference this entry.</p>
        ) : (
          <ul>
            {model.items.map((item) => (
              <li key={`${item.taskId}-${item.itemId}`}>
                Task {item.taskId} · item {item.itemId} ·{" "}
                {displayEnum(item.status)} · stage {displayEnum(item.stage)} ·{" "}
                {item.current
                  ? "present occurrence"
                  : item.relevance === null
                    ? "relevance not established"
                    : displayEnum(item.relevance)}{" "}
                · checkpoint{" "}
                {item.checkpointAvailable ? "available" : "not available"} ·
                updated {item.updatedAt}
                {item.checkpoint === null ? null : (
                  <div className="mf-dashboard-meta">
                    <CheckpointFacts checkpoint={item.checkpoint} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="detail-reviews">
        <h4 id="detail-reviews">Related reviews</h4>
        <TruncatedNote
          section="reviews"
          label="review"
          truncated={model.truncated}
        />
        {model.relatedReviews.length === 0 ? (
          <p>No review records are attached to this entry.</p>
        ) : (
          <ul>
            {model.relatedReviews.map((review) => (
              <li key={`${review.kind}-${review.reviewId}`}>
                {displayEnum(review.kind)} review {review.reviewId} ·{" "}
                {displayEnum(review.status)}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="detail-evidence">
        <h4 id="detail-evidence">Organize evidence</h4>
        <p>
          {model.evidenceAvailability === "available"
            ? "Bounded evidence summaries are attached to this record."
            : "Evidence is unavailable for this record. This page does not re-collect evidence."}
        </p>
        <TruncatedNote section="evidence" truncated={model.truncated} />
        {model.evidence.map((evidence, index) => (
          <div key={`${evidence.outcome}-${index}`}>
            <p>
              Outcome {displayEnum(evidence.outcome)} · captured{" "}
              {safeValue(evidence.capturedAt)} ·{" "}
              {evidence.errorPresent
                ? "a bounded evidence failure was recorded"
                : "no evidence error"}
              {evidence.truncated ? " · truncated" : ""}
            </p>
            {evidence.warnings.length === 0 ? null : (
              <>
                <p>Evidence warnings:</p>
                <ul>
                  {evidence.warnings.map((warning, warningIndex) => (
                    <li key={warningIndex}>{warning}</li>
                  ))}
                </ul>
              </>
            )}
            {Object.values(evidence.sections).map((section) => (
              <EvidenceSectionView key={section.name} section={section} />
            ))}
          </div>
        ))}
      </section>
      <section aria-labelledby="detail-reprocess">
        <h4 id="detail-reprocess">Reprocess eligibility</h4>
        <p>
          {model.reprocess.eligible
            ? "A reprocess request would be admissible for this record."
            : `A reprocess request is not admissible: ${model.reprocess.reason}`}
        </p>
        <p className="mf-dashboard-meta">
          Eligibility is an explanation only. This read-only page cannot create
          or continue a reprocess request.
        </p>
        {model.reprocessRequests.length === 0 ? null : (
          <ul>
            {model.reprocessRequests.map((request) => (
              <li key={request.requestId}>
                Request {request.requestId} · {displayEnum(request.status)} ·{" "}
                {request.nextAction}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="detail-actions">
        <h4 id="detail-actions">Manual operations</h4>
        <p className="mf-dashboard-meta">
          The actions below are computed by the backend for the exact
          authenticated principal, current source and runtime readiness. Scan
          discovers and indexes source files; Preview runs the complete pipeline
          with zero Storage mutation.
        </p>
        {model.currentActions.length === 0 ? (
          <p>No current action is admissible for this record.</p>
        ) : (
          <ul>
            {model.currentActions.map((action, index) => (
              <li key={`${action.label}-${index}`}>
                {action.label} —{" "}
                {action.admissible
                  ? "admissible in the current Web UI"
                  : "not admissible"}{" "}
                ·{" "}
                {action.confirmationRequired
                  ? "confirmation required"
                  : "no confirmation required"}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export interface FileIndexDetailViewProps {
  readonly status: SystemStatusModel;
  readonly fileId: string;
  readonly detail: FileDetailRead | undefined;
  readonly detailPending: boolean;
  readonly detailFetching: boolean;
  readonly returnContext: FileIndexCatalogSearchState;
  readonly onRetry: () => void;
  readonly onRefresh: () => void;
  readonly actionMatrix:
    | { readonly ok: true; readonly model: ManualActionMatrixModel }
    | { readonly ok: false; readonly failure: unknown }
    | undefined;
  readonly actionMatrixPending: boolean;
  readonly resourceLibraryId: string | null;
}

export function FileIndexDetailView({
  status,
  fileId,
  detail,
  detailPending,
  detailFetching,
  returnContext,
  onRetry,
  onRefresh,
  actionMatrix,
  actionMatrixPending,
  resourceLibraryId,
}: FileIndexDetailViewProps) {
  const backUrl = catalogReturnUrl(returnContext);
  const backActions = (
    <div className="mf-actions">
      <Link className="mf-button mf-button-secondary" to={backUrl}>
        Back to FileIndex catalog
      </Link>
      <Link className="mf-button mf-button-secondary" to="/library">
        Back to Library
      </Link>
      <a className="mf-button mf-button-secondary" href="/ui">
        Open current Web UI
      </a>
    </div>
  );
  return (
    <div className="mf-file-index">
      <header className="mf-dashboard-head">
        <div>
          <h2>FileIndex record</h2>
          <p className="mf-dashboard-meta">
            Read-only detail for {fileId} · nothing on this page moves, renames
            or deletes a file, or starts work
          </p>
        </div>
        <RefreshControl onRefresh={onRefresh} refreshing={detailFetching} />
      </header>
      {detailPending || detail === undefined ? (
        <StatusBanner variant="info" title="Loading FileIndex detail">
          <p>Requesting one bounded authenticated GET for this record.</p>
        </StatusBanner>
      ) : !detail.ok ? (
        <section className="mf-status mf-status-error" role="alert">
          <h2>{detail.failure.title}</h2>
          <p>
            The bounded FileIndex detail read did not complete. No work or
            mutation was started.
          </p>
          <p>
            <strong>Next action:</strong> {detail.failure.nextAction}
          </p>
          <div className="mf-actions">
            <Button type="button" onClick={onRetry} disabled={detailFetching}>
              {detailFetching ? "Retrying…" : "Retry read"}
            </Button>
          </div>
          {backActions}
        </section>
      ) : (
        <>
          <FileIndexDetailSections model={detail.model} />
          <section className="mf-count-section">
            <h3>Actions for this file</h3>
            {actionMatrixPending ? (
              <p className="mf-dashboard-meta">
                Loading action availability from the backend.
              </p>
            ) : actionMatrix?.ok && actionMatrix.model ? (
              <div className="mf-actions">
                {actionMatrix.model.actions.scan.available ? (
                  <Link
                    className="mf-button mf-button-primary"
                    to="/operations/scan/new"
                    search={{
                      scopeKind: "file",
                      fileId,
                      resourceLibraryId: resourceLibraryId ?? undefined,
                    }}
                  >
                    Start bounded Scan
                  </Link>
                ) : (
                  <p className="mf-dashboard-meta">
                    Scan unavailable:{" "}
                    {actionMatrix.model.actions.scan.reason ?? "not available"}
                  </p>
                )}
                {actionMatrix.model.actions.preview.available ? (
                  <Link
                    className="mf-button mf-button-primary"
                    to="/operations/preview/new"
                    search={{
                      scopeKind: "file",
                      fileId,
                      resourceLibraryId: resourceLibraryId ?? undefined,
                    }}
                  >
                    Run zero-mutation Preview
                  </Link>
                ) : (
                  <p className="mf-dashboard-meta">
                    Preview unavailable:{" "}
                    {actionMatrix.model.actions.preview.reason ??
                      "not available"}
                  </p>
                )}
                {actionMatrix.model.actions.organize.available ? (
                  <Link
                    className="mf-button mf-button-primary"
                    to="/operations/organize/new"
                    search={{
                      scopeKind: "file",
                      fileId,
                      resourceLibraryId: resourceLibraryId ?? undefined,
                    }}
                  >
                    Prepare manual organize
                  </Link>
                ) : (
                  <p className="mf-dashboard-meta">
                    Manual organize unavailable:{" "}
                    {actionMatrix.model.actions.organize.reason ??
                      "not available"}
                  </p>
                )}
              </div>
            ) : (
              <p className="mf-dashboard-meta">
                Action availability could not be loaded. No actions are offered.
              </p>
            )}
          </section>
          <div className="mf-actions">
            <StorageBackLink status={status} model={detail.model} />
          </div>
          {backActions}
        </>
      )}
    </div>
  );
}

export function FileIndexDetailPage() {
  const { fileId } = useParams({ from: "/library/file-index/$fileId" });
  const location = useRouterState({ select: (state) => state.location });
  const token = useAuthToken();
  const returnContext = parseCatalogReturnContext(
    new URLSearchParams(location.searchStr ?? ""),
  );
  const status = useQuery(systemStatusQueryOptions(token));
  const storageIds = new Set(
    (status.data?.storages ?? []).map((storage) => storage.id),
  );
  const statusReady =
    status.data?.configurationActive === true &&
    status.data.resourceLibraries.some(
      (library) => library.enabled && storageIds.has(library.storageId),
    );
  const detail = useQuery(
    fileDetailQueryOptions(
      token,
      fileId,
      returnContext.resourceLibrary,
      statusReady,
    ),
  );

  // Fetch the manual action matrix for this file
  // Use the loaded record's resourceLibraryId when available, falling back to
  // the URL return context for when the detail hasn't loaded yet.
  const recordResourceLibraryId =
    detail.data?.ok === true
      ? detail.data.model.record.resourceLibraryId
      : (returnContext.resourceLibrary ?? null);
  const actionMatrixQuery = useQuery(
    manualActionsQueryOptions(
      token,
      {
        scopeKind: "file",
        fileId,
        resourceLibraryId: recordResourceLibraryId,
      },
      statusReady && recordResourceLibraryId !== null,
    ),
  );

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
              <p>Loading the exact managed Active runtime authority.</p>
            </StatusBanner>
          );
        }
        if (!statusData.configurationActive) {
          return (
            <StatusBanner variant="warning" title="No Active runtime">
              <p>
                FileIndex detail is only meaningful against the exact managed
                Active runtime. Draft, JSON and stale configuration rows are not
                display authority.
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
        if (!statusReady) {
          return (
            <StatusBanner variant="warning" title="No managed FileIndex scope">
              <p>
                The Active runtime has no enabled ResourceLibrary bound to a
                configured Storage, so this detail cannot be read from an
                authoritative scope.
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
          <AuthorizedReadBoundary
            query={detail}
            unavailableTitle="FileIndex detail unavailable"
          >
            {({
              data: detailData,
              isPending: detailPending,
              isFetching: detailFetching,
              refresh,
            }) => (
              <FileIndexDetailView
                status={statusData}
                fileId={fileId}
                detail={detailData}
                detailPending={detailPending}
                detailFetching={detailFetching}
                returnContext={returnContext}
                onRetry={refresh}
                onRefresh={() => {
                  refreshStatus();
                  refresh();
                }}
                actionMatrix={actionMatrixQuery.data}
                actionMatrixPending={actionMatrixQuery.isPending}
                resourceLibraryId={returnContext.resourceLibrary ?? null}
              />
            )}
          </AuthorizedReadBoundary>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
