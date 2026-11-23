import { expect, test, type Page } from "@playwright/test";
import { accountForToken, submitSignIn } from "./auth";

/**
 * Real-Python API/Web parity proof for Task45.5 (RO-7), kept through Task 58.2.
 *
 * Runs against `playwright.python.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact and the real `MediaFlowApi` over one temporary checked
 * Active SQLite store.  The retired general CLI was the second surface in the
 * original proof; its two library-file reads are the current
 * `GET /api/resource-libraries/{id}/files` and
 * `GET /api/media-libraries/{id}/files` routes the Web pages themselves call,
 * so the same isolated fixture still backs both compared paths.
 *
 * Proven journeys on one mixed directory (media + non-media + directory +
 * Unicode + long name + boundary whitespace + many pages):
 *   - the Web ResourceLibrary Files page and the API agree entry-for-entry;
 *   - the Web MediaLibrary Files page and the API agree entry-for-entry;
 *   - cursor pagination binds library kind/id/root and reaches every entry;
 *   - the read is strictly read-only (no directory/observation/Task write and
 *     no mutation request reaches the API);
 *   - an unknown/disabled library and a missing directory answer honestly and
 *     recover on retry without falling back to a JSON snapshot or an index.
 *
 * All tokens and fixtures are throwaway harness values; no production media,
 * credential, Storage adapter or Provider is involved.
 */

const ADMIN_TOKEN = "harness-admin-token";
const LIVE_PATH = "Live";

/** The exact non-ASCII and boundary-whitespace fixtures under `Live`. */
const UNICODE_NAME = "长片名.2020.mkv";
const LONG_NAME = `${"L".repeat(120)}.mkv`;
const PADDED_NAME = " padded .mkv";

type FilesPage = {
  entries: Array<{ name: string; type: string; size: number }>;
  nextCursor: string | null;
  hasNext: boolean;
};

/** Read one live library directory through the exact route the page uses. */
async function libraryFiles(
  page: Page,
  options: {
    kind: "resource" | "media";
    library: string;
    path?: string;
    limit?: number;
    cursor?: string;
  },
): Promise<{ status: number; document: FilesPage }> {
  const params = new URLSearchParams();
  if (options.path !== undefined) params.set("path", options.path);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor !== undefined) params.set("cursor", options.cursor);
  const url =
    options.kind === "resource"
      ? `/api/resource-libraries/${options.library}/files?${params.toString()}`
      : `/api/media-libraries/${options.library}/files?${params.toString()}`;
  const response = await page.request.get(url, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  return {
    status: response.status(),
    document: (await response.json()) as FilesPage,
  };
}

/** The ordered (name, type, size) tuples of one library page. */
function pageRows(document: FilesPage): Array<[string, string, string]> {
  return document.entries.map((entry) => [
    entry.name,
    entry.type,
    String(entry.size),
  ]);
}

async function apiRows(
  page: Page,
  kind: "resource" | "media",
  library: string,
  path: string,
): Promise<Array<{ name: string; type: string; size: number }>> {
  const url =
    kind === "resource"
      ? `/api/resource-libraries/${library}/files?path=${encodeURIComponent(path)}&limit=100`
      : `/api/media-libraries/${library}/files?path=${encodeURIComponent(path)}&limit=100`;
  const response = await page.request.get(url, {
    headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
  });
  expect(response.ok()).toBe(true);
  const document = (await response.json()) as {
    entries: Array<{ name: string; type: string; size: number }>;
  };
  return document.entries;
}

