/**
 * Exact manual Organize Preview: visible findings, exact selection and the one
 * meaningful Web Execute action.
 *
 * The page renders only backend-advertised facts: which items are current,
 * complete and executable, what each exact plan would do (operation,
 * attachments, conflicts, capabilities, destructive implications) and whether
 * the resident Processing Worker can actually claim admitted work. Blocked or
 * unselected siblings stay visible and can never be silently included.
 *
 * Execute is one confirmation: the browser submits the reviewed selection, the
 * optimistic intent version and the destructive choices the operator actually
 * made. It never receives, stores or copies an execution token, digest or
 * authorization identifier, and an ambiguous or rejected admission is never
 * retried automatically.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { executeOrganizePreview } from "../../shared/api/api-client";
import type {
  ManualPreviewItemModel,
  ManualPreviewModel,
} from "../../entities/operations/preview";
import type { OrganizePreviewModel } from "../../entities/operations/organize";
import {
  organizeExecutionListQueryKey,
  organizePreviewQueryOptions,
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

interface DestructiveImplications {
  readonly overwriteRequired: boolean;
  readonly sourceCleanupRequired: boolean;
  readonly statement: string;
}

function destructiveImplications(
  item: ManualPreviewItemModel,
): DestructiveImplications | null {
  const plan = (item as unknown as { readonly plan?: unknown }).plan;
  if (plan === null || typeof plan !== "object") {
    return null;
  }
  const candidate = (plan as Record<string, unknown>)[
    "destructiveImplications"
  ];
  if (candidate === null || typeof candidate !== "object") {
    return null;
  }
  const record = candidate as Record<string, unknown>;
  if (
    typeof record["overwriteRequired"] !== "boolean" ||
    typeof record["sourceCleanupRequired"] !== "boolean" ||
    typeof record["statement"] !== "string"
  ) {
    return null;
  }
  return {
    overwriteRequired: record["overwriteRequired"],
    sourceCleanupRequired: record["sourceCleanupRequired"],
    statement: record["statement"],
  };
}

function ItemFindings({ item }: { readonly item: ManualPreviewItemModel }) {
  const implications = destructiveImplications(item);
  return (
    <dl>
      <dt>Status</dt>
      <dd>
        {displayEnum(item.status)}
        {item.current ? "" : " (historical/blocked)"}
      </dd>
      <dt>Source</dt>
      <dd>
        {safeValue(item.sourceStorageId)}:{safeValue(item.sourcePath)}
      </dd>
      <dt>RecognitionType</dt>
      <dd>
        {safeValue(
          (
            item as unknown as {
              readonly plan?: { readonly recognitionType?: string | null };
            }
          ).plan?.recognitionType ?? null,
        )}
      </dd>
      <dt>Metadata identity</dt>
      <dd>
        {safeValue(item.provider)} / {safeValue(item.providerId)} ·{" "}
        {safeValue(item.title)}
      </dd>
      <dt>Operation</dt>
      <dd>
        {safeValue(
          (
            item as unknown as {
              readonly plan?: { readonly operation?: string | null };
            }
          ).plan?.operation ?? null,
        )}
      </dd>
      <dt>Proposed destination</dt>
      <dd>
        {safeValue(item.targetStorageId)}:
        {safeValue(item.targetPath ?? item.destination?.relativePath ?? null)}
      </dd>
      <dt>Capabilities</dt>
      <dd>
        {item.capabilities === null
          ? "—"
          : `${safeValue(item.capabilities.verdict)} · missing: ${
              item.capabilities.missing.length > 0
                ? item.capabilities.missing.join(", ")
                : "none"
            }`}
      </dd>
      <dt>Attachments</dt>
      <dd>
        {item.attachments.length === 0
          ? "none"
          : item.attachments
              .map(
                (value) =>
                  `${value.type ?? "attachment"}${
                    value.language ? ` (${value.language})` : ""
                  }`,
              )
              .join(", ")}
      </dd>
      <dt>Conflicts</dt>
      <dd>
        {item.conflicts.length === 0
          ? "none"
          : item.conflicts.map((value) => value.type ?? "conflict").join(", ")}
      </dd>
      <dt>Warnings</dt>
      <dd>{item.warnings.length === 0 ? "none" : item.warnings.join("; ")}</dd>
      <dt>Destructive implications</dt>
      <dd>{implications === null ? "—" : implications.statement}</dd>
    </dl>
  );
}

export function OrganizePreviewPage() {
  const { previewId } = useParams({
    from: "/operations/organize/preview/$previewId",
  });
  const token = useAuthToken();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const previewQuery = useQuery(organizePreviewQueryOptions(token, previewId));

  const [selected, setSelected] = useState<readonly string[] | null>(null);
  const [allowOverwrite, setAllowOverwrite] = useState(false);
  const [allowSourceCleanup, setAllowSourceCleanup] = useState(false);
  const [result, setResult] = useState<{
    readonly ok: boolean;
    readonly message: string;
  } | null>(null);

  const executeMutation = useMutation({
    mutationFn: (options: {
      readonly itemIds: readonly string[];
      readonly intentVersion: number;
    }) =>
      executeOrganizePreview(token, {
        previewId,
        itemIds: options.itemIds,
        expectedIntentVersion: options.intentVersion,
        allowOverwrite,
        allowSourceCleanup,
      }),
    retry: false,
    onMutate: () => setResult(null),
    onSuccess: (value) => {
      if (value.ok) {
        // A repeated submission resolves to the same durable execution; the
        // page always continues to the durable identity it received.
        void queryClient.invalidateQueries({
          queryKey: [organizeExecutionListQueryKey],
        });
        void navigate({
          to: "/operations/organize/execution/$executionId",
          params: { executionId: value.model.executionId },
        });
        return;
      }
      setResult({
        ok: false,
        message:
          value.status === 0
            ? "The admission request could not reach the API. Nothing was submitted; reload before retrying."
            : `The exact execution was refused (${value.code}). No Storage mutation happened. Reload the Preview and request a fresh one when the cause is repaired — nothing is retried automatically.`,
      });
    },
  });

  const preview: OrganizePreviewModel | undefined = previewQuery.data?.ok
    ? previewQuery.data.model
    : undefined;

  const executableIds = useMemo(
    () => (preview ? [...preview.executionCandidateItemIds] : []),
    [preview],
  );
  const activeSelection = selected ?? executableIds;
  const requiresOverwrite = useMemo(
    () =>
      (preview?.items ?? []).some(
        (item) => destructiveImplications(item)?.overwriteRequired === true,
      ),
    [preview],
  );
  const requiresCleanup = useMemo(
    () =>
      (preview?.items ?? []).some(
        (item) => destructiveImplications(item)?.sourceCleanupRequired === true,
      ),
    [preview],
  );

  return (
    <AuthorizedReadBoundary
      query={previewQuery}
      unavailableTitle="Preview unavailable"
    >
      {({ data, isFetching, refresh }) => {
        if (data === undefined) {
          return (
            <StatusBanner variant="info" title="Loading exact Preview">
              <p>Reading the durable zero-mutation Preview.</p>
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
        const model = data.model;
        const execute = model.executeAction;
        const destructiveConfirmed =
          (!requiresOverwrite || allowOverwrite) &&
          (!requiresCleanup || allowSourceCleanup);
        return (
          <div className="mf-dashboard">
            <header className="mf-dashboard-head">
              <div>
                <h2>Exact manual organize Preview</h2>
                <p className="mf-dashboard-meta">
                  Preview {model.previewId} · {displayEnum(model.status)} ·{" "}
                  {model.current ? "current" : "historical"} · zero Storage
                  mutation
                </p>
              </div>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
            </header>
            <StatusBanner variant="info" title="Zero Storage mutation">
              <p>
                Running and reading this Preview changed nothing in Storage. It
                is analysis evidence, not execution authority.
              </p>
            </StatusBanner>
            {model.nextAction && (
              <p className="mf-dashboard-meta">{model.nextAction}</p>
            )}
            <section className="mf-count-section">
              <h3>Worker readiness</h3>
              <p className="mf-dashboard-meta">
                {model.worker.ready
                  ? "A resident Processing Worker can claim admitted exact work."
                  : `Not ready: ${model.worker.durableState ?? model.worker.condition ?? "unknown"}`}
              </p>
              {model.worker.nextAction && (
                <p className="mf-dashboard-meta">{model.worker.nextAction}</p>
              )}
            </section>
            {model.items.map((item) => {
              const isExecutable = executableIds.includes(item.itemId);
              return (
                <section className="mf-count-section" key={item.itemId}>
                  <h3>
                    {item.sourceFilename ?? item.itemId}{" "}
                    <span className="mf-status-badge">
                      {isExecutable ? "executable" : "not executable"}
                    </span>
                  </h3>
                  <label>
                    <input
                      type="checkbox"
                      aria-label={`Select ${item.itemId}`}
                      checked={activeSelection.includes(item.itemId)}
                      disabled={!isExecutable}
                      onChange={(event) =>
                        setSelected(
                          event.target.checked
                            ? [...activeSelection, item.itemId]
                            : activeSelection.filter(
                                (value) => value !== item.itemId,
                              ),
                        )
                      }
                    />{" "}
                    Include this exact item
                  </label>
                  <ItemFindings item={item} />
                  {destructiveImplications(item) !== null && (
                    <p className="mf-dashboard-meta">
                      {destructiveImplications(item)?.statement}
                    </p>
                  )}
                  {item.failure !== null && (
                    <StatusBanner variant="error" title="Item finding">
                      <p>{item.failure.message}</p>
                      <p className="mf-dashboard-meta">
                        {item.failure.nextAction}
                      </p>
                    </StatusBanner>
                  )}
                </section>
              );
            })}
            <section className="mf-count-section">
              <h3>Execute</h3>
              <p className="mf-dashboard-meta">
                {execute.available
                  ? "One confirmation admits exactly the selected items after the server creates and consumes short-lived one-shot authority."
                  : `Unavailable: ${execute.reason ?? "the backend does not advertise it"}`}
              </p>
              {execute.durableOutcome && (
                <p className="mf-dashboard-meta">{execute.durableOutcome}</p>
              )}
              {requiresOverwrite && (
                <label>
                  <input
                    type="checkbox"
                    checked={allowOverwrite}
                    onChange={(event) =>
                      setAllowOverwrite(event.target.checked)
                    }
                  />{" "}
                  I confirm the reviewed plan may replace an existing
                  destination file
                </label>
              )}
              {requiresCleanup && (
                <label>
                  <input
                    type="checkbox"
                    checked={allowSourceCleanup}
                    onChange={(event) =>
                      setAllowSourceCleanup(event.target.checked)
                    }
                  />{" "}
                  I confirm the reviewed plan may delete emptied source
                  directories
                </label>
              )}
              <div className="mf-actions">
                <Button
                  type="button"
                  disabled={
                    !execute.available ||
                    executeMutation.isPending ||
                    activeSelection.length === 0 ||
                    !destructiveConfirmed
                  }
                  onClick={() =>
                    executeMutation.mutate({
                      itemIds: activeSelection,
                      intentVersion: model.intentVersion ?? 0,
                    })
                  }
                >
                  {executeMutation.isPending
                    ? "Admitting exact work…"
                    : "Execute selected exact items"}
                </Button>
                {model.intentId !== null && (
                  <Link
                    className="mf-button mf-button-secondary"
                    to="/operations/organize/intent/$intentId"
                    params={{ intentId: model.intentId }}
                  >
                    Back to the durable intent
                  </Link>
                )}
              </div>
              {result !== null && (
                <StatusBanner variant="error" title="Execution not admitted">
                  <p>{result.message}</p>
                </StatusBanner>
              )}
            </section>
          </div>
        );
      }}
    </AuthorizedReadBoundary>
  );
}

export type { ManualPreviewModel };
