/**
 * Slice53 RO-3 (`V2-OPS-019`): the stable Organize receiving route.
 *
 * The Task Center's existing `继续整理` / `查看只读摘要` links still address
 * `/operations/organize/new`. These tests enter through that real route and
 * prove it now opens the same per-file dialog the Files page uses, reads only
 * the exact durable preparation, preserves the read-only ended boundary and
 * never starts admission, analysis or execution by being opened.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;
const TOKEN = "receive-route-token";
const DISCOVERY_ID = "prep-1";
const INTENT_ID = "intent-1";
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

function action() {
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
      scopes: [{ kind: "file", path: "Movies/One.2001.mkv" }],
      existing: [],
      refused: [],
    },
    budgets: {},
    progress: {
      phase: "prepared",
      visitedEntries: 1,
      visitedDirectories: 0,
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
    organizeFlow: {
      taskId: "organize-task-1",
      status: "running",
      continuable: true,
    },
    admissionRequestId: null,
    autoPrepare: true,
    prepared: true,
    previewId: PREVIEW_ID,
    intentId: INTENT_ID,
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

function previewDocument(): Json {
  const value = clone("organizePreviewDetail");
  value["previewId"] = PREVIEW_ID;
  value["intentId"] = INTENT_ID;
  value["current"] = true;
  const items = value["items"] as Json[];
  const first = items[0]!;
  first["itemId"] = "item-1";
  first["previewItemId"] = "pitem-1";
  const source = first["source"] as Json;
  source["path"] = "Movies/One.2001.mkv";
  source["filename"] = "One.2001.mkv";
  (value["selection"] as Json)["selectedItemIds"] = ["item-1"];
  (value["selection"] as Json)["unselectedItemIds"] = [];
  value["executionCandidateItemIds"] = ["item-1"];
  const execute = (value["actions"] as Json)["execute"] as Json;
  execute["path"] =
    `/api/v1/operations/organize/previews/${PREVIEW_ID}/execute`;
  return value;
}

function intentDocument(): Json {
  const value = clone("organizeIntentChoice");
  value["intentId"] = INTENT_ID;
  const items = value["items"] as Json[];
  const first = items[0]!;
  first["itemId"] = "item-1";
  const source = first["source"] as Json;
  source["path"] = "Movies/One.2001.mkv";
  source["filename"] = "One.2001.mkv";
  const choice = (value["actions"] as Json)["choice"] as Json;
  choice["path"] =
    `/api/v1/operations/organize/intents/${INTENT_ID}/items/{itemId}/choice`;
  // The backend's read-only latest-plan association of the ended work.
  value["latestPlan"] = {
    previewId: PREVIEW_ID,
    status: "previewed",
    current: true,
    intentVersion: 2,
    createdAt: "2026-01-01T00:00:00+00:00",
    updatedAt: "2026-01-01T00:00:00+00:00",
    truncated: false,
  };
  return value;
}

interface BackendState {
  intentUnavailable: boolean;
}

function stubBackend(
  state: BackendState,
  discoveryOverrides: Record<string, unknown> = {},
) {
  const calls = {
    discoveryPosts: [] as string[],
    analyzePosts: [] as string[],
    executePosts: [] as string[],
    intentReads: 0,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (
        url === `/api/v1/operations/organize/discoveries/${DISCOVERY_ID}` &&
        method === "GET"
      ) {
        return jsonResponse(discoveryDocument(discoveryOverrides));
      }
      if (
        /\/operations\/organize\/discoveries\/[^/]+\/analyze$/.test(url) &&
        method === "POST"
      ) {
        calls.analyzePosts.push(url);
        return jsonResponse(discoveryDocument(discoveryOverrides));
      }
      if (
        url === `/api/v1/operations/organize/intents/${INTENT_ID}` &&
        method === "GET"
      ) {
        calls.intentReads += 1;
        if (state.intentUnavailable) {
          return jsonResponse({ error: { code: "unavailable" } }, 503);
        }
        return jsonResponse(intentDocument());
      }
      if (
        url === `/api/v1/operations/organize/previews/${PREVIEW_ID}` &&
        method === "GET"
      ) {
        return jsonResponse(previewDocument());
      }
      if (url.startsWith("/api/v1/operations/organize/executions")) {
        return jsonResponse({
          items: [],
          total: 0,
          limit: 100,
          truncated: false,
        });
      }
      if (/\/operations\/organize\/previews\/[^/]+\/execute$/.test(url)) {
        calls.executePosts.push(url);
        return jsonResponse({ executionId: "exec-1", taskId: "task-1" }, 202);
      }
      if (
        /\/resource-libraries\/[^/]+\/files\/discoveries$/.test(url) &&
        method === "POST"
      ) {
        calls.discoveryPosts.push(url);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return calls;
}

function renderPreparedRoute(extra = ""): void {
  authStore.setToken(TOKEN);
  renderApp(
    `/ui-v2/operations/organize/new?discoveryId=${DISCOVERY_ID}` +
      `&resourceLibraryId=library${extra}`,
  );
}

describe("Organize receiving route", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    authStore.clearToken();
  });

  it("guides a generic creation URL to Files without starting work", async () => {
    const calls = stubBackend({ intentUnavailable: false });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/organize/new");

    expect(
      await screen.findByRole("heading", { name: "从资源库文件页开始整理" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "返回任务中心" })).toHaveAttribute(
      "href",
      "/ui-v2/operations",
    );
    expect(calls.discoveryPosts).toHaveLength(0);
    expect(calls.analyzePosts).toHaveLength(0);
    expect(calls.executePosts).toHaveLength(0);
  });

  it("opens the exact prepared work in the same per-file dialog by read-only navigation", async () => {
    const calls = stubBackend({ intentUnavailable: false });
    renderPreparedRoute("&returnOps=run%3Dorganize-task-1");

    const dialog = await screen.findByRole("dialog", {
      name: "整理所选文件",
    });
    expect(
      await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ }),
    ).toBeVisible();
    expect(within(dialog).getAllByText("One.2001.mkv").length).toBeGreaterThan(
      0,
    );
    expect(
      within(dialog).getByRole("button", { name: /整批复核/ }),
    ).toBeVisible();
    // Opening a preparation link is a pure read: no admission, no analysis,
    // no execution.
    expect(calls.discoveryPosts).toHaveLength(0);
    expect(calls.analyzePosts).toHaveLength(0);
    expect(calls.executePosts).toHaveLength(0);
  });

  it("leaves the route after an explicit unsaved-draft discard", async () => {
    const user = userEvent.setup();
    const calls = stubBackend({ intentUnavailable: false });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      `/ui-v2/operations/organize/new?discoveryId=${DISCOVERY_ID}` +
        `&resourceLibraryId=library&returnOps=${encodeURIComponent("run=organize-task-1")}`,
    );

    const dialog = await screen.findByRole("dialog", {
      name: "整理所选文件",
    });
    await user.selectOptions(
      await within(dialog).findByLabelText("识别类型 One.2001.mkv"),
      "B",
    );
    await user.click(within(dialog).getByRole("button", { name: "关闭" }));
    expect(
      await within(dialog).findByText(/有尚未保存的逐文件修正草稿/),
    ).toBeVisible();
    await user.click(
      within(dialog).getByRole("button", { name: "放弃草稿并关闭" }),
    );

    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/operations"),
    );
    expect(new URLSearchParams(router.history.location.search).get("run")).toBe(
      "organize-task-1",
    );
    // Browsing, editing a draft and leaving never saved, analyzed or executed.
    expect(calls.analyzePosts).toHaveLength(0);
    expect(calls.executePosts).toHaveLength(0);
  });

  it("closes an originated continuation back to the exact task-center run", async () => {
    const user = userEvent.setup();
    const calls = stubBackend({ intentUnavailable: false });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      `/ui-v2/operations/organize/new?discoveryId=${DISCOVERY_ID}` +
        `&resourceLibraryId=library&returnOps=${encodeURIComponent("run=organize-task-1")}`,
    );

    const dialog = await screen.findByRole("dialog", {
      name: "整理所选文件",
    });
    await user.click(within(dialog).getByRole("button", { name: "关闭" }));

    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/operations"),
    );
    expect(new URLSearchParams(router.history.location.search).get("run")).toBe(
      "organize-task-1",
    );
    // Closing the card never cancels, replays or starts durable work.
    expect(calls.discoveryPosts).toHaveLength(0);
    expect(calls.analyzePosts).toHaveLength(0);
    expect(calls.executePosts).toHaveLength(0);
  });

  it("opens ended work as the same dialog's read-only original summary", async () => {
    const calls = stubBackend(
      { intentUnavailable: false },
      {
        status: "completed",
        organizeFlow: {
          taskId: "organize-task-1",
          status: "completed",
          continuable: false,
        },
      },
    );
    renderPreparedRoute();

    const dialog = await screen.findByRole("dialog", {
      name: "整理所选文件",
    });
    expect(await within(dialog).findByText(/本次整理工作已结束/)).toBeVisible();
    const history = await within(dialog).findByRole("region", {
      name: "只读原计划摘要",
    });
    expect(within(history).getByText(/方案 preview-1/)).toBeVisible();
    expect(
      within(history).getAllByText(/One\.2001\.mkv/).length,
    ).toBeGreaterThan(0);
    // Ended work has no paging, batch review or confirmation affordance.
    expect(
      within(dialog).queryByRole("button", { name: /确认整理/ }),
    ).toBeNull();
    expect(
      within(dialog).queryByRole("button", { name: /整批复核/ }),
    ).toBeNull();
    expect(
      within(dialog).queryByRole("button", { name: /保存并重新分析/ }),
    ).toBeNull();
    expect(calls.analyzePosts).toHaveLength(0);
    expect(calls.executePosts).toHaveLength(0);
  });

  it("reports a failed original-summary read and retries it in place", async () => {
    const user = userEvent.setup();
    const state = { intentUnavailable: true };
    const calls = stubBackend(state, {
      status: "analyzing",
      prepared: false,
      previewId: null,
      organizeFlow: {
        taskId: "organize-task-1",
        status: "failed",
        continuable: false,
      },
    });
    renderPreparedRoute();

    const dialog = await screen.findByRole("dialog", {
      name: "整理所选文件",
    });
    expect(
      await within(dialog).findByText(/原计划摘要暂时无法读取/),
    ).toBeVisible();
    // The failure is a read failure, never "this work never had a summary".
    expect(within(dialog).queryByText(/从未生成过计划摘要/)).toBeNull();

    state.intentUnavailable = false;
    await user.click(
      within(dialog).getByRole("button", { name: "重新读取原计划摘要" }),
    );
    await vi.waitFor(() => expect(calls.intentReads).toBeGreaterThan(1));
    expect(
      await within(dialog).findByRole("region", { name: "只读原计划摘要" }),
    ).toBeVisible();
  });

  it("states plainly when ended work never generated a summary", async () => {
    stubBackend(
      { intentUnavailable: false },
      {
        status: "failed",
        prepared: false,
        previewId: null,
        intentId: null,
        organizeFlow: {
          taskId: "organize-task-1",
          status: "failed",
          continuable: false,
        },
      },
    );
    renderPreparedRoute();

    const dialog = await screen.findByRole("dialog", {
      name: "整理所选文件",
    });
    expect(await within(dialog).findByText(/从未生成过计划摘要/)).toBeVisible();
    expect(
      within(dialog).queryByRole("region", { name: "只读原计划摘要" }),
    ).toBeNull();
  });
});
