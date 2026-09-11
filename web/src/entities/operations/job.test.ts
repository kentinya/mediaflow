import { describe, expect, it } from "vitest";
import { normalizeJobDetail, normalizeJobListPage } from "./job";

const NOW = "2026-08-22T12:00:00+00:00";
const LATER = "2026-08-22T12:06:00+00:00";

function jobLifecycle(overrides: Record<string, unknown> = {}) {
  return {
    objectType: "job",
    objectId: "job-1",
    state: "pending",
    version: NOW,
    terminal: false,
    permitted: true,
    permission: "cancel_job",
    cancellationRequested: false,
    commandKind: "source discovery",
    knownEffects:
      "the Job owns admission and queue state; Storage effects belong to its linked Task",
    nextAction: "refresh the Job to read the durable state",
    actions: [
      {
        action: "cancel",
        label: "Cancel Job",
        method: "POST",
        path: "/api/v1/jobs/{id}/cancel",
        available: true,
        unavailableReason: null,
        confirmationRequired: false,
        cooperative: true,
        durableOutcome: "a durable cancellation request is stored",
        sideEffects: "no Storage mutation",
        retrySafe: false,
        nextAction: "refresh the Job",
      },
    ],
    ...overrides,
  };
}

function job(overrides: Record<string, unknown> = {}) {
  return {
    job_id: "job-1",
    command: "scan",
    status: "pending",
    created_at: NOW,
    updated_at: NOW,
    started_at: null,
    completed_at: null,
    task_id: null,
    cancellation_requested: false,
    execute_authorized: false,
    failure: null,
    definition_id: null,
    schedule_id: null,
    run_mode: null,
    configuration_snapshot_id: "snap-1",
    lifecycle: jobLifecycle(),
    ...overrides,
  };
}

