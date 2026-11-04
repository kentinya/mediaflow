/**
 * Pure create-form model for the Automation creation dialog.
 *
 * The form compiles ordinary operator choices into exactly the existing typed
 * candidate fields: one positive interval (seconds) or one five-field Cron
 * expression plus an IANA timezone. It never calculates a due time, invents a
 * schedule mode, mutates authority or creates a Draft. The internal ID is
 * generated once per creation session from Web Crypto; when no cryptographic
 * random source exists the caller receives an explicit unavailable state
 * instead of a weak random or timestamp ID.
 */

import { AUTOMATION_AUTOMATIC_ORGANIZATION_MODE } from "../../entities/operations/automation";
import type {
  AutomationDefinitionFormAuthorityModel,
  AutomationResourceLibraryOption,
} from "../../entities/operations/automation-lifecycle";
import type {
  AutomationPublicationFormState,
  PendingAutomationPublication,
} from "./automation-publication-session";

export type CreateScheduleKind = "interval" | "daily" | "weekly" | "cron";
export type IntervalUnit = "seconds" | "minutes" | "hours";

export interface AutomationCreateForm {
  readonly id: string;
  readonly name: string;
  readonly resourceLibraryId: string;
  readonly scopeMode: "root" | "subdirectory";
  readonly sourceScope: string;
  readonly itemLimit: string;
  readonly schedule: CreateScheduleKind;
  readonly intervalValue: string;
  readonly intervalUnit: IntervalUnit;
  readonly dailyTime: string;
  readonly weeklyDay: string;
  readonly weeklyTime: string;
  readonly cron: string;
  readonly timezone: string;
}

export interface CreateFormIssue {
  readonly fieldId: string;
  readonly label: string;
  readonly message: string;
}

/** The backend's identifier grammar and bounded field lengths. */
const DEFINITION_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,63}$/;
const DECIMAL_PATTERN = /^(\d+)(?:\.(\d+))?$/;
const TIME_PATTERN = /^([01]\d|2[0-3]):([0-5]\d)$/;
const MAX_CRON_LENGTH = 64;
const ID_RANDOM_BYTES = 12;
const ID_PREFIX = "automation-";

export const DEFAULT_INTERVAL_VALUE = "1";
export const DEFAULT_INTERVAL_UNIT: IntervalUnit = "hours";
export const DEFAULT_ITEM_LIMIT = "100";

/** The browser's IANA timezone, or the documented UTC fallback. */
export function browserTimeZone(): {
  readonly timeZone: string;
  readonly recognized: boolean;
} {
  try {
    const candidate = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (candidate.length > 0 && timeZoneIsValid(candidate)) {
      return { timeZone: candidate, recognized: true };
    }
  } catch {
    // Fall through to the explicit UTC fallback.
  }
  return { timeZone: "UTC", recognized: false };
}

/** Whether the backend/browser can resolve this IANA timezone identifier. */
export function timeZoneIsValid(value: string): boolean {
  const trimmed = value.trim();
  if (trimmed.length === 0 || trimmed.length > 64) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: trimmed }).format(0);
    return true;
  } catch {
    return false;
  }
}

/**
 * One stable creation identity from the Web Crypto random source.
 *
 * The value is legal for the existing backend grammar and never derives from
 * the operator-entered name, the current time or `Math.random`.
 */
export function newAutomationDefinitionId(): string | null {
  try {
    const cryptoApi = globalThis.crypto;
    if (typeof cryptoApi?.getRandomValues !== "function") return null;
    const bytes = cryptoApi.getRandomValues(new Uint8Array(ID_RANDOM_BYTES));
    const hex = Array.from(bytes, (value) =>
      value.toString(16).padStart(2, "0"),
    ).join("");
    return `${ID_PREFIX}${hex}`;
  } catch {
    return null;
  }
}

