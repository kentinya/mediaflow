import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/manual-operations.json";
import {
  normalizeManualPreview,
  normalizeManualPreviewItem,
  normalizeManualPreviewListPage,
} from "./preview";

type Json = Record<string, unknown>;

const documents = fixture as unknown as Record<string, Json>;

/**
 * Every case below starts from the exact document the real Python API returned
 * (see `manual-operations-contract.test.ts`) and then mutates one field, so a
 * malformed or hostile payload is rejected against the real contract instead of
 * a hand-written approximation of it.
 */
function previewPayload(overrides: Json = {}): Json {
  const base = JSON.parse(JSON.stringify(documents["previewDetail"])) as Record<
    string,
    unknown
  >;
  return { ...base, ...overrides };
}

function firstItem(payload: Json): Json {
  return (payload["items"] as Json[])[0];
}

describe("normalizeManualPreview", () => {
  it("accepts the real API preview document", () => {
    const model = normalizeManualPreview(previewPayload());
    expect(model.status).toBe("previewed");
    expect(model.zeroMutation).toBe(true);
    expect(model.scope?.scopeKind).toBe("file");
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.title).toBe("One");
    expect(model.items[0]?.targetPath).toBe("Anime/One (2001)/One (2001).mkv");
    expect(model.items[0]?.policies).toEqual({
      recognitionTypePolicyId: "type-A",
      metadataPolicyId: "A",
      namingPolicyId: "A",
      classificationPolicyId: "A",
      organizePolicyId: "A",
    });
    expect(model.items[0]?.analysis?.parse?.titleCandidate).toBe("One");
    expect(model.items[0]?.analysis?.recognition?.ruleId).toBe(
      "manual-preview",
    );
    expect(model.items[0]?.analysis?.metadata?.match?.candidateCount).toBe(1);
    expect(model.items[0]?.analysis?.naming?.filename).toBe("One (2001).mkv");
    expect(model.items[0]?.analysis?.classification?.matchedRuleName).toBe(
      "Japanese Animation",
    );
  });

  it("rejects an unknown status instead of casting it", () => {
    expect(() =>
      normalizeManualPreview(previewPayload({ status: "completed" })),
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

  it("rejects non-array items or selection lists", () => {
    expect(() =>
      normalizeManualPreview(previewPayload({ items: "not-array" })),
    ).toThrow();
    expect(() =>
      normalizeManualPreview(
        previewPayload({ selection: { selectedItemIds: "not-array" } }),
      ),
    ).toThrow();
  });

  it("rejects a scope object that is not a record", () => {
    expect(() =>
      normalizeManualPreview(previewPayload({ scope: "invalid" })),
    ).toThrow();
  });

  it("rejects a half-identified scope instead of inventing an absence", () => {
    expect(() =>
      normalizeManualPreview(previewPayload({ scopeId: null })),
    ).toThrow();
  });

  it("rejects an execution state the backend cannot mean", () => {
    expect(() =>
      normalizeManualPreview(
        previewPayload({ executionState: "organization_authorized" }),
      ),
    ).toThrow();
  });

  it("keeps a legacy preview without a source scope visible", () => {
    const model = normalizeManualPreview(
      previewPayload({ scope: null, scopeKind: null, scopeId: null }),
    );
    expect(model.scope).toBeNull();
    expect(model.scopeKind).toBeNull();
    expect(model.items).toHaveLength(1);
  });

  it("normalizes bounded preview item failure", () => {
    const model = normalizeManualPreview(
      previewPayload({
        items: [
          {
            ...firstItem(previewPayload()),
            status: "failed",
            plan: null,
            failure: {
              category: "provider",
              message: "metadata lookup failed",
              nextAction: "check provider availability",
            },
          },
        ],
      }),
    );
    expect(model.items[0]?.status).toBe("failed");
    expect(model.items[0]?.planStatus).toBeNull();
    expect(model.items[0]?.failure?.category).toBe("provider");
    expect(model.items[0]?.failure?.nextAction).toBe(
      "check provider availability",
    );
  });

  it("preserves bounded attachments and conflicts without host roots", () => {
    const item = firstItem(previewPayload());
    const plan = item["plan"] as Json;
    const model = normalizeManualPreview(
      previewPayload({
        items: [
          {
            ...item,
            plan: {
              ...plan,
              attachments: [
                {
                  type: "subtitle",
                  operation: "link",
                  suffix: ".zh",
                  language: "zh",
                  filename: "One (2001).zh.srt",
                  storageId: "target",
                },
              ],
              conflicts: [
                {
                  type: "target_exists",
                  source: "Anime/One (2001)/One (2001).mkv",
                  destination: "Anime/One (2001)/One (2001).mkv",
                  details: "an existing target was found",
                },
              ],
              warnings: ["the target directory is created by this plan"],
            },
          },
        ],
      }),
    );
    const projected = model.items[0];
    expect(projected?.attachments).toHaveLength(1);
    expect(projected?.attachments[0]?.language).toBe("zh");
    expect(projected?.conflicts).toHaveLength(1);
    expect(projected?.conflicts[0]?.type).toBe("target_exists");
    expect(projected?.warnings).toEqual([
      "the target directory is created by this plan",
    ]);
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
  it("normalizes one real API preview item", () => {
    const item = normalizeManualPreviewItem(firstItem(previewPayload()));
    expect(item.recognitionType).toBe("A");
    expect(item.title).toBe("One");
    expect(item.provider).toBe("tmdb");
    expect(item.providerId).toBe("129");
    expect(item.organizePolicy).toBe("A");
    expect(item.failure).toBeNull();
  });

  it("keeps an item without a plan visible without inventing findings", () => {
    const item = normalizeManualPreviewItem({
      ...firstItem(previewPayload()),
      status: "blocked",
      plan: null,
      failure: {
        category: "conflict",
        message: "the current source is unavailable",
        nextAction: "rerun a fresh Preview for this source",
      },
    });
    expect(item.status).toBe("blocked");
    expect(item.sourcePath).toBe("One.2001.mkv");
    expect(item.recognitionType).toBeNull();
    expect(item.title).toBeNull();
    expect(item.targetPath).toBeNull();
    expect(item.attachments).toEqual([]);
    expect(item.conflicts).toEqual([]);
    expect(item.capabilities).toBeNull();
    expect(item.policies).toBeNull();
    expect(item.analysis).toBeNull();
    expect(item.failure?.category).toBe("conflict");
  });
});

describe("normalizeManualPreviewListPage", () => {
  it("accepts the real API preview list page", () => {
    const page = normalizeManualPreviewListPage(
      JSON.parse(JSON.stringify(documents["previewList"])) as Json,
    );
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
