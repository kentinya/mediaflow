import { describe, expect, it } from "vitest";
import {
  baselineValues,
  booleanStateLabel,
  collectGroupEdits,
  editableFields,
  fieldChanged,
  groupChanged,
  parseSettingInput,
  readSettingGroups,
  serializeSettingValue,
} from "./configuration-settings";

const sections = {
  Localization: {
    locale: {
      label: "System locale",
      value: "zh-CN",
      valueType: "string",
      boundary: "restart_required",
    },
    timezone: {
      label: "System timezone",
      value: "Asia/Shanghai",
      valueType: "string",
      boundary: "restart_required",
    },
  },
  Database: {
    "persistence.databasePath": {
      label: "Database location",
      value: "/data/mediaflow.sqlite3",
      valueType: "string",
      boundary: "bootstrap_immutable",
    },
    historyPath: {
      label: "History file path",
      value: null,
      valueType: "string",
      boundary: "restart_required",
    },
  },
  Automation: {
    "automation.workerPollSeconds": {
      label: "Worker poll interval",
      value: 2,
      valueType: "number",
      boundary: "hot_consumed",
    },
  },
  Logging: {
    "operationalLogging.enabled": {
      label: "Operational logging enabled",
      value: false,
      valueType: "boolean",
      boundary: "hot_consumed",
    },
    "operationalLogging.minimumLevel": {
      label: "Operational logging level",
      value: "INFO",
      valueType: "enum",
      boundary: "hot_consumed",
    },
    "operationalLogging.retentionDays": {
      label: "Log retention",
      value: 30,
      valueType: "integer",
      boundary: "hot_consumed",
    },
    "operationalLogging.maximumRecords": {
      label: "Maximum log records",
      value: 10000,
      valueType: "integer",
      boundary: "hot_consumed",
    },
  },
  Workflow: {
    "workflowRetry.enabled": {
      label: "Workflow retry enabled",
      value: null,
      valueType: "boolean",
      boundary: "hot_consumed",
    },
    "workflowRetry.maxAttempts": {
      label: "Maximum retry attempts",
      value: 3,
      valueType: "integer",
      boundary: "hot_consumed",
    },
    "workflowRetry.baseDelaySeconds": {
      label: "Base delay",
      value: 1,
      valueType: "number",
      boundary: "hot_consumed",
    },
    "workflowRetry.maxDelaySeconds": {
      label: "Maximum delay",
      value: 30,
      valueType: "number",
      boundary: "hot_consumed",
    },
    "workflowRetry.jitterRatio": {
      label: "Jitter ratio",
      value: 0.2,
      valueType: "number",
      boundary: "hot_consumed",
    },
  },
  Notifications: {
    "notifications.pollSeconds": {
      label: "Poll interval",
      value: 5,
      valueType: "number",
      boundary: "hot_consumed",
    },
    "notifications.deliveryLeaseSeconds": {
      label: "Lease",
      value: 300,
      valueType: "integer",
      boundary: "hot_consumed",
    },
  },
};

const groups = readSettingGroups({ sections });
const allFields = editableFields(groups);
const field = (path: string) => {
  const found = allFields.find((candidate) => candidate.path === path);
  if (found === undefined) throw new Error(`missing field ${path}`);
  return found;
};

