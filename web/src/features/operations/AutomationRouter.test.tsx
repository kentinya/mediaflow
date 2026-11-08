import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { renderApp } from "../../../tests/utils";

/**
 * Component/router proof for the V2 Automation journey.
 *
 * Every document mirrors the exact operator projection the real Python API
 * returns (proved by tests/test_v2_automation_operations.py). The assertions
 * prove the operator journey and its safety properties: Draft/Active
 * distinction, backend-authoritative availability, one confirmed grant action,
 * exact request methods and bodies, no authority material in any request, and
 * no executable control for a state the backend does not advertise.
 */

type Json = Record<string, unknown>;

const TOKEN = "automation-token";
const ACTIVE_REVISION = "revision-active-1";
const DRAFT_REVISION = "revision-draft-1";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: unknown;
}

function recordingFetch(
  respond: (call: Call) => Response | Promise<Response> | undefined,
): {
  calls: Call[];
} {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: init?.method ?? "GET",
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as unknown)
            : null,
      };
      calls.push(call);
      const response = respond(call);
      if (response !== undefined) {
        return response;
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return { calls };
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function action(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: "/api/v1/automation/task-definitions/auto-task/grant",
    requiresConfirmation: false,
    sideEffects: "none",
    durableOutcome: "a persistent scoped unattended execution grant is stored",
    nextAction: "review the grant eligibility and explicitly confirm",
    ...overrides,
  };
}

function definitionDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id: "auto-task",
    name: "Nightly automation",
    definitionState: "active",
    enabled: true,
    resourceLibraryId: "source",
    mode: "automatic-organization",
    itemLimit: 12,
    sourceScope: null,
    intervalSeconds: 3600,
    occurrence: {
      enabled: true,
      nextRunAt: "2026-01-01T08:00:00+00:00",
      lastOccurrenceAt: null,
      lastJobId: null,
      lastTaskId: null,
      lastOutcome: null,
      lastReason: null,
      nextAction: "wait for the next due occurrence",
      lastFailureCategory: null,
      outcomeSummary: null,
    },
    unattendedExecutionGrant: {
      status: "none",
      active: false,
      grantId: null,
      definitionId: "auto-task",
      definitionChangedSinceGrant: false,
      nextAction: "review the exact definition bounds and explicitly grant",
    },
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    draftState: {
      present: false,
      reason: "no open successor Draft contains this definition",
      revisionId: null,
      revisionVersion: null,
      revisionStatus: null,
      baseActiveRevisionId: null,
      updatedAt: null,
      validatedAt: null,
      validationErrors: [],
    },
    executionReadiness: {
      state: "enabled",
      explanation:
        "The saved schedule is enabled; runtime checks remain required.",
      nextAction: "Review the saved scope and limits.",
    },
    grantEligibility: {
      eligible: true,
      status: "eligible",
      previewId: "preview-1",
      previewStatus: "previewed",
      current: true,
      zeroMutation: true,
      effectiveItemLimit: 12,
      maxItemsPerRun: 12,
      currentPermission: {
        principalId: "admin",
        status: "valid",
        allowed: true,
      },
      explanation:
        "the exact current Preview and permission satisfy the bounds",
      durableState: "no grant or media mutation has been created",
      retrySafe: true,
      nextAction: "review the exact bounds and explicitly confirm the grant",
      error: null,
    },
    actions: {
      detail: action({
        available: true,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/auto-task",
        requiresConfirmation: false,
        durableOutcome: null,
        nextAction: "inspect the durable definition state",
      }),
      occurrences: action({
        available: true,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/auto-task/occurrences",
        requiresConfirmation: false,
        durableOutcome: null,
        nextAction: "inspect the bounded occurrence history",
      }),
      runOnce: action({
        path: "/api/v1/operations/automation/task-definitions/auto-task/run-once",
        requiresConfirmation: false,
        durableOutcome:
          "a durable bounded discovery of the definition scope is admitted",
        nextAction: "start Run once and review the exact plan summary",
      }),
      grantState: action({
        available: true,
        method: "GET",
        path: "/api/v1/automation/task-definitions/auto-task/grant-state",
        durableOutcome: null,
        nextAction: "read the current grant state",
      }),
      grant: action({ requiresConfirmation: true }),
      revoke: action({
        path: "/api/v1/automation/task-definitions/auto-task/revoke",
        durableOutcome: "the grant is revoked",
        nextAction: "revoke the grant when its bounds are no longer wanted",
      }),
      copy: action({
        available: false,
        method: "POST",
        path: "/api/v1/automation/task-definitions/auto-task/copy",
        requiresConfirmation: false,
        reason: "an open successor Draft is required to copy this definition",
        durableOutcome: "a copied definition is stored inside the Draft",
        nextAction: "create or open a successor Draft, then copy",
      }),
      draftCreate: action({
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
        requiresConfirmation: false,
        durableOutcome: "a successor Draft is stored",
        nextAction: "create or open the successor Draft",
      }),
    },
    ...overrides,
  };
}

