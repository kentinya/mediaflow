import { expect, test, type Page } from "@playwright/test";

/**
 * Rules readiness and Settings handoff browser proof for Slice 41, Task 41.5.
 *
 * Runs against the built V2 artifact plus the local fake API only. Every token
 * below is a throwaway non-secret value; no production service, credential,
 * user media or Storage is involved. The fake serves the rules documents from
 * `web/tests/fixtures/rules-readiness.json`, which the Python test
 * `tests/test_v2_settings_rule_readiness.py` captures from the real API, so this
 * journey cannot drift from the backend contract.
 *
 * Covered journey:
 * - A family deep link opens the complete inventory with no editor, survives a
 *   real browser refresh, and Back/Forward keep the section.
 * - Overview readiness gaps lead to the affected family inventory.
 * - The section input is allowlisted: malformed, path-like and credential-like
 *   values fall back to the read-only Overview and are never echoed.
 * - Settings shows the readiness derived from the same Active authority, links
 *   each gap to its family, and keeps no-Active distinct from an empty graph.
 * - Settings offers an explicit safe return to the originating family and never
 *   auto-navigates.
 * - A publication between two Settings reads is observed on refresh instead of
 *   being presented as the previous, stale readiness.
 * - No surface writes: the fake records every mutation and only GET reads occur.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
// A principal that may read every surface but holds no management permission.
const READ_ONLY_TOKEN = "e2e-readonly-token";

async function connectAs(page: Page, token = VIEWER_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

/** Reset the per-session rules fixture used by the fake API. */
async function resetRules(page: Page, query = ""): Promise<void> {
  await page.request.post(`/__test__/reset-rules${query}`);
}

async function openRules(
  page: Page,
  search = "",
  token = VIEWER_TOKEN,
): Promise<void> {
  await page.goto(`/ui-v2/rules${search}`);
  await connectAs(page, token);
  await expect(
    page.getByRole("heading", { name: "整理规则", exact: true }),
  ).toBeVisible();
}

async function openSettings(page: Page, search = ""): Promise<void> {
  await page.goto(`/ui-v2/configuration${search}`);
  await connectAs(page, VIEWER_TOKEN);
  await expect(
    page.getByRole("heading", { name: "配置生命周期" }),
  ).toBeVisible();
}

/**
 * Record this page's own API traffic. The fake server keeps one shared evidence
 * log across parallel workers, so a per-page listener is the only assertion that
 * cannot observe another test's writes.
 */
function recordApiTraffic(page: Page): string[] {
  const traffic: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      traffic.push(`${request.method()} ${request.url()}`);
    }
  });
  return traffic;
}

