import recordFixture from "../../../tests/fixtures/automation-records-prestart.json";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  automationRecordsUrl,
  fetchAutomationRecords,
  admitAutomationRunOnce,
  reconcileAutomationRunOnce,
} from "./api-client";

const TOKEN = "memory-only-token-value";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  implementation: () => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function runOnceDocument(overrides: Record<string, unknown> = {}) {
  return {
    journey: "automation-run-once",
    executionKind: "organizing",
    discoveryId: "task-1",
    taskId: "task-1",
    definitionId: "nightly",
    definitionName: "Nightly",
    resourceLibraryId: "library",
    sourceScope: null,
    runMode: "automatic-organization",
    definitionItemLimit: 10,
    effectivePrimaryLimit: 10,
    phase: "discovering",
    status: "queued",
    version: 1,
    primarySourceCount: 0,
    progress: {
      counters: {
        visitedEntries: 1,
        excludedEntries: 0,
        unstableEntries: 0,
        errorEntries: 0,
      },
      incompleteReason: "none",
      message: "queued",
    },
    refusalReason: null,
    frozen: false,
    frozenAt: null,
    intentId: null,
    previewId: null,
    nextAction: "inspect the linked Task Center run",
    error: null,
    actions: {},
    ...overrides,
  };
}

describe("definition Run once admission", () => {
  it("sends only the observed revision fields and omits an unobserved digest", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(runOnceDocument(), 202),
    );
    const result = await admitAutomationRunOnce(TOKEN, {
      definitionId: "nightly",
      admissionRequestId: "11111111-1111-4111-8111-111111111111",
      expectedRevisionId: "revision-1",
      expectedRevisionVersion: 4,
    });
    expect(result.ok).toBe(true);
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(input).toBe(
      "/api/v1/operations/automation/definitions/nightly/run-once",
    );
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      admissionRequestId: "11111111-1111-4111-8111-111111111111",
      expectedRevisionId: "revision-1",
      expectedRevisionVersion: 4,
    });
    expect(String(init.body)).not.toContain("expectedRevisionDigest");
    expect(String(init.body)).not.toContain("expectedDefinitionFingerprint");
  });

  it("keeps explicitly supplied fence evidence exact", async () => {
    const fetchMock = stubFetch(async () =>
      jsonResponse(runOnceDocument(), 202),
    );
    await admitAutomationRunOnce(TOKEN, {
      definitionId: "nightly",
      admissionRequestId: "request-1",
      expectedDefinitionFingerprint: "fingerprint-1",
      expectedRevisionId: "revision-1",
      expectedRevisionVersion: 4,
      expectedRevisionDigest: "a".repeat(64),
    });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({
      expectedDefinitionFingerprint: "fingerprint-1",
      expectedRevisionId: "revision-1",
      expectedRevisionVersion: 4,
      expectedRevisionDigest: "a".repeat(64),
    });
  });

  it("reconciles only by the caller's definition and request identity", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(runOnceDocument()));
    const result = await reconcileAutomationRunOnce(TOKEN, {
      definitionId: "nightly",
      admissionRequestId: "request-1",
    });
    expect(result.ok).toBe(true);
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(input).toBe(
      "/api/v1/operations/automation/definitions/nightly/run-once" +
        "?admissionRequestId=request-1",
    );
    expect(init.method ?? "GET").toBe("GET");
  });
});

describe("records-only outcome API", () => {
  it("adds a scoped outcome without changing legacy status filters", async () => {
    const fetchMock = stubFetch(async () => jsonResponse(recordFixture));
    const read = await fetchAutomationRecords(TOKEN, {
      outcome: "failed",
      status: "partial_success",
      definition: "auto-task",
      trigger: "scheduled",
      direction: "previous",
      cursor: "bounded",
      limit: 7,
    });
    expect(read.ok).toBe(true);
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const params = new URL(input, "http://test").searchParams;
    expect(params.get("outcome")).toBe("failed");
    expect(params.get("status")).toBe("partial_success");
    expect(params.get("direction")).toBe("previous");
    expect(init.method).toBe("GET");
    expect(automationRecordsUrl({ status: "failed" })).toBe(
      "/api/v1/operations/automation/records?status=failed",
    );
  });
});
