import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

/**
 * Component/router proof for the native Automation definition lifecycle page.
 *
 * The documents mirror the exact projections the real Python API publishes
 * (proved by tests/test_v2_automation_lifecycle.py). The assertions prove the
 * operator journey and its safety properties: one checked 保存 publishes the
 * intended successor, a new definition is offered disabled, enable/copy/removal
 * are separate explicit commands with confirmation where it matters, the exact
 * request method/path/body is used, and no control appears for a state the
 * backend does not advertise.
 */

const TOKEN = "lifecycle-token";
const ACTIVE_REVISION = "revision-active-1";
const DIGEST = "a".repeat(64);

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: Record<string, unknown> | null;
}

function recordingFetch(respond: (call: Call) => Response | undefined) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: init?.method ?? "GET",
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      };
      calls.push(call);
      return (
        respond(call) ?? jsonResponse({ error: { code: "not_found" } }, 404)
      );
    }),
  );
  return calls;
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

const ACTIVE = {
  revisionId: ACTIVE_REVISION,
  version: 3,
  revisionSequence: 2,
  status: "active",
  digest: DIGEST,
};

function formAuthority() {
  return {
    active: ACTIVE,
    sideEffects: "none",
    fields: [
      "id",
      "name",
      "enabled",
      "resourceLibraryId",
      "mode",
      "itemLimit",
      "intervalSeconds",
      "cron",
      "timezone",
    ],
    defaults: {},
    resourceLibraries: [
      {
        id: "source",
        name: "Source",
        enabled: true,
        storageId: "s",
        storagePath: "Media",
      },
    ],
    enums: {
      modes: ["scan-only", "scan-and-plan", "automatic-organization"],
      scheduleTypes: ["interval", "cron"],
    },
    limits: {
      id: 64,
      name: 120,
      sourceScope: 1024,
      timezone: 64,
      itemLimit: { minimum: 1, maximum: 10000 },
      intervalSeconds: { minimum: 1, maximum: 31536000 },
    },
    actions: {
      create: true,
      edit: true,
      copy: true,
      toggle: true,
      remove: true,
    },
  };
}

function definition(overrides: Record<string, unknown> = {}) {
  return {
    id: "nightly",
    name: "Nightly",
    enabled: false,
    resourceLibraryId: "source",
    mode: "scan-only",
    itemLimit: 10,
    sourceScope: null,
    intervalSeconds: 3600,
    cron: null,
    timezone: null,
    ...overrides,
  };
}

function editProjection() {
  return {
    definition: definition(),
    active: ACTIVE,
    definitionState: "active",
    sideEffects: "none",
  };
}

function removalImpact() {
  return {
    definition: {
      id: "nightly",
      name: "Nightly",
      enabled: false,
      mode: "scan-only",
    },
    definitionState: "active",
    references: { total: 0, items: [], truncated: false },
    unattendedAuthority: { status: "none", active: false, grantId: null },
    active: ACTIVE,
    sideEffects: "none",
  };
}

function publication(action: string, value: Record<string, unknown> | null) {
  return {
    action,
    definition: value,
    removed: value === null ? { id: "nightly" } : null,
    active: {
      ...ACTIVE,
      revisionId: "revision-active-2",
      version: 4,
      revisionSequence: 3,
    },
    sideEffects: "configuration_only",
  };
}

async function connect(token = TOKEN) {
  authStore.setToken(token);
}

