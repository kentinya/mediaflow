import { afterEach, describe, expect, it, vi } from "vitest";
import type { AutomationDefinitionFormAuthorityModel } from "../../entities/operations/automation-lifecycle";
import {
  buildCreateCandidate,
  buildCandidateFromPublicationForm,
  browserTimeZone,
  compiledSchedule,
  createFormFromPublication,
  formatPreviewTime,
  initialCreateForm,
  intervalSecondsFromForm,
  newAutomationDefinitionId,
  publicationFormFromCreateForm,
  scheduleSummary,
  timeZoneIsValid,
  validateCreateForm,
  type AutomationCreateForm,
} from "./automation-create-form";
import type { PendingAutomationPublication } from "./automation-publication-session";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const AUTHORITY: AutomationDefinitionFormAuthorityModel = {
  executionEffects: null,
  active: {
    revisionId: "active-1",
    version: 3,
    revisionSequence: 2,
    status: "active",
    digest: "a".repeat(64),
  },
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
      storageId: "source-storage",
      storagePath: "Media",
    },
    {
      id: "disabled",
      name: "Disabled",
      enabled: false,
      storageId: "source-storage",
      storagePath: "Other",
    },
  ],
  modes: ["automatic-organization"],
  scheduleTypes: ["interval", "cron"],
  actions: { create: true },
  limits: {
    id: 64,
    name: 120,
    sourceScope: 1024,
    timezone: 64,
    itemLimitMinimum: 1,
    itemLimitMaximum: 10000,
    intervalMinimum: 0,
    intervalExclusiveMinimum: true,
    intervalMaximum: 31536000,
  },
};

function form(
  overrides: Partial<AutomationCreateForm> = {},
): AutomationCreateForm {
  return {
    ...initialCreateForm({
      id: "automation-0123456789abcdef",
      timeZone: "UTC",
    }),
    resourceLibraryId: "source",
    name: "夜间整理",
    ...overrides,
  };
}

