/**
 * URL-context contract for the selected-run detail (Slice 42 RO-3).
 *
 * Every value the detail view owns round-trips through the URL, and any
 * value outside its bounded grammar degrades to the safe default instead of
 * being replayed against the server.
 */

import { describe, expect, it } from "vitest";
import {
  DEFAULT_RUN_DETAIL_STATE,
  RUN_DETAIL_SEARCH_KEYS,
  readRunDetailState,
  runDetailStateSearch,
} from "./run-detail-state";

describe("run detail URL state", () => {
  it("defaults to the closed 任务详情 view with no submitted filters", () => {
    expect(readRunDetailState({})).toEqual(DEFAULT_RUN_DETAIL_STATE);
    expect(runDetailStateSearch(DEFAULT_RUN_DETAIL_STATE)).toEqual({});
  });

  it("round-trips every detail value through the URL", () => {
    const state = {
      tab: "records" as const,
      itemStatus: "waiting" as const,
      recordKind: "log" as const,
      evidenceItem: "item-01",
      itemCursor: "abc-_123",
      itemDirection: "backward" as const,
      recordCursor: "def-_456",
      recordDirection: "backward" as const,
    };
    const search = runDetailStateSearch(state);
    expect(search).toEqual({
      tab: "records",
      istat: "waiting",
      rkind: "log",
      item: "item-01",
      icur: "abc-_123",
      idir: "backward",
      rcur: "def-_456",
      rdir: "backward",
    });
    expect(readRunDetailState(search)).toEqual(state);
  });

  it("drops tampered values instead of replaying them", () => {
    const state = readRunDetailState({
      tab: "admin",
      istat: "half_done",
      rkind: "mystery",
      item: "item-01; DROP TABLE",
      icur: "../../etc/passwd",
      idir: "sideways",
      rcur: "cursor with spaces",
      rdir: "",
    });
    expect(state).toEqual(DEFAULT_RUN_DETAIL_STATE);
  });

  it("keeps the search-key set exactly to what this view owns", () => {
    expect([...RUN_DETAIL_SEARCH_KEYS].sort()).toEqual(
      ["icur", "idir", "item", "istat", "rcur", "rdir", "rkind", "tab"].sort(),
    );
  });
});
