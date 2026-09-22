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
import {
  Link,
  useNavigate,
  useParams,
  useSearch,
} from "@tanstack/react-router";
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
import {
  filesReturnHref,
  filesReturnSearch,
  readFilesReturnContext,
} from "../../shared/navigation/files-return";

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
  onReload,
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
  };
  readonly onSaved: (message: string) => void;
  readonly onReload: () => void;
}) {
  const token = useAuthToken();
  const queryClient = useQueryClient();
  const recognitionTypes = options.recognitionTypes.filter(
    (value) => value.enabled,
  );
  // RecognitionType is the single operator-facing choice source. The three
  // downstream policies are never editable on their own; they are always the
  // exact pinned mapping of the selected RecognitionType, so the normal journey
  // can never submit an `incompatible_choice`.
  const [recognitionTypeId, setRecognitionTypeId] = useState<string>(
    item.choice.recognitionTypeId ?? "",
  );
  const [result, setResult] = useState<string | null>(null);

  const editable = Boolean(item.nextAction) && item.status === "ready";
  const hasSelection = recognitionTypeId !== "";
  const selected = hasSelection
    ? recognitionTypes.find((value) => value.id === recognitionTypeId)
    : undefined;
  // A selected RecognitionType that is missing from the current pinned options
  // (disabled or removed), or whose downstream mapping is incomplete, must fail
  // closed: the editor shows an actionable reload state and submits nothing.
  const selectionUnavailable = hasSelection && selected === undefined;
  const mappingComplete =
    selected !== undefined &&
    selected.namingPolicyId !== null &&
    selected.classificationPolicyId !== null &&
    selected.organizePolicyId !== null;
  const mappingIncomplete = selected !== undefined && !mappingComplete;
  const failClosed = selectionUnavailable || mappingIncomplete;

  // The submitted choice is always projected from the pinned mapping, so an
  // initial render with a stale stored downstream policy is normalized to the
  // RecognitionType's exact policies before any save.
  const projectedChoice: OrganizeChoiceModel | null =
    selected !== undefined && mappingComplete
      ? {
          metadata: item.choice.metadata,
          recognitionTypeId: selected.id,
          namingPolicyId: selected.namingPolicyId,
          classificationPolicyId: selected.classificationPolicyId,
          organizePolicyId: selected.organizePolicyId,
        }
      : null;

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
            value={recognitionTypeId}
            disabled={!editable}
            onChange={(event) => {
              setResult(null);
              setRecognitionTypeId(event.target.value);
            }}
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
            value={projectedChoice?.namingPolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.namingPolicyId !== undefined &&
              projectedChoice?.namingPolicyId !== null && (
                <option value={projectedChoice.namingPolicyId}>
                  {projectedChoice.namingPolicyId}
                </option>
              )}
          </select>
        </label>
        <label>
          Classification policy
          <select
            aria-label={`Classification policy ${item.itemId}`}
            value={projectedChoice?.classificationPolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.classificationPolicyId !== undefined &&
              projectedChoice?.classificationPolicyId !== null && (
                <option value={projectedChoice.classificationPolicyId}>
                  {projectedChoice.classificationPolicyId}
                </option>
              )}
          </select>
        </label>
        <label>
          Organize policy
          <select
            aria-label={`Organize policy ${item.itemId}`}
            value={projectedChoice?.organizePolicyId ?? ""}
            disabled
          >
            <option value="">—</option>
            {projectedChoice?.organizePolicyId !== undefined &&
              projectedChoice?.organizePolicyId !== null && (
                <option value={projectedChoice.organizePolicyId}>
                  {projectedChoice.organizePolicyId}
                </option>
              )}
          </select>
        </label>
        <p className="mf-dashboard-meta">
          RecognitionType determines the naming, classification and organize
          policies. Selecting a RecognitionType applies its exact pinned
          configuration mapping; these downstream policies cannot be chosen
          independently.
        </p>
      </div>
      {failClosed && (
        <StatusBanner
          variant="error"
          title="RecognitionType mapping unavailable"
        >
          <p>
            {selectionUnavailable
              ? `The selected RecognitionType "${recognitionTypeId}" is not in the current pinned configuration options, so its policies cannot be applied.`
              : `The selected RecognitionType "${recognitionTypeId}" is missing a configured naming, classification or organize policy in the current pinned configuration.`}
          </p>
          <p className="mf-dashboard-meta">
            Reload the intent to load the current options and choose an
            available RecognitionType. No choice was submitted.
          </p>
          <div className="mf-actions">
            <Button type="button" variant="secondary" onClick={onReload}>
              Reload options
            </Button>
          </div>
        </StatusBanner>
      )}
      <div className="mf-actions">
        <Button
          type="button"
          disabled={
            mutation.isPending ||
            !editable ||
            !hasSelection ||
            failClosed ||
            projectedChoice === null
          }
          onClick={() => {
            if (projectedChoice !== null) {
              mutation.mutate(projectedChoice);
            }
          }}
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
  const searchParams = useSearch({ strict: false }) as Record<string, unknown>;
  const filesReturn = readFilesReturnContext(searchParams);
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
          search: filesReturn === null ? {} : filesReturnSearch(filesReturn),
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
                onReload={refresh}
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
                {filesReturn !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to={filesReturnHref(filesReturn)}
                  >
                    返回文件
                  </Link>
                )}
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
