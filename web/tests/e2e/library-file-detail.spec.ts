import { expect, test, type Page } from "@playwright/test";

const VIEWER_TOKEN = "e2e-viewer-token";

function apiRequestsOf(page: Page): Array<{ url: string; method: string }> {
  const seen: Array<{ url: string; method: string }> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      seen.push({ url: request.url(), method: request.method() });
    }
  });
  return seen;
}

async function connectAs(page: Page, token = VIEWER_TOKEN): Promise<void> {
  await page.getByLabel("API token").fill(token);
  await page.getByRole("button", { name: "Connect" }).click();
}

test("catalog detail preserves query context and exposes bounded evidence", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  await page.goto(
    "/ui-v2/library/file-index?query=Example&processingDisposition=organized",
  );
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  await connectAs(page);

  await page.getByRole("link", { name: "Example.mkv" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/library\/file-index\/file-index-example\?q_query=Example&q_processingDisposition=organized/,
  );
  await expect(
    page.getByRole("heading", { name: "FileIndex record" }),
  ).toBeVisible();
  for (const heading of [
    "Source and library",
    "Discovery and stability",
    "Current occurrence",
    "Processing state",
    "Identity and policy evidence",
    "Task items",
    "Related reviews",
    "Organize evidence",
    "Reprocess eligibility",
    "Manual operations",
  ]) {
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
  await expect(
    page.getByText(
      "only the algorithm name is displayed; fingerprint values are never exposed to this page.",
    ),
  ).toBeVisible();
  await expect(page.getByText("Reprocess this record")).toBeVisible();
  await expect(page.getByText(VIEWER_TOKEN)).toHaveCount(0);
  await expect(page.url()).not.toContain("fingerprint");
  await expect(page.url()).not.toContain("token");

  await page.getByRole("link", { name: "Back to FileIndex catalog" }).click();
  await expect(page).toHaveURL(
    /\/ui-v2\/library\/file-index\?query=Example&processingDisposition=organized/,
  );
  await expect(page.getByText("Example.mkv", { exact: true })).toBeVisible();
  expect(requests.every((request) => request.method === "GET")).toBe(true);
  expect(requests.every((request) => !request.url.includes(VIEWER_TOKEN))).toBe(
    true,
  );
});

test("detail distinguishes current historical legacy missing and truncated facts", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/file-index/file-index-example");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "FileIndex record" }),
  ).toBeVisible();
  for (const label of [
    "Title Candidate",
    "Recognition Type ID",
    "Provider ID",
    "Directory",
    "Relative Destination",
    "Target",
    "Checkpoint stage",
  ]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(
    page.getByText("The parser used bounded filename facts."),
  ).toBeVisible();
  await expect(
    page.getByText(/historical different occurrence/i),
  ).toBeVisible();

  await page.goto("/ui-v2/library/file-index/file-index-legacy");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "FileIndex record" }),
  ).toBeVisible();
  await expect(page.getByText("Legacy", { exact: true })).toBeVisible();
  await expect(
    page.getByText(/Only historical Results are available/),
  ).toBeVisible();
  await expect(
    page.getByText(/Legacy evidence was not captured/).first(),
  ).toBeVisible();
  await expect(page.getByText(/checkpoint not available/)).toBeVisible();
  await expect(page.getByText("Open physical location")).toBeVisible();

  await page.goto("/ui-v2/library/file-index/file-index-missing-evidence");
  await connectAs(page);
  await expect(
    page.getByText(
      "Evidence is unavailable for this record. This page does not re-collect evidence.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("No organize Result records are attached to this entry."),
  ).toBeVisible();
  await expect(
    page.getByText("No bounded task-item records reference this entry."),
  ).toBeVisible();

  await page.goto("/ui-v2/library/file-index/file-index-truncated");
  await connectAs(page);
  for (const label of [
    "occurrenceHistory",
    "review",
    "evidence",
    "items",
    "results",
  ]) {
    await expect(
      page.getByText(new RegExp("More " + label + " records exist")),
    ).toBeVisible();
  }
  await expect(
    page
      .getByText(
        "More bounded facts exist for this section; they were not loaded.",
      )
      .first(),
  ).toBeVisible();

  await page.goto("/ui-v2/library/file-index/file-index-mismatched");
  await connectAs(page);
  await expect(
    page.getByText(
      /Storage and ResourceLibrary are not a matching enabled pair/,
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open physical location" }),
  ).toHaveCount(0);
});

test("direct detail entry and refresh retain memory-only auth continuation", async ({
  page,
}) => {
  await page.goto(
    "/ui-v2/library/file-index/file-index-example?q_query=Example&q_storage=local-media",
  );
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await connectAs(page);
  await expect(page).toHaveURL(
    /file-index-example\?q_query=Example&q_storage=local-media/,
  );
  await expect(
    page.getByRole("heading", { name: "FileIndex record" }),
  ).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(/\/ui-v2\/$/);
  await expect(page.getByRole("heading", { name: "V2 entry" })).toBeVisible();
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    cookie: document.cookie,
  }));
  expect(storage).toEqual({ local: 0, session: 0, cookie: "" });
  await connectAs(page);
  await expect(page).toHaveURL(
    /file-index-example\?q_query=Example&q_storage=local-media/,
  );
});

