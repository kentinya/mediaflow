import { describe, expect, it } from "vitest";
import {
  StorageFilesNormalizationError,
  normalizeStorageFiles,
} from "./storage-files";

const storageFilesPayload = {
  configuration: {
    authority: "MANAGED",
    revisionId: "rev-1",
    version: 1,
    digest: "digest-1",
  },
  resourceLibrary: {
    id: "resources-1",
    name: "Incoming resources",
    enabled: true,
    rootPath: "incoming",
    storage: {
      id: "local-1",
      name: "Local media",
      type: "local",
      readOnly: false,
    },
  },
  path: "nested",
  breadcrumbs: [
    { name: "ResourceLibrary root", path: "", isRoot: true },
    { name: "nested", path: "nested", isRoot: false },
  ],
  entries: [
    {
      name: "show.mkv",
      path: "nested/show.mkv",
      type: "file",
      entryType: "file",
      size: 1048576,
      modifiedAt: "2026-08-22T12:00:00+00:00",
      isDirectory: false,
      isSymlink: false,
      traversable: false,
      selectable: true,
      indexMembership: {
        available: true,
        indexed: true,
        memberships: [{ fileId: "obsolete", resourceLibraryId: "resources-1" }],
        total: 1,
      },
    },
    {
      name: "sub",
      path: "nested/sub",
      type: "directory",
      entryType: "directory",
      size: 0,
      modifiedAt: "2026-08-22T12:00:00+00:00",
      isDirectory: true,
      isSymlink: false,
      traversable: true,
      selectable: false,
    },
  ],
  limit: 50,
  nextCursor: "cursor-2",
  hasNext: true,
  exhausted: false,
  sideEffects: "none",
  retrySafe: true,
};

describe("normalizeStorageFiles", () => {
  it("normalizes ResourceLibrary-scoped live Storage files", () => {
    const model = normalizeStorageFiles(storageFilesPayload);
    expect(model.resourceLibrary).toEqual({
      id: "resources-1",
      name: "Incoming resources",
      enabled: true,
      rootPath: "incoming",
      storage: {
        id: "local-1",
        name: "Local media",
        type: "local",
        readOnly: false,
      },
      fileCount: null,
      totalSize: null,
    });
    expect(model.storageId).toBe("local-1");
    expect(model.path).toBe("nested");
    expect(model.breadcrumbs[0]).toEqual({
      name: "ResourceLibrary root",
      path: "",
      isRoot: true,
    });
    expect(model.entries[0]).toMatchObject({
      name: "show.mkv",
      path: "nested/show.mkv",
      type: "file",
      selectable: true,
    });
    expect("membership" in model.entries[0]).toBe(false);
    expect(model.nextCursor).toBe("cursor-2");
    expect(model.hasNext).toBe(true);
    expect(model.exhausted).toBe(false);
    expect(model.sideEffects).toBe("none");
    expect(model.retrySafe).toBe(true);
  });

  it("normalizes optional bounded business projection without making it authority", () => {
    const model = normalizeStorageFiles({
      ...storageFilesPayload,
      resourceLibrary: {
        ...storageFilesPayload.resourceLibrary,
        fileCount: 1248,
        totalSize: 324 * 1024 * 1024 * 1024,
      },
      entries: [
        {
          ...storageFilesPayload.entries[0],
          recognitionResult: "Avatar (2009)",
          businessStatus: "pending",
          fileId: "must-not-cross-boundary",
        },
      ],
    });
    expect(model.resourceLibrary?.fileCount).toBe(1248);
    expect(model.resourceLibrary?.totalSize).toBe(324 * 1024 * 1024 * 1024);
    expect(model.entries[0]?.recognitionResult).toBe("Avatar (2009)");
    expect(model.entries[0]?.businessStatus).toBe("pending");
    expect(model.entries[0]).not.toHaveProperty("fileId");
  });

  it("accepts the compatibility storage object while still ignoring FileIndex fields", () => {
    const payload = {
      ...storageFilesPayload,
      resourceLibrary: undefined,
      storage: {
        id: "local-1",
        name: "Local media",
        type: "local",
        readOnly: true,
      },
      nextCursor: null,
      hasNext: false,
      entries: [storageFilesPayload.entries[0]],
    };
    const model = normalizeStorageFiles(payload);
    expect(model.resourceLibrary).toBeNull();
    expect(model.storageName).toBe("Local media");
    expect(model.entries[0]).not.toHaveProperty("membership");
    expect(model.hasNext).toBe(false);
  });

  it.each([
    ["non-object payload", "nope"],
    ["array payload", [storageFilesPayload]],
    [
      "missing configuration",
      { ...storageFilesPayload, configuration: undefined },
    ],
    [
      "non-managed configuration authority",
      {
        ...storageFilesPayload,
        configuration: {
          ...storageFilesPayload.configuration,
          authority: "JSON_BOOTSTRAP",
        },
      },
    ],
    [
      "missing storage authority",
      {
        ...storageFilesPayload,
        resourceLibrary: undefined,
        storage: undefined,
      },
    ],
    ["missing entries", { ...storageFilesPayload, entries: undefined }],
    ["non-array entries", { ...storageFilesPayload, entries: {} }],
    [
      "too many entries",
      { ...storageFilesPayload, entries: Array(201).fill({}) },
    ],
    [
      "non-boolean traversable",
      {
        ...storageFilesPayload,
        entries: [{ ...storageFilesPayload.entries[0], traversable: "yes" }],
      },
    ],
    ["missing breadcrumbs", { ...storageFilesPayload, breadcrumbs: undefined }],
    ["non-string sideEffects", { ...storageFilesPayload, sideEffects: 42 }],
  ])("rejects %s", (_name, payload) => {
    expect(() => normalizeStorageFiles(payload)).toThrow(
      StorageFilesNormalizationError,
    );
  });
});
