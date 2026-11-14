import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

/**
 * Component/router proof for the V2 Notification journey after
 * PATCH-20261114-3.
 *
 * Every document mirrors the exact operator projection the real Python API
 * returns (proved by tests/test_v2_notification_operations.py). The assertions
 * prove the operator journey and its safety properties: Active/Draft
 * distinction, Chinese presentation, backend-authoritative availability,
 * exactly one signed test request per explicit action, exact recovery
 * methods/bodies with explicit confirmation, no automatic mutation replay
 * after stale rejections, no authority material in any request, unsaved-input
 * separation and no executable control for a state the backend does not
 * advertise.
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

function recordingFetch(
  respond: (call: Call) => Response | Promise<Response> | undefined = () =>
    undefined,
): { calls: Call[] } {
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
      const response = await respond(call);
      if (response !== undefined) {
        return response;
      }
      // The Notification list is the persistent background of every card, so
      // every journey reads it. A default healthy page keeps tests focused on
      // the card under test; individual tests override their own reads.
      if (
        call.method === "GET" &&
        call.url === "/api/v1/operations/notifications/webhooks"
      ) {
        return jsonResponse(listPayload());
      }
      if (
        call.method === "GET" &&
        call.url.startsWith("/api/v1/notifications?")
      ) {
        return jsonResponse(deliveriesPayload());
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
    events: ["task.completed", "task.failed"],
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
  const draftOverrides =
    (overrides.draftState as Record<string, unknown> | undefined) ?? {};
  const draftRevision =
    draftOverrides.present === false ? null : DRAFT_REVISION;
  return {
    ...webhookDocument({ id }),
    definitionState: "active",
    activeConfiguration: activeConfiguration(),
    draftState: draftState(),
    actions: definitionActions(draftRevision, id),
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
      "task.completed",
      "task.failed",
      "task.cancelled",
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
      "task.completed",
      "task.failed",
      "task.cancelled",
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

function deniedDraftActions(): Record<string, unknown> {
  const reason =
    "the connected API principal cannot manage Webhook Definitions (required permission: manage_configuration)";
  return {
    createDraft: {
      available: false,
      reason,
      method: "POST",
      path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "a successor Draft is stored",
      nextAction: "ask for permission",
    },
    save: {
      available: false,
      reason,
      method: "PUT",
      path: `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/${WEBHOOK_ID}`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the bounded definition form is stored",
      nextAction: "ask for permission",
    },
    validate: {
      available: false,
      reason,
      method: "POST",
      path: `/api/v1/configuration/revisions/${DRAFT_REVISION}/validate`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the open Draft is validated",
      nextAction: "ask for permission",
    },
    activate: {
      available: false,
      reason,
      method: "POST",
      path: `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}/activate-draft`,
      requiresConfirmation: true,
      sideEffects: "none",
      durableOutcome: "the reviewed Draft becomes Active",
      nextAction: "ask for permission",
    },
    test: action({ available: false, reason }),
  };
}

function deliveryListItem(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    deliveryId: "delivery-1",
    webhookId: WEBHOOK_ID,
    eventId: "event-1",
    eventType: "task.completed",
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

function deliveriesPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    limit: 20,
    status: "dead-letter",
    previous_cursor: null,
    next_cursor: null,
    items: [deliveryListItem()],
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

/** The real API's document after a dead letter was requeued to pending. */
function pendingDeliveryDetailPayload(): Record<string, unknown> {
  return deliveryDetailPayload({
    status: "pending",
    attempts: 0,
    nextAttemptAt: "2026-09-12T00:06:00+00:00",
    updatedAt: "2026-09-12T00:05:30+00:00",
    deliveredAt: null,
    failureCategory: null,
    responseStatus: null,
    knownEffects: "No outbound request for this delivery has completed.",
    nextAction:
      "No manual action required; the notification worker will claim this delivery when it is due.",
    recovery: {
      availableActions: [],
      reason: "This delivery is pending automatic delivery.",
      actions: [],
    },
    actions: {},
  });
}

async function connect(): Promise<void> {
  authStore.setToken(TOKEN);
}

async function dialog(): Promise<HTMLElement> {
  return screen.findByRole("dialog");
}

