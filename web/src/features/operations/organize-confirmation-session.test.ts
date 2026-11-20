import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { clearPrincipalSessionData } from "../../shared/auth/principal-session-data";
import {
  beginOrganizeConfirmationRetention,
  clearOrganizeConfirmation,
  organizeConfirmationKey,
  readOrganizeConfirmations,
  type OrganizeConfirmationWork,
} from "./organize-confirmation-session";

const PRINCIPAL = "operator-1";
const WORK: OrganizeConfirmationWork = {
  kind: "files",
  discoveryId: "discovery-1",
};
const SUBMISSION = {
  previewId: "preview-1",
  itemIds: ["item-1", "item-2"],
  expectedIntentVersion: 3,
  allowOverwrite: false,
  allowSourceCleanup: true,
};
const KEY = [
  "mediaflow.operations.organize-confirmations:" +
    principalIdStorageSegment(PRINCIPAL),
  "files",
  "discovery-1",
].join("|");

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("organize confirmation session", () => {
  it("retains the exact submitted request before the POST and reads it back", () => {
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, SUBMISSION),
    ).toEqual({ ok: true });
    expect(readOrganizeConfirmations(PRINCIPAL, WORK)).toEqual([
      { work: WORK, submission: SUBMISSION, retainedAt: expect.any(Number) },
    ]);
    expect(organizeConfirmationKey(WORK, SUBMISSION)).toBe(
      "files|discovery-1|preview-1|3|0|1|item-1,item-2",
    );
  });

  it("keeps batches and principals/work contexts isolated", () => {
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, SUBMISSION),
    ).toEqual({ ok: true });
    const second = {
      ...SUBMISSION,
      previewId: "preview-2",
      itemIds: ["item-3"],
    };
    expect(beginOrganizeConfirmationRetention(PRINCIPAL, WORK, second)).toEqual(
      { ok: true },
    );
    const otherWork: OrganizeConfirmationWork = {
      kind: "files",
      discoveryId: "discovery-2",
    };
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, otherWork, {
        ...SUBMISSION,
        previewId: "preview-9",
      }),
    ).toEqual({ ok: true });
    expect(
      beginOrganizeConfirmationRetention("operator-2", WORK, {
        ...SUBMISSION,
        previewId: "preview-8",
      }),
    ).toEqual({ ok: true });
    expect(
      readOrganizeConfirmations(PRINCIPAL, WORK).map(
        (entry) => entry.submission.previewId,
      ),
    ).toEqual(["preview-1", "preview-2"]);
    expect(
      readOrganizeConfirmations(PRINCIPAL, otherWork)[0]?.submission.previewId,
    ).toBe("preview-9");
    expect(
      readOrganizeConfirmations("operator-2", WORK)[0]?.submission.previewId,
    ).toBe("preview-8");
  });

  it("is idempotent for the exact batch and validates bounded input", () => {
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, SUBMISSION),
    ).toEqual({ ok: true });
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, SUBMISSION),
    ).toEqual({ ok: true });
    expect(readOrganizeConfirmations(PRINCIPAL, WORK)).toHaveLength(1);
    expect(beginOrganizeConfirmationRetention(null, WORK, SUBMISSION)).toEqual({
      ok: false,
      reason: "identity-unavailable",
    });
    expect(
      beginOrganizeConfirmationRetention(
        PRINCIPAL,
        { kind: "files", discoveryId: "../escape" },
        SUBMISSION,
      ),
    ).toEqual({ ok: false, reason: "invalid-request" });
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, {
        ...SUBMISSION,
        expectedIntentVersion: 0,
      }),
    ).toEqual({ ok: false, reason: "invalid-request" });
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, {
        ...SUBMISSION,
        itemIds: [],
      }),
    ).toEqual({ ok: false, reason: "invalid-request" });
  });

  it("never overwrites the retained set beyond its bounded capacity", () => {
    for (let index = 0; index < 20; index += 1) {
      expect(
        beginOrganizeConfirmationRetention(PRINCIPAL, WORK, {
          ...SUBMISSION,
          previewId: `preview-${index}`,
        }),
      ).toEqual({ ok: true });
    }
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, {
        ...SUBMISSION,
        previewId: "preview-overflow",
      }),
    ).toEqual({ ok: false, reason: "capacity" });
  });

  it("treats unreadable or corrupt retained text as no readable request", () => {
    window.localStorage.setItem(KEY, "{broken");
    expect(readOrganizeConfirmations(PRINCIPAL, WORK)).toEqual([]);
    window.localStorage.setItem(
      KEY,
      JSON.stringify({
        version: 1,
        entries: [{ work: WORK, submission: { previewId: "preview-1" } }],
      }),
    );
    expect(readOrganizeConfirmations(PRINCIPAL, WORK)).toEqual([]);
  });

  it("refuses submission when browser storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, SUBMISSION),
    ).toEqual({ ok: false, reason: "storage-unavailable" });
  });

  it("clears only the exactly matching batch", () => {
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, SUBMISSION),
    ).toEqual({ ok: true });
    clearOrganizeConfirmation(PRINCIPAL, WORK, {
      ...SUBMISSION,
      previewId: "preview-other",
    });
    expect(readOrganizeConfirmations(PRINCIPAL, WORK)).toHaveLength(1);
    clearOrganizeConfirmation(PRINCIPAL, WORK, SUBMISSION);
    expect(readOrganizeConfirmations(PRINCIPAL, WORK)).toEqual([]);
  });

  it("discards retained requests when the active principal changes", () => {
    expect(
      beginOrganizeConfirmationRetention(PRINCIPAL, WORK, SUBMISSION),
    ).toEqual({ ok: true });
    clearPrincipalSessionData();
    expect(readOrganizeConfirmations(PRINCIPAL, WORK)).toEqual([]);
  });
});
