/**
 * Frontend-owned bounded Automation engine-settings model.
 *
 * The backend publishes one focused, digest-free operator document under
 * `/api/v1/operations/automation/settings`. Two truths are kept strictly apart
 * here, exactly as the API states them:
 *
 * - the **published target** — the four engine values of the current immutable
 *   Active snapshot, with its revision identity; and
 * - the **adoption** — what each relevant live resident process actually
 *   installed, reported by that consumer after it adopted the values.
 *
 * Normalization is fail-closed: an unknown state, a non-finite number, a
 * missing required identity or a contradictory adoption flag makes the whole
 * response malformed. This is what prevents the page from ever presenting a
 * published target as collectively adopted, or an unreported/stale consumer as
 * success.
 */

import {
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeOptionalFiniteNumber,
  readRecord,
} from "../shared/normalize";

/** The exact four fields this form publishes, in operator order. */
export const AUTOMATION_ENGINE_FIELDS = [
  "automation.maximumActiveJobs",
  "automation.staleJobAgeSeconds",
  "automation.workerPollSeconds",
  "automation.schedulerPollSeconds",
] as const;

export type AutomationEngineField = (typeof AUTOMATION_ENGINE_FIELDS)[number];

export interface AutomationEngineFieldView {
  readonly fieldPath: AutomationEngineField;
  readonly label: string;
  readonly unit: string;
  readonly valueType: string;
  readonly minimum: number | null;
  readonly maximum: number | null;
  readonly meaning: string;
  readonly notMeaning: string;
  readonly consumer: string | null;
  readonly integer: boolean;
}

export type AdoptionStatus =
  | "adopted"
  | "pending"
  | "override"
  | "stale"
  | "stopped"
  | "stopped_unreported"
  | "unreported"
  | "unavailable"
  | "schema_incompatible";

const ADOPTION_STATUSES: readonly AdoptionStatus[] = [
  "adopted",
  "pending",
  "override",
  "stale",
  "stopped",
  "stopped_unreported",
  "unreported",
  "unavailable",
  "schema_incompatible",
];

/** Operator copy for each truthful adoption state. */
export const ADOPTION_STATUS_LABELS: Readonly<Record<AdoptionStatus, string>> =
  {
    adopted: "已采用当前发布值",
    pending: "等待下一个安全边界",
    override: "使用部署/命令行覆盖值",
    stale: "心跳或报告已过期",
    stopped: "进程已停止",
    stopped_unreported: "进程已停止,无采用报告",
    unreported: "尚未上报采用",
    unavailable: "暂不可用",
    schema_incompatible: "进程版本不一致",
  };

export interface ConsumerInstanceView {
  readonly instanceId: string;
  readonly liveness: string;
  readonly status: AdoptionStatus;
  readonly effectiveValue: number | null;
  readonly publishedRevisionId: string | null;
  readonly reportedRevisionId: string | null;
  readonly reportedAt: string | null;
  readonly appliedFields: readonly string[];
  readonly overrideSource: string | null;
  readonly durableState: string;
  readonly nextAction: string;
}

export interface ConsumerAdoptionView {
  readonly service: string;
  readonly field: string | null;
  readonly fields: readonly string[];
  readonly publishedValue: number | null;
  readonly publishedValues: Readonly<Record<string, number | null>>;
  readonly adopted: boolean;
  readonly basis: "consumer" | "api_local";
  readonly instanceCount: number;
  readonly instances: readonly ConsumerInstanceView[];
  readonly explanation: string | null;
}

export interface PublishedTargetView {
  readonly revisionId: string;
  readonly revisionVersion: number | null;
  readonly digest: string;
  readonly values: Readonly<Record<AutomationEngineField, number>>;
}

export interface AutomationSettingsUnavailable {
  readonly reason: string;
  readonly durableState: string;
  readonly nextAction: string;
}

export interface AutomationSettingsModel {
  readonly target: PublishedTargetView | null;
  readonly fields: readonly AutomationEngineFieldView[];
  readonly consumers: readonly ConsumerAdoptionView[];
  readonly adoption: {
    readonly consumers: number;
    readonly adoptedConsumers: number;
    readonly allAdopted: boolean;
  };
  readonly canManage: boolean;
  readonly configRecheckSeconds: number;
  readonly unavailable: AutomationSettingsUnavailable | null;
  readonly asOf: string | null;
}

function boundedText(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.length <= 4096 ? value : fallback;
}

/** An optional record: an absent field is `null` rather than malformed. */
function optionalRecord(value: unknown): Record<string, unknown> | null {
  if (value === null || value === undefined) return null;
  return readRecord(value, "automation engine settings record");
}

/** An optional bounded display string: absent/empty becomes null. */
function optionalText(value: unknown, maxLength = 1024): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trimEnd();
  if (trimmed.length === 0 || trimmed.length > maxLength) return null;
  return trimmed;
}

function optionalNumber(value: unknown, field: string): number | null {
  return normalizeOptionalFiniteNumber(value, field);
}

