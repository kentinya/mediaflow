import { describe, expect, it } from "vitest";
import {
  ResourceLibrarySaveNormalizationError,
  normalizeResourceLibrarySave,
} from "./resource-library";

const response = {
  resourceLibrary: {
    id: "new-library",
    name: "New Library",
    storageId: "local-1",
    storagePath: "incoming/new",
    enabled: true,
  },
  active: { revisionId: "rev-2", status: "active", version: 2 },
};

describe("normalizeResourceLibrarySave", () => {
  it("keeps the exact candidate and immutable Active identity", () => {
    expect(normalizeResourceLibrarySave(response)).toEqual({
      id: "new-library",
      name: "New Library",
      storageId: "local-1",
      storagePath: "incoming/new",
      enabled: true,
      activeRevisionId: "rev-2",
    });
  });

  it("represents a disabled saved library truthfully and accepts Storage root", () => {
    const model = normalizeResourceLibrarySave({
      ...response,
      resourceLibrary: {
        ...response.resourceLibrary,
        enabled: false,
        storagePath: "",
      },
    });
    expect(model).toMatchObject({
      id: "new-library",
      enabled: false,
      storagePath: "",
    });
  });

  it.each([
    [
      "invalid ID",
      {
        ...response,
        resourceLibrary: { ...response.resourceLibrary, id: "../outside" },
      },
    ],
    ["missing Active identity", { ...response, active: { status: "active" } }],
    [
      "non-Active status",
      { ...response, active: { revisionId: "rev-2", status: "draft" } },
    ],
  ])("rejects %s", (_label, payload) => {
    expect(() => normalizeResourceLibrarySave(payload)).toThrow(
      ResourceLibrarySaveNormalizationError,
    );
  });
});
