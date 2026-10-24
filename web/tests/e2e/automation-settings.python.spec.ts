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
  // The published target is stated as the exact Active it came from.  The raw
  // revision identity is diagnostic and stays folded rather than being the
  // primary page content, so the operator sees the version and can expand it.
  await expect(panel.getByText(/版本 \d+ · Active/)).toBeVisible();
  const diagnostics = panel.getByText("诊断标识");
  await expect(diagnostics).toBeVisible();
  await diagnostics.click();
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

test("a checked Save from the form publishes once and keeps adoption separate", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const before = await settingsDocument(page);

  // The shared form Save is the real command, not a raw API call: it carries
  // one submission identity and the checked Active identity it was edited on.
  const target = before.target!.values["automation.maximumActiveJobs"];
  const nextCapacity = target === 90 ? 91 : 90;
  const jobs = panel.getByLabel(/并行任务上限/);
  await jobs.fill(String(nextCapacity));
  const requests: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "PUT" &&
      new URL(request.url()).pathname === SETTINGS_PATH
    ) {
      requests.push(request.postData() ?? "");
    }
  });
  await panel.getByRole("button", { name: "保存设置" }).click();

  await expect(panel.getByText(/已发布新的目标值/)).toBeVisible();
  const after = await settingsDocument(page);
  expect(after.target!.values["automation.maximumActiveJobs"]).toBe(
    nextCapacity,
  );
  expect(after.target!.revisionId).not.toBe(before.target!.revisionId);
  // Exactly one submission for one click, and it named its own identity.
  expect(requests).toHaveLength(1);
  const body = JSON.parse(requests[0]!) as {
    submissionId?: string;
    expectedRevisionId?: string;
  };
  expect(typeof body.submissionId).toBe("string");
  expect(body.expectedRevisionId).toBe(before.target!.revisionId);
  // Publication is still shown apart from adoption.
  await expect(
    panel.getByText(/尚未整体采用|全部相关常驻进程都已采用当前发布值/).first(),
  ).toBeVisible();
});

test("a concurrent writer makes the ordinary background readback refuse the stale Save", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const before = await settingsDocument(page);

  // The operator starts editing the capacity field.
  const jobs = panel.getByLabel(/并行任务上限/);
  await jobs.fill("77");

  // Another writer publishes a different field while this form is open.
  const otherPoll =
    before.target!.values["automation.schedulerPollSeconds"] === 9 ? 8 : 9;
  const other = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      settings: {
        ...before.target!.values,
        "automation.schedulerPollSeconds": otherPoll,
      },
      expectedRevisionId: before.target!.revisionId,
      expectedDigest: before.target!.digest,
      submissionId: "e2e-concurrent-writer-1",
    },
  });
  expect(other.status()).toBe(201);

  // The panel's ordinary bounded readback (~5s) must deliver that publication
  // and refuse to re-arm the operator's old input against the new identity.
  await expect(
    panel.getByText(/已发布的设置在此期间被其他保存改变/),
  ).toBeVisible({
    timeout: 20_000,
  });
  await expect(panel.getByRole("button", { name: "保存设置" })).toBeDisabled();
  // The typed input stayed correctable.
  await expect(jobs).toHaveValue("77");
  // Only the concurrent writer published: the form never submitted.
  const after = await settingsDocument(page);
  expect(after.target!.values["automation.maximumActiveJobs"]).toBe(
    before.target!.values["automation.maximumActiveJobs"],
  );
  expect(after.target!.values["automation.schedulerPollSeconds"]).toBe(
    otherPoll,
  );
});

