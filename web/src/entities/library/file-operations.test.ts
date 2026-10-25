import { describe, expect, it } from "vitest";
import {
  LibraryFileOperationNormalizationError,
  libraryOperationHasProgress,
  libraryOperationStateLabel,
  normalizeLibraryFileOperationDetail,
  normalizeLibraryFileOperationOrigin,
  normalizeLibraryFileOperationPage,
  type LibraryFileOperationEntry,
} from "./file-operations";

/** One backend-shaped entry document for a ResourceLibrary operation. */
function entryDocument(overrides: Record<string, unknown> = {}) {
  return {
    taskId: "task-1",
    operation: "create_directory",
    operationLabel: "新建文件夹",
    command: "files_direct_command",
    commandLabel: "文件维护",
    status: "completed",
    terminal: true,
    pauseRequested: false,
    createdAt: "2024-01-15T10:30:00+00:00",
    updatedAt: "2024-01-15T10:30:01+00:00",
    version: "2024-01-15T10:30:01+00:00",
    totalItems: 1,
    settledItems: 1,
    succeededItems: 1,
    failedItems: 0,
    pendingItems: 0,
    allSucceeded: true,
    settled: true,
    sourceScope: "Resources/",
    targetScope: "Resources/shows",
    configurationSnapshotId: "rev-1",
    resourceLibraryId: "source",
    ...overrides,
  };
}

function pageDocument(overrides: Record<string, unknown> = {}) {
  return {
    items: [entryDocument()],
    libraryKind: "resource",
    libraryIdField: "resourceLibraryId",
    libraryId: "source",
    resourceLibraryId: "source",
    limit: 20,
    total: 1,
    hasNext: false,
    hasPrevious: false,
    previousCursor: null,
    nextCursor: null,
    truncated: false,
    sideEffects: "none",
    retrySafe: true,
    ...overrides,
  };
}

describe("library file-operation normalization", () => {
  it("reads one page of this library's ordinary work", () => {
    const model = normalizeLibraryFileOperationPage(
      pageDocument(),
      "resource",
      "source",
    );
    expect(model.total).toBe(1);
    expect(model.items[0]).toMatchObject({
      taskId: "task-1",
      operation: "create_directory",
      operationLabel: "新建文件夹",
      allSucceeded: true,
    });
  });

  it("accepts the media kind only through its own identity field", () => {
    const media = pageDocument({
      libraryKind: "media",
      libraryIdField: "mediaLibraryId",
      libraryId: "movies",
      mediaLibraryId: "movies",
      resourceLibraryId: undefined,
      items: [
        entryDocument({
          resourceLibraryId: undefined,
          mediaLibraryId: "movies",
          operation: "delete",
          operationLabel: "删除",
          targetScope: null,
        }),
      ],
    });
    delete (media as Record<string, unknown>).resourceLibraryId;
    const model = normalizeLibraryFileOperationPage(media, "media", "movies");
    expect(model.items[0].targetScope).toBeNull();
  });

  it("rejects a foreign kind, foreign library and split identity", () => {
    expect(() =>
      normalizeLibraryFileOperationPage(pageDocument(), "media", "source"),
    ).toThrow(LibraryFileOperationNormalizationError);
    expect(() =>
      normalizeLibraryFileOperationPage(pageDocument(), "resource", "other"),
    ).toThrow(LibraryFileOperationNormalizationError);
    const split = pageDocument({
      items: [entryDocument({ mediaLibraryId: "movies" })],
    });
    expect(() =>
      normalizeLibraryFileOperationPage(split, "resource", "source"),
    ).toThrow(LibraryFileOperationNormalizationError);
  });

  it("rejects an unknown operation, an unknown status shape and a mutation claim", () => {
    for (const overrides of [
      { items: [entryDocument({ operation: "organize" })] },
      { items: [entryDocument({ status: undefined })] },
      { items: [entryDocument({ totalItems: -1 })] },
      { sideEffects: "storage_mutations" },
      { items: "not-an-array" },
    ]) {
      expect(() =>
        normalizeLibraryFileOperationPage(
          pageDocument(overrides),
          "resource",
          "source",
        ),
      ).toThrow(LibraryFileOperationNormalizationError);
    }
  });

  it("allows an unavailable operation/scope to stay explicitly unknown", () => {
    const model = normalizeLibraryFileOperationPage(
      pageDocument({
        items: [
          entryDocument({
            operation: null,
            operationLabel: "文件维护",
            sourceScope: null,
            targetScope: null,
          }),
        ],
      }),
      "resource",
      "source",
    );
    expect(model.items[0].operation).toBeNull();
    expect(model.items[0].sourceScope).toBeNull();
  });

  it("normalizes one exact detail and refuses a mismatched Task", () => {
    const detail = normalizeLibraryFileOperationDetail(
      entryDocument({ nextAction: "刷新目录", durableState: null }),
      "resource",
      "source",
      "task-1",
    );
    expect(detail.nextAction).toBe("刷新目录");
    expect(detail.lifecycle).toBeNull();
    expect(() =>
      normalizeLibraryFileOperationDetail(
        entryDocument(),
        "resource",
        "source",
        "task-2",
      ),
    ).toThrow(LibraryFileOperationNormalizationError);
  });

  it("normalizes a proven origin and a bounded non-match", () => {
    const matched = normalizeLibraryFileOperationOrigin(
      {
        matched: true,
        taskId: "task-1",
        libraryKind: "resource",
        libraryIdField: "resourceLibraryId",
        libraryId: "source",
        resourceLibraryId: "source",
        path: "shows",
        sideEffects: "none",
        retrySafe: true,
      },
      "resource",
    );
    expect(matched).toMatchObject({ matched: true, libraryId: "source" });
    const unmatched = normalizeLibraryFileOperationOrigin(
      {
        matched: false,
        taskId: "task-9",
        reason: "origin_unavailable",
        nextAction: "open the exact Task detail in Operations",
        sideEffects: "none",
      },
      "resource",
    );
    expect(unmatched).toMatchObject({
      matched: false,
      reason: "origin_unavailable",
    });
    expect(() =>
      normalizeLibraryFileOperationOrigin(
        { matched: true, taskId: "task-1", libraryKind: "media" },
        "resource",
      ),
    ).toThrow(LibraryFileOperationNormalizationError);
  });
});

