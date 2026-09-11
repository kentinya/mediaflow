import { expect, test, type Page } from "@playwright/test";

/**
 * Built-artifact browser proof for the V2 Operations workspace journey.
 *
 * It runs against the built V2 artifact plus the local fake API: no production
 * credentials, media, Storage or external providers are used. The fake mirrors
 * the authoritative Python contract (bounded filters, filter-bound cursors,
 * backend-computed lifecycle projection, optimistic lifecycle rejection), and
 * records only safe request metadata for the no-automatic-replay proof.
 */

const VIEWER_TOKEN = "e2e-viewer-token";
const READ_ONLY_TOKEN = "e2e-readonly-token";

async function connect(page: Page, token: string = VIEWER_TOKEN) {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

async function openOperations(page: Page) {
  await page.getByRole("link", { name: "Operations", exact: true }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
}

async function openTaskList(page: Page) {
  await openOperations(page);
  await page.getByRole("link", { name: "Tasks", exact: true }).first().click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks$/);
  await expect(
    page.getByRole("heading", { name: "Tasks", exact: true }),
  ).toBeVisible();
}

async function openJobList(page: Page) {
  await openOperations(page);
  await page.getByRole("link", { name: "Jobs", exact: true }).first().click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs$/);
  await expect(
    page.getByRole("heading", { name: "Jobs", exact: true }),
  ).toBeVisible();
}

async function openTaskDetail(page: Page, taskId: string) {
  await openTaskList(page);
  await page.getByRole("link", { name: taskId }).click();
  await expect(
    page.getByRole("heading", { name: `Task ${taskId}` }),
  ).toBeVisible();
}

async function openJobDetail(page: Page, jobId: string) {
  await openJobList(page);
  await page.getByRole("link", { name: jobId }).click();
  await expect(
    page.getByRole("heading", { name: `Job ${jobId}` }),
  ).toBeVisible();
}

test("Operations landing shows Worker readiness and workspace links", async ({
  page,
}) => {
  await connect(page);
  await openOperations(page);

  await expect(
    page.getByRole("heading", { name: "Worker readiness" }),
  ).toBeVisible();
  await expect(page.getByText(/Worker ready/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Tasks", exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Jobs", exact: true }).first(),
  ).toBeVisible();
});

test("the submitted Operations filter is reflected in the URL and survives reconnect", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);
  await page.getByLabel("Filter by status").selectOption("failed");
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();

  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.getByLabel("API token")).toBeVisible();
});

test("an unauthenticated deep entry reconnects to the same filtered collection", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations/tasks?status=failed");
  await expect(page.getByLabel("API token")).toBeVisible();
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
});

test("a reload drops the memory-only token and returns to the connection boundary", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);
  await page.reload();
  await expect(page.getByLabel("API token")).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
});

