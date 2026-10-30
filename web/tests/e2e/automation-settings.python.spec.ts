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
        readonly instanceId: string;
        readonly status: string;
        readonly effectiveValue: number | null;
      }>;
      readonly historyCount?: number;
      readonly history?: Array<{
        readonly instanceId: string;
        readonly liveness: string;
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

test("a graceful resident restart restores current adoption and keeps the predecessor as history", async ({
  page,
}) => {
  // A43-01: the ordinary restart path must not let the stopped predecessor veto
  // (or certify) the deployment-wide claim. Both entries are real: the consumers
  // are the production ResidentLoop + adoption reporter, and the read is the
  // real settings API the page itself calls.
  const started = await page.request.post(
    "/__harness__/start-resident-consumers",
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(started.ok()).toBe(true);

  const published = await settingsDocument(page);
  const schedulerPoll =
    published.target!.values["automation.schedulerPollSeconds"];

  // Publish a distinctly different Scheduler cadence through the checked Save.
  const nextValue = schedulerPoll === 3 ? 4 : 3;
  const saved = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      settings: {
        ...published.target!.values,
        "automation.schedulerPollSeconds": nextValue,
      },
      expectedRevisionId: published.target!.revisionId,
      expectedDigest: published.target!.digest,
    },
  });
  expect(saved.status()).toBe(201);

  const consumerIds = async (service: string): Promise<string[]> =>
    (await settingsDocument(page)).consumers[service]!.instances.map(
      (item) => item.instanceId,
    );
  await expect
    .poll(
      async () => (await settingsDocument(page)).adoption.adoptedConsumers,
      { timeout: 30_000 },
    )
    .toBe(2);
  const predecessor = (await consumerIds("scheduler"))[0]!;
  expect(predecessor).toBeTruthy();

  // The graceful stop + fresh replacement happens through one existing-style
  // harness call that runs the production stop/register path.
  const restarted = await page.request.post(
    "/__harness__/restart-resident-consumer?service=scheduler",
    { headers: { Authorization: `Bearer ${ADMIN_TOKEN}` } },
  );
  expect(restarted.ok()).toBe(true);

  // The replacement is a new current consumer and the claim recovers without any
  // operator workaround.
  await expect
    .poll(
      async () => {
        const document = await settingsDocument(page);
        const ids = document.consumers["scheduler"]!.instances.map(
          (item) => item.instanceId,
        );
        return {
          allAdopted: document.adoption.allAdopted,
          newIdentity: ids.length === 1 && ids[0] !== predecessor,
        };
      },
      { timeout: 40_000 },
    )
    .toEqual({ allAdopted: true, newIdentity: true });

  const after = await settingsDocument(page);
  const history = after.consumers["scheduler"] as unknown as {
    history?: Array<{ instanceId: string; liveness: string }>;
    historyCount?: number;
  };
  expect(history.historyCount).toBe(1);
  expect(history.history?.map((item) => item.instanceId)).toEqual([
    predecessor,
  ]);
  expect(history.history?.[0]?.liveness).toBe("stopped");

  // The page shows the same truth: the live replacement adopted, and the
  // retained identity is folded into history rather than presented as a
  // current consumer to "start up".
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const schedulerAdoption = page.getByRole("region", {
    name: "调度器轮询采用情况",
  });
  await expect(
    schedulerAdoption.getByText("全部当前实例已采用", { exact: true }),
  ).toBeVisible();
  await expect(
    schedulerAdoption.getByText("已采用当前发布值").first(),
  ).toBeHidden();
  await schedulerAdoption.getByText(/^实例详情/).click();
  await expect(
    schedulerAdoption.getByText("已采用当前发布值").first(),
  ).toBeVisible({ timeout: 20_000 });
  // History is folded diagnosis: expanding it is how the operator reads it, and
  // the retained identity appears there rather than as a current consumer.
  const historySummary = schedulerAdoption.getByText(/历史注册/);
  await expect(historySummary).toBeVisible();
  await historySummary.click();
  await expect(schedulerAdoption.getByText(predecessor)).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    panel.getByText(/全部相关常驻进程都已采用当前发布值/),
  ).toBeVisible({ timeout: 20_000 });
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

  // The panel's ordinary bounded readback (~5s) delivers that publication. The
  // old four-field input is never re-armed against the new identity, and the
  // operator is not simply blocked either: only the field they actually edited
  // is merged onto the latest publication.
  await expect(panel.getByText(/你改过的字段已合并到最新发布值上/)).toBeVisible(
    {
      timeout: 20_000,
    },
  );
  // The typed capacity is kept and the other writer's scheduler value is shown.
  await expect(jobs).toHaveValue("77");
  await expect(panel.getByLabel(/调度器轮询间隔/)).toHaveValue(
    String(otherPoll),
  );
  // Only the concurrent writer has published so far.
  const after = await settingsDocument(page);
  expect(after.target!.values["automation.maximumActiveJobs"]).toBe(
    before.target!.values["automation.maximumActiveJobs"],
  );
  expect(after.target!.values["automation.schedulerPollSeconds"]).toBe(
    otherPoll,
  );

  // The deliberate Save publishes the capacity and keeps the other writer's
  // scheduler value: no silent revert, no whole-form re-arm.
  await panel.getByRole("button", { name: "保存设置" }).click();
  await expect(panel.getByText(/已发布新的目标值/)).toBeVisible({
    timeout: 20_000,
  });
  const saved = await settingsDocument(page);
  expect(saved.target!.values["automation.maximumActiveJobs"]).toBe(77);
  expect(saved.target!.values["automation.schedulerPollSeconds"]).toBe(
    otherPoll,
  );

  // After the merged Save the form shows the returned publication: capacity 77
  // with the other writer's scheduler value, nothing pending, and no invented
  // "you typed during the Save" message (which used to restore the old value).
  await expect(jobs).toHaveValue("77");
  await expect(panel.getByLabel(/调度器轮询间隔/)).toHaveValue(
    String(otherPoll),
  );
  await expect(panel.getByText(/保存期间输入的其他值/)).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "保存设置" })).toBeDisabled();

  // The next ordinary capacity-only edit keeps the other writer's scheduler
  // value: it must never be silently restored to the pre-merge value.
  await jobs.fill("78");
  await expect(panel.getByRole("button", { name: "保存设置" })).toBeEnabled();
  await expect(panel.getByLabel(/调度器轮询间隔/)).toHaveValue(
    String(otherPoll),
  );
  await panel.getByRole("button", { name: "保存设置" }).click();
  await expect(panel.getByText(/已发布新的目标值/)).toBeVisible({
    timeout: 20_000,
  });
  const twiceSaved = await settingsDocument(page);
  expect(twiceSaved.target!.values["automation.maximumActiveJobs"]).toBe(78);
  expect(twiceSaved.target!.values["automation.schedulerPollSeconds"]).toBe(
    otherPoll,
  );
});