/**
 * The full-population metric cards exactly as the backend publishes them.
 *
 * The backend counts the whole authorized admitted-run population, so the
 * values are independent of the page the table happens to show.
 */
function metricsDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    available: true,
    scope: "full_authorized_population",
    basis:
      "each original admitted run counted once by its durable admission " +
      "timestamp in the configured system timezone",
    timezone: "Asia/Shanghai",
    cronTimezoneNote:
      "Cron definition timezones stay separate from this system calendar",
    evaluatedAt: "2026-03-01T04:00:00+08:00",
    monthToDateAdmitted: 4,
    previousPeriodAdmitted: 0,
    comparisonAvailable: false,
    comparisonUnavailableReason: "no_comparable_previous_period",
    monthToDateTerminal: 3,
    monthToDateActive: 1,
    monthToDateUnavailable: 0,
    monthToDateNoWork: 1,
    monthToDatePartial: 0,
    monthToDateFailed: 1,
    monthToDateCancelled: 0,
    monthToDateUncertain: 0,
    inventory: inventoryCountsDocument(),
    denominatorStatement:
      "completed plus failed Task flow results in the current local month (3)",
    successRate: 2 / 3,
    completedCount: 2,
    evaluatedCount: 3,
    noWorkStatement:
      "skipped files are not organized files and a reached item bound does " +
      "not prove scope exhaustion",
    nextAction: null,
    windows: {
      current: {
        start: "2026-02-28T16:00:00+00:00",
        end: "2026-03-01T04:00:00+00:00",
        startLocal: "2026-03-01T00:00:00+08:00",
        endLocal: "2026-03-01T12:00:00+08:00",
        nextPeriodStartLocal: "2026-04-01T00:00:00+08:00",
      },
      previous: {
        start: "2026-01-31T16:00:00+00:00",
        end: "2026-02-28T16:00:00+00:00",
        startLocal: "2026-02-01T00:00:00+08:00",
        endLocal: "2026-03-01T00:00:00+08:00",
      },
    },
    ...overrides,
  };
}

/** The exact submitted inventory read basis the backend echoes back. */
function inventoryQueryDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    q: null,
    enabled: null,
    library: null,
    state: null,
    sort: "name",
    direction: "asc",
    limit: 20,
    scope: "full_authorized_population",
    ...overrides,
  };
}

function inventoryCountsDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    published: 1,
    enabled: 1,
    draftOnly: 0,
    total: 1,
    basis: "exact_current_active_and_open_drafts",
    scope: "full_authorized_population",
    ...overrides,
  };
}

function listDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    items: [definitionDocument()],
    total: 1,
    truncated: false,
    metrics: metricsDocument(),
    inventoryCounts: inventoryCountsDocument(),
    latestAdmittedRuns: {},
    query: inventoryQueryDocument(),
    itemsTruncatedByCap: false,
    next_cursor: null,
    previous_cursor: null,
    draftState: {
      present: false,
      reason: "no open successor Draft exists",
      revisionId: null,
      revisionVersion: null,
      revisionStatus: null,
      baseActiveRevisionId: null,
      updatedAt: null,
      validatedAt: null,
      validationErrors: [],
    },
    resourceLibraryOptions: [{ id: "source", name: "Source", enabled: true }],
    actions: {
      create: action({
        method: "POST",
        path: "/api/v1/automation/task-definitions",
        requiresConfirmation: false,
        durableOutcome: "the bounded definition is stored inside the Draft",
        nextAction: "start or open a successor Draft, then create",
      }),
      createDraft: action({
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
        requiresConfirmation: false,
        durableOutcome: "a successor Draft is stored",
        nextAction: "create or open the successor Draft",
      }),
    },
    ...overrides,
  };
}

