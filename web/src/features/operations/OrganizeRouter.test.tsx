import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import fixture from "../../entities/operations/__fixtures__/manual-operations.json";

/**
 * Component/router proof for the V2 manual Organize journey.
 *
 * Every API payload is the exact document the real Python API returns
 * (captured into the checked-in fixture and re-proved by
 * `tests/test_manual_operations_contract.py`), so these tests exercise the real
 * route tree, the real query/mutation boundaries and the real normalizers
 * together. The assertions prove the operator journey and its safety
 * properties: one Execute action, no token/digest in any request body, no
 * automatic retry after ambiguity and no executable control for a state the
 * backend does not advertise.
 */

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;
const TOKEN = "organize-token";

function document(name: string): Json {
  return JSON.parse(JSON.stringify(documents[name])) as Json;
}

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

function intentDocument(): Json {
  const value = document("organizeIntentChoice");
  const items = value["items"] as Json[];
  for (const item of items) {
    item["itemId"] = "item-1";
  }
  value["intentId"] = "intent-1";
  const actions = value["actions"] as Json;
  (actions["choice"] as Json)["path"] =
    "/api/v1/operations/organize/intents/intent-1/items/{itemId}/choice";
  (actions["preview"] as Json)["path"] =
    "/api/v1/operations/organize/intents/intent-1/previews";
  return value;
}

function previewDocument(): Json {
  const value = document("organizePreviewDetail");
  value["previewId"] = "preview-1";
  value["intentId"] = "intent-1";
  value["executionCandidateItemIds"] = ["item-1"];
  const items = value["items"] as Json[];
  items[0]["itemId"] = "item-1";
  const actions = value["actions"] as Json;
  (actions["execute"] as Json)["available"] = true;
  (actions["execute"] as Json)["reason"] = null;
  (actions["execute"] as Json)["path"] =
    "/api/v1/operations/organize/previews/preview-1/execute";
  return value;
}

describe("V2 manual Organize journey", () => {
  it("renders the durable intent, saves one optimistic choice edit and creates the exact Preview", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/organize/intents/intent-1/previews" &&
        call.method === "POST"
      ) {
        return jsonResponse(previewDocument(), 201);
      }
      if (call.url.startsWith("/api/v1/operations/organize/previews/")) {
        return jsonResponse(previewDocument());
      }
      if (call.url.startsWith("/api/v1/operations/organize/intents/intent-1")) {
        if (call.method === "GET") {
          return jsonResponse(intentDocument());
        }
        return jsonResponse(intentDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/organize/intent/intent-1");

    await screen.findByRole("heading", { name: "Manual organize intent" });
    expect(screen.getByText(/version 2/)).toBeVisible();

    await user.selectOptions(
      await screen.findByLabelText("Organize policy item-1"),
      "A",
    );
    await user.click(screen.getByRole("button", { name: "Save choice" }));

    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "POST" &&
            call.url.includes(
              "/api/v1/operations/organize/intents/intent-1/items/item-1/choice",
            ),
        ),
      ).toBe(true),
    );
    const choice = calls.find((call) =>
      call.url.includes("/items/item-1/choice"),
    );
    expect(choice?.body).toMatchObject({
      expectedVersion: 2,
      expectedItemVersion: 2,
      organizePolicyId: "A",
    });
    expect(JSON.stringify(choice?.body)).not.toMatch(
      /fingerprint|digest|token|path/i,
    );

    await user.click(
      await screen.findByRole("button", { name: "Create exact Preview" }),
    );
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.url ===
              "/api/v1/operations/organize/intents/intent-1/previews" &&
            call.method === "POST",
        ),
      ).toBe(true),
    );
    // The journey continues to the exact Preview route.
    await screen.findByRole("heading", {
      name: /Exact manual organize Preview/,
    });
  });

  it("admits exactly the selected exact items with one Execute action and no authority material", async () => {
    const user = userEvent.setup();
    const execution = document("organizeExecutionDetail");
    execution["executionId"] = "execution-1";
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/organize/previews/preview-1" &&
        call.method === "GET"
      ) {
        return jsonResponse(previewDocument());
      }
      if (
        call.url === "/api/v1/operations/organize/previews/preview-1/execute" &&
        call.method === "POST"
      ) {
        return jsonResponse(execution, 202);
      }
      if (
        call.url === "/api/v1/operations/organize/executions/execution-1" &&
        call.method === "GET"
      ) {
        return jsonResponse(execution);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/organize/preview/preview-1");

    await screen.findByRole("heading", {
      name: /Exact manual organize Preview/,
    });
    expect(screen.getByText(/Zero Storage mutation/)).toBeVisible();
    const executeButton = await screen.findByRole("button", {
      name: "Execute selected exact items",
    });
    expect(executeButton).toBeEnabled();
    await user.click(executeButton);

    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.url ===
              "/api/v1/operations/organize/previews/preview-1/execute" &&
            call.method === "POST",
        ),
      ).toBe(true),
    );
    const execute = calls.find((call) => call.url.endsWith("/execute"));
    expect(execute?.body).toMatchObject({
      confirmation: true,
      itemIds: ["item-1"],
      expectedIntentVersion: 2,
    });
    const serialized = JSON.stringify(execute?.body);
    expect(serialized).not.toMatch(
      /authorization|token|digest|fingerprint|snapshot/i,
    );
    // Exactly one submission was attempted.
    expect(calls.filter((call) => call.url.endsWith("/execute")).length).toBe(
      1,
    );

    await screen.findByRole("heading", {
      name: "Manual organize execution",
    });
    expect(screen.getByText(/Execution execution-1/)).toBeVisible();
    expect(screen.getByText("Result")).toBeVisible();
  });

  it("renders no executable control when the backend withholds the Execute action", async () => {
    const preview = previewDocument();
    const actions = preview["actions"] as Json;
    (actions["execute"] as Json)["available"] = false;
    (actions["execute"] as Json)["reason"] =
      "registered workers are live but report a runtime schema that differs from the active application";
    const worker = preview["worker"] as Json;
    worker["ready"] = false;
    recordingFetch((call) => {
      if (call.url === "/api/v1/operations/organize/previews/preview-1") {
        return jsonResponse(preview);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/organize/preview/preview-1");

    await screen.findByRole("heading", {
      name: /Exact manual organize Preview/,
    });
    const executeButton = screen.getByRole("button", {
      name: "Execute selected exact items",
    });
    expect(executeButton).toBeDisabled();
    expect(screen.getByText(/Not ready:/)).toBeVisible();
  });

  it("never retries a rejected admission and keeps the durable Preview visible", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/operations/organize/previews/preview-1") {
        return jsonResponse(previewDocument());
      }
      if (call.url.endsWith("/execute")) {
        return jsonResponse(
          { error: { code: "authorization_expired", message: "expired" } },
          409,
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/organize/preview/preview-1");

    await screen.findByRole("heading", {
      name: /Exact manual organize Preview/,
    });
    await user.click(
      screen.getByRole("button", { name: "Execute selected exact items" }),
    );

    await screen.findByText(/Execution not admitted/);
    expect(screen.getByText(/authorization_expired/)).toBeVisible();
    expect(calls.filter((call) => call.url.endsWith("/execute")).length).toBe(
      1,
    );
  });
});
