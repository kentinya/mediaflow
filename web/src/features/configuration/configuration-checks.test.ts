import { describe, expect, it } from "vitest";
import {
  destinationFailureCopy,
  destinationVerdictLabel,
  readCheckObjects,
  readPublishChecks,
  storageFailureCopy,
  type CheckEvidenceSnapshot,
  type CheckObjects,
} from "./configuration-checks";

const objects = (overrides: Partial<CheckObjects> = {}): CheckObjects => ({
  storages: [
    { id: "source-storage", name: "Source", type: "local", enabled: true },
    { id: "media-target", name: "Target", type: "local", enabled: true },
  ],
  resourceLibraries: [
    {
      id: "source",
      name: "Source",
      enabled: true,
      storageId: "source-storage",
    },
  ],
  mediaLibraries: [
    { id: "movies", name: "Movies", enabled: true, storageId: "media-target" },
  ],
  recognitionTypes: [
    { id: "A", name: "Movies", enabled: true },
    { id: "B", name: "TV", enabled: false },
  ],
  recognitionTypePolicies: [
    {
      enabled: true,
      recognitionType: "A",
      namingPolicy: "naming",
      classificationPolicy: "classification",
      organizePolicy: "organize",
    },
  ],
  namingPolicies: [{ id: "naming", enabled: true }],
  organizePolicies: [{ id: "organize", enabled: true }],
  classificationPolicies: [
    {
      id: "classification",
      enabled: true,
      mediaLibraryIds: ["movies"],
    },
  ],
  ...overrides,
});

const evidence = (
  overrides: Partial<CheckEvidenceSnapshot> = {},
): CheckEvidenceSnapshot => ({
  storageChecks: [],
  strategyTest: null,
  destinationPrecheck: null,
  ...overrides,
});

