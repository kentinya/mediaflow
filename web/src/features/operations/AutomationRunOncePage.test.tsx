import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";

/**
 * Component/router proof for the definition-bound Run once journey.
 *
 * Every payload mirrors the exact operator projection the real Python API
 * returns (proved by tests/test_v2_automation_run_once.py and
 * tests/test_v2_automation_operations.py). The assertions prove the journey and
 * its safety properties: the frozen manifest's complete zero-mutation plan is
 * re-read from its durable association at the same URL after a reload, without
 * another Finalize, another analysis or any execution authority.
 */

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;
const TOKEN = "run-once-token";
const DISCOVERY_ID = "discovery-1";
const INTENT_ID = "intent-1";
const PREVIEW_ID = "preview-1";
const API_PATH = `/api/v1/operations/automation/run-once/${DISCOVERY_ID}`;

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: unknown;
}

function recordingFetch(respond: (call: Call) => Response | undefined): {
  calls: Call[];
} {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: init?.method ?? "GET",
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as unknown)
            : null,
      };
      calls.push(call);
      const response = respond(call);
      if (response !== undefined) return response;
      return jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return { calls };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function action(overrides: Json = {}): Json {
  return {
    available: false,
    method: "POST",
    path: null,
    reason: null,
    sideEffects: "none",
    durableOutcome: null,
    nextAction: null,
    ...overrides,
  };
}

/**
 * The exact bounded Run once projection of a discovery that finished its walk.
 * `previewId` is `null` while the manifest has not been frozen yet, and names
 * the exact durable plan afterwards, exactly as the backend now resolves it from
 * the linked intent.
 */
function runOnceDocument(overrides: Json = {}): Json {
  const value: Json = {
    journey: "automation-run-once",
    discoveryId: DISCOVERY_ID,
    definitionId: "nightly",
    definitionName: "Nightly",
    definitionFingerprint: "fingerprint",
    definitionOrigin: {
      origin: "definition-run-once",
      definitionId: "nightly",
      definitionName: "Nightly",
      definitionFingerprint: "fingerprint",
      configurationRevisionId: "revision-1",
      configurationRevisionVersion: 1,
      configurationRevisionDigest: "digest",
      resourceLibraryId: "library",
      sourceScope: "Movies",
      runMode: "automatic-organization",
      definitionItemLimit: 10,
      effectivePrimaryLimit: 10,
      admissionRequestId: null,
    },
    resourceLibraryId: "library",
    sourceScope: "Movies",
    runMode: "automatic-organization",
    definitionItemLimit: 10,
    effectivePrimaryLimit: 10,
    phase: "ready",
    status: "completed",
    version: 3,
    progress: {
      phase: "walking",
      activeCursor: null,
      activeCursorsSeen: [],
      activeDirectory: null,
      counters: {
        activeSeconds: 0.01,
        errorEntries: 0,
        excludedEntries: 0,
        pageFetches: 1,
        primarySources: 1,
        unstableEntries: 0,
        visitedDirectories: 1,
        visitedEntries: 2,
      },
      findings: [],
      reasons: [],
      refusalReasons: [],
      incompleteReason: "none",
      materialRefusal: null,
      message: "",
      pendingDirectories: [],
      pendingFiles: [],
      scopeEntries: [{ kind: "directory", path: "" }],
    },
    counts: {
      visitedEntries: 2,
      visitedDirectories: 1,
      pageFetches: 1,
      primarySources: 1,
      excludedEntries: 0,
      unstableEntries: 0,
      errorEntries: 0,
      activeSeconds: 0.01,
    },
    primarySourceCount: 1,
    intentId: null,
    previewId: null,
    frozen: false,
    frozenAt: null,
    zeroMutation: true,
    sideEffects: "none",
    admissionRequestId: null,
    nextAction: "finalize the completed discovery to review its exact Preview",
    actions: {
      pause: action(),
      cancel: action(),
      resume: action(),
      finalize: action({
        available: true,
        durableOutcome:
          "the complete bounded manifest is frozen and an exact zero-mutation " +
          "manual Preview is stored",
        nextAction:
          "review the exact Preview of the frozen manifest, then separately " +
          "confirm execution",
      }),
      narrowScope: action(),
      preview: action({ method: "GET" }),
    },
  };
  return { ...value, ...overrides };
}

/** The frozen Run once projection after its exact plan is durably linked. */
function frozenRunOnceDocument(previewId: string | null): Json {
  const value = runOnceDocument({
    phase: "frozen",
    intentId: INTENT_ID,
    previewId,
    frozen: true,
    frozenAt: "2026-10-21T23:47:21+00:00",
    version: 5,
    nextAction:
      "review the exact zero-mutation manual Preview of the frozen manifest, " +
      "then separately confirm execution",
    actions: {
      pause: action(),
      cancel: action(),
      resume: action(),
      finalize: action(),
      narrowScope: action(),
      preview: action({
        available: true,
        method: "GET",
        path:
          previewId === null
            ? null
            : `/api/v1/operations/organize/previews/${previewId}`,
        nextAction:
          "review the frozen manifest's exact plan summary in this Run once",
      }),
    },
  });
  return value;
}

