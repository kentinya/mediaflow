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
    // The number of leading discovery reads that still report an unchanged
    // waiting state before the plan links.
    waitingReads: 0 as number,
    discoveryReads: 0 as number,
    // A real no-candidate problem on the first file, plus the durable
    // metadata-correction decision the same TaskItem exposes after analysis.
    metadataProblem: false as boolean,
    metadataProblemResolved: false as boolean,
    // A real metadata-review problem: two tied legal candidates on item-1.
    metadataCandidateProblem: false as boolean,
    metadataCandidateResolved: false as boolean,
    failMetadataDecision: false as boolean,
    failMetadataContinue: false as boolean,
  };
  const calls = {
    discoveryPosts: [] as Json[],
    choicePosts: [] as Json[],
    analyzePosts: [] as Json[],
    executePosts: [] as Json[],
    admissionReads: 0,
    metadataSearchPosts: [] as Json[],
    recoveryDecisionPosts: [] as Json[],
    recoveryContinuePosts: [] as Json[],
  };
  /** A deliberately stuck Execute response the test releases by hand. */
  let releasedExecute: ((response: Response) => void) | null = null;
  let holdExecute = false;
  const heldExecuteResponses: Response[] = [];

  const discoveryDocument = (): Json => ({
    journey: "discovery",
    discoveryId: DISCOVERY_ID,
    resourceLibraryId: "library",
    storageId: "source",
    configurationSnapshotId: "active-1",
    status: "completed",
    version: 5,
    createdAt: "2026-01-01T00:00:00+00:00",
    updatedAt: "2026-01-01T00:00:00+00:00",
    selection: {
      scopeCount: 1,
      scopes: [{ kind: "directory", path: "Movies" }],
      existing: [],
      refused: [],
    },
    budgets: {},
    progress: {
      phase: "prepared",
      visitedEntries: FILE_COUNT + 1,
      visitedDirectories: 1,
      pageFetches: 1,
      primarySources: FILE_COUNT,
      excludedEntries: 0,
      unstableEntries: 0,
      errorEntries: 0,
      activeSeconds: 0.1,
      incomplete: false,
      incompleteReason: null,
      refusalReasons: [],
      materialRefusal: null,
      findings: [],
      reasons: [],
      message: "the exact zero-mutation plan summary is ready",
    },
    primarySourceCount: FILE_COUNT,
    organizeTaskId: state.endedFlow ? null : "organize-task-1",
    organizeFlow: {
      taskId: "organize-task-1",
      status: state.endedFlow ? "completed" : "running",
      continuable: !state.endedFlow,
    },
    admissionRequestId: null,
    autoPrepare: true,
    prepared: true,
    previewId:
      state.endedFlow && !state.endedFlowKeepsPreview ? null : state.previewId,
    intentId: INTENT_ID,
    frozen: true,
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
      prepare: discoveryAction(),
    },
    sources: [],
    nextAction: "open the linked exact plan summary",
    failure: null,
    sideEffects: "none",
    zeroMutation: true,
    execution: "not_available_from_discovery",
  });

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
    if (latestPlan !== null) latestPlan["previewId"] = state.previewId;
    value["actions"] = {
      choice: {
        available: true,
        method: "POST",
        path: `/api/v1/operations/organize/intents/${INTENT_ID}/items/{itemId}/choice`,
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
    const order = Array.from({ length: FILE_COUNT }, (_, index) => index);
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
        destination["filename"] = filename(index);
        destination["storageRelativePath"] = `Movies/${filename(index)}`;
        destination["relativePath"] = `Movies/${filename(index)}`;
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
    if (
      (state.metadataProblem && !state.metadataProblemResolved) ||
      (state.metadataCandidateProblem && !state.metadataCandidateResolved)
    ) {
      const problem = (value["items"] as Json[]).find(
        (item) => item["itemId"] === "item-1",
      );
      if (problem !== undefined) {
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
    const execute = (value["actions"] as Json)["execute"] as Json;
    execute["path"] =
      `/api/v1/operations/organize/previews/${previewId}/execute`;
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
          can_search: true,
          choices: [],
          allowed_strategies: [],
          conflict_types: [],
        },
    manualRecoveryAvailable: false,
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
    recoveryKind: "business_problem",
    next_action: resolved
      ? "continue safe analysis"
      : "choose one legal metadata candidate",
  });

  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url === "/api/v1/system/status") {
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
                storage_id: "local-1",
                root_path: "/library",
                enabled: true,
              },
            ],
          },
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
        url === `/api/v1/operations/organize/discoveries/${DISCOVERY_ID}` &&
        method === "GET"
      ) {
        state.discoveryReads += 1;
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
        return jsonResponse(discoveryDocument());
      }

      if (
        url === `/api/v1/tasks/organize-task-1/items/problem-item-1/recovery` &&
        method === "GET"
      ) {
        return jsonResponse(
          state.metadataCandidateProblem
            ? metadataCandidateRecovery(state.metadataCandidateResolved)
            : metadataCorrectionRecovery(state.metadataProblemResolved),
        );
      }

      if (
        url ===
          `/api/v1/tasks/organize-task-1/items/problem-item-1/recovery/metadata-search` &&
        method === "POST"
      ) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Json;
        calls.metadataSearchPosts.push(body);
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
          `/api/v1/tasks/organize-task-1/items/problem-item-1/recovery/decision` &&
        method === "POST"
      ) {
        calls.recoveryDecisionPosts.push(
          JSON.parse(String(init?.body ?? "{}")) as Json,
        );
        if (state.failMetadataDecision) {
          return jsonResponse({ error: { code: "stale_checkpoint" } }, 409);
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
          `/api/v1/tasks/organize-task-1/items/problem-item-1/recovery/continue` &&
        method === "POST"
      ) {
        calls.recoveryContinuePosts.push(
          JSON.parse(String(init?.body ?? "{}")) as Json,
        );
        if (state.failMetadataContinue) {
          return jsonResponse({ error: { code: "unavailable" } }, 503);
        }
        return jsonResponse({
          sideEffects: "none",
          next_action: "wait for the Worker and inspect its linked result",
          nativeAnalysis: { taskId: "organize-task-1" },
        });
      }

      if (
        url ===
          `/api/v1/operations/organize/discoveries/${DISCOVERY_ID}/analyze` &&
        method === "POST"
      ) {
        calls.analyzePosts.push(JSON.parse(String(init?.body ?? "{}")) as Json);
        if (state.flipPreviewOnAnalyze) {
          state.previewId = "preview-2";
        }
        return jsonResponse(discoveryDocument());
      }

      if (
        url === `/api/v1/operations/organize/intents/${INTENT_ID}` &&
        method === "GET"
      ) {
        return jsonResponse(intentDocument());
      }

      const choiceMatch = url.match(
        /^\/api\/v1\/operations\/organize\/intents\/intent-1\/items\/([^/]+)\/choice$/,
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
        /^\/api\/v1\/operations\/organize\/previews\/([^/?]+)$/,
      );
      if (previewMatch !== null && method === "GET") {
        const previewId = previewMatch[1] ?? "";
        if (previewId === PREVIEW_ID) {
          return jsonResponse(previewDocument(PREVIEW_ID, false));
        }
        if (previewId === "preview-2") {
          return jsonResponse(previewDocument("preview-2", true));
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }

      if (
        url.startsWith("/api/v1/operations/organize/executions") &&
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
        /^\/api\/v1\/operations\/organize\/previews\/([^/?]+)\/admission/,
      );
      if (admissionMatch !== null && method === "GET") {
        calls.admissionReads += 1;
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
        /^\/api\/v1\/operations\/organize\/previews\/([^/?]+)\/execute$/,
      );
      if (executeMatch !== null && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}")) as Json;
        calls.executePosts.push(body);
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
                path: "/api/v1/operations/organize/executions/exec-1",
                nextAction: "inspect the durable task",
                reason: null,
                sideEffects: "none",
                durableOutcome: null,
              },
              task: {
                available: true,
                method: "GET",
                path: "/api/v1/operations/tasks/task-handoff-1",
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
              path: "/api/v1/operations/organize/executions/exec-1",
              nextAction: "inspect the durable task",
              reason: null,
              sideEffects: "none",
              durableOutcome: null,
            },
            task: {
              available: true,
              method: "GET",
              path: "/api/v1/operations/tasks/task-handoff-1",
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
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  authStore.clearToken();
  document.body.innerHTML = "";
});

