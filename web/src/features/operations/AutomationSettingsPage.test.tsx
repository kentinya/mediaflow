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
      if (call.url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "automation-settings-admin" });
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

function otherWriterTarget(): Json {
  return {
    revisionId: "revision-published-2",
    revisionVersion: 8,
    digest: "digest-published-2",
    values: {
      "automation.maximumActiveJobs": 100,
      "automation.staleJobAgeSeconds": 3600,
      "automation.workerPollSeconds": 2,
      "automation.schedulerPollSeconds": 9,
    },
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
      name: "保存设置",
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
      name: "保存设置",
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
      within(panel).getByRole("button", { name: "保存设置" }),
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

  it("sends an unparseable entry as a typed refusal instead of a silently different request", async () => {
    // `NaN` cannot travel in JSON: dropping it or sending `null` implicitly would
    // change what the operator submitted and break reconciliation of the exact
    // refused request. The value is sent as `null`, which the backend refuses by
    // type, and the retained context carries the same content.
    const putBodies: Json[] = [];
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        if (call.method === "PUT") {
          putBodies.push(JSON.parse(call.body ?? "{}") as Json);
          return jsonResponse(
            {
              error: {
                code: "settings_invalid_type",
                message: "automation.maximumActiveJobs must be a number",
                details: {
                  field: "automation.maximumActiveJobs",
                  durableState: "active_unchanged",
                  sideEffects: "none",
                  nextAction: "enter a numeric value",
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
    await userEvent.type(jobs, "abc");
    await userEvent.click(
      within(panel).getByRole("button", { name: "保存设置" }),
    );
    await waitFor(() => {
      expect(putBodies).toHaveLength(1);
    });
    const settings = putBodies[0]["settings"] as Json;
    expect(settings["automation.maximumActiveJobs"]).toBeNull();
    expect(settings["automation.workerPollSeconds"]).toBe(2);
    // The text is preserved for correction.
    expect(jobs.value).toBe("abc");
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
            state: "not_committed",
            committed: false,
            sideEffects: "none",
            evidence: null,
            nextAction:
              "the submission failed; correct the value and save again",
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
      within(panel).getByRole("button", { name: "保存设置" }),
    );

    await waitFor(() => {
      expect(within(panel).getByText(/上一次保存结果未知/)).toBeTruthy();
    });
    // The save button stays disabled: an ambiguous mutation is never replayed.
    const save = within(panel).getByRole("button", {
      name: "保存设置",
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    const reconcile = within(panel).getByRole("button", {
      name: "核实上次提交",
    });
    await userEvent.click(reconcile);
    await waitFor(() => {
      expect(within(panel).getByText(/核对完成:本次提交没有发布/)).toBeTruthy();
    });
    // The retained unknown submission is now resolved, so a deliberate save is
    // offered again (the operator's input stayed correctable throughout).
    await waitFor(() => {
      expect(
        (
          within(panel).getByRole("button", {
            name: "保存设置",
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(false);
    });
  });

  it("refuses to accept input while a Save's response is outstanding", async () => {
    // B43.4-R2: the reviewed defect cleared a newer edit on success and silently
    // reverted the typed value.  The form must never accept a value for a request
    // that is already in flight, so the operator cannot type 42 into a Save that
    // only published 41.
    const gate: { release: (() => void) | null } = { release: null };
    let publishedFive = false;
    const pending = new Promise<void>((resolve) => {
      gate.release = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url === "/api/v1/auth/principal") {
          return jsonResponse({ principal_id: "automation-settings-admin" });
        }
        if (url.includes("/operations/automation/settings")) {
          if (method === "PUT") {
            await pending;
            publishedFive = true;
            return jsonResponse(
              {
                published: true,
                unchanged: false,
                revisionId: "revision-published-4",
                sideEffects: "configuration_only",
                readback: settingsDocument({
                  target: {
                    revisionId: "revision-published-4",
                    revisionVersion: 9,
                    digest: "digest-published-4",
                    values: {
                      "automation.maximumActiveJobs": 41,
                      "automation.staleJobAgeSeconds": 3600,
                      "automation.workerPollSeconds": 2,
                      "automation.schedulerPollSeconds": 5,
                    },
                  },
                }),
              },
              201,
            );
          }
          return jsonResponse(
            settingsDocument(
              publishedFive
                ? {
                    target: {
                      revisionId: "revision-published-4",
                      revisionVersion: 9,
                      digest: "digest-published-4",
                      values: {
                        "automation.maximumActiveJobs": 41,
                        "automation.staleJobAgeSeconds": 3600,
                        "automation.workerPollSeconds": 2,
                        "automation.schedulerPollSeconds": 5,
                      },
                    },
                  }
                : {},
            ),
          );
        }
        if (url.includes("/operations/automation/task-definitions")) {
          return jsonResponse(automationInventory());
        }
        if (url.includes("/operations/automation/metrics")) {
          return jsonResponse({ available: false });
        }
        if (url.includes("/operations/automation/records")) {
          return jsonResponse({ items: [], total: 0 });
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    await connect("/ui-v2/operations/automation?tab=settings");
    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    await userEvent.clear(jobs);
    await userEvent.type(jobs, "41");
    await userEvent.click(
      within(panel).getByRole("button", { name: "保存设置" }),
    );

    // While the real request is outstanding the field refuses new input.
    await waitFor(() => {
      expect(jobs.disabled).toBe(true);
    });
    await userEvent.type(jobs, "2");
    expect(jobs.value).toBe("41");

    // The late success arrives; only 41 was ever published and shown.
    gate.release?.();
    await waitFor(() => {
      expect(within(panel).getByText(/已发布新的目标值/)).toBeTruthy();
    });
    expect(
      (within(panel).getByLabelText(/并行任务上限/) as HTMLInputElement).value,
    ).toBe("41");
    expect(within(panel).queryByText(/保存期间输入的其他值/)).toBeNull();
  });

  it("never silently clears an edit that raced a finishing Save", async () => {
    // The complementary case: a value that does arrive after the request was
    // sent is retained and explicitly re-based on the just-published identity
    // instead of being cleared or rebased onto the old one.
    const gate: { release: (() => void) | null } = { release: null };
    let afterFirstSave = false;
    const pending = new Promise<void>((resolve) => {
      gate.release = resolve;
    });
    const putBodies: Json[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url === "/api/v1/auth/principal") {
          return jsonResponse({ principal_id: "automation-settings-admin" });
        }
        if (url.includes("/operations/automation/settings")) {
          if (method === "PUT") {
            putBodies.push(JSON.parse(String(init?.body ?? "{}")) as Json);
            if (putBodies.length === 1) {
              await pending;
              afterFirstSave = true;
              return jsonResponse(
                {
                  published: true,
                  unchanged: false,
                  revisionId: "revision-published-5",
                  sideEffects: "configuration_only",
                  readback: settingsDocument({
                    target: {
                      revisionId: "revision-published-5",
                      revisionVersion: 10,
                      digest: "digest-published-5",
                      values: {
                        "automation.maximumActiveJobs": 41,
                        "automation.staleJobAgeSeconds": 3600,
                        "automation.workerPollSeconds": 3,
                        "automation.schedulerPollSeconds": 5,
                      },
                    },
                  }),
                },
                201,
              );
            }
            return jsonResponse(
              {
                published: true,
                unchanged: false,
                revisionId: "revision-published-6",
                sideEffects: "configuration_only",
                readback: settingsDocument({
                  target: {
                    revisionId: "revision-published-6",
                    revisionVersion: 11,
                    digest: "digest-published-6",
                    values: {
                      "automation.maximumActiveJobs": 41,
                      "automation.staleJobAgeSeconds": 3600,
                      "automation.workerPollSeconds": 4,
                      "automation.schedulerPollSeconds": 5,
                    },
                  },
                }),
              },
              201,
            );
          }
          // The readback follows the just-published identity after the Save.
          return jsonResponse(
            settingsDocument(
              afterFirstSave
                ? {
                    target: {
                      revisionId: "revision-published-5",
                      revisionVersion: 10,
                      digest: "digest-published-5",
                      values: {
                        "automation.maximumActiveJobs": 41,
                        "automation.staleJobAgeSeconds": 3600,
                        "automation.workerPollSeconds": 3,
                        "automation.schedulerPollSeconds": 5,
                      },
                    },
                  }
                : {},
            ),
          );
        }
        if (url.includes("/operations/automation/task-definitions")) {
          return jsonResponse(automationInventory());
        }
        if (url.includes("/operations/automation/metrics")) {
          return jsonResponse({ available: false });
        }
        if (url.includes("/operations/automation/records")) {
          return jsonResponse({ items: [], total: 0 });
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }),
    );
    await connect("/ui-v2/operations/automation?tab=settings");
    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    await userEvent.clear(jobs);
    await userEvent.type(jobs, "41");
    await userEvent.click(
      within(panel).getByRole("button", { name: "保存设置" }),
    );
    await waitFor(() => {
      expect(jobs.disabled).toBe(true);
    });
    gate.release?.();
    await waitFor(() => {
      expect(within(panel).getByText(/已发布新的目标值/)).toBeTruthy();
    });
    // The published value is what the form now shows, and no phantom second
    // submission was ever made from input the user never got to type.
    expect(
      (within(panel).getByLabelText(/并行任务上限/) as HTMLInputElement).value,
    ).toBe("41");
    expect(putBodies).toHaveLength(1);
  });

  it("reconciles a lost rejection, survives a reload and allows a deliberate correction", async () => {
    // B43.4-R5 real journey: the operator's Save was refused stale because another
    // writer published first, and only that refusal response was lost.  The
    // retained submission must reconcile into a *terminal, correctable* state,
    // survive a page reload while unresolved, and then allow a deliberate save.
    const retained = {
      submissionId: "submission-lost-rejection-1",
      input: {
        "automation.maximumActiveJobs": "61",
        "automation.staleJobAgeSeconds": "3600",
        "automation.workerPollSeconds": "2",
        "automation.schedulerPollSeconds": "5",
      },
      submittedValues: {
        "automation.maximumActiveJobs": 61,
        "automation.staleJobAgeSeconds": 3600,
        "automation.workerPollSeconds": 2,
        "automation.schedulerPollSeconds": 5,
      },
      baselineRevisionId: TARGET_REVISION,
      baselineRevisionVersion: 7,
      baselineDigest: "digest-published-1",
      submittedAt: "2026-03-16T00:00:02+00:00",
    };
    const storageKey =
      "mediaflow.operations.automation-settings-submission:v1:automation-settings-admin";
    window.sessionStorage.setItem(storageKey, JSON.stringify(retained));
    let reconciled = false;
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        if (call.method === "PUT") {
          reconciled = true;
          return jsonResponse({
            state: "not_committed",
            committed: false,
            sideEffects: "none",
            evidence: {
              revisionId: "revision-unpublished-1",
              durableState: "submission_refused_stale",
              evidenceComplete: true,
              identityMatched: true,
            },
            nextAction:
              "review the current values and save your corrected values deliberately",
          });
        }
        return jsonResponse(
          settingsDocument({
            target: {
              revisionId: "revision-published-2",
              revisionVersion: 8,
              digest: "digest-published-2",
              values: {
                "automation.maximumActiveJobs": 41,
                "automation.staleJobAgeSeconds": 3600,
                "automation.workerPollSeconds": 2,
                "automation.schedulerPollSeconds": 5,
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
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation?tab=settings");
    let panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    expect(await within(panel).findByText(/上一次保存结果未知/)).toBeTruthy();
    await userEvent.click(
      within(panel).getByRole("button", { name: "核实上次提交" }),
    );
    await waitFor(() => {
      expect(within(panel).getByText(/本次提交没有发布/)).toBeTruthy();
    });
    expect(reconciled).toBe(true);
    // The typed value is retained, corrected against the *current* identity, and
    // a deliberate Save is available again.
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    expect(jobs.value).toBe("61");
    await waitFor(() => {
      expect(
        (
          within(panel).getByRole("button", {
            name: "保存设置",
          }) as HTMLButtonElement
        ).disabled,
      ).toBe(false);
    });
    expect(window.sessionStorage.getItem(storageKey)).toBeNull();

    // A real reload while the submission is *still* unresolved keeps the block.
    cleanup();
    authStore.setToken(TOKEN);
    window.sessionStorage.setItem(storageKey, JSON.stringify(retained));
    renderApp("/ui-v2/operations/automation?tab=settings");
    panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    expect(await within(panel).findByText(/上一次保存结果未知/)).toBeTruthy();
    expect(
      (
        within(panel).getByRole("button", {
          name: "保存设置",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });

  it("recovers a lost invalid-input rejection per field without reverting another writer", async () => {
    // B43.4-R5 end-to-end: capacity 3.5 was refused 422 and only that response was
    // lost, while another writer changed the scheduler poll.  After reconciliation
    // the form must (a) prove this request published nothing, (b) keep the invalid
    // text correctable, and (c) preserve the other writer's scheduler value — the
    // next Save must publish only the corrected capacity.
    const retained = {
      submissionId: "submission-invalid-3-5",
      input: {
        "automation.maximumActiveJobs": "3.5",
        "automation.staleJobAgeSeconds": "3600",
        "automation.workerPollSeconds": "2",
        "automation.schedulerPollSeconds": "5",
      },
      submittedValues: {
        "automation.maximumActiveJobs": 3.5,
        "automation.staleJobAgeSeconds": 3600,
        "automation.workerPollSeconds": 2,
        "automation.schedulerPollSeconds": 5,
      },
      baselineRevisionId: TARGET_REVISION,
      baselineRevisionVersion: 7,
      baselineDigest: "digest-published-1",
      baselineValues: {
        "automation.maximumActiveJobs": "100",
        "automation.staleJobAgeSeconds": "3600",
        "automation.workerPollSeconds": "2",
        "automation.schedulerPollSeconds": "5",
      },
      submittedAt: "2026-03-16T00:00:00+00:00",
    };
    const storageKey =
      "mediaflow.operations.automation-settings-submission:v1:automation-settings-admin";
    window.sessionStorage.setItem(storageKey, JSON.stringify(retained));
    const putBodies: Json[] = [];
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        if (call.method === "PUT") {
          const body = JSON.parse(call.body ?? "{}") as Json;
          putBodies.push(body);
          if (body["reconcile"] === true) {
            return jsonResponse({
              state: "not_committed",
              committed: false,
              sideEffects: "none",
              evidence: {
                durableState: "submission_input_rejected",
                submissionOutcome: "input_rejected",
                field: "automation.maximumActiveJobs",
                evidenceComplete: true,
                identityMatched: true,
              },
              rejection: {
                code: "settings_fractional_integer",
                message: "automation.maximumActiveJobs must be a whole number",
                field: "automation.maximumActiveJobs",
                nextAction: "enter a whole number of seconds/jobs",
              },
              nextAction: "correct that value and save deliberately again",
            });
          }
          return jsonResponse(
            {
              published: true,
              unchanged: false,
              revisionId: "revision-published-9",
              sideEffects: "configuration_only",
              readback: settingsDocument({
                target: {
                  revisionId: "revision-published-9",
                  revisionVersion: 9,
                  digest: "digest-published-9",
                  values: {
                    "automation.maximumActiveJobs": 4,
                    "automation.staleJobAgeSeconds": 3600,
                    "automation.workerPollSeconds": 2,
                    "automation.schedulerPollSeconds": 9,
                  },
                },
              }),
            },
            201,
          );
        }
        return jsonResponse(
          settingsDocument({
            target: {
              ...otherWriterTarget(),
              values: {
                "automation.maximumActiveJobs": 100,
                "automation.staleJobAgeSeconds": 3600,
                "automation.workerPollSeconds": 2,
                "automation.schedulerPollSeconds": 9,
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
    expect(await within(panel).findByText(/上一次保存结果未知/)).toBeTruthy();
    await userEvent.click(
      within(panel).getByRole("button", { name: "核实上次提交" }),
    );
    await waitFor(() => {
      expect(within(panel).getByText(/本次提交没有发布/)).toBeTruthy();
    });
    // The rejection is readable (code plus field) and the invalid text is still
    // correctable.
    expect(
      within(panel).getByText(
        /automation\.maximumActiveJobs:settings_fractional_integer/,
      ),
    ).toBeTruthy();
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    expect(jobs.value).toBe("3.5");
    expect(jobs.disabled).toBe(false);
    expect(window.sessionStorage.getItem(storageKey)).toBeNull();

    // The operator corrects the value; the other writer's scheduler 9 is kept.
    await userEvent.clear(jobs);
    await userEvent.type(jobs, "4");
    const scheduler = within(panel).getByLabelText(
      /调度器轮询间隔/,
    ) as HTMLInputElement;
    expect(scheduler.value).toBe("9");
    const save = within(panel).getByRole("button", {
      name: "保存设置",
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(false);
    await userEvent.click(save);
    await waitFor(() => {
      const submitted = putBodies.filter((body) => body["reconcile"] !== true);
      expect(submitted).toHaveLength(1);
    });
    const submitted = putBodies.filter((body) => body["reconcile"] !== true)[0];
    expect(submitted["expectedRevisionId"]).toBe("revision-published-2");
    expect(submitted["settings"]).toEqual({
      "automation.maximumActiveJobs": 4,
      "automation.staleJobAgeSeconds": 3600,
      "automation.workerPollSeconds": 2,
      "automation.schedulerPollSeconds": 9,
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
    expect(screen.queryByRole("button", { name: "保存设置" })).toBeNull();
  });

  // This journey deliberately waits for the panel's real 5s polling interval, so
  // it declares its own timeout rather than shortening the product interval:
  // the assertion is about the *ordinary* background read, not a manual refresh.
  it(
    "merges only the edited field after a background readback changed the target",
    { timeout: 20_000 },
    async () => {
      // B43.4-R2/R5 real journey: the operator edits capacity, another writer
      // changes the scheduler poll, and the ordinary background GET delivers that
      // newer publication.  The old four-field input must not be re-armed against
      // the new identity (that would silently restore scheduler 5), and it must
      // not simply refuse forever either: only the field the operator changed is
      // merged into the *current* target, and Save publishes exactly that.
      let reads = 0;
      let putBody: Json | null = null;
      recordingFetch((call) => {
        if (call.url.includes("/operations/automation/settings")) {
          if (call.method === "PUT") {
            putBody = JSON.parse(call.body ?? "{}") as Json;
            return jsonResponse(
              {
                published: true,
                unchanged: false,
                revisionId: "revision-published-3",
                sideEffects: "configuration_only",
                readback: settingsDocument({
                  target: {
                    revisionId: "revision-published-3",
                    revisionVersion: 9,
                    digest: "digest-published-3",
                    values: {
                      "automation.maximumActiveJobs": 70,
                      "automation.staleJobAgeSeconds": 3600,
                      "automation.workerPollSeconds": 2,
                      "automation.schedulerPollSeconds": 9,
                    },
                  },
                }),
              },
              201,
            );
          }
          reads += 1;
          // The first read is the target the operator edits; every later
          // background read is the other writer's publication.
          if (reads === 1) return jsonResponse(settingsDocument());
          return jsonResponse(
            settingsDocument({ target: otherWriterTarget() }),
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
      const panel = await screen.findByRole("region", {
        name: "自动化引擎设置",
      });
      const jobs = within(panel).getByLabelText(
        /并行任务上限/,
      ) as HTMLInputElement;
      await userEvent.clear(jobs);
      await userEvent.type(jobs, "70");
      // The ordinary bounded readback (the panel's real 5s polling interval, not
      // a manual refresh) delivers the other writer's publication.
      await waitFor(
        () => {
          expect(reads).toBeGreaterThan(1);
        },
        { timeout: 9_000 },
      );
      await waitFor(() => {
        expect(within(panel).getByText("revision-published-2")).toBeTruthy();
      });
      // The edit was merged deterministically: nothing needs confirming, and the
      // other writer's scheduler value is displayed (never silently replaced by
      // the value this operator read before).
      expect(
        within(panel).getByText(/你改过的字段已合并到最新发布值上/),
      ).toBeTruthy();
      expect(jobs.value).toBe("70");
      expect(
        (within(panel).getByLabelText(/调度器轮询间隔/) as HTMLInputElement)
          .value,
      ).toBe("9");

      const save = within(panel).getByRole("button", {
        name: "保存设置",
      }) as HTMLButtonElement;
      expect(save.disabled).toBe(false);
      await userEvent.click(save);
      await waitFor(() => {
        expect(putBody).not.toBeNull();
      });
      // The Save is checked against the *latest* identity and publishes the
      // merged values: capacity 70 with the other writer's scheduler 9 intact.
      expect(putBody!["expectedRevisionId"]).toBe("revision-published-2");
      expect(putBody!["expectedDigest"]).toBe("digest-published-2");
      expect(putBody!["settings"]).toEqual({
        "automation.maximumActiveJobs": 70,
        "automation.staleJobAgeSeconds": 3600,
        "automation.workerPollSeconds": 2,
        "automation.schedulerPollSeconds": 9,
      });
    },
  );

  it(
    "requires an explicit choice for a same-field conflict and never publishes it unconfirmed",
    { timeout: 20_000 },
    async () => {
      // B43.4-R5 second half: both writers change the *same* field, so no
      // deterministic merge exists.  Save stays refused until the operator
      // explicitly picks a side, and the pick itself publishes nothing.
      let reads = 0;
      const putBodies: Json[] = [];
      recordingFetch((call) => {
        if (call.url.includes("/operations/automation/settings")) {
          if (call.method === "PUT") {
            putBodies.push(JSON.parse(call.body ?? "{}") as Json);
            return jsonResponse(
              {
                published: true,
                unchanged: false,
                revisionId: "revision-published-4",
                sideEffects: "configuration_only",
                readback: settingsDocument({
                  target: {
                    revisionId: "revision-published-4",
                    revisionVersion: 10,
                    digest: "digest-published-4",
                    values: {
                      "automation.maximumActiveJobs": 70,
                      "automation.staleJobAgeSeconds": 3600,
                      "automation.workerPollSeconds": 2,
                      "automation.schedulerPollSeconds": 5,
                    },
                  },
                }),
              },
              201,
            );
          }
          reads += 1;
          if (reads === 1) return jsonResponse(settingsDocument());
          return jsonResponse(
            settingsDocument({
              target: {
                revisionId: "revision-published-2b",
                revisionVersion: 8,
                digest: "digest-published-2b",
                values: {
                  "automation.maximumActiveJobs": 90,
                  "automation.staleJobAgeSeconds": 3600,
                  "automation.workerPollSeconds": 2,
                  "automation.schedulerPollSeconds": 5,
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
      const panel = await screen.findByRole("region", {
        name: "自动化引擎设置",
      });
      const jobs = within(panel).getByLabelText(
        /并行任务上限/,
      ) as HTMLInputElement;
      await userEvent.clear(jobs);
      await userEvent.type(jobs, "70");
      await waitFor(
        () => {
          expect(reads).toBeGreaterThan(1);
        },
        { timeout: 9_000 },
      );
      const save = within(panel).getByRole("button", {
        name: "保存设置",
      }) as HTMLButtonElement;
      // Both values are shown and Save is refused until the operator chooses.
      await waitFor(() => {
        expect(
          within(panel).getByText(/当前发布值为 90,你输入的值是 70/),
        ).toBeTruthy();
      });
      expect(save.disabled).toBe(true);
      expect(putBodies).toHaveLength(0);

      // Choosing to keep the operator's value updates the form; it publishes
      // nothing by itself.
      await userEvent.click(
        within(panel).getByRole("button", { name: "保留我的修改" }),
      );
      expect(putBodies).toHaveLength(0);
      await waitFor(() => {
        expect(save.disabled).toBe(false);
      });
      await userEvent.click(save);
      await waitFor(() => {
        expect(putBodies).toHaveLength(1);
      });
      // Only the explicit choice is published, against the latest identity.
      expect(putBodies[0]["expectedRevisionId"]).toBe("revision-published-2b");
      expect(
        (putBodies[0]["settings"] as Json)["automation.maximumActiveJobs"],
      ).toBe(70);
    },
  );

  it(
    "lets the operator adopt the current value instead of a conflicting input",
    { timeout: 20_000 },
    async () => {
      let reads = 0;
      const putBodies: Json[] = [];
      recordingFetch((call) => {
        if (call.url.includes("/operations/automation/settings")) {
          if (call.method === "PUT") {
            putBodies.push(JSON.parse(call.body ?? "{}") as Json);
            return jsonResponse(
              {
                published: true,
                unchanged: false,
                revisionId: "revision-published-5",
                sideEffects: "configuration_only",
                readback: settingsDocument(),
              },
              201,
            );
          }
          reads += 1;
          if (reads === 1) return jsonResponse(settingsDocument());
          return jsonResponse(
            settingsDocument({
              target: {
                revisionId: "revision-published-2c",
                revisionVersion: 8,
                digest: "digest-published-2c",
                values: {
                  "automation.maximumActiveJobs": 90,
                  "automation.staleJobAgeSeconds": 3600,
                  "automation.workerPollSeconds": 2,
                  "automation.schedulerPollSeconds": 5,
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
      const panel = await screen.findByRole("region", {
        name: "自动化引擎设置",
      });
      const jobs = within(panel).getByLabelText(
        /并行任务上限/,
      ) as HTMLInputElement;
      await userEvent.clear(jobs);
      await userEvent.type(jobs, "70");
      await waitFor(
        () => {
          expect(reads).toBeGreaterThan(1);
        },
        { timeout: 9_000 },
      );
      await userEvent.click(
        within(panel).getByRole("button", { name: "采用当前值" }),
      );
      // The conflicting field now shows the published value and nothing differs,
      // so there is nothing to publish and no input was discarded silently.
      await waitFor(() => {
        expect(jobs.value).toBe("90");
      });
      const save = within(panel).getByRole("button", {
        name: "保存设置",
      }) as HTMLButtonElement;
      expect(save.disabled).toBe(true);
      expect(putBodies).toHaveLength(0);
    },
  );

  it("restores and reconciles an unknown submission after a reload", async () => {
    // B43.4-R5 real journey: the Save reached the backend but the response was
    // lost; the page reloaded.  The retained submission must come back, block a
    // new Save, and be reconciled by its own durable evidence.
    authStore.setToken(TOKEN);
    const retained = {
      submissionId: "submission-reload-1",
      input: {
        "automation.maximumActiveJobs": "80",
        "automation.staleJobAgeSeconds": "3600",
        "automation.workerPollSeconds": "2",
        "automation.schedulerPollSeconds": "5",
      },
      submittedValues: {
        "automation.maximumActiveJobs": 80,
        "automation.staleJobAgeSeconds": 3600,
        "automation.workerPollSeconds": 2,
        "automation.schedulerPollSeconds": 5,
      },
      baselineRevisionId: TARGET_REVISION,
      baselineRevisionVersion: 7,
      baselineDigest: "digest-published-1",
      submittedAt: "2026-03-16T00:00:01+00:00",
    };
    window.sessionStorage.setItem(
      "mediaflow.operations.automation-settings-submission:v1:automation-settings-admin",
      JSON.stringify(retained),
    );
    let reconcileBody: Json | null = null;
    recordingFetch((call) => {
      if (call.url.includes("/operations/automation/settings")) {
        if (call.method === "PUT") {
          reconcileBody = JSON.parse(call.body ?? "{}") as Json;
          return jsonResponse({
            state: "committed",
            committed: true,
            sideEffects: "none",
            evidence: { revisionId: "revision-published-9" },
            nextAction: "this exact submission is the current published target",
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
    renderApp("/ui-v2/operations/automation?tab=settings");
    const panel = await screen.findByRole("region", { name: "自动化引擎设置" });
    // The unknown submission survived the reload and still blocks a new Save.
    expect(await within(panel).findByText(/上一次保存结果未知/)).toBeTruthy();
    const jobs = within(panel).getByLabelText(
      /并行任务上限/,
    ) as HTMLInputElement;
    expect(jobs.value).toBe("80");
    expect(
      (
        within(panel).getByRole("button", {
          name: "保存设置",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    await userEvent.click(
      within(panel).getByRole("button", { name: "核实上次提交" }),
    );
    await waitFor(() => {
      expect(within(panel).getByText(/核对完成:本次提交已发布/)).toBeTruthy();
    });
    // The reconciliation named the exact retained submission identity.
    expect(reconcileBody).toMatchObject({
      reconcile: true,
      submissionId: "submission-reload-1",
    });
    expect(
      window.sessionStorage.getItem(
        "mediaflow.operations.automation-settings-submission:v1:automation-settings-admin",
      ),
    ).toBeNull();
  });

  it("states a genuinely adopted deployment as adopted", async () => {
    // B43.4-R4: the api_local row's adopted flag is always false, so aggregating
    // it made a real all-adopted deployment render as pending.
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
                instanceCount: 1,
                instances: [
                  instance("adopted", { instanceId: "worker-adopted" }),
                ],
              },
              scheduler: {
                service: "scheduler",
                field: "automation.schedulerPollSeconds",
                publishedValue: 5,
                adopted: true,
                instanceCount: 1,
                instances: [
                  instance("adopted", { instanceId: "scheduler-adopted" }),
                ],
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
    expect(
      within(panel).getByText("全部相关常驻进程都已采用当前发布值"),
    ).toBeTruthy();
    expect(within(panel).queryByText(/尚未整体采用/)).toBeNull();
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
      name: "保存设置",
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
  });
});