function previewDocument(): Json {
  const value = JSON.parse(
    JSON.stringify(documents["organizePreviewDetail"]),
  ) as Json;
  value["previewId"] = PREVIEW_ID;
  value["intentId"] = INTENT_ID;
  value["executionCandidateItemIds"] = ["item-1"];
  const items = value["items"] as Json[];
  items[0]!["itemId"] = "item-1";
  const selection = value["selection"] as Json;
  selection["selectedItemIds"] = ["item-1"];
  selection["unselectedItemIds"] = [];
  const actions = value["actions"] as Json;
  (actions["execute"] as Json)["available"] = true;
  (actions["execute"] as Json)["reason"] = null;
  (actions["execute"] as Json)["path"] =
    `/api/v1/operations/organize/previews/${PREVIEW_ID}/execute`;
  return value;
}

describe("V2 Automation Run once journey", () => {
  it("restores the frozen plan at the same URL after a reload without re-freezing", async () => {
    const user = userEvent.setup();
    let frozen = false;
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "operator" });
      }
      if (call.url === API_PATH && call.method === "GET") {
        // The durable Run once record resolves its exact plan from the linked
        // intent association, so a reload reads the same plan identity back.
        return jsonResponse(
          frozen ? frozenRunOnceDocument(PREVIEW_ID) : runOnceDocument(),
        );
      }
      if (call.url === `${API_PATH}/finalize` && call.method === "POST") {
        frozen = true;
        const response = frozenRunOnceDocument(PREVIEW_ID);
        response["preview"] = previewDocument();
        response["previewPath"] = `/operations/organize/preview/${PREVIEW_ID}`;
        return jsonResponse(response, 201);
      }
      if (call.url === `/api/v1/operations/organize/previews/${PREVIEW_ID}`) {
        return jsonResponse(previewDocument());
      }
      if (
        call.method === "GET" &&
        call.url.startsWith("/api/v1/operations/organize/executions?previewId=")
      ) {
        return jsonResponse({
          journey: "organize",
          items: [],
          limit: 100,
          total: 0,
          truncated: false,
        });
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      `/ui-v2/operations/automation/run-once/${DISCOVERY_ID}`,
    );
    await screen.findByRole("heading", { name: "运行一次" });
    await user.click(
      await screen.findByRole("button", { name: "冻结清单并生成计划摘要" }),
    );
    await screen.findByRole("heading", { name: "本次运行计划的零变更摘要" });
    // The exact plan identity travels in the journey URL so a reload, a
    // Back/Forward step or a re-opened link restores it.
    expect(
      new URLSearchParams(router.history.location.search).get("plan"),
    ).toBe(PREVIEW_ID);
    const finalizeCount = calls.filter(
      (call) => call.url === `${API_PATH}/finalize`,
    ).length;

    // A hard reload with an empty query cache: the same durable Run once read
    // must restore the same plan summary without another Finalize.
    cleanup();
    renderApp(router.history.location.href);
    await screen.findByText("来源清单已冻结");
    expect(
      await screen.findByRole("heading", { name: "本次运行计划的零变更摘要" }),
    ).toBeVisible();
    expect(screen.getByText(new RegExp(`计划 ${PREVIEW_ID}`))).toBeVisible();
    expect(
      calls.filter((call) => call.url === `${API_PATH}/finalize`),
    ).toHaveLength(finalizeCount);
    // Re-reading the plan is inert: no execution was submitted.
    expect(
      calls.some(
        (call) => call.method === "POST" && call.url.endsWith("/execute"),
      ),
    ).toBe(false);
  });

  it("keeps the finalize action and plan route available after the manifest froze", async () => {
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "operator" });
      }
      if (call.url === API_PATH && call.method === "GET") {
        return jsonResponse(frozenRunOnceDocument(PREVIEW_ID));
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(`/ui-v2/operations/automation/run-once/${DISCOVERY_ID}`);

    await screen.findByText("来源清单已冻结");
    // The plan summary is restored from the durable association, and the
    // already-frozen manifest offers no second freeze action.
    expect(
      await screen.findByRole("heading", { name: "本次运行计划的零变更摘要" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "冻结清单并生成计划摘要" }),
    ).toBeNull();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
  });

  it("refuses a stale URL plan that no longer names this Run once's plan", async () => {
    recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "operator" });
      }
      if (call.url === API_PATH && call.method === "GET") {
        // A newer durable plan supersedes the stale URL hint: the same page
        // shows the current plan, never the one the address still names.
        return jsonResponse(frozenRunOnceDocument(PREVIEW_ID));
      }
      if (call.url === `/api/v1/operations/organize/previews/${PREVIEW_ID}`) {
        return jsonResponse(previewDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(
      `/ui-v2/operations/automation/run-once/${DISCOVERY_ID}?plan=preview-stale`,
    );

    await screen.findByText("来源清单已冻结");
    expect(
      await screen.findByRole("heading", { name: "本次运行计划的零变更摘要" }),
    ).toBeVisible();
    expect(screen.getByText(new RegExp(`计划 ${PREVIEW_ID}`))).toBeVisible();
    expect(screen.queryByText(/计划 preview-stale/)).toBeNull();
  });

  it("offers only the explicit freeze action while the manifest is not frozen", async () => {
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "operator" });
      }
      if (call.url === API_PATH && call.method === "GET") {
        return jsonResponse(runOnceDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(`/ui-v2/operations/automation/run-once/${DISCOVERY_ID}`);

    expect(
      await screen.findByRole("button", { name: "冻结清单并生成计划摘要" }),
    ).toBeEnabled();
    // No plan exists yet, so no summary and no execution control is rendered.
    expect(
      screen.queryByRole("heading", { name: "本次运行计划的零变更摘要" }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /确认整理/ })).toBeNull();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    expect(screen.queryByRole("button", { name: "暂停分析" })).toBeNull();
  });
});
