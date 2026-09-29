import { describe, expect, it, vi } from "vitest";
import { rulesPayload } from "../../entities/rules/rules-workspace.test";
import {
  fetchRulesInventory,
  runRulesPreview,
  rulesInventoryPath,
  RulesWorkspaceApiError,
} from "./api-client";

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
});
