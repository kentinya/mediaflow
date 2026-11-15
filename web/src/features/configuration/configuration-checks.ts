/**
 * The exact-revision publish checks shown before a checked activation.
 *
 * The backend owns applicability and the final decision: checked activation
 * re-evaluates the referenced Storages, the Recognition Strategy Test and the
 * destination precheck against the exact revision version and digest. This
 * module mirrors that bounded requirement set from the same revision read, so
 * the operator sees which item is missing, failed or stale and can run it from
 * this page. It never treats local evidence as publication authority and never
 * grants execution, overwrite or delete permission.
 */

export type PublishCheckKind = "storage" | "strategy" | "destination";

export type PublishCheckState = "passed" | "failed" | "missing" | "stale";

export interface CheckStorage {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly enabled: boolean;
}

export interface CheckLibrary {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly storageId: string | null;
}

export interface CheckRecognitionType {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
}

export interface CheckPolicy {
  readonly id: string;
  readonly enabled: boolean;
}

/** The enabled chain one RecognitionType policy binds for destination use. */
export interface CheckTypePolicy {
  readonly enabled: boolean;
  readonly recognitionType: string;
  readonly namingPolicy: string;
  readonly classificationPolicy: string;
  readonly organizePolicy: string;
}

export interface CheckClassificationPolicy {
  readonly id: string;
  readonly enabled: boolean;
  /** MediaLibraries explicitly referenced by at least one classification rule. */
  readonly mediaLibraryIds: readonly string[];
}

