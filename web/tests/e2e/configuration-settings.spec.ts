import { expect, test, type Page } from "@playwright/test";

/**
 * Current Settings direct-publication journey against the built V2 artifact and
 * the isolated Node fake API. The page reads the exact Active values, applies a
 * group with its baseline identity, verifies a lost answer automatically by the
 * same request identity, and opens JSON only on demand.
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

async function openSettings(page: Page, extra = ""): Promise<void> {
  await resetSettings(page, "active", extra);
  await page.goto("/configuration");
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
      request.url().endsWith("/api/system/settings")
    ) {
      saves.push(request.postDataJSON() as Record<string, unknown>);
    }
  });
  return saves;
}

async function openLogging(page: Page): Promise<void> {
  await page.getByRole("button", { name: "日志", exact: true }).click();
}

test.describe("Settings direct publication", () => {
  test("typed groups read Active and JSON stays on demand", async ({
    page,
  }) => {
    await openSettings(page);
    await expect(page.getByLabel("配置状态摘要")).toBeVisible();
    await expect(page.getByText("配置已生效")).toBeVisible();
    await expect(page.getByText("序号 4", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "刷新" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "重新读取" })).toHaveCount(0);
    await expect(page.getByLabel("配置 JSON", { exact: true })).toHaveCount(0);

    await expect(page.getByLabel("系统语言")).toHaveValue("zh-CN");
    await openLogging(page);
    await expect(page.getByLabel("启用操作日志")).toHaveValue("false");
    await expect(page.getByLabel("日志保留天数")).toHaveValue("30");
    await expect(page.getByLabel("Database location")).toHaveCount(0);

    await page.getByRole("button", { name: "配置 JSON", exact: true }).click();
    await expect(page.getByLabel("配置 JSON", { exact: true })).toHaveValue(/zh-CN/);
    await page.getByRole("button", { name: "收起配置内容" }).click();
    await expect(page.getByLabel("配置 JSON", { exact: true })).toHaveCount(0);
  });

  test("one group apply sends the exact baseline and publishes once", async ({
    page,
  }) => {
    const saves = recordSaves(page);
    const retired: string[] = [];
    page.on("request", (request) => {
      if (/\/validate|\/activate|successor/.test(request.url())) {
        retired.push(request.url());
      }
    });
    await openSettings(page);
    await openLogging(page);
    await page.getByLabel("日志保留天数").fill("45");
    await page.getByRole("button", { name: "应用更改" }).click();
    await expect(page.getByText("更改已应用")).toBeVisible();
    await expect.poll(() => saves.length).toBe(1);
    expect(saves[0]).toMatchObject({
      expectedActiveRevisionId: "settings-active-1",
      expectedActiveVersion: 4,
      expectedActiveDigest: "settings-digest-1",
      edits: [{ fieldPath: "operationalLogging.retentionDays", value: 45 }],
    });
    expect(typeof saves[0]["submissionId"]).toBe("string");
    expect(retired).toEqual([]);
    await expect(page.getByText("序号 5", { exact: true })).toBeVisible();
    await expect(page.getByText("配置已生效")).toBeVisible();
    await expect(page.getByRole("button", { name: "刷新" })).toHaveCount(0);
  });

  test("a lost apply answer is verified automatically without a second publish", async ({
    page,
  }) => {
    const saves = recordSaves(page);
    await resetSettings(page, "active", "saveFail=unknown");
    await page.goto("/configuration");
    await connect(page);
    await openLogging(page);
    await page.getByLabel("日志保留天数").fill("46");
    await page.getByRole("button", { name: "应用更改" }).click();
    // The server committed before losing the answer. The page never replays
    // the publication and reads the new effective sequence back.
    await expect(page.getByText("序号 5", { exact: true })).toBeVisible();
    expect(saves).toHaveLength(1);
  });

  test("the narrow viewport stays readable without horizontal overflow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openSettings(page);
    await openLogging(page);
    await expect(page.getByRole("button", { name: "应用更改" })).toBeVisible();
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
