/**
 * Bounded Preview detail page: shows the preview aggregate status, the exact
 * source scope, the item findings the backend persisted (recognition,
 * metadata identity, policies, bounded proposed target, attachments,
 * capabilities, conflicts, warnings) and the configuration pin (snapshot ID
 * only, no digest).
 *
 * Preview is visibly DryRun/analysis, produces no Storage mutation and no
 * execution authority. This page never starts, continues or replays
 * processing, and it renders only what the backend document contains: an
 * absent finding stays visibly absent instead of being fabricated.
 */

import { useParams } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import type {
  ManualPreviewItemModel,
  ManualPreviewPoliciesModel,
} from "../../entities/operations/preview";
import { useAuthToken } from "../../shared/api/auth-context";
import { manualPreviewDetailQueryOptions } from "./manual-preview-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function StatusBadge({ status }: { readonly status: string }) {
  return <span className="mf-status-badge">{status}</span>;
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

function targetLabel(item: {
  readonly targetStorageId: string | null;
  readonly targetPath: string | null;
}): string {
  if (item.targetPath === null) {
    return "—";
  }
  return item.targetStorageId === null
    ? item.targetPath
    : `${item.targetStorageId}:${item.targetPath}`;
}

function numberLabel(value: number | null): string {
  return value === null ? "—" : String(value);
}

function PolicyFindings({
  policies,
}: {
  readonly policies: ManualPreviewPoliciesModel | null;
}) {
  if (policies === null) {
    return <p className="mf-dashboard-meta">No policy mapping was recorded.</p>;
  }
  return (
    <dl>
      <dt>RecognitionType policy</dt>
      <dd>{safeValue(policies.recognitionTypePolicyId)}</dd>
      <dt>Metadata policy</dt>
      <dd>{safeValue(policies.metadataPolicyId)}</dd>
      <dt>Naming policy</dt>
      <dd>{safeValue(policies.namingPolicyId)}</dd>
      <dt>Classification policy</dt>
      <dd>{safeValue(policies.classificationPolicyId)}</dd>
      <dt>Organize policy</dt>
      <dd>{safeValue(policies.organizePolicyId)}</dd>
    </dl>
  );
}

function PipelineFindings({ item }: { readonly item: ManualPreviewItemModel }) {
  const analysis = item.analysis;
  return (
    <>
      <h4>Resolved policies</h4>
      <PolicyFindings policies={item.policies} />
      <h4>Pipeline analysis</h4>
      {analysis === null ? (
        <p className="mf-dashboard-meta">No pipeline analysis was recorded.</p>
      ) : (
        <>
          <section>
            <h5>Parse</h5>
            {analysis.parse === null ? (
              <p className="mf-dashboard-meta">
                No parse finding was recorded.
              </p>
            ) : (
              <dl>
                <dt>Title candidate</dt>
                <dd>{safeValue(analysis.parse.titleCandidate)}</dd>
                <dt>Year</dt>
                <dd>{numberLabel(analysis.parse.year)}</dd>
                <dt>Season / episode</dt>
                <dd>
                  {numberLabel(analysis.parse.season)} /{" "}
                  {numberLabel(analysis.parse.episode)}
                </dd>
                <dt>Resolution / source</dt>
                <dd>
                  {safeValue(analysis.parse.resolution)} /{" "}
                  {safeValue(analysis.parse.source)}
                </dd>
                <dt>Codec / audio / HDR</dt>
                <dd>
                  {safeValue(analysis.parse.videoCodec)} /{" "}
                  {safeValue(analysis.parse.audio)} /{" "}
                  {safeValue(analysis.parse.hdr)}
                </dd>
                <dt>Evidence</dt>
                <dd>
                  {analysis.parse.evidence.length === 0
                    ? "—"
                    : analysis.parse.evidence
                        .map((evidence) =>
                          [evidence.field, evidence.value, evidence.source]
                            .filter((value): value is string => value !== null)
                            .join(" · "),
                        )
                        .join("; ")}
                </dd>
              </dl>
            )}
          </section>
          <section>
            <h5>Recognition</h5>
            {analysis.recognition === null ? (
              <p className="mf-dashboard-meta">
                No recognition finding was recorded.
              </p>
            ) : (
              <dl>
                <dt>Status / type</dt>
                <dd>
                  {safeValue(analysis.recognition.status)} /{" "}
                  {safeValue(analysis.recognition.recognitionTypeId)}
                </dd>
                <dt>Rule / confidence / score</dt>
                <dd>
                  {safeValue(analysis.recognition.ruleId)} /{" "}
                  {safeValue(analysis.recognition.confidence)} /{" "}
                  {numberLabel(analysis.recognition.score)}
                </dd>
                <dt>Reasons</dt>
                <dd>
                  {analysis.recognition.reasons.length === 0
                    ? "—"
                    : analysis.recognition.reasons
                        .map((reason) =>
                          [reason.code, reason.message]
                            .filter((value): value is string => value !== null)
                            .join(": "),
                        )
                        .join("; ")}
                </dd>
              </dl>
            )}
          </section>
          <section>
            <h5>Metadata</h5>
            {analysis.metadata === null ? (
              <p className="mf-dashboard-meta">
                No metadata finding was recorded.
              </p>
            ) : (
              <dl>
                <dt>Available / status</dt>
                <dd>
                  {analysis.metadata.available ? "Yes" : "No"} /{" "}
                  {safeValue(analysis.metadata.status)}
                </dd>
                <dt>Query</dt>
                <dd>{safeValue(analysis.metadata.query)}</dd>
                <dt>Match</dt>
                <dd>
                  {analysis.metadata.match === null
                    ? "—"
                    : `${safeValue(analysis.metadata.match.status)} · ${analysis.metadata.match.candidateCount} candidate(s)`}
                </dd>
              </dl>
            )}
          </section>
          <section>
            <h5>Naming</h5>
            {analysis.naming === null ? (
              <p className="mf-dashboard-meta">
                No naming finding was recorded.
              </p>
            ) : (
              <dl>
                <dt>Available / policy</dt>
                <dd>
                  {analysis.naming.available ? "Yes" : "No"} /{" "}
                  {safeValue(analysis.naming.policyId)}
                </dd>
                <dt>Directory / filename</dt>
                <dd>
                  {safeValue(analysis.naming.directory)} /{" "}
                  {safeValue(analysis.naming.filename)}
                </dd>
                <dt>Reason</dt>
                <dd>{safeValue(analysis.naming.reason)}</dd>
              </dl>
            )}
          </section>
          <section>
            <h5>Classification</h5>
            {analysis.classification === null ? (
              <p className="mf-dashboard-meta">
                No classification finding was recorded.
              </p>
            ) : (
              <dl>
                <dt>Available / status</dt>
                <dd>
                  {analysis.classification.available ? "Yes" : "No"} /{" "}
                  {safeValue(analysis.classification.status)}
                </dd>
                <dt>MediaLibrary / relative path</dt>
                <dd>
                  {safeValue(analysis.classification.mediaLibraryId)} /{" "}
                  {safeValue(analysis.classification.relativePath)}
                </dd>
                <dt>Matched rule</dt>
                <dd>
                  {safeValue(analysis.classification.matchedRuleId)} /{" "}
                  {safeValue(analysis.classification.matchedRuleName)}
                </dd>
                <dt>Evidence</dt>
                <dd>
                  {analysis.classification.evidence.length === 0
                    ? "—"
                    : analysis.classification.evidence.join("; ")}
                </dd>
              </dl>
            )}
          </section>
        </>
      )}
    </>
  );
}

