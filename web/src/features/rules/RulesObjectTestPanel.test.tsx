import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import { rulesPayload } from "../../entities/rules/rules-workspace.test";
import {
  editProjectionPayload,
  formAuthorityPayload,
} from "./rules-form-fixtures";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  vi.unstubAllGlobals();
});

function analysisPayload(
  overrides: Readonly<Record<string, unknown>> = {},
): Record<string, unknown> {
  return {
    family: "recognitionRules",
    objectId: "C",
    outcome: "matched",
    conclusion: "规则在提交路径上匹配,输出类型 C",
    applicability: "applicable",
    runtimeEligibility: "separate",
    readiness: null,
    result: {
      ruleId: "rule-c",
      outputRecognitionType: "C",
      outputTypeEnabled: true,
      enabled: true,
      testedPath: "电影/Example.Movie.2024.mkv",
      parsed: { titleCandidate: "Example Movie", season: null, episode: null },
      condition: {
        kind: "logical",
        operator: "and",
        truth: true,
        children: [
          {
            kind: "atomic",
            field: "path",
            operator: "contains",
            expected: "/电影/",
            actual: "/电影/Example.Movie.2024.mkv",
            truth: true,
          },
        ],
      },
      evidence: [
        {
          field: "path",
          operator: "contains",
          expected: "/电影/",
          actual: "/电影/Example.Movie.2024.mkv",
        },
      ],
      competition: "single-rule local test",
    },
    message: null,
    nextAction: null,
    failureCategory: null,
    revisionId: "candidate-revision-1234",
    revisionVersion: 2,
    revisionDigest: "b".repeat(64),
    testedAt: "2026-01-01T00:00:00+00:00",
    stale: false,
    localOnly: true,
    candidateState: "validated_non_active",
    providerCalls: 0,
    storageReads: 0,
    identityStatus: null,
    syntheticIdentity: false,
    blockers: [],
    executionAuthorityGranted: null,
    ...overrides,
  };
}

function stubRulesRoutes(
  onAnalysis: (body: Record<string, unknown>, url: string) => Response,
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/form-authority"))
      return new Response(JSON.stringify(formAuthorityPayload));
    if (url.includes("/objects/"))
      return new Response(JSON.stringify(editProjectionPayload));
    if (url.includes("/analysis/"))
      return onAnalysis(
        JSON.parse(String(init?.body)) as Record<string, unknown>,
        url,
      );
    if (url.endsWith("/complete-flow"))
      return onAnalysis(
        JSON.parse(String(init?.body)) as Record<string, unknown>,
        url,
      );
    if (url.includes("/inventory"))
      return new Response(JSON.stringify(rulesPayload));
    return new Response(JSON.stringify({ error: { code: "not_found" } }), {
      status: 404,
    });
  });
}

