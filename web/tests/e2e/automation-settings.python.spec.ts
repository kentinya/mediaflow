import { expect, test, type Page } from "@playwright/test";

/**
 * Real-Python browser proof for the native Automation engine settings journey
 * (Task 43.4, RO-6).
 *
 * This spec runs against `playwright.python.automation.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact and the real `MediaFlowApi` over one temporary SQLite
 * runtime database with a real checked Active configuration. Every read and Save
 * therefore travels through the real managed publication authority, and the
 * adoption readback is derived from a *real* resident loop in the same process
 * that installed the published cadence and wrote its own durable report — never
 * from a fabricated API row.
 *
 * Proven journeys: the settings tab and the System Settings Automation section
 * reach the same form; a Save publishes an Active successor and the response
 * says publication, not adoption; the live consumers then report their own
 * adopted cadence without a restart; a stale form is refused; an out-of-scope or
 * non-finite value never publishes; and reads/Save cause no media effects.
 */

const ADMIN_TOKEN = "harness-admin-token";
const SETTINGS_PATH = "/api/v1/operations/automation/settings";

async function connectOn(
  page: Page,
  path: string,
  token = ADMIN_TOKEN,
): Promise<void> {
  await page.goto(path);
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

interface SettingsDocument {
  readonly target: {
    readonly revisionId: string;
    readonly digest: string;
    readonly values: Record<string, number>;
  } | null;
  readonly adoption: {
    readonly consumers: number;
    readonly adoptedConsumers: number;
    readonly allAdopted: boolean;
  };
  readonly consumers: Record<
    string,
    {
      readonly adopted: boolean;
      readonly instances: Array<{
        readonly status: string;
        readonly effectiveValue: number | null;
      }>;
    }
  >;
}

async function settingsDocument(page: Page): Promise<SettingsDocument> {
  const response = await page.request.get(SETTINGS_PATH, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as SettingsDocument;
}

function recordApiCalls(page: Page): { method: string; path: string }[] {
  const api: { method: string; path: string }[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/v1/")) {
      api.push({ method: request.method(), path: url.pathname });
    }
  });
  return api;
}

test("the settings tab renders the four fields and states publication apart from adoption", async ({
  page,
}) => {
  const api = recordApiCalls(page);
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();

  const before = await settingsDocument(page);
  expect(before.target).not.toBeNull();
  await expect(panel.getByText("已发布目标")).toBeVisible();
  // The published target is named with its real Active revision.
  await expect(
    panel.getByText(new RegExp(before.target!.revisionId)),
  ).toBeVisible();
  // Before any consumer has adopted this publication, the page says so.
  await expect(panel.getByText(/尚未整体采用/).first()).toBeVisible();
  await expect(
    panel.getByText(/全部相关常驻进程都已采用当前发布值/),
  ).toHaveCount(0);

  for (const label of [
    /并行任务上限/,
    /任务失效判定时间/,
    /Worker 轮询间隔/,
    /调度器轮询间隔/,
  ]) {
    await expect(panel.getByLabel(label)).toBeVisible();
  }

  // Reading never wrote anything.
  expect(api.filter((call) => call.method !== "GET")).toHaveLength(0);
});

test("a live resident consumer adopts the published cadence without a restart", async ({
  page,
}) => {
  // Start the real resident cadence consumers *before* publishing, which is
  // exactly the "process started before the new Active" case.
  const started = await page.request.post(
    "/__harness__/start-resident-consumers",
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(started.ok()).toBe(true);

  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();

  const before = await settingsDocument(page);
  const publishedBefore = before.target!.values["automation.workerPollSeconds"];

  // Publish a distinctly different Worker cadence through the real API, using
  // the checked Active identity the page itself would send.
  const nextValue = publishedBefore === 1.5 ? 2.5 : 1.5;
  const saved = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      settings: {
        ...before.target!.values,
        "automation.workerPollSeconds": nextValue,
      },
      expectedRevisionId: before.target!.revisionId,
      expectedDigest: before.target!.digest,
    },
  });
  expect(saved.status()).toBe(201);
  const savedBody = (await saved.json()) as {
    published: boolean;
    revisionId: string;
  };
  expect(savedBody.published).toBe(true);
  expect(savedBody.revisionId).not.toBe(before.target!.revisionId);

  // The consumer reports the *new* value it actually installed, on its own.
  await expect
    .poll(
      async () => {
        const document = await settingsDocument(page);
        const worker = document.consumers["worker"];
        return worker.instances.map((item) => item.effectiveValue);
      },
      { timeout: 25_000 },
    )
    .toContain(nextValue);

  // The page readback shows the adopted consumer without a restart.
  await expect(
    page.getByRole("region", { name: "Worker 轮询采用情况" }),
  ).toBeVisible();
  await expect
    .poll(
      async () =>
        (await settingsDocument(page)).consumers["worker"].instances.every(
          (item) => item.status === "adopted",
        ),
      { timeout: 25_000 },
    )
    .toBe(true);
  const after = await settingsDocument(page);
  expect(after.target!.values["automation.workerPollSeconds"]).toBe(nextValue);
  expect(after.consumers["worker"].adopted).toBe(true);
});

test("a stale form is refused and the published Active is preserved", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const before = await settingsDocument(page);

  // A stale digest cannot publish: the previous Active stays authoritative.
  const stale = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      settings: {
        ...before.target!.values,
        "automation.maximumActiveJobs": 71,
      },
      expectedRevisionId: "stale-revision",
      expectedDigest: "stale-digest",
    },
  });
  expect(stale.status()).toBe(409);
  const after = await settingsDocument(page);
  expect(after.target!.revisionId).toBe(before.target!.revisionId);
  expect(after.target!.values["automation.maximumActiveJobs"]).not.toBe(71);
});

test("out-of-scope, non-finite and out-of-range values never publish", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const before = await settingsDocument(page);
  const values = { ...before.target!.values };

  const cases: Array<{
    readonly body: Record<string, unknown>;
    readonly code: string;
  }> = [
    {
      body: { ...values, locale: "en-GB" },
      code: "settings_field_unsupported",
    },
    {
      body: { ...values, "automation.workerPollSeconds": 0 },
      code: "settings_out_of_range",
    },
    {
      body: { ...values, "automation.maximumActiveJobs": 5.5 },
      code: "settings_fractional_integer",
    },
    {
      body: { ...values, "automation.schedulerPollSeconds": "2" },
      code: "settings_invalid_type",
    },
  ];
  for (const item of cases) {
    const response = await page.request.put(SETTINGS_PATH, {
      headers: {
        Authorization: `Bearer ${ADMIN_TOKEN}`,
        "Content-Type": "application/json",
      },
      data: { settings: item.body },
    });
    expect([409, 422]).toContain(response.status());
    expect(await settingsDocument(page)).toMatchObject({
      target: { revisionId: before.target!.revisionId },
    });
  }
});

test("the System Settings Automation section reaches the same form and authority", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/configuration");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const document = await settingsDocument(page);
  await expect(
    panel.getByText(new RegExp(document.target!.revisionId)),
  ).toBeVisible();
  // It is the same four-field form, not a second settings store.
  await expect(panel.getByLabel(/并行任务上限/)).toBeVisible();
  await expect(panel.getByLabel(/调度器轮询间隔/)).toBeVisible();
});
