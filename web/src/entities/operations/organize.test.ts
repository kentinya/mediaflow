import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/manual-operations.json";
import {
  normalizeOrganizeAction,
  normalizeOrganizeExecution,
  normalizeOrganizeIntent,
  normalizeOrganizePreview,
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

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;

function previewDocument(): Json {
  const value = JSON.parse(
    JSON.stringify(documents["organizePreviewDetail"]),
  ) as Json;
  value["previewId"] = "preview-1";
  value["intentId"] = "intent-1";
  value["executionCandidateItemIds"] = ["item-1"];
  const item = (value["items"] as Json[])[0];
  item["itemId"] = "item-1";
  const action = (value["actions"] as Json)["execute"] as Json;
  action["available"] = true;
  action["reason"] = null;
  action["path"] = "/api/v1/operations/organize/previews/preview-1/execute";
  return value;
}

function intentDocument(): Json {
  const value = JSON.parse(JSON.stringify(documents["organizeIntent"])) as Json;
  value["intentId"] = "intent-1";
  const actions = value["actions"] as Json;
  for (const actionName of ["choice"] as const) {
    const action = actions[actionName] as Json;
    action["path"] = (action["path"] as string).replace("<uuid>", "intent-1");
  }
  const item = (value["items"] as Json[])[0]!;
  item["itemId"] = "item-1";
  return value;
}

describe("normalizeOrganizeIntent source identity", () => {
  it("preserves a supported long path and boundary whitespace exactly", () => {
    const longPath =
      "LongFolder/" +
      [...Array(6)].map(() => "D".repeat(171)).join("/") +
      "/" +
      "L".repeat(175) +
      ".mkv";
    expect(longPath).toHaveLength(1222);
    const value = intentDocument();
    const item = (value["items"] as Json[])[0]!;
    const source = item["source"] as Json;
    source["path"] = longPath;

    const model = normalizeOrganizeIntent(value);
    expect(model.items[0]?.sourcePath).toBe(longPath);

    source["path"] = " Leading/Trailing name .mkv ";
    expect(normalizeOrganizeIntent(value).items[0]?.sourcePath).toBe(
      " Leading/Trailing name .mkv ",
    );
  });

  it("rejects paths beyond the supported identity bound", () => {
    const value = intentDocument();
    const item = (value["items"] as Json[])[0]!;
    (item["source"] as Json)["path"] = "a".repeat(4097);
    expect(() => normalizeOrganizeIntent(value)).toThrow(
      OrganizeNormalizationError,
    );
  });
});

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

describe("normalizeOrganizePreview candidate safety binding", () => {
  it("requires every execution candidate to have current typed plan safety facts", () => {
    const malformedVariants: Array<(value: Json) => void> = [
      (value) => {
        ((value["items"] as Json[])[0]!["plan"] as Json)["operation"] = null;
      },
      (value) => {
        ((value["items"] as Json[])[0]!["plan"] as Json)[
          "destructiveImplications"
        ] = null;
      },
      (value) => {
        (value["items"] as Json[])[0]!["recognitionType"] = "C";
        ((value["items"] as Json[])[0]!["plan"] as Json)["recognitionType"] =
          null;
      },
      (value) => {
        (value["items"] as Json[])[0]!["current"] = false;
      },
      (value) => {
        (value["items"] as Json[])[0]!["status"] = "blocked";
      },
      (value) => {
        value["executionCandidateItemIds"] = ["missing-item"];
      },
      (value) => {
        value["selection"] = { selectedItemIds: [], unselectedItemIds: [] };
      },
    ];
    for (const mutate of malformedVariants) {
      const value = previewDocument();
      mutate(value);
      expect(() => normalizeOrganizePreview(value)).toThrow(
        OrganizeNormalizationError,
      );
    }
  });

  it("keeps a legitimate blocked no-plan item visible and non-executable", () => {
    const value = previewDocument();
    const item = (value["items"] as Json[])[0]!;
    item["status"] = "blocked";
    item["current"] = false;
    item["executionState"] = "not_available_in_this_task";
    item["plan"] = null;
    value["executionCandidateItemIds"] = [];
    const action = (value["actions"] as Json)["execute"] as Json;
    action["available"] = false;
    action["reason"] = "no Preview item is current, complete and executable";

    const model = normalizeOrganizePreview(value);
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.recognitionType).toBeNull();
    expect(model.items[0]?.operation).toBeNull();
    expect(model.items[0]?.destructiveImplications).toBeNull();
    expect(model.executionCandidateItemIds).toEqual([]);
    expect(model.executeAction.available).toBe(false);
  });

  it("rejects duplicate item identities before they can become an ambiguous candidate", () => {
    const value = previewDocument();
    const item = (value["items"] as Json[])[0]!;
    value["items"] = [item, { ...item, previewItemId: "item-duplicate" }];
    expect(() => normalizeOrganizePreview(value)).toThrow(
      OrganizeNormalizationError,
    );
  });

  it("rejects an offered Execute action without an exact candidate set", () => {
    const value = previewDocument();
    value["executionCandidateItemIds"] = [];
    expect(() => normalizeOrganizePreview(value)).toThrow(
      OrganizeNormalizationError,
    );
  });
});

