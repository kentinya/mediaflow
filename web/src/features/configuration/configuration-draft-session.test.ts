import { afterEach, describe, expect, it } from "vitest";
import {
  readRetainedSettingsSession,
  settingsSessionKey,
  writeRetainedSettingsSession,
  type RetainedSettingsSession,
} from "./configuration-draft-session";
import { clearPrincipalSessionData } from "../../shared/auth/principal-session-data";

const session: RetainedSettingsSession = {
  selectedRevisionId: "draft-1",
  activeGroup: "Logging",
  awaitingVerification: false,
  forms: {
    "draft-1": {
      values: { locale: "en-US", "operationalLogging.enabled": "true" },
      initial: { locale: "zh-CN", "operationalLogging.enabled": "false" },
      authority: {
        kind: "draft",
        revisionId: "draft-1",
        revisionVersion: 4,
        draftVersion: 2,
        digest: "digest-1",
      },
    },
  },
};

afterEach(() => {
  window.sessionStorage.clear();
});

describe("configuration settings session retention", () => {
  it("round-trips the exact input and edit authority for one principal", () => {
    writeRetainedSettingsSession("admin-a", session);
    expect(readRetainedSettingsSession("admin-a")).toEqual({
      available: true,
      value: session,
    });
    // Another principal cannot read the first principal's session.
    expect(readRetainedSettingsSession("admin-b")).toEqual({
      available: true,
      value: null,
    });
    writeRetainedSettingsSession("admin-a", null);
    expect(readRetainedSettingsSession("admin-a")).toEqual({
      available: true,
      value: null,
    });
  });

  it("discards malformed or mismatched records instead of guessing", () => {
    const key = settingsSessionKey("admin-a");
    window.sessionStorage.setItem(key, "{not-json");
    expect(readRetainedSettingsSession("admin-a").available).toBe(false);
    expect(window.sessionStorage.getItem(key)).toBeNull();

    window.sessionStorage.setItem(
      key,
      JSON.stringify({
        ...session,
        forms: {
          "draft-2": session.forms["draft-1"],
        },
      }),
    );
    // The form authority names draft-1 while the map key claims draft-2.
    expect(readRetainedSettingsSession("admin-a").available).toBe(false);
    expect(window.sessionStorage.getItem(key)).toBeNull();
  });

  it("removes every retained Settings session on an explicit principal change", () => {
    writeRetainedSettingsSession("admin-a", session);
    writeRetainedSettingsSession("admin-b", session);
    clearPrincipalSessionData();
    expect(readRetainedSettingsSession("admin-a").value).toBeNull();
    expect(readRetainedSettingsSession("admin-b").value).toBeNull();
  });
});