/**
 * Normalize one published-target document.
 *
 * Exported for the reconciliation answer, whose `target` is the same document
 * the readback carries: a merge decided after reconcile must be bound to that
 * exact current identity rather than to a pre-request value.
 */
export function normalizePublishedTarget(
  value: unknown,
): PublishedTargetView | null {
  return normalizeTarget(value);
}

function normalizeTarget(value: unknown): PublishedTargetView | null {
  const record = optionalRecord(value);
  if (record === null) return null;
  const revisionId = normalizeBoundedText(
    record["revisionId"],
    "revisionId",
    128,
  );
  const digest = normalizeBoundedText(record["digest"], "digest", 128);
  if (revisionId === null || digest === null) {
    throw new Error("automation engine settings target lacks an identity");
  }
  const values = readRecord(
    record["values"],
    "automation engine settings values",
  );
  if (values === null) {
    throw new Error("automation engine settings target lacks values");
  }
  const normalized = {} as Record<AutomationEngineField, number>;
  for (const field of AUTOMATION_ENGINE_FIELDS) {
    const raw = values[field];
    if (typeof raw !== "number" || !Number.isFinite(raw)) {
      throw new Error(
        `automation engine settings target value ${field} is invalid`,
      );
    }
    normalized[field] = raw;
  }
  return {
    revisionId,
    revisionVersion: optionalNumber(
      record["revisionVersion"],
      "revisionVersion",
    ),
    digest,
    values: normalized,
  };
}

function normalizeField(value: unknown): AutomationEngineFieldView {
  const record = readRecord(value, "automation engine settings field");
  if (record === null) {
    throw new Error("automation engine settings field is malformed");
  }
  const fieldPath = record["fieldPath"];
  if (
    typeof fieldPath !== "string" ||
    !(AUTOMATION_ENGINE_FIELDS as readonly string[]).includes(fieldPath)
  ) {
    throw new Error("unknown automation engine settings field");
  }
  return {
    fieldPath: fieldPath as AutomationEngineField,
    label: boundedText(record["label"], fieldPath),
    unit: boundedText(record["unit"]),
    valueType: boundedText(record["valueType"], "number"),
    minimum: optionalNumber(record["minimum"], "minimum"),
    maximum: optionalNumber(record["maximum"], "maximum"),
    meaning: boundedText(record["meaning"]),
    notMeaning: boundedText(record["notMeaning"]),
    consumer: optionalText(record["consumer"], 64),
    integer: record["integer"] === true,
  };
}

function normalizeInstance(value: unknown): ConsumerInstanceView {
  const record = readRecord(
    value,
    "automation engine settings consumer instance",
  );
  if (record === null) {
    throw new Error(
      "automation engine settings consumer instance is malformed",
    );
  }
  const status = record["status"];
  if (
    typeof status !== "string" ||
    !(ADOPTION_STATUSES as readonly string[]).includes(status)
  ) {
    throw new Error("unknown automation engine settings adoption status");
  }
  const instanceId = optionalText(record["instanceId"], 128);
  if (instanceId === null) {
    throw new Error(
      "automation engine settings consumer instance lacks an identity",
    );
  }
  return {
    instanceId,
    liveness: boundedText(record["liveness"]),
    status: status as AdoptionStatus,
    effectiveValue: optionalNumber(record["effectiveValue"], "effectiveValue"),
    publishedRevisionId: optionalText(record["publishedRevisionId"], 128),
    reportedRevisionId: optionalText(record["reportedRevisionId"], 128),
    reportedAt: optionalText(record["reportedAt"], 64),
    appliedFields: Array.isArray(record["appliedFields"])
      ? record["appliedFields"].filter(
          (item): item is string => typeof item === "string",
        )
      : [],
    overrideSource: optionalText(record["overrideSource"], 32),
    durableState: boundedText(record["durableState"]),
    nextAction: boundedText(record["nextAction"]),
  };
}

function normalizeConsumer(
  service: string,
  value: unknown,
): ConsumerAdoptionView {
  const record = readRecord(value, "automation engine settings consumer");
  if (record === null) {
    throw new Error("automation engine settings consumer is malformed");
  }
  const instances = Array.isArray(record["instances"])
    ? record["instances"].map(normalizeInstance)
    : [];
  const publishedValues: Record<string, number | null> = {};
  const rawPublished = optionalRecord(record["publishedValues"]);
  if (rawPublished !== null) {
    for (const [key, raw] of Object.entries(rawPublished)) {
      publishedValues[key] = optionalNumber(raw, key);
    }
  }
  // A collective claim is only accepted when it is consistent with the
  // instance evidence the same document carries. This is the guard that keeps
  // a fabricated "allAdopted" flag from becoming a deployment-wide success.
  const reportedAdopted = record["adopted"] === true;
  const consistent =
    !reportedAdopted ||
    (instances.length > 0 &&
      instances.every((instance) => instance.status === "adopted"));
  return {
    service,
    field: optionalText(record["field"], 128),
    fields: Array.isArray(record["fields"])
      ? record["fields"].filter(
          (item): item is string => typeof item === "string",
        )
      : [],
    publishedValue: optionalNumber(record["publishedValue"], "publishedValue"),
    publishedValues,
    adopted: reportedAdopted && consistent,
    basis: record["basis"] === "api_local" ? "api_local" : "consumer",
    instanceCount: normalizeBoundedCount(
      record["instanceCount"] ?? 0,
      "instanceCount",
    ),
    instances,
    explanation: optionalText(record["explanation"], 1024),
  };
}

