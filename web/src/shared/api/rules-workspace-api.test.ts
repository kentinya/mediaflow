import { describe, expect, it, vi } from "vitest";
import { rulesPayload } from "../../entities/rules/rules-workspace.test";
import {
  fetchRuleEdit,
  fetchRulesInventory,
  fetchRuleImpact,
  fetchRuleCopy,
  isRulesObjectId,
  removeRuleObject,
  runRulesPreview,
  rulesInventoryPath,
  RulesWorkspaceApiError,
  saveRuleObject,
  setRuleObjectEnabled,
  editRuleObject,
} from "./api-client";

const AUTHORITY = {
  expectedRevisionId: "rev-1",
  expectedVersion: 1,
  expectedDigest: "a".repeat(64),
};

const response = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("Rules workspace API", () => {
  it("allowlists and encodes supported inventory filters", () => {
    expect(
      rulesInventoryPath({
        family: "recognitionTypes",
        query: " Special ",
        enabled: true,
      }),
    ).toBe(
      "/api/v1/operations/rules/inventory?family=recognitionTypes&q=Special&enabled=true",
    );
    expect(rulesInventoryPath()).toBe("/api/v1/operations/rules/inventory");
  });

  it("normalizes accepted data and maps bounded errors", async () => {
    const fetchOk = vi.fn(async () => response(rulesPayload));
    const model = await fetchRulesInventory("token", {}, fetchOk);
    expect(model.active?.status).toBe("ACTIVE");
    expect(fetchOk).toHaveBeenCalledWith(
      "/api/v1/operations/rules/inventory",
      expect.objectContaining({ method: "GET" }),
    );
    await expect(
      fetchRulesInventory("token", {}, async () => response({}, 401)),
    ).rejects.toMatchObject<Partial<RulesWorkspaceApiError>>({
      category: "unauthorized",
    });
    await expect(
      fetchRulesInventory("token", {}, async () => response({}, 403)),
    ).rejects.toMatchObject<Partial<RulesWorkspaceApiError>>({
      category: "forbidden",
    });
    await expect(
      fetchRulesInventory("token", {}, async () =>
        response({ ...rulesPayload, sections: {} }),
      ),
    ).rejects.toMatchObject<Partial<RulesWorkspaceApiError>>({
      category: "malformed",
    });
  });

  it("submits and normalizes an exact-revision preview without replay", async () => {
    const fetchOk = vi.fn(async () =>
      response({
        revisionId: "rev-1",
        revisionVersion: 4,
        revisionDigest: "a".repeat(64),
        status: "completed",
        stale: false,
        result: { recognitionType: "C" },
        message: "completed",
        nextAction: "review",
        failureCategory: null,
      }),
    );
    const outcome = await runRulesPreview(
      "token",
      "organize",
      {
        expectedRevisionId: "rev-1",
        expectedVersion: 4,
        expectedDigest: "a".repeat(64),
        recognitionType: "C",
      },
      fetchOk,
    );
    expect(outcome.ok && outcome.model.result?.recognitionType).toBe("C");
    expect(fetchOk).toHaveBeenCalledTimes(1);
    expect(fetchOk).toHaveBeenCalledWith(
      "/api/v1/operations/rules/previews/organize",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("accepts every backend-legal rules object ID and encodes it on the route", async () => {
    // The exact contract RulesWorkspaceCommandService enforces: first char
    // alphanumeric, then letters/digits/._:@+ - plus internal spaces, <= 64.
    for (const objectId of [
      "proof+type",
      "proof@type",
      "proof type",
      "proof.type",
      "movie",
      "a".repeat(64),
    ]) {
      expect(isRulesObjectId(objectId), objectId).toBe(true);
    }
    for (const objectId of [
      "",
      "a".repeat(65),
      " proof",
      "proof/type",
      "proof\\type",
      "proof%20type",
      ".proof",
      "-proof",
      "_proof",
    ]) {
      expect(isRulesObjectId(objectId), JSON.stringify(objectId)).toBe(false);
    }

    const seenUrls: string[] = [];
    const fetchOk = vi.fn(async (input: RequestInfo | URL) => {
      seenUrls.push(String(input));
      return response({
        family: "recognitionTypes",
        object: { id: "proof+type", enabled: true },
        references: {
          total: 0,
          items: [],
          truncated: false,
          removalBlocked: false,
        },
        active: { revisionId: "rev-1", version: 1 },
        sideEffects: "none",
      });
    });
    for (const objectId of [
      "proof+type",
      "proof@type",
      "proof type",
      "proof.type",
    ]) {
      const edit = await fetchRuleEdit(
        "token",
        "recognitionTypes",
        objectId,
        fetchOk,
      );
      expect(edit.ok, objectId).toBe(true);
      const copy = await fetchRuleCopy(
        "token",
        "recognitionTypes",
        objectId,
        fetchOk,
      );
      expect(copy.ok, objectId).toBe(true);
      const impact = await fetchRuleImpact(
        "token",
        "recognitionTypes",
        objectId,
        fetchOk,
      );
      expect(impact.ok, objectId).toBe(true);
    }
    // Every accepted ID is percent-encoded on the wire, never sent raw and
    // never turned into a different object identity.
    expect(seenUrls).toContain(
      "/api/v1/operations/rules/objects/recognitionTypes/proof%2Btype/copy",
    );
    expect(seenUrls).toContain(
      "/api/v1/operations/rules/objects/recognitionTypes/proof%20type/impact",
    );
    expect(seenUrls.every((url) => !url.includes(" "))).toBe(true);
  });

  it("rejects IDs outside the backend contract before any request travels", async () => {
    const fetchMock = vi.fn();
    for (const objectId of [
      "",
      "a".repeat(65),
      " proof",
      "proof/type",
      "proof\\type",
    ]) {
      const outcome = await fetchRuleEdit(
        "token",
        "recognitionTypes",
        objectId,
        fetchMock,
      );
      expect(outcome).toMatchObject({
        ok: false,
        status: 400,
        code: "invalid_request",
      });
      expect(fetchMock).not.toHaveBeenCalled();
      fetchMock.mockClear();
    }
  });

  it("commands accept backend-legal IDs with immutable identity and encode the route", async () => {
    const seenUrls: string[] = [];
    const fetchOk = vi.fn(async (input: RequestInfo | URL) => {
      seenUrls.push(String(input));
      return response({
        family: "recognitionTypes",
        object: { id: "proof+type", enabled: true },
        references: {
          total: 0,
          items: [],
          truncated: false,
          removalBlocked: false,
        },
        active: { revisionId: "rev-1", version: 2 },
        sideEffects: "none",
      });
    });
    const save = await saveRuleObject(
      "token",
      "recognitionTypes",
      { id: "proof+type", name: "N", enabled: true },
      AUTHORITY,
      fetchOk,
    );
    expect(save.ok).toBe(true);
    const edit = await editRuleObject(
      "token",
      "recognitionTypes",
      "proof+type",
      { id: "proof+type", name: "N2", enabled: true },
      AUTHORITY,
      fetchOk,
    );
    expect(edit.ok).toBe(true);
    const toggle = await setRuleObjectEnabled(
      "token",
      "recognitionTypes",
      "proof+type",
      false,
      AUTHORITY,
      fetchOk,
    );
    expect(toggle.ok).toBe(true);
    const remove = await removeRuleObject(
      "token",
      "recognitionTypes",
      "proof+type",
      AUTHORITY,
      fetchOk,
    );
    expect(remove.ok).toBe(true);
    expect(seenUrls).toContain(
      "/api/v1/operations/rules/objects/recognitionTypes",
    );
    expect(seenUrls).toContain(
      "/api/v1/operations/rules/objects/recognitionTypes/proof%2Btype",
    );
    expect(seenUrls).toContain(
      "/api/v1/operations/rules/objects/recognitionTypes/proof%2Btype/state/disable",
    );
  });

  it("refuses an edit whose candidate ID differs from the route identity", async () => {
    const fetchMock = vi.fn();
    const outcome = await editRuleObject(
      "token",
      "recognitionTypes",
      "proof+type",
      { id: "other", enabled: true },
      AUTHORITY,
      fetchMock,
    );
    expect(outcome).toMatchObject({
      ok: false,
      status: 400,
      code: "invalid_request",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
