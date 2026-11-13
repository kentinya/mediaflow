import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import {
  operationsLandingSearch,
  parseOperationsReturnContext,
} from "../../shared/navigation/operations-return";
import { renderApp } from "../../../tests/utils";
import manualOperationsFixture from "../../entities/operations/__fixtures__/manual-operations.json";
import { localDayEndIso, localDayStartIso } from "./run-time";

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
  const document: Record<string, unknown> = {
    run_kind: "task",
    run_id: "task-001",
    command: "preview",
    command_label: "预览",
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
    success_items: 1,
    partial_items: 0,
    uncertain_effect_items: 0,
    missing_result_items: 0,
    current_stage: "processing",
    pause_requested: false,
    attention: false,
    problem_types: [],
    problem_file_counts: {
      recognition: 0,
      metadata: 0,
      classification: 0,
      conflict: 0,
    },
    // Attention is exactly the union of the four business problem types, so
    // an attention row always names its reason; the fixture derives it from the
    // overrides instead of letting the two fields disagree.
    attention_reason: null,
    configuration_snapshot_id: "snap-1",
    worker_id: null,
    sideEffects: "none",
    ...overrides,
  };
  if (
    document.attention_reason === null &&
    document.attention === true &&
    Array.isArray(document.problem_types) &&
    document.problem_types.length > 0
  ) {
    document.attention_reason = "task_problem";
  }
  return document;
}

