import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import {
  editProjectionPayload,
  formAuthorityPayload,
} from "./rules-form-fixtures";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

describe("RulesEditPage previews", () => {
  it("runs explicit preview actions and keeps a visible result or recovery state", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        calls.push(url);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        if (url.includes("/previews/"))
          return new Response(
            JSON.stringify({
              revisionId: formAuthorityPayload.active.revisionId,
              revisionVersion: 1,
              revisionDigest: formAuthorityPayload.active.digest,
              status: "completed",
              stale: false,
              result: { recognitionType: "C", explanation: "bounded" },
              message: "preview completed",
              nextAction: "review",
              failureCategory: null,
            }),
          );
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    expect(await screen.findByRole("heading", { name: "C" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "测试与预览" })).toBeVisible();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "测试识别策略" }));
    expect(await screen.findByText(/preview completed/)).toBeVisible();
    expect(calls.some((url) => url.endsWith("/previews/strategy"))).toBe(true);
    await waitFor(() =>
      expect(screen.getByText(/结果对应当前 revision/)).toBeVisible(),
    );
  });
});
