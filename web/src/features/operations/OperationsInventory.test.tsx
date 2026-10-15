import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import {
  operationsLandingSearch,
  parseOperationsReturnContext,
} from "../../shared/navigation/operations-return";
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
    processed_items: 2,
    current_stage: "processing",
    pause_requested: false,
    attention: false,
    problem_types: [],
    problem_file_counts: {
      recognition: 0,
      metadata: 0,
      classification: 0,
      conflict: 0,
      failure: 0,
    },
    configuration_snapshot_id: "snap-1",
    worker_id: null,
    sideEffects: "none",
    ...overrides,
  };
}

function summaryDocument(overrides: Record<string, unknown> = {}) {
  const zero = {
    recognition: 0,
    metadata: 0,
    classification: 0,
    conflict: 0,
    failure: 0,
  };
  return {
    available: true,
    scope: "current_filters",
    source_options_scope: "authorized_population",
    total: 1,
    running: 1,
    attention: 0,
    ended: 0,
    problem_tasks: zero,
    problem_files: zero,
    sources: [],
    sources_truncated: false,
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
    view: null,
    problem: null,
    source: null,
    summary: summaryDocument(),
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
    scope: "current_filters",
    source_options_scope: "authorized_population",
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
            problem_types: ["failure"],
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
            problem_types: ["failure"],
          }),
        ],
        status_counts: { running: 1, pending: 1, failed: 1 },
        attention_count: 2,
        total: 3,
        summary: summaryDocument({
          total: 3,
          running: 2,
          attention: 2,
          ended: 1,
          problem_tasks: {
            recognition: 0,
            metadata: 0,
            classification: 0,
            conflict: 0,
            failure: 2,
          },
          problem_files: {
            recognition: 0,
            metadata: 0,
            classification: 0,
            conflict: 0,
            failure: 2,
          },
        }),
      }),
      requested,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    // Chinese business labels describe operation and state.
    expect((await screen.findAllByText("扫描")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("预览")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("失败").length).toBeGreaterThan(0);
    // The unknown legacy command stays honest.
    expect(screen.getByText(/未识别的历史命令/)).toBeVisible();
    // Missing historical scope evidence is explicitly unavailable.
    expect(screen.getByText("不可用")).toBeVisible();
    // The nine sibling views are present on one navigation row.
    expect(screen.getByRole("button", { name: "全部任务" })).toBeVisible();
    expect(screen.getByRole("button", { name: "需要处理" })).toBeVisible();
    expect(screen.getByRole("button", { name: "失败恢复" })).toBeVisible();
    // The summary advertises the whole-population attention count.
    expect(
      screen.getAllByRole("button", { name: /需要处理/ }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText(
        /任务列表合并授权范围内的 Job 与 Task，并按明确关联去重/,
      ),
    ).toBeVisible();
    expect(screen.queryByText(/unified job\/task run inventory/)).toBeNull();
    // Worker readiness and manual entries stay discoverable.
    expect((await screen.findAllByText(/Worker 就绪/)).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByRole("link", { name: "发起受限扫描" })).toBeVisible();
    expect(
      requested.some((url) => url.includes("/api/v1/operations/runs")),
    ).toBe(true);
  });

  it("shows stage, result, and recovery guidance in their matching views", async () => {
    const user = userEvent.setup();
    stubInventoryJourney(
      pageDocument({
        items: [
          runDocument(),
          runDocument({
            run_id: "task-ended",
            task_id: "task-ended",
            source_scope: "Movies/Completed",
            status: "completed",
            processed_items: 4,
            completed_items: 4,
            updated_at: "2026-08-22T12:08:00+00:00",
            current_stage: null,
          }),
          runDocument({
            run_id: "task-metadata",
            task_id: "task-metadata",
            source_scope: "Movies/Metadata",
            status: "partial_success",
            attention: true,
            problem_types: ["metadata"],
            problem_file_counts: {
              recognition: 0,
              metadata: 1,
              classification: 0,
              conflict: 0,
              failure: 0,
            },
            current_stage: null,
            processed_items: null,
          }),
        ],
        total: 3,
        status_counts: { running: 1, completed: 1, partial_success: 1 },
        summary: summaryDocument({
          total: 3,
          running: 1,
          ended: 2,
          attention: 1,
        }),
      }),
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const views = await screen.findByRole("navigation", {
      name: "任务中心视图",
    });
    expect(
      await screen.findByRole("columnheader", { name: "当前阶段" }),
    ).toBeVisible();
    expect(
      screen.getByRole("columnheader", { name: "处理进度" }),
    ).toBeVisible();
    expect(screen.getByText("分析媒体")).toBeVisible();
    expect(screen.getAllByText("2 / 4 项")).toHaveLength(1);

    await user.click(within(views).getByRole("button", { name: "进行中" }));
    expect(
      await screen.findByRole("columnheader", { name: "当前阶段" }),
    ).toBeVisible();
    expect(screen.getByText("分析媒体")).toBeVisible();
    expect(screen.getAllByText("2 / 4 项")).toHaveLength(1);

    await user.click(within(views).getByRole("button", { name: "已结束" }));
    expect(
      await screen.findByRole("columnheader", { name: "结果摘要" }),
    ).toBeVisible();
    expect(screen.getByText(/已处理 4 \/ 4 项；失败 0 项/)).toBeVisible();

    await user.click(within(views).getByRole("button", { name: "元数据恢复" }));
    expect(
      await screen.findByRole("columnheader", { name: "问题说明" }),
    ).toBeVisible();
    const table = screen.getByRole("table");
    const metadataRow = within(table)
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("Movies/Metadata"));
    expect(metadataRow).toBeDefined();
    if (metadataRow === undefined) {
      throw new Error("metadata recovery row was not rendered");
    }
    expect(
      within(metadataRow).getByText(
        "元数据身份仍待确认或补正；打开文件记录核对当前候选。",
      ),
    ).toBeVisible();
    expect(within(metadataRow).getByText("1 个文件")).toBeVisible();
    expect(
      within(metadataRow).getByRole("button", { name: "查看问题文件" }),
    ).toBeVisible();
  });

  it("submits server filters, applies card filters and resets to the same population", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubInventoryJourney(
      pageDocument({
        items: [],
        total: 0,
        summary: summaryDocument({
          total: 2,
          running: 1,
          sources: [
            { value: "Movies/alpha", label: "Movies/alpha" },
            { value: "Movies/beta", label: "Movies/beta" },
          ],
        }),
      }),
      requested,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
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

    await user.selectOptions(screen.getByLabelText("来源"), "Movies/beta");
    await waitFor(() =>
      expect(
        requested.some((url) => url.includes("source=Movies%2Fbeta")),
      ).toBe(true),
    );

    await user.click(screen.getAllByRole("button", { name: "重置筛选" })[0]!);
    await waitFor(() =>
      expect(
        requested.some(
          (url) =>
            url.includes("/api/v1/operations/runs") &&
            !url.includes("status=failed") &&
            !url.includes("q=") &&
            !url.includes("source="),
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
    // The disposition filter option shares the status label text, so the
    // bounded presence check uses the All* variant over the detail panel.
    expect(within(detail).getAllByText(/进行中/).length).toBeGreaterThan(0);
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
    expect(
      (await within(detail).findAllByText(/进行中/)).length,
    ).toBeGreaterThan(0);
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

    await screen.findByRole("heading", { name: "任务中心" });
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

    await screen.findByRole("heading", { name: "任务中心" });
    expect(
      await screen.findByRole("heading", { name: "任务中心暂不可用" }),
    ).toBeVisible();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders a read failure with retry and never claims zero runs", async () => {
    stubFetch(async () => {
      throw new TypeError("network down");
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
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
          source_scope: "Movies/Second page",
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

    expect((await screen.findAllByText("Movies")).length).toBeGreaterThan(0);
    const forward = screen.getByRole("button", { name: "下一页" });
    expect(forward).toBeEnabled();
    await user.click(forward);
    expect(
      (await screen.findAllByText("Movies/Second page")).length,
    ).toBeGreaterThan(0);
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

  it("switches to the 需要处理 view through the server and never disables it", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const attentionPage = pageDocument({
      items: [
        runDocument({
          status: "failed",
          attention: true,
          problem_types: ["failure"],
          problem_file_counts: {
            recognition: 0,
            metadata: 0,
            classification: 0,
            conflict: 0,
            failure: 1,
          },
        }),
      ],
      status_counts: { failed: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 2,
        running: 1,
        attention: 1,
        ended: 1,
        problem_tasks: {
          recognition: 0,
          metadata: 0,
          classification: 0,
          conflict: 0,
          failure: 1,
        },
        problem_files: {
          recognition: 0,
          metadata: 0,
          classification: 0,
          conflict: 0,
          failure: 1,
        },
      }),
    });
    const fullPage = pageDocument({
      items: [
        runDocument(),
        runDocument({
          run_id: "task-002",
          task_id: "task-002",
          source_scope: "Movies/Needs review",
          status: "failed",
          attention: true,
          problem_types: ["failure"],
        }),
      ],
      status_counts: { running: 1, failed: 1 },
      attention_count: 1,
      total: 2,
      summary: summaryDocument({
        total: 2,
        running: 1,
        attention: 1,
        ended: 1,
        problem_tasks: {
          recognition: 0,
          metadata: 0,
          classification: 0,
          conflict: 0,
          failure: 1,
        },
        problem_files: {
          recognition: 0,
          metadata: 0,
          classification: 0,
          conflict: 0,
          failure: 1,
        },
      }),
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse(
          url.includes("view=attention") ? attentionPage : fullPage,
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

    const tab = await screen.findByRole("button", { name: "需要处理" });
    // The advertised view is an operable control, never a disabled label.
    expect(tab).toBeEnabled();
    expect(tab).not.toHaveAttribute("aria-current", "page");

    await user.click(tab);
    await waitFor(() =>
      expect(router.history.location.search).toContain("view=attention"),
    );
    await waitFor(() =>
      expect(requested.some((url) => url.includes("view=attention"))).toBe(
        true,
      ),
    );
    // The active view reads as the current page.
    expect(
      await screen.findByRole("button", { name: "需要处理" }),
    ).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("table")).toBeVisible();

    // Switching back to 全部任务 restores the unfiltered population.
    await user.click(screen.getByRole("button", { name: "全部任务" }));
    await waitFor(() =>
      expect(router.history.location.search).not.toContain("view=attention"),
    );
    expect(
      (await screen.findAllByText("Movies/Needs review")).length,
    ).toBeGreaterThan(0);
  });

  it("opens the exact Task/type problem file list from a recovery row", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const recoveryPage = pageDocument({
      items: [
        runDocument({
          run_id: "task-002",
          task_id: "task-002",
          source_scope: "Movies/Failure",
          status: "failed",
          attention: true,
          problem_types: ["failure"],
          problem_file_counts: {
            recognition: 0,
            metadata: 0,
            classification: 0,
            conflict: 0,
            failure: 1,
          },
        }),
      ],
      status_counts: { failed: 1 },
      attention_count: 1,
      total: 1,
      view: "failure",
      problem: "failure",
      summary: summaryDocument({
        total: 1,
        running: 0,
        attention: 1,
        ended: 1,
        problem_tasks: {
          recognition: 0,
          metadata: 0,
          classification: 0,
          conflict: 0,
          failure: 1,
        },
        problem_files: {
          recognition: 0,
          metadata: 0,
          classification: 0,
          conflict: 0,
          failure: 21,
        },
      }),
    });
    const problemItems = {
      run_id: "task-002",
      task_id: "task-002",
      problem: "failure",
      limit: 20,
      items: [
        {
          item_id: "item-a",
          task_id: "task-002",
          storage_id: "source",
          resource_library_id: "movies",
          source_path: "Movies/a.mkv",
          status: "failed",
          stage: "metadata",
          attempts: 1,
          created_at: "2026-08-22T12:00:00+00:00",
          updated_at: "2026-08-22T12:00:00+00:00",
          destination_storage_id: null,
          destination_path: null,
          execution_status: null,
          failure: {
            category: "provider_failure",
            message: "metadata lookup did not complete",
            durableState: "failed outcome is durable",
            sideEffects: "none",
            retrySafe: true,
            nextAction: "inspect the Provider and retry metadata analysis",
          },
          checkpoint: {
            status: "failed",
            stage: "metadata",
            raw_stage: "metadata",
            blocker_kind: null,
            blocker_id: null,
            effect_certainty: "none",
            retry_safety: "safe",
            permitted_action_ids: ["retry"],
            refusal_reason: null,
            checkpoint_version: "a".repeat(64),
            recovery_request: null,
            recovery_continuation: null,
          },
        },
      ],
      total: 30,
      matching_total: 21,
      dispositions: {
        pending: 20,
        active: 0,
        waiting: 0,
        success: 2,
        skipped: 0,
        failed_partial: 8,
        ignored: 0,
        cancelled: 0,
      },
      uncertain_success: 0,
      truncated: true,
      previous_cursor: null,
      next_cursor: "page-two",
      sideEffects: "none",
    };
    const problemItemsPageTwo = {
      ...problemItems,
      items: [
        {
          ...problemItems.items[0],
          item_id: "item-b",
          source_path: "Movies/b.mkv",
        },
      ],
      truncated: false,
      previous_cursor: "page-one",
      next_cursor: null,
    };
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.includes("/problem-items")) {
        return jsonResponse(
          url.includes("cursor=page-two") ? problemItemsPageTwo : problemItems,
        );
      }
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse(recoveryPage);
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
    const { router } = renderApp("/ui-v2/operations?view=failure");

    const table = await screen.findByRole("table");
    const recoveryRow = within(table)
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("Movies/Failure"));
    expect(recoveryRow).toBeDefined();
    if (recoveryRow === undefined) {
      throw new Error("recovery row was not rendered");
    }
    expect(within(recoveryRow).getByText("1 个文件")).toBeVisible();
    expect(within(recoveryRow).queryByText("21 个文件")).toBeNull();
    await user.click(
      within(recoveryRow).getByRole("button", { name: "查看失败文件" }),
    );
    await waitFor(() =>
      expect(router.history.location.search).toContain("problemRun=task-002"),
    );
    expect(router.history.location.search).toContain("view=failure");
    const panel = await screen.findByRole("region", { name: "问题文件处理" });
    expect(within(panel).getByText(/失败问题 — 文件清单/)).toBeVisible();
    // The exact Task/type file list is server-filtered: only the failure file
    // appears, with its durable reason and next step.
    expect(
      (await within(panel).findAllByText(/Movies\/a\.mkv/)).length,
    ).toBeGreaterThan(0);
    expect(within(panel).getByText(/匹配 21 个文件/)).toBeVisible();
    expect(within(panel).getByText(/无存储变更/)).toBeVisible();
    expect(within(panel).getByText(/元数据服务未完成查询/)).toBeVisible();
    expect(within(panel).getByText(/检查元数据服务状态/)).toBeVisible();
    expect(within(panel).queryByText("provider_failure")).toBeNull();
    expect(within(panel).getByText("显式重新检查")).toBeVisible();
    expect(within(panel).queryByText("retry", { exact: true })).toBeNull();
    expect(
      requested.some(
        (url) =>
          url.includes("problem-items") && url.includes("problem=failure"),
      ),
    ).toBe(true);
    await user.click(within(panel).getByRole("button", { name: "下一页" }));
    expect(
      (await within(panel).findAllByText(/Movies\/b\.mkv/)).length,
    ).toBeGreaterThan(0);
    await waitFor(() =>
      expect(router.history.location.search).toContain(
        "problemCursor=page-two",
      ),
    );
    expect(router.history.location.search).toContain("problemDir=forward");
    await user.click(within(panel).getByRole("button", { name: "上一页" }));
    expect(
      (await within(panel).findAllByText(/Movies\/a\.mkv/)).length,
    ).toBeGreaterThan(0);
    await waitFor(() =>
      expect(router.history.location.search).toContain(
        "problemCursor=page-one",
      ),
    );
    await user.click(within(panel).getByRole("button", { name: "下一页" }));
    expect(
      (await within(panel).findAllByText(/Movies\/b\.mkv/)).length,
    ).toBeGreaterThan(0);
    await user.click(
      within(panel).getByRole("button", {
        name: "查看该文件证据与恢复记录",
      }),
    );
    await waitFor(() =>
      expect(router.history.location.pathname).toBe(
        "/ui-v2/operations/tasks/task-002",
      ),
    );
    expect(router.history.location.search).toContain("item=item-b");
    const returnContext = new URLSearchParams(
      router.history.location.search,
    ).get("returnOps");
    expect(parseOperationsReturnContext(returnContext)).toMatchObject({
      view: "failure",
      problemRun: "task-002",
      problemCursor: "page-two",
      problemDir: "forward",
    });
  });

  it("renders an honest scan-error run instead of rejecting the page", async () => {
    const requested: string[] = [];
    stubInventoryJourney(
      pageDocument({
        items: [
          runDocument({
            total_items: 0,
            completed_items: 0,
            processed_items: null,
            current_stage: null,
            failed_items: 1,
          }),
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
    expect(screen.getAllByText("Movies").length).toBeGreaterThan(0);
    // Legal independent scan errors never read as a malformed document and
    // never read as an empty inventory.
    expect(
      screen.queryByRole("heading", { name: "任务中心暂不可用" }),
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
      .getByRole("heading", { name: "任务中心" })
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

  it("starts the new-task journey with a valid empty default-list origin", async () => {
    // The default (unfiltered, unselected) task center serializes a valid
    // empty `returnOps=` origin. The `新建整理任务` entry must carry that
    // marker — not drop it as "no origin" — so the journey can return here
    // with its admitted run selected (Task 42.3 correction, AC-T3/AC-T5).
    const requested: string[] = [];
    stubInventoryJourney(pageDocument({ items: [], total: 0 }), requested);
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const entry = await screen.findByRole("link", {
      name: "新建整理任务",
    });
    expect(entry).toBeVisible();
    const href = entry.getAttribute("href") ?? "";
    expect(href).toContain("returnOps=");
    // The marker value is exactly the empty default-list context.
    const query = href.slice(href.indexOf("?") + 1);
    expect(new URLSearchParams(query).get("returnOps")).toBe("");

    // The journey this entry starts resolves back to the same landing with
    // the admitted run selected: the preserved empty context plus the run
    // identity is exactly the bounded search the landing accepts.
    const context = new URLSearchParams(query).get("returnOps") ?? null;
    expect(operationsLandingSearch(context, "admitted-task-1")).toEqual({
      run: "admitted-task-1",
    });
    // The router accepts this search as the landing's own continuation.
    await router.navigate({
      to: "/operations",
      search: operationsLandingSearch(context, "admitted-task-1"),
    });
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=admitted-task-1"),
    );
  });
});

const LIFECYCLE_VERSION = "2026-08-22T12:06:00+00:00";

function lifecycleAction(
  name: string,
  available: boolean,
  unavailableReason: string | null,
  preview?: unknown,
) {
  return {
    action: name,
    label: `${name} label`,
    method: "POST",
    path: `/api/v1/tasks/{id}/${name}`,
    available,
    unavailableReason,
    confirmationRequired: false,
    cooperative: true,
    durableOutcome: `${name} durable outcome`,
    sideEffects: "no Storage mutation",
    retrySafe: false,
    nextAction: `${name} next action`,
    ...(preview === undefined ? {} : { preview }),
  };
}

/** The native recovery entry the backend publishes with an authority refusal. */
const AUTHORITY_PREVIEW = {
  available: true,
  reason: null,
  method: "POST",
  path: "/api/v1/tasks/task-001/remaining-scope-previews",
  requiresConfirmation: false,
  sideEffects: "none",
  durableOutcome:
    "a durable zero-mutation exact Preview of the remaining eligible scope is stored",
  nextAction:
    "review the exact Preview, then make one fresh explicit execution intent",
};

function runLifecycleDocument(overrides: Record<string, unknown> = {}) {
  return {
    objectType: "task",
    objectId: "task-001",
    state: "running",
    version: LIFECYCLE_VERSION,
    executionPath: "operator_workflow",
    terminal: false,
    permitted: true,
    permission: "cancel_job",
    pauseRequested: false,
    cancellationRequested: false,
    commandKind: null,
    effectCertainty: "none",
    resultsObserved: 0,
    resultsComplete: true,
    uncertainResults: 0,
    knownEffects: "当前没有已记录的存储效果",
    nextAction: "刷新读取持久状态",
    actions: [
      lifecycleAction("cancel", true, null),
      lifecycleAction("pause", true, null),
      lifecycleAction(
        "resume",
        false,
        "没有可用的持久排队继续边界;请在终端继续该暂停范围",
      ),
    ],
    ...overrides,
  };
}

/**
 * A fetch stub for the selected-run control journey: the inventory page, the
 * selected run overview carrying a lifecycle projection, and the bounded
 * landing reads. `submit` decides the POST outcome and records every POST.
 */
function stubLifecycleJourney(options: {
  readonly lifecycle?: Record<string, unknown>;
  readonly overview?: Record<string, unknown>;
  readonly respond: (
    url: string,
    init: RequestInit | undefined,
    attempt: number,
  ) => Response;
  readonly posts: { readonly url: string; readonly body: unknown }[];
}): {
  readonly fetchMock: ReturnType<typeof vi.fn>;
  readonly overviewReads: () => number;
} {
  let overviewReads = 0;
  const fetchMock = stubFetch(async (input, init) => {
    const url = String(input);
    if (init?.method === "POST") {
      options.posts.push({
        url,
        body:
          typeof init.body === "string"
            ? (JSON.parse(init.body) as unknown)
            : null,
      });
      return options.respond(url, init, options.posts.length);
    }
    if (
      url.startsWith("/api/v1/operations/runs?") ||
      url === "/api/v1/operations/runs"
    ) {
      return jsonResponse(pageDocument());
    }
    if (url === "/api/v1/operations/runs/task-001") {
      overviewReads += 1;
      return jsonResponse(
        runDocument({
          ...options.overview,
          lifecycle: options.lifecycle ?? runLifecycleDocument(),
        }),
      );
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/")) {
      // The invalidated detail tabs re-read their own bounded pages.
      return jsonResponse({ error: { code: "not_found" } }, 404);
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
  return { fetchMock, overviewReads: () => overviewReads };
}

describe("selected run lifecycle controls", () => {
  it("submits exactly one authenticated POST with the displayed version", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    const { fetchMock } = stubLifecycleJourney({
      posts,
      respond: () =>
        jsonResponse({
          action: "pause",
          taskId: "task-001",
          task: {
            task_id: "task-001",
            command: "scan",
            status: "running",
            execute_authorized: false,
            created_at: "2026-08-22T12:00:00+00:00",
            updated_at: "2026-08-22T12:07:00+00:00",
            started_at: "2026-08-22T12:00:01+00:00",
            completed_at: null,
            total_items: 4,
            completed_items: 1,
            failed_items: 0,
            failure: null,
            pause_requested: true,
            configuration_snapshot_id: "snap-1",
            item_limit: null,
          },
          lifecycle: runLifecycleDocument({
            version: "2026-08-22T12:07:00+00:00",
            pauseRequested: true,
          }),
          durableOutcome: "暂停请求已持久保存",
        }),
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    // The withheld Resume is explained, never rendered as a control.
    expect(
      within(controls).queryByRole("button", { name: "继续剩余范围" }),
    ).toBeNull();
    expect(
      within(controls).getByText(/没有可用的持久排队继续边界/),
    ).toBeVisible();

    await user.click(
      within(controls).getByRole("button", { name: "请求暂停" }),
    );

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]?.url).toBe("/api/v1/tasks/task-001/pause");
    expect(posts[0]?.body).toEqual({ expectedUpdatedAt: LIFECYCLE_VERSION });
    // The accepted envelope is reported truthfully, and a click never becomes
    // more than one submission.
    expect(
      await within(controls).findByText(/暂停请求已持久保存/),
    ).toBeVisible();
    expect(posts).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalled();
  });

  it("locks resubmission after a malformed control response until refresh", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    const { overviewReads } = stubLifecycleJourney({
      posts,
      // A 200 whose body cannot describe the accepted control: the durable
      // outcome is unknown, so no second command may be sent.
      respond: () => jsonResponse({ action: "pause" }),
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    await waitFor(() => expect(overviewReads()).toBeGreaterThanOrEqual(1));
    const pause = within(controls).getByRole("button", { name: "请求暂停" });
    await user.click(pause);
    await waitFor(() => expect(posts).toHaveLength(1));

    // Unknown outcome: the reconciliation copy is shown and every control is
    // disabled, so a resubmission cannot be clicked.
    expect(await within(controls).findByText(/控制结果未知/)).toBeVisible();
    expect(
      within(controls).getByRole("button", { name: "请求暂停" }),
    ).toBeDisabled();
    expect(
      within(controls).getByRole("button", { name: "取消运行" }),
    ).toBeDisabled();
    await user.click(
      within(controls).getByRole("button", { name: "请求暂停" }),
    );
    expect(posts).toHaveLength(1);

    // One explicit successful reconciliation reads the overview again and
    // clears the lock, re-enabling the advertised controls without ever
    // resubmitting the command.
    const readsBefore = overviewReads();
    await user.click(
      within(controls).getByRole("button", { name: "刷新核对持久状态" }),
    );
    await waitFor(() => expect(overviewReads()).toBeGreaterThan(readsBefore));
    await waitFor(() =>
      expect(
        within(controls).getByRole("button", { name: "请求暂停" }),
      ).toBeEnabled(),
    );
    expect(posts).toHaveLength(1);
  });

  it("admits the native exact Preview the withheld Continue advertised", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    stubLifecycleJourney({
      posts,
      lifecycle: runLifecycleDocument({
        state: "paused",
        permitted: true,
        actions: [
          lifecycleAction("cancel", false, "a paused Task cannot be cancelled"),
          lifecycleAction(
            "pause",
            false,
            "only a running Task accepts a pause",
          ),
          lifecycleAction(
            "resume",
            false,
            "the stored execute flag is not authority",
            AUTHORITY_PREVIEW,
          ),
        ],
      }),
      respond: () =>
        jsonResponse(
          {
            error: {
              code: "scope_unresolved",
              message:
                "the run's admitted scope does not resolve to a ResourceLibrary",
              details: { sideEffects: "none" },
            },
          },
          409,
        ),
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    // The withheld Continue is never a button, but its recovery entry is a real
    // control driven by the backend path.
    expect(
      within(controls).queryByRole("button", { name: "继续剩余范围" }),
    ).toBeNull();
    const recovery = within(controls).getByRole("button", {
      name: "查看剩余范围的精确预览",
    });
    await user.click(recovery);

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]?.url).toBe(
      "/api/v1/tasks/task-001/remaining-scope-previews",
    );
    // The browser submits nothing but the run identity: the scope, the pin and
    // the source identities stay server-side.
    expect(posts[0]?.body).toEqual({});
    // A bounded refusal is reported without ever locking the operator out.
    expect(await within(controls).findByText(/该控制被拒绝/)).toBeVisible();
  });

  it("routes to the run that really owns an already-continued scope", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    stubLifecycleJourney({
      posts,
      overview: {
        continuation: {
          continuationId: "continuation-1",
          status: "queued",
          command: "scan",
          jobId: "job-1",
          newTaskId: "task-linked",
          itemLimit: 2,
          createdAt: "2026-08-22T12:41:00+00:00",
          completedAt: null,
          attemptCount: 1,
          truncated: false,
          nextAction: "follow the linked continuation run",
          sideEffects: "none",
        },
      },
      respond: () => jsonResponse({ error: { code: "not_found" } }, 404),
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?run=task-001");

    const facts = await screen.findByRole("region", { name: "运行详情" });
    await user.click(
      await within(facts).findByRole("button", {
        name: "打开链接的继续运行",
      }),
    );
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=task-linked"),
    );
    // Selecting the linked run never submits a control.
    expect(posts).toHaveLength(0);
  });

  it("opens the linked exact Preview with the selected run as its return context", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    stubLifecycleJourney({
      posts,
      overview: {
        continuation: {
          continuationId: "preview-recovery",
          status: "previewed",
          command: "preview",
          jobId: null,
          newTaskId: null,
          itemLimit: 2,
          createdAt: "2026-08-22T12:41:00+00:00",
          completedAt: null,
          attemptCount: 1,
          truncated: false,
          recoveryKind: "exact_preview",
          recoveryPreviewId: "preview-recovery",
          executionId: null,
          nextAction: "review the exact Preview",
          sideEffects: "none",
        },
      },
      respond: () => jsonResponse({ error: { code: "not_found" } }, 404),
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations?status=paused&run=task-001",
    );

    const facts = await screen.findByRole("region", { name: "运行详情" });
    await user.click(
      await within(facts).findByRole("button", {
        name: "查看关联的精确预览",
      }),
    );

    await waitFor(() =>
      expect(router.history.location.pathname).toContain(
        "/operations/organize/preview/preview-recovery",
      ),
    );
    const returnOps = new URLSearchParams(router.history.location.search).get(
      "returnOps",
    );
    expect(returnOps).not.toBeNull();
    expect(returnOps).toContain("status=paused");
    expect(returnOps).toContain("run=task-001");
    expect(posts).toHaveLength(0);
  });
});