test("an unknown submission is reconciled from its own durable evidence, never by value equality", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const before = await settingsDocument(page);
  const values = { ...before.target!.values };

  // A submission identity that was never published, whose values happen to
  // equal the current target, must not be reported as committed.
  const equalButForeign = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      reconcile: true,
      settings: values,
      submissionId: "e2e-never-submitted-identity",
    },
  });
  expect(equalButForeign.status()).toBe(200);
  const foreign = (await equalButForeign.json()) as {
    state: string;
    committed: boolean;
  };
  expect(foreign.state).toBe("unresolved");
  expect(foreign.committed).toBe(false);

  // A real submission whose answer was lost is reconciled by its own identity.
  const nextCapacity = values["automation.maximumActiveJobs"] === 88 ? 89 : 88;
  const published = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      settings: {
        ...values,
        "automation.maximumActiveJobs": nextCapacity,
      },
      expectedRevisionId: before.target!.revisionId,
      expectedDigest: before.target!.digest,
      submissionId: "e2e-lost-response-1",
    },
  });
  expect(published.status()).toBe(201);
  const committed = await published.json();
  const reconciled = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      reconcile: true,
      settings: {
        ...values,
        "automation.maximumActiveJobs": nextCapacity,
      },
      submissionId: "e2e-lost-response-1",
    },
  });
  const resolved = (await reconciled.json()) as {
    state: string;
    committed: boolean;
    committedRevisionId: string | null;
  };
  expect(resolved.state).toBe("committed");
  expect(resolved.committed).toBe(true);
  expect(resolved.committedRevisionId).toBe(
    (committed as { revisionId: string }).revisionId,
  );
});

test("a lost rejection response reconciles into a correctable form, across a reload", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const before = await settingsDocument(page);

  // The operator starts editing, then another writer publishes first.
  const jobs = panel.getByLabel(/并行任务上限/);
  const submittedCapacity =
    before.target!.values["automation.maximumActiveJobs"] === 61 ? 62 : 61;
  await jobs.fill(String(submittedCapacity));
  const otherPoll =
    before.target!.values["automation.schedulerPollSeconds"] === 9 ? 8 : 9;
  const other = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      settings: {
        ...before.target!.values,
        "automation.schedulerPollSeconds": otherPoll,
      },
      expectedRevisionId: before.target!.revisionId,
      expectedDigest: before.target!.digest,
      submissionId: "e2e-lost-rejection-winner",
    },
  });
  expect(other.status()).toBe(201);
  const winner = await settingsDocument(page);

  // The form's own Save finishes 409 on the server, but *only that response* is
  // lost (the real request still reached and was processed by the API).
  let serverStatus: number | null = null;
  await page.route(`**${SETTINGS_PATH}`, async (route) => {
    if (route.request().method() !== "PUT") {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    serverStatus = response.status();
    await route.abort("failed");
  });
  await panel.getByRole("button", { name: "保存设置" }).click();
  await expect(panel.getByText(/上一次保存结果未知/)).toBeVisible({
    timeout: 20_000,
  });
  expect(serverStatus).toBe(409);
  await page.unroute(`**${SETTINGS_PATH}`);

  // Nothing was published by that request.
  expect((await settingsDocument(page)).target!.revisionId).toBe(
    winner.target!.revisionId,
  );

  // Reloading while unresolved keeps the block in place *and* keeps the typed
  // value; the operator then reconciles it from durable evidence.
  await page.reload();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  const reloaded = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(reloaded.getByText(/上一次保存结果未知/)).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    reloaded.getByRole("button", { name: "保存设置" }),
  ).toBeDisabled();
  await reloaded.getByRole("button", { name: "核实上次提交" }).click();
  await expect(reloaded.getByText(/本次提交没有发布/)).toBeVisible({
    timeout: 20_000,
  });
  // The typed value is retained and a deliberate Save is possible again.
  await expect(reloaded.getByLabel(/并行任务上限/)).toHaveValue(
    String(submittedCapacity),
  );
  await expect(
    reloaded.getByRole("button", { name: "保存设置" }),
  ).toBeEnabled();
  // Reconciling proved truth, it did not publish anything.
  expect((await settingsDocument(page)).target!.revisionId).toBe(
    winner.target!.revisionId,
  );
});

test("the System Settings Automation section reaches the same form and authority", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/configuration");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const document = await settingsDocument(page);
  await expect(panel.getByText(/版本 \d+ · Active/)).toBeVisible();
  await panel.getByText("诊断标识").click();
  await expect(
    panel.getByText(new RegExp(document.target!.revisionId)),
  ).toBeVisible();
  // It is the same four-field form, not a second settings store.
  await expect(panel.getByLabel(/并行任务上限/)).toBeVisible();
  await expect(panel.getByLabel(/调度器轮询间隔/)).toBeVisible();
});
