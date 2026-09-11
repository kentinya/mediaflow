/**
 * Bounded scan detail page: shows the scan aggregate status, progress,
 * items with paging, lifecycle links, and a cancel button when the
 * backend says the scan is eligible for cancellation.
 *
 * Successful siblings remain visible and terminal; an uncertain effect is
 * never labelled safe to repeat, and a rejected control is never replayed.
 */

import { useCallback, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { submitManualScanCancellation } from "../../shared/api/api-client";
import { manualScanDetailQueryOptions } from "./manual-scan-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function StatusBadge({ status }: { readonly status: string }) {
  return <span className="mf-status-badge">{status}</span>;
}

export function ScanDetailPage() {
  const { taskId } = useParams({ strict: false }) as { taskId: string };
  const token = useAuthToken();
  const [itemCursor, setItemCursor] = useState<string | null>(null);
  const [itemDirection, setItemDirection] = useState<"forward" | "backward">(
    "forward",
  );
  const [cancelResult, setCancelResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  const query = useQuery(
    manualScanDetailQueryOptions(token, {
      taskId,
      itemLimit: 20,
      itemCursor,
    }),
  );

  const cancelMutation = useMutation({
    mutationFn: (tid: string) => submitManualScanCancellation(token, tid),
    retry: false,
    onMutate: () => setCancelResult(null),
    onSuccess: (result) => {
      if (result.ok) {
        setCancelResult({
          ok: true,
          message: "Scan cancellation requested successfully.",
        });
        void query.refetch();
      } else {
        setCancelResult({
          ok: false,
          message:
            result.code === "transport_unavailable"
              ? "The cancel request could not reach the API. Nothing was changed."
              : `Cancel request was rejected (${result.code}). Reload and try again.`,
        });
      }
    },
  });

  const goItemsForward = useCallback(() => {
    if (query.data?.ok === true && query.data.model.itemCursor) {
      setItemCursor(query.data.model.itemCursor);
      setItemDirection("forward");
    }
  }, [query.data]);

  const goItemsBackward = useCallback(() => {
    if (query.data?.ok === true && itemCursor !== null) {
      setItemCursor(null);
      setItemDirection("backward");
    }
  }, [query.data, itemCursor]);

  return (
    <AuthorizedReadBoundary
      query={query}
      unavailableTitle="Scan detail unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Scan detail">
              <p>Requesting the scan document from the API.</p>
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
        const scan = data.model;
        const isTerminal = [
          "completed",
          "partial_success",
          "failed",
          "cancelled",
        ].includes(scan.status);
        const canCancel = !isTerminal && !scan.cancellationRequested;

        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Scan {scan.taskId}</h2>
                <p className="mf-dashboard-meta">
                  Bounded scan document · scope: {displayEnum(scan.scopeKind)}
                  {scan.fileId ? ` · file: ${scan.fileId}` : ""}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Scan aggregate</h3>
              <dl>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={scan.status} />
                </dd>
                <dt>Mode</dt>
                <dd>{scan.mode ? displayEnum(scan.mode) : "—"}</dd>
                <dt>Scope</dt>
                <dd>{displayEnum(scan.scopeKind)}</dd>
                <dt>Source path</dt>
                <dd>{scan.sourcePath}</dd>
                <dt>Storage</dt>
                <dd>{scan.storageId}</dd>
                <dt>Progress</dt>
                <dd>
                  {scan.progress.completed} / {scan.progress.total} completed
                  {scan.progress.failed > 0
                    ? ` (${scan.progress.failed} failed)`
                    : ""}
                </dd>
                <dt>Created</dt>
                <dd>{scan.createdAt}</dd>
                <dt>Updated</dt>
                <dd>{scan.updatedAt}</dd>
                <dt>Reconciliation</dt>
                <dd>
                  {scan.reconciliationComplete ? "Complete" : "In progress"}
                </dd>
                {scan.configurationSnapshotId && (
                  <>
                    <dt>Pinned configuration</dt>
                    <dd>
                      {scan.configurationSnapshotId} (immutable revision
                      identity)
                    </dd>
                  </>
                )}
                <dt>Known effects</dt>
                <dd>{scan.knownEffects}</dd>
                <dt>Side effects</dt>
                <dd>{scan.sideEffects}</dd>
                <dt>Retry safe</dt>
                <dd>{scan.retrySafe ? "Yes" : "No"}</dd>
                {scan.failureStage && (
                  <>
                    <dt>Failure stage</dt>
                    <dd>{displayEnum(scan.failureStage)}</dd>
                  </>
                )}
                {scan.nextAction && (
                  <>
                    <dt>Next action</dt>
                    <dd>{scan.nextAction}</dd>
                  </>
                )}
                {scan.cancellationRequested && (
                  <>
                    <dt>Cancellation</dt>
                    <dd>Cancellation has been requested</dd>
                  </>
                )}
              </dl>
            </section>
            {scan.errors.length > 0 && (
              <section className="mf-count-section">
                <h3>Errors</h3>
                <ul>
                  {scan.errors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </section>
            )}
            <section className="mf-count-section">
              <h3>Items ({scan.items.length} on this page)</h3>
              {scan.items.length === 0 ? (
                <p className="mf-dashboard-meta">
                  No items are visible in this page window.
                </p>
              ) : (
                <>
                  <div style={{ overflowX: "auto" }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Item ID</th>
                          <th>Source</th>
                          <th>Status</th>
                          <th>Stage</th>
                          <th>Created</th>
                          <th>Failure</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scan.items.map((item) => (
                          <tr key={item.itemId}>
                            <td>{item.itemId}</td>
                            <td>
                              {item.storageId}:{item.sourcePath}
                            </td>
                            <td>
                              <StatusBadge status={item.status} />
                            </td>
                            <td>{displayEnum(item.stage)}</td>
                            <td>{item.createdAt}</td>
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
                  <div className="mf-actions">
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={!itemCursor}
                      onClick={goItemsBackward}
                    >
                      Previous items
                    </button>
                    <button
                      type="button"
                      className="mf-button mf-button-secondary"
                      disabled={
                        itemDirection === "forward"
                          ? scan.itemCursor === null
                          : !itemCursor
                      }
                      onClick={goItemsForward}
                    >
                      Next items
                    </button>
                  </div>
                </>
              )}
            </section>
            {canCancel && (
              <div className="mf-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={cancelMutation.isPending}
                  onClick={() => cancelMutation.mutate(scan.taskId)}
                >
                  {cancelMutation.isPending ? "Cancelling…" : "Request cancel"}
                </Button>
              </div>
            )}
            {cancelResult !== null && (
              <StatusBanner
                variant={cancelResult.ok ? "success" : "error"}
                title={cancelResult.ok ? "Cancel requested" : "Cancel failed"}
              >
                <p>{cancelResult.message}</p>
              </StatusBanner>
            )}
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/tasks/$taskId"
                params={{ taskId: scan.taskId }}
              >
                View full Task detail
              </Link>
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
