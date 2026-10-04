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
  preview?: unknown,
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
    ...(preview === undefined ? {} : { preview }),
  };
}

const RECOVERY = {
  available: true,
  reason: null,
  method: "POST",
  path: "/api/v1/tasks/task-1/remaining-scope-previews",
  requiresConfirmation: false,
  sideEffects: "none",
  durableOutcome: "a durable zero-mutation exact Preview is stored",
  nextAction: "review the exact Preview, then authorize execution again",
};

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

  it("accepts the raw state against a closed allow-set", () => {
    // A caller that cannot know one exact raw state (the unified run overview,
    // whose own aggregate status is derived) passes the modelled set; the
    // projection's own raw state must still be one of them.
    const model = normalizeLifecycleProjection(projection(), {
      objectType: "task",
      objectId: "task-1",
      state: ["pending", "running", "paused"],
    });
    expect(model.state).toBe("running");
    expect(() =>
      normalizeLifecycleProjection(projection({ state: "unknown" }), {
        objectType: "task",
        objectId: "task-1",
        state: ["pending", "running", "paused"],
      }),
    ).toThrow();
    // An empty allow-set cannot describe any real object state.
    expect(() =>
      normalizeLifecycleProjection(projection(), {
        objectType: "task",
        objectId: "task-1",
        state: [],
      }),
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

describe("native continuation recovery normalization", () => {
  it("normalizes the recovery entry of a withheld Continue", () => {
    const model = normalizeLifecycleProjection(
      projection({
        state: "paused",
        actions: [
          action(
            "resume",
            false,
            "the stored execute flag is not authority",
            RECOVERY,
          ),
        ],
      }),
      { ...OBJECT, state: "paused" },
    );
    expect(model.actions[0]?.recovery).toEqual({
      action: "preview",
      method: "POST",
      path: "/api/v1/tasks/task-1/remaining-scope-previews",
      available: true,
      confirmationRequired: false,
      durableOutcome: "a durable zero-mutation exact Preview is stored",
      sideEffects: "none",
      nextAction: "review the exact Preview, then authorize execution again",
    });
  });

  it("carries no recovery when the backend published none", () => {
    const model = normalizeLifecycleProjection(
      projection({
        state: "paused",
        actions: [action("resume", false, "the pinned revision is gone")],
      }),
      { ...OBJECT, state: "paused" },
    );
    expect(model.actions[0]?.recovery).toBeNull();
  });

  it("rejects a recovery entry that is not a POST instead of rendering it", () => {
    expect(() =>
      normalizeLifecycleProjection(
        projection({
          state: "paused",
          actions: [
            action("resume", false, "authority required", {
              ...RECOVERY,
              method: "DELETE",
            }),
          ],
        }),
        { ...OBJECT, state: "paused" },
      ),
    ).toThrow();
  });

  it("rejects a recovery entry that is not advertised as available", () => {
    expect(() =>
      normalizeLifecycleProjection(
        projection({
          state: "paused",
          actions: [
            action("resume", false, "authority required", {
              ...RECOVERY,
              available: false,
            }),
          ],
        }),
        { ...OBJECT, state: "paused" },
      ),
    ).toThrow();
  });
});
