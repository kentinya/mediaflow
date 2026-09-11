/**
 * Durable manual intent detail: optimistic choice editing and exact Preview.
 *
 * Every control comes from the backend document: the enabled pinned options,
 * per-item ``version`` values and the advertised ``actions`` availability.
 * A choice edit submits the intent and item versions the operator actually
 * saw, so a concurrent change is rejected atomically instead of silently
 * overwriting another edit. Editing a choice invalidates earlier Preview
 * evidence, and the page never treats a Preview as execution authority.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import {
  submitOrganizePreview,
  updateOrganizeChoice,
} from "../../shared/api/api-client";
import type {
  OrganizeChoiceModel,
  OrganizeIntentItemModel,
} from "../../entities/operations/organize";
import {
  organizeIntentQueryKey,
  organizeIntentQueryOptions,
} from "./organize-query";
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

function safeValue(value: string | null): string {
  return value === null || value === "" ? "—" : value;
}

function ChoiceEditor({
  intentId,
  intentVersion,
  item,
  options,
  onSaved,
}: {
  readonly intentId: string;
  readonly intentVersion: number;
  readonly item: OrganizeIntentItemModel;
  readonly options: {
    readonly recognitionTypes: readonly {
      readonly id: string;
      readonly name: string | null;
      readonly metadataPolicyId: string | null;
      readonly namingPolicyId: string | null;
      readonly classificationPolicyId: string | null;
      readonly organizePolicyId: string | null;
      readonly enabled: boolean;
    }[];
    readonly namingPolicies: readonly { readonly id: string }[];
    readonly classificationPolicies: readonly { readonly id: string }[];
    readonly organizePolicies: readonly {
      readonly id: string;
      readonly operation: string | null;
    }[];
  };
  readonly onSaved: (message: string) => void;
}) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const recognitionTypes = options.recognitionTypes.filter(
    (value) => value.enabled,
  );
  const [choice, setChoice] = useState<OrganizeChoiceModel>(item.choice);
  const [result, setResult] = useState<string | null>(null);

  const selected = recognitionTypes.find(
    (value) => value.id === choice.recognitionTypeId,
  );
  // The pinned RecognitionType is the authority for which downstream policies
  // are even offered; the operator may still choose among the enabled ones.
  const namingPolicies = options.namingPolicies.filter((value) => value.id);
  const classificationPolicies = options.classificationPolicies.filter(
    (value) => value.id,
  );
  const organizePolicies = options.organizePolicies.filter((value) => value.id);

  const mutation = useMutation({
    mutationFn: (next: OrganizeChoiceModel) =>
      updateOrganizeChoice(token, {
        intentId,
        itemId: item.itemId,
        expectedVersion: intentVersion,
        expectedItemVersion: item.version,
        ...(next.recognitionTypeId
          ? { recognitionTypeId: next.recognitionTypeId }
          : {}),
        ...(next.namingPolicyId ? { namingPolicyId: next.namingPolicyId } : {}),
        ...(next.classificationPolicyId
          ? { classificationPolicyId: next.classificationPolicyId }
          : {}),
        ...(next.organizePolicyId
          ? { organizePolicyId: next.organizePolicyId }
          : {}),
      }),
    retry: false,
    onSuccess: (value) => {
      if (value.ok) {
        setResult(null);
        onSaved(
          "Choice saved durably. Every earlier Preview of this intent is now historical evidence; create a fresh Preview before executing.",
        );
        void queryClient.invalidateQueries({
          queryKey: [organizeIntentQueryKey],
        });
        return;
      }
      setResult(
        value.status === 409
          ? "Another change was saved first, so this edit was rejected without overwriting it. Reload the intent and apply the choice again."
          : `The choice was rejected (${value.code}). Nothing was changed.`,
      );
    },
  });

  return (
    <section className="mf-count-section">
      <h3>{item.filename ?? item.itemId}</h3>
      <dl>
        <dt>Source identity</dt>
        <dd>{safeValue(item.sourceFileId)}</dd>
        <dt>Storage-relative path</dt>
        <dd>{safeValue(item.sourcePath)}</dd>
        <dt>ResourceLibrary / Storage</dt>
        <dd>
          {safeValue(item.resourceLibraryId)} /{" "}
          {safeValue(item.sourceStorageId)}
        </dd>
        <dt>Scan / occurrence</dt>
        <dd>
          {displayEnum(item.scanStatus ?? "unknown")} /{" "}
          {displayEnum(item.occurrenceState ?? "unknown")}
        </dd>
        <dt>Item status / version</dt>
        <dd>
          {displayEnum(item.status)} / {item.version}
        </dd>
      </dl>
      {item.failure !== null && (
        <StatusBanner variant="error" title="Item finding">
          <p>{item.failure.message}</p>
          <p className="mf-dashboard-meta">{item.failure.nextAction}</p>
        </StatusBanner>
      )}
      <div className="mf-field-group">
        <label>
          RecognitionType
          <select
            aria-label={`RecognitionType ${item.itemId}`}
            value={choice.recognitionTypeId ?? ""}
            disabled={!item.nextAction || item.status !== "ready"}
            onChange={(event) =>
              setChoice({
                ...choice,
                recognitionTypeId: event.target.value,
              })
            }
          >
            <option value="">Choose a RecognitionType</option>
            {recognitionTypes.map((value) => (
              <option key={value.id} value={value.id}>
                {value.name ?? value.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Naming policy
          <select
            aria-label={`Naming policy ${item.itemId}`}
            value={choice.namingPolicyId ?? ""}
            disabled={!item.nextAction || item.status !== "ready"}
            onChange={(event) =>
              setChoice({ ...choice, namingPolicyId: event.target.value })
            }
          >
            <option value="">Choose a naming policy</option>
            {namingPolicies.map((value) => (
              <option key={value.id} value={value.id}>
                {value.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Classification policy
          <select
            aria-label={`Classification policy ${item.itemId}`}
            value={choice.classificationPolicyId ?? ""}
            disabled={!item.nextAction || item.status !== "ready"}
            onChange={(event) =>
              setChoice({
                ...choice,
                classificationPolicyId: event.target.value,
              })
            }
          >
            <option value="">Choose a classification policy</option>
            {classificationPolicies.map((value) => (
              <option key={value.id} value={value.id}>
                {value.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Organize policy
          <select
            aria-label={`Organize policy ${item.itemId}`}
            value={choice.organizePolicyId ?? ""}
            disabled={!item.nextAction || item.status !== "ready"}
            onChange={(event) =>
              setChoice({ ...choice, organizePolicyId: event.target.value })
            }
          >
            <option value="">Choose an organize policy</option>
            {organizePolicies.map((value) => (
              <option key={value.id} value={value.id}>
                {value.id}
                {value.operation ? ` (${value.operation})` : ""}
              </option>
            ))}
          </select>
        </label>
        {selected !== undefined && (
          <p className="mf-dashboard-meta">
            The pinned RecognitionType advertises metadata{" "}
            {safeValue(selected.metadataPolicyId)}, naming{" "}
            {safeValue(selected.namingPolicyId)}, classification{" "}
            {safeValue(selected.classificationPolicyId)} and organize{" "}
            {safeValue(selected.organizePolicyId)} policies.
          </p>
        )}
      </div>
      <div className="mf-actions">
        <Button
          type="button"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(choice)}
        >
          {mutation.isPending ? "Saving choice…" : "Save choice"}
        </Button>
      </div>
      {result !== null && (
        <StatusBanner variant="error" title="Choice not saved">
          <p>{result}</p>
        </StatusBanner>
      )}
    </section>
  );
}

export function OrganizeIntentPage() {
  const { intentId } = useParams({
    from: "/operations/organize/intent/$intentId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const [notice, setNotice] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const intentQuery = useQuery(organizeIntentQueryOptions(token, intentId));

  const previewMutation = useMutation({
    mutationFn: (expectedVersion: number) =>
      submitOrganizePreview(token, { intentId, expectedVersion }),
    retry: false,
    onMutate: () => setPreviewError(null),
    onSuccess: (value) => {
      if (value.ok) {
        void navigate({
          to: "/operations/organize/preview/$previewId",
          params: { previewId: value.model.previewId },
        });
        return;
      }
      setPreviewError(
        `The exact Preview was rejected (${value.code}). Nothing was changed; reload the intent and request a fresh Preview.`,
      );
    },
  });

  return (
    <AuthorizedReadBoundary
      query={intentQuery}
      unavailableTitle="Manual intent unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading durable intent">
              <p>Reading the current durable manual intent.</p>
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
        const intent = data.model;
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Manual organize intent</h2>
                <p className="mf-dashboard-meta">
                  Intent {intent.intentId} · version {intent.version} ·{" "}
                  {displayEnum(intent.status)} · configuration{" "}
                  {safeValue(intent.configurationSnapshotId)}
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <p className="mf-dashboard-meta">
              This intent changes no Storage. Editing a choice invalidates every
              earlier Preview of this intent, so the operator always executes
              evidence that matches the current choices.
            </p>
            {notice !== null && (
              <StatusBanner variant="info" title="Choice updated">
                <p>{notice}</p>
              </StatusBanner>
            )}
            {intent.failure !== null && (
              <StatusBanner variant="error" title="Intent finding">
                <p>{intent.failure.message}</p>
                <p className="mf-dashboard-meta">{intent.failure.nextAction}</p>
              </StatusBanner>
            )}
            {intent.items.map((item) => (
              <ChoiceEditor
                key={item.itemId}
                intentId={intent.intentId}
                intentVersion={intent.version}
                item={item}
                options={intent.options}
                onSaved={setNotice}
              />
            ))}
            <section className="mf-count-section">
              <h3>Exact Preview</h3>
              <p className="mf-dashboard-meta">
                {intent.actions.preview.available
                  ? "The backend advertises a zero-mutation Preview for the current reviewed choices."
                  : `Unavailable: ${intent.actions.preview.reason ?? "the backend does not advertise it"}`}
              </p>
              {intent.actions.preview.durableOutcome && (
                <p className="mf-dashboard-meta">
                  {intent.actions.preview.durableOutcome}
                </p>
              )}
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={
                    !intent.actions.preview.available ||
                    previewMutation.isPending
                  }
                  onClick={() => previewMutation.mutate(intent.version)}
                >
                  {previewMutation.isPending
                    ? "Creating exact Preview…"
                    : "Create exact Preview"}
                </Button>
                <Link
                  className="mf-button mf-button-secondary"
                  to="/operations"
                >
                  Back to Operations
                </Link>
              </div>
              {previewError !== null && (
                <StatusBanner variant="error" title="Preview not created">
                  <p>{previewError}</p>
                </StatusBanner>
              )}
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}