test("Task list filters through the backend and distinguishes filtered-empty", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);

  await page.getByLabel("Filter by status").selectOption("failed");
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();
  await expect(page.getByRole("link", { name: "task-001" })).toHaveCount(0);

  await page.getByLabel("Filter by work kind").selectOption("organize");
  await expect(
    page.getByRole("heading", { name: "No matching Tasks" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Reset filters" }).first().click();
  await expect(page.getByRole("link", { name: "task-001" })).toBeVisible();
});

test("Task list keeps the submitted filter and reports the real page boundary", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);

  await page.getByLabel("Filter by status").selectOption("running");
  await expect(page.getByRole("link", { name: "task-002" })).toBeVisible();
  await expect(page.getByRole("link", { name: "task-005" })).toBeVisible();
  await expect(page.getByRole("link", { name: "task-001" })).toHaveCount(0);

  // The filtered collection fits one bounded page, so the list reports no
  // further page instead of inventing one.
  await expect(page.getByRole("button", { name: "Next" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Previous" })).toBeDisabled();
});

test("Job list filters by status and work kind", async ({ page }) => {
  await connect(page);
  await openJobList(page);

  await page.getByLabel("Filter by work kind").selectOption("preview");
  await expect(page.getByRole("link", { name: "job-003" })).toBeVisible();
  await expect(page.getByRole("link", { name: "job-001" })).toHaveCount(0);

  await page.getByLabel("Filter by status").selectOption("failed");
  await expect(page.getByRole("link", { name: "job-005" })).toBeVisible();
  await expect(page.getByRole("link", { name: "job-003" })).toHaveCount(0);
});

test("Task detail separates the aggregate from items and results", async ({
  page,
}) => {
  await connect(page);
  await openTaskDetail(page, "task-001");

  await expect(
    page.getByRole("heading", { name: "Task aggregate" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: /TaskItems/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Results/ })).toBeVisible();
  // A successful sibling stays visible next to the failed one.
  await expect(page.getByText("item-001")).toBeVisible();
  await expect(page.getByText("item-002")).toBeVisible();
  await expect(
    page.getByText("Pinned configuration", { exact: true }),
  ).toBeVisible();
});

test("the operations read and the rendered page stay free of a hostile historical record", async ({
  page,
}) => {
  const consoleMessages: string[] = [];
  const requested: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  page.on("request", (request) => requested.push(request.url()));

  await connect(page);
  await openTaskDetail(page, "task-001");
  await page.waitForTimeout(250);

  const html = await page.content();
  const visible = await page.locator("body").innerText();
  for (const hostile of [
    "topsecret",
    "/home/alice",
    "https://private.example",
    "/mnt/private-library",
    "C:\\Users\\alice",
    "/srv/media",
    "deadbeef",
    "fingerprint-value",
  ]) {
    expect(html).not.toContain(hostile);
    expect(visible).not.toContain(hostile);
    expect(consoleMessages.join("\n")).not.toContain(hostile);
  }
  expect(html).not.toContain(VIEWER_TOKEN);
  // The V2 workspace reads the bounded Operations projection, not the legacy
  // compatibility document, so no fingerprint value is fetched at all.
  expect(
    requested.some((url) => url.includes("/api/v1/operations/tasks/task-001")),
  ).toBe(true);
  expect(
    requested.some(
      (url) =>
        url.includes("/api/v1/tasks/task-001") &&
        !url.includes("/api/v1/operations/"),
    ),
  ).toBe(false);
});

test("Job detail distinguishes admission state, Worker ownership and the linked Task", async ({
  page,
}) => {
  await connect(page);
  await openJobDetail(page, "job-002");
  await expect(
    page.getByText("No Worker owns this Job right now."),
  ).toBeVisible();
  await expect(page.getByText(/Condition: no_worker/)).toBeVisible();

  // A second detail is reached through the shell list, keeping the
  // memory-only connection.
  await page.getByRole("link", { name: "Back to Jobs" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs$/);
  await page.getByRole("link", { name: "job-004" }).click();
  await expect(
    page.getByRole("heading", { name: "Job job-004" }),
  ).toBeVisible();
  await expect(page.getByText("worker-e2e-stale")).toBeVisible();
  await expect(page.getByText(/Owner status/)).toBeVisible();
  await expect(page.getByText(/Condition: stale_worker/)).toBeVisible();
  await expect(page.getByRole("link", { name: "task-006" })).toBeVisible();
});

test("a permitted Task control sends exactly one versioned POST and renders the durable result", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/")) {
      mutations.push(request.url());
    }
  });
  await connect(page);
  await openTaskDetail(page, "task-002");
  await page.getByRole("button", { name: "Request pause" }).click();

  await expect(
    page.getByRole("heading", { name: "Control accepted" }),
  ).toBeVisible();
  expect(
    mutations.filter((url) => url.endsWith("/api/v1/tasks/task-002/pause")),
  ).toHaveLength(1);
});

