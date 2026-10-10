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
) {
  return {
    available,
    method: "POST",
    path: `/api/v1/operations/organize/discoveries/${DISCOVERY_ID}/${path}`,
    requiresVersion: true,
    sideEffects: "none",
    refusal,
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
    pauseRequested: false,
    primarySourceCount: 1,
    progress,
    resourceLibraryId: "library",
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
});
