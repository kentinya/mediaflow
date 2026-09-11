/**
 * Bounded preview detail page: shows the preview aggregate status, items
 * with source/choice/plan, zero-mutation badge and configuration pin
 * (snapshotId only, no digest).
 *
 * Preview is visibly DryRun/analysis, produces no Storage mutation and
 * no execution authority. This page never starts, continues or replays
 * processing.
 */

import { useParams } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
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
                  {displayEnum(preview.scopeKind)} ·{" "}
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
                <dd>{displayEnum(preview.scopeKind)}</dd>
                <dt>Scope ID</dt>
                <dd>{preview.scopeId}</dd>
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
                {preview.executionState && (
                  <>
                    <dt>Execution state</dt>
                    <dd>{displayEnum(preview.executionState)}</dd>
                  </>
                )}
                {preview.selection && (
                  <>
                    <dt>Selection</dt>
                    <dd>{preview.selection}</dd>
                  </>
                )}
                {preview.nextAction && (
                  <>
                    <dt>Next action</dt>
                    <dd>{preview.nextAction}</dd>
                  </>
                )}
              </dl>
            </section>
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
                            {item.sourceStorageId}:{item.sourcePath}
                          </td>
                          <td>{safeValue(item.recognitionType)}</td>
                          <td>{safeValue(item.title)}</td>
                          <td>
                            {safeValue(item.provider)}
                            {item.providerId ? ` #${item.providerId}` : ""}
                          </td>
                          <td>{safeValue(item.targetPath)}</td>
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