/** The initial ordinary form: whole ResourceLibrary, hourly, limit 100. */
export function initialCreateForm(input: {
  readonly id: string;
  readonly timeZone: string;
}): AutomationCreateForm {
  return {
    id: input.id,
    name: "",
    resourceLibraryId: "",
    scopeMode: "root",
    sourceScope: "",
    itemLimit: DEFAULT_ITEM_LIMIT,
    schedule: "interval",
    intervalValue: DEFAULT_INTERVAL_VALUE,
    intervalUnit: DEFAULT_INTERVAL_UNIT,
    dailyTime: "08:00",
    weeklyDay: "1",
    weeklyTime: "08:00",
    cron: "",
    timezone: input.timeZone,
  };
}

function decimalMultiply(value: string, factor: number): string | null {
  const match = DECIMAL_PATTERN.exec(value);
  if (match === null) return null;
  const fraction = match[2] ?? "";
  if (fraction.length > 18) return null;
  try {
    const digits = BigInt(match[1] + fraction);
    const product = digits * BigInt(factor);
    if (fraction.length === 0) return product.toString();
    const text = product.toString().padStart(fraction.length + 1, "0");
    const integer = text.slice(0, -fraction.length) || "0";
    const decimal = text.slice(-fraction.length).replace(/0+$/, "");
    return decimal.length > 0 ? `${integer}.${decimal}` : integer;
  } catch {
    return null;
  }
}

/** Convert the operator's interval value/unit to canonical decimal seconds. */
export function intervalSecondsFromForm(
  value: string,
  unit: IntervalUnit,
): string | null {
  const factor = unit === "seconds" ? 1 : unit === "minutes" ? 60 : 3600;
  const seconds = decimalMultiply(value.trim(), factor);
  if (seconds === null) return null;
  const numeric = Number(seconds);
  return Number.isFinite(numeric) && numeric > 0 ? seconds : null;
}

function parseTime(value: string): { hour: number; minute: number } | null {
  const match = TIME_PATTERN.exec(value.trim());
  if (match === null) return null;
  return { hour: Number(match[1]), minute: Number(match[2]) };
}

function cronFromTime(time: string, weekday: number | null): string | null {
  const parsed = parseTime(time);
  if (parsed === null) return null;
  return weekday === null
    ? `${parsed.minute} ${parsed.hour} * * *`
    : `${parsed.minute} ${parsed.hour} * * ${weekday}`;
}

/**
 * Read one compiled Cron expression back into the convenience controls.
 *
 * Anything that is not exactly the form's own daily/weekly shape stays
 * advanced Cron, so an operator's arbitrary expression is never silently
 * rewritten into a different schedule.
 */