describe("Rules object-scoped local test", () => {
  it("tests only the exact unsaved candidate and renders the condition trace", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      stubRulesRoutes((body) => {
        bodies.push(body);
        return new Response(JSON.stringify(analysisPayload()));
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionRules/rule-c");
    expect(
      await screen.findByRole("heading", { name: "测试与预览" }),
    ).toBeVisible();
    // Opening the page performs no analysis submission.
    expect(bodies).toHaveLength(0);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "测试该识别规则" }));
    expect(await screen.findByText(/规则在提交路径上匹配/)).toBeVisible();
    expect(screen.getAllByText("path").length).toBeGreaterThan(0);
    expect(screen.getByText(/→ 实际/)).toBeVisible();
    expect(screen.getByText(/运行时资格/)).toBeVisible();
    expect(screen.getByText(/与本次本地结论分开判定/)).toBeVisible();
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({
      candidate: { family: "recognitionRules", objectId: "rule-c" },
      liveMetadata: false,
    });
    expect((bodies[0]?.sample as Record<string, unknown>)?.path).toBe(
      "电影/Example.Movie.2024.mkv",
    );
  });

  it("never submits on edit, navigation or refresh and marks the result stale", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      stubRulesRoutes((body) => {
        bodies.push(body);
        return new Response(JSON.stringify(analysisPayload()));
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionRules/rule-c");
    await screen.findByRole("heading", { name: "测试与预览" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "测试该识别规则" }));
    await screen.findByText(/规则在提交路径上匹配/);
    expect(bodies).toHaveLength(1);
    // A relevant edit invalidates currency but submits nothing by itself.
    fireEvent.change(screen.getByLabelText(/^名称/), {
      target: { value: "Edited" },
    });
    expect(
      await screen.findByText(/该结果已过期;当前表单、样本或 Active 已变化/),
    ).toBeVisible();
    expect(bodies).toHaveLength(1);
  });

  it("keeps a rejected analysis actionable and retains the input", async () => {
    vi.stubGlobal(
      "fetch",
      stubRulesRoutes(
        () =>
          new Response(
            JSON.stringify({
              error: {
                code: "rules_reference_unavailable",
                message: "reference unavailable",
                details: {
                  stage: "reference",
                  nextAction: "修正引用后显式重跑",
                  durableState: "active_unchanged",
                },
              },
            }),
            { status: 409 },
          ),
      ),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionRules/rule-c");
    await screen.findByRole("heading", { name: "测试与预览" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "测试该识别规则" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("rules_reference_unavailable");
    expect(alert).toHaveTextContent("修正引用后显式重跑");
    expect(alert).toHaveTextContent("输入仍保留");
    // The submitted path survives the failure so recovery needs no retyping.
    expect(screen.getByLabelText("测试合成路径")).toHaveValue(
      "电影/Example.Movie.2024.mkv",
    );
  });

  it("offers no live Provider option for families that cannot use one", async () => {
    vi.stubGlobal(
      "fetch",
      stubRulesRoutes(() => new Response(JSON.stringify(analysisPayload()))),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionRules/rule-c");
    await screen.findByRole("heading", { name: "测试与预览" });
    expect(screen.queryByLabelText("允许实时元数据测试")).toBeNull();
  });

  it("offers the explicit live Provider option for the MetadataPolicy family", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      stubRulesRoutes((body) => {
        bodies.push(body);
        return new Response(
          JSON.stringify(
            analysisPayload({
              family: "metadataPolicies",
              result: {
                policyId: "C",
                mode: "offline",
                verified: false,
                queryType: "movie",
                effectiveSettings: { providerId: "tmdb" },
                credentialReadiness: {
                  providerId: "tmdb",
                  fields: [{ field: "TMDB_ACCESS_TOKEN", state: "SET" }],
                },
              },
              outcome: "valid",
              conclusion: "元数据策略本地配置有效(离线,未调用 Provider)",
            }),
          ),
        );
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/metadataPolicies/C");
    await screen.findByRole("heading", { name: "测试与预览" });
    expect(screen.getByLabelText("允许实时元数据测试")).not.toBeChecked();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "测试该元数据策略" }));
    await screen.findByText(/未调用 Provider/);
    expect(bodies[0]?.liveMetadata).toBe(false);
    expect(screen.getByText("TMDB_ACCESS_TOKEN: SET")).toBeVisible();
  });

  it("requires no sample input for a definition or reference check", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      stubRulesRoutes((body) => {
        bodies.push(body);
        return new Response(
          JSON.stringify(
            analysisPayload({
              family: "typeBindings",
              result: {
                recognitionType: "C",
                recognitionTypeIdentity: "C",
                recognitionTypeEnabled: true,
                enabled: true,
                resolvedPolicies: {
                  metadataPolicy: { id: "C", resolved: true, enabled: true },
                  namingPolicy: { id: "A", resolved: true, enabled: true },
                  classificationPolicy: {
                    id: "A",
                    resolved: true,
                    enabled: true,
                  },
                  organizePolicy: { id: "A", resolved: true, enabled: true },
                },
                duplicateEnabledBindings: [],
              },
              outcome: "valid",
              conclusion: "绑定有效:类型、启用唯一性与四项策略引用均可解析",
            }),
          ),
        );
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/typeBindings/type-c");
    await screen.findByRole("heading", { name: "测试与预览" });
    expect(screen.queryByLabelText("测试合成路径")).toBeNull();
    expect(screen.queryByLabelText("测试样本标题")).toBeNull();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "检查该类型绑定" }));
    await screen.findByText(/绑定有效/);
    expect(bodies[0]?.sample).toBeNull();
    expect(screen.getByText(/身份保持:C/)).toBeVisible();
  });

  it("labels the physical readiness of an OrganizePolicy explanation as unchecked", async () => {
    vi.stubGlobal(
      "fetch",
      stubRulesRoutes(
        () =>
          new Response(
            JSON.stringify(
              analysisPayload({
                family: "organizePolicies",
                result: {
                  policyId: "C",
                  operation: "move",
                  conflictStrategy: "manual",
                  overwriteAuthorized: false,
                  deleteAuthorized: false,
                  requiredStorageCapabilities: ["move"],
                  warnings: [],
                  physicalReadiness: "未检查",
                  executionReadiness: "未检查",
                },
                outcome: "valid",
                conclusion: "整理策略定义有效",
              }),
            ),
          ),
      ),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/organizePolicies/C");
    await screen.findByRole("heading", { name: "测试与预览" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "解释该整理策略" }));
    await screen.findByText("整理策略定义有效");
    expect(screen.getAllByText("未检查").length).toBeGreaterThanOrEqual(2);
  });
});