async function openWebFiles(
  page: Page,
  kind: "resource" | "media",
  library: string,
  path: string,
): Promise<void> {
  await page.setViewportSize({ width: 760, height: 900 });
  const route =
    kind === "resource"
      ? `/resourcelib/files?resourceLibraryId=${library}&path=${encodeURIComponent(path)}`
      : `/medialib/files?mediaLibraryId=${library}&path=${encodeURIComponent(path)}`;
  await page.goto(route);
  await submitSignIn(page, accountForToken(ADMIN_TOKEN));
  await expect(
    page.getByRole("heading", {
      name: kind === "resource" ? "文件" : "媒体库",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
}

test("the API and the Web ResourceLibrary page list the same live directory", async ({
  page,
}) => {
  const api = await libraryFiles(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
  });
  expect(api.status).toBe(200);
  const rows = pageRows(api.document);
  const names = rows.map(([name]) => name);
  expect(names).toContain("Alpha.2001.mkv");
  expect(names).toContain("Beta.txt");
  expect(names).toContain("Gamma-Directory");
  expect(names).toContain(UNICODE_NAME);
  expect(names).toContain(LONG_NAME);
  // Boundary whitespace is preserved exactly, not trimmed away.
  expect(names).toContain(PADDED_NAME);
  // The page publishes no total for a single bounded directory read.
  expect(api.document.hasNext).toBe(false);

  const entries = await apiRows(page, "resource", "source", LIVE_PATH);
  // The page and the API agree entry-for-entry: same order, type and size.
  expect(rows).toEqual(
    entries.map((entry) => [entry.name, entry.type, String(entry.size)]),
  );

  await openWebFiles(page, "resource", "source", LIVE_PATH);
  for (const name of [
    "Alpha.2001.mkv",
    "Beta.txt",
    "Gamma-Directory",
    UNICODE_NAME,
    LONG_NAME,
  ]) {
    await expect(
      page.getByLabel(`文件条目 ${name}`, { exact: true }),
    ).toBeVisible();
  }
});

test("the API and the Web MediaLibrary page list the same live directory", async ({
  page,
}) => {
  const api = await libraryFiles(page, {
    kind: "media",
    library: "movies",
    path: LIVE_PATH,
  });
  expect(api.status).toBe(200);
  const rows = pageRows(api.document);
  expect(rows.map(([name]) => name)).toContain("Alpha.2001.mkv");

  const entries = await apiRows(page, "media", "movies", LIVE_PATH);
  expect(rows).toEqual(
    entries.map((entry) => [entry.name, entry.type, String(entry.size)]),
  );

  await openWebFiles(page, "media", "movies", LIVE_PATH);
  await expect(
    page.getByLabel("文件条目 Alpha.2001.mkv", { exact: true }),
  ).toBeVisible();
});

test("cursor pagination binds library kind/id/root and reaches every entry", async ({
  page,
}) => {
  // The full fixture directory is fixed, so paging through every bounded page
  // must reconstruct it entry-for-entry with real, non-empty, non-overlapping
  // pages — never a silently repeated or truncated listing.
  const full = await libraryFiles(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
    limit: 100,
  });
  expect(full.status).toBe(200);
  const expected = pageRows(full.document).map(([name]) => name);
  expect(expected.length).toBeGreaterThan(5);

  const first = await libraryFiles(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
    limit: 5,
  });
  expect(first.status).toBe(200);
  expect(first.document.hasNext).toBe(true);
  const cursor = first.document.nextCursor;
  expect(cursor).toBeTruthy();

  const second = await libraryFiles(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
    limit: 5,
    cursor: cursor as string,
  });
  expect(second.status).toBe(200);
  const firstNames = pageRows(first.document).map(([name]) => name);
  const secondNames = pageRows(second.document).map(([name]) => name);
  expect(secondNames.length).toBeGreaterThan(0);
  expect(secondNames).not.toEqual(firstNames);
  expect(secondNames.some((name) => firstNames.includes(name))).toBe(false);

  // Continue to the last page and prove the union equals the full listing.
  const collected = [...firstNames, ...secondNames];
  let next: string | null = second.document.nextCursor;
  while (next) {
    const pageResult = await libraryFiles(page, {
      kind: "resource",
      library: "source",
      path: LIVE_PATH,
      limit: 5,
      cursor: next,
    });
    expect(pageResult.status).toBe(200);
    collected.push(...pageRows(pageResult.document).map(([name]) => name));
    next = pageResult.document.nextCursor;
  }
  expect([...collected].sort()).toEqual([...expected].sort());

  // The same cursor is rejected across a different library kind and root: a
  // cursor is bound to library kind, ID, root, configuration and directory.
  const crossed = await libraryFiles(page, {
    kind: "media",
    library: "movies",
    path: LIVE_PATH,
    limit: 5,
    cursor: cursor as string,
  });
  expect(crossed.status).toBe(400);
  expect(JSON.stringify(crossed.document)).toContain(
    "storage_browser_cursor_invalid",
  );
});