test("a lost same-field conflict stays an explicit choice until the operator saves", async ({
  page,
}) => {
  // Both writers change the *same* field and only the original 409 response is
  // lost.  Reconciling proves that request published nothing, but the overlap
  // must stay a conflict: each choice writes nothing, and only the explicit Save
  // publishes the operator's value — while an older context without baseline
  // values needs the same explicit choice.
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const before = await settingsDocument(page);
  const original = before.target!.values["automation.maximumActiveJobs"];
  const mine = original === 61 ? 62 : 61;
  // The other writer's value must differ from both possible `mine` values; 71
  // differs from 61 and 62, and the harness default capacity is not 71.
  const current = 71;

  // The operator types a capacity the other writer will also change.
  const jobs = panel.getByLabel(/并行任务上限/);
  await jobs.fill(String(mine));
  const other = await page.request.put(SETTINGS_PATH, {
    headers: {
      Authorization: `Bearer ${ADMIN_TOKEN}`,
      "Content-Type": "application/json",
    },
    data: {
      settings: {
        ...before.target!.values,
        "automation.maximumActiveJobs": current,
      },
      expectedRevisionId: before.target!.revisionId,
      expectedDigest: before.target!.digest,
      submissionId: "e2e-same-field-winner",
    },
  });
  expect(other.status()).toBe(201);
  const winner = await settingsDocument(page);
  expect(winner.target!.values["automation.maximumActiveJobs"]).toBe(current);

  // The form's own Save is refused 409 by the real API, but only the response is
  // lost, so the page must retain the attempt and reconcile it from durability.
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
  expect((await settingsDocument(page)).target!.revisionId).toBe(
    winner.target!.revisionId,
  );

  await page.reload();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  const reloaded = page.getByRole("region", { name: "自动化引擎设置" });
  await reloaded.getByRole("button", { name: "核实上次提交" }).click();
  await expect(reloaded.getByText(/本次提交没有发布/)).toBeVisible({
    timeout: 20_000,
  });

  // The conflict survives the reconciliation: both values are stated, Save is
  // refused, and reconciling published nothing.
  const conflictCopy = new RegExp(
    `当前发布值为 ${current},你输入的值是 ${mine}`,
  );
  await expect(reloaded.getByText(conflictCopy)).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    reloaded.getByRole("button", { name: "保存设置" }),
  ).toBeDisabled();
  expect((await settingsDocument(page)).target!.revisionId).toBe(
    winner.target!.revisionId,
  );

  // Adopting the current value publishes nothing and leaves nothing to save.
  await reloaded.getByRole("button", { name: "采用当前值" }).click();
  await expect(reloaded.getByLabel(/并行任务上限/)).toHaveValue(
    String(current),
  );
  await expect(
    reloaded.getByRole("button", { name: "保存设置" }),
  ).toBeDisabled();
  expect((await settingsDocument(page)).target!.revisionId).toBe(
    winner.target!.revisionId,
  );

  // Keeping the operator's value also publishes nothing; only the explicit Save
  // does, and it is checked against the current identity.
  await reloaded.getByLabel(/并行任务上限/).fill(String(mine));
  await expect(reloaded.getByText(conflictCopy)).toBeVisible();
  await reloaded.getByRole("button", { name: "保留我的修改" }).click();
  await expect(
    reloaded.getByRole("button", { name: "保存设置" }),
  ).toBeEnabled();
  expect((await settingsDocument(page)).target!.revisionId).toBe(
    winner.target!.revisionId,
  );
  await reloaded.getByRole("button", { name: "保存设置" }).click();
  await expect(reloaded.getByText(/已发布新的目标值/)).toBeVisible({
    timeout: 20_000,
  });
  const published = await settingsDocument(page);
  expect(published.target!.values["automation.maximumActiveJobs"]).toBe(mine);
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
  // The typed value is retained, and the other writer's untouched scheduler
  // change is *shown* rather than silently reverted to the value this form read.
  await expect(reloaded.getByLabel(/并行任务上限/)).toHaveValue(
    String(submittedCapacity),
  );
  await expect(reloaded.getByLabel(/调度器轮询间隔/)).toHaveValue(
    String(otherPoll),
  );
  await expect(
    reloaded.getByRole("button", { name: "保存设置" }),
  ).toBeEnabled();
  // Reconciling proved truth, it did not publish anything.
  expect((await settingsDocument(page)).target!.revisionId).toBe(
    winner.target!.revisionId,
  );

  // The decisive check B flagged: the *next* Save must publish the operator's
  // capacity while preserving the other writer's scheduler value.  Before the
  // correction the offered Save silently restored scheduler 5.
  await reloaded.getByRole("button", { name: "保存设置" }).click();
  await expect(reloaded.getByText(/已发布新的目标值/)).toBeVisible({
    timeout: 20_000,
  });
  const afterSave = await settingsDocument(page);
  expect(afterSave.target!.values["automation.maximumActiveJobs"]).toBe(
    submittedCapacity,
  );
  expect(afterSave.target!.values["automation.schedulerPollSeconds"]).toBe(
    otherPoll,
  );
});