describe("NotificationListPage", () => {
  it("presents the Active definition, readable events and the deliveries surface", async () => {
    recordingFetch();
    await connect();
    renderApp("/ui-v2/operations/notifications");
    expect(await screen.findByText("Webhook 定义")).toBeVisible();
    expect(screen.getByText("ops-webhook")).toBeVisible();
    expect(screen.getByText("已生效")).toBeVisible();
    expect(screen.getByText("已启用")).toBeVisible();
    expect(screen.getByText("密钥引用：已就绪")).toBeVisible();
    expect(
      screen.getByText("https://example.invalid/hooks/mediaflow"),
    ).toBeVisible();
    expect(screen.getByText("任务完成")).toBeVisible();
    expect(screen.getByRole("link", { name: "查看投递记录" })).toBeVisible();
    expect(screen.getByRole("link", { name: "新建 Webhook" })).toBeVisible();
  });

  it("renders a Draft-only definition without presenting it as Active", async () => {
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
    const name = await screen.findByText("draft-only-webhook");
    const card = name.closest("li");
    expect(card).not.toBeNull();
    const view = within(card as HTMLElement);
    expect(view.getByText("仅草稿")).toBeVisible();
    expect(view.queryByText("已生效")).toBeNull();
  });

  it("does not offer a creatable link without a Draft and explains the next step", async () => {
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
          }),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications");
    expect(await screen.findByText(/后继草稿才能继续/)).toBeVisible();
    expect(screen.queryByRole("link", { name: "新建 Webhook" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "新建 Webhook（不可用）" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "创建后继草稿" })).toBeEnabled();
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

describe("NotificationNewPage", () => {
  it("does not render a fillable form without an editable Draft", async () => {
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/operations/notifications/webhooks") {
        return jsonResponse(
          listPayload({
            draftState: draftState({
              present: false,
              reason: "no open successor Draft exists",
              revisionId: null,
              revisionVersion: null,
              revisionStatus: null,
              baseActiveRevisionId: null,
              updatedAt: null,
              validatedAt: null,
              validationErrors: [],
            }),
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
          }),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/webhooks/new");
    const view = within(await dialog());
    expect(await view.findByText("当前不能新建 Webhook")).toBeVisible();
    expect(view.queryByLabelText("标识符")).toBeNull();
    expect(view.queryByRole("button", { name: "保存到草稿" })).toBeNull();
    expect(view.getByRole("button", { name: "创建后继草稿" })).toBeEnabled();
    const read = view.getByRole("button", { name: "读取最新草稿状态" });
    expect(read).toBeEnabled();
    const readsBefore = calls.filter(
      (call) =>
        call.method === "GET" &&
        call.url === "/api/v1/operations/notifications/webhooks",
    ).length;
    await userEvent.click(read);
    await waitFor(() => {
      expect(
        calls.filter(
          (call) =>
            call.method === "GET" &&
            call.url === "/api/v1/operations/notifications/webhooks",
        ).length,
      ).toBe(readsBefore + 1);
    });
    expect(view.queryByLabelText("标识符")).toBeNull();
  });
});

describe("NotificationNewPage", () => {
  it("keeps the form and reports an unknown create result without replaying", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks`
      ) {
        throw new Error("network lost");
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp(
      "/ui-v2/operations/notifications/webhooks/new",
    );
    const view = within(await dialog());
    await userEvent.type(
      await view.findByLabelText("标识符"),
      "created-webhook",
    );
    await userEvent.type(
      view.getByLabelText("HTTPS 接收地址"),
      "https://example.invalid/hooks/created",
    );
    await userEvent.type(
      view.getByLabelText("密钥环境变量引用"),
      "MEDIAFLOW_WEBHOOK_SECRET",
    );
    await userEvent.click(view.getByRole("checkbox", { name: /任务完成/ }));
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    expect(await view.findByText(/命令结果未知/)).toBeVisible();
    expect(view.getByLabelText("标识符")).toHaveValue("created-webhook");
    expect(router.state.location.pathname).toBe(
      "/operations/notifications/webhooks/new",
    );
    expect(
      calls.filter(
        (call) =>
          call.method === "POST" &&
          call.url ===
            `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks`,
      ),
    ).toHaveLength(1);
  });

  it("locks the create form while the leaving save is in flight and shows the submitted value", async () => {
    const createdId = "created-webhook";
    const submittedUrl = "https://example.invalid/hooks/created";
    let releaseSave!: () => void;
    const saveGate = new Promise<void>((resolve) => {
      releaseSave = resolve;
    });
    const { calls } = recordingFetch((call) => {
      if (
        call.method === "POST" &&
        call.url ===
          `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks`
      ) {
        return saveGate.then(() =>
          jsonResponse({
            revisionId: DRAFT_REVISION,
            version: 5,
            webhook: webhookDocument({
              id: createdId,
              url: submittedUrl,
              events: ["task.completed"],
            }),
          }),
        );
      }
      if (
        call.method === "GET" &&
        call.url === `/api/v1/operations/notifications/webhooks/${createdId}`
      ) {
        return jsonResponse({
          webhook: definitionPayload({
            id: createdId,
            url: submittedUrl,
            events: ["task.completed"],
          }),
          activeConfiguration: activeConfiguration(),
        });
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp(
      "/ui-v2/operations/notifications/webhooks/new",
    );
    const view = within(await dialog());
    await userEvent.type(await view.findByLabelText("标识符"), createdId);
    const urlInput = view.getByLabelText("HTTPS 接收地址");
    await userEvent.type(urlInput, submittedUrl);
    await userEvent.type(
      view.getByLabelText("密钥环境变量引用"),
      "MEDIAFLOW_WEBHOOK_SECRET",
    );
    await userEvent.click(view.getByRole("checkbox", { name: /任务完成/ }));
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() => {
      expect(
        calls.filter(
          (call) =>
            call.method === "POST" &&
            call.url ===
              `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks`,
        ),
      ).toHaveLength(1);
    });

    // The success path leaves the card, so the exact submitted form must not
    // accept a newer value that the detail cannot show or that would be lost.
    expect(view.getByLabelText("标识符")).toBeDisabled();
    expect(urlInput).toBeDisabled();
    expect(view.getByLabelText("密钥环境变量引用")).toBeDisabled();
    expect(view.getByRole("checkbox", { name: /任务完成/ })).toBeDisabled();
    expect(
      view.getByRole("checkbox", { name: /启用这个 Webhook/ }),
    ).toBeDisabled();
    expect(view.getByLabelText("请求超时（秒）")).toBeDisabled();
    expect(view.getByLabelText("最大尝试次数")).toBeDisabled();
    expect(view.getByLabelText("基础重试间隔（秒）")).toBeDisabled();
    expect(view.getByLabelText("最大重试间隔（秒）")).toBeDisabled();
    await userEvent.type(urlInput, "-locked");
    expect(urlInput).toHaveValue(submittedUrl);

    releaseSave();
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        `/operations/notifications/webhooks/${createdId}`,
      );
    });
    expect(await screen.findByText("定义已保存到草稿")).toBeVisible();
    const detail = within(await dialog());
    expect(await detail.findByText(submittedUrl)).toBeVisible();
    expect(
      calls.filter(
        (call) =>
          call.method === "POST" &&
          call.url.endsWith(`/webhooks/${WEBHOOK_ID}/test`),
      ),
    ).toHaveLength(0);
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);
  });

  it("unlocks the create form and keeps the input after a rejected save", async () => {
    let releaseSave!: () => void;
    const saveGate = new Promise<void>((resolve) => {
      releaseSave = resolve;
    });
    const { calls } = recordingFetch((call) => {
      if (
        call.method === "POST" &&
        call.url ===
          `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks`
      ) {
        return saveGate.then(() =>
          jsonResponse(
            { error: { code: "notification_definition_conflict" } },
            409,
          ),
        );
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp(
      "/ui-v2/operations/notifications/webhooks/new",
    );
    const view = within(await dialog());
    await userEvent.type(
      await view.findByLabelText("标识符"),
      "conflicted-webhook",
    );
    const urlInput = view.getByLabelText("HTTPS 接收地址");
    await userEvent.type(urlInput, "https://example.invalid/hooks/conflicted");
    await userEvent.type(
      view.getByLabelText("密钥环境变量引用"),
      "MEDIAFLOW_WEBHOOK_SECRET",
    );
    await userEvent.click(view.getByRole("checkbox", { name: /任务完成/ }));
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() => {
      expect(
        calls.filter(
          (call) =>
            call.method === "POST" &&
            call.url ===
              `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks`,
        ),
      ).toHaveLength(1);
    });
    expect(urlInput).toBeDisabled();
    releaseSave();

    expect(await view.findByText(/定义没有写入/)).toBeVisible();
    expect(view.getByLabelText("标识符")).toBeEnabled();
    expect(view.getByLabelText("标识符")).toHaveValue("conflicted-webhook");
    expect(urlInput).toBeEnabled();
    expect(urlInput).toHaveValue("https://example.invalid/hooks/conflicted");
    expect(router.state.location.pathname).toBe(
      "/operations/notifications/webhooks/new",
    );
    expect(
      calls.filter(
        (call) =>
          call.method === "POST" &&
          call.url ===
            `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks`,
      ),
    ).toHaveLength(1);
  });
});

describe("NotificationDetailPage", () => {
  it("opens the definition card over the list and sends one bound test request", async () => {
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
            revisionId: ACTIVE_REVISION,
            version: 3,
            status: "active",
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
    const card = await dialog();
    const view = within(card);
    expect(await view.findByText("密钥引用：已就绪")).toBeVisible();
    await userEvent.click(
      await view.findByRole("button", { name: "发送签名测试" }),
    );
    expect(await view.findByText(/测试成功/)).toBeVisible();
    const testCalls = calls.filter(
      (call) => call.method === "POST" && call.url.endsWith("/test"),
    );
    expect(testCalls).toHaveLength(1);
    expect(testCalls[0].body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedVersion: 3,
    });
    expect(JSON.stringify(testCalls[0].body)).not.toMatch(/digest/i);
    expect(
      calls.filter(
        (call) => call.method !== "GET" && !call.url.endsWith("/test"),
      ),
    ).toHaveLength(0);
  });

  it("shows the stale-test recovery without replaying the request", async () => {
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
    const view = within(await dialog());
    await userEvent.click(
      await view.findByRole("button", { name: "发送签名测试" }),
    );
    expect(await view.findByText(/没有发送测试请求/)).toBeVisible();
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/test"),
      ),
    ).toHaveLength(1);
  });

  it("does not render a misbound test outcome as success", async () => {
    recordingFetch((call) => {
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
          testId: "test-9",
          webhook: { id: "another-webhook" },
          revision: {
            revisionId: ACTIVE_REVISION,
            version: 3,
            status: "active",
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
    const view = within(await dialog());
    await userEvent.click(
      await view.findByRole("button", { name: "发送签名测试" }),
    );
    expect(await view.findByText(/测试结果未知/)).toBeVisible();
    expect(view.queryByText(/测试成功/)).toBeNull();
  });

  it("keeps the list inert and closes a clean card with Escape", async () => {
    recordingFetch((call) => {
      if (
        call.url === `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload(),
          activeConfiguration: activeConfiguration(),
        });
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp(
      `/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}`,
    );
    const view = within(await dialog());
    await waitFor(() => {
      expect(
        document
          .getElementById("notification-definitions-background")
          ?.closest("[inert]"),
      ).not.toBeNull();
    });
    await userEvent.keyboard("{Escape}");
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/operations/notifications");
    });
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => {
      expect(document.activeElement?.id).toBe(
        "notification-definitions-background",
      );
    });
    void view;
  });

  it("does not offer an executable editor when no Draft is open", async () => {
    recordingFetch((call) => {
      if (
        call.url === `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload({
            draftState: draftState({
              present: false,
              reason: "no open successor Draft",
              revisionId: null,
              revisionVersion: null,
              revisionStatus: null,
            }),
          }),
          activeConfiguration: activeConfiguration(),
        });
      }
      return undefined;
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}`);
    const view = within(await dialog());
    expect(
      await view.findByRole("button", { name: "编辑草稿（不可用）" }),
    ).toBeDisabled();
    expect(view.getByRole("button", { name: "创建后继草稿" })).toBeEnabled();
    expect(view.queryByLabelText("HTTPS 接收地址")).toBeNull();
  });

  it("submits copy, enable and disable with the exact optimistic version", async () => {
    let draftVersion = 4;
    const { calls } = recordingFetch((call) => {
      if (
        call.url === `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload({
            draftState: draftState({ revisionVersion: draftVersion }),
          }),
          activeConfiguration: activeConfiguration(),
        });
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/${WEBHOOK_ID}/copy`
      ) {
        draftVersion += 1;
        expect(call.body).toMatchObject({
          expectedVersion: 4,
          newId: "ops-webhook-copy",
        });
        return jsonResponse({
          revisionId: DRAFT_REVISION,
          version: draftVersion,
          status: "draft",
          object: { id: "ops-webhook-copy", enabled: false },
        });
      }
      if (
        call.url ===
        "/api/v1/operations/notifications/webhooks/ops-webhook-copy"
      ) {
        return jsonResponse({
          webhook: definitionPayload({
            id: "ops-webhook-copy",
            definitionState: "draft-only",
            draftState: draftState({ revisionVersion: draftVersion }),
          }),
          activeConfiguration: activeConfiguration(),
        });
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/ops-webhook-copy/enable`
      ) {
        draftVersion += 1;
        return jsonResponse({
          revisionId: DRAFT_REVISION,
          version: draftVersion,
          status: "draft",
          object: { id: "ops-webhook-copy", enabled: true },
        });
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/ops-webhook-copy/disable`
      ) {
        draftVersion += 1;
        return jsonResponse({
          revisionId: DRAFT_REVISION,
          version: draftVersion,
          status: "draft",
          object: { id: "ops-webhook-copy", enabled: false },
        });
      }
      return undefined;
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}`);
    let view = within(await dialog());
    await userEvent.click(
      await view.findByRole("button", { name: "复制到草稿" }),
    );
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Webhook ops-webhook-copy" }),
      ).toBeVisible();
    });
    view = within(await dialog());
    await userEvent.click(view.getByRole("button", { name: "在草稿中启用" }));
    await waitFor(() => {
      expect(
        calls.filter(
          (call) =>
            call.method === "GET" &&
            call.url ===
              "/api/v1/operations/notifications/webhooks/ops-webhook-copy",
        ).length,
      ).toBeGreaterThanOrEqual(2);
    });
    await userEvent.click(
      within(await dialog()).getByRole("button", { name: "在草稿中停用" }),
    );
    const enableCall = calls.find((call) =>
      call.url.endsWith("/ops-webhook-copy/enable"),
    );
    const disableCall = calls.find((call) =>
      call.url.endsWith("/ops-webhook-copy/disable"),
    );
    expect(enableCall?.method).toBe("POST");
    expect(enableCall?.body).toMatchObject({ expectedVersion: 5 });
    expect(disableCall?.body).toMatchObject({ expectedVersion: 6 });
    expect(JSON.stringify([enableCall?.body, disableCall?.body])).not.toMatch(
      /digest|Bearer /i,
    );
  });

  it("does not render a wrong-object copy response as success", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload(),
          activeConfiguration: activeConfiguration(),
        });
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/${WEBHOOK_ID}/copy`
      ) {
        return jsonResponse({
          revisionId: DRAFT_REVISION,
          version: 5,
          status: "draft",
          object: { id: "ops-webhook-copy-malicious", enabled: false },
        });
      }
      return undefined;
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}`);
    const view = within(await dialog());
    await userEvent.click(
      await view.findByRole("button", { name: "复制到草稿" }),
    );
    expect(await view.findByText(/命令结果未知/)).toBeVisible();
    expect(
      view.getByRole("heading", { name: `Webhook ${WEBHOOK_ID}` }),
    ).toBeVisible();
    expect(view.queryByText(/ops-webhook-copy-malicious/)).toBeNull();
    expect(calls.filter((call) => call.url.endsWith("/copy"))).toHaveLength(1);
  });

  it("does not render a contradictory enable toggle as success", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload(),
          activeConfiguration: activeConfiguration(),
        });
      }
      if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/enable`)) {
        return jsonResponse({
          revisionId: DRAFT_REVISION,
          version: 5,
          status: "draft",
          object: { id: WEBHOOK_ID, enabled: false },
        });
      }
      return undefined;
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/webhooks/${WEBHOOK_ID}`);
    const view = within(await dialog());
    await userEvent.click(
      await view.findByRole("button", { name: "在草稿中启用" }),
    );
    expect(await view.findByText(/命令结果未知/)).toBeVisible();
    expect(calls.filter((call) => call.url.endsWith("/enable"))).toHaveLength(
      1,
    );
  });
});

describe("NotificationEditorPage", () => {
  function editorResponder(
    state: {
      version?: number;
      url?: string;
      draftStatus?: string;
      failReadsAfter?: number;
    } = {},
  ) {
    let version = state.version ?? 4;
    let url = state.url ?? "https://example.invalid/hooks/mediaflow";
    let draftStatus = state.draftStatus ?? "validated";
    let reads = 0;
    return {
      calls: [] as Call[],
      responder(call: Call): Response | undefined {
        if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/draft`)) {
          reads += 1;
          if (
            state.failReadsAfter !== undefined &&
            reads > state.failReadsAfter
          ) {
            return jsonResponse({ error: { code: "unavailable" } }, 500);
          }
          return jsonResponse(
            draftDocumentPayload({
              draft: {
                revisionId: DRAFT_REVISION,
                revisionVersion: version,
                revisionStatus: draftStatus,
                baseActiveRevisionId: ACTIVE_REVISION,
                updatedAt: "2026-09-12T00:00:00+00:00",
                validatedAt: "2026-09-12T00:01:00+00:00",
                validationErrors: [],
                webhook: webhookDocument({ url }),
              },
            }),
          );
        }
        if (
          call.url ===
          `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/${WEBHOOK_ID}`
        ) {
          version += 1;
          draftStatus = "draft";
          const body = call.body as {
            object?: { url?: string };
          };
          url = body.object?.url ?? url;
          return jsonResponse({
            revisionId: DRAFT_REVISION,
            version,
            status: "draft",
            webhook: webhookDocument({ url }),
          });
        }
        if (call.url.endsWith(`/revisions/${DRAFT_REVISION}/validate`)) {
          draftStatus = "validated";
          return jsonResponse({
            revisionId: DRAFT_REVISION,
            version,
            status: "validated",
            validationErrors: [],
          });
        }
        if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/test`)) {
          return jsonResponse({
            testId: "test-1",
            webhook: { id: WEBHOOK_ID },
            revision: {
              revisionId: DRAFT_REVISION,
              version,
              status: draftStatus,
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
        if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/activate-draft`)) {
          return jsonResponse({
            activatedRevisionId: DRAFT_REVISION,
            activatedVersion: version,
            revisionSequence: 3,
            publishedFromRevisionId: DRAFT_REVISION,
            publishedFromVersion: version,
            activeConfiguration: {
              revisionId: DRAFT_REVISION,
              version,
              revisionSequence: 3,
              status: "active",
            },
            webhook: webhookDocument({ url }),
          });
        }
        return undefined;
      },
    };
  }

  it("saves the bounded form with the exact optimistic version", async () => {
    const state = editorResponder();
    const { calls } = recordingFetch((call) => state.responder(call));
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "https://example.invalid/hooks/edited");
    const save = view.getByRole("button", { name: "保存到草稿" });
    expect(save).toBeEnabled();
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
      object: {
        id: WEBHOOK_ID,
        url: "https://example.invalid/hooks/edited",
      },
    });
    expect(JSON.stringify(saveCall?.body)).not.toMatch(/secretValue|Bearer /i);
    expect(await view.findByText(/已保存到草稿版本 5/)).toBeVisible();
  });

  it("preserves input typed while a save response is in flight and requires a second explicit save", async () => {
    const state = editorResponder();
    let releaseSave!: () => void;
    const saveGate = new Promise<void>((resolve) => {
      releaseSave = resolve;
    });
    const { calls } = recordingFetch((call) => {
      if (call.method === "PUT") {
        const response = state.responder(call);
        if (response === undefined) throw new Error("missing save response");
        return saveGate.then(() => response);
      }
      return state.responder(call);
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "https://example.invalid/hooks/submitted-a");
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    await waitFor(() => {
      expect(calls.filter((call) => call.method === "PUT")).toHaveLength(1);
    });

    const typedDuringSave = "https://example.invalid/hooks/typed-during-save";
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, typedDuringSave);
    expect(urlInput).toHaveValue(typedDuringSave);
    releaseSave();

    expect(
      await view.findByText(
        /已保存提交时的内容到草稿版本 5；保存请求处理期间你继续输入的内容仍保留为未保存修改/,
      ),
    ).toBeVisible();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(typedDuringSave);
    expect(view.getByText("有未保存修改", { exact: true })).toBeVisible();
    expect(view.queryByText("当前输入与已保存草稿一致")).toBeNull();
    expect(view.getByRole("button", { name: "检查草稿" })).toBeDisabled();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(1);

    const draftReads = () =>
      calls.filter(
        (call) => call.method === "GET" && call.url.endsWith("/draft"),
      ).length;
    await waitFor(() => {
      expect(view.getByRole("button", { name: "读取最新草稿" })).toBeEnabled();
    });
    const readsBefore = draftReads();
    await userEvent.click(view.getByRole("button", { name: "读取最新草稿" }));
    await waitFor(() => expect(draftReads()).toBe(readsBefore + 1));
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(typedDuringSave);
    expect(view.getByText("有未保存修改", { exact: true })).toBeVisible();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(1);

    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    expect(await view.findByText(/已保存到草稿版本 6/)).toBeVisible();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(typedDuringSave);
    const saves = calls.filter((call) => call.method === "PUT");
    expect(saves).toHaveLength(2);
    expect(saves[0].body).toMatchObject({
      expectedVersion: 4,
      object: { url: "https://example.invalid/hooks/submitted-a" },
    });
    expect(saves[1].body).toMatchObject({
      expectedVersion: 5,
      object: { url: typedDuringSave },
    });
  });

  it("shows a read-only deep link without a fillable form, save or test request", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.method === "GET" &&
        call.url.endsWith(`/webhooks/${WEBHOOK_ID}/draft`)
      ) {
        return jsonResponse(
          draftDocumentPayload({ actions: deniedDraftActions() }),
        );
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp(
      `/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`,
    );
    const view = within(await dialog());
    expect(
      await view.findByRole("heading", {
        name: `查看 Webhook ${WEBHOOK_ID}`,
      }),
    ).toBeVisible();
    expect(
      await view.findByText("当前账号没有所需的 Webhook 配置管理权限。"),
    ).toBeVisible();
    expect(view.getByText("只能查看这个草稿")).toBeVisible();
    expect(view.queryByLabelText("HTTPS 接收地址")).toBeNull();
    expect(view.queryByRole("button", { name: "保存到草稿" })).toBeNull();
    expect(view.queryByRole("button", { name: "检查草稿" })).toBeNull();
    expect(view.queryByRole("button", { name: "发送签名测试" })).toBeNull();
    expect(
      view.getByText("https://example.invalid/hooks/mediaflow"),
    ).toBeVisible();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);

    await userEvent.click(view.getByRole("button", { name: "查看定义" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        `/operations/notifications/webhooks/${WEBHOOK_ID}`,
      );
    });
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
  });

  it("turns a real save 403 into the permission reason and removes the form", async () => {
    let denied = false;
    const state = editorResponder();
    const { calls } = recordingFetch((call) => {
      if (call.method === "PUT") {
        denied = true;
        return jsonResponse({ error: { code: "permission_denied" } }, 403);
      }
      if (
        denied &&
        call.method === "GET" &&
        call.url.endsWith(`/webhooks/${WEBHOOK_ID}/draft`)
      ) {
        return jsonResponse(
          draftDocumentPayload({ actions: deniedDraftActions() }),
        );
      }
      return state.responder(call);
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(
      urlInput,
      "https://example.invalid/hooks/no-permission",
    );
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));

    expect(
      await view.findByText(
        /保存没有执行（403）：当前账号没有保存这个草稿的权限/,
      ),
    ).toBeVisible();
    expect(view.queryByText(/表单或草稿版本已过期/)).toBeNull();
    expect(await view.findByText("只能查看这个草稿")).toBeVisible();
    expect(
      view.getByText("当前账号没有所需的 Webhook 配置管理权限。"),
    ).toBeVisible();
    expect(view.queryByLabelText("HTTPS 接收地址")).toBeNull();
    expect(view.queryByRole("button", { name: "保存到草稿" })).toBeNull();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(1);
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
  });

  it("sends a test only for the saved revision and invalidates it on input change", async () => {
    const state = editorResponder();
    const { calls } = recordingFetch((call) => state.responder(call));
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const test = await view.findByRole("button", { name: "发送签名测试" });
    expect(test).toBeEnabled();
    await userEvent.click(test);
    expect(await view.findByText(/测试成功/)).toBeVisible();
    const urlInput = view.getByLabelText("HTTPS 接收地址");
    await userEvent.type(urlInput, "x");
    expect(view.queryByText(/测试成功/)).toBeNull();
    expect(view.getByRole("button", { name: "发送签名测试" })).toBeDisabled();
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/test"),
      ),
    ).toHaveLength(1);
  });

  it("reports an unknown signed-test result without claiming it failed or replaying it", async () => {
    const state = editorResponder();
    const { calls } = recordingFetch((call) => {
      if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/test`)) {
        throw new Error("network lost");
      }
      return state.responder(call);
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    await userEvent.click(
      await view.findByRole("button", { name: "发送签名测试" }),
    );
    expect(await view.findByText(/测试结果未知/)).toBeVisible();
    expect(view.queryByText(/测试成功/)).toBeNull();
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/test"),
      ),
    ).toHaveLength(1);
  });

  it("does not let a late test response overwrite newer input", async () => {
    let resolveTest!: (response: Response) => void;
    const testResponse = new Promise<Response>((resolve) => {
      resolveTest = resolve;
    });
    const state = editorResponder();
    recordingFetch((call) => {
      if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/test`)) {
        return testResponse;
      }
      return state.responder(call);
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    await userEvent.click(
      await view.findByRole("button", { name: "发送签名测试" }),
    );
    await userEvent.type(view.getByLabelText("HTTPS 接收地址"), "x");
    resolveTest(
      jsonResponse({
        testId: "test-late",
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
      }),
    );
    await waitFor(() => {
      expect(view.queryByText(/测试成功/)).toBeNull();
    });
  });

  it("requires the explicit confirmation checkbox before activation", async () => {
    const state = editorResponder();
    const { calls } = recordingFetch((call) => state.responder(call));
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const activate = await view.findByRole("button", {
      name: "发布已检查草稿",
    });
    expect(activate).toBeDisabled();
    await userEvent.click(
      view.getByLabelText("我确认把当前已检查的草稿发布为新的已生效配置"),
    );
    await userEvent.click(activate);
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

  it("locks the editor while publishing and opens the active definition with the submitted value", async () => {
    const publishedUrl = "https://example.invalid/hooks/published-a";
    const state = editorResponder();
    let releaseActivation!: () => void;
    const activationGate = new Promise<void>((resolve) => {
      releaseActivation = resolve;
    });
    const { calls } = recordingFetch((call) => {
      if (call.url.endsWith("/activate-draft")) {
        const response = state.responder(call);
        if (response === undefined) {
          throw new Error("missing activation response");
        }
        return activationGate.then(() => response);
      }
      if (
        call.method === "GET" &&
        call.url === `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload({ url: publishedUrl }),
          activeConfiguration: activeConfiguration(),
        });
      }
      return state.responder(call);
    });
    await connect();
    const { router } = renderApp(
      `/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`,
    );
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, publishedUrl);
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    expect(await view.findByText(/已保存到草稿版本 5/)).toBeVisible();
    await userEvent.click(view.getByRole("button", { name: "检查草稿" }));
    expect(await view.findByText("草稿检查通过")).toBeVisible();

    await userEvent.click(
      view.getByLabelText("我确认把当前已检查的草稿发布为新的已生效配置"),
    );
    await userEvent.click(view.getByRole("button", { name: "发布已检查草稿" }));
    await waitFor(() => {
      expect(
        calls.filter((call) => call.url.endsWith("/activate-draft")),
      ).toHaveLength(1);
    });

    expect(urlInput).toBeDisabled();
    expect(view.getByLabelText("密钥环境变量引用")).toBeDisabled();
    expect(view.getByRole("checkbox", { name: /任务完成/ })).toBeDisabled();
    expect(
      view.getByRole("checkbox", { name: /启用这个 Webhook/ }),
    ).toBeDisabled();
    expect(view.getByLabelText("请求超时（秒）")).toBeDisabled();
    expect(view.getByLabelText("最大尝试次数")).toBeDisabled();
    expect(view.getByLabelText("基础重试间隔（秒）")).toBeDisabled();
    expect(view.getByLabelText("最大重试间隔（秒）")).toBeDisabled();
    await userEvent.type(urlInput, "-locked");
    expect(urlInput).toHaveValue(publishedUrl);

    releaseActivation();
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        `/operations/notifications/webhooks/${WEBHOOK_ID}`,
      );
    });
    expect(await screen.findByText("草稿已发布为已生效配置")).toBeVisible();
    const detail = within(await dialog());
    expect(await detail.findByText(publishedUrl)).toBeVisible();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(1);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/test"),
      ),
    ).toHaveLength(0);
    expect(
      calls.filter((call) => call.url.endsWith("/activate-draft")),
    ).toHaveLength(1);
  });

  it("does not replay a stale activation and keeps the input correctable", async () => {
    const state = editorResponder();
    let releaseActivation!: () => void;
    const activationGate = new Promise<void>((resolve) => {
      releaseActivation = resolve;
    });
    const { calls } = recordingFetch((call) => {
      if (call.url.endsWith("/activate-draft")) {
        return activationGate.then(() =>
          jsonResponse(
            { error: { code: "notification_activation_out_of_scope" } },
            409,
          ),
        );
      }
      return state.responder(call);
    });
    await connect();
    const { router } = renderApp(
      `/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`,
    );
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.click(
      await view.findByLabelText(
        "我确认把当前已检查的草稿发布为新的已生效配置",
      ),
    );
    await userEvent.click(view.getByRole("button", { name: "发布已检查草稿" }));
    await waitFor(() => {
      expect(
        calls.filter((call) => call.url.endsWith("/activate-draft")),
      ).toHaveLength(1);
    });
    expect(urlInput).toBeDisabled();
    releaseActivation();

    expect(await view.findByText(/发布没有执行/)).toBeVisible();
    expect(urlInput).toBeEnabled();
    expect(urlInput).toHaveValue("https://example.invalid/hooks/mediaflow");
    expect(router.state.location.pathname).toBe(
      `/operations/notifications/editor/${WEBHOOK_ID}`,
    );
    expect(
      calls.filter((call) => call.url.endsWith("/activate-draft")),
    ).toHaveLength(1);
  });

  function draftConflictSession() {
    let version = 4;
    let url = "https://example.invalid/hooks/mediaflow";
    let status = "validated";
    return {
      remoteWrite(nextUrl: string) {
        version += 1;
        url = nextUrl;
        status = "draft";
      },
      responder(call: Call): Response | undefined {
        if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/draft`)) {
          return jsonResponse(
            draftDocumentPayload({
              draft: {
                revisionId: DRAFT_REVISION,
                revisionVersion: version,
                revisionStatus: status,
                baseActiveRevisionId: ACTIVE_REVISION,
                updatedAt: "2026-09-12T00:00:00+00:00",
                validatedAt:
                  status === "validated" ? "2026-09-12T00:01:00+00:00" : null,
                validationErrors: [],
                webhook: webhookDocument({ url }),
              },
            }),
          );
        }
        if (
          call.url ===
          `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/webhooks/${WEBHOOK_ID}`
        ) {
          const body = call.body as {
            expectedVersion?: number;
            object?: { url?: string };
          };
          if (body.expectedVersion !== version) {
            return jsonResponse(
              { error: { code: "configuration_version_conflict" } },
              409,
            );
          }
          version += 1;
          url = body.object?.url ?? url;
          status = "draft";
          return jsonResponse({
            revisionId: DRAFT_REVISION,
            version,
            status,
            webhook: webhookDocument({ url }),
          });
        }
        if (call.url.endsWith(`/revisions/${DRAFT_REVISION}/validate`)) {
          status = "validated";
          return jsonResponse({
            revisionId: DRAFT_REVISION,
            version,
            status,
            validationErrors: [],
          });
        }
        return undefined;
      },
    };
  }

  it("recovers from a real 409 through the card read control and keeps local input", async () => {
    const session = draftConflictSession();
    const { calls } = recordingFetch((call) => session.responder(call));
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "https://example.invalid/hooks/admin-a");

    // A second writer saves a newer Draft version before this card submits.
    session.remoteWrite("https://example.invalid/hooks/admin-b");
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    expect(
      await view.findByText(/保存没有应用：草稿在你编辑期间已经变化/),
    ).toBeVisible();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(
      "https://example.invalid/hooks/admin-a",
    );
    const failedSaves = calls.filter((call) => call.method === "PUT");
    expect(failedSaves).toHaveLength(1);

    const draftReads = () =>
      calls.filter(
        (call) => call.method === "GET" && call.url.endsWith("/draft"),
      ).length;
    const readsBefore = draftReads();
    await userEvent.click(view.getByRole("button", { name: "读取最新草稿" }));
    expect(await view.findByText(/草稿已在其他位置更新/)).toBeVisible();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(
      "https://example.invalid/hooks/admin-a",
    );
    expect(draftReads()).toBe(readsBefore + 1);
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(1);

    await userEvent.click(
      view.getByRole("button", { name: "保留本地输入并重新保存" }),
    );
    expect(view.queryByText(/草稿已在其他位置更新/)).toBeNull();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(
      "https://example.invalid/hooks/admin-a",
    );
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    expect(await view.findByText(/已保存到草稿版本 6/)).toBeVisible();

    const saves = calls.filter((call) => call.method === "PUT");
    expect(saves).toHaveLength(2);
    expect(saves[1].body).toMatchObject({
      expectedVersion: 5,
      object: { url: "https://example.invalid/hooks/admin-a" },
    });
    expect(JSON.stringify(saves[1].body)).not.toMatch(/Bearer |digest/i);
  });

  it("adopts the server Draft after a 409 and invalidates the old evidence", async () => {
    const session = draftConflictSession();
    const { calls } = recordingFetch((call) => session.responder(call));
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    await view.findByLabelText("HTTPS 接收地址");
    await userEvent.click(view.getByRole("button", { name: "检查草稿" }));
    expect(await view.findByText("草稿检查通过")).toBeVisible();
    const confirmBox = view.getByLabelText(
      "我确认把当前已检查的草稿发布为新的已生效配置",
    );
    await userEvent.click(confirmBox);
    expect(confirmBox).toBeChecked();

    const urlInput = view.getByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "https://example.invalid/hooks/admin-a");
    session.remoteWrite("https://example.invalid/hooks/admin-b");
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    expect(
      await view.findByText(/保存没有应用：草稿在你编辑期间已经变化/),
    ).toBeVisible();

    await userEvent.click(view.getByRole("button", { name: "读取最新草稿" }));
    expect(await view.findByText(/草稿已在其他位置更新/)).toBeVisible();
    await userEvent.click(view.getByRole("button", { name: "采用服务端值" }));
    expect(view.queryByText(/草稿已在其他位置更新/)).toBeNull();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(
      "https://example.invalid/hooks/admin-b",
    );
    expect(view.queryByText("草稿检查通过")).toBeNull();
    expect(
      view.getByLabelText("我确认把当前已检查的草稿发布为新的已生效配置"),
    ).not.toBeChecked();
    expect(view.getByRole("button", { name: "保存到草稿" })).toBeDisabled();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(1);
  });

  function draftLifecycleSession() {
    let draft: {
      revisionId: string;
      version: number;
      status: string;
      url: string;
    } | null = {
      revisionId: DRAFT_REVISION,
      version: 4,
      status: "validated",
      url: "https://example.invalid/hooks/mediaflow",
    };
    let activeRevisionId = ACTIVE_REVISION;
    let activeVersion = 3;
    let activeUrl = "https://example.invalid/hooks/mediaflow";

    const activeConfiguration = () => ({
      revisionId: activeRevisionId,
      version: activeVersion,
      revisionSequence: 2,
      status: "active",
    });

    const actions = () => {
      const revisionId = draft?.revisionId ?? null;
      const noDraftReason =
        "an open successor Draft is required to edit this Webhook definition";
      return {
        createDraft: {
          available: true,
          reason: null,
          method: "POST",
          path: `/api/v1/configuration/revisions/${activeRevisionId}/successor`,
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome:
            "a successor Draft seeded from the immutable Active configuration is stored",
          nextAction:
            "create the successor Draft, then edit this Webhook definition inside it",
        },
        save: {
          available: revisionId !== null,
          reason: revisionId === null ? noDraftReason : null,
          method: "PUT",
          path:
            revisionId === null
              ? null
              : `/api/v1/configuration/revisions/${revisionId}/objects/webhooks/${WEBHOOK_ID}`,
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome:
            "the bounded definition form is stored in the open successor Draft",
          nextAction: "save the bounded form, then validate and activate",
        },
        validate: {
          available: revisionId !== null,
          reason: revisionId === null ? noDraftReason : null,
          method: "POST",
          path:
            revisionId === null
              ? null
              : `/api/v1/configuration/revisions/${revisionId}/validate`,
          requiresConfirmation: false,
          sideEffects: "none",
          durableOutcome:
            "the open Draft is validated without any runtime effect",
          nextAction: "validate the Draft, then review the validation evidence",
        },
        activate: {
          available: revisionId !== null,
          reason: revisionId === null ? noDraftReason : null,
          method: "POST",
          path: `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}/activate-draft`,
          requiresConfirmation: true,
          sideEffects: "none",
          durableOutcome:
            "the exact reviewed Webhook-only Draft change becomes Active",
          nextAction: "activate the reviewed Draft after validating it",
        },
        test: action(
          revisionId === null
            ? { available: false, reason: noDraftReason }
            : {},
          WEBHOOK_ID,
        ),
      };
    };

    return {
      publish(url: string) {
        draft = null;
        activeRevisionId = DRAFT_REVISION;
        activeVersion = 5;
        activeUrl = url;
      },
      replaceOpenDraft(revisionId: string, version: number, url: string) {
        draft = { revisionId, version, status: "draft", url };
      },
      responder(call: Call): Response | undefined {
        if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/draft`)) {
          if (draft === null) {
            return jsonResponse(
              draftDocumentPayload({
                activeConfiguration: activeConfiguration(),
                webhook: webhookDocument({ url: activeUrl }),
                draft: null,
                actions: actions(),
              }),
            );
          }
          return jsonResponse(
            draftDocumentPayload({
              activeConfiguration: activeConfiguration(),
              webhook: webhookDocument({ url: activeUrl }),
              draft: {
                revisionId: draft.revisionId,
                revisionVersion: draft.version,
                revisionStatus: draft.status,
                baseActiveRevisionId: activeRevisionId,
                updatedAt: "2026-09-12T00:00:00+00:00",
                validatedAt:
                  draft.status === "validated"
                    ? "2026-09-12T00:01:00+00:00"
                    : null,
                validationErrors: [],
                webhook: webhookDocument({ url: draft.url }),
              },
              actions: actions(),
            }),
          );
        }
        if (
          call.url ===
          `/api/v1/configuration/revisions/${activeRevisionId}/successor`
        ) {
          draft = {
            revisionId: "revision-draft-2",
            version: 1,
            status: "draft",
            url: activeUrl,
          };
          return jsonResponse(
            { revisionId: draft.revisionId, created: true },
            201,
          );
        }
        if (
          draft !== null &&
          call.url ===
            `/api/v1/configuration/revisions/${draft.revisionId}/objects/webhooks/${WEBHOOK_ID}`
        ) {
          const body = call.body as {
            expectedVersion?: number;
            object?: { url?: string };
          };
          if (body.expectedVersion !== draft.version) {
            return jsonResponse(
              { error: { code: "configuration_version_conflict" } },
              409,
            );
          }
          draft = {
            ...draft,
            version: draft.version + 1,
            status: "draft",
            url: body.object?.url ?? draft.url,
          };
          return jsonResponse({
            revisionId: draft.revisionId,
            version: draft.version,
            status: draft.status,
            webhook: webhookDocument({ url: draft.url }),
          });
        }
        return undefined;
      },
    };
  }

  it("preserves unsaved input after another administrator publishes the Draft and saves it in a new successor", async () => {
    const session = draftLifecycleSession();
    const { calls } = recordingFetch((call) => session.responder(call));
    const unsavedUrl = "https://example.invalid/hooks/unsaved-local";
    const publishedUrl = "https://example.invalid/hooks/published-by-b";
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, unsavedUrl);

    session.publish(publishedUrl);
    const readsBefore = calls.filter(
      (call) => call.method === "GET" && call.url.endsWith("/draft"),
    ).length;
    await userEvent.click(view.getByRole("button", { name: "读取最新草稿" }));
    expect(
      await view.findByText("草稿已不再打开，本地输入已保留"),
    ).toBeVisible();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(unsavedUrl);
    expect(
      calls.filter(
        (call) => call.method === "GET" && call.url.endsWith("/draft"),
      ),
    ).toHaveLength(readsBefore + 1);
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/successor"),
      ),
    ).toHaveLength(0);

    await userEvent.click(view.getByRole("button", { name: "创建后继草稿" }));
    expect(await view.findByText("读取到另一个草稿修订")).toBeVisible();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(unsavedUrl);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/successor"),
      ),
    ).toHaveLength(1);
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);

    await userEvent.click(
      view.getByRole("button", { name: "保留本地输入并重新保存" }),
    );
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    expect(await view.findByText(/已保存到草稿版本 2/)).toBeVisible();
    const saves = calls.filter((call) => call.method === "PUT");
    expect(saves).toHaveLength(1);
    expect(saves[0].url).toBe(
      "/api/v1/configuration/revisions/revision-draft-2/objects/webhooks/ops-webhook",
    );
    expect(saves[0].body).toMatchObject({
      expectedVersion: 1,
      object: { url: unsavedUrl },
    });
  });

  it("holds local input when a read opens a different Draft revision and adopts only on choice", async () => {
    const session = draftLifecycleSession();
    const { calls } = recordingFetch((call) => session.responder(call));
    const unsavedUrl = "https://example.invalid/hooks/unsaved-local";
    const serverUrl = "https://example.invalid/hooks/server-revision";
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, unsavedUrl);

    session.replaceOpenDraft("revision-draft-2", 2, serverUrl);
    await userEvent.click(view.getByRole("button", { name: "读取最新草稿" }));
    expect(await view.findByText("读取到另一个草稿修订")).toBeVisible();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(unsavedUrl);
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);

    await userEvent.click(view.getByRole("button", { name: "采用服务端值" }));
    expect(view.queryByText("读取到另一个草稿修订")).toBeNull();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(serverUrl);
    expect(view.getByRole("button", { name: "保存到草稿" })).toBeDisabled();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);
  });

  it("discards retained local input only through the explicit discard action", async () => {
    const session = draftLifecycleSession();
    const { calls } = recordingFetch((call) => session.responder(call));
    const unsavedUrl = "https://example.invalid/hooks/unsaved-local";
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, unsavedUrl);

    session.publish("https://example.invalid/hooks/published-by-b");
    await userEvent.click(view.getByRole("button", { name: "读取最新草稿" }));
    expect(
      await view.findByText("草稿已不再打开，本地输入已保留"),
    ).toBeVisible();

    await userEvent.click(view.getByRole("button", { name: "关闭通知卡片" }));
    const prompt = await view.findByRole("alertdialog");
    expect(within(prompt).getByText("有未保存的修改")).toBeVisible();
    await userEvent.click(
      within(prompt).getByRole("button", { name: "继续编辑" }),
    );
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(unsavedUrl);

    await userEvent.click(view.getByRole("button", { name: "放弃本地输入" }));
    expect(view.queryByLabelText("HTTPS 接收地址")).toBeNull();
    expect(await view.findByText(/当前没有渲染可填写的表单/)).toBeVisible();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/successor"),
      ),
    ).toHaveLength(0);
  });

  it("keeps the known save result when the follow-up read fails", async () => {
    const state = editorResponder({ failReadsAfter: 1 });
    recordingFetch((call) => state.responder(call));
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "https://example.invalid/hooks/edited");
    await userEvent.click(view.getByRole("button", { name: "保存到草稿" }));
    expect(await view.findByText(/已保存到草稿版本 5/)).toBeVisible();
    expect(await view.findByText("最新读取失败")).toBeVisible();
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(
      "https://example.invalid/hooks/edited",
    );
  });

  it("offers continue/discard on unsaved close and discards only explicitly", async () => {
    const state = editorResponder();
    recordingFetch((call) => state.responder(call));
    await connect();
    const { router } = renderApp(
      `/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`,
    );
    const view = within(await dialog());
    const urlInput = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(urlInput);
    await userEvent.type(urlInput, "https://example.invalid/hooks/kept");
    await userEvent.click(view.getByRole("button", { name: "关闭通知卡片" }));
    const prompt = await view.findByRole("alertdialog");
    expect(within(prompt).getByText("有未保存的修改")).toBeVisible();
    await userEvent.click(
      within(prompt).getByRole("button", { name: "继续编辑" }),
    );
    expect(view.getByLabelText("HTTPS 接收地址")).toHaveValue(
      "https://example.invalid/hooks/kept",
    );
    await waitFor(() => {
      expect(document.activeElement?.id).toBe("notification-edit-url");
    });
    await userEvent.click(view.getByRole("button", { name: "关闭通知卡片" }));
    const secondPrompt = await view.findByRole("alertdialog");
    await userEvent.click(
      within(secondPrompt).getByRole("button", { name: "放弃并离开" }),
    );
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/operations/notifications");
    });
  });

  it("does not render a fillable form when no Draft can be edited", async () => {
    const { calls } = recordingFetch((call) => {
      if (call.url.endsWith(`/webhooks/${WEBHOOK_ID}/draft`)) {
        return jsonResponse(
          draftDocumentPayload({
            draft: null,
            actions: {
              createDraft: {
                available: false,
                reason: "the connected API principal cannot create a Draft",
                method: "POST",
                path: null,
                requiresConfirmation: false,
                sideEffects: "none",
                durableOutcome: "a successor Draft is stored",
                nextAction: "ask for permission",
              },
              save: {
                available: false,
                reason: "an open successor Draft is required",
                method: "PUT",
                path: null,
                requiresConfirmation: false,
                sideEffects: "none",
                durableOutcome: "stored",
                nextAction: "start a Draft",
              },
              validate: {
                available: false,
                reason: "an open successor Draft is required",
                method: "POST",
                path: null,
                requiresConfirmation: false,
                sideEffects: "none",
                durableOutcome: "validated",
                nextAction: "start a Draft",
              },
              activate: {
                available: false,
                reason: "an open successor Draft is required",
                method: "POST",
                path: `/api/v1/operations/notifications/webhooks/${WEBHOOK_ID}/activate-draft`,
                requiresConfirmation: true,
                sideEffects: "none",
                durableOutcome: "active",
                nextAction: "start a Draft",
              },
              test: action({ available: false, reason: "permission" }),
            },
          }),
        );
      }
      return undefined;
    });
    await connect();
    renderApp(`/ui-v2/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    expect(await view.findByText(/当前没有渲染可填写的表单/)).toBeVisible();
    expect(view.queryByLabelText("HTTPS 接收地址")).toBeNull();
    expect(view.getByRole("button", { name: "创建后继草稿" })).toBeDisabled();
    const read = view.getByRole("button", { name: "读取最新草稿" });
    expect(read).toBeEnabled();
    const readsBefore = calls.filter(
      (call) => call.method === "GET" && call.url.endsWith("/draft"),
    ).length;
    await userEvent.click(read);
    await waitFor(() => {
      expect(
        calls.filter(
          (call) => call.method === "GET" && call.url.endsWith("/draft"),
        ).length,
      ).toBe(readsBefore + 1);
    });
    expect(view.queryByLabelText("HTTPS 接收地址")).toBeNull();
  });
});

