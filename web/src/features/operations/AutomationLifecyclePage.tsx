/**
 * Native V2 Automation definition lifecycle page.
 *
 * One typed form and one checked `保存` publish the intended successor: the
 * backend composes it from the exact observed Active, validates the whole
 * document, runs the applicable checks and atomically activates it. The operator
 * never orchestrates Draft/Validate/Activate, and this page never claims a
 * Draft is Active. Enable/disable, copy and removal are separate explicit
 * lifecycle commands with their own durable outcomes; removal evidence and
 * unattended-authority state come from the backend projection. Reads create
 * nothing, and every mutation disables automatic retry so an ambiguous outcome
 * is reconciled by reading durable truth rather than by replaying the request.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  copyAutomationDefinitionFocused,
  createAutomationDefinitionFocused,
  fetchAutomationCopyCandidate,
  fetchAutomationEditProjection,
  fetchAutomationFormAuthority,
  fetchAutomationRemovalImpact,
  previewAutomationSchedule,
  removeAutomationDefinitionFocused,
  saveAutomationDefinitionFocused,
  setAutomationDefinitionEnabledFocused,
} from "../../shared/api/api-client";
import { automationListQueryKey } from "./automation-query";
import {
  AUTOMATION_RUN_MODES,
  type AutomationRunMode,
} from "../../entities/operations/automation";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

interface FormState {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly resourceLibraryId: string;
  readonly mode: AutomationRunMode;
  readonly sourceScope: string;
  readonly itemLimit: string;
  readonly scheduleType: "interval" | "cron";
  readonly intervalSeconds: string;
  readonly cron: string;
  readonly timezone: string;
}

const NEW_FORM: FormState = {
  id: "",
  name: "",
  enabled: false,
  resourceLibraryId: "",
  mode: "scan-only",
  sourceScope: "",
  itemLimit: "100",
  scheduleType: "interval",
  intervalSeconds: "3600",
  cron: "",
  timezone: "UTC",
};

function buildCandidate(form: FormState): Record<string, unknown> {
  return {
    id: form.id.trim(),
    name: form.name.trim(),
    enabled: form.enabled,
    resourceLibraryId: form.resourceLibraryId,
    mode: form.mode,
    itemLimit: Number(form.itemLimit),
    ...(form.sourceScope.trim()
      ? { sourceScope: form.sourceScope.trim() }
      : {}),
    ...(form.scheduleType === "interval"
      ? {
          intervalSeconds: Number(form.intervalSeconds),
          cron: null,
          timezone: null,
        }
      : {
          intervalSeconds: null,
          cron: form.cron.trim(),
          timezone: form.timezone.trim(),
        }),
  };
}

function formIsValid(form: FormState, editing: boolean): boolean {
  return (
    (editing || form.id.trim().length > 0) &&
    form.name.trim().length > 0 &&
    form.resourceLibraryId.length > 0 &&
    /^\d+$/.test(form.itemLimit) &&
    Number(form.itemLimit) > 0 &&
    (form.scheduleType === "interval"
      ? /^\d+$/.test(form.intervalSeconds) && Number(form.intervalSeconds) > 0
      : form.cron.trim().length > 0 && form.timezone.trim().length > 0)
  );
}

export function AutomationLifecyclePage() {
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const params = useParams({ strict: false }) as { definitionId?: string };
  const definitionId = params.definitionId;
  const editing = typeof definitionId === "string" && definitionId.length > 0;

  const authorityQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-authority"],
    queryFn: () => fetchAutomationFormAuthority(token),
    enabled: token !== null,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const editQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-edit", definitionId ?? ""],
    queryFn: () => fetchAutomationEditProjection(token, definitionId ?? ""),
    enabled: token !== null && editing,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const [form, setForm] = useState<FormState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const authority = authorityQuery.data;
  const editProjection = editQuery.data;
  const authorityModel =
    authority !== undefined && authority.ok ? authority.model : null;
  const loaded =
    editProjection !== undefined && editProjection.ok
      ? editProjection.model.definition
      : null;
  const currentForm: FormState | null =
    form !== null
      ? form
      : loaded !== null
        ? {
            id: loaded.id,
            name: loaded.name,
            enabled: loaded.enabled,
            resourceLibraryId: loaded.resourceLibraryId,
            mode: loaded.mode,
            sourceScope: loaded.sourceScope ?? "",
            itemLimit: String(loaded.itemLimit),
            scheduleType: loaded.scheduleType,
            intervalSeconds:
              loaded.intervalSeconds !== null
                ? String(loaded.intervalSeconds)
                : "",
            cron: loaded.cron ?? "",
            timezone: loaded.timezone ?? "UTC",
          }
        : editing
          ? null
          : NEW_FORM;

  const activeIdentity = authorityModel?.active ?? null;
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: [automationListQueryKey] });
    void queryClient.invalidateQueries({
      queryKey: ["operations.automation-lifecycle-authority"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["operations.automation-lifecycle-edit", definitionId ?? ""],
    });
  };

  const saveMutation = useMutation({
    mutationFn: (input: {
      readonly form: FormState;
      readonly digest: string;
      readonly revisionId: string;
      readonly version: number;
    }) =>
      editing
        ? saveAutomationDefinitionFocused(token, {
            definitionId: input.form.id,
            object: buildCandidate(input.form),
            authority: {
              expectedRevisionId: input.revisionId,
              expectedVersion: input.version,
              expectedDigest: input.digest,
            },
          })
        : createAutomationDefinitionFocused(token, {
            object: buildCandidate(input.form),
            authority: {
              expectedRevisionId: input.revisionId,
              expectedVersion: input.version,
              expectedDigest: input.digest,
            },
          }),
    retry: false,
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (result) => {
      if (result.ok) {
        setNotice(
          result.model.action === "remove"
            ? "The definition was removed and its future unattended authority was revoked."
            : "The published definition is the Active configuration consumed by runtime.",
        );
        invalidate();
        if (result.model.definition?.id) {
          void navigate({
            to: "/operations/automation/lifecycle/$definitionId",
            params: { definitionId: result.model.definition.id },
          });
        }
        return;
      }
      setError(
        result.status === 409
          ? "The command was rejected because the Active configuration changed. Refresh and review durable state before submitting again; nothing is retried automatically."
          : `The command was rejected (${result.code}). Read the current durable state and try again.`,
      );
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly enabled: boolean;
      readonly digest: string;
      readonly revisionId: string;
      readonly version: number;
    }) =>
      setAutomationDefinitionEnabledFocused(token, {
        definitionId: input.id,
        enabled: input.enabled,
        authority: {
          expectedRevisionId: input.revisionId,
          expectedVersion: input.version,
          expectedDigest: input.digest,
        },
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (result) => {
      if (result.ok) {
        setNotice(
          result.model.definition?.enabled
            ? "The definition is enabled and eligible for future Scheduler evaluation; no work was started."
            : "The definition is disabled; future scheduled emission stops at the checked boundary and admitted work is unchanged.",
        );
        invalidate();
        return;
      }
      setError(
        `The state change was rejected (${result.code}). Refresh and review state.`,
      );
    },
  });

  const copyMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly digest: string;
      readonly revisionId: string;
      readonly version: number;
    }) =>
      copyAutomationDefinitionFocused(token, {
        definitionId: input.id,
        authority: {
          expectedRevisionId: input.revisionId,
          expectedVersion: input.version,
          expectedDigest: input.digest,
        },
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (result) => {
      if (result.ok) {
        setNotice(
          "The copy was published as a new, disabled definition without authority.",
        );
        invalidate();
        if (result.model.definition?.id) {
          void navigate({
            to: "/operations/automation/lifecycle/$definitionId",
            params: { definitionId: result.model.definition.id },
          });
        }
        return;
      }
      setError(`Copying the definition was rejected (${result.code}).`);
    },
  });

  const removeMutation = useMutation({
    mutationFn: (input: {
      readonly id: string;
      readonly digest: string;
      readonly revisionId: string;
      readonly version: number;
    }) =>
      removeAutomationDefinitionFocused(token, {
        definitionId: input.id,
        authority: {
          expectedRevisionId: input.revisionId,
          expectedVersion: input.version,
          expectedDigest: input.digest,
        },
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setNotice(null);
      setConfirmRemove(false);
    },
    onSuccess: (result) => {
      if (result.ok) {
        setNotice(
          "The definition was removed; grants, audits and run history were retained and future unattended authority was revoked.",
        );
        invalidate();
        void navigate({ to: "/operations/automation" });
        return;
      }
      setError(
        `Removal was rejected (${result.code}). The Active definition and its authority state are reported above.`,
      );
    },
  });

  const previewMutation = useMutation({
    mutationFn: (candidate: Record<string, unknown>) =>
      previewAutomationSchedule(token, {
        candidate,
        objectId: definitionId ?? null,
      }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (!result.ok) {
        setError(`Schedule preview was rejected (${result.code}).`);
      }
    },
  });

  const removalQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-removal", definitionId ?? ""],
    queryFn: () => fetchAutomationRemovalImpact(token, definitionId ?? ""),
    enabled: token !== null && editing,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const copyCandidateQuery = useQuery({
    queryKey: ["operations.automation-lifecycle-copy", definitionId ?? ""],
    queryFn: () => fetchAutomationCopyCandidate(token, definitionId ?? ""),
    enabled: false,
    retry: false,
  });

  const digest = activeIdentity?.digest ?? "";
  const version = activeIdentity?.revisionSequence ?? 0;
  const revisionId = activeIdentity?.revisionId ?? "";
  const canManage =
    authorityModel !== null && activeIdentity !== null && digest.length > 0;

  return (
    <AuthorizedReadBoundary
      query={authorityQuery}
      unavailableTitle="Automation lifecycle unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined || currentForm === null) {
          return (
            <StatusBanner variant="info" title="Loading the definition">
              <p>
                Reading the exact Active Automation authority and typed form.
              </p>
            </StatusBanner>
          );
        }
        if (!data.ok) {
          return (
            <StatusBanner
              variant="error"
              title="Automation authority unavailable"
            >
              <p>
                {data.details?.nextAction ??
                  "Refresh after the Active configuration is available."}
              </p>
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
        const valid = formIsValid(currentForm, editing);
        const update = (patch: Partial<FormState>) =>
          setForm({ ...currentForm, ...patch });
        const preview = previewMutation.data;
        const previewModel =
          preview !== undefined && preview.ok ? preview.model : null;
        const removal =
          removalQuery.data !== undefined && removalQuery.data.ok
            ? removalQuery.data.model
            : null;
        const copyCandidate =
          copyCandidateQuery.data !== undefined && copyCandidateQuery.data.ok
            ? copyCandidateQuery.data.model
            : null;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>
                  {editing
                    ? "Edit Automation definition"
                    : "Create Automation definition"}
                </h2>
                <p className="mf-dashboard-meta">
                  One checked 保存 composes the focused successor from the exact
                  Active configuration, validates the whole document and
                  atomically activates it. No separate Draft/Validate/Activate
                  step is required, and unrelated changes never ride along.
                </p>
                {activeIdentity !== null && (
                  <p className="mf-dashboard-meta">
                    Active revision {activeIdentity.revisionId} · version{" "}
                    {activeIdentity.revisionSequence}
                  </p>
                )}
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <section className="mf-count-section">
              <h3>Definition</h3>
              {!editing && (
                <>
                  <p className="mf-label">
                    <label htmlFor="lifecycle-id">Definition ID</label>
                  </p>
                  <input
                    id="lifecycle-id"
                    value={currentForm.id}
                    onChange={(event) => update({ id: event.target.value })}
                    maxLength={64}
                  />
                </>
              )}
              <p className="mf-label">
                <label htmlFor="lifecycle-name">Name</label>
              </p>
              <input
                id="lifecycle-name"
                value={currentForm.name}
                onChange={(event) => update({ name: event.target.value })}
                maxLength={120}
              />
              <p className="mf-label">
                <label htmlFor="lifecycle-library">ResourceLibrary</label>
              </p>
              <select
                id="lifecycle-library"
                value={currentForm.resourceLibraryId}
                onChange={(event) =>
                  update({ resourceLibraryId: event.target.value })
                }
              >
                <option value="">select one ResourceLibrary</option>
                {authorityModel?.resourceLibraries.map((option) => (
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
                <label htmlFor="lifecycle-scope">Relative source scope</label>
              </p>
              <input
                id="lifecycle-scope"
                value={currentForm.sourceScope}
                onChange={(event) =>
                  update({ sourceScope: event.target.value })
                }
                placeholder="empty for the ResourceLibrary root"
                maxLength={1024}
              />
              <p className="mf-label">
                <label htmlFor="lifecycle-mode">Run mode</label>
              </p>
              <select
                id="lifecycle-mode"
                value={currentForm.mode}
                onChange={(event) =>
                  update({ mode: event.target.value as AutomationRunMode })
                }
              >
                {AUTOMATION_RUN_MODES.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode}
                  </option>
                ))}
              </select>
              <p className="mf-label">
                <label htmlFor="lifecycle-limit">Item limit</label>
              </p>
              <input
                id="lifecycle-limit"
                value={currentForm.itemLimit}
                onChange={(event) => update({ itemLimit: event.target.value })}
                inputMode="numeric"
              />
              <p className="mf-label">
                <label htmlFor="lifecycle-enabled">Enabled</label>
              </p>
              <select
                id="lifecycle-enabled"
                value={currentForm.enabled ? "yes" : "no"}
                onChange={(event) =>
                  update({ enabled: event.target.value === "yes" })
                }
              >
                <option value="no">disabled</option>
                <option value="yes">enabled</option>
              </select>
              {!editing && (
                <p className="mf-dashboard-meta">
                  A new definition is published disabled. Enable it as a
                  separate explicit action after it exists.
                </p>
              )}
            </section>
            <section className="mf-count-section">
              <h3>Schedule</h3>
              <p className="mf-label">
                <label htmlFor="lifecycle-schedule-type">Schedule type</label>
              </p>
              <select
                id="lifecycle-schedule-type"
                value={currentForm.scheduleType}
                onChange={(event) =>
                  update({
                    scheduleType:
                      event.target.value === "cron" ? "cron" : "interval",
                  })
                }
              >
                <option value="interval">interval (seconds)</option>
                <option value="cron">Cron with IANA timezone</option>
              </select>
              {currentForm.scheduleType === "interval" ? (
                <>
                  <p className="mf-label">
                    <label htmlFor="lifecycle-interval">Interval seconds</label>
                  </p>
                  <input
                    id="lifecycle-interval"
                    value={currentForm.intervalSeconds}
                    onChange={(event) =>
                      update({ intervalSeconds: event.target.value })
                    }
                    inputMode="numeric"
                  />
                </>
              ) : (
                <>
                  <p className="mf-label">
                    <label htmlFor="lifecycle-cron">Cron expression</label>
                  </p>
                  <input
                    id="lifecycle-cron"
                    value={currentForm.cron}
                    onChange={(event) => update({ cron: event.target.value })}
                    placeholder="0 8 * * *"
                    maxLength={64}
                  />
                  <p className="mf-label">
                    <label htmlFor="lifecycle-timezone">Timezone</label>
                  </p>
                  <input
                    id="lifecycle-timezone"
                    value={currentForm.timezone}
                    onChange={(event) =>
                      update({ timezone: event.target.value })
                    }
                    maxLength={64}
                  />
                </>
              )}
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={!valid || previewMutation.isPending}
                  onClick={() =>
                    previewMutation.mutate(buildCandidate(currentForm))
                  }
                >
                  {previewMutation.isPending
                    ? "Calculating…"
                    : "Preview upcoming times"}
                </Button>
              </div>
              {previewModel !== null && (
                <>
                  <p className="mf-dashboard-meta">
                    {previewModel.scheduleType} schedule · zero mutation ·{" "}
                    {previewModel.timezone ?? "no timezone"}
                  </p>
                  {previewModel.upcoming.length > 0 && (
                    <ul>
                      {previewModel.upcoming.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                  {previewModel.notes.map((note) => (
                    <p className="mf-dashboard-meta" key={note}>
                      {note}
                    </p>
                  ))}
                </>
              )}
            </section>
            <div className="mf-actions">
              <Button
                type="button"
                disabled={!valid || !canManage || saveMutation.isPending}
                onClick={() =>
                  saveMutation.mutate({
                    form: currentForm,
                    digest,
                    revisionId,
                    version,
                  })
                }
              >
                {saveMutation.isPending ? "Publishing…" : "保存"}
              </Button>
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/automation"
              >
                Back to Automation
              </Link>
            </div>
            {!canManage && (
              <StatusBanner variant="info" title="Save unavailable">
                <p>
                  The exact Active authority could not be read, so no Save is
                  offered. Refresh after Active configuration is available.
                </p>
              </StatusBanner>
            )}
            {editing && (
              <section className="mf-count-section">
                <h3>Lifecycle actions</h3>
                <div className="mf-actions">
                  <Button
                    type="button"
                    disabled={!canManage || toggleMutation.isPending}
                    onClick={() =>
                      toggleMutation.mutate({
                        id: currentForm.id,
                        enabled: !currentForm.enabled,
                        digest,
                        revisionId,
                        version,
                      })
                    }
                  >
                    {toggleMutation.isPending
                      ? "Updating…"
                      : currentForm.enabled
                        ? "Disable schedule"
                        : "Enable schedule"}
                  </Button>
                  <Button
                    type="button"
                    disabled={!canManage || copyMutation.isPending}
                    onClick={() =>
                      copyMutation.mutate({
                        id: currentForm.id,
                        digest,
                        revisionId,
                        version,
                      })
                    }
                  >
                    {copyMutation.isPending
                      ? "Copying…"
                      : "Copy as disabled definition"}
                  </Button>
                </div>
                {copyCandidate !== null && (
                  <p className="mf-dashboard-meta">
                    Copy candidate {copyCandidate.definition.id} (
                    {copyCandidate.definition.enabled ? "enabled" : "disabled"})
                  </p>
                )}
                <h3>Reference-safe removal</h3>
                {removal === null ? (
                  <p className="mf-dashboard-meta">Reading removal evidence…</p>
                ) : (
                  <>
                    <p className="mf-dashboard-meta">
                      {removal.referenceTotal} configuration reference(s) ·
                      unattended authority {removal.authorityStatus}
                    </p>
                    <p className="mf-label">
                      <label htmlFor="lifecycle-confirm-removal">
                        Confirm definition removal
                      </label>
                    </p>
                    <label htmlFor="lifecycle-confirm-removal">
                      <input
                        id="lifecycle-confirm-removal"
                        type="checkbox"
                        checked={confirmRemove}
                        onChange={(event) =>
                          setConfirmRemove(event.target.checked)
                        }
                      />{" "}
                      I confirm removing this definition; future scheduling and
                      unattended mutation stop while grants, audits and history
                      are retained
                    </label>
                    <div className="mf-actions">
                      <Button
                        type="button"
                        disabled={
                          !confirmRemove ||
                          !canManage ||
                          removeMutation.isPending
                        }
                        onClick={() =>
                          removeMutation.mutate({
                            id: currentForm.id,
                            digest,
                            revisionId,
                            version,
                          })
                        }
                      >
                        {removeMutation.isPending
                          ? "Removing…"
                          : "Remove definition"}
                      </Button>
                    </div>
                  </>
                )}
              </section>
            )}
            {notice !== null && (
              <StatusBanner variant="success" title="Published">
                <p>{notice}</p>
              </StatusBanner>
            )}
            {error !== null && (
              <StatusBanner variant="error" title="Command not completed">
                <p>{error}</p>
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
