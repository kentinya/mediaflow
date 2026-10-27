import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import {
  operationsLandingSearch,
  parseOperationsReturnContext,
} from "../../shared/navigation/operations-return";
import { renderApp } from "../../../tests/utils";
import manualOperationsFixture from "../../entities/operations/__fixtures__/manual-operations.json";

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
      screen.getByText(
        /任务列表合并授权范围内的 Job 与 Task，并按明确关联去重/,
      ),
    ).toBeVisible();
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

/** The durable remaining-scope preparation document the backend admits. */
function remainingScopeDiscoveryDocument(
  overrides: {
    readonly previewId?: string | null;
    readonly status?: string;
    readonly nextAction?: string;
  } = {},
): Record<string, unknown> {
  const previewId = overrides.previewId ?? null;
  const status =
    overrides.status ?? (previewId === null ? "queued" : "completed");
  const nextAction =
    overrides.nextAction ?? "wait for the resident Processing Worker";
  return {
    journey: "discovery",
    discoveryId: "discovery-remaining",
    resourceLibraryId: "source",
    storageId: "source-storage",
    configurationSnapshotId: "snapshot-remaining",
    status,
    version: 1,
    selection: {
      scopeCount: 1,
      scopes: [{ path: "Incoming", kind: "directory" }],
    },
    budgets: {},
    progress: {
      phase: previewId === null ? "queued" : "prepared",
      primarySources: previewId === null ? 0 : 1,
      visitedEntries: 0,
      visitedDirectories: 0,
      pageFetches: 0,
      excludedEntries: 0,
      unstableEntries: 0,
      errorEntries: 0,
      incomplete: false,
      incompleteReason: null,
      refusalReasons: [],
      materialRefusal: null,
      findings: [],
      reasons: [],
      message: "queued for bounded remaining-scope observation",
    },
    primarySourceCount: previewId === null ? 0 : 1,
    admissionRequestId: null,
    autoPrepare: true,
    prepared: previewId !== null,
    previewId,
    intentId: previewId === null ? null : "intent-remaining",
    frozen: previewId !== null,
    frozenAt: null,
    pauseRequested: false,
    cancelRequested: false,
    nextObservationAt: null,
    worker: {
      ready: true,
      condition: "worker_ready",
      durableState: "one resident Worker is registered",
      nextAction: "wait for the resident Processing Worker",
    },
    actions: {
      pause: {
        available: true,
        method: "POST",
        path: "/pause",
        requiresVersion: true,
        sideEffects: "none",
      },
      resume: {
        available: false,
        method: "POST",
        path: "/resume",
        requiresVersion: true,
        sideEffects: "none",
      },
      cancel: {
        available: true,
        method: "POST",
        path: "/cancel",
        requiresVersion: true,
        sideEffects: "none",
      },
      finalize: {
        available: false,
        method: "POST",
        path: "/finalize",
        requiresVersion: true,
        sideEffects: "none",
      },
      prepare: {
        available: false,
        method: "POST",
        path: "/analyze",
        requiresVersion: true,
        sideEffects: "none",
      },
    },
    sources: [],
    nextAction,
    failure: null,
    sideEffects: "none",
    zeroMutation: true,
    execution: "not_available_from_discovery",
  };
}

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
  /**
   * Optional bounded extra GET handler.  It may answer synchronously or
   * asynchronously, so a test can keep one read in flight long enough to
   * observe the derived loading state before its outcome lands.
   */
  readonly extraGet?: (
    url: string,
  ) => Response | null | Promise<Response | null>;
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
    const extra = await options.extraGet?.(url);
    if (extra !== undefined && extra !== null) {
      return extra;
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
  return { fetchMock, overviewReads: () => overviewReads };
}