/** One bounded definition occurrence history read. */
function occurrencesDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    definitionId: "auto-task",
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    items: [],
    limit: 20,
    truncated: false,
    next_cursor: null,
    previous_cursor: null,
    ...overrides,
  };
}

/** One empty but valid execution records page. */
function recordsDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    items: [],
    limit: 20,
    definition: "auto-task",
    trigger: null,
    status: null,
    outcome: null,
    from: null,
    to: null,
    total: 0,
    truncated: false,
    population:
      "admitted Automation runs deduplicated by explicit task linkage",
    historyBasis:
      "definition/name/scope/version from the durable admission, never backfilled from the current Active configuration",
    next_cursor: null,
    previous_cursor: null,
    ...overrides,
  };
}

/**
 * A definition that lives only inside the open successor Draft (newly
 * created or copied): draft-only state, empty occurrence history, no grant
 * and no Active-definition actions until checked activation.
 */
function draftOnlyDefinitionDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const notActiveReason =
    "this definition exists only inside an open successor Draft; " +
    "activate the Draft to make it the Active definition";
  return {
    id: "created-task",
    name: "Created automation",
    definitionState: "draft-only",
    executionReadiness: {
      state: "draft-only",
      explanation: "Not consumed by runtime.",
      nextAction: "Review the Draft.",
    },
    enabled: false,
    resourceLibraryId: "source",
    mode: "automatic-organization",
    itemLimit: 9,
    sourceScope: null,
    intervalSeconds: null,
    cron: "0 8 * * *",
    timezone: "UTC",
    occurrence: {
      enabled: false,
      nextRunAt: null,
      lastOccurrenceAt: null,
      lastJobId: null,
      lastTaskId: null,
      lastOutcome: null,
      lastReason: null,
      nextAction: null,
      lastFailureCategory: null,
      outcomeSummary: null,
    },
    unattendedExecutionGrant: {
      status: "none",
      active: false,
      grantId: null,
      definitionId: "created-task",
      definitionChangedSinceGrant: false,
      nextAction: "review the exact definition bounds and explicitly grant",
    },
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    draftState: {
      present: true,
      reason: null,
      revisionId: DRAFT_REVISION,
      revisionVersion: 2,
      revisionStatus: "draft",
      baseActiveRevisionId: ACTIVE_REVISION,
      updatedAt: "2026-01-01T00:00:00+00:00",
      validatedAt: null,
      validationErrors: [],
    },
    actions: {
      detail: action({
        available: true,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/created-task",
        requiresConfirmation: false,
        durableOutcome: null,
        nextAction: "inspect the durable definition state",
      }),
      occurrences: action({
        available: true,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/created-task/occurrences",
        requiresConfirmation: false,
        durableOutcome: null,
        nextAction: "inspect the bounded occurrence history",
      }),
      runOnce: action({
        available: false,
        reason: notActiveReason,
        path: "/api/v1/operations/automation/task-definitions/created-task/run-once",
        requiresConfirmation: false,
        durableOutcome:
          "a durable bounded discovery of the definition scope is admitted",
        nextAction: "activate the Draft before starting Run once",
      }),
      grantState: action({
        available: true,
        method: "GET",
        path: "/api/v1/automation/task-definitions/created-task/grant-state",
        durableOutcome: null,
        nextAction: "read the current grant state",
      }),
      grant: action({
        available: false,
        reason: notActiveReason,
        path: "/api/v1/automation/task-definitions/created-task/grant",
        requiresConfirmation: true,
        durableOutcome:
          "a persistent scoped unattended execution grant is stored",
        nextAction: "activate the Draft before granting unattended authority",
      }),
      revoke: action({
        available: false,
        reason: notActiveReason,
        path: "/api/v1/automation/task-definitions/created-task/revoke",
        durableOutcome: "the grant is revoked",
        nextAction: "activate the Draft before granting unattended authority",
      }),
      copy: action({
        method: "POST",
        path: "/api/v1/automation/task-definitions/created-task/copy",
        requiresConfirmation: false,
        durableOutcome: "a copied definition is stored inside the Draft",
        nextAction: "copy the definition inside the open successor Draft",
      }),
      draftCreate: action({
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
        requiresConfirmation: false,
        durableOutcome: "a successor Draft is stored",
        nextAction: "create or open the successor Draft",
      }),
    },
    ...overrides,
  };
}

