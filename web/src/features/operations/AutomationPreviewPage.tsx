/**
 * V2 Automation exact Preview page.
 *
 * One zero-mutation Preview of one exact Active definition: identity, counts,
 * staleness and the bounded per-item findings, paged from the backend. The
 * Preview grants no execution authority; the unattended grant is offered only
 * when the backend advertises it for this exact current Preview and the
 * operator confirms it explicitly.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  grantAutomationAuthority,
  revokeAutomationAuthority,
} from "../../shared/api/api-client";
import {
  automationDefinitionQueryKey,
  automationPreviewItemsQueryOptions,
  automationPreviewQueryOptions,
} from "./automation-query";
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

export function AutomationPreviewPage() {
  const { definitionId, previewId } = useParams({
    from: "/operations/automation/preview/$definitionId/$previewId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [itemsAfter, setItemsAfter] = useState<number | null>(null);
  const [confirmGrant, setConfirmGrant] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const previewQuery = useQuery(
    automationPreviewQueryOptions(token, definitionId, previewId),
  );
  const itemsQuery = useQuery(
    automationPreviewItemsQueryOptions(
      token,
      definitionId,
      previewId,
      itemsAfter,
    ),
  );

  const grantMutation = useMutation({
    mutationFn: () =>
      grantAutomationAuthority(token, { definitionId, previewId }),
    retry: false,
    onMutate: () => {
      setError(null);
      setConfirmGrant(false);
    },
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [automationDefinitionQueryKey],
        });
        void navigate({
          to: "/operations/automation/definition/$definitionId",
          params: { definitionId },
        });
        return;
      }
      setError(
        `The grant was rejected (${result.code}). Run a fresh exact Preview and read the eligibility again; nothing is retried automatically.`,
      );
    },
  });

  const revokeMutation = useMutation({
    mutationFn: () => revokeAutomationAuthority(token, { definitionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [automationDefinitionQueryKey],
        });
        return;
      }
      setError(
        `The revocation was rejected (${result.code}). Reload the durable grant state and try again.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={previewQuery}
      unavailableTitle="Automation Preview unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Preview">
              <p>Reading the exact Preview evidence.</p>
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
                  to="/operations/automation/definition/$definitionId"
                  params={{ definitionId }}
                >
                  Back to the definition
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const preview = data.model;
        const itemsPage = itemsQuery.data;
        const items =
          itemsPage !== undefined && itemsPage.ok
            ? itemsPage.model.items
            : preview.items;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Exact Automation Preview</h2>
                <p className="mf-dashboard-meta">
                  Preview {preview.previewId} · definition{" "}
                  {preview.definitionId} · Active revision{" "}
                  {preview.configurationRevisionId} (version{" "}
                  {preview.configurationRevisionVersion}) ·{" "}
                  {displayEnum(preview.status)} · zero Storage mutation
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <StatusBanner variant="info" title="Zero Storage mutation">
              <p>
                Creating and reading this Preview changed nothing in Storage. It
                is analysis evidence, not execution authority.
              </p>
            </StatusBanner>
            {!preview.current && (
              <StatusBanner variant="warning" title="Historical evidence">
                <p>
                  {preview.staleReason ??
                    "This Preview is historical evidence; run a fresh exact Preview after the definition changed."}
                </p>
              </StatusBanner>
            )}
            {preview.error && (
              <StatusBanner variant="error" title="Preview finding">
                <p>{preview.error}</p>
              </StatusBanner>
            )}
            {preview.boundaryErrors.length > 0 && (
              <StatusBanner variant="warning" title="Boundary findings">
                <ul>
                  {preview.boundaryErrors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Scope and counts</h3>
              <dl>
                <dt>Run mode</dt>
                <dd>{displayEnum(preview.runMode)}</dd>
                <dt>ResourceLibrary</dt>
                <dd>{preview.resourceLibraryId}</dd>
                <dt>Source scope</dt>
                <dd>{preview.sourceScope ?? "ResourceLibrary root"}</dd>
                <dt>Discovered</dt>
                <dd>{preview.counts.discovered}</dd>
                <dt>Selected / permitted</dt>
                <dd>
                  {preview.counts.selected} / {preview.counts.permitted}
                </dd>
                <dt>Excluded or ignored</dt>
                <dd>{preview.counts.excludedIgnored}</dd>
                <dt>Unstable</dt>
                <dd>{preview.counts.unstable}</dd>
                <dt>Effective item limit</dt>
                <dd>{preview.effectiveItemLimit}</dd>
              </dl>
              {preview.nextAction && (
                <p className="mf-dashboard-meta">{preview.nextAction}</p>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Preview items</h3>
              {items.map((item) => (
                <section className="mf-count-section" key={item.previewItemId}>
                  <h3>
                    {item.source.filename}{" "}
                    <span className="mf-status-badge">
                      {displayEnum(item.status)}
                    </span>
                  </h3>
                  <dl>
                    <dt>Source</dt>
                    <dd>
                      {item.source.path} ({item.source.storageId})
                    </dd>
                    <dt>Recognition</dt>
                    <dd>
                      {item.recognition.recognitionTypeId ?? "unresolved"}
                      {item.recognition.status
                        ? ` · ${item.recognition.status}`
                        : ""}
                    </dd>
                    {item.metadata.title && (
                      <>
                        <dt>Metadata</dt>
                        <dd>
                          {item.metadata.provider ?? "provider"} ·{" "}
                          {item.metadata.title}
                          {item.metadata.year ? ` (${item.metadata.year})` : ""}
                        </dd>
                      </>
                    )}
                    {item.destination.path && (
                      <>
                        <dt>Destination</dt>
                        <dd>
                          {item.destination.path} (
                          {item.destination.storageId ?? "target"})
                        </dd>
                      </>
                    )}
                    {item.operation && (
                      <>
                        <dt>Operation</dt>
                        <dd>{displayEnum(item.operation)}</dd>
                      </>
                    )}
                    {item.conflicts.length > 0 && (
                      <>
                        <dt>Conflicts</dt>
                        <dd>{item.conflicts.join("; ")}</dd>
                      </>
                    )}
                    <dt>Capability verdict</dt>
                    <dd>{item.capabilities.verdict ?? "unknown"}</dd>
                    {item.blocker && (
                      <>
                        <dt>Blocker</dt>
                        <dd>{item.blocker}</dd>
                      </>
                    )}
                    {item.warnings.length > 0 && (
                      <>
                        <dt>Warnings</dt>
                        <dd>{item.warnings.join("; ")}</dd>
                      </>
                    )}
                  </dl>
                  {item.nextAction && (
                    <p className="mf-dashboard-meta">{item.nextAction}</p>
                  )}
                </section>
              ))}
              {items.length === 0 && (
                <p className="mf-dashboard-meta">
                  No Preview item evidence exists.
                </p>
              )}
              {preview.itemsTruncated || itemsAfter !== null || (
                <p className="mf-dashboard-meta">
                  Showing {items.length} of {preview.itemTotal} item(s).
                </p>
              )}
              {(() => {
                const itemsAction = preview.actions.items;
                const nextAfter =
                  itemsPage !== undefined && itemsPage.ok
                    ? itemsPage.model.nextAfter
                    : preview.itemTotal > preview.items.length
                      ? preview.items.length
                      : null;
                if (!itemsAction.available || nextAfter === null) {
                  return null;
                }
                return (
                  <div className="mf-actions">
                    <Button
                      type="button"
                      disabled={itemsQuery.isPending}
                      onClick={() => setItemsAfter(nextAfter)}
                    >
                      {itemsQuery.isPending
                        ? "Loading items…"
                        : `Load more items (from ${nextAfter})`}
                    </Button>
                  </div>
                );
              })()}
            </section>
            <section className="mf-count-section">
              <h3>Unattended authority</h3>
              {preview.grantEligibility !== null && (
                <p className="mf-dashboard-meta">
                  {preview.grantEligibility.eligible
                    ? "The exact current Preview and the current granting-principal permission satisfy the persisted grant bounds."
                    : preview.grantEligibility.explanation}
                </p>
              )}
              {preview.grantEligibility?.error && (
                <p className="mf-dashboard-meta">
                  {preview.grantEligibility.error.nextAction}
                </p>
              )}
              {preview.actions.grant.available && (
                <div className="mf-actions">
                  <label>
                    <input
                      type="checkbox"
                      checked={confirmGrant}
                      aria-label="Confirm unattended execution grant"
                      onChange={(event) =>
                        setConfirmGrant(event.target.checked)
                      }
                    />{" "}
                    I confirm the exact bounded unattended authority for this
                    Preview
                  </label>
                  <Button
                    type="button"
                    disabled={!confirmGrant || grantMutation.isPending}
                    onClick={() => grantMutation.mutate()}
                  >
                    {grantMutation.isPending
                      ? "Granting…"
                      : "Grant unattended authority"}
                  </Button>
                </div>
              )}
              {!preview.actions.grant.available && (
                <p className="mf-dashboard-meta">
                  {preview.actions.grant.reason ??
                    "The backend does not advertise the grant action."}
                </p>
              )}
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={revokeMutation.isPending}
                  onClick={() => revokeMutation.mutate()}
                >
                  {revokeMutation.isPending ? "Revoking…" : "Revoke grant"}
                </Button>
              </div>
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/automation/definition/$definitionId"
                params={{ definitionId }}
              >
                Back to the definition
              </Link>
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/automation"
              >
                Back to Automation
              </Link>
            </div>
            {error !== null && (
              <StatusBanner variant="error" title="Action not completed">
                <p>{error}</p>
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