describe("library operation state copy", () => {
  const base: LibraryFileOperationEntry = {
    taskId: "task-1",
    operation: "delete",
    operationLabel: "删除",
    command: "files_delete",
    commandLabel: "删除",
    status: "running",
    terminal: false,
    pauseRequested: false,
    createdAt: "2024-01-15T10:30:00+00:00",
    updatedAt: "2024-01-15T10:30:01+00:00",
    version: "2024-01-15T10:30:01+00:00",
    totalItems: 4,
    settledItems: 2,
    succeededItems: 2,
    failedItems: 0,
    pendingItems: 2,
    allSucceeded: false,
    settled: false,
    sourceScope: null,
    targetScope: null,
    configurationSnapshotId: null,
  };

  it("only claims completion for a settled all-success operation", () => {
    expect(
      libraryOperationStateLabel({
        ...base,
        status: "completed",
        terminal: true,
        settled: true,
        allSucceeded: true,
        settledItems: 4,
        succeededItems: 4,
        pendingItems: 0,
      }),
    ).toBe("已完成");
    // A terminal Task with a non-successful item is not completion.
    expect(
      libraryOperationStateLabel({
        ...base,
        status: "completed",
        terminal: true,
        settled: true,
        allSucceeded: false,
        settledItems: 4,
        succeededItems: 3,
        failedItems: 1,
        pendingItems: 0,
      }),
    ).toContain("未成功");
    expect(
      libraryOperationStateLabel({
        ...base,
        status: "partial_success",
        terminal: true,
      }),
    ).toContain("部分成功");
  });

  it("names real progress, pause and unknown sibling outcomes", () => {
    expect(libraryOperationStateLabel(base)).toContain("执行中");
    expect(
      libraryOperationStateLabel({ ...base, pauseRequested: true }),
    ).toContain("暂停请求已记录");
    expect(
      libraryOperationStateLabel({ ...base, status: "pending" }),
    ).toContain("排队等待 Worker");
    expect(libraryOperationHasProgress(base)).toBe(true);
    expect(
      libraryOperationHasProgress({
        ...base,
        terminal: true,
        settled: true,
        status: "completed",
        settledItems: 4,
        succeededItems: 4,
        pendingItems: 0,
      }),
    ).toBe(false);
  });
});
