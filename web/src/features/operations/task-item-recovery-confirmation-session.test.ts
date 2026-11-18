import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { clearPrincipalSessionData } from "../../shared/auth/principal-session-data";
import {
  beginTaskItemRecoveryConfirmationRetention,
  clearTaskItemRecoveryConfirmation,
  readTaskItemRecoveryConfirmation,
} from "./task-item-recovery-confirmation-session";

const PRINCIPAL = "operator-1";
const IDENTITY = { runId: "run-1", taskId: "task-1", itemId: "item-1" };

function submission(
  overrides: Partial<{
    preparationId: string;
    previewId: string;
    itemIds: string[];
    expectedIntentVersion: number;
    allowOverwrite: boolean;
    allowSourceCleanup: boolean;
  }> = {},
) {
  return {
    preparationId: "preparation-1",
    previewId: "preview-1",
    itemIds: ["item-2"],
    expectedIntentVersion: 1,
    allowOverwrite: false,
    allowSourceCleanup: false,
    ...overrides,
  };
}

function storedKey(
  principal: string,
  identity: { runId: string; taskId: string; itemId: string },
): string {
  return [
    "mediaflow.operations.task-item-recovery-confirmations:" +
      principalIdStorageSegment(principal),
    encodeURIComponent(identity.runId),
    encodeURIComponent(identity.taskId),
    encodeURIComponent(identity.itemId),
  ].join("|");
}

beforeEach(() => {
  window.sessionStorage.clear();
});

afterEach(() => {
  window.sessionStorage.clear();
});

describe("task item recovery confirmation session", () => {
  it("retains the exact submitted request before the POST and reads it back for the same principal", () => {
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        IDENTITY,
        submission(),
      ),
    ).toEqual({ ok: true });
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toEqual(
      submission(),
    );
  });

  it("keeps entries independent per principal, run, Task and item", () => {
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        IDENTITY,
        submission(),
      ),
    ).toEqual({ ok: true });
    const otherItem = { ...IDENTITY, itemId: "item-2" };
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        otherItem,
        submission({ preparationId: "preparation-2" }),
      ),
    ).toEqual({ ok: true });
    const otherPrincipal = "operator-2";
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        otherPrincipal,
        IDENTITY,
        submission({ previewId: "preview-2" }),
      ),
    ).toEqual({ ok: true });
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toEqual(
      submission(),
    );
    expect(
      readTaskItemRecoveryConfirmation(PRINCIPAL, otherItem)?.preparationId,
    ).toBe("preparation-2");
    expect(
      readTaskItemRecoveryConfirmation(otherPrincipal, IDENTITY)?.previewId,
    ).toBe("preview-2");
  });

  it("never overwrites an unreconciled entry for the same item", () => {
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        IDENTITY,
        submission(),
      ),
    ).toEqual({ ok: true });
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        IDENTITY,
        submission({ previewId: "preview-9" }),
      ),
    ).toEqual({ ok: false, reason: "already-pending" });
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toEqual(
      submission(),
    );
  });

  it("refuses a submission that cannot be retained or validated", () => {
    expect(
      beginTaskItemRecoveryConfirmationRetention(null, IDENTITY, submission()),
    ).toEqual({ ok: false, reason: "identity-unavailable" });
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        { ...IDENTITY, itemId: "item/1" },
        submission(),
      ),
    ).toEqual({ ok: false, reason: "invalid-request" });
    expect(
      beginTaskItemRecoveryConfirmationRetention(PRINCIPAL, IDENTITY, {
        ...submission(),
        expectedIntentVersion: 0,
      }),
    ).toEqual({ ok: false, reason: "invalid-request" });
    expect(
      beginTaskItemRecoveryConfirmationRetention(PRINCIPAL, IDENTITY, {
        ...submission(),
        itemIds: [],
      }),
    ).toEqual({ ok: false, reason: "invalid-request" });
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toBeNull();
  });

  it("keeps the retained set bounded per principal", () => {
    for (let index = 0; index < 20; index += 1) {
      expect(
        beginTaskItemRecoveryConfirmationRetention(
          PRINCIPAL,
          { runId: `run-${index}`, taskId: `task-${index}`, itemId: "item-1" },
          submission(),
        ),
      ).toEqual({ ok: true });
    }
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        { runId: "run-x", taskId: "task-x", itemId: "item-1" },
        submission(),
      ),
    ).toEqual({ ok: false, reason: "capacity" });
  });

  it("treats unreadable retained text as no readable request", () => {
    window.sessionStorage.setItem(storedKey(PRINCIPAL, IDENTITY), "{broken");
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toBeNull();
    window.sessionStorage.setItem(
      storedKey(PRINCIPAL, IDENTITY),
      JSON.stringify({ previewId: "preview-1" }),
    );
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toBeNull();
  });

  it("clears only the exactly matching submission", () => {
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        IDENTITY,
        submission(),
      ),
    ).toEqual({ ok: true });
    clearTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY, {
      ...submission(),
      previewId: "preview-other",
    });
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toEqual(
      submission(),
    );
    clearTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY, submission());
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toBeNull();
  });

  it("clears a proven outcome and never touches another subject's entry", () => {
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        IDENTITY,
        submission(),
      ),
    ).toEqual({ ok: true });
    const otherItem = { ...IDENTITY, itemId: "item-2" };
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        otherItem,
        submission({ preparationId: "preparation-2" }),
      ),
    ).toEqual({ ok: true });
    clearTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY);
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toBeNull();
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, otherItem)).toEqual(
      submission({ preparationId: "preparation-2" }),
    );
  });

  it("discards retained requests when the active principal changes", () => {
    expect(
      beginTaskItemRecoveryConfirmationRetention(
        PRINCIPAL,
        IDENTITY,
        submission(),
      ),
    ).toEqual({ ok: true });
    clearPrincipalSessionData();
    expect(readTaskItemRecoveryConfirmation(PRINCIPAL, IDENTITY)).toBeNull();
  });
});