describe("publish check requirement model", () => {
  it("requires the referenced enabled Storages, strategy test and destination precheck", () => {
    const model = readPublishChecks(objects(), evidence());
    expect(model.items.map((item) => item.id)).toEqual([
      "storage:source-storage",
      "storage:media-target",
      "strategy",
      "destination",
    ]);
    expect(model.applicable).toBe(4);
    expect(model.satisfied).toBe(false);
    expect(model.blocking).toEqual([
      "存储只读检查：Source（source-storage）",
      "存储只读检查：Target（media-target）",
      "识别策略测试",
      "目标预检",
    ]);
  });

  it("accepts current passed Storage evidence and rejects stale evidence", () => {
    const passed = readPublishChecks(
      objects({
        mediaLibraries: [],
        resourceLibraries: [
          {
            id: "retired",
            name: "Retired",
            enabled: false,
            storageId: "source-storage",
          },
        ],
        recognitionTypes: [],
      }),
      evidence({
        storageChecks: [
          {
            storageId: "source-storage",
            status: "passed",
            stale: false,
            checkedAt: "2026-11-15T10:00:00+00:00",
          },
        ],
      }),
    );
    expect(passed.satisfied).toBe(true);
    expect(passed.items[0]?.state).toBe("passed");
    const stale = readPublishChecks(
      objects({
        mediaLibraries: [],
        resourceLibraries: [
          {
            id: "retired",
            name: "Retired",
            enabled: false,
            storageId: "source-storage",
          },
        ],
        recognitionTypes: [],
      }),
      evidence({
        storageChecks: [
          {
            storageId: "source-storage",
            status: "passed",
            stale: true,
            checkedAt: "2026-11-15T10:00:00+00:00",
          },
        ],
      }),
    );
    expect(stale.items[0]?.state).toBe("stale");
    expect(stale.items[0]?.nextAction).toBe("请重新运行该存储的只读检查。");
  });

  it("explains a failed Storage check in Chinese and keeps the backend reason for diagnostics", () => {
    const model = readPublishChecks(
      objects({
        storages: [
          ...objects().storages,
          { id: "spare", name: "", type: "local", enabled: true },
        ],
        mediaLibraries: [],
      }),
      evidence({
        storageChecks: [
          {
            storageId: "source-storage",
            status: "failed",
            stale: false,
            failureCategory: "missing_secret",
            message: "required deployment credential is unset",
            nextAction: "set the credential, rerun the check",
          },
        ],
      }),
    );
    const storage = model.items.find(
      (item) => item.id === "storage:source-storage",
    );
    expect(storage?.detail).toBe("只读检查未通过：部署凭据未配置。");
    expect(storage?.nextAction).toContain("部署环境为该存储配置所需凭据");
    expect(storage?.backendMessage).toBe(
      "required deployment credential is unset",
    );
    expect(storage?.backendNextAction).toBe(
      "set the credential, rerun the check",
    );
  });

  it("keeps a referenced but missing Storage a correction, not a silent pass", () => {
    const model = readPublishChecks(
      objects({
        storages: [
          { id: "media-target", name: "Target", type: "local", enabled: true },
        ],
        resourceLibraries: [
          {
            id: "retired",
            name: "Retired",
            enabled: false,
            storageId: "missing-storage",
          },
        ],
        mediaLibraries: [],
        recognitionTypes: [],
      }),
      evidence(),
    );
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.state).toBe("failed");
    expect(model.items[0]?.detail).toContain("不存在");
    expect(model.items[0]?.nextAction).toContain("补齐该存储引用");
  });

  it("skips a disabled referenced Storage because checked activation does not require it", () => {
    const model = readPublishChecks(
      objects({
        storages: [
          {
            id: "source-storage",
            name: "Source",
            type: "local",
            enabled: false,
          },
        ],
        mediaLibraries: [],
        recognitionTypes: [],
      }),
      evidence(),
    );
    expect(model.items.map((item) => item.id)).toEqual(["strategy"]);
  });

  it("requires a destination precheck only when the media chain is usable", () => {
    const unresolved = readPublishChecks(
      objects({
        resourceLibraries: [],
        classificationPolicies: [
          { id: "classification", enabled: true, mediaLibraryIds: [] },
        ],
      }),
      evidence(),
    );
    expect(unresolved.items.map((item) => item.id)).toEqual([
      "storage:media-target",
    ]);
    const disabledNaming = readPublishChecks(
      objects({
        resourceLibraries: [],
        namingPolicies: [{ id: "naming", enabled: false }],
      }),
      evidence(),
    );
    expect(disabledNaming.items.some((item) => item.id === "destination")).toBe(
      false,
    );
    // A disabled policy reference is an incomplete chain, not a destination.
    const disabledClassification = readPublishChecks(
      objects({
        resourceLibraries: [],
        classificationPolicies: [
          { id: "classification", enabled: false, mediaLibraryIds: ["movies"] },
        ],
      }),
      evidence(),
    );
    expect(
      disabledClassification.items.some((item) => item.id === "destination"),
    ).toBe(false);
  });

  it("does not invent checks for an empty baseline", () => {
    const model = readPublishChecks(
      {
        storages: [],
        resourceLibraries: [],
        mediaLibraries: [],
        recognitionTypes: [],
        recognitionTypePolicies: [],
        namingPolicies: [],
        organizePolicies: [],
        classificationPolicies: [],
      },
      evidence(),
    );
    expect(model.applicable).toBe(0);
    expect(model.satisfied).toBe(true);
    expect(model.blocking).toEqual([]);
  });

  it("states the recognition outcome without hiding an unrecognized result", () => {
    const model = readPublishChecks(
      objects({ mediaLibraries: [] }),
      evidence({
        strategyTest: {
          status: "completed",
          stale: false,
          testedAt: "2026-11-15T10:00:00+00:00",
          result: { recognition: { status: "unrecognized" } },
        },
        storageChecks: [
          {
            storageId: "source-storage",
            status: "passed",
            stale: false,
          },
        ],
      }),
    );
    const strategy = model.items.find((item) => item.id === "strategy");
    expect(strategy?.state).toBe("passed");
    expect(strategy?.detail).toContain("没有匹配的识别规则");
    expect(strategy?.nextAction).toContain("不阻止 checked 激活");
    expect(model.satisfied).toBe(true);
  });

  it("treats a completed destination precheck as blocked only for a capability gap", () => {
    const ready = readPublishChecks(
      objects(),
      evidence({
        storageChecks: [
          { storageId: "source-storage", status: "passed", stale: false },
          { storageId: "media-target", status: "passed", stale: false },
        ],
        strategyTest: { status: "completed", stale: false },
        destinationPrecheck: {
          status: "completed",
          stale: false,
          result: {
            verdict: "rename",
            mediaLibraryId: "movies",
            destinationPath:
              "Movies/Action/The Matrix (1999)/The Matrix (1999).mkv",
          },
        },
      }),
    );
    expect(ready.satisfied).toBe(true);
    const destination = ready.items.find((item) => item.id === "destination");
    expect(destination?.detail).toContain("将按冲突策略改名");
    expect(destination?.detail).toContain("Movies/Action");
    const gap = readPublishChecks(
      objects(),
      evidence({
        storageChecks: [
          { storageId: "source-storage", status: "passed", stale: false },
          { storageId: "media-target", status: "passed", stale: false },
        ],
        strategyTest: { status: "completed", stale: false },
        destinationPrecheck: {
          status: "completed",
          stale: false,
          result: { verdict: "capability_gap" },
        },
      }),
    );
    expect(gap.items.find((item) => item.id === "destination")?.state).toBe(
      "failed",
    );
    expect(gap.satisfied).toBe(false);
  });

  it("explains a destination failure with its bounded category and next step", () => {
    const model = readPublishChecks(
      objects({ storages: [], resourceLibraries: [] }),
      evidence({
        destinationPrecheck: {
          status: "failed",
          stale: false,
          failureCategory: "invalid_rule",
          message:
            "no enabled classification rule matched the destination sample",
          nextAction:
            "correct the destination or conflict policy, then rerun precheck",
        },
      }),
    );
    const destination = model.items.find((item) => item.id === "destination");
    expect(destination?.detail).toBe(
      "目标预检未通过：没有分类规则匹配该示例。",
    );
    expect(destination?.nextAction).toContain("调整示例的题材或国家");
    expect(destination?.backendNextAction).toContain("rerun precheck");
  });

  it("exposes only enabled libraries and recognition types as selectable inputs", () => {
    const model = readPublishChecks(objects(), evidence());
    expect(model.strategyLibraries).toEqual([
      { id: "source", label: "Source（source）" },
    ]);
    expect(model.recognitionTypeOptions).toEqual([
      { id: "A", label: "Movies（A）" },
    ]);
  });

  it("keeps unknown backend categories explicit instead of guessing a pass", () => {
    expect(storageFailureCopy("something_new")).toEqual({
      label: "检查未通过",
      nextAction: "请核对存储配置与部署凭据后重新运行检查。",
    });
    expect(destinationFailureCopy(undefined).label).toBe("预检未通过");
    expect(destinationVerdictLabel("ready")).toBe("目标可正常写入");
    expect(destinationVerdictLabel("unexpected")).toBeNull();
  });
});

describe("revision check projections", () => {
  it("reads only bounded objects and ignores a malformed projection", () => {
    expect(readCheckObjects(null)).toEqual({
      storages: [],
      resourceLibraries: [],
      mediaLibraries: [],
      recognitionTypes: [],
      recognitionTypePolicies: [],
      namingPolicies: [],
      organizePolicies: [],
      classificationPolicies: [],
    });
    const parsed = readCheckObjects({
      storages: [
        { id: "s", name: "S", type: "smb", enabled: false },
        "not-an-object",
      ],
      resourceLibraries: [{ id: "r", storageId: "s" }],
      mediaLibraries: [{ id: "m", storageId: "s", enabled: false }],
    });
    expect(parsed.storages).toEqual([
      { id: "s", name: "S", type: "smb", enabled: false },
    ]);
    expect(parsed.resourceLibraries).toEqual([
      { id: "r", name: "", enabled: true, storageId: "s" },
    ]);
    expect(parsed.mediaLibraries[0]).toMatchObject({ enabled: false });
    expect(parsed.recognitionTypePolicies).toEqual([]);
    expect(parsed.classificationPolicies).toEqual([]);
  });
});
