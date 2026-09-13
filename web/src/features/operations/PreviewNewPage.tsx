/**
 * Preview admission page: shows the backend action matrix for the exact
 * authenticated principal, current source/scope and runtime readiness,
 * then submits a bounded server-bound preview admission.
 *
 * After admission the operator is redirected to the preview detail page.
 * Preview is visibly DryRun/analysis, produces no Storage mutation and
 * no execution authority.
 */

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import type { ManualActionMatrixModel } from "../../entities/operations/manual-actions";
import { submitServerBoundPreview } from "../../shared/api/api-client";
import { manualActionsQueryOptions } from "./manual-actions-query";
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
        {matrix.source?.fileId && (
          <>
            <dt>File ID</dt>
            <dd>{matrix.source.fileId}</dd>
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

export function PreviewNewPage() {
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const rawScopeKind = String(searchParams.scopeKind ?? "");
  const scopeKind =
    rawScopeKind === "file" || rawScopeKind === "resourceLibrary"
      ? (rawScopeKind as "file" | "resourceLibrary")
      : null;
  const relativePath = searchParams.relativePath ? String(searchParams.relativePath) : undefined;
  const resourceLibraryId = searchParams.resourceLibraryId
    ? String(searchParams.resourceLibraryId)
    : undefined;

  const token = useAuthToken();
  const navigate = useNavigate();

  const matrixQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind,
      fileId: null,
      resourceLibraryId: resourceLibraryId ?? null,
    }),
  );

  const [admissionResult, setAdmissionResult] = useState<{
    ok: boolean;
    message: string;
    previewId?: string;
  } | null>(null);

  const previewMutation = useMutation({
    mutationFn: () =>
      submitServerBoundPreview(token, {
        scopeKind: scopeKind as "file" | "resourceLibrary",
        relativePath: relativePath ?? null,
        resourceLibraryId: resourceLibraryId ?? null,
      }),
    retry: false,
    onMutate: () => setAdmissionResult(null),
    onSuccess: (result) => {
      if (result.ok) {
        setAdmissionResult({
          ok: true,
          message: "Preview admitted successfully",
          previewId: result.model.previewId,
        });
        // The admitted durable state stays visible for a moment before the
        // operator is continued to the durable Preview detail; nothing is
        // resubmitted.
        window.setTimeout(() => {
          void navigate({
            to: "/operations/preview/$previewId",
            params: { previewId: result.model.previewId },
          });
        }, 600);
      } else {
        setAdmissionResult({
          ok: false,
          message:
            result.code === "transport_unavailable"
              ? "The preview admission could not reach the API. Nothing was started."
              : `Preview admission was rejected (${result.code}). Reload the current state and submit again — nothing is retried automatically.`,
        });
      }
    },
  });

  const selectedResourceLibraryId = resourceLibraryId ?? "";
  const isValidScope =
    scopeKind === "file"
      ? Boolean(relativePath && resourceLibraryId)
      : scopeKind === "resourceLibrary"
        ? Boolean(resourceLibraryId)
        : false;

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
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Run zero-mutation Preview</h2>
                <p className="mf-dashboard-meta">
                  Server-bound admission for the exact current source and
                  runtime. Preview runs the complete pipeline with zero Storage
                  mutation and produces no execution authority.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {(matrix.selectionRequired || !isValidScope) && (
              <StatusBanner variant="error" title="Invalid scope">
                <p>
                  Select one ResourceLibrary file or one configured
                  ResourceLibrary before running a Preview.
                </p>
                <div className="mf-actions">
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations"
                  >
                    Back to Operations
                  </Link>
                </div>
              </StatusBanner>
            )}
            {matrix.selectionRequired && (
              <section className="mf-count-section">
                <h3>ResourceLibrary scope</h3>
                <p className="mf-dashboard-meta">
                  The backend lists the ResourceLibraries this principal may
                  preview. Choose one exact scope; no action is available before
                  that choice.
                </p>
                <p>
                  <label htmlFor="preview-resource-library">
                    ResourceLibrary scope
                  </label>{" "}
                  <select
                    id="preview-resource-library"
                    aria-label="ResourceLibrary scope"
                    value={selectedResourceLibraryId}
                    onChange={(event) => {
                      const chosen = event.target.value;
                      void navigate({
                        to: "/operations/preview/new",
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
            {isValidScope && (
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
                  <h3>Preview action</h3>
                  <p className="mf-dashboard-meta">
                    Zero-mutation analysis: the complete parse, recognition,
                    metadata, naming, classification and planning pipeline runs
                    with no Storage mutation.
                  </p>
                  <ActionAvailability
                    label="Preview"
                    available={matrix.actions.preview.available}
                    reason={matrix.actions.preview.reason}
                    nextAction={matrix.actions.preview.nextAction}
                  />
                  {matrix.limits.previewMaxItems !== null && (
                    <p className="mf-dashboard-meta">
                      Preview item limit: {matrix.limits.previewMaxItems}
                    </p>
                  )}
                </section>
                <section className="mf-count-section">
                  <h3>Scan action</h3>
                  <p className="mf-dashboard-meta">
                    Scan discovers and indexes source files without mutation.
                  </p>
                  <ActionAvailability
                    label="Scan"
                    available={matrix.actions.scan.available}
                    reason={matrix.actions.scan.reason}
                    nextAction={matrix.actions.scan.nextAction}
                  />
                </section>
                <div className="mf-actions">
                  <Button
                    type="button"
                    disabled={
                      !matrix.actions.preview.available ||
                      previewMutation.isPending
                    }
                    onClick={() => previewMutation.mutate()}
                  >
                    {previewMutation.isPending
                      ? "Submitting…"
                      : "Submit zero-mutation Preview"}
                  </Button>
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations"
                  >
                    Back to Operations
                  </Link>
                </div>
                {admissionResult !== null && (
                  <StatusBanner
                    variant={admissionResult.ok ? "success" : "error"}
                    title={
                      admissionResult.ok
                        ? "Preview admitted"
                        : "Preview admission failed"
                    }
                  >
                    <p>{admissionResult.message}</p>
                  </StatusBanner>
                )}
              </>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
