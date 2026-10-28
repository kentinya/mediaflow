import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor } from "@testing-library/react";
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
    monthToDateNoWork: 1,
    monthToDatePartial: 0,
    monthToDateFailed: 0,
    monthToDateCancelled: 0,
    monthToDateUncertain: 0,
    inventory: inventoryCountsDocument(),
    denominatorStatement:
      "terminal admitted runs in the current local month (3)",
    successRate: 2 / 3,
    completedCount: 2,
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

function draftDocument(
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
    draft: {
      revisionId: DRAFT_REVISION,
      revisionVersion: 2,
      revisionStatus: "draft",
      baseActiveRevisionId: ACTIVE_REVISION,
      updatedAt: "2026-01-01T00:00:00+00:00",
      validatedAt: null,
      validationErrors: [],
      definition: {
        id: "auto-task",
        name: "Nightly automation",
        enabled: true,
        resourceLibraryId: "source",
        mode: "automatic-organization",
        itemLimit: 12,
        sourceScope: null,
        intervalSeconds: 3600,
        cron: null,
        timezone: null,
      },
    },
    resourceLibraryOptions: [{ id: "source", name: "Source", enabled: true }],
    actions: {
      createDraft: action({
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
        requiresConfirmation: false,
        durableOutcome: "a successor Draft is stored",
        nextAction: "create the successor Draft",
      }),
      save: action({
        method: "PUT",
        path: `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/auto-task`,
        requiresConfirmation: false,
        durableOutcome: "the bounded form is stored in the Draft",
        nextAction: "save the bounded form, then validate and activate",
      }),
      validate: action({
        method: "POST",
        path: `/api/v1/configuration/revisions/${DRAFT_REVISION}/validate`,
        requiresConfirmation: false,
        durableOutcome: "the Draft is validated with zero mutation",
        nextAction: "validate the Draft",
      }),
      activate: action({
        method: "POST",
        path: "/api/v1/operations/automation/task-definitions/auto-task/activate-draft",
        requiresConfirmation: true,
        durableOutcome:
          "the exact Draft becomes the immutable Active configuration",
        nextAction: "confirm one explicit activation of the validated Draft",
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
    expect(screen.getByText("较上月")).toBeVisible();
    // No comparable previous period is published as the documented marker,
    // never as a fabricated zero.
    expect(screen.getAllByText("暂无可比数据").length).toBeGreaterThan(0);
    // The backend advertises creation for this principal.
    expect(screen.getByRole("link", { name: "新建自动化任务" })).toBeVisible();
    // The three sibling tabs are real navigation, labelled as in the
    // reference composition.
    expect(screen.getByRole("button", { name: "任务列表" })).toBeVisible();
    expect(screen.getByRole("button", { name: "执行记录" })).toBeVisible();
    expect(screen.getByRole("button", { name: "系统设置" })).toBeVisible();
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

  it("reads execution readiness without exposing independent grant controls", async () => {
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/automation/task-definitions/auto-task"
      ) {
        const value = definitionDocument();
        delete value.unattendedExecutionGrant;
        delete value.grantEligibility;
        return jsonResponse({ definition: value });
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/definition/auto-task");
    await screen.findByRole("heading", { name: /Automation definition/ });
    expect(
      screen.getByRole("heading", { name: "Execution readiness" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Edit saved definition" }),
    ).toBeVisible();
    expect(
      screen.queryByLabelText("Confirm unattended execution grant"),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Grant unattended authority" }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: "Revoke grant" })).toBeNull();
    expect(calls.every((call) => call.method === "GET")).toBe(true);
    expect(calls.some((call) => call.url.includes("grant"))).toBe(false);
  });

  it("saves the bounded Draft form and never submits a digest", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (
        call.url.endsWith(
          "/operations/automation/task-definitions/auto-task/draft",
        )
      ) {
        return jsonResponse(draftDocument());
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/auto-task`
      ) {
        return jsonResponse({ version: 3 }, 200);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/editor/auto-task");

    await screen.findByRole("heading", { name: "Edit Automation definition" });
    expect(screen.getByText(/revision-draft-1/)).toBeVisible();
    const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
    expect(nameInput.value).toBe("Nightly automation");
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed automation");
    await user.click(screen.getByRole("button", { name: "Save into Draft" }));

    await waitFor(() =>
      expect(
        calls.some(
          (item) =>
            item.url ===
              `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/auto-task` &&
            item.method === "PUT",
        ),
      ).toBe(true),
    );
    const save = calls.find((item) => item.method === "PUT");
    expect(save?.body).toMatchObject({
      expectedVersion: 2,
      object: { name: "Renamed automation", id: "auto-task" },
    });
    expect(JSON.stringify(save?.body)).not.toMatch(/digest|fingerprint/i);
  });

  it("activates the checked Draft only after explicit confirmation and without a digest", async () => {
    const user = userEvent.setup();
    const validated = draftDocument({
      draft: {
        revisionId: DRAFT_REVISION,
        revisionVersion: 3,
        revisionStatus: "validated",
        baseActiveRevisionId: ACTIVE_REVISION,
        updatedAt: "2026-01-01T00:00:00+00:00",
        validatedAt: "2026-01-01T00:10:00+00:00",
        validationErrors: [],
        definition: {
          id: "auto-task",
          name: "Nightly automation",
          enabled: true,
          resourceLibraryId: "source",
          mode: "automatic-organization",
          itemLimit: 12,
          sourceScope: null,
          intervalSeconds: 3600,
          cron: null,
          timezone: null,
        },
      },
    });
    const { calls } = recordingFetch((call) => {
      if (
        call.url.endsWith(
          "/operations/automation/task-definitions/auto-task/draft",
        )
      ) {
        return jsonResponse(validated);
      }
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions/auto-task/activate-draft"
      ) {
        return jsonResponse({
          activatedRevisionId: "revision-active-2",
          activatedVersion: 4,
          revisionSequence: 3,
          activeConfiguration: {
            revisionId: "revision-active-2",
            version: 4,
            revisionSequence: 3,
            status: "active",
          },
          definition: null,
        });
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/editor/auto-task");

    await screen.findByRole("heading", { name: "Edit Automation definition" });
    const confirm = screen.getByLabelText("Confirm checked activation");
    const activateButton = screen.getByRole("button", {
      name: "Activate checked Draft",
    });
    expect(activateButton).toBeDisabled();
    await user.click(confirm);
    await user.click(activateButton);

    await waitFor(() =>
      expect(
        calls.some(
          (item) =>
            item.url ===
              "/api/v1/operations/automation/task-definitions/auto-task/activate-draft" &&
            item.method === "POST",
        ),
      ).toBe(true),
    );
    const activation = calls.find((item) =>
      item.url.endsWith("/activate-draft"),
    );
    expect(activation?.body).toMatchObject({
      expectedRevisionId: DRAFT_REVISION,
      expectedVersion: 3,
    });
    expect(JSON.stringify(activation?.body)).not.toMatch(
      /digest|fingerprint|expectedDigest/i,
    );
  });

  it("edits every owned definition field and stores exactly one schedule form", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (
        call.url.endsWith(
          "/operations/automation/task-definitions/auto-task/draft",
        )
      ) {
        return jsonResponse(
          draftDocument({
            resourceLibraryOptions: [
              { id: "source", name: "Source", enabled: true },
              { id: "target-library", name: "Target", enabled: true },
            ],
          }),
        );
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/auto-task`
      ) {
        return jsonResponse({ version: 3 }, 200);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/editor/auto-task");

    await screen.findByRole("heading", { name: "Edit Automation definition" });
    await user.selectOptions(
      screen.getByLabelText("ResourceLibrary"),
      "target-library",
    );
    // Automatic organization is the only retained mode: the editor has no mode
    // selector, so no removed mode can ever be chosen.
    expect(screen.queryByLabelText("Run mode")).toBeNull();
    expect(document.querySelector("#automation-edit-mode")).toBeNull();
    expect(
      screen.getByTestId("automation-edit-mode-intent").textContent,
    ).toContain("automatic-organization");
    await user.selectOptions(screen.getByLabelText("Schedule type"), "cron");
    await user.clear(screen.getByLabelText("Cron expression"));
    await user.type(screen.getByLabelText("Cron expression"), "0 8 * * *");
    await user.clear(screen.getByLabelText("Timezone"));
    await user.type(screen.getByLabelText("Timezone"), "Asia/Shanghai");
    await user.click(screen.getByRole("button", { name: "Save into Draft" }));

    await waitFor(() =>
      expect(
        calls.some(
          (item) =>
            item.url ===
              `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/auto-task` &&
            item.method === "PUT",
        ),
      ).toBe(true),
    );
    const save = calls.find((item) => item.method === "PUT");
    expect(save?.body).toMatchObject({
      expectedVersion: 2,
      object: {
        id: "auto-task",
        resourceLibraryId: "target-library",
        mode: "automatic-organization",
        intervalSeconds: null,
        cron: "0 8 * * *",
        timezone: "Asia/Shanghai",
      },
    });
  });

  it("refuses an unsupported Draft mode without conversion or mutation", async () => {
    // A historical Draft may still carry a removed mode. It stays visible as
    // unsupported history, is never silently rewritten, and no Save is offered
    // until the operator explicitly confirms the correction to the retained
    // mode. There is no mode selector to choose from.
    const { calls } = recordingFetch((call) => {
      if (
        call.url.endsWith(
          "/operations/automation/task-definitions/auto-task/draft",
        )
      ) {
        return jsonResponse(
          draftDocument({
            draft: {
              revisionId: DRAFT_REVISION,
              revisionVersion: 2,
              revisionStatus: "draft",
              baseActiveRevisionId: ACTIVE_REVISION,
              updatedAt: "2026-01-01T00:00:00+00:00",
              validatedAt: null,
              validationErrors: [],
              definition: {
                id: "auto-task",
                name: "Nightly automation",
                enabled: true,
                resourceLibraryId: "source",
                mode: "scan-and-plan",
                itemLimit: 12,
                sourceScope: null,
                intervalSeconds: 3600,
                cron: null,
                timezone: null,
              },
            },
          }),
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/editor/auto-task");

    await screen.findByRole("heading", {
      name: "Automation Draft unavailable",
    });
    expect(
      screen.queryByRole("button", { name: "Save into Draft" }),
    ).toBeNull();
    expect(
      screen.queryByRole("checkbox", { name: /Publish this Draft/ }),
    ).toBeNull();
    expect(calls.some((item) => item.method !== "GET")).toBe(false);
  });

  it("reports a stale Draft save without replaying the mutation", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (
        call.url.endsWith(
          "/operations/automation/task-definitions/auto-task/draft",
        )
      ) {
        return jsonResponse(draftDocument());
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/auto-task`
      ) {
        return jsonResponse(
          { error: { code: "configuration_version_conflict" } },
          409,
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/editor/auto-task");

    await screen.findByRole("heading", { name: "Edit Automation definition" });
    const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed automation");
    await user.click(screen.getByRole("button", { name: "Save into Draft" }));

    await screen.findByText(/The Draft changed before the save was applied/);
    const saves = calls.filter((item) => item.method === "PUT");
    // The rejected save is never retried automatically.
    expect(saves).toHaveLength(1);
  });

  it("completes create and copy into reachable draft-only definitions", async () => {
    const user = userEvent.setup();
    // The create form's own inventory read shares the page read basis.
    void 0;
    const listWithDraft = listDocument({
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
    });
    const draftOnlyDetail = {
      definition: draftOnlyDefinitionDocument(),
    };
    const { calls } = recordingFetch((call) => {
      if (
        call.url ===
          "/api/v1/operations/automation/task-definitions?limit=20" &&
        call.method === "GET"
      ) {
        return jsonResponse(listWithDraft);
      }
      if (
        call.url ===
          "/api/v1/operations/automation/task-definitions/created-task" &&
        call.method === "GET"
      ) {
        return jsonResponse(draftOnlyDetail);
      }
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions/created-task/draft"
      ) {
        const createdDraft = draftDocument({
          definitionId: "created-task",
          draft: {
            revisionId: DRAFT_REVISION,
            revisionVersion: 2,
            revisionStatus: "draft",
            baseActiveRevisionId: ACTIVE_REVISION,
            updatedAt: "2026-01-01T00:00:00+00:00",
            validatedAt: null,
            validationErrors: [],
            definition: {
              id: "created-task",
              name: "Created automation",
              enabled: false,
              resourceLibraryId: "source",
              mode: "automatic-organization",
              itemLimit: 9,
              sourceScope: null,
              intervalSeconds: null,
              cron: "0 8 * * *",
              timezone: "UTC",
            },
          },
        }) as Record<string, unknown>;
        createdDraft.actions = {
          ...(createdDraft.actions as Record<string, unknown>),
          save: action({
            method: "PUT",
            path: `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/created-task`,
            requiresConfirmation: false,
            durableOutcome: "the bounded form is stored in the Draft",
            nextAction: "save the bounded form, then validate and activate",
          }),
          activate: action({
            method: "POST",
            path: "/api/v1/operations/automation/task-definitions/created-task/activate-draft",
            requiresConfirmation: true,
            durableOutcome:
              "the exact Draft becomes the immutable Active configuration",
            nextAction:
              "confirm one explicit activation of the validated Draft",
          }),
        };
        return jsonResponse(createdDraft);
      }
      if (
        call.url === "/api/v1/automation/task-definitions" &&
        call.method === "POST"
      ) {
        return jsonResponse({
          revisionId: DRAFT_REVISION,
          version: 2,
          automationTaskDefinition: {
            id: "created-task",
            name: "Created automation",
          },
        });
      }
      if (
        call.url ===
        `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/created-task`
      ) {
        return jsonResponse({ version: 3 }, 200);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/new");

    // Complete the bounded create form and submit it.
    await screen.findByRole("heading", {
      name: "Create Automation definition",
    });
    await user.type(screen.getByLabelText("Name"), "Created automation");
    await user.selectOptions(
      screen.getByLabelText("ResourceLibrary"),
      "source",
    );
    // The create form has no mode selector at all: no removed mode can exist as
    // a selectable value because no selector is rendered.
    expect(screen.queryByLabelText("Run mode")).toBeNull();
    expect(document.querySelector("#automation-mode")).toBeNull();
    expect(screen.getByTestId("automation-mode-intent").textContent).toContain(
      "automatic-organization",
    );
    await user.selectOptions(screen.getByLabelText("Schedule type"), "cron");
    await user.type(screen.getByLabelText("Cron expression"), "0 8 * * *");
    await user.type(screen.getByLabelText("Timezone"), "UTC");
    await user.click(
      screen.getByRole("button", { name: "Create definition in Draft" }),
    );

    // The operator lands on the exact created definition, which is
    // reachable, marked draft-only, and editable through its open Draft.
    await screen.findByRole("heading", {
      name: "Automation definition Created automation",
    });
    expect(screen.getAllByText(/draft-only/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Open successor Draft/)).toBeVisible();
    await user.click(
      screen.getByRole("link", { name: "Edit successor Draft" }),
    );
    await screen.findByRole("heading", { name: "Edit Automation definition" });
    const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
    expect(nameInput.value).toBe("Created automation");
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed created automation");
    await user.click(screen.getByRole("button", { name: "Save into Draft" }));
    await waitFor(() =>
      expect(
        calls.some(
          (item) =>
            item.url ===
              `/api/v1/configuration/revisions/${DRAFT_REVISION}/objects/automationTaskDefinitions/created-task` &&
            item.method === "PUT",
        ),
      ).toBe(true),
    );
  });
});
