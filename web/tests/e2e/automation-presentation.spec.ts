import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

const prestartRecords = JSON.parse(
  readFileSync(
    new URL("../fixtures/automation-records-prestart.json", import.meta.url),
    "utf8",
  ),
);

// Built assets and isolated API fixtures only; no production media or settings.
for (const width of [1536, 390]) {
  test(`automation presentation stays readable at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: width === 1536 ? 1024 : 844 });
    await page.request.post("/__test__/reset-automation");
    await page.route(
      "**/api/v1/operations/automation/records?*",
      async (route) => {
        await route.fulfill({ json: prestartRecords });
      },
    );
    await page.goto("/ui-v2/operations/automation");
    await page.getByLabel("API token").fill("e2e-viewer-token");
    await page.getByRole("button", { name: "Connect" }).click();
    const main = page.getByRole("main");
    const title = main.getByRole("heading", { name: "自动化", exact: true });
    await expect(title).toBeVisible();
    await expect(main.getByText("自动化", { exact: true })).toHaveCount(1);
    await expect(
      main.getByText(/统计范围：|统计时区：|skipped files/),
    ).toHaveCount(0);
    const titleStyle = await title.evaluate((el) => {
      const style = getComputedStyle(el);
      return {
        size: style.fontSize,
        weight: style.fontWeight,
        top: el.getBoundingClientRect().top,
      };
    });
    expect(titleStyle.size).toBe("30px");
    expect(titleStyle.weight).toBe("700");
    const search = main.getByRole("searchbox", { name: "搜索", exact: true });
    await expect(search).toBeVisible();
    expect(
      await search.evaluate((el) => el.getBoundingClientRect().height),
    ).toBeGreaterThanOrEqual(34);
    await search.focus();
    expect(
      await search.evaluate((el) => getComputedStyle(el).outlineStyle),
    ).toBe("solid");
    await title.click();
    await expect(page).toHaveURL(/tab=definitions/);
    const assertNoOverflow = async () => {
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
      ).toBe(true);
    };
    await assertNoOverflow();
    if (width === 1536) {
      expect(
        (await main
          .getByRole("table", { name: "自动化任务", exact: true })
          .boundingBox())!.y,
      ).toBeLessThan(450);
    }
    await page.screenshot({
      fullPage: true,
      path: testInfo.outputPath("definitions.png"),
    });

    await page.getByRole("button", { name: "执行记录", exact: true }).click();
    const records = page.getByRole("table", {
      name: "自动化执行记录",
      exact: true,
    });
    await expect(records).toBeVisible();
    const failed = records.getByRole("row").filter({ hasText: "missing" });
    const details = failed.getByRole("button", { name: "查看详情" });
    await expect(details).toHaveAttribute("aria-expanded", "false");
    expect((await failed.boundingBox())!.height).toBeLessThan(110);
    await assertNoOverflow();
    await page.screenshot({
      fullPage: true,
      path: testInfo.outputPath("records.png"),
    });
    const writes: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/") && request.method() !== "GET")
        writes.push(request.method());
    });
    const detailId = await details.getAttribute("aria-controls");
    await details.click();
    const evidence = page.locator(`[id="${detailId}"]`);
    await expect(evidence.getByText(/原因：scope_root_missing/)).toBeVisible();
    await expect(
      evidence.getByText(/没有创建正式整理任务，也没有产生媒体效果/),
    ).toBeVisible();
    await expect(evidence.getByText("2026-01-01T12:00:00+00:00")).toHaveCount(
      2,
    );
    await page.getByRole("button", { name: "收起详情" }).click();
    await expect(evidence).toBeHidden();
    expect(writes).toEqual([]);

    await page.getByRole("button", { name: "全局设置", exact: true }).click();
    const settings = page.getByRole("region", { name: "自动化引擎设置" });
    await expect(settings.getByLabel(/Worker 轮询间隔/)).toBeVisible();
    await expect(
      settings.getByRole("button", { name: "保存设置" }),
    ).toBeDisabled();
    await expect(
      main.getByText(/关于自动化引擎|调度与时区说明|配置示例/),
    ).toHaveCount(0);
    await expect(main.getByRole("region", { name: "自动化统计" })).toHaveCount(
      0,
    );
    await assertNoOverflow();
    await page.screenshot({
      fullPage: true,
      path: testInfo.outputPath("settings.png"),
    });
    expect(writes).toEqual([]);
  });
}
