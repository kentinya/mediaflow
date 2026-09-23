import { describe, expect, it } from "vitest";
import {
  MediaLibraryConfigNormalizationError,
  MEDIA_LIBRARY_ID,
  normalizeMediaLibraryRemoval,
  normalizeMediaLibraryRemovalPreview,
  normalizeMediaLibrarySave,
} from "./media-library";

/**
 * Frontend-owned MediaLibrary configuration models.  The successful documents
 * below mirror the real Python API responses (`tests/test_media_library_activation.py`);
 * no production service or credential is involved.
 */

const saveResponse = {
  mediaLibrary: {
    id: "movies",
    name: "电影库",
    storageId: "cloud-1",
    rootPath: "Media/Movies",
    enabled: true,
  },
  active: {
    revisionId: "rev-2",
    status: "active",
    version: 2,
    digest: "digest-2",
  },
  configuration: {
    authority: "MANAGED",
    revisionId: "rev-2",
    version: 2,
    digest: "digest-2",
  },
  sideEffects: "configuration_only",
};

const previewResponse = {
  mediaLibrary: {
    id: "movies",
    name: "电影库",
    storageId: "cloud-1",
    rootPath: "Media/Movies",
    enabled: true,
  },
  storage: {
    id: "cloud-1",
    name: "115 Storage",
    type: "openlist",
    enabled: true,
  },
  references: { total: 0, items: [], truncated: false },
  active: { revisionId: "rev-2", version: 2, digest: "digest-2" },
};

const removalResponse = {
  removed: { id: "movies" },
  active: {
    revisionId: "rev-3",
    status: "active",
    version: 3,
    digest: "digest-3",
  },
  configuration: {
    authority: "MANAGED",
    revisionId: "rev-3",
    version: 3,
    digest: "digest-3",
  },
  sideEffects: "configuration_only",
};

describe("MEDIA_LIBRARY_ID", () => {
  it("enforces the image's lowercase-letter/digit/hyphen creation rule", () => {
    expect(MEDIA_LIBRARY_ID.test("movies")).toBe(true);
    expect(MEDIA_LIBRARY_ID.test("movies-2024")).toBe(true);
    expect(MEDIA_LIBRARY_ID.test("a1")).toBe(true);
    expect(MEDIA_LIBRARY_ID.test("Movies")).toBe(false);
    expect(MEDIA_LIBRARY_ID.test("-movies")).toBe(false);
    expect(MEDIA_LIBRARY_ID.test("movies_lib")).toBe(false);
    expect(MEDIA_LIBRARY_ID.test("movies lib")).toBe(false);
    expect(MEDIA_LIBRARY_ID.test("")).toBe(false);
    expect(MEDIA_LIBRARY_ID.test("a".repeat(65))).toBe(false);
  });
});

