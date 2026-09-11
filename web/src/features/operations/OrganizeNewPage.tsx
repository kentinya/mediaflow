/**
 * Manual Organize entry page.
 *
 * The operator arrives from a current FileIndex detail, a ResourceLibrary
 * Operations scope or an eligible Preview. Availability always comes from the
 * backend action matrix for the exact principal, scope and runtime; this page
 * never infers permission, source currentness or Worker readiness from the
 * route. A ResourceLibrary-scoped selection lists the current ready FileIndex
 * records and submits only their identities, so no path, fingerprint or
 * digest is ever typed, copied or displayed.
 *
 * After the durable intent is created the operator continues to the
 * refresh-safe intent route; the browser holds no authority.
 */

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { submitOrganizeIntent } from "../../shared/api/api-client";
import { manualActionsQueryOptions } from "./manual-actions-query";
import { fileIndexQueryOptions } from "../library/file-index-query";
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

export function OrganizeNewPage() {
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
  const [selectedItemIds, setSelectedItemIds] = useState<readonly string[]>([]);
  const [admissionResult, setAdmissionResult] = useState<{
    readonly ok: boolean;
    readonly message: string;
  } | null>(null);

  const matrixQuery = useQuery(
    manualActionsQueryOptions(token, {
      scopeKind,
      fileId: fileId ?? null,
      resourceLibraryId: resourceLibraryId ?? null,
    }),
  );

  const catalogQuery = useQuery(
    fileIndexQueryOptions(
      token,
      {
        resourceLibrary: resourceLibraryId ?? null,
        storage: null,
        scanStatus: "ready",
        query: null,
        processingDisposition: null,
        recognitionType: null,
        provider: null,
        providerId: null,
        title: null,
        taskId: null,
        year: null,
        after: null,
        cursorFileId: null,
        before: null,
      },
      scopeKind === "resourceLibrary" && Boolean(resourceLibraryId),
    ),
  );

  const intentMutation = useMutation({
    mutationFn: () =>
      submitOrganizeIntent(token, {
        scopeKind: scopeKind as "file" | "resourceLibrary",
        fileId: fileId ?? null,
        resourceLibraryId: resourceLibraryId ?? null,
        itemIds: scopeKind === "resourceLibrary" ? selectedItemIds : null,
      }),
    retry: false,
    onMutate: () => setAdmissionResult(null),
    onSuccess: (result) => {
      if (result.ok) {
        void navigate({
          to: "/operations/organize/intent/$intentId",
          params: { intentId: result.model.intentId },
        });
        return;
      }
      setAdmissionResult({
        ok: false,
        message:
          result.code === "transport_unavailable"
            ? "The intent request could not reach the API. Nothing was created."
            : `Creating the durable intent was rejected (${result.code}). Reload the current state and submit again; nothing is retried automatically.`,
      });
    },
  });

  const isValidScope =
    scopeKind === "file"
      ? Boolean(fileId && resourceLibraryId)
      : scopeKind === "resourceLibrary"
        ? Boolean(resourceLibraryId)
        : false;

  return (
    <AuthorizedReadBoundary
      query={matrixQuery}
      unavailableTitle="Manual Organize unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading manual Organize">
              <p>Checking the exact scope and action availability.</p>
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
        const organize = matrix.actions.organize;
        const catalog = catalogQuery.data;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Create manual organize intent</h2>
                <p className="mf-dashboard-meta">
                  A durable intent records the exact current sources and the
                  permitted choices. Creating or editing it changes no Storage
                  and grants no execution authority.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {!isValidScope && (
              <StatusBanner variant="error" title="Invalid scope">
                <p>
                  Select one exact current FileIndex item or one configured
                  ResourceLibrary before creating a manual intent.
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
            {isValidScope && (
              <>
                <section className="mf-count-section">
                  <h3>Scope</h3>
                  <dl>
                    <dt>Scope kind</dt>
                    <dd>{displayEnum(scopeKind as string)}</dd>
                    {resourceLibraryId && (
                      <>
                        <dt>ResourceLibrary</dt>
                        <dd>{resourceLibraryId}</dd>
                      </>
                    )}
                    {fileId && (
                      <>
                        <dt>FileIndex identity</dt>
                        <dd>{fileId}</dd>
                      </>
                    )}
                  </dl>
                </section>
                {scopeKind === "resourceLibrary" && (
                  <section className="mf-count-section">
                    <h3>Current ready sources</h3>
                    {catalogQuery.isPending && (
                      <p className="mf-dashboard-meta">
                        Loading current ready FileIndex records.
                      </p>
                    )}
                    {catalog !== undefined && !catalog.ok && (
                      <p className="mf-dashboard-meta">
                        {catalog.failure.title}: {catalog.failure.nextAction}
                      </p>
                    )}
                    {catalog !== undefined && catalog.ok && (
                      <>
                        <p className="mf-dashboard-meta">
                          Select the exact current records to review. Blocked or
                          unselected records are never included silently.
                        </p>
                        <ul className="mf-check-list">
                          {catalog.model.items.map((record) => (
                            <li key={record.fileId}>
                              <label>
                                <input
                                  type="checkbox"
                                  checked={selectedItemIds.includes(
                                    record.fileId,
                                  )}
                                  onChange={(event) =>
                                    setSelectedItemIds((current) =>
                                      event.target.checked
                                        ? [...current, record.fileId]
                                        : current.filter(
                                            (value) => value !== record.fileId,
                                          ),
                                    )
                                  }
                                />{" "}
                                {record.filename ?? record.fileId}
                              </label>
                            </li>
                          ))}
                        </ul>
                        {catalog.model.items.length === 0 && (
                          <p className="mf-dashboard-meta">
                            No current ready FileIndex record exists in this
                            ResourceLibrary.
                          </p>
                        )}
                      </>
                    )}
                  </section>
                )}
                <section className="mf-count-section">
                  <h3>Organize action</h3>
                  <p className="mf-dashboard-meta">
                    {organize.available
                      ? "The backend advertises a durable manual intent for this exact scope."
                      : `Unavailable: ${organize.reason ?? "the backend does not advertise it"}`}
                  </p>
                  {organize.nextAction && (
                    <p className="mf-dashboard-meta">{organize.nextAction}</p>
                  )}
                </section>
                <div className="mf-actions">
                  <Button
                    type="button"
                    disabled={
                      !organize.available ||
                      intentMutation.isPending ||
                      (scopeKind === "resourceLibrary" &&
                        selectedItemIds.length === 0)
                    }
                    onClick={() => intentMutation.mutate()}
                  >
                    {intentMutation.isPending
                      ? "Creating durable intent…"
                      : "Create durable intent"}
                  </Button>
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations"
                  >
                    Back to Operations
                  </Link>
                </div>
                {admissionResult !== null && (
                  <StatusBanner variant="error" title="Intent not created">
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
