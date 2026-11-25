/**
 * Slice53 RO-1/RO-2/RO-3 — the Files → preparation card → task-center
 * handoff journey (plan: V2-OPS-018/019 TARGET, journey = Manual organize).
 *
 * Every test enters through the real Files page (`批量整理` on an admitted
 * selection) and drives the real route tree, query/mutation boundary and
 * normalizers against the exact contract-captured documents from
 * `manual-operations.json`, retargeted to this journey's ids. No route or
 * component entry is invented: the dialog only exists where an operator can
 * really open it, and no `page.route`-style interception exists — the stubbed
 * fetch is the backend boundary itself.
 *
 * Covered behaviour:
 * - ten files each need one candidate choice + one explicit save/analysis,
 *   with zero Execute before the single `确认整理 10 项` (AC-11);
 * - paging keeps unsaved drafts and never saves; closing with a draft pins
 *   the explicit discard choice (AC-9 / AC-2);
 * - a saved choice whose analysis failed reports the split honestly and only
 *   retries the analysis (AC-4);
 * - a newer summary keeps the visible page on the same durable itemId (AC-5);
 * - an unknown Execute response is never retried: only the bounded admission
 *   read proves the outcome, then the exact task handoff happens (AC-7);
 * - the original unknown submission keeps its exact preview/subset/version/
 *   effect identity while a sibling re-analysis publishes a newer summary,
 *   and reconciles only that original request (A53-01);
 * - an unready or already-admitted sibling never enters the fresh
 *   confirmation, and browsing is zero-execute (AC-6 / AC-10);
 * - Escape with nothing pending closes the card and returns focus to the
 *   invoking control (AC-9).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;
const TOKEN = "dialog-token";
const DISCOVERY_ID = "prep-1";
const INTENT_ID = "intent-1";
const PREVIEW_ID = "preview-1";
const FILE_COUNT = 10;

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function clone(name: string): Json {
  return JSON.parse(JSON.stringify(documents[name])) as Json;
}

const filename = (index: number) =>
  `Movie.${String(index + 1).padStart(2, "0")}.mkv`;

/** One stateful backend double for this journey's bounded surface. */
function makeBackend() {
  const state = {
    previewId: PREVIEW_ID as string,
    // Set by a test that wants the next analysis to link a different plan.
    flipPreviewOnAnalyze: false as boolean,
    // Whatever the operator saved last: the fake persists it like the real
    // choice authority, so the next page reads back the saved identity.
    savedMetadata: new Map<string, Json | null>(),
    // One ended flow projects its original saved plan as read-only history.
    endedFlow: false as boolean,
    endedFlowKeepsPreview: false as boolean,
    // The exact durable primary-bound refusal a truncated preparation records.
    primaryLimit: false as boolean,
    // Leading primary-limit reads whose linked Task has not settled yet.  The
    // walk's refusal and the Task's terminal status are separate commits.
    primaryLimitSettlementReads: 0 as number,
    // The number of leading discovery reads that still report an unchanged
    // waiting state before the plan links.
    waitingReads: 0 as number,
    // Leading reads of a just-admitted, still-queued preparation whose walk
    // has not started.
    queuedReads: 0 as number,
    // Leading reads that report the saved request while no Worker advertises
    // the discovery capability; a later read proves automatic recovery.
    workerUnavailableReads: 0 as number,
    // The real Worker publishes the completed walk before it freezes and enters
    // analysis.  These two counts stage exactly that gap: an unfrozen completed
    // walk, then the frozen intent whose analysis is still linking the plan.
    walkOnlyReads: 0 as number,
    frozenOnlyReads: 0 as number,
    // A live analysis request whose durable stage is analysing before the plan
    // links, a bounded rejection of the preparation's own action, and the
    // advertised human-waiting recovery state that really accepts a re-analysis.
    analyzingReads: 0 as number,
    analyzeShowsAnalyzing: false as boolean,
    rejectAnalysisOnce: false as boolean,
    manualAnalysisRecovery: false as boolean,
    // The linked preparation still advertises its exact zero-mutation
    // re-analysis at the human-waiting boundary.
    reanalysisAvailable: false as boolean,
    discoveryReads: 0 as number,
    // A real no-candidate problem on the first file, plus the durable
    // metadata-correction decision the same TaskItem exposes after analysis.
    metadataProblem: false as boolean,
    metadataProblemResolved: false as boolean,
    // A real metadata-review problem: two tied legal candidates on item-1.
    metadataCandidateProblem: false as boolean,
    metadataCandidateResolved: false as boolean,
    // A metadata Provider technical failure: the backend published the stage
    // error and no candidate/problem TaskItem, so the Files body must not
    // instruct the operator to pick a candidate.
    metadataProviderFailure: false as boolean,
    // A real destination conflict on item-1 whose exact TaskItem can be
    // skipped. Resolved means the durable read reports `skipped` with no
    // analysis authority, exactly like the backend's conflict decision.
    conflictProblem: false as boolean,
    conflictResolved: false as boolean,
    // The exact Task's durable settled items the Files overview reads back
    // through the bounded run-items endpoint, whether or not a newer plan
    // still publishes that file.
    durableSettledItems: [] as {
      readonly itemId: string;
      readonly status: "skipped" | "ignored";
      readonly sourcePath: string;
      readonly taskId: string;
    }[],
    // A user-ignored review whose durable checkpoint is the terminal result.
    ignoredProblem: false as boolean,
    // Hold the bounded settled-record reads to prove a late read never moves
    // the operator or discards the current file's draft.
    holdSettledReads: false as boolean,
    // The same Task's settled-record read is temporarily unavailable.
    failSettledRecords: false as boolean,
    // The backend saved the skip but its response never reaches the browser.
    loseConflictDecisionResponse: false as boolean,
    failMetadataDecision: false as boolean,
    failMetadataContinue: false as boolean,
    recoveryAnalysisQueued: false as boolean,
    // B-PATCH-01: the next year-conditioned search is refused by the real
    // API's invalid_year envelope before any Provider call.
    rejectMetadataSearchYear: false as boolean,
    // The exact paths the Files admission carried: the summary then plans
    // exactly those files, so a two-file journey is a two-item plan.
    selectedPaths: [] as string[],
    // A refused sibling is not planned; the preview carries only the admitted
    // paths even though the Files admission carried both.
    previewItemPaths: [] as string[],
    // The exact admitted scopes the preparation read publishes, so a mixed
    // selection is summarized by kind and remains expandable.
    scopeSelections: [] as { kind: "file" | "directory"; path: string }[],
    refusedSelections: [] as {
      readonly kind: "file" | "directory";
      readonly path: string;
      readonly code: string;
      readonly reason: string;
      readonly message: string;
      readonly nextAction: string;
      readonly existingWorkId: string | null;
      readonly existingWorkKind: string | null;
    }[],
    // A first plan with blocked items is not current even though no newer
    // analysis exists; the card must not call it superseded without evidence.
    previewCurrent: true as boolean,
    previewStaleTail: 0 as number,
    // A different durable latest plan is the only proof of supersession.
    latestPlanPreviewId: null as string | null,
    // The exact read-back a Files per-file analysis may publish for item-1:
    // a resolved ready plan, an explicit skip, a new conflict/next problem,
    // or the same problem still needing correction.
    secondPlanKind: null as
      | null
      | "ready"
      | "skip"
      | "conflict"
      | "metadata"
      | "classification"
      | "sibling",
    secondPlanProblemTaskItemId: "problem-item-1" as string,
    previewAttachmentCount: 0 as number,
    // The A53-01 journey: an overwrite the operator must authorize on every
    // exact summary, and bounded admission-read failures.
    requireOverwrite: false as boolean,
    failAdmissionReads: 0 as number,
    // A completed preparation whose only directory content was excluded as a
    // non-primary extension.  No plan is generated for this walk.
    zeroPrimary: false as boolean,
    // The same completed zero-primary preparation read after its Worker
    // stopped or its heartbeat expired; the durable result still governs.
    zeroPrimaryWorkerUnavailable: false as boolean,
    // The first linked-summary read fails once; the same preparation context
    // keeps the retry entry for that exact summary.
    failFirstPreviewRead: false as boolean,
    // Previews whose Execute the backend durably admitted. A lost response
    // changes nothing about this record.
    admittedPreviewIds: [] as string[],
    // The plan's library ids/Storage no longer agree with the live library
    // reads, so the batch row must keep the exact verified Storage paths.
    mismatchedLibraries: false as boolean,
    // The plan's MediaLibrary-relative path legally starts with the root's own
    // name (`Movies` root plus a `Movies/Anime` classification path), exactly
    // like the real readability fixture.
    libraryPrefixedTargets: false as boolean,
    // The plan's exact Storage path is not under the reviewed library root, so
    // the library name must not replace the exact Storage identity.
    foreignTargetRoot: false as boolean,
  };
  const calls = {
    discoveryPosts: [] as Json[],
    choicePosts: [] as Json[],
    analyzePosts: [] as Json[],
    executePosts: [] as Json[],
    executePreviewIds: [] as string[],
    admissionReads: 0,
    admissionRequests: [] as {
      readonly previewId: string;
      readonly params: Record<string, string>;
    }[],
    metadataSearchPosts: [] as Json[],
    recoveryDecisionPosts: [] as Json[],
    recoveryContinuePosts: [] as Json[],
    settledRecordsReads: 0,
  };
  /** A deliberately stuck Execute response the test releases by hand. */
  let releasedExecute: ((response: Response) => void) | null = null;
  let holdExecute = false;
  const heldExecuteResponses: Response[] = [];
  const settledReadReleases: (() => void)[] = [];

  /**
   * The exact item indices this admission plans: the file rows the real
   * Files discovery request carried. A selection without a recognised file
   * path keeps the full ten-file default of this journey.
   */
  const previewItemIndices = (): number[] => {
    const indices: number[] = [];
    const paths =
      state.previewItemPaths.length > 0
        ? state.previewItemPaths
        : state.selectedPaths;
    for (const path of paths) {
      const match = /^Movies\/Movie\.(\d{2})\.mkv$/.exec(path);
      if (match !== null) indices.push(Number(match[1]) - 1);
    }
    indices.sort((left, right) => left - right);
    return indices.length > 0
      ? indices
      : Array.from({ length: FILE_COUNT }, (_, index) => index);
  };

  const discoveryDocument = (): Json => {
    const discoveryScopes =
      state.scopeSelections.length > 0
        ? state.scopeSelections
        : [{ kind: "directory" as const, path: "Movies" }];
    const value: Json = {
      journey: "discovery",
      discoveryId: DISCOVERY_ID,
      resourceLibraryId: "library",
      storageId: "source",
      configurationSnapshotId: "active-1",
      status: state.primaryLimit ? "partial_success" : "completed",
      version: 5,
      createdAt: "2026-01-01T00:00:00+00:00",
      updatedAt: "2026-01-01T00:00:00+00:00",
      selection: {
        scopeCount: discoveryScopes.length,
        scopes: discoveryScopes,
        existing: [],
        refused: state.refusedSelections.map((refused) => ({
          ...refused,
          organizing: false,
          prunedAncestor: null,
        })),
      },
      budgets: {},
      progress: {
        phase: "prepared",
        visitedEntries: previewItemIndices().length + 1,
        visitedDirectories: 1,
        pageFetches: 1,
        primarySources: previewItemIndices().length,
        excludedEntries: 0,
        unstableEntries: 0,
        errorEntries: 0,
        activeSeconds: 0.1,
        incomplete: state.primaryLimit,
        incompleteReason: state.primaryLimit ? "primary_limit" : null,
        refusalReasons: state.primaryLimit ? ["primary_limit"] : [],
        materialRefusal: state.primaryLimit ? "primary_limit" : null,
        findings: [],
        reasons: [],
        message: "the exact zero-mutation plan summary is ready",
      },
      primarySourceCount: previewItemIndices().length,
      organizeTaskId: state.endedFlow ? null : "organize-task-1",
      organizeFlow: {
        taskId: "organize-task-1",
        status: state.endedFlow
          ? state.primaryLimit
            ? "failed"
            : "completed"
          : "running",
        continuable: !state.endedFlow,
      },
      admissionRequestId: null,
      autoPrepare: !state.primaryLimit,
      prepared: !state.primaryLimit,
      previewId:
        state.primaryLimit || (state.endedFlow && !state.endedFlowKeepsPreview)
          ? null
          : state.previewId,
      intentId: state.primaryLimit ? null : INTENT_ID,
      frozen: !state.primaryLimit,
      freezeRequestedAt: null,
      pauseRequested: false,
      cancelRequested: false,
      nextObservationAt: null,
      worker: {
        ready: true,
        condition: "ready",
        durableState: "ready",
        nextAction: "claim",
      },
      actions: {
        cancel: discoveryAction(),
        finalize: discoveryAction(),
        prepare: state.reanalysisAvailable
          ? {
              ...discoveryAction(),
              available: true,
              path: `/api/operations/organize/discoveries/${DISCOVERY_ID}/analyze`,
            }
          : discoveryAction(),
      },
      sources: [],
      nextAction: "open the linked exact plan summary",
      failure: null,
      sideEffects: "none",
      zeroMutation: true,
      execution: "not_available_from_discovery",
    };
    if (state.zeroPrimary) {
      value["status"] = "completed";
      value["previewId"] = null;
      value["prepared"] = false;
      value["intentId"] = null;
      value["frozen"] = false;
      value["primarySourceCount"] = 0;
      const progress = value["progress"] as Json;
      progress["phase"] = "completed";
      progress["message"] =
        "the bounded walk completed with no primary media source";
      progress["primarySources"] = 0;
      progress["visitedEntries"] = 1;
      progress["excludedEntries"] = 1;
      progress["reasons"] = [
        {
          reason: "unsupported_extension",
          count: 1,
          examplePath: "Gamma-Directory/child.txt",
        },
      ];
      value["nextAction"] =
        "narrow the selected scope or correct the configured filters, then retry";
      if (state.zeroPrimaryWorkerUnavailable) {
        value["worker"] = {
          ready: false,
          condition: "no_worker",
          durableState:
            "all registered processing workers have stale heartbeats",
          nextAction: "start the resident Processing Worker",
        };
      }
    }
    return value;
  };

  function discoveryAction() {
    return {
      available: false,
      method: "POST",
      path: null,
      requiresVersion: true,
      sideEffects: "none",
      refusal: null,
      pendingReason: null,
      reason: null,
      nextAction: null,
    };
  }

  const intentDocument = (): Json => {
    const value = clone("organizeIntentWithPlan");
    value["intentId"] = INTENT_ID;
    value["previewRequired"] = true;
    const latestPlan = value["latestPlan"] as Json | null;
    if (latestPlan !== null) {
      // During the staged walk→freeze→analysis gap the intent is already
      // durable, but it has not published the linked plan yet.
      if (state.discoveryReads <= state.walkOnlyReads + state.frozenOnlyReads) {
        value["latestPlan"] = null;
      } else {
        latestPlan["previewId"] = state.latestPlanPreviewId ?? state.previewId;
      }
    }
    value["actions"] = {
      choice: {
        available: true,
        method: "POST",
        path: `/api/operations/organize/intents/${INTENT_ID}/items/{itemId}/choice`,
        requiresVersion: false,
        sideEffects: "none",
        refusal: null,
        pendingReason: null,
        reason: null,
        nextAction: null,
      },
      execute: {
        available: false,
        method: null,
        path: null,
        requiresVersion: false,
        sideEffects: "none",
        refusal: "execution is only offered from a current exact plan summary",
        pendingReason: null,
        reason: "execution is only offered from a current exact plan summary",
        nextAction: null,
      },
    };
    const template = (value["items"] as Json[])[0]!;
    value["items"] = Array.from({ length: FILE_COUNT }, (_, index) => {
      const item = JSON.parse(JSON.stringify(template)) as Json;
      item["itemId"] = `item-${index + 1}`;
      item["position"] = index;
      item["version"] = 1;
      item["status"] = "ready";
      item["failure"] = null;
      item["nextAction"] = "confirm a metadata identity";
      item["source"] = {
        ...(item["source"] as Json),
        filename: filename(index),
        path: `Movies/${filename(index)}`,
        storageId: "source",
        resourceLibraryId: "library",
        fileId: null,
        occurrenceState: "verified",
        scanStatus: null,
        extension: "mkv",
        size: 1024,
      };
      item["choice"] = {
        recognitionTypeId: "A",
        namingPolicyId: "A",
        classificationPolicyId: "A",
        organizePolicyId: "A",
        metadata: state.savedMetadata.get(`item-${index + 1}`) ?? null,
      };
      item["allowedMetadataIdentities"] = [
        {
          provider: "tmdb",
          providerId: String(129 + index),
          mediaType: "movie",
          title: filename(index).replace(".mkv", ""),
          year: 2001,
        },
        {
          provider: "tmdb",
          providerId: String(900 + index),
          mediaType: "movie",
          title: "Alternative",
          year: 2002,
        },
      ];
      return item;
    });
    return value;
  };

  const previewDocument = (previewId: string, reversed: boolean): Json => {
    const value = clone("organizePreviewDetail");
    value["previewId"] = previewId;
    value["intentId"] = INTENT_ID;
    value["current"] = true;
    value["truncated"] = false;
    value["status"] = "previewed";
    value["intentVersion"] = 7;
    value["organizeFlow"] = {
      taskId: "organize-task-1",
      status: "running",
      continuable: true,
    };
    const template = (value["items"] as Json[])[0]!;
    const order = previewItemIndices();
    if (reversed) order.reverse();
    value["items"] = order.map((index, position) => {
      const item = JSON.parse(JSON.stringify(template)) as Json;
      item["itemId"] = `item-${index + 1}`;
      item["previewItemId"] = `pitem-${previewId}-${index + 1}`;
      item["position"] = position;
      item["current"] = true;
      item["truncated"] = false;
      item["stage"] = "ready";
      item["status"] = "previewed";
      item["executionState"] = "ready_for_explicit_authorization";
      item["failure"] = null;
      item["nextAction"] = "confirm the exact plan";
      item["sideEffects"] = "none";
      item["source"] = {
        ...(item["source"] as Json),
        filename: filename(index),
        path: `Movies/${filename(index)}`,
        storageId: "source",
        resourceLibraryId: "library",
        extension: "mkv",
        size: 1024,
      };
      const plan = item["plan"] as Json;
      // Derive the visible destination from the file so ten distinct targets
      // stay readable without hand-writing ten plans.
      const destination = (plan["destination"] ?? null) as Json | null;
      if (destination !== null) {
        // The real Preview plan carries the MediaLibrary-relative path plus the
        // exact Storage path that the library root composes. The fixture
        // library root is `Movies`, so the only legal way its own name repeats
        // at the start of the library-relative path is a `Movies/Anime`
        // classification result.
        const libraryRelative = state.libraryPrefixedTargets
          ? `Movies/Anime/${filename(index)}`
          : filename(index);
        destination["filename"] = filename(index);
        destination["relativePath"] = libraryRelative;
        destination["storageRelativePath"] = state.foreignTargetRoot
          ? `Archive/${filename(index)}`
          : `Movies/${libraryRelative}`;
      }
      if (state.requireOverwrite) {
        const implications = plan["destructiveImplications"] as Json;
        implications["overwriteRequired"] = true;
      }
      if (state.previewAttachmentCount > 0) {
        plan["attachments"] = Array.from(
          { length: state.previewAttachmentCount },
          (_, attachmentIndex) => ({
            type: "subtitle",
            source: {
              storageId: "source",
              path: `Movies/Movie.01.${attachmentIndex + 1}.srt`,
            },
            destination: {
              storageId: "target",
              path: `Movies/Movie.01.${attachmentIndex + 1}.srt`,
            },
            operation: "MOVE",
            suffix: "srt",
            language: "zh",
            blockedReason:
              attachmentIndex === 0 ? null : "target already exists",
            nextAction:
              attachmentIndex === 0 ? null : "rename the attachment target",
          }),
        );
      }
      return item;
    });
    value["executionCandidateItemIds"] = order.map(
      (index) => `item-${index + 1}`,
    );
    value["selection"] = {
      selectedItemIds: order.map((index) => `item-${index + 1}`),
      unselectedItemIds: [],
    };
    if (previewId === "preview-2" && state.secondPlanKind !== null) {
      const item = (value["items"] as Json[]).find(
        (row) => row["itemId"] === "item-1",
      );
      const plan = item?.["plan"] as Json | undefined;
      if (item !== undefined && plan !== undefined) {
        if (state.secondPlanKind === "sibling") {
          const sibling = (value["items"] as Json[]).find(
            (row) => row["itemId"] === "item-2",
          );
          const siblingPlan = sibling?.["plan"] as Json | undefined;
          if (siblingPlan !== undefined) {
            const identity = siblingPlan["mediaIdentity"] as Json;
            identity["title"] = "Sibling Resolved";
            const destination = siblingPlan["destination"] as Json;
            destination["storageRelativePath"] = "Movies/Sibling Resolved.mkv";
            destination["relativePath"] = "Movies/Sibling Resolved.mkv";
          }
        } else if (state.secondPlanKind === "ready") {
          const identity = plan["mediaIdentity"] as Json;
          identity["title"] = "Resolved Movie";
          identity["providerId"] = "777";
          const destination = plan["destination"] as Json;
          destination["storageRelativePath"] = "Movies/Resolved Movie.mkv";
          destination["relativePath"] = "Movies/Resolved Movie.mkv";
          destination["filename"] = "Resolved Movie.mkv";
        } else if (state.secondPlanKind === "skip") {
          plan["operation"] = "SKIP";
          plan["planStatus"] = "noop";
        } else if (state.secondPlanKind === "conflict") {
          item["status"] = "blocked";
          item["executionState"] = "not_available_in_this_task";
          item["stage"] = "conflict";
          item["failure"] = null;
          plan["executionState"] = "not_available_in_this_task";
          plan["conflicts"] = [
            {
              type: "DESTINATION_EXISTS",
              source: `source:Movies/${filename(0)}`,
              destination: "target:Movies/Resolved Movie.mkv",
              details: "the destination already exists",
            },
          ];
        } else {
          // metadata / classification: the same item publishes a fresh
          // problem TaskItem of that family.
          item["status"] = "blocked";
          item["executionState"] = "not_available_in_this_task";
          item["stage"] = state.secondPlanKind;
          item["failure"] = {
            category: "business_problem",
            message:
              state.secondPlanKind === "classification"
                ? "classification could not select a destination"
                : "metadata identity still needs the operator",
            nextAction: "save the current file decision and re-analyze",
          };
          plan["problemTaskItemId"] = state.secondPlanProblemTaskItemId;
          const analysis = plan["analysis"] as Json;
          if (state.secondPlanKind === "classification") {
            const classification = analysis["classification"] as Json;
            classification["status"] = "unclassified";
            classification["available"] = false;
          } else {
            const metadata = analysis["metadata"] as Json;
            metadata["status"] = "need_confirm";
            metadata["available"] = true;
          }
        }
        if (
          state.secondPlanKind !== "ready" &&
          state.secondPlanKind !== "skip" &&
          state.secondPlanKind !== "sibling"
        ) {
          value["executionCandidateItemIds"] = (
            (value["executionCandidateItemIds"] as string[]) ?? []
          ).filter((itemId) => itemId !== "item-1");
          const selection = value["selection"] as Json;
          selection["selectedItemIds"] = (
            selection["selectedItemIds"] as string[]
          ).filter((itemId) => itemId !== "item-1");
          selection["unselectedItemIds"] = ["item-1"];
        }
      }
    }
    if (!state.previewCurrent) {
      value["current"] = false;
      value["status"] = "stale";
      value["executionState"] = "not_available_in_this_task";
      const items = value["items"] as Json[];
      const staleItems = items.slice(
        -Math.max(1, Math.min(state.previewStaleTail, items.length)),
      );
      const staleIds = new Set(staleItems.map((item) => item["itemId"]));
      for (const item of staleItems) {
        item["current"] = false;
        item["status"] = "stale";
        item["executionState"] = "not_available_in_this_task";
        item["nextAction"] = "request a fresh Preview for this item";
        item["failure"] = {
          category: "workflow_failure",
          message:
            "scheduled organization failed at a bounded workflow boundary",
          durableState:
            "this is a zero-mutation preparation finding; no execution TaskItem or Result was created",
          nextAction: "request a fresh Preview for this item",
          retrySafe: false,
          sideEffects: "none",
        };
      }
      value["executionCandidateItemIds"] = items
        .filter((item) => !staleIds.has(item["itemId"]))
        .map((item) => item["itemId"]);
      value["selection"] = {
        selectedItemIds: value["executionCandidateItemIds"],
        unselectedItemIds: [...staleIds],
      };
      const execute = (value["actions"] as Json)["execute"] as Json;
      execute["available"] = false;
      execute["reason"] =
        "this fixed plan is historical evidence and can no longer be executed";
      execute["nextAction"] =
        "request a fresh Preview after repairing the blocked items";
    }
    if (
      (state.metadataProblem && !state.metadataProblemResolved) ||
      (state.metadataCandidateProblem && !state.metadataCandidateResolved)
    ) {
      const problem = (value["items"] as Json[]).find(
        (item) => item["itemId"] === "item-1",
      );
      if (problem !== undefined) {
        problem["status"] = "blocked";
        problem["executionState"] = "not_available_in_this_task";
        problem["stage"] = "metadata";
        problem["failure"] = {
          category: "metadata_failure",
          message:
            "metadata identity was not found under the pinned MetadataPolicy",
          nextAction:
            "correct the metadata search title/year or choose a Provider identity",
        };
        const plan = problem["plan"] as Json;
        plan["problemTaskItemId"] = "problem-item-1";
        const analysis = plan["analysis"] as Json;
        const metadata = analysis["metadata"] as Json;
        metadata["available"] = false;
        metadata["status"] = "not_found";
        const match = metadata["match"] as Json;
        match["status"] = "not_found";
        match["candidateCount"] = 0;
        match["candidates"] = [];
      }
      value["executionCandidateItemIds"] = (
        value["executionCandidateItemIds"] as string[]
      ).filter((itemId) => itemId !== "item-1");
      value["selection"] = {
        selectedItemIds: (
          (value["selection"] as Json)["selectedItemIds"] as string[]
        ).filter((itemId) => itemId !== "item-1"),
        unselectedItemIds: ["item-1"],
      };
    }
    if (state.conflictProblem) {
      const problem = (value["items"] as Json[]).find(
        (item) => item["itemId"] === "item-1",
      );
      if (problem !== undefined) {
        problem["status"] = "blocked";
        problem["executionState"] = "not_available_in_this_task";
        problem["stage"] = "conflict";
        problem["failure"] = null;
        const plan = problem["plan"] as Json;
        plan["problemTaskItemId"] = "problem-item-1";
        plan["executionState"] = "not_available_in_this_task";
        plan["conflicts"] = [
          {
            type: "DESTINATION_EXISTS",
            source: `source:Movies/${filename(0)}`,
            destination: "target:Movies/Movie.01 (2001)/Movie.01.mkv",
            details: "the destination already exists",
          },
        ];
      }
      value["executionCandidateItemIds"] = (
        (value["executionCandidateItemIds"] as string[]) ?? []
      ).filter((itemId) => itemId !== "item-1");
      const selection = value["selection"] as Json;
      selection["selectedItemIds"] = (
        selection["selectedItemIds"] as string[]
      ).filter((itemId) => itemId !== "item-1");
      selection["unselectedItemIds"] = ["item-1"];
    }
    if (state.metadataProviderFailure) {
      const problem = (value["items"] as Json[]).find(
        (item) => item["itemId"] === "item-1",
      );
      if (problem !== undefined) {
        problem["status"] = "unavailable";
        problem["executionState"] = "not_available_in_this_task";
        problem["stage"] = "metadata";
        problem["nextAction"] =
          "inspect the configured Metadata Provider, then explicitly rerun Preview";
        problem["failure"] = {
          category: "storage_failure",
          message:
            "Storage failure: the configured Storage operation did not complete",
          durableState:
            "this is a zero-mutation preparation finding; no execution TaskItem or Result was created",
          nextAction:
            "inspect the configured Metadata Provider, then explicitly rerun Preview",
          retrySafe: true,
          sideEffects: "none",
        };
        const plan = problem["plan"] as Json;
        plan["problemTaskItemId"] = null;
        plan["operation"] = null;
        plan["planStatus"] = null;
        plan["destination"] = null;
        plan["attachments"] = [];
        plan["conflicts"] = [];
        plan["destructiveImplications"] = null;
        plan["mediaIdentity"] = null;
        plan["capabilities"] = {
          verdict: "not_determined",
          required: [],
          declared: [],
          missing: [],
        };
        const analysis = plan["analysis"] as Json;
        analysis["metadata"] = {
          available: false,
          status: "provider_error",
          query: "Movie.01",
          identity: null,
          match: null,
        };
      }
      value["executionCandidateItemIds"] = (
        (value["executionCandidateItemIds"] as string[]) ?? []
      ).filter((itemId) => itemId !== "item-1");
      const selection = value["selection"] as Json;
      selection["selectedItemIds"] = (
        selection["selectedItemIds"] as string[]
      ).filter((itemId) => itemId !== "item-1");
      selection["unselectedItemIds"] = ["item-1"];
      if ((value["executionCandidateItemIds"] as string[]).length === 0) {
        // The real backend only advertises Execute for a current plan with an
        // executable candidate; an all-unavailable plan carries a refusal.
        const execute = (value["actions"] as Json)["execute"] as Json;
        execute["available"] = false;
        execute["reason"] = "no current executable candidate";
        execute["nextAction"] =
          "inspect the Provider and the original preparation result";
      }
    }
    const execute = (value["actions"] as Json)["execute"] as Json;
    execute["path"] = `/api/operations/organize/previews/${previewId}/execute`;
    return value;
  };

  const metadataCorrectionRecovery = (resolved: boolean): Json => ({
    task_id: "organize-task-1",
    item_id: "problem-item-1",
    checkpoint: {
      status: resolved ? "pending" : "waiting_metadata_correction",
      stage: resolved ? "queued" : "waiting_metadata_correction",
      raw_stage: resolved
        ? "metadata_correction_resolved"
        : "waiting_metadata_correction",
      effects: { certainty: "none" },
      retry_safety: resolved ? "safe" : "unsafe",
      checkpoint_version: "b".repeat(64),
      blocker: resolved
        ? null
        : { kind: "metadata_correction", blocker_id: "correction-1" },
      permitted_action_ids: resolved
        ? ["retry"]
        : ["resolve_metadata_correction", "ignore"],
      refusal_reason: null,
      next_action: resolved
        ? "continue safe analysis"
        : "correct the metadata search",
    },
    decision: resolved
      ? null
      : {
          kind: "metadata_correction",
          review_id: "correction-1",
          status: "pending",
          query: "Movie.01",
          year: 2001,
          media_type: "movie",
          reason: "Season 4 is not available for '黑袍纠察队' (2024)",
          can_search: true,
          choices: [],
          allowed_strategies: [],
          conflict_types: [],
        },
    manualRecoveryAvailable: false,
    native_analysis: {
      task_id: "organize-task-1",
      item_id: "problem-item-1",
      readable: true,
      queue_state: state.recoveryAnalysisQueued ? "queued" : "waiting_human",
      machine_stage: state.recoveryAnalysisQueued ? "analysis" : null,
    },
    recoveryKind: "business_problem",
    next_action: resolved
      ? "continue safe analysis"
      : "correct the metadata search",
  });

  const metadataCandidateRecovery = (resolved: boolean): Json => ({
    task_id: "organize-task-1",
    item_id: "problem-item-1",
    checkpoint: {
      status: resolved ? "pending" : "waiting_metadata",
      stage: resolved ? "queued" : "waiting_metadata",
      raw_stage: resolved ? "metadata_resolved" : "waiting_metadata",
      effects: { certainty: "none" },
      retry_safety: resolved ? "safe" : "unsafe",
      checkpoint_version: "c".repeat(64),
      blocker: resolved
        ? null
        : { kind: "metadata", blocker_id: "metadata-review-1" },
      permitted_action_ids: resolved
        ? ["retry"]
        : ["resolve_metadata", "ignore"],
      refusal_reason: null,
      next_action: resolved
        ? "continue safe analysis"
        : "choose one legal metadata candidate",
    },
    decision: resolved
      ? null
      : {
          kind: "metadata",
          review_id: "metadata-review-1",
          status: "pending",
          query: "Movie.01",
          year: 2001,
          media_type: "movie",
          can_search: false,
          candidates: [
            {
              rank: 1,
              provider: "tmdb",
              provider_id: "501",
              media_type: "movie",
              title: "Movie.01",
              original_title: null,
              canonical_year: 2001,
            },
            {
              rank: 2,
              provider: "tmdb",
              provider_id: "601",
              media_type: "movie",
              title: "Movie.01",
              original_title: "Original Movie",
              canonical_year: 2001,
            },
          ],
          allowed_strategies: [],
          conflict_types: [],
        },
    manualRecoveryAvailable: false,
    native_analysis: {
      task_id: "organize-task-1",
      item_id: "problem-item-1",
      readable: true,
      queue_state: state.recoveryAnalysisQueued ? "queued" : "waiting_human",
      machine_stage: state.recoveryAnalysisQueued ? "analysis" : null,
    },
    recoveryKind: "business_problem",
    next_action: resolved
      ? "continue safe analysis"
      : "choose one legal metadata candidate",
  });

  const conflictRecovery = (resolved: boolean): Json => ({
    task_id: "organize-task-1",
    item_id: "problem-item-1",
    checkpoint: {
      status: resolved ? "skipped" : "waiting_conflict",
      stage: resolved ? "conflict_resolved" : "waiting_conflict",
      raw_stage: resolved ? "conflict_resolved" : "waiting_conflict",
      effects: { certainty: "none" },
      retry_safety: "safe",
      checkpoint_version: "d".repeat(64),
      blocker: resolved ? null : { kind: "conflict", blocker_id: "conflict-1" },
      // The backend offers ignore only for the recognition/metadata review
      // families, never for a destination conflict.
      permitted_action_ids: resolved ? [] : ["resolve_conflict"],
      refusal_reason: null,
      next_action: resolved ? null : "choose a conflict strategy",
    },
    decision: resolved
      ? null
      : {
          kind: "conflict",
          review_id: "conflict-1",
          status: "pending",
          configured_strategy: "manual",
          allowed_strategies: ["skip", "rename"],
          conflict_types: ["DESTINATION_EXISTS"],
          source_path: "Movies/Movie.01.mkv",
          target_path: "Movies/Movie.01 (2001)/Movie.01.mkv",
        },
    manualRecoveryAvailable: false,
    native_analysis: {
      task_id: "organize-task-1",
      item_id: "problem-item-1",
      readable: true,
      queue_state: "waiting_human",
      machine_stage: null,
    },
    recoveryKind: resolved ? "technical_history" : "business_problem",
    next_action: resolved ? "none" : "choose a conflict strategy",
  });

  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url === "/api/auth/principal" && method === "GET") {
        return jsonResponse({ principal_id: "dialog-operator" });
      }

      if (url === "/api/system/status") {
        return jsonResponse({
          system: {
            configuration_valid: true,
            configuration_authority: "MANAGED",
            configuration_snapshot_id: "active-1",
          },
          storages: {
            total: 1,
            truncated: false,
            items: [
              {
                id: "local-1",
                name: "Storage local-1",
                type: "local",
                read_only: false,
                enabled: true,
              },
            ],
          },
          resource_libraries: {
            total: 1,
            truncated: false,
            items: [
              {
                id: "library",
                name: "资源库A",
                storage_id: state.mismatchedLibraries
                  ? "other-source"
                  : "source",
                root_path: state.mismatchedLibraries ? "Elsewhere" : "",
                enabled: true,
              },
            ],
          },
        });
      }

      if (url === "/api/media-libraries" && method === "GET") {
        return jsonResponse({
          items: [
            {
              id: "movies",
              name: "电影库",
              enabled: true,
              rootPath: "Movies",
              storage: {
                id: state.mismatchedLibraries ? "other-target" : "target",
                name: "Storage target",
                type: "local",
                readOnly: false,
              },
            },
          ],
          total: 1,
          sideEffects: "none",
        });
      }

      if (/\/resource-libraries\/[^/]+\/files(\?|$)/.test(url)) {
        return jsonResponse({
          configuration: { authority: "MANAGED", revisionId: "active-1" },
          resourceLibrary: {
            id: "library",
            name: "资源库A",
            enabled: true,
            rootPath: "/library",
            storage: {
              id: "local-1",
              name: "Storage local-1",
              type: "local",
              readOnly: false,
            },
          },
          path: "",
          breadcrumbs: [{ name: "root", path: "", isRoot: true }],
          entries: [
            {
              name: "Movies",
              path: "Movies",
              type: "directory",
              size: 0,
              modifiedAt: "2026-08-23T11:15:00Z",
              isDirectory: true,
              isSymlink: false,
              traversable: true,
              selectable: true,
              recognitionResult: null,
              businessStatus: null,
            },
            ...Array.from({ length: FILE_COUNT }, (_, index) => ({
              name: filename(index),
              path: `Movies/${filename(index)}`,
              type: "file",
              size: 1024,
              modifiedAt: "2026-08-23T11:15:00Z",
              isDirectory: false,
              isSymlink: false,
              traversable: false,
              selectable: true,
              organizeEligible: true,
              organizeKind: "file" as const,
              recognitionResult: null,
              businessStatus: null,
            })),
          ],
          limit: 50,
          nextCursor: null,
          hasNext: false,
          exhausted: true,
          sideEffects: "none",
          retrySafe: true,
        });
      }

      if (
        /\/resource-libraries\/[^/]+\/files\/discoveries$/.test(url) &&
        method === "POST"
      ) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Json;
        calls.discoveryPosts.push(body);
        state.selectedPaths = (body["paths"] as string[] | undefined) ?? [];
        return jsonResponse(
          {
            discoveryId: DISCOVERY_ID,
            journey: "discovery",
            selection: {
              scopeCount: 1,
              scopes: [],
            },
            status: "queued",
          },
          202,
        );
      }

      if (
        url === `/api/operations/organize/discoveries/${DISCOVERY_ID}` &&
        method === "GET"
      ) {
        state.discoveryReads += 1;
        if (state.primaryLimit && state.primaryLimitSettlementReads > 0) {
          state.primaryLimitSettlementReads -= 1;
          if (state.primaryLimitSettlementReads === 0) state.endedFlow = true;
        }
        if (state.workerUnavailableReads > 0) {
          state.workerUnavailableReads -= 1;
          const unavailable = discoveryDocument();
          unavailable["status"] = "queued";
          unavailable["previewId"] = null;
          unavailable["prepared"] = false;
          unavailable["intentId"] = null;
          unavailable["frozen"] = false;
          unavailable["primarySourceCount"] = 0;
          const progress = unavailable["progress"] as Json;
          progress["visitedEntries"] = 0;
          progress["visitedDirectories"] = 0;
          progress["primarySources"] = 0;
          progress["excludedEntries"] = 0;
          progress["unstableEntries"] = 0;
          progress["errorEntries"] = 0;
          progress["message"] =
            "the request is saved; no live Worker advertises media_discovery";
          unavailable["worker"] = {
            ready: false,
            condition: "unsupported_command",
            durableState: "live workers do not advertise the requested command",
            nextAction:
              "start or upgrade a resident worker that supports bounded discovery",
          };
          return jsonResponse(unavailable);
        }
        if (state.queuedReads > 0) {
          state.queuedReads -= 1;
          const queued = discoveryDocument();
          queued["status"] = "queued";
          queued["previewId"] = null;
          queued["prepared"] = false;
          queued["intentId"] = null;
          queued["frozen"] = false;
          queued["primarySourceCount"] = 0;
          const progress = queued["progress"] as Json;
          progress["visitedEntries"] = 0;
          progress["visitedDirectories"] = 0;
          progress["primarySources"] = 0;
          progress["excludedEntries"] = 0;
          progress["unstableEntries"] = 0;
          progress["errorEntries"] = 0;
          progress["message"] = "bounded discovery is running";
          return jsonResponse(queued);
        }
        if (state.discoveryReads <= state.waitingReads) {
          const waiting = discoveryDocument();
          waiting["status"] = "waiting_stability";
          waiting["previewId"] = null;
          waiting["intentId"] = null;
          waiting["frozen"] = false;
          const progress = waiting["progress"] as Json;
          progress["unstableEntries"] = 2;
          progress["message"] =
            "the whole scope was visited, but some sources are not yet proven stable";
          return jsonResponse(waiting);
        }
        if (state.analyzingReads > 0) {
          state.analyzingReads -= 1;
          const analyzing = discoveryDocument();
          analyzing["status"] = "analyzing";
          analyzing["previewId"] = null;
          analyzing["prepared"] = false;
          const progress = analyzing["progress"] as Json;
          progress["phase"] = "analyzing";
          progress["message"] =
            "the reviewed source list is frozen; the analysis is building the plan summary";
          return jsonResponse(analyzing);
        }
        if (
          state.discoveryReads <=
          state.walkOnlyReads + state.frozenOnlyReads
        ) {
          const intermediate = discoveryDocument();
          intermediate["previewId"] = null;
          intermediate["prepared"] = false;
          if (state.discoveryReads <= state.walkOnlyReads) {
            // The completed walk is durable, but freezing the reviewed source
            // list and entering analysis have not been published yet.
            intermediate["intentId"] = null;
            intermediate["frozen"] = false;
            intermediate["nextAction"] =
              "wait for the resident Processing Worker to finish the bounded discovery";
          } else {
            intermediate["intentId"] = INTENT_ID;
            intermediate["frozen"] = true;
            const prepare = (intermediate["actions"] as Json)[
              "prepare"
            ] as Json;
            // The real backend advertises this action only at the Task's
            // human-waiting boundary.  While the Worker still owns the freeze
            // it reports the same work as pending instead.
            prepare["available"] = state.manualAnalysisRecovery;
            prepare["pendingReason"] = state.manualAnalysisRecovery
              ? null
              : "discovery_analysis_pending";
            prepare["path"] = state.manualAnalysisRecovery
              ? `/api/operations/organize/discoveries/${DISCOVERY_ID}/analyze`
              : null;
          }
          return jsonResponse(intermediate);
        }
        return jsonResponse(discoveryDocument());
      }

      if (
        url === `/api/tasks/organize-task-1/items/problem-item-1/recovery` &&
        method === "GET"
      ) {
        if (state.ignoredProblem) {
          return jsonResponse({
            task_id: "organize-task-1",
            item_id: "problem-item-1",
            checkpoint: {
              status: "ignored",
              stage: "ignored",
              raw_stage: "ignored",
              effects: { certainty: "none" },
              retry_safety: "safe",
              checkpoint_version: "f".repeat(64),
              blocker: null,
              permitted_action_ids: [],
              refusal_reason: null,
              next_action: null,
            },
            decision: null,
            manualRecoveryAvailable: false,
            native_analysis: {
              task_id: "organize-task-1",
              item_id: "problem-item-1",
              readable: true,
              queue_state: "waiting_human",
              machine_stage: null,
            },
            recoveryKind: "technical_history",
            next_action: "none",
          });
        }
        return jsonResponse(
          state.conflictProblem
            ? conflictRecovery(state.conflictResolved)
            : state.metadataCandidateProblem
              ? metadataCandidateRecovery(state.metadataCandidateResolved)
              : metadataCorrectionRecovery(state.metadataProblemResolved),
        );
      }

      if (
        url === `/api/tasks/organize-task-1/items/problem-item-1/recovery` &&
        method === "POST"
      ) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Json;
        if (body["actionId"] !== "ignore") {
          return jsonResponse({ error: { code: "invalid_action" } }, 409);
        }
        state.ignoredProblem = true;
        return jsonResponse({
          task_id: "organize-task-1",
          item_id: "problem-item-1",
          action_id: "ignore",
          accepted: true,
          sideEffects: "none",
          next_action: "reload the ignored item",
        });
      }

      if (
        url ===
          `/api/tasks/organize-task-1/items/problem-item-1/recovery/metadata-search` &&
        method === "POST"
      ) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Json;
        calls.metadataSearchPosts.push(body);
        if (state.rejectMetadataSearchYear) {
          return jsonResponse(
            {
              error: {
                code: "invalid_year",
                message:
                  "enter a search year between 1870 and 2100, or clear the year",
                details: {
                  sideEffects: "none",
                  nextAction:
                    "correct or clear the year, then run Metadata search again",
                },
              },
            },
            400,
          );
        }
        return jsonResponse({
          task_id: "organize-task-1",
          item_id: "problem-item-1",
          checkpoint_version: "b".repeat(64),
          provider: "tmdb",
          media_type: "movie",
          query: body["query"] ?? "",
          candidates: [
            {
              rank: 1,
              provider_id: "704",
              media_type: "movie",
              title: "DialogRename",
              original_title: null,
              year: 2024,
              release_date: "2024-01-01",
              original_language: "en",
            },
          ],
          truncated: false,
          next_action: "choose one candidate and save the decision",
        });
      }

      if (
        url ===
          `/api/tasks/organize-task-1/items/problem-item-1/recovery/decision` &&
        method === "POST"
      ) {
        calls.recoveryDecisionPosts.push(
          JSON.parse(String(init?.body ?? "{}")) as Json,
        );
        if (state.failMetadataDecision) {
          return jsonResponse({ error: { code: "stale_checkpoint" } }, 409);
        }
        state.recoveryAnalysisQueued = false;
        if (state.conflictProblem) {
          state.conflictResolved = true;
          if (state.loseConflictDecisionResponse) {
            throw new TypeError("response lost after the durable skip");
          }
          return jsonResponse(conflictRecovery(true));
        }
        if (state.metadataCandidateProblem) {
          state.metadataCandidateResolved = true;
          return jsonResponse(metadataCandidateRecovery(true));
        }
        state.metadataProblemResolved = true;
        return jsonResponse(metadataCorrectionRecovery(true));
      }

      if (
        url ===
          `/api/tasks/organize-task-1/items/problem-item-1/recovery/continue` &&
        method === "POST"
      ) {
        calls.recoveryContinuePosts.push(
          JSON.parse(String(init?.body ?? "{}")) as Json,
        );
        if (state.failMetadataContinue) {
          return jsonResponse({ error: { code: "unavailable" } }, 503);
        }
        state.recoveryAnalysisQueued = true;
        if (state.flipPreviewOnAnalyze) state.previewId = "preview-2";
        return jsonResponse({
          sideEffects: "none",
          next_action: "wait for the Worker and inspect its linked result",
          nativeAnalysis: { taskId: "organize-task-1" },
        });
      }

      if (
        url ===
          `/api/operations/organize/discoveries/${DISCOVERY_ID}/analyze` &&
        method === "POST"
      ) {
        calls.analyzePosts.push(JSON.parse(String(init?.body ?? "{}")) as Json);
        if (state.rejectAnalysisOnce) {
          // The Worker published a newer preparation while this page still
          // showed the older walk.  The same preparation is re-read next.
          state.rejectAnalysisOnce = false;
          state.walkOnlyReads = 0;
          state.frozenOnlyReads = 0;
          state.analyzingReads = 0;
          return jsonResponse(
            {
              error: {
                code: "discovery_conflict",
                message: "the preparation changed since it was read",
                details: {
                  nextAction:
                    "reload the discovery and retry the same deliberate action",
                },
              },
            },
            409,
          );
        }
        state.walkOnlyReads = 0;
        state.frozenOnlyReads = 0;
        if (state.flipPreviewOnAnalyze) {
          state.previewId = "preview-2";
        }
        if (state.analyzeShowsAnalyzing) state.analyzingReads = 2;
        return jsonResponse(discoveryDocument());
      }

      if (
        url === `/api/operations/organize/intents/${INTENT_ID}` &&
        method === "GET"
      ) {
        return jsonResponse(intentDocument());
      }

      const choiceMatch = url.match(
        /^\/api\/operations\/organize\/intents\/intent-1\/items\/([^/]+)\/choice$/,
      );
      if (choiceMatch !== null && method === "POST") {
        const itemId = choiceMatch[1] ?? "";
        const body = JSON.parse(String(init?.body ?? "{}")) as Json;
        calls.choicePosts.push({ itemId, ...body });
        state.savedMetadata.set(
          itemId,
          (body["metadata"] as Json | null) ?? null,
        );
        return jsonResponse(intentDocument());
      }

      const previewMatch = url.match(
        /^\/api\/operations\/organize\/previews\/([^/?]+)$/,
      );
      if (previewMatch !== null && method === "GET") {
        const previewId = previewMatch[1] ?? "";
        if (previewId === PREVIEW_ID) {
          if (state.failFirstPreviewRead) {
            state.failFirstPreviewRead = false;
            return jsonResponse(
              {
                error: { code: "unavailable", message: "summary read failed" },
              },
              503,
            );
          }
          return jsonResponse(previewDocument(PREVIEW_ID, false));
        }
        if (previewId === "preview-2") {
          return jsonResponse(previewDocument("preview-2", true));
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }

      if (
        url.startsWith("/api/operations/organize/executions") &&
        method === "GET"
      ) {
        return jsonResponse({
          items: [],
          journey: "organize-execution-list",
          limit: 100,
          total: 0,
          truncated: false,
        });
      }

      const admissionMatch = url.match(
        /^\/api\/operations\/organize\/previews\/([^/?]+)\/admission/,
      );
      if (admissionMatch !== null && method === "GET") {
        const previewId = admissionMatch[1] ?? "";
        const rawQuery = url.split("?")[1] ?? "";
        calls.admissionReads += 1;
        calls.admissionRequests.push({
          previewId,
          params: Object.fromEntries(new URLSearchParams(rawQuery)),
        });
        if (state.failAdmissionReads > 0) {
          state.failAdmissionReads -= 1;
          return jsonResponse({ error: { code: "unavailable" } }, 503);
        }
        if (!state.admittedPreviewIds.includes(previewId)) {
          // No durable admission exists under this exact summary: the honest
          // answer for a preview the operator never executed.
          return jsonResponse({
            outcome: "not_admitted",
            reason: "execution_not_found",
            executionId: null,
            taskId: null,
            status: null,
            selectedItemIds: [],
            completedItemCount: 0,
            failedItemCount: 0,
            sideEffects: "none",
            nextAction: "refresh the exact summary before confirming again",
          });
        }
        return jsonResponse({
          outcome: "known",
          reason: null,
          executionId: "exec-1",
          taskId: "task-handoff-1",
          status: "running",
          selectedItemIds: ["item-1"],
          completedItemCount: 0,
          failedItemCount: 0,
          sideEffects: "none",
          nextAction: "inspect the durable task in Task Center",
        });
      }

      const executeMatch = url.match(
        /^\/api\/operations\/organize\/previews\/([^/?]+)\/execute$/,
      );
      if (executeMatch !== null && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}")) as Json;
        calls.executePosts.push(body);
        calls.executePreviewIds.push(executeMatch[1] ?? "");
        // The durable admission record exists regardless of what the browser
        // later sees: a lost response never erases it.
        state.admittedPreviewIds.push(executeMatch[1] ?? "");
        const respond = () =>
          jsonResponse({
            executionId: "exec-1",
            taskId: "task-handoff-1",
            previewId: executeMatch[1],
            intentId: INTENT_ID,
            status: "admitted",
            durableState: "awaiting worker claim",
            intentVersion: 7,
            selectedItemIds: (body["itemIds"] as string[]) ?? [],
            unselectedItemIds: [],
            selectedItemCount: ((body["itemIds"] as string[]) ?? []).length,
            unselectedItemCount: 0,
            completedItemCount: 0,
            failedItemCount: 0,
            allowOverwrite: body["allowOverwrite"] === true,
            allowSourceCleanup: body["allowSourceCleanup"] === true,
            createdAt: "2026-01-01T00:00:00+00:00",
            updatedAt: "2026-01-01T00:00:00+00:00",
            completedAt: null,
            nextAction: "the resident worker claims the admitted execution",
            failure: null,
            knownEffects: {
              verifiedItemCount: 0,
              uncertainItemCount: 0,
              failedWithoutEffectCount: 0,
              statement: "no item effect has been observed yet",
            },
            items: [],
            actions: {
              detail: {
                available: true,
                method: "GET",
                path: "/api/operations/organize/executions/exec-1",
                nextAction: "inspect the durable task",
                reason: null,
                sideEffects: "none",
                durableOutcome: null,
              },
              task: {
                available: true,
                method: "GET",
                path: "/api/operations/tasks/task-handoff-1",
                nextAction: "inspect the durable task",
                reason: null,
                sideEffects: "none",
                durableOutcome: null,
              },
              recovery: {
                available: false,
                method: null,
                path: null,
                nextAction: null,
                reason: "recovery is only offered for a failed item",
                sideEffects: "none",
                durableOutcome: null,
              },
            },
          });
        if (holdExecute) {
          const held = new Promise<Response>((resolve) => {
            releasedExecute = resolve;
          });
          void held.then((response) => heldExecuteResponses.push(response));
          return held;
        }
        return respond();
      }

      const runItemsMatch = url.match(
        /^\/api\/operations\/runs\/([^/?]+)\/items(?:\?|$)/,
      );
      if (runItemsMatch !== null && method === "GET") {
        calls.settledRecordsReads += 1;
        if (state.failSettledRecords) {
          return jsonResponse({ error: { code: "unavailable" } }, 503);
        }
        if (state.holdSettledReads) {
          await new Promise<void>((resolve) => {
            settledReadReleases.push(resolve);
          });
        }
        const taskId = runItemsMatch[1] ?? "";
        const params = new URLSearchParams(url.split("?")[1] ?? "");
        const status = params.get("status");
        const all = state.durableSettledItems.filter(
          (row) => row.taskId === taskId,
        );
        const records = all.filter(
          (row) => status === null || row.status === status,
        );
        const dispositions = {
          pending: 0,
          active: 0,
          waiting: 0,
          success: 0,
          skipped: all.filter((row) => row.status === "skipped").length,
          ignored: all.filter((row) => row.status === "ignored").length,
          failed_partial: 0,
          cancelled: 0,
        };
        return jsonResponse({
          run_id: taskId,
          task_id: taskId,
          filter: { status },
          limit: 100,
          items: records.map((row) => ({
            item_id: row.itemId,
            task_id: taskId,
            storage_id: "source",
            resource_library_id: "library",
            source_path: row.sourcePath,
            status: row.status,
            stage: row.status === "skipped" ? "conflict_resolved" : "ignored",
            attempts: 1,
            created_at: "2026-01-01T00:00:00+00:00",
            updated_at: "2026-01-01T00:00:00+00:00",
            destination_storage_id: null,
            destination_path: null,
            execution_status: null,
            failure: null,
            checkpoint: {
              status: row.status,
              stage: row.status === "skipped" ? "conflict_resolved" : "ignored",
              raw_stage:
                row.status === "skipped" ? "conflict_resolved" : "ignored",
              blocker_kind: null,
              blocker_id: null,
              effect_certainty: "none",
              retry_safety: "safe",
              refusal_reason: null,
              checkpoint_version: "e".repeat(64),
              permitted_action_ids: [],
            },
            recovery_kind: "technical_history",
          })),
          total: all.length,
          matching_total: records.length,
          dispositions,
          uncertain_success: 0,
          truncated: false,
          previous_cursor: null,
          next_cursor: null,
          unavailable: null,
          sideEffects: "none",
        });
      }

      return jsonResponse({ error: { code: "not_found" } }, 404);
    },
  );

  return {
    calls,
    fetchMock,
    state,
    holdExecute: () => {
      holdExecute = true;
    },
    releaseSettledReads: () => {
      state.holdSettledReads = false;
      for (const resolve of settledReadReleases.splice(0)) resolve();
    },
    releaseExecute: () => {
      holdExecute = false;
      const resolve = releasedExecute;
      releasedExecute = null;
      // Resolve the held request with a normal admitted answer.
      resolve?.(
        jsonResponse({
          executionId: "exec-1",
          taskId: "task-handoff-1",
          previewId: PREVIEW_ID,
          intentId: INTENT_ID,
          status: "admitted",
          durableState: "awaiting worker claim",
          intentVersion: 7,
          selectedItemIds: ["item-1"],
          unselectedItemIds: [],
          selectedItemCount: 1,
          unselectedItemCount: 0,
          completedItemCount: 0,
          failedItemCount: 0,
          allowOverwrite: false,
          allowSourceCleanup: false,
          createdAt: "2026-01-01T00:00:00+00:00",
          updatedAt: "2026-01-01T00:00:00+00:00",
          completedAt: null,
          nextAction: "the resident worker claims the admitted execution",
          failure: null,
          knownEffects: {
            verifiedItemCount: 0,
            uncertainItemCount: 0,
            failedWithoutEffectCount: 0,
            statement: "no item effect has been observed yet",
          },
          items: [],
          actions: {
            detail: {
              available: true,
              method: "GET",
              path: "/api/operations/organize/executions/exec-1",
              nextAction: "inspect the durable task",
              reason: null,
              sideEffects: "none",
              durableOutcome: null,
            },
            task: {
              available: true,
              method: "GET",
              path: "/api/operations/tasks/task-handoff-1",
              nextAction: "inspect the durable task",
              reason: null,
              sideEffects: "none",
              durableOutcome: null,
            },
            recovery: {
              available: false,
              method: null,
              path: null,
              nextAction: null,
              reason: "recovery is only offered for a failed item",
              sideEffects: "none",
              durableOutcome: null,
            },
          },
        }),
      );
    },
  };
}

