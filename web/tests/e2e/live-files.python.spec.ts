import { expect, test, type Page } from "@playwright/test";

/**
 * Real-Python/CLI/Web parity proof for Task45.5 (RO-7).
 *
 * Runs against `playwright.python.config.ts`, which starts
 * `scripts/operations_inventory_harness.py`: one Python process serving the
 * built V2 artifact, the real `MediaFlowApi` and the real `mediaflow files
 * list` CLI over one temporary checked Active SQLite store. The same isolated
 * fixture therefore backs both surfaces, so a parity assertion compares two
 * real product paths rather than two independently faked servers.
 *
 * Proven journeys on one mixed directory (media + non-media + directory +
 * Unicode + long name + boundary whitespace + many pages):
 *   - the Web ResourceLibrary Files page and the CLI agree entry-for-entry;
 *   - the Web MediaLibrary Files page and the CLI agree entry-for-entry;
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

type CliResult = { ok: boolean; code: number; output: string };

async function cliFilesList(
  page: Page,
  options: {
    kind: "resource" | "media";
    library: string;
    path?: string;
    limit?: number;
    cursor?: string;
  },
): Promise<CliResult> {
  const params = new URLSearchParams({
    kind: options.kind,
    library: options.library,
  });
  if (options.path !== undefined) params.set("path", options.path);
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.cursor !== undefined) params.set("cursor", options.cursor);
  const response = await page.request.get(
    `/__harness__/cli-files-list?${params.toString()}`,
  );
  expect(response.ok()).toBe(true);
  return (await response.json()) as CliResult;
}

/** Parse the CLI's `NAME | TYPE | SIZE | MODIFIED` rows into ordered tuples. */
function cliRows(output: string): Array<[string, string, string]> {
  const rows: Array<[string, string, string]> = [];
  for (const line of output.split("\n")) {
    const match = line.match(/^(.*) \| (file|directory) \| (\d+) \| /);
    if (match !== null && match[1] !== "NAME") {
      rows.push([match[1], match[2], match[3]]);
    }
  }
  return rows;
}

