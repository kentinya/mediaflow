import { describe, expect, it } from "vitest";
import {
  normalizeManualPreview,
  normalizeManualPreviewItem,
  normalizeManualPreviewListPage,
} from "./preview";

const NOW = "2026-08-22T12:00:00+00:00";
const LATER = "2026-08-22T12:06:00+00:00";

function previewPayload(overrides: Record<string, unknown> = {}) {
  return {
    previewId: "preview-1",
    intentId: null,
    actor: "operator",
    intentVersion: null,
    status: "completed",
    current: true,
    createdAt: NOW,
    updatedAt: LATER,
    nextAction: null,
    error: null,
    sideEffects: "no Storage mutation",
    zeroMutation: true,
    executionState: null,
    truncated: false,
    scope: { scopeKind: "file", scopeId: "file-1" },
    scopeKind: "file",
    scopeId: "file-1",
    selection: null,
    configurationSnapshotId: "snap-1",
    items: [
      {
        itemId: "item-1",
        sourceStorageId: "local",
        sourcePath: "movie.mkv",
        recognitionType: "A",
        title: "Movie",
        provider: "tmdb",
        providerId: "123",
        targetPath: "Movies/Movie/Movie.mkv",
        organizePolicy: "move",
        status: "success",
        failure: null,
      },
    ],
    ...overrides,
  };
}

describe("normalizeManualPreview", () => {
  it("accepts a modelled preview document", () => {
    const model = normalizeManualPreview(previewPayload());
    expect(model.previewId).toBe("preview-1");
    expect(model.status).toBe("completed");
    expect(model.zeroMutation).toBe(true);
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.title).toBe("Movie");
  });

  it("rejects an unknown status instead of casting it", () => {
    expect(() =>
      normalizeManualPreview(previewPayload({ status: "broken" })),
    ).toThrow();
  });

  it("rejects coerced booleans", () => {
    expect(() =>
      normalizeManualPreview(previewPayload({ zeroMutation: "yes" })),
    ).toThrow();
    expect(() =>
      normalizeManualPreview(previewPayload({ current: 1 })),
    ).toThrow();
  });

  it("rejects non-array items", () => {
    expect(() =>
      normalizeManualPreview(previewPayload({ items: "not-array" })),
    ).toThrow();
  });

  it("rejects a scope object that is not a record", () => {
    expect(() =>
      normalizeManualPreview(previewPayload({ scope: "invalid" })),
    ).toThrow();
  });

  it("normalizes preview item failure", () => {
    const model = normalizeManualPreview(
      previewPayload({
        items: [
          {
            itemId: "item-1",
            sourceStorageId: "local",
            sourcePath: "movie.mkv",
            recognitionType: null,
            title: null,
            provider: null,
            providerId: null,
            targetPath: null,
            organizePolicy: null,
            status: "failed",
            failure: {
              category: "provider",
              message: "metadata lookup failed",
              nextAction: "check provider availability",
            },
          },
        ],
      }),
    );
    expect(model.items[0]?.failure?.category).toBe("provider");
    expect(model.items[0]?.failure?.nextAction).toBe(
      "check provider availability",
    );
  });

  it("never carries a hostile historical record into the model", () => {
    const model = normalizeManualPreview(
      previewPayload({
        error: "Authorization: Bearer topsecret",
        source_display: "/srv/media/private.mkv",
        source_fingerprint: "fingerprint-value",
      }),
    );
    const serialized = JSON.stringify(model);
    expect(serialized).not.toContain("topsecret");
    expect(serialized).not.toContain("/srv/media");
    expect(serialized).not.toContain("fingerprint-value");
  });
});

describe("normalizeManualPreviewItem", () => {
  it("normalizes a preview item", () => {
    const item = normalizeManualPreviewItem({
      itemId: "item-1",
      sourceStorageId: "local",
      sourcePath: "movie.mkv",
      recognitionType: "A",
      title: "Movie",
      provider: "tmdb",
      providerId: "123",
      targetPath: "Movies/Movie/Movie.mkv",
      organizePolicy: "move",
      status: "success",
      failure: null,
    });
    expect(item.itemId).toBe("item-1");
    expect(item.recognitionType).toBe("A");
    expect(item.failure).toBeNull();
  });
});

describe("normalizeManualPreviewListPage", () => {
  it("accepts a modelled list page", () => {
    const page = normalizeManualPreviewListPage({
      items: [previewPayload()],
      limit: 20,
      total: 1,
      scopeKind: "file",
      scopeId: "file-1",
    });
    expect(page.items).toHaveLength(1);
    expect(page.total).toBe(1);
    expect(page.scopeKind).toBe("file");
  });

  it("rejects non-array items", () => {
    expect(() =>
      normalizeManualPreviewListPage({
        items: "not-array",
        limit: 20,
        total: 0,
        scopeKind: "file",
        scopeId: "file-1",
      }),
    ).toThrow();
  });
});
