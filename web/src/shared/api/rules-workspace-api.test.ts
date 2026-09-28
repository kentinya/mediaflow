import { describe, expect, it, vi } from "vitest";
import { rulesPayload } from "../../entities/rules/rules-workspace.test";
import {
  fetchRulesInventory,
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
});
