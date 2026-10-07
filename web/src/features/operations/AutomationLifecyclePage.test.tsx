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

/** Stub the authenticated-principal read every lifecycle render now issues. */
function principalResponse(): Response {
  return jsonResponse({ principal_id: "lifecycle-operator" });
}

describe("AutomationLifecyclePage", () => {
  it("publishes one checked create Save with the exact Active authority", async () => {
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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

  it("targets the route definition after Copy navigation, not retained input", async () => {
    // P1-1 regression: open the origin, change its Name without saving, then
    // navigate to the copy route (as the real Copy action does). A later Save
    // must publish the route's definition (the copy), never apply the
    // origin's retained input.
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      if (
        call.url.endsWith("/automation/definitions/nightly-copy") &&
        call.method === "GET"
      ) {
        return jsonResponse({
          definition: definition({
            id: "nightly-copy",
            name: "Nightly copy",
          }),
          active: { ...ACTIVE, revisionId: "revision-active-2" },
          definitionState: "active",
          sideEffects: "none",
        });
      }
      if (
        call.url.endsWith("/automation/definitions/nightly-copy") &&
        call.method === "PUT"
      ) {
        return jsonResponse(
          publication("edit", definition({ id: "nightly-copy" })),
        );
      }
      if (call.url.endsWith("/nightly-copy/removal-impact")) {
        return jsonResponse(removalImpact());
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    // Change the origin's name without saving.
    await userEvent.type(screen.getByLabelText("Name"), " retained");
    // Navigate to the copy route the way Copy navigation does.
    await router.navigate({
      to: "/operations/automation/lifecycle/$definitionId",
      params: { definitionId: "nightly-copy" },
    });
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.url.endsWith("/automation/definitions/nightly-copy") &&
            call.method === "GET",
        ),
      ).toBe(true),
    );
    // The retained origin input is not applied to the copy route; the Save
    // publishes the copy's own loaded values under the copy identity.
    await screen.findByDisplayValue("Nightly copy");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "PUT" &&
            call.url.endsWith("/automation/definitions/nightly-copy"),
        ),
      ).toBe(true),
    );
    const save = calls.find(
      (call) =>
        call.method === "PUT" &&
        call.url.endsWith("/automation/definitions/nightly-copy"),
    );
    expect(save?.body).toMatchObject({
      object: { id: "nightly-copy", name: "Nightly copy" },
    });
    expect(
      calls.some(
        (call) =>
          call.method === "PUT" &&
          call.url.endsWith("/automation/definitions/nightly"),
      ),
    ).toBe(false);
  });

  it("publishes a cleared source scope instead of keeping the stored value", async () => {
    // P1-4 regression: the scope field is always submitted, so clearing it
    // and saving publishes the cleared scope.
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
        return jsonResponse({
          definition: definition({ sourceScope: "incoming" }),
          active: ACTIVE,
          definitionState: "active",
          sideEffects: "none",
        });
      }
      if (call.url.endsWith("/nightly/removal-impact")) {
        return jsonResponse(removalImpact());
      }
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "PUT"
      ) {
        return jsonResponse(publication("edit", definition()));
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    await screen.findByDisplayValue("incoming");
    await userEvent.clear(screen.getByLabelText("Relative source scope"));
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "PUT" &&
            call.url.endsWith("/automation/definitions/nightly"),
        ),
      ).toBe(true),
    );
    const save = calls.find(
      (call) =>
        call.method === "PUT" &&
        call.url.endsWith("/automation/definitions/nightly"),
    );
    expect(save?.body).toMatchObject({ object: { sourceScope: "" } });
  });

  it("accepts a fractional interval value", async () => {
    // P1-4 regression: interval seconds are finite positive numbers.
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
        return jsonResponse({
          definition: definition({ intervalSeconds: 1.5 }),
          active: ACTIVE,
          definitionState: "active",
          sideEffects: "none",
        });
      }
      if (call.url.endsWith("/nightly/removal-impact")) {
        return jsonResponse(removalImpact());
      }
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "PUT"
      ) {
        return jsonResponse(publication("edit", definition()));
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    await screen.findByDisplayValue("1.5");
    // The form accepts and saves the supported fractional value.
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "PUT" &&
            call.url.endsWith("/automation/definitions/nightly"),
        ),
      ).toBe(true),
    );
    const save = calls.find(
      (call) =>
        call.method === "PUT" &&
        call.url.endsWith("/automation/definitions/nightly"),
    );
    expect(save?.body).toMatchObject({ object: { intervalSeconds: 1.5 } });
  });

  it("offers daily and weekly schedule conveniences compiled to Cron", async () => {
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "PUT"
      ) {
        return jsonResponse(publication("edit", definition()));
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    await userEvent.selectOptions(
      screen.getByLabelText("Schedule"),
      "daily at 08:00",
    );
    // The daily convenience compiles to the exact Cron expression and keeps
    // the timezone field.
    await screen.findByDisplayValue("0 8 * * *");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "PUT" &&
            call.url.endsWith("/automation/definitions/nightly"),
        ),
      ).toBe(true),
    );
    const save = calls.find(
      (call) =>
        call.method === "PUT" &&
        call.url.endsWith("/automation/definitions/nightly"),
    );
    expect(save?.body).toMatchObject({
      object: { cron: "0 8 * * *", intervalSeconds: null },
    });
  });

  it("blocks Copy resubmission until an unknown outcome is reconciled", async () => {
    // P1-5 regression: a transport-lost Copy response is an unknown outcome.
    // The page retains the submitted intent, offers reconciliation from
    // durable evidence bound to the exact submitted authority, and never
    // allocates a second copy automatically.
    let copyCalls = 0;
    const copyIntentCalls: string[] = [];
    recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      if (call.url.endsWith("/nightly/copy")) {
        copyCalls += 1;
        // First request is committed but its response is lost; the reconciliation
        // read then proves the committed copy.
        if (copyCalls === 1) {
          throw new Error("network dropped");
        }
        return jsonResponse(
          publication("copy", definition({ id: "nightly-copy" })),
        );
      }
      if (call.url.includes("/nightly/copy-intent")) {
        // The reconciliation read carries the exact submitted intent: the
        // observed Active identity the lost Copy was submitted against.
        copyIntentCalls.push(call.url);
        return jsonResponse({
          definitionId: "nightly",
          sourcePresent: true,
          committed: true,
          committedDefinitionId: "nightly-copy",
          lastObserved: {
            auditId: "audit-1",
            action: "copy",
            occurredAt: "2026-01-01T00:00:00+00:00",
            candidateId: "nightly-copy",
            published: true,
          },
          observedCommands: 1,
          active: ACTIVE,
          sideEffects: "none",
          nextAction: "the copy committed durably",
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    await userEvent.click(
      screen.getByRole("button", { name: "Copy as disabled definition" }),
    );
    await screen.findByText(/outcome unknown/i);
    // The blocked state offers reconciliation, not a second Copy.
    await userEvent.click(
      screen.getByRole("button", { name: "Reconcile the submitted Copy" }),
    );
    await screen.findByText(/committed durably as nightly-copy/);
    // The reconciliation read carries the submitted intent's fence.
    expect(copyIntentCalls[0]).toContain("expectedRevisionId=");
    expect(copyIntentCalls[0]).toContain(
      `expectedDigest=${encodeURIComponent(DIGEST)}`,
    );
    // Opening the committed copy clears the intent.
    await userEvent.click(
      screen.getByRole("button", { name: "Open the committed copy" }),
    );
  });

  it("does not silently repin a retained candidate after the Active changes", async () => {
    // P1 regression: open a definition, change only its Name without saving.
    // Another legitimate writer publishes item limit 9. Refresh. The retained
    // form still shows the operator's input, but the Save command must use
    // the authority snapshot belonging to that retained input — never the
    // refreshed Active identity. The page surfaces the stale candidate and
    // blocks Save until the operator deliberately re-adopts the current
    // values, so a concurrent edit can never be silently overwritten.
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    // Change only the Name; the retained candidate is composed against the
    // observed Active revision.
    await userEvent.type(screen.getByLabelText("Name"), " retained");
    // Another writer publishes; every authority read after the original render
    // observes the newer revision.
    let authorityReads = 0;
    const secondAuthority = jsonResponse({
      ...formAuthority(),
      active: {
        ...ACTIVE,
        revisionId: "revision-active-2",
        version: 4,
        revisionSequence: 3,
        digest: "b".repeat(64),
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url === "/api/v1/auth/principal") {
          return principalResponse();
        }
        if (url.endsWith("/automation/definitions") && method === "GET") {
          authorityReads += 1;
          return secondAuthority.clone();
        }
        if (
          url.endsWith("/automation/definitions/nightly") &&
          method === "GET"
        ) {
          return jsonResponse(editProjection());
        }
        if (url.endsWith("/nightly/removal-impact")) {
          return jsonResponse(removalImpact());
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    // Refresh: the page re-reads the current authority.
    await userEvent.click(
      screen.getAllByRole("button", { name: "Refresh" })[0],
    );
    await waitFor(() => expect(authorityReads).toBeGreaterThanOrEqual(1));
    // The retained input is still visible (no silent value replacement), but
    // the page truthfully reports the stale candidate and blocks Save.
    expect(screen.getByLabelText("Name")).toHaveValue("Nightly retained");
    await screen.findByText(
      /unsaved edits are based on an older configuration/i,
    );
    const save = screen.getByRole("button", { name: "保存" });
    expect(save).toBeDisabled();
    // No command was published behind the operator's back.
    expect(
      calls.some((call) => call.method === "PUT" || call.method === "POST"),
    ).toBe(false);
    // The deliberate re-adoption replaces the candidate with the current
    // durable values and the current authority, then Save targets the route's
    // definition with the fresh fence.
    await userEvent.click(
      screen.getByRole("button", {
        name: "Review current values and re-adopt them",
      }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Name")).toHaveValue("Nightly"),
    );
    const freshSave = screen.getByRole("button", { name: "保存" });
    expect(freshSave).toBeEnabled();
  });

  it("keeps an unknown Copy outcome blocking after a real page reload", async () => {
    // P1 regression: a Copy whose response was lost stays unknown across a
    // reload. The intent persists in session storage (identity + observed
    // authority only), Copy stays blocked without any reconciliation, and the
    // reconciliation read carries the submitted intent's exact fence.
    sessionStorage.clear();
    const copyIntentCalls: string[] = [];
    recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return principalResponse();
      }
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
      if (call.url.includes("/nightly/copy-intent")) {
        copyIntentCalls.push(call.url);
        return jsonResponse({
          definitionId: "nightly",
          sourcePresent: true,
          committed: false,
          committedDefinitionId: null,
          lastObserved: {
            auditId: "audit-2",
            action: "copy",
            occurredAt: "2026-01-01T00:00:00+00:00",
            candidateId: "nightly-copy",
            published: false,
          },
          observedCommands: 1,
          active: ACTIVE,
          sideEffects: "none",
          nextAction: "no durable publication evidence",
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    // Simulate the persisted unknown outcome from a lost response before the
    // reload, exactly as the page writes it.
    sessionStorage.setItem(
      "mediaflow.operations.automation-copy-intent:lifecycle-operator",
      JSON.stringify({
        sourceId: "nightly",
        authority: {
          revisionId: ACTIVE_REVISION,
          version: ACTIVE.revisionSequence,
          digest: DIGEST,
        },
      }),
    );
    // A real page reload: fresh modules, fresh component state.
    cleanup();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    // Copy stays blocked without any reconciliation.
    const copy = screen.getByRole("button", {
      name: "Copy as disabled definition",
    });
    expect(copy).toBeDisabled();
    await screen.findByText(/outcome unknown/i);
    expect(
      screen.queryByRole("button", { name: "Reconcile the submitted Copy" }),
    ).toBeEnabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Reconcile the submitted Copy" }),
    );
    await screen.findByText(/No durable publication evidence/);
    expect(copyIntentCalls[0]).toContain(
      `expectedRevisionId=${encodeURIComponent(ACTIVE_REVISION)}`,
    );
    // Reconciliation resolved the unknown outcome; the block is lifted.
    await userEvent.click(
      screen.getByRole("button", {
        name: "Reconciled: no copy was published",
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Copy as disabled definition" }),
      ).toBeEnabled(),
    );
    sessionStorage.clear();
  });
});
