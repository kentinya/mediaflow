import { describe, expect, it } from "vitest";
import {
  normalizeNotificationAction,
  normalizeNotificationActiveConfiguration,
  normalizeNotificationDefinitionsPage,
  normalizeNotificationDeliveryDetail,
  normalizeNotificationDraftState,
  normalizeWebhookDefinition,
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
  it("normalizes a bounded success outcome", () => {
    const result = normalizeWebhookTestResult({
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
    });
    expect(result.outcome).toBe("success");
    expect(result.category).toBe("http_204");
    expect(result.webhookId).toBe("ops");
  });

  it("fails closed when the outcome carries a revision digest", () => {
    expect(() =>
      normalizeWebhookTestResult({
        webhook: { id: "ops" },
        revision: {
          revisionId: "rev-draft",
          version: 4,
          status: "draft",
          digest: "sha256:deadbeef",
        },
        outcome: "success",
        category: "http_204",
        responseStatus: 204,
        message: "ok",
        durableState: "no_delivery_created_no_configuration_change",
        retrySafe: true,
        nextAction: "none",
      }),
    ).toThrow(NotificationNormalizationError);
  });

  it("fails closed on an unknown outcome category", () => {
    expect(() =>
      normalizeWebhookTestResult({
        webhook: { id: "ops" },
        revision: { revisionId: "rev-draft", version: 4, status: "draft" },
        outcome: "failure",
        category: "stack_trace",
        responseStatus: null,
        message: "boom",
        durableState: "no_delivery_created_no_configuration_change",
        retrySafe: true,
        nextAction: "none",
      }),
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
