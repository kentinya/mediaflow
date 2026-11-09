/**
 * OpenList metadata-only browse, bounded organize and native move proof.
 *
 * Run after `npm run build` under the dedicated real-Python harness:
 *
 *   npm run test:e2e -- --config=playwright.openlist-metadata.python.config.ts \
 *     tests/e2e/openlist-metadata.python.spec.ts
 *
 * The provider always answers `/api/fs/get` with HTTP 405.  The complete Files
 * journey must therefore browse, analyze, summarize, confirm and finish with
 * only `refresh: false` directory listings plus native move/rename.  No
 * download link, content read or unapproved mutation is allowed at any stage,
 * including the Worker's post-execution verification.
 */

import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const ADMIN_TOKEN = "harness-admin-token";
const SOURCES = ["One.2001.mkv", "Two.2002.mkv"] as const;
const SOURCE_PATHS = SOURCES.map((name) => `/Downloads/${name}`);
const TARGETS = [
  "/Downloads/Movies/Movies/Anime/One (2001) [tmdbid-101]/One (2001).mkv",
  "/Downloads/Movies/Movies/Anime/Two (2002) [tmdbid-102]/Two (2002).mkv",
];
const EVIDENCE_DIR =
  process.env.MF_OPENLIST_EVIDENCE ?? "test-results/openlist-metadata";

interface ProviderCall {
  readonly method: string;
  readonly path: string;
  readonly body: Record<string, unknown> | null;
  readonly authorized: boolean;
}

interface ProviderEntry {
  readonly path: string;
  readonly directory: boolean;
  readonly size: number;
  readonly sha256: string;
}

interface ProviderState {
  readonly entries: ProviderEntry[];
  readonly calls: ProviderCall[];
}

interface DiscoveryAdvance {
  readonly advanced: boolean;
  readonly previewId?: string | null;
}

interface ManualWorkerResult {
  readonly completed: boolean;
  readonly taskId?: string;
}

function contentEndpoints(state: ProviderState): ProviderCall[] {
  return state.calls.filter(
    (call) =>
      call.path === "/api/fs/get" ||
      call.path === "/api/fs/put" ||
      call.path === "/api/fs/copy" ||
      call.path === "/api/fs/remove" ||
      call.path === "/api/fs/mkdir" ||
      (call.method === "GET" && call.path !== "/ping"),
  );
}

function mutations(state: ProviderState): ProviderCall[] {
  return state.calls.filter(
    (call) => call.path === "/api/fs/move" || call.path === "/api/fs/rename",
  );
}

async function providerState(page: Page): Promise<ProviderState> {
  const response = await page.request.get("/__harness__/openlist-state");
  expect(response.ok()).toBe(true);
  return (await response.json()) as ProviderState;
}

async function openFiles(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1280, height: 960 });
  await page.goto("/ui-v2/resourcelib/files?resourceLibraryId=source");
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "文件", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("One.2001.mkv", { exact: true })).toBeVisible();
  await expect(page.getByText("Two.2002.mkv", { exact: true })).toBeVisible();
}

