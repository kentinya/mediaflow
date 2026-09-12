import { describe, expect, it } from "vitest";
import {
  normalizeOrganizeAction,
  OrganizeNormalizationError,
} from "./organize";

/**
 * Focused normalization regressions for the manual Organize action contracts.
 *
 * A route is only ever an action's transport when it is exactly the owned
 * object's route plus the kind's exact suffix, and every real object identity
 * and path segment is one URI-safe segment: the only non-URI-safe segment any
 * path may carry is the one intentional `{itemId}` route-template segment the
 * backend publishes for the per-item choice route. Anything else fails closed
 * so a hostile or masked placeholder value can never become an executable
 * control.
 */

function offeredExecuteAction(path: string): Record<string, unknown> {
  return {
    available: true,
    durableOutcome:
      "one durable admitted execution and its Processing Worker outcome are stored; only OrganizerExecutor may then mutate Storage",
    method: "POST",
    nextAction: "confirm one Execute action for the selected exact items",
    path,
    reason: null,
    requiresConfirmation: true,
    sideEffects: "reported_per_item",
  };
}

describe("normalizeOrganizeAction route binding", () => {
  it("rejects a non-URI-safe object identity and its matching execute route", () => {
    expect(() =>
      normalizeOrganizeAction(
        offeredExecuteAction(
          "/api/v1/operations/organize/previews/<preview>/execute",
        ),
        "actions.execute",
        "preview-execute",
        "<preview>",
      ),
    ).toThrow(OrganizeNormalizationError);
  });

  it("rejects a non-URI-safe segment even when the identity itself is safe", () => {
    expect(() =>
      normalizeOrganizeAction(
        offeredExecuteAction(
          "/api/v1/operations/organize/previews/<preview>/execute",
        ),
        "actions.execute",
        "preview-execute",
        "preview-1",
      ),
    ).toThrow(OrganizeNormalizationError);
  });

  it("rejects a non-URI-safe identity even when the path names a safe object", () => {
    expect(() =>
      normalizeOrganizeAction(
        offeredExecuteAction(
          "/api/v1/operations/organize/previews/preview-1/execute",
        ),
        "actions.execute",
        "preview-execute",
        "<preview>",
      ),
    ).toThrow(OrganizeNormalizationError);
  });

  it("rejects braces and angle brackets outside the one template segment", () => {
    for (const path of [
      "/api/v1/operations/organize/previews/preview-1/{execute}",
      "/api/v1/operations/organize/previews/pre{view}/execute",
      "/api/v1/operations/organize/previews/preview-1/execu>te",
    ]) {
      expect(() =>
        normalizeOrganizeAction(
          offeredExecuteAction(path),
          "actions.execute",
          "preview-execute",
          "preview-1",
        ),
      ).toThrow(OrganizeNormalizationError);
    }
  });

  it("rejects the route template outside its declared parameter position", () => {
    // `{itemId}` is a placeholder for the per-item parameter, never an object
    // identity: a path whose identity segment is the template is malformed.
    expect(() =>
      normalizeOrganizeAction(
        offeredExecuteAction(
          "/api/v1/operations/organize/previews/{itemId}/execute",
        ),
        "actions.execute",
        "preview-execute",
        "preview-1",
      ),
    ).toThrow(OrganizeNormalizationError);
  });

  it("accepts the one intentional {itemId} route-template segment for the per-item choice route", () => {
    const model = normalizeOrganizeAction(
      {
        available: true,
        durableOutcome:
          "a durable optimistic choice revision is stored and every earlier Preview of this intent becomes historical evidence",
        method: "POST",
        nextAction:
          "edit one item choice with its current intent and item versions",
        path: "/api/v1/operations/organize/intents/intent-1/items/{itemId}/choice",
        reason: null,
        sideEffects: "none",
      },
      "actions.choice",
      "intent-choice",
      "intent-1",
    );
    expect(model.available).toBe(true);
    expect(model.method).toBe("POST");
    expect(model.path).toBe(
      "/api/v1/operations/organize/intents/intent-1/items/{itemId}/choice",
    );
  });

  it("accepts a real per-item segment in the parameter position", () => {
    const model = normalizeOrganizeAction(
      {
        available: true,
        reason: null,
        method: "POST",
        path: "/api/v1/operations/organize/intents/intent-1/items/item-1/choice",
        sideEffects: "none",
      },
      "actions.choice",
      "intent-choice",
      "intent-1",
    );
    expect(model.available).toBe(true);
    expect(model.path).toBe(
      "/api/v1/operations/organize/intents/intent-1/items/item-1/choice",
    );
  });

  it("still rejects a wrong suffix, method or another object's route", () => {
    for (const path of [
      // The Preview's own read route without the /execute suffix.
      "/api/v1/operations/organize/previews/preview-1",
      // An arbitrary descendant of the owned route.
      "/api/v1/operations/organize/previews/preview-1/execute/extra",
      // A wrong fixed suffix.
      "/api/v1/operations/organize/previews/preview-1/executes",
      // Another object's route.
      "/api/v1/operations/organize/previews/other-preview/execute",
      // Another collection's route.
      "/api/v1/operations/tasks/task-1",
    ]) {
      expect(() =>
        normalizeOrganizeAction(
          offeredExecuteAction(path),
          "actions.execute",
          "preview-execute",
          "preview-1",
        ),
      ).toThrow(OrganizeNormalizationError);
    }
    expect(() =>
      normalizeOrganizeAction(
        {
          ...offeredExecuteAction(
            "/api/v1/operations/organize/previews/preview-1/execute",
          ),
          method: "GET",
        },
        "actions.execute",
        "preview-execute",
        "preview-1",
      ),
    ).toThrow(OrganizeNormalizationError);
  });

  it("still accepts the transport-less recovery handoff and rejects a transport-less intent execute", () => {
    const recovery = normalizeOrganizeAction(
      {
        available: true,
        method: null,
        nextAction:
          "open Review & Recovery to inspect the failed item; MediaFlow never replays an uncertain mutation automatically",
        path: null,
        reason: null,
        sideEffects: "none",
      },
      "actions.recovery",
      "execution-recovery",
    );
    expect(recovery.available).toBe(true);
    expect(recovery.method).toBeNull();
    expect(recovery.path).toBeNull();

    expect(() =>
      normalizeOrganizeAction(
        {
          available: true,
          method: null,
          path: null,
          reason: null,
          sideEffects: "none",
        },
        "actions.execute",
        "intent-execute",
      ),
    ).toThrow(OrganizeNormalizationError);
  });
});
