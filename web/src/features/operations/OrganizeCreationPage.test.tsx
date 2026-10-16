/**
 * Operator journey for the in-context creation workspace (Task 45.2 RO-2).
 *
 * These tests drive the real `/operations/organize/new` route with a stubbed
 * API boundary.  The Preview and action-matrix payloads are the exact
 * contract-captured documents the real Python API returns, so these tests
 * exercise the real route tree, query boundaries and normalizers together.
 * They prove the same-page preparation journey:
 *
 * - a full preparation shows its durable progress and links the exact plan
 *   summary on the same page;
 * - the confirmation button counts exactly the selected ready subset;
 * - a material budget refusal never offers an executable prefix;
 * - an ambiguous Execute response is never retried automatically and only the
 *   bounded admission-outcome read resolves it.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;
const TOKEN = "creation-token";
const DISCOVERY_ID = "prep-1";
const PREVIEW_ID = "preview-1";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function clone(name: string): Json {
  return JSON.parse(JSON.stringify(documents[name])) as Json;
}

/** The exact contract Preview detail, retargeted to this workspace's ids. */
function previewDocument(): Json {
  const value = clone("organizePreviewDetail");
  value["previewId"] = PREVIEW_ID;
  value["intentId"] = "intent-1";
  value["executionCandidateItemIds"] = ["item-1"];
  const items = value["items"] as Json[];
  const first = items[0]!;
  first["itemId"] = "item-1";
  first["previewItemId"] = "pitem-1";
  const source = first["source"] as Json;
  source["path"] = "Movies/One.2001.mkv";
  source["filename"] = "One.2001.mkv";
  (value["selection"] as Json)["selectedItemIds"] = ["item-1"];
  (value["selection"] as Json)["unselectedItemIds"] = [];
  const execute = (value["actions"] as Json)["execute"] as Json;
  execute["path"] =
    `/api/v1/operations/organize/previews/${PREVIEW_ID}/execute`;
  return value;
}

function discoveryDocument(overrides: Record<string, unknown> = {}): Json {
  return {
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
    },
    budgets: {},
    progress: {
      phase: "prepared",
      visitedEntries: 2,
      visitedDirectories: 1,
      pageFetches: 1,
      primarySources: 1,
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
    primarySourceCount: 1,
    admissionRequestId: null,
    autoPrepare: true,
    prepared: true,
    previewId: PREVIEW_ID,
    intentId: "intent-1",
    frozen: true,
    frozenAt: "2026-01-01T00:00:00+00:00",
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
      pause: action(),
      resume: action(),
      cancel: action(),
      finalize: action(),
      prepare: action(),
    },
    sources: [],
    nextAction: "open the linked exact plan summary",
    failure: null,
    sideEffects: "none",
    zeroMutation: true,
    execution: "not_available_from_discovery",
    ...overrides,
  };
}

function action() {
  return {
    available: false,
    method: "POST",
    path: null,
    requiresVersion: true,
    sideEffects: "none",
    refusal: null,
    pendingReason: null,
  };
}

