import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { clearPrincipalSessionData } from "../../shared/auth/principal-session-data";
import {
  beginRunOnceSubmission,
  clearRunOnceIntent,
  readRunOnceSession,
} from "./automation-run-once-session";

const PRINCIPAL = "operator-1";
const PRINCIPAL_SEGMENT = principalIdStorageSegment(PRINCIPAL);
const LEGACY_PREFIX = "mediaflow.operations.automation-run-once-intent:";
const LIST_PREFIX = "mediaflow.operations.automation-run-once-intents:";
const REQUEST = "11111111-1111-4111-8111-111111111111";

function listKey(definitionId: string): string {
  return `${LIST_PREFIX}${PRINCIPAL_SEGMENT}:${encodeURIComponent(definitionId)}`;
}

function stubRequestId(value: string | null) {
  vi.stubGlobal("crypto", {
    randomUUID: () => {
      if (value === null) throw new Error("no entropy");
      return value;
    },
  });
}

beforeEach(() => {
  window.sessionStorage.clear();
  stubRequestId(REQUEST);
});

afterEach(() => {
  window.sessionStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("automation Run-once session", () => {
  it("persists independent requests per definition without overwriting another row", () => {
    const first = beginRunOnceSubmission(PRINCIPAL, "nightly");
    expect(first.ok).toBe(true);
    stubRequestId("22222222-2222-4222-8222-222222222222");
    const second = beginRunOnceSubmission(PRINCIPAL, "weekly");
    expect(second.ok).toBe(true);

    const read = readRunOnceSession(PRINCIPAL);
    expect(read.invalidLegacy).toBe(false);
    expect(read.pending).toEqual([
      {
        definitionId: "nightly",
        requestId: REQUEST,
        legacy: false,
      },
      {
        definitionId: "weekly",
        requestId: "22222222-2222-4222-8222-222222222222",
        legacy: false,
      },
    ]);
  });

  it("refuses a second request for the same row instead of overwriting its identity", () => {
    expect(beginRunOnceSubmission(PRINCIPAL, "nightly").ok).toBe(true);
    stubRequestId("33333333-3333-4333-8333-333333333333");
    expect(beginRunOnceSubmission(PRINCIPAL, "nightly")).toEqual({
      ok: false,
      reason: "already-pending",
    });
    expect(readRunOnceSession(PRINCIPAL).pending).toEqual([
      { definitionId: "nightly", requestId: REQUEST, legacy: false },
    ]);
  });

  it("reads the retired edit-page key for exact reconciliation and never resubmits it", () => {
    window.sessionStorage.setItem(
      `${LEGACY_PREFIX}${PRINCIPAL_SEGMENT}`,
      JSON.stringify({
        definitionId: "nightly",
        requestId: "legacy-request",
        authority: {
          revisionId: "revision-old",
          version: 2,
          digest: "a".repeat(64),
        },
        fingerprint: "fingerprint",
      }),
    );
    expect(readRunOnceSession(PRINCIPAL).pending).toEqual([
      {
        definitionId: "nightly",
        requestId: "legacy-request",
        legacy: true,
      },
    ]);
    expect(beginRunOnceSubmission(PRINCIPAL, "nightly")).toEqual({
      ok: false,
      reason: "already-pending",
    });
  });

  it("reports an invalid old value without turning it into a new run", () => {
    window.sessionStorage.setItem(
      `${LEGACY_PREFIX}${PRINCIPAL_SEGMENT}`,
      JSON.stringify({ definitionId: "", requestId: "" }),
    );
    expect(readRunOnceSession(PRINCIPAL)).toEqual({
      pending: [],
      invalidLegacy: true,
    });
    expect(beginRunOnceSubmission(PRINCIPAL, "nightly").ok).toBe(true);
    expect(readRunOnceSession(PRINCIPAL).invalidLegacy).toBe(true);
  });

  it("does not send work when no random request identity exists", () => {
    stubRequestId(null);
    vi.stubGlobal("crypto", {});
    const result = beginRunOnceSubmission(PRINCIPAL, "nightly");
    expect(result).toEqual({ ok: false, reason: "request-id-unavailable" });
    expect(window.sessionStorage.getItem(listKey("nightly"))).toBeNull();
  });

  it("does not send work when the reconciliation context cannot be stored", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(beginRunOnceSubmission(PRINCIPAL, "nightly")).toEqual({
      ok: false,
      reason: "storage-unavailable",
    });
  });

  it("keeps the pending population bounded without dropping existing rows", () => {
    for (let index = 0; index < 20; index += 1) {
      window.sessionStorage.setItem(
        listKey(`definition-${index}`),
        JSON.stringify({
          version: 1,
          definitionId: `definition-${index}`,
          requestId: `request-${index}`,
          createdAt: index,
        }),
      );
    }
    expect(readRunOnceSession(PRINCIPAL).pending).toHaveLength(20);
    expect(beginRunOnceSubmission(PRINCIPAL, "one-more")).toEqual({
      ok: false,
      reason: "capacity",
    });
    expect(readRunOnceSession(PRINCIPAL).pending).toHaveLength(20);
  });

  it("clears only the exact request and the matching legacy entry", () => {
    beginRunOnceSubmission(PRINCIPAL, "nightly");
    beginRunOnceSubmission(PRINCIPAL, "weekly");
    window.sessionStorage.setItem(
      `${LEGACY_PREFIX}${PRINCIPAL_SEGMENT}`,
      JSON.stringify({
        definitionId: "legacy-definition",
        requestId: "legacy",
      }),
    );

    clearRunOnceIntent(PRINCIPAL, "nightly");
    expect(
      readRunOnceSession(PRINCIPAL).pending.map((item) => item.definitionId),
    ).toEqual(["legacy-definition", "weekly"]);

    clearRunOnceIntent(PRINCIPAL, "legacy-definition", "different-request");
    expect(
      readRunOnceSession(PRINCIPAL).pending.map((item) => item.definitionId),
    ).toEqual(["legacy-definition", "weekly"]);

    clearRunOnceIntent(PRINCIPAL, "legacy-definition", "legacy");
    expect(
      readRunOnceSession(PRINCIPAL).pending.map((item) => item.definitionId),
    ).toEqual(["weekly"]);
  });

  it("does not clear a row's newer request with an older request identity", () => {
    beginRunOnceSubmission(PRINCIPAL, "nightly");
    clearRunOnceIntent(PRINCIPAL, "nightly", "older-request");
    expect(readRunOnceSession(PRINCIPAL).pending).toEqual([
      { definitionId: "nightly", requestId: REQUEST, legacy: false },
    ]);
    clearRunOnceIntent(PRINCIPAL, "nightly", REQUEST);
    expect(readRunOnceSession(PRINCIPAL).pending).toEqual([]);
  });

  it("drops every run-once session key when the principal changes", () => {
    beginRunOnceSubmission(PRINCIPAL, "nightly");
    window.sessionStorage.setItem(
      `${LEGACY_PREFIX}${PRINCIPAL_SEGMENT}`,
      JSON.stringify({ definitionId: "old", requestId: "old-request" }),
    );
    window.sessionStorage.setItem("unrelated", "keep");
    clearPrincipalSessionData();
    const remaining: string[] = [];
    for (let index = 0; index < window.sessionStorage.length; index += 1) {
      const key = window.sessionStorage.key(index);
      if (
        key !== null &&
        (key.startsWith(LEGACY_PREFIX) || key.startsWith(LIST_PREFIX))
      ) {
        remaining.push(key);
      }
    }
    expect(remaining).toEqual([]);
    expect(window.sessionStorage.getItem("unrelated")).toBe("keep");
  });
});