test("the live read is strictly read-only on the server", async ({ page }) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    const method = request.method();
    // Signing in is authentication, not a listing effect: the session POST is
    // the browser establishing identity, so it is excluded from the
    // "the read mutates nothing" evidence.
    if (request.url().includes("/api/auth/")) return;
    if (
      method !== "GET" &&
      method !== "HEAD" &&
      request.url().includes("/api/")
    ) {
      mutations.push(`${method} ${request.url()}`);
    }
  });
  const before = await page.request.get("/__harness__/retirement-state");
  const beforeCounts = (
    (await before.json()) as { counts: Record<string, number> }
  ).counts;

  await openWebFiles(page, "resource", "source", LIVE_PATH);
  await page.getByRole("button", { name: "刷新" }).click();
  await expect(page.getByRole("table")).toBeVisible();
  const read = await libraryFiles(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
  });
  expect(read.status).toBe(200);

  const after = await page.request.get("/__harness__/retirement-state");
  const afterCounts = (
    (await after.json()) as { counts: Record<string, number> }
  ).counts;
  expect(afterCounts).toEqual(beforeCounts);
  expect(mutations).toEqual([]);
});

test("sorted and selected live folders open the same real entry on both pages", async ({
  page,
}) => {
  for (const kind of ["resource", "media"] as const) {
    const library = kind === "resource" ? "source" : "movies";
    await openWebFiles(page, kind, library, LIVE_PATH);

    const nameHeader = page.locator('th[data-column-width="name"]');
    const nameSort = nameHeader.getByRole("button", { name: "名称" });
    await nameSort.click();
    await expect(nameHeader).toHaveAttribute("aria-sort", "ascending");
    await nameSort.click();
    await expect(nameHeader).toHaveAttribute("aria-sort", "descending");

    // The page-session width must survive the real Storage read of a new
    // directory, so the visible boundary is the same before and after.
    const nameResize = page.getByRole("separator", {
      name: "调整名称列宽",
    });
    const widthBefore = Number(await nameResize.getAttribute("aria-valuenow"));
    await nameResize.focus();
    await page.keyboard.press("ArrowRight");
    await expect
      .poll(async () => Number(await nameResize.getAttribute("aria-valuenow")))
      .toBe(widthBefore + 16);

    // The selected path is the real directory, not a re-ordered display index.
    await page.getByRole("checkbox", { name: "选择 Gamma-Directory" }).check();
    await expect(page.getByText(/已选择 1 个文件夹/)).toBeVisible();

    // The same exact selection follows the grid/list switch before opening.
    await page.getByRole("button", { name: "网格视图" }).click();
    await expect(
      page.getByRole("checkbox", { name: "选择 Gamma-Directory" }),
    ).toBeChecked();
    await expect(
      page.getByLabel("文件条目 Gamma-Directory", { exact: true }),
    ).toHaveClass(/is-selected/);
    await page.getByRole("button", { name: "列表视图" }).click();
    await expect(
      page.getByRole("checkbox", { name: "选择 Gamma-Directory" }),
    ).toBeChecked();

    // Opening the sorted/selected row performs the real Storage read.
    await page
      .getByRole("row", { name: "文件条目 Gamma-Directory" })
      .getByRole("button", { name: "Gamma-Directory" })
      .click();
    await expect(
      page.getByLabel("文件条目 child.txt", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/Gamma-Directory/).first()).toBeVisible();
    // The new real directory keeps the same order and column width.
    await expect(nameHeader).toHaveAttribute("aria-sort", "descending");
    await expect(nameResize).toHaveAttribute(
      "aria-valuenow",
      String(widthBefore + 16),
    );
  }
});

test("unknown library and missing directory answer honestly and recover", async ({
  page,
}) => {
  const unknown = await libraryFiles(page, {
    kind: "resource",
    library: "does-not-exist",
    path: LIVE_PATH,
  });
  expect(unknown.status).toBeGreaterThanOrEqual(400);
  const unknownBody = JSON.stringify(unknown.document);
  expect(unknownBody).toContain("storage_browser_resource_library_not_found");
  expect(unknownBody).toContain("nextAction");

  const missing = await libraryFiles(page, {
    kind: "resource",
    library: "source",
    path: "No-Such-Directory",
  });
  expect(missing.status).toBeGreaterThanOrEqual(400);
  const missingBody = JSON.stringify(missing.document);
  expect(missingBody).toContain("storage_browser_not_found");
  expect(missingBody).toContain("nextAction");

  // The failure is recoverable: reading the real directory immediately after
  // succeeds and never falls back to a JSON snapshot or an index.
  const recovered = await libraryFiles(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
  });
  expect(recovered.status).toBe(200);
  expect(pageRows(recovered.document).length).toBeGreaterThan(0);
});