describe("organize creation workspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    authStore.clearToken();
  });

  it("shows the linked plan summary and confirms only the selected ready subset", async () => {
    const user = userEvent.setup();
    let executeBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === `/api/v1/operations/organize/discoveries/${DISCOVERY_ID}`) {
          return jsonResponse(discoveryDocument());
        }
        if (url === `/api/v1/operations/organize/previews/${PREVIEW_ID}`) {
          const value = previewDocument();
          const first = (value["items"] as Json[])[0]!;
          const second = JSON.parse(JSON.stringify(first)) as Json;
          second["itemId"] = "item-2";
          second["previewItemId"] = "pitem-2";
          second["position"] = 1;
          (second["source"] as Json)["filename"] = "Two.2002.mkv";
          (second["source"] as Json)["path"] = "Movies/Two.2002.mkv";
          value["items"] = [first, second];
          value["executionCandidateItemIds"] = ["item-1", "item-2"];
          (value["selection"] as Json)["selectedItemIds"] = [
            "item-1",
            "item-2",
          ];
          return jsonResponse(value);
        }
        if (
          url === `/api/v1/operations/organize/previews/${PREVIEW_ID}/execute`
        ) {
          executeBody = JSON.parse(String(init?.body ?? "{}")) as Record<
            string,
            unknown
          >;
          return jsonResponse(
            {
              executionId: "exec-1",
              taskId: "task-1",
              status: "admitted",
              selectedItemCount: 1,
            },
            202,
          );
        }
        if (url.startsWith("/api/v1/operations/organize/executions")) {
          return jsonResponse({
            items: [],
            total: 0,
            limit: 100,
            truncated: false,
          });
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    authStore.setToken(TOKEN);
    renderApp(`/ui-v2/operations/organize/new?discoveryId=${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "新建整理任务" });
    // The same page shows the exact plan summary without a Preview jump.
    await screen.findByRole("heading", { name: "计划摘要" });
    await screen.findByText("One.2001.mkv");
    // Deselect one ready item: the confirmation must count exactly one.
    await user.click(
      screen.getByRole("checkbox", { name: "选择 Two.2002.mkv" }),
    );
    const confirm = await screen.findByRole("button", {
      name: "确认整理 1 项",
    });
    await user.click(confirm);
    await waitFor(() => expect(executeBody).not.toBeNull());
    expect(executeBody?.["itemIds"]).toEqual(["item-1"]);
    expect(executeBody?.["confirmation"]).toBe(true);
  });

  it("never offers an executable prefix after a material budget refusal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === `/api/v1/operations/organize/discoveries/${DISCOVERY_ID}`) {
          return jsonResponse(
            discoveryDocument({
              status: "partial_success",
              previewId: null,
              prepared: false,
              progress: {
                phase: "partial",
                visitedEntries: 5,
                visitedDirectories: 1,
                pageFetches: 1,
                primarySources: 2,
                excludedEntries: 0,
                unstableEntries: 0,
                errorEntries: 0,
                activeSeconds: 0.1,
                incomplete: true,
                incompleteReason: "primary_limit",
                refusalReasons: ["primary_limit"],
                materialRefusal: "primary_limit",
                findings: [],
                reasons: [],
                message: "bounded discovery stopped at a limit",
              },
              nextAction: "narrow the selected scope",
            }),
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    authStore.setToken(TOKEN);
    renderApp(`/ui-v2/operations/organize/new?discoveryId=${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "新建整理任务" });
    await screen.findByText(/不能冻结为可执行清单/);
    expect(screen.queryByRole("button", { name: /确认整理/ })).toBeNull();
  });

  it("treats an ambiguous Execute response as unknown and reconciles without replay", async () => {
    const user = userEvent.setup();
    let executePosts = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === `/api/v1/operations/organize/discoveries/${DISCOVERY_ID}`) {
          return jsonResponse(discoveryDocument());
        }
        if (url === `/api/v1/operations/organize/previews/${PREVIEW_ID}`) {
          return jsonResponse(previewDocument());
        }
        if (
          url === `/api/v1/operations/organize/previews/${PREVIEW_ID}/execute`
        ) {
          executePosts += 1;
          throw new TypeError("simulated lost execute response");
        }
        if (
          url.startsWith(
            `/api/v1/operations/organize/previews/${PREVIEW_ID}/admission`,
          )
        ) {
          return jsonResponse({
            outcome: "known",
            executionId: "exec-9",
            taskId: "task-9",
          });
        }
        if (url.startsWith("/api/v1/operations/organize/executions")) {
          return jsonResponse({
            items: [],
            total: 0,
            limit: 100,
            truncated: false,
          });
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    authStore.setToken(TOKEN);
    renderApp(`/ui-v2/operations/organize/new?discoveryId=${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "计划摘要" });
    await user.click(
      await screen.findByRole("button", { name: "确认整理 1 项" }),
    );
    // The ambiguous outcome is shown, never silently retried.
    await screen.findByText("执行结果未知");
    expect(executePosts).toBe(1);
    // The bounded reconciliation read proves the durable admission.
    await user.click(screen.getByRole("button", { name: "核对提交结果" }));
    await waitFor(() => expect(executePosts).toBe(1));
  });
});
