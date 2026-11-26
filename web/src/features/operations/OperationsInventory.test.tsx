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
import { runProblemFilesQueryKey } from "./run-query";
import { beginOrganizeConfirmationRetention } from "./organize-confirmation-session";

const TOKEN = "operations-inventory-token";

function signInForOrganize() {
  authStore.setSession({
    principalId: TOKEN,
    accountId: "operations-account",
    username: "operator",
    roles: [],
    permissions: ["read", "submit_dry_run", "execute_manual_organize"],
  });
}

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
  window.localStorage.clear();
  window.sessionStorage.clear();
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

function problemFileItemDocument(overrides: Record<string, unknown> = {}) {
  return {
    item_id: "problem-item-a",
    task_id: "task-001",
    storage_id: "source",
    resource_library_id: "movies",
    source_path: "Movies/problem-a.mkv",
    status: "waiting_metadata_correction",
    stage: "waiting_metadata_correction",
    attempts: 1,
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:00:00+00:00",
    destination_storage_id: null,
    destination_path: null,
    execution_status: null,
    failure: null,
    checkpoint: {
      status: "waiting_metadata_correction",
      stage: "waiting_metadata_correction",
      raw_stage: "waiting_metadata_correction",
      blocker_kind: null,
      blocker_id: null,
      effect_certainty: "none",
      retry_safety: "safe",
      permitted_action_ids: ["resolve_metadata_correction"],
      refusal_reason: null,
      checkpoint_version: "a".repeat(64),
      recovery_request: null,
    },
    ...overrides,
  };
}

function progressDocument(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    kind: "organize",
    unit: "主条目",
    unit_key: "task_items",
    basis: "整理计数:成功表示已验证的存储操作结果。",
    success_means: "已验证的存储操作成功",
    known_total: 1,
    indeterminate: false,
    processed: 1,
    dispositions: {
      pending: 0,
      active: 0,
      waiting: 1,
      success: 0,
      skipped: 0,
      failed_partial: 0,
      ignored: 0,
      cancelled: 0,
    },
    confirmed_success: 0,
    uncertain_success: 0,
    scan_errors: null,
    scan_discovery_complete: null,
    scan_progress: {},
    attachment_steps: 0,
    effect_counts: {},
    results_total: 0,
    results_complete: true,
    sideEffects: "none",
    ...overrides,
  };
}

