import { afterEach, describe, expect, it, vi } from "vitest";

import { checkOrganizeAdmission } from "./organize-admission-watch";

const SUBMISSION = {
  previewId: "preview-1",
  itemIds: ["item-1", "item-2"],
  expectedIntentVersion: 2,
  allowOverwrite: false,
  allowSourceCleanup: true,
};

function knownResponse(): Response {
  return new Response(
    JSON.stringify({
      outcome: "known",
      reason: null,
      executionId: "execution-1",
      taskId: "task-1",
      status: "admitted",
      selectedItemIds: ["item-1", "item-2"],
      completedItemCount: 0,
      failedItemCount: 0,
      sideEffects: "none",
      nextAction: "inspect the durable task",
    }),
    { status: 200 },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("organize admission watch", () => {
  it("deduplicates concurrent reads of the exact same principal and submission", async () => {
    const resolveFetch: { current: ((response: Response) => void) | null } = {
      current: null,
    };
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch.current = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const first = checkOrganizeAdmission("token", "operator-1", SUBMISSION);
    const second = checkOrganizeAdmission("token", "operator-1", {
      ...SUBMISSION,
      itemIds: ["item-2", "item-1"],
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolveFetch.current?.(knownResponse());
    const [left, right] = await Promise.all([first, second]);
    expect(left.ok).toBe(true);
    expect(right).toEqual(left);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Only a later, distinct attempt issues a new durable read.
    const third = checkOrganizeAdmission("token", "operator-1", SUBMISSION);
    await Promise.resolve();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    resolveFetch.current?.(knownResponse());
    await third;
  });

  it("binds the deduplication to the principal and the exact effect choices", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ error: { code: "unavailable" } }), {
          status: 503,
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await checkOrganizeAdmission("token", "operator-1", SUBMISSION);
    await checkOrganizeAdmission("token", "operator-2", SUBMISSION);
    await checkOrganizeAdmission("token", "operator-1", {
      ...SUBMISSION,
      allowSourceCleanup: false,
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
