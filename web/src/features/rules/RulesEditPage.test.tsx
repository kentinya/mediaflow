import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";
import { rulesPayload } from "../../entities/rules/rules-workspace.test";
import {
  editProjectionPayload,
  formAuthorityPayload,
  saveSuccessPayload,
} from "./rules-form-fixtures";
import { __resetRuleDraftsForTests } from "./rules-workspace-labels";

afterEach(() => {
  cleanup();
  authStore.clearToken();
  __resetRuleDraftsForTests();
  vi.unstubAllGlobals();
});

function localAnalysisPayload(
  overrides: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  return {
    family: "recognitionTypes",
    objectId: "C",
    outcome: "valid",
    conclusion: "本地检查通过",
    applicability: "applicable",
    runtimeEligibility: "separate",
    readiness: null,
    result: { definition: { id: "C", name: "Special" }, associatedRules: [] },
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

describe("RulesEditPage edit card", () => {
  it("opens the edit card local test with typed controls and no complete-chain preview", async () => {
    const requests: { method: string; url: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        requests.push({ method, url });
        if (url.endsWith("/auth/principal"))
          return new Response(
            JSON.stringify({ principal_id: "rules-principal-a" }),
          );
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.endsWith("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    const dialog = await screen.findByRole("dialog", {
      name: "编辑识别类型 · Special",
    });
    // The exact identity stays immutable and readable in the ID field.
    const idField = within(dialog).getByLabelText(/^ID/) as HTMLInputElement;
    expect(idField.value).toBe("C");
    expect(idField.readOnly).toBe(true);
    // The legacy complete-chain preview area and its entry buttons are gone
    // from the edit surface (Slice54 RO-3); only the two local areas remain.
    for (const name of [
      "完整链路预览",
      "测试识别策略",
      "预览分类",
      "预览命名",
      "解释整理权限",
    ]) {
      expect(within(dialog).queryByText(name)).toBeNull();
      expect(within(dialog).queryByRole("button", { name })).toBeNull();
    }
    expect(within(dialog).getByRole("tab", { name: "设置" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await userEvent.click(
      within(dialog).getByRole("tab", { name: "单项测试" }),
    );
    expect(
      await within(dialog).findByRole("heading", { name: "测试与预览" }),
    ).toBeVisible();
    // The identification sample stays typed and explicit; the association is
    // an opt-in and nothing runs on open, switch or opt-in.
    expect(within(dialog).getByLabelText("试识别关联规则")).toBeVisible();
    expect(within(dialog).queryByLabelText("测试合成路径")).toBeNull();
    await userEvent.click(within(dialog).getByLabelText("试识别关联规则"));
    expect(within(dialog).getByLabelText("测试合成路径")).toBeVisible();
    expect(
      requests.every(
        (entry) =>
          entry.method === "GET" &&
          (entry.url.endsWith("/auth/principal") ||
            entry.url.endsWith("/form-authority") ||
            entry.url.endsWith("/inventory") ||
            entry.url.includes("/objects/recognitionTypes/C")),
      ),
    ).toBe(true);
  });
  it("keeps a late local-test result stale after the form changes across areas", async () => {
    let resolveAnalysis: ((response: Response) => void) | undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveAnalysis = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/auth/principal"))
          return new Response(
            JSON.stringify({ principal_id: "rules-principal-a" }),
          );
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.endsWith("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        if (url.includes("/analysis/")) return pending;
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    const dialog = await screen.findByRole("dialog", {
      name: "编辑识别类型 · Special",
    });
    await userEvent.click(
      within(dialog).getByRole("tab", { name: "单项测试" }),
    );
    await within(dialog).findByRole("heading", { name: "测试与预览" });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "测试该识别类型" }),
    );
    expect(
      await within(dialog).findByText(/正在测试提交时的未保存对象/),
    ).toBeVisible();
    // Edit the form in the other area of the same card while the run is in
    // flight; both areas stay mounted, so the result survives the switch.
    await userEvent.click(within(dialog).getByRole("tab", { name: "设置" }));
    fireEvent.change(within(dialog).getByLabelText(/^名称/), {
      target: { value: "Changed while pending" },
    });
    await userEvent.click(
      within(dialog).getByRole("tab", { name: "单项测试" }),
    );
    await act(async () => {
      resolveAnalysis?.(new Response(JSON.stringify(localAnalysisPayload({}))));
      await pending;
    });
    expect(await within(dialog).findByText(/该结果已过期/)).toBeVisible();
    expect(
      within(dialog).getByRole("button", { name: "用当前输入重新运行此项" }),
    ).toBeEnabled();
  });
  it("renders classification decisions as readable local-test explanations", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/auth/principal"))
          return new Response(
            JSON.stringify({ principal_id: "rules-principal-a" }),
          );
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.endsWith("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        if (url.includes("/objects/classificationPolicies/")) {
          const objectUrl = decodeURIComponent(
            url.split("/objects/classificationPolicies/")[1],
          );
          return new Response(
            JSON.stringify({
              family: "classificationPolicies",
              object: {
                id: objectUrl,
                name: "Movie classification",
                description: "",
                enabled: true,
                priority: 0,
                rules: [],
              },
              references: {
                total: 0,
                items: [],
                truncated: false,
                removalBlocked: false,
              },
              active: formAuthorityPayload.active,
              sideEffects: "none",
            }),
          );
        }
        if (url.includes("/analysis/")) {
          bodies.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
          return new Response(
            JSON.stringify(
              localAnalysisPayload({
                family: "classificationPolicies",
                objectId: "policy-a",
                outcome: "matched",
                conclusion: "分类规则命中:action-movie",
                result: {
                  status: "classified",
                  matchedRuleId: "action-movie",
                  mediaLibraryId: "movies",
                  mediaLibraryResolved: true,
                  relativePath: "电影/华语",
                  destinationContract: "media_library_path",
                  matchEvidence: ["genre matched"],
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
    renderApp("/ui-v2/rules/edit/classificationPolicies/policy-a");
    const dialog = await screen.findByRole("dialog", {
      name: "编辑分类规则 · Movie classification",
    });
    await userEvent.click(
      within(dialog).getByRole("tab", { name: "单项测试" }),
    );
    await within(dialog).findByRole("heading", { name: "测试与预览" });
    // The typed identity sample belongs to the card and travels with the
    // exact candidate; the evidence leads with the actual matched rule and
    // the real destination while full JSON stays in diagnostics.
    await userEvent.click(within(dialog).getByLabelText("测试样本识别类型"));
    await userEvent.type(
      within(dialog).getByLabelText("测试样本识别类型"),
      "C",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "测试该分类规则" }),
    );
    expect(await within(dialog).findByText(/分类规则命中/)).toBeVisible();
    expect(within(dialog).getByText("action-movie")).toBeVisible();
    expect(within(dialog).getByText("电影/华语")).toBeVisible();
    expect(within(dialog).getByText(/完整证据 JSON/)).toBeVisible();
    expect(bodies[0]).toMatchObject({
      candidate: {
        family: "classificationPolicies",
        objectId: "policy-a",
      },
      sample: {
        title: "The Matrix",
        mediaType: "movie",
        recognitionType: "C",
        year: 1999,
      },
    });
    // The classification sample never smuggles in naming-only fields.
    expect((bodies[0]?.sample as Record<string, unknown>).extension).toBe(
      undefined,
    );
    expect(
      bodies.some(
        (body) =>
          typeof body.liveMetadata === "boolean" && body.liveMetadata === false,
      ),
    ).toBe(true);
  });
  it("shows typed sample validation recovery and reruns after correction", async () => {
    const bodies: Record<string, unknown>[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/auth/principal"))
          return new Response(
            JSON.stringify({ principal_id: "rules-principal-a" }),
          );
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.endsWith("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        if (url.includes("/objects/recognitionTypes/C"))
          return new Response(JSON.stringify(editProjectionPayload));
        if (url.includes("/analysis/")) {
          bodies.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
          return new Response(JSON.stringify(localAnalysisPayload({})));
        }
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    const dialog = await screen.findByRole("dialog", {
      name: "编辑识别类型 · Special",
    });
    await userEvent.click(
      within(dialog).getByRole("tab", { name: "单项测试" }),
    );
    await within(dialog).findByRole("heading", { name: "测试与预览" });
    await userEvent.click(within(dialog).getByLabelText("试识别关联规则"));
    // A bounded invalid sample is refused before any request travels.
    fireEvent.change(within(dialog).getByLabelText("测试合成路径"), {
      target: { value: "" },
    });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "测试该识别类型" }),
    );
    expect(
      await within(dialog).findByText(/需要一个不超过 4096 个字符的合成路径/),
    ).toBeVisible();
    expect(bodies).toHaveLength(0);
    // Correcting the input in place re-runs explicitly with the fixed sample.
    fireEvent.change(within(dialog).getByLabelText("测试合成路径"), {
      target: { value: "电影/The Matrix (2000).mkv" },
    });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "用当前输入重新运行此项" }),
    );
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]?.sample).toMatchObject({
      path: "电影/The Matrix (2000).mkv",
    });
  });
});

