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
      "Organizing Rules",
      "Storage Management",
    ]);
    expect(
      destinations.filter((item) => item.availability === "migration"),
    ).toHaveLength(2);
    expect(childDestinations.map((item) => item.label)).toEqual([
      "Files",
      "Task list",
      "Edit rule object",
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
    expect(destinationForPath("/rules")?.id).toBe("rules");
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

  it("resolves rules edit routes carrying every backend-legal object ID", () => {
    // The rules edit route is bound to the backend rules identifier contract:
    // `+`, `@`, internal spaces and dots must all resolve to the same
    // destination without coercion, while other dynamic destinations keep the
    // generic URI-safe grammar.
    for (const objectId of [
      "proof+type",
      "proof@type",
      "proof type",
      "proof.type",
      "movie",
      "a".repeat(64),
    ]) {
      const encoded = encodeURIComponent(objectId);
      expect(
        destinationForPath(`/rules/edit/recognitionTypes/${encoded}`)?.id,
        objectId,
      ).toBe("rules-edit");
      expect(isDestinationPath(`/rules/edit/recognitionTypes/${encoded}`)).toBe(
        true,
      );
    }
    // Unencoded internal space still resolves: the browser decodes it before
    // the router sees it.
    expect(
      destinationForPath("/rules/edit/recognitionTypes/proof type")?.id,
    ).toBe("rules-edit");
  });

  it("keeps the rules edit route allowlist narrow", () => {
    // The navigation model carries the route shape and identity grammar; the
    // page guard (isRuleFormFamily) remains the family authority. Unsupported
    // depth and unsafe/oversized identity shapes stay outside the contract.
    expect(isDestinationPath("/rules/edit/recognitionTypes")).toBe(false);
    expect(isDestinationPath("/rules/edit/recognitionTypes/a/b")).toBe(false);
    expect(
      isDestinationPath(`/rules/edit/recognitionTypes/${"a".repeat(65)}`),
    ).toBe(false);
    expect(isDestinationPath("/rules/edit/recognitionTypes/..")).toBe(false);
    // Malformed percent-encoding fails closed.
    expect(isDestinationPath("/rules/edit/recognitionTypes/proof%2")).toBe(
      false,
    );
    // Other dynamic destinations keep rejecting the same characters.
    expect(isDestinationPath("/operations/tasks/proof+type")).toBe(false);
    expect(isDestinationPath("/operations/tasks/proof type")).toBe(false);
    expect(isDestinationPath("/operations/tasks/proof@type")).toBe(false);
    // Ordinary task IDs keep working.
    expect(isDestinationPath("/operations/tasks/task-1")).toBe(true);
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

    it("keeps only the allowlisted Rules family section", () => {
      expect(
        allowlistedDestinationSearch(
          "/rules",
          "section=recognitionTypes&token=secret&revision=sha256:abc",
        ),
      ).toBe("section=recognitionTypes");
      // An unknown, credential-like or path-like section never survives a
      // reconnect; the workspace then falls back to its read-only Overview.
      for (const search of [
        "section=not-a-family",
        "section=../../storage",
        "section=Bearer%20abc",
        "section=sha256%3Aabcdef",
        "token=secret",
      ]) {
        expect(allowlistedDestinationSearch("/rules", search)).toBeNull();
      }
    });

    it("returns null for non-library/files routes", () => {
      expect(allowlistedDestinationSearch("/dashboard", "q=test")).toBeNull();
      expect(
        allowlistedDestinationSearch("/operations", "storage=local-1"),
      ).toBeNull();
    });

    it("keeps only the submitted run-inventory filters and selection", () => {
      expect(
        allowlistedDestinationSearch(
          "/operations",
          "status=failed&q=%E7%94%B5%E5%BD%B1&run=job-001&token=secret",
        ),
      ).toBe("status=failed&q=%E7%94%B5%E5%BD%B1&run=job-001");
      // The manual scope selector keeps one closed scope kind and one bounded
      // library identity.
      expect(
        allowlistedDestinationSearch(
          "/operations",
          "scopeKind=resourceLibrary&resourceLibraryId=resources",
        ),
      ).toBe("scopeKind=resourceLibrary&resourceLibraryId=resources");
      expect(
        allowlistedDestinationSearch(
          "/operations",
          "scopeKind=storage&resourceLibraryId=../escape",
        ),
      ).toBeNull();
      expect(
        allowlistedDestinationSearch("/operations", "authorization=Bearer%20x"),
      ).toBeNull();
    });

    it("keeps the run-inventory attention facet, cursor page and direction", () => {
      // The three continuation keys survive a reconnect only with their exact
      // legal values, so refresh/401-reconnect restores filters, paging and
      // the selection together.
      expect(
        allowlistedDestinationSearch(
          "/operations",
          "status=failed&run=job-001&attention=true&cursor=abc123-DEF_0&dir=backward",
        ),
      ).toBe(
        "status=failed&run=job-001&attention=true&cursor=abc123-DEF_0&dir=backward",
      );
      expect(
        allowlistedDestinationSearch(
          "/operations",
          "dir=forward&attention=true",
        ),
      ).toBe("attention=true&dir=forward");
      // Only the literal submitted facet value is kept: another spelling is a
      // filter the backend would reject, so it never replays on reconnect.
      for (const search of [
        "attention=false",
        "attention=yes",
        "attention=1",
        "attention=true%20",
      ]) {
        expect(allowlistedDestinationSearch("/operations", search)).toBeNull();
      }
      // Paging state must match the closed cursor/direction grammar.
      for (const search of [
        "cursor=../../etc/passwd",
        `cursor=${"a".repeat(513)}`,
        "cursor=has%20space",
        "cursor=",
        "dir=sideways",
        "dir=",
      ]) {
        expect(allowlistedDestinationSearch("/operations", search)).toBeNull();
      }
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
