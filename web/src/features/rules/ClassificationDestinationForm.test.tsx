/**
 * Classification destination authoring and explicit legacy conversion.
 *
 * These tests bind the Web form to the revised contract: the destination is the
 * selected MediaLibrary plus one safe relative `path`, the library display name
 * is never copied into a path segment, and a stored legacy prefix is only ever
 * removed by a deliberate operator action.  All destination strings are backend
 * values rendered verbatim; the browser never calculates an authoritative path.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import { formAuthorityPayload } from "./rules-form-fixtures";
import { __resetRuleDraftsForTests } from "./rules-workspace-labels";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
  // Correctable drafts are per (family, object) and survive a remount by design,
  // so each case starts from a clean draft state.
  __resetRuleDraftsForTests();
});

const REVISED_POLICY = {
  id: "class-a",
  name: "Movie classification",
  description: "revised destination",
  enabled: true,
  priority: 0,
  rules: [
    {
      id: "action-movie",
      name: "Action movie",
      priority: 100,
      enabled: true,
      confidence: 100,
      description: "",
      conditions: { mediaType: ["movie"], genres: ["Action"] },
      result: {
        mediaLibraryId: "movies",
        path: ["电影", "华语"],
        destinationContract: "media_library_path",
      },
    },
  ],
};

const LEGACY_POLICY = {
  ...REVISED_POLICY,
  rules: [
    {
      ...REVISED_POLICY.rules[0],
      result: {
        mediaLibraryId: "movies",
        library: "Movies",
        path: ["电影", "华语"],
        destinationContract: "legacy_library_prefix",
      },
    },
  ],
};

function editPayload(object: unknown) {
  return {
    family: "classificationPolicies",
    object,
    references: {
      total: 0,
      items: [],
      truncated: false,
      removalBlocked: false,
    },
    active: {
      revisionId: "11111111-1111-4111-8111-111111111111",
      version: 1,
      digest: "0".repeat(64),
    },
    sideEffects: "none",
  };
}

function stubFetch(object: unknown, saves: Record<string, unknown>[]): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/form-authority"))
        return new Response(JSON.stringify(formAuthorityPayload));
      if (
        url.includes("/objects/classificationPolicies/") &&
        init?.method !== "PUT"
      )
        return new Response(JSON.stringify(editPayload(object)));
      if (url.includes("/objects/") && init?.method === "PUT") {
        saves.push(JSON.parse(String(init.body)) as Record<string, unknown>);
        return new Response(
          JSON.stringify({
            status: "active",
            revisionId: "22222222-2222-4222-8222-222222222222",
            version: 2,
            digest: "c".repeat(64),
            active: {
              revisionId: "22222222-2222-4222-8222-222222222222",
              version: 2,
              digest: "c".repeat(64),
            },
            message: "published",
            nextAction: "none",
          }),
        );
      }
      return new Response(JSON.stringify({ error: { code: "not_found" } }), {
        status: 404,
      });
    }),
  );
}

describe("classification destination authoring", () => {
  it("authors the revised contract without a library name or category output", async () => {
    const saves: Record<string, unknown>[] = [];
    stubFetch(REVISED_POLICY, saves);
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/classificationPolicies/class-a");
    await screen.findByRole("heading", { name: "class-a" });

    // The default state is the compact internal-rule inventory: the rule's own
    // priority, ID/name, condition summary and selected destination, with no
    // editor open until the explicit inner action.
    expect(screen.getAllByText("分类规则列表").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("columnheader", { name: "目标位置" }),
    ).toBeVisible();
    expect(screen.queryByLabelText("目标媒体库")).toBeNull();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "编辑规则 1" }));

    // The explicit inner edit exposes the destination selector and one safe path only.
    expect(screen.getByLabelText("目标媒体库")).toBeVisible();
    expect(screen.getByLabelText("相对路径")).toBeVisible();
    expect(screen.queryByLabelText("分类")).toBeNull();
    expect(screen.queryByLabelText("子分类")).toBeNull();

    // The selected root and the composed target are stated from backend values.
    expect(screen.getByTestId("destination-contract")).toHaveTextContent(
      "/Media",
    );
    expect(screen.getByTestId("destination-contract")).toHaveTextContent(
      "电影/华语",
    );

    await user.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saves.length).toBe(1));
    const submitted = saves[0]?.object as Record<string, unknown>;
    const rules = submitted.rules as Record<string, unknown>[];
    const result = rules[0]?.result as Record<string, unknown>;
    expect(result.mediaLibraryId).toBe("movies");
    expect(result.path).toEqual(["电影", "华语"]);
    // No library display name is submitted for revised authoring.
    expect(result.library).toBeUndefined();
  });

  it("shows a stored legacy prefix and converts only on explicit intent", async () => {
    const saves: Record<string, unknown>[] = [];
    stubFetch(LEGACY_POLICY, saves);
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/classificationPolicies/class-a");
    await screen.findByRole("heading", { name: "class-a" });

    // The legacy contract is stated inside the explicit rule editor, together
    // with the proposed revised routing, before any deliberate conversion.
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "编辑规则 1" }));
    const notice = await screen.findByRole("status");
    expect(notice).toHaveTextContent("旧版前缀");
    expect(notice).toHaveTextContent("Movies");
    expect(notice).toHaveTextContent("/Media");
    expect(notice).toHaveTextContent("电影/华语");

    await user.click(
      screen.getByRole("button", { name: "移除规则 1 的旧版目标前缀" }),
    );
    await user.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saves.length).toBe(1));
    const submitted = saves[0]?.object as Record<string, unknown>;
    const rules = submitted.rules as Record<string, unknown>[];
    const result = rules[0]?.result as Record<string, unknown>;
    // Removal is an explicit null intent, never a silently omitted key.
    expect(result.library).toBeNull();
    // The existing explicit path is preserved rather than prefixed.
    expect(result.path).toEqual(["电影", "华语"]);
  });

  it("preserves a legacy prefix when the operator makes an unrelated edit", async () => {
    const saves: Record<string, unknown>[] = [];
    stubFetch(LEGACY_POLICY, saves);
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/classificationPolicies/class-a");
    await screen.findByRole("heading", { name: "class-a" });

    const user = userEvent.setup();
    // A cosmetic edit to the policy itself must not require opening (or
    // converting) any internal rule.
    const description = screen.getByLabelText("描述");
    await user.clear(description);
    await user.type(description, "cosmetic only");
    await user.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(saves.length).toBe(1));
    const submitted = saves[0]?.object as Record<string, unknown>;
    const rules = submitted.rules as Record<string, unknown>[];
    const result = rules[0]?.result as Record<string, unknown>;
    // The unchanged legacy contract travels with the object, so an unrelated
    // Save cannot switch the destination contract.
    expect(result.library).toBe("Movies");
  });
});
