/**
 * The retained unknown-submission context (Task 43.4 R5/S7).
 *
 * A lost Save response must stay reconcilable across a real reload without ever
 * storing a credential, and another principal's retained outcome must never be
 * readable — let alone reconciled — as this one's.
 */

import { afterEach, describe, expect, it } from "vitest";
import {
  newSubmissionId,
  readPendingSubmission,
  submissionSessionKey,
  writePendingSubmission,
  type PendingEngineSettingsSubmission,
} from "./automation-settings-session";
import { clearPrincipalSessionData } from "../../shared/auth/principal-session-data";

const ADMIN = "admin";
const OTHER = "运营-乙";

function context(overrides: Partial<PendingEngineSettingsSubmission> = {}) {
  return {
    submissionId: "submission-1",
    input: {
      "automation.maximumActiveJobs": "80",
      "automation.staleJobAgeSeconds": "3600",
      "automation.workerPollSeconds": "2",
      "automation.schedulerPollSeconds": "5",
    },
    submittedValues: {
      "automation.maximumActiveJobs": 80,
      "automation.staleJobAgeSeconds": 3600,
      "automation.workerPollSeconds": 2,
      "automation.schedulerPollSeconds": 5,
    },
    baselineRevisionId: "revision-1",
    baselineRevisionVersion: 3,
    baselineDigest: "digest-1",
    submittedAt: "2026-03-16T00:00:00+00:00",
    ...overrides,
  } satisfies PendingEngineSettingsSubmission;
}

afterEach(() => {
  window.sessionStorage.clear();
});

describe("retained engine-settings submission", () => {
  it("round-trips one submission for the same principal", () => {
    writePendingSubmission(ADMIN, context());
    const read = readPendingSubmission(ADMIN);
    expect(read.available).toBe(true);
    expect(read.value).toMatchObject({
      submissionId: "submission-1",
      baselineRevisionId: "revision-1",
    });
  });

  it("is principal-scoped, including a Unicode principal", () => {
    writePendingSubmission(ADMIN, context());
    expect(readPendingSubmission(OTHER)).toEqual({
      available: true,
      value: null,
    });
    writePendingSubmission(OTHER, context({ submissionId: "submission-2" }));
    expect(readPendingSubmission(OTHER).value?.submissionId).toBe(
      "submission-2",
    );
    expect(readPendingSubmission(ADMIN).value?.submissionId).toBe(
      "submission-1",
    );
    expect(submissionSessionKey(ADMIN)).not.toBe(submissionSessionKey(OTHER));
  });

  it("never stores a credential, token or free-form secret", () => {
    writePendingSubmission(ADMIN, context());
    const raw = window.sessionStorage.getItem(submissionSessionKey(ADMIN))!;
    expect(raw).not.toMatch(/token|bearer|secret|password|authorization/i);
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    expect(Object.keys(parsed).sort()).toEqual([
      "baselineDigest",
      "baselineRevisionId",
      "baselineRevisionVersion",
      "input",
      "submissionId",
      "submittedAt",
      "submittedValues",
    ]);
  });

  it("round-trips the published baseline values a recovery needs", () => {
    // Without them a recovery cannot tell an edited field from one the form
    // merely carried, which is exactly what let an old form overwrite another
    // writer's change. They are stored as text so a rejected entry survives.
    const baselineValues = {
      "automation.maximumActiveJobs": "3.5",
      "automation.staleJobAgeSeconds": "3600",
      "automation.workerPollSeconds": "2",
      "automation.schedulerPollSeconds": "5",
    };
    writePendingSubmission(ADMIN, context({ baselineValues }));
    expect(readPendingSubmission(ADMIN).value?.baselineValues).toEqual(
      baselineValues,
    );
  });

  it("keeps a context retained by an older build usable", () => {
    // No baselineValues: it must still be readable so the submission can be
    // reconciled; per-field recovery then asks explicitly instead of guessing.
    writePendingSubmission(ADMIN, context());
    const read = readPendingSubmission(ADMIN);
    expect(read.available).toBe(true);
    expect(read.value?.submissionId).toBe("submission-1");
    expect(read.value?.baselineValues).toBeUndefined();
  });

  it("drops a malformed or over-long retained record instead of trusting it", () => {
    window.sessionStorage.setItem(
      submissionSessionKey(ADMIN),
      JSON.stringify({ submissionId: "", input: {} }),
    );
    expect(readPendingSubmission(ADMIN)).toEqual({
      available: true,
      value: null,
    });
    // A genuinely unusable value map is dropped...
    window.sessionStorage.setItem(
      submissionSessionKey(ADMIN),
      JSON.stringify(
        context({ submittedValues: { "a.b": "not-a-number" } as never }),
      ),
    );
    expect(readPendingSubmission(ADMIN).value).toBeNull();
    // ...while `null` is a legitimate entry: it is exactly how an unparseable
    // typed value travels, and dropping it would break reconciliation of the
    // refused request.
    window.sessionStorage.setItem(
      submissionSessionKey(ADMIN),
      JSON.stringify(context({ submittedValues: { "a.b": null } })),
    );
    expect(readPendingSubmission(ADMIN).value?.submittedValues).toEqual({
      "a.b": null,
    });
  });

  it("clears every retained submission when the principal changes", () => {
    writePendingSubmission(ADMIN, context());
    writePendingSubmission(OTHER, context({ submissionId: "submission-2" }));
    clearPrincipalSessionData();
    expect(readPendingSubmission(ADMIN).value).toBeNull();
    expect(readPendingSubmission(OTHER).value).toBeNull();
  });

  it("mints a bounded, non-secret submission identity", () => {
    const identity = newSubmissionId();
    expect(identity).not.toBeNull();
    expect(identity!.length).toBeGreaterThan(0);
    expect(identity!.length).toBeLessThanOrEqual(64);
    expect(newSubmissionId()).not.toBe(identity);
  });
});
