import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

const TOKEN = "operations-inventory-token";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(
  implementation: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function runDocument(overrides: Record<string, unknown> = {}) {
  return {
    run_kind: "task",
    run_id: "task-001",
    command: "scan",
    command_label: "扫描",
    recognized_command: true,
    status: "running",
    trigger: "manual",
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:06:00+00:00",
    job_id: null,
    task_id: "task-001",
    schedule_id: null,
    definition_id: null,
    source_scope: "Movies",
    target_scope: null,
    library_kind: "resource",
    total_items: 4,
    completed_items: 1,
    failed_items: 0,
    pause_requested: false,
    attention: false,
    configuration_snapshot_id: "snap-1",
    worker_id: null,
    sideEffects: "none",
    ...overrides,
  };
}

function pageDocument(overrides: Record<string, unknown> = {}) {
  return {
    items: [runDocument()],
    limit: 20,
    status: null,
    command: null,
    q: null,
    from: null,
    to: null,
    attention: false,
    total: 1,
    truncated: false,
    status_counts: { running: 1 },
    attention_count: 0,
    population:
      "unified job/task run inventory, deduplicated by explicit task linkage",
    sideEffects: "none",
    previous_cursor: null,
    next_cursor: null,
    ...overrides,
  };
}

function readinessPayload(overrides: Record<string, unknown> = {}) {
  return {
    ready: true,
    condition: "ready",
    category: null,
    durableState: "resident processing worker is live and ready",
    sideEffects: "none",
    retrySafe: true,
    nextAction: "none",
    activeWorkersCount: 1,
    activeSnapshotId: "snap-1",
    expectedRuntimeSchemaVersion: 41,
    ...overrides,
  };
}

function managementReadinessPayload() {
  return {
    available: true,
    infrastructureReady: true,
    asOf: "2026-08-22T12:00:00+00:00",
    sideEffects: "none",
    infrastructure: { services: {} },
  };
}

function manualActionsPayload() {
  return {
    scopeKind: null,
    scopeId: null,
    fileId: null,
    resourceLibraryId: null,
    selectionRequired: true,
    source: null,
    resourceLibraries: [
      {
        resourceLibraryId: "resources",
        storageId: "local",
        scanMode: null,
        enabled: true,
        reason: null,
      },
    ],
    runtime: { ready: true, condition: "ready", nextAction: null },
    actions: {
      scan: { available: true, reason: null },
      preview: { available: true, reason: null },
      organize: { available: false, reason: "not advertised" },
    },
    limits: { previewMaxItems: 100 },
  };
}

/**
 * A fetch stub serving the full inventory journey: the unified run page, the
 * Worker readiness, the resident-service readiness and the manual action
 * matrix the landing composes.
 */
function stubInventoryJourney(
  page: Record<string, unknown>,
  requested: string[] = [],
) {
  return stubFetch(async (input) => {
    const url = String(input);
    requested.push(url);
    if (
      url.startsWith("/api/v1/operations/runs?") ||
      url === "/api/v1/operations/runs"
    ) {
      return jsonResponse(page);
    }
    if (url === "/api/v1/workers/readiness") {
      return jsonResponse(readinessPayload());
    }
    if (url === "/api/v1/management/readiness") {
      return jsonResponse(managementReadinessPayload());
    }
    if (url.startsWith("/api/v1/operations/manual-actions")) {
      return jsonResponse(manualActionsPayload());
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
}

describe("Operations run inventory landing", () => {
  it("renders the reference-aligned Chinese inventory with real data", async () => {
    const requested: string[] = [];
    stubInventoryJourney(
      pageDocument({
        items: [
          runDocument(),
          runDocument({
            run_id: "job-002",
            run_kind: "job",
            job_id: "job-002",
            task_id: null,
            command: "preview",
            command_label: "预览",
            status: "pending",
            attention: true,
            source_scope: null,
            trigger: "scheduled",
            definition_id: "def-1",
          }),
          runDocument({
            run_id: "legacy-003",
            command: "legacy_historic_work",
            command_label: null,
            recognized_command: false,
            status: "failed",
            attention: true,
          }),
        ],
        status_counts: { running: 1, pending: 1, failed: 1 },
        attention_count: 2,
        total: 3,
      }),
      requested,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "操作与任务" });
    // Chinese business labels describe operation and state.
    expect((await screen.findAllByText("扫描")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("预览")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("失败").length).toBeGreaterThan(0);
    // The unknown legacy command stays honest.
    expect(screen.getByText(/未识别的历史命令/)).toBeVisible();
    // Missing historical scope evidence is explicitly unavailable.
    expect(screen.getByText("不可用")).toBeVisible();
    // The attention card labels its overlapping facet semantics.
    expect(
      screen.getByText(/需要关注（与状态计数重叠，不是独立终态）/),
    ).toBeVisible();
    // Worker readiness and manual entries stay discoverable.
    expect((await screen.findAllByText(/Worker 就绪/)).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByRole("link", { name: "发起受限扫描" })).toBeVisible();
    expect(
      requested.some((url) => url.includes("/api/v1/operations/runs")),
    ).toBe(true);
  });

  it("submits server filters, applies card filters and resets to the same population", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubInventoryJourney(pageDocument({ items: [], total: 0 }), requested);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "操作与任务" });
    await waitFor(() =>
      expect(
        requested.some((url) => url.includes("/api/v1/operations/runs")),
      ).toBe(true),
    );
    expect(
      await screen.findByRole("heading", { name: "还没有运行记录" }),
    ).toBeVisible();

    await user.type(screen.getByLabelText("搜索"), "电影");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    await waitFor(() =>
      expect(
        requested.some((url) => url.includes("q=%E7%94%B5%E5%BD%B1")),
      ).toBe(true),
    );

    await user.selectOptions(screen.getByLabelText("状态"), "failed");
    await waitFor(() =>
      expect(requested.some((url) => url.includes("status=failed"))).toBe(true),
    );

    await user.click(screen.getAllByRole("button", { name: "重置筛选" })[0]!);
    await waitFor(() =>
      expect(
        requested.some(
          (url) =>
            url.includes("/api/v1/operations/runs") &&
            !url.includes("status=failed") &&
            !url.includes("q="),
        ),
      ).toBe(true),
    );
  });

  it("selects a run into the overview panel and closes back to the list", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    let overviewRead = false;
    const fetchMock = stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        overviewRead = true;
        return jsonResponse(runDocument({ target_scope: "Library/History" }));
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse(readinessPayload());
      }
      if (url === "/api/v1/management/readiness") {
        return jsonResponse(managementReadinessPayload());
      }
      if (url.startsWith("/api/v1/operations/manual-actions")) {
        return jsonResponse(manualActionsPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /扫描/ }));
    await waitFor(() => expect(overviewRead).toBe(true));
    const detail = await screen.findByRole("region", { name: "运行详情" });
    expect(await within(detail).findByText("手动")).toBeVisible();
    expect(within(detail).getByText(/进行中/)).toBeVisible();
    // The overview shows known durable facts and labels completed items as
    // not an organize-success claim while running.
    expect(within(detail).getByText(/不代表最终整理成功/)).toBeVisible();
    // The historical source and target scope the projection publishes are
    // part of the visible overview (absent evidence renders explicitly).
    expect(within(detail).getByText("Movies")).toBeVisible();
    expect(within(detail).getByText("Library/History")).toBeVisible();
    // A deep evidence link to the exact existing Task detail route.
    expect(
      within(detail).getByRole("link", { name: "打开 Task 详情" }),
    ).toHaveAttribute("href", "/ui-v2/operations/tasks/task-001");

    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "运行详情" })).toBeNull(),
    );
    expect(fetchMock).toHaveBeenCalled();
  });

  it("opens a supported deep link to the selected run and keeps list context", async () => {
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(runDocument());
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse(readinessPayload());
      }
      if (url === "/api/v1/management/readiness") {
        return jsonResponse(managementReadinessPayload());
      }
      if (url.startsWith("/api/v1/operations/manual-actions")) {
        return jsonResponse(manualActionsPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&status=running");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    await within(detail).findByText(/进行中/);
    // The bounded list context survives beside the panel.
    expect(await screen.findByRole("table")).toBeVisible();
    expect(
      requested.some(
        (url) => url.includes("status=running") && url.includes("limit=20"),
      ),
    ).toBe(true);
  });

  it("renders the bounded failure states distinctly", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse({ error: { code: "internal_error" } }, 500);
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse(readinessPayload());
      }
      if (url === "/api/v1/management/readiness") {
        return jsonResponse(managementReadinessPayload());
      }
      if (url.startsWith("/api/v1/operations/manual-actions")) {
        return jsonResponse(manualActionsPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "操作与任务" });
    expect(
      await screen.findByRole("heading", { name: "Operations unavailable" }),
    ).toBeVisible();
    expect(screen.queryByText("还没有运行记录")).toBeNull();
  });

  it("treats a malformed inventory response as a bounded failure, not an empty list", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse({ items: "everything", total: -1 });
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse(readinessPayload());
      }
      if (url === "/api/v1/management/readiness") {
        return jsonResponse(managementReadinessPayload());
      }
      if (url.startsWith("/api/v1/operations/manual-actions")) {
        return jsonResponse(manualActionsPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "操作与任务" });
    expect(
      await screen.findByRole("heading", { name: "操作与任务暂不可用" }),
    ).toBeVisible();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders a read failure with retry and never claims zero runs", async () => {
    stubFetch(async () => {
      throw new TypeError("network down");
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "操作与任务" });
    expect(
      await screen.findByRole("heading", { name: "Operations unavailable" }),
    ).toBeVisible();
    expect(screen.queryByText("还没有运行记录")).toBeNull();
  });

  it("pages forward only through server cursors without merging pages", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const pageTwo = pageDocument({
      items: [
        runDocument({
          run_id: "task-101",
          task_id: "task-101",
          status: "completed",
        }),
      ],
      total: 3,
      previous_cursor: "prev-cursor",
      next_cursor: null,
    });
    const pageOne = pageDocument({
      total: 3,
      truncated: true,
      next_cursor: "next-cursor",
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.includes("cursor=next-cursor")) {
        return jsonResponse(pageTwo);
      }
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse(pageOne);
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse(readinessPayload());
      }
      if (url === "/api/v1/management/readiness") {
        return jsonResponse(managementReadinessPayload());
      }
      if (url.startsWith("/api/v1/operations/manual-actions")) {
        return jsonResponse(manualActionsPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    expect(await screen.findByText("task-001")).toBeVisible();
    const forward = screen.getByRole("button", { name: "下一页" });
    expect(forward).toBeEnabled();
    await user.click(forward);
    expect(await screen.findByText("task-101")).toBeVisible();
    expect(requested.some((url) => url.includes("cursor=next-cursor"))).toBe(
      true,
    );
    // The page lives in the URL, so refresh/back/reconnect restore it.
    await waitFor(() =>
      expect(router.history.location.search).toContain("cursor=next-cursor"),
    );
    expect(router.history.location.search).toContain("dir=forward");
    // The second page reports the honest server total, not page-size math.
    expect(screen.getByText(/共 3 条/)).toBeVisible();
  });

  it("applies the attention facet its card advertises and never disables it", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const attentionPage = pageDocument({
      items: [runDocument({ status: "failed", attention: true })],
      status_counts: { failed: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
    });
    const fullPage = pageDocument({
      items: [
        runDocument(),
        runDocument({
          run_id: "task-002",
          task_id: "task-002",
          status: "failed",
          attention: true,
        }),
      ],
      status_counts: { running: 1, failed: 1 },
      attention_count: 1,
      total: 2,
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse(
          url.includes("attention=true") ? attentionPage : fullPage,
        );
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse(readinessPayload());
      }
      if (url === "/api/v1/management/readiness") {
        return jsonResponse(managementReadinessPayload());
      }
      if (url.startsWith("/api/v1/operations/manual-actions")) {
        return jsonResponse(manualActionsPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const card = await screen.findByRole("button", {
      name: /需要关注（与状态计数重叠，不是独立终态）/,
    });
    // The advertised facet is an operable control, never a disabled label.
    expect(card).toBeEnabled();
    expect(card).not.toBeDisabled();
    expect(card).toHaveAttribute("aria-pressed", "false");

    const unfacetedReads = () =>
      requested.filter(
        (url) =>
          url.startsWith("/api/v1/operations/runs?") &&
          !url.includes("attention=true"),
      ).length;

    const beforeFacet = unfacetedReads();
    await user.click(card);
    await waitFor(() =>
      expect(router.history.location.search).toContain("attention=true"),
    );
    await waitFor(() =>
      expect(requested.some((url) => url.includes("attention=true"))).toBe(
        true,
      ),
    );
    // The facet becomes its own server-side population read; the unfiltered
    // read is not repeated while the facet is submitted.
    expect(unfacetedReads()).toBe(beforeFacet);
    // The card reads as pressed while its facet is submitted. The count
    // cards disappear for one render while the facet read is in flight, so
    // this waits for the re-rendered card instead of reading it synchronously.
    expect(
      await screen.findByRole("button", {
        name: /需要关注（与状态计数重叠，不是独立终态）/,
      }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("table")).toBeVisible();

    await user.click(
      screen.getByRole("button", {
        name: /需要关注（与状态计数重叠，不是独立终态）/,
      }),
    );
    await waitFor(() =>
      expect(router.history.location.search).not.toContain("attention=true"),
    );
    // Clearing the facet restores the full population (a still-fresh bounded
    // read may be reused instead of re-fetched), and the card reads as
    // unpressed again.
    expect(await screen.findByText("task-002")).toBeVisible();
    expect(
      await screen.findByRole("button", {
        name: /需要关注（与状态计数重叠，不是独立终态）/,
      }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("renders an honest scan-error run instead of rejecting the page", async () => {
    const requested: string[] = [];
    stubInventoryJourney(
      pageDocument({
        items: [
          runDocument({ total_items: 0, completed_items: 0, failed_items: 1 }),
        ],
        status_counts: { completed: 1 },
        attention_count: 0,
        total: 1,
      }),
      requested,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    expect(await screen.findByRole("table")).toBeVisible();
    expect(screen.getByText("task-001")).toBeVisible();
    // Legal independent scan errors never read as a malformed document and
    // never read as an empty inventory.
    expect(
      screen.queryByRole("heading", { name: "操作与任务暂不可用" }),
    ).toBeNull();
    expect(
      screen.queryByRole("heading", { name: "还没有运行记录" }),
    ).toBeNull();
    expect(
      requested.some((url) => url.includes("/api/v1/operations/runs")),
    ).toBe(true);
  });

  it("re-reads the selected overview from the header refresh control", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(runDocument());
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse(readinessPayload());
      }
      if (url === "/api/v1/management/readiness") {
        return jsonResponse(managementReadinessPayload());
      }
      if (url.startsWith("/api/v1/operations/manual-actions")) {
        return jsonResponse(manualActionsPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /扫描/ }));
    await screen.findByRole("region", { name: "运行详情" });
    const overviewReads = () =>
      requested.filter((url) => url.startsWith("/api/v1/operations/runs/"))
        .length;
    await waitFor(() => expect(overviewReads()).toBeGreaterThanOrEqual(1));

    const before = overviewReads();
    const header = screen
      .getByRole("heading", { name: "操作与任务" })
      .closest("header");
    if (header === null) {
      throw new Error("landing header was not rendered");
    }
    // The landing header refresh owns every bounded landing read, including
    // the selected overview (the Resident-service control stays untouched).
    const headerRefresh = await within(header as HTMLElement).findByRole(
      "button",
      { name: "Refresh" },
    );
    await user.click(headerRefresh);
    await waitFor(() => expect(overviewReads()).toBeGreaterThan(before));
  });

  it("pushes a history entry for the selection and Back restores the list", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(runDocument());
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse(readinessPayload());
      }
      if (url === "/api/v1/management/readiness") {
        return jsonResponse(managementReadinessPayload());
      }
      if (url.startsWith("/api/v1/operations/manual-actions")) {
        return jsonResponse(manualActionsPayload());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /扫描/ }));
    const detail = await screen.findByRole("region", { name: "运行详情" });
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=task-001"),
    );
    // The detail is the right column of the detail-aware two-column layout.
    expect(detail.closest(".mf-run-layout.mf-run-has-detail")).not.toBeNull();

    router.history.back();
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "运行详情" })).toBeNull(),
    );
    await waitFor(() =>
      expect(router.history.location.search).not.toContain("run="),
    );
    expect(await screen.findByRole("table")).toBeVisible();
    // Without a selection the list is back to its full-width entry state.
    expect(document.querySelector(".mf-run-has-detail")).toBeNull();
  });
});
