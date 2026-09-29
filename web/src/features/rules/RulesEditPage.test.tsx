import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
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
    const previewBodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push(url);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        if (url.includes("/previews/")) {
          previewBodies.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
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
        }
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
    expect(previewBodies[0]).toMatchObject({
      resourceLibraryId: "source",
      candidate: {
        family: "recognitionTypes",
        objectId: "C",
        values: { id: "C" },
      },
    });

    const sample = screen.getByLabelText("命名、分类与目标样本 JSON");
    fireEvent.change(sample, {
      target: {
        value: JSON.stringify({ title: "Second sample", recognitionType: "C" }),
      },
    });
    expect(await screen.findByText(/该结果已过期/)).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "用当前输入重新运行此项" }),
    );
    await waitFor(() => expect(previewBodies).toHaveLength(2));
    expect(
      screen.getAllByRole("heading", { name: "strategy 结果" }),
    ).toHaveLength(2);
  });
});
