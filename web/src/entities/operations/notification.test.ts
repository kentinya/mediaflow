import { describe, expect, it } from "vitest";
import {
  normalizeNotificationAction,
  normalizeNotificationActiveConfiguration,
  normalizeNotificationDefinitionsPage,
  normalizeNotificationDeliveryDetail,
  normalizeNotificationDraftState,
  normalizeNotificationActivation,
  normalizeNotificationRecoveryResult,
  normalizeWebhookDefinition,
  normalizeWebhookDefinitionMutation,
  normalizeWebhookTestResult,
  NotificationNormalizationError,
} from "./notification";

/**
 * Focused normalization regressions for the V2 Notification operator
 * documents. Every action transport is bound to its exact owned route, method
 * and URI-safe identity, every contradictory state block fails closed, and a
 * test outcome that carries a revision digest is malformed by definition.
 */

function offeredAction(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: "/api/v1/operations/notifications/webhooks/ops/test",
    requiresConfirmation: false,
    sideEffects: "one_signed_test_request",
    durableOutcome: "no durable change",
    nextAction: "test the exact displayed revision",
    ...overrides,
  };
}

function webhookDocumentPayload(
  id: string,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id,
    url: "https://example.invalid/hooks/mediaflow",
    secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
    events: ["job.completed"],
    enabled: true,
    timeoutSeconds: 10,
    maxAttempts: 5,
    baseRetrySeconds: 5,
    maxRetrySeconds: 300,
    secretReadiness: [
      { field: "secretEnv", env: "MEDIAFLOW_WEBHOOK_SECRET", state: "UNSET" },
    ],
    structuralValid: true,
    validationError: null,
    ...overrides,
  };
}

