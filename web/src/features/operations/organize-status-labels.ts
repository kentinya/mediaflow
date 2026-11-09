/**
 * Shared operator wording for durable preparation facts (Slice 53 RO-1).
 *
 * The manual-organize creation workspace and the Files preparation dialog
 * render the same backend preparation status, refusal reasons and worker
 * facts; they must not diverge in what an operator reads. This module owns
 * only bounded display maps — no state, no command, no authority.
 */

export const PREPARATION_STATUS_LABELS: Readonly<Record<string, string>> = {
  queued: "已准备，等待处理 Worker",
  running: "正在有界发现所选范围",
  analyzing: "正在完整分析并生成计划摘要",
  waiting_stability: "等待来源稳定",
  paused: "已暂停",
  completed: "准备完成",
  partial_success: "准备完成（范围不完整）",
  failed: "准备失败",
  cancelled: "已取消",
};

export const REASON_LABELS: Readonly<Record<string, string>> = {
  temporary_file: "临时/下载中的文件",
  unsupported_extension: "非媒体扩展名",
  configured_exclude: "命中配置排除规则",
  excluded_extension_rule: "命中配置的扩展名排除规则",
  not_included: "不满足配置包含规则",
  unsupported_entry_type: "不支持的条目类型",
  symbolic_link: "符号链接",
  unreadable_directory: "目录不可读",
  waiting_minimum_age: "未达到最小文件年龄",
  waiting_stable_size: "等待稳定大小",
  source_changed_since_observation: "观察到文件发生变化",
  configured_depth_exceeded: "超出配置深度",
  safety_depth_limit: "超出安全深度上限",
  unsafe_provider_entry: "存储返回了不安全的条目",
  repeated_provider_cursor: "存储返回了重复游标",
  primary_limit: "来源数量达到上限",
  entry_limit: "检查条目数达到上限",
  directory_limit: "打开目录数达到上限",
  page_limit: "分页次数达到上限",
  depth_limit: "深度达到上限",
  time_limit: "活跃时间达到上限",
  read_failure: "读取失败",
  cursor_repeated: "存储返回了重复游标",
  cursor_invalid: "存储返回了无效游标",
  unreadable: "无法读取",
  eligibility: "不符合整理条件",
  // The verified-source refusals of a Files admission, so a refused sibling in
  // the exact plan summary is explained instead of showing an internal token.
  source_already_organizing: "已属于未结束的整理工作",
  source_owned_by_another_operator: "已被其他操作员未结束的整理工作占用",
  admission_not_committed: "范围变化，未加入整理工作",
};

/** Look up a bounded operator label, falling back to the recorded value. */
export function label(
  map: Readonly<Record<string, string>>,
  value: string,
): string {
  return map[value] ?? value;
}
