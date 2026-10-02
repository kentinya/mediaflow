/**
 * URL-owned state of one selected run's `任务详情` / `操作记录` detail.
 *
 * The active tab, the server-submitted item/record filters, both server
 * cursors and the inspected item live in the URL (never in component state),
 * so a refresh, a browser Back/Forward step and a 401 reconnect all restore
 * the exact detail context — and the auth-continuation allowlist can admit
 * precisely these bounded values. Every value falls back to its safe default
 * when absent or outside its grammar: a tampered URL degrades to the default
 * view instead of being replayed against the server.
 */

import {
  RUN_DETAIL_CURSOR_TOKEN,
  RUN_DETAIL_ITEM_TOKEN,
  RUN_DISPOSITIONS,
  RUN_RECORD_KINDS,
  type RunDisposition,
  type RunRecordKind,
} from "../../entities/operations/run-detail";

/** Every URL key this detail view owns; anything else is left untouched. */
export const RUN_DETAIL_SEARCH_KEYS: ReadonlySet<string> = new Set([
  "tab",
  "istat",
  "rkind",
  "item",
  "icur",
  "idir",
  "rcur",
  "rdir",
]);

export const RUN_DETAIL_TABS = ["detail", "records"] as const;
export type RunDetailTab = (typeof RUN_DETAIL_TABS)[number];

export interface RunDetailState {
  readonly tab: RunDetailTab;
  /** The submitted server-side item disposition filter. */
  readonly itemStatus: RunDisposition | null;
  /** The submitted server-side record kind filter. */
  readonly recordKind: RunRecordKind | null;
  /** The inspected item's evidence (a bounded item identity). */
  readonly evidenceItem: string | null;
  readonly itemCursor: string | null;
  readonly itemDirection: "forward" | "backward";
  readonly recordCursor: string | null;
  readonly recordDirection: "forward" | "backward";
}

export const DEFAULT_RUN_DETAIL_STATE: RunDetailState = {
  tab: "detail",
  itemStatus: null,
  recordKind: null,
  evidenceItem: null,
  itemCursor: null,
  itemDirection: "forward",
  recordCursor: null,
  recordDirection: "forward",
};

function readToken(search: Record<string, unknown>, key: string): string {
  const value = search[key];
  return typeof value === "string" ? value : "";
}

function readDirection(
  search: Record<string, unknown>,
  key: string,
): "forward" | "backward" {
  return readToken(search, key) === "backward" ? "backward" : "forward";
}

export function readRunDetailState(
  search: Record<string, unknown>,
): RunDetailState {
  const rawTab = readToken(search, "tab");
  const rawStatus = readToken(search, "istat");
  const rawKind = readToken(search, "rkind");
  const rawItem = readToken(search, "item");
  const rawItemCursor = readToken(search, "icur");
  const rawRecordCursor = readToken(search, "rcur");
  return {
    tab: rawTab === "records" ? "records" : "detail",
    itemStatus:
      rawStatus !== "" &&
      (RUN_DISPOSITIONS as readonly string[]).includes(rawStatus)
        ? (rawStatus as RunDisposition)
        : null,
    recordKind:
      rawKind !== "" &&
      (RUN_RECORD_KINDS as readonly string[]).includes(rawKind)
        ? (rawKind as RunRecordKind)
        : null,
    evidenceItem:
      rawItem !== "" && RUN_DETAIL_ITEM_TOKEN.test(rawItem) ? rawItem : null,
    itemCursor:
      rawItemCursor !== "" && RUN_DETAIL_CURSOR_TOKEN.test(rawItemCursor)
        ? rawItemCursor
        : null,
    itemDirection: readDirection(search, "idir"),
    recordCursor:
      rawRecordCursor !== "" && RUN_DETAIL_CURSOR_TOKEN.test(rawRecordCursor)
        ? rawRecordCursor
        : null,
    recordDirection: readDirection(search, "rdir"),
  };
}

/**
 * The state as URL search values, omitting every default. The cursor always
 * travels with its direction so the paging buttons can derive their disabled
 * state from the same context the server minted.
 */
export function runDetailStateSearch(
  state: RunDetailState,
): Record<string, string> {
  const search: Record<string, string> = {};
  if (state.tab !== "detail") search["tab"] = state.tab;
  if (state.itemStatus !== null) search["istat"] = state.itemStatus;
  if (state.recordKind !== null) search["rkind"] = state.recordKind;
  if (state.evidenceItem !== null) search["item"] = state.evidenceItem;
  if (state.itemCursor !== null) {
    search["icur"] = state.itemCursor;
    if (state.itemDirection !== "forward") search["idir"] = state.itemDirection;
  }
  if (state.recordCursor !== null) {
    search["rcur"] = state.recordCursor;
    if (state.recordDirection !== "forward") {
      search["rdir"] = state.recordDirection;
    }
  }
  return search;
}
