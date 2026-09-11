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

function executionDocument(): Json {
  const value = document("organizeExecutionDetail");
  value["executionId"] = "execution-1";
  // The transport must name the exact object it belongs to, exactly as the
  // real backend emits it for the durable execution identity.
  const actions = value["actions"] as Json;
  (actions["detail"] as Json)["path"] =
    "/api/v1/operations/organize/executions/execution-1";
  return value;
}

/** The exact Execute transport the backend advertises for one Preview. */
function previewExecuteAction(): Json {
  return {
    available: true,
    durableOutcome:
      "one durable admitted execution and its Processing Worker outcome are stored; only OrganizerExecutor may then mutate Storage",
    method: "POST",
    nextAction: "confirm one Execute action for the selected exact items",
    path: "/api/v1/operations/organize/previews/preview-1/execute",
    reason: null,
    requiresConfirmation: true,
    sideEffects: "reported_per_item",
  };
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
    const execution = executionDocument();
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
    const withheld = actions["execute"] as Json;
    withheld["available"] = false;
    withheld["reason"] =
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

  it("fails closed on malformed action and selection data without rendering a control", async () => {
    const previewRequests = { count: 0 };
    // Each malformed variant must make the whole Preview read malformed so no
    // executable control, hostile value or execution request can follow.
    const malformedVariants: Array<(value: Json) => void> = [
      // An offered action without its exact transport method.
      (value) => {
        ((value["actions"] as Json)["execute"] as Json)["method"] = null;
      },
      // An offered action without its bounded relative route.
      (value) => {
        ((value["actions"] as Json)["execute"] as Json)["path"] = null;
      },
      // An offered action that also claims a reason is contradictory.
      (value) => {
        ((value["actions"] as Json)["execute"] as Json)["reason"] =
          "not really offered";
      },
      // An absolute, non-API path must never become a route.
      (value) => {
        ((value["actions"] as Json)["execute"] as Json)["path"] =
          "https://attacker.example/execute";
      },
      // A traversal-shaped relative route is rejected too.
      (value) => {
        ((value["actions"] as Json)["execute"] as Json)["path"] =
          "/api/v1/../../operations/organize/previews/preview-1/execute";
      },
      // A withholding action must still explain itself.
      (value) => {
        const action = (value["actions"] as Json)["execute"] as Json;
        action["available"] = false;
        action["reason"] = null;
      },
      // A confirmation is only ever asked for a mutating action.
      (value) => {
        const action = (value["actions"] as Json)["execute"] as Json;
        action["requiresConfirmation"] = true;
        action["method"] = "GET";
      },
      // A selection that contradicts its own identity list is malformed.
      (value) => {
        value["executionCandidateItemIds"] = ["item-1", "item-1"];
      },
    ];

    for (const mutate of malformedVariants) {
      const document = previewDocument();
      mutate(document);
      const { calls } = recordingFetch((call) => {
        if (call.url === "/api/v1/operations/organize/previews/preview-1") {
          previewRequests.count += 1;
          return jsonResponse(document);
        }
        return undefined;
      });
      authStore.setToken(TOKEN);
      renderApp("/ui-v2/operations/organize/preview/preview-1");

      // The bounded malformed read state replaces the journey, so no Execute
      // control and no hostile value can reach the DOM.
      await screen.findByText(
        /could not be understood as the expected contract/i,
      );
      expect(
        screen.queryByRole("button", {
          name: "Execute selected exact items",
        }),
      ).toBeNull();
      const rendered = (await screen.findByRole("main")).textContent ?? "";
      expect(rendered).not.toMatch(/attacker\.example|hacked/);
      // Nothing was ever submitted for a document the model refused.
      expect(
        calls.filter((call) => call.url.endsWith("/execute")),
      ).toHaveLength(0);
      cleanup();
      authStore.clearToken();
    }
    expect(previewRequests.count).toBe(malformedVariants.length);
  });

  it("fails closed on malformed execution item and effect data", async () => {
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
      const document = executionDocument();
      mutate(document);
      recordingFetch((call) => {
        if (call.url === "/api/v1/operations/organize/executions/execution-1") {
          return jsonResponse(document);
        }
        return undefined;
      });
      authStore.setToken(TOKEN);
      renderApp("/ui-v2/operations/organize/execution/execution-1");

      await screen.findByText(
        /could not be understood as the expected contract/i,
      );
      const rendered = (await screen.findByRole("main")).textContent ?? "";
      expect(rendered).not.toMatch(/hacked|RM_RF_SLASH|rm -rf \/|totally/);
      cleanup();
      authStore.clearToken();
    }
  });

  it("renders the valid uncertain-outcome evidence without calling it malformed", async () => {
    // The executor records an attempted/unknown mutation with no verified
    // effect as the bounded ``UNCERTAIN_EXECUTOR_INVOCATION`` marker. This is
    // truthful, non-replayable evidence: the detail page must render it, not
    // refuse the whole read.
    const document = executionDocument();
    const item = (document["items"] as Json[])[0];
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
    recordingFetch((call) => {
      if (call.url === "/api/v1/operations/organize/executions/execution-1") {
        return jsonResponse(document);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/organize/execution/execution-1");

    await screen.findByRole("heading", { name: "Manual organize execution" });
    const rendered = (await screen.findByRole("main")).textContent ?? "";
    expect(rendered).toContain("UNCERTAIN_EXECUTOR_INVOCATION");
    expect(rendered).not.toMatch(/could not be understood as the expected/);
  });

  it("renders no Execute control when the execute action names another route or method", async () => {
    // The Execute control is rendered only from the mutating POST route of
    // this exact Preview. A contradictory transport — a safe method or a route
    // belonging to another object — is malformed, never an executable control.
    const wrongTransports: readonly Json[] = [
      { ...previewExecuteAction(), method: "GET" },
      {
        ...previewExecuteAction(),
        path: "/api/v1/operations/organize/previews/other-preview/execute",
      },
      {
        ...previewExecuteAction(),
        path: "/api/v1/operations/tasks/task-1",
      },
    ];
    for (const transport of wrongTransports) {
      const document = previewDocument();
      document["actions"] = { ...((document["actions"] as Json) ?? {}) };
      (document["actions"] as Json)["execute"] = transport;
      recordingFetch((call) => {
        if (call.url === "/api/v1/operations/organize/previews/preview-1") {
          return jsonResponse(document);
        }
        return undefined;
      });
      authStore.setToken(TOKEN);
      renderApp("/ui-v2/operations/organize/preview/preview-1");

      await screen.findByText(
        /could not be understood as the expected contract/i,
      );
      expect(
        screen.queryByRole("button", {
          name: "Execute selected exact items",
        }),
      ).toBeNull();
      cleanup();
      authStore.clearToken();
    }
  });
});
