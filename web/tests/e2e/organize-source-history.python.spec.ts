import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

/**
 * Real-Python browser proof for Slice 47 RO-6: a recorded failed/partial
 * organizing outcome warns before the ordinary confirmation and never blocks a
 * deliberate new request.
 *
 * The spec runs against `playwright.python.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serves the
 * built V2 artifact and the real MediaFlow API over one temporary SQLite
 * runtime with a checked Active configuration, real Local Storage and a
 * synthetic metadata provider. The harness control route records the source's
 * prior outcome through the real Manual Organize admission/analysis/
 * confirmation/publication path; only the executor boundary is a local seam
 * that reports a partial outcome whose Storage effect stays unknown.
 *
 * Proven operator journey: the file's same-version latest formal outcome is
 * `partial` with an unconfirmed effect; the batch that produced it already
 * released its single slot; Files shows the short reminder (target and unknown
 * effect in the item detail, in plain language) and the ordinary selected
 * confirmation; confirming performs a genuinely new organize whose real MOVE
 * effect is visible in Storage.
 */

const BASE = "http://127.0.0.1:4183";
const ADMIN_TOKEN = "harness-admin-token";
const FILE = "One.2001.mkv";

interface SeededHistory {
  readonly taskId: string;
  readonly executionId: string;
  readonly taskStatus: string;
  readonly queueState: string;
  readonly capacityBefore: number;
  readonly capacityUse: number;
  readonly mutationRecorded: string | null;
  readonly resultStatus: string;
  readonly effectCertainty: string;
  readonly uncertainEffects: string[];
  readonly destinationPath: string;
  readonly sourceExists: boolean;
  readonly destinationTargets: string[];
}

interface FileState {
  readonly sourceExists: boolean;
  readonly destinationTargets: string[];
}

async function connect(page: Page): Promise<void> {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("region", { name: "探索" })).toBeVisible();
}

async function fileState(
  request: APIRequestContext,
  file = FILE,
): Promise<FileState> {
  const response = await request.get(
    `${BASE}/__harness__/manual-file-state?file=${file}`,
  );
  expect(response.ok()).toBe(true);
  return (await response.json()) as FileState;
}

async function driveDiscovery(request: APIRequestContext): Promise<void> {
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
  throw new Error("the bounded discovery walk linked no exact plan summary");
}

test("a recorded partial history warns, then the confirmed new organize takes effect", async ({
  page,
  request,
}) => {
  // The prior pass is a real admitted/analyzed/confirmed organizing Task whose
  // recorded outcome is partial with an unconfirmed Storage effect.
  const seededResponse = await request.post(
    `${BASE}/__harness__/seed-recorded-unknown-history?file=${FILE}`,
  );
  expect(seededResponse.ok()).toBe(true);
  const seeded = (await seededResponse.json()) as SeededHistory;
  expect(seeded.resultStatus).toBe("PARTIAL");
  expect(seeded.effectCertainty).toBe("unknown");
  expect(seeded.uncertainEffects).toContain("mutation_outcome");
  expect(seeded.sourceExists).toBe(true);
  expect(seeded.destinationTargets).toEqual([]);
  // Slice 47 capacity rule: every file of that pass is terminal and its own
  // call returned, so the recorded unknown effect keeps no slot.
  expect(seeded.queueState).toBe("settled");
  expect(seeded.mutationRecorded).toBeNull();
  expect(seeded.capacityUse).toBe(seeded.capacityBefore);

  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await connect(page);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/resourcelib\/files/);
  await page
    .getByRole("button", { name: /source/ })
    .first()
    .click();
  await request.post(`${BASE}/__harness__/register-manual-worker`);
  await page.getByRole("checkbox", { name: `选择 ${FILE}` }).check();
  await page.getByRole("button", { name: "批量整理" }).click();
  await expect(page).toHaveURL(/organizeDiscovery=/);
  await driveDiscovery(request);
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card.getByRole("heading", { name: /第 1 \/ 1 个/ })).toBeVisible(
    { timeout: 30_000 },
  );

  // The short reminder is bound to this exact file and never claims that the
  // unknown effect was verified.
  await expect(
    page.getByText("部分文件上次整理未完成", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/上次整理部分成功/).first()).toBeVisible();
  await expect(page.getByText(new RegExp(FILE)).first()).toBeVisible();
  await expect(
    page.getByText("上次整理记录（同一文件版本）", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText(/效果未确认/).first()).toBeVisible();
  // The item detail names the recorded facts in plain language: the possible
  // target and the unconfirmed effect, without internal step codes or a
  // second verification product.
  await expect(page.getByText(/未确认效果/).first()).toBeVisible();
  await expect(
    page.getByText("存储写入结果", { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByText(/系统已核验|已验证安全/)).toHaveCount(0);
  await expect(
    page.getByRole("checkbox", { name: /我已知晓|我已核对|历史已确认/ }),
  ).toHaveCount(0);

  // Reading the summary is zero-effect: the reviewed source and target are
  // exactly as recorded until the operator confirms.
  expect(await fileState(request)).toEqual({
    sourceExists: true,
    destinationTargets: [],
  });

  // The ordinary selected confirmation is the only confirm, and it binds to
  // the reviewed subset.  The card hands the proved admission to the existing
  // task-center selection instead of a second result surface.
  await page.getByRole("button", { name: /整批复核/ }).click();
  await expect(page.getByText(/将整理 1 项/)).toBeVisible();
  await page.getByRole("button", { name: "确认整理 1 项" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible({
    timeout: 30_000,
  });

  const worker = await request.post(`${BASE}/__harness__/run-manual-worker`);
  expect(worker.ok()).toBe(true);
  const completed = (await worker.json()) as {
    readonly completed: boolean;
    readonly status: string;
  };
  expect(completed.completed).toBe(true);

  // The new work has its own real MOVE effect; the recorded unknown history
  // stays as it was (nothing replays or rewrites it).
  await expect
    .poll(async () => (await fileState(request)).destinationTargets.length)
    .toBeGreaterThan(0);
  const after = await fileState(request);
  expect(after.sourceExists).toBe(false);
  expect(after.destinationTargets).toEqual(
    expect.arrayContaining([expect.stringMatching(/One/)]),
  );
});