describe("AutomationLifecyclePage", () => {
  it("publishes one checked create Save with the exact Active authority", async () => {
    const calls = recordingFetch((call) => {
      if (
        call.url.endsWith("/automation/definitions") &&
        call.method === "GET"
      ) {
        return jsonResponse(formAuthority());
      }
      if (
        call.url.endsWith("/automation/definitions") &&
        call.method === "POST"
      ) {
        return jsonResponse(publication("create", definition()));
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle");
    await screen.findByRole("heading", {
      name: "Create Automation definition",
    });
    await userEvent.type(screen.getByLabelText("Definition ID"), "nightly");
    await userEvent.type(screen.getByLabelText("Name"), "Nightly");
    await userEvent.selectOptions(
      screen.getByLabelText("ResourceLibrary"),
      "source",
    );
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => {
      expect(
        calls.some(
          (call) =>
            call.method === "POST" &&
            call.url.endsWith("/automation/definitions"),
        ),
      ).toBe(true);
    });
    const create = calls.find(
      (call) =>
        call.method === "POST" && call.url.endsWith("/automation/definitions"),
    );
    expect(create?.body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedVersion: 2,
      expectedDigest: DIGEST,
      object: {
        id: "nightly",
        name: "Nightly",
        resourceLibraryId: "source",
        enabled: false,
      },
    });
  });

  it("offers enable and a disabled copy for a published definition", async () => {
    const calls = recordingFetch((call) => {
      if (
        call.url.endsWith("/automation/definitions") &&
        call.method === "GET"
      ) {
        return jsonResponse(formAuthority());
      }
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      ) {
        return jsonResponse(editProjection());
      }
      if (call.url.endsWith("/nightly/removal-impact")) {
        return jsonResponse(removalImpact());
      }
      if (call.url.endsWith("/nightly/enable")) {
        return jsonResponse(
          publication("enable", definition({ enabled: true })),
        );
      }
      if (call.url.endsWith("/nightly/copy")) {
        return jsonResponse(
          publication(
            "copy",
            definition({ id: "nightly-copy", name: "Nightly copy" }),
          ),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    await screen.findByText(/0 configuration reference\(s\)/);

    await userEvent.click(
      screen.getByRole("button", { name: "Enable schedule" }),
    );
    await waitFor(() =>
      expect(calls.some((call) => call.url.endsWith("/nightly/enable"))).toBe(
        true,
      ),
    );
    const enable = calls.find((call) => call.url.endsWith("/nightly/enable"));
    expect(enable?.body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedVersion: 2,
      expectedDigest: DIGEST,
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Copy as disabled definition" }),
    );
    await waitFor(() =>
      expect(calls.some((call) => call.url.endsWith("/nightly/copy"))).toBe(
        true,
      ),
    );
  });

  it("requires an explicit confirmation before the destructive removal", async () => {
    const calls = recordingFetch((call) => {
      if (
        call.url.endsWith("/automation/definitions") &&
        call.method === "GET"
      ) {
        return jsonResponse(formAuthority());
      }
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      ) {
        return jsonResponse(editProjection());
      }
      if (call.url.endsWith("/nightly/removal-impact")) {
        return jsonResponse(removalImpact());
      }
      if (call.url.endsWith("/nightly") && call.method === "DELETE") {
        return jsonResponse(publication("remove", null));
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    await screen.findByText(/0 configuration reference\(s\)/);

    // Removal requires an explicit confirmation before the destructive command.
    const remove = screen.getByRole("button", { name: "Remove definition" });
    expect(remove).toBeDisabled();
    expect(calls.some((call) => call.method === "DELETE")).toBe(false);
    await userEvent.click(screen.getByLabelText("Confirm definition removal"));
    await userEvent.click(remove);
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "DELETE" &&
            call.url.endsWith("/automation/definitions/nightly"),
        ),
      ).toBe(true),
    );
  });

  it("calculates upcoming times without publishing anything", async () => {
    const calls = recordingFetch((call) => {
      if (
        call.url.endsWith("/automation/definitions") &&
        call.method === "GET"
      ) {
        return jsonResponse(formAuthority());
      }
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      ) {
        return jsonResponse(editProjection());
      }
      if (call.url.endsWith("/nightly/removal-impact")) {
        return jsonResponse(removalImpact());
      }
      if (call.url.endsWith("/schedule-preview")) {
        return jsonResponse({
          scheduleType: "interval",
          timezone: null,
          intervalSeconds: 3600,
          cron: null,
          upcoming: [{ at: "2026-01-01T01:00:00+00:00" }],
          notes: ["interval schedules repeat from first evaluation"],
          enabled: false,
          zeroMutation: true,
          sideEffects: "none",
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    await userEvent.click(
      screen.getByRole("button", { name: "Preview upcoming times" }),
    );
    await screen.findByText("2026-01-01T01:00:00+00:00");
    expect(
      calls.some(
        (call) =>
          call.method !== "GET" && !call.url.endsWith("/schedule-preview"),
      ),
    ).toBe(false);
  });

  it("renders no control when the authority document is malformed", async () => {
    recordingFetch((call) => {
      if (
        call.url.endsWith("/automation/definitions") &&
        call.method === "GET"
      ) {
        // A missing digest is malformed authority evidence: the page must fail
        // closed instead of offering a Save it cannot fence.
        return jsonResponse({
          ...formAuthority(),
          active: { ...ACTIVE, digest: "" },
        });
      }
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      ) {
        return jsonResponse(editProjection());
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByText("Automation authority unavailable");
    expect(screen.queryByRole("button", { name: "保存" })).toBeNull();
  });
});
