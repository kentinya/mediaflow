import { describe, expect, it } from "vitest";
import { normalizeWorkerList, normalizeWorkerReadiness } from "./worker";

const READY = {
  ready: true,
  condition: "ready",
  category: null,
  durableState: "resident processing worker is live and ready",
  sideEffects: "none",
  retrySafe: true,
  nextAction: "none",
  activeWorkersCount: 1,
  activeSnapshotId: "snap-1",
  activeSnapshotDigest: "digest-1",
  expectedRuntimeSchemaVersion: 33,
};

describe("normalizeWorkerReadiness", () => {
  it("accepts a ready document", () => {
    const model = normalizeWorkerReadiness(READY);
    expect(model.ready).toBe(true);
    expect(model.condition).toBe("ready");
    expect(model.category).toBeNull();
  });

  it("never models an Active snapshot digest", () => {
    // The administrative compatibility document still carries the digest, so
    // the Operations model must ignore it instead of retaining a fingerprint.
    const model = normalizeWorkerReadiness(READY);
    expect(JSON.stringify(model)).not.toContain("digest-1");
    expect("activeSnapshotDigest" in model).toBe(false);
  });

  it("accepts a not-ready document with an actionable reason", () => {
    const model = normalizeWorkerReadiness({
      ...READY,
      ready: false,
      condition: "no_worker",
      category: "no_worker",
      activeWorkersCount: 0,
      nextAction: "start a processing worker",
    });
    expect(model.ready).toBe(false);
    expect(model.nextAction).toBe("start a processing worker");
  });

  it("rejects a coerced readiness flag or an unknown condition", () => {
    expect(() =>
      normalizeWorkerReadiness({ ...READY, ready: "true" }),
    ).toThrow();
    expect(() =>
      normalizeWorkerReadiness({ ...READY, condition: "mostly_ready" }),
    ).toThrow();
  });

  it("rejects a contradicted readiness flag, category or worker count", () => {
    expect(() =>
      normalizeWorkerReadiness({ ...READY, condition: "stale_worker" }),
    ).toThrow();
    expect(() =>
      normalizeWorkerReadiness({
        ...READY,
        ready: false,
        condition: "no_worker",
        category: null,
        activeWorkersCount: 0,
      }),
    ).toThrow();
    expect(() =>
      normalizeWorkerReadiness({ ...READY, activeWorkersCount: 0 }),
    ).toThrow();
    expect(() =>
      normalizeWorkerReadiness({
        ...READY,
        ready: false,
        condition: "no_worker",
        category: "no_worker",
        activeWorkersCount: -1,
      }),
    ).toThrow();
  });
});

describe("normalizeWorkerList", () => {
  function worker(overrides: Record<string, unknown> = {}) {
    return {
      worker_id: "worker-1",
      label: "resident",
      status: "live",
      last_heartbeat_at: "2026-08-22T12:00:00+00:00",
      registered_at: "2026-08-22T11:00:00+00:00",
      heartbeat_interval_seconds: 5,
      supported_commands: ["scan", "preview"],
      configuration_snapshot_id: "snap-1",
      runtime_schema_version: 33,
      ...overrides,
    };
  }

  it("accepts a modelled worker list", () => {
    const model = normalizeWorkerList({ workers: [worker()], count: 1 });
    expect(model.workers[0]?.supportedCommands).toEqual(["scan", "preview"]);
  });

  it("rejects an unknown supported command instead of coercing it", () => {
    expect(() =>
      normalizeWorkerList({
        workers: [worker({ supported_commands: ["scan", "obliterate"] })],
        count: 1,
      }),
    ).toThrow();
    expect(() =>
      normalizeWorkerList({
        workers: [worker({ supported_commands: "scan" })],
        count: 1,
      }),
    ).toThrow();
  });

  it("rejects an unknown worker status or a duplicated worker", () => {
    expect(() =>
      normalizeWorkerList({ workers: [worker({ status: "busy" })], count: 1 }),
    ).toThrow();
    expect(() =>
      normalizeWorkerList({ workers: [worker(), worker()], count: 2 }),
    ).toThrow();
  });

  it("rejects a total smaller than the returned page", () => {
    expect(() =>
      normalizeWorkerList({ workers: [worker()], count: 0 }),
    ).toThrow();
  });
});