describe("RulesEditPage classification save recovery", () => {
  const classificationAuthority = {
    ...formAuthorityPayload,
    mediaLibraries: [
      {
        id: "movies",
        name: "Movies",
        enabled: true,
        storageId: "media-target",
        rootPath: "/Media",
      },
    ],
    families: formAuthorityPayload.families.map((entry) =>
      entry.family === "classificationPolicies"
        ? {
            ...entry,
            fields: [
              "id",
              "name",
              "description",
              "enabled",
              "priority",
              "rules",
            ],
          }
        : entry,
    ),
  };

  it("states a refused Save and keeps the affected rule reachable on the full page", async () => {
    const calls: { method: string; url: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        calls.push({ method, url });
        if (url.endsWith("/auth/principal"))
          return new Response(
            JSON.stringify({ principal_id: "rules-principal-a" }),
          );
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(classificationAuthority));
        if (url.endsWith("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        if (url.includes("/objects/classificationPolicies/"))
          return new Response(
            JSON.stringify({
              family: "classificationPolicies",
              object: {
                id: "policy-a",
                name: "Policy A",
                description: "",
                enabled: true,
                priority: 0,
                rules: [
                  {
                    id: "rule-1",
                    name: "规则 1",
                    priority: 10,
                    enabled: true,
                    conditions: { mediaType: ["movie"] },
                    result: { mediaLibraryId: "movies", path: ["电影"] },
                  },
                ],
              },
              references: {
                total: 0,
                items: [],
                truncated: false,
                removalBlocked: false,
              },
              active: formAuthorityPayload.active,
              sideEffects: "none",
            }),
          );
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/classificationPolicies/policy-a");
    await screen.findByRole("dialog", {
      name: "编辑分类规则 · Policy A",
    });
    const user = userEvent.setup();

    // The compact internal-rule list is the default state on the full page too.
    expect(screen.queryByLabelText("相对路径")).toBeNull();
    await user.click(screen.getByRole("button", { name: "编辑规则 1" }));
    const path = await screen.findByLabelText("相对路径");
    await user.clear(path);
    await user.type(path, "..");
    await user.click(screen.getByRole("button", { name: "完成" }));
    expect(screen.queryByLabelText("相对路径")).toBeNull();

    const mutatingBefore = calls.filter((call) => call.method !== "GET").length;
    await user.click(screen.getByRole("button", { name: "保存" }));

    // The page-level refusal names the closed rule, its retained error and the
    // correction route; nothing was sent to the server.
    expect(
      await screen.findByText(/保存未生效:有 1 处输入未通过校验/),
    ).toBeVisible();
    expect(screen.getByText("分类规则 1 · 相对路径")).toBeVisible();
    expect(screen.getByRole("button", { name: "修正规则 1" })).toBeVisible();
    expect(calls.filter((call) => call.method !== "GET").length).toBe(
      mutatingBefore,
    );

    // The correction route reopens the exact retained input.
    await user.click(screen.getByRole("button", { name: "修正规则 1" }));
    const reopened = await screen.findByLabelText("相对路径");
    expect(reopened).toHaveValue("..");
  });
});

describe("RulesEditPage object identity", () => {
  it("opens backend-legal IDs — plus, at, space and dot — on the same route", async () => {
    const requested: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        requested.push(url);
        if (url.endsWith("/auth/principal"))
          return new Response(
            JSON.stringify({ principal_id: "rules-principal-a" }),
          );
        if (url.endsWith("/form-authority"))
          return new Response(JSON.stringify(formAuthorityPayload));
        if (url.endsWith("/inventory"))
          return new Response(JSON.stringify(rulesPayload));
        if (url.includes("/objects/recognitionTypes/"))
          return new Response(
            JSON.stringify({
              ...editProjectionPayload,
              object: {
                ...editProjectionPayload.object,
                id: decodeURIComponent(
                  url.split("/objects/recognitionTypes/")[1],
                ),
              },
            }),
          );
        return new Response(JSON.stringify({ error: { code: "not_found" } }), {
          status: 404,
        });
      }),
    );
    authStore.setToken("rules-token");
    // Each route is the exact production deep-link shape: the ID arrives
    // percent-encoded exactly as a refresh/reconnect would deliver it.
    const cases: readonly [string, string][] = [
      ["/ui-v2/rules/edit/recognitionTypes/proof%2Btype", "proof+type"],
      ["/ui-v2/rules/edit/recognitionTypes/proof%40type", "proof@type"],
      ["/ui-v2/rules/edit/recognitionTypes/proof%20type", "proof type"],
      ["/ui-v2/rules/edit/recognitionTypes/proof.type", "proof.type"],
    ];
    for (const [route, expectedId] of cases) {
      cleanup();
      renderApp(route);
      const dialog = await screen.findByRole("dialog", {
        name: "编辑识别类型 · Special",
      });
      // The decoded backend identity is what the immutable ID field holds.
      expect(
        (within(dialog).getByLabelText(/^ID/) as HTMLInputElement).value,
      ).toBe(expectedId);
      // The editor for this exact identity was requested; the object was
      // never swapped for a different one and no write happened.
      expect(
        requested.some((url) =>
          url.includes(
            `/objects/recognitionTypes/${encodeURIComponent(expectedId)}`,
          ),
        ),
      ).toBe(true);
      expect(screen.getAllByRole("dialog")).toHaveLength(1);
    }
    // Opening the editor never runs analysis, previews or writes.
    expect(
      requested.every(
        (url) => !url.includes("/analysis/") && !url.includes("/previews/"),
      ),
    ).toBe(true);
  });

  it("keeps the safe-rejection state for identities outside the backend contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
    authStore.setToken("rules-token");
    for (const route of [
      "/ui-v2/rules/edit/recognitionTypes/proof%2Ftype",
      `/ui-v2/rules/edit/recognitionTypes/${"a".repeat(65)}`,
      "/ui-v2/rules/edit/notAFamily/proof.type",
    ]) {
      cleanup();
      renderApp(route);
      expect(await screen.findByText("无法打开该对象")).toBeVisible();
      // The rejection is read-only for the rejected identity: no object
      // projection read travels for an ID the backend could never publish.
      const objectReads = vi
        .mocked(fetch)
        .mock.calls.map((call) => String(call[0]))
        .filter((url) => url.includes("/operations/rules/objects/"));
      expect(objectReads).toHaveLength(0);
      vi.mocked(fetch).mockClear();
    }
  });
});