export function PreviewDetailPage() {
  const { previewId } = useParams({ strict: false }) as {
    previewId: string;
  };
  const token = useAuthToken();

  const query = useQuery(manualPreviewDetailQueryOptions(token, previewId));

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Preview detail unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Preview detail">
              <p>Requesting the preview document from the API.</p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner variant="error" title={data.failure.title}>
              <p>{data.failure.nextAction}</p>
              <div className="mf-actions">
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                >
                  Back to Operations
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const preview = data.model;

        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Preview {preview.previewId}</h2>
                <p className="mf-dashboard-meta">
                  Bounded preview document · scope:{" "}
                  {preview.scopeKind ? displayEnum(preview.scopeKind) : "—"} ·{" "}
                  <span className="mf-status-badge">Zero-mutation</span>
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Preview aggregate</h3>
              <dl>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={preview.status} />
                </dd>
                <dt>Zero-mutation</dt>
                <dd>
                  {preview.zeroMutation
                    ? "Yes — no Storage mutation was performed"
                    : "Not confirmed"}
                </dd>
                <dt>Scope kind</dt>
                <dd>
                  {preview.scopeKind ? displayEnum(preview.scopeKind) : "—"}
                </dd>
                <dt>Scope ID</dt>
                <dd>{safeValue(preview.scopeId)}</dd>
                <dt>Actor</dt>
                <dd>{preview.actor}</dd>
                <dt>Current</dt>
                <dd>{preview.current ? "Yes" : "No"}</dd>
                <dt>Created</dt>
                <dd>{preview.createdAt}</dd>
                <dt>Updated</dt>
                <dd>{preview.updatedAt}</dd>
                {preview.configurationSnapshotId && (
                  <>
                    <dt>Pinned configuration</dt>
                    <dd>
                      {preview.configurationSnapshotId} (immutable revision
                      identity)
                    </dd>
                  </>
                )}
                {preview.intentId && (
                  <>
                    <dt>Intent ID</dt>
                    <dd>{preview.intentId}</dd>
                  </>
                )}
                {preview.intentVersion !== null && (
                  <>
                    <dt>Intent version</dt>
                    <dd>{preview.intentVersion}</dd>
                  </>
                )}
                <dt>Side effects</dt>
                <dd>{preview.sideEffects}</dd>
                <dt>Truncated</dt>
                <dd>{preview.truncated ? "Yes" : "No"}</dd>
                <dt>Selected items</dt>
                <dd>{preview.selection.selectedItemIds.length}</dd>
                {preview.executionState && (
                  <>
                    <dt>Execution state</dt>
                    <dd>{displayEnum(preview.executionState)}</dd>
                  </>
                )}
                {preview.nextAction && (
                  <>
                    <dt>Next action</dt>
                    <dd>{preview.nextAction}</dd>
                  </>
                )}
              </dl>
              {preview.executionState === "not_available_in_this_task" && (
                <p className="mf-dashboard-meta">
                  This Preview carries no execution authority: organizing the
                  reviewed items is a separate explicit manual step.
                </p>
              )}
            </section>
            {preview.failure && (
              <section className="mf-count-section">
                <h3>Failure</h3>
                <dl>
                  <dt>Category</dt>
                  <dd>{preview.failure.category}</dd>
                  <dt>What happened</dt>
                  <dd>{preview.failure.message}</dd>
                  <dt>Next action</dt>
                  <dd>{preview.failure.nextAction}</dd>
                </dl>
              </section>
            )}
            <section className="mf-count-section">
              <h3>Items ({preview.items.length})</h3>
              {preview.items.length === 0 ? (
                <p className="mf-dashboard-meta">
                  No preview items were produced. This may indicate the source
                  had no processable files.
                </p>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Item ID</th>
                        <th>Source</th>
                        <th>Recognition</th>
                        <th>Title</th>
                        <th>Provider</th>
                        <th>Target</th>
                        <th>Policy</th>
                        <th>Status</th>
                        <th>Failure</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.items.map((item) => (
                        <tr key={item.itemId}>
                          <td>{item.itemId}</td>
                          <td>
                            {safeValue(item.sourceStorageId)}:
                            {safeValue(item.sourcePath)}
                          </td>
                          <td>{safeValue(item.recognitionType)}</td>
                          <td>{safeValue(item.title)}</td>
                          <td>
                            {safeValue(item.provider)}
                            {item.providerId ? ` #${item.providerId}` : ""}
                          </td>
                          <td>{targetLabel(item)}</td>
                          <td>{safeValue(item.organizePolicy)}</td>
                          <td>
                            <StatusBadge status={item.status} />
                          </td>
                          <td>
                            {item.failure
                              ? `${item.failure.category}: ${item.failure.nextAction}`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
            {preview.items.map((item) => (
              <section
                className="mf-count-section"
                key={`detail-${item.itemId}`}
              >
                <h3>
                  Findings for {item.title ?? item.sourcePath ?? item.itemId}
                </h3>
                <dl>
                  <dt>Stage</dt>
                  <dd>{displayEnum(item.stage)}</dd>
                  <dt>Plan status</dt>
                  <dd>{safeValue(item.planStatus)}</dd>
                  <dt>Target</dt>
                  <dd>{targetLabel(item)}</dd>
                  <dt>Capabilities</dt>
                  <dd>
                    {item.capabilities
                      ? `${safeValue(item.capabilities.verdict)}${
                          item.capabilities.missing.length > 0
                            ? ` — missing: ${item.capabilities.missing.join(", ")}`
                            : ""
                        }`
                      : "—"}
                  </dd>
                </dl>
                <h4>Attachments ({item.attachments.length})</h4>
                {item.attachments.length === 0 ? (
                  <p className="mf-dashboard-meta">
                    No sidecar attachment was planned for this item.
                  </p>
                ) : (
                  <ul>
                    {item.attachments.map((attachment, index) => (
                      <li key={`${item.itemId}-attachment-${index}`}>
                        {safeValue(attachment.type)}
                        {attachment.language
                          ? ` · language ${attachment.language}`
                          : ""}
                        {attachment.operation
                          ? ` · ${attachment.operation}`
                          : ""}
                        {attachment.filename ? ` · ${attachment.filename}` : ""}
                      </li>
                    ))}
                  </ul>
                )}
                <h4>Conflicts ({item.conflicts.length})</h4>
                {item.conflicts.length === 0 ? (
                  <p className="mf-dashboard-meta">
                    No conflict was recorded for this item.
                  </p>
                ) : (
                  <ul>
                    {item.conflicts.map((conflict, index) => (
                      <li key={`${item.itemId}-conflict-${index}`}>
                        {safeValue(conflict.type)}
                        {conflict.destination
                          ? ` · target ${conflict.destination}`
                          : ""}
                        {conflict.details ? ` · ${conflict.details}` : ""}
                      </li>
                    ))}
                  </ul>
                )}
                <h4>Warnings ({item.warnings.length})</h4>
                {item.warnings.length === 0 ? (
                  <p className="mf-dashboard-meta">No warning was recorded.</p>
                ) : (
                  <ul>
                    {item.warnings.map((warning, index) => (
                      <li key={`${item.itemId}-warning-${index}`}>{warning}</li>
                    ))}
                  </ul>
                )}
                {item.failure && (
                  <p className="mf-dashboard-meta">
                    {item.failure.message} — {item.failure.nextAction}
                  </p>
                )}
                <PipelineFindings item={item} />
              </section>
            ))}
            <div className="mf-actions">
              <Link className="mf-button mf-button-secondary" to="/operations">
                Back to Operations
              </Link>
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
