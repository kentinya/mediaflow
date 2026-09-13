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
import { normalizeManualScan } from "./scan";

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
    expect(model.actions.scan.available).toBe(true);
    expect(model.actions.scan.path).toBe("/api/v1/operations/scans");
    expect(model.actions.scan.modes).toEqual(["full", "incremental"]);
    expect(model.actions.preview.available).toBe(true);
    expect(model.actions.preview.path).toBe("/api/v1/operations/previews");
    expect(model.source?.filename).toBe("One.2001.mkv");
    expect(model.source?.path).toBe("One.2001.mkv");
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
    expect(model.actions.scan.available).toBe(false);
    expect(model.actions.preview.available).toBe(false);
    expect(model.actions.scan.reason).toContain(
      "select an exact ResourceLibrary",
    );
    expect(model.resourceLibraries).toHaveLength(1);
  });
});

describe("real API Scan documents", () => {
  it("normalizes the admission response and the refreshable detail", () => {
    const admission = normalizeManualScan(document("scanAdmission"));
    expect(admission.status).toBe("running");
    expect(admission.mode).toBe("incremental");
    expect(admission.scopeKind).toBe("file");
    expect(admission.items).toEqual([]);
    expect(admission.itemLimit).toBeNull();
    expect(admission.actions.cancel.available).toBe(true);
    expect(admission.actions.cancel.method).toBe("POST");
    expect(admission.actions.cancel.path).toContain("/cancel");

    const detail = normalizeManualScan(document("scanDetail"));
    expect(detail.status).toBe("completed");
    expect(detail.progress.filesVisited).toBe(1);
    expect(detail.progress.mediaCandidates).toBe(1);
    expect(detail.progress.errors).toBe(0);
    expect(detail.items).toHaveLength(1);
    expect(detail.items[0]?.status).toBe("ready");
    expect(detail.items[0]?.change).toBe("unchanged");
    expect(detail.items[0]?.sourcePath).toBe("One.2001.mkv");
    expect(detail.items[0]?.failure).toBeNull();
    expect(detail.errors).toEqual([]);
    expect(detail.failure).toBeNull();
    expect(detail.actions.cancel.available).toBe(false);
  });

  it("normalizes the paged ResourceLibrary detail without dropping siblings", () => {
    const paged = normalizeManualScan(document("scanLibraryDetail"));
    expect(paged.scopeKind).toBe("resourceLibrary");
    expect(paged.itemLimit).toBe(1);
    expect(paged.items).toHaveLength(1);
    expect(paged.itemsTruncated).toBe(true);
    expect(paged.nextItemCursor).not.toBeNull();
    expect(paged.previousItemCursor).toBeNull();
    expect(paged.reconciliationComplete).toBe(true);
    expect(paged.progress.filesVisited).toBe(2);
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
          "this exact plan replaces and deletes nothing; source media is preserved by the reviewed operation",
      });
      expect(item?.title).toBe("One");
      expect(item?.provider).toBe("tmdb");
      expect(item?.providerId).toBe("129");
      expect(item?.organizePolicy).toBe("A");
      expect(item?.targetStorageId).toBe("target");
      expect(item?.targetPath).toBe("Anime/One (2001)/One (2001).mkv");
      expect(item?.destination?.relativePath).toBe(
        "Anime/One (2001)/One (2001).mkv",
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
