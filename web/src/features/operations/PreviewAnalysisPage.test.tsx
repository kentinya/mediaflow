import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

/**
 * Component/router proof for the durable exact Preview analysis page.
 *
 * The documents mirror the exact projection the real Python API publishes
 * (proved by tests/test_preview_analysis.py). The assertions prove the
 * operator journey and its safety properties: progress is shown while the
 * analysis runs, the exact linked Preview appears only for a completed
 * analysis, a control submits the observed durable version, and a rejected
 * control is reported once without any automatic replay.
 */

type Json = Record<string, unknown>;

const TOKEN = "preview-analysis-token";
const ANALYSIS_ID = "analysis-1";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: Json | null;
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
            ? (JSON.parse(init.body) as Json)
            : null,
      };
      calls.push(call);
      const response = respond(call);
      if (response !== undefined) {
        return response;
      }
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

function analysisDocument(overrides: Json = {}): Json {
  return {
    analysisId: ANALYSIS_ID,
    kind: "manual",
    actor: "operator",
    configurationSnapshotId: "snapshot-1",
    configurationSnapshotDigest: "a".repeat(64),
    status: "queued",
    version: 1,
    progress: {
      phase: "queued",
      message:
        "queued for durable exact analysis by the resident Processing Worker",
      visitedEntries: 4,
      analysedItems: 0,
      totalItems: 7,
    },
    definitionId: null,
    definitionFingerprint: null,
    intentId: "intent-1",
    intentVersion: 2,
    previewId: null,
    error: null,
    cancelRequested: false,
    pauseRequested: false,
    createdAt: "2026-01-01T00:00:00+00:00",
    updatedAt: "2026-01-01T00:00:00+00:00",
    admissionRequestId: null,
    zeroMutation: true,
    sideEffects: "none",
    previewPath: null,
    actions: {
      pause: { available: true },
      resume: { available: false },
      cancel: { available: true },
      preview: { available: false },
    },
    ...overrides,
  };
}

const DETAIL_URL = `/api/v1/operations/automation/preview-analyses/${ANALYSIS_ID}`;
const ROUTE = `/ui-v2/operations/automation/preview-analyses/${ANALYSIS_ID}`;

describe("PreviewAnalysisPage", () => {
  it("renders queued progress with pause/cancel and no preview link", async () => {
    recordingFetch((call) => {
      if (call.url === DETAIL_URL && call.method === "GET") {
        return jsonResponse(analysisDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(ROUTE);

    await screen.findByRole("heading", { name: "精确预览分析" });
    await screen.findByText("排队中");
    // The bounded progress counters and the durable message are visible.
    expect(screen.getByText("4")).toBeVisible();
    expect(screen.getByText("7")).toBeVisible();
    expect(screen.getByText(/queued for durable exact analysis/)).toBeVisible();
    // The zero-mutation statement is explicit (the page states it both in the
    // header and beside the progress).
    expect(
      screen.getAllByText(/分析只读取存储元数据，不会移动、复制或删除任何文件/)
        .length,
    ).toBeGreaterThanOrEqual(1);
    // The advertised controls exist and no Preview is linked yet.
    expect(screen.getByRole("button", { name: "暂停分析" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "取消分析" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "继续分析" })).toBeNull();
    expect(screen.queryByRole("link", { name: "打开精确预览" })).toBeNull();
    // Return links mirror the Run once page.
    expect(
      screen.getByRole("link", { name: "返回自动化列表" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "返回任务中心" }),
    ).toBeInTheDocument();
  });

  it("renders the exact Preview link for a completed analysis and no controls", async () => {
    recordingFetch((call) => {
      if (call.url === DETAIL_URL && call.method === "GET") {
        return jsonResponse(
          analysisDocument({
            status: "completed",
            version: 5,
            previewId: "preview-1",
            previewPath: "/operations/organize/preview/preview-1",
            progress: {
              phase: "completed",
              message: "the exact zero-mutation Preview is stored",
              visitedEntries: 12,
              analysedItems: 7,
              totalItems: 7,
            },
            actions: {
              pause: { available: false },
              resume: { available: false },
              cancel: { available: false },
              preview: { available: true },
            },
          }),
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(ROUTE);

    await screen.findByText("分析完成");
    const link = await screen.findByRole("link", { name: "打开精确预览" });
    // The exact Preview lives in the manual Organize route tree; the router
    // link carries the application basepath rather than a basepath-less URL.
    expect(link.getAttribute("href")).toContain(
      "/operations/organize/preview/preview-1",
    );
    // A settled analysis advertises no cooperative control.
    expect(screen.queryByRole("button", { name: "暂停分析" })).toBeNull();
    expect(screen.queryByRole("button", { name: "继续分析" })).toBeNull();
    expect(screen.queryByRole("button", { name: "取消分析" })).toBeNull();
  });

  it("sends the observed durable version when pausing", async () => {
    let paused = false;
    const { calls } = recordingFetch((call) => {
      if (call.url === DETAIL_URL && call.method === "GET") {
        return jsonResponse(
          paused
            ? analysisDocument({
                status: "paused",
                version: 4,
                progress: {
                  phase: "paused",
                  message:
                    "paused cooperatively; resume to continue the same analysis",
                  visitedEntries: 4,
                  analysedItems: 0,
                  totalItems: 7,
                },
                actions: {
                  pause: { available: false },
                  resume: { available: true },
                  cancel: { available: true },
                  preview: { available: false },
                },
              })
            : analysisDocument({ version: 3 }),
        );
      }
      if (call.url === `${DETAIL_URL}/pause` && call.method === "POST") {
        paused = true;
        return jsonResponse(
          analysisDocument({
            status: "paused",
            version: 4,
            progress: {
              phase: "paused",
              message:
                "paused cooperatively; resume to continue the same analysis",
              visitedEntries: 4,
              analysedItems: 0,
              totalItems: 7,
            },
            actions: {
              pause: { available: false },
              resume: { available: true },
              cancel: { available: true },
              preview: { available: false },
            },
          }),
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(ROUTE);

    await screen.findByText("排队中");
    await userEvent.click(
      await screen.findByRole("button", { name: "暂停分析" }),
    );
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.url === `${DETAIL_URL}/pause` && call.method === "POST",
        ),
      ).toBe(true),
    );
    const control = calls.find((call) => call.url === `${DETAIL_URL}/pause`);
    expect(control?.body).toEqual({ expectedVersion: 3 });
    await screen.findByText("已暂停");
  });

  it("reports a rejected control once with no automatic retry", async () => {
    let controlCalls = 0;
    recordingFetch((call) => {
      if (call.url === DETAIL_URL && call.method === "GET") {
        return jsonResponse(analysisDocument({ version: 3 }));
      }
      if (call.url === `${DETAIL_URL}/cancel` && call.method === "POST") {
        controlCalls += 1;
        return jsonResponse(
          {
            error: {
              code: "preview_analysis_conflict",
              message: "the analysis version is stale",
              details: { nextAction: "reload the durable analysis state" },
            },
          },
          409,
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(ROUTE);

    await screen.findByText("排队中");
    await userEvent.click(
      await screen.findByRole("button", { name: "取消分析" }),
    );
    await screen.findByText(/这次分析已被另一次操作更新/);
    // Exactly one control request was sent: an ambiguous rejection is never
    // replayed automatically.
    expect(controlCalls).toBe(1);
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(controlCalls).toBe(1);
  });
});
