import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  screen,
  waitFor,
} from "@testing-library/react";
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

function previewPayload(result: Readonly<Record<string, unknown>>) {
  return {
    revisionId: "candidate-revision-1234",
    revisionVersion: 2,
    revisionDigest: "b".repeat(64),
    status: "completed",
    stale: false,
    result,
    message: "preview completed",
    nextAction: "review",
    failureCategory: null,
  };
}

describe("RulesEditPage previews", () => {
  it("uses typed sample controls and renders revision-linked strategy evidence", async () => {
    const previewBodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        if (url.endsWith("/previews/strategy")) {
          previewBodies.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
          return new Response(
            JSON.stringify(
              previewPayload({
                recognition: {
                  status: "recognized",
                  recognitionType: "C",
                  ruleId: "rule-c",
                  score: 90,
                  confidence: 0.9,
                  matchedRules: [
                    {
                      ruleId: "rule-c",
                      recognitionType: "C",
                      priority: 100,
                      score: 90,
                    },
                  ],
                  reasons: [{ code: "matched", message: "title matched" }],
                  warnings: [],
                },
                policy: {
                  typePolicyId: "type-c",
                  metadataPolicy: "C",
                  namingPolicy: "A",
                  classificationPolicy: "A",
                  organizePolicy: "A",
                },
                recognitionTypePreserved: true,
              }),
            ),
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
    expect(screen.getByLabelText("样本标题")).toHaveValue("The Matrix");
    expect(screen.getByLabelText("样本 RecognitionType")).toHaveValue("C");
    expect(screen.getByLabelText("样本 RecognitionType")).toBeDisabled();
    expect(screen.queryByRole("option", { name: "从路径解析" })).toBeNull();
    expect(screen.queryByLabelText("命名、分类与目标样本 JSON")).toBeNull();
    expect(screen.queryByRole("button", { name: "测试元数据策略" })).toBeNull();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "测试识别策略" }));
    expect(await screen.findByText(/候选修订 candidat/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "匹配规则" })).toBeVisible();
    expect(screen.getAllByText("rule-c")[0]).toBeVisible();
    expect(screen.getByText("type-c")).toBeVisible();
    expect(previewBodies[0]).toMatchObject({
      resourceLibraryId: "source",
      candidate: {
        family: "recognitionTypes",
        objectId: "C",
        values: { id: "C" },
      },
    });
    expect(previewBodies[0]?.sample).toBeUndefined();

    fireEvent.change(screen.getByLabelText("样本标题"), {
      target: { value: "Second sample" },
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

  it("keeps an in-flight old-candidate result stale after the form changes", async () => {
    let resolvePreview: ((response: Response) => void) | undefined;
    const pending = new Promise<Response>((resolve) => {
      resolvePreview = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        if (url.endsWith("/previews/strategy")) return pending;
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    await screen.findByRole("heading", { name: "C" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "测试识别策略" }));
    expect(screen.getByText(/正在测试提交时的候选/)).toBeVisible();
    fireEvent.change(screen.getByLabelText(/^名称/), {
      target: { value: "Changed while pending" },
    });
    await act(async () => {
      resolvePreview?.(
        new Response(
          JSON.stringify(
            previewPayload({
              recognition: { status: "recognized", recognitionType: "C" },
              policy: null,
              recognitionTypePreserved: true,
            }),
          ),
        ),
      );
      await pending;
    });
    expect(await screen.findByText(/该结果已过期/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "用当前输入重新运行此项" }),
    ).toBeEnabled();
  });

  it("renders classification and organize decisions as readable explanations", async () => {
    const previewBodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        if (url.includes("/previews/"))
          previewBodies.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
        if (url.endsWith("/previews/classification"))
          return new Response(
            JSON.stringify(
              previewPayload({
                status: "classified",
                appliedPolicyId: "A",
                matchedRuleId: "movies-rule",
                matchedRuleName: "Movies",
                mediaLibraryId: "movies",
                mediaLibraryResolved: true,
                relativePath: "Sci-Fi",
                recognitionType: "C",
                matchEvidence: ["genre matched"],
                warnings: [],
              }),
            ),
          );
        if (url.endsWith("/previews/organize"))
          return new Response(
            JSON.stringify(
              previewPayload({
                operation: "move",
                conflictStrategy: "manual",
                requiredStorageCapabilities: ["can_move"],
                warnings: ["review conflict"],
                destinationStatus: "completed",
                destination: {
                  destinationPath: "Movies/Sci-Fi/The Matrix.mkv",
                  verdict: "ready",
                  conflictProjection: { projectedOutcome: "ready" },
                },
                executionAllowed: true,
                executionAuthorityGranted: "none",
                allowBlockReasons: [
                  "read-only checks passed; execution still requires separate authority",
                ],
              }),
            ),
          );
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    await screen.findByRole("heading", { name: "C" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "预览分类" }));
    expect(
      await screen.findByRole("heading", { name: "分类结果" }),
    ).toBeVisible();
    expect(screen.getByText("Movies")).toBeVisible();
    expect(screen.getByText("Sci-Fi")).toBeVisible();
    expect(previewBodies[0]).toMatchObject({
      policySelection: { mode: "binding", recognitionType: "C" },
      sample: {
        title: "The Matrix",
        mediaType: "movie",
        recognitionType: "C",
        year: 1999,
      },
    });
    expect(
      (previewBodies[0]?.sample as Record<string, unknown>).extension,
    ).toBeUndefined();
    await user.click(screen.getByRole("button", { name: "解释整理权限" }));
    expect(
      await screen.findByRole("heading", { name: "整理权限与目标" }),
    ).toBeVisible();
    expect(screen.getByText("Movies/Sci-Fi/The Matrix.mkv")).toBeVisible();
    expect(screen.getByText("can_move")).toBeVisible();
    expect(
      screen.getByText(
        "read-only checks passed; execution still requires separate authority",
      ),
    ).toBeVisible();
    expect(screen.getByText("none")).toBeVisible();
  });

  it("shows typed validation recovery and reruns after correction", async () => {
    const previewBodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        if (url.endsWith("/previews/naming")) {
          previewBodies.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
          return new Response(
            JSON.stringify(
              previewPayload({
                appliedPolicyId: "A",
                recognitionType: "C",
                mediaType: "movie",
                directory: "The Matrix (2000)",
                filename: "The Matrix (2000).mkv",
                renderedVariables: { title: "The Matrix", year: "2000" },
                sanitizationChanges: [],
                warnings: [],
              }),
            ),
          );
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    await screen.findByRole("heading", { name: "C" });
    const user = userEvent.setup();
    fireEvent.change(screen.getByLabelText("样本年份"), {
      target: { value: "10000" },
    });
    await user.click(screen.getByRole("button", { name: "预览命名" }));
    expect(
      await screen.findByText(/年份 必须是 0 到 9999 的整数/),
    ).toBeVisible();
    expect(previewBodies).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("样本年份"), {
      target: { value: "2000" },
    });
    await user.click(
      screen.getByRole("button", { name: "用当前输入重新运行此项" }),
    );
    expect(await screen.findByText("The Matrix (2000).mkv")).toBeVisible();
    expect(previewBodies).toHaveLength(1);
    expect(previewBodies[0]).toMatchObject({
      policySelection: { mode: "binding", recognitionType: "C" },
      sample: { title: "The Matrix", year: 2000, recognitionType: "C" },
    });
  });
});