test.describe("Rules readiness and Settings handoff", () => {
  test("a family deep link survives refresh and keeps Back/Forward history", async ({
    page,
  }) => {
    await resetRules(page);
    await openRules(page, "?section=recognitionTypes");

    // The deep link opens the complete full-width inventory: every Active
    // object of the family, no selected object and no editor.
    await expect(
      page.getByRole("heading", { name: "识别类型", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("row", { name: /Normal Movie/ })).toBeVisible();
    await expect(page.getByRole("row", { name: /TV/ })).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    // The create action is the only way into the drawer; the deep link itself
    // never opened a form or selected an object.
    await expect(
      page.getByRole("button", { name: "添加识别类型" }),
    ).toBeVisible();

    // A real browser refresh restores the same section, not the Overview.
    await page.reload();
    await connectAs(page);
    await expect(
      page.getByRole("heading", { name: "识别类型", exact: true }),
    ).toBeVisible();
    expect(page.url()).toContain("section=recognitionTypes");

    // Navigating to the Overview and back is real history, and the section tab
    // is a link-level control that never opens the editor.
    await page.getByRole("button", { name: "概览" }).click();
    await expect(
      page.getByRole("heading", { name: "规则关系概览" }),
    ).toBeVisible();
    await page.goBack();
    await expect(
      page.getByRole("heading", { name: "识别类型", exact: true }),
    ).toBeVisible();
    await page.goForward();
    await expect(
      page.getByRole("heading", { name: "规则关系概览" }),
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("a readiness gap leads to the affected family and malformed input stays safe", async ({
    page,
  }) => {
    await resetRules(page, "?gaps=typeBindings");
    await openRules(page);

    // The backend-named gap is actionable: it opens that exact family.
    await expect(page.getByRole("heading", { name: "配置缺口" })).toBeVisible();
    const gapAction = page.getByRole("link", {
      name: "查看类型绑定",
      exact: true,
    });
    await expect(gapAction).toBeVisible();
    await gapAction.click();
    await expect(
      page.getByRole("heading", { name: "类型绑定", exact: true }),
    ).toBeVisible();
    expect(page.url()).toContain("section=typeBindings");
    await expect(page.getByRole("dialog")).toHaveCount(0);

    // Malformed, path-like and credential-like section values are refused: the
    // workspace falls back to the read-only Overview. The bearer token stays
    // memory-only, so a fresh entry re-connects each time — which is also where
    // the allowlist must prove it never replays the hostile value.
    for (const hostile of [
      "not-a-family",
      "../../storage",
      "Bearer%20abc",
      "sha256%3Aabcdef",
    ]) {
      await page.goto(`/ui-v2/rules?section=${hostile}`);
      await connectAs(page);
      await expect(
        page.getByRole("heading", { name: "规则关系概览" }),
      ).toBeVisible();
      expect(page.url()).not.toContain("Bearer");
      expect(page.url()).not.toContain("sha256");
      expect(page.url()).not.toContain("not-a-family");
      expect(page.url()).not.toContain("..");
      await expect(page.getByRole("dialog")).toHaveCount(0);
    }
  });

  test("an empty Active offers the dependency path without inventing objects", async ({
    page,
  }) => {
    await resetRules(page, "?empty=1");
    await openRules(page);
    await expect(
      page.getByRole("heading", { name: "按依赖顺序补齐" }),
    ).toBeVisible();
    // The first dependency has no prerequisite and is offered first.
    const first = page
      .getByRole("heading", { name: "按依赖顺序补齐" })
      .locator("xpath=following-sibling::ol[1]/li[1]");
    await expect(first.getByRole("link", { name: "识别类型" })).toBeVisible();
    await expect(page.getByText(/系统不会生成默认对象/)).toBeVisible();
    // Every family is empty: no row is presented as an Active object.
    await expect(page.getByRole("row", { name: /Normal Movie/ })).toHaveCount(
      0,
    );
  });

  test("Settings shows the same Active readiness and links each family", async ({
    page,
  }) => {
    await resetRules(page, "?gaps=recognitionRules");
    await openSettings(page);

    await expect(
      page.getByRole("heading", { name: "整理规则就绪状态" }),
    ).toBeVisible();
    await expect(page.getByText("部分规则族尚未就绪")).toBeVisible();
    // The exact Active the readiness describes is named.
    await expect(page.getByText("对应 Active 序号")).toBeVisible();

    // The gap and each family inventory are reachable from Settings.
    const gapLink = page
      .getByRole("region", { name: "整理规则就绪状态" })
      .getByRole("link", { name: "查看识别规则" })
      .first();
    await expect(gapLink).toHaveAttribute(
      "href",
      "/ui-v2/rules?section=recognitionRules",
    );
    await expect(
      page.getByRole("link", { name: "查看识别类型" }),
    ).toHaveAttribute("href", "/ui-v2/rules?section=recognitionTypes");
    await gapLink.click();
    await expect(
      page.getByRole("heading", { name: "识别规则", exact: true }),
    ).toBeVisible();
  });

  test("a no-Active configuration never renders readiness as an empty graph", async ({
    page,
  }) => {
    await resetRules(page, "?noActive=1");
    await openSettings(page);
    await expect(
      page.getByRole("heading", { name: "整理规则就绪状态" }),
    ).toBeVisible();
    await expect(page.getByText("尚无 Active 配置").first()).toBeVisible();
    // A missing Active is not an inventory: no family is offered as if it were
    // the current readiness, and the handoff to the workspace still exists.
    await expect(page.getByRole("link", { name: "查看识别类型" })).toHaveCount(
      0,
    );
    await expect(
      page.getByRole("link", { name: "打开整理规则工作区" }),
    ).toBeVisible();
  });

  test("Settings returns to the originating family only on explicit intent", async ({
    page,
  }) => {
    await resetRules(page);
    await openRules(page, "?section=classificationPolicies");
    await page.getByRole("link", { name: "前往系统设置" }).click();

    // Settings stays on Settings: the return is offered, never automatic.
    await expect(
      page.getByRole("heading", { name: "配置生命周期" }),
    ).toBeVisible();
    expect(page.url()).toContain("returnTo=rules");
    expect(page.url()).toContain("returnSection=classificationPolicies");
    // No raw revision, digest or token travels in the navigation state.
    expect(page.url()).not.toContain("bearer");
    expect(page.url()).not.toContain("digest");

    // The explicit return lands on the exact originating family inventory.
    await page.getByRole("link", { name: "返回整理规则 · 分类策略" }).click();
    await expect(
      page.getByRole("heading", { name: "分类策略", exact: true }),
    ).toBeVisible();
    expect(page.url()).toContain("section=classificationPolicies");
  });

  test("a no-Active family deep link keeps its family through setup and return", async ({
    page,
  }) => {
    // The B-review blocker journey: a family deep link on a no-Active
    // instance must keep its originating family through the Settings handoff,
    // through the first-activation publication, and back to the exact family
    // inventory.
    await resetRules(page, "?noActive=1");
    const traffic = recordApiTraffic(page);
    await page.goto("/ui-v2/rules?section=metadataPolicies");
    await connectAs(page);

    // The no-Active state renders on the deep-linked family, and the Settings
    // handoff carries the originating family — no Overview fallback.
    await expect(
      page.getByRole("heading", { name: "尚无 Active 配置" }),
    ).toBeVisible();
    const settingsLink = page.getByRole("link", {
      name: "前往系统设置查看配置状态",
    });
    await expect(settingsLink).toHaveAttribute(
      "href",
      "/ui-v2/configuration?returnTo=rules&returnSection=metadataPolicies",
    );
    await expect(page.getByRole("dialog")).toHaveCount(0);

    // The handoff reaches Settings and the explicit return carries the family.
    await settingsLink.click();
    await expect(
      page.getByRole("heading", { name: "配置生命周期" }),
    ).toBeVisible();
    expect(page.url()).toContain("returnSection=metadataPolicies");
    const returnLink = page.getByRole("link", {
      name: "返回整理规则 · 元数据策略",
    });
    await expect(returnLink).toHaveAttribute(
      "href",
      "/ui-v2/rules?section=metadataPolicies",
    );

    // First setup through the real lifecycle: create, validate, activate.
    await page.getByRole("button", { name: "创建首个 Draft" }).click();
    await expect(
      page.getByRole("button", { name: "恢复 Draft" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "恢复 Draft" }).click();
    await page.getByRole("button", { name: "验证 Draft" }).click();
    await expect
      .poll(() =>
        page.getByRole("button", { name: "checked-activate" }).isEnabled(),
      )
      .toBe(true);
    await page.getByRole("button", { name: "checked-activate" }).click();

    // The automatic return lands on the originating family inventory, now
    // backed by the published Active.
    await expect(
      page.getByRole("heading", { name: "元数据策略", exact: true }),
    ).toBeVisible();
    expect(page.url()).toContain("section=metadataPolicies");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    // The only writes in the whole journey are the explicit first-setup
    // lifecycle commands the operator pressed on Settings; the rules surface
    // itself (deep link, handoff, return) issued reads exclusively, and no
    // Provider, Storage, Task, Job or rule-object mutation occurred.
    const writes = traffic
      .filter((entry) => !entry.startsWith("GET "))
      .map((entry) => new URL(entry.split(" ")[1]!).pathname);
    expect(writes).toEqual([
      "/api/v1/configuration/drafts/first",
      "/api/v1/configuration/revisions/rules-setup-draft-e2e/validate",
      "/api/v1/configuration/revisions/rules-setup-draft-e2e/activate",
    ]);
  });

  test("a publication between two Settings reads is observed instead of shown stale", async ({
    page,
  }) => {
    await resetRules(page);
    await openSettings(page);
    const settings = page.getByRole("region", { name: "整理规则就绪状态" });
    const firstSequence = await settings.locator("dd").nth(1).textContent();

    // A competing writer publishes a successor Active, then the operator
    // refreshes: the page must re-read and show the new readiness.
    await page.request.post("/__test__/advance-rules-active");
    await page
      .getByRole("button", { name: /刷新|Refresh/ })
      .first()
      .click();
    await expect
      .poll(async () => settings.locator("dd").nth(1).textContent())
      .not.toBe(firstSequence);
    // The refreshed readiness is not reported as a mixed snapshot.
    await expect(page.getByText("Active 已变更,需要刷新")).toHaveCount(0);
  });

  test("the readiness journey performs no write on any surface", async ({
    page,
  }) => {
    await resetRules(page, "?gaps=typeBindings");
    const traffic = recordApiTraffic(page);
    await openRules(page, "?section=recognitionTypes");
    await page.getByRole("button", { name: "概览" }).click();
    await page.getByRole("link", { name: "查看类型绑定", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "类型绑定", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "刷新 Active" }).click();
    await openSettings(page);
    await page.getByRole("link", { name: "查看识别类型" }).click();
    await expect(
      page.getByRole("heading", { name: "识别类型", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    // The whole cross-surface journey issued reads only: no request carried a
    // mutating method, so no Draft, work or Active was created.
    expect(traffic.length).toBeGreaterThan(0);
    expect(traffic.filter((entry) => !entry.startsWith("GET "))).toEqual([]);
  });

  test("a read-only principal keeps the full inventory with no write control", async ({
    page,
  }) => {
    await resetRules(page);
    const traffic = recordApiTraffic(page);
    await openRules(page, "?section=recognitionTypes", READ_ONLY_TOKEN);
    // The read-only principal sees the complete Active inventory...
    await expect(page.getByRole("row", { name: /Normal Movie/ })).toBeVisible();
    // ...but no create, edit or lifecycle control, and the journey still wrote
    // nothing.
    await expect(page.getByRole("button", { name: /^添加/ })).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "编辑", exact: true }),
    ).toHaveCount(0);
    expect(traffic.filter((entry) => !entry.startsWith("GET "))).toEqual([]);
  });
});
