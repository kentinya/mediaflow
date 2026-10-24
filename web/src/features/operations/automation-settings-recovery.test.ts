/**
 * Per-field recovery of a focused engine-settings submission (Task 43.4 R2/R5).
 *
 * The table from the review is the contract: an unchanged field keeps the other
 * writer's value, a changed-but-unsaved field keeps the operator's value, an
 * already-equal field needs no publication, and a real same-field overlap needs an
 * explicit choice. A missing baseline (a context retained by an older build) is
 * never guessed.
 */

import { describe, expect, it } from "vitest";
import { planRecovery, sameTypedValue } from "./automation-settings-recovery";

const BASELINE = {
  "automation.maximumActiveJobs": "100",
  "automation.staleJobAgeSeconds": "3600",
  "automation.workerPollSeconds": "2",
  "automation.schedulerPollSeconds": "5",
};

const CURRENT = {
  "automation.maximumActiveJobs": "100",
  "automation.staleJobAgeSeconds": "3600",
  "automation.workerPollSeconds": "2",
  "automation.schedulerPollSeconds": "9",
};

describe("sameTypedValue", () => {
  it("treats numeric formatting as equivalent without truncating", () => {
    expect(sameTypedValue("5", "5.0")).toBe(true);
    expect(sameTypedValue(" 7 ", "7")).toBe(true);
    expect(sameTypedValue("3.5", "3")).toBe(false);
    expect(sameTypedValue("abc", "abc")).toBe(true);
    expect(sameTypedValue("abc", "abd")).toBe(false);
    expect(sameTypedValue("", "")).toBe(true);
  });
});

describe("planRecovery", () => {
  it("keeps another writer's change and the operator's unsaved edit", () => {
    const plan = planRecovery({
      typed: { ...BASELINE, "automation.maximumActiveJobs": "61" },
      baseline: BASELINE,
      current: CURRENT,
    });
    expect(plan.blocked).toBe(false);
    expect(plan.conflicts).toEqual([]);
    // The operator's capacity is kept; the scheduler keeps the other writer's 9.
    expect(plan.input["automation.maximumActiveJobs"]).toBe("61");
    expect(plan.input["automation.schedulerPollSeconds"]).toBe("9");
  });

  it("does not treat a field clicked back to its original value as edited", () => {
    const plan = planRecovery({
      typed: { ...BASELINE },
      baseline: BASELINE,
      current: CURRENT,
    });
    expect(plan.blocked).toBe(false);
    expect(plan.input["automation.schedulerPollSeconds"]).toBe("9");
    expect(plan.notes).toEqual([]);
  });

  it("accepts a value another writer already published as no pending work", () => {
    const plan = planRecovery({
      typed: { ...BASELINE, "automation.schedulerPollSeconds": "9" },
      baseline: BASELINE,
      current: CURRENT,
    });
    expect(plan.blocked).toBe(false);
    expect(plan.input["automation.schedulerPollSeconds"]).toBe("9");
  });

  it("requires an explicit choice when both sides changed the same field", () => {
    const current = { ...BASELINE, "automation.maximumActiveJobs": "90" };
    const typed = { ...BASELINE, "automation.maximumActiveJobs": "61" };
    const plan = planRecovery({ typed, baseline: BASELINE, current });
    expect(plan.blocked).toBe(true);
    expect(plan.conflicts).toEqual(["automation.maximumActiveJobs"]);
    expect(plan.notes[0]).toContain("90");
    expect(plan.notes[0]).toContain("61");

    const keepMine = planRecovery({
      typed,
      baseline: BASELINE,
      current,
      resolutions: { "automation.maximumActiveJobs": "mine" },
    });
    expect(keepMine.blocked).toBe(false);
    expect(keepMine.input["automation.maximumActiveJobs"]).toBe("61");

    const useCurrent = planRecovery({
      typed,
      baseline: BASELINE,
      current,
      resolutions: { "automation.maximumActiveJobs": "current" },
    });
    expect(useCurrent.blocked).toBe(false);
    expect(useCurrent.input["automation.maximumActiveJobs"]).toBe("90");
  });

  it("never guesses a baseline that an older context did not carry", () => {
    const typed = { ...BASELINE, "automation.maximumActiveJobs": "3.5" };
    const plan = planRecovery({ typed, baseline: null, current: CURRENT });
    expect(plan.blocked).toBe(true);
    // Conservative: every field whose suggested value differs from the current
    // publication needs an explicit difference choice, because which fields the
    // operator edited is genuinely unknown here.
    expect(plan.conflicts).toEqual([
      "automation.maximumActiveJobs",
      "automation.schedulerPollSeconds",
    ]);
    // The invalid text stays visible so it can be corrected.
    expect(plan.input["automation.maximumActiveJobs"]).toBe("3.5");
    // A field that already equals the current value is not a conflict.
    expect(plan.conflicts).not.toContain("automation.workerPollSeconds");
  });

  it("keeps an invalid entry verbatim for correction", () => {
    const plan = planRecovery({
      typed: { ...BASELINE, "automation.staleJobAgeSeconds": "90.25" },
      baseline: BASELINE,
      current: CURRENT,
    });
    expect(plan.input["automation.staleJobAgeSeconds"]).toBe("90.25");
  });
});