/** The exact remaining-scope Preview document the panel confirms against. */
function remainingScopePreviewFixture(): Record<string, unknown> {
  const preview = JSON.parse(
    JSON.stringify(
      (manualOperationsFixture as Record<string, unknown>)[
        "organizePreviewDetail"
      ],
    ),
  ) as Record<string, unknown>;
  preview["previewId"] = "preview-remaining";
  preview["intentId"] = "intent-remaining";
  preview["intentVersion"] = 3;
  preview["executionCandidateItemIds"] = ["item-1"];
  const items = preview["items"] as Record<string, unknown>[];
  items[0]!["itemId"] = "item-1";
  items[0]!["previewItemId"] = "preview-item-1";
  (preview["selection"] as Record<string, unknown>)["selectedItemIds"] = [
    "item-1",
  ];
  (preview["selection"] as Record<string, unknown>)["unselectedItemIds"] = [];
  const actions = preview["actions"] as Record<string, Record<string, unknown>>;
  actions["execute"]!["path"] =
    "/api/v1/operations/organize/previews/preview-remaining/execute";
  return preview;
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
            command: "preview",
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
      name: "在当前界面生成剩余范围摘要",
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
          command: "preview",
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

  it("shows the linked zero-mutation plan summary in the run detail panel", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    // The run's durable continuation points at one complete zero-mutation plan.
    // That plan is summarized and confirmed in this same panel: no separate
    // Preview destination is opened and no navigation is produced.
    const preview = remainingScopePreviewFixture();
    preview["previewId"] = "preview-recovery";
    preview["intentId"] = "intent-recovery";
    preview["intentVersion"] = 2;
    (preview["actions"] as Record<string, Record<string, unknown>>)["execute"]![
      "path"
    ] = "/api/v1/operations/organize/previews/preview-recovery/execute";

    stubLifecycleJourney({
      posts,
      overview: {
        continuation: {
          continuationId: "preview-recovery",
          status: "previewed",
          command: "organize",
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
          nextAction: "review the exact plan",
          sideEffects: "none",
        },
      },
      respond: () => jsonResponse({ error: { code: "not_found" } }, 404),
      extraGet: (url) =>
        url === "/api/v1/operations/organize/previews/preview-recovery"
          ? jsonResponse(preview)
          : null,
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations?status=paused&run=task-001",
    );

    const facts = await screen.findByRole("region", { name: "运行详情" });
    // The facts name the same-panel summary instead of a removed destination.
    expect(
      await within(facts).findByText(/完整零变更计划摘要显示在本运行详情内/),
    ).toBeVisible();
    expect(
      within(facts).queryByRole("button", { name: "查看关联的精确预览" }),
    ).toBeNull();

    // The same shared same-page summary component renders this run's exact
    // plan; its heading names the remaining-scope journey.
    const summary = await screen.findByRole("region", {
      name: "新计划摘要",
    });
    expect(
      within(summary).getByText("剩余范围计划摘要（零变更）"),
    ).toBeVisible();
    expect(
      await within(summary).findByRole("button", {
        name: /确认继续整理剩余 1 项/,
      }),
    ).toBeEnabled();
    expect(posts).toHaveLength(0);
    expect(router.history.location.pathname).toBe("/ui-v2/operations");
    expect(user).toBeDefined();
  });

  it("prepares and confirms the paused remaining scope in the same panel", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    const preview = JSON.parse(
      JSON.stringify(
        (manualOperationsFixture as Record<string, unknown>)[
          "organizePreviewDetail"
        ],
      ),
    ) as Record<string, unknown>;
    preview["previewId"] = "preview-remaining";
    preview["intentId"] = "intent-remaining";
    preview["intentVersion"] = 3;
    preview["executionCandidateItemIds"] = ["item-1"];
    const items = preview["items"] as Record<string, unknown>[];
    items[0]!["itemId"] = "item-1";
    items[0]!["previewItemId"] = "preview-item-1";
    (preview["selection"] as Record<string, unknown>)["selectedItemIds"] = [
      "item-1",
    ];
    (preview["selection"] as Record<string, unknown>)["unselectedItemIds"] = [];
    const actions = preview["actions"] as Record<
      string,
      Record<string, unknown>
    >;
    actions["execute"]!["path"] =
      "/api/v1/operations/organize/previews/preview-remaining/execute";

    const { fetchMock } = stubLifecycleJourney({
      posts,
      lifecycle: runLifecycleDocument({
        state: "paused",
        actions: [
          lifecycleAction("cancel", true, null),
          lifecycleAction("resume", false, "authority required", {
            available: true,
            reason: null,
            method: "POST",
            path: "/api/v1/tasks/task-001/remaining-scope-previews",
            requiresConfirmation: false,
            sideEffects: "none",
            durableOutcome: "durable exact Preview",
            nextAction: "review then authorize",
          }),
        ],
      }),
      extraGet: (url) =>
        url.endsWith("/discoveries/discovery-remaining")
          ? jsonResponse(
              remainingScopeDiscoveryDocument({
                previewId: "preview-remaining",
              }),
            )
          : url.endsWith("/preview-remaining")
            ? jsonResponse(preview)
            : null,
      respond: (url) => {
        if (url.endsWith("/remaining-scope-previews")) {
          return jsonResponse(
            remainingScopeDiscoveryDocument({ previewId: null }),
            202,
          );
        }
        if (url.endsWith("/execute")) {
          return jsonResponse(
            {
              executionId: "execution-remaining",
              taskId: "task-remaining",
              status: "admitted",
              selectedItemIds: ["item-1"],
              nextAction: "track the durable Worker execution",
            },
            202,
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      },
    });
    expect(fetchMock).toBeDefined();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    await user.click(
      within(controls).getByRole("button", {
        name: "在当前界面生成剩余范围摘要",
      }),
    );

    const summary = await screen.findByRole("region", { name: "新计划摘要" });
    const confirm = await within(summary).findByRole("button", {
      name: /确认继续整理剩余 1 项/,
    });
    // The summary is zero-mutation: no execution is admitted before confirm.
    expect(posts.some((post) => post.url.endsWith("/execute"))).toBe(false);
    await user.click(confirm);
    await waitFor(() =>
      expect(posts.some((post) => post.url.endsWith("/execute"))).toBe(true),
    );
    const execute = posts.find((post) => post.url.endsWith("/execute"))!;
    expect(execute.body).toMatchObject({
      itemIds: ["item-1"],
      expectedIntentVersion: 3,
    });
  });

  it("reconciles a lost paused remaining-scope confirmation against the exact request", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    const preview = JSON.parse(
      JSON.stringify(
        (manualOperationsFixture as Record<string, unknown>)[
          "organizePreviewDetail"
        ],
      ),
    ) as Record<string, unknown>;
    preview["previewId"] = "preview-remaining";
    preview["intentId"] = "intent-remaining";
    preview["intentVersion"] = 3;
    preview["executionCandidateItemIds"] = ["item-1"];
    const items = preview["items"] as Record<string, unknown>[];
    items[0]!["itemId"] = "item-1";
    items[0]!["previewItemId"] = "preview-item-1";
    (preview["selection"] as Record<string, unknown>)["selectedItemIds"] = [
      "item-1",
    ];
    (preview["selection"] as Record<string, unknown>)["unselectedItemIds"] = [];
    const actions = preview["actions"] as Record<
      string,
      Record<string, unknown>
    >;
    actions["execute"]!["path"] =
      "/api/v1/operations/organize/previews/preview-remaining/execute";

    let admissionReads = 0;
    stubLifecycleJourney({
      posts,
      lifecycle: runLifecycleDocument({
        state: "paused",
        actions: [
          lifecycleAction("cancel", true, null),
          lifecycleAction("resume", false, "authority required", {
            available: true,
            reason: null,
            method: "POST",
            path: "/api/v1/tasks/task-001/remaining-scope-previews",
            requiresConfirmation: false,
            sideEffects: "none",
            durableOutcome: "durable exact Preview",
            nextAction: "review then authorize",
          }),
        ],
      }),
      extraGet: (url) =>
        url.endsWith("/discoveries/discovery-remaining")
          ? jsonResponse(
              remainingScopeDiscoveryDocument({
                previewId: "preview-remaining",
              }),
            )
          : url.endsWith("/preview-remaining")
            ? jsonResponse(preview)
            : url.includes("/preview-remaining/admission")
              ? (() => {
                  admissionReads += 1;
                  return jsonResponse({
                    outcome: "known",
                    reason: null,
                    executionId: "execution-remaining",
                    taskId: "task-remaining",
                    status: "admitted",
                    selectedItemIds: ["item-1"],
                    completedItemCount: 0,
                    failedItemCount: 0,
                    sideEffects: "none",
                    nextAction: "track the durable Worker execution",
                  });
                })()
              : null,
      respond: (url) => {
        if (url.endsWith("/remaining-scope-previews")) {
          return jsonResponse(
            remainingScopeDiscoveryDocument({ previewId: null }),
            202,
          );
        }
        if (url.endsWith("/execute")) {
          // The admission really committed but the response is lost.
          throw new TypeError("network down");
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    await user.click(
      within(controls).getByRole("button", {
        name: "在当前界面生成剩余范围摘要",
      }),
    );
    const summary = await screen.findByRole("region", { name: "新计划摘要" });
    await user.click(
      await within(summary).findByRole("button", {
        name: /确认继续整理剩余 1 项/,
      }),
    );
    // The lost response is never described as a proven zero effect; the exact
    // submission is retained for reconciliation and no automatic retry occurs.
    expect(
      await screen.findByRole("button", { name: "核对本次确认的持久状态" }),
    ).toBeVisible();
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      1,
    );

    await user.click(
      screen.getByRole("button", { name: "核对本次确认的持久状态" }),
    );
    // The reconciliation read binds the exact submitted selection and version.
    await waitFor(() => expect(admissionReads).toBe(1));
    expect(
      await screen.findByRole("button", { name: "查看关联执行结果" }),
    ).toBeVisible();
    // No second execute was ever issued.
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      1,
    );
  });

  it("restores the durable paused remaining-scope summary and admitted execution", async () => {
    const posts: { url: string; body: unknown }[] = [];
    const { fetchMock } = stubLifecycleJourney({
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
          recoveryPreviewId: "preview-remaining",
          executionId: null,
          nextAction: "review the exact Preview",
          sideEffects: "none",
        },
      },
      respond: () => jsonResponse({ error: { code: "not_found" } }, 404),
    });
    expect(fetchMock).toBeDefined();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?status=paused&run=task-001");

    // The durable summary is restored from the overview read alone; the browser
    // never re-posts remaining-scope-previews to rebuild a lost summary.
    const summary = await screen.findByRole("region", { name: "新计划摘要" });
    expect(summary).toBeVisible();
    expect(
      posts.some((post) => post.url.endsWith("/remaining-scope-previews")),
    ).toBe(false);
  });

  it("surfaces a terminal remaining-scope preparation failure without a summary", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    stubLifecycleJourney({
      posts,
      lifecycle: runLifecycleDocument({
        state: "paused",
        actions: [
          lifecycleAction("cancel", true, null),
          lifecycleAction("resume", false, "authority required", {
            available: true,
            reason: null,
            method: "POST",
            path: "/api/v1/tasks/task-001/remaining-scope-previews",
            requiresConfirmation: false,
            sideEffects: "none",
            durableOutcome: "durable exact Preview",
            nextAction: "review then authorize",
          }),
        ],
      }),
      extraGet: (url) =>
        url.endsWith("/discoveries/discovery-remaining")
          ? jsonResponse(
              remainingScopeDiscoveryDocument({
                status: "failed",
                nextAction: "修复来源可读性后重新发起剩余范围准备",
              }),
            )
          : null,
      respond: (url) => {
        if (url.endsWith("/remaining-scope-previews")) {
          return jsonResponse(
            remainingScopeDiscoveryDocument({ previewId: null }),
            202,
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    await user.click(
      within(controls).getByRole("button", {
        name: "在当前界面生成剩余范围摘要",
      }),
    );

    // The terminal preparation keeps its durable next action visible and never
    // fabricates a confirmable summary.
    expect(
      await screen.findByText(/修复来源可读性后重新发起剩余范围准备/),
    ).toBeVisible();
    expect(screen.queryByRole("region", { name: "新计划摘要" })).toBeNull();
    expect(posts.some((post) => post.url.endsWith("/execute"))).toBe(false);
  });

  it("does not reopen a confirmed summary when the overview carries its admitted execution", async () => {
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
          recoveryPreviewId: "preview-remaining",
          executionId: "execution-remaining",
          nextAction: "review the exact Preview",
          sideEffects: "none",
        },
      },
      respond: () => jsonResponse({ error: { code: "not_found" } }, 404),
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?status=paused&run=task-001");

    // The overview already proves this exact Preview was admitted: the cached
    // summary is not reopened for another confirmation, and no POST is sent.
    await screen.findByRole("region", { name: "运行详情" });
    expect(screen.queryByRole("region", { name: "新计划摘要" })).toBeNull();
    expect(posts).toHaveLength(0);
  });

  it("recovers a failed first preparation read with one explicit re-read, not another POST", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    const preview = remainingScopePreviewFixture();
    let discoveryReads = 0;
    stubLifecycleJourney({
      posts,
      lifecycle: runLifecycleDocument({
        state: "paused",
        actions: [
          lifecycleAction("cancel", true, null),
          lifecycleAction(
            "resume",
            false,
            "authority required",
            AUTHORITY_PREVIEW,
          ),
        ],
      }),
      extraGet: async (url) => {
        if (url.endsWith("/discoveries/discovery-remaining")) {
          discoveryReads += 1;
          if (discoveryReads === 1) {
            // Keep the first read in flight briefly so the derived loading
            // notice is observable, then fail it with a bounded 503.
            await new Promise((resolve) => setTimeout(resolve, 150));
            return jsonResponse(
              { error: { code: "service_unavailable" } },
              503,
            );
          }
          return jsonResponse(
            remainingScopeDiscoveryDocument({
              previewId: "preview-remaining",
            }),
          );
        }
        if (url.endsWith("/preview-remaining")) {
          return jsonResponse(preview);
        }
        return null;
      },
      respond: (url) => {
        if (url.endsWith("/remaining-scope-previews")) {
          return jsonResponse(
            remainingScopeDiscoveryDocument({ previewId: null }),
            202,
          );
        }
        if (url.endsWith("/execute")) {
          return jsonResponse(
            {
              executionId: "execution-remaining",
              taskId: "task-remaining",
              status: "admitted",
              selectedItemIds: ["item-1"],
              nextAction: "track the durable Worker execution",
            },
            202,
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    await user.click(
      within(controls).getByRole("button", {
        name: "在当前界面生成剩余范围摘要",
      }),
    );

    // The first read is an explicit loading state of an already admitted
    // preparation — never an empty panel and never a second POST.
    expect(
      await screen.findByRole("heading", { name: "正在读取剩余范围准备" }),
    ).toBeVisible();
    expect(
      posts.filter((post) => post.url.endsWith("/remaining-scope-previews")),
    ).toHaveLength(1);

    // The failed read is a truthful, recoverable state: the stage, the
    // admitted-but-not-executed fact, the unknown durable state and the
    // explicit re-read next step are visible; it is not shown as an empty
    // state, as "no work was created", or as a finished/failed preparation.
    expect(
      await screen.findByRole("heading", {
        name: "剩余范围准备状态读取失败",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/阶段：读取本页已受理的剩余范围准备状态/),
    ).toBeVisible();
    expect(screen.getByText(/这是准备受理，不是执行受理/)).toBeVisible();
    expect(screen.getByText(/尚未成功读到该准备的持久状态/)).toBeVisible();
    expect(screen.queryByRole("region", { name: "新计划摘要" })).toBeNull();
    expect(screen.queryByText(/没有创建执行/)).toBeNull();
    expect(
      posts.filter((post) => post.url.endsWith("/remaining-scope-previews")),
    ).toHaveLength(1);
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      0,
    );

    // Fault cleared: the explicit action repeats only the same GET of this
    // discovery id, and the same exact summary reappears on this page.
    await user.click(screen.getByRole("button", { name: "重新读取本次准备" }));
    expect(
      await screen.findByRole("region", { name: "新计划摘要" }),
    ).toBeVisible();
    expect(
      await screen.findByRole("heading", {
        name: "剩余范围计划摘要（零变更）",
      }),
    ).toBeVisible();
    expect(discoveryReads).toBe(2);
    expect(
      posts.filter((post) => post.url.endsWith("/remaining-scope-previews")),
    ).toHaveLength(1);
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      0,
    );
  });

  it("keeps the last known preparation state through a failed poll and recovers on the explicit re-read", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    const preview = remainingScopePreviewFixture();
    let discoveryReads = 0;
    stubLifecycleJourney({
      posts,
      lifecycle: runLifecycleDocument({
        state: "paused",
        actions: [
          lifecycleAction("cancel", true, null),
          lifecycleAction(
            "resume",
            false,
            "authority required",
            AUTHORITY_PREVIEW,
          ),
        ],
      }),
      extraGet: (url) => {
        if (url.endsWith("/discoveries/discovery-remaining")) {
          discoveryReads += 1;
          if (discoveryReads === 1) {
            return jsonResponse(
              remainingScopeDiscoveryDocument({ previewId: null }),
            );
          }
          if (discoveryReads === 2) {
            return jsonResponse(
              { error: { code: "service_unavailable" } },
              503,
            );
          }
          return jsonResponse(
            remainingScopeDiscoveryDocument({
              previewId: "preview-remaining",
            }),
          );
        }
        if (url.endsWith("/preview-remaining")) {
          return jsonResponse(preview);
        }
        return null;
      },
      respond: (url) => {
        if (url.endsWith("/remaining-scope-previews")) {
          return jsonResponse(
            remainingScopeDiscoveryDocument({ previewId: null }),
            202,
          );
        }
        if (url.endsWith("/execute")) {
          return jsonResponse(
            {
              executionId: "execution-remaining",
              taskId: "task-remaining",
              status: "admitted",
              selectedItemIds: ["item-1"],
              nextAction: "track the durable Worker execution",
            },
            202,
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    await user.click(
      within(controls).getByRole("button", {
        name: "在当前界面生成剩余范围摘要",
      }),
    );

    // The first successful durable read derives the admitted-in-progress
    // notice; no read failure and no summary exist yet.
    expect(
      await screen.findByText(
        /常驻 Worker 将在配置的稳定区间满足后生成计划摘要/,
      ),
    ).toBeVisible();
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      0,
    );

    // The next bounded poll fails: the panel switches to the read-failure
    // state with the last known durable state preserved, states that the new
    // state is unknown, and stops polling by itself.
    expect(
      await screen.findByRole(
        "heading",
        { name: "剩余范围准备状态读取失败" },
        { timeout: 5000 },
      ),
    ).toBeVisible();
    expect(screen.getByText(/最后已知状态：排队中/)).toBeVisible();
    expect(
      screen.getByText(/失败原因：服务当前不可读取该准备状态/),
    ).toBeVisible();
    expect(screen.queryByRole("region", { name: "新计划摘要" })).toBeNull();
    expect(discoveryReads).toBe(2);
    expect(
      posts.filter((post) => post.url.endsWith("/remaining-scope-previews")),
    ).toHaveLength(1);
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      0,
    );

    // Fault cleared: the explicit re-read GETs the same discovery id, the
    // polling resumes its ordinary life cycle, and the same exact summary is
    // restored — still exactly one preparation POST and no execution.
    await user.click(screen.getByRole("button", { name: "重新读取本次准备" }));
    expect(
      await screen.findByRole("region", { name: "新计划摘要" }),
    ).toBeVisible();
    expect(discoveryReads).toBe(3);
    expect(
      posts.filter((post) => post.url.endsWith("/remaining-scope-previews")),
    ).toHaveLength(1);
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      0,
    );
  });

  it("keeps the shared auth boundary copy for a forbidden preparation read", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    stubLifecycleJourney({
      posts,
      lifecycle: runLifecycleDocument({
        state: "paused",
        actions: [
          lifecycleAction("cancel", true, null),
          lifecycleAction(
            "resume",
            false,
            "authority required",
            AUTHORITY_PREVIEW,
          ),
        ],
      }),
      extraGet: (url) =>
        url.endsWith("/discoveries/discovery-remaining")
          ? jsonResponse({ error: { code: "forbidden" } }, 403)
          : null,
      respond: (url) => {
        if (url.endsWith("/remaining-scope-previews")) {
          return jsonResponse(
            remainingScopeDiscoveryDocument({ previewId: null }),
            202,
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    await user.click(
      within(controls).getByRole("button", {
        name: "在当前界面生成剩余范围摘要",
      }),
    );

    // The 403 reuses the shared auth boundary's bounded recovery copy, while
    // the admitted preparation facts and the re-read action stay visible on
    // this page; nothing is treated as an empty state.
    expect(
      await screen.findByText("Connect a principal with read permission"),
    ).toBeVisible();
    expect(screen.getByText(/这是准备受理，不是执行受理/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "重新读取本次准备" }),
    ).toBeVisible();
    expect(
      posts.filter((post) => post.url.endsWith("/remaining-scope-previews")),
    ).toHaveLength(1);
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      0,
    );
  });

  it("follows the shared authority recovery when the preparation read is rejected with 401", async () => {
    const user = userEvent.setup();
    const posts: { url: string; body: unknown }[] = [];
    stubLifecycleJourney({
      posts,
      lifecycle: runLifecycleDocument({
        state: "paused",
        actions: [
          lifecycleAction("cancel", true, null),
          lifecycleAction(
            "resume",
            false,
            "authority required",
            AUTHORITY_PREVIEW,
          ),
        ],
      }),
      extraGet: (url) =>
        url.endsWith("/discoveries/discovery-remaining")
          ? jsonResponse({ error: { code: "unauthorized" } }, 401)
          : null,
      respond: (url) => {
        if (url.endsWith("/remaining-scope-previews")) {
          return jsonResponse(
            remainingScopeDiscoveryDocument({ previewId: null }),
            202,
          );
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const controls = await screen.findByRole("region", { name: "运行控制" });
    await user.click(
      within(controls).getByRole("button", {
        name: "在当前界面生成剩余范围摘要",
      }),
    );

    // This is the only 401 in the journey: the shared authority recovery
    // clears the rejected principal, the route stays behind the shared
    // "new credentials required" state, and the local failure notice hands
    // over to it instead of keeping its own copy.
    await waitFor(() => {
      expect(authStore.isRejected()).toBe(true);
      expect(
        screen.queryByRole("heading", {
          name: "剩余范围准备状态读取失败",
        }),
      ).toBeNull();
    });
    expect(
      (
        await screen.findAllByText(
          "The API token was rejected. Enter a valid API principal token to continue.",
        )
      ).length,
    ).toBeGreaterThan(0);
    expect(
      posts.filter((post) => post.url.endsWith("/remaining-scope-previews")),
    ).toHaveLength(1);
    expect(posts.filter((post) => post.url.endsWith("/execute"))).toHaveLength(
      0,
    );
  });
});
