import { describe, expect, it } from "vitest";
import {
  StorageFilesNormalizationError,
  normalizeStorageFiles,
} from "./storage-files";

/** Wire shape matching the existing Python runtime Files document. */
const storageFilesPayload = {
  revisionId: "rev-1",
  revision: { authority: "MANAGED", revisionId: "rev-1" },
  configuration: {
    authority: "MANAGED",
    revisionId: "rev-1",
    version: 1,
    digest: "digest-1",
  },
  storage: { id: "local-1", name: "Local media", type: "local" },
  storageId: "local-1",
  storageName: "Local media",
  storageType: "local",
  path: "nested",
  breadcrumbs: [
    { name: "Storage root", path: "", isRoot: true },
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
      selectable: false,
      indexMembership: {
        available: true,
        indexed: true,
        memberships: [{ fileId: "file-1", resourceLibraryId: "resources-1" }],
        total: 1,
        truncated: false,
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
      selectable: true,
      indexMembership: {
        available: true,
        indexed: false,
        memberships: [],
        total: 0,
        truncated: false,
      },
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
  it("normalizes the bounded runtime Files document into the frontend model", () => {
    const model = normalizeStorageFiles(storageFilesPayload);
    expect(model.storageId).toBe("local-1");
    expect(model.storageName).toBe("Local media");
    expect(model.path).toBe("nested");
    expect(model.breadcrumbs).toHaveLength(2);
    expect(model.entries[0].membership).toEqual({
      kind: "indexed",
      libraryName: null,
      total: 1,
      memberships: [{ fileId: "file-1", resourceLibraryId: "resources-1" }],
    });
    expect(model.entries[1].membership.kind).toBe("not-indexed");
    expect(model.authority).toBe("MANAGED");
    expect(model.nextCursor).toBe("cursor-2");
    expect(model.hasNext).toBe(true);
    expect(model.exhausted).toBe(false);
    expect(model.sideEffects).toBe("none");
    expect(model.retrySafe).toBe(true);
  });

  it("distinguishes an ambiguous non-truncated multi-match membership", () => {
    const payload = {
      ...storageFilesPayload,
      entries: [
        {
          ...storageFilesPayload.entries[0],
          indexMembership: {
            available: true,
            indexed: true,
            memberships: [
              { fileId: "file-1", resourceLibraryId: "resources-1" },
              { fileId: "file-2", resourceLibraryId: "resources-2" },
            ],
            total: 2,
            truncated: false,
          },
        },
      ],
    };
    const model = normalizeStorageFiles(payload);
    expect(model.entries[0].membership).toEqual({
      kind: "ambiguous",
      libraryName: null,
      total: 2,
      memberships: [],
    });
  });

  it("ignores unknown fields and supports truncated/unavailable membership", () => {
    const payload = {
      ...storageFilesPayload,
      future: { hidden: true },
      nextCursor: null,
      hasNext: false,
      entries: [
        {
          ...storageFilesPayload.entries[0],
          indexMembership: {
            available: true,
            indexed: true,
            total: 9,
            truncated: true,
          },
        },
        {
          ...storageFilesPayload.entries[1],
          indexMembership: {
            available: false,
            indexed: false,
            total: 0,
            truncated: false,
          },
        },
      ],
    };
    const model = normalizeStorageFiles(payload);
    expect(model.entries[0].membership).toEqual({
      kind: "truncated",
      libraryName: null,
      total: 9,
      memberships: [],
    });
    expect(model.entries[1].membership).toEqual({
      kind: "unavailable",
      libraryName: null,
      total: 0,
      memberships: [],
    });
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
      "missing configuration authority",
      {
        ...storageFilesPayload,
        configuration: {
          ...storageFilesPayload.configuration,
          authority: undefined,
        },
      },
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
    ["missing storage", { ...storageFilesPayload, storage: undefined }],
    ["missing entries", { ...storageFilesPayload, entries: undefined }],
    ["non-array entries", { ...storageFilesPayload, entries: {} }],
    [
      "too many entries",
      { ...storageFilesPayload, entries: Array(201).fill({}) },
    ],
    [
      "missing membership available",
      {
        ...storageFilesPayload,
        entries: [
          {
            ...storageFilesPayload.entries[0],
            indexMembership: { indexed: true, total: 1 },
          },
        ],
      },
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
