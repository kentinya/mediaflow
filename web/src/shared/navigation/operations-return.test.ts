import { describe, expect, it } from "vitest";
import {
  OPERATIONS_RETURN_KEY,
  operationsLandingSearch,
  operationsReturnContextFromSearch,
  operationsReturnSearch,
  parseOperationsReturnContext,
  readOperationsReturnContext,
} from "./operations-return";

describe("operations return context", () => {
  it("reads only the bounded serialized context", () => {
    expect(
      readOperationsReturnContext({
        [OPERATIONS_RETURN_KEY]: "status=failed&q=matrix",
      }),
    ).toBe("status=failed&q=matrix");
    // Absent or non-string means "not Operations-originated".
    expect(readOperationsReturnContext({ status: "failed" })).toBeNull();
    expect(readOperationsReturnContext(null)).toBeNull();
    expect(
      readOperationsReturnContext({ [OPERATIONS_RETURN_KEY]: 7 }),
    ).toBeNull();
    // An empty-but-present context still marks the journey origin.
    expect(readOperationsReturnContext({ [OPERATIONS_RETURN_KEY]: "" })).toBe(
      "",
    );
  });

  it("drops tampered or oversized values instead of entering a URL", () => {
    const hostile = [
      "token=abc123",
      "cursor=" + "A".repeat(600),
      "q=%2e%2e%2f%2e%2e%2fetc",
      "status=../../dashboard",
      "returnOps=q=x",
      "attention=1&dir=aside",
    ];
    for (const value of hostile) {
      // Out-of-grammar serialization degrades to "not Operations-originated";
      // anything that survives is re-parsed key by key below.
      const context = readOperationsReturnContext({
        [OPERATIONS_RETURN_KEY]: value,
      });
      const parsed = parseOperationsReturnContext(context);
      // No hostile key ever reaches the parsed record.
      expect(parsed["token"]).toBeUndefined();
      expect(parsed["returnOps"]).toBeUndefined();
      expect(
        parsed["attention"] === true ? "true" : parsed["attention"],
      ).not.toBe("1");
      expect(parsed["dir"] ?? "forward").toBe("forward");
      if (parsed["cursor"] !== undefined) {
        expect(String(parsed["cursor"]).length).toBeLessThanOrEqual(512);
      }
      if (parsed["status"] !== undefined) {
        expect(parsed["status"]).toMatch(/^[a-z][a-z0-9_]{0,31}$/);
      }
    }
  });

  it("re-validates every preserved key through the published grammar", () => {
    const parsed = parseOperationsReturnContext(
      "status=waiting_confirm&command=manual_organize_execute&q=%E7%9F%A9%E9%98%B5" +
        "&from=2026-01-01&to=2026-02-01T10:00:00Z&attention=true" +
        "&cursor=abc123&dir=backward&run=run-1&tab=items&istat=success" +
        "&rkind=result&item=item-1&icur=x&rcur=y&idir=forward&rdir=bogus",
    );
    expect(parsed["status"]).toBe("waiting_confirm");
    expect(parsed["command"]).toBe("manual_organize_execute");
    expect(parsed["q"]).toBe("矩阵");
    expect(parsed["from"]).toBe("2026-01-01");
    expect(parsed["attention"]).toBe(true);
    expect(parsed["cursor"]).toBe("abc123");
    expect(parsed["dir"]).toBe("backward");
    expect(parsed["run"]).toBe("run-1");
    expect(parsed["tab"]).toBe("items");
    expect(parsed["item"]).toBe("item-1");
    // An out-of-grammar direction is dropped, not defaulted in.
    expect(parsed["rdir"]).toBeUndefined();
    expect(parseOperationsReturnContext(null)).toEqual({});
    expect(parseOperationsReturnContext("")).toEqual({});
  });

  it("restores the preserved view or selects the admitted run", () => {
    const context =
      "status=failed&run=older-selected&cursor=abc&tab=items&item=old-item";
    // A plain back/cancel return restores the exact previous selection and
    // its detail view unchanged.
    expect(operationsLandingSearch(context, null)).toEqual({
      status: "failed",
      run: "older-selected",
      cursor: "abc",
      tab: "items",
      item: "old-item",
    });
    // Returning with the admitted run replaces the stale selection and drops
    // the detail keys that addressed the *other* run's evidence.
    expect(operationsLandingSearch(context, "admitted-task-1")).toEqual({
      status: "failed",
      cursor: "abc",
      run: "admitted-task-1",
    });
    // Without any context the landing keeps the default view plus the run.
    expect(operationsLandingSearch(null, "run-2")).toEqual({ run: "run-2" });
    expect(operationsLandingSearch("", null)).toEqual({});
    // An out-of-grammar run identity never addresses other work.
    expect(operationsLandingSearch("status=failed", "../tasks/other")).toEqual({
      status: "failed",
    });
  });

  it("serializes the submitted list state without nesting the context key", () => {
    const context = operationsReturnContextFromSearch({
      status: "failed",
      attention: true,
      q: "long title",
      run: "selected-1",
      cursor: "abc",
      dir: "forward",
      [OPERATIONS_RETURN_KEY]: "q=never-nested",
    });
    expect(context).toBe(
      "status=failed&attention=true&q=long+title&run=selected-1&cursor=abc&dir=forward",
    );
    expect(
      readOperationsReturnContext({ [OPERATIONS_RETURN_KEY]: context }),
    ).toBe(context);
    const roundTrip = parseOperationsReturnContext(context);
    expect(roundTrip["status"]).toBe("failed");
    expect(roundTrip["attention"]).toBe(true);
    expect(roundTrip["q"]).toBe("long title");
    expect(roundTrip[OPERATIONS_RETURN_KEY]).toBeUndefined();
  });

  it("carries the context through the journey search record", () => {
    expect(operationsReturnSearch(null)).toEqual({});
    expect(operationsReturnSearch("")).toEqual({ [OPERATIONS_RETURN_KEY]: "" });
    expect(operationsReturnSearch("status=failed")).toEqual({
      [OPERATIONS_RETURN_KEY]: "status=failed",
    });
  });
});
