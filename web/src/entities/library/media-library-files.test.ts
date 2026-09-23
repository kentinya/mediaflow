import { describe, expect, it } from "vitest";
import {
  MediaLibraryFilesNormalizationError,
  MediaLibraryListNormalizationError,
  normalizeMediaLibraryFiles,
  normalizeMediaLibraryList,
} from "./media-library-files";

function document(overrides: Record<string, unknown> = {}): unknown {
  return {
    revisionId: "rev-1",
    configuration: {
      authority: "MANAGED",
      revisionId: "rev-1",
      version: 1,
      digest: "digest-1",
    },
    mediaLibrary: {
      id: "movies",
      name: "Movies",
      enabled: true,
      rootPath: "Movies",
      storage: {
        id: "storage",
        name: "Storage",
        type: "local",
        readOnly: false,
      },
    },
    storageId: "storage",
    storageName: "Storage",
    storageType: "local",
    path: "",
    breadcrumbs: [{ name: "MediaLibrary root", path: "", isRoot: true }],
    entries: [
      {
        name: "Breaking Bad",
        path: "Breaking Bad",
        type: "directory",
        entryType: "directory",
        size: 0,
        modifiedAt: "2024-01-15T10:30:00+00:00",
        isDirectory: true,
        isSymlink: false,
        traversable: true,
        selectable: true,
      },
    ],
    limit: 50,
    nextCursor: null,
    hasNext: false,
    exhausted: true,
    sideEffects: "none",
    retrySafe: true,
    ...overrides,
  };
}

describe("media library files entity", () => {
  it("normalizes the bounded read-only MediaLibrary browse projection", () => {
    const model = normalizeMediaLibraryFiles(document());
    expect(model.authority).toBe("MANAGED");
    expect(model.revisionId).toBe("rev-1");
    expect(model.mediaLibrary?.id).toBe("movies");
    expect(model.mediaLibrary?.rootPath).toBe("Movies");
    expect(model.storageId).toBe("storage");
    expect(model.path).toBe("");
    expect(model.entries).toHaveLength(1);
    expect(model.entries[0]?.isDirectory).toBe(true);
    expect(model.sideEffects).toBe("none");
  });

  it("preserves exact identity including boundary whitespace", () => {
    const model = normalizeMediaLibraryFiles(
      document({
        entries: [
          {
            name: "SSH ",
            path: "电影/SSH ",
            type: "directory",
            entryType: "directory",
            size: 0,
            modifiedAt: "2024-01-15T10:30:00+00:00",
            isDirectory: true,
            isSymlink: false,
            traversable: true,
            selectable: true,
          },
        ],
      }),
    );
    expect(model.entries[0]?.name).toBe("SSH ");
    expect(model.entries[0]?.path).toBe("电影/SSH ");
  });

  it("carries no thumbnail, statistics, recognition or file-index facts", () => {
    const model = normalizeMediaLibraryFiles(document());
    const serialized = JSON.stringify(model);
    expect(serialized).not.toContain("thumbnail");
    expect(serialized).not.toContain("poster");
    expect(serialized).not.toContain("fileId");
    expect(serialized).not.toContain("organizeEligible");
    expect(serialized).not.toContain("recognitionResult");
    expect(serialized).not.toContain("fileCount");
    expect(serialized).not.toContain("totalSize");
  });

  it("fails closed on a non-managed authority or a malformed entry", () => {
    expect(() =>
      normalizeMediaLibraryFiles(
        document({
          configuration: { authority: "DRAFT", revisionId: "rev-1" },
        }),
      ),
    ).toThrow(MediaLibraryFilesNormalizationError);
    expect(() =>
      normalizeMediaLibraryFiles(
        document({
          entries: [{ name: "x", path: "x" }],
        }),
      ),
    ).toThrow(MediaLibraryFilesNormalizationError);
    expect(() =>
      normalizeMediaLibraryFiles(document({ entries: "not-an-array" })),
    ).toThrow(MediaLibraryFilesNormalizationError);
  });

  it("normalizes the enabled MediaLibrary card list without statistics", () => {
    const model = normalizeMediaLibraryList({
      surface: "media_libraries",
      items: [
        {
          id: "movies",
          name: "Movies",
          enabled: true,
          rootPath: "Movies",
          storage: {
            id: "storage",
            name: "Storage",
            type: "local",
            readOnly: false,
          },
        },
      ],
      total: 1,
      sideEffects: "none",
    });
    expect(model.total).toBe(1);
    expect(model.items[0]?.id).toBe("movies");
    expect(model.items[0]?.storage.name).toBe("Storage");
    expect(JSON.stringify(model)).not.toContain("fileCount");
    expect(JSON.stringify(model)).not.toContain("totalSize");
  });

  it("rejects a malformed card list", () => {
    expect(() => normalizeMediaLibraryList({ items: "nope" })).toThrow(
      MediaLibraryListNormalizationError,
    );
    expect(() =>
      normalizeMediaLibraryList({
        items: [{ id: "a", name: "A", rootPath: "", storage: {} }],
        total: 1,
      }),
    ).toThrow(MediaLibraryListNormalizationError);
  });
});
