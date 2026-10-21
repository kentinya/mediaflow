import { expect, test, type Page } from "@playwright/test";

/**
 * Manual Organize journey built-artifact browser proof.
 *
 * Runs the built V2 artifact against the local fake API. The fake tokens are
 * non-secret throwaway values and no production service, media or credential is
 * involved. No request is intercepted with `page.route`: every test drives the
 * real route tree, query/mutation boundary and normalizers against the real
 * bounded fake documents.
 *
 * Safe test-observable evidence comes from `GET /__test__/manual-operations`,
 * which records only bounded method/path/object/body metadata: no Bearer value,
 * digest, fingerprint, path or authority material is recorded or asserted.
 *
 * Covered journey: durable intent with pinned options and optimistic versions,
 * a choice edit that invalidates earlier plan evidence, the shared analysis with
 * its complete fixed plan summary rendered in that same page, one meaningful
 * Execute action, the durable admitted execution and its per-item outcome, a
 * refresh-safe outcome route and unauthenticated deep-entry continuation.
 */

const BASE_URL = "http://127.0.0.1:4173";
const VIEWER_TOKEN = "e2e-viewer-token";
const READ_ONLY_TOKEN = "e2e-readonly-token";
const INTENT_ID = "organize-intent-e2e-001";
/** The bounded plan variants the fake can return for one session's analysis. */
type PlanVariant =
  | "default"
  | "destructive"
  | "hostile"
  | "misbound"
  | "suffix"
  | "lost"
  | "lost-unadmitted";
const EXECUTION_ID = "organize-execution-e2e-001";
const FAILED_EXECUTION_ID = "organize-execution-failed-e2e-001";

test.beforeEach(async ({ page }) => {
  // One deterministic fake state and one evidence bucket per test: the fake
  // server scopes both to the browser session cookie it sets here, so two
  // parallel workers can never erase or observe another test's evidence.
  const reset = await page.request.post(`${BASE_URL}/__test__/reset-organize`);
  expect(reset.status()).toBe(200);
});

interface ManualRequestEvidence {
  readonly method: string;
  readonly path: string;
  readonly objectType: string;
  readonly objectId?: string;
  readonly body?: Readonly<Record<string, unknown>>;
}

async function manualEvidence(page: Page): Promise<ManualRequestEvidence[]> {
  // `page.request` shares the browser context, so the per-test session cookie
  // set by the reset above is sent here: this returns the shared bucket plus
  // exactly this test's recorded requests, never another test's.
  const response = await page.request.get(
    `${BASE_URL}/__test__/manual-operations`,
  );
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as {
    readonly items?: readonly ManualRequestEvidence[];
    readonly requests?: readonly ManualRequestEvidence[];
  };
  return [...(payload.items ?? payload.requests ?? [])];
}

/** Deep-link first, then connect: the API token lives in memory only. */
async function connect(page: Page, token: string): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

/**
 * Reach one bounded shared plan through the real intent journey.
 *
 * There is no separate plan/Preview destination: the operator runs the shared
 * analysis in the intent page and the complete fixed plan is summarized there.
 * A test that needs a specific bounded fixture variant asks the fake for it in
 * its own session first, so the analysis returns that exact document.
 */
async function openPlan(
  page: Page,
  token: string,
  variant: PlanVariant = "default",
): Promise<void> {
  if (variant !== "default") {
    const selected = await page.request.post(
      `/__test__/organize-plan-variant?variant=${variant}`,
    );
    expect(selected.status()).toBe(200);
  }
  await page.goto(`/ui-v2/operations/organize/intent/${INTENT_ID}`);
  await connect(page, token);
  await expect(page.getByRole("heading", { name: "整理意图" })).toBeVisible();
  await page.getByRole("button", { name: "生成分析摘要" }).click();
  await expect(
    page.getByRole("heading", { name: "当前整理计划（零变更摘要）" }),
  ).toBeVisible();
}

