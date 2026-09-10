import { describe, expect, it } from "vitest";
import {
  availableLifecycleAction,
  availableLifecycleActions,
  normalizeLifecycleProjection,
} from "./lifecycle";

const OBJECT = {
  objectType: "task" as const,
  objectId: "task-1",
  state: "running",
};

function projection(overrides: Record<string, unknown> = {}) {
  return {
    objectType: "task",
    objectId: "task-1",
    state: "running",
    version: "2026-08-22T12:00:00+00:00",
    terminal: false,
    permitted: true,
    permission: "cancel_job",
    knownEffects: "no Storage effect is recorded for this Task",
    nextAction: "refresh the Task to read the durable state",
    pauseRequested: false,
    effectCertainty: "none",
    resultsObserved: 0,
    resultsComplete: true,
    uncertainResults: 0,
    actions: [
      action("cancel", true, null),
      action("pause", true, null),
      action("resume", false, "no durable queued continuation exists"),
    ],
    ...overrides,
  };
}

function action(
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

describe("normalizeLifecycleProjection", () => {
  it("accepts a well-formed projection and exposes only advertised actions", () => {
    const model = normalizeLifecycleProjection(projection(), OBJECT);
    expect(model.permitted).toBe(true);
    expect(availableLifecycleActions(model).map((item) => item.action)).toEqual(
      ["cancel", "pause"],
    );
    expect(availableLifecycleAction(model, "resume")).toBeNull();
    expect(availableLifecycleAction(model, "cancel")?.durableOutcome).toContain(
      "durable",
    );
  });

  it("rejects a projection for another object, type or state", () => {
    expect(() =>
      normalizeLifecycleProjection(projection({ objectId: "task-2" }), OBJECT),
    ).toThrow();
    expect(() =>
      normalizeLifecycleProjection(projection({ objectType: "job" }), OBJECT),
    ).toThrow();
    expect(() =>
      normalizeLifecycleProjection(projection({ state: "paused" }), OBJECT),
    ).toThrow();
  });

  it("rejects an unknown action name", () => {
    expect(() =>
      normalizeLifecycleProjection(
        projection({ actions: [action("obliterate", true, null)] }),
        OBJECT,
      ),
    ).toThrow();
  });

  it("rejects a job projection that advertises a Task-only action", () => {
    expect(() =>
      normalizeLifecycleProjection(
        {
          ...projection(),
          objectType: "job",
          objectId: "job-1",
          actions: [action("pause", true, null)],
        },
        { objectType: "job", objectId: "job-1", state: "running" },
      ),
    ).toThrow();
  });

  it("rejects duplicated actions", () => {
    expect(() =>
      normalizeLifecycleProjection(
        projection({
          actions: [
            action("cancel", false, "not available"),
            action("cancel", false, "not available"),
          ],
        }),
        OBJECT,
      ),
    ).toThrow();
  });

  it("rejects contradictory availability and reason fields", () => {
    expect(() =>
      normalizeLifecycleProjection(
        projection({ actions: [action("cancel", true, "because")] }),
        OBJECT,
      ),
    ).toThrow();
    expect(() =>
      normalizeLifecycleProjection(
        projection({ actions: [action("cancel", false, null)] }),
        OBJECT,
      ),
    ).toThrow();
  });

  it("rejects an actionable control for a read-only principal", () => {
    expect(() =>
      normalizeLifecycleProjection(
        projection({
          permitted: false,
          actions: [action("cancel", true, null)],
        }),
        OBJECT,
      ),
    ).toThrow();
  });

  it("rejects a coerced boolean or an unknown effect certainty", () => {
    expect(() =>
      normalizeLifecycleProjection(projection({ terminal: "false" }), OBJECT),
    ).toThrow();
    expect(() =>
      normalizeLifecycleProjection(
        projection({ effectCertainty: "probably_fine" }),
        OBJECT,
      ),
    ).toThrow();
  });

  it("rejects a missing or non-object projection", () => {
    expect(() => normalizeLifecycleProjection(null, OBJECT)).toThrow();
    expect(() => normalizeLifecycleProjection("cancel", OBJECT)).toThrow();
  });
});
