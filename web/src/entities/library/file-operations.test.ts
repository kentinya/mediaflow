import { describe, expect, it } from "vitest";
import {
  LibraryFileOperationNormalizationError,
  libraryOperationHasProgress,
  libraryOperationStateLabel,
  normalizeLibraryFileOperationDetail,
  normalizeLibraryFileOperationOrigin,
  normalizeLibraryFileOperationOrigins,
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
    skippedItems: 0,
    cancelledItems: 0,
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

  it("normalizes one exact detail, its per-item evidence and a mismatched Task", () => {
    const detail = normalizeLibraryFileOperationDetail(
      entryDocument({
        nextAction: "刷新目录",
        durableState: "task_partial_success",
        effectCertainty: "uncertain",
        itemsTruncated: false,
        items: [
          {
            itemId: "item-1",
            path: "a.mkv",
            destination: "a.mkv",
            status: "UNCERTAIN",
            stage: "failed",
            attempts: 1,
            effect: "uncertain",
            effectCertainty: "uncertain",
            knownEffects: ["entry:UNCERTAIN:a.mkv"],
            failure: {
              category: "workflow_failure",
              message: "bounded refusal",
              durableState: "TaskItem is durable",
              sideEffects: "none",
              retrySafe: false,
              nextAction: "inspect before repeating",
            },
            nextAction: "刷新来源与目标目录核实实际效果",
          },
        ],
      }),
      "resource",
      "source",
      "task-1",
    );
    expect(detail.nextAction).toBe("刷新目录");
    expect(detail.durableState).toBe("task_partial_success");
    expect(detail.effectCertainty).toBe("uncertain");
    expect(detail.items).toHaveLength(1);
    expect(detail.items[0]).toMatchObject({
      path: "a.mkv",
      status: "UNCERTAIN",
      effect: "uncertain",
    });
    expect(detail.items[0].failure?.category).toBe("workflow_failure");
    expect(detail.lifecycle).toBeNull();
    expect(() =>
      normalizeLibraryFileOperationDetail(
        entryDocument(),
        "resource",
        "source",
        "task-2",
      ),
    ).toThrow(LibraryFileOperationNormalizationError);
    // An unknown durable state is malformed rather than rendered verbatim.
    expect(() =>
      normalizeLibraryFileOperationDetail(
        entryDocument({ durableState: "something-else" }),
        "resource",
        "source",
        "task-1",
      ),
    ).toThrow(LibraryFileOperationNormalizationError);
  });

  it("keeps every recorded child entry and the item continuation truthful", () => {
    // A paused folder Move really moved some children: the document names each
    // one with its own destination, status and recorded checkpoints, and the
    // aggregate certainty never collapses a known change to "no change".
    const detail = normalizeLibraryFileOperationDetail(
      entryDocument({
        status: "paused",
        terminal: false,
        settled: false,
        allSucceeded: false,
        totalItems: 3,
        settledItems: 1,
        succeededItems: 1,
        pendingItems: 2,
        durableState: "task_paused",
        effectCertainty: "partial",
        itemTotal: 3,
        itemsTruncated: true,
        nextCursor: "cursor-2",
        items: [
          {
            itemId: "item-1",
            path: "show",
            destination: "Movies/show",
            status: "PAUSED",
            stage: "paused",
            attempts: 1,
            effect: "partial",
            effectCertainty: "partial",
            knownEffects: [],
            children: [
              {
                path: "show",
                destination: "Movies/show",
                status: "SUCCESS",
                effect: "transferred",
                checkpoints: [],
              },
              {
                path: "show/ep00.mkv",
                destination: "Movies/show/ep00.mkv",
                status: "SUCCESS",
                effect: "transferred",
                checkpoints: [],
              },
              {
                path: "show/ep01.mkv",
                destination: "Movies/show/ep01.mkv",
                status: "FAILED",
                effect: "retained",
                checkpoints: [],
                failure: {
                  category: "storage_failure",
                  message: "bounded provider refusal",
                  durableState: "TaskItem is durable",
                  sideEffects: "none",
                  retrySafe: false,
                  nextAction: "inspect the source",
                },
              },
            ],
            childrenTruncated: false,
            nextAction: "在确认剩余范围安全后再明确继续该操作",
          },
        ],
      }),
      "resource",
      "source",
      "task-1",
    );
    expect(detail.itemTotal).toBe(3);
    expect(detail.itemsTruncated).toBe(true);
    expect(detail.nextCursor).toBe("cursor-2");
    expect(detail.effectCertainty).toBe("partial");
    expect(detail.items[0].children).toHaveLength(3);
    expect(detail.items[0].children[1]).toMatchObject({
      path: "show/ep00.mkv",
      destination: "Movies/show/ep00.mkv",
      effect: "transferred",
    });
    expect(detail.items[0].children[2].failure?.message).toBe(
      "bounded provider refusal",
    );
    // A page whose item population contradicts the operation's own count is
    // malformed, never silently accepted as a truncated page.
    expect(() =>
      normalizeLibraryFileOperationDetail(
        entryDocument({ itemTotal: 0 }),
        "resource",
        "source",
        "task-1",
      ),
    ).toThrow(LibraryFileOperationNormalizationError);
    // An unknown child status/effect is malformed rather than rendered.
    expect(() =>
      normalizeLibraryFileOperationDetail(
        entryDocument({
          items: [
            {
              itemId: "item-1",
              path: "show",
              destination: "Movies/show",
              status: "PAUSED",
              stage: "paused",
              attempts: 1,
              effect: "partial",
              effectCertainty: "partial",
              knownEffects: [],
              children: [
                {
                  path: "show/x.mkv",
                  destination: "",
                  status: "MYSTERY",
                  effect: "transferred",
                  checkpoints: [],
                },
              ],
              childrenTruncated: false,
              nextAction: "inspect",
            },
          ],
        }),
        "resource",
        "source",
        "task-1",
      ),
    ).toThrow(LibraryFileOperationNormalizationError);
  });

  it("normalizes a proven origin and a bounded non-match", () => {
    const matched = normalizeLibraryFileOperationOrigin({
      matched: true,
      taskId: "task-1",
      libraryKind: "media",
      libraryIdField: "mediaLibraryId",
      libraryId: "movies",
      mediaLibraryId: "movies",
      path: "shows",
      sideEffects: "none",
      retrySafe: true,
    });
    // The published kind is part of the result: one read serves both kinds.
    expect(matched).toMatchObject({
      matched: true,
      libraryKind: "media",
      libraryId: "movies",
    });
    const unmatched = normalizeLibraryFileOperationOrigin({
      matched: false,
      taskId: "task-9",
      reason: "origin_unavailable",
      nextAction: "open the exact Task detail in Operations",
      sideEffects: "none",
    });
    expect(unmatched).toMatchObject({
      matched: false,
      reason: "origin_unavailable",
    });
    // A split identity is rejected instead of being rebound to one kind.
    expect(() =>
      normalizeLibraryFileOperationOrigin({
        matched: true,
        taskId: "task-1",
        libraryKind: "resource",
        libraryIdField: "resourceLibraryId",
        libraryId: "source",
        resourceLibraryId: "source",
        mediaLibraryId: "movies",
        path: null,
        sideEffects: "none",
      }),
    ).toThrow(LibraryFileOperationNormalizationError);
  });

  it("normalizes the bounded origin index and refuses the other kind", () => {
    expect(() =>
      normalizeLibraryFileOperationOrigins(
        {
          items: [
            {
              libraryKind: "media",
              libraryId: "movies",
              mediaLibraryId: "movies",
            },
          ],
          libraryKind: "media",
          libraryIdField: "mediaLibraryId",
          total: 1,
          truncated: false,
          sideEffects: "none",
        },
        "resource",
      ),
    ).toThrow(LibraryFileOperationNormalizationError);
    const model = normalizeLibraryFileOperationOrigins(
      {
        items: [
          {
            libraryKind: "media",
            libraryIdField: "mediaLibraryId",
            libraryId: "movies",
            mediaLibraryId: "movies",
          },
        ],
        libraryKind: "media",
        libraryIdField: "mediaLibraryId",
        total: 1,
        truncated: false,
        sideEffects: "none",
      },
      "media",
    );
    expect(model.items).toEqual([
      { libraryKind: "media", libraryId: "movies" },
    ]);
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
    skippedItems: 0,
    cancelledItems: 0,
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
