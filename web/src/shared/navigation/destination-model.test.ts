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
    ).toHaveLength(2);
    expect(childDestinations.map((item) => item.label)).toEqual([
      "Storage files",
      "FileIndex",
      "FileIndex detail",
      "Task list",
      "Task detail",
      "Job list",
      "Job detail",
      "Start Scan",
      "Scan detail",
      "Start Preview",
      "Preview detail",
      "Manual organize",
      "Manual intent",
      "Exact organize Preview",
      "Organize execution",
    ]);
  });

  it("resolves paths without duplicating route metadata", () => {
    expect(destinationForPath("/dashboard")?.id).toBe("overview");
    expect(destinationForPath("/library")?.availability).toBe("implemented");
    expect(destinationForPath("/library/files")?.id).toBe("library-files");
    expect(destinationForPath("/library/file-index")?.id).toBe(
      "library-file-index",
    );
    expect(destinationForPath("/unknown")).toBeUndefined();
  });

  it("resolves one-segment concrete instances of the detail route", () => {
    expect(destinationForPath("/library/file-index/file-123")?.id).toBe(
      "library-file-index-detail",
    );
    expect(destinationForPath("/library/file-index/file-123")?.title).toBe(
      "FileIndex detail | MediaFlow",
    );
    // The catalog route keeps its own identity; only one extra segment is a
    // detail instance. Deeper or empty paths never resolve.
    expect(destinationForPath("/library/file-index")?.id).toBe(
      "library-file-index",
    );
    expect(destinationForPath("/library/file-index/a/b")).toBeUndefined();
    expect(destinationForPath("/library/file-index/")?.id).toBe(
      "library-file-index",
    );
    // The declared template path resolves to the same destination contract;
    // it is never a navigable route (the router only registers the
    // parameterized path), but it must not invent a second identity.
    expect(destinationForPath("/library/file-index/$fileId")?.id).toBe(
      "library-file-index-detail",
    );
    expect(isDestinationPath("/library/file-index/file-123")).toBe(true);
    expect(isDestinationPath("/library/file-index/abc")).toBe(true);
  });

  it("derives a unique path allowlist from the destinations contract", () => {
    expect(destinationPaths).toEqual(destinations.map((item) => item.path));
    expect(new Set(destinationPaths).size).toBe(destinations.length);
    expect(allDestinationPaths).toContain("/library/files");
    expect(allDestinationPaths).toContain("/library/file-index");
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

    it("preserves only catalog view state for FileIndex continuation", () => {
      const search = allowlistedDestinationSearch(
        "/library/file-index",
        "query=movie&processingDisposition=organized&token=secret&limit=50",
      );
      expect(search).toBe("query=movie&processingDisposition=organized");
    });

    it("preserves q_ keys and drops others for the detail route", () => {
      const search = allowlistedDestinationSearch(
        "/library/file-index/$fileId",
        "q_query=movie&q_resourceLibrary=tv&token=secret&limit=50",
      );
      expect(search).toBe("q_query=movie&q_resourceLibrary=tv");
    });

    it("returns null when no q_ keys are present on the detail route", () => {
      expect(
        allowlistedDestinationSearch(
          "/library/file-index/$fileId",
          "token=secret&limit=50",
        ),
      ).toBeNull();
    });

    it("keeps only the submitted Operations collection filters", () => {
      expect(
        allowlistedDestinationSearch(
          "/operations/tasks",
          "status=failed&command=preview&token=secret&cursor=abc",
        ),
      ).toBe("status=failed&command=preview");
      expect(
        allowlistedDestinationSearch(
          "/operations/jobs",
          "authorization=Bearer%20x&status=pending",
        ),
      ).toBe("status=pending");
      expect(
        allowlistedDestinationSearch(
          "/operations/tasks",
          "token=secret&unknown=x",
        ),
      ).toBeNull();
    });

    it("keeps only the bounded parent-list context on an Operations detail route", () => {
      expect(
        allowlistedDestinationSearch(
          "/operations/tasks/$taskId",
          "q_status=failed&q_command=preview&status=failed&token=secret",
        ),
      ).toBe("q_status=failed&q_command=preview");
      expect(
        allowlistedDestinationSearch(
          "/operations/jobs/$jobId",
          "q_status=pending&token=secret",
        ),
      ).toBe("q_status=pending");
      expect(
        allowlistedDestinationSearch(
          "/operations/jobs/$jobId",
          "token=secret&status=pending",
        ),
      ).toBeNull();
    });

    it("drops credential-like values from an Operations collection link", () => {
      expect(
        allowlistedDestinationSearch(
          "/operations/tasks",
          "status=Bearer%20abc&command=preview",
        ),
      ).toBe("command=preview");
    });
  });
});
