import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

const TOKEN = "notification-token";
const ACTIVE_REVISION = "revision-active-1";
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
      if (response !== undefined) return response;
      if (
        call.method === "GET" &&
        call.url === "/api/operations/notifications/webhooks"
      ) {
        return jsonResponse(listPayload());
      }
      if (
        call.method === "GET" &&
        call.url ===
          `/api/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          webhook: definitionPayload(),
          activeConfiguration: activeConfiguration(),
        });
      }
      if (call.method === "GET" && call.url.startsWith("/api/notifications?")) {
        return jsonResponse({ items: [], total: 0, truncated: false });
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

function action(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: `/api/operations/notifications/webhooks/${WEBHOOK_ID}/test`,
    requiresConfirmation: false,
    sideEffects: "one_signed_test_request",
    durableOutcome: "no durable change",
    nextAction: "test the exact displayed revision",
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

function definitionActions(): Record<string, unknown> {
  const operationsRoute = `/api/operations/notifications/webhooks/${WEBHOOK_ID}`;
  const editPath = `/api/configuration/revisions/${ACTIVE_REVISION}/objects/webhooks/${WEBHOOK_ID}`;
  return {
    detail: {
      available: true,
      reason: null,
      method: "GET",
      path: operationsRoute,
      sideEffects: "none",
      durableOutcome: null,
      nextAction: "inspect the Webhook definition",
    },
    test: action(),
    edit: {
      available: true,
      reason: null,
      method: "PUT",
      path: editPath,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the definition is published directly",
      nextAction: "apply the form",
    },
    copy: {
      available: true,
      reason: null,
      method: "POST",
      path: `${editPath}/copy`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the copied definition is published directly",
      nextAction: "open the copied definition",
    },
    enable: {
      available: true,
      reason: null,
      method: "POST",
      path: `${editPath}/enable`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the definition is enabled in the Active configuration",
      nextAction: "refresh the definition",
    },
    disable: {
      available: true,
      reason: null,
      method: "POST",
      path: `${editPath}/disable`,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "the definition is disabled in the Active configuration",
      nextAction: "refresh the definition",
    },
    draftCreate: {
      available: false,
      reason: "Webhook definitions are published directly; no draft exists",
      method: "POST",
      path: null,
      requiresConfirmation: false,
      sideEffects: "none",
      durableOutcome: "none",
      nextAction: "apply the Webhook form",
    },
    activate: {
      available: false,
      reason: "the definition is already Active",
      method: "POST",
      path: null,
      requiresConfirmation: true,
      sideEffects: "none",
      durableOutcome: "none",
      nextAction: "apply the form",
    },
  };
}

function definitionPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    ...webhookDocument(),
    definitionState: "active",
    activeConfiguration: activeConfiguration(),
    draftState: {
      present: true,
      reason: null,
      revisionId: ACTIVE_REVISION,
      revisionVersion: 3,
      revisionStatus: "validated",
      baseActiveRevisionId: null,
      updatedAt: null,
      validatedAt: null,
      validationErrors: [],
    },
    actions: definitionActions(),
    supportedEvents: ["task.completed", "task.failed"],
    ...overrides,
  };
}

function listPayload(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    activeConfiguration: activeConfiguration(),
    items: [
      {
        ...definitionPayload(),
        actions: definitionActions(),
      },
    ],
    total: 1,
    truncated: false,
    draftState: {
      present: true,
      reason: null,
      revisionId: ACTIVE_REVISION,
      revisionVersion: 3,
      revisionStatus: "validated",
      baseActiveRevisionId: null,
      updatedAt: null,
      validatedAt: null,
      validationErrors: [],
    },
    supportedEvents: ["task.completed", "task.failed"],
    actions: {
      create: {
        available: true,
        reason: null,
        method: "POST",
        path: `/api/configuration/revisions/${ACTIVE_REVISION}/objects/webhooks`,
        sideEffects: "none",
        durableOutcome: "the definition is published directly",
        nextAction: "apply the definition",
      },
      createDraft: {
        available: false,
        reason: "Webhook definitions are published directly; no draft exists",
        method: "POST",
        path: null,
        sideEffects: "none",
        durableOutcome: "none",
        nextAction: "apply the definition",
      },
    },
    ...overrides,
  };
}

async function dialog(): Promise<HTMLElement> {
  return screen.findByRole("dialog");
}

describe("V2 Notification direct publication", () => {
  it("lists the Active definition and opens a direct create form", async () => {
    recordingFetch();
    authStore.setToken(TOKEN);
    renderApp("/operations/notifications");
    expect(
      await screen.findByText(/https:\/\/example\.invalid\/hooks\/mediaflow/),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /创建后继草稿/ })).toBeNull();
    expect(screen.getByText("无", { selector: "strong" })).toBeVisible();
    await userEvent.click(screen.getByRole("link", { name: "新建 Webhook" }));
    const view = within(await dialog());
    expect(await view.findByLabelText("标识符")).toBeVisible();
  });

  it("creates a definition through the Active object route without a draft", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.method === "POST" &&
        call.url ===
          `/api/configuration/revisions/${ACTIVE_REVISION}/objects/webhooks`
      ) {
        return jsonResponse({
          revisionId: "revision-active-2",
          version: 1,
          publishedFromRevisionId: ACTIVE_REVISION,
          publishedFromVersion: 3,
          webhook: webhookDocument({ id: "new-webhook" }),
        });
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/operations/notifications/webhooks/new");
    const view = within(await dialog());
    await userEvent.clear(await view.findByLabelText("标识符"));
    await userEvent.type(view.getByLabelText("标识符"), "new-webhook");
    await userEvent.type(
      view.getByLabelText("HTTPS 接收地址"),
      "https://example.invalid/hooks/new",
    );
    await userEvent.type(
      view.getByLabelText("密钥环境变量引用"),
      "MEDIAFLOW_WEBHOOK_SECRET",
    );
    const eventOptions = view.getAllByRole("checkbox");
    await userEvent.click(eventOptions[0]);
    await userEvent.click(view.getByRole("button", { name: "应用更改" }));
    await waitFor(() => {
      const write = calls.find(
        (call) =>
          call.url ===
            `/api/configuration/revisions/${ACTIVE_REVISION}/objects/webhooks` &&
          call.method === "POST",
      );
      expect(write).toBeDefined();
      expect(write?.body).toMatchObject({ expectedVersion: 3 });
    });
    expect(
      calls.some((call) => call.url.includes("/successor")),
    ).toBe(false);
  });

  it("applies the Active form and never posts draft or activation routes", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.method === "PUT" &&
        call.url ===
          `/api/configuration/revisions/${ACTIVE_REVISION}/objects/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({
          revisionId: "revision-active-2",
          version: 1,
          publishedFromRevisionId: ACTIVE_REVISION,
          publishedFromVersion: 3,
          webhook: webhookDocument(),
        });
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(`/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    expect(await view.findByText(/点击「应用更改」后/)).toBeVisible();
    const url = await view.findByLabelText("HTTPS 接收地址");
    await userEvent.clear(url);
    await userEvent.type(url, "https://example.invalid/hooks/updated");
    await userEvent.click(view.getByRole("button", { name: "应用更改" }));
    await waitFor(() => {
      const write = calls.find(
        (call) =>
          call.method === "PUT" &&
          call.url ===
            `/api/configuration/revisions/${ACTIVE_REVISION}/objects/webhooks/${WEBHOOK_ID}`,
      );
      expect(write).toBeDefined();
      expect(write?.body).toMatchObject({
        expectedVersion: 3,
        object: {
          url: "https://example.invalid/hooks/updated",
        },
      });
    });
    expect(
      calls.some((call) =>
        /\/successor|\/validate|\/activate|\/draft/.test(call.url),
      ),
    ).toBe(false);
  });

  it("sends exactly one signed test when explicitly requested", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.method === "POST" &&
        call.url ===
          `/api/operations/notifications/webhooks/${WEBHOOK_ID}/test`
      ) {
        return jsonResponse({
          testId: "test-1",
          webhookId: WEBHOOK_ID,
          revision: {
            revisionId: ACTIVE_REVISION,
            version: 3,
            status: "active",
          },
          webhook: webhookDocument(),
          outcome: "success",
          category: "http_204",
          responseStatus: 204,
          message: "delivered",
          durableState: "no durable change",
          retrySafe: true,
          nextAction: "review the outcome",
        });
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp(`/operations/notifications/editor/${WEBHOOK_ID}`);
    const view = within(await dialog());
    await userEvent.click(
      await view.findByRole("button", { name: "发送签名测试" }),
    );
    await waitFor(() =>
      expect(
        calls.filter(
          (call) =>
            call.method === "POST" &&
            call.url ===
              `/api/operations/notifications/webhooks/${WEBHOOK_ID}/test`,
        ),
      ).toHaveLength(1),
    );
    expect(await view.findByText(/测试成功/)).toBeVisible();
  });

  it("does not render a fillable form when no Active configuration exists", async () => {
    recordingFetch((call) => {
      if (
        call.method === "GET" &&
        call.url === "/api/operations/notifications/webhooks"
      ) {
        return jsonResponse(
          listPayload({
            activeConfiguration: null,
            items: [],
            total: 0,
            actions: {
              create: {
                available: false,
                reason: "no Active configuration exists",
                method: "POST",
                path: null,
                sideEffects: "none",
                durableOutcome: "none",
                nextAction: "initialize configuration in Settings",
              },
              createDraft: {
                available: false,
                reason: "no Active configuration exists",
                method: "POST",
                path: null,
                sideEffects: "none",
                durableOutcome: "none",
                nextAction: "initialize configuration in Settings",
              },
            },
          }),
        );
      }
      if (
        call.method === "GET" &&
        call.url ===
          `/api/operations/notifications/webhooks/${WEBHOOK_ID}`
      ) {
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/operations/notifications");
    expect(
      await screen.findByText("还没有 Webhook 定义。"),
    ).toBeVisible();
    expect(screen.queryByRole("link", { name: "新建 Webhook" })).toBeNull();
    expect(screen.queryByRole("button", { name: /草稿/ })).toBeNull();
  });
});
