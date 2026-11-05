import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
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
      modes: ["automatic-organization"],
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
      enable: true,
      createEnabled: true,
    },
    actionReasons: {
      enable: null,
      createEnabled: null,
    },
  };
}

function definition(overrides: Record<string, unknown> = {}) {
  return {
    id: "nightly",
    name: "Nightly",
    enabled: false,
    resourceLibraryId: "source",
    mode: "automatic-organization",
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
      mode: "automatic-organization",
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
  it("publishes each confirmed save, returns to the list and continues after re-opening", async () => {
    let active = ACTIVE;
    let saved = definition();
    const commands: Call[] = [];
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") return principalResponse();
      if (
        call.url.endsWith("/automation/definitions") &&
        call.method === "GET"
      ) {
        return jsonResponse({ ...formAuthority(), active });
      }
      if (call.url.endsWith("/nightly/removal-impact"))
        return jsonResponse(removalImpact());
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      ) {
        return jsonResponse({ ...editProjection(), definition: saved, active });
      }
      if (
        call.method === "PUT" ||
        call.url.endsWith("/nightly/enable") ||
        call.url.endsWith("/nightly/disable")
      ) {
        commands.push(call);
        if (call.body?.expectedRevisionId !== active.revisionId) {
          return jsonResponse({ error: { code: "active_changed" } }, 409);
        }
        saved =
          call.method === "PUT"
            ? definition(call.body?.object as Record<string, unknown>)
            : { ...saved, enabled: call.url.endsWith("/nightly/enable") };
        active = {
          ...active,
          revisionId: `own-${commands.length}`,
          revisionSequence: active.revisionSequence + 1,
        };
        return jsonResponse({ ...publication("save", saved), active });
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp("/operations/automation/lifecycle/nightly");
    const name = await screen.findByLabelText(/任务名称/);
    await userEvent.clear(name);
    await userEvent.type(name, "Updated");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    // The confirmed Save returns to the original list: the card closes and
    // the saved row is what the list presents.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(saved.name).toBe("Updated"));
    // Re-opening the same definition continues editing against the confirmed
    // publication: the backfill is the saved value and the next command uses
    // its fence.
    await router.navigate({
      to: "/operations/automation/lifecycle/$definitionId",
      params: { definitionId: "nightly" },
    });
    const reopenedName = await screen.findByLabelText(/任务名称/);
    await waitFor(() => expect(reopenedName).toHaveValue("Updated"));
    // The shared enable switch only changes the form choice: the publication
    // is the same explicit Save, and no immediate enable command exists.
    await userEvent.click(screen.getByLabelText("启用定时计划"));
    expect(calls.some((call) => call.url.endsWith("/nightly/enable"))).toBe(
      false,
    );
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saved.enabled).toBe(true));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await router.navigate({
      to: "/operations/automation/lifecycle/$definitionId",
      params: { definitionId: "nightly" },
    });
    const secondOpenName = await screen.findByLabelText(/任务名称/);
    await waitFor(() => expect(secondOpenName).toHaveValue("Updated"));
    expect(screen.getByLabelText("启用定时计划")).toBeChecked();
    await userEvent.click(screen.getByLabelText("启用定时计划"));
    await userEvent.clear(secondOpenName);
    await userEvent.type(secondOpenName, "Updated again");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saved.name).toBe("Updated again"));
    await waitFor(() => expect(saved.enabled).toBe(false));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(commands.map((call) => call.body?.expectedRevisionId)).toEqual([
      ACTIVE_REVISION,
      "own-1",
      "own-2",
    ]);
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(3);
  });

  it("retains typing made while Save is pending and advances only its confirmed fence", async () => {
    let active = ACTIVE;
    let saved = definition();
    let completeSave: ((response: Response) => void) | undefined;
    recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") return principalResponse();
      if (call.url.endsWith("/automation/definitions") && call.method === "GET")
        return jsonResponse({ ...formAuthority(), active });
      if (call.url.endsWith("/nightly/removal-impact"))
        return jsonResponse(removalImpact());
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      )
        return jsonResponse({ ...editProjection(), definition: saved, active });
      return undefined;
    });
    const readFetch = globalThis.fetch;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PUT")
          return new Promise<Response>((resolve) => {
            completeSave = resolve;
          });
        return readFetch(input, init);
      }),
    );
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    const name = await screen.findByLabelText(/任务名称/);
    await userEvent.clear(name);
    await userEvent.type(name, "Submitted");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(completeSave).toBeDefined());
    await userEvent.clear(name);
    await userEvent.type(name, "Later typing");
    saved = definition({ name: "Submitted" });
    const confirmed = publication("save", saved);
    active = confirmed.active;
    completeSave?.(jsonResponse(confirmed));
    await screen.findByText(/已保存并保持启用|已保存，当前为停用状态/);
    expect(name).toHaveValue("Later typing");
    expect(screen.getByRole("button", { name: "保存" })).toBeEnabled();
    expect(screen.queryByText(/未保存的修改基于较旧的配置/)).toBeNull();
  });

  it("reconciles an unknown Save without replay and preserves later input", async () => {
    let active = ACTIVE;
    let saved = definition();
    let writes = 0;
    const fences: (string | undefined)[] = [];
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") return principalResponse();
      if (call.url.endsWith("/automation/definitions") && call.method === "GET")
        return jsonResponse({ ...formAuthority(), active });
      if (call.url.endsWith("/nightly/removal-impact"))
        return jsonResponse(removalImpact());
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      )
        return jsonResponse({ ...editProjection(), definition: saved, active });
      if (call.method === "PUT") {
        writes += 1;
        fences.push(call.body?.expectedRevisionId as string | undefined);
        saved = definition(call.body?.object as Record<string, unknown>);
        active = publication("save", saved).active;
        // Publication committed; its successful response was lost in transport.
        return jsonResponse({ error: { code: "response_lost" } }, 503);
      }
      if (call.url.endsWith("/nightly/publication-intent"))
        return jsonResponse({
          state: "published",
          publication: { ...publication("save", saved), active },
        });
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    const name = await screen.findByLabelText(/任务名称/);
    await userEvent.clear(name);
    await userEvent.type(name, "Submitted once");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await screen.findByText("发布结果待核对");
    expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
    await userEvent.clear(name);
    await userEvent.type(name, "Later input");
    await userEvent.click(screen.getByRole("button", { name: "核对本次发布" }));
    await screen.findByText(/已从持久审计核对本次发布/);
    // The proved publication cannot pose as the current saved state: the
    // response carries no current-state evidence, so the current state is
    // reported as unconfirmable, the later input is preserved, and the old
    // candidate is never handed a new baseline — Save stays blocked until the
    // operator explicitly re-reads the durable values.
    expect(name).toHaveValue("Later input");
    expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
    await screen.findByText(/未保存的修改基于较旧的配置/);
    await userEvent.click(
      screen.getByRole("button", { name: "核对当前值并采用" }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText(/任务名称/)).toHaveValue("Submitted once"),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "保存" })).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(writes).toBe(2));
    const read = calls.find((call) =>
      call.url.endsWith("/nightly/publication-intent"),
    );
    expect(read?.body?.expectedRevisionId).toBe(ACTIVE_REVISION);
    expect((read?.body?.object as Record<string, unknown>).name).toBe(
      "Submitted once",
    );
    // The deliberate next Save targets the current durable fence, never the
    // reconciled publication's own revision.
    expect(fences[1]).toBe("revision-active-2");
  });

  it("keeps enablement in the shared form and no longer offers lifecycle commands", async () => {
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
      if (call.method === "PUT") {
        return jsonResponse(
          publication(
            "edit",
            definition({
              ...(call.body?.object as Record<string, unknown>),
              enabled: true,
            }),
          ),
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    await screen.findByText(/0 个配置引用/);
    const dialog = within(screen.getByRole("dialog"));

    // The screenshot's lifecycle group is gone: no duplicate enable/copy
    // commands and no separate refresh button in its place. Copy lives on the
    // list next to 编辑 and removal keeps its own explicit entry.
    expect(dialog.queryByRole("heading", { name: "生命周期操作" })).toBeNull();
    expect(dialog.queryByRole("button", { name: "启用定时计划" })).toBeNull();
    expect(dialog.queryByRole("button", { name: "停用定时计划" })).toBeNull();
    expect(dialog.queryByRole("button", { name: "复制为停用定义" })).toBeNull();
    expect(dialog.queryByRole("button", { name: "刷新" })).toBeNull();
    expect(
      dialog.getByRole("heading", { name: "引用安全的移除定义" }),
    ).toBeVisible();

    // The shared switch changes only the form choice, then the explicit Save
    // publishes it through the same checked command.
    const toggle = dialog.getByLabelText("启用定时计划");
    expect(toggle).not.toBeChecked();
    await userEvent.click(toggle);
    expect(toggle).toBeChecked();
    expect(calls.some((call) => call.method !== "GET")).toBe(false);
    await userEvent.click(dialog.getByRole("button", { name: "保存" }));
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "PUT" &&
            call.url.endsWith("/automation/definitions/nightly"),
        ),
      ).toBe(true),
    );
    const save = calls.find((call) => call.method === "PUT");
    expect((save?.body?.object as Record<string, unknown>).enabled).toBe(true);
    expect(
      calls.some(
        (call) =>
          call.url.endsWith("/nightly/enable") ||
          call.url.endsWith("/nightly/disable") ||
          call.url.endsWith("/nightly/copy"),
      ),
    ).toBe(false);
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
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    await screen.findByText(/0 个配置引用/);

    // Removal requires an explicit confirmation before the destructive command.
    const remove = screen.getByRole("button", { name: "移除定义" });
    expect(remove).toBeDisabled();
    expect(calls.some((call) => call.method === "DELETE")).toBe(false);
    await userEvent.click(screen.getByLabelText(/我确认移除此定义/));
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
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    // The shared card calculates the backend upcoming times automatically and
    // renders them in the chosen timezone; the read is zero-mutation and
    // publishes nothing.
    await screen.findByText(/2026/);
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
    await screen.findByText("自动化配置不可用");
    expect(screen.queryByRole("button", { name: "保存" })).toBeNull();
  });

  it("reports corrupt published evidence as unavailable, never a draft candidate", async () => {
    // P1 regression: the backend now answers the affected lifecycle read with
    // the actionable configuration_unavailable state when a removed
    // definition's published revision is structurally corrupt. The page must
    // render that bounded recovery, never a never-published Draft candidate and
    // never an editable definition.
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
        return jsonResponse(
          {
            error: {
              code: "configuration_unavailable",
              message:
                "the durable publication evidence for Automation Task Definition 'nightly' could not be read completely",
              details: {
                reason: "historical_evidence_unavailable",
                durableState: "managed_active_unavailable",
                sideEffects: "none",
                retrySafe: true,
                nextAction:
                  "inspect configuration status and stage a replacement Draft",
              },
            },
          },
          503,
        );
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByText("无法读取该定义");
    // The bounded recovery is offered and the unavailable evidence is named.
    expect(
      screen.getByText(/读取定义失败（configuration_unavailable）/),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "保存" })).toBeNull();
    expect(screen.queryByLabelText(/任务名称/)).toBeNull();
    expect(screen.queryByText("draft-only")).toBeNull();
    // No command was published behind the operator's back.
    expect(
      calls.some((call) => call.method === "PUT" || call.method === "POST"),
    ).toBe(false);
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
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    // Change the origin's name without saving.
    await userEvent.type(screen.getByLabelText(/任务名称/), " retained");
    // Navigate to the copy route the way Copy navigation does. Leaving with
    // unsaved input is blocked until the operator makes the discard choice;
    // the blocked navigation keeps this route mounted.
    void router.navigate({
      to: "/operations/automation/lifecycle/$definitionId",
      params: { definitionId: "nightly-copy" },
    });
    await screen.findByRole("alertdialog");
    await userEvent.click(screen.getByRole("button", { name: "放弃修改" }));
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
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    await screen.findByDisplayValue("incoming");
    // The card's clear interaction switches the scope to the whole library;
    // the cleared value is exactly what the save publishes.
    await userEvent.selectOptions(screen.getByLabelText("来源范围"), "root");
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
    await screen.findByRole("heading", { name: "编辑自动化任务" });
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
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    await userEvent.selectOptions(screen.getByLabelText("执行频率"), "daily");
    // The daily convenience keeps its exact time control and compiles to the
    // same canonical Cron the backend already consumes.
    await screen.findByLabelText("每天运行时间");
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
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    // Change only the Name; the retained candidate is composed against the
    // observed Active revision.
    await userEvent.type(screen.getByLabelText(/任务名称/), " retained");
    // Another writer publishes; every authority read after the original render
    // observes the newer revision.
    let authorityReads = 0;
    let staleSaveAttempts = 0;
    const peerPublished = true;
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
          // The real edit projection always resolves the definition and its
          // own exact Active identity together, so after the peer published
          // the re-read carries the newer fence with the current values.
          return peerPublished
            ? jsonResponse({
                definition: definition(),
                active: {
                  ...ACTIVE,
                  revisionId: "revision-active-2",
                  version: 4,
                  revisionSequence: 3,
                  digest: "b".repeat(64),
                },
                definitionState: "active",
                sideEffects: "none",
              })
            : jsonResponse(editProjection());
        }
        if (url.endsWith("/nightly/removal-impact")) {
          return jsonResponse(removalImpact());
        }
        if (
          url.endsWith("/automation/definitions/nightly") &&
          method === "PUT"
        ) {
          // The backend's authoritative fence refuses the retained candidate.
          staleSaveAttempts += 1;
          return jsonResponse(
            { error: { code: "configuration_version_conflict" } },
            409,
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    // The explicit Save is refused by the newer Active. The page then re-reads
    // the current state (not a resubmission) and reports the stale candidate.
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(staleSaveAttempts).toBe(1));
    await waitFor(() => expect(authorityReads).toBeGreaterThanOrEqual(1));
    // The retained input is still visible (no silent value replacement), but
    // the page truthfully reports the stale candidate and blocks Save.
    expect(screen.getByLabelText(/任务名称/)).toHaveValue("Nightly retained");
    await screen.findByText(/未保存的修改基于较旧的配置/);
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
        name: "核对当前值并采用",
      }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText(/任务名称/)).toHaveValue("Nightly"),
    );
    const freshSave = screen.getByRole("button", { name: "保存" });
    expect(freshSave).toBeEnabled();
  });

  it("re-adoption re-reads the definition with its own fence and preserves the peer's fields", async () => {
    // P1 regression: open a definition (item limit 5), change only its Name
    // without saving. Another legitimate writer publishes item limit 9.
    // Refresh blocks Save; pressing re-adoption must load the *current*
    // durable values (limit 9) together with the fence they were read with —
    // never the cached limit 5 paired with the newer fence — so the operator's
    // Save preserves the peer's durable field.
    let peerPublished = false;
    const savedBodies: Record<string, unknown>[] = [];
    const dynamicFetch = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url === "/api/v1/auth/principal") {
          return principalResponse();
        }
        if (url.endsWith("/automation/definitions") && method === "GET") {
          // The authority read observes the peer's publication once it lands.
          return peerPublished
            ? jsonResponse({
                ...formAuthority(),
                active: {
                  ...ACTIVE,
                  revisionId: "revision-active-2",
                  version: 4,
                  revisionSequence: 3,
                  digest: "b".repeat(64),
                },
              })
            : jsonResponse(formAuthority());
        }
        if (
          url.endsWith("/automation/definitions/nightly") &&
          method === "GET"
        ) {
          // The edit projection resolves the definition and its own exact
          // Active identity together: the peer's limit 9 travels with the
          // peer's fence, so the reviewed values and the offered authority
          // always belong to the same publication.
          return peerPublished
            ? jsonResponse({
                definition: definition({ itemLimit: 9 }),
                active: {
                  ...ACTIVE,
                  revisionId: "revision-active-2",
                  version: 4,
                  revisionSequence: 3,
                  digest: "b".repeat(64),
                },
                definitionState: "active",
                sideEffects: "none",
              })
            : jsonResponse(editProjection());
        }
        if (url.endsWith("/nightly/removal-impact")) {
          return jsonResponse(removalImpact());
        }
        if (
          url.endsWith("/automation/definitions/nightly") &&
          method === "PUT"
        ) {
          const body = JSON.parse(String(init?.body)) as Record<
            string,
            unknown
          >;
          if (body.expectedRevisionId !== "revision-active-2") {
            return jsonResponse(
              { error: { code: "configuration_version_conflict" } },
              409,
            );
          }
          savedBodies.push(body);
          return jsonResponse(
            publication("edit", definition({ itemLimit: 9, name: "Nightly" })),
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      },
    );
    vi.stubGlobal("fetch", dynamicFetch);
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    expect(screen.getByLabelText("处理上限")).toHaveValue("10");
    // The operator changes only the Name; the candidate is composed against
    // the observed Active revision.
    await userEvent.type(screen.getByLabelText(/任务名称/), " retained");
    // Another legitimate writer publishes item limit 9.
    peerPublished = true;
    // The explicit Save is refused by the peer's newer Active; the page then
    // re-reads the current state instead of silently repinning the candidate.
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await screen.findByText(/未保存的修改基于较旧的配置/);
    await expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
    // Deliberate re-adoption re-reads the definition: the current durable
    // values (the peer's limit 9) are loaded with the fence they were read
    // with, and the operator's retained Name is discarded — the re-read is
    // the values the operator reviews before saving again.
    await userEvent.click(
      screen.getByRole("button", {
        name: "核对当前值并采用",
      }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("处理上限")).toHaveValue("9"),
    );
    await expect(screen.getByLabelText(/任务名称/)).toHaveValue("Nightly");
    const freshSave = screen.getByRole("button", { name: "保存" });
    await waitFor(() => expect(freshSave).toBeEnabled());
    await userEvent.click(freshSave);
    // The confirmed Save returns to the list: the card closes.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // The Save submitted the reviewed current values with the matching fence:
    // the peer's durable limit 9 survives; only the Name changed.
    expect(savedBodies).toHaveLength(1);
    const save = savedBodies[0] as {
      expectedRevisionId: string;
      expectedDigest: string;
      object: { itemLimit: number; name: string };
    };
    expect(save.expectedRevisionId).toBe("revision-active-2");
    expect(save.expectedDigest).toBe("b".repeat(64));
    expect(save.object.itemLimit).toBe(9);
    // The reviewed current Name is what Save publishes; the peer's durable
    // item limit 9 was preserved through the re-adoption.
    expect(save.object.name).toBe("Nightly");
  });

  it("re-opens only the confirmed save's own values and fence while the definition read is slow", async () => {
    // P1 regression (B49.2-03): enable and save from the edit card, then
    // immediately edit the same definition again and change only its Name.
    // The next definition read is slow, so the card is first rendered from the
    // cached projection. The backfilled values and the publication fence must
    // still be the confirmed save's own pair: the older cached fields joined to
    // the newer Active would silently publish the definition as disabled.
    let saved = definition();
    let active = ACTIVE;
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") return principalResponse();
      if (call.url.endsWith("/automation/definitions") && call.method === "GET")
        return jsonResponse({ ...formAuthority(), active });
      if (call.url.endsWith("/nightly/removal-impact"))
        return jsonResponse(removalImpact());
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      )
        return jsonResponse({ ...editProjection(), definition: saved, active });
      if (call.method === "PUT") {
        // The real authority refuses a candidate whose fence is not its own
        // observed Active; the fake enforces the same rule.
        if (call.body?.expectedRevisionId !== active.revisionId) {
          return jsonResponse({ error: { code: "active_changed" } }, 409);
        }
        saved = definition(call.body?.object as Record<string, unknown>);
        active = {
          ...active,
          revisionId: `confirmed-${calls.filter((item) => item.method === "PUT").length}`,
          revisionSequence: active.revisionSequence + 1,
          digest: "d".repeat(64),
        };
        return jsonResponse({ ...publication("save", saved), active });
      }
      return undefined;
    });
    await connect();
    const { router } = renderApp("/operations/automation/lifecycle/nightly");
    await screen.findByRole("heading", { name: "编辑自动化任务" });
    await userEvent.clear(screen.getByLabelText(/任务名称/));
    await userEvent.type(screen.getByLabelText(/任务名称/), "启用并保存");
    await userEvent.clear(screen.getByLabelText("处理上限"));
    await userEvent.type(screen.getByLabelText("处理上限"), "12");
    await userEvent.click(screen.getByLabelText("启用定时计划"));
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(saved.enabled).toBe(true));
    expect(saved.name).toBe("启用并保存");
    const confirmedRevision = active.revisionId;

    // The immediate re-open reads the definition slowly: everything the card
    // offers must come from the confirmed save's own pair, not the previous
    // projection joined to the newer Active.
    const readFetch = globalThis.fetch;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (
          init?.method === "GET" &&
          String(input).endsWith("/automation/definitions/nightly")
        ) {
          return new Promise<Response>(() => {});
        }
        return readFetch(input, init);
      }),
    );
    await router.navigate({
      to: "/operations/automation/lifecycle/$definitionId",
      params: { definitionId: "nightly" },
    });
    const reopened = await screen.findByLabelText(/任务名称/);
    await waitFor(() => expect(reopened).toHaveValue("启用并保存"));
    expect(screen.getByLabelText("处理上限")).toHaveValue("12");
    expect(screen.getByLabelText("启用定时计划")).toBeChecked();

    await userEvent.clear(reopened);
    await userEvent.type(reopened, "只改名称");
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saved.name).toBe("只改名称"));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const writes = calls.filter((call) => call.method === "PUT");
    expect(writes).toHaveLength(2);
    expect(writes[1]?.body?.expectedRevisionId).toBe(confirmedRevision);
    // Only the Name changed, so the enablement chosen in the previous confirmed
    // save survives the second Save.
    expect((writes[1]?.body?.object as Record<string, unknown>).enabled).toBe(
      true,
    );
    expect((writes[1]?.body?.object as Record<string, unknown>).itemLimit).toBe(
      12,
    );
    expect(saved.enabled).toBe(true);
  });

  it("never publishes an older definition read on a newer Active's fence", async () => {
    // P1 regression (B49.2-03): the authority read can legitimately observe a
    // newer Active than the definition projection the card backfilled from.
    // The exact values and their fence are one read, so the card can never
    // submit the older fields against the newer revision: it reports the stale
    // candidate, publishes nothing, and only a deliberate re-read of the
    // current values is published.
    const peerActive = {
      ...ACTIVE,
      revisionId: "revision-peer",
      version: 7,
      revisionSequence: 6,
      digest: "c".repeat(64),
    };
    let peerRead = false;
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") return principalResponse();
      if (call.url.endsWith("/automation/definitions") && call.method === "GET")
        return jsonResponse({ ...formAuthority(), active: peerActive });
      if (call.url.endsWith("/nightly/removal-impact"))
        return jsonResponse(removalImpact());
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      )
        return peerRead
          ? jsonResponse({
              ...editProjection(),
              definition: definition({ itemLimit: 9 }),
              active: peerActive,
            })
          : jsonResponse(editProjection());
      if (call.method === "PUT") {
        if (call.body?.expectedRevisionId !== peerActive.revisionId) {
          return jsonResponse({ error: { code: "active_changed" } }, 409);
        }
        return jsonResponse({
          ...publication(
            "save",
            definition(call.body?.object as Record<string, unknown>),
          ),
          active: peerActive,
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    const name = await screen.findByLabelText(/\u4efb\u52a1\u540d\u79f0/);
    await waitFor(() => expect(name).toHaveValue("Nightly"));
    // The values shown are the ones the projection read together with its own
    // Active; the newer authority Active is never joined to them.
    expect(screen.getByLabelText("\u5904\u7406\u4e0a\u9650")).toHaveValue("10");
    await userEvent.clear(name);
    await userEvent.type(name, "\u4e0d\u5e94\u53d1\u5e03");
    await screen.findByText(
      /\u672a\u4fdd\u5b58\u7684\u4fee\u6539\u57fa\u4e8e\u8f83\u65e7\u7684\u914d\u7f6e/,
    );
    expect(screen.getByRole("button", { name: "\u4fdd\u5b58" })).toBeDisabled();
    expect(calls.some((call) => call.method === "PUT")).toBe(false);
    // The deliberate re-read adopts the peer's current values with the Active
    // they were read with, so the next Save is fenced exactly.
    peerRead = true;
    await userEvent.click(
      screen.getByRole("button", {
        name: "\u6838\u5bf9\u5f53\u524d\u503c\u5e76\u91c7\u7528",
      }),
    );
    await waitFor(() =>
      expect(screen.getByLabelText("\u5904\u7406\u4e0a\u9650")).toHaveValue(
        "9",
      ),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "\u4fdd\u5b58" }),
      ).toBeEnabled(),
    );
    await userEvent.click(screen.getByRole("button", { name: "\u4fdd\u5b58" }));
    await waitFor(() =>
      expect(calls.some((call) => call.method === "PUT")).toBe(true),
    );
    const write = calls.find((call) => call.method === "PUT");
    expect(write?.body?.expectedRevisionId).toBe("revision-peer");
    expect((write?.body?.object as Record<string, unknown>).itemLimit).toBe(9);
  });

  it("keeps a candidate composed from a newer projection savable", async () => {
    // The definition projection can legitimately be re-read after a peer
    // publication while this dialog's authority query still reports the older
    // Active. Input composed against those newer values is current, so the page
    // must not report it as stale or block it: the Save carries the projection's
    // own fence and the peer's field survives.
    const newerActive = {
      ...ACTIVE,
      revisionId: "revision-newer",
      version: 5,
      revisionSequence: 4,
      digest: "e".repeat(64),
    };
    const calls = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") return principalResponse();
      if (call.url.endsWith("/automation/definitions") && call.method === "GET")
        return jsonResponse({ ...formAuthority(), active: ACTIVE });
      if (call.url.endsWith("/nightly/removal-impact"))
        return jsonResponse(removalImpact());
      if (
        call.url.endsWith("/automation/definitions/nightly") &&
        call.method === "GET"
      )
        return jsonResponse({
          ...editProjection(),
          definition: definition({ itemLimit: 9 }),
          active: newerActive,
        });
      if (call.method === "PUT") {
        return jsonResponse({
          ...publication(
            "save",
            definition(call.body?.object as Record<string, unknown>),
          ),
          active: newerActive,
        });
      }
      return undefined;
    });
    await connect();
    renderApp("/operations/automation/lifecycle/nightly");
    const name = await screen.findByLabelText(/\u4efb\u52a1\u540d\u79f0/);
    await waitFor(() => expect(name).toHaveValue("Nightly"));
    await userEvent.type(name, " retained");
    expect(
      screen.queryByText(
        /\u672a\u4fdd\u5b58\u7684\u4fee\u6539\u57fa\u4e8e\u8f83\u65e7\u7684\u914d\u7f6e/,
      ),
    ).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "\u4fdd\u5b58" }));
    await waitFor(() =>
      expect(calls.some((call) => call.method === "PUT")).toBe(true),
    );
    const write = calls.find((call) => call.method === "PUT");
    expect(write?.body?.expectedRevisionId).toBe("revision-newer");
    expect((write?.body?.object as Record<string, unknown>).itemLimit).toBe(9);
  });
});
