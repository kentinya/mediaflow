/**
 * Durable manual Organize execution outcome.
 *
 * The page shows the aggregate admission/worker/terminal state, every selected
 * and unselected item identity, known completed effects, effect certainty, the
 * linked Task/TaskItem/Result identities and the current next action. It never
 * replays uncertain work automatically: a failure links to the Task and to
 * Review & Recovery/V1 instead.
 */

import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { organizeExecutionQueryOptions } from "./organize-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";

function displayEnum(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

export function OrganizeExecutionPage() {
  const { executionId } = useParams({
    from: "/operations/organize/execution/$executionId",
  });
  const token = useAuthToken();
  const executionQuery = useQuery(
    organizeExecutionQueryOptions(token, executionId),
  );

  return (
    <AuthorizedReadBoundary
      query={executionQuery}
      unavailableTitle="Execution unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading durable execution">
              <p>Reading the admitted exact execution and its outcomes.</p>
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
        const execution = data.model;
        const terminal = [
          "completed",
          "partial_success",
          "failed",
          "cancelled",
        ].includes(execution.status);
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Manual organize execution</h2>
                <p className="mf-dashboard-meta">
                  Execution {execution.executionId} ·{" "}
                  {displayEnum(execution.status)} · Task {execution.taskId}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Admission and Worker state</h3>
              <dl>
                <dt>Durable state</dt>
                <dd>{displayEnum(execution.durableState)}</dd>
                <dt>Items</dt>
                <dd>
                  {execution.selectedItemCount} selected ·{" "}
                  {execution.unselectedItemCount} unselected ·{" "}
                  {execution.completedItemCount} verified ·{" "}
                  {execution.failedItemCount} failed
                </dd>
                <dt>Destructive authority</dt>
                <dd>
                  overwrite{" "}
                  {execution.allowOverwrite ? "authorized" : "not authorized"} ·
                  source cleanup{" "}
                  {execution.allowSourceCleanup
                    ? "authorized"
                    : "not authorized"}
                </dd>
                <dt>Admitted</dt>
                <dd>{execution.createdAt}</dd>
                <dt>Last update</dt>
                <dd>{execution.updatedAt}</dd>
              </dl>
              <p className="mf-dashboard-meta">{execution.nextAction}</p>
              <p className="mf-dashboard-meta">
                {execution.knownEffects.statement}
              </p>
            </section>
            {execution.failure !== null && (
              <StatusBanner variant="error" title="Execution finding">
                <p>{execution.failure.message}</p>
                <p className="mf-dashboard-meta">
                  {execution.failure.nextAction}
                </p>
              </StatusBanner>
            )}
            {execution.items.map((item) => (
              <section className="mf-count-section" key={item.itemId}>
                <h3>
                  {item.itemId}{" "}
                  <span className="mf-status-badge">
                    {displayEnum(item.status)}
                  </span>
                </h3>
                <dl>
                  <dt>Stage</dt>
                  <dd>{displayEnum(item.stage ?? "unknown")}</dd>
                  <dt>Effect certainty</dt>
                  <dd>{displayEnum(item.effectCertainty ?? "unknown")}</dd>
                  <dt>Completed operations</dt>
                  <dd>
                    {item.completedOperations.length === 0
                      ? "none"
                      : item.completedOperations.join(", ")}
                  </dd>
                  <dt>Uncertain effects</dt>
                  <dd>
                    {item.uncertainEffects.length === 0
                      ? "none"
                      : item.uncertainEffects.join(", ")}
                  </dd>
                  <dt>Result</dt>
                  <dd>{safeValue(item.resultId)}</dd>
                  <dt>TaskItem</dt>
                  <dd>{safeValue(item.taskItemId)}</dd>
                </dl>
                {item.effects.length > 0 && (
                  <ul>
                    {item.effects.map((effect, position) => (
                      <li key={`${item.itemId}-${position}`}>
                        {displayEnum(effect.action ?? "effect")} ·{" "}
                        {effect.verified ? "verified" : "unverified"} ·{" "}
                        {safeValue(effect.sourceLocation)} →{" "}
                        {safeValue(effect.destinationLocation)}
                      </li>
                    ))}
                  </ul>
                )}
                {item.failure !== null && (
                  <StatusBanner variant="error" title="Item finding">
                    <p>{item.failure.message}</p>
                    <p className="mf-dashboard-meta">
                      {item.failure.nextAction}
                    </p>
                  </StatusBanner>
                )}
                {item.nextAction && (
                  <p className="mf-dashboard-meta">{item.nextAction}</p>
                )}
              </section>
            ))}
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/tasks/$taskId"
                params={{ taskId: execution.taskId }}
              >
                Open the durable Task
              </Link>
              {execution.actions.recovery.available && (
                <Link className="mf-button mf-button-secondary" to="/review">
                  Open Review &amp; Recovery
                </Link>
              )}
              {execution.previewId && (
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/organize/preview/$previewId"
                  params={{ previewId: execution.previewId }}
                >
                  Back to the reviewed Preview
                </Link>
              )}
              <Link className="mf-button mf-button-secondary" to="/operations">
                Back to Operations
              </Link>
            </div>
            {!terminal && (
              <p className="mf-dashboard-meta">
                This execution is not terminal yet. Refresh to read the current
                durable state; no action is replayed automatically.
              </p>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