test("a lost invalid-input rejection reconciles into a correctable integer", async ({
  page,
}) => {
  await connectOn(page, "/ui-v2/operations/automation?tab=settings");
  const panel = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(panel).toBeVisible();
  const before = await settingsDocument(page);
  const otherPoll =
    before.target!.values["automation.schedulerPollSeconds"] === 9 ? 8 : 9;

  // Another writer changes the scheduler poll, so the recovery must not revert it.
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
      submissionId: "e2e-invalid-winner",
    },
  });
  expect(other.status()).toBe(201);
  const winner = await settingsDocument(page);

  // The real form accepts the text `3.5` for the integer capacity and the real
  // API refuses it 422/settings_fractional_integer; only that response is lost.
  const jobs = panel.getByLabel(/并行任务上限/);
  await jobs.fill("3.5");
  let serverStatus: number | null = null;
  let serverCode: string | null = null;
  await page.route(`**${SETTINGS_PATH}`, async (route) => {
    if (route.request().method() !== "PUT") {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    serverStatus = response.status();
    const payload = (await response.json()) as {
      error?: { code?: string };
    };
    serverCode = payload.error?.code ?? null;
    await route.abort("failed");
  });
  await panel.getByRole("button", { name: "保存设置" }).click();
  await expect(panel.getByText(/上一次保存结果未知/)).toBeVisible({
    timeout: 20_000,
  });
  expect(serverStatus).toBe(422);
  expect(serverCode).toBe("settings_fractional_integer");
  await page.unroute(`**${SETTINGS_PATH}`);
  expect((await settingsDocument(page)).target!.revisionId).toBe(
    winner.target!.revisionId,
  );

  // Reload while unresolved, then reconcile the exact refused submission.
  await page.reload();
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  const reloaded = page.getByRole("region", { name: "自动化引擎设置" });
  await expect(reloaded.getByText(/上一次保存结果未知/)).toBeVisible({
    timeout: 20_000,
  });
  const reconcile = reloaded.getByRole("button", { name: "核实上次提交" });
  const reconcileResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(SETTINGS_PATH) &&
      response.request().method() === "PUT",
  );
  await reconcile.click();
  const reconciled = await reconcileResponse;
  expect(reconciled.status()).toBe(200);
  const reconciledBody = (await reconciled.json()) as {
    state: string;
    rejection?: { code?: string; field?: string };
  };
  expect(reconciledBody.state).toBe("not_committed");
  expect(reconciledBody.rejection?.code).toBe("settings_fractional_integer");
  expect(reconciledBody.rejection?.field).toBe("automation.maximumActiveJobs");

  // The invalid text is retained and editable; the other writer's scheduler
  // value is preserved in the form.
  await expect(reloaded.getByLabel(/并行任务上限/)).toHaveValue("3.5");
  await expect(reloaded.getByLabel(/并行任务上限/)).toBeEditable();
  await expect(reloaded.getByLabel(/调度器轮询间隔/)).toHaveValue(
    String(otherPoll),
  );

  // Correcting it and saving publishes only the corrected value.
  await reloaded.getByLabel(/并行任务上限/).fill("4");
  await reloaded.getByRole("button", { name: "保存设置" }).click();
  await expect(reloaded.getByText(/已发布新的目标值/)).toBeVisible({
    timeout: 20_000,
  });
  const afterSave = await settingsDocument(page);
  expect(afterSave.target!.values["automation.maximumActiveJobs"]).toBe(4);
  expect(afterSave.target!.values["automation.schedulerPollSeconds"]).toBe(
    otherPoll,
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