/** The one mounted card, so assertions never read the Files background rows. */
function card(): HTMLElement {
  return screen.getByRole("dialog", { name: "整理所选文件" });
}

/** Mount the real Files page and open the real batch entry. */
async function openDialog(
  user: ReturnType<typeof userEvent.setup>,
  configure?: (backend: Backend) => void,
): Promise<
  Backend & { readonly router: ReturnType<typeof renderApp>["router"] }
> {
  const backend = makeBackend();
  configure?.(backend);
  vi.stubGlobal("fetch", backend.fetchMock);
  authStore.setToken(TOKEN);
  const { router } = renderApp("/ui-v2/resourcelib/files");
  await screen.findByRole("table");
  await user.click(screen.getByRole("checkbox", { name: "选择全部" }));
  await user.click(screen.getByRole("button", { name: "批量整理" }));
  await screen.findByRole("dialog", { name: "整理所选文件" });
  return Object.assign(backend, { router });
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

    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    expect(screen.getByText(/将整理 10 项/)).toBeVisible();

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
    await user.click(screen.getByRole("button", { name: "搜索作品" }));
    await waitFor(() =>
      expect(backend.calls.metadataSearchPosts).toHaveLength(1),
    );
    expect(backend.calls.metadataSearchPosts[0]).toMatchObject({
      query: "DialogRename",
      mediaType: "movie",
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
    await user.click(screen.getByRole("button", { name: "关闭" }));
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
    await user.click(screen.getByRole("button", { name: "关闭" }));
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

  it("keeps unsaved drafts across paging, never saves on paging and pins the discard choice on close", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user);
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

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
    await user.click(screen.getByRole("button", { name: "关闭" }));
    const prompt = await screen.findByRole("alertdialog");
    expect(
      within(prompt).getByText("有尚未保存的逐文件修正草稿。"),
    ).toBeVisible();
    expect(backend.calls.choicePosts).toHaveLength(0);
    await user.click(within(prompt).getByRole("button", { name: "继续编辑" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(screen.getByRole("dialog", { name: "整理所选文件" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "关闭" }));
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
    await user.click(screen.getByRole("button", { name: "关闭" }));
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
    backend.router.history.push("/ui-v2/resourcelib/files");
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
    await user.click(screen.getByRole("button", { name: "关闭" }));
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

    await user.selectOptions(
      screen.getByLabelText("元数据身份 Movie.01.mkv"),
      "tmdb/129/movie",
    );
    await user.click(screen.getByRole("button", { name: "保存并重新分析" }));

    const warning =
      await screen.findByText(/候选选择已保存,但重新分析暂未完成/);
    expect(warning).toBeVisible();
    expect(backend.calls.choicePosts).toHaveLength(1);
    expect(backend.calls.analyzePosts).toHaveLength(0);
    expect(backend.calls.executePosts).toHaveLength(0);

    // The split retry only re-runs the analysis: no second save of the same
    // durable decision and no execution.
    const retry = await screen.findByRole("button", { name: "重新分析" });
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

    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    await screen.findByRole("region", { name: "整批复核" });
    await user.click(screen.getByRole("button", { name: "确认整理 10 项" }));

    await screen.findByText(/执行结果未知/);
    expect(backend.calls.executePosts).toHaveLength(1);
    // Escape / close stay locked: the unknown outcome must be reconciled, not
    // abandoned.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "整理所选文件" })).toBeVisible();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "整理所选文件" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "核对提交结果" }));

    await waitFor(() => expect(backend.calls.admissionReads).toBe(1));
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
    expect(backend.calls.admissionReads).toBe(1);
  }, 30_000);

  it("keeps unknown batches independent: unready and past-admitted siblings stay outside the fresh confirmation", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user);
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });

    // Fresh entry first: the confirmed subset must contain only what the
    // operator can actually confirm right now.
    expect(backend.calls.executePosts).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: /整批复核/ }));
    const region = await screen.findByRole("region", { name: "整批复核" });
    expect(within(region).getByText(/将整理 10 项/)).toBeVisible();

    // Browse-only steps are still zero-execute even on the confirm step.
    await user.click(screen.getByRole("button", { name: "返回逐项复核" }));
    await screen.findByRole("heading", { name: /第 1 \/ 10 个/ });
    expect(backend.calls.executePosts).toHaveLength(0);

    // Excluding one file is an honest selection state, not a persistent
    // ignore: the confirmation counts exactly the remaining subset.
    await user.click(
      screen.getByRole("checkbox", { name: "纳入 Movie.01.mkv" }),
    );
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
      await user.click(screen.getByRole("button", { name: "返回逐项复核" }));
      // Each pass resumes on the previously visited file; one step forward
      // lands on exactly the file this pass excludes.
      await user.click(screen.getByRole("button", { name: "下一项" }));
      await user.click(
        screen.getByRole("checkbox", { name: `纳入 ${filename(index)}` }),
      );
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

  it("keeps polling an unchanged waiting preparation until the exact plan links", async () => {
    const user = userEvent.setup();
    await openDialog(user, (value) => {
      value.state.waitingReads = 3;
    });

    // The first read is an honest waiting state, and the interval keeps
    // reading the same unchanged document without needing a render.
    await screen.findByText("等待来源稳定");
    await screen.findByRole(
      "heading",
      { name: /第 1 \/ 10 个/ },
      { timeout: 12_000 },
    );
    expect(within(card()).getAllByText("Movie.01.mkv").length).toBeGreaterThan(
      0,
    );
  }, 20_000);

  it("keeps an ended flow as a read-only original summary with no confirmation", async () => {
    const user = userEvent.setup();
    const backend = await openDialog(user, (value) => {
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

  it("renders the linked plan as read-only history when an ended flow kept it", async () => {
    const user = userEvent.setup();
    await openDialog(user, (value) => {
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
});
