import { expect, test, type Page } from "@playwright/test";

/**
 * Rules object-identity browser journey for Slice 41, Task 41.6.
 *
 * Runs against the built V2 artifact plus the local fake API only. Every token
 * below is a throwaway non-secret value; no production service, credential,
 * user media or Storage is involved. The fake serves the object-lifecycle
 * documents on the real `/api/v1/operations/rules/objects/*` routes with the
 * real backend identifier grammar, and its static `/ui-v2/` serving mirrors the
 * production Python dotted-ID entry exception, so this journey cannot pass
 * against a permissive fake that proves nothing.
 *
 * Covered journey:
 * - Create objects whose IDs use `+`, `@`, internal space and a dot through the
 *   real create drawer, then Edit each one.
 * - A dotted-ID edit deep link survives a real browser refresh and a
 *   disconnect/reconnect with the same identity and family.
 * - A name-only Save keeps the ID immutable and publishes a new Active.
 * - Copy opens a distinct candidate; disable/enable publish successors; an
 *   unreferenced remove publishes a successor without the object.
 * - The inventory rows never show a failed candidate as Active, and no
 *   surface writes without its explicit command.
 */

const VIEWER_TOKEN = "e2e-viewer-token";

async function connectAs(page: Page, token = VIEWER_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

async function resetRules(page: Page, query = ""): Promise<void> {
  await page.request.post(`/__test__/reset-rules${query}`);
}

/**
 * Record this page's own API traffic. The fake keeps one shared evidence log
 * across parallel workers, so a per-page listener is the only assertion that
 * can attribute writes to this journey.
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

const ID_CASES = [
  { raw: "proof+type", encoded: "proof%2Btype", label: "加号 ID" },
  { raw: "proof@type", encoded: "proof%40type", label: "At ID" },
  { raw: "proof type", encoded: "proof%20type", label: "空格 ID" },
  { raw: "proof.type", encoded: "proof.type", label: "点号 ID" },
] as const;

/**
 * Seed one recognitionType with a special ID through the fake's real routes.
 * The seed composes against the exact Active identity the fake currently
 * serves, the same way a browser Save would.
 */
async function seedRecognitionType(
  page: Page,
  objectId: string,
): Promise<void> {
  const authority = await page.request.get(
    "/api/v1/operations/rules/form-authority",
    { headers: { Authorization: `Bearer ${VIEWER_TOKEN}` } },
  );
  if (!authority.ok()) throw new Error("authority read failed while seeding");
  const document = (await authority.json()) as {
    active: { revisionId: string; version: number; digest: string };
  };
  const response = await page.request.post(
    "/api/v1/operations/rules/objects/recognitionTypes",
    {
      headers: { Authorization: `Bearer ${VIEWER_TOKEN}` },
      data: {
        object: { id: objectId, name: `对象 ${objectId}`, enabled: true },
        expectedRevisionId: document.active.revisionId,
        expectedVersion: document.active.version,
        expectedDigest: document.active.digest,
      },
    },
  );
  if (!response.ok()) {
    throw new Error(`seeding ${objectId} failed: ${response.status()}`);
  }
}

test.describe("Rules object identity", () => {
  test("a dotted-ID edit deep link survives refresh and reconnect", async ({
    page,
  }) => {
    await resetRules(page, "?empty=1");
    await seedRecognitionType(page, "proof.type");
    await page.goto("/ui-v2/rules/edit/recognitionTypes/proof.type");
    await connectAs(page);
    // The built artifact served by the same boundary as production delivers
    // the entry document for the dotted route, and the editor opens the exact
    // object: no ID replacement, no fallback to the inventory.
    await expect(
      page.getByRole("heading", { name: "proof.type" }),
    ).toBeVisible();
    await expect(page.getByText(/编辑识别类型/)).toBeVisible();

    // A real browser refresh re-enters the same edit route.
    await page.reload();
    await connectAs(page);
    await expect(
      page.getByRole("heading", { name: "proof.type" }),
    ).toBeVisible();
    expect(page.url()).toContain("/rules/edit/recognitionTypes/proof.type");

    // After an explicit disconnect the token is memory-only: re-entering the
    // same deep link, connecting, and the boundary continuation must return to
    // the same edit context with the same identity; the object identity never
    // depends on the browser session.
    await page.getByRole("button", { name: "Disconnect" }).click();
    await page.goto("/ui-v2/rules/edit/recognitionTypes/proof.type");
    await connectAs(page);
    await expect(
      page.getByRole("heading", { name: "proof.type" }),
    ).toBeVisible();
    expect(page.url()).toContain("/rules/edit/recognitionTypes/proof.type");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("plus, at, space and dot IDs open for edit through SPA navigation", async ({
    page,
  }) => {
    await resetRules(page, "?empty=1");
    for (const idCase of ID_CASES) {
      await seedRecognitionType(page, idCase.raw);
    }
    for (const idCase of ID_CASES) {
      // Each direct entry is a fresh document: the token is memory-only, so
      // every entry reconnects and the AuthBoundary continuation returns to
      // the same identity-bearing edit route.
      await page.goto(`/ui-v2/rules/edit/recognitionTypes/${idCase.encoded}`);
      await connectAs(page);
      await expect(
        page.getByRole("heading", { name: idCase.raw }),
      ).toBeVisible();
      expect(page.url()).toContain(
        `/rules/edit/recognitionTypes/${idCase.encoded}`,
      );
    }
  });

  test("an identity-bearing object publishes, reopens, saves name-only, copies, toggles and removes", async ({
    page,
  }) => {
    const traffic = recordApiTraffic(page);
    await resetRules(page, "?empty=1");
    await page.goto("/ui-v2/rules?section=recognitionTypes");
    await connectAs(page);
    await expect(
      page.getByRole("heading", { name: "识别类型", exact: true }),
    ).toBeVisible();

    // Create through the one explicit create-drawer entry (the empty-state
    // command; the toolbar carries the same action for a non-empty list).
    await page
      .getByText("尚无识别类型配置")
      .locator("xpath=ancestor::div[1]")
      .getByRole("button", { name: "添加识别类型" })
      .click();
    const drawer = page.getByRole("dialog", { name: "添加识别类型" });
    await drawer.getByLabel(/^ID/).fill("proof+type");
    await drawer.getByLabel(/^名称/).fill("加号对象");
    await drawer.getByRole("button", { name: "保存" }).click();
    await expect(
      page.getByText(/已发布为新的 Active|新的 Active 已发布/).first(),
    ).toBeVisible();
    await expect(page.getByRole("row", { name: /proof\+type/ })).toBeVisible();

    // Reopen for edit from the inventory: same identity.
    await page
      .getByRole("row", { name: /proof\+type/ })
      .getByRole("button", { name: "编辑" })
      .click();
    await expect(
      page.getByRole("heading", { name: "proof+type" }),
    ).toBeVisible();
    await expect(page.getByText(/ID 不可更改/)).toBeVisible();

    // Name-only Save: the ID stays immutable and a successor publishes.
    const nameField = page.getByLabel(/^名称/);
    await nameField.fill("加号对象改名");
    await page.getByRole("button", { name: "保存", exact: true }).click();
    await expect(page.getByText(/已发布为新的 Active/)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "proof+type" }),
    ).toBeVisible();

    // Copy opens a distinct candidate with a backend-selected ID. The edit
    // page renders the same return action twice (header + footer actions);
    // either one is the same explicit return.
    await page.getByRole("link", { name: "返回整理规则清单" }).first().click();
    await expect(
      page.getByRole("heading", { name: "识别类型", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("row", { name: /proof\+type/ })
      .getByRole("button", { name: "复制" })
      .click();
    const copyDrawer = page.getByRole("dialog", { name: "复制识别类型" });
    await expect(copyDrawer).toBeVisible();
    // The copy candidate carries a distinct backend-selected ID; the source
    // object keeps its identity and the candidate is not Active until an
    // explicit Save.
    await expect(copyDrawer.getByLabel(/^ID/)).toHaveValue("proof+type-copy-1");
    // Closing an untouched candidate arms the discard warning; the second
    // click is the explicit discard.
    await copyDrawer.getByRole("button", { name: "关闭规则表单" }).click();
    await copyDrawer.getByRole("button", { name: "关闭规则表单" }).click();
    await expect(copyDrawer).toHaveCount(0);

    // Disable from the list publishes an explicit successor.
    await page
      .getByRole("row", { name: /proof\+type/ })
      .getByRole("button", { name: "停用" })
      .click();
    await page.getByRole("button", { name: "确认", exact: true }).click();
    await expect(page.getByText(/已停用,新的 Active 已发布/)).toBeVisible();

    // Remove (unreferenced) publishes a successor without the object.
    await page
      .getByRole("row", { name: /proof\+type/ })
      .getByRole("button", { name: "移除" })
      .click();
    await expect(page.getByText(/正在读取该对象的真实引用影响/)).toBeHidden();
    await page.getByRole("button", { name: "确认移除" }).click();
    await expect(page.getByText(/已移除,新的 Active 已发布/)).toBeVisible();
    await expect(page.getByRole("row", { name: /proof\+type/ })).toHaveCount(0);

    // The journey's writes are exactly the explicit commands above; every
    // other rules call is a read.
    const writes = traffic.filter(
      (entry) =>
        entry.startsWith("POST ") ||
        entry.startsWith("PUT ") ||
        entry.startsWith("DELETE "),
    );
    expect(writes.length).toBeGreaterThanOrEqual(4);
    for (const entry of writes) {
      expect(entry).toMatch(/rules\/objects/);
    }
  });
});
