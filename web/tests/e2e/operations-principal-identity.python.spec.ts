import { expect, test, type APIRequestContext } from "@playwright/test";
import { accountForToken, submitSignIn } from "./auth";

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
  const identity = await request.get(`${BASE}/api/auth/principal`, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(identity.status()).toBe(200);
  expect(await identity.json()).toEqual({ principal_id: PRINCIPAL_ID });

  const api: { method: string; path: string }[] = [];
  page.on("request", (browserRequest) => {
    const url = new URL(browserRequest.url());
    if (url.pathname.startsWith("/api/")) {
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

  await page.goto(`${BASE}/`);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  await expect(page.getByRole("table")).toBeVisible();

  // The file exists only in the harness's temporary live Local Storage. The
  // browser selects it from the actual ResourceLibrary listing.
  await page.getByRole("checkbox", { name: "选择 Three.2003.mkv" }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  await driveDiscoveryWorker(request);
  // The current Files landing is the overview; the per-file review is its
  // own explicit entry for the exact selected file.
  const overview = card.getByRole("region", { name: "本次整理概览" });
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await overview.getByRole("button", { name: "查看 Three.2003.mkv" }).click();
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );
  const recognition = card.locator('select[aria-label^="识别类型 "]');
  if (
    !(await recognition
      .first()
      .isVisible()
      .catch(() => false))
  ) {
    await card.getByText("修正识别或作品", { exact: true }).click();
  }
  await expect(recognition.first()).toBeVisible({ timeout: 15_000 });
  await recognition.first().selectOption("C");
  await card.getByRole("button", { name: "保存并重新分析" }).click();
  await expect(
    card.getByText(/选择已保存,正在按固定配置重新分析/),
  ).toBeVisible();
  await driveDiscoveryWorker(request);
  // A saved correction re-analyzes and returns to the same overview; the
  // exact file is opened again before its inclusion is confirmed.
  await expect(overview).toBeVisible({ timeout: 30_000 });
  await overview.getByRole("button", { name: "查看 Three.2003.mkv" }).click();
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    {
      timeout: 30_000,
    },
  );
  await expect(card.getByText("纳入本次整理").first()).toBeVisible({
    timeout: 30_000,
  });
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  // Simulate only the browser losing a real successful API response: the
  // Playwright proxy lets the production API commit its durable admission,
  // then aborts the client response.
  let droppedExecuteResponse = false;
  await page.route(
    /\/api\/operations\/organize\/previews\/[^/]+\/execute$/,
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
  await page.getByRole("button", { name: /整批复核/ }).click();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  // The retained request is reconciled automatically under the same
  // backend-authenticated principal; there is no manual query button.
  await expect(page).toHaveURL(/\/operations\?.*run=/, {
    timeout: 30_000,
  });
  const runId = new URL(page.url()).searchParams.get("run");
  expect(runId).toBeTruthy();
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: /核对提交结果/ })).toHaveCount(
    0,
  );
  expect(executePosts()).toHaveLength(1);
  expect(
    api.filter(
      (entry) =>
        entry.method === "GET" &&
        /\/operations\/organize\/previews\/[^/]+\/admission$/.test(entry.path),
    ).length,
  ).toBeGreaterThanOrEqual(1);
  expect(
    await (await request.get(`${BASE}/__harness__/manual-file-state`)).json(),
  ).toEqual({ sourceExists: true, destinationTargets: [] });

  // A reload and reconnect retain the same Chinese principal and the exact
  // selected run. The token stays memory-only and the admission is not
  // replayed.
  await page.reload();
  const signIn = page.getByLabel("Login name");
  const authenticated = page.getByRole("button", { name: "Account menu" });
  await expect(signIn.or(authenticated).first()).toBeVisible();
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  await expect(page).toHaveURL(new RegExp(`run=${runId}`));
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();
  expect(
    await (
      await request.get(`${BASE}/api/auth/principal`, {
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