describe("normalizeJobDetail", () => {
  it("accepts a modelled pending Job with no Worker", () => {
    const model = normalizeJobDetail(job());
    expect(model.status).toBe("pending");
    expect(model.workerEvidence).toBeNull();
    expect(model.lifecycle.actions[0]?.available).toBe(true);
  });

  it("rejects an unknown command instead of coercing it", () => {
    expect(() => normalizeJobDetail(job({ command: "rm -rf" }))).toThrow();
    expect(() => normalizeJobDetail(job({ status: "queued" }))).toThrow();
  });

  it("rejects coerced booleans", () => {
    expect(() =>
      normalizeJobDetail(job({ cancellation_requested: "false" })),
    ).toThrow();
    expect(() =>
      normalizeJobDetail(job({ execute_authorized: null })),
    ).toThrow();
  });

  it("rejects a pending Job that claims a start time", () => {
    expect(() => normalizeJobDetail(job({ started_at: NOW }))).toThrow();
  });

  it("rejects an owner-less running Job and an unowned pending Job with owner evidence", () => {
    expect(() =>
      normalizeJobDetail(job({ status: "running", started_at: NOW })),
    ).toThrow();
    expect(() => normalizeJobDetail(job({ workerId: "worker-1" }))).toThrow();
  });

  it("accepts a running Job with complete Worker ownership evidence", () => {
    const model = normalizeJobDetail(
      job({
        status: "running",
        started_at: NOW,
        workerId: "worker-1",
        ownerStatus: "stale",
        ownerLastHeartbeatAt: LATER,
        lifecycle: jobLifecycle({ state: "running", version: NOW }),
      }),
    );
    expect(model.workerEvidence?.ownerStatus).toBe("stale");
    expect(model.operationalCondition).toBeNull();
  });

  it("rejects an unknown owner status or readiness condition", () => {
    expect(() =>
      normalizeJobDetail(
        job({
          status: "running",
          started_at: NOW,
          workerId: "worker-1",
          ownerStatus: "ghost",
          ownerLastHeartbeatAt: LATER,
          lifecycle: jobLifecycle({ state: "running" }),
        }),
      ),
    ).toThrow();
    expect(() =>
      normalizeJobDetail(
        job({
          operationalCondition: {
            condition: "maybe",
            stage: "pending",
            durableState: "x",
            sideEffects: "none",
            retrySafe: true,
            nextAction: "y",
          },
        }),
      ),
    ).toThrow();
  });

  it("accepts a stale owner together with its unusable-Worker condition", () => {
    const model = normalizeJobDetail(
      job({
        status: "running",
        started_at: NOW,
        workerId: "worker-1",
        ownerStatus: "stale",
        ownerLastHeartbeatAt: LATER,
        lifecycle: jobLifecycle({ state: "running" }),
        operationalCondition: {
          condition: "stale_worker",
          stage: "running",
          durableState: "the owning processing worker has a stale heartbeat",
          sideEffects: "none",
          retrySafe: true,
          nextAction: "restart the resident worker",
        },
      }),
    );
    expect(model.workerEvidence?.ownerStatus).toBe("stale");
    expect(model.operationalCondition?.condition).toBe("stale_worker");
  });

  it("rejects a Job whose lifecycle contradicts its cancellation state", () => {
    expect(() =>
      normalizeJobDetail(
        job({ lifecycle: jobLifecycle({ cancellationRequested: true }) }),
      ),
    ).toThrow();
  });

  it("rejects a lifecycle projection that belongs to another Job", () => {
    expect(() =>
      normalizeJobDetail(
        job({ lifecycle: jobLifecycle({ objectId: "job-2" }) }),
      ),
    ).toThrow();
  });

  it("accepts bounded failure evidence and rejects a malformed one", () => {
    const model = normalizeJobDetail(
      job({
        status: "failed",
        started_at: NOW,
        completed_at: LATER,
        task_id: "task-1",
        lifecycle: jobLifecycle({ state: "failed" }),
        failure: {
          category: "processing_error",
          message: "the queued workflow failed",
          durableState: "the queued workflow failed",
          sideEffects: "none",
          retrySafe: false,
          nextAction: "inspect the linked Task results",
        },
      }),
    );
    expect(model.failure?.category).toBe("processing_error");
    expect(() =>
      normalizeJobDetail(job({ failure: { category: "x" } })),
    ).toThrow();
  });

  it("never carries a hostile historical record into the model", () => {
    const model = normalizeJobDetail(
      job({
        error:
          "Authorization: Bearer topsecret /home/alice/private.mkv " +
          "https://private.example/api /mnt/private-library " +
          "C:\\Users\\alice\\media",
        failure_category: "workflow_cancelled",
        failure_next_action: "Authorization: Bearer topsecret",
        definition_fingerprint: "fingerprint-value",
        source_scope: "/srv/media",
        configuration_snapshot_digest:
          "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
      }),
    );
    const serialized = JSON.stringify(model);
    expect(serialized).not.toContain("topsecret");
    expect(serialized).not.toContain("/home/alice");
    expect(serialized).not.toContain("https://private.example");
    expect(serialized).not.toContain("/mnt/private-library");
    expect(serialized).not.toContain("C:\\Users\\alice");
    expect(serialized).not.toContain("/srv/media");
    expect(serialized).not.toContain("deadbeef");
    expect(serialized).not.toContain("fingerprint-value");
    expect("configurationSnapshotDigest" in model).toBe(false);
    expect("error" in model).toBe(false);
  });
});

describe("normalizeJobListPage", () => {
  it("echoes the submitted backend filters", () => {
    const page = normalizeJobListPage({
      items: [job()],
      limit: 20,
      status: "pending",
      command: "scan",
      truncated: false,
      previous_cursor: null,
      next_cursor: null,
    });
    expect(page.status).toBe("pending");
    expect(page.command).toBe("scan");
  });

  it("rejects an unknown echoed command", () => {
    expect(() =>
      normalizeJobListPage({
        items: [],
        limit: 20,
        status: null,
        command: "delete-everything",
      }),
    ).toThrow();
  });
});
