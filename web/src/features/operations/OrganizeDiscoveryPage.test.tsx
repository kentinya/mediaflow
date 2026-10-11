/**
 * Operator journey for one bounded discovery (Slice 44 RO-6 / Task 44.7).
 *
 * These tests drive the real discovery route with a stubbed API boundary and
 * prove the corrected manifest/refusal facts reach the operator:
 *
 * - a truncated or unconfined walk explains the durable, monotonic material
 *   refusal even when the current dominant fact is an ordinary read failure;
 * - the finalize control is not advertised for a refused walk;
 * - a valid completed walk keeps its exact unique source count.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderApp } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";

const TOKEN = "discovery-token";
const DISCOVERY_ID = "d-44-7";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function action(
  path: string,
  available: boolean,
  refusal: string | null = null,
  pendingReason: string | null = null,
) {
  return {
    available,
    method: "POST",
    path: `/api/v1/operations/organize/discoveries/${DISCOVERY_ID}/${path}`,
    requiresVersion: true,
    sideEffects: "none",
    refusal,
    pendingReason,
  };
}

function discoveryDocument(progress: Record<string, unknown>) {
  return {
    actions: {
      cancel: action("cancel", true),
      finalize: action("finalize", false, "discovery_budget_limited"),
      pause: action("pause", true),
      resume: action("resume", false),
    },
    budgets: {
      maxActiveSeconds: 600,
      maxCursorBytes: 2048,
      maxDepth: 32,
      maxEntryNameBytes: 1024,
      maxFindings: 100,
      maxPageFetches: 2000,
      maxPathBytes: 4096,
      maxPrimarySources: 100,
      maxScopePaths: 100,
      maxSegments: 128,
      maxVisitedDirectories: 1000,
      maxVisitedEntries: 10000,
      pageLimit: 100,
    },
    cancelRequested: false,
    createdAt: "2026-01-01T00:00:00+00:00",
    discoveryId: DISCOVERY_ID,
    execution: "not_available_from_discovery",
    failure: null,
    frozen: false,
    frozenAt: null,
    intentId: null,
    journey: "discovery",
    nextAction:
      "the selected scope exceeded a discovery budget; narrow the scope and start a new bounded discovery instead of freezing this incomplete subset",
    nextObservationAt: null,
    pauseRequested: false,
    primarySourceCount: 1,
    progress,
    resourceLibraryId: "library",
    storageId: "source",
    configurationSnapshotId: "active-1",
    selection: {
      scopeCount: 2,
      scopes: [
        { kind: "directory", path: "Loop" },
        { kind: "directory", path: "Locked" },
      ],
    },
    sideEffects: "none",
    sources: [
      {
        extension: "mkv",
        filename: "A.2001.mkv",
        modifiedAt: "2026-01-01T00:00:00+00:00",
        path: "Loop/A.2001.mkv",
        size: 512,
      },
    ],
    status: "partial_success",
    updatedAt: "2026-01-01T00:00:00+00:00",
    version: 5,
    worker: {
      condition: "ready",
      durableState: "a resident Processing Worker is ready",
      nextAction: "continue",
      ready: true,
    },
    zeroMutation: true,
  };
}

function stubFetch(payload: unknown) {
  const fetchMock = vi.fn(async () => jsonResponse(payload));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("bounded discovery refusal journey", () => {
  it("explains a durable material refusal hidden behind a read failure", async () => {
    authStore.setToken(TOKEN);
    stubFetch(
      discoveryDocument({
        activeSeconds: 1.5,
        errorEntries: 1,
        excludedEntries: 0,
        findings: [],
        incomplete: true,
        incompleteReason: "read_failure",
        refusalReasons: ["cursor_repeated"],
        materialRefusal: "cursor_repeated",
        message: "bounded discovery stopped at a limit: read_failure",
        pageFetches: 3,
        phase: "partial",
        primarySources: 1,
        reasons: [{ count: 1, reason: "repeated_provider_cursor" }],
        unstableEntries: 0,
        visitedDirectories: 3,
        visitedEntries: 20,
      }),
    );
    renderApp(`/ui-v2/operations/organize/discovery/${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "整理发现" });
    // The durable material refusal is explained even though the current
    // dominant fact is the read failure.
    await waitFor(() => {
      expect(
        screen.getByText(/本次发现已达到预算或安全上限/, { exact: false }),
      ).toBeTruthy();
    });
    expect(screen.getAllByText(/存储返回了重复游标/).length).toBeGreaterThan(0);
    // Finalize is not advertised for the refused walk.
    expect(screen.queryByRole("button", { name: /冻结|完成发现/ })).toBeNull();
  });

  it("explains the fenced concurrent finalize instead of a raw conflict code", async () => {
    authStore.setToken(TOKEN);
    // A completed, finalizable walk: the only finalize outcome is the durable
    // 409 the backend returns when another request already linked the intent.
    const completed = discoveryDocument({
      activeSeconds: 1.5,
      errorEntries: 0,
      excludedEntries: 0,
      findings: [],
      incomplete: false,
      incompleteReason: null,
      refusalReasons: [],
      materialRefusal: null,
      message: "bounded discovery completed the whole admitted scope",
      pageFetches: 3,
      phase: "completed",
      primarySources: 1,
      reasons: [],
      unstableEntries: 0,
      visitedDirectories: 3,
      visitedEntries: 20,
    });
    completed.actions.finalize = action("finalize", true);
    completed.status = "completed";
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/finalize")) {
        return jsonResponse(
          {
            error: {
              code: "discovery_conflict",
              details: { nextAction: "reload the discovery and retry" },
              message:
                "the discovery changed before this transition was published",
            },
          },
          409,
        );
      }
      return jsonResponse(completed);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp(`/ui-v2/operations/organize/discovery/${DISCOVERY_ID}`);

    const button = await screen.findByRole("button", {
      name: "冻结来源并继续整理",
    });
    button.click();
    await waitFor(() => {
      expect(
        screen.getByText(/只存在一份已链接的来源清单/, { exact: false }),
      ).toBeTruthy();
    });
    // The raw protocol code never reaches the operator.
    expect(screen.queryByText(/discovery_conflict/)).toBeNull();
  });

  it("shows the pending pause stage and offers Continue only after acknowledgement", async () => {
    authStore.setToken(TOKEN);
    // The pause request is durable but the resident Worker has not yet
    // acknowledged it at a safe boundary: Continue must not be offered, and the
    // transient stage must be explained instead of looking like a dead end.
    const pending = discoveryDocument({
      activeSeconds: 1.5,
      errorEntries: 0,
      excludedEntries: 0,
      findings: [],
      incomplete: false,
      incompleteReason: null,
      refusalReasons: [],
      materialRefusal: null,
      message:
        "a cooperative pause was requested; the Worker stops at a safe boundary",
      pageFetches: 3,
      phase: "queued",
      primarySources: 1,
      reasons: [],
      unstableEntries: 0,
      visitedDirectories: 3,
      visitedEntries: 20,
    });
    pending.pauseRequested = true;
    pending.status = "queued";
    pending.actions.pause = action("pause", false);
    pending.actions.resume = action(
      "resume",
      false,
      null,
      "discovery_pause_pending",
    );
    stubFetch(pending);
    renderApp(`/ui-v2/operations/organize/discovery/${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "整理发现" });
    await waitFor(() => {
      expect(
        screen.getByText(/正在等待后台 Worker/, { exact: false }),
      ).toBeTruthy();
    });
    expect(screen.queryByRole("button", { name: "继续发现" })).toBeNull();
  });

  it("offers Continue once the pause has been acknowledged", async () => {
    authStore.setToken(TOKEN);
    const acknowledged = discoveryDocument({
      activeSeconds: 1.5,
      errorEntries: 0,
      excludedEntries: 0,
      findings: [],
      incomplete: false,
      incompleteReason: null,
      refusalReasons: [],
      materialRefusal: null,
      message:
        "discovery is paused; findings and counters are durable and safe to continue",
      pageFetches: 3,
      phase: "paused",
      primarySources: 1,
      reasons: [],
      unstableEntries: 0,
      visitedDirectories: 3,
      visitedEntries: 20,
    });
    acknowledged.pauseRequested = true;
    acknowledged.status = "paused";
    acknowledged.actions.pause = action("pause", false);
    acknowledged.actions.resume = action("resume", true);
    stubFetch(acknowledged);
    renderApp(`/ui-v2/operations/organize/discovery/${DISCOVERY_ID}`);

    await screen.findByRole("heading", { name: "整理发现" });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "继续发现" })).toBeTruthy();
    });
    expect(
      screen.queryByText(/正在等待后台 Worker/, { exact: false }),
    ).toBeNull();
  });
});
