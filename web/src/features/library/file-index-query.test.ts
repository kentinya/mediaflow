import { describe, expect, it } from "vitest";
import {
  parseCatalogReturnContext,
  serializeCatalogReturnContext,
} from "./file-index-query";

describe("serializeCatalogReturnContext / parseCatalogReturnContext", () => {
  it("round-trips an empty search", () => {
    const before = {
      resourceLibrary: null,
      storage: null,
      scanStatus: null,
      query: null,
      processingDisposition: null,
      recognitionType: null,
      provider: null,
      providerId: null,
      title: null,
      taskId: null,
      year: null,
      after: null,
      cursorFileId: null,
      before: null,
    };
    const serialized = serializeCatalogReturnContext(before);
    expect(serialized).toBe("");
    expect(parseCatalogReturnContext(new URLSearchParams(serialized))).toEqual(
      before,
    );
  });

  it("round-trips a non-empty catalog filter state", () => {
    const before = {
      resourceLibrary: "resources",
      storage: "local-media",
      scanStatus: "ready",
      query: "Matrix",
      processingDisposition: null,
      recognitionType: "Movie",
      provider: "tmdb",
      providerId: "648",
      title: null,
      taskId: null,
      year: "1999",
      after: null,
      cursorFileId: null,
      before: null,
    };
    const serialized = serializeCatalogReturnContext(before);
    expect(serialized).toContain("q_resourceLibrary=resources");
    expect(serialized).toContain("q_storage=local-media");
    expect(serialized).toContain("q_query=Matrix");
    expect(serialized).not.toContain("processingDisposition");
    const restored = parseCatalogReturnContext(new URLSearchParams(serialized));
    expect(restored).toEqual(before);
  });

  it("ignores q_ prefixes unknown to the allowlist", () => {
    const params = new URLSearchParams("q_resourceLibrary=resources&foo=bar");
    expect(parseCatalogReturnContext(params).resourceLibrary).toBe("resources");
    // `foo` is not part of FileIndexCatalogSearchState and must be silently ignored.
    expect(Object.keys(parseCatalogReturnContext(params))).not.toContain("foo");
  });
});
