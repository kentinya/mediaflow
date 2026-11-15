import { expect, test, type Page } from "@playwright/test";

/**
 * PATCH-20261115-1 Settings hierarchy, typed advanced fields and the two
 * publication semantics, against the built V2 artifact and the isolated Node
 * fake API. Every token is a throwaway non-secret value; no production service,
 * user media or real configuration is involved.
 *
 * The fake implements the real public shapes (revisionId+expectedVersion Draft
 * edits, expectedActive* successors, status-only validation and checked
 * activation), so the browser cannot fake adoption or a successful publication.
 */

const TOKEN = "e2e-viewer-token";

async function connect(page: Page): Promise<void> {
  await page.getByLabel("API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
}

async function resetSettings(
  page: Page,
  mode = "active",
  extra = "",
): Promise<void> {
  const query = `mode=${mode}${extra === "" ? "" : `&${extra}`}`;
  await page.request.post(`/__test__/reset-settings?${query}`);
}

async function openSettings(
  page: Page,
  options: {
    readonly mode?: string;
    readonly search?: string;
    readonly extra?: string;
  } = {},
): Promise<void> {
  await resetSettings(page, options.mode ?? "active", options.extra ?? "");
  await page.goto(`/ui-v2/configuration${options.search ?? ""}`);
  await connect(page);
  await expect(
    page.getByRole("heading", { name: "系统设置", exact: true }),
  ).toBeVisible();
}

function recordSaves(page: Page): Array<Record<string, unknown>> {
  const saves: Array<Record<string, unknown>> = [];
  page.on("request", (request) => {
    if (
      request.method() === "PUT" &&
      request.url().endsWith("/api/v1/system/settings")
    ) {
      saves.push(request.postDataJSON() as Record<string, unknown>);
    }
  });
  return saves;
}

async function openGroup(page: Page, name: string): Promise<void> {
  await page.getByRole("button", { name, exact: true }).click();
}

test.describe("Settings hierarchy and typed settings", () => {
  test("one settings title, a compact status and typed groups lead to the runtime fields", async ({
    page,
  }) => {
    await openSettings(page);
    const h1 = page.locator("h1");
    await expect(h1).toHaveCount(1);
    await expect(h1).toHaveText("系统设置");
    await expect(page.getByText("配置生命周期")).toHaveCount(0);
    // The shell no longer contributes a duplicate location line or an unusable
    // read-only file search to this surface.
    await expect(page.locator(".mf-page-context")).toHaveCount(0);
    await expect(page.getByRole("searchbox")).toHaveCount(0);

    await expect(page.getByLabel("配置状态摘要")).toBeVisible();
    await expect(page.getByText("配置已生效")).toBeVisible();
    await expect(page.getByText("序号 4", { exact: true })).toBeVisible();
    // The exact Active JSON is already loaded; the operator does not have to
    // open it before finding the editable fields.
    const activeJson = page.getByLabel("配置 JSON");
    await expect(activeJson).toHaveValue(/zh-CN/);
    await expect(page.getByText(/来源：生效配置/)).toBeVisible();

    const summaryBox = await page.getByLabel("配置状态摘要").boundingBox();
    const engineBox = await page
      .getByRole("region", { name: "系统运行设置" })
      .boundingBox();
    const advancedBox = await page
      .getByRole("heading", { name: "高级配置" })
      .boundingBox();
    expect(summaryBox).not.toBeNull();
    expect(engineBox).not.toBeNull();
    expect(advancedBox).not.toBeNull();
    expect(summaryBox!.y).toBeLessThan(engineBox!.y);
    expect(engineBox!.y).toBeLessThan(advancedBox!.y);

    // The typed groups render without opening JSON, with Chinese labels,
    // units and per-field publish boundaries.
    await expect(page.getByLabel("系统语言")).toHaveValue("zh-CN");
    await expect(page.getByText("需重启后生效").first()).toBeVisible();
    await openGroup(page, "日志");
    await expect(page.getByLabel("启用操作日志")).toHaveValue("false");
    await expect(page.getByText("当前：关闭")).toBeVisible();
    await expect(page.getByLabel("最低日志级别")).toHaveValue("INFO");
    await expect(page.getByLabel("日志保留天数")).toHaveValue("30");
    // The bootstrap-owned deployment locator is never offered for editing.
    await expect(page.getByLabel("Database location")).toHaveCount(0);
    // Runtime adoption remains a separate truth, collapsed in diagnostics.
    await expect(page.getByText("诊断", { exact: true })).toBeVisible();
  });

  test("a group Save submits only its changed fields, then validates and activates the exact version", async ({
    page,
  }) => {
    const saves = recordSaves(page);
    await openSettings(page);
    await openGroup(page, "日志");
    const retention = page.getByLabel("日志保留天数");
    await retention.fill("45");
    await page.getByRole("button", { name: "保存到草稿" }).click();
    await expect(page.getByText("已保存到草稿")).toBeVisible();
    await expect(page.getByText(/草稿尚未生效/)).toBeVisible();
    await expect.poll(() => saves.length).toBe(1);
    expect(saves[0]).toMatchObject({
      expectedActiveRevisionId: "settings-active-1",
      expectedActiveVersion: 4,
      expectedActiveDigest: "settings-digest-1",
      edits: [
        {
          fieldPath: "operationalLogging.retentionDays",
          value: 45,
        },
      ],
    });
    await expect(
      page.getByRole("option", { name: /草稿（编辑版本 1）/ }),
    ).toHaveCount(1);
    await expect(page.getByText("尚未验证；修改后需重新验证")).toBeVisible();

    const validateRequests: string[] = [];
    const activations: Array<Record<string, unknown>> = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().includes("/validate")) {
        validateRequests.push(new URL(request.url()).pathname);
      }
      if (request.method() === "POST" && request.url().endsWith("/activate")) {
        activations.push(request.postDataJSON() as Record<string, unknown>);
      }
    });
    await page.getByRole("button", { name: "验证草稿" }).click();
    await expect(page.getByText("草稿验证通过")).toBeVisible();
    await expect(page.getByText(/验证有效（版本 1）/)).toBeVisible();
    await expect
      .poll(() => page.getByRole("button", { name: "激活配置" }).isEnabled())
      .toBe(true);
    expect(validateRequests).toEqual([
      "/api/v1/configuration/revisions/settings-draft-from-active-1/validate",
    ]);

    await page.getByRole("button", { name: "激活配置" }).click();
    await expect(page.getByText("配置已激活")).toBeVisible();
    // Activation stays on the checked boundary for the exact validated
    // revision; an unchecked compatibility request is not accepted.
    expect(activations).toEqual([{ expectedVersion: 1, checked: true }]);
    await expect(page.getByText("配置已生效")).toBeVisible();
    await expect(
      page.getByRole("option", { name: /生效配置（序号 5）/ }),
    ).toHaveCount(1);
    await expect(page.getByRole("button", { name: "激活配置" })).toHaveCount(0);
    // The activated snapshot is read back as Active, not as a second Draft.
    await expect(page.getByLabel("配置 JSON")).toHaveValue(/zh-CN/);
    expect(saves).toHaveLength(1);
  });

  test("discarding one group keeps another group's unsaved input", async ({
    page,
  }) => {
    const saves = recordSaves(page);
    await openSettings(page);
    const timezone = page.getByLabel("系统时区");
    await timezone.fill("Europe/Berlin");
    await openGroup(page, "日志");
    const retention = page.getByLabel("日志保留天数");
    await retention.fill("45");
    await page.getByRole("button", { name: "放弃本组修改" }).click();
    await expect(retention).toHaveValue("30");
    await openGroup(page, "语言与时区");
    await expect(page.getByLabel("系统时区")).toHaveValue("Europe/Berlin");
    await expect(page.getByText(/本组有未保存修改/)).toBeVisible();
    await page.getByRole("button", { name: "保存到草稿" }).click();
    await expect(page.getByText("已保存到草稿")).toBeVisible();
    await expect.poll(() => saves.length).toBe(1);
    expect(saves[0]).toMatchObject({
      expectedActiveRevisionId: "settings-active-1",
      edits: [{ fieldPath: "timezone", value: "Europe/Berlin" }],
    });
  });

  test("boolean states and strict numeric input never send a rewritten value", async ({
    page,
  }) => {
    const saves = recordSaves(page);
    await openSettings(page);
    await openGroup(page, "日志");
    await page.getByLabel("启用操作日志").selectOption("true");
    const retention = page.getByLabel("日志保留天数");
    await retention.fill("12x");
    await page.getByRole("button", { name: "保存到草稿" }).click();
    await expect(page.getByText(/不能包含空格或尾随字符/)).toBeVisible();
    await expect(page.getByText("输入未提交")).toBeVisible();
    expect(saves).toHaveLength(0);
    await expect(retention).toHaveValue("12x");

    // An empty/whitespace value and a trailing character are equally refused;
    // the input is not parsed into a prefix number and sent.
    await retention.fill(" 15");
    await page.getByRole("button", { name: "保存到草稿" }).click();
    expect(saves).toHaveLength(0);

    await retention.fill("15");
    await page.getByRole("button", { name: "保存到草稿" }).click();
    await expect.poll(() => saves.length).toBe(1);
    expect(saves[0].edits).toEqual([
      { fieldPath: "operationalLogging.enabled", value: true },
      { fieldPath: "operationalLogging.retentionDays", value: 15 },
    ]);
    await expect(page.getByText("当前：开启")).toBeVisible();

    // The unconfigured tri-state stays distinguishable on the next group.
    await openGroup(page, "重试");
    const retryEnabled = page.getByLabel("启用工作流重试");
    await expect(retryEnabled).toHaveValue("unset");
    await expect(page.getByText("当前：未配置")).toBeVisible();
    await retryEnabled.selectOption("true");
    await page.getByRole("button", { name: "保存到草稿" }).click();
    await expect.poll(() => saves.length).toBe(2);
    expect(saves[1]).toMatchObject({
      revisionId: "settings-draft-from-active-1",
      expectedVersion: 1,
      edits: [{ fieldPath: "workflowRetry.enabled", value: true }],
    });
  });

  test("an existing Draft is not selected implicitly when an Active exists", async ({
    page,
  }) => {
    const draftReads: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/revisions/settings-draft-1")) {
        draftReads.push(request.url());
      }
    });
    await openSettings(page, { mode: "activeDraft" });
    await expect(page.getByLabel("配置 JSON")).toHaveValue(/zh-CN/);
    await expect(page.getByText(/来源：生效配置/)).toBeVisible();
    await expect(
      page.getByRole("option", { name: /草稿（编辑版本 1）/ }),
    ).toHaveCount(1);
    expect(draftReads).toHaveLength(0);
  });

  test("no-Active recovery is explicit and reads never create a Draft", async ({
    page,
  }) => {
    const writes: string[] = [];
    page.on("request", (request) => {
      if (request.method() !== "GET") {
        writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
      }
    });
    await openSettings(page, { mode: "draftOnly" });
    await expect(page.getByText("已有草稿待恢复")).toBeVisible();
    await expect(page.getByLabel("配置 JSON")).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "选择要恢复的草稿" }),
    ).toBeVisible();
    expect(writes).toHaveLength(0);
    await page.getByRole("button", { name: /恢复草稿/ }).click();
    await expect(page.getByLabel("配置 JSON")).toHaveValue(/zh-CN/);
    await expect(page.getByText("草稿", { exact: true }).first()).toBeVisible();
    expect(writes).toHaveLength(0);
  });

  test("a corrupt Active is explicit recovery, not a Draft substitute", async ({
    page,
  }) => {
    const draftReads: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/revisions/settings-draft-1")) {
        draftReads.push(request.url());
      }
    });
    await openSettings(page, { mode: "corrupt" });
    await expect(page.getByText("生效配置不可用，需要恢复")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "生效配置需要恢复" }),
    ).toBeVisible();
    await expect(page.getByText("等待恢复生效配置")).toBeVisible();
    await expect(page.getByLabel("配置 JSON")).toHaveCount(0);
    expect(draftReads).toHaveLength(0);
  });

  test("a read failure keeps no stale object on screen and disables publication", async ({
    page,
  }) => {
    await openSettings(page, { extra: "failRead=1" });
    await expect(
      page.getByText(/配置服务暂不可用，未读取到当前内容/),
    ).toBeVisible();
    await expect(page.getByLabel("配置 JSON")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "验证草稿" })).toHaveCount(0);
    // No write is offered while the exact read failed.
    await expect(page.getByText(/没有使用旧内容替代/)).toBeVisible();
  });

  test("a lost Save answer is verified read-only and is never replayed", async ({
    page,
  }) => {
    const saves = recordSaves(page);
    await openSettings(page, { extra: "saveFail=unknown" });
    await openGroup(page, "日志");
    await page.getByLabel("日志保留天数").fill("45");
    await page.getByRole("button", { name: "保存到草稿" }).click();
    await expect(page.getByText("操作结果未知")).toBeVisible();
    await expect(page.getByText("操作结果待核实")).toBeVisible();
    expect(saves).toHaveLength(1);
    await page.getByRole("button", { name: "核实当前状态" }).click();
    await expect(page.getByText("已核实当前配置状态")).toBeVisible();
    // The write really happened; the verified read shows the new Draft and the
    // page did not re-send the uncertain request.
    await expect(
      page.getByRole("option", { name: /草稿（编辑版本 1）/ }),
    ).toHaveCount(1);
    expect(saves).toHaveLength(1);
  });

  test("exported content is labelled and never replaces the exact revision JSON", async ({
    page,
  }) => {
    await openSettings(page);
    const activeJson = page.getByLabel("配置 JSON");
    await expect(activeJson).toHaveValue(/zh-CN/);
    await page.getByRole("button", { name: "导出脱敏配置包" }).click();
    const packageJson = page.getByLabel("脱敏配置包");
    await expect(packageJson).toHaveValue(/mediaflow.configuration.v1/);
    await expect(page.getByText(/内容：脱敏配置包/)).toBeVisible();
    await page.getByRole("button", { name: "配置 JSON" }).click();
    await expect(page.getByLabel("配置 JSON")).toHaveValue(/zh-CN/);
    await expect(page.getByLabel("配置 JSON")).not.toHaveValue(
      /mediaflow.configuration.v1/,
    );
  });

  test("the narrow viewport stays readable without horizontal overflow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openSettings(page);
    await openGroup(page, "日志");
    await expect(page.getByLabel("日志保留天数")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "保存到草稿" }),
    ).toBeVisible();
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    await page.getByText("诊断", { exact: true }).click();
    const afterDiagnostics = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(afterDiagnostics).toBeLessThanOrEqual(1);
  });
});
