import { describe, expect, it } from "vitest";
import {
  ATTENTION_RUN_STATUSES,
  RUN_STATUS_LABELS,
  isAttentionRun,
  normalizeRunInventoryPage,
  normalizeRunOverview,
  normalizeRunSummary,
  RunNormalizationError,
} from "./run";

function runDocument(overrides: Record<string, unknown> = {}) {
  return {
    run_kind: "task",
    run_id: "task-1",
    command: "scan",
    command_label: "扫描",
    recognized_command: true,
    status: "completed",
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
    completed_items: 2,
    failed_items: 0,
    pause_requested: false,
    attention: false,
    configuration_snapshot_id: "snap-1",
    worker_id: null,
    sideEffects: "none",
    ...overrides,
  };
}

function pageDocument(overrides: Record<string, unknown> = {}) {
  return {
    items: [runDocument()],
    limit: 20,
    status: null,
    command: null,
    q: null,
    from: null,
    to: null,
    attention: false,
    total: 1,
    truncated: false,
    status_counts: { completed: 1 },
    attention_count: 0,
    population: "unified job/task run inventory",
    sideEffects: "none",
    previous_cursor: null,
    next_cursor: null,
    ...overrides,
  };
}

function lifecycleAction(
  name: string,
  available: boolean,
  unavailableReason: string | null,
) {
  return {
    action: name,
    label: `${name} label`,
    method: "POST",
    path: `/api/v1/tasks/{id}/${name}`,
    available,
    unavailableReason,
    confirmationRequired: false,
    cooperative: true,
    durableOutcome: "a durable request is stored",
    sideEffects: "no Storage mutation",
    retrySafe: false,
    nextAction: "refresh the Task",
  };
}

function lifecycleProjection(overrides: Record<string, unknown> = {}) {
  return {
    objectType: "task",
    objectId: "task-1",
    state: "running",
    version: "2026-08-22T12:06:00+00:00",
    executionPath: "operator_workflow",
    terminal: false,
    permitted: true,
    permission: "cancel_job",
    pauseRequested: false,
    effectCertainty: "none",
    resultsObserved: 0,
    resultsComplete: true,
    uncertainResults: 0,
    knownEffects: "no Storage effect is recorded for this Task",
    nextAction: "refresh the Task to read the durable state",
    actions: [
      lifecycleAction("cancel", true, null),
      lifecycleAction("pause", true, null),
      lifecycleAction("resume", false, "no durable queued continuation exists"),
    ],
    ...overrides,
  };
}