describe("normalizeMediaLibrarySave", () => {
  it("keeps the exact candidate and the immutable published Active identity", () => {
    expect(normalizeMediaLibrarySave(saveResponse)).toEqual({
      id: "movies",
      name: "电影库",
      storageId: "cloud-1",
      rootPath: "Media/Movies",
      enabled: true,
      activeRevisionId: "rev-2",
      activeVersion: 2,
      activeDigest: "digest-2",
    });
  });

  it("represents a disabled saved library truthfully and accepts the Storage root", () => {
    const model = normalizeMediaLibrarySave({
      ...saveResponse,
      mediaLibrary: {
        ...saveResponse.mediaLibrary,
        enabled: false,
        rootPath: "",
      },
    });
    expect(model.enabled).toBe(false);
    expect(model.rootPath).toBe("");
  });

  it("rejects a split-identity document whose durable block disagrees with Active", () => {
    // The response claims Active rev-3 while the durable configuration block
    // still names rev-2: publishing that as success would misreport authority.
    expect(() =>
      normalizeMediaLibrarySave({
        ...saveResponse,
        configuration: {
          authority: "MANAGED",
          revisionId: "rev-3",
          version: 2,
          digest: "digest-2",
        },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
    expect(() =>
      normalizeMediaLibrarySave({
        ...saveResponse,
        configuration: {
          authority: "MANAGED",
          revisionId: "rev-2",
          version: 3,
          digest: "digest-2",
        },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
    expect(() =>
      normalizeMediaLibrarySave({
        ...saveResponse,
        configuration: {
          authority: "MANAGED",
          revisionId: "rev-2",
          version: 2,
          digest: "digest-3",
        },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
  });

  it("rejects a document that is not a published Active configuration", () => {
    expect(() =>
      normalizeMediaLibrarySave({
        ...saveResponse,
        active: { ...saveResponse.active, status: "draft" },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
    expect(() =>
      normalizeMediaLibrarySave({
        ...saveResponse,
        configuration: { ...saveResponse.configuration, authority: "DRAFT" },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
  });

  it("rejects malformed, unsafe or missing identities instead of rendering success", () => {
    const bad = [
      {
        ...saveResponse,
        mediaLibrary: { ...saveResponse.mediaLibrary, id: "Movies" },
      },
      {
        ...saveResponse,
        mediaLibrary: { ...saveResponse.mediaLibrary, name: "" },
      },
      {
        ...saveResponse,
        mediaLibrary: { ...saveResponse.mediaLibrary, enabled: "yes" },
      },
      {
        ...saveResponse,
        mediaLibrary: { ...saveResponse.mediaLibrary, storageId: "" },
      },
      { ...saveResponse, active: { ...saveResponse.active, digest: "" } },
    ];
    for (const payload of bad) {
      expect(() => normalizeMediaLibrarySave(payload)).toThrow(
        MediaLibraryConfigNormalizationError,
      );
    }
    expect(() => normalizeMediaLibrarySave(null)).toThrow(
      MediaLibraryConfigNormalizationError,
    );
    expect(() => normalizeMediaLibrarySave("ok")).toThrow(
      MediaLibraryConfigNormalizationError,
    );
  });
});

describe("normalizeMediaLibraryRemovalPreview", () => {
  it("keeps the selected library and the exact previewed Active revision", () => {
    expect(normalizeMediaLibraryRemovalPreview(previewResponse)).toEqual({
      mediaLibrary: {
        id: "movies",
        name: "电影库",
        storageId: "cloud-1",
        rootPath: "Media/Movies",
        enabled: true,
      },
      storage: {
        id: "cloud-1",
        name: "115 Storage",
        type: "openlist",
        enabled: true,
      },
      references: { total: 0, items: [], truncated: false },
      active: { revisionId: "rev-2", version: 2, digest: "digest-2" },
    });
  });

  it("reports blocking ClassificationPolicy references as bounded evidence", () => {
    const model = normalizeMediaLibraryRemovalPreview({
      ...previewResponse,
      references: {
        total: 2,
        items: [
          {
            section: "classificationPolicies",
            id: "policy-a",
            field: "mediaLibraryId",
          },
          {
            section: "classificationPolicies",
            id: "policy-b",
            field: "mediaLibraryId",
          },
        ],
        truncated: true,
      },
    });
    expect(model.references.total).toBe(2);
    expect(model.references.items).toHaveLength(2);
    expect(model.references.items[0]).toEqual({
      section: "classificationPolicies",
      id: "policy-a",
      field: "mediaLibraryId",
    });
    expect(model.references.truncated).toBe(true);
  });

  it("keeps a missing Storage truthful instead of inventing one", () => {
    const model = normalizeMediaLibraryRemovalPreview({
      ...previewResponse,
      storage: null,
    });
    expect(model.storage).toBeNull();
  });

  it("requires the bindable Active revision evidence for a confirmation", () => {
    expect(() =>
      normalizeMediaLibraryRemovalPreview({
        ...previewResponse,
        active: { version: 2 },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
    expect(() =>
      normalizeMediaLibraryRemovalPreview({
        ...previewResponse,
        references: { total: 0, items: "none", truncated: false },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
  });
});

describe("normalizeMediaLibraryRemoval", () => {
  it("keeps the removed identity and the newly published Active revision", () => {
    expect(normalizeMediaLibraryRemoval(removalResponse)).toEqual({
      removedId: "movies",
      activeRevisionId: "rev-3",
      activeVersion: 3,
      activeDigest: "digest-3",
    });
  });

  it("rejects a split-identity removal document", () => {
    expect(() =>
      normalizeMediaLibraryRemoval({
        ...removalResponse,
        configuration: {
          authority: "MANAGED",
          revisionId: "rev-2",
          version: 3,
          digest: "digest-3",
        },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
  });

  it("rejects an unsafe removed identity or a non-Active result", () => {
    expect(() =>
      normalizeMediaLibraryRemoval({
        ...removalResponse,
        removed: { id: "../escape" },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
    expect(() =>
      normalizeMediaLibraryRemoval({
        ...removalResponse,
        active: { ...removalResponse.active, status: "draft" },
      }),
    ).toThrow(MediaLibraryConfigNormalizationError);
  });
});
