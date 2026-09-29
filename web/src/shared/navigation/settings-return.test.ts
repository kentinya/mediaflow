import { describe, expect, it } from "vitest";
import {
  readSettingsReturnContext,
  settingsReturnDestination,
  settingsReturnSearch,
} from "./settings-return";

describe("Settings return context", () => {
  it("round-trips one allowlisted business destination", () => {
    const search = settingsReturnSearch({
      target: "resource-files",
      libraryId: "source-1",
      path: "Season 01",
    });
    const context = readSettingsReturnContext(search);
    expect(context).toEqual({
      target: "resource-files",
      libraryId: "source-1",
      path: "Season 01",
    });
    expect(settingsReturnDestination(context!)).toEqual({
      to: "/resourcelib/files",
      search: { resourceLibraryId: "source-1", path: "Season 01" },
    });
  });

  it.each([
    { returnTo: "https://evil.example" },
    { returnTo: "storage", returnPath: "secret" },
    { returnTo: "resource-files", returnPath: "../escape" },
    { returnTo: "media-files", returnLibraryId: "bad/id" },
  ])("rejects unsafe or unsupported return state", (search) => {
    expect(readSettingsReturnContext(search)).toBeNull();
  });

  it("carries only the allowlisted section for a Rules handoff", () => {
    const search = settingsReturnSearch({
      target: "rules",
      section: "recognitionTypes",
    });
    expect(search).toEqual({
      returnTo: "rules",
      returnSection: "recognitionTypes",
    });
    const context = readSettingsReturnContext(search);
    expect(context).toEqual({ target: "rules", section: "recognitionTypes" });
    expect(settingsReturnDestination(context!)).toEqual({
      to: "/rules",
      search: { section: "recognitionTypes" },
    });
    // An Overview handoff carries nothing but the target itself.
    expect(settingsReturnSearch({ target: "rules" })).toEqual({
      returnTo: "rules",
    });
    expect(settingsReturnDestination({ target: "rules" })).toEqual({
      to: "/rules",
      search: {},
    });
  });

  it("refuses to carry a path, identity or unknown family out of Rules", () => {
    for (const search of [
      { returnTo: "rules", returnLibraryId: "source-1" },
      { returnTo: "rules", returnPath: "Season 01" },
      { returnTo: "rules", returnSection: "not-a-family" },
      { returnTo: "rules", returnSection: "recognitionTypes/../../storage" },
      // A digest, revision or credential value is never a valid section.
      { returnTo: "rules", returnSection: "sha256:abcdef" },
      { returnTo: "rules", returnSection: "Bearer abc" },
      { returnTo: "storage", returnSection: "recognitionTypes" },
    ]) {
      expect(readSettingsReturnContext(search)).toBeNull();
    }
  });

  it("does not carry authority or tokens", () => {
    const encoded = JSON.stringify(settingsReturnSearch({ target: "storage" }));
    expect(encoded).toBe('{"returnTo":"storage"}');
    expect(
      JSON.stringify(
        settingsReturnSearch({ target: "rules", section: "typeBindings" }),
      ),
    ).toBe('{"returnTo":"rules","returnSection":"typeBindings"}');
  });
});
