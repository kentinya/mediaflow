/**
 * V2 Automation definition creation page.
 *
 * The bounded form offers only the fields an Automation Task Definition owns:
 * name, enabled state, ResourceLibrary, relative source scope, run mode, item
 * limit and exactly one interval or Cron/timezone schedule. Options come from
 * the backend projection. A definition is stored inside the open successor
 * Draft; when none exists the operator starts one explicitly, because reads
 * never create durable state. Validation and activation happen on the Draft
 * editor afterwards; this page starts no work and grants no authority.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  createAutomationDefinition,
  createAutomationSuccessorDraft,
} from "../../shared/api/api-client";
import {
  automationListQueryKey,
  automationListQueryOptions,
} from "./automation-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

export function AutomationNewPage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [resourceLibraryId, setResourceLibraryId] = useState("");
  const [sourceScope, setSourceScope] = useState("");
  const [mode, setMode] = useState("scan-only");
  const [itemLimit, setItemLimit] = useState("100");
  const [scheduleType, setScheduleType] = useState<"interval" | "cron">(
    "interval",
  );
  const [intervalSeconds, setIntervalSeconds] = useState("3600");
  const [cron, setCron] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [error, setError] = useState<string | null>(null);

  const listQuery = useQuery(automationListQueryOptions(token));

  const draftMutation = useMutation({
    mutationFn: (activeRevisionId: string) =>
      createAutomationSuccessorDraft(token, { activeRevisionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [automationListQueryKey],
        });
        return;
      }
      setError(
        `Starting the successor Draft was rejected (${result.code}). Reload the current state and try again; nothing is retried automatically.`,
      );
    },
  });

  const createMutation = useMutation({
    mutationFn: (input: { revisionId: string; expectedVersion: number }) =>
      createAutomationDefinition(token, {
        revisionId: input.revisionId,
        expectedVersion: input.expectedVersion,
        object: {
          id: `automation-${Date.now()}`,
          name,
          enabled,
          resourceLibraryId,
          mode,
          itemLimit: Number(itemLimit),
          ...(sourceScope ? { sourceScope } : {}),
          ...(scheduleType === "interval"
            ? { intervalSeconds: Number(intervalSeconds) }
            : { cron, timezone }),
        },
      }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [automationListQueryKey],
        });
        if (result.model.id) {
          void navigate({
            to: "/operations/automation/definition/$definitionId",
            params: { definitionId: result.model.id },
          });
        }
        return;
      }
      setError(
        `Creating the definition was rejected (${result.code}). Reload the current state and submit again; nothing is retried automatically.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={listQuery}
      unavailableTitle="Automation unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Automation">
              <p>Reading the Active configuration and Draft state.</p>
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
                >
                  Back to Automation
                </Link>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </div>
            </StatusBanner>
          );
        }
        const page = data.model;
        const create = page.actions.create;
        const createDraft = page.actions.createDraft;
        const draftReady =
          page.draftState.present && page.draftState.revisionId !== null;
        const formValid =
          name.trim().length > 0 &&
          resourceLibraryId.length > 0 &&
          /^\d+$/.test(itemLimit) &&
          (scheduleType === "interval"
            ? /^\d+$/.test(intervalSeconds)
            : cron.trim().length > 0 && timezone.trim().length > 0);
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Create Automation definition</h2>
                <p className="mf-dashboard-meta">
                  The bounded form stores one definition inside the open
                  successor Draft. Options and constraints come from the
                  backend; the form cannot select per-file providers, policies,
                  destinations or Storage operations.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {!draftReady && (
              <StatusBanner variant="info" title="Successor Draft required">
                <p>
                  {page.draftState.reason}{" "}
                  {createDraft.available
                    ? "Start one explicitly; reading never creates durable state."
                    : ""}
                </p>
                {createDraft.available && (
                  <div className="mf-actions">
                    <Button
                      type="button"
                      disabled={draftMutation.isPending}
                      onClick={() => {
                        if (page.activeConfiguration !== null) {
                          draftMutation.mutate(
                            page.activeConfiguration.revisionId,
                          );
                        }
                      }}
                    >
                      {draftMutation.isPending
                        ? "Starting successor Draft…"
                        : "Start successor Draft"}
                    </Button>
                  </div>
                )}
                {!createDraft.available && createDraft.reason && (
                  <p>{createDraft.reason}</p>
                )}
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Definition</h3>
              <p className="mf-label">
                <label htmlFor="automation-name">Name</label>
              </p>
              <input
                id="automation-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={120}
              />
              <p className="mf-label">
                <label htmlFor="automation-enabled">Enabled</label>
              </p>
              <select
                id="automation-enabled"
                value={enabled ? "yes" : "no"}
                onChange={(event) => setEnabled(event.target.value === "yes")}
              >
                <option value="no">disabled (start without schedule)</option>
                <option value="yes">enabled</option>
              </select>
              <p className="mf-label">
                <label htmlFor="automation-library">ResourceLibrary</label>
              </p>
              <select
                id="automation-library"
                value={resourceLibraryId}
                onChange={(event) => setResourceLibraryId(event.target.value)}
              >
                <option value="">select one ResourceLibrary</option>
                {page.resourceLibraryOptions.map((option) => (
                  <option
                    key={option.id}
                    value={option.id}
                    disabled={!option.enabled}
                  >
                    {option.name ?? option.id}
                    {option.enabled ? "" : " (disabled)"}
                  </option>
                ))}
              </select>
              <p className="mf-label">
                <label htmlFor="automation-scope">Relative source scope</label>
              </p>
              <input
                id="automation-scope"
                value={sourceScope}
                onChange={(event) => setSourceScope(event.target.value)}
                placeholder="empty for the ResourceLibrary root"
                maxLength={256}
              />
              <p className="mf-label">
                <label htmlFor="automation-mode">Run mode</label>
              </p>
              <select
                id="automation-mode"
                value={mode}
                onChange={(event) => setMode(event.target.value)}
              >
                <option value="scan-only">scan-only</option>
                <option value="scan-and-plan">scan-and-plan</option>
                <option value="automatic-organization">
                  automatic-organization
                </option>
              </select>
              <p className="mf-label">
                <label htmlFor="automation-limit">Item limit</label>
              </p>
              <input
                id="automation-limit"
                value={itemLimit}
                onChange={(event) => setItemLimit(event.target.value)}
                inputMode="numeric"
              />
            </section>
            <section className="mf-count-section">
              <h3>Schedule</h3>
              <p className="mf-label">
                <label htmlFor="automation-schedule-type">Schedule type</label>
              </p>
              <select
                id="automation-schedule-type"
                value={scheduleType}
                onChange={(event) =>
                  setScheduleType(
                    event.target.value === "cron" ? "cron" : "interval",
                  )
                }
              >
                <option value="interval">interval (seconds)</option>
                <option value="cron">Cron with timezone</option>
              </select>
              {scheduleType === "interval" ? (
                <>
                  <p className="mf-label">
                    <label htmlFor="automation-interval">
                      Interval seconds
                    </label>
                  </p>
                  <input
                    id="automation-interval"
                    value={intervalSeconds}
                    onChange={(event) => setIntervalSeconds(event.target.value)}
                    inputMode="numeric"
                  />
                </>
              ) : (
                <>
                  <p className="mf-label">
                    <label htmlFor="automation-cron">Cron expression</label>
                  </p>
                  <input
                    id="automation-cron"
                    value={cron}
                    onChange={(event) => setCron(event.target.value)}
                    placeholder="0 8 * * *"
                    maxLength={64}
                  />
                  <p className="mf-label">
                    <label htmlFor="automation-timezone">Timezone</label>
                  </p>
                  <input
                    id="automation-timezone"
                    value={timezone}
                    onChange={(event) => setTimezone(event.target.value)}
                    maxLength={64}
                  />
                </>
              )}
            </section>
            <div className="mf-actions">
              <Button
                type="button"
                disabled={
                  !create.available ||
                  !formValid ||
                  !draftReady ||
                  createMutation.isPending
                }
                onClick={() => {
                  if (page.draftState.revisionId !== null) {
                    createMutation.mutate({
                      revisionId: page.draftState.revisionId,
                      expectedVersion: page.draftState.revisionVersion ?? 0,
                    });
                  }
                }}
              >
                {createMutation.isPending
                  ? "Creating definition…"
                  : "Create definition in Draft"}
              </Button>
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/automation"
              >
                Back to Automation
              </Link>
            </div>
            {!create.available && create.reason && (
              <p className="mf-dashboard-meta">{create.reason}</p>
            )}
            {error !== null && (
              <StatusBanner variant="error" title="Definition not created">
                <p>{error}</p>
              </StatusBanner>
            )}
            <p className="mf-dashboard-meta">
              The Draft is not Active yet. Open the definition, validate it and
              activate it explicitly to publish the change.
            </p>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