type Backend = ReturnType<typeof makeBackend>;

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  authStore.clearToken();
  window.localStorage.clear();
  window.sessionStorage.clear();
  document.body.innerHTML = "";
});

/** The one mounted card, so assertions never read the Files background rows. */
function card(): HTMLElement {
  return screen.getByRole("dialog", { name: "整理所选文件" });
}

/** Open the on-demand correction details the way the operator does. */
async function openCorrection(
  user: ReturnType<typeof userEvent.setup>,
): Promise<void> {
  const summary = within(card()).queryByText(/^修正识别或作品/);
  if (summary === null) return;
  const details = summary.closest("details");
  if (details !== null && !details.open) await user.click(summary);
}

/**
 * Enter the Files owned overview and open its first exact file, which is the
 * ordinary per-file review the Slice53 journeys used to reach directly.
 */
async function enterFirstOverviewFile(
  user: ReturnType<typeof userEvent.setup>,
  expectedHeading: RegExp = /第 1 \/ 10 个/,
): Promise<void> {
  const overview = await screen.findByRole(
    "region",
    { name: "本次整理概览" },
    { timeout: 5_000 },
  );
  const first = within(overview).getAllByRole("button", { name: /^查看 / })[0];
  if (first === undefined) throw new Error("overview exposed no readable file");
  await user.click(first);
  await screen.findByRole("heading", { name: expectedHeading });
}

