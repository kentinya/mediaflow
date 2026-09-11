/**
 * Scan admission page: shows the backend action matrix for the exact
 * authenticated principal, current source/scope and runtime readiness,
 * then submits one bounded server-bound scan admission.
 *
 * The operator selects the exact ResourceLibrary scope (when the route does
 * not already carry one) and the bounded Scan mode from what the backend
 * advertises. Nothing is defaulted locally, no action is offered when the
 * backend does not advertise it, and a rejected admission is never replayed:
 * the operator must read the current state again and submit anew.
 *
 * After admission the operator is sent to the durable Scan detail for the
 * newly created work. This page never holds the browser request open.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { submitServerBoundScan } from "../../shared/api/api-client";
import { manualActionsQueryOptions } from "./manual-actions-query";
import { workerReadinessQueryKey } from "./worker-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";
import type { ManualActionMatrixModel } from "../../entities/operations/manual-actions";
import type { ScanMode } from "../../entities/operations/scan";

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function SourceIdentity({
  matrix,
}: {
  readonly matrix: ManualActionMatrixModel;
}) {
  return (
    <section className="mf-count-section">
      <h3>Source identity</h3>
      <dl>
        <dt>Scope kind</dt>
        <dd>{matrix.scopeKind ? displayEnum(matrix.scopeKind) : "—"}</dd>
        {matrix.fileId && (
          <>
            <dt>File ID</dt>
            <dd>{matrix.fileId}</dd>
          </>
        )}
        {matrix.resourceLibraryId && (
          <>
            <dt>ResourceLibrary ID</dt>
            <dd>{matrix.resourceLibraryId}</dd>
          </>
        )}
        {matrix.source?.filename && (
          <>
            <dt>Filename</dt>
            <dd>{matrix.source.filename}</dd>
          </>
        )}
        {matrix.source?.path && (
          <>
            <dt>Storage-relative path</dt>
            <dd>{matrix.source.path}</dd>
          </>
        )}
        {matrix.source?.storageId && (
          <>
            <dt>Storage</dt>
            <dd>{matrix.source.storageId}</dd>
          </>
        )}
        {matrix.source?.occurrenceState && (
          <>
            <dt>Occurrence state</dt>
            <dd>{displayEnum(matrix.source.occurrenceState)}</dd>
          </>
        )}
        {matrix.source?.scanStatus && (
          <>
            <dt>Scan status</dt>
            <dd>{displayEnum(matrix.source.scanStatus)}</dd>
          </>
        )}
      </dl>
    </section>
  );
}

function ActionAvailability({
  label,
  available,
  reason,
  nextAction,
}: {
  readonly label: string;
  readonly available: boolean;
  readonly reason: string | null;
  readonly nextAction: string | null;
}) {
  return (
    <div>
      <h4>{label}</h4>
      <p>
        {available ? (
          <span className="mf-status-badge">Available</span>
        ) : (
          <>
            Not available
            {reason ? `: ${reason}` : ""}
          </>
        )}
      </p>
      {nextAction && <p className="mf-dashboard-meta">{nextAction}</p>}
    </div>
  );
}

export function ScanNewPage() {
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const rawScopeKind = String(searchParams.scopeKind ?? "");
  const scopeKind =
    rawScopeKind === "file" || rawScopeKind === "resourceLibrary"
      ? (rawScopeKind as "file" | "resourceLibrary")
      : null;
  const fileId = searchParams.fileId ? String(searchParams.fileId) : undefined;
  const resourceLibraryId = searchParams.resourceLibraryId
    ? String(searchParams.resourceLibraryId)
    : undefined;

  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<ScanMode>("full");

  const matrixQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind,
      fileId: fileId ?? null,
      resourceLibraryId: resourceLibraryId ?? null,
    }),
  );

  const [admissionResult, setAdmissionResult] = useState<{
    ok: boolean;
    message: string;
    taskId?: string;
  } | null>(null);

  const scanMutation = useMutation({
    mutationFn: (exactMode: ScanMode) =>
      submitServerBoundScan(token, {
        scopeKind: scopeKind as "file" | "resourceLibrary",
        fileId: fileId ?? null,
        resourceLibraryId: resourceLibraryId ?? null,
        mode: exactMode,
      }),
    retry: false,
    onMutate: () => setAdmissionResult(null),
    onSuccess: (result, submittedMode) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [workerReadinessQueryKey],
        });
        setAdmissionResult({
          ok: true,
          message: "Scan admitted successfully",
          taskId: result.model.taskId,
        });
        // The admitted durable state stays visible for a moment before the
        // operator is continued to the durable Scan detail; nothing is
        // resubmitted and the explicit link below remains available.
        window.setTimeout(() => {
          void navigate({
            to: "/operations/scan/$taskId",
            params: { taskId: result.model.taskId },
          });
        }, 600);
      } else {
        setAdmissionResult({
          ok: false,
          message:
            result.code === "transport_unavailable"
              ? "The scan admission could not reach the API. Nothing was started."
              : `Scan admission was rejected (${result.code}). Reload the current state and submit again — nothing is retried automatically.`,
        });
      }
      void submittedMode;
    },
  });

  const selectedResourceLibraryId = resourceLibraryId ?? "";

  return (
    <AuthorizedReadBoundary
      query={matrixQuery}
      unavailableTitle="Action matrix unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading action matrix">
              <p>Checking runtime readiness and action availability.</p>
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
        const matrix = data.model;
        const advertisedModes = matrix.actions.scan.modes;
        const exactScopeChosen =
          scopeKind === "file"
            ? Boolean(fileId && resourceLibraryId)
            : scopeKind === "resourceLibrary"
              ? Boolean(resourceLibraryId)
              : false;
        const canSubmit =
          matrix.actions.scan.available &&
          exactScopeChosen &&
          advertisedModes.includes(mode) &&
          !scanMutation.isPending;

        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Start bounded Scan</h2>
                <p className="mf-dashboard-meta">
                  Server-bound admission for the exact current source and
                  runtime. Scan discovers and indexes source files; it never
                  mutates Storage.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {!exactScopeChosen && (
              <StatusBanner variant="error" title="Invalid scope">
                <p>
                  Select one exact current FileIndex item or one configured
                  ResourceLibrary before submitting a Scan.
                </p>
              </StatusBanner>
            )}
            {matrix.selectionRequired && (
              <section className="mf-count-section">
                <h3>ResourceLibrary scope</h3>
                <p className="mf-dashboard-meta">
                  The backend lists the ResourceLibraries this principal may
                  scan. Choose one exact scope; no action is available before
                  that choice.
                </p>
                <p>
                  <label htmlFor="scan-resource-library">
                    ResourceLibrary scope
                  </label>{" "}
                  <select
                    id="scan-resource-library"
                    aria-label="ResourceLibrary scope"
                    value={selectedResourceLibraryId}
                    onChange={(event) => {
                      const chosen = event.target.value;
                      void navigate({
                        to: "/operations/scan/new",
                        search: chosen
                          ? {
                              scopeKind: "resourceLibrary" as const,
                              resourceLibraryId: chosen,
                            }
                          : { scopeKind: "resourceLibrary" as const },
                        replace: true,
                      });
                    }}
                  >
                    <option value="">Choose a ResourceLibrary</option>
                    {matrix.resourceLibraries.map((library) => (
                      <option
                        key={library.resourceLibraryId}
                        value={library.resourceLibraryId}
                        disabled={!library.enabled}
                      >
                        {library.resourceLibraryId}
                        {library.enabled ? "" : " (disabled)"}
                      </option>
                    ))}
                  </select>
                </p>
              </section>
            )}
            {exactScopeChosen && (
              <>
                <section className="mf-count-section">
                  <h3>Runtime readiness</h3>
                  <dl>
                    <dt>Ready</dt>
                    <dd>{matrix.runtime.ready ? "Yes" : "No"}</dd>
                    <dt>Condition</dt>
                    <dd>{displayEnum(matrix.runtime.condition)}</dd>
                    {matrix.runtime.nextAction && (
                      <>
                        <dt>Next action</dt>
                        <dd>{matrix.runtime.nextAction}</dd>
                      </>
                    )}
                  </dl>
                </section>
                <SourceIdentity matrix={matrix} />
                <section className="mf-count-section">
                  <h3>Scan action</h3>
                  <ActionAvailability
                    label="Scan"
                    available={matrix.actions.scan.available}
                    reason={matrix.actions.scan.reason}
                    nextAction={matrix.actions.scan.nextAction}
                  />
                  <p>
                    <label htmlFor="scan-mode">Scan mode</label>{" "}
                    <select
                      id="scan-mode"
                      aria-label="Scan mode"
                      value={mode}
                      onChange={(event) =>
                        setMode(event.target.value as ScanMode)
                      }
                    >
                      {advertisedModes.map((value) => (
                        <option key={value} value={value}>
                          {displayEnum(value)}
                        </option>
                      ))}
                    </select>
                  </p>
                </section>
                <section className="mf-count-section">
                  <h3>Preview action</h3>
                  <p className="mf-dashboard-meta">
                    Preview runs the complete pipeline with zero Storage
                    mutation. The findings are shown on a separate page.
                  </p>
                  <ActionAvailability
                    label="Preview"
                    available={matrix.actions.preview.available}
                    reason={matrix.actions.preview.reason}
                    nextAction={matrix.actions.preview.nextAction}
                  />
                </section>
              </>
            )}
            <div className="mf-actions">
              <Button
                type="button"
                disabled={!canSubmit}
                onClick={() => scanMutation.mutate(mode)}
              >
                {scanMutation.isPending ? "Submitting…" : "Submit bounded Scan"}
              </Button>
              <Link className="mf-button mf-button-secondary" to="/operations">
                Back to Operations
              </Link>
            </div>
            {admissionResult !== null && (
              <StatusBanner
                variant={admissionResult.ok ? "success" : "error"}
                title={
                  admissionResult.ok ? "Scan admitted" : "Scan admission failed"
                }
              >
                <p>{admissionResult.message}</p>
                {admissionResult.taskId && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations/scan/$taskId"
                    params={{ taskId: admissionResult.taskId }}
                  >
                    Open the durable Scan detail
                  </Link>
                )}
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