test("physical membership uses one explicit resolver GET and returns to safe context", async ({
  page,
}) => {
  const requests = apiRequestsOf(page);
  await page.goto("/ui-v2/library/files?storage=local-media");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "Local media" }),
  ).toBeVisible();
  expect(
    requests.filter((request) =>
      request.url.includes("/api/v1/files/by-source"),
    ),
  ).toHaveLength(0);

  const row = page
    .getByRole("listitem")
    .filter({ hasText: "show.mkv" })
    .first();
  await row.getByRole("button", { name: "Check indexed link" }).click();
  await expect(
    page.getByText(/A unique current FileIndex record was confirmed/),
  ).toBeVisible();
  await expect(
    row.getByRole("link", { name: "Open indexed record" }),
  ).toBeVisible();
  await expect
    .poll(
      () =>
        requests.filter((request) =>
          request.url.includes("/api/v1/files/by-source"),
        ).length,
    )
    .toBe(1);
  const resolverRequest = requests.find((request) =>
    request.url.includes("/api/v1/files/by-source"),
  );
  expect(resolverRequest?.url).toContain("resourceLibrary=resources");
  expect(resolverRequest?.method).toBe("GET");

  await row.getByRole("link", { name: "Open indexed record" }).click();
  await expect(
    page.getByRole("heading", { name: "FileIndex record" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open physical location" }).click();
  await expect(page).toHaveURL(/\/ui-v2\/library\/files\?/);
  await expect(page).toHaveURL(/storage=local-media/);
  await expect(page).toHaveURL(/resourceLibrary=resources/);
  await expect(page).toHaveURL(/path=Movies/);
  await expect(
    page.getByRole("heading", { name: "Local media" }),
  ).toBeVisible();
  expect(requests.every((request) => request.method === "GET")).toBe(true);
});

test("missing, ambiguous, malformed and unavailable resolver states never select a record", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/files?storage=local-media");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "Local media" }),
  ).toBeVisible();

  const ambiguous = page
    .getByRole("listitem")
    .filter({ hasText: "ambiguous.mkv" })
    .first();
  await ambiguous.getByRole("button", { name: "Check indexed link" }).click();
  await expect(page.getByText(/multiple FileIndex matches/)).toBeVisible();
  await expect(
    ambiguous.getByRole("link", { name: "Open indexed record" }),
  ).toHaveCount(0);

  const missing = page
    .getByRole("listitem")
    .filter({ hasText: "missing-link.mkv" })
    .first();
  await missing.getByRole("button", { name: "Check indexed link" }).click();
  await expect(
    page.getByText(/No current FileIndex record matches/),
  ).toBeVisible();
  await expect(
    missing.getByRole("link", { name: "Open indexed record" }),
  ).toHaveCount(0);

  const unavailable = page
    .getByRole("listitem")
    .filter({ hasText: "unavailable.mkv" })
    .first();
  await unavailable.getByRole("button", { name: "Check indexed link" }).click();
  await expect(
    page.getByText(/indexed link could not be checked/),
  ).toBeVisible();
  await expect(
    unavailable.getByRole("link", { name: "Open indexed record" }),
  ).toHaveCount(0);

  const malformed = page
    .getByRole("listitem")
    .filter({ hasText: "malformed.mkv" })
    .first();
  await malformed.getByRole("button", { name: "Check indexed link" }).click();
  await expect(
    page.getByRole("heading", { name: "Indexed link unavailable" }),
  ).toBeVisible();
  await expect(
    malformed.getByRole("link", { name: "Open indexed record" }),
  ).toHaveCount(0);
});

test("detail not-found, unavailable, 401 and 403 states remain bounded", async ({
  page,
}) => {
  await page.goto("/ui-v2/library/file-index/does-not-exist");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "FileIndex record not found" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Back to FileIndex catalog" }),
  ).toBeVisible();

  await page.goto("/ui-v2/library/file-index/file-index-malformed");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "FileIndex detail unavailable" }),
  ).toBeVisible();
  await expect(page.getByText(/expected read-only contract/)).toBeVisible();

  await page.goto("/ui-v2/library/file-index/file-index-unavailable");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "FileIndex detail unavailable" }),
  ).toBeVisible();

  await page.goto("/ui-v2/library/file-index/file-index-unauthorized");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "Not authorized" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/file-index-unauthorized/);

  await page.goto("/ui-v2/library/file-index/file-index-forbidden");
  await connectAs(page);
  await expect(page.getByRole("heading", { name: "Forbidden" })).toBeVisible();
  await expect(page).toHaveURL(/file-index-forbidden/);
});

test("detail remains keyboard-usable at a narrow viewport and offers no V2 work control", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ui-v2/library/file-index/file-index-example");
  await connectAs(page);
  await expect(
    page.getByRole("heading", { name: "FileIndex record" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Back to FileIndex catalog" }).focus();
  await expect(
    page.getByRole("link", { name: "Back to FileIndex catalog" }),
  ).toBeFocused();
  await expect(page.getByRole("button", { name: /reprocess/i })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /scan|organize|preview/i }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Open current Web UI" }),
  ).toBeVisible();
});