describe("V2 Automation journey", () => {
  it("renders the Active identity, definition state and gated create entry", async () => {
    recordingFetch((call) => {
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions?sort=name&limit=20"
      ) {
        return jsonResponse(listDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "自动化" });
    const main = screen.getByRole("main");
    expect(within(main).getAllByText("自动化", { exact: true })).toHaveLength(
      1,
    );
    expect(main.querySelector(".mf-page-context")).toBeNull();
    expect(
      within(main).queryByText(/统计范围：|统计时区：|skipped files/),
    ).toBeNull();
    // The reference-style table publishes the definition's real schedule and
    // its truthful "no result yet" state.
    expect(await screen.findByText(/Nightly automation/)).toBeVisible();
    expect(screen.getByText(/每隔 3600 秒/)).toBeVisible();
    expect(screen.getByText(/尚无执行/)).toBeVisible();
    // The full-population cards come from the backend metrics document, not
    // from the rendered page rows.
    expect(await screen.findByText("自动化任务数")).toBeVisible();
    expect(screen.getByText("本月执行次数")).toBeVisible();
    expect(screen.getByText("成功率")).toBeVisible();
    expect(screen.getByText(/评估 3 次 · 已结束 3 次/)).toBeVisible();
    expect(screen.getByText("较上月")).toBeVisible();
    // No comparable previous period is published as the documented marker,
    // never as a fabricated zero.
    expect(screen.getAllByText("暂无可比数据").length).toBeGreaterThan(0);
    // The backend advertises creation for this principal.
    expect(screen.getByRole("link", { name: "新建自动化任务" })).toBeVisible();
    // The two sibling tabs are real navigation; runtime settings live in the
    // existing System Settings page instead of a third Automation tab.
    expect(screen.getByRole("button", { name: "任务列表" })).toBeVisible();
    expect(screen.getByRole("button", { name: "执行记录" })).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "全局设置" }),
    ).not.toBeInTheDocument();
  });

  it("renders an explicit unavailable card value instead of a fabricated zero", async () => {
    recordingFetch((call) => {
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions?sort=name&limit=20"
      ) {
        return jsonResponse(
          listDocument({
            metrics: metricsDocument({
              available: false,
              monthToDateAdmitted: null,
              monthToDateTerminal: null,
              successRate: null,
              nextAction: "inspect the runtime database, then refresh",
            }),
          }),
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "自动化" });
    await waitFor(() =>
      expect(screen.getAllByText("暂无统计").length).toBeGreaterThan(0),
    );
    expect(
      screen.getByText(/指标暂不可用：inspect the runtime database/),
    ).toBeVisible();
  });

  it("reaches the whole population through the server page cursor", async () => {
    recordingFetch((call) => {
      // The page read carries the submitted limit, so the next request is the
      // one the backend minted its cursor for.
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions?sort=name&limit=20"
      ) {
        return jsonResponse(
          listDocument({
            items: [definitionDocument(), draftOnlyDefinitionDocument()],
            total: 3,
            truncated: true,
            next_cursor: "page-2",
          }),
        );
      }
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions?sort=name&limit=20&cursor=page-2"
      ) {
        return jsonResponse(
          listDocument({
            items: [draftOnlyDefinitionDocument({ name: "Third automation" })],
            total: 3,
            truncated: false,
            previous_cursor: "page-1",
          }),
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "自动化" });
    // The count is the full population total, not the rows on this page.
    expect(await screen.findByText(/共 3 个自动化任务/)).toBeVisible();
    expect(screen.getByText(/Created automation/)).toBeVisible();
    const next = screen.getByRole("button", { name: "下一页" });
    expect(next).toBeEnabled();
    await userEvent.setup().click(next);
    // The second page is a real server read of the remaining row.
    await screen.findByText("Third automation");
    // The second page replaces the first: the operator never sees a merge of
    // two different pages.
    expect(screen.queryByText(/Nightly automation/)).toBeNull();
  });

  it("renders no create entry when the backend withholds the action", async () => {
    const page = listDocument();
    (page["actions"] as Json)["create"] = action({
      available: false,
      method: "POST",
      path: "/api/v1/automation/task-definitions",
      requiresConfirmation: false,
      reason:
        "the connected API principal cannot create Automation Task Definitions",
      durableOutcome: "the bounded definition is stored inside the Draft",
      nextAction: "start or open a successor Draft, then create",
    });
    recordingFetch((call) => {
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions?sort=name&limit=20"
      ) {
        return jsonResponse(page);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "自动化" });
    await screen.findByText("自动化任务数");
    expect(screen.queryByRole("link", { name: "新建自动化任务" })).toBeNull();
  });

  it("renders the definition name as plain text and keeps the supported row actions", async () => {
    recordingFetch((call) => {
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions?sort=name&limit=20"
      ) {
        return jsonResponse(listDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    const row = await screen.findByRole("row", {
      name: /Nightly automation/,
    });
    expect(within(row).getByText("Nightly automation")).toBeVisible();
    expect(
      within(row).queryByRole("button", { name: "Nightly automation" }),
    ).toBeNull();
    expect(within(row).queryByRole("button", { name: "打开" })).toBeNull();
    expect(within(row).getByRole("button", { name: "编辑" })).toBeVisible();
    expect(within(row).getByRole("button", { name: "运行一次" })).toBeVisible();
  });

  it.each([
    "/ui-v2/operations/automation/definition/auto-task?returnTab=definitions",
    "/ui-v2/operations/automation/editor/auto-task?returnTab=definitions",
  ])(
    "answers the retired Automation address %s with the ordinary not-found page",
    async (path) => {
      const { calls } = recordingFetch(() => undefined);
      authStore.setToken(TOKEN);
      renderApp(path);

      expect(
        await screen.findByRole("heading", { name: "Route not found" }),
      ).toBeVisible();
      expect(
        screen.queryByRole("heading", { name: /Automation definition/ }),
      ).toBeNull();
      expect(screen.queryByText("Back to the definition")).toBeNull();
      expect(calls).toEqual([]);
    },
  );

  it("returns from occurrence history to the definition-filtered execution records", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions/auto-task/occurrences?limit=20"
      ) {
        return jsonResponse(occurrencesDocument());
      }
      if (call.url.startsWith("/api/v1/operations/automation/records?")) {
        return jsonResponse(recordsDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations/automation/occurrences/auto-task",
    );

    await screen.findByRole("heading", { name: "Automation occurrences" });
    await user.click(
      screen.getByRole("link", { name: "Back to execution records" }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/operations/automation"),
    );
    expect(router.state.location.search).toMatchObject({
      tab: "records",
      rdefinition: "auto-task",
    });
    await screen.findByRole("region", { name: "自动化执行记录" });
    expect(
      calls.some(
        (call) =>
          call.method === "GET" &&
          call.url.startsWith("/api/v1/operations/automation/records?") &&
          call.url.includes("definition=auto-task"),
      ),
    ).toBe(true);
  });

  it("returns from a failed occurrence read to the same legal records route", async () => {
    const user = userEvent.setup();
    recordingFetch((call) => {
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions/auto-task/occurrences?limit=20"
      ) {
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      if (call.url.startsWith("/api/v1/operations/automation/records?")) {
        return jsonResponse(recordsDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp(
      "/ui-v2/operations/automation/occurrences/auto-task",
    );

    await screen.findByRole("heading", { name: "Operations unavailable" });
    await user.click(
      screen.getByRole("link", { name: "Back to execution records" }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/operations/automation"),
    );
    expect(router.state.location.search).toMatchObject({
      tab: "records",
      rdefinition: "auto-task",
    });
  });

  it("opens the same create dialog from the legacy create deep link", async () => {
    const user = userEvent.setup();
    const formAuthority = {
      active: {
        revisionId: ACTIVE_REVISION,
        version: 3,
        revisionSequence: 2,
        status: "active",
        digest: "a".repeat(64),
      },
      fields: [
        "id",
        "name",
        "enabled",
        "resourceLibraryId",
        "mode",
        "itemLimit",
        "intervalSeconds",
        "cron",
        "timezone",
      ],
      defaults: {},
      resourceLibraries: [
        {
          id: "source",
          name: "Source",
          enabled: true,
          storageId: "source-storage",
          storagePath: "Media",
        },
      ],
      enums: {
        modes: ["automatic-organization"],
        scheduleTypes: ["interval", "cron"],
      },
      limits: {
        id: 64,
        name: 120,
        sourceScope: 1024,
        timezone: 64,
        itemLimit: { minimum: 1, maximum: 10000 },
        intervalSeconds: {
          minimum: 0,
          exclusiveMinimum: true,
          maximum: 31536000,
        },
      },
      actions: {
        create: true,
        edit: true,
        copy: true,
        toggle: true,
        remove: true,
      },
    };
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "automation-operator" });
      }
      if (
        call.url ===
          "/api/v1/operations/automation/task-definitions?sort=name&limit=20" &&
        call.method === "GET"
      ) {
        return jsonResponse(listDocument());
      }
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(formAuthority);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations/automation/new");

    // The legacy address no longer renders a second multi-step Draft flow:
    // the ordinary list stays as the background and the same create card is
    // the only form.
    await screen.findByRole("heading", { name: "新建自动化任务" });
    await screen.findByLabelText(/任务名称/);
    expect(screen.getByRole("heading", { name: "自动化" })).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Create Automation definition" }),
    ).toBeNull();
    expect(screen.queryByText("Start successor Draft")).toBeNull();
    expect(screen.queryByLabelText("Definition ID")).toBeNull();
    expect(screen.queryByLabelText("Enabled")).toBeNull();

    // Opening and cancelling publishes nothing.
    await user.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/operations/automation"),
    );
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(0);
  });

  it("PATCH-20261107-1 removes the standing refresh entry without skipping the create reads", async () => {
    const user = userEvent.setup();
    const formAuthority = {
      active: {
        revisionId: ACTIVE_REVISION,
        version: 3,
        revisionSequence: 2,
        status: "active",
        digest: "a".repeat(64),
      },
      fields: [
        "id",
        "name",
        "enabled",
        "resourceLibraryId",
        "mode",
        "itemLimit",
        "intervalSeconds",
        "cron",
        "timezone",
      ],
      defaults: {},
      resourceLibraries: [
        {
          id: "source",
          name: "Source",
          enabled: true,
          storageId: "source-storage",
          storagePath: "Media",
        },
      ],
      enums: {
        modes: ["automatic-organization"],
        scheduleTypes: ["interval", "cron"],
      },
      limits: {
        id: 64,
        name: 120,
        sourceScope: 1024,
        timezone: 64,
        itemLimit: { minimum: 1, maximum: 10000 },
        intervalSeconds: {
          minimum: 0,
          exclusiveMinimum: true,
          maximum: 31536000,
        },
      },
      actions: {
        create: true,
        edit: true,
        copy: true,
        toggle: true,
        remove: true,
      },
    };
    const { calls } = recordingFetch((call) => {
      if (call.url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "automation-operator" });
      }
      if (
        call.url ===
          "/api/v1/operations/automation/task-definitions?sort=name&limit=20" &&
        call.method === "GET"
      ) {
        return jsonResponse(listDocument());
      }
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(formAuthority);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "自动化" });
    await screen.findByText(/Nightly automation/);
    const main = screen.getByRole("main");
    // The standing header refresh entry is gone from the workspace.
    expect(
      within(main).queryByRole("button", { name: /^(刷新|刷新中…)$/ }),
    ).toBeNull();

    await user.click(screen.getByRole("link", { name: "新建自动化任务" }));
    await screen.findByRole("heading", { name: "新建自动化任务" });
    // Opening the create card cannot add, disable or relabel a refresh entry
    // that no longer exists.
    expect(
      screen.queryByRole("button", { name: /^(刷新|刷新中…)$/ }),
    ).toBeNull();
    // The necessary list and authority reads still happened.
    expect(
      calls.some(
        (call) =>
          call.method === "GET" &&
          call.url ===
            "/api/v1/operations/automation/task-definitions?sort=name&limit=20",
      ),
    ).toBe(true);
    expect(
      calls.some(
        (call) =>
          call.method === "GET" &&
          call.url === "/api/v1/operations/automation/definitions",
      ),
    ).toBe(true);
    // Opening and rendering the card submits no business command.
    expect(calls.filter((call) => call.method !== "GET")).toHaveLength(0);
  });
});
