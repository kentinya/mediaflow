/**
 * V2 Automation occurrence history.
 *
 * Each occurrence preserves its pinned definition/configuration identity and
 * links the exact Task evidence already owned by Operations. Reading and
 * paging never emits an occurrence, submits work or touches Storage.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearch } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { automationOccurrencesQueryOptions } from "./automation-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { describeAutomationRunMode } from "../../entities/operations/automation";
import { readAutomationListReturn } from "../../shared/navigation/automation-list-return";

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function AutomationOccurrencesPage() {
  const { definitionId } = useParams({
    from: "/operations/automation/occurrences/$definitionId",
  });
  const token = useAuthToken();
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const [cursor, setCursor] = useState<string | null>(null);
  const [direction, setDirection] = useState<"previous" | "next">("next");
  // The old definition detail page used to own this entry. The bounded list
  // return context it carried is still honoured, but the ordinary exit is the
  // execution records tab filtered to this exact definition.
  const retainedReturn = readAutomationListReturn(searchParams).search;
  // A definitions-tab return is preserved as-is. A records-tab return keeps
  // its own filters but always carries this definition when it omitted one;
  // any other value degrades to the ordinary definition-filtered records tab.
  const backSearch: Record<string, string> =
    retainedReturn?.tab === "definitions"
      ? retainedReturn
      : retainedReturn?.tab === "records"
        ? {
            ...retainedReturn,
            rdefinition: retainedReturn["rdefinition"] ?? definitionId,
          }
        : { tab: "records", rdefinition: definitionId };
  const backLabel =
    backSearch["tab"] === "definitions"
      ? "Back to the Automation list"
      : "Back to execution records";

  const occurrencesQuery = useQuery(
    automationOccurrencesQueryOptions(token, definitionId, cursor, direction),
  );

  return (
    <AuthorizedReadBoundary
      query={occurrencesQuery}
      unavailableTitle="Occurrences unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading occurrences">
              <p>Reading the bounded occurrence history.</p>
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
                  to="/operations/automation"
                  search={backSearch}
                >
                  {backLabel}
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const page = data.model;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Automation occurrences</h2>
                <p className="mf-dashboard-meta">
                  Definition {page.definitionId}
                  {page.activeConfiguration
                    ? ` · Active revision ${page.activeConfiguration.revisionId} (version ${page.activeConfiguration.version})`
                    : ""}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {page.manualRuns.length > 0 && (
              <section className="mf-count-section">
                <h3>Run once history</h3>
                {page.manualRuns.map((run) => (
                  <p key={run.runId}>
                    <Link
                      to="/operations/automation/run-once/$discoveryId"
                      params={{ discoveryId: run.runId }}
                    >
                      {run.kind === "organizing"
                        ? "Organizing Run once"
                        : "Historical analysis"}
                    </Link>{" "}
                    · {run.status}
                  </p>
                ))}
              </section>
            )}
            {page.items.length === 0 && (
              <StatusBanner variant="info" title="No occurrences yet">
                <p>
                  The Scheduler has not emitted an occurrence for this
                  definition. Reading this page never emits one.
                </p>
              </StatusBanner>
            )}
            {page.items.map((occurrence) => (
              <section
                className="mf-count-section"
                key={occurrence.occurrenceId}
              >
                <h3>
                  {occurrence.occurrenceAt}{" "}
                  <span className="mf-status-badge">
                    {displayEnum(occurrence.outcome)}
                  </span>
                </h3>
                <dl>
                  <dt>Run mode</dt>
                  <dd>{describeAutomationRunMode(occurrence.runMode)}</dd>
                  <dt>Pinned revision</dt>
                  <dd>
                    {occurrence.configurationRevisionId} (version{" "}
                    {occurrence.configurationRevisionVersion})
                  </dd>
                  <dt>Scope</dt>
                  <dd>
                    {occurrence.resourceLibraryId}
                    {occurrence.sourceScope
                      ? ` · ${occurrence.sourceScope}`
                      : ""}
                  </dd>
                  <dt>Item limit</dt>
                  <dd>{occurrence.itemLimit ?? "unbounded"}</dd>
                  {occurrence.reason && (
                    <>
                      <dt>Reason</dt>
                      <dd>{occurrence.reason}</dd>
                    </>
                  )}
                  {occurrence.failureCategory && (
                    <>
                      <dt>Failure category</dt>
                      <dd>{displayEnum(occurrence.failureCategory)}</dd>
                    </>
                  )}
                </dl>
                {occurrence.outcomeSummary !== null && (
                  <p className="mf-dashboard-meta">
                    {occurrence.outcomeSummary.totalItems} item(s) ·{" "}
                    {occurrence.outcomeSummary.boundStatement}
                  </p>
                )}
                {occurrence.nextAction && (
                  <p className="mf-dashboard-meta">{occurrence.nextAction}</p>
                )}
                <div className="mf-actions">
                  {/* The retired mixed collections are closed, so the exact
                      occurrence evidence opens the same run *inside* the center,
                      never a second mixed list.  Reading it stays GET-only. */}
                  {occurrence.actions.task?.available === true && (
                    <Link
                      className="mf-button mf-button-secondary"
                      to="/operations"
                      search={{ run: occurrence.taskId }}
                    >
                      Open the exact run in the Task Center
                    </Link>
                  )}
                </div>
              </section>
            ))}
            <div className="mf-actions">
              {page.previousCursor !== null && (
                <button
                  type="button"
                  className="mf-button mf-button-secondary"
                  onClick={() => {
                    setDirection("previous");
                    setCursor(page.previousCursor);
                  }}
                >
                  Previous page
                </button>
              )}
              {page.nextCursor !== null && (
                <button
                  type="button"
                  className="mf-button mf-button-secondary"
                  onClick={() => {
                    setDirection("next");
                    setCursor(page.nextCursor);
                  }}
                >
                  Next page
                </button>
              )}
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/automation"
                search={backSearch}
              >
                {backLabel}
              </Link>
            </div>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