describe("run summary normalization", () => {
  it("normalizes a bounded run document", () => {
    const run = normalizeRunSummary(runDocument());
    expect(run.runId).toBe("task-1");
    expect(run.commandLabel).toBe("扫描");
    expect(run.status).toBe("completed");
    expect(run.libraryKind).toBe("resource");
    expect(run.attention).toBe(false);
  });

  it("rejects an unknown status instead of coercing it", () => {
    expect(() =>
      normalizeRunSummary(runDocument({ status: "almost_done" })),
    ).toThrow(RunNormalizationError);
  });

  it("rejects an unknown trigger and library kind", () => {
    expect(() =>
      normalizeRunSummary(runDocument({ trigger: "magic" })),
    ).toThrow(RunNormalizationError);
    expect(() =>
      normalizeRunSummary(runDocument({ library_kind: "bucket" })),
    ).toThrow(RunNormalizationError);
  });

  it("rejects contradictory progress pairs", () => {
    expect(() =>
      normalizeRunSummary(
        runDocument({ total_items: 1, completed_items: 2, failed_items: 0 }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("still rejects completing more items than the run has, for any command", () => {
    // `completed <= total` is independent of the task-kind sum rule below.
    expect(() =>
      normalizeRunSummary(
        runDocument({
          command: "scan",
          total_items: 1,
          completed_items: 2,
          failed_items: 0,
        }),
      ),
    ).toThrow(RunNormalizationError);
    expect(() =>
      normalizeRunSummary(
        runDocument({
          command: "preview",
          total_items: 0,
          completed_items: 1,
          failed_items: 0,
        }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("requires the item total whenever a completed/failed count is reported", () => {
    expect(() =>
      normalizeRunSummary(
        runDocument({ total_items: null, completed_items: 1 }),
      ),
    ).toThrow(RunNormalizationError);
    expect(() =>
      normalizeRunSummary(runDocument({ total_items: null, failed_items: 1 })),
    ).toThrow(RunNormalizationError);
  });

  it("accepts an honest scan-error run but keeps exact partitions bounded", () => {
    // A production Scan may carry independent scan errors beyond its known
    // item list (total 0, no completion, one failure): one such run must
    // render as a row instead of rejecting the whole page.
    const scanError = normalizeRunSummary(
      runDocument({
        command: "scan",
        total_items: 0,
        completed_items: 0,
        failed_items: 1,
      }),
    );
    expect(scanError.totalItems).toBe(0);
    expect(scanError.completedItems).toBe(0);
    expect(scanError.failedItems).toBe(1);

    // Every exact-partition command still partitions one item list, including
    // a MediaLibrary-owned direct command whose family is derived the same
    // way the backend derives its label.
    for (const command of [
      "manual_organize",
      "files_direct_command",
      "files_delete",
      "files_transfer",
      "media_files_transfer",
      "manual_organize:intent-1",
    ]) {
      expect(() =>
        normalizeRunSummary(
          runDocument({
            command,
            total_items: 2,
            completed_items: 2,
            failed_items: 1,
          }),
        ),
      ).toThrow(RunNormalizationError);
    }
    // The same exact-partition command stays valid inside its own total.
    expect(
      normalizeRunSummary(
        runDocument({
          command: "manual_organize",
          total_items: 3,
          completed_items: 2,
          failed_items: 1,
        }),
      ).failedItems,
    ).toBe(1);
  });

  it("requires a label for a recognized command and rejects a mismatch", () => {
    expect(() =>
      normalizeRunSummary(
        runDocument({ command_label: null, recognized_command: true }),
      ),
    ).toThrow(RunNormalizationError);
    const unknown = normalizeRunSummary(
      runDocument({
        command: "legacy_historic_work",
        command_label: null,
        recognized_command: false,
      }),
    );
    expect(unknown.recognizedCommand).toBe(false);
    expect(unknown.commandLabel).toBeNull();
  });

  it("keeps the backend attention facet exact", () => {
    expect(() =>
      normalizeRunSummary(runDocument({ status: "failed", attention: false })),
    ).toThrow(RunNormalizationError);
    const attention = normalizeRunSummary(
      runDocument({ status: "failed", attention: true }),
    );
    expect(attention.attention).toBe(true);
    expect(isAttentionRun("failed")).toBe(true);
    expect(isAttentionRun("running")).toBe(false);
    expect(isAttentionRun("completed")).toBe(false);
  });

  it("models every backend attention status", () => {
    for (const status of ATTENTION_RUN_STATUSES) {
      expect(isAttentionRun(status)).toBe(true);
      expect(RUN_STATUS_LABELS[status]).toBeTruthy();
    }
  });

  it("exposes Chinese labels for every modelled state", () => {
    for (const label of Object.values(RUN_STATUS_LABELS)) {
      expect(label.length).toBeGreaterThan(0);
    }
  });
});

describe("run inventory page normalization", () => {
  it("normalizes a page with counts and cursors", () => {
    const page = normalizeRunInventoryPage(
      pageDocument({
        status_counts: { failed: 2, running: 1 },
        attention_count: 2,
        total: 3,
        next_cursor: "cursor-1",
      }),
    );
    expect(page.total).toBe(3);
    expect(page.statusCounts["failed"]).toBe(2);
    expect(page.attentionCount).toBe(2);
    expect(page.nextCursor).toBe("cursor-1");
  });

  it("rejects an attention count that disagrees with the modelled facet", () => {
    expect(() =>
      normalizeRunInventoryPage(
        pageDocument({
          status_counts: { failed: 2 },
          attention_count: 5,
        }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("reads the submitted attention facet as a required boolean", () => {
    expect(normalizeRunInventoryPage(pageDocument()).attention).toBe(false);
    const applied = normalizeRunInventoryPage(
      pageDocument({
        items: [runDocument({ status: "failed", attention: true })],
        status_counts: { failed: 1 },
        attention_count: 1,
        total: 1,
        attention: true,
      }),
    );
    expect(applied.attention).toBe(true);
    // A wrong-typed or missing echo is malformed data, never a coerced false.
    expect(() =>
      normalizeRunInventoryPage(pageDocument({ attention: "yes" })),
    ).toThrow(RunNormalizationError);
    expect(() =>
      normalizeRunInventoryPage(pageDocument({ attention: "true" })),
    ).toThrow(RunNormalizationError);
    expect(() =>
      normalizeRunInventoryPage(pageDocument({ attention: undefined })),
    ).toThrow(RunNormalizationError);
  });

  it("rejects an attention echo the population does not honour", () => {
    // The server echoed the facet over a page whose partitions are not all
    // attention statuses: it advertised a filter it did not apply.
    expect(() =>
      normalizeRunInventoryPage(
        pageDocument({
          items: [runDocument({ status: "running" })],
          status_counts: { running: 1 },
          attention_count: 0,
          total: 1,
          attention: true,
        }),
      ),
    ).toThrow(RunNormalizationError);
    // Every partition is an attention status, but the facet page does not
    // cover the whole reported population either.
    expect(() =>
      normalizeRunInventoryPage(
        pageDocument({
          items: [runDocument({ status: "failed", attention: true })],
          status_counts: { failed: 1 },
          attention_count: 1,
          total: 2,
          attention: true,
        }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("rejects a filtered total smaller than the page", () => {
    expect(() => normalizeRunInventoryPage(pageDocument({ total: 0 }))).toThrow(
      RunNormalizationError,
    );
  });

  it("rejects a malformed status partition", () => {
    expect(() =>
      normalizeRunInventoryPage(pageDocument({ status_counts: "all" })),
    ).toThrow(RunNormalizationError);
    expect(() =>
      normalizeRunInventoryPage(
        pageDocument({ status_counts: { failed: -1 } }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("rejects a non-list items field", () => {
    expect(() =>
      normalizeRunInventoryPage(pageDocument({ items: "everything" })),
    ).toThrow(RunNormalizationError);
  });

  it("echoes the submitted status filter only when modelled", () => {
    const page = normalizeRunInventoryPage(pageDocument({ status: "failed" }));
    expect(page.status).toBe("failed");
    expect(() =>
      normalizeRunInventoryPage(pageDocument({ status: "bogus" })),
    ).toThrow(RunNormalizationError);
  });
});

describe("run overview normalization", () => {
  it("normalizes one overview document", () => {
    const run = normalizeRunOverview(runDocument());
    expect(run.runId).toBe("task-1");
  });

  it("rejects a bare non-object payload", () => {
    // readRecord rejects the payload before the typed normalization runs;
    // either way the caller sees one failed read, never a partial model.
    expect(() => normalizeRunOverview("task-1")).toThrow(/invalid field/);
  });
});

describe("run lifecycle projection normalization", () => {
  it("accepts a valid linked-Task lifecycle and exposes its advertised actions", () => {
    const run = normalizeRunSummary(
      runDocument({
        task_id: "task-1",
        job_id: null,
        lifecycle: lifecycleProjection(),
      }),
    );
    expect(run.lifecycle).not.toBeNull();
    expect(run.lifecycle?.objectType).toBe("task");
    expect(run.lifecycle?.objectId).toBe("task-1");
    expect(
      run.lifecycle?.actions
        .filter((item) => item.available)
        .map((i) => i.action),
    ).toEqual(["cancel", "pause"]);
  });

  it("accepts a valid pre-Task Job lifecycle advertising only cancel", () => {
    const run = normalizeRunSummary(
      runDocument({
        run_kind: "job",
        run_id: "job-1",
        task_id: null,
        job_id: "job-1",
        lifecycle: {
          ...lifecycleProjection(),
          objectType: "job",
          objectId: "job-1",
          actions: [lifecycleAction("cancel", true, null)],
        },
      }),
    );
    expect(run.lifecycle?.objectType).toBe("job");
    expect(run.lifecycle?.actions.map((item) => item.action)).toEqual([
      "cancel",
    ]);
  });

  it("accepts every modelled raw Task state and rejects an unknown one", () => {
    for (const state of [
      "pending",
      "running",
      "paused",
      "completed",
      "partial_success",
      "failed",
      "cancelled",
    ]) {
      const run = normalizeRunSummary(
        runDocument({ lifecycle: lifecycleProjection({ state }) }),
      );
      expect(run.lifecycle?.state).toBe(state);
    }
    expect(() =>
      normalizeRunSummary(
        runDocument({ lifecycle: lifecycleProjection({ state: "unknown" }) }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("accepts every modelled raw Job state and rejects a Task-only state", () => {
    for (const state of [
      "pending",
      "running",
      "completed",
      "failed",
      "cancelled",
    ]) {
      const run = normalizeRunSummary(
        runDocument({
          run_kind: "job",
          run_id: "job-1",
          task_id: null,
          job_id: "job-1",
          lifecycle: {
            ...lifecycleProjection(),
            objectType: "job",
            objectId: "job-1",
            state,
            actions: [lifecycleAction("cancel", false, "terminal")],
            permitted: false,
          },
        }),
      );
      expect(run.lifecycle?.state).toBe(state);
    }
    // `paused` is a raw Task state, never a Job state.
    expect(() =>
      normalizeRunSummary(
        runDocument({
          run_kind: "job",
          run_id: "job-1",
          task_id: null,
          job_id: "job-1",
          lifecycle: {
            ...lifecycleProjection(),
            objectType: "job",
            objectId: "job-1",
            state: "paused",
            actions: [lifecycleAction("cancel", false, "not cancellable")],
            permitted: false,
          },
        }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("rejects a lifecycle for another object identity", () => {
    expect(() =>
      normalizeRunSummary(
        runDocument({
          lifecycle: lifecycleProjection({ objectId: "task-other" }),
        }),
      ),
    ).toThrow(RunNormalizationError);
    expect(() =>
      normalizeRunSummary(
        runDocument({
          job_id: "job-1",
          lifecycle: {
            ...lifecycleProjection(),
            objectType: "job",
            objectId: "job-other",
            actions: [lifecycleAction("cancel", true, null)],
          },
        }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("rejects an unknown lifecycle object type", () => {
    expect(() =>
      normalizeRunSummary(
        runDocument({
          lifecycle: lifecycleProjection({ objectType: "workflow" }),
        }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("rejects a lifecycle on a run with no matching identity", () => {
    // A run with no Task cannot own a Task projection...
    expect(() =>
      normalizeRunSummary(
        runDocument({ task_id: null, lifecycle: lifecycleProjection() }),
      ),
    ).toThrow(RunNormalizationError);
    // ...and a run with no Job cannot own a Job projection.
    expect(() =>
      normalizeRunSummary(
        runDocument({
          task_id: null,
          job_id: null,
          lifecycle: {
            ...lifecycleProjection(),
            objectType: "job",
            objectId: "job-1",
            actions: [lifecycleAction("cancel", true, null)],
          },
        }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("rejects a malformed inner projection, including a contradictory action", () => {
    expect(() =>
      normalizeRunSummary(
        runDocument({ lifecycle: lifecycleProjection({ actions: "cancel" }) }),
      ),
    ).toThrow(RunNormalizationError);
    // A withheld action must carry its own refusal reason (delegated to the
    // lifecycle normalizer), so the run fails closed rather than rendering a
    // reasonless control.
    expect(() =>
      normalizeRunSummary(
        runDocument({
          lifecycle: lifecycleProjection({
            actions: [lifecycleAction("cancel", false, null)],
          }),
        }),
      ),
    ).toThrow(RunNormalizationError);
    // An available action that also carries a refusal reason is contradictory.
    expect(() =>
      normalizeRunSummary(
        runDocument({
          lifecycle: lifecycleProjection({
            actions: [lifecycleAction("cancel", true, "because")],
          }),
        }),
      ),
    ).toThrow(RunNormalizationError);
  });

  it("normalizes an absent or explicit null lifecycle to null", () => {
    expect(normalizeRunSummary(runDocument()).lifecycle).toBeNull();
    expect(
      normalizeRunSummary(runDocument({ lifecycle: null })).lifecycle,
    ).toBeNull();
    // The inventory page rows legitimately carry no lifecycle projection at
    // all, so a whole page still normalizes.
    const page = normalizeRunInventoryPage(pageDocument());
    expect(page.items[0]?.lifecycle).toBeNull();
  });
});
