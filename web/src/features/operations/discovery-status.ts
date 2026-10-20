/**
 * Bounded Chinese labels for one discovery preparation status token.
 *
 * Kept outside the discovery page so any feature that must name the last
 * known durable state of an admitted preparation (the operations landing's
 * remaining-scope read recovery) uses exactly the same wording without
 * importing a page component.
 */

export const DISCOVERY_STATUS_LABELS: Readonly<Record<string, string>> = {
  queued: "排队中",
  running: "发现中",
  paused: "已暂停",
  waiting_stability: "等待稳定",
  completed: "发现完成",
  partial_success: "部分完成",
  failed: "失败",
  cancelled: "已取消",
};