export interface CheckObjects {
  readonly storages: readonly CheckStorage[];
  readonly resourceLibraries: readonly CheckLibrary[];
  readonly mediaLibraries: readonly CheckLibrary[];
  readonly recognitionTypes: readonly CheckRecognitionType[];
  readonly recognitionTypePolicies: readonly CheckTypePolicy[];
  readonly namingPolicies: readonly CheckPolicy[];
  readonly organizePolicies: readonly CheckPolicy[];
  readonly classificationPolicies: readonly CheckClassificationPolicy[];
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

const text = (value: unknown): string =>
  typeof value === "string" ? value : "";

const bool = (value: unknown, fallback: boolean): boolean =>
  typeof value === "boolean" ? value : fallback;

function records(value: unknown): readonly Record<string, unknown>[] {
  return Array.isArray(value)
    ? value
        .map((item) => asRecord(item))
        .filter((item): item is Record<string, unknown> => item !== null)
    : [];
}

/**
 * Read the bounded object projection of one revision read.
 *
 * A storage, library or recognition type that the backend did not project is
 * absent rather than invented: an unresolved reference stays visibly missing
 * so the operator corrects it instead of the page guessing a target.
 */
export function readCheckObjects(value: unknown): CheckObjects {
  const objects = asRecord(value) ?? {};
  const storages = records(objects.storages).map((item) => ({
    id: text(item.id),
    name: text(item.name),
    type: text(item.type),
    enabled: bool(item.enabled, true),
  }));
  const library = (item: Record<string, unknown>): CheckLibrary => ({
    id: text(item.id),
    name: text(item.name),
    enabled: bool(item.enabled, true),
    storageId: text(item.storageId) === "" ? null : text(item.storageId),
  });
  return {
    storages,
    resourceLibraries: records(objects.resourceLibraries).map(library),
    mediaLibraries: records(objects.mediaLibraries).map(library),
    recognitionTypes: records(objects.recognitionTypes).map((item) => ({
      id: text(item.id),
      name: text(item.name),
      enabled: bool(item.enabled, true),
    })),
    recognitionTypePolicies: records(objects.recognitionTypePolicies).map(
      (item) => ({
        enabled: bool(item.enabled, true),
        recognitionType: text(item.recognitionType),
        namingPolicy: text(item.namingPolicy),
        classificationPolicy: text(item.classificationPolicy),
        organizePolicy: text(item.organizePolicy),
      }),
    ),
    namingPolicies: records(objects.namingPolicies).map((item) => ({
      id: text(item.id),
      enabled: bool(item.enabled, true),
    })),
    organizePolicies: records(objects.organizePolicies).map((item) => ({
      id: text(item.id),
      enabled: bool(item.enabled, true),
    })),
    classificationPolicies: records(objects.classificationPolicies).map(
      (item) => ({
        id: text(item.id),
        enabled: bool(item.enabled, true),
        mediaLibraryIds: records(item.rules)
          .map((rule) => {
            const result = asRecord(rule.result) ?? rule;
            return text(result.mediaLibraryId);
          })
          .filter((id) => id !== ""),
      }),
    ),
  };
}

/**
 * Whether checked activation requires a destination precheck for this Draft.
 *
 * This mirrors the backend's own bounded requirement: at least one enabled
 * MediaLibrary reachable through an enabled RecognitionType policy whose
 * naming, classification and organize policies are all enabled and whose
 * classification policy has a rule that explicitly names that library. An
 * ambiguous or missing reference is not guessed at.
 */
export function destinationPrecheckApplicable(objects: CheckObjects): boolean {
  const libraryIds = new Set(
    objects.mediaLibraries
      .filter((library) => library.enabled)
      .map((library) => library.id),
  );
  if (libraryIds.size === 0) return false;
  const namingIds = new Set(
    objects.namingPolicies
      .filter((policy) => policy.enabled)
      .map((policy) => policy.id),
  );
  const organizeIds = new Set(
    objects.organizePolicies
      .filter((policy) => policy.enabled)
      .map((policy) => policy.id),
  );
  const typeIds = new Set(
    objects.recognitionTypes
      .filter((type) => type.enabled)
      .map((type) => type.id),
  );
  for (const policy of objects.recognitionTypePolicies) {
    if (!policy.enabled) continue;
    if (!typeIds.has(policy.recognitionType)) continue;
    if (!namingIds.has(policy.namingPolicy)) continue;
    if (!organizeIds.has(policy.organizePolicy)) continue;
    const classification = objects.classificationPolicies.find(
      (candidate) => candidate.id === policy.classificationPolicy,
    );
    if (classification === undefined || !classification.enabled) continue;
    if (classification.mediaLibraryIds.some((id) => libraryIds.has(id))) {
      return true;
    }
  }
  return false;
}

export interface CheckEvidenceSnapshot {
  readonly storageChecks: readonly Record<string, unknown>[];
  readonly strategyTest: Record<string, unknown> | null;
  readonly destinationPrecheck: Record<string, unknown> | null;
}

export function readCheckEvidence(
  detail: Record<string, unknown>,
): CheckEvidenceSnapshot {
  return {
    storageChecks: records(detail.storageChecks),
    strategyTest: asRecord(detail.recognitionStrategyTest),
    destinationPrecheck: asRecord(detail.destinationPrecheck),
  };
}

export interface PublishCheckItem {
  readonly id: string;
  readonly kind: PublishCheckKind;
  /** Operator-facing title naming the exact checked object. */
  readonly title: string;
  readonly state: PublishCheckState;
  readonly stateLabel: string;
  /** Chinese statement of what the check observed. */
  readonly detail: string;
  /** Chinese next step when the check is not satisfied. */
  readonly nextAction: string | null;
  /** The backend's own bounded message, kept for diagnostics. */
  readonly backendMessage: string | null;
  readonly backendNextAction: string | null;
  readonly checkedAt: string | null;
  readonly storageId: string | null;
}

export interface PublishCheckModel {
  readonly items: readonly PublishCheckItem[];
  readonly applicable: number;
  readonly satisfied: boolean;
  /** Chinese titles of the items that still need a successful run. */
  readonly blocking: readonly string[];
  /** Enabled ResourceLibraries a strategy test may bind to. */
  readonly strategyLibraries: readonly CheckOption[];
  /** Enabled RecognitionTypes a destination sample may select. */
  readonly recognitionTypeOptions: readonly CheckOption[];
}

export interface CheckOption {
  readonly id: string;
  readonly label: string;
}

const STATE_LABELS: Readonly<Record<PublishCheckState, string>> = {
  passed: "已通过",
  failed: "未通过",
  missing: "未运行",
  stale: "已过期",
};

/** Chinese wording for the backend's Storage check failure categories. */
const STORAGE_FAILURES: Readonly<
  Record<string, { readonly label: string; readonly nextAction: string }>
> = {
  missing_secret: {
    label: "部署凭据未配置",
    nextAction: "请先在部署环境为该存储配置所需凭据，然后重新运行检查。",
  },
  permission_denied: {
    label: "权限不足",
    nextAction: "请确认部署凭据与根路径权限，纠正后重新运行检查。",
  },
  authentication_failed: {
    label: "认证失败",
    nextAction: "请确认部署凭据有效，纠正后重新运行检查。",
  },
  invalid_path: {
    label: "根路径无效",
    nextAction: "请修正存储根路径使其存在且可读，然后重新运行检查。",
  },
  not_found: {
    label: "根路径不存在",
    nextAction: "请确认存储根路径存在，纠正后重新运行检查。",
  },
  connection_failed: {
    label: "连接失败",
    nextAction: "请确认存储服务可访问后重新运行检查。",
  },
  timeout: {
    label: "连接超时",
    nextAction: "请确认存储服务可访问后重新运行检查。",
  },
  rate_limited: {
    label: "被存储服务限流",
    nextAction: "请稍候再重新运行检查。",
  },
  unsupported_operation: {
    label: "存储不支持所需操作",
    nextAction: "请核对存储类型与根路径可读能力后重新运行检查。",
  },
  disabled: {
    label: "存储已停用",
    nextAction: "请启用该存储或取消引用，然后重新运行检查。",
  },
  invalid_configuration: {
    label: "存储配置无效",
    nextAction: "请修正该存储的连接配置后重新运行检查。",
  },
  read_only_violation: {
    label: "只读约束被违反",
    nextAction: "检查发现了写入副作用；请不要激活，先核对存储配置。",
  },
  capacity_unavailable: {
    label: "检查并发已满",
    nextAction: "请稍候片刻再重新运行检查。",
  },
  worker_unavailable: {
    label: "检查执行器暂不可用",
    nextAction: "请稍候再重新运行检查。",
  },
  unknown: {
    label: "未知错误",
    nextAction: "请核对存储配置与部署凭据后重新运行检查。",
  },
};

const DEFAULT_STORAGE_FAILURE = {
  label: "检查未通过",
  nextAction: "请核对存储配置与部署凭据后重新运行检查。",
} as const;

export function storageFailureCopy(category: unknown): {
  readonly label: string;
  readonly nextAction: string;
} {
  const key = typeof category === "string" ? category : "";
  return STORAGE_FAILURES[key] ?? DEFAULT_STORAGE_FAILURE;
}

const RECOGNITION_STATUS: Readonly<Record<string, string>> = {
  matched: "已匹配识别规则",
  ambiguous: "匹配到多个识别类型，需要核对规则优先级",
  unrecognized: "没有匹配的识别规则，不会阻止激活，但请核对识别规则",
};

/** Chinese wording for the destination precheck's projected outcome. */
const DESTINATION_VERDICTS: Readonly<Record<string, string>> = {
  ready: "目标可正常写入",
  skip: "目标已存在，将按冲突策略跳过",
  rename: "目标已存在，将按冲突策略改名",
  overwrite_requires_confirmation: "目标已存在，覆盖需要显式授权",
  manual_confirmation_required: "目标冲突将进入人工确认",
  capability_gap: "目标存储缺少所需能力",
};

export function destinationVerdictLabel(verdict: unknown): string | null {
  const key = typeof verdict === "string" ? verdict : "";
  return DESTINATION_VERDICTS[key] ?? null;
}

const DESTINATION_FAILURES: Readonly<
  Record<string, { readonly label: string; readonly nextAction: string }>
> = {
  invalid_rule: {
    label: "没有分类规则匹配该示例",
    nextAction:
      "请调整示例的题材或国家，或修正分类规则使其匹配该示例，然后重新运行预检。",
  },
  missing_type_policy: {
    label: "识别类型缺少策略绑定",
    nextAction: "请为该识别类型绑定命名、分类与整理策略，然后重新运行预检。",
  },
  duplicate_type_policy: {
    label: "识别类型存在重复策略绑定",
    nextAction: "请只保留一个启用的策略绑定，然后重新运行预检。",
  },
  invalid_policy_reference: {
    label: "策略引用无效",
    nextAction:
      "请修正识别类型策略引用的命名、分类或整理策略，然后重新运行预检。",
  },
  policy_disabled: {
    label: "策略已停用",
    nextAction:
      "请启用对应策略，或为该识别类型绑定启用的策略，然后重新运行预检。",
  },
  recognition_type_disabled: {
    label: "识别类型已停用",
    nextAction: "请启用该识别类型或改用已启用的识别类型，然后重新运行预检。",
  },
  unresolved_media_library: {
    label: "分类结果引用的媒体库不存在",
    nextAction: "请修正分类规则中的媒体库引用，然后重新运行预检。",
  },
  missing_destination_root: {
    label: "目标库根路径不存在",
    nextAction: "请创建根路径或修正媒体库的相对根路径，然后重新运行预检。",
  },
  destination_root_not_directory: {
    label: "目标库根路径不是目录",
    nextAction: "请修正媒体库的相对根路径，然后重新运行预检。",
  },
  permission_denied: {
    label: "目标存储权限不足",
    nextAction: "请确认目标存储凭据与目录权限后重新运行预检。",
  },
  not_found: {
    label: "目标路径不存在",
    nextAction: "请确认目标存储与路径可访问后重新运行预检。",
  },
  unsafe_destination: {
    label: "目标路径不安全",
    nextAction:
      "请修正分类规则或命名模板生成的安全相对路径，然后重新运行预检。",
  },
  invalid_configuration: {
    label: "目标配置无效",
    nextAction: "请核对目标存储与媒体库配置后重新运行预检。",
  },
  duplicate_destination: {
    label: "示例目标互相冲突",
    nextAction:
      "请调整示例或命名/分类规则使不同输入得到不同目标，然后重新运行预检。",
  },
  read_only_violation: {
    label: "预检发现写入副作用",
    nextAction: "请不要激活，先核对目标预检实现是否保持只读。",
  },
  unavailable: {
    label: "暂不可用",
    nextAction: "请稍候再重新运行预检。",
  },
  timeout: {
    label: "预检超时",
    nextAction: "请确认存储可用后重新运行预检。",
  },
  invalid_input: {
    label: "示例输入不合法",
    nextAction: "请修正示例字段后重新运行预检。",
  },
  invalid: {
    label: "目标无法安全推算",
    nextAction: "请核对整理策略的冲突设置后重新运行预检。",
  },
};

const DEFAULT_DESTINATION_FAILURE = {
  label: "预检未通过",
  nextAction: "请核对目标存储、媒体库与策略链后重新运行预检。",
} as const;

export function destinationFailureCopy(category: unknown): {
  readonly label: string;
  readonly nextAction: string;
} {
  const key = typeof category === "string" ? category : "";
  return DESTINATION_FAILURES[key] ?? DEFAULT_DESTINATION_FAILURE;
}

function item(value: Omit<PublishCheckItem, "stateLabel">): PublishCheckItem {
  return { ...value, stateLabel: STATE_LABELS[value.state] };
}

function storageItem(
  storage: CheckStorage | null,
  storageId: string,
  check: Record<string, unknown> | null,
): PublishCheckItem {
  const storageName =
    storage === null
      ? storageId
      : storage.name.trim() === ""
        ? storage.id
        : `${storage.name}（${storage.id}）`;
  const base = {
    id: `storage:${storageId}`,
    kind: "storage" as const,
    title: `存储只读检查：${storageName}`,
    storageId,
  };
  if (storage === null) {
    return item({
      ...base,
      state: "failed",
      detail: "该草稿引用的存储在修订中不存在，无法完成只读检查。",
      nextAction: "请在整理规则或存储管理中补齐该存储引用，然后重新验证草稿。",
      backendMessage: null,
      backendNextAction: null,
      checkedAt: null,
    });
  }
  if (check === null) {
    return item({
      ...base,
      state: "missing",
      detail: "该存储尚未在此编辑版本上运行只读检查。",
      nextAction: "请运行该存储的只读检查。",
      backendMessage: null,
      backendNextAction: null,
      checkedAt: null,
    });
  }
  const stale = check.stale === true;
  const checkedAt = text(check.checkedAt) === "" ? null : text(check.checkedAt);
  const backendMessage =
    text(check.message) === "" ? null : text(check.message);
  const backendNextAction =
    text(check.nextAction) === "" ? null : text(check.nextAction);
  if (stale) {
    return item({
      ...base,
      state: "stale",
      detail: "该检查针对的编辑版本或凭据状态已经变化，需要重新运行。",
      nextAction: "请重新运行该存储的只读检查。",
      backendMessage,
      backendNextAction,
      checkedAt,
    });
  }
  if (check.status === "passed") {
    return item({
      ...base,
      state: "passed",
      detail: "只读根检查通过，存储可读。",
      nextAction: null,
      backendMessage: null,
      backendNextAction: null,
      checkedAt,
    });
  }
  const failure = storageFailureCopy(check.failureCategory);
  return item({
    ...base,
    state: "failed",
    detail: `只读检查未通过：${failure.label}。`,
    nextAction: failure.nextAction,
    backendMessage,
    backendNextAction,
    checkedAt,
  });
}

function strategyItem(
  resourceLibraries: readonly CheckLibrary[],
  evidence: Record<string, unknown> | null,
): PublishCheckItem | null {
  if (!resourceLibraries.some((library) => library.enabled)) return null;
  const base = {
    id: "strategy",
    kind: "strategy" as const,
    title: "识别策略测试",
    storageId: null,
  };
  if (evidence === null) {
    return item({
      ...base,
      state: "missing",
      detail: "该编辑版本尚未运行识别策略测试。",
      nextAction: "验证草稿后，用下方所选资源库与合成文件名运行测试。",
      backendMessage: null,
      backendNextAction: null,
      checkedAt: null,
    });
  }
  const checkedAt =
    text(evidence.testedAt) === "" ? null : text(evidence.testedAt);
  const backendMessage =
    text(evidence.message) === "" ? null : text(evidence.message);
  const backendNextAction =
    text(evidence.nextAction) === "" ? null : text(evidence.nextAction);
  if (evidence.stale === true) {
    return item({
      ...base,
      state: "stale",
      detail: "该测试针对的编辑版本已经变化，需要重新运行。",
      nextAction: "请重新验证草稿，然后重新运行识别策略测试。",
      backendMessage,
      backendNextAction,
      checkedAt,
    });
  }
  if (evidence.status !== "completed") {
    return item({
      ...base,
      state: "failed",
      detail: "识别策略测试未完成，无法确认识别结果。",
      nextAction: "请核对识别规则与所选资源库后重新运行测试。",
      backendMessage,
      backendNextAction,
      checkedAt,
    });
  }
  const result = asRecord(evidence.result);
  const recognition = asRecord(result?.recognition);
  const status = text(recognition?.status);
  const recognitionType = text(recognition?.recognitionType);
  const detail =
    status === ""
      ? "识别策略测试已完成。"
      : `${RECOGNITION_STATUS[status] ?? "识别策略测试已完成"}${
          recognitionType === "" ? "。" : `（识别类型 ${recognitionType}）。`
        }`;
  return item({
    ...base,
    state: "passed",
    detail,
    nextAction:
      status === "unrecognized" || status === "ambiguous"
        ? "建议核对该合成文件名与识别规则；这不阻止 checked 激活。"
        : null,
    backendMessage: null,
    backendNextAction: null,
    checkedAt,
  });
}

function destinationItem(
  mediaLibraries: readonly CheckLibrary[],
  evidence: Record<string, unknown> | null,
): PublishCheckItem | null {
  if (!mediaLibraries.some((library) => library.enabled)) return null;
  const base = {
    id: "destination",
    kind: "destination" as const,
    title: "目标预检",
    storageId: null,
  };
  if (evidence === null) {
    return item({
      ...base,
      state: "missing",
      detail: "该编辑版本尚未运行目标预检。",
      nextAction: "请用下方示例运行只读目标预检。",
      backendMessage: null,
      backendNextAction: null,
      checkedAt: null,
    });
  }
  const checkedAt =
    text(evidence.precheckedAt) === "" ? null : text(evidence.precheckedAt);
  const backendMessage =
    text(evidence.message) === "" ? null : text(evidence.message);
  const backendNextAction =
    text(evidence.nextAction) === "" ? null : text(evidence.nextAction);
  if (evidence.stale === true) {
    return item({
      ...base,
      state: "stale",
      detail: "该预检针对的编辑版本已经变化，需要重新运行。",
      nextAction: "请重新运行目标预检。",
      backendMessage,
      backendNextAction,
      checkedAt,
    });
  }
  const result = asRecord(evidence.result);
  if (evidence.status !== "completed") {
    const failure = destinationFailureCopy(evidence.failureCategory);
    return item({
      ...base,
      state: "failed",
      detail: `目标预检未通过：${failure.label}。`,
      nextAction: failure.nextAction,
      backendMessage,
      backendNextAction,
      checkedAt,
    });
  }
  const verdict = text(result?.verdict);
  if (verdict === "capability_gap") {
    return item({
      ...base,
      state: "failed",
      detail: "目标预检完成，但目标存储缺少当前整理操作所需的全部能力。",
      nextAction: "请更改整理操作或目标存储后重新运行预检。",
      backendMessage,
      backendNextAction,
      checkedAt,
    });
  }
  const destination = text(result?.destinationPath);
  const library = text(result?.mediaLibraryId);
  const verdictLabel = destinationVerdictLabel(verdict);
  return item({
    ...base,
    state: "passed",
    detail: `目标预检通过：${verdictLabel ?? "目标可推算"}${
      library === "" ? "" : `；媒体库 ${library}`
    }${destination === "" ? "" : `；目标路径 ${destination}`}。`,
    nextAction: null,
    backendMessage: null,
    backendNextAction: null,
    checkedAt,
  });
}

/**
 * The exact requirement set checked activation will enforce, derived from the
 * same revision read the page displays.
 */
export function readPublishChecks(
  objects: CheckObjects,
  evidence: CheckEvidenceSnapshot,
): PublishCheckModel {
  const storages = new Map(objects.storages.map((item) => [item.id, item]));
  const referenced: string[] = [];
  for (const library of [
    ...objects.resourceLibraries,
    ...objects.mediaLibraries,
  ]) {
    if (library.storageId === null) continue;
    if (!referenced.includes(library.storageId)) {
      referenced.push(library.storageId);
    }
  }
  const items: PublishCheckItem[] = [];
  for (const storageId of referenced) {
    const storage = storages.get(storageId) ?? null;
    // A disabled Storage is not required by checked activation; a referenced
    // but missing Storage still fails closed and is shown as a correction.
    if (storage !== null && !storage.enabled) continue;
    const check =
      evidence.storageChecks.find(
        (candidate) => text(candidate.storageId) === storageId,
      ) ?? null;
    items.push(storageItem(storage, storageId, check));
  }
  const strategy = strategyItem(
    objects.resourceLibraries,
    evidence.strategyTest,
  );
  if (strategy !== null) items.push(strategy);
  const destination = destinationPrecheckApplicable(objects)
    ? destinationItem(objects.mediaLibraries, evidence.destinationPrecheck)
    : null;
  if (destination !== null) items.push(destination);
  const blocking = items
    .filter((entry) => entry.state !== "passed")
    .map((entry) => entry.title);
  return {
    items,
    applicable: items.length,
    satisfied: blocking.length === 0,
    blocking,
    strategyLibraries: objects.resourceLibraries
      .filter((library) => library.enabled)
      .map((library) => ({
        id: library.id,
        label:
          library.name.trim() === ""
            ? library.id
            : `${library.name}（${library.id}）`,
      })),
    recognitionTypeOptions: objects.recognitionTypes
      .filter((type) => type.enabled)
      .map((type) => ({
        id: type.id,
        label: type.name.trim() === "" ? type.id : `${type.name}（${type.id}）`,
      })),
  };
}
