/**
 * Contract test: the documents the real Python API returns must normalize
 * through the real client models.
 *
 * `web/src/entities/operations/__fixtures__/manual-operations.json` is written
 * by `tests/test_manual_operations_contract.py`, which drives the real
 * `MediaFlowApi` (real runtime configuration, real LocalStorage source, real
 * scanner-produced FileIndex record, real manual Scan/Preview services) and
 * captures the exact bounded documents for:
 *
 *   GET  /api/v1/operations/manual-actions
 *   POST /api/v1/operations/scans
 *   GET  /api/v1/operations/scans/{taskId}
 *   POST /api/v1/operations/previews
 *   GET  /api/v1/operations/previews
 *   GET  /api/v1/operations/previews/{previewId}
 *
 * That Python module also proves the checked-in fixture is still exactly what
 * the API returns. This test proves the frontend consumes those real payloads:
 * the same non-null fields, the same nested plan findings, and no fabricated
 * value where the API returned none.
 */

import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/manual-operations.json";
import { normalizeManualActionMatrix } from "./manual-actions";
import {
  normalizeManualPreview,
  normalizeManualPreviewListPage,
} from "./preview";

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;

function document(name: string): Json {
  return JSON.parse(JSON.stringify(documents[name])) as Json;
}

describe("real API action matrix documents", () => {
  it("normalizes the exact-file matrix the backend advertises", () => {
    const model = normalizeManualActionMatrix(document("actionMatrix"));
    expect(model.scopeKind).toBe("file");
    expect(model.scopeId).not.toBeNull();
    expect(model.fileId).not.toBeNull();
    expect(model.resourceLibraryId).toBe("library");
    expect(model.selectionRequired).toBe(false);
    expect(model.runtime.ready).toBe(true);
    expect(model.runtime.condition).toBe("configuration_active");
    // A single-file admission is made from the live directory, so the matrix
    // states that prerequisite instead of resolving a remembered file ID.
    expect(model.actions.preview.available).toBe(false);
    expect(model.actions.preview.reason).toContain("live file");
    expect(model.actions.organize.available).toBe(false);
    expect(model.actions.organize.reason).toContain("live file");
    expect(model.source).toBeNull();
    expect(model.limits.previewMaxItems).toBeGreaterThan(0);
    expect(
      model.resourceLibraries.map((item) => item.resourceLibraryId),
    ).toEqual(["library"]);
    expect(model.resourceLibraries[0]?.enabled).toBe(true);
  });

  it("offers no actionable submission before an exact ResourceLibrary is selected", () => {
    const model = normalizeManualActionMatrix(
      document("resourceLibraryDiscovery"),
    );
    expect(model.scopeKind).toBe("resourceLibrary");
    expect(model.scopeId).toBeNull();
    expect(model.resourceLibraryId).toBeNull();
    expect(model.selectionRequired).toBe(true);
    expect(model.source).toBeNull();
    expect(model.actions.preview.available).toBe(false);
    expect(model.resourceLibraries).toHaveLength(1);
  });
});

describe("real API Preview documents", () => {
  it("normalizes the admission, detail and list documents with real findings", () => {
    for (const name of ["previewAdmission", "previewDetail"]) {
      const preview = normalizeManualPreview(document(name));
      expect(preview.status).toBe("previewed");
      expect(preview.zeroMutation).toBe(true);
      expect(preview.current).toBe(true);
      expect(preview.scopeKind).toBe("file");
      expect(preview.scope?.scopeKind).toBe("file");
      expect(preview.scope?.itemCount).toBe(1);
      expect(preview.selection.selectedItemIds).toHaveLength(1);
      expect(preview.selection.unselectedItemIds).toEqual([]);
      expect(preview.failure).toBeNull();

      const item = preview.items[0];
      expect(item).toBeDefined();
      expect(item?.status).toBe("previewed");
      expect(item?.zeroMutation).toBe(true);
      expect(item?.sourcePath).toBe("One.2001.mkv");
      expect(item?.sourceFilename).toBe("One.2001.mkv");
      expect(item?.recognitionType).toBe("A");
      expect(item?.operation).toBe("MOVE");
      expect(item?.destructiveImplications).toEqual({
        overwriteRequired: false,
        sourceCleanupRequired: false,
        statement:
          "this exact plan moves each source to its reviewed target; after a successful organize the source location no longer holds the original media file",
      });
      expect(item?.title).toBe("One");
      expect(item?.provider).toBe("tmdb");
      expect(item?.providerId).toBe("129");
      expect(item?.organizePolicy).toBe("A");
      expect(item?.targetStorageId).toBe("target");
      expect(item?.targetPath).toBe(
        "Movies/Movies/Anime/One (2001)/One (2001).mkv",
      );
      expect(item?.destination?.relativePath).toBe(
        "Movies/Anime/One (2001)/One (2001).mkv",
      );
      expect(item?.planStatus).toBe("ready");
      expect(item?.capabilities?.verdict).toBe("ok");
      expect(item?.capabilities?.missing).toEqual([]);
      expect(item?.attachments).toEqual([]);
      expect(item?.conflicts).toEqual([]);
      expect(item?.warnings).toEqual([]);
      expect(item?.failure).toBeNull();
    }
  });

  it("normalizes the bounded preview list page", () => {
    const page = normalizeManualPreviewListPage(document("previewList"));
    expect(page.total).toBe(1);
    expect(page.limit).toBeGreaterThan(0);
    expect(page.scopeKind).toBe("file");
    expect(page.items).toHaveLength(1);
    expect(page.items[0]?.zeroMutation).toBe(true);
  });
});
