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
      "Storage Management",
    ]);
    expect(
      destinations.filter((item) => item.availability === "migration"),
    ).toHaveLength(2);
    expect(childDestinations.map((item) => item.label)).toEqual([
      "Files",
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
      "Automation",
      "Create Automation definition",
      "Automation definition",
      "Automation Draft editor",
      "Automation Preview",
      "Automation occurrences",
      "Notifications",
      "Create Webhook definition",
      "Webhook definition",
      "Webhook Draft editor",
      "Notification deliveries",
      "Notification delivery detail",
    ]);
  });

  it("resolves paths without duplicating route metadata", () => {
    expect(destinationForPath("/dashboard")?.id).toBe("overview");
    expect(destinationForPath("/medialib/files")?.id).toBe("library");
    expect(destinationForPath("/resourcelib/files")?.id).toBe("library-files");
    expect(destinationForPath("/library")).toBeUndefined();
    expect(destinationForPath("/library/files")).toBeUndefined();
    expect(destinationForPath("/library/file-index")).toBeUndefined();
    expect(destinationForPath("/unknown")).toBeUndefined();
  });

  it("rejects retired FileIndex routes while preserving dynamic detail routes", () => {
    expect(destinationForPath("/library/file-index/file-123")).toBeUndefined();
    expect(destinationForPath("/library/file-index/$fileId")).toBeUndefined();
    expect(isDestinationPath("/library/file-index/file-123")).toBe(false);
    expect(
      destinationForPath("/operations/automation/preview/def-1/preview-1")?.id,
    ).toBe("operations-automation-preview");
    expect(
      destinationForPath("/operations/automation/preview/def-1"),
    ).toBeUndefined();
  });

  it("derives a unique path allowlist from the destinations contract", () => {
    expect(destinationPaths).toEqual(destinations.map((item) => item.path));
    expect(new Set(destinationPaths).size).toBe(destinations.length);
    expect(allDestinationPaths).toContain("/resourcelib/files");
    expect(allDestinationPaths).toContain("/medialib/files");
    expect(allDestinationPaths).not.toContain("/library/file-index");
    for (const path of destinationPaths) {
      expect(isDestinationPath(path)).toBe(true);
    }
    expect(isDestinationPath("/resourcelib/files")).toBe(true);
    expect(isDestinationPath("/medialib/files")).toBe(true);
    expect(isDestinationPath("/library/files")).toBe(false);
    expect(isDestinationPath("/library")).toBe(false);
    expect(isDestinationPath("/")).toBe(false);
    expect(isDestinationPath("/dashboard/")).toBe(false);
    expect(isDestinationPath("/unknown")).toBe(false);
    expect(isDestinationPath("https://evil.example.com/dashboard")).toBe(false);
  });

  describe("allowlistedDestinationSearch", () => {
    it("returns allowed ResourceLibrary/path/cursor keys for library/files", () => {
      const search = allowlistedDestinationSearch(
        "/resourcelib/files",
        "resourceLibraryId=resources&path=movies&cursor=abc",
      );
      expect(search).toBe("resourceLibraryId=resources&path=movies&cursor=abc");
    });

    it("keeps only the media-library identity, path and cursor on medialib/files", () => {
      expect(
        allowlistedDestinationSearch(
          "/medialib/files",
          "mediaLibraryId=movies&path=Breaking+Bad&cursor=abc",
        ),
      ).toBe("mediaLibraryId=movies&path=Breaking+Bad&cursor=abc");
      // A ResourceLibrary identity never crosses the kind boundary.
      expect(
        allowlistedDestinationSearch(
          "/medialib/files",
          "resourceLibraryId=resources&mediaLibraryId=movies",
        ),
      ).toBe("mediaLibraryId=movies");
    });

    it("drops unknown and credential-like query keys", () => {
      const search = allowlistedDestinationSearch(
        "/resourcelib/files",
        "resourceLibraryId=resources&token=secret&authorization=Bearer x&unknown=x",
      );
      expect(search).toBe("resourceLibraryId=resources");
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
          "/resourcelib/files",
          "token=secret&unknown=x",
        ),
      ).toBeNull();
    });

    it("preserves safe URL encoding", () => {
      const search = allowlistedDestinationSearch(
        "/resourcelib/files",
        "resourceLibraryId=resources&path=movies%2FNew%20%26%20Old&cursor=a+b/c",
      );
      // URLSearchParams normalizes %20 to + for spaces and %2F to / for slashes
      expect(search).toBe(
        "resourceLibraryId=resources&path=movies%2FNew+%26+Old&cursor=a+b%2Fc",
      );
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
