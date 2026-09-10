import { expect, test } from "@playwright/test";

/**
 * Browser proof for the V2 Operations workspace journey.
 *
 * It runs against the built V2 artifact plus the local fake API: no
 * production credentials, media, Storage or external providers are used.
 */

const VIEWER_TOKEN = "e2e-viewer-token";

async function connect(page: import("@playwright/test").Page) {
  await page.goto("/ui-v2/");
  await page.getByLabel("API token").fill(VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

test("Operations landing shows Worker readiness and workspace links", async ({
  page,
}) => {
  await connect(page);

  // Navigate to Operations via shell nav link.
  await page.getByRole("link", { name: "Operations" }).click();

  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  // The page context shows "Operations"; wait for the component to load.
  await expect(
    page.getByRole("heading", { name: "Worker readiness" }),
  ).toBeVisible();

  // Workspace links are present.
  await expect(
    page.getByRole("link", { name: "Tasks" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Jobs" }).first(),
  ).toBeVisible();
});

test("Task list shows tasks and links to detail", async ({ page }) => {
  await connect(page);

  // Navigate to Tasks via the landing page link.
  await page.getByRole("link", { name: "Operations" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await page.getByRole("link", { name: "Tasks" }).first().click();

  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks$/);
  // Wait for the table to appear.
  await expect(page.getByRole("link", { name: "task-001" })).toBeVisible();
  await expect(page.getByRole("link", { name: "task-002" })).toBeVisible();

  // Click into task detail.
  await page.getByRole("link", { name: "task-001" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks\/task-001$/);
  await expect(
    page.getByRole("heading", { name: /Task task-001/ }),
  ).toBeVisible();
});

test("Job list shows jobs and links to detail", async ({ page }) => {
  await connect(page);

  // Navigate to Jobs via the landing page link.
  await page.getByRole("link", { name: "Operations" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations$/);
  await page.getByRole("link", { name: "Jobs" }).first().click();

  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs$/);
  // Wait for the table to appear.
  await expect(page.getByRole("link", { name: "job-001" })).toBeVisible();

  // Click into job detail.
  await page.getByRole("link", { name: "job-001" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/jobs\/job-001$/);
  await expect(
    page.getByRole("heading", { name: /Job job-001/ }),
  ).toBeVisible();
});

test("Dashboard Task/Job counts link to Operations lists", async ({
  page,
}) => {
  await connect(page);

  // Dashboard shows "View all →" links for Tasks and Jobs.
  const viewAllTasks = page.getByRole("link", { name: "View all →" }).first();
  await expect(viewAllTasks).toBeVisible();
  await viewAllTasks.click();
  await expect(page).toHaveURL(/\/ui-v2\/operations\/tasks$/);
  // Wait for task data to load.
  await expect(page.getByRole("link", { name: "task-001" })).toBeVisible();
});
