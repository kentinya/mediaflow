/**
 * V2 Automation successor-Draft editor.
 *
 * The editor reads the backend's Draft document: the exact open Draft with its
 * optimistic version, the bounded definition form, and the backend-advertised
 * save/validate/activate transports. Saving, validation and checked
 * activation are separate explicit actions bound to the exact Draft revision;
 * a stale version is rejected atomically and the page refreshes to durable
 * truth without replaying anything. Activation never starts work.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  activateAutomationDraft,
  createAutomationSuccessorDraft,
  saveAutomationDefinitionDraft,
  validateAutomationDraft,
} from "../../shared/api/api-client";
import {
  automationDraftQueryKey,
  automationDraftQueryOptions,
} from "./automation-query";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";
import { StatusBanner } from "../../shared/ui/StatusBanner";
import { Button } from "../../shared/ui/Button";

export function AutomationEditorPage() {
  const { definitionId } = useParams({
    from: "/operations/automation/editor/$definitionId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<{
    readonly revisionId: string;
    readonly name: string;
    readonly enabled: boolean;
    readonly sourceScope: string;
    readonly itemLimit: string;
  } | null>(null);
  const [confirmActivate, setConfirmActivate] = useState(false);
  const [validationErrors, setValidationErrors] = useState<readonly string[]>(
    [],
  );
  const [error, setError] = useState<string | null>(null);

  const draftQuery = useQuery(automationDraftQueryOptions(token, definitionId));

  const draftData = draftQuery.data;
  const loadedDraft =
    draftData !== undefined && draftData.ok ? draftData.model.draft : null;
  // The form state is derived per Draft revision: the first render of a given
  // revision seeds the bounded form from the durable document, and every edit
  // updates that exact revision's form. No effect re-seeds it.
  const currentForm =
    form !== null &&
    loadedDraft !== null &&
    form.revisionId === loadedDraft.revisionId
      ? form
      : loadedDraft !== null
        ? {
            revisionId: loadedDraft.revisionId,
            name: loadedDraft.definition.name,
            enabled: loadedDraft.definition.enabled,
            sourceScope: loadedDraft.definition.sourceScope ?? "",
            itemLimit: String(loadedDraft.definition.itemLimit),
          }
        : null;
  const updateForm = (
    patch: Partial<{
      name: string;
      enabled: boolean;
      sourceScope: string;
      itemLimit: string;
    }>,
  ) => {
    if (currentForm !== null) {
      setForm({ ...currentForm, ...patch });
    }
  };

  const draftMutation = useMutation({
    mutationFn: (activeRevisionId: string) =>
      createAutomationSuccessorDraft(token, { activeRevisionId }),
    retry: false,
    onMutate: () => setError(null),
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [automationDraftQueryKey],
        });
        return;
      }
      setError(
        `Starting the successor Draft was rejected (${result.code}). Reload and try again; nothing is retried automatically.`,
      );
    },
  });

  const saveMutation = useMutation({
    mutationFn: (input: {
      revisionId: string;
      expectedVersion: number;
      object: Record<string, unknown>;
    }) =>
      saveAutomationDefinitionDraft(token, {
        revisionId: input.revisionId,
        definitionId,
        expectedVersion: input.expectedVersion,
        object: input.object,
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setValidationErrors([]);
    },
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [automationDraftQueryKey],
        });
        setConfirmActivate(false);
        return;
      }
      setError(
        result.status === 409
          ? "The Draft changed before the save was applied. Refresh the Draft and apply the change again; the winning revision was preserved."
          : `Saving the Draft was rejected (${result.code}). Reload and try again; nothing is retried automatically.`,
      );
    },
  });

  const validateMutation = useMutation({
    mutationFn: (revisionId: string) =>
      validateAutomationDraft(token, { revisionId }),
    retry: false,
    onMutate: () => {
      setError(null);
      setValidationErrors([]);
    },
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [automationDraftQueryKey],
        });
        setValidationErrors(result.model.validationErrors);
        return;
      }
      setError(
        `Validation was rejected (${result.code}). Reload the Draft and try again; validation is zero-mutation.`,
      );
    },
  });

  const activateMutation = useMutation({
    mutationFn: (input: { expectedVersion: number }) =>
      activateAutomationDraft(token, {
        definitionId,
        expectedVersion: input.expectedVersion,
      }),
    retry: false,
    onMutate: () => {
      setError(null);
      setConfirmActivate(false);
    },
    onSuccess: (result) => {
      if (result.ok) {
        void queryClient.invalidateQueries({
          queryKey: [automationDraftQueryKey],
        });
        void navigate({
          to: "/operations/automation/definition/$definitionId",
          params: { definitionId },
        });
        return;
      }
      setError(
        result.status === 409
          ? "Activation was rejected: the Draft or an underlying check changed. Refresh the Draft, re-run the read-only checks and activate again."
          : `Activation was rejected (${result.code}). Read the current durable state and try again; nothing is retried automatically.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={draftQuery}
      unavailableTitle="Automation Draft unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading Draft">
              <p>Reading the open successor Draft and its exact version.</p>
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
        const draftDocument = data.model;
        const draft = draftDocument.draft;
        if (draft === null) {
          const createDraft = draftDocument.actions.createDraft;
          return (
            <div className="mf-dashboard">
              <header className="mf-dashboard-head">
                <div>
                  <h2>Edit Automation definition</h2>
                  <p className="mf-dashboard-meta">
                    No open successor Draft contains this definition.
                  </p>
                </div>
                <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              </header>
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={!createDraft.available || draftMutation.isPending}
                  onClick={() => {
                    if (draftDocument.activeConfiguration !== null) {
                      draftMutation.mutate(
                        draftDocument.activeConfiguration.revisionId,
                      );
                    }
                  }}
                >
                  {draftMutation.isPending
                    ? "Starting successor Draft…"
                    : "Start successor Draft"}
                </Button>
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations/automation/definition/$definitionId"
                  params={{ definitionId }}
                >
                  Back to the definition
                </Link>
              </div>
              {!createDraft.available && createDraft.reason && (
                <StatusBanner variant="info" title="Draft start unavailable">
                  <p>{createDraft.reason}</p>
                </StatusBanner>
              )}
              {error !== null && (
                <StatusBanner variant="error" title="Draft not started">
                  <p>{error}</p>
                </StatusBanner>
              )}
            </div>
          );
        }
        const save = draftDocument.actions.save;
        const validate = draftDocument.actions.validate;
        const activate = draftDocument.actions.activate;
        const formName = currentForm?.name ?? "";
        const formItemLimit = currentForm?.itemLimit ?? "";
        const formEnabled = currentForm?.enabled ?? false;
        const formScope = currentForm?.sourceScope ?? "";
        const formValid =
          formName.trim().length > 0 &&
          /^\d+$/.test(formItemLimit) &&
          Number(formItemLimit) > 0;
        const buildObject = (): Record<string, unknown> => ({
          ...draft.definition,
          name: formName.trim(),
          enabled: formEnabled,
          ...(formScope ? { sourceScope: formScope } : { sourceScope: null }),
          itemLimit: Number(formItemLimit),
        });
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Edit Automation definition</h2>
                <p className="mf-dashboard-meta">
                  Draft revision {draft.revisionId} · version{" "}
                  {draft.revisionVersion} · {draft.revisionStatus} · the Active
                  configuration is unchanged until checked activation.
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            {draft.validationErrors.length > 0 && (
              <StatusBanner variant="error" title="Draft validation findings">
                <ul>
                  {draft.validationErrors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Bounded definition form</h3>
              <p className="mf-label">
                <label htmlFor="automation-edit-name">Name</label>
              </p>
              <input
                id="automation-edit-name"
                value={currentForm?.name ?? ""}
                onChange={(event) => updateForm({ name: event.target.value })}
                maxLength={120}
              />
              <p className="mf-label">
                <label htmlFor="automation-edit-enabled">Enabled</label>
              </p>
              <select
                id="automation-edit-enabled"
                value={currentForm?.enabled ? "yes" : "no"}
                onChange={(event) =>
                  updateForm({ enabled: event.target.value === "yes" })
                }
              >
                <option value="no">disabled</option>
                <option value="yes">enabled</option>
              </select>
              <p className="mf-label">
                <label htmlFor="automation-edit-scope">
                  Relative source scope
                </label>
              </p>
              <input
                id="automation-edit-scope"
                value={currentForm?.sourceScope ?? ""}
                onChange={(event) =>
                  updateForm({ sourceScope: event.target.value })
                }
                maxLength={256}
              />
              <p className="mf-label">
                <label htmlFor="automation-edit-limit">Item limit</label>
              </p>
              <input
                id="automation-edit-limit"
                value={currentForm?.itemLimit ?? ""}
                onChange={(event) =>
                  updateForm({ itemLimit: event.target.value })
                }
                inputMode="numeric"
              />
              <p className="mf-dashboard-meta">
                ResourceLibrary {draft.definition.resourceLibraryId} · mode{" "}
                {draft.definition.mode} · schedule{" "}
                {draft.definition.scheduleType === "interval"
                  ? `every ${draft.definition.intervalSeconds} seconds`
                  : `${draft.definition.cron} (${draft.definition.timezone})`}
              </p>
            </section>
            <div className="mf-actions">
              <Button
                type="button"
                disabled={
                  !save.available || !formValid || saveMutation.isPending
                }
                onClick={() =>
                  saveMutation.mutate({
                    revisionId: draft.revisionId,
                    expectedVersion: draft.revisionVersion,
                    object: buildObject(),
                  })
                }
              >
                {saveMutation.isPending ? "Saving Draft…" : "Save into Draft"}
              </Button>
              <Button
                type="button"
                disabled={!validate.available || validateMutation.isPending}
                onClick={() => validateMutation.mutate(draft.revisionId)}
              >
                {validateMutation.isPending
                  ? "Validating Draft…"
                  : "Validate Draft"}
              </Button>
            </div>
            {validationErrors.length > 0 && (
              <StatusBanner variant="error" title="Validation failed">
                <ul>
                  {validationErrors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </StatusBanner>
            )}
            {validationErrors.length === 0 && validateMutation.isSuccess && (
              <StatusBanner variant="success" title="Draft validated">
                <p>
                  The Draft validated with no findings and zero mutation. Check
                  the read-only evidence and activate explicitly to publish.
                </p>
              </StatusBanner>
            )}
            <section className="mf-count-section">
              <h3>Checked activation</h3>
              <p className="mf-dashboard-meta">
                {activate.available
                  ? "Activation runs the existing read-only Storage, strategy and destination checks server-side and publishes this exact Draft as the immutable Active configuration. No Scan, Job, Task or occurrence is started."
                  : `Activation unavailable: ${activate.reason ?? "not advertised"}`}
              </p>
              {activate.available && (
                <div className="mf-actions">
                  <label>
                    <input
                      type="checkbox"
                      checked={confirmActivate}
                      aria-label="Confirm checked activation"
                      onChange={(event) =>
                        setConfirmActivate(event.target.checked)
                      }
                    />{" "}
                    I confirm this exact Draft as the new Active configuration
                  </label>
                  <Button
                    type="button"
                    disabled={
                      !confirmActivate ||
                      activateMutation.isPending ||
                      draft.revisionStatus !== "validated"
                    }
                    onClick={() =>
                      activateMutation.mutate({
                        expectedVersion: draft.revisionVersion,
                      })
                    }
                  >
                    {activateMutation.isPending
                      ? "Activating Draft…"
                      : "Activate checked Draft"}
                  </Button>
                </div>
              )}
            </section>
            <div className="mf-actions">
              <Link
                className="mf-button mf-button-secondary"
                to="/operations/automation/definition/$definitionId"
                params={{ definitionId }}
              >
                Back to the definition
              </Link>
            </div>
            {error !== null && (
              <StatusBanner variant="error" title="Draft action not completed">
                <p>{error}</p>
              </StatusBanner>
            )}
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