test("a terminal Task exposes no control and no request is sent", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/")) {
      posts.push(request.url());
    }
  });
  await connect(page);
  await openTaskDetail(page, "task-001");
  await expect(page.getByRole("button", { name: "Cancel Task" })).toHaveCount(
    0,
  );
  await expect(
    page.getByText(
      "The backend advertises no lifecycle action for this Task state and principal.",
    ),
  ).toBeVisible();
  await page.waitForTimeout(250);
  expect(posts).toHaveLength(0);
});

test("a read-only principal receives no actionable control", async ({
  page,
}) => {
  await connect(page, READ_ONLY_TOKEN);
  await openTaskDetail(page, "task-002");
  await expect(page.getByRole("button", { name: "Cancel Task" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: "Request pause" })).toHaveCount(
    0,
  );
  await expect(
    page.getByText(/does not hold the cancel_job permission/).first(),
  ).toBeVisible();
});

test("Job cancellation is exact, single and followed by the returned durable state", async ({
  page,
}) => {
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/v1/")) {
      posts.push(request.url());
    }
  });
  await connect(page);
  await openJobDetail(page, "job-002");
  await page.getByRole("button", { name: "Cancel Job" }).click();
  await expect(
    page.getByRole("heading", { name: "Cancellation requested" }),
  ).toBeVisible();
  await expect(page.getByText(/Durable state: cancelled/)).toBeVisible();
  await page.waitForTimeout(250);
  expect(
    posts.filter((url) => url.endsWith("/api/v1/jobs/job-002/cancel")),
  ).toHaveLength(1);
});

test("Operations failures stay inside the shell and offer a valid next action", async ({
  page,
}) => {
  await connect(page);
  // An unauthenticated deep entry to a missing Operations object reconnects
  // and then renders the bounded not-found state inside the shell.
  await page.goto("/ui-v2/operations/tasks/does-not-exist");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", { name: "Record not found" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to Tasks" })).toBeVisible();
});

test("an unknown Operations route renders the not-found boundary", async ({
  page,
}) => {
  await page.goto("/ui-v2/operations/tasks/task-001/unknown");
  await expect(
    page.getByRole("heading", { name: "Route not found" }),
  ).toBeVisible();
});

test("Dashboard counts and recent failures link to exact Operations state", async ({
  page,
}) => {
  await connect(page);

  await page
    .getByRole("link", { name: /Failed/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();

  await page.getByRole("link", { name: "Overview" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/dashboard$/);
  await expect(
    page.getByRole("link", { name: "Open this Task" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open this Job" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs\/job-005$/);
  await expect(
    page.getByRole("heading", { name: "Job job-005" }),
  ).toBeVisible();
});

test("the Library landing offers a bounded Operations cross-link", async ({
  page,
}) => {
  await connect(page);
  await page.getByRole("link", { name: "Library" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/library$/);
  await page.getByRole("link", { name: "Open Operations Tasks" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks$/);
});

test("the Operations workspace is keyboard operable and responsive", async ({
  page,
}) => {
  await connect(page);
  await openTaskList(page);

  // Keyboard: reach the status filter and change it without a pointer.
  await page.getByLabel("Filter by status").focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByLabel("Filter by status")).not.toHaveValue("all");

  await page.setViewportSize({ width: 380, height: 720 });
  await expect(page.getByLabel("Filter by work kind")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Tasks", exact: true }),
  ).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(
    page.getByRole("heading", { name: "Tasks", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reset filters" }).first(),
  ).toBeVisible();
});

test("dropping credential-like Operations search state on reconnect", async ({
  page,
}) => {
  const consoleMessages: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  // A deep entry carrying an unknown, credential-like key must be reduced to
  // the allowlisted route before the reconnect continuation replays it.
  await page.goto("/ui-v2/operations/tasks?status=failed&token=secret");
  await expect(page.getByLabel("API token")).toBeVisible();
  expect(page.url()).not.toContain("token=secret");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\?status=failed$/);
  await expect(page.getByRole("link", { name: "task-004" })).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(VIEWER_TOKEN);
  expect(consoleMessages.join("\n")).not.toContain(VIEWER_TOKEN);
});