describe("RulesEditPage restored-draft pairing against a newer read", () => {
  // 乙 publishes a newer successor of the same object while 甲 keeps a draft
  // composed against the older read (B54-01). The stub lets the page see the
  // newer projection on the next open, exactly as a refresh would.
  const v2Active = {
    ...formAuthorityPayload.active,
    revisionId: "22222222-2222-4222-8222-222222222222",
    revisionSequence: 2,
    version: 2,
    digest: "2".repeat(64),
  };
  const v2Projection = {
    ...editProjectionPayload,
    object: {
      id: "C",
      name: "Special",
      description: "乙的新说明",
      enabled: true,
    },
    active: v2Active,
  };

  interface DraftHarness {
    readonly puts: Record<string, unknown>[];
    readonly state: {
      projection: unknown;
      authority: unknown;
    };
  }

  function stubDraftJourney(): DraftHarness {
    const harness: DraftHarness = {
      puts: [],
      state: {
        projection: editProjectionPayload,
        authority: formAuthorityPayload,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        const json = (payload: unknown, status = 200) =>
          new Response(JSON.stringify(payload), {
            status,
            headers: { "Content-Type": "application/json" },
          });
        if (url.endsWith("/auth/principal"))
          return json({ principal_id: "rules-principal-a" });
        if (method === "PUT") {
          harness.puts.push(
            JSON.parse(String(init?.body)) as Record<string, unknown>,
          );
          return json(saveSuccessPayload);
        }
        if (url.endsWith("/form-authority"))
          return json(harness.state.authority);
        if (url.endsWith("/inventory")) return json(rulesPayload);
        if (url.includes("/objects/recognitionTypes/C"))
          return json(harness.state.projection);
        return json({ error: { code: "not_found" } }, 404);
      }),
    );
    return harness;
  }

  /** 甲 opens object C, replaces the name and leaves without an explicit save. */
  async function leaveDraft(input: string): Promise<void> {
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    const dialog = await screen.findByRole("dialog", {
      name: "编辑识别类型 · Special",
    });
    const user = userEvent.setup();
    const name = within(dialog).getByLabelText(/^名称/) as HTMLInputElement;
    await user.clear(name);
    await user.type(name, input);
    expect(name.value).toBe(input);
    cleanup();
  }

  it("blocks the restored draft until adopting the current value keeps 乙's publication", async () => {
    const harness = stubDraftJourney();
    await leaveDraft("候选甲");

    // 乙 published a successor; 甲 refreshes and reconnects on the same route.
    harness.state.projection = v2Projection;
    harness.state.authority = { ...formAuthorityPayload, active: v2Active };
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    const dialog = await screen.findByRole("dialog", {
      name: "编辑识别类型 · Special",
    });
    // The restored input is visible pairing with its own older read, and the
    // decision is demanded before anything could be published.
    expect(within(dialog).getByLabelText(/^名称/)).toHaveValue("候选甲");
    const panel = await within(dialog).findByTestId("rules-verify-panel");
    expect(panel).toHaveTextContent("恢复的输入需要先核对当前值");
    expect(within(dialog).getByLabelText(/^描述/)).toHaveValue(
      "Special handling",
    );
    const save = within(dialog).getByRole("button", { name: "保存" });
    expect(save).toBeDisabled();
    expect(harness.puts).toHaveLength(0);

    // Adopting the current value keeps 乙's description under the v2 pairing.
    await userEvent.click(
      within(dialog).getByRole("button", { name: "采用当前值" }),
    );
    await waitFor(() =>
      expect(within(dialog).queryByTestId("rules-verify-panel")).toBeNull(),
    );
    expect(within(dialog).getByLabelText(/^名称/)).toHaveValue("Special");
    expect(within(dialog).getByLabelText(/^描述/)).toHaveValue("乙的新说明");
    await userEvent.click(within(dialog).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(harness.puts).toHaveLength(1));
    const body = harness.puts[0] as {
      expectedVersion: number;
      object: Record<string, unknown>;
    };
    expect(body.expectedVersion).toBe(2);
    expect(body.object.name).toBe("Special");
    expect(body.object.description).toBe("乙的新说明");
  });

  it("submits the kept input only after the explicit re-check pairs it with the newer read", async () => {
    const harness = stubDraftJourney();
    await leaveDraft("候选甲");

    harness.state.projection = v2Projection;
    harness.state.authority = { ...formAuthorityPayload, active: v2Active };
    authStore.setToken("rules-token");
    renderApp("/ui-v2/rules/edit/recognitionTypes/C");
    const dialog = await screen.findByRole("dialog", {
      name: "编辑识别类型 · Special",
    });
    await within(dialog).findByTestId("rules-verify-panel");
    const save = within(dialog).getByRole("button", { name: "保存" });
    expect(save).toBeDisabled();

    // Keeping the input re-pairs the baseline with the fresh Active read in
    // one visible step; only then may the same candidate be published.
    await userEvent.click(
      within(dialog).getByRole("button", { name: "保留输入,重新复核" }),
    );
    await waitFor(() =>
      expect(within(dialog).queryByTestId("rules-verify-panel")).toBeNull(),
    );
    expect(within(dialog).getByLabelText(/^名称/)).toHaveValue("候选甲");
    expect(within(dialog).getByRole("button", { name: "保存" })).toBeEnabled();
    await userEvent.click(within(dialog).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(harness.puts).toHaveLength(1));
    const body = harness.puts[0] as {
      expectedVersion: number;
      object: Record<string, unknown>;
    };
    expect(body.expectedVersion).toBe(2);
    expect(body.object.name).toBe("候选甲");
    // The kept candidate is submitted as it was kept — the decided pairing,
    // never a mix of the old input under a silently swapped baseline.
    expect(body.object.description).toBe("Special handling");
  });
});
