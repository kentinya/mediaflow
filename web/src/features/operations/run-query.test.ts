import { describe, expect, it } from "vitest";
import {
  runInventoryQueryOptions,
  runOverviewQueryOptions,
  runRefetchInterval,
} from "./run-query";
import type {
  RunInventoryRead,
  RunOverviewRead,
} from "../../shared/api/api-client";
import {
  normalizeRunInventoryPage,
  normalizeRunOverview,
  type RunStatus,
} from "../../entities/operations/run";

/**
 * One shared bounded polling policy for the inventory page and the selected
 * run overview: active work polls, terminal or unreadable work settles.
 */
const FAILED_READ: RunInventoryRead = {
  ok: false,
  failure: {
    kind: "unavailable",
    title: "Operations unavailable",
    nextAction: "Reload the current Active runtime and retry the same read.",
  },
};

const FAILED_OVERVIEW_READ: RunOverviewRead = {
  ok: false,
  failure: {
    kind: "not_found",
    title: "Record not found",
    nextAction: "Return to the Operations list.",
  },
};

function runDocument(overrides: Record<string, unknown> = {}) {
  return {
    run_kind: "task",
    run_id: "task-1",
    command: "scan",
    command_label: "扫描",
    recognized_command: true,
    status: "running",
    trigger: "manual",
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:06:00+00:00",
    job_id: null,
    task_id: "task-1",
    schedule_id: null,
    definition_id: null,
    source_scope: "Movies",
    target_scope: null,
    library_kind: "resource",
    total_items: 2,
    completed_items: 1,
    failed_items: 0,
    pause_requested: false,
    attention: false,
    configuration_snapshot_id: "snap-1",
    worker_id: null,
    sideEffects: "none",
    ...overrides,
  };
}

function overviewRead(status: RunStatus): RunOverviewRead {
  return {
    ok: true,
    model: normalizeRunOverview(
      runDocument({
        status,
        attention: [
          "pending",
          "paused",
          "waiting",
          "partial_success",
          "failed",
        ].includes(status),
      }),
    ),
  };
}

function inventoryRead(statuses: readonly RunStatus[]): RunInventoryRead {
  const statusCounts: Record<string, number> = {};
  let attentionCount = 0;
  for (const status of statuses) {
    statusCounts[status] = (statusCounts[status] ?? 0) + 1;
    if (
      ["pending", "paused", "waiting", "partial_success", "failed"].includes(
        status,
      )
    ) {
      attentionCount += 1;
    }
  }
  return {
    ok: true,
    model: normalizeRunInventoryPage({
      items: statuses.map((status, index) =>
        runDocument({
          run_id: `task-${index + 1}`,
          task_id: `task-${index + 1}`,
          status,
          attention: [
            "pending",
            "paused",
            "waiting",
            "partial_success",
            "failed",
          ].includes(status),
        }),
      ),
      limit: 20,
      status: null,
      command: null,
      q: null,
      from: null,
      to: null,
      attention: false,
      total: statuses.length,
      truncated: false,
      status_counts: statusCounts,
      attention_count: attentionCount,
      population: "unified job/task run inventory",
      sideEffects: "none",
      previous_cursor: null,
      next_cursor: null,
    }),
  };
}

describe("run refetch interval", () => {
  it("never schedules a poll for a missing or failed read", () => {
    expect(runRefetchInterval(undefined)).toBe(false);
    expect(runRefetchInterval(FAILED_READ)).toBe(false);
    expect(runRefetchInterval(FAILED_OVERVIEW_READ)).toBe(false);
  });

  it("polls an inventory page while any listed run is non-terminal", () => {
    expect(runRefetchInterval(inventoryRead(["running", "completed"]))).toBe(
      5_000,
    );
    expect(runRefetchInterval(inventoryRead(["pending"]))).toBe(5_000);
    expect(runRefetchInterval(inventoryRead(["completed"]))).toBe(false);
    expect(
      runRefetchInterval(inventoryRead(["completed", "cancelled", "failed"])),
    ).toBe(false);
    expect(runRefetchInterval(inventoryRead([]))).toBe(false);
  });

  it("polls the selected overview only while its own state is active", () => {
    expect(runRefetchInterval(overviewRead("running"))).toBe(5_000);
    expect(runRefetchInterval(overviewRead("paused"))).toBe(5_000);
    expect(runRefetchInterval(overviewRead("completed"))).toBe(false);
    expect(runRefetchInterval(overviewRead("failed"))).toBe(false);
    expect(runRefetchInterval(overviewRead("partial_success"))).toBe(false);
    expect(runRefetchInterval(overviewRead("cancelled"))).toBe(false);
  });

  it("keeps both run queries bounded and side-effect free", () => {
    const inventory = runInventoryQueryOptions("token");
    expect(inventory.retry).toBe(false);
    expect(inventory.staleTime).toBe(10_000);
    expect(inventory.refetchIntervalInBackground).toBe(false);
    const overview = runOverviewQueryOptions("token", "task-1");
    expect(overview.retry).toBe(false);
    expect(overview.staleTime).toBe(10_000);
    expect(overview.refetchIntervalInBackground).toBe(false);
    // The same shared policy drives both options objects.
    expect(inventory.refetchInterval).toBeTypeOf("function");
    expect(overview.refetchInterval).toBeTypeOf("function");
  });
});