/** Mount the real Files page and open the real batch entry. */
async function openDialog(
  user: ReturnType<typeof userEvent.setup>,
  configure?: (backend: Backend) => void,
  selection?: readonly string[],
  entry: "file" | "preparation" | "overview" = "file",
): Promise<
  Backend & { readonly router: ReturnType<typeof renderApp>["router"] }
> {
  const backend = makeBackend();
  configure?.(backend);
  vi.stubGlobal("fetch", backend.fetchMock);
  authStore.setToken(TOKEN);
  const { router } = renderApp("/resourcelib/files");
  await screen.findByRole("table");
  if (selection === undefined) {
    await user.click(screen.getByRole("checkbox", { name: "选择全部" }));
  } else {
    for (const name of selection) {
      await user.click(screen.getByRole("checkbox", { name: `选择 ${name}` }));
    }
  }
  await user.click(screen.getByRole("button", { name: "批量整理" }));
  await screen.findByRole("dialog", { name: "整理所选文件" });
  if (entry === "file") {
    await enterFirstOverviewFile(
      user,
      new RegExp(`第 \\d+ \\/ ${selection?.length ?? FILE_COUNT} 个`),
    );
  }
  if (entry === "overview") {
    await screen.findByRole("region", { name: "本次整理概览" });
  }
  return Object.assign(backend, { router });
}

/** Keep the real preparation screen instead of entering its plan. */
async function openPreparationDialog(
  user: ReturnType<typeof userEvent.setup>,
  configure?: (backend: Backend) => void,
  selection?: readonly string[],
): Promise<
  Backend & { readonly router: ReturnType<typeof renderApp>["router"] }
> {
  return openDialog(user, configure, selection, "preparation");
}