test.describe("manual organize journey", () => {
  test("creates a durable intent, saves one choice and creates the exact Preview", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/organize/intent/${INTENT_ID}`);
    await connect(page, VIEWER_TOKEN);

    await expect(page.getByRole("heading", { name: "整理意图" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "生成分析摘要" }),
    ).toBeEnabled();

    // The downstream policy controls only display the RecognitionType's pinned
    // mapping; they are never independently editable in the normal journey.
    await expect(
      page.getByLabel("命名策略 organize-item-e2e-001"),
    ).toBeDisabled();
    await expect(
      page.getByLabel("分类策略 organize-item-e2e-001"),
    ).toBeDisabled();
    await expect(
      page.getByLabel("整理策略 organize-item-e2e-001"),
    ).toBeDisabled();

    // Selecting the RecognitionType brings out its exact configured naming,
    // classification and organize policies automatically.
    await page.getByLabel("识别类型 organize-item-e2e-001").selectOption("A");
    await expect(page.getByLabel("命名策略 organize-item-e2e-001")).toHaveValue(
      "A",
    );
    await page.getByRole("button", { name: "保存选择" }).click();
    await expect(page.getByText(/计划摘要已成为历史证据/)).toBeVisible();

    const afterChoice = await manualEvidence(page);
    const choice = afterChoice.filter(
      (entry) => entry.objectType === "organize_choice",
    );
    expect(choice).toHaveLength(1);
    expect(choice[0]?.body).toMatchObject({
      expectedItemVersion: 1,
      expectedVersion: 1,
      recognitionTypeId: "A",
      namingPolicyId: "A",
      classificationPolicyId: "A",
      organizePolicyId: "A",
    });
    expect(JSON.stringify(choice)).not.toContain("Bearer");

    await page.getByRole("button", { name: "生成分析摘要" }).click();

    // The intent action runs the shared Organize analysis inline, so the
    // operator stays on this same page with the complete fixed plan summary.
    await expect(page).toHaveURL(
      new RegExp(`/ui-v2/operations/organize/intent/${INTENT_ID}$`),
    );
    await expect(
      page.getByRole("heading", { name: "当前整理计划（零变更摘要）" }),
    ).toBeVisible();
    await expect(page.getByText(/分析不会修改文件/)).toBeVisible();
    await expect(page.getByText(/计划 organize-preview-e2e-001/)).toBeVisible();

    const afterAnalysis = await manualEvidence(page);
    const preview = afterAnalysis.filter(
      (entry) => entry.objectType === "organize_preview",
    );
    // The shared analysis admitted exactly one exact plan; reading the summary
    // afterwards is a plain GET and carries no secret or pin material.
    expect(preview.filter((entry) => entry.method === "POST")).toHaveLength(1);
    expect(preview.some((entry) => entry.method === "GET")).toBe(true);
    expect(JSON.stringify(preview)).not.toMatch(/fingerprint|digest|snapshot/i);
    // No independent Preview analysis admission exists any more.
    expect(
      afterAnalysis.filter(
        (entry) => entry.objectType === "organize_preview_analysis",
      ),
    ).toHaveLength(0);
  });

  test("admits exactly one Execute action and follows the durable outcome", async ({
    page,
  }) => {
    await openPlan(page, VIEWER_TOKEN);

    const execute = page.getByRole("button", {
      name: "确认整理 1 项",
    });
    await expect(execute).toBeEnabled();
    await execute.click();

    await expect(
      page.getByRole("heading", { name: "整理执行情况" }),
    ).toBeVisible();
    await expect(
      page.getByText(/执行记录 organize-execution-e2e-001/),
    ).toBeVisible();
    await expect(page.getByText("已验证完成", { exact: true })).toBeVisible();
    await expect(page.getByText("任务条目")).toBeVisible();

    const evidence = await manualEvidence(page);
    const admissions = evidence.filter(
      (entry) => entry.objectType === "organize_execute",
    );
    expect(admissions).toHaveLength(1);
    expect(admissions[0]?.body).toMatchObject({
      confirmation: true,
      expectedIntentVersion: 1,
      itemIds: ["organize-item-e2e-001"],
      allowOverwrite: false,
      allowSourceCleanup: false,
    });
    expect(JSON.stringify(admissions)).not.toMatch(
      /authorization|token|digest|fingerprint|snapshot/i,
    );
  });

  test("reconciles a lost admitted response and selects its durable Operations run", async ({
    page,
  }) => {
    const returnOps = encodeURIComponent("command=manual_organize&status=all");
    await page.goto(
      `/ui-v2/operations/organize/intent/${INTENT_ID}?returnOps=${returnOps}`,
    );
    await connect(page, VIEWER_TOKEN);
    const selected = await page.request.post(
      "/__test__/organize-plan-variant?variant=lost",
    );
    expect(selected.status()).toBe(200);
    await page.getByRole("button", { name: "生成分析摘要" }).click();
    await expect(
      page.getByRole("heading", { name: "当前整理计划（零变更摘要）" }),
    ).toBeVisible();

    const execute = page.getByRole("button", {
      name: "确认整理 1 项",
    });
    await expect(execute).toBeEnabled();
    await execute.click();
    await expect(
      page.getByRole("heading", { name: "执行结果未知" }),
    ).toBeVisible();
    await expect(execute).toBeDisabled();

    // The fake server returns an ambiguous 503 after it persists the exact
    // admission. The browser must wait for an explicit read and may not send
    // a second Execute while that outcome is unresolved.
    let evidence = await manualEvidence(page);
    expect(
      evidence.filter(
        (entry) =>
          entry.objectType === "organize_execute" && entry.method === "POST",
      ),
    ).toHaveLength(1);
    expect(
      evidence.filter(
        (entry) => entry.objectType === "organize_admission_read",
      ),
    ).toHaveLength(0);

    await page.getByRole("button", { name: "核对提交结果" }).click();
    await expect(
      page.getByRole("heading", { name: "任务中心", exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(/command=manual_organize/);
    await expect(page).toHaveURL(/run=organize-task-e2e-001/);
    await expect(page.getByRole("region", { name: "运行详情" })).toBeVisible();

    evidence = await manualEvidence(page);
    expect(
      evidence.filter(
        (entry) =>
          entry.objectType === "organize_execute" && entry.method === "POST",
      ),
    ).toHaveLength(1);
    expect(
      evidence.filter(
        (entry) =>
          entry.objectType === "organize_admission_read" &&
          entry.method === "GET",
      ),
    ).toHaveLength(1);
    expect(page.url()).not.toMatch(/token|digest|fingerprint|authorization/i);
  });

  test("a page reload cannot reopen Execute when the plan already has an admission", async ({
    page,
  }) => {
    await openPlan(page, VIEWER_TOKEN, "lost");

    const execute = page.getByRole("button", {
      name: "确认整理 1 项",
    });
    await execute.click();
    await expect(
      page.getByRole("heading", { name: "执行结果未知" }),
    ).toBeVisible();
    await expect(execute).toBeDisabled();

    // Reload clears component state and the memory-only API token. Re-running
    // the shared analysis returns the same durable fixed plan, whose bounded
    // execution read must still keep Execute closed and expose the existing
    // record for inspection without claiming it is equivalent to a selection
    // the reloaded page no longer holds.
    await page.reload();
    await expect(page.getByLabel("API token")).toBeVisible();
    await connect(page, VIEWER_TOKEN);
    await page.getByRole("button", { name: "生成分析摘要" }).click();
    await expect(
      page.getByRole("heading", { name: "该计划已有持久执行记录" }),
    ).toBeVisible();
    await expect(execute).toBeDisabled();
    await expect(
      page.getByRole("link", { name: /查看已有执行/ }),
    ).toBeVisible();

    const evidence = await manualEvidence(page);
    expect(
      evidence.filter(
        (entry) =>
          entry.objectType === "organize_execute" && entry.method === "POST",
      ),
    ).toHaveLength(1);
  });

  test("keeps Execute locked after a proven absence until the exact Preview is refreshed", async ({
    page,
  }) => {
    await openPlan(page, VIEWER_TOKEN, "lost-unadmitted");

    const execute = page.getByRole("button", {
      name: "确认整理 1 项",
    });
    await execute.click();
    await expect(
      page.getByRole("heading", { name: "执行结果未知" }),
    ).toBeVisible();
    await expect(execute).toBeDisabled();
    await page.getByRole("button", { name: "核对提交结果" }).click();
    await expect(page.getByText(/持久受理记录证明/)).toBeVisible();
    await expect(execute).toBeDisabled();

    const evidenceBeforeRefresh = await manualEvidence(page);
    expect(
      evidenceBeforeRefresh.filter(
        (entry) =>
          entry.objectType === "organize_execute" && entry.method === "POST",
      ),
    ).toHaveLength(1);

    await page.getByRole("button", { name: "刷新计划后再决定" }).click();
    await expect(
      page.getByRole("heading", { name: "计划已刷新，可以重新审阅" }),
    ).toBeVisible();
    await expect(execute).toBeEnabled();

    // Only the operator's second explicit click may submit again.
    await execute.click();
    await expect(
      page.getByRole("heading", { name: "执行结果未知" }),
    ).toBeVisible();
    const evidenceAfterResubmit = await manualEvidence(page);
    expect(
      evidenceAfterResubmit.filter(
        (entry) =>
          entry.objectType === "organize_execute" && entry.method === "POST",
      ),
    ).toHaveLength(2);
  });

  test("requires separate destructive confirmations for the exact Preview selection", async ({
    page,
  }) => {
    await openPlan(page, VIEWER_TOKEN, "destructive");

    await expect(page.getByText("复制").first()).toBeVisible();
    await expect(
      page.getByText(
        /此精确方案会把来源复制到目标，来源媒体保留。另外，会替换已有目标文件，需要明确授权覆盖；会删除整理后为空的来源目录，需要明确授权来源清理。/,
      ),
    ).toHaveCount(1);
    const execute = page.getByRole("button", {
      name: "确认整理 1 项",
    });
    await expect(execute).toBeDisabled();

    const overwrite = page.getByRole("checkbox", {
      name: /按已审阅方案替换现有目标文件/,
    });
    const cleanup = page.getByRole("checkbox", {
      name: /删除整理后为空的来源目录/,
    });
    await overwrite.check();
    await expect(execute).toBeDisabled();
    await cleanup.check();
    await expect(execute).toBeEnabled();
    await execute.click();
    await expect(
      page.getByRole("heading", { name: "整理执行情况" }),
    ).toBeVisible();

    const evidence = await manualEvidence(page);
    const admissions = evidence.filter(
      (entry) => entry.objectType === "organize_execute",
    );
    expect(admissions).toHaveLength(1);
    expect(admissions[0]?.body).toMatchObject({
      confirmation: true,
      expectedIntentVersion: 1,
      itemIds: ["organize-item-e2e-001"],
      allowOverwrite: true,
      allowSourceCleanup: true,
    });
  });

  test("keeps the durable outcome refresh-safe with no authority in the URL", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/organize/execution/${EXECUTION_ID}`);
    await connect(page, VIEWER_TOKEN);
    await expect(
      page.getByRole("heading", { name: "整理执行情况" }),
    ).toBeVisible();
    await page.reload();
    // Bearer material is memory-only, so a reload returns to the shared
    // connection boundary; connecting again returns to the same durable route.
    await connect(page, VIEWER_TOKEN);
    await expect(
      page.getByRole("heading", { name: "整理执行情况" }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "查看关联任务" }),
    ).toBeVisible();
    expect(page.url()).toContain(EXECUTION_ID);
    expect(page.url()).not.toMatch(/token|digest|fingerprint|authorization/i);
  });

  test("offers no manual organize control to a read-only principal", async ({
    page,
  }) => {
    await page.goto("/ui-v2/operations");
    await connect(page, READ_ONLY_TOKEN);
    // The unified inventory landing renders with its Chinese business heading.
    await expect(
      page.getByRole("heading", { name: "任务中心", exact: true }),
    ).toBeVisible();
    // The task-center entry is the native `新建整理任务` journey start; a
    // read-only principal is offered neither the old nor the new control.
    await expect(page.getByRole("link", { name: "新建整理任务" })).toHaveCount(
      0,
    );
    await expect(page.getByRole("link", { name: "准备手动整理" })).toHaveCount(
      0,
    );
    await expect(page.getByRole("link", { name: "发起受限扫描" })).toHaveCount(
      0,
    );
  });

  test("unauthenticated deep entry returns to the connection boundary", async ({
    page,
  }) => {
    await page.goto(`/ui-v2/operations/organize/intent/${INTENT_ID}`);
    await expect(page.getByRole("button", { name: "Connect" })).toBeVisible();
  });

  test("renders no Execute control for a malformed bounded document", async ({
    page,
  }) => {
    // The fake serves a contract-shaped document with an unmodelled action
    // route and an unknown item status. The built artifact must fail closed:
    // the malformed read state replaces the journey, no Execute control is
    // rendered, and no hostile value reaches the DOM.
    await openPlan(page, VIEWER_TOKEN, "hostile");

    await expect(
      page.getByText(/could not be understood as the expected contract/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "确认整理 1 项" }),
    ).toHaveCount(0);
    const rendered = (await page.locator("main").textContent()) ?? "";
    expect(rendered).not.toContain("attacker.example");
    expect(rendered).not.toContain("hacked");
    expect(rendered).not.toContain("DELETE");
    // The page itself never submitted an execute request.
    const evidence = await manualEvidence(page);
    expect(
      evidence.filter((entry) => entry.objectType === "organize_execute"),
    ).toHaveLength(0);
  });

  test("renders no Execute control when the execute action names a wrong route or method", async ({
    page,
  }) => {
    // The fake serves a contract-shaped document whose Execute action carries
    // a safe method and a route belonging to another Preview. The built
    // artifact must fail closed instead of rendering the fixed Execute control
    // from a transport that does not belong to this object.
    await openPlan(page, VIEWER_TOKEN, "misbound");

    await expect(
      page.getByText(/could not be understood as the expected contract/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "确认整理 1 项" }),
    ).toHaveCount(0);
    // No execute request was ever submitted for this Preview.
    const evidence = await manualEvidence(page);
    expect(
      evidence.filter((entry) => entry.objectType === "organize_execute"),
    ).toHaveLength(0);
  });

  test("renders no Execute control when the execute action names the Preview's own read route", async ({
    page,
  }) => {
    // The fake serves a contract-shaped document whose Execute action carries
    // the mutating POST method and this exact Preview's *read* route — the
    // same path without the `/execute` suffix. That route is not the action's
    // transport, so the built artifact must fail closed: no Execute control,
    // no submission, no hostile promotion of a read route into a mutation.
    await openPlan(page, VIEWER_TOKEN, "suffix");

    await expect(
      page.getByText(/could not be understood as the expected contract/i),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "确认整理 1 项" }),
    ).toHaveCount(0);
    const evidence = await manualEvidence(page);
    expect(
      evidence.filter((entry) => entry.objectType === "organize_execute"),
    ).toHaveLength(0);
  });

  test("renders a real failed execution with its evidence and the Review & Recovery handoff", async ({
    page,
  }) => {
    // A terminal failure is durable, truthful evidence, never a malformed
    // read: the failed item and its bounded finding render, the recovery
    // handoff the backend offers without any transport renders as the safe
    // Review & Recovery destination, and nothing replays or submits the work.
    await page.goto(
      `/ui-v2/operations/organize/execution/${FAILED_EXECUTION_ID}`,
    );
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByRole("heading", { name: "整理执行情况" }),
    ).toBeVisible();
    // The bounded finding renders on the execution and on the failed item.
    await expect(
      page
        .getByText(/destination collision: the configured destination/)
        .first(),
    ).toBeVisible();
    await expect(
      page.getByText(
        /inspect the pre-mutation failure, repair it, then request a fresh Preview/,
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "打开复核与恢复" }),
    ).toBeVisible();
    // The recovery handoff is a destination, not a mutation: this journey only
    // ever read the execution, never submitted anything. (The evidence merges
    // the shared serial Scan/Preview bucket, so only organize-journey entries
    // are asserted here.)
    const evidence = await manualEvidence(page);
    expect(
      evidence.filter((entry) => entry.objectType === "organize_execute"),
    ).toHaveLength(0);
    expect(
      evidence.filter(
        (entry) =>
          entry.method !== "GET" &&
          ["organize_choice", "organize_preview", "organize_execute"].includes(
            entry.objectType,
          ),
      ),
    ).toHaveLength(0);
  });

  test("the failed execution retires the FileIndex reconciliation surface and never replays Organize", async ({
    page,
  }) => {
    // Task45.5 RO-7: the FileIndex display reconciliation is retired. A
    // durable Result no longer offers a "re-check the file index" action, and
    // the page never offers an Organize replay either.
    await page.goto(
      `/ui-v2/operations/organize/execution/${FAILED_EXECUTION_ID}`,
    );
    await connect(page, VIEWER_TOKEN);

    await expect(
      page.getByRole("heading", { name: "整理执行情况" }),
    ).toBeVisible();
    await expect(page.getByText(/文件索引核对/)).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "重新核对文件索引" }),
    ).toHaveCount(0);

    const evidence = await manualEvidence(page);
    expect(
      evidence.filter(
        (entry) => entry.objectType === "organize_file_index_reconciliation",
      ),
    ).toHaveLength(0);
    expect(
      evidence.filter(
        (entry) =>
          entry.objectType === "organize_execute" ||
          entry.objectType === "organize_preview",
      ),
    ).toHaveLength(0);
  });
});