describe("DeliveryListPage", () => {
  it("renders readable statuses, attempts and failure summaries", async () => {
    recordingFetch((call) => {
      if (call.url.startsWith("/api/v1/notifications?")) {
        return jsonResponse(deliveriesPayload());
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries?status=dead-letter");
    expect(await screen.findByText("通知投递记录")).toBeVisible();
    const card = screen
      .getByText("任务完成", { selector: ".mf-notification-webhook-name" })
      .closest("li");
    expect(card).not.toBeNull();
    const view = within(card as HTMLElement);
    expect(view.getByText("死信")).toBeVisible();
    expect(view.getByText("尝试 3 次")).toBeVisible();
    expect(view.getByText("接收端返回 HTTP 400")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "投递状态" })).toHaveValue(
      "dead-letter",
    );
  });

  it("opens a filtered delivery and returns to the same filter", async () => {
    recordingFetch((call) => {
      if (call.url.startsWith("/api/v1/notifications?")) {
        return jsonResponse(deliveriesPayload());
      }
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(deliveryDetailPayload());
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp(
      "/ui-v2/operations/notifications/deliveries?status=dead-letter",
    );
    await userEvent.click(
      await screen.findByRole("link", { name: "查看投递" }),
    );
    const view = within(await dialog());
    expect(view.getByText("投递 delivery-1")).toBeVisible();
    expect(router.state.location.search).toMatchObject({
      status: "dead-letter",
    });
    await userEvent.click(view.getByRole("link", { name: "返回投递列表" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        "/operations/notifications/deliveries",
      );
    });
    expect(router.state.location.search).toMatchObject({
      status: "dead-letter",
    });
    expect(screen.getByRole("combobox", { name: "投递状态" })).toHaveValue(
      "dead-letter",
    );
  });
});

describe("DeliveryDetailPage recovery", () => {
  it("recovers a real HTTP 400 dead letter to pending without claiming the receiver was never reached", async () => {
    let recovered = false;
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(
          recovered ? pendingDeliveryDetailPayload() : deliveryDetailPayload(),
        );
      }
      if (call.url === "/api/v1/notifications/delivery-1/requeue") {
        recovered = true;
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
          delivery: pendingDeliveryDetailPayload(),
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries/delivery-1");
    const view = within(await dialog());
    expect(
      await view.findByText("接收端返回 HTTP 400", { exact: true }),
    ).toBeVisible();
    expect(view.getByText(/没有确认成功：接收端返回 HTTP 400/)).toBeVisible();
    const button = await view.findByRole("button", {
      name: "重新入队死信投递",
    });
    expect(button).toBeDisabled();
    await userEvent.click(
      view.getByLabelText("我确认重新入队这条精确的死信投递"),
    );
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
    expect(await view.findByText(/重新入队已完成/)).toBeVisible();
    expect(await view.findByText(/当前没有已确认的发送结果/)).toBeVisible();
    expect(view.queryByText(/接收端尚未收到/)).toBeNull();
    expect(
      view.getByText("待投递 · 等待下一次尝试", { exact: true }),
    ).toBeVisible();
    expect(
      calls.filter(
        (call) => call.url === "/api/v1/notifications/delivery-1/requeue",
      ),
    ).toHaveLength(1);
  });

  it("reports an unknown recovery result without replaying it", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(deliveryDetailPayload());
      }
      if (call.url === "/api/v1/notifications/delivery-1/requeue") {
        throw new Error("network lost");
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries/delivery-1");
    const view = within(await dialog());
    await userEvent.click(
      await view.findByLabelText("我确认重新入队这条精确的死信投递"),
    );
    await userEvent.click(
      view.getByRole("button", { name: "重新入队死信投递" }),
    );
    expect(await view.findByText(/命令结果未知/)).toBeVisible();
    expect(view.getByText("死信", { exact: true })).toBeVisible();
    expect(
      calls.filter(
        (call) => call.url === "/api/v1/notifications/delivery-1/requeue",
      ),
    ).toHaveLength(1);
  });

  it("does not replay a stale recovery and offers the exact refresh", async () => {
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
    const view = within(await dialog());
    await userEvent.click(
      await view.findByLabelText("我确认重新入队这条精确的死信投递"),
    );
    await userEvent.click(
      view.getByRole("button", { name: "重新入队死信投递" }),
    );
    expect(await view.findByText(/没有应用恢复/)).toBeVisible();
    expect(
      calls.filter(
        (call) => call.url === "/api/v1/notifications/delivery-1/requeue",
      ),
    ).toHaveLength(1);
  });

  it("keeps the known recovery result when the follow-up read fails", async () => {
    let reads = 0;
    recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        reads += 1;
        if (reads > 1) {
          return jsonResponse({ error: { code: "unavailable" } }, 500);
        }
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
    const view = within(await dialog());
    await userEvent.click(
      await view.findByLabelText("我确认重新入队这条精确的死信投递"),
    );
    await userEvent.click(
      view.getByRole("button", { name: "重新入队死信投递" }),
    );
    expect(await view.findByText(/重新入队已完成/)).toBeVisible();
    expect(await view.findByText("最新读取失败")).toBeVisible();
  });

  it("renders no recovery control when the backend advertises none", async () => {
    recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(
          deliveryDetailPayload({
            status: "delivered",
            deliveredAt: "2026-09-12T00:04:00+00:00",
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
    const view = within(await dialog());
    expect(await view.findByText("没有可用的人工恢复")).toBeVisible();
    expect(view.queryByRole("button", { name: /重新入队/ })).toBeNull();
  });

  it("fails closed on a malformed delivery document", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(deliveryDetailPayload({ status: "exploded" }));
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries/delivery-1");
    const view = within(await dialog());
    expect(await view.findByText("投递读取失败")).toBeVisible();
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(0);
    expect(view.queryByRole("button", { name: /重新入队/ })).toBeNull();
  });

  it("fails closed when a recovery transport names another delivery", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/notifications/deliveries/delivery-1"
      ) {
        return jsonResponse(
          deliveryDetailPayload({
            actions: {
              requeue: {
                available: true,
                reason: null,
                method: "POST",
                path: "/api/v1/notifications/delivery-2/requeue",
                requiresConfirmation: true,
                sideEffects: "delivery_queue_state_only",
                durableOutcome: "the delivery returns to pending",
                nextAction: "confirm the requeue",
              },
            },
          }),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/ui-v2/operations/notifications/deliveries/delivery-1");
    const view = within(await dialog());
    expect(await view.findByText("投递读取失败")).toBeVisible();
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(0);
  });
});
