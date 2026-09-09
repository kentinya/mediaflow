import { describe, expect, it } from "vitest";
import {
  allDestinationPaths,
  allowlistedDestinationSearch,
  childDestinations,
  destinationForPath,
  destinationPaths,
  destinations,
  isDestinationPath,
} from "./destination-model";

describe("destination model", () => {
  it("defines one operator-oriented route contract", () => {
    expect(destinations.map((item) => item.label)).toEqual([
      "Overview",
      "Library",
      "Operations",
      "Review & Recovery",
      "Configuration",
    ]);
    expect(
      destinations.filter((item) => item.availability === "migration"),
    ).toHaveLength(3);
    expect(childDestinations.map((item) => item.label)).toEqual([
      "Storage files",
    ]);
  });

  it("resolves paths without duplicating route metadata", () => {
    expect(destinationForPath("/dashboard")?.id).toBe("overview");
    expect(destinationForPath("/library")?.availability).toBe("implemented");
    expect(destinationForPath("/library/files")?.id).toBe("library-files");
    expect(destinationForPath("/unknown")).toBeUndefined();
  });

  it("derives a unique path allowlist from the destinations contract", () => {
    expect(destinationPaths).toEqual(destinations.map((item) => item.path));
    expect(new Set(destinationPaths).size).toBe(destinations.length);
    expect(allDestinationPaths).toContain("/library/files");
    for (const path of destinationPaths) {
      expect(isDestinationPath(path)).toBe(true);
    }
    expect(isDestinationPath("/library/files")).toBe(true);
    expect(isDestinationPath("/")).toBe(false);
    expect(isDestinationPath("/dashboard/")).toBe(false);
    expect(isDestinationPath("/unknown")).toBe(false);
    expect(isDestinationPath("https://evil.example.com/dashboard")).toBe(false);
  });

  describe("allowlistedDestinationSearch", () => {
    it("returns allowed storage/path/cursor keys for library/files", () => {
      const search = allowlistedDestinationSearch(
        "/library/files",
        "storage=local-1&path=movies&cursor=abc",
      );
      expect(search).toBe("storage=local-1&path=movies&cursor=abc");
    });

    it("drops unknown and credential-like query keys", () => {
      const search = allowlistedDestinationSearch(
        "/library/files",
        "storage=local-1&token=secret&authorization=Bearer x&unknown=x",
      );
      expect(search).toBe("storage=local-1");
    });

    it("returns null for non-library/files routes", () => {
      expect(allowlistedDestinationSearch("/dashboard", "q=test")).toBeNull();
      expect(
        allowlistedDestinationSearch("/operations", "storage=local-1"),
      ).toBeNull();
    });

    it("returns null when no allowed keys are present", () => {
      expect(
        allowlistedDestinationSearch(
          "/library/files",
          "token=secret&unknown=x",
        ),
      ).toBeNull();
    });

    it("preserves safe URL encoding", () => {
      const search = allowlistedDestinationSearch(
        "/library/files",
        "storage=local-1&path=movies%2FNew%20%26%20Old&cursor=a+b/c",
      );
      // URLSearchParams normalizes %20 to + for spaces and %2F to / for slashes
      expect(search).toBe(
        "storage=local-1&path=movies%2FNew+%26+Old&cursor=a+b%2Fc",
      );
    });
  });
});
