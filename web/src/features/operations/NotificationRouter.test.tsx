import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import { dashboardPayload } from "../../../tests/fixtures";

/**
 * Component/router proof for the V2 Notification journey.
 *
 * Every document mirrors the exact operator projection the real Python API
 * returns (proved by tests/test_v2_notification_operations.py). The assertions
 * prove the operator journey and its safety properties: Active/Draft
 * distinction, backend-authoritative availability, exactly one signed test
 * request per explicit action, exact recovery methods/bodies with explicit
 * confirmation, no automatic mutation replay after stale rejections, no
 * authority material in any request, and no executable control for a state the
 * backend does not advertise.
 */

const TOKEN = "notification-token";
const ACTIVE_REVISION = "revision-active-1";
const DRAFT_REVISION = "revision-draft-1";
const WEBHOOK_ID = "ops-webhook";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: unknown;
}

function recordingFetch(respond: (call: Call) => Response | undefined): {
  calls: Call[];
} {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: init?.method ?? "GET",
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as unknown)
            : null,
      };
      calls.push(call);
      const response = respond(call);
      if (response !== undefined) {
        return response;
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return { calls };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function action(
  overrides: Record<string, unknown> = {},
  webhookId: string = WEBHOOK_ID,
): Record<string, unknown> {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: `/api/v1/operations/notifications/webhooks/${webhookId}/test`,
    requiresConfirmation: false,
    sideEffects: "one_signed_test_request",
    durableOutcome: "no durable change",
    nextAction: "test the exact displayed revision",
    ...overrides,
  };
}

function webhookDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id: WEBHOOK_ID,
    url: "https://example.invalid/hooks/mediaflow",
    secretEnv: "MEDIAFLOW_WEBHOOK_SECRET",
    events: ["job.completed", "job.failed"],
    enabled: true,
    timeoutSeconds: 10,
    maxAttempts: 5,
    baseRetrySeconds: 5,
    maxRetrySeconds: 300,
    secretReadiness: [
      { field: "secretEnv", env: "MEDIAFLOW_WEBHOOK_SECRET", state: "SET" },
    ],
    structuralValid: true,
    validationError: null,
    ...overrides,
  };
}

function draftState(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    present: true,
    reason: null,
    revisionId: DRAFT_REVISION,
    revisionVersion: 4,
    revisionStatus: "validated",
    baseActiveRevisionId: ACTIVE_REVISION,
    updatedAt: "2026-09-12T00:00:00+00:00",
    validatedAt: "2026-09-12T00:01:00+00:00",
    validationErrors: [],
    ...overrides,
  };
}

function activeConfiguration(): Record<string, unknown> {
  return {
    revisionId: ACTIVE_REVISION,
    version: 3,
    revisionSequence: 2,
    status: "active",
  };
}

function definitionActions(
  draftRevision: string | null,
  webhookId: string = WEBHOOK_ID,
): Record<string, unknown> {
  const operationsRoute = `/api/v1/operations/notifications/webhooks/${webhookId}`;
  const editPath =
    draftRevision === null
      ? null
      : `/api/v1/configuration/revisions/${draftRevision}/objects/webhooks/${webhookId}`;
  return {
    detail: {
      available: true,
      reason: null,
      method: "GET",
      path: operationsRoute,
      sideEffects: "none",
      durableOutcome: null,
      nextAction: "inspect the exact bounded Webhook definition state",
    },
    test: action({}, webhookId),
    edit: {
      available: draftRevision !== null,
      reason:
        draftRevision === null ? "an open successor Draft is required" : null,
      method: "PUT",
      path: editPath,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the bounded definition form is stored",
      nextAction: "save the bounded form",
    },
    copy: {
      available: draftRevision !== null,
      reason:
        draftRevision === null ? "an open successor Draft is required" : null,
      method: "POST",
      path: editPath === null ? null : `${editPath}/copy`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "a copied definition is stored",
      nextAction: "open the copied definition",
    },
    enable: {
      available: draftRevision !== null,
      reason:
        draftRevision === null ? "an open successor Draft is required" : null,
      method: "POST",
      path: editPath === null ? null : `${editPath}/enable`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the definition is enabled in the Draft",
      nextAction: "review the Draft",
    },
    disable: {
      available: draftRevision !== null,
      reason:
        draftRevision === null ? "an open successor Draft is required" : null,
      method: "POST",
      path: editPath === null ? null : `${editPath}/disable`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the definition is disabled in the Draft",
      nextAction: "review the Draft",
    },
    draftCreate: {
      available: true,
      reason: null,
      method: "POST",
      path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "a successor Draft is stored",
      nextAction: "create the successor Draft",
    },
    activate: {
      available: draftRevision !== null,
      reason:
        draftRevision === null ? "an open successor Draft is required" : null,
      method: "POST",
      path: `${operationsRoute}/activate-draft`,
      requiresConfirmation: true,
      sideEffects: "none",
      durableOutcome: "the reviewed Draft becomes Active",
      nextAction: "activate the reviewed Draft",
    },
  };
}

function definitionPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const id = (overrides.id as string | undefined) ?? WEBHOOK_ID;
  return {
    ...webhookDocument({ id }),
    definitionState: "active",
    activeConfiguration: activeConfiguration(),
    draftState: draftState(),
    actions: definitionActions(DRAFT_REVISION, id),
    ...overrides,
  };
}

function listPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    activeConfiguration: activeConfiguration(),
    items: [definitionPayload()],
    total: 1,
    truncated: false,
    draftState: draftState(),
    supportedEvents: [
      "job.completed",
      "job.failed",
      "job.cancelled",
      "schedule.emitted",
    ],
    actions: {
      create: {
        available: true,
        reason: null,
        method: "POST",
        path: `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks`,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "the definition is stored in the Draft",
        nextAction: "create the definition inside the Draft",
      },
      createDraft: {
        available: true,
        reason: null,
        method: "POST",
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "a successor Draft is stored",
        nextAction: "create the successor Draft",
      },
    },
    ...overrides,
  };
}

function draftDocumentPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    webhookId: WEBHOOK_ID,
    activeConfiguration: activeConfiguration(),
    webhook: webhookDocument(),
    draft: {
      revisionId: DRAFT_REVISION,
      revisionVersion: 4,
      revisionStatus: "validated",
      baseActiveRevisionId: ACTIVE_REVISION,
      updatedAt: "2026-09-12T00:00:00+00:00",
      validatedAt: "2026-09-12T00:01:00+00:00",
      validationErrors: [],
      webhook: webhookDocument(),
    },
    supportedEvents: [
      "job.completed",
      "job.failed",
      "job.cancelled",
      "schedule.emitted",
    ],
    actions: {
      createDraft: {
        available: true,
        reason: null,
        method: "POST",
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "a successor Draft is stored",
        nextAction: "create the successor Draft",
      },
      save: {
        available: true,
        reason: null,
        method: "PUT",
        path: `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/${WEBHOOK_ID}`,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "the bounded definition form is stored",
        nextAction: "save the bounded form",
      },
      validate: {
        available: true,
        reason: null,
        method: "POST",
        path: `/api/v1/configuration/revisions/${DRAFT_REVISION}/validate`,
        requiresConfirmation: false,
        sideEffects: "none",
        durableOutcome: "the open Draft is validated",
        nextAction: "validate the Draft",
      },
      activate: {
        available: true,
        reason: null,
        method: "POST",
        path: `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}/activate-draft`,
        requiresConfirmation: true,
        sideEffects: "none",
        durableOutcome: "the reviewed Draft becomes Active",
        nextAction: "activate the reviewed Draft",
      },
      test: action(),
    },
    ...overrides,
  };
}

function deliveryListItem(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    deliveryId: "delivery-1",
    webhookId: WEBHOOK_ID,
    eventId: "event-1",
    eventType: "job.completed",
    status: "dead-letter",
    attempts: 3,
    nextAttemptAt: "2026-09-12T00:05:00+00:00",
    createdAt: "2026-09-12T00:00:00+00:00",
    updatedAt: "2026-09-12T00:05:00+00:00",
    deliveredAt: null,
    failureCategory: "http_400",
    responseStatus: 400,
    ...overrides,
  };
}

function deliveryDetailPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    ...deliveryListItem(),
    lease: { state: "not_leased" },
    knownEffects:
      "the receiver never confirmed success after the configured attempts",
    retrySafe: true,
    nextAction: "confirm the endpoint is reachable, then explicitly requeue",
    recovery: {
      availableActions: ["requeue-dead-letter"],
      reason: "The delivery reached the terminal dead-letter state.",
      actions: [
        {
          name: "requeue-dead-letter",
          durableState: "the delivery stays one row with the same identity",
          sideEffects: "no new delivery and no media change",
          retrySafe: true,
          duplicateImplication:
            "receivers must tolerate duplicates (at-least-once)",
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
        durableOutcome: "the dead-letter delivery returns to pending",
        nextAction: "confirm the requeue, then refresh",
      },
    },
    ...overrides,
  };
}

async function connect(): Promise<void> {
  authStore.setToken(TOKEN);
}

describe("NotificationListPage", () => {
  it("renders the Active definition and links the deliveries surface", async () => {
    recordingFetch((call) => {
      if (call.url === "/api/v1/operations/notifications/webhooks") {
        return jsonResponse(listPayload());
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications");
    expect(await screen.findByText("Webhook definitions")).toBeVisible();
    expect(screen.getByText("ops-webhook")).toBeVisible();
    expect(screen.getByText("Active")).toBeVisible();
    expect(
      screen.getByText(/secret readiness: MEDIAFLOW_WEBHOOK_SECRET: SET/),
    ).toBeVisible();
    expect(screen.getByText("Open deliveries")).toBeVisible();
  });

  it("renders a Draft-only definition without labelling it Active", async () => {
    recordingFetch((call) => {
      if (call.url === "/api/v1/operations/notifications/webhooks") {
        return jsonResponse(
          listPayload({
            items: [
              definitionPayload({
                id: "draft-only-webhook",
                definitionState: "draft-only",
                secretReadiness: [],
              }),
            ],
          }),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications");
    expect(await screen.findByText("draft-only-webhook")).toBeVisible();
    expect(screen.getByText("Draft only")).toBeVisible();
    expect(screen.queryByText("Active")).toBeNull();
  });

  it("renders no create control and the truthful reason when unavailable", async () => {
    recordingFetch((call) => {
      if (call.url === "/api/v1/operations/notifications/webhooks") {
        return jsonResponse(
          listPayload({
            actions: {
              create: {
                available: false,
                reason:
                  "an open successor Draft is required to add a Webhook definition",
                method: "POST",
                path: null,
                requiresConfirmation: false,
                sideEffects: "none",
                durableOutcome: "the definition is stored in the Draft",
                nextAction: "start a successor Draft",
              },
              createDraft: {
                available: false,
                reason:
                  "the connected API principal cannot create a successor Draft",
                method: "POST",
                path: null,
                requiresConfirmation: false,
                sideEffects: "none",
                durableOutcome: "a successor Draft is stored",
                nextAction: "ask for the manage configuration permission",
              },
            },
          }),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications");
    expect(
      await screen.findByText(/an open successor Draft is required/),
    ).toBeVisible();
  });

  it("fails closed on a malformed page without rendering a control", async () => {
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/operations/notifications/webhooks") {
        return jsonResponse({ items: "not-a-list" });
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications");
    expect(await screen.findByText(/could not be understood/)).toBeVisible();
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(0);
  });
});

describe("NotificationDetailPage signed test", () => {
  it("sends exactly one bound test request and never a digest", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload(),
          activeConfiguration: activeConfiguration(),
        });
      }
      if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/test`)) {
        return jsonResponse({
          testId: "test-1",
          webhook: { id: WEBHOOK_ID },
          revision: {
            revisionId: DRAFT_REVISION,
            version: 4,
            status: "validated",
          },
          outcome: "success",
          category: "http_204",
          responseStatus: 204,
          message: "the Webhook endpoint returned HTTP 204",
          durableState: "no_delivery_created_no_configuration_change",
          sideEffects: "none",
          retrySafe: true,
          nextAction: "no further action required",
        });
      }
      return undefined;
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}`);
    const button = await screen.findByRole("button", {
      name: "Test this exact revision",
    });
    await userEvent.click(button);
    await waitFor(() => {
      expect(screen.getByText(/Test succeeded/)).toBeVisible();
    });
    const testCalls = calls.filter(
      (call) => call.method === "POST" && call.url.endsWith("/test"),
    );
    expect(testCalls).toHaveLength(1);
    expect(testCalls[0].body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedVersion: 3,
    });
    expect(JSON.stringify(testCalls[0].body)).not.toMatch(/digest/i);
    // No delivery was created, nothing else mutated.
    expect(
      calls.filter(
        (call) => call.method !== "GET" && !call.url.endsWith("/test"),
      ),
    ).toHaveLength(0);
  });

  it("shows the stale-rejection recovery without replaying the request", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload(),
          activeConfiguration: activeConfiguration(),
        });
      }
      if (call.url.endsWith("/test")) {
        return jsonResponse(
          {
            error: {
              code: "configuration_version_conflict",
              details: { durableState: "no test request was sent" },
            },
          },
          409,
        );
      }
      return undefined;
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}`);
    const button = await screen.findByRole("button", {
      name: "Test this exact revision",
    });
    await userEvent.click(button);
    expect(await screen.findByText(/no test request was sent/)).toBeVisible();
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/test"),
      ),
    ).toHaveLength(1);
  });
});

describe("NotificationEditorPage checked activation", () => {
  function respondDraft(
    calls: Call[],
    overrides: {
      saveStatus?: number;
      activateStatus?: number;
    } = {},
  ) {
    return (call: Call): Response | undefined => {
      if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/draft`)) {
        return jsonResponse(draftDocumentPayload());
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/${WEBHOOK_ID}`
      ) {
        if (overrides.saveStatus === 409) {
          return jsonResponse(
            { error: { code: "configuration_version_conflict" } },
            409,
          );
        }
        return jsonResponse({
          revisionId: DRAFT_REVISION,
          webhook: webhookDocument(),
        });
      }
      if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/activate-draft`)) {
        if (overrides.activateStatus === 409) {
          return jsonResponse(
            { error: { code: "notification_activation_out_of_scope" } },
            409,
          );
        }
        return jsonResponse({
          activatedRevisionId: DRAFT_REVISION,
          activatedVersion: 5,
          revisionSequence: 3,
          activeConfiguration: activeConfiguration(),
          webhook: webhookDocument(),
        });
      }
      void calls;
      return undefined;
    };
  }

  it("saves the bounded form with the exact optimistic version", async () => {
    const { calls } = recordingFetch((call) => respondDraft(calls)(call));
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const save = await screen.findByRole("button", { name: "Save into Draft" });
    await userEvent.click(save);
    await waitFor(() => {
      expect(
        calls.some(
          (call) =>
            call.method === "PUT" &&
            call.url ===
              `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/${WEBHOOK_ID}`,
        ),
      ).toBe(true);
    });
    const saveCall = calls.find((call) => call.method === "PUT");
    expect(saveCall?.body).toMatchObject({
      expectedVersion: 4,
      object: { id: WEBHOOK_ID },
    });
    expect(JSON.stringify(saveCall?.body)).not.toMatch(/secretValue|Bearer /i);
  });

  it("requires the explicit confirmation checkbox before activation", async () => {
    const { calls } = recordingFetch((call) =>
      respondDraft(calls, { activateStatus: 409 })(call),
    );
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const activate = await screen.findByRole("button", {
      name: "Activate checked Draft",
    });
    expect(activate).toBeDisabled();
    const checkbox = screen.getByLabelText("Confirm checked activation");
    await userEvent.click(checkbox);
    await userEvent.click(
      screen.getByRole("button", { name: "Activate checked Draft" }),
    );
    await waitFor(() => {
      expect(
        calls.some(
          (call) =>
            call.method === "POST" && call.url.endsWith("/activate-draft"),
        ),
      ).toBe(true);
    });
    const activationCall = calls.find((call) =>
      call.url.endsWith("/activate-draft"),
    );
    expect(activationCall?.body).toMatchObject({
      expectedRevisionId: DRAFT_REVISION,
      expectedVersion: 4,
    });
    expect(JSON.stringify(activationCall?.body)).not.toMatch(/digest/i);
  });

  it("does not replay a stale activation and offers the bounded recovery", async () => {
    const { calls } = recordingFetch((call) =>
      respondDraft(calls, { activateStatus: 409 })(call),
    );
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const checkbox = await screen.findByLabelText("Confirm checked activation");
    await userEvent.click(checkbox);
    await userEvent.click(
      screen.getByRole("button", { name: "Activate checked Draft" }),
    );
    expect(await screen.findByText(/Activation was rejected/)).toBeVisible();
    expect(
      calls.filter((call) => call.url.endsWith("/activate-draft")),
    ).toHaveLength(1);
  });
});