function convenienceFromCron(cron: string): {
  schedule: CreateScheduleKind;
  dailyTime: string;
  weeklyDay: string;
  weeklyTime: string;
} {
  const fields = cron.trim().split(/\s+/);
  if (fields.length === 5) {
    const [minute, hour, dayOfMonth, month, dayOfWeek] = fields;
    if (
      dayOfMonth === "*" &&
      month === "*" &&
      DECIMAL_PATTERN.test(minute) &&
      DECIMAL_PATTERN.test(hour)
    ) {
      const time = `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
      if (parseTime(time) !== null) {
        if (/^[0-6]$/.test(dayOfWeek)) {
          return {
            schedule: "weekly",
            dailyTime: "08:00",
            weeklyDay: dayOfWeek,
            weeklyTime: time,
          };
        }
        if (dayOfWeek === "*") {
          return {
            schedule: "daily",
            dailyTime: time,
            weeklyDay: "1",
            weeklyTime: "08:00",
          };
        }
      }
    }
  }
  return {
    schedule: "cron",
    dailyTime: "08:00",
    weeklyDay: "1",
    weeklyTime: "08:00",
  };
}

/** Compile one ordinary schedule selection into the canonical candidate. */
export function compiledSchedule(form: AutomationCreateForm): {
  readonly cron: string;
  readonly timezone: string;
  readonly intervalSeconds: string | null;
} | null {
  if (form.schedule === "interval") {
    const intervalSeconds = intervalSecondsFromForm(
      form.intervalValue,
      form.intervalUnit,
    );
    return intervalSeconds === null
      ? null
      : { cron: "", timezone: "", intervalSeconds };
  }
  if (form.schedule === "daily") {
    const cron = cronFromTime(form.dailyTime, null);
    return cron === null
      ? null
      : { cron, timezone: form.timezone.trim(), intervalSeconds: null };
  }
  if (form.schedule === "weekly") {
    const weekday = Number(form.weeklyDay);
    if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6) return null;
    const cron = cronFromTime(form.weeklyTime, weekday);
    return cron === null
      ? null
      : { cron, timezone: form.timezone.trim(), intervalSeconds: null };
  }
  const cron = form.cron.trim();
  return cron.length === 0
    ? null
    : { cron, timezone: form.timezone.trim(), intervalSeconds: null };
}

/** One Chinese summary of the exact schedule the form will submit. */
export function scheduleSummary(form: AutomationCreateForm): string {
  if (form.schedule === "interval") {
    const seconds = intervalSecondsFromForm(
      form.intervalValue,
      form.intervalUnit,
    );
    if (seconds === null) return "请填写有效的执行间隔";
    const unitLabel =
      form.intervalUnit === "seconds"
        ? "秒"
        : form.intervalUnit === "minutes"
          ? "分钟"
          : "小时";
    return `每隔 ${form.intervalValue} ${unitLabel}（${seconds} 秒）`;
  }
  if (form.schedule === "daily") {
    return `每天 ${form.dailyTime}（${form.timezone || "时区未填写"}）`;
  }
  if (form.schedule === "weekly") {
    const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    return `${weekdays[Number(form.weeklyDay)] ?? "每周"} ${form.weeklyTime}（${
      form.timezone || "时区未填写"
    }）`;
  }
  return `Cron ${form.cron || "未填写"}（${form.timezone || "时区未填写"}）`;
}

/** Validate every ordinary field; the backend remains the final authority. */
export function validateCreateForm(
  form: AutomationCreateForm,
  authority: AutomationDefinitionFormAuthorityModel,
): readonly CreateFormIssue[] {
  const issues: CreateFormIssue[] = [];
  const name = form.name.trim();
  if (name.length === 0) {
    issues.push({
      fieldId: "automation-create-name",
      label: "名称",
      message: "请填写任务名称。",
    });
  } else if (name.length > authority.limits.name) {
    issues.push({
      fieldId: "automation-create-name",
      label: "名称",
      message: `任务名称不能超过 ${authority.limits.name} 个字符。`,
    });
  }

  const library = authority.resourceLibraries.find(
    (item) => item.id === form.resourceLibraryId,
  );
  if (form.resourceLibraryId.length === 0) {
    issues.push({
      fieldId: "automation-create-library",
      label: "资源库",
      message: "请选择要扫描的资源库。",
    });
  } else if (library === undefined) {
    issues.push({
      fieldId: "automation-create-library",
      label: "资源库",
      message: "所选资源库已不可用，请重新选择。",
    });
  } else if (!library.enabled) {
    issues.push({
      fieldId: "automation-create-library",
      label: "资源库",
      message: "所选资源库已停用，请选择已启用的资源库。",
    });
  }

  const sourceScope = form.sourceScope.trim();
  if (form.scopeMode === "subdirectory") {
    if (sourceScope.length === 0) {
      issues.push({
        fieldId: "automation-create-scope",
        label: "来源子目录",
        message: "请选择子目录，或切换为整个资源库。",
      });
    } else if (
      sourceScope.length > authority.limits.sourceScope ||
      sourceScope.startsWith("/") ||
      sourceScope.startsWith("\\") ||
      sourceScope.includes("\\") ||
      // eslint-disable-next-line no-control-regex
      /[\u0000-\u001f\u007f]/.test(sourceScope) ||
      sourceScope.split("/").some((part) => part === "..")
    ) {
      issues.push({
        fieldId: "automation-create-scope",
        label: "来源子目录",
        message: "请填写资源库内的安全相对路径，不能以斜杠开头或包含 ..。",
      });
    }
  }

  const itemLimit = Number(form.itemLimit);
  if (
    !/^\d+$/.test(form.itemLimit) ||
    !Number.isInteger(itemLimit) ||
    itemLimit < authority.limits.itemLimitMinimum ||
    itemLimit > authority.limits.itemLimitMaximum
  ) {
    issues.push({
      fieldId: "automation-create-limit",
      label: "处理上限",
      message: `请输入 ${authority.limits.itemLimitMinimum}–${authority.limits.itemLimitMaximum} 之间的整数。`,
    });
  }

  if (form.schedule === "interval") {
    const secondsText = intervalSecondsFromForm(
      form.intervalValue,
      form.intervalUnit,
    );
    const seconds = secondsText === null ? Number.NaN : Number(secondsText);
    if (
      secondsText === null ||
      !Number.isFinite(seconds) ||
      seconds <= authority.limits.intervalMinimum ||
      seconds > authority.limits.intervalMaximum
    ) {
      issues.push({
        fieldId: "automation-create-interval",
        label: "执行间隔",
        message: `请输入大于 0 且不超过 ${authority.limits.intervalMaximum} 秒的间隔，可包含小数。`,
      });
    }
  } else if (form.schedule === "daily") {
    if (parseTime(form.dailyTime) === null) {
      issues.push({
        fieldId: "automation-create-daily-time",
        label: "每日时间",
        message: "请填写有效时间（00:00–23:59）。",
      });
    }
  } else if (form.schedule === "weekly") {
    const weekday = Number(form.weeklyDay);
    if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6) {
      issues.push({
        fieldId: "automation-create-weekly-day",
        label: "每周星期",
        message: "请选择星期。",
      });
    }
    if (parseTime(form.weeklyTime) === null) {
      issues.push({
        fieldId: "automation-create-weekly-time",
        label: "每周时间",
        message: "请填写有效时间（00:00–23:59）。",
      });
    }
  } else if (form.cron.trim().length === 0) {
    issues.push({
      fieldId: "automation-create-cron",
      label: "Cron 表达式",
      message: "请填写 Cron 表达式。",
    });
  } else if (form.cron.trim().length > MAX_CRON_LENGTH) {
    issues.push({
      fieldId: "automation-create-cron",
      label: "Cron 表达式",
      message: `Cron 表达式不能超过 ${MAX_CRON_LENGTH} 个字符。`,
    });
  }

  const timezone = form.timezone.trim();
  if (form.schedule !== "interval") {
    if (timezone.length === 0) {
      issues.push({
        fieldId: "automation-create-timezone",
        label: "时区",
        message: "请填写 IANA 时区，例如 Asia/Shanghai。",
      });
    } else if (
      timezone.length > authority.limits.timezone ||
      !timeZoneIsValid(timezone)
    ) {
      issues.push({
        fieldId: "automation-create-timezone",
        label: "时区",
        message: "无法识别该时区，请填写 IANA 时区，例如 Asia/Shanghai。",
      });
    }
  }

  if (
    !DEFINITION_ID_PATTERN.test(form.id) ||
    form.id.length > authority.limits.id
  ) {
    issues.push({
      fieldId: "automation-create-id",
      label: "内部 ID",
      message:
        "无法生成合法的内部 ID。请刷新页面重试；系统不会使用弱随机或时间戳代替。",
    });
  }
  return issues;
}

/** Build the exact candidate the existing checked create command submits. */
export function buildCreateCandidate(
  form: AutomationCreateForm,
): Record<string, unknown> | null {
  const schedule = compiledSchedule(form);
  if (schedule === null) return null;
  return {
    id: form.id.trim(),
    name: form.name.trim(),
    enabled: false,
    resourceLibraryId: form.resourceLibraryId,
    mode: AUTOMATION_AUTOMATIC_ORGANIZATION_MODE,
    itemLimit: Number(form.itemLimit),
    sourceScope:
      form.scopeMode === "subdirectory" ? form.sourceScope.trim() : "",
    ...(form.schedule === "interval"
      ? {
          intervalSeconds: Number(schedule.intervalSeconds),
          cron: null,
          timezone: null,
        }
      : {
          intervalSeconds: null,
          cron: schedule.cron,
          timezone: schedule.timezone,
        }),
  };
}

/** The submitted-form projection retained for a lost-response reconciliation. */
export function publicationFormFromCreateForm(
  form: AutomationCreateForm,
): AutomationPublicationFormState {
  const schedule = compiledSchedule(form);
  return {
    id: form.id.trim(),
    name: form.name.trim(),
    enabled: false,
    resourceLibraryId: form.resourceLibraryId,
    mode: AUTOMATION_AUTOMATIC_ORGANIZATION_MODE,
    sourceScope:
      form.scopeMode === "subdirectory" ? form.sourceScope.trim() : "",
    itemLimit: form.itemLimit.trim(),
    scheduleType: form.schedule === "interval" ? "interval" : "cron",
    intervalSeconds:
      form.schedule === "interval" ? (schedule?.intervalSeconds ?? "") : "",
    cron: form.schedule === "interval" ? "" : (schedule?.cron ?? ""),
    timezone:
      form.schedule === "interval"
        ? form.timezone.trim() || "UTC"
        : form.timezone.trim(),
  };
}

/** Rebuild the operator form from one retained submitted command. */
export function createFormFromPublication(
  pending: PendingAutomationPublication,
  timeZoneFallback: string,
): AutomationCreateForm {
  const source = pending.form;
  const convenience =
    source.scheduleType === "interval"
      ? {
          schedule: "interval" as CreateScheduleKind,
          dailyTime: "08:00",
          weeklyDay: "1",
          weeklyTime: "08:00",
        }
      : convenienceFromCron(source.cron);
  return {
    id: source.id,
    name: source.name,
    resourceLibraryId: source.resourceLibraryId,
    scopeMode: source.sourceScope.trim().length > 0 ? "subdirectory" : "root",
    sourceScope: source.sourceScope,
    itemLimit: source.itemLimit,
    schedule: convenience.schedule,
    intervalValue:
      source.scheduleType === "interval"
        ? source.intervalSeconds || DEFAULT_INTERVAL_VALUE
        : DEFAULT_INTERVAL_VALUE,
    intervalUnit:
      source.scheduleType === "interval" ? "seconds" : DEFAULT_INTERVAL_UNIT,
    dailyTime: convenience.dailyTime,
    weeklyDay: convenience.weeklyDay,
    weeklyTime: convenience.weeklyTime,
    cron: source.scheduleType === "cron" ? source.cron : "",
    timezone: source.timezone || timeZoneFallback,
  };
}

/** Format one backend preview instant in the selected timezone. */
export function formatPreviewTime(
  value: string,
  timeZone: string | null,
): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return value;
  const resolved = timeZone ?? browserTimeZone().timeZone;
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: resolved,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  } catch {
    return value;
  }
}

/** The enabled ResourceLibrary choices the backend advertised. */
export function enabledResourceLibraries(
  authority: AutomationDefinitionFormAuthorityModel,
): readonly AutomationResourceLibraryOption[] {
  return authority.resourceLibraries.filter((item) => item.enabled);
}

/** Rebuild the exact submitted candidate for a lost-response reconciliation. */
export function buildCandidateFromPublicationForm(
  form: AutomationPublicationFormState,
): Record<string, unknown> {
  return {
    id: form.id.trim(),
    name: form.name.trim(),
    enabled: false,
    resourceLibraryId: form.resourceLibraryId,
    mode: form.mode,
    itemLimit: Number(form.itemLimit),
    sourceScope: form.sourceScope.trim(),
    ...(form.scheduleType === "interval"
      ? {
          intervalSeconds: Number(form.intervalSeconds),
          cron: null,
          timezone: null,
        }
      : {
          intervalSeconds: null,
          cron: form.cron.trim(),
          timezone: form.timezone.trim(),
        }),
  };
}