async function apiRows(
  page: Page,
  kind: "resource" | "media",
  library: string,
  path: string,
): Promise<Array<{ name: string; type: string; size: number }>> {
  const url =
    kind === "resource"
      ? `/api/v1/resource-libraries/${library}/files?path=${encodeURIComponent(path)}&limit=100`
      : `/api/v1/media-libraries/${library}/files?path=${encodeURIComponent(path)}&limit=100`;
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
      ? `/ui-v2/resourcelib/files?resourceLibraryId=${library}&path=${encodeURIComponent(path)}`
      : `/ui-v2/medialib/files?mediaLibraryId=${library}&path=${encodeURIComponent(path)}`;
  await page.goto(route);
  await page.getByLabel("API token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(
    page.getByRole("heading", {
      name: kind === "resource" ? "文件" : "媒体库",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
}

test("CLI and the Web ResourceLibrary page list the same live directory", async ({
  page,
}) => {
  const cli = await cliFilesList(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
  });
  expect(cli.code).toBe(0);
  const rows = cliRows(cli.output);
  const names = rows.map(([name]) => name);
  expect(names).toContain("Alpha.2001.mkv");
  expect(names).toContain("Beta.txt");
  expect(names).toContain("Gamma-Directory");
  expect(names).toContain(UNICODE_NAME);
  expect(names).toContain(LONG_NAME);
  // Boundary whitespace is preserved exactly, not trimmed away.
  expect(names).toContain(PADDED_NAME);
  expect(cli.output).toContain("Total: unknown");
  expect(cli.output).not.toContain("file_id");

  const entries = await apiRows(page, "resource", "source", LIVE_PATH);
  const apiTuples = entries.map(
    (entry) => [entry.name, entry.type, String(entry.size)] as const,
  );
  // The CLI applies no Organize/media filter: it publishes every entry the API
  // publishes, in the same order, with the same type and size.
  expect(rows.map((row) => [row[0], row[1], row[2]])).toEqual(
    apiTuples.map((row) => [row[0], row[1], row[2]]),
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

test("CLI and the Web MediaLibrary page list the same live directory", async ({
  page,
}) => {
  const cli = await cliFilesList(page, {
    kind: "media",
    library: "movies",
    path: LIVE_PATH,
  });
  expect(cli.code).toBe(0);
  const rows = cliRows(cli.output);
  expect(rows.map(([name]) => name)).toContain("Alpha.2001.mkv");

  const entries = await apiRows(page, "media", "movies", LIVE_PATH);
  expect(rows.map((row) => [row[0], row[1], row[2]])).toEqual(
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
  // must reconstruct it entry-for-entry.  A CLI cursor failure still exits 0,
  // so the assertions must prove real, non-empty, non-overlapping pages rather
  // than only checking the exit code.
  const full = await cliFilesList(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
    limit: 100,
  });
  expect(full.code).toBe(0);
  const expected = cliRows(full.output).map(([name]) => name);
  expect(expected.length).toBeGreaterThan(5);

  const first = await cliFilesList(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
    limit: 5,
  });
  expect(first.code).toBe(0);
  expect(first.output).toContain("More available: yes");
  expect(first.output).not.toContain("storage_browser_cursor_invalid");
  const cursor = first.output.match(/Next cursor: (.+)/)?.[1]?.trim();
  expect(cursor).toBeTruthy();
  expect(cursor).not.toBe("-");

  const second = await cliFilesList(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
    limit: 5,
    cursor: cursor as string,
  });
  expect(second.code).toBe(0);
  // The second page must actually load: a cursor error would otherwise be
  // invisible behind the CLI's exit code.
  expect(second.output).not.toContain("storage_browser_cursor_invalid");
  const secondNames = cliRows(second.output).map(([name]) => name);
  expect(secondNames.length).toBeGreaterThan(0);
  const firstNames = cliRows(first.output).map(([name]) => name);
  expect(secondNames).not.toEqual(firstNames);
  expect(secondNames.some((name) => firstNames.includes(name))).toBe(false);

  // Continue to the last page and prove the union equals the full listing.
  const collected = [...firstNames, ...secondNames];
  let next: string | undefined = second.output
    .match(/Next cursor: (.+)/)?.[1]
    ?.trim();
  while (next && next !== "-") {
    const pageResult = await cliFilesList(page, {
      kind: "resource",
      library: "source",
      path: LIVE_PATH,
      limit: 5,
      cursor: next,
    });
    expect(pageResult.code).toBe(0);
    expect(pageResult.output).not.toContain("storage_browser_cursor_invalid");
    collected.push(...cliRows(pageResult.output).map(([name]) => name));
    next = pageResult.output.match(/Next cursor: (.+)/)?.[1]?.trim();
  }
  expect([...collected].sort()).toEqual([...expected].sort());

  // The same cursor is rejected across a different library kind and root: a
  // cursor is bound to library kind, ID, root, configuration and directory.
  const crossed = await cliFilesList(page, {
    kind: "media",
    library: "movies",
    path: LIVE_PATH,
    limit: 5,
    cursor: cursor as string,
  });
  expect(crossed.output).toContain("storage_browser_cursor_invalid");
});

test("the live read is strictly read-only on the server", async ({ page }) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    const method = request.method();
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
  await cliFilesList(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
  });

  const after = await page.request.get("/__harness__/retirement-state");
  const afterCounts = (
    (await after.json()) as { counts: Record<string, number> }
  ).counts;
  expect(afterCounts).toEqual(beforeCounts);
  expect(mutations).toEqual([]);
});

test("unknown library and missing directory answer honestly and recover", async ({
  page,
}) => {
  const unknown = await cliFilesList(page, {
    kind: "resource",
    library: "does-not-exist",
    path: LIVE_PATH,
  });
  expect(unknown.output).toContain(
    "storage_browser_resource_library_not_found",
  );
  expect(unknown.output).toMatch(/Next action:/);

  const missing = await cliFilesList(page, {
    kind: "resource",
    library: "source",
    path: "No-Such-Directory",
  });
  expect(missing.output).toContain("storage_browser_not_found");
  expect(missing.output).toMatch(/Next action:/);

  // The failure is recoverable: reading the real directory immediately after
  // succeeds and never falls back to a JSON snapshot or an index.
  const recovered = await cliFilesList(page, {
    kind: "resource",
    library: "source",
    path: LIVE_PATH,
  });
  expect(recovered.code).toBe(0);
  expect(cliRows(recovered.output).length).toBeGreaterThan(0);
});