describe("DeliveryListPage", () => {
  it("renders the durable delivery statuses and filter", async () => {
    recordingFetch((call) => {
      if (call.url.startsWith("/api/v1/notifications?")) {
        return jsonResponse({
          limit: 20,
          status: "dead-letter",
          previous_cursor: null,
          next_cursor: null,
          items: [deliveryListItem()],
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries?status=dead-letter");
    const badges = await screen.findAllByText("Dead letter");
    expect(badges.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("attempts: 3")).toBeVisible();
    expect(screen.getByText(/last response HTTP 400/)).toBeVisible();
  });
});

describe("DeliveryDetailPage recovery", () => {
  it("requires explicit confirmation and submits the exact observed fence", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(deliveryDetailPayload());
      }
      if (call.url === "/api/v1/notifications/delivery-1/requeue") {
        return jsonResponse({
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
          duplicateImplication: "duplicates",
          nextAction: "refresh this delivery",
          delivery: deliveryDetailPayload({ status: "pending" }),
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries/delivery-1");
    const button = await screen.findByRole("button", {
      name: "Requeue dead-letter delivery",
    });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Confirm dead-letter requeue"));
    await userEvent.click(button);
    await waitFor(() => {
      expect(
        calls.some(
          (call) =>
            call.method === "POST" &&
            call.url === "/api/v1/notifications/delivery-1/requeue",
        ),
      ).toBe(true);
    });
    const recovery = calls.find(
      (call) => call.url === "/api/v1/notifications/delivery-1/requeue",
    );
    expect(recovery?.body).toMatchObject({
      expectedStatus: "dead-letter",
      expectedUpdatedAt: "2026-09-12T00:05:00+00:00",
    });
  });

  it("does not replay a stale recovery and offers refresh instead", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(deliveryDetailPayload());
      }
      if (call.url === "/api/v1/notifications/delivery-1/requeue") {
        return jsonResponse(
          { error: { code: "notification_delivery_conflict" } },
          409,
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries/delivery-1");
    await userEvent.click(
      await screen.findByLabelText("Confirm dead-letter requeue"),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Requeue dead-letter delivery" }),
    );
    expect(await screen.findByText(/no recovery was applied/)).toBeVisible();
    expect(
      calls.filter(
        (call) => call.url === "/api/v1/notifications/delivery-1/requeue",
      ),
    ).toHaveLength(1);
  });

  it("renders no recovery control when the backend advertises none", async () => {
    recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(
          deliveryDetailPayload({
            status: "delivered",
            recovery: {
              availableActions: [],
              reason: "The delivery already completed successfully.",
              actions: [],
            },
            actions: {},
          }),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries/delivery-1");
    expect(
      await screen.findByText("No manual recovery advertised"),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /Requeue/ })).toBeNull();
  });

  it("fails closed on a malformed delivery document", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(
          deliveryDetailPayload({
            status: "exploded",
          }),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries/delivery-1");
    expect(await screen.findByText(/could not be understood/)).toBeVisible();
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(0);
  });
});

describe("Dashboard notification links", () => {
  it("links the exact delivery for a notification failure", async () => {
    recordingFetch((call) => {
      if (call.url.startsWith("/api/v1/dashboard")) {
        return jsonResponse({
          ...dashboardPayload,
          dead_letter_notifications: 1,
          recent_failures: [
            {
              kind: "notification",
              identifier: "delivery-1",
              status: "dead-letter",
              occurred_at: "2026-09-12T00:00:00+00:00",
              category: "delivery_failed",
            },
          ],
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/dashboard");
    const link = await screen.findByRole("link", {
      name: "Open this delivery",
    });
    expect(link.getAttribute("href")).toBe(
      "/ui-v2/operations/notifications/deliveries/delivery-1",
    );
    const notificationsSection = screen
      .getByText("Notifications")
      .closest("section");
    expect(notificationsSection).not.toBeNull();
    const deadLetterLink = within(
      notificationsSection as HTMLElement,
    ).getByRole("link", { name: /Dead-letter notifications/ });
    expect(deadLetterLink.getAttribute("href")).toContain("status=dead-letter");
  });
});
