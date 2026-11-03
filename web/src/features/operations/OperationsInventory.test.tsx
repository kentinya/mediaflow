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

    await screen.findByRole("region", { name: "运行详情" });
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
    const detail = await screen.findByRole("region", { name: "运行详情" });
    expect(await within(detail).findByText("手动")).toBeVisible();
    // The disposition filter option shares the status label text, so the
    // bounded presence check uses the All* variant over the detail panel.
    expect(within(detail).getAllByText(/进行中/).length).toBeGreaterThan(0);
    // The overview shows known durable facts and labels completed items as
    // not an organize-success claim while running.
    expect(within(detail).getByText(/不代表整理成功/)).toBeVisible();
    // The historical source and target scope the projection publishes are
    // part of the visible overview (absent evidence renders explicitly).
    expect(within(detail).getByText("Movies")).toBeVisible();
    expect(within(detail).getByText("Library/History")).toBeVisible();
    // A deep evidence link that stays inside the center's own run context:
    // the retired mixed Task collection is closed (B46.4-04).
    expect(
      within(detail).getByRole("link", {
        name: "在任务中心查看该运行的详情",
      }),
    ).toHaveAttribute("href", "/ui-v2/operations?run=task-001");

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
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&view=running");

    const detail = await screen.findByRole("region", { name: "运行详情" });
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
    const detail = await screen.findByRole("region", { name: "运行详情" });
    expect(within(detail).getAllByText("失败").length).toBeGreaterThan(0);
    expect(
      within(detail).queryByText(/每个必要条目都有精确关联的真实成功证据/),
    ).toBeNull();
    // Selecting the really recovered run publishes that exact claim.
    await user.click(
      within(recoveredRow).getByRole("button", { name: /恢复完成/ }),
    );
    const recoveredDetail = await screen.findByRole("region", {
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
});
