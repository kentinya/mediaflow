import { describe, expect, it } from "vitest";
import {
  normalizeTaskDetailPage,
  normalizeTaskListPage,
  normalizeTaskRecord,
} from "./task";

const NOW = "2026-08-22T12:00:00+00:00";
const LATER = "2026-08-22T12:06:00+00:00";

function lifecycle(overrides: Record<string, unknown> = {}) {
  return {
    objectType: "task",
    objectId: "task-1",
    state: "completed",
    version: LATER,
    terminal: true,
    permitted: true,
    permission: "cancel_job",
    knownEffects: "1 recorded item result completed a verified Storage effect",
    nextAction: "this Task is terminal; no lifecycle control is available",
    pauseRequested: false,
    effectCertainty: "verified_complete",
    resultsObserved: 1,
    resultsComplete: true,
    uncertainResults: 0,
    actions: [
      {
        action: "cancel",
        label: "Cancel Task",
        method: "POST",
        path: "/api/v1/tasks/{id}/cancel",
        available: false,
        unavailableReason: "a completed Task cannot be cancelled",
        confirmationRequired: false,
        cooperative: true,
        durableOutcome: "the Task is durably marked cancelled",
        sideEffects: "no Storage mutation",
        retrySafe: false,
        nextAction: "refresh the Task",
      },
    ],
    ...overrides,
  };
}

function task(overrides: Record<string, unknown> = {}) {
  return {
    task_id: "task-1",
    command: "preview",
    status: "completed",
    execute_authorized: false,
    created_at: NOW,
    updated_at: LATER,
    started_at: NOW,
    completed_at: LATER,
    total_items: 2,
    completed_items: 1,
    failed_items: 1,
    error: null,
    failureExplanation: null,
    pause_requested: false,
    configuration_snapshot_id: "snap-1",
    configuration_snapshot_digest: "digest-1",
    ...overrides,
  };
}

function result(overrides: Record<string, unknown> = {}) {
  return {
    result_id: "result-1",
    task_id: "task-1",
    item_id: "item-1",
    source_storage_id: "source",
    source_path: "movie.mkv",
    destination_storage_id: "target",
    destination_path: "Movies/movie.mkv",
    recognition_type: "A",
    provider: "tmdb",
    provider_id: "1",
    metadata_policy_id: "A",
    naming_policy_id: "A",
    classification_policy_id: "A",
    organize_policy_id: "A",
    operation: "move",
    status: "success",
    created_at: LATER,
    title: "Movie",
    error: null,
    completed_operations: ["move"],
    effect_certainty: "verified_complete",
    uncertain_effects: [],
    ...overrides,
  };
}

describe("normalizeTaskRecord", () => {
  it("accepts a modelled Task record", () => {
    const model = normalizeTaskRecord(task());
    expect(model.taskId).toBe("task-1");
    expect(model.status).toBe("completed");
    expect(model.failureExplanation).toBeNull();
  });

  it("rejects an unknown status instead of casting it", () => {
    expect(() =>
      normalizeTaskRecord(task({ status: "nearly_done" })),
    ).toThrow();
  });

  it("rejects coerced booleans", () => {
    expect(() =>
      normalizeTaskRecord(task({ execute_authorized: "yes" })),
    ).toThrow();
    expect(() => normalizeTaskRecord(task({ pause_requested: 1 }))).toThrow();
  });

  it("rejects contradictory progress and terminal state", () => {
    expect(() =>
      normalizeTaskRecord(
        task({ total_items: 1, completed_items: 1, failed_items: 1 }),
      ),
    ).toThrow();
    expect(() =>
      normalizeTaskRecord(task({ status: "running", completed_at: LATER })),
    ).toThrow();
    expect(() =>
      normalizeTaskRecord(task({ status: "failed", completed_at: null })),
    ).toThrow();
  });

  it("rejects a pause request on a non-running Task", () => {
    expect(() =>
      normalizeTaskRecord(task({ pause_requested: true })),
    ).toThrow();
  });

  it("normalizes the bounded failure explanation object", () => {
    const model = normalizeTaskRecord(
      task({
        failureExplanation: {
          category: "storage",
          message: "source unavailable",
          durableState: "the source Storage became unavailable",
          sideEffects: "none",
          retrySafe: true,
          nextAction: "restore the source Storage",
        },
      }),
    );
    expect(model.failureExplanation?.category).toBe("storage");
    expect(model.failureExplanation?.retrySafe).toBe(true);
  });
});

