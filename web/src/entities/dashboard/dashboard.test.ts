import { describe, expect, it } from "vitest";
import {
  DashboardNormalizationError,
  isDashboardEmpty,
  normalizeDashboard,
} from "./dashboard";
import { dashboardModel, dashboardPayload } from "../../../tests/fixtures";

describe("normalizeDashboard", () => {
  it("normalizes the existing API snapshot into the frontend model", () => {
    expect(normalizeDashboard(dashboardPayload)).toEqual(dashboardModel);
  });

  it("ignores unknown extra fields", () => {
    const payload = { ...dashboardPayload, future_field: { nested: true } };
    expect(normalizeDashboard(payload)).toEqual(dashboardModel);
  });

  it.each([
    ["non-object payload", "not-an-object"],
    ["array payload", [dashboardPayload]],
    ["null payload", null],
    ["missing as_of", { ...dashboardPayload, as_of: undefined }],
    ["non-string as_of", { ...dashboardPayload, as_of: 42 }],
    ["missing files group", { ...dashboardPayload, files: undefined }],
    [
      "missing count field",
      {
        ...dashboardPayload,
        files: { ...(dashboardPayload.files as object), ready: undefined },
      },
    ],
    ["string count", { ...dashboardPayload, media_libraries: "3" }],
    ["negative count", { ...dashboardPayload, resource_libraries: -1 }],
    ["float count", { ...dashboardPayload, pending_confirmations: 1.5 }],
    ["non-array recent_failures", { ...dashboardPayload, recent_failures: {} }],
    [
      "incomplete recent failure",
      { ...dashboardPayload, recent_failures: [{ kind: "job" }] },
    ],
  ])("rejects %s", (_name, payload) => {
    expect(() => normalizeDashboard(payload)).toThrow(
      DashboardNormalizationError,
    );
  });
});

describe("isDashboardEmpty", () => {
  it("is empty when files, tasks and jobs are all zero", () => {
    const model = normalizeDashboard({
      ...dashboardPayload,
      files: { total: 0, ready: 0, unstable: 0, missing: 0, errors: 0 },
      tasks: {
        total: 0,
        pending: 0,
        running: 0,
        completed: 0,
        partial_success: 0,
        failed: 0,
        cancelled: 0,
        paused: 0,
      },
      jobs: {
        total: 0,
        pending: 0,
        running: 0,
        completed: 0,
        failed: 0,
        cancelled: 0,
      },
      recent_failures: [],
    });
    expect(isDashboardEmpty(model)).toBe(true);
  });

  it("is not empty when any recorded file, task or job exists", () => {
    expect(isDashboardEmpty(dashboardModel)).toBe(false);
  });
});