export function normalizeAutomationSettings(
  value: unknown,
): AutomationSettingsModel {
  const record = readRecord(value, "automation engine settings");
  if (record === null) {
    throw new Error("automation engine settings document is malformed");
  }
  const rawFields = record["fields"];
  if (!Array.isArray(rawFields) || rawFields.length === 0) {
    throw new Error(
      "automation engine settings document has no field metadata",
    );
  }
  const fields = rawFields.map(normalizeField);
  const target = normalizeTarget(record["target"]);
  const rawConsumers = optionalRecord(record["consumers"]);
  const consumers =
    rawConsumers === null
      ? []
      : Object.entries(rawConsumers).map(([service, item]) =>
          normalizeConsumer(service, item),
        );
  const adoption = optionalRecord(record["adoption"]);
  const rawUnavailable = optionalRecord(record["unavailable"]);
  const reportedAllAdopted = adoption?.["allAdopted"] === true;
  // The collective claim covers the resident *cadence* consumers only. The
  // API-local capacity evidence has a different basis (it is read by the
  // admission/observation boundary itself), so including it would render a real
  // deployment-wide adoption as "pending" forever.
  const cadenceConsumers = consumers.filter(
    (consumer) => consumer.basis !== "api_local",
  );
  const allAdopted =
    reportedAllAdopted &&
    cadenceConsumers.length > 0 &&
    cadenceConsumers.every((consumer) => consumer.adopted);
  return {
    target,
    fields,
    consumers,
    adoption: {
      consumers:
        adoption === null
          ? 0
          : normalizeBoundedCount(adoption["consumers"], "consumers"),
      adoptedConsumers:
        adoption === null
          ? 0
          : normalizeBoundedCount(
              adoption["adoptedConsumers"],
              "adoptedConsumers",
            ),
      allAdopted,
    },
    canManage: record["canManage"] === true,
    configRecheckSeconds:
      optionalNumber(record["configRecheckSeconds"], "configRecheckSeconds") ??
      5,
    unavailable:
      rawUnavailable === null
        ? null
        : {
            reason: boundedText(rawUnavailable["reason"], "unavailable"),
            durableState: boundedText(rawUnavailable["durableState"]),
            nextAction: boundedText(rawUnavailable["nextAction"]),
          },
    asOf: optionalText(record["asOf"], 64),
  };
}

/**
 * The exact submit body. Every field is required and sent as a number: the
 * browser never truncates with `parseInt`, so a fractional or out-of-range
 * value reaches the backend's real validation instead of being silently
 * coerced into a different published setting.
 *
 * `submissionId` names exactly this request. The backend binds it into durable
 * audit evidence, so an unknown outcome is reconciled against *this*
 * submission's own publication rather than against equal values another writer
 * happened to publish.
 */
export function automationSettingsBody(
  values: Readonly<Record<string, string>>,
  target: Pick<
    PublishedTargetView,
    "revisionId" | "revisionVersion" | "digest"
  >,
  submissionId?: string | null,
): Record<string, unknown> {
  const settings: Record<string, number | null> = {};
  for (const field of AUTOMATION_ENGINE_FIELDS) {
    const raw = values[field];
    const parsed = raw === undefined ? Number.NaN : Number(raw.trim());
    // A non-numeric entry is sent as `null` rather than as `NaN`, because JSON
    // cannot carry NaN and silently dropping it would send a *different* request
    // than the one the operator made — and a different one than reconciliation
    // needs to identify. `null` is refused by the backend's type validation,
    // which is exactly the refusal the operator must be able to correct.
    settings[field] = Number.isFinite(parsed) ? parsed : null;
  }
  return {
    settings,
    expectedRevisionId: target.revisionId,
    expectedRevisionVersion: target.revisionVersion,
    expectedDigest: target.digest,
    ...(submissionId === undefined || submissionId === null
      ? {}
      : { submissionId }),
  };
}

export type EngineSubmissionState =
  "committed" | "superseded" | "not_committed" | "unresolved";

/**
 * The reconciliation body for one *identified* submission.
 *
 * The typed values alone cannot prove anything: they are sent together with
 * the submission identity so the backend resolves that request's own durable
 * trail. A submission with no identity is reported as unresolved rather than
 * being credited with whatever the current target happens to say.
 */
export function automationSettingsReconcileBody(
  values: Readonly<Record<string, number | null>>,
  submissionId: string,
): Record<string, unknown> {
  const settings: Record<string, number | null> = {};
  for (const field of AUTOMATION_ENGINE_FIELDS) {
    const raw = values[field];
    // The identical content the Save carried: a `null` entry stays `null` so the
    // backend's content fingerprint matches the refused request exactly.
    settings[field] = raw === undefined ? null : raw;
  }
  return { reconcile: true, settings, submissionId };
}
