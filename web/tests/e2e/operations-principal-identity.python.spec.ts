import { expect, test, type APIRequestContext } from "@playwright/test";

const BASE = "http://127.0.0.1:4184";
const ADMIN_TOKEN = "harness-admin-token";
const PRINCIPAL_ID = "值班管理员";

/**
 * A legal Unicode principal drives the supported file-selection organize
 * journey. The browser loses only the successful Execute response; the exact
 * durable admission is reconciled, the same principal reconnects after reload,
 * and the real Worker result is read back without a second submission.
 *
 * Runs against `playwright.python.unicode-principal.config.ts` with the
 * harness's independent temporary SQLite/Local Storage fixture and the
 * configuration-resolved `值班管理员` admin principal. No production media,
 * credentials or external service is involved.
 */
test("a Unicode principal reconciles a lost organize admission and reads back the Worker result", async ({
  page,
  request,
}) => {
  const identity = await request.get(`${BASE}/api/v1/auth/principal`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(identity.status()).toBe(200);
  expect(await identity.json()).toEqual({ principal_id: PRINCIPAL_ID });

  const api: { method: string; path: string }[] = [];
  page.on("request", (browserRequest) => {
    const url = new URL(browserRequest.url());
    if (url.pathname.startsWith("/api/v1/")) {
      api.push({ method: browserRequest.method(), path: url.pathname });
    }
  });
  const executePosts = () =>
    api.filter(
      (entry) =>
        entry.method === "POST" &&
        /\/operations\/organize\/previews\/[^/]+\/execute$/.test(entry.path),
    );

  const registered = await request.post(
    `${BASE}/__harness__/register-manual-worker`,
  );
  expect(registered.ok()).toBeTruthy();

  await page.goto(`${BASE}/ui-v2/`);
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  await expect(page.getByRole("table")).toBeVisible();

  // The file exists only in the harness's temporary live Local Storage. The
  // browser selects it from the actual ResourceLibrary listing.
  await page.getByRole("checkbox", { name: "选择 Three.2003.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(
    page.getByRole("heading", { name: "新建整理任务", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/discoveryId=/);
  await driveDiscoveryWorker(request);
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  const recognition = page.locator('select[aria-label^="识别类型 "]');
  await expect(recognition.first()).toBeVisible({ timeout: 15_000 });
  await recognition.first().selectOption("C");
  await expect(page.getByText(/修正已持久保存/)).toBeVisible();
  await driveDiscoveryWorker(request);
  await expect(
    page.getByRole("heading", { name: "计划摘要", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole("heading", { name: /Three\.2003\.mkv 可执行/ }),
  ).toBeVisible();
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  // Simulate only the browser losing a real successful API response: the
  // Playwright proxy lets the production API commit its durable admission,
  // then aborts the client response.
  let droppedExecuteResponse = false;
  await page.route(
    /\/api\/v1\/operations\/organize\/previews\/[^/]+\/execute$/,
    async (route) => {
      if (droppedExecuteResponse) {
        await route.continue();
        return;
      }
      droppedExecuteResponse = true;
      await route.fetch();
      await route.abort("connectionreset");
    },
  );
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(
    page.getByRole("heading", { name: "执行结果未知" }),
  ).toBeVisible();
  expect(executePosts()).toHaveLength(1);
  await expect(page.getByText("已受理执行，不再纳入本次创建")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "确认整理 0 项" }),
  ).toBeDisabled();
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  await page.getByRole("button", { name: "核对提交结果" }).click();
  await expect(
    page.getByRole("heading", { name: "整理执行情况" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "查看关联任务" }).click();
  await expect(
    page.getByRole("heading", { name: "任务中心", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/run=/);
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  expect(executePosts()).toHaveLength(1);
  expect(
    api.filter(
      (entry) =>
        entry.method === "GET" &&
        /\/operations\/organize\/previews\/[^/]+\/admission$/.test(entry.path),
    ),
  ).toHaveLength(1);

  // A reload and reconnect retain the same Chinese principal and the exact
  // selected run. The token stays memory-only and the admission is not
  // replayed.
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`run=${runId}`));
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  expect(
    await (
      await request.get(`${BASE}/api/v1/auth/principal`, {
        headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
      })
    ).json(),
  ).toEqual({ principal_id: PRINCIPAL_ID });
  const browserState = await page.evaluate(() => ({
    local: window.localStorage.length,
    sessionValues: Object.values(window.sessionStorage),
    cookie: document.cookie,
    body: document.body.textContent ?? "",
  }));
  expect(browserState.local).toBe(0);
  expect(browserState.cookie).toBe("");
  expect(
    browserState.sessionValues.some((value) => value.includes(ADMIN_TOKEN)),
  ).toBe(false);
  expect(browserState.body).not.toContain(ADMIN_TOKEN);
  expect(executePosts()).toHaveLength(1);

  const workerRun = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(workerRun.ok()).toBeTruthy();
  expect(await workerRun.json()).toMatchObject({
    completed: true,
    taskId: runId,
    status: "completed",
    itemCount: 1,
  });
  const detail = page.getByRole("dialog", { name: "运行详情" });
  await detail
    .getByRole("button", { name: "刷新", exact: true })
    .first()
    .click();
  const items = detail.getByRole("region", { name: "主条目" });
  await expect(items.getByText("Three.2003.mkv")).toBeVisible();
  const evidenceResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response.url().includes(`/operations/runs/${runId}/items/`),
  );
  await items.getByRole("button", { name: "查看证据" }).click();
  const evidence = (await (await evidenceResponse).json()) as {
    readonly results: readonly {
      readonly effect_certainty: string;
      readonly recognition_type: string;
    }[];
  };
  expect(evidence.results).toHaveLength(1);
  expect(evidence.results[0]).toMatchObject({
    effect_certainty: "verified_complete",
    recognition_type: "C",
  });
  await expect(
    detail.getByRole("region", { name: "条目证据" }).getByText("文件已整理", {
      exact: true,
    }),
  ).toBeVisible();
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toMatchObject({
    sourceExists: false,
    destinationTargets: expect.arrayContaining([
      expect.stringContaining("Three"),
    ]),
  });
  expect(executePosts()).toHaveLength(1);
});

async function driveDiscoveryWorker(request: APIRequestContext): Promise<void> {
  for (let step = 0; step < 20; step += 1) {
    const advanced = await request.post(
      `${BASE}/__harness__/run-discovery-worker`,
    );
    const body = (await advanced.json()) as {
      readonly advanced: boolean;
      readonly previewId?: string | null;
    };
    if (body.advanced && body.previewId != null) return;
  }
  throw new Error("bounded discovery Worker did not link its Preview");
}