function definitionPayload(
  id: string,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const operationsRoute = `/api/v1/operations/notifications/webhooks/${id}`;
  const draftRoute = `/api/v1/configuration/revisions/rev-draft/objects/webhooks/${id}`;
  return {
    ...webhookDocumentPayload(id),
    definitionState: "active",
    activeConfiguration: {
      revisionId: "rev-1",
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    draftState: {
      present: true,
      reason: null,
      revisionId: "rev-draft",
      revisionVersion: 4,
      revisionStatus: "draft",
      baseActiveRevisionId: "rev-1",
      updatedAt: "2026-09-12T00:00:00+00:00",
      validatedAt: null,
      validationErrors: [],
    },
    actions: {
      detail: {
        available: true,
        reason: null,
        method: "GET",
        path: operationsRoute,
        sideEffects: "none",
        durableOutcome: null,
        nextAction: "inspect the exact bounded Webhook definition state",
      },
      test: offeredAction(),
      edit: {
        available: true,
        reason: null,
        method: "PUT",
        path: draftRoute,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "the bounded definition form is stored",
        nextAction: "save the bounded form",
      },
      copy: {
        available: true,
        reason: null,
        method: "POST",
        path: `${draftRoute}/copy`,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "a copied definition is stored",
        nextAction: "open the copied definition",
      },
      enable: {
        available: true,
        reason: null,
        method: "POST",
        path: `${draftRoute}/enable`,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "the definition is enabled in the Draft",
        nextAction: "review the Draft",
      },
      disable: {
        available: true,
        reason: null,
        method: "POST",
        path: `${draftRoute}/disable`,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "the definition is disabled in the Draft",
        nextAction: "review the Draft",
      },
      draftCreate: {
        available: true,
        reason: null,
        method: "POST",
        path: "/api/v1/configuration/revisions/rev-1/successor",
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "a successor Draft is stored",
        nextAction: "create the successor Draft",
      },
      activate: {
        available: true,
        reason: null,
        method: "POST",
        path: `${operationsRoute}/activate-draft`,
        requiresConfirmation: true,
        sideEffects: "none",
        durableOutcome: "the reviewed Draft becomes Active",
        nextAction: "activate the reviewed Draft",
      },
    },
    ...overrides,
  };
}

describe("notification active configuration", () => {
  it("normalizes the exact immutable identity", () => {
    const model = normalizeNotificationActiveConfiguration({
      revisionId: "rev-1",
      version: 3,
      revisionSequence: 2,
      status: "active",
    });
    expect(model).toEqual({
      revisionId: "rev-1",
      version: 3,
      revisionSequence: 2,
      status: "active",
    });
  });

  it("fails closed on a missing revision identity", () => {
    expect(() =>
      normalizeNotificationActiveConfiguration({
        version: 3,
        revisionSequence: 2,
        status: "active",
      }),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("notification draft state", () => {
  it("requires the exact optimistic identity when a Draft is present", () => {
    expect(
      normalizeNotificationDraftState({
        present: true,
        reason: null,
        revisionId: "rev-draft",
        revisionVersion: 4,
      }).present,
    ).toBe(true);
    expect(() =>
      normalizeNotificationDraftState({
        present: true,
        reason: null,
        revisionId: null,
        revisionVersion: null,
      }),
    ).toThrow(NotificationNormalizationError);
  });

  it("rejects a present=false block that carries revision evidence", () => {
    expect(() =>
      normalizeNotificationDraftState({
        present: false,
        reason: "no draft",
        revisionId: "rev-draft",
        revisionVersion: null,
      }),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("webhook definition", () => {
  it("normalizes the bounded document and exact action transports", () => {
    const model = normalizeWebhookDefinition(definitionPayload("ops"));
    expect(model.document.id).toBe("ops");
    expect(model.document.events).toEqual(["job.completed"]);
    expect(model.definitionState).toBe("active");
    expect(model.actions.activate.requiresConfirmation).toBe(true);
    expect(model.actions.detail.path).toBe(
      "/api/v1/operations/notifications/webhooks/ops",
    );
  });

  it("fails closed when an unknown event value appears", () => {
    expect(() =>
      normalizeWebhookDefinition(
        definitionPayload("ops", {
          events: ["job.completed", "media.imported"],
        }),
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when an action names a foreign route", () => {
    const payload = definitionPayload("ops");
    const actions = payload.actions as Record<string, unknown>;
    actions.test = offeredAction({
      path: "/api/v1/operations/notifications/webhooks/other/test",
    });
    expect(() => normalizeWebhookDefinition(payload)).toThrow(
      NotificationNormalizationError,
    );
  });

  it("fails closed when a withheld action carries no reason", () => {
    const payload = definitionPayload("ops");
    const actions = payload.actions as Record<string, unknown>;
    actions.test = { ...offeredAction(), available: false, reason: null };
    expect(() => normalizeWebhookDefinition(payload)).toThrow(
      NotificationNormalizationError,
    );
  });

  it("rejects a contradictory structural block", () => {
    expect(() =>
      normalizeWebhookDefinition(
        definitionPayload("ops", { structuralValid: "yes" }),
      ),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("notification definitions page", () => {
  function pagePayload(
    overrides: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      activeConfiguration: {
        revisionId: "rev-1",
        version: 3,
        revisionSequence: 2,
        status: "active",
      },
      items: [definitionPayload("ops")],
      total: 1,
      truncated: false,
      draftState: {
        present: false,
        reason: "no open successor Draft exists",
        revisionId: null,
        revisionVersion: null,
        revisionStatus: null,
        baseActiveRevisionId: null,
        updatedAt: null,
        validatedAt: null,
        validationErrors: [],
      },
      supportedEvents: ["job.completed", "job.failed"],
      actions: {
        create: {
          available: false,
          reason: "an open successor Draft is required",
          method: "POST",
          path: null,
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome: "the definition is stored in the Draft",
          nextAction: "start a successor Draft",
        },
        createDraft: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/configuration/revisions/rev-1/successor",
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome: "a successor Draft is stored",
          nextAction: "create the successor Draft",
        },
      },
      ...overrides,
    };
  }

  it("normalizes the whole page", () => {
    const page = normalizeNotificationDefinitionsPage(pagePayload());
    expect(page.items).toHaveLength(1);
    expect(page.supportedEvents).toEqual(["job.completed", "job.failed"]);
    expect(page.actions.create.available).toBe(false);
    expect(page.actions.create.reason).toContain("successor Draft");
  });

  it("fails closed above the deterministic page limit", () => {
    const items = Array.from({ length: 101 }, (_value, index) =>
      definitionPayload(`webhook-${index}`),
    );
    expect(() =>
      normalizeNotificationDefinitionsPage(pagePayload({ items, total: 101 })),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed on an unsupported event in the advertised catalog", () => {
    expect(() =>
      normalizeNotificationDefinitionsPage(
        pagePayload({ supportedEvents: ["job.completed", "smtp.sent"] }),
      ),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("webhook test result", () => {
  const REQUESTED = { webhookId: "ops", revisionId: "rev-draft", version: 4 };

  function testResultPayload(
    overrides: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      testId: "test-1",
      webhook: { id: "ops" },
      revision: { revisionId: "rev-draft", version: 4, status: "draft" },
      outcome: "success",
      category: "http_204",
      responseStatus: 204,
      message: "the Webhook endpoint returned HTTP 204",
      durableState: "no_delivery_created_no_configuration_change",
      sideEffects: "none",
      retrySafe: true,
      nextAction: "no further action required",
      ...overrides,
    };
  }

  it("normalizes a bounded success outcome bound to the requested mutation", () => {
    const result = normalizeWebhookTestResult(testResultPayload(), REQUESTED);
    expect(result.outcome).toBe("success");
    expect(result.category).toBe("http_204");
    expect(result.webhookId).toBe("ops");
  });

  it("fails closed when the outcome names another webhook", () => {
    expect(() =>
      normalizeWebhookTestResult(
        testResultPayload({ webhook: { id: "other" } }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the outcome names another revision or version", () => {
    expect(() =>
      normalizeWebhookTestResult(
        testResultPayload({
          revision: { revisionId: "rev-other", version: 4, status: "draft" },
        }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeWebhookTestResult(
        testResultPayload({
          revision: { revisionId: "rev-draft", version: 5, status: "draft" },
        }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the outcome carries a revision digest", () => {
    expect(() =>
      normalizeWebhookTestResult(
        testResultPayload({
          revision: {
            revisionId: "rev-draft",
            version: 4,
            status: "draft",
            digest: "sha256:deadbeef",
          },
        }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed on an unknown outcome category", () => {
    expect(() =>
      normalizeWebhookTestResult(
        testResultPayload({
          category: "stack_trace",
          responseStatus: null,
          message: "boom",
        }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed on an unsafe webhook identity", () => {
    expect(() =>
      normalizeWebhookTestResult(
        testResultPayload({ webhook: { id: "../escape" } }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("notification delivery detail", () => {
  function deliveryPayload(
    overrides: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      deliveryId: "delivery-1",
      webhookId: "ops",
      eventId: "event-1",
      eventType: "job.completed",
      status: "dead-letter",
      attempts: 3,
      createdAt: "2026-09-12T00:00:00+00:00",
      updatedAt: "2026-09-12T00:05:00+00:00",
      deliveredAt: null,
      nextAttemptAt: "2026-09-12T00:05:00+00:00",
      failureCategory: "http_400",
      responseStatus: 400,
      lease: { state: "not_leased" },
      knownEffects: "the receiver never confirmed success",
      retrySafe: true,
      nextAction: "confirm the endpoint is reachable, then requeue",
      recovery: {
        availableActions: ["requeue-dead-letter"],
        reason: "The delivery reached the terminal dead-letter state.",
        actions: [
          {
            name: "requeue-dead-letter",
            durableState: "the delivery stays one row",
            sideEffects: "no new delivery and no media change",
            retrySafe: true,
            duplicateImplication: "receivers must tolerate duplicates",
            nextAction: "explicitly requeue this delivery",
          },
        ],
      },
      actions: {
        requeue: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/notifications/delivery-1/requeue",
          requiresConfirmation: true,
          sideEffects: "delivery_queue_state_only",
          durableOutcome: "the delivery returns to pending",
          nextAction: "confirm the requeue",
        },
      },
      ...overrides,
    };
  }

  it("normalizes the bounded detail with permission-aware actions", () => {
    const model = normalizeNotificationDeliveryDetail(deliveryPayload());
    expect(model.delivery.status).toBe("dead-letter");
    expect(model.lease.state).toBe("not_leased");
    expect(model.recovery.availableActions).toEqual(["requeue-dead-letter"]);
    expect(model.actions.requeue?.path).toBe(
      "/api/v1/notifications/delivery-1/requeue",
    );
    expect(model.actions.resolveStale).toBeNull();
    expect(model.recovery.evidence[0].duplicateImplication).toContain(
      "duplicates",
    );
  });

  it("normalizes an expired lease window", () => {
    const model = normalizeNotificationDeliveryDetail(
      deliveryPayload({
        status: "delivering",
        lease: {
          state: "expired",
          leaseSeconds: 300,
          claimedAt: "2026-09-12T00:00:00+00:00",
          expiresAt: "2026-09-12T00:05:00+00:00",
        },
        recovery: {
          availableActions: ["resolve-stale"],
          reason: "The delivery lease expired.",
          actions: [],
        },
        actions: {},
      }),
    );
    expect(model.lease.state).toBe("expired");
    expect(model.actions.requeue).toBeNull();
  });

  it("fails closed when a lease state carries no window", () => {
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({
          status: "delivering",
          lease: { state: "expired" },
        }),
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when a not_leased lease carries window evidence", () => {
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({
          lease: { state: "not_leased", leaseSeconds: 300 },
        }),
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when a recovery transport has no eligibility evidence", () => {
    const payload = deliveryPayload();
    payload.recovery = {
      availableActions: [],
      reason: "no action",
      actions: [],
    };
    expect(() => normalizeNotificationDeliveryDetail(payload)).toThrow(
      NotificationNormalizationError,
    );
  });

  it("fails closed on an unknown delivery status", () => {
    expect(() =>
      normalizeNotificationDeliveryDetail(deliveryPayload({ status: "lost" })),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when requeue is advertised for a non dead-letter delivery", () => {
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({
          status: "delivering",
          lease: {
            state: "active",
            leaseSeconds: 300,
            claimedAt: "2026-09-12T00:00:00+00:00",
            expiresAt: "2026-09-12T00:05:00+00:00",
          },
        }),
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when stale resolution is advertised without an expired lease", () => {
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({
          status: "delivering",
          lease: {
            state: "active",
            leaseSeconds: 300,
            claimedAt: "2026-09-12T00:00:00+00:00",
            expiresAt: "2026-09-12T00:05:00+00:00",
          },
          recovery: {
            availableActions: ["resolve-stale"],
            reason: "contradictory",
            actions: [],
          },
          actions: {},
        }),
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({
          status: "dead-letter",
          recovery: {
            availableActions: ["resolve-stale"],
            reason: "contradictory",
            actions: [],
          },
          actions: {},
        }),
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when a lease window contradicts a non-delivering status", () => {
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({
          lease: {
            state: "active",
            leaseSeconds: 300,
            claimedAt: "2026-09-12T00:00:00+00:00",
            expiresAt: "2026-09-12T00:05:00+00:00",
          },
        }),
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when recovery evidence is not advertised as available", () => {
    const payload = deliveryPayload();
    payload.recovery = {
      availableActions: [],
      reason: "no action",
      actions: [
        {
          name: "requeue-dead-letter",
          durableState: "the delivery stays one row",
          sideEffects: "no new delivery and no media change",
          retrySafe: true,
          duplicateImplication: "receivers must tolerate duplicates",
          nextAction: "explicitly requeue this delivery",
        },
      ],
    };
    payload.actions = {};
    expect(() => normalizeNotificationDeliveryDetail(payload)).toThrow(
      NotificationNormalizationError,
    );
  });

  it("fails closed on an unsafe delivery identity", () => {
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({ deliveryId: "delivery/1" }),
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({ deliveryId: "delivery 1" }),
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({ webhookId: "ops%2Fwebhook" }),
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed on an unsafe event identity", () => {
    expect(() =>
      normalizeNotificationDeliveryDetail(
        deliveryPayload({ eventId: "event|1" }),
      ),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("notification action transport", () => {
  it("pins the delivery recovery route to the exact delivery identity", () => {
    const model = normalizeNotificationAction(
      {
        available: true,
        reason: null,
        method: "POST",
        path: "/api/v1/notifications/delivery-9/resolve-stale",
        requiresConfirmation: true,
        sideEffects: "delivery_queue_state_only",
        durableOutcome: "the expired lease is resolved",
        nextAction: "confirm the stale resolution",
      },
      "actions.resolveStale",
      "delivery-resolve-stale",
      "delivery-9",
    );
    expect(model.available).toBe(true);
  });

  it("rejects a resolve-stale transport bound to another delivery", () => {
    expect(() =>
      normalizeNotificationAction(
        {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/notifications/delivery-9/resolve-stale",
          requiresConfirmation: true,
          sideEffects: "delivery_queue_state_only",
          durableOutcome: "the expired lease is resolved",
          nextAction: "confirm the stale resolution",
        },
        "actions.resolveStale",
        "delivery-resolve-stale",
        "delivery-8",
      ),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("draft-only list item", () => {
  it("normalizes a draft-only definition bound to its own identity", () => {
    const payload = {
      ...webhookDocumentPayload("draft-only-webhook", {
        secretReadiness: [],
      }),
      definitionState: "draft-only",
      activeConfiguration: {
        revisionId: "rev-1",
        version: 3,
        revisionSequence: 2,
        status: "active",
      },
      draftState: {
        present: true,
        reason: null,
        revisionId: "rev-draft",
        revisionVersion: 4,
        revisionStatus: "draft",
        baseActiveRevisionId: "rev-1",
        updatedAt: "2026-09-12T00:00:00+00:00",
        validatedAt: null,
        validationErrors: [],
      },
      actions: {
        detail: {
          available: true,
          reason: null,
          method: "GET",
          path: "/api/v1/operations/notifications/webhooks/draft-only-webhook",
          sideEffects: "none",
          durableOutcome: null,
          nextAction: "inspect",
        },
        test: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/operations/notifications/webhooks/draft-only-webhook/test",
          requiresConfirmation: false,
          sideEffects: "one_signed_test_request",
          durableOutcome: "no durable change",
          nextAction: "test the exact displayed revision",
        },
        edit: {
          available: true,
          reason: null,
          method: "PUT",
          path: "/api/v1/configuration/revisions/rev-draft/objects/webhooks/draft-only-webhook",
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome: "stored",
          nextAction: "save",
        },
        copy: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/configuration/revisions/rev-draft/objects/webhooks/draft-only-webhook/copy",
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome: "copied",
          nextAction: "open the copy",
        },
        enable: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/configuration/revisions/rev-draft/objects/webhooks/draft-only-webhook/enable",
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome: "enabled in draft",
          nextAction: "review",
        },
        disable: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/configuration/revisions/rev-draft/objects/webhooks/draft-only-webhook/disable",
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome: "disabled in draft",
          nextAction: "review",
        },
        draftCreate: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/configuration/revisions/rev-1/successor",
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome: "successor draft",
          nextAction: "create",
        },
        activate: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/operations/notifications/webhooks/draft-only-webhook/activate-draft",
          requiresConfirmation: true,
          sideEffects: "none",
          durableOutcome: "published",
          nextAction: "activate",
        },
      },
    };
    const model = normalizeWebhookDefinition(
      payload as unknown as Record<string, unknown>,
    );
    expect(model.definitionState).toBe("draft-only");
    expect(model.document.id).toBe("draft-only-webhook");
  });
});

describe("notification activation result", () => {
  const REQUESTED = { webhookId: "ops", revisionId: "rev-draft", version: 4 };

  function activationPayload(
    overrides: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      // The managed activation preserves the reviewed Draft revision identity
      // as the new Active identity: same revision id, same version.
      activatedRevisionId: "rev-draft",
      activatedVersion: 4,
      revisionSequence: 4,
      publishedFromRevisionId: "rev-draft",
      publishedFromVersion: 4,
      activeConfiguration: {
        revisionId: "rev-draft",
        version: 4,
        revisionSequence: 4,
        status: "active",
      },
      webhook: webhookDocumentPayload("ops"),
      ...overrides,
    };
  }

  it("normalizes a success bound to the requested mutation", () => {
    const model = normalizeNotificationActivation(
      activationPayload(),
      REQUESTED,
    );
    expect(model.activatedRevisionId).toBe("rev-draft");
    expect(model.activatedVersion).toBe(4);
    expect(model.webhook?.id).toBe("ops");
  });

  it("fails closed when the response names another webhook", () => {
    expect(() =>
      normalizeNotificationActivation(
        activationPayload({ webhook: webhookDocumentPayload("other") }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the response answers another reviewed revision", () => {
    expect(() =>
      normalizeNotificationActivation(
        activationPayload({ publishedFromRevisionId: "rev-older" }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeNotificationActivation(
        activationPayload({ publishedFromVersion: 3 }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the activated identity is split from the reviewed Draft", () => {
    // A success document whose Active revision/version differs from the exact
    // reviewed Draft identity never renders as this activation.
    expect(() =>
      normalizeNotificationActivation(
        activationPayload({
          activatedRevisionId: "rev-active-2",
          activatedVersion: 5,
          activeConfiguration: {
            revisionId: "rev-active-2",
            version: 5,
            revisionSequence: 4,
            status: "active",
          },
        }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeNotificationActivation(
        activationPayload({ activatedVersion: 5 }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the reported Active identity is inconsistent", () => {
    expect(() =>
      normalizeNotificationActivation(
        activationPayload({
          activeConfiguration: {
            revisionId: "rev-draft",
            version: 6,
            revisionSequence: 4,
            status: "active",
          },
        }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeNotificationActivation(
        activationPayload({ activeConfiguration: null }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the activated definition is missing", () => {
    expect(() =>
      normalizeNotificationActivation(
        activationPayload({ webhook: null }),
        REQUESTED,
      ),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("webhook definition mutation result", () => {
  const DRAFT = { revisionId: "rev-draft", expectedVersion: 4 };

  function mutationPayload(
    overrides: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      revisionId: "rev-draft",
      version: 5,
      status: "draft",
      webhook: { id: "created", enabled: false },
      ...overrides,
    };
  }

  it("normalizes a created definition bound to the exact submitted identity", () => {
    const model = normalizeWebhookDefinitionMutation(mutationPayload(), {
      ...DRAFT,
      documentField: "webhook",
      expectedId: "created",
      copySourceId: null,
      copyNewId: null,
      expectedEnabled: null,
    });
    expect(model).toEqual({
      revisionId: "rev-draft",
      version: 5,
      id: "created",
    });
  });

  it("normalizes a saved Draft bound to the edited identity and successor version", () => {
    const model = normalizeWebhookDefinitionMutation(
      mutationPayload({ webhook: { id: "ops" } }),
      {
        ...DRAFT,
        documentField: "webhook",
        expectedId: "ops",
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: null,
      },
    );
    expect(model.id).toBe("ops");
    expect(model.version).toBe(5);
  });

  it("normalizes an unpinned copy bound to the derived source family", () => {
    const model = normalizeWebhookDefinitionMutation(
      mutationPayload({
        object: { id: "ops-copy-2", enabled: false },
        webhook: undefined,
      }),
      {
        ...DRAFT,
        documentField: "object",
        expectedId: null,
        copySourceId: "ops",
        copyNewId: null,
        expectedEnabled: false,
      },
    );
    expect(model.id).toBe("ops-copy-2");
  });

  it("rejects a same-prefix identity that is not the exact derived copy", () => {
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({
          object: { id: "ops-malicious", enabled: false },
          webhook: undefined,
        }),
        {
          ...DRAFT,
          documentField: "object",
          expectedId: null,
          copySourceId: "ops",
          copyNewId: "ops-copy",
          expectedEnabled: false,
        },
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("normalizes a pinned copy bound to the exact requested new identity", () => {
    const model = normalizeWebhookDefinitionMutation(
      mutationPayload({
        object: { id: "pinned-copy", enabled: false },
        webhook: undefined,
      }),
      {
        ...DRAFT,
        documentField: "object",
        expectedId: null,
        copySourceId: "ops",
        copyNewId: "pinned-copy",
        expectedEnabled: false,
      },
    );
    expect(model.id).toBe("pinned-copy");
  });

  it("normalizes an exact enable and disable toggle bound to the toggled identity", () => {
    const enable = normalizeWebhookDefinitionMutation(
      mutationPayload({
        object: { id: "ops", enabled: true },
        webhook: undefined,
      }),
      {
        ...DRAFT,
        documentField: "object",
        expectedId: "ops",
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: true,
      },
    );
    expect(enable.id).toBe("ops");
    const disable = normalizeWebhookDefinitionMutation(
      mutationPayload({
        object: { id: "ops", enabled: false },
        webhook: undefined,
      }),
      {
        ...DRAFT,
        documentField: "object",
        expectedId: "ops",
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: false,
      },
    );
    expect(disable.id).toBe("ops");
  });

  it("fails closed when the response answers another revision", () => {
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ revisionId: "rev-other" }),
        {
          ...DRAFT,
          documentField: "webhook",
          expectedId: "created",
          copySourceId: null,
          copyNewId: null,
          expectedEnabled: null,
        },
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the version is not the submitted mutation's successor", () => {
    const binding = {
      ...DRAFT,
      documentField: "webhook" as const,
      expectedId: "created",
      copySourceId: null,
      copyNewId: null,
      expectedEnabled: null,
    };
    // The submitted version itself: the mutation never stored.
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ version: 4 }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
    // A version that skips ahead of the one-shot successor bump.
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ version: 6 }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ version: null }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the response carries no changed definition", () => {
    expect(() =>
      normalizeWebhookDefinitionMutation(mutationPayload({ webhook: null }), {
        ...DRAFT,
        documentField: "webhook",
        expectedId: "created",
        copySourceId: null,
        copyNewId: null,
        expectedEnabled: null,
      }),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ webhook: undefined }),
        {
          ...DRAFT,
          documentField: "webhook",
          expectedId: "created",
          copySourceId: null,
          copyNewId: null,
          expectedEnabled: null,
        },
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ webhook: "created-webhook" }),
        {
          ...DRAFT,
          documentField: "webhook",
          expectedId: "created",
          copySourceId: null,
          copyNewId: null,
          expectedEnabled: null,
        },
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the response answers another or unsafe identity", () => {
    const binding = {
      ...DRAFT,
      documentField: "webhook" as const,
      expectedId: "created",
      copySourceId: null,
      copyNewId: null,
      expectedEnabled: null,
    };
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ webhook: { id: "another-webhook" } }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ webhook: { id: "../escape" } }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ webhook: { enabled: false } }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when a copy answers for the source or an unrelated definition", () => {
    const binding = {
      ...DRAFT,
      documentField: "object" as const,
      expectedId: null,
      copySourceId: "ops",
      copyNewId: null,
      expectedEnabled: false,
    };
    // The copied-from source itself is not a new definition.
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({
          object: { id: "ops", enabled: false },
          webhook: undefined,
        }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
    // An unrelated identity is not derived from this copy mutation.
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({
          object: { id: "another-webhook", enabled: false },
          webhook: undefined,
        }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
    // A pinned copy must answer for the exact requested new identity.
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({
          object: { id: "ops-copy", enabled: false },
          webhook: undefined,
        }),
        { ...binding, copyNewId: "pinned-copy" },
      ),
    ).toThrow(NotificationNormalizationError);
    // The managed copy stores a disabled Draft definition.
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({
          object: { id: "ops-copy", enabled: true },
          webhook: undefined,
        }),
        binding,
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when a toggle contradicts the requested enabled state", () => {
    const enable = {
      ...DRAFT,
      documentField: "object" as const,
      expectedId: "ops",
      copySourceId: null,
      copyNewId: null,
      expectedEnabled: true,
    };
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({
          object: { id: "ops", enabled: false },
          webhook: undefined,
        }),
        enable,
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({ object: { id: "ops" }, webhook: undefined }),
        enable,
      ),
    ).toThrow(NotificationNormalizationError);
    const disable = { ...enable, expectedEnabled: false };
    expect(() =>
      normalizeWebhookDefinitionMutation(
        mutationPayload({
          object: { id: "ops", enabled: true },
          webhook: undefined,
        }),
        disable,
      ),
    ).toThrow(NotificationNormalizationError);
  });
});

describe("notification recovery result", () => {
  function recoveryPayload(
    overrides: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      action: "requeue-dead-letter",
      outcome: "success",
      deliveryId: "delivery-1",
      previousStatus: "dead-letter",
      status: "pending",
      attempts: 0,
      durableState: "dead_letter_requeued_same_identity",
      sideEffects: "delivery_queue_state_only_no_new_row_no_media_change",
      retrySafe: true,
      atLeastOnce: "receivers must tolerate duplicates",
      nextAction: "refresh this delivery",
      ...overrides,
    };
  }

  it("normalizes a requeue bound to the exact delivery and fence", () => {
    const model = normalizeNotificationRecoveryResult(recoveryPayload(), {
      deliveryId: "delivery-1",
      action: "requeue-dead-letter",
      previousStatus: "dead-letter",
    });
    expect(model.status).toBe("pending");
    expect(model.deliveryId).toBe("delivery-1");
  });

  it("normalizes a stale resolution bound to the exact delivery and fence", () => {
    const model = normalizeNotificationRecoveryResult(
      recoveryPayload({
        action: "resolve-stale",
        previousStatus: "delivering",
        durableState: "stale_delivery_returned_to_queue_same_identity",
      }),
      {
        deliveryId: "delivery-1",
        action: "resolve-stale",
        previousStatus: "delivering",
      },
    );
    expect(model.action).toBe("resolve-stale");
  });

  it("fails closed when the result names another delivery", () => {
    expect(() =>
      normalizeNotificationRecoveryResult(
        recoveryPayload({ deliveryId: "delivery-2" }),
        {
          deliveryId: "delivery-1",
          action: "requeue-dead-letter",
          previousStatus: "dead-letter",
        },
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed when the result names another action", () => {
    expect(() =>
      normalizeNotificationRecoveryResult(
        recoveryPayload({ action: "resolve-stale" }),
        {
          deliveryId: "delivery-1",
          action: "requeue-dead-letter",
          previousStatus: "dead-letter",
        },
      ),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed on a transition inconsistent with the action", () => {
    expect(() =>
      normalizeNotificationRecoveryResult(
        recoveryPayload({ previousStatus: "delivering" }),
        {
          deliveryId: "delivery-1",
          action: "requeue-dead-letter",
          previousStatus: "dead-letter",
        },
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeNotificationRecoveryResult(
        recoveryPayload({
          action: "resolve-stale",
          previousStatus: "dead-letter",
          durableState: "stale_delivery_returned_to_queue_same_identity",
        }),
        {
          deliveryId: "delivery-1",
          action: "resolve-stale",
          previousStatus: "delivering",
        },
      ),
    ).toThrow(NotificationNormalizationError);
    expect(() =>
      normalizeNotificationRecoveryResult(
        recoveryPayload({ status: "retry" }),
        {
          deliveryId: "delivery-1",
          action: "requeue-dead-letter",
          previousStatus: "dead-letter",
        },
      ),
    ).toThrow(NotificationNormalizationError);
  });
});
