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

  it("does not carry authority or tokens", () => {
    const encoded = JSON.stringify(settingsReturnSearch({ target: "storage" }));
    expect(encoded).toBe('{"returnTo":"storage"}');
  });
});