test("OpenList metadata-only stat completes a native move and rename with fs/get 405", async ({
  page,
}) => {
  await openFiles(page);
  const initial = await providerState(page);
  const initialEntries = new Map(
    initial.entries.map((entry) => [entry.path, entry]),
  );
  expect(initialEntries.has(SOURCE_PATHS[0])).toBe(true);
  expect(initialEntries.has(SOURCE_PATHS[1])).toBe(true);

  for (const name of SOURCES) {
    await page.getByRole("checkbox", { name: `选择 ${name}` }).check();
  }
  await page.getByRole("button", { name: "批量整理" }).click();
  const card = page.getByRole("dialog", { name: "整理所选文件" });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(/organizeDiscovery=/);

  let previewId: string | null = null;
  for (let step = 0; step < 24; step += 1) {
    const response = await page.request.post(
      "/__harness__/run-discovery-worker",
    );
    const advanced = (await response.json()) as DiscoveryAdvance;
    if (advanced.advanced && advanced.previewId != null) {
      previewId = advanced.previewId;
      break;
    }
  }
  expect(previewId).not.toBeNull();
  await expect(
    card.getByRole("heading", { name: /第 1 \/ 2 个/ }),
  ).toBeVisible();

  const beforeConfirmation = await providerState(page);
  expect(mutations(beforeConfirmation)).toHaveLength(0);
  for (const path of SOURCE_PATHS) {
    expect(
      beforeConfirmation.entries.some((entry) => entry.path === path),
    ).toBe(true);
  }
  for (const call of beforeConfirmation.calls) {
    if (call.path === "/api/fs/list") {
      expect(call.body?.refresh).toBe(false);
    }
    if (call.method === "POST") {
      expect(["/api/fs/list"]).toContain(call.path);
    }
  }

  await page.request.post("/__harness__/register-manual-worker");
  await page.getByRole("button", { name: /整批复核/ }).click();
  await page.getByRole("button", { name: /^确认整理 2 项$/ }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\?.*run=/);
  await expect(page.getByRole("dialog", { name: "运行详情" })).toBeVisible();

  let worker: ManualWorkerResult | null = null;
  for (let step = 0; step < 30; step += 1) {
    const response = await page.request.post("/__harness__/run-manual-worker");
    worker = (await response.json()) as ManualWorkerResult;
    const state = await providerState(page);
    const sourcesGone = SOURCE_PATHS.every(
      (path) => !state.entries.some((entry) => entry.path === path),
    );
    if (worker.completed && sourcesGone) break;
  }
  expect(worker?.completed).toBe(true);
  expect(worker?.taskId).toBeTruthy();

  const after = await providerState(page);
  for (const path of SOURCE_PATHS) {
    expect(after.entries.some((entry) => entry.path === path)).toBe(false);
  }
  TARGETS.forEach((target, index) => {
    const entry = after.entries.find((value) => value.path === target);
    const source = initialEntries.get(SOURCE_PATHS[index]);
    expect(entry).toBeDefined();
    expect(entry?.directory).toBe(false);
    expect(entry?.size).toBe(source?.size);
    expect(entry?.sha256).toBe(source?.sha256);
  });

  expect(contentEndpoints(after)).toHaveLength(0);
  const applied = mutations(after);
  expect(applied.length).toBe(4);
  expect(new Set(applied.map((call) => call.path))).toEqual(
    new Set(["/api/fs/move", "/api/fs/rename"]),
  );
  for (const call of after.calls) {
    if (call.path === "/api/fs/list") {
      expect(call.body?.refresh).toBe(false);
    }
    if (call.method === "POST") {
      expect(["/api/fs/list", "/api/fs/move", "/api/fs/rename"]).toContain(
        call.path,
      );
    } else {
      expect(call.path).toBe("/ping");
    }
    expect(call.authorized).toBe(true);
  }

  const taskResponse = await page.request.get(
    `/__harness__/task-result-state?taskId=${encodeURIComponent(worker!.taskId!)}`,
  );
  const task = (await taskResponse.json()) as {
    readonly available: boolean;
    readonly taskStatus: string;
    readonly results: Array<{
      readonly status: string;
      readonly effectCertainty: string;
    }>;
  };
  expect(task.available).toBe(true);
  expect(task.taskStatus).toBe("completed");
  expect(task.results).toHaveLength(2);
  for (const result of task.results) {
    expect(result.status).toBe("SUCCESS");
    expect(result.effectCertainty).toBe("verified_complete");
  }

  const detail = page.getByRole("dialog", { name: "运行详情" });
  await expect(detail).toBeVisible();
  await detail
    .getByRole("button", { name: "刷新", exact: true })
    .first()
    .click();
  await expect(detail.getByText("2成功", { exact: true })).toBeVisible({
    timeout: 15_000,
  });

  const final = await providerState(page);
  expect(mutations(final).length).toBe(4);
  expect(contentEndpoints(final)).toHaveLength(0);

  mkdirSync(EVIDENCE_DIR, { recursive: true });
  writeFileSync(
    `${EVIDENCE_DIR}/openlist-metadata.json`,
    JSON.stringify(
      {
        taskId: worker!.taskId,
        sources: SOURCE_PATHS,
        targets: TARGETS,
        entries: final.entries,
        calls: final.calls,
        contentEndpointCalls: contentEndpoints(final).length,
        mutationCalls: mutations(final).length,
        task: {
          status: task.taskStatus,
          results: task.results,
        },
      },
      null,
      2,
    ),
  );
  await page.screenshot({
    path: `${EVIDENCE_DIR}/openlist-metadata.png`,
    fullPage: true,
  });
});