function manualSubmissionDocument(overrides: Record<string, unknown> = {}) {
  return {
    executionId: "execution-1",
    previewId: "preview-1",
    intentVersion: 3,
    selectedItemIds: ["item-1"],
    status: "completed",
    createdAt: "2026-08-22T12:01:00+00:00",
    destructiveAuthority: {
      allowOverwrite: false,
      allowSourceCleanup: false,
    },
    items: [
      {
        itemId: "item-1",
        taskItemId: "task-item-1",
        status: "success",
        resultId: "result-1",
        sourcePath: "Movies/One.2001.mkv",
        checkpointPath: "/api/tasks/task-001/items/task-item-1",
      },
    ],
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

function problemFilesPageDocument(overrides: Record<string, unknown> = {}) {
  const zero = {
    recognition: 0,
    metadata: 0,
    classification: 0,
    conflict: 0,
  };
  return {
    problem: null,
    limit: 20,
    items: [],
    total: 0,
    problem_file_total: 0,
    task_total: 0,
    problem_file_counts: zero,
    from: null,
    to: null,
    truncated: false,
    previous_cursor: null,
    next_cursor: null,
    sideEffects: "none",
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
      url.startsWith("/api/operations/runs?") ||
      url === "/api/operations/runs"
    ) {
      return jsonResponse(page);
    }
    if (url.startsWith("/api/operations/problem-items")) {
      return jsonResponse(problemFilesPageDocument());
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
    renderApp("/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    // Chinese business labels describe operation and state.
    expect((await screen.findAllByText("整理")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("失败").length).toBeGreaterThan(0);
    expect(screen.getAllByText("元数据问题").length).toBeGreaterThan(0);
    // The unknown legacy command stays honest.
    expect(screen.getByText(/未识别的历史命令/)).toBeVisible();
    // Missing historical scope evidence is explicitly unavailable.
    expect(screen.getByText("不可用")).toBeVisible();
    // The four first-level views are present on one navigation row; the four
    // recovery types are filters inside Attention and the retired Failure
    // Recovery view is gone.
    for (const label of ["全部任务", "进行中", "需要处理", "已结束"]) {
      expect(screen.getByRole("button", { name: label })).toBeVisible();
    }
    for (const label of ["识别恢复", "元数据恢复", "分类恢复", "冲突处理"]) {
      expect(screen.queryByRole("button", { name: label })).toBeNull();
    }
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
      requested.some((url) => url.includes("/api/workers/readiness")),
    ).toBe(false);
    expect(
      requested.some((url) => url.includes("/api/management/readiness")),
    ).toBe(false);
    expect(requested.some((url) => url.includes("/api/operations/runs"))).toBe(
      true,
    );
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
            status: "completed",
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
    renderApp("/operations");

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

    await user.click(within(views).getByRole("button", { name: "需要处理" }));
    // Attention is the shared problem-file list with its five light filters,
    // not a task table with a separate type view.
    const filters = await screen.findByRole("group", { name: "问题类型" });
    for (const label of ["全部", "识别", "元数据", "分类", "冲突"]) {
      expect(
        within(filters).getByRole("button", { name: new RegExp(`^${label}`) }),
      ).toBeVisible();
    }
    await user.click(within(filters).getByRole("button", { name: /^元数据/ }));
    expect(
      await screen.findByRole("heading", { name: "当前没有问题文件" }),
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
    const { router } = renderApp("/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    await waitFor(() =>
      expect(
        requested.some((url) => url.includes("/api/operations/runs")),
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
      `/operations?view=${view}&q=old&status=failed&source=Movies&command=organize&attention=true&problem=metadata&cursor=old`,
    );
    const problemSurface = [
      "attention",
      "recognition",
      "metadata",
      "classification",
      "conflict",
    ].includes(view);
    await screen.findByRole("heading", {
      name: problemSurface ? "当前没有问题文件" : "还没有运行记录",
    });
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
        .filter((url) => url.startsWith("/api/operations/runs?"))
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
            params.get("view") ===
              (problemSurface ? "attention" : view === "all" ? null : view)
          );
        }),
    ).toBe(true);
  });

  it("keeps the date range and clear without timezone explanations", async () => {
    stubInventoryJourney(pageDocument({ items: [], total: 0 }));
    authStore.setToken(TOKEN);
    renderApp("/operations?view=ended&from=2026-08-01&to=2026-08-02");
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
      if (url.startsWith("/api/operations/runs?")) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(runDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/operations?q=secret&status=failed&source=Movies%2Fbeta" +
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
      url.startsWith("/api/operations/runs?"),
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
      if (!url.startsWith("/api/operations/runs?")) {
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }
      const from =
        new URL(url, "http://mediaflow.test").searchParams.get("from") ?? "all";
      return new Promise<Response>((resolve) => pending.set(from, resolve));
    });
    authStore.setToken(TOKEN);
    renderApp("/operations");

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
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        overviewRead = true;
        return jsonResponse(runDocument({ target_scope: "Library/History" }));
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    await waitFor(() => expect(overviewRead).toBe(true));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await user.click(
      await within(detail).findByRole("button", { name: "操作记录" }),
    );
    await user.click(within(detail).getByText("任务信息与技术诊断"));
    expect(within(detail).getByText("手动")).toBeVisible();
    expect(within(detail).getByText("Library/History")).toBeVisible();
    await user.click(within(detail).getByRole("button", { name: "任务详情" }));
    // The disposition filter option shares the status label text, so the
    // bounded presence check uses the All* variant over the detail panel.
    expect(within(detail).getAllByText(/进行中/).length).toBeGreaterThan(0);
    // The overview leads with the flow status and own facts; the removed
    // "processed is not organize success" tutorial is not printed.
    expect(
      within(detail).getByRole("region", { name: "状态与流程" }),
    ).toBeVisible();
    expect(within(detail).queryByText(/不代表整理成功/)).toBeNull();
    // A run without a Files preparation association publishes no preparation
    // area at all, not even an empty one.
    expect(
      within(detail).queryByRole("region", { name: "文件整理准备" }),
    ).toBeNull();
    // The historical source stays in the visible detail title.
    expect(within(detail).getByText("Movies")).toBeVisible();
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

  it("reports an unconfirmed Files preparation as waiting instead of admitted execution (Task 59.2 AC-04/AC-05)", async () => {
    const overview = runDocument({
      status: "running",
      command: "manual_organize",
      command_label: "手动整理",
      current_stage: null,
      total_items: 1,
      completed_items: 0,
      processed_items: 1,
      filesPreparation: {
        discoveryId: "discovery-1",
        resourceLibraryId: "source",
        continuable: true,
      },
      progress: progressDocument(),
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/operations/runs?")) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    signInForOrganize();
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    // The durable waiting item and the still-continuable Files preparation
    // are the first-screen evidence; a whole-Task `running` status is not an
    // admission claim.
    expect(await within(detail).findByText("等待确认")).toBeVisible();
    expect(
      within(detail).getByText("点击「继续整理」，核对 1 个文件的方案。"),
    ).toBeVisible();
    // The processed range names its preparation/analysis basis and the
    // still-waiting file instead of borrowing an execution or success claim.
    const progress = within(detail).getByRole("region", { name: "处理进度" });
    expect(
      within(progress).getByText(
        "已进入准备与分析 1 / 1 个主条目（准备与分析计数，含 1 个等待确认）",
      ),
    ).toBeVisible();
    expect(
      within(progress).getByText("处理进度", { exact: true }),
    ).toBeVisible();
    // The processed range is text: no bar implies the waiting files ran.
    expect(within(progress).queryByRole("progressbar")).toBeNull();
    // The zero executed files stay a separate fact from the waiting range.
    expect(
      within(progress).getByText(
        "尚未执行文件操作，暂无文件结果；1 个文件等待确认，确认前不执行文件操作。",
      ),
    ).toBeVisible();
    expect(
      within(detail).queryByText("执行已受理，文件结果由后端独立记录。"),
    ).toBeNull();
    // The continuable preparation is the shared toolbar's primary action, so
    // both tabs offer the same next step.
    expect(within(detail).getByRole("link", { name: "继续整理" })).toHaveClass(
      "mf-button-primary",
    );
  });

  it("Task59.3 names the real Files preparation stage before any plan exists", async () => {
    const user = userEvent.setup();
    const discoveryBase = hostDiscoveryDocument();
    let discovery: Record<string, unknown> = {
      ...discoveryBase,
      status: "queued",
      version: 1,
      previewId: null,
      intentId: null,
      prepared: false,
      frozen: false,
      progress: {
        ...(discoveryBase.progress as Record<string, unknown>),
        phase: "queued",
      },
    };
    // This is the real state immediately after a Files admission: the Task
    // exists, the Worker has not run, and the plan is not generated.
    let overview = runDocument({
      status: "pending",
      current_stage: null,
      total_items: 1,
      completed_items: 0,
      processed_items: 0,
      success_items: 0,
      filesPreparation: {
        discoveryId: "discovery-1",
        resourceLibraryId: "source",
        continuable: true,
      },
      progress: progressDocument({
        known_total: 1,
        processed: 0,
        dispositions: {
          pending: 1,
          active: 0,
          waiting: 0,
          success: 0,
          skipped: 0,
          failed_partial: 0,
          ignored: 0,
          cancelled: 0,
        },
        results_total: 0,
        effect_counts: {},
      }),
    });
    let previewReads = 0;
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      if (url === "/api/operations/organize/discoveries/discovery-1") {
        return jsonResponse(discovery);
      }
      if (url === `/api/operations/organize/previews/${HOST_PREVIEW_ID}`) {
        previewReads += 1;
        return jsonResponse(hostPreviewDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations");

    // The real entry is the task list row, not a task-center deep link.
    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    await waitFor(() =>
      expect(
        new URLSearchParams(router.history.location.search).get("run"),
      ).toBe("task-001"),
    );
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const flow = await within(detail).findByRole("region", {
      name: "状态与流程",
    });
    // An admitted preparation is not an admitted execution: the title names
    // the discovery stage and the page shows no file result.
    expect(
      await within(flow).findByRole("heading", {
        name: "准备已受理，正在排队",
      }),
    ).toBeVisible();
    expect(
      within(flow).queryByRole("heading", { name: "已受理，等待执行" }),
    ).toBeNull();
    const progress = within(detail).getByRole("region", { name: "处理进度" });
    expect(
      within(progress).getByText(
        "已进入准备与分析 0 / 1 个主条目（准备与分析计数；其余尚未结束）",
      ),
    ).toBeVisible();
    expect(within(progress).queryByText(/^待处理\s+1$/)).toBeNull();
    expect(within(progress).queryByRole("progressbar")).toBeNull();

    // The same detail follows the durable preparation read; no reopen and no
    // invented stage in between.
    discovery = hostDiscoveryDocument({
      status: "analyzing",
      version: 2,
      previewId: null,
      intentId: null,
      prepared: false,
      frozen: false,
    });
    await waitFor(
      () =>
        expect(
          within(flow).getByRole("heading", {
            name: "正在分析并生成方案",
          }),
        ).toBeVisible(),
      { timeout: 8_000 },
    );

    // The Worker publishes the exact plan: the same detail follows the
    // waiting items and reads that plan, and the progress names the
    // confirmation boundary instead of an execution range.
    overview = runDocument({
      status: "running",
      command: "manual_organize",
      command_label: "手动整理",
      current_stage: null,
      total_items: 1,
      completed_items: 0,
      processed_items: 1,
      filesPreparation: {
        discoveryId: "discovery-1",
        resourceLibraryId: "source",
        continuable: true,
      },
      progress: progressDocument(),
    });
    discovery = hostDiscoveryDocument({
      status: "completed",
      version: 3,
      previewId: HOST_PREVIEW_ID,
      intentId: HOST_INTENT_ID,
      prepared: true,
      frozen: true,
    });
    await waitFor(
      () =>
        expect(
          within(flow).getByRole("heading", { name: "等待确认" }),
        ).toBeVisible(),
      { timeout: 8_000 },
    );
    await waitFor(() => expect(previewReads).toBeGreaterThan(0), {
      timeout: 8_000,
    });
    expect(within(progress).queryByRole("progressbar")).toBeNull();
    expect(
      within(progress).getByText(
        "尚未执行文件操作，暂无文件结果；1 个文件等待确认，确认前不执行文件操作。",
      ),
    ).toBeVisible();
  }, 20_000);

  it("states one normal completion heading before the real progress and results (Task 59.3 AC-06)", async () => {
    const overview = runDocument({
      status: "completed",
      current_stage: null,
      total_items: 2,
      completed_items: 2,
      processed_items: 2,
      success_items: 2,
      progress: progressDocument({
        known_total: 2,
        processed: 2,
        dispositions: {
          pending: 0,
          active: 0,
          waiting: 0,
          success: 2,
          skipped: 0,
          failed_partial: 0,
          ignored: 0,
          cancelled: 0,
        },
        confirmed_success: 2,
        results_total: 2,
        effect_counts: { verified_complete: 2 },
      }),
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const flow = await within(detail).findByRole("region", {
      name: "状态与流程",
    });
    // A normal completion is one heading; the old status pill, stage line and
    // second completion sentence are gone.
    expect(
      within(flow).getByRole("heading", { name: "流程已完成" }),
    ).toBeVisible();
    expect(within(flow).queryByText("本次整理已完成")).toBeNull();
    expect(within(flow).queryByText("流程状态")).toBeNull();
    expect(within(flow).queryByText("当前阶段")).toBeNull();
    const progress = within(detail).getByRole("region", { name: "处理进度" });
    expect(within(progress).getByText("已处理 2 / 2 个主条目")).toBeVisible();
    const results = within(detail).getByRole("region", { name: "文件结果" });
    expect(within(results).getByText("成功")).toBeVisible();
    // The approved reading order is unchanged: heading, progress, results.
    expect(
      flow.compareDocumentPosition(progress) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      progress.compareDocumentPosition(results) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("Task59.3 reads the current plan's confirmable sibling beside a business problem", async () => {
    const backend = stubOrganizeHost({
      overview: {
        status: "running",
        current_stage: null,
        total_items: 2,
        completed_items: 0,
        processed_items: 2,
        attention: true,
        problem_types: ["metadata"],
        problem_file_counts: {
          recognition: 0,
          metadata: 1,
          classification: 0,
          conflict: 0,
        },
        progress: progressDocument({
          known_total: 2,
          processed: 2,
          dispositions: {
            pending: 0,
            active: 0,
            waiting: 2,
            success: 0,
            skipped: 0,
            failed_partial: 0,
            ignored: 0,
            cancelled: 0,
          },
        }),
      },
    });
    signInForOrganize();
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    // The live plan names one confirmable sibling; the other waiting file keeps
    // its own metadata problem and is never folded into that confirmation.
    expect(
      await within(detail).findByRole("heading", { name: "等待确认" }),
    ).toBeVisible();
    expect(
      await within(detail).findByText(
        "1 个文件可确认，另有 1 个等待处理。点击「继续整理」，核对 1 个文件的方案。",
      ),
    ).toBeVisible();
    expect(within(detail).getByText("当前业务问题")).toBeVisible();
    expect(backend.calls.discoveryReads).toBeGreaterThan(0);
    expect(backend.calls.posts).toEqual([]);
  });

  it("does not count a preparation failure as an executed file before confirmation (Task 59.3)", async () => {
    const backend = stubOrganizeHost({
      overview: {
        status: "running",
        current_stage: null,
        total_items: 2,
        completed_items: 0,
        processed_items: 2,
        attention: true,
        problem_types: ["metadata"],
        problem_file_counts: {
          recognition: 0,
          metadata: 1,
          classification: 0,
          conflict: 0,
        },
        progress: progressDocument({
          known_total: 2,
          processed: 2,
          dispositions: {
            pending: 0,
            active: 0,
            waiting: 1,
            success: 0,
            skipped: 0,
            failed_partial: 1,
            ignored: 0,
            cancelled: 0,
          },
          effect_counts: {},
          results_total: 0,
        }),
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const progress = await within(detail).findByRole("region", {
      name: "处理进度",
    });
    // The failed sibling settled during metadata preparation and has no
    // Result row; only the still-waiting sibling is part of the confirmation.
    expect(
      await within(progress).findByText(
        "尚未执行文件操作，暂无文件结果；1 个文件等待确认，确认前不执行文件操作。",
      ),
    ).toBeVisible();
    expect(within(progress).queryByText(/已执行 1 个文件/)).toBeNull();
    expect(backend.calls.posts).toEqual([]);
  });

  it("does not call a recorded no-operation result an executed file (Task 59.3)", async () => {
    const backend = stubOrganizeHost({
      overview: {
        status: "running",
        current_stage: null,
        total_items: 2,
        completed_items: 0,
        processed_items: 2,
        attention: true,
        problem_types: ["metadata"],
        problem_file_counts: {
          recognition: 0,
          metadata: 1,
          classification: 0,
          conflict: 0,
        },
        progress: progressDocument({
          known_total: 2,
          processed: 2,
          dispositions: {
            pending: 0,
            active: 0,
            waiting: 1,
            success: 0,
            skipped: 0,
            failed_partial: 1,
            ignored: 0,
            cancelled: 0,
          },
          effect_counts: { none: 1 },
          results_total: 1,
        }),
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const progress = await within(detail).findByRole("region", {
      name: "处理进度",
    });
    // A formal Result can prove a refused/skipped outcome without any file
    // operation; it stays a recorded result, never an executed file count.
    expect(
      await within(progress).findByText(
        "已有文件结果，本次未执行文件操作；1 个文件等待确认，确认前不执行文件操作。",
      ),
    ).toBeVisible();
    expect(within(progress).queryByText(/已执行 1 个文件/)).toBeNull();
    expect(backend.calls.posts).toEqual([]);
  });

  it("states an already-admitted confirmation and a still-waiting sibling separately (Task 59.2 AC-04/AC-05)", async () => {
    const overview = runDocument({
      status: "running",
      command: "manual_organize",
      command_label: "手动整理",
      current_stage: null,
      total_items: 2,
      completed_items: 1,
      processed_items: 1,
      success_items: 1,
      filesPreparation: {
        discoveryId: "discovery-1",
        resourceLibraryId: "source",
        continuable: true,
      },
      progress: progressDocument({
        known_total: 2,
        processed: 2,
        dispositions: {
          pending: 0,
          active: 0,
          waiting: 1,
          success: 1,
          skipped: 0,
          failed_partial: 0,
          ignored: 0,
          cancelled: 0,
        },
        confirmed_success: 1,
        results_total: 1,
        effect_counts: { verified_complete: 1 },
      }),
      manualOrganizeSubmissions: [manualSubmissionDocument()],
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/operations/runs?")) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    signInForOrganize();
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    expect(await within(detail).findByText("等待确认")).toBeVisible();
    expect(
      within(detail).getByText(
        "已有 1 次确认记录被受理；点击「继续整理」，核对 1 个文件的方案。",
      ),
    ).toBeVisible();
    expect(
      within(detail).getByRole("link", { name: "继续整理" }),
    ).toBeVisible();
    // The full range does not hide the executed sibling: the settled result
    // and the still-unconfirmed file are stated separately.
    const progress = within(detail).getByRole("region", { name: "处理进度" });
    expect(
      within(progress).getByText(
        "已进入准备与分析 2 / 2 个主条目（准备与分析计数，含 1 个等待确认）",
      ),
    ).toBeVisible();
    expect(
      within(progress).getByText(
        "已执行 1 个文件；1 个文件等待确认，确认前不执行文件操作。",
      ),
    ).toBeVisible();
  });

  it("PATCH-20261113-3 continues the exact Files preparation above the preserved task center", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    signInForOrganize();
    const { router } = renderApp("/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    // The continuable state offers only the shared toolbar's next step; the
    // hosted card itself carries the confirmation boundary.
    expect(
      within(detail).queryByText(/此运行由文件页的整理选择发起/),
    ).toBeNull();
    const toolbar = within(detail).getByRole("navigation", {
      name: "运行详情与操作记录",
    });
    const link = await within(toolbar).findByRole("link", { name: "继续整理" });
    expect(link).toHaveClass("mf-button-primary");
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

  it("Task59.4 reads an in-progress hosted preparation from its exact address", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    backend.state.preparationPhase = "waiting";
    signInForOrganize();
    const { router } = renderApp("/operations?run=task-001&dialog=organize");
    const detail = await screen.findByRole("dialog", { name: "运行详情" });

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    // The hosted entry now reads the same real first preparation step and
    // facts as the Files host, instead of a second waiting body.
    expect(
      await within(dialog).findByText("正在等待来源文件稳定"),
    ).toBeVisible();
    expect(within(dialog).getByText("第 1 步，共 2 步")).toBeVisible();
    expect(within(dialog).getByText("来源资源库")).toBeVisible();
    expect(within(dialog).getByText("受理范围")).toBeVisible();
    expect(within(dialog).getByText("准备进度")).toBeVisible();
    expect(within(dialog).getByText(/已找到 10 个主文件/)).toBeVisible();
    expect(
      within(dialog).queryByRole("heading", { name: /第 1 \/ 1 个/ }),
    ).toBeNull();

    // The same Task's durable stage moves to analysis; the mounted hosted
    // preparation reads that exact second step without a new admission.
    backend.state.preparationPhase = "analyzing";
    expect(
      await within(dialog).findByText("生成整理方案", {}, { timeout: 5_000 }),
    ).toBeVisible();
    expect(within(dialog).getByText("第 2 步，共 2 步")).toBeVisible();
    expect(
      within(dialog).getByText(/已找到 10 个主文件 · 来源已冻结，正在分析/),
    ).toBeVisible();
    expect(backend.calls.posts).toEqual([]);

    // The linked plan then hands over to the existing managed review.
    backend.state.preparationPhase = "ready";
    await within(dialog).findByRole(
      "heading",
      { name: /第 1 \/ 1 个/ },
      { timeout: 5_000 },
    );
    expect(backend.calls.posts).toEqual([]);

    await user.click(within(dialog).getByRole("button", { name: /^关闭$/ }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    // Closing the exact address keeps the same Task detail behind it.
    expect(screen.getByRole("dialog", { name: "运行详情" })).toBe(detail);
    const closed = new URLSearchParams(router.history.location.search);
    expect(closed.get("run")).toBe("task-001");
    expect(closed.get("dialog")).toBeNull();
    expect(backend.calls.posts).toEqual([]);
  }, 20_000);

  it("Task59.2 continues from 操作记录 and returns to the same tab and control", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    signInForOrganize();
    const { router } = renderApp("/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const toolbar = await within(detail).findByRole("navigation", {
      name: "运行详情与操作记录",
    });
    const recordsTab = within(toolbar).getByRole("button", {
      name: "操作记录",
    });
    const link = await within(toolbar).findByRole("link", { name: "继续整理" });

    // The continue entry leaves the detail tab; 操作记录 keeps the same one.
    await user.click(recordsTab);
    expect(recordsTab).toHaveAttribute("aria-current", "page");
    expect(new URLSearchParams(router.history.location.search).get("tab")).toBe(
      "records",
    );
    expect(within(toolbar).getByRole("link", { name: "继续整理" })).toBe(link);

    await user.click(link);
    const dialog = await screen.findByRole("dialog", {
      name: "整理所选文件",
    });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    // The exact hosted preparation keeps the current tab context in its
    // address: no preparation or library identity is added to the browser.
    const opened = new URLSearchParams(router.history.location.search);
    expect(opened.get("run")).toBe("task-001");
    expect(opened.get("tab")).toBe("records");
    expect(opened.get("dialog")).toBe("organize");
    expect(opened.get("discoveryId")).toBeNull();
    expect(screen.getByRole("dialog", { name: "运行详情" })).toBe(detail);

    await user.click(within(dialog).getByRole("button", { name: /^关闭$/ }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    // Closing returns to the same task, the same tab and the exact control.
    const closed = new URLSearchParams(router.history.location.search);
    expect(closed.get("run")).toBe("task-001");
    expect(closed.get("tab")).toBe("records");
    expect(closed.get("dialog")).toBeNull();
    expect(screen.getByRole("dialog", { name: "运行详情" })).toBe(detail);
    expect(
      within(toolbar).getByRole("button", { name: "操作记录" }),
    ).toHaveAttribute("aria-current", "page");
    await waitFor(() => expect(document.activeElement).toBe(link));
    expect(backend.calls.posts).toEqual([]);
  });

  it("removes the ended flow's duplicate preparation entries and keeps its file truth", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
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
    const { router } = renderApp("/operations");

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
          url.startsWith("/api/operations/runs?") ||
          url === "/api/operations/runs"
        ) {
          return jsonResponse(pageDocument());
        }
        if (url === "/api/operations/runs/task-001") {
          return jsonResponse(runDocument(overrides));
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      });
      authStore.setToken(TOKEN);
      renderApp("/operations?run=task-001");

      const detail = await screen.findByRole("dialog", { name: "运行详情" });
      await within(detail).findByRole("region", { name: "状态与流程" });
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

  it("labels a failed primary-limit preparation and keeps it read-only", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(
          runDocument({
            status: "failed",
            current_stage: null,
            filesPreparation: {
              discoveryId: "discovery-1",
              resourceLibraryId: "source",
              continuable: false,
            },
            filesPreparationPrimaryLimit: true,
          }),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    expect(
      await within(detail).findByText("准备阶段超限，本次未执行整理"),
    ).toBeVisible();
    expect(
      within(detail).queryByRole("region", { name: "文件整理准备" }),
    ).toBeNull();
    expect(within(detail).queryByRole("link", { name: "继续整理" })).toBeNull();
  });

  it("PATCH-20261111-5 drops the continuable preparation area when the selected flow's own poll turns terminal", async () => {
    const requested: { url: string; method: string }[] = [];
    let overview = runDocument({
      status: "running",
      progress: progressDocument(),
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
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    signInForOrganize();
    const { router } = renderApp("/operations?run=task-001");

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
      if (url.startsWith("/api/operations/runs?")) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(runDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001&view=running");

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
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse({ error: { code: "internal_error" } }, 500);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations");

    await screen.findByRole("heading", { name: "任务中心" });
    expect(
      await screen.findByRole("heading", { name: "Operations unavailable" }),
    ).toBeVisible();
    expect(screen.queryByText("还没有运行记录")).toBeNull();
  });

  it("treats a malformed inventory response as a bounded failure, not an empty list", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse({ items: "everything", total: -1 });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations");

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
    renderApp("/operations");

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
    const { router } = renderApp("/operations");
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
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(pageOne);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations");

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

  it("switches to the shared Attention problem-file list through the server", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const attentionRun = runDocument({
      run_id: "task-002",
      task_id: "task-002",
      source_scope: "Movies/Needs review",
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
    const attentionPage = pageDocument({
      items: [attentionRun],
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
      items: [runDocument(), attentionRun],
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
    const problemPage = problemFilesPageDocument({
      items: [
        {
          run: attentionRun,
          item: problemFileItemDocument({ task_id: "task-002" }),
          problem_types: ["metadata"],
        },
      ],
      total: 1,
      problem_file_total: 1,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 0,
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/problem-items")) {
        return jsonResponse(problemPage);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(
          url.includes("view=attention") ? attentionPage : fullPage,
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations");

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
    // The active view reads as the current page and the shared inbox is the
    // one list surface, with its five problem-type filters.
    expect(
      await screen.findByRole("button", { name: "需要处理" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      await screen.findByRole("heading", { name: "问题文件" }),
    ).toBeVisible();
    expect(screen.queryByRole("table")).toBeNull();
    // The four statistics already state the attention population; the list
    // has no second yellow banner repeating the same task count.
    expect(
      screen.queryByText(/个任务需要处理，可按恢复类型集中查看/),
    ).toBeNull();
    expect(
      requested.some(
        (url) =>
          url.startsWith("/api/operations/problem-items") &&
          !url.includes("problem="),
      ),
    ).toBe(true);
    expect(screen.getByText("problem-a.mkv")).toBeVisible();
    expect(screen.getByText("Movies/Needs review")).toBeVisible();

    // Switching back to 全部任务 restores the unfiltered population table.
    await user.click(screen.getByRole("button", { name: "全部任务" }));
    await waitFor(() =>
      expect(router.history.location.search).not.toContain("view=attention"),
    );
    expect(
      (await screen.findAllByText("Movies/Needs review")).length,
    ).toBeGreaterThan(0);
    expect(await screen.findByRole("table")).toBeVisible();
  });

  it("filters and opens the exact Task/file directly from the Attention inbox", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const attentionRun = runDocument({
      run_id: "task-mixed",
      task_id: "task-mixed",
      source_scope: "Movies/Mixed problems",
      status: "waiting",
      attention: true,
      problem_types: ["metadata", "conflict"],
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 1,
      },
    });
    const attentionPage = pageDocument({
      items: [attentionRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
        problem_tasks: {
          recognition: 0,
          metadata: 1,
          classification: 0,
          conflict: 1,
        },
        problem_files: {
          recognition: 0,
          metadata: 1,
          classification: 0,
          conflict: 1,
        },
      }),
    });
    const metadataItem = problemFileItemDocument({
      item_id: "item-meta",
      task_id: "task-mixed",
      source_path: "Movies/metadata.mkv",
      status: "waiting_metadata_correction",
      stage: "waiting_metadata_correction",
    });
    const conflictItem = problemFileItemDocument({
      item_id: "item-conflict",
      task_id: "task-mixed",
      source_path: "Movies/conflict.mkv",
      status: "waiting_confirm",
      stage: "waiting_confirm",
      checkpoint: {
        status: "waiting_confirm",
        stage: "waiting_confirm",
        raw_stage: "waiting_confirm",
        blocker_kind: "conflict",
        blocker_id: "conflict-1",
        effect_certainty: "none",
        retry_safety: "safe",
        permitted_action_ids: ["resolve_conflict"],
        refusal_reason: null,
        checkpoint_version: "b".repeat(64),
        recovery_request: null,
      },
    });
    const allPage = problemFilesPageDocument({
      items: [
        {
          run: attentionRun,
          item: metadataItem,
          problem_types: ["metadata"],
        },
        {
          run: attentionRun,
          item: conflictItem,
          problem_types: ["conflict"],
        },
      ],
      total: 2,
      problem_file_total: 2,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 1,
      },
    });
    const metadataPage = problemFilesPageDocument({
      problem: "metadata",
      items: [
        {
          run: attentionRun,
          item: metadataItem,
          problem_types: ["metadata"],
        },
      ],
      total: 1,
      problem_file_total: 2,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 1,
      },
    });
    const conflictPage = problemFilesPageDocument({
      problem: "conflict",
      items: [
        {
          run: attentionRun,
          item: conflictItem,
          problem_types: ["conflict"],
        },
      ],
      total: 1,
      problem_file_total: 2,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 1,
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/problem-items")) {
        const params = new URL(url, "http://mediaflow.test").searchParams;
        if (params.get("problem") === "metadata")
          return jsonResponse(metadataPage);
        if (params.get("problem") === "conflict")
          return jsonResponse(conflictPage);
        return jsonResponse(allPage);
      }
      if (url === "/api/operations/runs/task-mixed") {
        return jsonResponse(attentionRun);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(attentionPage);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations?view=attention");

    expect(
      await screen.findByRole("heading", { name: "问题文件" }),
    ).toBeVisible();
    expect(await screen.findByText("metadata.mkv")).toBeVisible();
    expect(screen.getByText("conflict.mkv")).toBeVisible();
    const filters = screen.getByRole("group", { name: "问题类型" });
    expect(
      within(filters).getByRole("button", { name: /^全部 2/ }),
    ).toBeVisible();
    expect(
      within(filters).getByRole("button", { name: /^元数据 1/ }),
    ).toBeVisible();
    expect(
      within(filters).getByRole("button", { name: /^冲突 1/ }),
    ).toBeVisible();

    await user.click(within(filters).getByRole("button", { name: /^元数据/ }));
    await waitFor(() =>
      expect(router.history.location.search).toContain("problemType=metadata"),
    );
    await waitFor(() => expect(screen.queryByText("conflict.mkv")).toBeNull());
    expect(screen.getByText("metadata.mkv")).toBeVisible();
    expect(
      requested.some(
        (url) =>
          url.startsWith("/api/operations/problem-items") &&
          url.includes("problem=metadata"),
      ),
    ).toBe(true);
    // The type counts stay complete-scope facts while the page narrows.
    expect(
      within(screen.getByRole("group", { name: "问题类型" })).getByRole(
        "button",
        { name: /^冲突 1/ },
      ),
    ).toBeVisible();

    await user.click(
      within(screen.getByRole("group", { name: "问题类型" })).getByRole(
        "button",
        { name: /^冲突/ },
      ),
    );
    await waitFor(() =>
      expect(router.history.location.search).toContain("problemType=conflict"),
    );
    expect(await screen.findByText("conflict.mkv")).toBeVisible();
    expect(screen.queryByText("metadata.mkv")).toBeNull();

    // The whole file row is the control: it opens this exact Task detail with
    // this exact file expanded, with no per-run intermediate list.
    await user.click(screen.getByText("conflict.mkv"));
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=task-mixed"),
    );
    expect(router.history.location.search).toContain("item=item-conflict");
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    // Closing restores the exact Attention filter, not the default list.
    expect(router.history.location.search).toContain("view=attention");
    expect(router.history.location.search).toContain("problemType=conflict");
  });

  it("shows a bounded problem-file read failure and rereads the same filter", async () => {
    const user = userEvent.setup();
    let fail = true;
    const attentionRun = runDocument({
      run_id: "task-read",
      task_id: "task-read",
      source_scope: "Movies/Read failure",
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
    const attentionPage = pageDocument({
      items: [attentionRun],
      status_counts: { failed: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 0,
        attention: 1,
        ended: 1,
      }),
    });
    const problemPage = problemFilesPageDocument({
      problem: "metadata",
      items: [
        {
          run: attentionRun,
          item: problemFileItemDocument({
            item_id: "item-read",
            task_id: "task-read",
            source_path: "Movies/read.mkv",
          }),
          problem_types: ["metadata"],
        },
      ],
      total: 1,
      problem_file_total: 1,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 0,
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/operations/problem-items")) {
        if (fail)
          return jsonResponse({ error: { code: "internal_error" } }, 500);
        return jsonResponse(problemPage);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(attentionPage);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?view=attention");

    const failure = await screen.findByRole("heading", {
      name: "问题文件暂时不可用",
    });
    expect(failure).toBeVisible();
    expect(screen.queryByText("当前没有问题文件")).toBeNull();
    fail = false;
    await user.click(
      within(failure.closest("section") ?? document.body).getByRole("button", {
        name: "刷新",
      }),
    );
    expect(await screen.findByText("read.mkv")).toBeVisible();
  });

  it("pages the Attention list forward and backward on the server's own cursors", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const pagedRun = runDocument({
      run_id: "task-paged",
      task_id: "task-paged",
      source_scope: "Movies/Paged metadata",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
      problem_file_counts: {
        recognition: 0,
        metadata: 21,
        classification: 0,
        conflict: 0,
      },
    });
    const inventory = pageDocument({
      items: [pagedRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    const pageOf = (
      itemId: string,
      fileName: string,
      overrides: Record<string, unknown>,
    ) =>
      problemFilesPageDocument({
        problem: "metadata",
        items: [
          {
            run: pagedRun,
            item: problemFileItemDocument({
              item_id: itemId,
              task_id: "task-paged",
              source_path: `Movies/${fileName}`,
            }),
            problem_types: ["metadata"],
          },
        ],
        total: 21,
        problem_file_total: 21,
        task_total: 1,
        problem_file_counts: {
          recognition: 0,
          metadata: 21,
          classification: 0,
          conflict: 0,
        },
        ...overrides,
      });
    const first = pageOf("item-01", "Metadata01.mkv", {
      next_cursor: "cursor-two",
    });
    const second = pageOf("item-21", "Metadata21.mkv", {
      previous_cursor: "cursor-first",
      next_cursor: "cursor-three",
    });
    const third = pageOf("item-41", "Metadata41.mkv", {
      previous_cursor: "cursor-two",
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/problem-items")) {
        const params = new URL(url, "http://mediaflow.test").searchParams;
        const cursor = params.get("cursor");
        if (cursor === "cursor-two") return jsonResponse(second);
        if (cursor === "cursor-first") return jsonResponse(first);
        if (cursor === "cursor-three") return jsonResponse(third);
        return jsonResponse(first);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(inventory);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/operations?view=attention&problemType=metadata",
    );

    const inbox = await screen.findByRole("region", { name: "问题文件" });
    expect(await within(inbox).findByText("Metadata01.mkv")).toBeVisible();
    // The list head states the current filter's file count; the aggregate
    // task count stays in the task statistics cards where it is scoped.
    expect(within(inbox).getByText("21 个文件", { exact: true })).toBeVisible();
    expect(within(inbox).queryByText(/个任务/)).toBeNull();
    const next = () => within(inbox).getByRole("button", { name: "下一页" });
    const previous = () =>
      within(inbox).getByRole("button", { name: "上一页" });
    expect(previous()).toBeDisabled();

    await user.click(next());
    expect(await within(inbox).findByText("Metadata21.mkv")).toBeVisible();
    expect(router.history.location.search).toContain(
      "problemCursor=cursor-two",
    );
    expect(router.history.location.search).toContain("problemDir=forward");
    expect(previous()).toBeEnabled();
    expect(next()).toBeEnabled();

    await user.click(previous());
    expect(await within(inbox).findByText("Metadata01.mkv")).toBeVisible();
    await waitFor(() =>
      expect(router.history.location.search).toContain("problemDir=backward"),
    );
    // The server still offers this collection's next page while the URL
    // direction is backward; the button follows its own cursor.
    expect(previous()).toBeDisabled();
    expect(next()).toBeEnabled();

    await user.click(next());
    expect(await within(inbox).findByText("Metadata21.mkv")).toBeVisible();
    await user.click(next());
    expect(await within(inbox).findByText("Metadata41.mkv")).toBeVisible();
    expect(router.history.location.search).toContain(
      "problemCursor=cursor-three",
    );
    expect(next()).toBeDisabled();
    expect(previous()).toBeEnabled();
  });

  it("keeps problem counts visibly unknown until the read succeeds", async () => {
    const user = userEvent.setup();
    const pendingReads: ((response: Response) => void)[] = [];
    let reads = 0;
    const countRun = runDocument({
      run_id: "task-counts",
      task_id: "task-counts",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 0,
      },
    });
    const inventory = pageDocument({
      items: [countRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/operations/problem-items")) {
        reads += 1;
        if (reads === 1) {
          return await new Promise<Response>((resolve) => {
            pendingReads.push(resolve);
          });
        }
        return jsonResponse(
          problemFilesPageDocument({
            problem: "metadata",
            total: 0,
            problem_file_total: 0,
            task_total: 0,
            problem_file_counts: {
              recognition: 0,
              metadata: 0,
              classification: 0,
              conflict: 0,
            },
          }),
        );
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(inventory);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?view=attention");

    const inbox = await screen.findByRole("region", { name: "问题文件" });
    expect(within(inbox).getByText("读取中")).toBeVisible();
    const filters = within(inbox).getByRole("group", { name: "问题类型" });
    expect(
      within(filters).getByRole("button", { name: "全部 —" }),
    ).toBeVisible();
    const resolveFirst = pendingReads[0];
    if (resolveFirst === undefined) throw new Error("the read did not start");
    resolveFirst(jsonResponse({ error: { code: "internal_error" } }, 500));
    await waitFor(() =>
      expect(within(inbox).getByText("计数未知")).toBeVisible(),
    );
    expect(
      within(filters).getByRole("button", { name: "元数据 —" }),
    ).toBeVisible();

    await user.click(within(inbox).getByRole("button", { name: "刷新" }));
    await waitFor(() =>
      expect(
        within(inbox).getByText("0 个文件", { exact: true }),
      ).toBeVisible(),
    );
    // A real zero after a successful read is a zero, not an unknown count.
    expect(
      within(filters).getByRole("button", { name: "全部 0" }),
    ).toBeVisible();
    expect(
      within(filters).getByRole("button", { name: "识别 0" }),
    ).toBeVisible();
    expect(within(inbox).getByText("当前没有问题文件")).toBeVisible();
  });

  it("keeps the problem list and counts in step for an empty date range", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const dateRun = runDocument({
      run_id: "task-dated",
      task_id: "task-dated",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
    });
    const inventory = pageDocument({
      items: [dateRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    const emptyRange = problemFilesPageDocument({
      problem: "metadata",
      total: 0,
      problem_file_total: 0,
      task_total: 0,
      problem_file_counts: {
        recognition: 0,
        metadata: 0,
        classification: 0,
        conflict: 0,
      },
      from: "2026-08-01T00:00:00+00:00",
      to: "2026-08-01T23:59:59.999999+00:00",
    });
    const fullRange = problemFilesPageDocument({
      problem: "metadata",
      items: [
        {
          run: dateRun,
          item: problemFileItemDocument({
            item_id: "item-dated",
            task_id: "task-dated",
            source_path: "Movies/dated.mkv",
          }),
          problem_types: ["metadata"],
        },
      ],
      total: 1,
      problem_file_total: 1,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 0,
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/problem-items")) {
        const params = new URL(url, "http://mediaflow.test").searchParams;
        return jsonResponse(
          params.get("from") === null ? fullRange : emptyRange,
        );
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(inventory);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/operations?view=attention&problemType=metadata&from=2026-08-01&to=2026-08-01",
    );

    const inbox = await screen.findByRole("region", { name: "问题文件" });
    expect(
      await within(inbox).findByText("当前日期范围没有问题文件"),
    ).toBeVisible();
    // The head and all five filters describe the same empty submitted range.
    expect(within(inbox).getByText("0 个文件", { exact: true })).toBeVisible();
    const filters = within(inbox).getByRole("group", { name: "问题类型" });
    for (const label of ["全部", "识别", "元数据", "分类", "冲突"]) {
      expect(
        within(filters).getByRole("button", { name: `${label} 0` }),
      ).toBeVisible();
    }
    expect(within(inbox).queryByRole("button", { name: "下一页" })).toBeNull();
    expect(within(inbox).queryByRole("button", { name: "上一页" })).toBeNull();

    await user.click(within(inbox).getByRole("button", { name: "清除时间" }));
    expect(await within(inbox).findByText("dated.mkv")).toBeVisible();
    expect(within(inbox).getByText("1 个文件", { exact: true })).toBeVisible();
    expect(
      within(filters).getByRole("button", { name: "元数据 1" }),
    ).toBeVisible();
    expect(router.history.location.search).not.toContain("from=");
    expect(
      requested.some(
        (url) =>
          url.startsWith("/api/operations/problem-items") &&
          !url.includes("from="),
      ),
    ).toBe(true);
  });

  it("keeps the selected problem type when a creation range starts a new page", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const datedRun = runDocument({
      run_id: "task-dated-page",
      task_id: "task-dated-page",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
    });
    const inventory = pageDocument({
      items: [datedRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    const entry = (itemId: string, fileName: string) => ({
      run: datedRun,
      item: problemFileItemDocument({
        item_id: itemId,
        task_id: "task-dated-page",
        source_path: `Movies/${fileName}`,
      }),
      problem_types: ["metadata"],
    });
    const firstPage = problemFilesPageDocument({
      problem: "metadata",
      items: [entry("item-one", "one.mkv")],
      total: 2,
      problem_file_total: 2,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 2,
        classification: 0,
        conflict: 0,
      },
      next_cursor: "metadata-page-two",
    });
    const secondPage = problemFilesPageDocument({
      problem: "metadata",
      items: [entry("item-two", "two.mkv")],
      total: 2,
      problem_file_total: 2,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 2,
        classification: 0,
        conflict: 0,
      },
      previous_cursor: "metadata-page-one",
    });
    const emptyRange = problemFilesPageDocument({
      problem: "metadata",
      from: "2999-01-01T00:00:00+00:00",
      to: "2999-01-01T23:59:59.999999+00:00",
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/problem-items")) {
        const params = new URL(url, "http://mediaflow.test").searchParams;
        if (params.get("from") !== null) return jsonResponse(emptyRange);
        return jsonResponse(
          params.get("cursor") === "metadata-page-two" ? secondPage : firstPage,
        );
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(inventory);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/operations?view=attention&problemType=metadata&problemCursor=metadata-page-two&problemDir=forward",
    );

    const inbox = await screen.findByRole("region", { name: "问题文件" });
    expect(await within(inbox).findByText("two.mkv")).toBeVisible();
    // The second page is narrowed by a new creation day: only the date
    // changes, the submitted problem type stays selected and the old page
    // cursor is never replayed against the new population.
    fireEvent.change(screen.getByLabelText("开始日期"), {
      target: { value: "2999-01-01" },
    });
    await waitFor(() =>
      expect(router.history.location.search).toContain("from=2999-01-01"),
    );
    expect(
      await within(inbox).findByText("当前日期范围没有问题文件"),
    ).toBeVisible();
    const narrowed = new URL(
      router.history.location.search,
      "http://mediaflow.test",
    ).searchParams;
    expect(narrowed.get("view")).toBe("attention");
    expect(narrowed.get("problemType")).toBe("metadata");
    expect(narrowed.get("problemCursor")).toBeNull();
    expect(narrowed.get("problemDir")).toBeNull();
    expect(
      requested.some((url) => {
        if (!url.startsWith("/api/operations/problem-items")) return false;
        const params = new URL(url, "http://mediaflow.test").searchParams;
        return (
          params.get("problem") === "metadata" &&
          params.get("from") !== null &&
          params.get("cursor") === null
        );
      }),
    ).toBe(true);

    // Clearing the date keeps the same type, restarts at the first page and
    // restores that filter's real files and counts.
    await user.click(
      within(screen.getByRole("region", { name: "运行筛选" })).getByRole(
        "button",
        { name: "清除" },
      ),
    );
    expect(await within(inbox).findByText("one.mkv")).toBeVisible();
    expect(within(inbox).getByText("2 个文件", { exact: true })).toBeVisible();
    const cleared = new URL(
      router.history.location.search,
      "http://mediaflow.test",
    ).searchParams;
    expect(cleared.get("problemType")).toBe("metadata");
    expect(cleared.get("from")).toBeNull();
    expect(cleared.get("problemCursor")).toBeNull();
    expect(within(inbox).getByRole("button", { name: "下一页" })).toBeEnabled();
  });

  it("returns to the nearest remaining file row when the opener settled", async () => {
    const user = userEvent.setup();
    const problemRun = runDocument({
      run_id: "task-neighbor",
      task_id: "task-neighbor",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
      problem_file_counts: {
        recognition: 0,
        metadata: 3,
        classification: 0,
        conflict: 0,
      },
    });
    const entry = (itemId: string, fileName: string) => ({
      run: problemRun,
      item: problemFileItemDocument({
        item_id: itemId,
        task_id: "task-neighbor",
        source_path: `Movies/${fileName}`,
      }),
      problem_types: ["metadata"],
    });
    const page = problemFilesPageDocument({
      problem: "metadata",
      items: [
        entry("item-one", "one.mkv"),
        entry("item-two", "two.mkv"),
        entry("item-three", "three.mkv"),
      ],
      total: 3,
      problem_file_total: 3,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 3,
        classification: 0,
        conflict: 0,
      },
    });
    let problemReads = 0;
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/operations/problem-items")) {
        problemReads += 1;
        return jsonResponse(
          problemReads === 1
            ? page
            : {
                ...page,
                items: [
                  entry("item-one", "one.mkv"),
                  entry("item-three", "three.mkv"),
                ],
                total: 2,
                problem_file_total: 2,
                problem_file_counts: {
                  recognition: 0,
                  metadata: 2,
                  classification: 0,
                  conflict: 0,
                },
              },
        );
      }
      if (url === "/api/operations/runs/task-neighbor") {
        return jsonResponse(problemRun);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(
          pageDocument({
            items: [problemRun],
            total: 1,
            view: "attention",
            attention: true,
            status_counts: { waiting: 1 },
            attention_count: 1,
            summary: summaryDocument({
              total: 1,
              running: 1,
              attention: 1,
              ended: 0,
            }),
          }),
        );
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router, queryClient } = renderApp(
      "/operations?view=attention&problemType=metadata",
    );

    const inbox = await screen.findByRole("region", { name: "问题文件" });
    const opener = within(
      (await within(inbox).findByText("two.mkv")).closest("li") ?? inbox,
    ).getByRole("button");
    await user.click(opener);
    await screen.findByRole("dialog", { name: "运行详情" });
    // A live problem read settles the opened file while its detail is open;
    // the exact row leaves the background list.
    await queryClient.refetchQueries({
      queryKey: [runProblemFilesQueryKey, "metadata", "", "", null],
    });
    const currentInbox = screen.getByRole("region", { name: "问题文件" });
    await waitFor(() =>
      expect(within(currentInbox).queryByText("two.mkv")).toBeNull(),
    );
    expect(within(currentInbox).getByText("2 个文件")).toBeVisible();
    const neighbor = within(
      within(currentInbox).getByText("three.mkv").closest("li") ?? currentInbox,
    ).getByRole("button");
    await user.click(
      within(screen.getByRole("dialog", { name: "运行详情" })).getByRole(
        "button",
        { name: "关闭详情" },
      ),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    expect(neighbor).toHaveFocus();
    expect(router.history.location.search).toContain("problemType=metadata");
  });

  it("resets a refused problem-file cursor to the same filter's first page", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const staleRun = runDocument({
      run_id: "task-stale",
      task_id: "task-stale",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
    });
    const inventory = pageDocument({
      items: [staleRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    const readable = problemFilesPageDocument({
      problem: "metadata",
      items: [
        {
          run: staleRun,
          item: problemFileItemDocument({
            item_id: "item-stale",
            task_id: "task-stale",
            source_path: "Movies/readable.mkv",
          }),
          problem_types: ["metadata"],
        },
      ],
      total: 1,
      problem_file_total: 1,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 0,
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/problem-items")) {
        const params = new URL(url, "http://mediaflow.test").searchParams;
        if (params.get("cursor") === "stale-cursor") {
          return jsonResponse({ error: { code: "bad_request" } }, 400);
        }
        return jsonResponse(readable);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(inventory);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/operations?view=attention&problemType=metadata&from=2026-08-01&problemCursor=stale-cursor&problemDir=forward",
    );

    const failure = await screen.findByRole("heading", {
      name: "问题文件暂时不可用",
    });
    await user.click(
      within(failure.closest("section") ?? document.body).getByRole("button", {
        name: "回到第一页",
      }),
    );
    expect(await screen.findByText("readable.mkv")).toBeVisible();
    const search = router.history.location.search;
    // The reset changes only the position: the type and creation date the
    // operator submitted stay in force.
    expect(search).toContain("view=attention");
    expect(search).toContain("problemType=metadata");
    expect(search).toContain("from=2026-08-01");
    expect(search).not.toContain("problemCursor");
    expect(
      requested.some(
        (url) =>
          url.startsWith("/api/operations/problem-items") &&
          !url.includes("cursor="),
      ),
    ).toBe(true);
  });

  it("offers a readable first page after the submitted page has settled", async () => {
    const user = userEvent.setup();
    const settledRun = runDocument({
      run_id: "task-settled",
      task_id: "task-settled",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
    });
    const inventory = pageDocument({
      items: [settledRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    const settled = problemFilesPageDocument({
      problem: "metadata",
      total: 0,
      problem_file_total: 0,
      task_total: 0,
      problem_file_counts: {
        recognition: 0,
        metadata: 0,
        classification: 0,
        conflict: 0,
      },
    });
    const readable = problemFilesPageDocument({
      problem: "metadata",
      items: [
        {
          run: settledRun,
          item: problemFileItemDocument({
            item_id: "item-readable",
            task_id: "task-settled",
            source_path: "Movies/readable.mkv",
          }),
          problem_types: ["metadata"],
        },
      ],
      total: 1,
      problem_file_total: 1,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 0,
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/operations/problem-items")) {
        const params = new URL(url, "http://mediaflow.test").searchParams;
        return jsonResponse(
          params.get("cursor") === "settled-cursor" ? settled : readable,
        );
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(inventory);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/operations?view=attention&problemType=metadata&problemCursor=settled-cursor&problemDir=forward",
    );

    const inbox = await screen.findByRole("region", { name: "问题文件" });
    expect(await within(inbox).findByText("当前没有问题文件")).toBeVisible();
    // This page holds no row and the server minted no neighbour cursor, so
    // the only usable position control is the readable first page.
    expect(within(inbox).queryByRole("button", { name: "上一页" })).toBeNull();
    expect(within(inbox).queryByRole("button", { name: "下一页" })).toBeNull();
    await user.click(within(inbox).getByRole("button", { name: "回到第一页" }));
    expect(await within(inbox).findByText("readable.mkv")).toBeVisible();
    expect(router.history.location.search).not.toContain("problemCursor");
    expect(router.history.location.search).toContain("problemType=metadata");
  });

  it("restores a committed per-run problem link's exact Task, type and page", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const legacyRun = runDocument({
      run_id: "task-legacy",
      task_id: "task-legacy",
      source_scope: "Movies/Legacy metadata",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
      problem_file_counts: {
        recognition: 0,
        metadata: 2,
        classification: 0,
        conflict: 0,
      },
    });
    const inventory = pageDocument({
      items: [legacyRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    const legacyItem = (itemId: string, fileName: string) => ({
      item_id: itemId,
      task_id: "task-legacy",
      storage_id: "source",
      resource_library_id: "movies",
      source_path: `Movies/${fileName}`,
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
      },
    });
    const legacyPage = {
      run_id: "task-legacy",
      task_id: "task-legacy",
      problem: "metadata",
      limit: 20,
      items: [legacyItem("item-a", "legacy-a.mkv")],
      total: 2,
      matching_total: 2,
      dispositions: {
        pending: 2,
        active: 0,
        waiting: 0,
        success: 0,
        skipped: 0,
        failed_partial: 0,
        ignored: 0,
        cancelled: 0,
      },
      uncertain_success: 0,
      truncated: true,
      previous_cursor: null,
      next_cursor: "legacy-page-two",
      sideEffects: "none",
    };
    const legacyPageTwo = {
      ...legacyPage,
      items: [legacyItem("item-b", "legacy-b.mkv")],
      previous_cursor: "legacy-page-one",
      next_cursor: null,
    };
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/runs/task-legacy/problem-items")) {
        const params = new URL(url, "http://mediaflow.test").searchParams;
        return jsonResponse(
          params.get("cursor") === "legacy-page-two"
            ? legacyPageTwo
            : legacyPage,
        );
      }
      if (url === "/api/operations/runs/task-legacy") {
        return jsonResponse(legacyRun);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(inventory);
      }
      if (url.startsWith("/api/operations/problem-items")) {
        return jsonResponse(problemFilesPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/operations?view=metadata&problemRun=task-legacy&problemCursor=legacy-page-two&problemDir=forward",
    );

    const panel = await screen.findByRole("region", { name: "问题文件处理" });
    expect(
      (await within(panel).findAllByText(/Movies\/legacy-b\.mkv/)).length,
    ).toBeGreaterThan(0);
    expect(within(panel).getByText(/元数据问题 — 文件清单/)).toBeVisible();
    // The committed cursor belongs to this Task/type collection; the
    // aggregate collection is never asked to read it.
    expect(
      requested.some(
        (url) =>
          url.startsWith("/api/operations/runs/task-legacy/problem-items") &&
          url.includes("cursor=legacy-page-two") &&
          url.includes("problem=metadata"),
      ),
    ).toBe(true);
    expect(
      requested.some((url) => url.startsWith("/api/operations/problem-items")),
    ).toBe(false);

    const evidenceButton = within(panel).getByRole("button", {
      name: "查看该文件证据与恢复记录",
    });
    await user.click(evidenceButton);
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    // The detail card overlays the panel; the panel and its scroll container
    // stay mounted instead of restarting at their heading.
    expect(screen.getByRole("region", { name: "问题文件处理" })).toBe(panel);
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=task-legacy"),
    );
    expect(router.history.location.search).toContain("item=item-b");
    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    // Closing returns to the exact Task/type page and the invoking row.
    const restored = await screen.findByRole("region", {
      name: "问题文件处理",
    });
    expect(restored).toBe(panel);
    expect(evidenceButton).toHaveFocus();
    expect(
      (await within(restored).findAllByText(/Movies\/legacy-b\.mkv/)).length,
    ).toBeGreaterThan(0);
    expect(router.history.location.search).toContain("problemRun=task-legacy");
    expect(router.history.location.search).toContain(
      "problemCursor=legacy-page-two",
    );

    // Browser Back closes the same detail with the same mounted page and
    // returns focus to the row that opened it.
    await user.click(evidenceButton);
    await screen.findByRole("dialog", { name: "运行详情" });
    router.history.back();
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    expect(screen.getByRole("region", { name: "问题文件处理" })).toBe(panel);
    expect(evidenceButton).toHaveFocus();
    expect(router.history.location.search).toContain("problemRun=task-legacy");
  });

  it("resets a refused per-run problem cursor to the same Task's first page", async () => {
    const user = userEvent.setup();
    const legacyRun = runDocument({
      run_id: "task-legacy-stale",
      task_id: "task-legacy-stale",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
    });
    const inventory = pageDocument({
      items: [legacyRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    const readable = {
      run_id: "task-legacy-stale",
      task_id: "task-legacy-stale",
      problem: "metadata",
      limit: 20,
      items: [
        {
          item_id: "item-readable",
          task_id: "task-legacy-stale",
          storage_id: "source",
          resource_library_id: "movies",
          source_path: "Movies/readable.mkv",
          status: "failed",
          stage: "metadata",
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
      total: 1,
      matching_total: 1,
      dispositions: {
        pending: 1,
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
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/operations/runs/task-legacy-stale/problem-items")
      ) {
        const params = new URL(url, "http://mediaflow.test").searchParams;
        if (params.get("cursor") === "stale-cursor") {
          return jsonResponse({ error: { code: "bad_request" } }, 400);
        }
        return jsonResponse(readable);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(inventory);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/operations?view=metadata&problemRun=task-legacy-stale&from=2026-08-01&problemCursor=stale-cursor&problemDir=forward",
    );

    const failure = await screen.findByRole("heading", {
      name: "Request rejected",
    });
    await user.click(
      within(failure.closest("section") ?? document.body).getByRole("button", {
        name: "回到第一页",
      }),
    );
    expect(
      (await screen.findAllByText(/Movies\/readable\.mkv/)).length,
    ).toBeGreaterThan(0);
    const search = router.history.location.search;
    expect(search).toContain("problemRun=task-legacy-stale");
    expect(search).toContain("view=metadata");
    expect(search).toContain("from=2026-08-01");
    expect(search).not.toContain("problemCursor");
  });

  it("keeps a legacy recovery deep link and its server page through the exact file", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    const attentionRun = runDocument({
      run_id: "task-legacy",
      task_id: "task-legacy",
      source_scope: "Movies/Legacy metadata",
      status: "waiting",
      attention: true,
      problem_types: ["metadata"],
      problem_file_counts: {
        recognition: 0,
        metadata: 2,
        classification: 0,
        conflict: 0,
      },
    });
    const attentionPage = pageDocument({
      items: [attentionRun],
      status_counts: { waiting: 1 },
      attention_count: 1,
      total: 1,
      attention: true,
      view: "attention",
      summary: summaryDocument({
        total: 1,
        running: 1,
        attention: 1,
        ended: 0,
      }),
    });
    const pageOneItem = problemFileItemDocument({
      item_id: "item-a",
      task_id: "task-legacy",
      source_path: "Movies/a.mkv",
    });
    const pageTwoItem = problemFileItemDocument({
      item_id: "item-b",
      task_id: "task-legacy",
      source_path: "Movies/b.mkv",
    });
    const pageOne = problemFilesPageDocument({
      problem: "metadata",
      items: [
        { run: attentionRun, item: pageOneItem, problem_types: ["metadata"] },
      ],
      total: 2,
      problem_file_total: 2,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 2,
        classification: 0,
        conflict: 0,
      },
      truncated: true,
      next_cursor: "page-two",
    });
    const pageTwo = problemFilesPageDocument({
      problem: "metadata",
      items: [
        { run: attentionRun, item: pageTwoItem, problem_types: ["metadata"] },
      ],
      total: 2,
      problem_file_total: 2,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 2,
        classification: 0,
        conflict: 0,
      },
      previous_cursor: "page-one",
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/problem-items")) {
        return jsonResponse(
          url.includes("cursor=page-two") ? pageTwo : pageOne,
        );
      }
      if (url === "/api/operations/runs/task-legacy") {
        return jsonResponse(attentionRun);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(attentionPage);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations?view=metadata");

    expect(await screen.findByText("a.mkv")).toBeVisible();
    expect(router.history.location.search).toContain("view=metadata");
    expect(
      requested.some(
        (url) =>
          url.startsWith("/api/operations/problem-items") &&
          url.includes("problem=metadata"),
      ),
    ).toBe(true);
    expect(
      await screen.findByRole("button", { name: "需要处理" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("group", { name: "问题类型" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "下一页" }));
    await waitFor(() =>
      expect(router.history.location.search).toContain(
        "problemCursor=page-two",
      ),
    );
    expect(await screen.findByText("b.mkv")).toBeVisible();
    await user.click(screen.getByText("b.mkv"));
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=task-legacy"),
    );
    expect(router.history.location.search).toContain("item=item-b");
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    // The legacy type link and the exact server page survive the round trip.
    expect(router.history.location.search).toContain("view=metadata");
    expect(router.history.location.search).toContain("problemCursor=page-two");
    expect(
      parseOperationsReturnContext(router.history.location.search),
    ).toMatchObject({ view: "metadata" });
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
    renderApp("/operations");

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
    // The center navigation offers exactly the four first-level views; the
    // four recovery types live inside Attention and Failure Recovery is gone.
    for (const label of ["全部任务", "进行中", "需要处理", "已结束"]) {
      expect(await screen.findByRole("button", { name: label })).toBeVisible();
    }
    for (const label of ["识别恢复", "元数据恢复", "分类恢复", "冲突处理"]) {
      expect(screen.queryByRole("button", { name: label })).toBeNull();
    }
    expect(screen.queryByRole("button", { name: "失败恢复" })).toBeNull();
    expect(requested.some((url) => url.includes("/api/operations/runs"))).toBe(
      true,
    );
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
    renderApp("/operations");

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
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/operations/runs/task-mixed-ended") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-mixed-ended&view=ended");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const flow = await within(detail).findByRole("region", {
      name: "状态与流程",
    });
    await within(flow).findByText("流程已完成，文件效果待核对");
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
    ).toEqual(["成功6", "部分成功2", "失败1"]);
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
            path: "/api/tasks/task-001/cancel",
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
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findByRole("region", { name: "状态与流程" });
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

  it("Task59.2 reads the advertised task action before results and run facts after the items", async () => {
    const overview = runDocument({
      lifecycle: lifecycleDocument(),
      progress: {
        available: true,
        kind: "organize",
        unit: "主条目",
        unit_key: "task_items",
        basis: "整理计数:成功表示已验证的存储操作结果。",
        success_means: "已验证的存储操作成功",
        known_total: 4,
        indeterminate: false,
        processed: 1,
        dispositions: {
          pending: 3,
          active: 0,
          waiting: 0,
          success: 1,
          skipped: 0,
          failed_partial: 0,
          ignored: 0,
          cancelled: 0,
        },
        confirmed_success: 1,
        uncertain_success: 0,
        scan_errors: null,
        scan_discovery_complete: null,
        scan_progress: {},
        attachment_steps: 0,
        effect_counts: { verified_complete: 1, attempted_unverified: 0 },
        results_total: 1,
        results_complete: true,
        sideEffects: "none",
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument({ items: [overview] }));
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(overview);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const progress = await within(detail).findByRole("region", {
      name: "处理进度",
    });
    // The backend-advertised cancel control lives in the shared tab toolbar,
    // above the body and available from either tab.
    const toolbar = await within(detail).findByRole("navigation", {
      name: "运行详情与操作记录",
    });
    expect(
      within(toolbar).getByRole("button", { name: "取消运行" }),
    ).toHaveClass("mf-button-danger");
    expect(
      within(detail).queryByRole("region", { name: "当前操作" }),
    ).toBeNull();
    const results = within(detail).getByRole("region", { name: "文件结果" });
    const items = within(detail).getByRole("region", { name: "主条目" });
    expect(
      toolbar.compareDocumentPosition(progress) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      progress.compareDocumentPosition(results) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      results.compareDocumentPosition(items) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(items.parentElement?.lastElementChild).toBe(items);
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
    renderApp("/operations");

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
    expect(requested.some((url) => url.includes("/api/operations/runs"))).toBe(
      true,
    );
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
      if (url.startsWith("/api/operations/runs?")) {
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
      if (url === "/api/operations/runs/mixed-run") {
        return jsonResponse(mixed);
      }
      if (url === "/api/operations/runs/recovered-run") {
        return jsonResponse(recovered);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations?run=mixed-run");

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
      await within(recoveredDetail).findByText("流程已完成（恢复成功）"),
    ).toBeVisible();
    expect(
      within(recoveredDetail).getByText(
        "必要文件效果均已验证，原处理记录仍可查阅。",
      ),
    ).toBeVisible();
  });

  it("re-reads the selected overview from the header refresh control", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url.startsWith("/api/operations/runs?")) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(runDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations");

    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /预览/ }));
    await screen.findByRole("dialog", { name: "运行详情" });
    const overviewReads = () =>
      requested.filter((url) => url.startsWith("/api/operations/runs/")).length;
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
      if (url.startsWith("/api/operations/runs?")) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(runDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations");

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

  it("opens and returns from an Attention file without resetting the route scroll", async () => {
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
    const problemPage = problemFilesPageDocument({
      problem: "metadata",
      items: [
        {
          run: problemRun,
          item: problemFileItemDocument({
            item_id: "item-a",
            task_id: "task-problem",
            source_path: "Movies/a.mkv",
          }),
          problem_types: ["metadata"],
        },
      ],
      total: 1,
      problem_file_total: 1,
      task_total: 1,
      problem_file_counts: {
        recognition: 0,
        metadata: 1,
        classification: 0,
        conflict: 0,
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/operations/problem-items")) {
        return jsonResponse(problemPage);
      }
      if (url === "/api/operations/runs/task-problem") {
        return jsonResponse(problemRun);
      }
      if (url.startsWith("/api/operations/runs")) {
        return jsonResponse(
          pageDocument({
            items: [problemRun],
            total: 1,
            view: "attention",
            attention: true,
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
    const { router } = renderApp("/operations?view=metadata");

    expect(await screen.findByText("a.mkv")).toBeVisible();
    const scrollTo = vi
      .spyOn(window, "scrollTo")
      .mockImplementation(() => undefined);
    await user.click(screen.getByText("a.mkv"));
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await waitFor(() =>
      expect(router.history.location.search).toContain("run=task-problem"),
    );
    expect(scrollTo).not.toHaveBeenCalled();

    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    expect(router.history.location.search).toContain("view=metadata");
    expect(router.history.location.search).not.toContain("run=");
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
    const { router } = renderApp("/operations");

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
          path: "/api/tasks/task-001/cancel",
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
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return gate;
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations");

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
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return gate;
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations");

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
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
      ) {
        return jsonResponse(pageDocument());
      }
      if (url === "/api/operations/runs/task-001") {
        return jsonResponse(runDocument({ lifecycle: lifecycleDocument() }));
      }
      if (url === "/api/tasks/task-001/cancel") {
        // The request never reached a decision: the transport failed, so the
        // outcome is unknown and every control of this run must stay locked.
        throw new TypeError("network unreachable");
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/operations");

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

    // The outcome belongs to the shared toolbar: 操作记录 reads the same lock
    // and feedback instead of losing the in-flight cancel context.
    const toolbar = within(detail).getByRole("navigation", {
      name: "运行详情与操作记录",
    });
    await user.click(within(toolbar).getByRole("button", { name: "操作记录" }));
    expect(
      within(toolbar).getByRole("button", { name: "操作记录" }),
    ).toHaveAttribute("aria-current", "page");
    expect(within(controls).getByText(/取消结果尚未确认/)).toBeTruthy();
    expect(
      within(controls).getByRole("button", { name: "取消运行" }),
    ).toBeDisabled();

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
    expect(posted).toEqual(["/api/tasks/task-001/cancel"]);
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
        url.startsWith("/api/operations/runs?") ||
        url === "/api/operations/runs"
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
      if (url === "/api/operations/runs/task-001") {
        return slowFirst;
      }
      if (url === "/api/operations/runs/task-002") {
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
    renderApp("/operations");

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
    await user.click(
      await within(second).findByRole("button", { name: "操作记录" }),
    );
    await user.click(within(second).getByText("任务信息与技术诊断"));
    expect(within(second).getByText("Media/Shows")).toBeVisible();
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
/** The plan this same preparation links after the in-place re-analysis. */
const HOST_SECOND_PREVIEW_ID = "preview-2";

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

/** A real in-progress hosted preparation: its walk has not produced a plan. */
function hostInProgressDiscovery(
  phase: "waiting" | "analyzing",
): Record<string, unknown> {
  const value = hostDiscoveryDocument();
  value["status"] = phase === "waiting" ? "waiting_stability" : "analyzing";
  value["previewId"] = null;
  value["intentId"] = null;
  value["prepared"] = false;
  value["frozen"] = phase === "analyzing";
  value["primarySourceCount"] = 10;
  const progress = value["progress"] as Record<string, unknown>;
  progress["phase"] = phase === "waiting" ? "partial" : "analyzing";
  progress["primarySources"] = 10;
  progress["unstableEntries"] = phase === "waiting" ? 2 : 0;
  progress["message"] =
    phase === "waiting"
      ? "the whole scope was visited, but some sources are not yet proven stable"
      : "the reviewed source list is frozen; the analysis is building the plan summary";
  return value;
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
    `/api/operations/organize/previews/${HOST_PREVIEW_ID}/execute`;
  return value;
}

/**
 * The exact summary the real Worker publishes after the in-place correction
 * from MOVE to COPY: same item, different recognition type, operation, target
 * and source retention, so the dialog's own facts prove this item's result.
 */
function hostSecondPreviewDocument(
  kind: "copy" | "sibling",
): Record<string, unknown> {
  const value = hostPreviewDocument();
  value["previewId"] = HOST_SECOND_PREVIEW_ID;
  value["intentVersion"] = 3;
  const actions = value["actions"] as Record<string, Record<string, unknown>>;
  actions["execute"]!["path"] =
    `/api/operations/organize/previews/${HOST_SECOND_PREVIEW_ID}/execute`;
  if (kind === "sibling") return value;
  const items = value["items"] as Record<string, unknown>[];
  const first = items[0]!;
  const choice = first["choice"] as Record<string, unknown>;
  choice["recognitionTypeId"] = "B";
  choice["namingPolicyId"] = "B";
  choice["classificationPolicyId"] = "B";
  choice["organizePolicyId"] = "B";
  const plan = first["plan"] as Record<string, unknown>;
  plan["recognitionType"] = "B";
  plan["operation"] = "COPY";
  const policies = plan["policies"] as Record<string, unknown>;
  policies["recognitionTypePolicyId"] = "type-B";
  policies["namingPolicyId"] = "B";
  policies["classificationPolicyId"] = "B";
  policies["organizePolicyId"] = "B";
  const destination = plan["destination"] as Record<string, unknown>;
  destination["filename"] = "One (2001) copy.mkv";
  destination["relativePath"] = "Shows/One (2001)/One (2001) copy.mkv";
  destination["storageRelativePath"] =
    "Movies/Shows/One (2001)/One (2001) copy.mkv";
  const implications = plan["destructiveImplications"] as Record<
    string,
    unknown
  >;
  implications["statement"] =
    "this exact plan copies each source to its reviewed target; the source location keeps the original media file";
  const analysis = plan["analysis"] as Record<string, unknown>;
  const recognition = analysis["recognition"] as Record<string, unknown>;
  recognition["recognitionTypeId"] = "B";
  const naming = analysis["naming"] as Record<string, unknown>;
  naming["directory"] = "One (2001)";
  naming["filename"] = "One (2001) copy.mkv";
  naming["policyId"] = "B";
  naming["recognitionTypeId"] = "B";
  return value;
}

function hostIntentDocument(
  latestPreviewId: string = HOST_PREVIEW_ID,
): Record<string, unknown> {
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
    `/api/operations/organize/intents/${HOST_INTENT_ID}/items/{itemId}/choice`;
  value["latestPlan"] = {
    previewId: latestPreviewId,
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
  actions["detail"]!["path"] = "/api/operations/organize/executions/exec-1";
  actions["task"]!["path"] = `/api/operations/tasks/${taskId}`;
  const items = value["items"] as Record<string, unknown>[];
  items[0]!["itemId"] = "item-1";
  items[0]!["taskId"] = taskId;
  items[0]!["taskItemId"] = "task-item-1";
  return value;
}

interface OrganizeHostBackend {
  readonly calls: {
    admissionReads: number;
    discoveryReads: number;
    intentReads: number;
    overviewReads: number;
    posts: string[];
  };
  readonly state: {
    intentUnavailable: boolean;
    executeTaskId: string;
    /** The next selected-Task overview poll answers 503 without mutating. */
    overviewUnavailable: boolean;
    /** The next Execute request's response is lost after a 503. */
    executeResponseLost: boolean;
    /** Bounded admission reads answer 503 while this stays true. */
    admissionUnavailable: boolean;
    /** The next analyze POST is admitted by this fake, then its response is lost. */
    analyzeResponseLost: boolean;
    /** Whether this exact preparation already links its second plan. */
    secondPlanPublished: boolean;
    /**
     * What that second plan carries: this item's own COPY result, or only a
     * sibling's newer summary where this item's readable facts are equal.
     */
    secondPlanKind: "copy" | "sibling";
    /** The hosted preparation's current real stage before its plan is ready. */
    preparationPhase: "waiting" | "analyzing" | "ready";
  };
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
    calls: {
      admissionReads: 0,
      discoveryReads: 0,
      intentReads: 0,
      overviewReads: 0,
      posts: [],
    },
    state: {
      intentUnavailable: options.intentUnavailable ?? false,
      executeTaskId: "task-001",
      overviewUnavailable: false,
      executeResponseLost: false,
      admissionUnavailable: false,
      analyzeResponseLost: false,
      secondPlanPublished: false,
      secondPlanKind: "copy",
      preparationPhase: "ready",
    },
  };
  stubFetch(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (method !== "GET") backend.calls.posts.push(url);
    if (url === "/api/auth/principal" && method === "GET") {
      return jsonResponse({ principal_id: "task-center-operator" });
    }
    if (
      url.startsWith("/api/operations/runs?") ||
      url === "/api/operations/runs"
    ) {
      return jsonResponse(pageDocument());
    }
    if (url === "/api/operations/runs/task-001") {
      backend.calls.overviewReads += 1;
      if (backend.state.overviewUnavailable) {
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return jsonResponse(
        runDocument({
          progress: progressDocument(),
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
      url === `/api/operations/organize/discoveries/${HOST_DISCOVERY_ID}` &&
      method === "GET"
    ) {
      backend.calls.discoveryReads += 1;
      const phase = backend.state.preparationPhase;
      const inProgress =
        phase === "ready" ? {} : hostInProgressDiscovery(phase);
      return jsonResponse(
        hostDiscoveryDocument({
          ...options.discovery,
          ...inProgress,
          ...(backend.state.secondPlanPublished
            ? { previewId: HOST_SECOND_PREVIEW_ID, version: 6 }
            : {}),
        }),
      );
    }
    if (
      url ===
        `/api/operations/organize/discoveries/${HOST_DISCOVERY_ID}/analyze` &&
      method === "POST"
    ) {
      if (backend.state.analyzeResponseLost) {
        // The real analysis is admitted and its exact plan published; only
        // this browser's copy of the response is lost.
        backend.state.analyzeResponseLost = false;
        backend.state.secondPlanPublished = true;
        throw new TypeError("Failed to fetch");
      }
      return jsonResponse(hostDiscoveryDocument(options.discovery));
    }
    if (
      /\/operations\/organize\/intents\/[^/]+\/items\/[^/]+\/choice$/.test(
        url,
      ) &&
      method === "POST"
    ) {
      return jsonResponse(hostIntentDocument());
    }
    if (
      url === `/api/operations/organize/intents/${HOST_INTENT_ID}` &&
      method === "GET"
    ) {
      backend.calls.intentReads += 1;
      if (backend.state.intentUnavailable) {
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return jsonResponse(
        hostIntentDocument(
          backend.state.secondPlanPublished
            ? HOST_SECOND_PREVIEW_ID
            : HOST_PREVIEW_ID,
        ),
      );
    }
    if (
      url === `/api/operations/organize/previews/${HOST_PREVIEW_ID}` &&
      method === "GET"
    ) {
      return jsonResponse(hostPreviewDocument());
    }
    if (
      url === `/api/operations/organize/previews/${HOST_SECOND_PREVIEW_ID}` &&
      method === "GET"
    ) {
      return jsonResponse(
        hostSecondPreviewDocument(backend.state.secondPlanKind),
      );
    }
    if (url.startsWith("/api/operations/organize/executions")) {
      return jsonResponse({
        items: [],
        total: 0,
        limit: 100,
        truncated: false,
      });
    }
    if (
      url === `/api/operations/organize/previews/${HOST_PREVIEW_ID}/execute` &&
      method === "POST"
    ) {
      if (backend.state.executeResponseLost) {
        backend.state.executeResponseLost = false;
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return jsonResponse(
        hostExecutionDocument(backend.state.executeTaskId),
        202,
      );
    }
    if (
      url.startsWith(
        `/api/operations/organize/previews/${HOST_PREVIEW_ID}/admission`,
      ) &&
      method === "GET"
    ) {
      backend.calls.admissionReads += 1;
      if (backend.state.admissionUnavailable) {
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return jsonResponse({
        outcome: "known",
        reason: null,
        executionId: "exec-1",
        taskId: backend.state.executeTaskId,
        status: "queued",
        selectedItemIds: ["item-1"],
        completedItemCount: 0,
        failedItemCount: 0,
        sideEffects: "none",
        nextAction: "the admitted execution queues in this task",
      });
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
      "/operations?run=task-001&tab=records&dialog=organize",
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
    const { router } = renderApp("/operations?dialog=organize");

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
    renderApp("/operations?run=task-001&dialog=organize");

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
    const { router } = renderApp("/operations?run=task-001&dialog=execute");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    expect(
      await within(detail).findByRole("region", { name: "状态与流程" }),
    ).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull();
    expect(
      screen.queryByRole("dialog", { name: "无法继续这次整理" }),
    ).toBeNull();
    expect(router.state.location.search["dialog"]).toBeUndefined();
    // The status summary may read this Task's own linked preparation; the
    // dropped marker still starts no replay or mutation.
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
    renderApp("/operations?run=task-001&dialog=organize");

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
    renderApp("/operations?run=task-001&dialog=organize");

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
    renderApp("/operations?run=task-001&dialog=organize");

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    expect(await within(dialog).findByText(/从未生成过计划摘要/)).toBeVisible();
    expect(
      within(dialog).queryByRole("region", { name: "只读原计划摘要" }),
    ).toBeNull();
  });

  it("never carries A's preparation into another selected Task", async () => {
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations?run=task-001&dialog=organize");

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

  it("keeps a first-entry read failure as an unavailable card until the association is read", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    backend.state.overviewUnavailable = true;
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001&dialog=organize");

    const notice = await screen.findByRole("dialog", {
      name: "无法继续这次整理",
    });
    expect(within(notice).getByText("Operations unavailable")).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull();
    expect(screen.queryByText("任务详情暂时无法读取")).toBeNull();
    expect(backend.calls.discoveryReads).toBe(0);

    backend.state.overviewUnavailable = false;
    await user.click(
      within(notice).getByRole("button", { name: "重新读取任务" }),
    );
    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    expect(backend.calls.posts).toEqual([]);
    // This direct continuation address never opened from the continue entry:
    // closing keeps the existing detail-close focus fallback.
    await user.click(within(dialog).getByRole("button", { name: /^关闭$/ }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "整理所选文件" })).toBeNull(),
    );
    await waitFor(() =>
      expect(document.activeElement).toBe(
        document.getElementById("mf-run-detail-close"),
      ),
    );
  });

  it("keeps an opened continuation's unsaved correction through a task-detail poll failure", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001&dialog=organize");

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(
      await within(dialog).findByText("修正识别或作品", { exact: true }),
    );
    const recognition = within(dialog).getByLabelText("识别类型 One.2001.mkv");
    await user.selectOptions(recognition, "B");
    expect(recognition).toHaveValue("B");
    const overviewReadsBefore = backend.calls.overviewReads;

    // The existing five-second Task-detail poll answers 503 while the
    // operator's unsaved correction is still only in this card.
    backend.state.overviewUnavailable = true;
    await screen.findByText("任务详情暂时无法读取", undefined, {
      timeout: 9_000,
    });
    expect(backend.calls.overviewReads).toBeGreaterThan(overviewReadsBefore);
    expect(
      screen.getAllByRole("dialog", { name: "整理所选文件" }),
    ).toHaveLength(1);
    expect(recognition).toHaveValue("B");
    expect(
      screen.queryByRole("dialog", { name: "无法继续这次整理" }),
    ).toBeNull();
    // No discard prompt is produced by the background read; the draft is
    // still present and nothing was submitted or replayed.
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(backend.calls.posts).toEqual([]);

    backend.state.overviewUnavailable = false;
    await user.click(
      within(dialog).getByRole("button", { name: "重新读取任务" }),
    );
    await waitFor(() =>
      expect(within(dialog).queryByText("任务详情暂时无法读取")).toBeNull(),
    );
    expect(recognition).toHaveValue("B");
    expect(
      screen.getAllByRole("dialog", { name: "整理所选文件" }),
    ).toHaveLength(1);
    expect(backend.calls.posts).toEqual([]);
  }, 15_000);

  it("keeps an unknown Execute reconciliation through a task-detail poll failure without replaying", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    backend.state.executeResponseLost = true;
    backend.state.admissionUnavailable = true;
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations?run=task-001&dialog=organize");

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(within(dialog).getByRole("button", { name: /整批复核/ }));
    await user.click(
      await within(dialog).findByRole("button", { name: "确认整理 1 项" }),
    );
    await screen.findByText(/原整理提交暂未确认|正在自动核对原整理提交/);
    expect(backend.calls.posts).toHaveLength(1);
    const submittedPreview = backend.calls.posts[0];
    expect(submittedPreview).toContain("/previews/preview-1/execute");

    backend.state.overviewUnavailable = true;
    await screen.findByText("任务详情暂时无法读取", undefined, {
      timeout: 9_000,
    });
    // The retained command identity is not cleared by the unrelated background
    // read failure; the dialog keeps its automatic reconciliation.
    expect(
      within(dialog).getByText(/原整理提交暂未确认|正在自动核对/),
    ).toBeVisible();
    expect(
      within(dialog).getByRole("button", { name: "确认整理 1 项" }),
    ).toBeDisabled();
    expect(backend.calls.posts).toHaveLength(1);

    backend.state.overviewUnavailable = false;
    await user.click(
      within(dialog).getByRole("button", { name: "重新读取任务" }),
    );
    await waitFor(() =>
      expect(within(dialog).queryByText("任务详情暂时无法读取")).toBeNull(),
    );

    // Once the read surface recovers, the exact original request is checked
    // automatically and hands off; no manual reconciliation or second Execute
    // exists.
    backend.state.admissionUnavailable = false;
    await waitFor(
      () =>
        expect(
          screen.queryByRole("dialog", { name: "整理所选文件" }),
        ).toBeNull(),
      { timeout: 15_000 },
    );
    expect(router.state.location.pathname).toBe("/operations");
    expect(new URLSearchParams(router.history.location.search).get("run")).toBe(
      "task-001",
    );
    expect(
      new URLSearchParams(router.history.location.search).get("dialog"),
    ).toBeNull();
    expect(backend.calls.posts).toEqual([submittedPreview]);
    expect(backend.calls.admissionReads).toBeGreaterThanOrEqual(1);
  }, 20_000);

  it("Task59.1 reads a lost in-place analysis back into the same continuation file", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    const { router } = renderApp("/operations?run=task-001&dialog=organize");

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(
      await within(dialog).findByText("修正识别或作品", { exact: true }),
    );
    const recognition = within(dialog).getByLabelText("识别类型 One.2001.mkv");
    await user.selectOptions(recognition, "B");

    // The operator's own click starts one real analysis. This fake admits it
    // and publishes the exact second plan, then loses only the browser's copy
    // of that response.
    backend.state.analyzeResponseLost = true;
    await user.click(
      within(dialog).getByRole("button", { name: "保存并重新分析" }),
    );

    // The same-preparation read proves admission; the published plan states
    // this item's own new result on the file the operator acted on. No Files
    // overview is invented in this host and the card never leaves its address.
    expect(
      await within(dialog).findByText(
        /已重新分析并读回当前方案：现在可以纳入本次整理/,
      ),
    ).toBeVisible();
    expect(within(dialog).getByText("复制 · 来源保留")).toBeVisible();
    const inclusion = within(dialog).getByRole("checkbox", {
      name: "纳入 One.2001.mkv",
    });
    expect(inclusion).toBeEnabled();
    expect(inclusion).toBeChecked();
    expect(
      within(dialog).queryByRole("region", { name: "本次整理概览" }),
    ).toBeNull();
    expect(
      within(dialog).queryByRole("button", { name: /等待新的零变更方案/ }),
    ).toBeNull();
    expect(router.state.location.pathname).toBe("/operations");
    const search = new URLSearchParams(router.history.location.search);
    expect(search.get("run")).toBe("task-001");
    expect(search.get("dialog")).toBe("organize");
    const analyzePosts = backend.calls.posts.filter((url) =>
      /\/discoveries\/[^/]+\/analyze$/.test(url),
    );
    expect(analyzePosts).toHaveLength(1);
    expect(backend.calls.posts.filter((url) => /\/execute$/.test(url))).toEqual(
      [],
    );
  }, 20_000);

  it("Task59.1 releases an in-place analysis wait when only a sibling summary changed", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    backend.state.secondPlanKind = "sibling";
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001&dialog=organize");

    const dialog = await screen.findByRole("dialog", { name: "整理所选文件" });
    await within(dialog).findByRole("heading", { name: /第 1 \/ 1 个/ });
    await user.click(
      await within(dialog).findByText("修正识别或作品", { exact: true }),
    );
    await user.selectOptions(
      within(dialog).getByLabelText("识别类型 One.2001.mkv"),
      "B",
    );
    backend.state.analyzeResponseLost = true;
    await user.click(
      within(dialog).getByRole("button", { name: "保存并重新分析" }),
    );

    // The newer summary reorders the same plan without changing this item's
    // facts. The proved analysis releases the wait on this file instead of
    // holding it forever, and nothing is re-requested or executed.
    expect(
      await within(dialog).findByText(/当前文件的可读方案事实没有变化/),
    ).toBeVisible();
    expect(
      within(dialog).getByRole("checkbox", { name: "纳入 One.2001.mkv" }),
    ).toBeEnabled();
    expect(
      within(dialog).queryByRole("button", { name: /等待新的零变更方案/ }),
    ).toBeNull();
    expect(
      backend.calls.posts.filter((url) =>
        /\/discoveries\/[^/]+\/analyze$/.test(url),
      ),
    ).toHaveLength(1);
    expect(backend.calls.posts.filter((url) => /\/execute$/.test(url))).toEqual(
      [],
    );
  }, 20_000);

  it("protects unsaved drafts against leaving the task center without losing the card", async () => {
    const user = userEvent.setup();
    const backend = stubOrganizeHost();
    signInForOrganize();
    const { router } = renderApp("/operations");

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
    router.history.push("/resourcelib/files");
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
    const { router } = renderApp("/operations?run=task-001&dialog=organize");

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

  it("shows one retained admission line instead of the removed submission card", async () => {
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    beginOrganizeConfirmationRetention(
      "task-center-operator",
      { kind: "files", discoveryId: HOST_DISCOVERY_ID },
      {
        previewId: "preview-1",
        itemIds: ["item-1"],
        expectedIntentVersion: 1,
        allowOverwrite: false,
        allowSourceCleanup: false,
      },
    );
    renderApp("/operations?run=task-001");
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const link = await within(detail).findByRole("link", {
      name: "查看任务",
    });
    expect(link).toBeVisible();
    expect(
      within(detail).queryByRole("region", { name: "原整理提交" }),
    ).toBeNull();
    expect(
      within(detail).queryByRole("button", { name: /核对提交结果/ }),
    ).toBeNull();
    expect(backend.calls.admissionReads).toBeGreaterThanOrEqual(1);
  });

  it("performs no per-submission admission read for an ordinary task", async () => {
    const backend = stubOrganizeHost();
    authStore.setToken(TOKEN);
    renderApp("/operations?run=task-001");
    await screen.findByRole("dialog", { name: "运行详情" });
    expect(backend.calls.admissionReads).toBe(0);
  });
});