function executionDocument(): Json {
  const value = JSON.parse(
    JSON.stringify(documents["organizeExecutionDetail"]),
  ) as Json;
  value["executionId"] = "execution-1";
  // The checked-in fixture masks every durable identity, so the exact objects
  // this document belongs to are restored here: the normalizer must name the
  // exact execution and its exact Task, exactly as the real backend emits
  // them for the Execute response and the durable history list.
  value["taskId"] = "task-1";
  const actions = value["actions"] as Json;
  (actions["detail"] as Json)["path"] =
    "/api/v1/operations/organize/executions/execution-1";
  (actions["task"] as Json)["path"] = "/api/v1/operations/tasks/task-1";
  return value;
}

describe("normalizeOrganizeExecution durable evidence", () => {
  it("accepts an attempted/unknown mutation as truthful non-replayable evidence", () => {
    // The executor records an attempted/unknown mutation with no verified
    // effect as the bounded ``UNCERTAIN_EXECUTOR_INVOCATION`` marker. This is
    // truthful evidence, never a malformed read: the model must carry it so a
    // reader can present it instead of replaying the uncertain work.
    const value = executionDocument();
    const item = (value["items"] as Json[])[0];
    item["status"] = "partial";
    item["effectCertainty"] = "attempted_unverified";
    item["completedOperations"] = ["UNCERTAIN_EXECUTOR_INVOCATION"];
    item["uncertainEffects"] = ["executor_invocation"];
    item["effects"] = [
      {
        action: "UNCERTAIN_EXECUTOR_INVOCATION",
        certainty: "attempted_unverified",
        destinationLocation: "One (2001)/One (2001).mkv",
        operation: null,
        sourceLocation: "One.2001.mkv",
        verified: false,
      },
    ];

    const model = normalizeOrganizeExecution(value);
    expect(model.items[0]?.effectCertainty).toBe("attempted_unverified");
    expect(model.items[0]?.uncertainEffects).toEqual(["executor_invocation"]);
    expect(model.items[0]?.effects[0]?.action).toBe(
      "UNCERTAIN_EXECUTOR_INVOCATION",
    );
    expect(model.items[0]?.effects[0]?.verified).toBe(false);
  });

  it("fails closed on malformed execution item and effect data", () => {
    const malformedVariants: Array<(value: Json) => void> = [
      // An unknown execution item status is never modelled.
      (value) => {
        (value["items"] as Json[])[0]["status"] = "hacked";
      },
      // An unknown effect certainty is never modelled.
      (value) => {
        (value["items"] as Json[])[0]["effectCertainty"] = "totally_verified";
      },
      // A verified success is never reported with uncertain certainty.
      (value) => {
        (value["items"] as Json[])[0]["effectCertainty"] = "unknown";
      },
      // A verified flag contradicting its certainty is malformed evidence.
      (value) => {
        (value["items"] as Json[])[0]["effects"] = [
          {
            action: "MOVE",
            certainty: "attempted_unverified",
            destinationLocation: "One (2001)/One (2001).mkv",
            operation: null,
            sourceLocation: "One.2001.mkv",
            verified: true,
          },
        ];
      },
      // An arbitrary effect action marker is never modelled.
      (value) => {
        (value["items"] as Json[])[0]["effects"] = [
          {
            action: "RM_RF_SLASH",
            certainty: "verified_complete",
            destinationLocation: "One (2001)/One (2001).mkv",
            operation: null,
            sourceLocation: "One.2001.mkv",
            verified: true,
          },
        ];
      },
      // An unknown uncertain-effect statement is never modelled.
      (value) => {
        (value["items"] as Json[])[0]["uncertainEffects"] = ["rm -rf /"];
      },
    ];

    for (const mutate of malformedVariants) {
      const value = executionDocument();
      mutate(value);
      // Closed-set item fields surface as the shared invalid-field error;
      // organize-specific contradictions fail with the Organize contract
      // error. Either way the read fails closed: no partial model escapes.
      expect(() => normalizeOrganizeExecution(value)).toThrow();
    }
  });
});