describe("automation create form", () => {
  it("starts with the ordinary defaults and a legal cryptographic identity", () => {
    const created = initialCreateForm({
      id: "automation-0123456789abcdef",
      timeZone: "UTC",
    });
    expect(created.itemLimit).toBe("100");
    expect(created.intervalValue).toBe("1");
    expect(created.intervalUnit).toBe("hours");
    expect(created.scopeMode).toBe("root");
    expect(created.schedule).toBe("interval");
    expect(created.timezone).toBe("UTC");
    expect(newAutomationDefinitionId()).toMatch(/^automation-[0-9a-f]{24}$/);
  });

  it("reports no safe identity when the runtime has no cryptographic random source", () => {
    vi.stubGlobal("crypto", {});
    expect(newAutomationDefinitionId()).toBeNull();
  });

  it("converts interval units exactly, including fractional values", () => {
    expect(intervalSecondsFromForm("1", "seconds")).toBe("1");
    expect(intervalSecondsFromForm("1.5", "seconds")).toBe("1.5");
    expect(intervalSecondsFromForm("1", "minutes")).toBe("60");
    expect(intervalSecondsFromForm("1.5", "minutes")).toBe("90");
    expect(intervalSecondsFromForm("1", "hours")).toBe("3600");
    expect(intervalSecondsFromForm("1.5", "hours")).toBe("5400");
    expect(intervalSecondsFromForm("0.001", "hours")).toBe("3.6");
    expect(intervalSecondsFromForm("", "hours")).toBeNull();
    expect(intervalSecondsFromForm("0", "hours")).toBeNull();
    expect(intervalSecondsFromForm("-1", "hours")).toBeNull();
    expect(intervalSecondsFromForm("1e3", "hours")).toBeNull();
  });

  it("compiles daily and weekly choices to the existing five-field Cron", () => {
    expect(
      compiledSchedule(form({ schedule: "daily", dailyTime: "08:30" })),
    ).toMatchObject({ cron: "30 8 * * *", intervalSeconds: null });
    expect(
      compiledSchedule(
        form({ schedule: "weekly", weeklyDay: "1", weeklyTime: "19:05" }),
      ),
    ).toMatchObject({ cron: "5 19 * * 1" });
    expect(
      compiledSchedule(form({ schedule: "cron", cron: "0 8 * * 1-5" })),
    ).toMatchObject({ cron: "0 8 * * 1-5" });
  });

  it("round-trips a submitted command without changing its schedule identity", () => {
    const pending: PendingAutomationPublication = {
      definitionId: "automation-0123456789abcdef",
      action: "create",
      form: publicationFormFromCreateForm(
        form({
          schedule: "weekly",
          weeklyDay: "5",
          weeklyTime: "21:15",
          timezone: "Asia/Shanghai",
          scopeMode: "subdirectory",
          sourceScope: "电影/华语",
          itemLimit: "7",
        }),
      ),
      authority: {
        revisionId: "active-1",
        version: 2,
        digest: "b".repeat(64),
      },
    };
    expect(pending.form).toMatchObject({
      scheduleType: "cron",
      cron: "15 21 * * 5",
      timezone: "Asia/Shanghai",
      enabled: false,
      sourceScope: "电影/华语",
      itemLimit: "7",
    });
    expect(buildCandidateFromPublicationForm(pending.form)).toMatchObject({
      id: "automation-0123456789abcdef",
      enabled: false,
      intervalSeconds: null,
      cron: "15 21 * * 5",
      timezone: "Asia/Shanghai",
    });
    expect(createFormFromPublication(pending, "UTC")).toMatchObject({
      schedule: "weekly",
      weeklyDay: "5",
      weeklyTime: "21:15",
      timezone: "Asia/Shanghai",
      scopeMode: "subdirectory",
      sourceScope: "电影/华语",
      itemLimit: "7",
    });
  });

  it("builds the exact checked candidate and never enables it", () => {
    expect(
      buildCreateCandidate(
        form({
          name: "  夜间整理  ",
          scopeMode: "subdirectory",
          sourceScope: " 电影 ",
          itemLimit: "12",
          intervalValue: "1.5",
          intervalUnit: "hours",
        }),
      ),
    ).toEqual({
      id: "automation-0123456789abcdef",
      name: "夜间整理",
      enabled: false,
      resourceLibraryId: "source",
      mode: "automatic-organization",
      itemLimit: 12,
      sourceScope: "电影",
      intervalSeconds: 5400,
      cron: null,
      timezone: null,
    });
    expect(
      buildCreateCandidate(
        form({
          schedule: "daily",
          dailyTime: "06:05",
          timezone: "Asia/Shanghai",
        }),
      ),
    ).toMatchObject({
      intervalSeconds: null,
      cron: "5 6 * * *",
      timezone: "Asia/Shanghai",
    });
  });

  it("validates every ordinary field and identifies the first correction", () => {
    const issues = validateCreateForm(
      form({
        name: " ",
        resourceLibraryId: "",
        scopeMode: "subdirectory",
        sourceScope: "../escape",
        itemLimit: "0",
        intervalValue: "0",
        intervalUnit: "hours",
        timezone: "",
      }),
      AUTHORITY,
    );
    expect(issues.map((issue) => issue.fieldId)).toEqual([
      "automation-create-name",
      "automation-create-library",
      "automation-create-scope",
      "automation-create-limit",
      "automation-create-interval",
    ]);

    const scheduleIssues = validateCreateForm(
      form({
        schedule: "weekly",
        weeklyDay: "9",
        weeklyTime: "25:00",
        timezone: "Mars/Olympus",
      }),
      AUTHORITY,
    );
    expect(scheduleIssues.map((issue) => issue.fieldId)).toEqual([
      "automation-create-weekly-day",
      "automation-create-weekly-time",
      "automation-create-timezone",
    ]);

    const cronIssues = validateCreateForm(
      form({ schedule: "cron", cron: " ", timezone: "UTC" }),
      AUTHORITY,
    );
    expect(cronIssues.map((issue) => issue.fieldId)).toEqual([
      "automation-create-cron",
    ]);
  });

  it("accepts valid forms and rejects disabled or unknown libraries", () => {
    expect(validateCreateForm(form(), AUTHORITY)).toHaveLength(0);
    expect(
      validateCreateForm(form({ resourceLibraryId: "disabled" }), AUTHORITY)[0]
        ?.message,
    ).toContain("停用");
    expect(
      validateCreateForm(form({ resourceLibraryId: "missing" }), AUTHORITY)[0]
        ?.message,
    ).toContain("不可用");
  });

  it("summarizes the schedule and formats preview instants in the chosen zone", () => {
    expect(
      scheduleSummary(form({ intervalValue: "1.5", intervalUnit: "hours" })),
    ).toContain("5400 秒");
    expect(
      scheduleSummary(
        form({ schedule: "weekly", weeklyDay: "1", weeklyTime: "08:00" }),
      ),
    ).toContain("周一");
    expect(timeZoneIsValid("Asia/Shanghai")).toBe(true);
    expect(timeZoneIsValid("Mars/Olympus")).toBe(false);
    const formatted = formatPreviewTime(
      "2026-11-02T00:00:00+00:00",
      "Asia/Shanghai",
    );
    expect(formatted).toContain("2026");
    expect(formatted).toContain("周一");
    expect(browserTimeZone().timeZone.length).toBeGreaterThan(0);
  });
});