describe("normalizeTaskListPage", () => {
  it("echoes the submitted backend filters", () => {
    const page = normalizeTaskListPage({
      items: [task()],
      limit: 20,
      status: "completed",
      command: "preview",
      truncated: false,
      previous_cursor: null,
      next_cursor: null,
    });
    expect(page.status).toBe("completed");
    expect(page.command).toBe("preview");
  });

  it("rejects an unknown echoed filter or a non-array page", () => {
    expect(() =>
      normalizeTaskListPage({ items: [], limit: 20, status: "unknown" }),
    ).toThrow();
    expect(() => normalizeTaskListPage({ items: {}, limit: 20 })).toThrow();
  });
});

describe("normalizeTaskDetailPage", () => {
  it("accepts independent items, results and a matching projection", () => {
    const page = normalizeTaskDetailPage({
      ...task(),
      lifecycle: lifecycle(),
      items: [
        {
          item_id: "item-1",
          task_id: "task-1",
          storage_id: "source",
          resource_library_id: "movies",
          source_path: "movie.mkv",
          source_display: "movie.mkv",
          status: "success",
          stage: "completed",
          attempts: 1,
          created_at: NOW,
          updated_at: LATER,
          plan_id: null,
          destination_storage_id: null,
          destination_path: null,
          execution_status: "completed",
          error: null,
          checkpoint: null,
        },
      ],
      results: [result()],
      item_limit: 20,
      result_limit: 20,
      items_truncated: false,
      results_truncated: false,
      previous_item_cursor: null,
      previous_result_cursor: null,
      next_item_cursor: null,
      next_result_cursor: null,
    });
    expect(page.task.taskId).toBe("task-1");
    expect(page.items[0]?.status).toBe("success");
    expect(page.results[0]?.effectCertainty).toBe("verified_complete");
    expect(page.lifecycle.objectId).toBe("task-1");
  });

  it("rejects an unknown TaskItem status", () => {
    expect(() =>
      normalizeTaskDetailPage({
        ...task(),
        lifecycle: lifecycle(),
        items: [{ item_id: "i", task_id: "task-1", status: "exploded" }],
        results: [],
        item_limit: 20,
        result_limit: 20,
        items_truncated: false,
        results_truncated: false,
      }),
    ).toThrow();
  });

  it("rejects a result whose uncertain-effect evidence contradicts its certainty", () => {
    expect(() =>
      normalizeTaskDetailPage({
        ...task(),
        lifecycle: lifecycle(),
        items: [],
        results: [
          result({
            effect_certainty: "verified_complete",
            uncertain_effects: ["move"],
          }),
        ],
        item_limit: 20,
        result_limit: 20,
        items_truncated: false,
        results_truncated: false,
      }),
    ).toThrow();
  });

  it("rejects a lifecycle projection that belongs to another Task", () => {
    expect(() =>
      normalizeTaskDetailPage({
        ...task(),
        lifecycle: lifecycle({ objectId: "task-other" }),
        items: [],
        results: [],
        item_limit: 20,
        result_limit: 20,
        items_truncated: false,
        results_truncated: false,
      }),
    ).toThrow();
  });

  it("rejects a detail response with no lifecycle projection", () => {
    expect(() =>
      normalizeTaskDetailPage({
        ...task(),
        items: [],
        results: [],
        item_limit: 20,
        result_limit: 20,
        items_truncated: false,
        results_truncated: false,
      }),
    ).toThrow();
  });
});
