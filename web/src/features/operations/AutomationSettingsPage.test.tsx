/**
 * Automation engine settings: shared form, exact checked Save and honest
 * adoption readback (Task 43.4 S1–S3, S5, S7).
 *
 * The journeys here are the ones an operator actually performs: open
 * `自动化 → 全局设置`, see the published target *separately* from what each live
 * consumer adopted, edit the four fields, save once, and then read back the
 * independent adoption result. The documents mirror the exact Python API
 * projection (proved by tests/test_automation_settings_management.py and
 * tests/test_automation_settings_resident.py).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

type Json = Record<string, unknown>;

const TOKEN = "automation-settings-token";
const TARGET_REVISION = "revision-published-1";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: string | null;
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
        body: typeof init?.body === "string" ? init.body : null,
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

function field(fieldPath: string, label: string, overrides: Json = {}): Json {
  return {
    fieldPath,
    label,
    unit: "秒",
    valueType: "number",
    minimum: null,
    maximum: null,
    meaning: `${label}的实际含义`,
    notMeaning: "不是其他概念",
    consumer: null,
    integer: false,
    ...overrides,
  };
}

function instance(status: string, overrides: Json = {}): Json {
  return {
    instanceId: `worker-${status}`,
    liveness: status === "stopped" ? "stopped" : "live",
    status,
    effectiveValue: status === "adopted" ? 1.5 : null,
    publishedRevisionId: TARGET_REVISION,
    reportedRevisionId: status === "unreported" ? null : TARGET_REVISION,
    reportedAt: "2026-03-16T00:00:00+00:00",
    appliedFields:
      status === "unreported" ? [] : ["automation.workerPollSeconds"],
    overrideSource: status === "override" ? "cli" : null,
    durableState: status,
    nextAction: `next action for ${status}`,
    ...overrides,
  };
}

function settingsDocument(overrides: Json = {}): Json {
  const values = {
    "automation.maximumActiveJobs": 100,
    "automation.staleJobAgeSeconds": 3600,
    "automation.workerPollSeconds": 2,
    "automation.schedulerPollSeconds": 5,
  };
  return {
    sideEffects: "none",
    asOf: "2026-03-16T00:00:00+00:00",
    configRecheckSeconds: 5,
    authority: "MANAGED",
    canManage: true,
    fields: [
      field("automation.maximumActiveJobs", "并行任务上限", {
        valueType: "integer",
        integer: true,
        minimum: 1,
        maximum: 10000,
        unit: "个任务",
      }),
      field("automation.staleJobAgeSeconds", "任务失效判定时间", {
        valueType: "integer",
        integer: true,
        minimum: 60,
        maximum: 604800,
      }),
      field("automation.workerPollSeconds", "Worker 轮询间隔", {
        consumer: "worker",
      }),
      field("automation.schedulerPollSeconds", "调度器轮询间隔", {
        consumer: "scheduler",
      }),
    ],
    target: {
      revisionId: TARGET_REVISION,
      revisionVersion: 7,
      digest: "digest-published-1",
      values,
    },
    consumers: {
      worker: {
        service: "worker",
        field: "automation.workerPollSeconds",
        publishedValue: 2,
        adopted: false,
        instanceCount: 1,
        instances: [instance("unreported")],
      },
      scheduler: {
        service: "scheduler",
        field: "automation.schedulerPollSeconds",
        publishedValue: 5,
        adopted: false,
        instanceCount: 1,
        instances: [instance("pending")],
      },
      api: {
        service: "api",
        field: "automation.maximumActiveJobs",
        fields: [
          "automation.maximumActiveJobs",
          "automation.staleJobAgeSeconds",
        ],
        publishedValues: {
          "automation.maximumActiveJobs": 100,
          "automation.staleJobAgeSeconds": 3600,
        },
        adopted: false,
        basis: "api_local",
        instanceCount: 0,
        instances: [],
        explanation: "容量与失效判定由准入/观察边界读取当前 Active。",
      },
    },
    adoption: { consumers: 2, adoptedConsumers: 0, allAdopted: false },
    ...overrides,
  };
}

function automationInventory(): Json {
  return {
    items: [],
    total: 0,
    limit: 20,
    nextCursor: null,
    previousCursor: null,
    sideEffects: "none",
    query: { q: "", enabled: null, library: null, state: null, sort: "name" },
    inventoryCounts: { published: 0, enabled: 0, draftOnly: 0 },
    latestAdmittedRuns: {},
    metrics: {},
    actions: { create: { available: false, reason: "no permission" } },
  };
}

async function connect(pagePath: string) {
  authStore.setToken(TOKEN);
  renderApp(pagePath);
}

describe("Automation engine settings surface", () => {
  it("separates the published target from per-consumer adoption", async () => {
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        return jsonResponse(settingsDocument());
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");

    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    // The published target is stated as such, with its exact identity.
    expect(within(panel).getByText(TARGET_REVISION)).toBeTruthy();
    expect(within(panel).getAllByText(/尚未整体采用/).length).toBeGreaterThan(
      0,
    );
    // A published value is shown in the editable field.
    const worker = within(panel).getByLabelText(
      /Worker 轮询间隔/,
    ) as HTMLInputElement;
    expect(worker.value).toBe("2");
    // The unreported consumer is never rendered as adopted.
    const workerAdoption = screen.getByRole("region", {
      name: "Worker 轮询采用情况",
    });
    expect(within(workerAdoption).getByText("尚未上报采用")).toBeTruthy();
    expect(within(workerAdoption).queryByText("已采用当前发布值")).toBeNull();
  });

  it("submits exactly the four fields with the checked Active identity", async () => {
    const calls: Call[] = [];
    let saved = false;
    recordingFetch((call) => {
      calls.push(call);
      if (call.url.includes("/operations/automation/settings")) {
        if (call.method === "PUT") {
          saved = true;
          return jsonResponse(
            {
              published: true,
              unchanged: false,
              revisionId: "revision-published-2",
              sideEffects: "configuration_only",
              readback: settingsDocument({
                target: {
                  revisionId: "revision-published-2",
                  revisionVersion: 8,
                  digest: "digest-published-2",
                  values: {
                    "automation.maximumActiveJobs": 42,
                    "automation.staleJobAgeSeconds": 3600,
                    "automation.workerPollSeconds": 1.5,
                    "automation.schedulerPollSeconds": 5,
                  },
                },
              }),
            },
            201,
          );
        }
        return jsonResponse(saved ? settingsDocument() : settingsDocument());
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");

    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    const worker = within(panel).getByLabelText(
      /Worker 轮询间隔/,
    ) as HTMLInputElement;
    await userEvent.clear(jobs);
    await userEvent.type(jobs, "42");
    await userEvent.clear(worker);
    await userEvent.type(worker, "1.5");
    const save = within(panel).getByRole("button", {
      name: "保存引擎设置",
    });
    expect((save as HTMLButtonElement).disabled).toBe(false);
    await userEvent.click(save);

    await waitFor(() => {
      expect(within(panel).getByText(/已发布新的目标值/)).toBeTruthy();
    });
    const put = calls.find(
      (call) =>
        call.url.includes("/operations/automation/settings") &&
        call.method === "PUT",
    );
    expect(put).toBeTruthy();
    const body = JSON.parse(put!.body ?? "{}") as Json;
    expect(body["expectedRevisionId"]).toBe(TARGET_REVISION);
    expect(body["expectedDigest"]).toBe("digest-published-1");
    expect(body["settings"]).toEqual({
      "automation.maximumActiveJobs": 42,
      "automation.staleJobAgeSeconds": 3600,
      "automation.workerPollSeconds": 1.5,
      "automation.schedulerPollSeconds": 5,
    });
    // Exactly one submission for one click.
    expect(
      calls.filter(
        (call) =>
          call.url.includes("/operations/automation/settings") &&
          call.method === "PUT",
      ),
    ).toHaveLength(1);
  });

  it("a double click produces exactly one publication", async () => {
    const calls: Call[] = [];
    recordingFetch((call) => {
      calls.push(call);
      if (call.url.includes("/operations/automation/settings")) {
        if (call.method === "PUT") {
          return jsonResponse(
            {
              published: true,
              unchanged: false,
              revisionId: "revision-published-3",
              sideEffects: "configuration_only",
              readback: settingsDocument(),
            },
            201,
          );
        }
        return jsonResponse(settingsDocument());
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");
    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    await userEvent.clear(jobs);
    await userEvent.type(jobs, "60");
    const save = within(panel).getByRole("button", {
      name: "保存引擎设置",
    });
    // Two clicks in the same event loop must not create two publications.
    await Promise.all([userEvent.click(save), userEvent.click(save)]);
    await waitFor(() => {
      expect(within(panel).getByText(/已发布新的目标值/)).toBeTruthy();
    });
    expect(
      calls.filter(
        (call) =>
          call.url.includes("/operations/automation/settings") &&
          call.method === "PUT",
      ),
    ).toHaveLength(1);
  });

  it("does not truncate a fractional value with parseInt", async () => {
    const calls: Call[] = [];
    recordingFetch((call) => {
      calls.push(call);
      if (call.url.includes("/operations/automation/settings")) {
        if (call.method === "PUT") {
          return jsonResponse(
            {
              error: {
                code: "settings_fractional_integer",
                message: "must be whole",
                details: {
                  field: "automation.maximumActiveJobs",
                  durableState: "active_unchanged",
                  sideEffects: "none",
                  nextAction: "enter a whole number",
                },
              },
            },
            422,
          );
        }
        return jsonResponse(settingsDocument());
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");

    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    await userEvent.clear(jobs);
    await userEvent.type(jobs, "3.5");
    await userEvent.click(
      within(panel).getByRole("button", { name: "保存引擎设置" }),
    );

    await waitFor(() => {
      expect(
        within(panel).getByText(/保存未生效\(settings_fractional_integer\)/),
      ).toBeTruthy();
    });
    const put = calls.find(
      (call) =>
        call.url.includes("/operations/automation/settings") &&
        call.method === "PUT",
    );
    const body = JSON.parse(put!.body ?? "{}") as Json;
    // The real 3.5 reached the backend: the browser did not coerce it to 3.
    expect((body["settings"] as Json)["automation.maximumActiveJobs"]).toBe(
      3.5,
    );
    // The operator's input is preserved for correction.
    expect(jobs.value).toBe("3.5");
  });

  it("blocks further saves and offers reconciliation for an unknown outcome", async () => {
    let failNext = true;
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        if (call.method === "PUT") {
          if (failNext) {
            failNext = false;
            // A 500 with no durable-state statement: genuinely unknown.
            return jsonResponse(
              { error: { code: "internal_error", message: "internal" } },
              500,
            );
          }
          return jsonResponse({
            committed: false,
            sideEffects: "none",
            nextAction: "publish deliberately again",
          });
        }
        return jsonResponse(settingsDocument());
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");

    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    await userEvent.clear(jobs);
    await userEvent.type(jobs, "50");
    await userEvent.click(
      within(panel).getByRole("button", { name: "保存引擎设置" }),
    );

    await waitFor(() => {
      expect(within(panel).getByText(/提交结果未知/)).toBeTruthy();
    });
    // The save button stays disabled: an ambiguous mutation is never replayed.
    const save = within(panel).getByRole("button", {
      name: "保存引擎设置",
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    const reconcile = within(panel).getByRole("button", {
      name: "核实上次提交",
    });
    await userEvent.click(reconcile);
    await waitFor(() => {
      expect(within(panel).getByText(/核对完成/)).toBeTruthy();
    });
  });

  it("renders a stopped/overridden consumer as not adopted with its next action", async () => {
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        const document = settingsDocument();
        (document["consumers"] as Json)["worker"] = {
          service: "worker",
          field: "automation.workerPollSeconds",
          publishedValue: 2,
          adopted: false,
          instanceCount: 2,
          instances: [
            instance("override", { instanceId: "worker-override" }),
            instance("stopped", { instanceId: "worker-stopped" }),
          ],
        };
        return jsonResponse(document);
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");

    const workerAdoption = await screen.findByRole("region", {
      name: "Worker 轮询采用情况",
    });
    expect(
      within(workerAdoption).getByText("使用部署/命令行覆盖值"),
    ).toBeTruthy();
    expect(within(workerAdoption).getByText("进程已停止")).toBeTruthy();
    expect(within(workerAdoption).queryByText("已采用当前发布值")).toBeNull();
    expect(
      within(workerAdoption).getByText("next action for override"),
    ).toBeTruthy();
  });

  it("rejects a document that claims deployment adoption without instance evidence", async () => {
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        return jsonResponse(
          settingsDocument({
            adoption: { consumers: 2, adoptedConsumers: 2, allAdopted: true },
            consumers: {
              worker: {
                service: "worker",
                field: "automation.workerPollSeconds",
                publishedValue: 2,
                adopted: true,
                instanceCount: 0,
                instances: [],
              },
              scheduler: {
                service: "scheduler",
                field: "automation.schedulerPollSeconds",
                publishedValue: 5,
                adopted: true,
                instanceCount: 0,
                instances: [],
              },
            },
          }),
        );
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");

    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    // The fabricated collective flag is refused: the page still says this is
    // not a deployment-wide adoption.
    expect(within(panel).getAllByText(/尚未整体采用/).length).toBeGreaterThan(
      0,
    );
    expect(
      within(panel).queryByText("全部相关常驻进程都已采用当前发布值"),
    ).toBeNull();
  });

  it("shows setup guidance instead of a form when no Active exists", async () => {
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        return jsonResponse({
          sideEffects: "none",
          asOf: "2026-03-16T00:00:00+00:00",
          configRecheckSeconds: 5,
          authority: "MANAGED",
          canManage: true,
          fields: settingsDocument()["fields"],
          target: null,
          consumers: {},
          adoption: { consumers: 0, adoptedConsumers: 0, allAdopted: false },
          unavailable: {
            reason: "active_missing",
            durableState: "no_active_configuration",
            nextAction: "complete first setup and activate a configuration",
          },
        });
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");

    expect(
      await screen.findByText(
        "complete first setup and activate a configuration",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "保存引擎设置" })).toBeNull();
  });

  it("keeps the form read-only without manage-permission", async () => {
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        return jsonResponse(settingsDocument({ canManage: false }));
      }
      if (call.url.includes("/operations/automation/task-definitions")) {
        return jsonResponse(automationInventory());
      }
      if (call.url.includes("/operations/automation/metrics")) {
        return jsonResponse({ available: false });
      }
      if (call.url.includes("/operations/automation/records")) {
        return jsonResponse({ items: [], total: 0 });
      }
      return undefined;
    });
    await connect("/ui-v2/operations/automation?tab=settings");

    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    expect(within(panel).getByText(/当前账号没有管理配置的权限/)).toBeTruthy();
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    expect(jobs.disabled).toBe(true);
    const save = within(panel).getByRole("button", {
      name: "保存引擎设置",
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
  });
});
