/**
 * V2 Automation entry page.
 *
 * The list shows the exact immutable Active revision identity and every
 * definition's durable schedule, occurrence and grant state. Availability
 * always comes from the backend action projection for the exact principal;
 * this page never infers permission or readiness. Reading mutates nothing.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { automationListQueryOptions } from "./automation-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function AutomationListPage() {
  const token = useAuthToken();
  const listQuery = useQuery(automationListQueryOptions(token));

  return (
    <AuthorizedReadBoundary
      query={listQuery}
      unavailableTitle="Automation unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Automation">
              <p>Reading the Active Automation definitions and their state.</p>
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
        const page = data.model;
        const active = page.activeConfiguration;
        const create = page.actions.create;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Automation</h2>
                <p className="mf-dashboard-meta">
                  Scheduled Automation Task Definitions, their unattended
                  authority and their durable occurrence history. Definitions
                  are edited inside a successor Draft and become effective only
                  after an explicit checked activation.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Active configuration</h3>
              {active === null ? (
                <p className="mf-dashboard-meta">
                  No Active configuration exists. Managed configuration setup
                  owns the first Draft.
                </p>
              ) : (
                <dl>
                  <dt>Active revision</dt>
                  <dd>{active.revisionId}</dd>
                  <dt>Version</dt>
                  <dd>
                    {active.version} (sequence {active.revisionSequence})
                  </dd>
                </dl>
              )}
              <p className="mf-dashboard-meta">
                {page.draftState.reason ?? ""}
              </p>
            </section>
            <div className="mf-actions">
              {create.available && (
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/automation/new"
                >
                  Create Automation definition
                </Link>
              )}
              <Link className="mf-button mf-button-secondary" to="/operations">
                Back to Operations
              </Link>
            </div>
            {!create.available && (
              <StatusBanner variant="info" title="Create unavailable">
                <p>
                  {create.reason ?? "The backend does not advertise creation."}
                </p>
                {create.nextAction && <p>{create.nextAction}</p>}
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Definitions</h3>
              {page.items.length === 0 && (
                <p className="mf-dashboard-meta">
                  No Automation Task Definition exists in the Active
                  configuration or in an open successor Draft.
                </p>
              )}
              {page.truncated && (
                <p className="mf-dashboard-meta">
                  Showing the first {page.items.length} of {page.total}{" "}
                  definitions; the bounded list excludes the rest.
                </p>
              )}
              {page.items.map((definition) => {
                const schedule =
                  definition.document.scheduleType === "interval"
                    ? `every ${definition.document.intervalSeconds} seconds`
                    : `${definition.document.cron} (${definition.document.timezone})`;
                return (
                  <section
                    className="mf-count-section"
                    key={definition.document.id}
                  >
                    <h3>
                      <Link
                        to="/operations/automation/definition/$definitionId"
                        params={{ definitionId: definition.document.id }}
                      >
                        {definition.document.name}
                      </Link>{" "}
                      <span className="mf-status-badge">
                        {definition.document.enabled ? "enabled" : "disabled"}
                      </span>
                      {definition.definitionState === "draft-only" && (
                        <span className="mf-status-badge">draft-only</span>
                      )}
                      {definition.grant.status === "active" && (
                        <span className="mf-status-badge">granted</span>
                      )}
                    </h3>
                    <dl>
                      <dt>Mode</dt>
                      <dd>{displayEnum(definition.document.mode)}</dd>
                      <dt>Schedule</dt>
                      <dd>{schedule}</dd>
                      <dt>Source scope</dt>
                      <dd>
                        {definition.document.sourceScope ??
                          "ResourceLibrary root"}
                      </dd>
                      <dt>Item limit</dt>
                      <dd>{definition.document.itemLimit}</dd>
                      <dt>Next run</dt>
                      <dd>{definition.nextRunAt ?? "not scheduled"}</dd>
                      <dt>Last outcome</dt>
                      <dd>{definition.lastOutcome ?? "no occurrence yet"}</dd>
                      {definition.lastReason && (
                        <>
                          <dt>Last reason</dt>
                          <dd>{definition.lastReason}</dd>
                        </>
                      )}
                    </dl>
                    {definition.draftState.present && (
                      <p className="mf-dashboard-meta">
                        An open successor Draft (version{" "}
                        {definition.draftState.revisionVersion}) contains this
                        definition.
                      </p>
                    )}
                    <div className="mf-actions">
                      <Link
                        className="mf-button mf-button-secondary"
                        to="/operations/automation/definition/$definitionId"
                        params={{ definitionId: definition.document.id }}
                      >
                        Open definition
                      </Link>
                      <Link
                        className="mf-button mf-button-secondary"
                        to="/operations/automation/occurrences/$definitionId"
                        params={{ definitionId: definition.document.id }}
                      >
                        Occurrences
                      </Link>
                    </div>
                  </section>
                );
              })}
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
