import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  checkOrganizeAdmission,
  useOrganizeAdmissionWatchGroup,
} from "./organize-admission-watch";

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
  vi.useRealTimers();
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

  it("leaves the failed batch read visible until an explicit read completes", async () => {
    vi.useFakeTimers();
    let resolveRetry!: (response: Response) => void;
    const retry = new Promise<Response>((resolve) => {
      resolveRetry = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { code: "unavailable" } }), {
          status: 503,
        }),
      )
      .mockReturnValueOnce(retry);
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() =>
      useOrganizeAdmissionWatchGroup({
        enabled: true,
        token: "token",
        principalId: "operator-review",
        entries: [{ key: "original", submission: SUBMISSION, workId: "work" }],
        explicitReviewRecovery: true,
        confirmAbsenceManually: true,
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.states.get("original")).toMatchObject({
      phase: "failed",
      reading: false,
    });
    await act(async () => {
      window.dispatchEvent(new Event("online"));
      document.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    act(() => result.current.retry());
    expect(result.current.states.get("original")).toMatchObject({
      phase: "failed",
      reading: true,
    });
    act(() => result.current.retry());
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => resolveRetry(knownResponse()));
    expect(result.current.states.get("original")).toMatchObject({
      phase: "known",
      reading: false,
    });
    expect(
      fetchMock.mock.calls.every(([, options]) => options.method === "GET"),
    ).toBe(true);
  });
});
