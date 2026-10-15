import { describe, expect, it } from "vitest";
import {
  recoveryBatchQueryOptions,
  runItemEvidenceQueryOptions,
  runProblemItemsQueryOptions,
  runRecordsQueryOptions,
} from "./run-detail-query";

type IntervalQuery = {
  readonly state: { readonly data: unknown; readonly status?: string };
};
type IntervalCallback = (query: IntervalQuery) => number | false;

function interval(
  options: { readonly refetchInterval?: unknown },
  data: unknown,
  status = data === undefined ? "pending" : "success",
) {
  const value = options.refetchInterval;
  return typeof value === "function"
    ? (value as IntervalCallback)({ state: { data, status } })
    : value;
}

const failedRead = {
  ok: false,
  failure: {
    kind: "unavailable",
    title: "Operations unavailable",
    nextAction: "Refresh the same read when service is available.",
  },
};

describe("run detail read polling", () => {
  it("polls successful visible problem and evidence reads, then stops on failure", () => {
    const problemFiles = runProblemItemsQueryOptions("token", {
      runId: "task-1",
      problem: "metadata",
      cursor: null,
      active: true,
    });
    const evidence = runItemEvidenceQueryOptions("token", {
      runId: "task-1",
      itemId: "item-1",
      active: true,
    });
    const records = runRecordsQueryOptions("token", {
      runId: "task-1",
      kind: null,
      cursor: null,
      active: true,
    });

    for (const options of [problemFiles, evidence, records]) {
      expect(interval(options, undefined)).toBe(false);
      expect(interval(options, failedRead)).toBe(false);
      expect(interval(options, { ok: true, model: {} })).toBe(5_000);
      expect(interval(options, { ok: true, model: {} }, "error")).toBe(false);
      expect(options.retry).toBe(false);
      expect(options.refetchIntervalInBackground).toBe(false);
    }
  });

  it("stops a recovery batch poll on failed or terminal reads", () => {
    const options = recoveryBatchQueryOptions("token", {
      taskId: "task-1",
      batchId: "batch-1",
      principalId: "operator",
      authGeneration: 1,
    });

    expect(interval(options, undefined)).toBe(false);
    expect(interval(options, failedRead)).toBe(false);
    expect(
      interval(options, { ok: true, model: { status: "running" } }, "error"),
    ).toBe(false);
    expect(interval(options, { ok: true, model: { status: "running" } })).toBe(
      5_000,
    );
    expect(
      interval(options, { ok: true, model: { status: "completed" } }),
    ).toBe(false);
    expect(options.retry).toBe(false);
    expect(options.refetchIntervalInBackground).toBe(false);
  });
});