describe("configuration settings model", () => {
  it("keeps the backend sections, excludes focused and bootstrap fields, and groups in operator order", () => {
    expect(groups.map((group) => group.title)).toEqual([
      "语言与时区",
      "路径",
      "日志",
      "重试",
      "通知运行",
    ]);
    expect(allFields.map((item) => item.path)).not.toContain(
      "automation.workerPollSeconds",
    );
    expect(allFields.map((item) => item.path)).not.toContain(
      "persistence.databasePath",
    );
    // An allowlisted field with no Chinese presentation still exists rather
    // than being dropped from the editor.
    expect(allFields.some((item) => item.path === "historyPath")).toBe(true);
    expect(field("locale").label).toBe("系统语言");
    expect(field("operationalLogging.minimumLevel").options).toEqual([
      { value: "TRACE", label: "跟踪（TRACE）" },
      { value: "DEBUG", label: "调试（DEBUG）" },
      { value: "INFO", label: "信息（INFO）" },
      { value: "WARN", label: "警告（WARN）" },
      { value: "ERROR", label: "错误（ERROR）" },
    ]);
    expect(field("operationalLogging.retentionDays").unit).toBe("天");
    expect(field("operationalLogging.retentionDays").minimum).toBe(1);
    expect(field("operationalLogging.retentionDays").maximum).toBe(3650);
  });

  it("distinguishes boolean false, true and unconfigured", () => {
    expect(serializeSettingValue(field("operationalLogging.enabled"))).toBe(
      "false",
    );
    expect(serializeSettingValue(field("workflowRetry.enabled"))).toBe("unset");
    expect(booleanStateLabel("false")).toBe("关闭");
    expect(booleanStateLabel("true")).toBe("开启");
    expect(booleanStateLabel("unset")).toBe("未配置");
    expect(
      parseSettingInput(field("operationalLogging.enabled"), "true"),
    ).toEqual({ ok: true, value: true });
    expect(
      parseSettingInput(field("operationalLogging.enabled"), "false"),
    ).toEqual({ ok: true, value: false });
    expect(
      parseSettingInput(field("workflowRetry.enabled"), "unset"),
    ).toMatchObject({ ok: false });
  });

  it("rejects unconvertible numbers and trailing characters instead of rewriting them", () => {
    const retention = field("operationalLogging.retentionDays");
    for (const input of [
      "",
      " ",
      "12abc",
      "12 ",
      " 12",
      "1.5",
      "NaN",
      "Infinity",
      "-Infinity",
      "0x10",
      "1e3",
    ]) {
      expect(parseSettingInput(retention, input)).toMatchObject({ ok: false });
    }
    expect(parseSettingInput(retention, "12")).toEqual({ ok: true, value: 12 });
    expect(parseSettingInput(retention, "0")).toMatchObject({ ok: false });
    expect(parseSettingInput(retention, "3651")).toMatchObject({ ok: false });

    const jitter = field("workflowRetry.jitterRatio");
    for (const input of ["-0.1", "1.1", "0.2.3", "1,2", "NaN"]) {
      expect(parseSettingInput(jitter, input)).toMatchObject({ ok: false });
    }
    expect(parseSettingInput(jitter, "0")).toEqual({ ok: true, value: 0 });
    expect(parseSettingInput(jitter, "1")).toEqual({ ok: true, value: 1 });
    expect(parseSettingInput(jitter, "0.25")).toEqual({
      ok: true,
      value: 0.25,
    });
  });

  it("submits only the changed fields of the selected group", () => {
    const baseline = baselineValues(groups);
    const logging = groups.find((group) => group.id === "Logging");
    if (logging === undefined) throw new Error("missing logging group");
    const inputs = {
      ...baseline,
      "operationalLogging.retentionDays": "45",
      "operationalLogging.minimumLevel": "DEBUG",
      // Another group's change must not be submitted by this group's Save.
      locale: "en-US",
    };
    expect(groupChanged(logging, inputs, baseline)).toBe(true);
    expect(collectGroupEdits(logging, inputs, baseline)).toEqual({
      edits: [
        { fieldPath: "operationalLogging.minimumLevel", value: "DEBUG" },
        { fieldPath: "operationalLogging.retentionDays", value: 45 },
      ],
      errors: {},
    });
    expect(
      collectGroupEdits(
        logging,
        { ...baseline, "operationalLogging.retentionDays": "45x" },
        baseline,
      ),
    ).toEqual({
      edits: [],
      errors: {
        "operationalLogging.retentionDays":
          "请输入完整整数，不能包含空格或尾随字符。",
      },
    });
  });

  it("keeps a value equal to the authoritative read out of the edit set", () => {
    const baseline = baselineValues(groups);
    const logging = groups.find((group) => group.id === "Logging");
    if (logging === undefined) throw new Error("missing logging group");
    expect(
      fieldChanged(field("operationalLogging.enabled"), "false", baseline),
    ).toBe(false);
    expect(groupChanged(logging, baseline, baseline)).toBe(false);
    expect(collectGroupEdits(logging, baseline, baseline).edits).toEqual([]);
  });

  it("checks the retry delay pair against the effective values", () => {
    const baseline = baselineValues(groups);
    const workflow = groups.find((group) => group.id === "Workflow");
    if (workflow === undefined) throw new Error("missing workflow group");
    const result = collectGroupEdits(
      workflow,
      { ...baseline, "workflowRetry.baseDelaySeconds": "45" },
      baseline,
    );
    expect(result.edits).toEqual([]);
    expect(result.errors["workflowRetry.maxDelaySeconds"]).toContain(
      "最大重试间隔需要不小于基础重试间隔",
    );
  });
});