function summaryDocument(overrides: Record<string, unknown> = {}) {
  const zero = {
    recognition: 0,
    metadata: 0,
    classification: 0,
    conflict: 0,
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

/**
 * A fetch stub serving the organizing inventory read.
 *
 * Slice46 RO-4 removed the global Worker/resident-status, discovery and
 * manual-operation blocks, so the landing issues no exclusive readiness,
 * management-readiness or manual-action read any more.
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
            command: "organize",
            command_label: "整理",
            status: "pending",
            attention: true,
            problem_types: ["metadata"],
            problem_file_counts: {
              recognition: 0,
              metadata: 1,
              classification: 0,
              conflict: 0,
            },
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
            problem_types: ["metadata"],
            problem_file_counts: {
              recognition: 0,
              metadata: 1,
              classification: 0,
              conflict: 0,
            },
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
            metadata: 2,
            classification: 0,
            conflict: 0,
          },
          problem_files: {
            recognition: 0,
            metadata: 2,
            classification: 0,
            conflict: 0,
          },
        }),
      }),
      requested,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    // Chinese business labels describe operation and state.
    expect((await screen.findAllByText("整理")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("失败").length).toBeGreaterThan(0);
    expect(screen.getAllByText("元数据问题").length).toBeGreaterThan(0);
    // The unknown legacy command stays honest.
    expect(screen.getByText(/未识别的历史命令/)).toBeVisible();
    // Missing historical scope evidence is explicitly unavailable.
    expect(screen.getByText("不可用")).toBeVisible();
    // The eight organizing views are present on one navigation row; the
    // retired Failure Recovery view is gone.
    expect(screen.getByRole("button", { name: "全部任务" })).toBeVisible();
    expect(screen.getByRole("button", { name: "需要处理" })).toBeVisible();
    expect(screen.getByRole("button", { name: "冲突处理" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "失败恢复" })).toBeNull();
    // The summary advertises the whole-population attention count.
    expect(
      screen.getAllByRole("button", { name: /需要处理/ }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.queryByText(/任务列表合并授权范围内的 Job 与 Task/),
    ).toBeNull();
    expect(screen.queryByText(/统计按当前筛选后的完整总体计算/)).toBeNull();
    expect(screen.queryByText(/unified job\/task run inventory/)).toBeNull();
    // The retired global Worker/resident block, discovery list and manual
    // operation section are all absent, together with their exclusive reads.
    expect(screen.queryByText(/Worker 就绪/)).toBeNull();
    expect(screen.queryByText(/常驻服务状态/)).toBeNull();
    expect(screen.queryByRole("link", { name: "发起受限扫描" })).toBeNull();
    expect(screen.queryByText(/整理发现/)).toBeNull();
    expect(screen.queryByText(/手动操作/)).toBeNull();
    expect(
      requested.some((url) => url.includes("/api/v1/workers/readiness")),
    ).toBe(false);
    expect(
      requested.some((url) => url.includes("/api/v1/management/readiness")),
    ).toBe(false);
    expect(
      requested.some((url) =>
        url.includes("/api/v1/operations/manual-actions"),
      ),
    ).toBe(false);
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
            success_items: 4,
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
    expect(screen.getByText(/成功 4/)).toBeVisible();

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

  it("offers only a local creation-time range on All and clears back to the whole population", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubInventoryJourney(
      pageDocument({
        items: [],
        total: 0,
        summary: summaryDocument({ total: 2, running: 1 }),
      }),
      requested,
    );
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    await waitFor(() =>
      expect(
        requested.some((url) => url.includes("/api/v1/operations/runs")),
      ).toBe(true),
    );
    expect(
      await screen.findByRole("heading", { name: "还没有运行记录" }),
    ).toBeVisible();

    // The All view has no keyword search, source/status/command controls or
    // search submit action; only the creation-day range remains.
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByRole("button", { name: "搜索" })).toBeNull();
    expect(screen.queryByLabelText("来源")).toBeNull();
    expect(screen.queryByLabelText("状态")).toBeNull();
    expect(screen.queryByLabelText("操作类型")).toBeNull();
    const from = screen.getByLabelText("开始日期");
    const to = screen.getByLabelText("结束日期");
    expect(from).not.toHaveAttribute("max");
    expect(to).not.toHaveAttribute("min");

    // Each date control applies independently; no search submit is needed.
    fireEvent.change(from, { target: { value: "2026-08-01" } });
    await waitFor(() =>
      expect(router.history.location.search).toBe("?from=2026-08-01"),
    );
    await waitFor(() =>
      expect(
        requested.some((url) => {
          const params = new URL(url, "http://mediaflow.test").searchParams;
          return params.get("from") === localDayStartIso("2026-08-01");
        }),
      ).toBe(true),
    );

    fireEvent.change(to, { target: { value: "2026-08-02" } });
    await waitFor(() =>
      expect(router.history.location.search).toBe(
        "?from=2026-08-01&to=2026-08-02",
      ),
    );
    await waitFor(() =>
      expect(
        requested.some((url) => {
          const params = new URL(url, "http://mediaflow.test").searchParams;
          return (
            params.get("from") === localDayStartIso("2026-08-01") &&
            params.get("to") === localDayEndIso("2026-08-02")
          );
        }),
      ).toBe(true),
    );
    // The end boundary covers the entire final second of the local day,
    // including the durable microsecond part.
    expect(localDayEndIso("2026-08-02")).toMatch(/\.999999Z$/);
    expect(from).toHaveAttribute("max", "2026-08-02");
    expect(to).toHaveAttribute("min", "2026-08-01");

    await user.click(
      within(screen.getByRole("region", { name: "运行筛选" })).getByRole(
        "button",
        { name: "清除" },
      ),
    );
    await waitFor(() => expect(router.history.location.search).toBe(""));
    await waitFor(() =>
      expect(
        requested.some((url) => {
          const params = new URL(url, "http://mediaflow.test").searchParams;
          return params.get("from") === null && params.get("to") === null;
        }),
      ).toBe(true),
    );
    expect(screen.queryByRole("button", { name: "清除时间" })).toBeNull();
  });

  it.each([
    "all",
    "running",
    "attention",
    "ended",
    "recognition",
    "metadata",
    "classification",
    "conflict",
  ])("uses only visible dates in %s, including legacy links", async (view) => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubInventoryJourney(pageDocument({ items: [], total: 0 }), requested);
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      `/ui-v2/operations?view=${view}&q=old&status=failed&source=Movies&command=organize&attention=true&problem=metadata&cursor=old`,
    );
    await screen.findByRole("heading", { name: "还没有运行记录" });
    const filters = screen.getByRole("region", { name: "运行筛选" });
    expect(within(filters).queryByRole("searchbox")).toBeNull();
    for (const label of ["来源", "状态", "操作类型"])
      expect(within(filters).queryByLabelText(label)).toBeNull();
    await waitFor(() =>
      expect(router.history.location.search).not.toMatch(
        /q=|status=|source=|command=|attention=|problem=|cursor=/,
      ),
    );
    fireEvent.change(screen.getByLabelText("开始日期"), {
      target: { value: "2026-08-01" },
    });
    await waitFor(() =>
      expect(router.history.location.search).toContain("from=2026-08-01"),
    );
    await user.click(
      within(screen.getByRole("region", { name: "运行筛选" })).getByRole(
        "button",
        { name: "清除" },
      ),
    );
    await waitFor(() =>
      expect(router.history.location.search).not.toContain("from="),
    );
    expect(
      requested
        .filter((url) => url.startsWith("/api/v1/operations/runs?"))
        .every((url) => {
          const params = new URL(url, "http://mediaflow.test").searchParams;
          return (
            [
              "q",
              "status",
              "source",
              "command",
              "attention",
              "problem",
              "cursor",
            ].every((key) => !params.has(key)) &&
            params.get("view") === (view === "all" ? null : view)
          );
        }),
    ).toBe(true);
  });

  it("keeps the date range and clear without timezone explanations", async () => {
    stubInventoryJourney(pageDocument({ items: [], total: 0 }));
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?view=ended&from=2026-08-01&to=2026-08-02");
    await screen.findByRole("heading", { name: "没有匹配的运行" });
    const filters = screen.getByRole("region", { name: "运行筛选" });
    expect(
      within(filters).getByRole("group", { name: "创建日期" }),
    ).toBeVisible();
    expect(within(filters).queryByText("本地时区")).toBeNull();
    expect(
      within(filters).queryByRole("button", { name: "时区说明" }),
    ).toBeNull();
    const from = within(filters).getByLabelText("开始日期");
    const to = within(filters).getByLabelText("结束日期");
    expect(from).toHaveValue("2026-08-01");
    expect(to).toHaveValue("2026-08-02");
    expect(from).not.toHaveAttribute(
      "aria-describedby",
      "run-time-filter-note",
    );
    expect(to).not.toHaveAttribute("aria-describedby", "run-time-filter-note");
    expect(within(filters).getByRole("button", { name: "清除" })).toBeVisible();
    expect(screen.getByRole("button", { name: "清除时间" })).toBeVisible();
  });

  it("drops removed All-view filters from an old link without losing its run", async () => {
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
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations?q=secret&status=failed&source=Movies%2Fbeta" +
        "&command=manual&attention=true&cursor=old-scope&run=task-001",
    );

    await screen.findByRole("dialog", { name: "运行详情" });
    await waitFor(() => {
      const search = router.history.location.search;
      expect(search).not.toContain("q=");
      expect(search).not.toContain("status=");
      expect(search).not.toContain("source=");
      expect(search).not.toContain("command=");
      expect(search).not.toContain("attention=");
      expect(search).toContain("run=task-001");
    });
    const listReads = requested.filter((url) =>
      url.startsWith("/api/v1/operations/runs?"),
    );
    expect(listReads.length).toBeGreaterThan(0);
    for (const read of listReads) {
      const params = new URL(read, "http://mediaflow.test").searchParams;
      expect(params.get("q")).toBeNull();
      expect(params.get("status")).toBeNull();
      expect(params.get("source")).toBeNull();
      expect(params.get("command")).toBeNull();
      expect(params.get("attention")).toBeNull();
      expect(params.get("cursor")).toBeNull();
    }
  });

  it("never lets an older time-range response overwrite the newest result", async () => {
    const pending = new Map<string, (response: Response) => void>();
    stubFetch(async (input) => {
      const url = String(input);
      if (!url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }
      const from =
        new URL(url, "http://mediaflow.test").searchParams.get("from") ?? "all";
      return new Promise<Response>((resolve) => pending.set(from, resolve));
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    await waitFor(() => expect(pending.has("all")).toBe(true));
    pending.get("all")!(jsonResponse(pageDocument()));
    await screen.findByRole("table");

    const from = screen.getByLabelText("开始日期");
    const first = localDayStartIso("2026-08-01");
    const second = localDayStartIso("2026-08-02");
    expect(first).not.toBeNull();
    expect(second).not.toBeNull();

    fireEvent.change(from, { target: { value: "2026-08-01" } });
    await waitFor(() => expect(pending.has(first as string)).toBe(true));
    fireEvent.change(from, { target: { value: "2026-08-02" } });
    await waitFor(() => expect(pending.has(second as string)).toBe(true));

    pending.get(second as string)!(
      jsonResponse(
        pageDocument({
          items: [runDocument({ source_scope: "NEWEST" })],
          summary: summaryDocument({ total: 1 }),
        }),
      ),
    );
    expect((await screen.findAllByText("NEWEST")).length).toBeGreaterThan(0);

    pending.get(first as string)!(
      jsonResponse(
        pageDocument({
          items: [runDocument({ source_scope: "OLDER" })],
          summary: summaryDocument({ total: 1 }),
        }),
      ),
    );
    await waitFor(() => expect(screen.queryAllByText("OLDER")).toHaveLength(0));
    expect(screen.getAllByText("NEWEST").length).toBeGreaterThan(0);
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
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    await waitFor(() => expect(overviewRead).toBe(true));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    expect(await within(detail).findByText("手动")).toBeVisible();
    // The disposition filter option shares the status label text, so the
    // bounded presence check uses the All* variant over the detail panel.
    expect(within(detail).getAllByText(/进行中/).length).toBeGreaterThan(0);
    // The overview leads with the flow status and own facts; the removed
    // "processed is not organize success" tutorial is not printed.
    expect(within(detail).getByText("流程状态")).toBeVisible();
    expect(within(detail).queryByText(/不代表整理成功/)).toBeNull();
    // A run without a Files preparation association publishes no preparation
    // area at all, not even an empty one.
    expect(
      within(detail).queryByRole("region", { name: "文件整理准备" }),
    ).toBeNull();
    // The historical source and target scope the projection publishes are
    // part of the visible overview (absent evidence renders explicitly).
    expect(within(detail).getByText("Movies")).toBeVisible();
    expect(within(detail).getByText("Library/History")).toBeVisible();
    // The former self-link back into this same task detail is gone.
    expect(within(detail).queryByText("更详细证据")).toBeNull();
    expect(
      within(detail).queryByRole("link", {
        name: "在任务中心查看该运行的详情",
      }),
    ).toBeNull();

    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    expect(fetchMock).toHaveBeenCalled();
  });

  it("PATCH-20261113-3 continues the exact Files preparation above the preserved task center", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    // The continuable state explains only the next step; the hosted card
    // itself carries the confirmation boundary.
    expect(
      within(detail).getByText("查看整理摘要，确认后执行。"),
    ).toBeVisible();
    expect(
      within(detail).queryByText(/此运行由文件页的整理选择发起/),
    ).toBeNull();
    const link = await within(detail).findByRole("link", { name: "继续整理" });
    // The continue address is the task center itself: exact Task + closed
    // marker, never a browser-supplied discovery or library identity.
    expect(link.getAttribute("href")).toContain("run=task-001");
    expect(link.getAttribute("href")).toContain("dialog=organize");
    expect(link.getAttribute("href")).not.toContain("discoveryId");
    expect(link.getAttribute("href")).not.toContain("resourceLibraryId");

    await user.click(link);
    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    expect(within(dialog).getAllByText("One.2001.mkv").length).toBeGreaterThan(
      0,
    );
    // The main path stays the task center: same route, exact Task, marker only.
    expect(router.state.location.pathname).toBe("/operations");
    const opened = new URLSearchParams(router.history.location.search);
    expect(opened.get("run")).toBe("task-001");
    expect(opened.get("dialog")).toBe("organize");
    expect(opened.get("discoveryId")).toBeNull();
    // The list and the exact run detail stay mounted behind the card.
    expect(screen.getByRole("table")).toBe(table);
    expect(screen.getByRole("dialog", { name: "运行详情" })).toBe(detail);
    // The preparation identity came from the Task's backend association.
    expect(backend.calls.discoveryReads).toBeGreaterThan(0);
    expect(backend.calls.posts).toEqual([]);

    await user.click(within(dialog).getByRole("button", { name: /^关闭$/ }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    // Closing removes only the marker: the same detail stays open and focus
    // returns to the exact continue entry that invoked the card.
    expect(router.state.location.pathname).toBe("/operations");
    const closed = new URLSearchParams(router.history.location.search);
    expect(closed.get("run")).toBe("task-001");
    expect(closed.get("dialog")).toBeNull();
    expect(screen.getByRole("dialog", { name: "运行详情" })).toBe(detail);
    expect(screen.getByRole("table")).toBe(table);
    await waitFor(() => expect(document.activeElement).toBe(link));
    // Opening and closing the card submits nothing.
    expect(backend.calls.posts).toEqual([]);
  });

  it("removes the ended flow's duplicate preparation entries and keeps its file truth", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(
          runDocument({
            status: "failed",
            filesPreparation: {
              discoveryId: "discovery-1",
              resourceLibraryId: "source",
              continuable: false,
            },
          }),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    // The ended flow exposes no duplicate preparation heading, ending notice,
    // empty action container or either former entry. Its real flow and file
    // results above are the complete detail.
    expect(
      within(detail).queryByRole("region", { name: "文件整理准备" }),
    ).toBeNull();
    expect(within(detail).queryByText("文件整理准备")).toBeNull();
    expect(
      within(detail).queryByText(
        "本次整理已结束。如需再次整理，请从文件页发起。",
      ),
    ).toBeNull();
    expect(within(detail).queryByRole("link", { name: "继续整理" })).toBeNull();
    expect(
      within(detail).queryByRole("link", { name: "查看只读摘要" }),
    ).toBeNull();
    expect(
      within(detail).queryByRole("link", { name: "从文件页重新发起" }),
    ).toBeNull();
    expect(
      within(detail).getByRole("region", { name: "文件结果" }),
    ).toBeVisible();
    // The removed entries were plain navigation; the opening journey itself
    // never submits anything.
    expect(router.state.location.pathname).toBe("/operations");
  });

  const PATCH_20261111_5_TERMINAL_CASES = [
    {
      name: "completed success",
      overrides: {
        status: "completed",
        current_stage: null,
        success_items: 1,
        filesPreparation: {
          discoveryId: "discovery-1",
          resourceLibraryId: "source",
          continuable: false,
        },
      },
      uncertain: false,
      missing: false,
    },
    {
      name: "completed with failed and uncertain file effects",
      overrides: {
        status: "completed",
        current_stage: null,
        success_items: 1,
        partial_items: 1,
        failed_items: 2,
        uncertain_effect_items: 1,
        missing_result_items: 1,
        filesPreparation: {
          discoveryId: "discovery-1",
          resourceLibraryId: "source",
          continuable: false,
        },
      },
      uncertain: true,
      missing: true,
    },
    {
      name: "failed",
      overrides: {
        status: "failed",
        current_stage: null,
        filesPreparation: {
          discoveryId: "discovery-1",
          resourceLibraryId: "source",
          continuable: false,
        },
      },
      uncertain: false,
      missing: false,
    },
    {
      name: "cancelled",
      overrides: {
        status: "cancelled",
        current_stage: null,
        filesPreparation: {
          discoveryId: "discovery-1",
          resourceLibraryId: "source",
          continuable: false,
        },
      },
      uncertain: false,
      missing: false,
    },
    {
      name: "completed without a preparation association",
      overrides: { status: "completed", current_stage: null },
      uncertain: false,
      missing: false,
    },
  ] as const;

  it.each(PATCH_20261111_5_TERMINAL_CASES)(
    "PATCH-20261111-5 keeps $name detail free of the ended preparation area",
    async ({ overrides, uncertain, missing }) => {
      stubFetch(async (input) => {
        const url = String(input);
        if (
          url.startsWith("/api/v1/operations/runs?") ||
          url === "/api/v1/operations/runs"
        ) {
          return jsonResponse(pageDocument());
        }
        if (url === "/api/v1/operations/runs/task-001") {
          return jsonResponse(runDocument(overrides));
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      });
      authStore.setToken(TOKEN);
      renderApp("/ui-v2/operations?run=task-001");

      const detail = await screen.findByRole("dialog", { name: "运行详情" });
      await within(detail).findByText("流程状态");
      expect(
        within(detail).queryByRole("region", { name: "文件整理准备" }),
      ).toBeNull();
      expect(within(detail).queryByText("文件整理准备")).toBeNull();
      expect(
        within(detail).queryByRole("link", { name: "查看只读摘要" }),
      ).toBeNull();
      expect(
        within(detail).queryByRole("link", { name: "从文件页重新发起" }),
      ).toBeNull();
      const results = within(detail).getByRole("region", { name: "文件结果" });
      if (uncertain) {
        expect(
          within(results).getByText(/目标文件结果尚未确认 1 个/),
        ).toBeVisible();
      }
      if (missing) {
        expect(
          within(results).getByText(/文件处理已结束，结果未记录 1 个/),
        ).toBeVisible();
      }
    },
  );

  it("PATCH-20261111-5 drops the continuable preparation area when the selected flow's own poll turns terminal", async () => {
    const requested: { url: string; method: string }[] = [];
    let overview = runDocument({
      status: "running",
      filesPreparation: {
        discoveryId: "discovery-1",
        resourceLibraryId: "source",
        continuable: true,
      },
    });
    stubFetch(async (input, init) => {
      const url = String(input);
      requested.push({ url, method: init?.method ?? "GET" });
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    expect(
      await within(detail).findByRole("link", { name: "继续整理" }),
    ).toBeVisible();
    overview = runDocument({
      status: "completed",
      current_stage: null,
      filesPreparation: {
        discoveryId: "discovery-1",
        resourceLibraryId: "source",
        continuable: false,
      },
    });
    // The selected overview's own 5s poll reads the durable terminal state;
    // no operator refresh or command is needed.
    await waitFor(
      () =>
        expect(
          within(detail).queryByRole("link", { name: "继续整理" }),
        ).toBeNull(),
      { timeout: 8_000 },
    );
    expect(
      within(detail).queryByRole("region", { name: "文件整理准备" }),
    ).toBeNull();
    expect(router.state.location.pathname).toBe("/operations");
    expect(new URLSearchParams(router.history.location.search).get("run")).toBe(
      "task-001",
    );
    // The terminal poll never submitted, replayed or navigated.
    expect(requested.filter((entry) => entry.method !== "GET")).toEqual([]);
  }, 12_000);

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
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&view=running");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    expect(
      (await within(detail).findAllByText(/进行中/)).length,
    ).toBeGreaterThan(0);
    // The bounded list context survives beside the panel.
    expect(await screen.findByRole("table")).toBeVisible();
    expect(
      requested.some(
        (url) => url.includes("view=running") && url.includes("limit=20"),
      ),
    ).toBe(true);
  });

  it("renders the bounded failure states distinctly", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse({ error: { code: "internal_error" } }, 500);
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

  it("retains the chosen time after a network failure and rereads that exact scope", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    let unavailable = true;
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      const params = new URL(url, "http://mediaflow.test").searchParams;
      if (params.has("from") && unavailable)
        throw new TypeError("network down");
      return jsonResponse(pageDocument());
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");
    await screen.findByRole("table");
    fireEvent.change(screen.getByLabelText("开始日期"), {
      target: { value: "2026-08-01" },
    });
    await screen.findByRole("heading", { name: "Operations unavailable" });
    expect(router.history.location.search).toBe("?from=2026-08-01");
    const failedRead = requested.at(-1);
    unavailable = false;
    await user.click(screen.getAllByRole("button", { name: "刷新" })[0]!);
    await screen.findByRole("table");
    expect(requested.at(-1)).toBe(failedRead);
    expect(screen.getByLabelText("开始日期")).toHaveValue("2026-08-01");
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
          problem_types: ["metadata"],
          problem_file_counts: {
            recognition: 0,
            metadata: 1,
            classification: 0,
            conflict: 0,
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
          metadata: 1,
          classification: 0,
          conflict: 0,
        },
        problem_files: {
          recognition: 0,
          metadata: 1,
          classification: 0,
          conflict: 0,
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
          problem_types: ["metadata"],
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
          metadata: 1,
          classification: 0,
          conflict: 0,
        },
        problem_files: {
          recognition: 0,
          metadata: 1,
          classification: 0,
          conflict: 0,
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
          source_scope: "Movies/Metadata",
          status: "failed",
          attention: true,
          problem_types: ["metadata"],
          problem_file_counts: {
            recognition: 0,
            metadata: 1,
            classification: 0,
            conflict: 0,
          },
        }),
      ],
      status_counts: { failed: 1 },
      attention_count: 1,
      total: 1,
      view: "metadata",
      problem: "metadata",
      summary: summaryDocument({
        total: 1,
        running: 0,
        attention: 1,
        ended: 1,
        problem_tasks: {
          recognition: 0,
          metadata: 1,
          classification: 0,
          conflict: 0,
        },
        problem_files: {
          recognition: 0,
          metadata: 21,
          classification: 0,
          conflict: 0,
        },
      }),
    });
    const problemItems = {
      run_id: "task-002",
      task_id: "task-002",
      problem: "metadata",
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
          // A refused continued source persists its own bounded category, so the
          // panel must show the source-changed reason/next step, never the raw
          // category token.
          failure: {
            category: "source_changed",
            message:
              "source changed: the exact reviewed source was replaced before continuation",
            durableState: "failed outcome is durable",
            sideEffects: "none",
            retrySafe: false,
            nextAction:
              "re-select the source from the current Files view and prepare a new summary",
          },
        },
        {
          ...problemItems.items[0],
          item_id: "item-c",
          source_path: "Movies/c.mkv",
          // B46.3-05: a scheduled occurrence refused because a Files admission
          // still owns the source persists its own bounded category.
          failure: {
            category: "source_already_organizing",
            message:
              "source already organizing: this file still belongs to another unfinished " +
              "organizing work, so this run did not take it over",
            durableState:
              "TaskItem and Result are durable with a failed outcome",
            sideEffects: "none",
            retrySafe: false,
            nextAction:
              "open that Files organizing work and continue or cancel it; this run keeps " +
              "its own remaining scope and never cancels, confirms or takes over the other work",
          },
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
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?view=metadata");

    const table = await screen.findByRole("table");
    const recoveryRow = within(table)
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("Movies/Metadata"));
    expect(recoveryRow).toBeDefined();
    if (recoveryRow === undefined) {
      throw new Error("recovery row was not rendered");
    }
    expect(within(recoveryRow).getByText("1 个文件")).toBeVisible();
    expect(within(recoveryRow).queryByText("21 个文件")).toBeNull();
    await user.click(
      within(recoveryRow).getByRole("button", { name: "查看问题文件" }),
    );
    await waitFor(() =>
      expect(router.history.location.search).toContain("problemRun=task-002"),
    );
    expect(router.history.location.search).toContain("view=metadata");
    const panel = await screen.findByRole("region", { name: "问题文件处理" });
    expect(within(panel).getByText(/元数据问题 — 文件清单/)).toBeVisible();
    // The exact Task/type file list is server-filtered: only that type's files
    // appear, with their durable reason and next step.
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
          url.includes("problem-items") && url.includes("problem=metadata"),
      ),
    ).toBe(true);
    await user.click(within(panel).getByRole("button", { name: "下一页" }));
    expect(
      (await within(panel).findAllByText(/Movies\/b\.mkv/)).length,
    ).toBeGreaterThan(0);
    expect(within(panel).getByText(/已核查的来源已被替换/)).toBeVisible();
    expect(within(panel).getByText(/回到当前文件页重新选择来源/)).toBeVisible();
    expect(within(panel).queryByText("source_changed")).toBeNull();
    // The refused duplicate-owner reason of a scheduled occurrence is its own
    // bounded category: the panel shows the readable reason and next step that
    // points back to the Files work, never the raw token.
    expect(
      within(panel).getByText(/该文件已属于未结束的整理工作/),
    ).toBeVisible();
    expect(
      within(panel).getByText(/打开并继续或取消那份文件页整理工作/),
    ).toBeVisible();
    expect(within(panel).queryByText("source_already_organizing")).toBeNull();
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
      within(panel).getAllByRole("button", {
        name: "查看该文件证据与恢复记录",
      })[0]!,
    );
    await waitFor(() =>
      expect(router.history.location.pathname).toBe("/ui-v2/operations"),
    );
    expect(router.history.location.search).toContain("item=item-b");
    expect(new URLSearchParams(router.history.location.search).get("run")).toBe(
      "task-002",
    );
    expect(
      parseOperationsReturnContext(router.history.location.search),
    ).toMatchObject({
      view: "metadata",
      problemRun: "task-002",
      problemCursor: "page-two",
      problemDir: "forward",
    });
  });

  it("opens an exact Task/type file list from a 需要处理 row without a dead action", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const attentionPage = pageDocument({
      items: [
        runDocument({
          run_id: "task-mixed",
          task_id: "task-mixed",
          source_scope: "Movies/Mixed",
          status: "partial_success",
          attention: true,
          problem_types: ["metadata", "classification"],
          problem_file_counts: {
            recognition: 0,
            metadata: 1,
            classification: 1,
            conflict: 0,
          },
        }),
        runDocument({
          run_id: "task-single",
          task_id: "task-single",
          source_scope: "Movies/Single",
          status: "waiting",
          attention: true,
          problem_types: ["classification"],
          problem_file_counts: {
            recognition: 0,
            metadata: 0,
            classification: 1,
            conflict: 0,
          },
        }),
      ],
      status_counts: { partial_success: 1, waiting: 1 },
      attention_count: 2,
      total: 2,
      view: "attention",
      summary: summaryDocument({
        total: 2,
        running: 2,
        attention: 2,
        ended: 0,
        problem_tasks: {
          recognition: 0,
          metadata: 1,
          classification: 1,
          conflict: 0,
        },
        problem_files: {
          recognition: 0,
          metadata: 1,
          classification: 1,
          conflict: 0,
        },
      }),
    });
    const problemItems = {
      run_id: "task-mixed",
      task_id: "task-mixed",
      problem: "metadata",
      limit: 20,
      items: [
        {
          item_id: "item-meta",
          task_id: "task-mixed",
          storage_id: "source",
          resource_library_id: "movies",
          source_path: "Movies/meta.mkv",
          status: "waiting_metadata_correction",
          stage: "waiting_metadata_correction",
          attempts: 1,
          created_at: "2026-08-22T12:00:00+00:00",
          updated_at: "2026-08-22T12:00:00+00:00",
          destination_storage_id: null,
          destination_path: null,
          execution_status: null,
          failure: null,
          checkpoint: null,
        },
      ],
      total: 2,
      matching_total: 1,
      dispositions: {
        pending: 1,
        active: 0,
        waiting: 1,
        success: 0,
        skipped: 0,
        failed_partial: 0,
        ignored: 0,
        cancelled: 0,
      },
      uncertain_success: 0,
      truncated: false,
      previous_cursor: null,
      next_cursor: null,
      sideEffects: "none",
    };
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.includes("/problem-items")) {
        return jsonResponse({ ...problemItems, problem: "metadata" });
      }
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse(attentionPage);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?view=attention");

    const table = await screen.findByRole("table");
    const mixedRow = within(table)
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("Movies/Mixed"));
    expect(mixedRow).toBeDefined();
    if (mixedRow === undefined) {
      throw new Error("attention row was not rendered");
    }
    // A Task with several current problems offers each exact type; no guess.
    await user.click(
      within(mixedRow).getByRole("button", { name: "元数据问题" }),
    );
    await waitFor(() =>
      expect(router.history.location.search).toContain("problemRun=task-mixed"),
    );
    expect(router.history.location.search).toContain("problemType=metadata");
    const panel = await screen.findByRole("region", { name: "问题文件处理" });
    expect(within(panel).getByText(/元数据问题 — 文件清单/)).toBeVisible();
    expect(
      (await within(panel).findAllByText(/Movies\/meta\.mkv/)).length,
    ).toBeGreaterThan(0);
    expect(
      requested.some(
        (url) =>
          url.includes("problem-items") && url.includes("problem=metadata"),
      ),
    ).toBe(true);

    // A row with exactly one current type opens that one type list directly.
    await user.click(
      within(panel).getByRole("button", { name: "返回任务列表" }),
    );
    const singleRow = within(await screen.findByRole("table"))
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("Movies/Single"));
    expect(singleRow).toBeDefined();
    if (singleRow === undefined) {
      throw new Error("single-type attention row was not rendered");
    }
    await user.click(
      within(singleRow).getByRole("button", { name: "查看问题文件" }),
    );
    await waitFor(() =>
      expect(router.history.location.search).toContain(
        "problemRun=task-single",
      ),
    );
    expect(requested.some((url) => url.includes("/problem-items"))).toBe(true);
  });

  it("keeps a terminal technical failure as read-only history, not attention", async () => {
    const requested: string[] = [];
    stubInventoryJourney(
      pageDocument({
        items: [
          runDocument({
            run_id: "pre-task-failure",
            run_kind: "job",
            job_id: "pre-task-failure",
            task_id: null,
            command: "organize",
            command_label: "整理",
            status: "failed",
            source_scope: null,
            total_items: null,
            completed_items: null,
            failed_items: null,
            processed_items: null,
            current_stage: null,
            // Task46.4 RO-4: a technical failure is never a fifth type and
            // never Attention; it stays real failed history in All/Ended.
            attention: false,
            problem_types: [],
            attention_reason: null,
          }),
        ],
        status_counts: { failed: 1 },
        attention_count: 0,
        total: 1,
        summary: summaryDocument({
          total: 1,
          running: 0,
          attention: 0,
          ended: 1,
        }),
      }),
      requested,
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    // The only row of the page is the technical failure: no attention column,
    // no runtime-repair guidance and no fabricated problem type.
    const row = within(table).getAllByRole("row")[1];
    expect(row).toBeDefined();
    if (row === undefined) {
      throw new Error("technical failure row was not rendered");
    }
    // The factual failed status stays readable; there is no fabricated repair
    // guidance, no runtime-repair label and no pending-task claim.
    expect(within(row).getAllByText("失败").length).toBeGreaterThan(0);
    expect(within(row).queryByText(/运行级修复/)).toBeNull();
    expect(screen.queryByText(/运行级修复/)).toBeNull();
    // The center navigation offers exactly the eight organizing views.
    for (const label of [
      "全部任务",
      "进行中",
      "需要处理",
      "已结束",
      "识别恢复",
      "元数据恢复",
      "分类恢复",
      "冲突处理",
    ]) {
      expect(await screen.findByRole("button", { name: label })).toBeVisible();
    }
    expect(screen.queryByRole("button", { name: "失败恢复" })).toBeNull();
    expect(
      requested.some((url) => url.includes("/api/v1/operations/runs")),
    ).toBe(true);
  });

  it("shows independent success, partial and failure counts for a completed mixed run", async () => {
    const user = userEvent.setup();
    stubInventoryJourney(
      pageDocument({
        items: [
          runDocument({
            run_id: "task-mixed-ended",
            task_id: "task-mixed-ended",
            source_scope: "Movies/Mixed",
            status: "completed",
            total_items: 10,
            completed_items: 10,
            processed_items: 10,
            success_items: 7,
            partial_items: 2,
            // The backend compatibility count is failed+partial; the list must
            // show the independent failure-only count (3 - 2 = 1).
            failed_items: 3,
            uncertain_effect_items: 1,
            missing_result_items: 0,
            current_stage: null,
          }),
        ],
        status_counts: { completed: 1 },
        attention_count: 0,
        total: 1,
        summary: summaryDocument({
          total: 1,
          running: 0,
          attention: 0,
          ended: 1,
        }),
      }),
    );
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const views = await screen.findByRole("navigation", {
      name: "任务中心视图",
    });
    await user.click(within(views).getByRole("button", { name: "已结束" }));
    expect(await screen.findByText(/成功 7，部分成功 2，失败 1/)).toBeVisible();
    expect(screen.getByText(/有文件效果尚不清楚/)).toBeVisible();
    expect(screen.queryByText(/失败 3/)).toBeNull();
  });

  it("PATCH-20261107-1 reads an ended mixed run as flow, processed range and independent file results", async () => {
    const overview = runDocument({
      run_id: "task-mixed-ended",
      task_id: "task-mixed-ended",
      command: "organize",
      command_label: "整理",
      source_scope: "Movies/Mixed",
      status: "completed",
      total_items: 10,
      completed_items: 10,
      processed_items: 10,
      success_items: 7,
      partial_items: 2,
      failed_items: 3,
      uncertain_effect_items: 1,
      missing_result_items: 1,
      current_stage: null,
      progress: {
        available: true,
        kind: "organize",
        unit: "主条目",
        unit_key: "task_items",
        basis: "整理计数:成功表示已验证的存储操作结果。",
        success_means: "已验证的存储操作成功",
        known_total: 10,
        indeterminate: false,
        processed: 10,
        dispositions: {
          pending: 0,
          active: 0,
          waiting: 0,
          success: 7,
          skipped: 0,
          failed_partial: 3,
          ignored: 0,
          cancelled: 0,
        },
        confirmed_success: 6,
        uncertain_success: 1,
        scan_errors: null,
        scan_discovery_complete: null,
        scan_progress: {},
        attachment_steps: 2,
        effect_counts: { verified_complete: 6, attempted_unverified: 1 },
        results_total: 7,
        results_complete: true,
        sideEffects: "none",
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/v1/operations/runs/task-mixed-ended") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-mixed-ended&view=ended");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const flow = await within(detail).findByRole("region", {
      name: "状态与流程",
    });
    await within(flow).findByText("已完成");
    const progress = await within(detail).findByRole("region", {
      name: "处理进度",
    });
    await within(progress).findByText(/已处理 10 \/ 10 个主条目/);
    const results = await within(detail).findByRole("region", {
      name: "文件结果",
    });
    // The independent outcomes are read directly, including the two caveat
    // facets; the removed basis/success-meaning/attachment-accounting prose
    // does not come back under another heading.
    expect(
      within(results)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["7成功", "2部分成功", "1失败"]);
    expect(
      within(results).getByText(/目标文件结果尚未确认 1 个/),
    ).toBeVisible();
    expect(
      within(results).getByText(/文件处理已结束，结果未记录 1 个/),
    ).toBeVisible();
    expect(
      within(detail).queryByText(/口径:|成功含义:|非成功率|单独计数/),
    ).toBeNull();
    expect(
      flow.compareDocumentPosition(progress) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      progress.compareDocumentPosition(results) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("PATCH-20261107-1 leaves no empty task operation area on a terminal run", async () => {
    const overview = runDocument({
      status: "completed",
      current_stage: null,
      lifecycle: {
        objectType: "task",
        objectId: "task-001",
        state: "completed",
        version: "2026-08-22T12:06:00+00:00",
        executionPath: "operator_workflow",
        terminal: true,
        permitted: true,
        permission: "cancel_job",
        knownEffects:
          "Storage effects are reported only from recorded item results",
        nextAction: "this Task is terminal; no lifecycle control is available",
        effectCertainty: "verified_complete",
        resultsObserved: 1,
        resultsComplete: true,
        uncertainResults: 0,
        pauseRequested: false,
        cancellationRequested: false,
        commandKind: null,
        actions: [
          {
            action: "cancel",
            label: "Cancel Task",
            method: "POST",
            path: "/api/v1/tasks/task-001/cancel",
            available: false,
            unavailableReason: "a completed Task cannot be cancelled",
            confirmationRequired: false,
            cooperative: true,
            durableOutcome: "a durable cancellation request is stored",
            sideEffects: "no Storage mutation",
            retrySafe: false,
            nextAction: "refresh the Task to read the durable state",
            recovery: null,
          },
        ],
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findByText("流程状态");
    // No standing control block, withheld-control list or permission token.
    expect(
      within(detail).queryByRole("group", { name: "任务操作" }),
    ).toBeNull();
    expect(within(detail).queryByText("运行控制")).toBeNull();
    expect(
      within(detail).queryByRole("button", { name: "取消运行" }),
    ).toBeNull();
    expect(
      within(detail).queryByText(
        /cancel_job|a completed Task cannot be cancelled|不可用的运行控制/,
      ),
    ).toBeNull();
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

  it("only claims recovered completion when the whole run really succeeded", async () => {
    // B46.4-02: the server publishes the per-item truth as ``status`` plus the
    // ``recovered_completion`` facet.  A run whose sibling was ignored keeps its
    // real failed state and its "失败" label; only a run whose every necessary
    // item has exact success proof may say "已完成（恢复成功）".
    const user = userEvent.setup();
    const mixed = runDocument({
      run_id: "mixed-run",
      task_id: "mixed-run",
      command_label: "混合结果",
      status: "failed",
      recovered_completion: false,
      total_items: 2,
      completed_items: 0,
      failed_items: 2,
      processed_items: 2,
      current_stage: null,
    });
    const recovered = runDocument({
      run_id: "recovered-run",
      task_id: "recovered-run",
      command_label: "恢复完成",
      status: "completed",
      recovered_completion: true,
      total_items: 2,
      completed_items: 0,
      failed_items: 2,
      processed_items: 2,
      current_stage: null,
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse(
          pageDocument({
            items: [mixed, recovered],
            status_counts: { failed: 1, completed: 1 },
            attention_count: 0,
            total: 2,
            summary: summaryDocument({
              total: 2,
              running: 0,
              attention: 0,
              ended: 2,
            }),
          }),
        );
      }
      if (url === "/api/v1/operations/runs/mixed-run") {
        return jsonResponse(mixed);
      }
      if (url === "/api/v1/operations/runs/recovered-run") {
        return jsonResponse(recovered);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=mixed-run");

    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    const mixedRow = rows.find((row) => row.textContent?.includes("混合结果"));
    const recoveredRow = rows.find((row) =>
      row.textContent?.includes("恢复完成"),
    );
    if (mixedRow === undefined || recoveredRow === undefined) {
      throw new Error("the exact run rows were not rendered");
    }
    expect(within(mixedRow).getByText("失败")).toBeVisible();
    expect(within(mixedRow).queryByText(/已完成（恢复成功）/)).toBeNull();
    expect(within(recoveredRow).getByText("已完成（恢复成功）")).toBeVisible();

    // The selected mixed run never explains itself as an all-item success.
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    expect(within(detail).getAllByText("失败").length).toBeGreaterThan(0);
    expect(
      within(detail).queryByText(/每个必要条目都有精确关联的真实成功证据/),
    ).toBeNull();
    // Selecting the really recovered run publishes that exact claim.
    await user.click(
      within(recoveredRow).getByRole("button", { name: /恢复完成/ }),
    );
    const recoveredDetail = await screen.findByRole("dialog", {
      name: "运行详情",
    });
    expect(
      await within(recoveredDetail).findByText(/已完成（恢复成功）/),
    ).toBeVisible();
    expect(
      within(recoveredDetail).getByText(
        /每个必要条目都有精确关联的真实成功证据/,
      ),
    ).toBeVisible();
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
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    await screen.findByRole("dialog", { name: "运行详情" });
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
      { name: "刷新" },
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
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=task-001"),
    );
    // The selection opens the centered card over the list: the card is a
    // modal layer, and the list is never narrowed by a detail column.
    expect(detail.closest(".mf-modal-layer")).not.toBeNull();
    expect(document.querySelector(".mf-run-has-detail")).toBeNull();

    router.history.back();
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    await waitFor(() =>
      expect(router.history.location.search).not.toContain("run="),
    );
    expect(await screen.findByRole("table")).toBeVisible();
    // Without a selection the list is back to its full-width entry state.
    expect(document.querySelector(".mf-run-has-detail")).toBeNull();
  });

  it("opens and returns from a problem-file list without resetting the route scroll", async () => {
    const user = userEvent.setup();
    const problemRun = runDocument({
      run_id: "task-problem",
      task_id: "task-problem",
      source_scope: "Movies/Problem",
      status: "failed",
      attention: true,
      problem_types: ["metadata"],
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 0,
      },
    });
    const problemItems = {
      run_id: "task-problem",
      task_id: "task-problem",
      problem: "metadata",
      limit: 20,
      items: [
        {
          item_id: "item-a",
          task_id: "task-problem",
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
          failure: null,
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
      total: 1,
      matching_total: 1,
      dispositions: {
        pending: 0,
        active: 0,
        waiting: 0,
        success: 0,
        skipped: 0,
        failed_partial: 1,
        ignored: 0,
        cancelled: 0,
      },
      uncertain_success: 0,
      truncated: false,
      previous_cursor: null,
      next_cursor: null,
      sideEffects: "none",
    };
    stubFetch(async (input) => {
      const url = String(input);
      if (url.includes("/problem-items")) {
        return jsonResponse(problemItems);
      }
      if (url.startsWith("/api/v1/operations/runs")) {
        return jsonResponse(
          pageDocument({
            items: [problemRun],
            total: 1,
            view: "metadata",
            problem: "metadata",
            status_counts: { failed: 1 },
            attention_count: 1,
            summary: summaryDocument({
              total: 1,
              running: 0,
              attention: 1,
              ended: 1,
              problem_tasks: {
                recognition: 0,
                metadata: 1,
                classification: 0,
                conflict: 0,
              },
              problem_files: {
                recognition: 0,
                metadata: 1,
                classification: 0,
                conflict: 0,
              },
            }),
          }),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?view=metadata");

    const table = await screen.findByRole("table");
    const row = within(table)
      .getAllByRole("row")
      .find((value) => value.textContent?.includes("Movies/Problem"));
    if (row === undefined) {
      throw new Error("the problem run row was not rendered");
    }
    const scrollTo = vi
      .spyOn(window, "scrollTo")
      .mockImplementation(() => undefined);
    await user.click(within(row).getByRole("button", { name: "查看问题文件" }));
    const panel = await screen.findByRole("region", { name: "问题文件处理" });
    await waitFor(() =>
      expect(router.history.location.search).toContain(
        "problemRun=task-problem",
      ),
    );
    expect(scrollTo).not.toHaveBeenCalled();

    await user.click(
      within(panel).getByRole("button", { name: "返回任务列表" }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "问题文件处理" })).toBeNull(),
    );
    expect(router.history.location.search).toContain("view=metadata");
    expect(router.history.location.search).not.toContain("problemRun=");
    expect(scrollTo).not.toHaveBeenCalled();
    scrollTo.mockRestore();
  });

  it("offers no center creation entry and keeps the bounded list context", async () => {
    // Task46.3 RO-2: the Task Center no longer offers a new-organize CTA, an
    // independent library picker, a manual-action section or a discovery section.
    // New manual file-selection work starts only from ResourceLibrary Files, so the
    // center must advertise no such link at all — and merely visiting it must still
    // create nothing.
    stubInventoryJourney(pageDocument({ items: [], total: 0 }), []);
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    expect(screen.queryByRole("link", { name: "新建整理任务" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "整理发现" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "手动操作" })).toBeNull();
    // The landing's own bounded continuation still resolves to the same list.
    await router.navigate({
      to: "/operations",
      search: operationsLandingSearch(null, "admitted-task-1"),
    });
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=admitted-task-1"),
    );
  });

  /** The backend-advertised cancellation the overview read publishes. */
  function lifecycleDocument(): Record<string, unknown> {
    return {
      objectType: "task",
      objectId: "task-001",
      state: "running",
      version: "2026-08-22T12:06:00+00:00",
      executionPath: "operator_workflow",
      terminal: false,
      permitted: true,
      permission: "cancel_job",
      knownEffects: "no Storage effect is recorded",
      nextAction: "refresh the Task",
      effectCertainty: "none",
      resultsObserved: 0,
      resultsComplete: true,
      uncertainResults: 0,
      pauseRequested: false,
      cancellationRequested: false,
      commandKind: null,
      actions: [
        {
          action: "cancel",
          label: "取消运行",
          method: "POST",
          path: "/api/v1/tasks/task-001/cancel",
          available: true,
          unavailableReason: null,
          confirmationRequired: false,
          cooperative: true,
          durableOutcome: "a durable cancellation request is stored",
          sideEffects: "no Storage mutation",
          retrySafe: false,
          nextAction: "refresh the Task to read the durable state",
          recovery: null,
        },
      ],
    };
  }

  it("keeps a slow overview read inside the coordinated card", async () => {
    const user = userEvent.setup();
    let releaseOverview!: (response: Response) => void;
    const gate = new Promise<Response>((resolve) => {
      releaseOverview = resolve;
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return gate;
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    // The card itself is the coordinated loading state: it exists while the
    // overview read is in flight and invents no flow/file result.
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findByText("正在加载运行详情");
    expect(within(detail).getByText("正在读取该运行的概览。")).toBeTruthy();
    expect(within(detail).queryByText(/已处理/)).toBeNull();

    releaseOverview(jsonResponse(runDocument()));
    await within(detail).findByText("Movies");
    expect(within(detail).queryByText("正在加载运行详情")).toBeNull();
  });

  it("never lets a late overview response reopen a closed card", async () => {
    const user = userEvent.setup();
    let releaseOverview!: (response: Response) => void;
    const gate = new Promise<Response>((resolve) => {
      releaseOverview = resolve;
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return gate;
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    // The overview response arrives after the card closed: it must not
    // resurrect the selection or the card.
    releaseOverview(jsonResponse(runDocument()));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    expect(router.history.location.search).not.toContain("run=");
  });

  it("keeps an unknown control outcome locked across card close and reopen", async () => {
    const user = userEvent.setup();
    const posted: string[] = [];
    stubFetch(async (input, init) => {
      const url = String(input);
      if ((init?.method ?? "GET") === "POST") {
        posted.push(url);
      }
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(runDocument({ lifecycle: lifecycleDocument() }));
      }
      if (url === "/api/v1/tasks/task-001/cancel") {
        // The request never reached a decision: the transport failed, so the
        // outcome is unknown and every control of this run must stay locked.
        throw new TypeError("network unreachable");
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const controls = await within(detail).findByRole("group", {
      name: "任务操作",
    });
    await user.click(
      within(controls).getByRole("button", { name: "取消运行" }),
    );
    await waitFor(() =>
      expect(
        within(controls).getByRole("button", { name: "取消运行" }),
      ).toBeDisabled(),
    );
    expect(within(controls).getByText(/取消结果尚未确认/)).toBeTruthy();

    // Closing the card must not drop the unresolved request's context.
    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const reopened = await screen.findByRole("dialog", { name: "运行详情" });
    const reopenedControls = await within(reopened).findByRole("group", {
      name: "任务操作",
    });
    expect(within(reopenedControls).getByText(/取消结果尚未确认/)).toBeTruthy();
    expect(
      within(reopenedControls).getByRole("button", {
        name: "核对持久状态",
      }),
    ).toBeEnabled();
    expect(
      within(reopenedControls).getByRole("button", { name: "取消运行" }),
    ).toBeDisabled();
    // The locked reopen never resubmits: still exactly one cancel POST.
    expect(posted).toEqual(["/api/v1/tasks/task-001/cancel"]);
  });

  /** The zero-change Preview a paused run's remaining-scope continuation reads. */
  function remainingPreviewDocument(): Record<string, unknown> {
    const preview = JSON.parse(
      JSON.stringify(
        (manualOperationsFixture as Record<string, unknown>)[
          "organizePreviewDetail"
        ],
      ),
    ) as Record<string, unknown>;
    preview["previewId"] = "preview-1";
    preview["intentId"] = "intent-1";
    preview["intentVersion"] = 1;
    preview["executionCandidateItemIds"] = ["item-2"];
    const items = preview["items"] as Record<string, unknown>[];
    items[0]!["itemId"] = "item-2";
    items[0]!["previewItemId"] = "preview-item-1";
    (preview["selection"] as Record<string, unknown>)["selectedItemIds"] = [
      "item-2",
    ];
    (preview["selection"] as Record<string, unknown>)["unselectedItemIds"] = [];
    const actions = preview["actions"] as Record<
      string,
      Record<string, unknown>
    >;
    actions["execute"]!["path"] =
      "/api/v1/operations/organize/previews/preview-1/execute";
    return preview;
  }

  /** The durable admission answer a successful reconciliation read returns. */
  function remainingAdmissionDocument(): Record<string, unknown> {
    return {
      outcome: "known",
      reason: null,
      executionId: "execution-remaining",
      taskId: "task-001",
      status: "queued",
      selectedItemIds: ["item-2"],
      completedItemCount: 0,
      failedItemCount: 0,
      sideEffects: "none",
      nextAction:
        "the admitted execution queues in this task; its per-item results appear in the task detail",
    };
  }

  function emptyItemsPageDocument(): Record<string, unknown> {
    return {
      items: [],
      total: 0,
      matching_total: 0,
      dispositions: {
        pending: 0,
        active: 0,
        waiting: 0,
        success: 0,
        skipped: 0,
        failed_partial: 0,
        ignored: 0,
        cancelled: 0,
      },
      uncertain_success: 0,
      truncated: false,
      previous_cursor: null,
      next_cursor: null,
      sideEffects: "none",
    };
  }

  it("PATCH-20261112-2 proves the remaining-scope reconciliation result stays in this task detail", async () => {
    const user = userEvent.setup();
    const continuation = {
      continuationId: "continuation-remaining",
      status: "accepted",
      command: "organize",
      newTaskId: null,
      itemLimit: null,
      createdAt: "2026-08-22T12:41:00+00:00",
      completedAt: null,
      attemptCount: 1,
      truncated: false,
      recoveryKind: "exact_preview",
      recoveryPreviewId: "preview-1",
      executionId: null,
      nextAction: "review the remaining scope and confirm its ready subset",
      sideEffects: "none",
    };
    const overview = runDocument({
      command: "organize",
      command_label: "整理",
      status: "paused",
      pause_requested: true,
      continuation,
    });
    const refreshedOverview = runDocument({
      command: "organize",
      command_label: "整理",
      status: "paused",
      pause_requested: true,
      updated_at: "2026-09-09T12:09:00+00:00",
      continuation,
    });
    const executePosts: string[] = [];
    const admissionReads: string[] = [];
    const heldOverviewResponses: ((response: Response) => void)[] = [];
    const heldItemsResponses: ((response: Response) => void)[] = [];
    let overviewReads = 0;
    let itemsReads = 0;
    // Reads issued after this flag are held, so only the reconciliation
    // refresh (not a routine poll) can release them below.
    let holdDetailReads = false;
    stubFetch(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "test-principal" });
      }
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/v1/operations/runs/task-001" && method === "GET") {
        overviewReads += 1;
        if (!holdDetailReads || overviewReads === 1) {
          return jsonResponse(overview);
        }
        return new Promise((resolve) => {
          heldOverviewResponses.push(resolve);
        });
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        itemsReads += 1;
        if (!holdDetailReads || itemsReads === 1) {
          return jsonResponse(emptyItemsPageDocument());
        }
        return new Promise((resolve) => {
          heldItemsResponses.push(resolve);
        });
      }
      if (
        method === "POST" &&
        url === "/api/v1/operations/organize/previews/preview-1/execute"
      ) {
        executePosts.push(url);
        // The response never reaches the browser: the durable outcome stays
        // unknown until one explicit reconciliation read proves it.
        throw new TypeError("network unreachable");
      }
      if (
        url.startsWith(
          "/api/v1/operations/organize/previews/preview-1/admission",
        )
      ) {
        admissionReads.push(url);
        return jsonResponse(remainingAdmissionDocument());
      }
      if (url === "/api/v1/operations/organize/previews/preview-1") {
        return jsonResponse(remainingPreviewDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(
      within(table).getByRole("button", { name: "Movies，整理详情" }),
    );
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findByText("暂停运行的剩余范围");
    // The plan summary defaults to the exact ready subset the backend
    // advertised; the confirm button names that count.
    const itemChoice =
      await within(detail).findByLabelText("选择 One.2001.mkv");
    await waitFor(() => expect(itemChoice).toBeChecked());

    await user.click(
      within(detail).getByRole("button", { name: "确认继续整理剩余 1 项" }),
    );
    // The lost response is an unknown outcome: the submitted admission is
    // kept for one explicit reconciliation read, never replayed.
    expect(await within(detail).findByText(/确认响应未送达/)).toBeVisible();
    expect(executePosts).toEqual([
      "/api/v1/operations/organize/previews/preview-1/execute",
    ]);

    holdDetailReads = true;
    await user.click(
      within(detail).getByRole("button", {
        name: "核对本次确认的持久状态",
      }),
    );
    expect(admissionReads).toHaveLength(1);

    // The known admission is stated in this same task detail; the retired
    // execution-page phrase is gone and the next step names this detail.
    const admittedMessage =
      await within(detail).findByText(/该精确子集已经受理/);
    expect(admittedMessage).toBeVisible();
    expect(admittedMessage.textContent).not.toContain("关联执行");
    expect(admittedMessage.textContent).toContain("本任务详情正在刷新");

    // The stated refresh really happens: the overview re-read and the
    // invalidated run-items read are both re-issued and their results land
    // in this same detail.
    await waitFor(() => expect(heldOverviewResponses.length).toBe(1));
    await waitFor(() => expect(heldItemsResponses.length).toBe(1));
    heldOverviewResponses[0]!(jsonResponse(refreshedOverview));
    heldItemsResponses[0]!(jsonResponse(emptyItemsPageDocument()));
    expect(await within(detail).findByText(/2026-09-09/)).toBeVisible();

    // One deliberate confirmation, one bounded reconciliation read; the
    // submission was never replayed and the operator never left this task.
    expect(executePosts).toEqual([
      "/api/v1/operations/organize/previews/preview-1/execute",
    ]);
    expect(admissionReads).toHaveLength(1);
    expect(
      within(detail).queryByRole("button", {
        name: "核对本次确认的持久状态",
      }),
    ).toBeNull();
  });

  it("shows only the reopened run's evidence after switching runs", async () => {
    const user = userEvent.setup();
    let releaseFirstOverview!: (response: Response) => void;
    const slowFirst = new Promise<Response>((resolve) => {
      releaseFirstOverview = resolve;
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/v1/operations/runs?") ||
        url === "/api/v1/operations/runs"
      ) {
        return jsonResponse(
          pageDocument({
            items: [
              runDocument(),
              runDocument({
                run_id: "task-002",
                source_scope: "Shows",
              }),
            ],
            total: 2,
          }),
        );
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return slowFirst;
      }
      if (url === "/api/v1/operations/runs/task-002") {
        return jsonResponse(
          runDocument({
            run_id: "task-002",
            source_scope: "Shows",
            target_scope: "Media/Shows",
          }),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(
      within(table).getByRole("button", { name: "Movies，预览详情" }),
    );
    await screen.findByRole("dialog", { name: "运行详情" });
    // Switching runs goes through the same real entries: close, then select
    // the other row while the first overview read is still in flight.
    await user.click(
      within(screen.getByRole("dialog", { name: "运行详情" })).getByRole(
        "button",
        { name: "关闭详情" },
      ),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    await user.click(
      within(table).getByRole("button", { name: "Shows，预览详情" }),
    );
    const second = await screen.findByRole("dialog", { name: "运行详情" });
    await within(second).findByText("Media/Shows");
    // The late first-run response can never leak into the open card.
    releaseFirstOverview(jsonResponse(runDocument()));
    await waitFor(() =>
      expect(within(second).queryByText("Movies")).toBeNull(),
    );
    expect(within(second).getByText("Media/Shows")).toBeTruthy();
  });
});

/**
 * PATCH-20261113-3 host fixtures: one exact admitted Files preparation whose
 * identity the selected Task's overview publishes. The preparation/intent/
 * summary documents are the same shared manual-operations fixture the dialog's
 * own tests use, so the hosted card exercises the real typed query boundary.
 */
const HOST_DISCOVERY_ID = "discovery-1";
const HOST_INTENT_ID = "intent-1";
const HOST_PREVIEW_ID = "preview-1";

function hostAction(): Record<string, unknown> {
  return {
    available: false,
    method: "POST",
    path: null,
    requiresVersion: true,
    sideEffects: "none",
    refusal: null,
    pendingReason: null,
    reason: null,
    nextAction: null,
  };
}

function hostDiscoveryDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    journey: "discovery",
    discoveryId: HOST_DISCOVERY_ID,
    resourceLibraryId: "library",
    storageId: "source",
    configurationSnapshotId: "active-1",
    status: "completed",
    version: 5,
    createdAt: "2026-01-01T00:00:00+00:00",
    updatedAt: "2026-01-01T00:00:00+00:00",
    selection: {
      scopeCount: 1,
      scopes: [{ kind: "file", path: "Movies/One.2001.mkv" }],
      existing: [],
      refused: [],
    },
    budgets: {},
    progress: {
      phase: "prepared",
      visitedEntries: 1,
      visitedDirectories: 0,
      pageFetches: 1,
      primarySources: 1,
      excludedEntries: 0,
      unstableEntries: 0,
      errorEntries: 0,
      activeSeconds: 0.1,
      incomplete: false,
      incompleteReason: null,
      refusalReasons: [],
      materialRefusal: null,
      findings: [],
      reasons: [],
      message: "the exact zero-mutation plan summary is ready",
    },
    primarySourceCount: 1,
    organizeFlow: {
      taskId: "task-001",
      status: "running",
      continuable: true,
    },
    admissionRequestId: null,
    autoPrepare: true,
    prepared: true,
    previewId: HOST_PREVIEW_ID,
    intentId: HOST_INTENT_ID,
    frozen: true,
    frozenAt: "2026-01-01T00:00:00+00:00",
    pauseRequested: false,
    cancelRequested: false,
    nextObservationAt: null,
    worker: {
      ready: true,
      condition: "ready",
      durableState: "ready",
      nextAction: "claim",
    },
    actions: {
      pause: hostAction(),
      resume: hostAction(),
      cancel: hostAction(),
      finalize: hostAction(),
      prepare: hostAction(),
    },
    sources: [],
    nextAction: "open the linked exact plan summary",
    failure: null,
    sideEffects: "none",
    zeroMutation: true,
    execution: "not_available_from_discovery",
    ...overrides,
  };
}

function hostPreviewDocument(): Record<string, unknown> {
  const value = JSON.parse(
    JSON.stringify(
      (manualOperationsFixture as Record<string, unknown>)[
        "organizePreviewDetail"
      ],
    ),
  ) as Record<string, unknown>;
  value["previewId"] = HOST_PREVIEW_ID;
  value["intentId"] = HOST_INTENT_ID;
  value["current"] = true;
  const items = value["items"] as Record<string, unknown>[];
  const first = items[0]!;
  first["itemId"] = "item-1";
  first["previewItemId"] = "pitem-1";
  const source = first["source"] as Record<string, unknown>;
  source["path"] = "Movies/One.2001.mkv";
  source["filename"] = "One.2001.mkv";
  const selection = value["selection"] as Record<string, unknown>;
  selection["selectedItemIds"] = ["item-1"];
  selection["unselectedItemIds"] = [];
  value["executionCandidateItemIds"] = ["item-1"];
  const actions = value["actions"] as Record<string, Record<string, unknown>>;
  actions["execute"]!["path"] =
    `/api/v1/operations/organize/previews/${HOST_PREVIEW_ID}/execute`;
  return value;
}

function hostIntentDocument(): Record<string, unknown> {
  const value = JSON.parse(
    JSON.stringify(
      (manualOperationsFixture as Record<string, unknown>)[
        "organizeIntentChoice"
      ],
    ),
  ) as Record<string, unknown>;
  value["intentId"] = HOST_INTENT_ID;
  const items = value["items"] as Record<string, unknown>[];
  const first = items[0]!;
  first["itemId"] = "item-1";
  const source = first["source"] as Record<string, unknown>;
  source["path"] = "Movies/One.2001.mkv";
  source["filename"] = "One.2001.mkv";
  const actions = value["actions"] as Record<string, Record<string, unknown>>;
  actions["choice"]!["path"] =
    `/api/v1/operations/organize/intents/${HOST_INTENT_ID}/items/{itemId}/choice`;
  value["latestPlan"] = {
    previewId: HOST_PREVIEW_ID,
    status: "previewed",
    current: true,
    intentVersion: 2,
    createdAt: "2026-01-01T00:00:00+00:00",
    updatedAt: "2026-01-01T00:00:00+00:00",
    truncated: false,
  };
  return value;
}

function hostExecutionDocument(taskId: string): Record<string, unknown> {
  const value = JSON.parse(
    JSON.stringify(
      (manualOperationsFixture as Record<string, unknown>)["organizeExecution"],
    ),
  ) as Record<string, unknown>;
  value["executionId"] = "exec-1";
  value["previewId"] = HOST_PREVIEW_ID;
  value["intentId"] = HOST_INTENT_ID;
  value["taskId"] = taskId;
  value["selectedItemIds"] = ["item-1"];
  value["unselectedItemIds"] = [];
  const actions = value["actions"] as Record<string, Record<string, unknown>>;
  actions["detail"]!["path"] = "/api/v1/operations/organize/executions/exec-1";
  actions["task"]!["path"] = `/api/v1/operations/tasks/${taskId}`;
  const items = value["items"] as Record<string, unknown>[];
  items[0]!["itemId"] = "item-1";
  items[0]!["taskId"] = taskId;
  items[0]!["taskItemId"] = "task-item-1";
  return value;
}

interface OrganizeHostBackend {
  readonly calls: {
    discoveryReads: number;
    intentReads: number;
    overviewReads: number;
    posts: string[];
  };
  readonly state: { intentUnavailable: boolean; executeTaskId: string };
}

/**
 * Serve the task center and the one exact preparation association. `overview`
 * and `discovery` override the settled durable state; every request is counted
 * so the tests can prove what opening/continuing actually read or submitted.
 */
function stubOrganizeHost(
  options: {
    readonly overview?: Record<string, unknown>;
    readonly discovery?: Record<string, unknown>;
    readonly intentUnavailable?: boolean;
  } = {},
): OrganizeHostBackend {
  const backend: OrganizeHostBackend = {
    calls: { discoveryReads: 0, intentReads: 0, overviewReads: 0, posts: [] },
    state: {
      intentUnavailable: options.intentUnavailable ?? false,
      executeTaskId: "task-001",
    },
  };
  stubFetch(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (method !== "GET") backend.calls.posts.push(url);
    if (
      url.startsWith("/api/v1/operations/runs?") ||
      url === "/api/v1/operations/runs"
    ) {
      return jsonResponse(pageDocument());
    }
    if (url === "/api/v1/operations/runs/task-001") {
      backend.calls.overviewReads += 1;
      return jsonResponse(
        runDocument({
          filesPreparation: {
            discoveryId: HOST_DISCOVERY_ID,
            resourceLibraryId: "source",
            continuable: true,
          },
          ...options.overview,
        }),
      );
    }
    if (
      url === `/api/v1/operations/organize/discoveries/${HOST_DISCOVERY_ID}` &&
      method === "GET"
    ) {
      backend.calls.discoveryReads += 1;
      return jsonResponse(hostDiscoveryDocument(options.discovery));
    }
    if (
      /\/operations\/organize\/discoveries\/[^/]+\/analyze$/.test(url) &&
      method === "POST"
    ) {
      return jsonResponse(hostDiscoveryDocument(options.discovery));
    }
    if (
      url === `/api/v1/operations/organize/intents/${HOST_INTENT_ID}` &&
      method === "GET"
    ) {
      backend.calls.intentReads += 1;
      if (backend.state.intentUnavailable) {
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return jsonResponse(hostIntentDocument());
    }
    if (
      url === `/api/v1/operations/organize/previews/${HOST_PREVIEW_ID}` &&
      method === "GET"
    ) {
      return jsonResponse(hostPreviewDocument());
    }
    if (url.startsWith("/api/v1/operations/organize/executions")) {
      return jsonResponse({
        items: [],
        total: 0,
        limit: 100,
        truncated: false,
      });
    }
    if (
      url ===
        `/api/v1/operations/organize/previews/${HOST_PREVIEW_ID}/execute` &&
      method === "POST"
    ) {
      return jsonResponse(
        hostExecutionDocument(backend.state.executeTaskId),
        202,
      );
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
  return backend;
}

describe("PATCH-20261113-3 task-center hosted preparation", () => {
  it("restores the same exact preparation from the canonical direct address", async () => {
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations?run=task-001&tab=records&dialog=organize",
    );

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    expect(router.state.location.pathname).toBe("/operations");
    const search = new URLSearchParams(router.history.location.search);
    expect(search.get("run")).toBe("task-001");
    expect(search.get("tab")).toBe("records");
    expect(search.get("dialog")).toBe("organize");
    // The address carries no preparation or library identity.
    expect(search.get("discoveryId")).toBeNull();
    expect(search.get("resourceLibraryId")).toBeNull();
    expect(backend.calls.posts).toEqual([]);
  });

  it("explains a marker without an exact Task and starts no read", async () => {
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?dialog=organize");

    const notice = await screen.findByRole("dialog", {
      name: "无法继续这次整理",
    });
    expect(within(notice).getByText("继续整理地址缺少准确任务")).toBeVisible();
    expect(backend.calls.overviewReads).toBe(0);
    expect(backend.calls.discoveryReads).toBe(0);
    await userEvent
      .setup()
      .click(within(notice).getByRole("button", { name: "关闭" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "无法继续这次整理" }),
      ).toBeNull(),
    );
    expect(router.state.location.pathname).toBe("/operations");
    expect(new URLSearchParams(router.history.location.search).get("run")).toBe(
      null,
    );
    expect(backend.calls.posts).toEqual([]);
  });

  it("explains a Task without the exact association without guessing one", async () => {
    const backend = stubOrganizeHost({
      overview: { filesPreparation: null },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&dialog=organize");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const notice = await screen.findByRole("dialog", {
      name: "无法继续这次整理",
    });
    expect(
      within(notice).getByText("这个任务没有关联的文件整理准备"),
    ).toBeVisible();
    expect(within(detail).queryByRole("link", { name: "继续整理" })).toBeNull();
    expect(backend.calls.discoveryReads).toBe(0);
    expect(backend.calls.posts).toEqual([]);
  });

  it("drops an unknown hosted-card marker instead of replaying it", async () => {
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations?run=task-001&dialog=execute",
    );

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    expect(await within(detail).findByText("流程状态")).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull();
    expect(
      screen.queryByRole("dialog", { name: "无法继续这次整理" }),
    ).toBeNull();
    expect(router.state.location.search["dialog"]).toBeUndefined();
    expect(backend.calls.discoveryReads).toBe(0);
    expect(backend.calls.posts).toEqual([]);
  });

  it("reopens ended work as read-only history from the canonical address", async () => {
    const backend = stubOrganizeHost({
      overview: {
        status: "completed",
        current_stage: null,
        filesPreparation: {
          discoveryId: HOST_DISCOVERY_ID,
          resourceLibraryId: "source",
          continuable: false,
        },
      },
      discovery: {
        status: "completed",
        organizeFlow: {
          taskId: "task-001",
          status: "completed",
          continuable: false,
        },
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&dialog=organize");

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    expect(await within(dialog).findByText(/本次整理工作已结束/)).toBeVisible();
    const history = await within(dialog).findByRole("region", {
      name: "只读原计划摘要",
    });
    expect(within(history).getByText(/方案 preview-1/)).toBeVisible();
    expect(
      within(dialog).queryByRole("button", { name: /确认整理/ }),
    ).toBeNull();
    expect(
      within(dialog).queryByRole("button", { name: /保存并重新分析/ }),
    ).toBeNull();
    expect(backend.calls.posts).toEqual([]);
  });

  it("distinguishes a failed original-summary read and retries it in place", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost({
      intentUnavailable: true,
      overview: {
        status: "failed",
        current_stage: null,
        filesPreparation: {
          discoveryId: HOST_DISCOVERY_ID,
          resourceLibraryId: "source",
          continuable: false,
        },
      },
      discovery: {
        status: "failed",
        prepared: false,
        previewId: null,
        intentId: HOST_INTENT_ID,
        organizeFlow: {
          taskId: "task-001",
          status: "failed",
          continuable: false,
        },
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&dialog=organize");

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    expect(
      await within(dialog).findByText(/原计划摘要暂时无法读取/),
    ).toBeVisible();
    expect(within(dialog).queryByText(/从未生成过计划摘要/)).toBeNull();

    backend.state.intentUnavailable = false;
    await user.click(
      within(dialog).getByRole("button", { name: "重新读取原计划摘要" }),
    );
    expect(
      await within(dialog).findByRole("region", { name: "只读原计划摘要" }),
    ).toBeVisible();
    expect(backend.calls.posts).toEqual([]);
  });

  it("states plainly when ended work never generated a summary", async () => {
    stubOrganizeHost({
      overview: {
        status: "failed",
        current_stage: null,
        filesPreparation: {
          discoveryId: HOST_DISCOVERY_ID,
          resourceLibraryId: "source",
          continuable: false,
        },
      },
      discovery: {
        status: "failed",
        prepared: false,
        previewId: null,
        intentId: null,
        organizeFlow: {
          taskId: "task-001",
          status: "failed",
          continuable: false,
        },
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&dialog=organize");

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    expect(await within(dialog).findByText(/从未生成过计划摘要/)).toBeVisible();
    expect(
      within(dialog).queryByRole("region", { name: "只读原计划摘要" }),
    ).toBeNull();
  });

  it("never carries A's preparation into another selected Task", async () => {
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations?run=task-001&dialog=organize",
    );

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    expect(backend.calls.discoveryReads).toBeGreaterThan(0);
    const discoveryReadsForA = backend.calls.discoveryReads;

    // The other Task has no exact association in this stub. The host must
    // resolve B from its own backend read and must not keep A's card, draft or
    // preparation (the dialog is keyed by the resolved exact preparation).
    void router.navigate({
      to: "/operations",
      search: { run: "task-002", dialog: "organize" },
    });
    const notice = await screen.findByRole("dialog", {
      name: "无法继续这次整理",
    });
    expect(within(notice).getByText("Record not found")).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull();
    expect(backend.calls.discoveryReads).toBe(discoveryReadsForA);
    expect(backend.calls.posts).toEqual([]);
  });

  it("protects unsaved drafts against leaving the task center without losing the card", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await user.click(
      await within(detail).findByRole("link", { name: "继续整理" }),
    );
    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await user.selectOptions(
      await within(dialog).findByLabelText("识别类型 One.2001.mkv"),
      "B",
    );
    // A route-changing exit (the real browser Back reaches the same blocker
    // through its popstate path) must not silently drop the draft.
    router.history.push("/ui-v2/resourcelib/files");
    const prompt = await screen.findByRole("alertdialog");
    expect(
      within(prompt).getByText(/有尚未保存的逐文件修正草稿/),
    ).toBeVisible();
    await user.click(within(prompt).getByRole("button", { name: "继续编辑" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(screen.getByRole("dialog", { name: "整理所选文件" })).toBeVisible();
    expect(router.state.location.pathname).toBe("/operations");
    expect(
      new URLSearchParams(router.history.location.search).get("dialog"),
    ).toBe("organize");
    expect(backend.calls.posts).toEqual([]);
  });

  it("hands a proved admission to the exact returned Task and refreshes it", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations?run=task-001&dialog=organize",
    );

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(within(dialog).getByRole("button", { name: /整批复核/ }));
    await user.click(
      await within(dialog).findByRole("button", {
        name: "确认整理 1 项",
      }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    expect(router.state.location.pathname).toBe("/operations");
    const search = new URLSearchParams(router.history.location.search);
    expect(search.get("run")).toBe("task-001");
    expect(search.get("dialog")).toBeNull();
    expect(
      backend.calls.posts.filter((url) => url.endsWith("/execute")),
    ).toHaveLength(1);
    // The exact Task's overview is explicitly re-read after the handoff; the
    // same-route navigation alone is not relied on to refresh anything.
    await waitFor(() =>
      expect(backend.calls.overviewReads).toBeGreaterThanOrEqual(2),
    );
    expect(
      await screen.findByRole("dialog", { name: "运行详情" }),
    ).toBeVisible();
  });
});