describe("ManualOrganizeDialog", () => {
  it("walks ten files with one candidate choice plus one save/analysis each and executes exactly once at the end", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user);

    const firstHeading = await screen.findByRole("heading", {
      name: /第 1 \/ 10 个/,
    });
    expect(firstHeading).toBeVisible();
    expect(within(card()).getByText("Movie.01.mkv")).toBeVisible();
    // Preparing is zero-mutation: browsing, saving and analyzing never
    // touched the Execute surface before the final confirmation.
    expect(backend.calls.executePosts).toHaveLength(0);

    for (let index = 0; index < FILE_COUNT; index += 1) {
      const name = filename(index);
      await waitFor(() =>
        expect(
          within(card()).getByRole("heading", {
            name: new RegExp(`第 ${index + 1} / 10 个`),
          }),
        ).toBeVisible(),
      );
      expect(within(card()).getAllByText(name).length).toBeGreaterThan(0);

      await openCorrection(user);
      const identitySelect = screen.getByLabelText(`元数据身份 ${name}`);
      const firstIdentity = within(identitySelect)
        .getAllByRole("option")
        .at(1)
        ?.getAttribute("value");
      expect(firstIdentity).toBeTruthy();
      await user.selectOptions(identitySelect, firstIdentity as string);

      const saveButton = screen.getByRole("button", { name: "保存并重新分析" });
      await waitFor(() => expect(saveButton).toBeEnabled());
      await user.click(saveButton);

      // One explicit save + one explicit analysis for this file — the card
      // reports both stages and never executes anything meanwhile.
      await waitFor(() =>
        expect(
          screen.getByText(/选择已保存,正在按固定配置重新分析/),
        ).toBeVisible(),
      );
      expect(backend.calls.executePosts).toHaveLength(0);

      if (index < FILE_COUNT - 1) {
        await user.click(screen.getByRole("button", { name: "下一项" }));
      }
    }

    expect(backend.calls.choicePosts).toHaveLength(FILE_COUNT);
    expect(backend.calls.analyzePosts).toHaveLength(FILE_COUNT);
    expect(backend.calls.choicePosts.map((body) => body["itemId"])).toEqual(
      Array.from({ length: FILE_COUNT }, (_, i) => `item-${i + 1}`),
    );
    for (const body of backend.calls.choicePosts) {
      expect(body["expectedItemVersion"]).toBe(1);
      expect(body["recognitionTypeId"]).toBe("A");
      expect(body["expectedVersion"]).toBeGreaterThanOrEqual(1);
    }
    expect(backend.calls.executePosts).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    expect(screen.getByRole("region", { name: "整批复核" })).toHaveTextContent(
      /本次确认\s*10\s*项/,
    );

    const confirm = screen.getByRole("button", { name: "确认整理 10 项" });
    expect(confirm).toBeEnabled();
    // Still zero Execute before the single operator confirmation.
    expect(backend.calls.executePosts).toHaveLength(0);

    // Two activation gestures in one tick: the in-process lock must keep this
    // at exactly one Execute while the card shows its in-flight state.
    backend.holdExecute();
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await screen.findByRole("button", { name: "正在提交..." });
    expect(screen.getByRole("button", { name: "正在提交..." })).toBeDisabled();
    await waitFor(() => expect(backend.calls.executePosts).toHaveLength(1));
    expect(backend.calls.executePosts[0]?.["itemIds"]).toHaveLength(FILE_COUNT);
    expect(backend.calls.executePosts[0]?.["confirmation"]).toBe(true);

    backend.releaseExecute();

    // Success hands the exact durable task to the task center's existing
    // selection mechanism: the route carries only `run=<taskId>`, never a
    // guess or a separate execution-results page.
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    await waitFor(() =>
      expect(backend.router.state.location.pathname).toBe("/operations"),
    );
    expect(backend.router.state.location.search).toMatchObject({
      run: "task-handoff-1",
    });
  }, 30_000);

  it("lets the current file correct a missing metadata candidate and keeps unsaved correction inputs across paging", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataProblem = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    // The backend published this exact file's metadata-correction problem on
    // its own TaskItem. The card must offer that native decision instead of a
    // dead generic failure.
    expect(within(card()).getByText(/没有找到匹配的作品/)).toBeVisible();
    expect(
      within(card()).getByText(/上次修正未通过验证：Season 4 is not available/),
    ).toBeVisible();
    const title = screen.getByLabelText("搜索标题");
    expect(title).toHaveValue("Movie.01");
    // The native TaskItem decision is the single correction path: the older
    // intent identity selectors are not also mounted for the same file.
    expect(
      within(card()).queryByLabelText("元数据身份 Movie.01.mkv"),
    ).toBeNull();
    expect(within(card()).queryByLabelText("识别类型 Movie.01.mkv")).toBeNull();
    expect(
      within(card()).getAllByRole("button", { name: "保存并重新分析" }),
    ).toHaveLength(1);
    await user.clear(title);
    await user.type(title, "DialogRename");
    const year = screen.getByLabelText("年份（可留空）");
    await user.clear(year);
    await user.type(year, "2024");

    // Paging is browse-only and must keep this file's unsaved correction.
    await user.click(screen.getByRole("button", { name: "下一项" }));
    await screen.findByRole("heading", { name: /第 2 \/ 10 个/ });
    await user.click(screen.getByRole("button", { name: "上一项" }));
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    await waitFor(() =>
      expect(screen.getByLabelText("搜索标题")).toHaveValue("DialogRename"),
    );
    expect(screen.getByLabelText("年份（可留空）")).toHaveValue(2024);
    expect(backend.calls.metadataSearchPosts).toHaveLength(0);
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    // The explicit Provider search is a read; choosing its grounded candidate
    // and saving the decision re-analyzes without executing anything.
    await user.click(screen.getByRole("button", { name: "搜索元数据" }));
    await waitFor(() =>
      expect(backend.calls.metadataSearchPosts).toHaveLength(1),
    );
    expect(backend.calls.metadataSearchPosts[0]).toMatchObject({
      query: "DialogRename",
      mediaType: "movie",
      // The search submits the exact edited year, not the original 2001.
      year: 2024,
    });
    await user.click(
      await screen.findByRole("radio", { name: /DialogRename/ }),
    );
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));

    await waitFor(() =>
      expect(backend.calls.recoveryDecisionPosts).toHaveLength(1),
    );
    expect(backend.calls.recoveryDecisionPosts[0]).toMatchObject({
      kind: "metadata_correction",
      query: "DialogRename",
      year: 2024,
      mediaType: "movie",
      providerId: "704",
    });
    await waitFor(() =>
      expect(backend.calls.recoveryContinuePosts).toHaveLength(1),
    );
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(
      await screen.findByText(/当前文件的决定已保存并请求重新分析/),
    ).toBeVisible();
    await waitFor(() =>
      expect(within(card()).getAllByText("纳入本次整理")[0]).toBeVisible(),
    );
    expect(backend.calls.executePosts).toHaveLength(0);

    // The correction was durably saved and re-analyzed: closing afterwards is
    // an ordinary close, not a discard prompt for inputs that already exist.
    await user.click(screen.getByRole("button", { name: "关闭整理弹窗" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("keeps one candidate selection and one save action for a native metadata decision", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataCandidateProblem = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    // Both legal candidates belong to the exact current TaskItem and are shown
    // once, as readable radio cards. There is no second, independently
    // writable metadata identity form on the same file.
    await screen.findByRole("radio", { name: /候选 1/ });
    expect(
      within(card()).queryByLabelText("元数据身份 Movie.01.mkv"),
    ).toBeNull();
    expect(within(card()).queryByLabelText("识别类型 Movie.01.mkv")).toBeNull();
    expect(
      within(card()).getAllByRole("button", { name: "保存并重新分析" }),
    ).toHaveLength(1);
    expect(within(card()).queryByText(/保存决策并继续安全分析/)).toBeNull();

    const save = screen.getByRole("button", { name: "保存并重新分析" });
    expect(save).toBeDisabled();

    // Changing the radio selection replaces the one draft. Nothing is written
    // by selecting, and selecting the second candidate leaves only that value.
    await user.click(screen.getByRole("radio", { name: /候选 2/ }));
    const candidateOne = screen.getByRole("radio", { name: /候选 1/ });
    const candidateTwo = screen.getByRole("radio", { name: /候选 2/ });
    expect(candidateOne).not.toBeChecked();
    expect(candidateTwo).toBeChecked();
    expect(save).toBeEnabled();
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);
    expect(backend.calls.choicePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    await user.click(save);
    await waitFor(() =>
      expect(backend.calls.recoveryDecisionPosts).toHaveLength(1),
    );
    expect(backend.calls.recoveryDecisionPosts[0]).toMatchObject({
      kind: "metadata",
      candidateRank: 2,
    });
    // The single save is followed by the existing zero-mutation analysis; no
    // second intent choice, search or execution was created.
    await waitFor(() =>
      expect(backend.calls.recoveryContinuePosts).toHaveLength(1),
    );
    expect(backend.calls.choicePosts).toHaveLength(0);
    expect(backend.calls.metadataSearchPosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
    await waitFor(() =>
      expect(within(card()).getAllByText("纳入本次整理")[0]).toBeVisible(),
    );
    // The ready page ends the stale selection/waiting copy and keeps the
    // ordinary correction collapsed; the adopted plan owns the first screen.
    expect(within(card()).queryByText(/先完成这个文件的选择/)).toBeNull();
    expect(within(card()).queryByText(/请在下方完成合法决定/)).toBeNull();
    const correction = within(card())
      .getByText(/^修正识别或作品/)
      .closest("details");
    expect(correction?.open).toBe(false);
    expect(
      within(card()).queryByText(/选择已保存,正在按固定配置重新分析/),
    ).toBeNull();
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("reports metadata decision save and analysis failures without executing or replaying", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataProblem = true;
      value.state.failMetadataDecision = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    const save = await screen.findByRole("button", {
      name: "保存并重新分析",
    });

    // A rejected decision stays on the current file; no analysis is requested
    // and no file operation happens.
    await user.click(save);
    expect(await screen.findByText(/条目已变化/)).toBeVisible();
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(1);
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(screen.getByLabelText("搜索标题")).toHaveValue("Movie.01");

    // A rejected save has not persisted the operator's correction, so the
    // same close protection keeps the edited title instead of losing it.
    const editedTitle = screen.getByLabelText("搜索标题");
    await user.clear(editedTitle);
    await user.type(editedTitle, "DialogRename");
    await user.click(screen.getByRole("button", { name: "关闭整理弹窗" }));
    const failedPrompt = await screen.findByRole("alertdialog");
    await user.click(
      within(failedPrompt).getByRole("button", { name: "继续编辑" }),
    );
    expect(screen.getByLabelText("搜索标题")).toHaveValue("DialogRename");

    // The durable decision succeeds but the Worker analysis request does not.
    // The card names that split instead of claiming either a failed save or a
    // successful re-analysis.
    backend.state.failMetadataDecision = false;
    backend.state.failMetadataContinue = true;
    await user.click(save);
    await waitFor(() =>
      expect(backend.calls.recoveryDecisionPosts).toHaveLength(2),
    );
    await waitFor(() =>
      expect(backend.calls.recoveryContinuePosts).toHaveLength(1),
    );
    expect(await screen.findByText(/服务响应无法确认操作结果/)).toBeVisible();
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("searches with the current year and invalidates stale candidates when the inputs change", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataProblem = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    const year = screen.getByLabelText("年份（可留空）");
    expect(year).toHaveValue(2001);
    await user.clear(year);
    await user.type(year, "2024");
    await user.click(screen.getByRole("button", { name: "搜索元数据" }));
    await waitFor(() =>
      expect(backend.calls.metadataSearchPosts).toHaveLength(1),
    );
    expect(backend.calls.metadataSearchPosts[0]).toMatchObject({
      query: "Movie.01",
      mediaType: "movie",
      year: 2024,
    });
    await screen.findByRole("radio", { name: /DialogRename/ });
    await user.click(screen.getByRole("radio", { name: /DialogRename/ }));

    // Clearing the year invalidates that search's read-only candidates and
    // the selection made from them: the saved decision can never carry a
    // Provider ID an older query produced.
    await user.clear(year);
    expect(screen.queryByRole("radio", { name: /DialogRename/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "搜索元数据" }));
    await waitFor(() =>
      expect(backend.calls.metadataSearchPosts).toHaveLength(2),
    );
    // The cleared year is an explicit unbounded search, never a silent
    // fallback to the original or previously edited year.
    expect(backend.calls.metadataSearchPosts[1]).toMatchObject({
      query: "Movie.01",
      mediaType: "movie",
      year: null,
    });
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));
    await waitFor(() =>
      expect(backend.calls.recoveryDecisionPosts).toHaveLength(1),
    );
    expect(backend.calls.recoveryDecisionPosts[0]).toMatchObject({
      kind: "metadata_correction",
      query: "Movie.01",
      year: null,
      mediaType: "movie",
    });
    expect(backend.calls.recoveryDecisionPosts[0]).not.toHaveProperty(
      "providerId",
    );
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("names the refused search year and keeps the card editable until a legal search succeeds", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataProblem = true;
      value.state.rejectMetadataSearchYear = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    const year = screen.getByLabelText("年份（可留空）");
    await user.clear(year);
    await user.type(year, "1869");
    await user.click(screen.getByRole("button", { name: "搜索元数据" }));
    await waitFor(() =>
      expect(backend.calls.metadataSearchPosts).toHaveLength(1),
    );
    expect(backend.calls.metadataSearchPosts[0]).toMatchObject({
      query: "Movie.01",
      mediaType: "movie",
      year: 1869,
    });

    // The exact refusal is visible: this search did not complete, nothing was
    // saved, the year rule and the correction are named. The dialog is not
    // locked and the typed input stays for a direct retry.
    const refusal = await screen.findByText(/本次搜索没有完成/);
    expect(refusal.textContent).toContain("1870–2100");
    expect(refusal.textContent).toContain("重新搜索");
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(screen.getByLabelText("年份（可留空）")).toHaveValue(1869);

    // A corrected year searches successfully on the same card; the refusal is
    // replaced by the grounded candidates and still nothing was saved.
    backend.state.rejectMetadataSearchYear = false;
    await user.clear(year);
    await user.type(year, "2024");
    await user.click(screen.getByRole("button", { name: "搜索元数据" }));
    await waitFor(() =>
      expect(backend.calls.metadataSearchPosts).toHaveLength(2),
    );
    expect(backend.calls.metadataSearchPosts[1]).toMatchObject({ year: 2024 });
    await screen.findByRole("radio", { name: /DialogRename/ });
    expect(screen.queryByText(/本次搜索没有完成/)).toBeNull();
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("keeps unsaved drafts across paging, never saves on paging and pins the discard choice on close", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user);
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    await openCorrection(user);
    const identitySelect = screen.getByLabelText("元数据身份 Movie.01.mkv");
    await user.selectOptions(identitySelect, "tmdb/129/movie");

    await user.click(screen.getByRole("button", { name: "下一项" }));
    await screen.findByRole("heading", { name: /第 2 \/ 10 个/ });
    // Paging is browse-only: no save, no analysis, no execution.
    expect(backend.calls.choicePosts).toHaveLength(0);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "上一项" }));
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    // The unsaved choice is still exactly where it was left.
    expect(
      (
        within(card()).getByLabelText(
          "元数据身份 Movie.01.mkv",
        ) as HTMLSelectElement
      ).value,
    ).toBe("tmdb/129/movie");
    expect(within(card()).getByText(/有未保存的修正/)).toBeVisible();

    // Closing with an unsaved draft pins an explicit choice; nothing was
    // silently cancelled or executed.
    await user.click(screen.getByRole("button", { name: "关闭整理弹窗" }));
    const prompt = await screen.findByRole("alertdialog");
    expect(
      within(prompt).getByText("有尚未保存的逐文件修正草稿。"),
    ).toBeVisible();
    expect(backend.calls.choicePosts).toHaveLength(0);
    await user.click(within(prompt).getByRole("button", { name: "继续编辑" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(screen.getByRole("dialog", { name: "整理所选文件" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "关闭整理弹窗" }));
    const secondPrompt = await screen.findByRole("alertdialog");
    await user.click(
      within(secondPrompt).getByRole("button", { name: "放弃草稿并关闭" }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    expect(backend.calls.choicePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("does not pin a discard prompt for an untouched native decision form", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataProblem = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    await screen.findByLabelText("搜索标题");

    // Merely opening the current file's native decision form changes no
    // operator input; closing stays an ordinary close.
    await user.click(screen.getByRole("button", { name: "关闭整理弹窗" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("protects unsaved native decision input across paging, Escape, close and browser back", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataProblem = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    const title = await screen.findByLabelText("搜索标题");
    await user.clear(title);
    await user.type(title, "DialogRename");
    const year = screen.getByLabelText("年份（可留空）");
    await user.clear(year);
    await user.type(year, "2024");

    // Browsing another file keeps the exact TaskItem's unsaved correction;
    // the page itself never saves or searches.
    await user.click(screen.getByRole("button", { name: "下一项" }));
    await screen.findByRole("heading", { name: /第 2 \/ 10 个/ });
    expect(within(card()).queryByLabelText("搜索标题")).toBeNull();
    expect(backend.calls.metadataSearchPosts).toHaveLength(0);
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);

    // Escape, the header close and a browser back all pin the same existing
    // discard choice while the correction of the other file is unsaved.
    fireEvent.keyDown(document, { key: "Escape" });
    const escapePrompt = await screen.findByRole("alertdialog");
    await user.click(
      within(escapePrompt).getByRole("button", { name: "继续编辑" }),
    );
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(card()).toBeVisible();

    await user.click(screen.getByRole("button", { name: "关闭整理弹窗" }));
    const closePrompt = await screen.findByRole("alertdialog");
    await user.click(
      within(closePrompt).getByRole("button", { name: "继续编辑" }),
    );
    expect(screen.queryByRole("alertdialog")).toBeNull();

    // The first card entry owns one in-app history destination, so this is
    // the same browser-back path an operator can take from the Files page.
    backend.router.history.push("/resourcelib/files");
    backend.router.history.back();
    const backPrompt = await screen.findByRole("alertdialog");
    expect(card()).toBeVisible();
    await user.click(
      within(backPrompt).getByRole("button", { name: "继续编辑" }),
    );

    // The untouched sibling was browse-only; returning to the first file
    // restores exactly the unsaved title and year.
    await user.click(screen.getByRole("button", { name: "上一项" }));
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    await waitFor(() =>
      expect(screen.getByLabelText("搜索标题")).toHaveValue("DialogRename"),
    );
    expect(screen.getByLabelText("年份（可留空）")).toHaveValue(2024);
    expect(within(card()).getByText(/有未保存的修正/)).toBeVisible();
    expect(backend.calls.metadataSearchPosts).toHaveLength(0);
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
    expect(backend.calls.choicePosts).toHaveLength(0);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    // Only the explicit discard leaves; nothing was saved, cancelled or
    // executed by closing or by the blocked navigation.
    await user.click(screen.getByRole("button", { name: "关闭整理弹窗" }));
    const discardPrompt = await screen.findByRole("alertdialog");
    await user.click(
      within(discardPrompt).getByRole("button", {
        name: "放弃草稿并关闭",
      }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    expect(backend.calls.metadataSearchPosts).toHaveLength(0);
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("reports a saved choice whose analysis failed and retries the analysis without saving twice", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user);
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    // The analysis request fails once: the save itself is durable and must be
    // reported as such, with an analysis-only retry.
    let failNextAnalysis = true;
    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/analyze") && failNextAnalysis) {
        failNextAnalysis = false;
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return original(input, init);
    });

    await openCorrection(user);
    await user.selectOptions(
      screen.getByLabelText("元数据身份 Movie.01.mkv"),
      "tmdb/129/movie",
    );
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));

    const warning =
      await screen.findByText(/已读取同一准备，本次分析明确未受理/);
    expect(warning).toBeVisible();
    expect(backend.calls.choicePosts).toHaveLength(1);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    // The split retry only re-runs the analysis: no second save of the same
    // durable decision and no execution.
    const retry = await screen.findByRole("button", {
      name: "保存并重新分析",
    });
    await user.click(retry);
    await waitFor(() => expect(backend.calls.analyzePosts).toHaveLength(1));
    expect(backend.calls.choicePosts).toHaveLength(1);

    await waitFor(() =>
      expect(
        screen.getByText(/已请求重新分析;新的精确方案就绪后会自动显示/),
      ).toBeVisible(),
    );
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("keeps the visible page on the same durable file when a newer summary reorders the items", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user);
    backend.state.flipPreviewOnAnalyze = true;
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    expect(within(card()).getByText("Movie.01.mkv")).toBeVisible();

    await openCorrection(user);
    await user.selectOptions(
      screen.getByLabelText("元数据身份 Movie.01.mkv"),
      "tmdb/129/movie",
    );
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));

    // The re-analysis links a second summary whose item order is reversed.
    // The card must follow the durable itemId: same file, new position.
    await waitFor(
      () =>
        expect(
          screen.getByRole("heading", { name: /第 10 \/ 10 个/ }),
        ).toBeVisible(),
      { timeout: 10_000 },
    );
    expect(within(card()).getByText("Movie.01.mkv")).toBeVisible();
    expect(within(card()).queryByText("Movie.02.mkv")).toBeNull();
    expect(backend.calls.executePosts).toHaveLength(0);

    // The superseded per-file authorization state cannot silently confirm the
    // new summary: no Execute has happened and the confirmation must be
    // entered again explicitly.
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    expect(
      screen.getByRole("button", { name: "确认整理 10 项" }),
    ).toBeEnabled();
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(
      screen.queryByRole("dialog", { name: "整理所选文件" }),
    ).toBeVisible();
  }, 30_000);

  it("never retries an unknown Execute: only the bounded admission read proves the outcome, then hands off", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user);
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    // The Execute response is lost to a 503 after the backend keeps its own
    // durable state; the card must keep the unknown submission instead of
    // resubmitting or closing.
    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    let executeFailed = false;
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/execute") && !executeFailed) {
        executeFailed = true;
        original(input, init);
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return original(input, init);
    });

    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    await user.click(screen.getByRole("button", { name: "确认整理 10 项" }));

    expect(backend.calls.executePosts).toHaveLength(1);
    // The saved request is read automatically; no manual reconciliation
    // button and no second Execute exist.
    expect(screen.queryByRole("button", { name: /核对提交结果/ })).toBeNull();
    await waitFor(() =>
      expect(backend.calls.admissionReads).toBeGreaterThanOrEqual(1),
    );
    expect(backend.calls.executePosts).toHaveLength(1); // never re-submitted
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    // The proved-off admission follows the same exact task-center handoff.
    await waitFor(() =>
      expect(backend.router.state.location.pathname).toBe("/operations"),
    );
    expect(backend.router.state.location.search).toMatchObject({
      run: "task-handoff-1",
    });
    expect(backend.calls.executePosts).toHaveLength(1);
    expect(backend.calls.admissionReads).toBeGreaterThanOrEqual(1);
  }, 30_000);

  it("keeps unknown batches independent: unready and past-admitted siblings stay outside the fresh confirmation", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user);
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    // Fresh entry first: the confirmed subset must contain only what the
    // operator can actually confirm right now.
    expect(backend.calls.executePosts).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const region = await screen.findByRole("region", { name: "整批复核" });
    expect(region).toHaveTextContent(/本次确认\s*10\s*项/);

    // Browse-only steps are still zero-execute even on the confirm step.
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    expect(backend.calls.executePosts).toHaveLength(0);

    // Excluding one file is an honest selection state, not a persistent
    // ignore: the confirmation counts exactly the remaining subset.
    await user.click(
      screen.getByRole("button", { name: `查看 ${filename(0)}` }),
    );
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    await user.click(
      screen.getByRole("checkbox", { name: "纳入 Movie.01.mkv" }),
    );
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    const confirm9 = screen.getByRole("button", { name: "确认整理 9 项" });
    expect(confirm9).toBeEnabled();
    // The excluded sibling is listed as "暂不纳入(now)", not silently lost.
    await screen.findByText("未纳入本次确认的文件(1 项)");
    expect(backend.calls.executePosts).toHaveLength(0);

    // Deselect the remaining files one page at a time; the count follows the
    // exact subset and drops to an explicit, disabled 0 state.
    for (let index = 1; index < FILE_COUNT; index += 1) {
      await user.click(screen.getByRole("button", { name: "返回整理概览" }));
      await screen.findByRole("region", { name: "本次整理概览" });
      // Each pass opens exactly the file this pass excludes.
      await user.click(
        screen.getByRole("button", { name: `查看 ${filename(index)}` }),
      );
      await screen.findByRole("heading", {
        name: new RegExp(`第 ${index + 1} \\/ 10 个`),
      });
      await user.click(
        screen.getByRole("checkbox", { name: `纳入 ${filename(index)}` }),
      );
      await user.click(screen.getByRole("button", { name: "返回整理概览" }));
      await screen.findByRole("region", { name: "本次整理概览" });
      await user.click(screen.getByRole("button", { name: /整批复核/ }));
      await screen.findByRole("region", { name: "整批复核" });
      const expected = FILE_COUNT - (index + 1);
      const button = screen.getByRole("button", {
        name: `确认整理 ${expected} 项`,
      });
      if (expected === 0) {
        // AC-2: the 0-selection state is real and honest — no confirmation is
        // possible, and nothing was executed while getting there.
        expect(button).toBeDisabled();
        expect(backend.calls.executePosts).toHaveLength(0);
        return;
      }
      expect(button).toBeEnabled();
    }
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("shows the compact first-plan preparation with only the source, admitted scope and close", async () => {
    const user = userEvent.setup();
    await openPreparationDialog(
      user,
      (value) => {
        value.state.queuedReads = 10;
        value.state.scopeSelections = [
          { kind: "file", path: "Movies/Movie.01.mkv" },
        ];
      },
      [filename(0)],
    );

    expect(
      await screen.findByText("申请已受理，正在排队等待处理"),
    ).toBeVisible();
    expect(card().querySelector(".mf-organize-status-spinner")).not.toBeNull();
    // The shared title is the only header copy during first-plan preparation.
    expect(
      within(card()).queryByText(/每次复核一个主文件及其关联附件/),
    ).toBeNull();
    expect(card()).toHaveTextContent("来源资源库");
    expect(card()).toHaveTextContent("library");
    expect(card()).toHaveTextContent("受理范围");
    expect(card()).toHaveTextContent("1 个文件");
    expect(card()).toHaveTextContent("准备进度");
    expect(card()).toHaveTextContent("尚未产生主文件数量");
    // The baseline stage card, diagnostics and Worker box are gone.
    expect(card().querySelector(".mf-organize-stage-copy")).toBeNull();
    expect(screen.queryByText(/准备诊断/)).toBeNull();
    expect(screen.queryByText(/处理 Worker 暂不可用/)).toBeNull();
    expect(screen.queryByRole("region", { name: "排除与等待原因" })).toBeNull();
    expect(screen.queryByText("已完整遍历所选范围。")).toBeNull();
    expect(screen.queryByText(/第 0 \/ 0 个/)).toBeNull();
    expect(screen.queryByRole("button", { name: /整批复核/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "下一项" })).toBeNull();

    const scopeSummary = within(card()).getByText("查看确切路径（1 项）");
    const scopeDetails = scopeSummary.closest("details");
    expect(scopeDetails?.open).toBe(false);
    await user.click(scopeSummary);
    expect(
      within(scopeDetails as HTMLElement).getByText("Movies/Movie.01.mkv"),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "关闭" })).toBeVisible();
  }, 20_000);

  it("presents a mixed scope, split source/target and a scan-friendly batch summary", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.requireOverwrite = true;
      },
      [filename(0)],
    );

    await screen.findByRole("heading", { name: /第 1 \/ 1 个/ });
    const sourceTerm = within(card()).getByText("来源", {
      selector: ".mf-organize-source-fact dt",
    });
    const targetTerm = within(card()).getByText("目标", {
      selector: ".mf-organize-target-fact dt",
    });
    const sourceRow = sourceTerm.closest("div");
    const targetRow = targetTerm.closest("div");
    expect(sourceRow).not.toBe(targetRow);
    expect(sourceRow).toHaveTextContent("source:Movies/Movie.01.mkv");
    expect(targetRow).toHaveTextContent("target:Movies/Movie.01.mkv");

    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const region = await screen.findByRole("region", { name: "整批复核" });
    expect(region).toHaveTextContent(/本次确认\s*1\s*项/);
    expect(region).toHaveTextContent(/未纳入\s*0\s*项/);
    expect(card()).toHaveTextContent("来源影响：移动成功后原位置不再保留");

    const batchList = await screen.findByRole("region", {
      name: "来源与目标",
    });
    const planDiagnostics = within(card())
      .getByText(/方案 preview-1/)
      .closest("details");
    expect(planDiagnostics).toHaveClass("mf-organize-plan-diagnostics");
    expect(
      batchList.compareDocumentPosition(planDiagnostics as Node) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      within(batchList).getByText("Movie.01.mkv", {
        selector: ".mf-organize-batch-file",
      }),
    ).toBeVisible();
    const batchFile = within(batchList).getByText("Movie.01.mkv", {
      selector: ".mf-organize-batch-file",
    });
    expect(batchFile.closest("button")).toBeNull();
    expect(batchList).toHaveTextContent("按当前方案");
    expect(batchList).toHaveTextContent("来源 资源库A：Movies/Movie.01.mkv");
    expect(batchList).toHaveTextContent("目标 电影库：Movie.01.mkv");
    expect(
      within(batchList).getByText("移动", {
        selector: ".mf-organize-batch-operation",
      }),
    ).toBeVisible();
    await user.click(batchFile);
    expect(screen.getByRole("region", { name: "整批复核" })).toBeVisible();
    expect(
      within(card()).getByText(/暂不能确认：替换已有目标文件需要明确授权/),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "确认整理 1 项" }),
    ).toBeDisabled();
    expect(backend.calls.executePosts).toHaveLength(0);

    await user.click(
      screen.getByRole("checkbox", {
        name: "我确认允许按已审阅方案替换现有目标文件",
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByText(/暂不能确认：替换已有目标文件需要明确授权/),
      ).toBeNull(),
    );
    expect(screen.getByRole("button", { name: "确认整理 1 项" })).toBeEnabled();
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 20_000);

  it("counts a refused selected sibling beside the admitted preparation and batch scope", async () => {
    const user = userEvent.setup();
    const refusedName = filename(0);
    const admittedName = filename(1);
    const backend = await openPreparationDialog(
      user,
      (value) => {
        value.state.queuedReads = 1;
        value.state.previewItemPaths = [`Movies/${admittedName}`];
        value.state.scopeSelections = [
          { kind: "file", path: `Movies/${admittedName}` },
        ];
        value.state.refusedSelections = [
          {
            kind: "file",
            path: `Movies/${refusedName}`,
            code: "source_already_organizing",
            reason: "source_already_organizing",
            message:
              "the source is already owned by an unfinished organizing work",
            nextAction: "open the existing work to continue or cancel it",
            existingWorkId: "organize-task-1",
            existingWorkKind: "task",
          },
        ];
      },
      [refusedName, admittedName],
    );

    expect(
      await screen.findByText("申请已受理，正在排队等待处理"),
    ).toBeVisible();
    expect(card()).toHaveTextContent("1 个文件");
    expect(card()).toHaveTextContent("未受理 1 项");
    expect(card()).toHaveTextContent(
      "未受理 1 项；展开「受理范围」可核对每项原因和下一步。",
    );

    const scopeSummary = within(card()).getByText("查看确切路径（2 项）");
    const scopeDetails = scopeSummary.closest("details") as HTMLElement;
    await user.click(scopeSummary);
    expect(scopeDetails).toHaveTextContent(admittedName);
    expect(scopeDetails).toHaveTextContent(refusedName);
    expect(scopeDetails).toHaveTextContent("未受理");
    expect(scopeDetails).toHaveTextContent("已属于未结束的整理工作");
    expect(screen.queryByText(/未受理的所选条目/)).toBeNull();

    await enterFirstOverviewFile(user, /第 1 \/ 1 个/);
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const region = await screen.findByRole("region", { name: "整批复核" });
    const summary = region.querySelector(
      ".mf-organize-batch-summary",
    ) as HTMLElement;
    const fact = (term: string): HTMLElement =>
      within(summary)
        .getByText(term, { selector: "dt" })
        .closest("div") as HTMLElement;
    expect(fact("本次确认")).toHaveTextContent("1 项");
    expect(fact("未纳入")).toHaveTextContent("0 项");
    expect(within(card()).getByText("未受理的所选条目(1 项)")).toBeVisible();
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(backend.calls.analyzePosts).toHaveLength(0);
  }, 20_000);

  it("explains a first plan blocked by stale items without claiming it was superseded", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.previewCurrent = false;
        value.state.previewStaleTail = 1;
      },
      [filename(0), filename(1)],
    );

    // A stale tail is grouped under "待处理" before the ready file, so the
    // first overview row is that pending exact item, not array position one.
    await screen.findByRole("heading", { name: /第 2 \/ 2 个/ });
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    expect(within(card()).getByText("本次方案暂不能整体确认")).toBeVisible();
    expect(
      within(card()).getByText(/本次分析有 1 个文件未就绪或已失效/),
    ).toBeVisible();
    const blocker = within(card())
      .getByText(/^暂不能确认：/)
      .closest(".mf-organize-confirm-blocker") as HTMLElement;
    expect(blocker).toHaveTextContent("本次方案有 1 个文件未就绪或已失效");
    expect(blocker).toHaveTextContent("先返回逐项复核处理这些文件");
    expect(blocker).not.toHaveTextContent("已被更新取代");
    expect(
      screen.getByRole("button", { name: "确认整理 1 项" }),
    ).toBeDisabled();
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(backend.calls.analyzePosts).toHaveLength(0);

    const skippedSummary =
      within(card()).getByText("未纳入本次确认的文件(1 项)");
    await user.click(skippedSummary);
    expect(
      within(card()).getByText(
        /该文件已不在当前方案中；需要重新分析后才能再次核对或纳入/,
      ),
    ).toBeVisible();
    await user.click(
      within(card()).getByRole("button", { name: `查看 ${filename(1)}` }),
    );
    await screen.findByRole("heading", { name: /第 2 \/ 2 个/ });
    expect(within(card()).getAllByText(filename(1)).length).toBeGreaterThan(0);
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(backend.calls.analyzePosts).toHaveLength(0);
  }, 20_000);

  it("names a newer plan only when the latest durable plan differs", async () => {
    const user = userEvent.setup();
    await openDialog(
      user,
      (value) => {
        value.state.previewCurrent = false;
        value.state.previewStaleTail = 1;
        value.state.latestPlanPreviewId = "preview-newer";
      },
      [filename(0), filename(1)],
    );

    await screen.findByRole("heading", { name: /第 2 \/ 2 个/ });
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    expect(within(card()).getByText("摘要已不是当前方案")).toBeVisible();
    expect(
      within(card()).getByText(/此计划摘要已被更新的分析取代/),
    ).toBeVisible();
    expect(within(card()).getByText(/^暂不能确认：/)).toHaveTextContent(
      "此计划摘要已被更新取代",
    );
  }, 20_000);

  it("keeps polling an unchanged waiting preparation until the exact plan links", async () => {
    const user = userEvent.setup();
    await openPreparationDialog(user, (value) => {
      value.state.waitingReads = 3;
    });

    // The first read is an honest waiting state, and the interval keeps
    // reading the same unchanged document without needing a render.  The
    // discovered primary count is real, while no unknown percentage is shown.
    await screen.findByText("正在等待来源文件稳定");
    expect(await screen.findByText("准备进度")).toBeVisible();
    expect(screen.getByText(/已找到 10 个主文件/)).toBeVisible();
    expect(card()).not.toHaveTextContent("%");
    await enterFirstOverviewFile(user, /第 1 \/ 10 个/);
    expect(within(card()).getAllByText("Movie.01.mkv").length).toBeGreaterThan(
      0,
    );
  }, 20_000);

  it("keeps the same preparation open from the completed walk until its linked plan arrives", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(user, (value) => {
      // The real Worker publishes the completed walk first, then freezes and
      // enters analysis.  Neither intermediate state is the whole preparation.
      value.state.walkOnlyReads = 1;
      value.state.frozenOnlyReads = 3;
    });

    await screen.findByText("准备已完成，等待后台生成方案");
    // The completed walk has not frozen an intent yet: the analysis action is
    // not advertised, and the card must keep reading instead of settling here.
    expect(
      screen.queryByRole("button", { name: "运行分析并生成计划摘要" }),
    ).toBeNull();

    // The frozen intent is durable while the plan is still linking.  The card
    // keeps polling and then shows the linked plan without a second submit;
    // the Worker still owns this Task stage, so no second analysis action is
    // advertised while it works.
    await waitFor(
      () => expect(backend.state.discoveryReads).toBeGreaterThanOrEqual(2),
      { timeout: 5_000 },
    );
    expect(
      screen.queryByRole("button", { name: "运行分析并生成计划摘要" }),
    ).toBeNull();
    await enterFirstOverviewFile(user, /第 1 \/ 10 个/);
    expect(backend.state.discoveryReads).toBeGreaterThanOrEqual(3);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 20_000);

  it("keeps the source and admitted scope while the first summary read fails, then retries that same summary", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(user, (value) => {
      value.state.failFirstPreviewRead = true;
    });

    expect(await screen.findByText("计划摘要暂时无法读取")).toBeVisible();
    expect(card()).toHaveTextContent("来源资源库");
    expect(card()).toHaveTextContent("library");
    expect(card()).toHaveTextContent("受理范围");
    expect(card()).not.toHaveTextContent(/每次复核一个主文件及其关联附件/);
    expect(card().querySelector(".mf-organize-preparation-spinner")).toBeNull();
    expect(screen.queryByRole("heading", { name: /第 1 \/ 10 个/ })).toBeNull();
    expect(screen.getByText(/已保存的准备与选择保持不变/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "重新读取计划摘要" }));
    await enterFirstOverviewFile(user, /第 1 \/ 10 个/);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 20_000);

  it("ends the first-plan wait with the real exclusions when the folder has no primary file", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(
      user,
      (value) => {
        value.state.zeroPrimary = true;
      },
      ["Movies"],
    );

    expect(await screen.findByText("未找到可整理的主文件")).toBeVisible();
    expect(card().querySelector(".mf-organize-preparation-spinner")).toBeNull();
    expect(screen.getByText(/已排除 1 个条目：非媒体扩展名 × 1/)).toBeVisible();
    expect(
      screen.getByText("本次没有生成整理方案，也没有整理任何文件。"),
    ).toBeVisible();
    expect(
      screen.getByText(
        "请关闭本弹窗返回原文件页，调整所选范围后重新发起整理。",
      ),
    ).toBeVisible();
    expect(screen.queryByText(/未受影响的已受理条目会继续准备/)).toBeNull();
    expect(
      screen.queryByRole("button", { name: "运行分析并生成计划摘要" }),
    ).toBeNull();
    expect(screen.queryByRole("heading", { name: /第 1 \/ 10 个/ })).toBeNull();

    await user.click(screen.getByRole("button", { name: "关闭" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    expect(backend.calls.discoveryPosts).toHaveLength(1);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 20_000);

  it("keeps the completed zero-primary result when the Worker heartbeat has expired", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(
      user,
      (value) => {
        value.state.zeroPrimary = true;
        value.state.zeroPrimaryWorkerUnavailable = true;
      },
      ["Movies"],
    );

    // This is the same durable preparation a refresh reads after the Worker
    // stopped: its own completed result, not the missing Worker, owns the
    // headline and the next step.
    expect(await screen.findByText("未找到可整理的主文件")).toBeVisible();
    expect(screen.queryByText("后台暂不可用")).toBeNull();
    expect(screen.queryByText("请求已保存，请联系管理员。")).toBeNull();
    expect(card().querySelector(".mf-organize-preparation-spinner")).toBeNull();
    expect(screen.getByText(/已排除 1 个条目：非媒体扩展名 × 1/)).toBeVisible();
    expect(
      screen.getByText("本次没有生成整理方案，也没有整理任何文件。"),
    ).toBeVisible();
    expect(
      screen.getByText(
        "请关闭本弹窗返回原文件页，调整所选范围后重新发起整理。",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "运行分析并生成计划摘要" }),
    ).toBeNull();
    expect(backend.calls.discoveryPosts).toHaveLength(1);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "关闭" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    expect(backend.calls.discoveryPosts).toHaveLength(1);
  }, 20_000);

  it("replaces the spinner with the saved-request Worker notice and recovers by polling the same preparation", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(user, (value) => {
      value.state.workerUnavailableReads = 1;
    });

    expect(await screen.findByText("后台暂不可用")).toBeVisible();
    expect(
      screen.getByText(
        "原请求已保存，当前没有可用后台；联系管理员恢复后即可继续读取这次准备。",
      ),
    ).toBeVisible();
    expect(card().querySelector(".mf-organize-preparation-spinner")).toBeNull();
    expect(card().querySelector(".mf-organize-stage-copy")).toBeNull();
    expect(screen.queryByText(/处理 Worker 暂不可用/)).toBeNull();
    expect(screen.queryByText(/准备诊断/)).toBeNull();
    expect(backend.calls.discoveryPosts).toHaveLength(1);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    // The same exact preparation is re-read in place; the plan then opens the
    // ordinary per-file review without another admission.
    await enterFirstOverviewFile(user, /第 1 \/ 10 个/);
    expect(backend.calls.discoveryPosts).toHaveLength(1);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 20_000);

  it("reports a rejected preparation analysis nearby and re-reads the same updated preparation", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(user, (value) => {
      // The Task has already settled into its human-waiting recovery boundary,
      // but the stale preparation read still shows the frozen walk while its
      // real plan is already linked in durable state.
      value.state.frozenOnlyReads = 100;
      value.state.manualAnalysisRecovery = true;
      value.state.rejectAnalysisOnce = true;
    });

    await screen.findByText("等待重新运行分析");
    const analyze = await screen.findByRole(
      "button",
      { name: "运行分析并生成计划摘要" },
      { timeout: 5_000 },
    );
    await user.click(analyze);
    await waitFor(() => expect(backend.calls.analyzePosts).toHaveLength(1));

    // The rejection names the durable refusal and the zero-mutation fact; the
    // same preparation is then re-read instead of asking for a second submit.
    await screen.findByText(/分析请求未获受理\(discovery_conflict\)/);
    await screen.findByText(/没有执行任何整理/);
    await enterFirstOverviewFile(user, /第 1 \/ 10 个/);
    expect(backend.calls.analyzePosts).toHaveLength(1);
    expect(backend.calls.choicePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("shows the preparation analysis request as accepted while the same preparation links its plan", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(user, (value) => {
      value.state.frozenOnlyReads = 100;
      value.state.manualAnalysisRecovery = true;
      value.state.analyzeShowsAnalyzing = true;
    });

    await screen.findByText("等待重新运行分析");
    const analyze = await screen.findByRole(
      "button",
      { name: "运行分析并生成计划摘要" },
      { timeout: 5_000 },
    );
    await user.click(analyze);
    await screen.findByText(/零变更分析正在运行/);
    expect(backend.calls.analyzePosts).toHaveLength(1);

    await enterFirstOverviewFile(user, /第 1 \/ 10 个/);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 20_000);

  it("keeps an ended flow as a read-only original summary with no confirmation", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(user, (value) => {
      value.state.endedFlow = true;
    });

    await screen.findByText("本次整理工作已结束");
    const history = await screen.findByRole("region", {
      name: "只读原计划摘要",
    });
    expect(within(history).getByText(/方案 preview-1/)).toBeVisible();
    expect(
      within(history).getAllByText(/Movie\.01\.mkv/).length,
    ).toBeGreaterThan(0);
    expect(
      within(history).getAllByText(/Movie\.10\.mkv/).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /确认整理/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "保存并重新分析" })).toBeNull();
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(backend.calls.analyzePosts).toHaveLength(0);
  }, 30_000);

  it("shows the bounded primary-limit message for a truncated ended flow", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(user, (value) => {
      value.state.endedFlow = true;
      value.state.primaryLimit = true;
    });

    await screen.findByText("本次整理工作已结束");
    expect(
      await screen.findByText(
        "本次未执行整理。最多支持 100 个主文件，请缩小选择范围后重新发起。",
      ),
    ).toBeVisible();
    // This exact refusal never produced a plan summary, so the card must not
    // claim that a saved summary is retained as read-only history.
    expect(screen.queryByText(/原计划摘要保留为只读历史/)).toBeNull();
    expect(screen.queryByText(/本次整理从未生成过计划摘要/)).toBeNull();
    expect(screen.queryByRole("region", { name: "只读原计划摘要" })).toBeNull();
    expect(screen.queryByRole("button", { name: /确认整理/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "保存并重新分析" })).toBeNull();
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(backend.calls.analyzePosts).toHaveLength(0);
  }, 30_000);

  it("keeps polling a primary-limit preparation until its Task settles", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(user, (value) => {
      value.state.primaryLimit = true;
      value.state.primaryLimitSettlementReads = 3;
    });

    // The walk's refusal is durable while settlement is still pending.  The
    // card says so honestly and keeps reading the same preparation instead of
    // settling on the truncated intermediate state.
    await screen.findByText(
      "检查已在主文件数量上限处停止；正在结束关联任务，结束后请缩小选择范围重新发起。",
      {},
      { timeout: 15_000 },
    );
    expect(screen.queryByText("本次整理工作已结束")).toBeNull();

    // The settlement commits on a later read; the same mounted card follows
    // it to the factual failed end with no second submission.
    await screen.findByText("本次整理工作已结束", {}, { timeout: 15_000 });
    expect(
      screen.getByText(
        "本次未执行整理。最多支持 100 个主文件，请缩小选择范围后重新发起。",
      ),
    ).toBeVisible();
    expect(screen.queryByText(/原计划摘要保留为只读历史/)).toBeNull();
    expect(backend.calls.discoveryPosts).toHaveLength(1);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(backend.state.discoveryReads).toBeGreaterThanOrEqual(3);
  }, 30_000);

  it("renders the linked plan as read-only history when an ended flow kept it", async () => {
    const user = userEvent.setup();
    await openPreparationDialog(user, (value) => {
      value.state.endedFlow = true;
      value.state.endedFlowKeepsPreview = true;
    });

    await screen.findByText("本次整理工作已结束");
    const history = await screen.findByRole("region", {
      name: "只读原计划摘要",
    });
    expect(within(history).getByText(/方案 preview-1/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /确认整理/ })).toBeNull();
  }, 20_000);

  it("keeps the router-owned Files history entry when the admitted card enters and leaves the address", async () => {
    // A real Files entry carries the router's own history index/key.  The
    // admitted preparation identity must join that same entry: replacing the
    // entry with a fresh/empty state makes a later browser Back look like an
    // unknown traversal, so a cancelled Back could no longer restore this
    // exact preparation address and a reload lost the card (Slice53 B P1).
    const routerState = {
      __TSR_index: 2,
      key: "router-entry",
      __TSR_key: "router-entry",
    };
    window.history.replaceState(
      routerState,
      "",
      "/resourcelib/files?resourceLibraryId=source",
    );
    const user = userEvent.setup();
    await openDialog(user);
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    const search = () => new URLSearchParams(window.location.search);
    await waitFor(() =>
      expect(search().get("organizeDiscovery")).toBe(DISCOVERY_ID),
    );
    expect(window.history.state).toEqual(routerState);

    await user.click(screen.getByRole("button", { name: "关闭整理弹窗" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    expect(search().get("organizeDiscovery")).toBeNull();
    // Closing removes only the bounded preparation key, never the router's
    // history entry identity.
    expect(window.history.state).toEqual(routerState);
  }, 30_000);

  it("closes on Escape when nothing is pending and returns focus to the invoking control", async () => {
    const user = userEvent.setup();
    await openDialog(user);
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    // The focus return contract relands on the real control that opened the
    // card — the batch entry itself.
    await waitFor(() =>
      expect((document.activeElement as HTMLElement | null)?.textContent).toBe(
        "批量整理",
      ),
    );
  }, 30_000);

  it("reconciles the original submission identity after a sibling re-analysis publishes a newer summary", async () => {
    const user = userEvent.setup();
    // A53-01: real Files entry with exactly two files, one confirmed and
    // answered only with a lost response; then the untouched sibling gets a
    // legal correction + re-analysis that publishes a newer summary before
    // the operator reconciles the original request.
    const backend = await openDialog(
      user,
      (value) => {
        value.state.flipPreviewOnAnalyze = true;
        value.state.requireOverwrite = true;
        value.state.failAdmissionReads = Number.MAX_SAFE_INTEGER;
      },
      [filename(0), filename(1)],
    );
    await screen.findByRole("heading", { name: /第 1 \/ 2 个/ });
    expect(within(card()).getByText("Movie.01.mkv")).toBeVisible();

    // Only Movie.01 is confirmed; the sibling stays out of this submission.
    await user.click(screen.getByRole("button", { name: "下一项" }));
    await screen.findByRole("heading", { name: /第 2 \/ 2 个/ });
    await user.click(
      screen.getByRole("checkbox", { name: "纳入 Movie.02.mkv" }),
    );
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    expect(screen.getByRole("region", { name: "整批复核" })).toHaveTextContent(
      /本次确认\s*1\s*项/,
    );
    const overwrite = screen.getByRole("checkbox", {
      name: "我确认允许按已审阅方案替换现有目标文件",
    });
    expect(overwrite).not.toBeChecked();
    await user.click(overwrite);
    await waitFor(() => expect(overwrite).toBeChecked());

    // The backend admits durably; only the browser-visible response is lost.
    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    let executeFailed = false;
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/execute") && !executeFailed) {
        executeFailed = true;
        original(input, init);
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return original(input, init);
    });

    const confirm = screen.getByRole("button", { name: "确认整理 1 项" });
    await waitFor(() => expect(confirm).toBeEnabled());
    await user.click(confirm);
    await screen.findByText(/原整理提交暂未确认|正在自动核对原整理提交/);
    expect(backend.calls.executePosts).toHaveLength(1);
    expect(backend.calls.executePreviewIds).toEqual([PREVIEW_ID]);
    expect(backend.calls.executePosts[0]).toMatchObject({
      confirmation: true,
      itemIds: ["item-1"],
      expectedIntentVersion: 7,
      allowOverwrite: true,
      allowSourceCleanup: false,
    });

    // The saved original request is read automatically; there is no manual
    // reconciliation control and no second Execute.
    expect(screen.queryByRole("button", { name: /核对提交结果/ })).toBeNull();
    expect(
      screen.getByRole("button", { name: "确认整理 1 项" }),
    ).toBeDisabled();

    // The first bounded read fails. The original unknown restriction stays,
    // and no denial from another summary is invented.
    await waitFor(() =>
      expect(backend.calls.admissionRequests.length).toBeGreaterThanOrEqual(1),
    );
    await screen.findByText(/读取暂时失败|暂未确认/);
    expect(screen.queryByText(/没有被受理/)).toBeNull();
    expect(screen.queryByText(/没有发生整理变更/)).toBeNull();
    expect(backend.calls.admissionRequests[0]?.previewId).toBe(PREVIEW_ID);
    expect(backend.calls.executePosts).toHaveLength(1);

    // The untouched sibling is corrected (RecognitionType C) and re-analyzed:
    // a newer exact summary appears while the original request stays unknown.
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(
      screen.getByRole("button", { name: `查看 ${filename(1)}` }),
    );
    await screen.findByRole("heading", { name: /第 2 \/ 2 个/ });
    await user.selectOptions(
      screen.getByLabelText(`识别类型 ${filename(1)}`),
      "C",
    );
    const save = screen.getByRole("button", { name: "保存并重新分析" });
    await waitFor(() => expect(save).toBeEnabled());
    await user.click(save);
    await waitFor(() => expect(backend.calls.choicePosts).toHaveLength(1));
    await waitFor(() => expect(backend.calls.analyzePosts).toHaveLength(1));

    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    // The newer summary is visible and owned by the current review.
    await screen.findByText(/方案 preview-2/);

    // Its own overwrite authorization starts fresh — the original request's
    // dangerous authorization is not inherited by the new plan.
    const freshOverwrite = screen.getByRole("checkbox", {
      name: "我确认允许按已审阅方案替换现有目标文件",
    });
    expect(freshOverwrite).not.toBeChecked();
    expect(
      screen.getByRole("button", { name: "确认整理 1 项" }),
    ).toBeDisabled();
    expect(backend.calls.executePosts).toHaveLength(1);

    // Restore the read surface: the automatic check now proves the original
    // request and hands off the exact original Task without any manual click.
    backend.state.failAdmissionReads = 0;
    await waitFor(
      () =>
        expect(
          screen.queryByRole("dialog", { name: "整理所选文件" }),
        ).toBeNull(),
      { timeout: 15_000 },
    );
    await waitFor(() =>
      expect(backend.router.state.location.pathname).toBe("/operations"),
    );
    expect(backend.router.state.location.search).toMatchObject({
      run: "task-handoff-1",
    });

    // Exactly one Execute; every automatic reconciliation request carries
    // exactly the original identity, item by item, and never the newer
    // summary.
    expect(backend.calls.executePosts).toHaveLength(1);
    const executed = backend.calls.executePosts[0]!;
    expect(backend.calls.admissionRequests.length).toBeGreaterThanOrEqual(2);
    for (const read of backend.calls.admissionRequests) {
      expect(read.previewId).toBe(PREVIEW_ID);
      expect(read.params["itemIds"]).toBe(
        (executed["itemIds"] as string[]).join(","),
      );
      expect(read.params["expectedIntentVersion"]).toBe(
        String(executed["expectedIntentVersion"]),
      );
      expect(read.params["allowOverwrite"]).toBe("true");
      expect(read.params["allowSourceCleanup"]).toBe("false");
    }
    expect(
      backend.calls.admissionRequests.some(
        (read) => read.previewId === "preview-2",
      ),
    ).toBe(false);
  }, 30_000);

  it("Task59.1 Files prepares through the same dialog overview, opens one exact file and returns with focus", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.previewAttachmentCount = 2;
      },
      [filename(0)],
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(
      within(overview).getByRole("heading", { name: "本次整理概览" }),
    ).toBeVisible();
    const count = (term: string): string => {
      const row = within(overview)
        .getByText(term, { selector: "dt" })
        .closest("div") as HTMLElement;
      return row.querySelector("dd")?.textContent ?? "";
    };
    expect(count("已选 / 可确认")).toBe("1 / 1");
    expect(count("需要处理")).toBe("0");
    expect(count("已有记录")).toBe("0");
    const readyRow = within(overview)
      .getByRole("button", { name: `查看 ${filename(0)}` })
      .closest("li") as HTMLElement;
    expect(within(readyRow).getByText("移动 · One")).toBeVisible();
    expect(within(readyRow).queryByText("查看精确路径与方案")).toBeNull();
    expect(within(readyRow).queryByText(/无关联附件/)).toBeNull();

    await user.click(
      within(overview).getByRole("button", { name: `查看 ${filename(0)}` }),
    );
    await screen.findByRole("heading", { name: /第 1 \/ 1 个/ });
    expect(card()).toHaveTextContent(`source:Movies/${filename(0)}`);
    await user.click(
      screen.getByRole("checkbox", { name: `纳入 ${filename(0)}` }),
    );
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));

    const returned = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const fileButton = within(returned).getByRole("button", {
      name: `查看 ${filename(0)}`,
    });
    await waitFor(() => expect(document.activeElement).toBe(fileButton));
    const returnedCount = (term: string): string => {
      const row = within(returned)
        .getByText(term, { selector: "dt" })
        .closest("div") as HTMLElement;
      return row.querySelector("dd")?.textContent ?? "";
    };
    expect(returnedCount("已选 / 可确认")).toBe("0 / 1");
    // Excluding the only ready file changes the selection, not the file's
    // own eligibility: the summary stays confirmable for any ready subset.
    expect(
      screen.getByRole("button", { name: "整批复核(已选 0 项)" }),
    ).toBeVisible();
    expect(within(card()).queryByText(/此刻可确认/)).toBeNull();
    expect(returnedCount("需要处理")).toBe("0");

    // The exact batch review names the source, destination, operation and
    // attachments; entering it is still zero-mutation, zero-execute.
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const confirm = await screen.findByRole("region", { name: "整批复核" });
    expect(confirm).toHaveTextContent(/本次确认\s*0\s*项/);
    expect(screen.queryByRole("button", { name: /确认整理 [1-9]/ })).toBeNull();
    expect(backend.calls.executePosts).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(
      screen.getByRole("button", { name: `查看 ${filename(0)}` }),
    );
    await user.click(
      screen.getByRole("checkbox", { name: `纳入 ${filename(0)}` }),
    );
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const listed = await screen.findByRole("region", {
      name: "来源与目标",
    });
    expect(listed).toHaveTextContent(`来源 资源库A：Movies/${filename(0)}`);
    expect(listed).toHaveTextContent("目标 电影库：Movie.01.mkv");
    expect(listed).toHaveTextContent("中文字幕（.zh.srt）");
    expect(listed).toHaveTextContent("附件 2 个");
    await user.click(
      within(listed).getByText(/展开核对来源、目标、操作与原因/),
    );
    const firstAttachment = within(listed)
      .getAllByText(/subtitle\(zh\) · 移动/)[0]
      ?.closest("li") as HTMLElement;
    expect(firstAttachment).toHaveTextContent(
      "source:Movies/Movie.01.1.srt → target:Movies/Movie.01.1.srt",
    );
    const secondAttachment = within(listed)
      .getAllByText(/subtitle\(zh\) · 移动/)[1]
      ?.closest("li") as HTMLElement;
    expect(secondAttachment).toHaveTextContent(
      "source:Movies/Movie.01.2.srt → target:Movies/Movie.01.2.srt",
    );
    expect(secondAttachment).toHaveTextContent(
      "排除原因：target already exists",
    );
    expect(secondAttachment).toHaveTextContent(
      "异常/下一步：rename the attachment target",
    );
    expect(within(listed).getAllByText(/subtitle\(zh\) · 移动/)).toHaveLength(
      2,
    );
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("keeps exact Storage paths when the reviewed library identity cannot be confirmed", async () => {
    const user = userEvent.setup();
    await openDialog(
      user,
      (value) => {
        value.state.mismatchedLibraries = true;
      },
      [filename(0)],
    );

    await screen.findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const listed = await screen.findByRole("region", {
      name: "来源与目标",
    });
    expect(listed).toHaveTextContent("来源 source:Movies/Movie.01.mkv");
    expect(listed).toHaveTextContent("目标 target:Movies/Movie.01.mkv");
    expect(listed).not.toHaveTextContent("资源库A：");
    expect(listed).not.toHaveTextContent("电影库：");
  }, 20_000);

  it("Task59.1 names a Files batch target even when it repeats the library root name", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.libraryPrefixedTargets = true;
      },
      [filename(0)],
    );

    await screen.findByRole("heading", { name: /第 1 \/ 1 个/ });
    const targetRow = within(card())
      .getByText("目标", { selector: ".mf-organize-target-fact dt" })
      .closest("div");
    expect(targetRow).toHaveTextContent(
      "target:Movies/Movies/Anime/Movie.01.mkv",
    );
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const listed = await screen.findByRole("region", {
      name: "来源与目标",
    });
    expect(listed).toHaveTextContent("目标 电影库：Movies/Anime/Movie.01.mkv");
    expect(listed).not.toHaveTextContent("目标 电影库：Anime/");
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 20_000);

  it("Task59.1 keeps the exact Storage target when the plan is outside the reviewed library root", async () => {
    const user = userEvent.setup();
    await openDialog(
      user,
      (value) => {
        value.state.foreignTargetRoot = true;
      },
      [filename(0)],
    );

    await screen.findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const listed = await screen.findByRole("region", {
      name: "来源与目标",
    });
    expect(listed).toHaveTextContent("目标 target:Archive/Movie.01.mkv");
    expect(listed).not.toHaveTextContent("电影库：");
  }, 20_000);

  it("Task59.1 Files keeps an unchecked ready sibling in the confirmable count", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      () => undefined,
      [filename(0), filename(1)],
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const count = (term: string): string => {
      const row = within(overview)
        .getByText(term, { selector: "dt" })
        .closest("div") as HTMLElement;
      return row.querySelector("dd")?.textContent ?? "";
    };
    expect(count("已选 / 可确认")).toBe("2 / 2");
    expect(
      screen.getByRole("button", { name: "整批复核(已选 2 项)" }),
    ).toBeVisible();

    await user.click(
      within(overview).getByRole("button", {
        name: `查看 ${filename(1)}`,
      }),
    );
    await screen.findByRole("heading", { name: /第 2 \/ 2 个/ });
    await user.click(
      screen.getByRole("checkbox", { name: `纳入 ${filename(1)}` }),
    );
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));

    const returned = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const returnedCount = (term: string): string => {
      const row = within(returned)
        .getByText(term, { selector: "dt" })
        .closest("div") as HTMLElement;
      return row.querySelector("dd")?.textContent ?? "";
    };
    // The unchecked file is still a ready, confirmable sibling; only the
    // exact selected subset shrinks.
    expect(returnedCount("已选 / 可确认")).toBe("1 / 2");
    const readyRow = within(returned)
      .getByRole("button", { name: `查看 ${filename(1)}` })
      .closest("li") as HTMLElement;
    expect(readyRow).not.toBeNull();
    expect(within(readyRow as HTMLElement).getByText("可确认")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "整批复核(已选 1 项)" }),
    ).toBeVisible();

    // The batch still submits only the exact selected file, never the sibling
    // merely because it remains eligible in the summary.
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const batch = await screen.findByRole("region", { name: "整批复核" });
    const summary = within(batch).getByText("本次确认").closest("div");
    expect(summary?.querySelector("dd")?.textContent).toBe("1 项");
    expect(screen.getByRole("button", { name: "确认整理 1 项" })).toBeEnabled();
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 shows a metadata provider technical failure as its own stage, not a candidate decision", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.metadataProviderFailure = true;
      },
      [filename(0), filename(1)],
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const count = (term: string): string => {
      const row = within(overview)
        .getByText(term, { selector: "dt" })
        .closest("div") as HTMLElement;
      return row.querySelector("dd")?.textContent ?? "";
    };
    expect(count("需要处理")).toBe("1");
    expect(count("已选 / 可确认")).toBe("1 / 1");

    const failedRow = within(overview)
      .getByRole("button", { name: `查看 ${filename(0)}` })
      .closest("li") as HTMLElement;
    expect(failedRow).toHaveTextContent("元数据服务技术失败");
    expect(failedRow).toHaveTextContent(/Metadata Provider/);
    expect(failedRow).toHaveTextContent(/原整理准备任务 organize-task-1/);
    expect(failedRow).not.toHaveTextContent("需要处理元数据候选");
    expect(failedRow).not.toHaveTextContent("Storage failure");
    const readyRow = within(overview)
      .getByRole("button", { name: `查看 ${filename(1)}` })
      .closest("li") as HTMLElement;
    expect(readyRow).toHaveTextContent("已纳入");

    await user.click(
      within(overview).getByRole("button", {
        name: `查看 ${filename(0)}`,
      }),
    );
    await screen.findByRole("heading", { name: /第 1 \/ 2 个/ });
    const status = within(card()).getByRole("region", { name: "当前状态" });
    expect(status).toHaveTextContent("元数据服务技术失败");
    expect(status).toHaveTextContent(/Metadata Provider/);
    expect(status).toHaveTextContent(/任务中心/);
    expect(status).not.toHaveTextContent("重新分析同一准备");
    expect(card()).not.toHaveTextContent("Storage failure");
    expect(within(card()).queryByRole("radio", { name: /候选/ })).toBeNull();
    expect(
      within(card()).queryByRole("button", { name: "保存并重新分析" }),
    ).toBeNull();
    expect(backend.calls.executePosts).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const listed = await screen.findByRole("region", {
      name: "来源与目标",
    });
    expect(listed).toHaveTextContent(filename(1));
    expect(listed).not.toHaveTextContent(filename(0));
    await user.click(screen.getByText(`未纳入本次确认的文件(1 项)`));
    const skippedRow = within(card())
      .getByRole("button", { name: `查看 ${filename(0)}` })
      .closest("li") as HTMLElement;
    expect(skippedRow).toHaveTextContent("元数据服务技术失败");
    expect(skippedRow).toHaveTextContent(/Metadata Provider/);
    expect(skippedRow).toHaveTextContent(/原整理准备任务 organize-task-1/);
    expect(skippedRow).not.toHaveTextContent("重新分析同一准备");
    expect(skippedRow).not.toHaveTextContent("Storage failure");
    expect(screen.getByRole("button", { name: "确认整理 1 项" })).toBeEnabled();
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 keeps the same metadata technical failure in the ended read-only summary", async () => {
    const user = userEvent.setup();
    const backend = await openPreparationDialog(
      user,
      (value) => {
        value.state.metadataProviderFailure = true;
        value.state.previewItemPaths = [`Movies/${filename(0)}`];
        value.state.endedFlow = true;
        value.state.endedFlowKeepsPreview = true;
      },
      [filename(0)],
    );

    await screen.findByText("本次整理工作已结束");
    const history = await screen.findByRole("region", {
      name: "只读原计划摘要",
    });
    expect(history).toHaveTextContent("元数据服务技术失败");
    expect(history).toHaveTextContent(/Metadata Provider/);
    expect(history).toHaveTextContent(/重新选择该文件发起新的整理/);
    expect(history).not.toHaveTextContent("重新分析同一准备");
    expect(history).not.toHaveTextContent("Storage failure");
    expect(
      within(history).queryByRole("button", { name: /确认整理/ }),
    ).toBeNull();
    expect(screen.getByRole("button", { name: "关闭" })).toBeEnabled();
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 20_000);

  it("Task59.1 returns to the overview only after this item's new ready plan is read back", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.flipPreviewOnAnalyze = true;
      value.state.secondPlanKind = "ready";
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    await openCorrection(user);
    const identity = screen.getByLabelText(`元数据身份 ${filename(0)}`);
    const alternate = within(identity)
      .getAllByRole("option")
      .at(2)
      ?.getAttribute("value");
    await user.selectOptions(identity, alternate as string);
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));
    await waitFor(() => expect(backend.calls.choicePosts).toHaveLength(1));
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(overview).toHaveTextContent(
      `「${filename(0)}」已可确认。整理方案已更新，整理尚未提交。`,
    );
    expect(overview).toHaveTextContent("Resolved Movie");
    expect(backend.calls.choicePosts).toHaveLength(1);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 returns to the overview when the accepted analysis response is lost", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.flipPreviewOnAnalyze = true;
      value.state.secondPlanKind = "ready";
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    await openCorrection(user);
    const identity = screen.getByLabelText(`元数据身份 ${filename(0)}`);
    const alternate = within(identity)
      .getAllByRole("option")
      .at(2)
      ?.getAttribute("value");
    await user.selectOptions(identity, alternate as string);

    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    let analyzeResponseLost = false;
    let analysisAccepted = false;
    let releasePreparationRead = () => {};
    const preparationReadGate = new Promise<void>((resolve) => {
      releasePreparationRead = resolve;
    });
    let markPreparationReadStarted: (() => void) | null = null;
    const preparationReadStarted = new Promise<void>((resolve) => {
      markPreparationReadStarted = resolve;
    });
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/analyze") && !analyzeResponseLost) {
        analyzeResponseLost = true;
        // The real API accepts and publishes the same analysis; only this
        // browser's copy of the response is dropped.
        await original(input, init);
        analysisAccepted = true;
        throw new TypeError("Failed to fetch");
      }
      if (
        analysisAccepted &&
        url.endsWith(`/api/operations/organize/discoveries/${DISCOVERY_ID}`)
      ) {
        markPreparationReadStarted?.();
        await preparationReadGate;
      }
      return original(input, init);
    });

    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));
    await waitFor(() => expect(backend.calls.analyzePosts).toHaveLength(1));
    await preparationReadStarted;
    // The first same-preparation read is slow. The saved choice and the
    // current file stay in place, and the one analysis action cannot submit
    // a second request while acceptance is still being read.
    const locked = await screen.findByRole("button", {
      name: "正在核对分析结果…",
    });
    expect(locked).toBeDisabled();
    expect(screen.getByText(/正在核对同一准备是否已受理/)).toBeVisible();
    expect(backend.calls.analyzePosts).toHaveLength(1);
    expect(backend.calls.choicePosts).toHaveLength(1);
    releasePreparationRead();
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(overview).toHaveTextContent(
      `「${filename(0)}」已可确认。整理方案已更新，整理尚未提交。`,
    );
    expect(backend.calls.choicePosts).toHaveLength(1);
    expect(backend.calls.analyzePosts).toHaveLength(1);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 restores the analysis-only action only after the same preparation proves non-admission", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.rejectAnalysisOnce = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    await openCorrection(user);
    await user.selectOptions(
      screen.getByLabelText(`识别类型 ${filename(0)}`),
      "C",
    );
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));
    await waitFor(() => expect(backend.calls.analyzePosts).toHaveLength(1));

    // The 409 is not treated as a retry ticket by itself: the same unchanged
    // preparation is read first and proves this request did not enter the
    // analysis stage. Only then does the saved choice get an analysis-only
    // retry, which never posts the choice again.
    const save = await screen.findByRole("button", {
      name: "保存并重新分析",
    });
    await waitFor(() => expect(save).toBeEnabled());
    expect(screen.getByText(/明确未受理/)).toBeVisible();
    expect(backend.calls.choicePosts).toHaveLength(1);

    await user.click(save);
    await waitFor(() => expect(backend.calls.analyzePosts).toHaveLength(2));
    expect(backend.calls.choicePosts).toHaveLength(1);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 returns to the overview when the native decision analysis response is lost", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataCandidateProblem = true;
      value.state.flipPreviewOnAnalyze = true;
      value.state.secondPlanKind = "ready";
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    await screen.findByRole("radio", { name: /候选 1/ });
    await user.click(screen.getByRole("radio", { name: /候选 2/ }));

    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    let continueResponseLost = false;
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/recovery/continue") && !continueResponseLost) {
        continueResponseLost = true;
        await original(input, init);
        throw new TypeError("Failed to fetch");
      }
      return original(input, init);
    });

    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));
    await waitFor(() =>
      expect(backend.calls.recoveryContinuePosts).toHaveLength(1),
    );
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(overview).toHaveTextContent(
      `「${filename(0)}」已可确认。整理方案已更新，整理尚未提交。`,
    );
    expect(backend.calls.recoveryContinuePosts).toHaveLength(1);
    expect(backend.calls.choicePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 keeps the same file and inputs when re-analysis still needs the same metadata correction", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataProblem = true;
      value.state.flipPreviewOnAnalyze = true;
      value.state.secondPlanKind = "metadata";
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    const title = screen.getByLabelText("搜索标题");
    await user.clear(title);
    await user.type(title, "DialogRename");
    await user.click(screen.getByRole("button", { name: "搜索元数据" }));
    await user.click(
      await screen.findByRole("radio", { name: /DialogRename/ }),
    );
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));
    await waitFor(() =>
      expect(backend.calls.recoveryContinuePosts.length).toBeGreaterThanOrEqual(
        1,
      ),
    );
    // The newer summary really arrived (the list reordered to put item-1 at
    // position 10), yet the same problem family keeps this exact form in place.
    await screen.findByRole("heading", { name: /第 10 \/ 10 个/ });

    expect(
      await screen.findByText(/仍需处理元数据候选；输入和位置已保留/),
    ).toBeVisible();
    expect(screen.queryByRole("region", { name: "本次整理概览" })).toBeNull();
    expect(within(card()).getAllByText(filename(0)).length).toBeGreaterThan(0);
    expect(backend.calls.choicePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 returns to the overview when re-analysis explicitly skips the file operation", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.flipPreviewOnAnalyze = true;
      value.state.secondPlanKind = "skip";
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    await openCorrection(user);
    const identity = screen.getByLabelText(`元数据身份 ${filename(0)}`);
    const alternate = within(identity)
      .getAllByRole("option")
      .at(2)
      ?.getAttribute("value");
    await user.selectOptions(identity, alternate as string);
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(overview).toHaveTextContent("明确跳过文件操作");
    expect(overview).toHaveTextContent("跳过 · One");
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 returns to the overview when re-analysis produces a new conflict blocker", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.flipPreviewOnAnalyze = true;
      value.state.secondPlanKind = "conflict";
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    await openCorrection(user);
    const identity = screen.getByLabelText(`元数据身份 ${filename(0)}`);
    const alternate = within(identity)
      .getAllByRole("option")
      .at(2)
      ?.getAttribute("value");
    await user.selectOptions(identity, alternate as string);
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(overview).toHaveTextContent(
      `「${filename(0)}」已重新分析，当前出现新的待处理问题：目标冲突。`,
    );
    const row = within(overview)
      .getByRole("button", { name: `查看 ${filename(0)}` })
      .closest("li") as HTMLElement;
    expect(row).toHaveTextContent("待处理");
    expect(row).toHaveTextContent("需要处理目标冲突");
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 keeps the current file, focus and options when only a sibling summary changed", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.flipPreviewOnAnalyze = true;
      value.state.secondPlanKind = "sibling";
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    await openCorrection(user);
    const identity = screen.getByLabelText(`元数据身份 ${filename(0)}`);
    const alternate = within(identity)
      .getAllByRole("option")
      .at(2)
      ?.getAttribute("value");
    await user.selectOptions(identity, alternate as string);
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));

    // The newer summary reorders the list but item-1's own readable result is
    // unchanged; the card stays on that exact file and never moves to the
    // overview or a sibling.
    await screen.findByRole("heading", { name: /第 10 \/ 10 个/ });
    expect(within(card()).getAllByText(filename(0)).length).toBeGreaterThan(0);
    expect(screen.queryByRole("region", { name: "本次整理概览" })).toBeNull();
    expect(
      screen.getByLabelText(`元数据身份 ${filename(0)}`),
    ).toBeInTheDocument();
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 releases the read lock when a lost analysis is proved and only a sibling summary changed", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.flipPreviewOnAnalyze = true;
      value.state.secondPlanKind = "sibling";
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    await openCorrection(user);
    const identity = screen.getByLabelText(`元数据身份 ${filename(0)}`);
    const alternate = within(identity)
      .getAllByRole("option")
      .at(2)
      ?.getAttribute("value");
    await user.selectOptions(identity, alternate as string);

    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    let analyzeResponseLost = false;
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/analyze") && !analyzeResponseLost) {
        analyzeResponseLost = true;
        await original(input, init);
        throw new TypeError("Failed to fetch");
      }
      return original(input, init);
    });

    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));
    await waitFor(() => expect(backend.calls.analyzePosts).toHaveLength(1));
    // The newer summary reorders files but this item's own facts are equal.
    // The proved analysis therefore releases the read lock instead of
    // holding the current file forever; browsing and inputs stay in place.
    await screen.findByRole("heading", { name: /第 10 \/ 10 个/ });
    expect(
      await screen.findByText(/当前文件的可读方案事实没有变化/),
    ).toBeVisible();
    expect(screen.queryByRole("region", { name: "本次整理概览" })).toBeNull();
    expect(
      screen.queryByRole("button", { name: "正在核对分析结果…" }),
    ).toBeNull();
    expect(backend.calls.analyzePosts).toHaveLength(1);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("shows one pending line before the original POST commits, then converges automatically", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, undefined, [filename(0)]);
    await screen.findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });

    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    const releaseExecute: { current: (() => void) | null } = { current: null };
    let executeAttempts = 0;
    let held: Promise<void> | null = null;
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/execute") && held === null) {
        executeAttempts += 1;
        held = new Promise<void>((resolve) => {
          releaseExecute.current = resolve;
        });
        await held;
        await original(input, init);
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return original(input, init);
    });

    await user.click(screen.getByRole("button", { name: "确认整理 1 项" }));
    // The first bounded read runs while the original POST is still in flight
    // and honestly reports no durable record yet.
    await waitFor(() =>
      expect(backend.calls.admissionReads).toBeGreaterThanOrEqual(1),
    );
    await screen.findByText(/暂未确认/);
    expect(screen.queryByRole("button", { name: /核对提交结果/ })).toBeNull();
    expect(executeAttempts).toBe(1);

    // The delayed original request now commits. The next automatic read finds
    // the same durable admission and hands off the exact Task.
    releaseExecute.current?.();
    await waitFor(
      () =>
        expect(
          screen.queryByRole("dialog", { name: "整理所选文件" }),
        ).toBeNull(),
      { timeout: 15_000 },
    );
    await waitFor(() =>
      expect(backend.router.state.location.pathname).toBe("/operations"),
    );
    expect(backend.router.state.location.search).toMatchObject({
      run: "task-handoff-1",
    });
    expect(executeAttempts).toBe(1);
    expect(backend.calls.admissionRequests[0]?.previewId).toBe(PREVIEW_ID);
  }, 30_000);

  it("offers one explicit confirmation of the exact retained batch after a proven no-record read", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, undefined, [filename(0)]);
    await screen.findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });

    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    let executeAttempts = 0;
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/execute")) {
        executeAttempts += 1;
        if (executeAttempts === 1) {
          // The first request never reaches the backend.
          return jsonResponse({ error: { code: "unavailable" } }, 503);
        }
      }
      return original(input, init);
    });

    await user.click(screen.getByRole("button", { name: "确认整理 1 项" }));
    const retry = await screen.findByRole(
      "button",
      { name: "确认同一批（1 项）" },
      { timeout: 10_000 },
    );
    expect(screen.getByText(/暂未确认/)).toBeVisible();
    expect(backend.calls.admissionRequests.length).toBeGreaterThanOrEqual(2);
    expect(executeAttempts).toBe(1);

    await user.click(retry);
    await waitFor(
      () =>
        expect(
          screen.queryByRole("dialog", { name: "整理所选文件" }),
        ).toBeNull(),
      { timeout: 15_000 },
    );
    expect(executeAttempts).toBe(2);
    expect(backend.calls.executePosts).toHaveLength(1);
    expect(backend.calls.executePosts[0]).toMatchObject({
      itemIds: ["item-1"],
      expectedIntentVersion: 7,
      allowOverwrite: false,
      allowSourceCleanup: false,
    });
    // The durable admission is still one exact batch; the first request never
    // reached the server.
    expect(backend.router.state.location.search).toMatchObject({
      run: "task-handoff-1",
    });
  }, 30_000);

  it("does not send a confirmation when its exact identity cannot be retained", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, undefined, [filename(0)]);
    await screen.findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    await screen.findByRole("region", { name: "本次整理概览" });
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    const confirm = screen.getByRole("button", { name: "确认整理 1 项" });
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("quota");
      });
    try {
      await user.click(confirm);
    } finally {
      setItem.mockRestore();
    }
    expect(await screen.findByText(/无法保存可核对的请求身份/)).toBeVisible();
    expect(backend.calls.executePosts).toHaveLength(0);
    // The reviewed selection is still present for the operator to retry.
    expect(screen.getByRole("button", { name: "确认整理 1 项" })).toBeEnabled();
  }, 30_000);

  it("A59-02 explains a stale plan row by the live metadata correction it still offers", async () => {
    const user = userEvent.setup();
    await openDialog(
      user,
      (value) => {
        value.state.metadataProblem = true;
        value.state.previewCurrent = false;
        value.state.previewStaleTail = FILE_COUNT;
      },
      undefined,
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    // The plan's item is stale, but its exact TaskItem still waits for the
    // metadata correction. The row must name that live next step instead of
    // the generic "left the plan" text.
    expect(within(overview).getByText(/需要处理作品搜索修正/)).toBeVisible();
    const metadataRow = within(overview)
      .getByText("Movie.01.mkv")
      .closest("li");
    expect(metadataRow).not.toBeNull();
    expect(
      within(metadataRow as HTMLElement).queryAllByText(/已不在当前方案中/),
    ).toHaveLength(0);

    await user.click(
      within(overview).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    expect(await screen.findByText(/没有找到匹配的作品/)).toBeVisible();
    expect(
      within(card()).getByRole("button", { name: "保存并重新分析" }),
    ).toBeVisible();
    expect(
      within(card()).queryAllByText("该文件已不在当前方案中"),
    ).toHaveLength(0);
  }, 30_000);

  it("A59-01 returns to the overview with the exact skipped result and no analysis", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.conflictProblem = true;
      },
      undefined,
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(within(overview).getByText(/需要处理目标冲突/)).toBeVisible();
    await user.click(
      within(overview).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    await user.click(await screen.findByRole("radio", { name: /跳过此条目/ }));
    await user.click(
      within(card()).getByRole("button", { name: "保存并重新分析" }),
    );

    await waitFor(() =>
      expect(backend.calls.recoveryDecisionPosts).toHaveLength(1),
    );
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    // The decision response itself ended this item: the same dialog returns
    // to the overview and its exact row carries the durable skipped result.
    const returned = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(within(returned).getByText(/决定已保存并读回/)).toBeVisible();
    expect(
      within(returned).getByText(/「Movie\.01\.mkv」已按当前决定跳过/),
    ).toBeVisible();
    const row = within(returned).getByText("Movie.01.mkv").closest("li");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("已有记录")).toBeVisible();
    expect(
      within(row as HTMLElement).getByText(/已按当前决定跳过，未纳入本次整理/),
    ).toBeVisible();
    expect(within(row as HTMLElement).queryAllByText("待处理")).toHaveLength(0);

    // Re-opening the same file reads the same result; the old conflict form
    // is not offered again.
    await user.click(
      within(returned).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    expect(await screen.findByText("此文件已跳过")).toBeVisible();
    expect(
      within(card()).queryAllByText(
        /当前文件在冲突决定被保存并由真实分析取代前不能纳入确认/,
      ),
    ).toHaveLength(0);
    expect(
      within(card()).queryByRole("radio", { name: /跳过此条目/ }),
    ).toBeNull();
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(1);
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
  }, 30_000);

  it("A59-01 keeps a settled skip on a stale plan and offers its preparation re-analysis", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.conflictProblem = true;
        value.state.previewCurrent = false;
        value.state.previewStaleTail = 1;
        value.state.reanalysisAvailable = true;
      },
      [filename(0)],
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    await expect(
      within(overview).getByText(/本次方案有 1 个文件未就绪或已失效/),
    ).toBeVisible();
    await user.click(
      within(overview).getByRole("button", { name: `查看 ${filename(0)}` }),
    );
    await user.click(await screen.findByRole("radio", { name: /跳过此条目/ }));
    await user.click(
      within(card()).getByRole("button", { name: "保存并重新分析" }),
    );

    const returned = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    // The settled item is not asked to be handled a second time. The plan
    // still needs one exact refresh, and its original preparation advertises
    // that zero-mutation analysis.
    await expect(
      within(returned).getByText(/本次方案因 1 个已结束文件需要更新/),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const batch = await screen.findByRole("region", { name: "整批复核" });
    await expect(
      within(batch).getByText(/本次方案因 1 个已结束文件需要更新/),
    ).toBeVisible();
    await expect(
      screen.getByRole("button", { name: "确认整理 0 项" }),
    ).toBeDisabled();
    await user.click(screen.getByText("未纳入本次确认的文件(1 项)"));
    expect(card()).toHaveTextContent(/该文件已按当前决定跳过/);
    expect(within(card()).queryAllByText(/该文件未就绪/)).toHaveLength(0);
    const reanalysis = within(card()).getByRole("button", {
      name: "重新分析同一准备",
    });
    await user.click(reanalysis);
    await waitFor(() => expect(backend.calls.analyzePosts).toHaveLength(1));
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("A59-01 uses the exact skipped result in the overview and batch omission", async () => {
    const user = userEvent.setup();
    await openDialog(
      user,
      (value) => {
        value.state.conflictProblem = true;
      },
      [filename(0), filename(1)],
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    await user.click(
      within(overview).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    await user.click(await screen.findByRole("radio", { name: /跳过此条目/ }));
    await user.click(
      within(card()).getByRole("button", { name: "保存并重新分析" }),
    );

    const returned = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const count = (term: string): string => {
      const row = within(returned)
        .getByText(term, { selector: "dt" })
        .closest("div") as HTMLElement;
      return row.querySelector("dd")?.textContent ?? "";
    };
    expect(count("已选 / 可确认")).toBe("1 / 1");
    expect(count("需要处理")).toBe("0");
    expect(count("已有记录")).toBe("1");
    // The exact selected subset stays readable from the one batch action;
    // the overview no longer repeats these counts in its fixed footer.
    expect(
      screen.getByRole("button", { name: "整批复核(已选 1 项)" }),
    ).toBeVisible();
    expect(within(card()).queryByText(/已选 \d+ 项 · 需要处理/)).toBeNull();
    const row = within(returned).getByText("Movie.01.mkv").closest("li");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("已有记录")).toBeVisible();
    expect(
      within(row as HTMLElement).getByText(/已跳过 · 来源保留/),
    ).toBeVisible();
    expect(
      within(row as HTMLElement).queryAllByText(/移动|来源不保留/),
    ).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    await user.click(screen.getByText("未纳入本次确认的文件(1 项)"));
    expect(
      within(card()).getByText(/该文件已按当前决定跳过，未纳入本次整理/),
    ).toBeVisible();
    expect(within(card()).queryAllByText(/本方案中该文件已失效/)).toHaveLength(
      0,
    );
    expect(screen.getByRole("button", { name: "确认整理 1 项" })).toBeEnabled();
  }, 30_000);

  it("A59-01 returns to the overview from a durable skip whose response was lost", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.conflictProblem = true;
        value.state.loseConflictDecisionResponse = true;
      },
      [filename(0), filename(1)],
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    await user.click(
      within(overview).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    await user.click(await screen.findByRole("radio", { name: /跳过此条目/ }));
    await user.click(
      within(card()).getByRole("button", { name: "保存并重新分析" }),
    );

    await waitFor(() =>
      expect(backend.calls.recoveryDecisionPosts).toHaveLength(1),
    );
    // The same-item recovery read saw the durable skip; the lost response is
    // not treated as a refusal and no analysis is requested.
    const returned = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const row = within(returned).getByText("Movie.01.mkv").closest("li");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("已有记录")).toBeVisible();
    expect(
      within(row as HTMLElement).getByText(/已跳过 · 来源保留/),
    ).toBeVisible();
    const count = (term: string): string => {
      const countRow = within(returned)
        .getByText(term, { selector: "dt" })
        .closest("div") as HTMLElement;
      return countRow.querySelector("dd")?.textContent ?? "";
    };
    expect(count("已选 / 可确认")).toBe("1 / 1");
    expect(count("需要处理")).toBe("0");
    expect(count("已有记录")).toBe("1");
    expect(
      screen.getByRole("button", { name: "整批复核(已选 1 项)" }),
    ).toBeVisible();
    const skippedButton = within(returned).getByRole("button", {
      name: "查看 Movie.01.mkv",
    });
    await waitFor(() => expect(document.activeElement).toBe(skippedButton));
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(1);
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(backend.state.conflictResolved).toBe(true);

    await user.click(
      within(returned).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    expect(await screen.findByText("此文件已跳过")).toBeVisible();
  }, 30_000);

  it("A59-01 keeps the operator's new file and draft when the skip result lands late", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.conflictProblem = true;
      },
      undefined,
      "overview",
    );
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    await user.click(
      within(overview).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    await user.click(await screen.findByRole("radio", { name: /跳过此条目/ }));

    let releaseDecision: (() => void) | null = null;
    const original = backend.fetchMock.getMockImplementation() as (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => Promise<Response>;
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (
        method === "POST" &&
        url ===
          "/api/tasks/organize-task-1/items/problem-item-1/recovery/decision"
      ) {
        await new Promise<void>((resolve) => {
          releaseDecision = resolve;
        });
      }
      return original(input, init);
    });

    await user.click(
      within(card()).getByRole("button", { name: "保存并重新分析" }),
    );
    await waitFor(() => expect(releaseDecision).not.toBeNull());
    // The operator leaves the original file while the decision is in flight.
    await user.click(screen.getByRole("button", { name: "下一项" }));
    await screen.findByRole("heading", { name: /第 2 \/ 10 个/ });
    expect(screen.queryByRole("region", { name: "本次整理概览" })).toBeNull();

    (releaseDecision as unknown as () => void)();
    await waitFor(() =>
      expect(backend.calls.recoveryDecisionPosts).toHaveLength(1),
    );
    // The late result updates only the original row: position and current
    // file stay exactly where the operator chose.
    expect(
      screen.getByRole("heading", { name: /第 2 \/ 10 个/ }),
    ).toBeVisible();
    expect(screen.queryByRole("region", { name: "本次整理概览" })).toBeNull();
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "上一项" }));
    expect(await screen.findByText("此文件已跳过")).toBeVisible();
  }, 30_000);

  it("A59-01 reads a durable skipped TaskItem on the first overview read", async () => {
    const user = userEvent.setup();
    await openDialog(
      user,
      (value) => {
        value.state.conflictProblem = true;
        value.state.conflictResolved = true;
        value.state.previewCurrent = false;
        value.state.previewStaleTail = FILE_COUNT;
      },
      undefined,
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const row = within(overview).getByText("Movie.01.mkv").closest("li");
    expect(row).not.toBeNull();
    await waitFor(() =>
      expect(within(row as HTMLElement).getByText("已有记录")).toBeVisible(),
    );
    expect(
      within(row as HTMLElement).getByText(/已按当前决定跳过，未纳入本次整理/),
    ).toBeVisible();
    expect(within(row as HTMLElement).queryAllByText("待处理")).toHaveLength(0);

    await user.click(
      within(overview).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    expect(await screen.findByText("此文件已跳过")).toBeVisible();
  }, 30_000);

  it("Task59.1 A59-06 renders the approved Files decision body with one footer action", async () => {
    const user = userEvent.setup();
    await openDialog(user, (value) => {
      value.state.conflictProblem = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    const decision = (
      await screen.findByRole("radiogroup", { name: "冲突处理方式" })
    ).closest(".mf-organize-decision-files") as HTMLElement;
    expect(decision).not.toBeNull();
    // The body is the file, its current problem and a concise reason, then
    // the server-allowed options. The old status/plan cards are gone.
    expect(within(decision).getByText("冲突处理")).toBeVisible();
    expect(
      within(decision).getByRole("heading", { name: "处理目标冲突" }),
    ).toBeVisible();
    expect(
      within(decision).getByText(
        "目标路径已有文件。选择处理方式，然后核对重新分析生成的计划。",
      ),
    ).toBeVisible();
    expect(within(card()).queryByText("当前状态")).toBeNull();
    expect(
      within(card()).queryByRole("heading", { name: "当前决定" }),
    ).toBeNull();
    expect(
      within(card()).queryByRole("heading", { name: "整理方案" }),
    ).toBeNull();
    // The existing target is stated once, before the options.
    expect(within(card()).getAllByText("已有目标")).toHaveLength(1);
    const target = "Movies/Movie.01 (2001)/Movie.01.mkv";
    expect(within(card()).getAllByText(target)).toHaveLength(1);
    const options = within(decision).getByRole("radiogroup", {
      name: "冲突处理方式",
    });
    expect(within(options).getAllByRole("radio")).toHaveLength(2);
    // A conflict has no ignore action; the one legal save lives in the fixed
    // footer, never in the scrolling body.
    expect(
      within(card()).queryByRole("button", { name: "忽略此文件" }),
    ).toBeNull();
    const save = within(card()).getByRole("button", {
      name: "保存并重新分析",
    });
    expect(save.closest(".mf-modal-footer")).not.toBeNull();
  }, 30_000);

  it("Task59.1 A59-06 orders the work search as title, year and media type", async () => {
    const user = userEvent.setup();
    await openDialog(user, (value) => {
      value.state.metadataProblem = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    await screen.findByRole("button", { name: "搜索元数据" });

    const title = screen.getByLabelText("搜索标题");
    const year = screen.getByLabelText("年份（可留空）");
    const mediaType = screen.getByLabelText("作品类型");
    const follows = (first: HTMLElement, second: HTMLElement) =>
      (first.compareDocumentPosition(second) &
        Node.DOCUMENT_POSITION_FOLLOWING) !==
      0;
    expect(follows(title, year)).toBe(true);
    expect(follows(year, mediaType)).toBe(true);
    expect(screen.getByRole("button", { name: "搜索元数据" })).toBeVisible();
  }, 30_000);

  it("Task59.1 A59-06 allows the backend-permitted ignore beside the save action", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataCandidateProblem = true;
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    await screen.findByRole("heading", { name: "确认作品" });
    const ignore = within(card()).getByRole("button", {
      name: "忽略此文件",
    });
    expect(ignore.closest(".mf-modal-footer")).not.toBeNull();

    await user.click(ignore);
    await waitFor(() => expect(backend.state.ignoredProblem).toBe(true));
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(
      within(overview).getByText(/「Movie\.01\.mkv」已忽略/),
    ).toBeVisible();
    const row = within(overview).getByText("Movie.01.mkv").closest("li");
    expect(row).not.toBeNull();
    await waitFor(() =>
      expect(within(row as HTMLElement).getByText("已有记录")).toBeVisible(),
    );
    expect(
      within(row as HTMLElement).getByText(/该文件已忽略，未纳入本次整理/),
    ).toBeVisible();
    expect(backend.calls.executePosts).toHaveLength(0);
    expect(backend.calls.recoveryContinuePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 keeps the Files decision footer to the return, paging and the conflict action", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.conflictProblem = true;
      },
      undefined,
      "overview",
    );
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    await user.click(
      within(overview).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    const footer = await waitFor(() => {
      const element = card().querySelector<HTMLElement>(".mf-modal-footer");
      expect(element).not.toBeNull();
      return element as HTMLElement;
    });
    const footerLabels = () =>
      within(footer)
        .getAllByRole("button")
        .map((button) => button.textContent?.trim() ?? "");
    // Left: the overview return. Right: paging, then this file's one action.
    expect(footerLabels()).toEqual([
      "返回整理概览",
      "上一项",
      "下一项",
      "保存并重新分析",
    ]);
    // Closing and the batch review keep their approved entries instead of
    // sharing the row with this file's decision.
    expect(within(footer).queryByRole("button", { name: "关闭" })).toBeNull();
    expect(
      within(footer).queryByRole("button", { name: /整批复核/ }),
    ).toBeNull();
    expect(screen.getByRole("button", { name: "关闭整理弹窗" })).toBeEnabled();

    // The draft note follows this file; the footer carries no index copy.
    expect(footer.textContent).not.toContain("有未保存的修正");
    // The saved strategy is "skip"; choosing another legal one is a draft.
    await user.click(screen.getByRole("radio", { name: /重命名目标/ }));
    const draftNote = within(card()).getByText("有未保存的修正");
    expect(draftNote.closest(".mf-organize-files-file-head")).not.toBeNull();
    expect(footer.textContent).not.toContain("有未保存的修正");
    expect(footer.textContent).not.toContain("第 1 / 10 个");
    expect(
      within(footer).getByRole("button", { name: "保存并重新分析" }),
    ).toBeEnabled();
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);

    // The footer never bypasses the overview for the batch review.
    await user.click(
      within(footer).getByRole("button", { name: "返回整理概览" }),
    );
    await screen.findByRole("region", { name: "本次整理概览" });
    expect(backend.calls.recoveryDecisionPosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 orders the permitted ignore before the save in the Files decision footer", async () => {
    const user = userEvent.setup();
    await openDialog(user, (value) => {
      value.state.metadataCandidateProblem = true;
    });
    await screen.findByRole("heading", { name: "确认作品" });
    const footer = card().querySelector<HTMLElement>(".mf-modal-footer");
    expect(footer).not.toBeNull();
    expect(
      within(footer as HTMLElement)
        .getAllByRole("button")
        .map((button) => button.textContent?.trim() ?? ""),
    ).toEqual([
      "返回整理概览",
      "上一项",
      "下一项",
      "忽略此文件",
      "保存并重新分析",
    ]);
  }, 30_000);

  it("Task59.1 A59-07 keeps a durable skipped record whose file a newer plan no longer lists", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.previewItemPaths = Array.from(
          { length: FILE_COUNT - 1 },
          (_, index) => `Movies/${filename(index + 1)}`,
        );
        value.state.durableSettledItems = [
          {
            itemId: "settled-item-1",
            status: "skipped",
            sourcePath: `Movies/${filename(0)}`,
            taskId: "organize-task-1",
          },
        ];
      },
      undefined,
      "overview",
    );

    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const row = within(overview).getByText("Movie.01.mkv").closest("li");
    expect(row).not.toBeNull();
    await waitFor(() =>
      expect(within(row as HTMLElement).getByText("已有记录")).toBeVisible(),
    );
    // The proof is read from the same Task, not invented from the summary.
    expect(backend.calls.settledRecordsReads).toBeGreaterThan(0);
    expect(
      within(row as HTMLElement).getByText(/已按当前决定跳过，未纳入本次整理/),
    ).toBeVisible();
    const counts = overview.querySelectorAll(
      ".mf-organize-overview-counts div",
    );
    const countFacts = Object.fromEntries(
      [...counts].map((entry) => [
        entry.querySelector("dt")?.textContent ?? "",
        entry.querySelector("dd")?.textContent ?? "",
      ]),
    );
    expect(countFacts).toMatchObject({
      "已选 / 可确认": "9 / 9",
      需要处理: "0",
      已有记录: "1",
    });
    // One row per proven file identity: the durable result does not duplicate.
    expect(
      within(overview).getAllByRole("button", { name: "查看 Movie.01.mkv" }),
    ).toHaveLength(1);

    await user.click(
      within(overview).getByRole("button", { name: "查看 Movie.01.mkv" }),
    );
    expect(await screen.findByText("此文件已跳过")).toBeVisible();
    expect(within(card()).queryByRole("radio")).toBeNull();
    expect(within(card()).queryByText("纳入本次整理")).toBeNull();

    // Returning to the overview keeps the record row and its exact count.
    await user.click(screen.getByRole("button", { name: "返回概览" }));
    const reopened = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const reopenedRow = within(reopened)
      .getByText("Movie.01.mkv")
      .closest("li");
    expect(
      within(reopenedRow as HTMLElement).getByText("已有记录"),
    ).toBeVisible();

    // The batch still spans only the nine current legal files.
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const summary = card().querySelector(".mf-organize-batch-summary");
    expect(summary).toHaveTextContent(/本次确认\s*9 项/);
    expect(
      within(card()).getByRole("region", { name: "来源与目标" }),
    ).not.toHaveTextContent("Movie.01.mkv");
    expect(backend.calls.executePosts).toHaveLength(0);
  }, 30_000);

  it("Task59.1 A59-07 updates an existing plan row instead of adding a second record row", async () => {
    const user = userEvent.setup();
    await openDialog(
      user,
      (value) => {
        value.state.conflictProblem = true;
        value.state.durableSettledItems = [
          {
            itemId: "problem-item-1",
            status: "skipped",
            sourcePath: `Movies/${filename(0)}`,
            taskId: "organize-task-1",
          },
        ];
      },
      undefined,
      "overview",
    );
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const rows = within(overview)
      .getAllByRole("button", { name: "查看 Movie.01.mkv" })
      .map((button) => button.closest("li"));
    expect(rows).toHaveLength(1);
    await waitFor(() =>
      expect(
        within(rows[0] as HTMLElement).getByText("已有记录"),
      ).toBeVisible(),
    );
    expect(
      within(rows[0] as HTMLElement).getByText(
        /已按当前决定跳过，未纳入本次整理/,
      ),
    ).toBeVisible();
    const countPairs = overview.querySelectorAll(
      ".mf-organize-overview-counts div",
    );
    const countFacts = Object.fromEntries(
      [...countPairs].map((entry) => [
        entry.querySelector("dt")?.textContent ?? "",
        entry.querySelector("dd")?.textContent ?? "",
      ]),
    );
    expect(countFacts["已有记录"]).toBe("1");
    expect(countFacts["需要处理"]).toBe("0");
  }, 30_000);

  it("Task59.1 A59-07 keeps the current file and draft when the record read lands late", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
      value.state.metadataProblem = true;
      value.state.holdSettledReads = true;
      value.state.durableSettledItems = [
        {
          itemId: "settled-sibling",
          status: "ignored",
          sourcePath: `Movies/${filename(1)}`,
          taskId: "organize-task-1",
        },
      ];
    });
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    const title = screen.getByLabelText("搜索标题");
    await user.clear(title);
    await user.type(title, "LateReadback");

    backend.releaseSettledReads();
    await waitFor(() =>
      expect(backend.calls.settledRecordsReads).toBeGreaterThan(0),
    );
    // The late result updates rows only: the same file and its unsaved input
    // stay exactly where the operator left them.
    expect(screen.getByLabelText("搜索标题")).toHaveValue("LateReadback");
    expect(
      screen.getByRole("heading", { name: /第 1 \/ 10 个/ }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "返回整理概览" }));
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    const siblingRow = within(overview).getByText("Movie.02.mkv").closest("li");
    expect(
      within(siblingRow as HTMLElement).getByText("已有记录"),
    ).toBeVisible();
    const currentRow = within(overview).getByText("Movie.01.mkv").closest("li");
    expect(within(currentRow as HTMLElement).getByText("待处理")).toBeVisible();
  }, 30_000);

  it("Task59.1 A59-07 keeps the same-task read feedback and a legal re-read", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(
      user,
      (value) => {
        value.state.failSettledRecords = true;
        value.state.durableSettledItems = [
          {
            itemId: "settled-item-1",
            status: "ignored",
            sourcePath: `Movies/${filename(0)}`,
            taskId: "organize-task-1",
          },
        ];
      },
      undefined,
      "overview",
    );
    const overview = await screen.findByRole("region", {
      name: "本次整理概览",
    });
    expect(
      await within(overview).findByText("暂时无法读取原任务的已结算记录"),
    ).toBeVisible();
    expect(overview).toHaveTextContent(/原任务 organize-task-1/);
    // The readable plan row stays, but without inventing its durable record.
    const planRow = within(overview).getByText("Movie.01.mkv").closest("li");
    expect(within(planRow as HTMLElement).getByText("已纳入")).toBeVisible();
    expect(within(planRow as HTMLElement).queryByText("已有记录")).toBeNull();
    const reread = within(overview).getByRole("button", {
      name: "重新读取已结算记录",
    });

    backend.state.failSettledRecords = false;
    await user.click(reread);
    await waitFor(() =>
      expect(
        within(overview).queryByText("暂时无法读取原任务的已结算记录"),
      ).toBeNull(),
    );
    const row = within(overview).getByText("Movie.01.mkv").closest("li");
    await waitFor(() =>
      expect(within(row as HTMLElement).getByText("已有记录")).toBeVisible(),
    );
    expect(
      within(overview).getAllByRole("button", { name: "查看 Movie.01.mkv" }),
    ).toHaveLength(1);
    expect(
      within(row as HTMLElement).getByText(/该文件已忽略，未纳入本次整理/),
    ).toBeVisible();
  }, 30_000);
});