describe("Rules complete-flow check", () => {
  it("stays a single read-only inventory request until explicitly opened", async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        urls.push(url);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    expect(await screen.findByText("完整流程检查")).toBeVisible();
    // Landing on Overview reads the inventory only.
    expect(urls.filter((url) => url.includes("/inventory"))).toHaveLength(1);
    expect(urls.filter((url) => url.includes("form-authority"))).toHaveLength(
      0,
    );
    expect(urls.filter((url) => url.includes("complete-flow"))).toHaveLength(0);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "打开完整流程检查" }));
    await waitFor(() =>
      expect(
        urls.filter((url) => url.includes("form-authority")).length,
      ).toBeGreaterThan(0),
    );
    expect(urls.filter((url) => url.includes("complete-flow"))).toHaveLength(0);
  });

  it("renders a real complete plan with its plan target and no execution authority", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        if (url.endsWith("/complete-flow")) {
          bodies.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
          return new Response(
            JSON.stringify(
              analysisPayload({
                family: "recognitionRules",
                objectId: null,
                outcome: "valid",
                conclusion: "完整流程检查通过:已生成完整整理计划",
                readiness: "complete_plan_ready",
                localOnly: false,
                identityStatus: "synthetic_offline",
                syntheticIdentity: true,
                blockers: [],
                executionAuthorityGranted: "none",
                result: {
                  recognition: {
                    status: "recognized",
                    recognitionType: "C",
                    ruleId: "rule-c",
                  },
                  policy: {
                    metadataPolicy: "C",
                    namingPolicy: "A",
                    classificationPolicy: "A",
                    organizePolicy: "A",
                  },
                  naming: { directory: "Anime", filename: "Example.mkv" },
                  classification: {
                    mediaLibraryId: "movies",
                    relativePath: "Anime",
                  },
                  plan: {
                    target: "/Movies/Anime/Example.mkv",
                    operation: "move",
                    status: "ready",
                    conflicts: [],
                  },
                },
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
    renderApp("/ui-v2/rules");
    await screen.findByText("完整流程检查");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "打开完整流程检查" }));
    await screen.findByLabelText("完整流程来源资源库");
    await user.click(screen.getByRole("button", { name: "运行完整流程检查" }));
    expect(await screen.findByText(/完整流程检查通过/)).toBeVisible();
    expect(screen.getByText("/Movies/Anime/Example.mkv")).toBeVisible();
    expect(screen.getByText("离线合成身份(未验证)")).toBeVisible();
    expect(screen.getByText("完整计划就绪")).toBeVisible();
    expect(bodies[0]?.liveMetadata).toBe(false);
    expect(bodies[0]?.syntheticIdentity).toMatchObject({ mediaType: "movie" });
  });

  it("shows exact missing-stage blockers instead of a fabricated plan", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.includes("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        if (url.endsWith("/complete-flow"))
          return new Response(
            JSON.stringify(
              analysisPayload({
                outcome: "invalid_input",
                conclusion: "完整流程检查发现缺失阶段",
                readiness: "blocked",
                localOnly: false,
                identityStatus: "not_reached",
                syntheticIdentity: false,
                blockers: [
                  {
                    stage: "binding",
                    message: "RecognitionType C 尚未配置可解析的下游绑定",
                  },
                ],
                result: {
                  recognition: { status: "recognized", recognitionType: "C" },
                },
              }),
            ),
          );
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules");
    await screen.findByText("完整流程检查");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "打开完整流程检查" }));
    await screen.findByLabelText("完整流程来源资源库");
    await user.click(screen.getByRole("button", { name: "运行完整流程检查" }));
    expect(await screen.findByText("缺失阶段")).toBeVisible();
    expect(screen.getByText(/尚未配置可解析的下游绑定/)).toBeVisible();
    expect(screen.getByText("受阻")).toBeVisible();
  });
});
