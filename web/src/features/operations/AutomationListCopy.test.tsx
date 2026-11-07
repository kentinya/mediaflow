/**
 * Browser-level proof for the Automation list Copy command.
 *
 * These tests drive the real route/component/API-client path: the list row
 * next to 编辑 submits the existing focused Copy command for the exact saved
 * source and observed Active fence, stays on the list, proves one copy per
 * click, and reconciles an unknown response from durable evidence without
 * allocating a second copy. The backend remains the only authority; the list
 * never infers permission or a new baseline.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { authStore } from "../../shared/api/auth-store";
import { principalIdStorageSegment } from "../../shared/auth/principal-identity";
import { renderApp } from "../../../tests/utils";

const TOKEN = "automation-list-copy-token";
const PRINCIPAL = "list-operator";
const ACTIVE_REVISION = "revision-active-1";
const DIGEST = "a".repeat(64);
const DEFINITION_ID = "auto-task";
const COPY_ID = "auto-task-copy";
const LEGACY_PREFIX = "mediaflow.operations.automation-copy-intent:";
const LIST_PREFIX = "mediaflow.operations.automation-copy-intents:";
/** The Active sequence a legacy Copy intent was submitted against. */
const AS_ACTIVE_VERSION = 2;

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  readonly url: string;
  readonly method: string;
  readonly body: Record<string, unknown> | null;
}

function recordingFetch(
  respond: (call: Call) => Response | Promise<Response> | undefined,
) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        url: String(input),
        method: init?.method ?? "GET",
        body:
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      };
      calls.push(call);
      const response = await respond(call);
      return response ?? jsonResponse({ error: { code: "not_found" } }, 404);
    }),
  );
  return calls;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function action(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: null,
    requiresConfirmation: false,
    sideEffects: "none",
    durableOutcome: null,
    nextAction: null,
    ...overrides,
  };
}

function definitionDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const id = typeof overrides.id === "string" ? overrides.id : DEFINITION_ID;
  const activeOverride = overrides.activeConfiguration;
  const activeRevisionId =
    activeOverride !== null &&
    typeof activeOverride === "object" &&
    typeof (activeOverride as Record<string, unknown>).revisionId === "string"
      ? ((activeOverride as Record<string, unknown>).revisionId as string)
      : ACTIVE_REVISION;
  return {
    id,
    name: "Nightly automation",
    enabled: false,
    resourceLibraryId: "source",
    mode: "automatic-organization",
    intervalSeconds: 3600,
    itemLimit: 12,
    sourceScope: null,
    definitionState: "active",
    occurrenceState: {
      enabled: false,
      nextRunAt: null,
      lastOccurrenceAt: null,
      lastJobId: null,
      lastOutcome: null,
      lastReason: null,
      nextAction: null,
      lastTaskId: null,
      lastFailureCategory: null,
    },
    unattendedExecutionGrant: {
      status: "none",
      active: false,
      grantId: null,
      definitionId: id,
      definitionChangedSinceGrant: false,
      nextAction: "review the exact definition bounds and explicitly grant",
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
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    actions: {
      detail: action({
        method: "GET",
        path: `/api/v1/operations/automation/task-definitions/${id}`,
      }),
      occurrences: action({
        method: "GET",
        path: `/api/v1/operations/automation/task-definitions/${id}/occurrences`,
      }),
      runOnce: action({
        method: "POST",
        path: `/api/v1/operations/automation/task-definitions/${id}/run-once`,
      }),
      grantState: action({
        method: "GET",
        path: `/api/v1/automation/task-definitions/${id}/grant-state`,
      }),
      grant: action({
        path: `/api/v1/automation/task-definitions/${id}/grant`,
        requiresConfirmation: true,
      }),
      revoke: action({
        path: `/api/v1/automation/task-definitions/${id}/revoke`,
      }),
      copy: action({
        method: "POST",
        path: `/api/v1/automation/task-definitions/${id}/copy`,
      }),
      draftCreate: action({
        path: `/api/v1/configuration/revisions/${activeRevisionId}/successor`,
      }),
    },
    ...overrides,
  };
}

function metricsDocument(): Record<string, unknown> {
  return {
    available: false,
    scope: "full_authorized_population",
    basis: "each original admitted run counted once",
    timezone: "UTC",
    cronTimezoneNote: "Cron definition timezones stay separate",
    evaluatedAt: "2026-03-15T20:00:00+00:00",
    monthToDateAdmitted: null,
    previousPeriodAdmitted: null,
    comparisonAvailable: false,
    denominatorStatement: "no comparable data",
    successRate: null,
    completedCount: null,
    evaluatedCount: null,
    monthToDateTerminal: null,
    monthToDateActive: null,
    monthToDateUnavailable: null,
    monthToDateNoWork: null,
    monthToDatePartial: null,
    monthToDateFailed: null,
    monthToDateCancelled: null,
    monthToDateUncertain: null,
    inventory: {
      published: 1,
      enabled: 0,
      draftOnly: 0,
      total: 1,
      basis: "exact_current_active_and_open_drafts",
      scope: "full_authorized_population",
    },
    noWorkStatement: "no work is not organizing success",
    nextAction: "publish an automation task",
    windows: null,
  };
}

function listDocument(
  items: Array<Record<string, unknown>> = [definitionDocument()],
): Record<string, unknown> {
  return {
    activeConfiguration: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
    },
    items,
    total: items.length,
    truncated: false,
    metrics: metricsDocument(),
    inventoryCounts: {
      published: items.length,
      enabled: 0,
      draftOnly: 0,
      total: items.length,
      basis: "exact_current_active_and_open_drafts",
      scope: "full_authorized_population",
    },
    latestAdmittedRuns: {},
    query: {
      q: null,
      enabled: null,
      library: null,
      state: null,
      sort: "name",
      direction: "asc",
      limit: 20,
      scope: "full_authorized_population",
    },
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
      }),
      createDraft: action({
        path: `/api/v1/configuration/revisions/${ACTIVE_REVISION}/successor`,
      }),
    },
  };
}

function formAuthority(overrides: Record<string, unknown> = {}) {
  return {
    active: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
      digest: DIGEST,
    },
    sideEffects: "none",
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
      intervalSeconds: { minimum: 1, maximum: 31536000 },
    },
    actions: {
      create: true,
      edit: true,
      copy: true,
      toggle: true,
      remove: true,
      enable: true,
      createEnabled: true,
    },
    actionReasons: { enable: null, createEnabled: null },
    ...overrides,
  };
}

function copyPublication(
  copy: Record<string, unknown> = definitionDocument({
    id: COPY_ID,
    name: "Nightly automation copy",
  }),
) {
  return {
    action: "copy",
    definition: copy,
    removed: null,
    active: {
      revisionId: "revision-active-2",
      version: 4,
      revisionSequence: 3,
      status: "active",
      digest: "b".repeat(64),
    },
    sideEffects: "configuration_only",
  };
}

function copyIntentDocument(overrides: Record<string, unknown> = {}) {
  return {
    definitionId: DEFINITION_ID,
    sourcePresent: true,
    committed: false,
    committedDefinitionId: null,
    lastObserved: null,
    observedCommands: 0,
    evidenceComplete: true,
    active: {
      revisionId: ACTIVE_REVISION,
      version: 3,
      revisionSequence: 2,
      status: "active",
      digest: DIGEST,
    },
    sideEffects: "none",
    nextAction: "no pending copy command was observed for this definition",
    ...overrides,
  };
}

function principalResponse(): Response {
  return jsonResponse({ principal_id: PRINCIPAL });
}

function baseResponder(list: Record<string, unknown> = listDocument()) {
  return (call: Call): Response | undefined => {
    if (call.url === "/api/v1/auth/principal") return principalResponse();
    if (
      call.url === "/api/v1/operations/automation/definitions" &&
      call.method === "GET"
    ) {
      return jsonResponse(formAuthority());
    }
    if (call.url.startsWith("/api/v1/operations/automation/task-definitions?"))
      return jsonResponse(list);
    return undefined;
  };
}

async function renderConnected() {
  authStore.setToken(TOKEN);
  const { router } = renderApp("/ui-v2/operations/automation");
  const table = await screen.findByRole("table", { name: "自动化任务" });
  return { table: within(table), router };
}

function row(table: ReturnType<typeof within>) {
  // A created copy's row also starts with the source name; the source row is
  // the one without the copy suffix.
  return table.getByRole("row", {
    name: /^Nightly automation(?! copy)/,
  });
}

function copyEntry(table: ReturnType<typeof within>) {
  return within(row(table)).getByRole("button", { name: "复制" });
}

afterEach(() => {
  cleanup();
  authStore.clearToken();
  authStore.clearIntendedPath();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Automation list Copy", () => {
  it("submits one copy for the exact saved source and observed Active, stays on the list and offers the copy's edit entry", async () => {
    const user = userEvent.setup();
    const pending = deferred<Response>();
    let items = [definitionDocument()];
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/copy")) {
        items = [
          definitionDocument(),
          definitionDocument({ id: COPY_ID, name: "Nightly automation copy" }),
        ];
        return pending.promise;
      }
      if (
        call.url.startsWith("/api/v1/operations/automation/task-definitions?")
      )
        return jsonResponse(listDocument(items));
      return baseResponder()(call);
    });
    const { table, router } = await renderConnected();
    const entry = copyEntry(table);
    await user.click(entry);

    expect(router.state.location.pathname).toBe("/operations/automation");
    expect(entry).toHaveTextContent("复制中…");
    expect(entry).toHaveAttribute("aria-disabled", "true");
    // A second click while the first submission is in flight is ignored.
    await user.click(entry);
    const posts = calls.filter(
      (call) => call.method === "POST" && call.url.endsWith("/copy"),
    );
    expect(posts).toHaveLength(1);
    expect(posts[0]?.url).toBe(
      `/api/v1/operations/automation/definitions/${DEFINITION_ID}/copy`,
    );
    expect(posts[0]?.body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedVersion: 2,
      expectedDigest: DIGEST,
    });

    pending.resolve(jsonResponse(copyPublication()));
    await waitFor(() => expect(entry).toHaveTextContent("复制"));
    expect(within(row(table)).getByText(/已复制为停用副本/)).toBeVisible();
    expect(
      within(row(table)).getByText(/副本「Nightly automation copy」/),
    ).toBeVisible();
    // The list refreshed its real rows and marked the new copy.
    const copyRow = table
      .getByRole("button", { name: "Nightly automation copy" })
      .closest("tr") as HTMLElement;
    expect(within(copyRow).getByText("刚刚复制")).toBeVisible();
    // The copy is a new disabled definition: its edit entry is the row button.
    await user.click(within(copyRow).getByRole("button", { name: "编辑" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        "/operations/automation/lifecycle/auto-task-copy",
      ),
    );
    // The source stayed on its own list context; nothing navigated on copy.
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/copy"),
      ),
    ).toHaveLength(1);
  });

  it("replaces a previous success with the new unknown intent and reconciles the second copy", async () => {
    const user = userEvent.setup();
    const secondCopyId = "auto-task-copy-2";
    let items = [definitionDocument()];
    let posts = 0;
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/copy")) {
        posts += 1;
        if (posts === 1) {
          items = [
            definitionDocument(),
            definitionDocument({
              id: COPY_ID,
              name: "Nightly automation copy",
            }),
          ];
          return jsonResponse(copyPublication());
        }
        // The second command committed, but its response was lost.
        items = [
          ...items,
          definitionDocument({
            id: secondCopyId,
            name: "Nightly automation copy 2",
          }),
        ];
        throw new Error("network dropped");
      }
      if (
        call.url.includes(
          `/automation/definitions/${DEFINITION_ID}/copy-intent`,
        )
      ) {
        return jsonResponse(
          copyIntentDocument({
            committed: true,
            committedDefinitionId: secondCopyId,
            observedCommands: 1,
            lastObserved: {
              auditId: "audit-2",
              action: "copy",
              occurredAt: "2026-01-01T00:00:01+00:00",
              candidateId: secondCopyId,
              published: true,
            },
          }),
        );
      }
      if (
        call.url.startsWith("/api/v1/operations/automation/task-definitions?")
      )
        return jsonResponse(listDocument(items));
      return baseResponder()(call);
    });
    const { table, router } = await renderConnected();
    await user.click(copyEntry(table));
    expect(
      await within(row(table)).findByText(/已复制为停用副本/),
    ).toBeVisible();
    await waitFor(() =>
      expect(copyEntry(table)).toHaveAttribute("aria-disabled", "false"),
    );

    await user.click(copyEntry(table));
    expect(await within(row(table)).findByText(/复制结果待核对/)).toBeVisible();
    // The first success must not stand in for this attempt's unknown outcome.
    expect(within(row(table)).queryByText(/已复制为停用副本/)).toBeNull();
    expect(
      within(row(table)).queryByRole("button", { name: "编辑副本" }),
    ).toBeNull();
    await user.click(copyEntry(table));
    const postsBeforeCheck = calls.filter(
      (call) => call.method === "POST" && call.url.endsWith("/copy"),
    );
    expect(postsBeforeCheck).toHaveLength(2);
    expect(postsBeforeCheck[1]?.body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedVersion: 2,
      expectedDigest: DIGEST,
    });

    await user.click(
      within(row(table)).getByRole("button", { name: "核对复制结果" }),
    );
    expect(
      await within(row(table)).findByText(/auto-task-copy-2/),
    ).toBeVisible();
    expect(
      within(row(table)).getByText(/已从持久证据确认本次复制/),
    ).toBeVisible();
    await user.click(
      within(row(table)).getByRole("button", { name: "编辑副本" }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        `/operations/automation/lifecycle/${secondCopyId}`,
      ),
    );
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/copy"),
      ),
    ).toHaveLength(2);
  });

  it("does not show the previous success when a later explicit copy is refused", async () => {
    const user = userEvent.setup();
    let items = [definitionDocument()];
    let posts = 0;
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/copy")) {
        posts += 1;
        if (posts === 1) {
          items = [
            definitionDocument(),
            definitionDocument({
              id: COPY_ID,
              name: "Nightly automation copy",
            }),
          ];
          return jsonResponse(copyPublication());
        }
        return jsonResponse(
          { error: { code: "configuration_version_conflict" } },
          409,
        );
      }
      if (
        call.url.startsWith("/api/v1/operations/automation/task-definitions?")
      )
        return jsonResponse(listDocument(items));
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    await user.click(copyEntry(table));
    expect(
      await within(row(table)).findByText(/已复制为停用副本/),
    ).toBeVisible();
    await waitFor(() =>
      expect(copyEntry(table)).toHaveAttribute("aria-disabled", "false"),
    );

    await user.click(copyEntry(table));
    expect(await within(row(table)).findByText("未能复制")).toBeVisible();
    // The refused attempt must not inherit the first copy's success card.
    expect(within(row(table)).queryByText(/已复制为停用副本/)).toBeNull();
    expect(
      within(row(table)).queryByRole("button", { name: "编辑副本" }),
    ).toBeNull();
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/copy"),
      ),
    ).toHaveLength(2);
    expect(
      window.sessionStorage.getItem(
        `${LIST_PREFIX}${principalIdStorageSegment(PRINCIPAL)}:${DEFINITION_ID}`,
      ),
    ).toBeNull();
  });

  it("reports an outdated Active and re-reads the list without replaying the copy", async () => {
    const user = userEvent.setup();
    let listReads = 0;
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/copy")) {
        return jsonResponse(
          { error: { code: "configuration_version_conflict" } },
          409,
        );
      }
      if (
        call.url.startsWith("/api/v1/operations/automation/task-definitions?")
      ) {
        listReads += 1;
        return jsonResponse(listDocument());
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    await user.click(copyEntry(table));

    expect(await within(row(table)).findByText("未能复制")).toBeVisible();
    expect(
      within(row(table)).getByText(
        "当前配置已被其他操作更新，本次复制未生效。",
      ),
    ).toBeVisible();
    expect(
      within(row(table)).getByText(
        "列表会重新读取当前配置；请确认最新保存内容后再决定是否复制。不会自动重试。",
      ),
    ).toBeVisible();
    expect(listReads).toBeGreaterThan(1);
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/copy"),
      ),
    ).toHaveLength(1);
    // A proved refusal leaves no pending intent and re-offers the command.
    expect(
      window.sessionStorage.getItem(
        `${LIST_PREFIX}${principalIdStorageSegment(PRINCIPAL)}:${DEFINITION_ID}`,
      ),
    ).toBeNull();
    await waitFor(() =>
      expect(copyEntry(table)).toHaveAttribute("aria-disabled", "false"),
    );
  });

  it("updates the list and its Copy authority after a conflict so the next explicit copy uses the current version", async () => {
    const user = userEvent.setup();
    const nextActive = {
      revisionId: "revision-active-2",
      version: 4,
      revisionSequence: 3,
      status: "active",
    };
    const nextDigest = "b".repeat(64);
    let current: "old" | "new" = "old";
    let posts = 0;
    const oldItem = definitionDocument();
    const newItem = definitionDocument({
      activeConfiguration: nextActive,
      itemLimit: 9,
    });
    const newTask = definitionDocument({
      id: "another-task",
      name: "Another automation",
    });
    const calls = recordingFetch((call) => {
      if (
        call.method === "GET" &&
        call.url === "/api/v1/operations/automation/definitions"
      ) {
        return jsonResponse(
          formAuthority({
            active:
              current === "new"
                ? { ...nextActive, digest: nextDigest }
                : {
                    revisionId: ACTIVE_REVISION,
                    version: 3,
                    revisionSequence: 2,
                    status: "active",
                    digest: DIGEST,
                  },
          }),
        );
      }
      if (call.method === "POST" && call.url.endsWith("/copy")) {
        posts += 1;
        if (posts === 1) {
          // The other tab published a new Active after this list was read.
          current = "new";
          return jsonResponse(
            { error: { code: "configuration_version_conflict" } },
            409,
          );
        }
        return jsonResponse(copyPublication());
      }
      if (
        call.url.startsWith("/api/v1/operations/automation/task-definitions?")
      ) {
        return jsonResponse(
          listDocument(current === "new" ? [newItem, newTask] : [oldItem]),
        );
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    await user.click(copyEntry(table));
    expect(await screen.findByText("未能复制")).toBeVisible();
    // The refreshed list shows the concurrent definition, not only the
    // rejection text.
    expect(
      await screen.findByRole("button", { name: "Another automation" }),
    ).toBeVisible();
    const refreshedTable = within(
      screen.getByRole("table", { name: "自动化任务" }),
    );
    // The refused Copy's own read-back updates both the rows and the
    // authority the next Copy submits against, so the removed header refresh
    // is not needed for the next explicit attempt (its request body below
    // proves the current revision is used).
    expect(within(row(refreshedTable)).getByText("9")).toBeVisible();
    await user.click(
      within(row(refreshedTable)).getByRole("button", { name: "复制" }),
    );
    expect(
      await within(row(refreshedTable)).findByText(/已复制为停用副本/),
    ).toBeVisible();
    const postCalls = calls.filter(
      (call) => call.method === "POST" && call.url.endsWith("/copy"),
    );
    expect(postCalls).toHaveLength(2);
    expect(postCalls[0]?.body).toMatchObject({
      expectedRevisionId: ACTIVE_REVISION,
      expectedVersion: 2,
      expectedDigest: DIGEST,
    });
    expect(postCalls[1]?.body).toMatchObject({
      expectedRevisionId: nextActive.revisionId,
      expectedVersion: nextActive.revisionSequence,
      expectedDigest: nextDigest,
    });
  });

  it("refuses to pair a row with a newer authority the row never displayed, then submits only after both reads agree", async () => {
    const user = userEvent.setup();
    const nextActive = {
      revisionId: "revision-active-2",
      version: 4,
      revisionSequence: 3,
      status: "active",
    };
    const nextDigest = "b".repeat(64);
    const authorityRead = deferred<Response>();
    let authorityReads = 0;
    let current: "old" | "new" = "old";
    let posts = 0;
    const calls = recordingFetch((call) => {
      if (
        call.method === "GET" &&
        call.url === "/api/v1/operations/automation/definitions"
      ) {
        authorityReads += 1;
        return authorityReads === 1
          ? authorityRead.promise
          : jsonResponse(
              formAuthority({
                active: { ...nextActive, digest: nextDigest },
              }),
            );
      }
      if (call.method === "POST" && call.url.endsWith("/copy")) {
        posts += 1;
        return jsonResponse(copyPublication());
      }
      if (
        call.url.startsWith("/api/v1/operations/automation/task-definitions?")
      ) {
        return jsonResponse(
          listDocument(
            current === "new"
              ? [
                  definitionDocument({
                    activeConfiguration: nextActive,
                    itemLimit: 9,
                  }),
                ]
              : [definitionDocument({ itemLimit: 5 })],
          ),
        );
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    expect(within(row(table)).getByText("5")).toBeVisible();
    // The authority read is still in flight; Copy is not offered yet.
    expect(
      within(row(table)).queryByRole("button", { name: "复制" }),
    ).toBeNull();
    authorityRead.resolve(
      jsonResponse(
        formAuthority({ active: { ...nextActive, digest: nextDigest } }),
      ),
    );
    const entry = await within(row(table)).findByRole("button", {
      name: "复制",
    });
    // Another tab saved a newer configuration after this list row was read.
    current = "new";
    await user.click(entry);
    expect(await screen.findByText("未能复制")).toBeVisible();
    expect(
      screen.getByText(/列表显示的任务配置与当前保存配置不一致/),
    ).toBeVisible();
    expect(posts).toBe(0);
    // The read-only recovery shows the actual saved values before any retry.
    expect(await screen.findByText("9")).toBeVisible();
    const refreshedTable = within(
      screen.getByRole("table", { name: "自动化任务" }),
    );
    await user.click(
      within(row(refreshedTable)).getByRole("button", { name: "复制" }),
    );
    expect(await screen.findByText(/已复制为停用副本/)).toBeVisible();
    const postCalls = calls.filter(
      (call) => call.method === "POST" && call.url.endsWith("/copy"),
    );
    expect(postCalls).toHaveLength(1);
    expect(postCalls[0]?.body).toMatchObject({
      expectedRevisionId: nextActive.revisionId,
      expectedVersion: nextActive.revisionSequence,
      expectedDigest: nextDigest,
    });
  });

  it("keeps a lost Copy response unknown and reconciles the exact intent before offering a second copy", async () => {
    const user = userEvent.setup();
    let items = [definitionDocument()];
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/copy")) {
        // The backend committed but the response was lost.
        items = [
          definitionDocument(),
          definitionDocument({ id: COPY_ID, name: "Nightly automation copy" }),
        ];
        throw new Error("network dropped");
      }
      if (
        call.url.includes(
          `/automation/definitions/${DEFINITION_ID}/copy-intent`,
        )
      ) {
        return jsonResponse(
          copyIntentDocument({
            committed: true,
            committedDefinitionId: COPY_ID,
            observedCommands: 1,
            lastObserved: {
              auditId: "audit-1",
              action: "copy",
              occurredAt: "2026-01-01T00:00:00+00:00",
              candidateId: COPY_ID,
              published: true,
            },
          }),
        );
      }
      if (
        call.url.startsWith("/api/v1/operations/automation/task-definitions?")
      )
        return jsonResponse(listDocument(items));
      return baseResponder()(call);
    });
    const { table, router } = await renderConnected();
    await user.click(copyEntry(table));

    expect(await within(row(table)).findByText(/复制结果待核对/)).toBeVisible();
    // The retained intent blocks a second submission.
    expect(copyEntry(table)).toHaveAttribute("aria-disabled", "true");
    expect(
      window.sessionStorage.getItem(
        `${LIST_PREFIX}${principalIdStorageSegment(PRINCIPAL)}:${DEFINITION_ID}`,
      ),
    ).not.toBeNull();

    await user.click(
      within(row(table)).getByRole("button", { name: "核对复制结果" }),
    );
    expect(
      await within(row(table)).findByText(/已复制为停用副本/),
    ).toBeVisible();
    expect(
      within(row(table)).getByText(/已从持久证据确认本次复制/),
    ).toBeVisible();
    const intentRead = calls.find((call) =>
      call.url.includes(`/automation/definitions/${DEFINITION_ID}/copy-intent`),
    );
    expect(intentRead?.url).toContain(
      `expectedRevisionId=${encodeURIComponent(ACTIVE_REVISION)}`,
    );
    expect(intentRead?.url).toContain(
      `expectedDigest=${encodeURIComponent(DIGEST)}`,
    );
    // No second copy was submitted and the retained intent is cleared.
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/copy"),
      ),
    ).toHaveLength(1);
    expect(
      window.sessionStorage.getItem(
        `${LIST_PREFIX}${principalIdStorageSegment(PRINCIPAL)}:${DEFINITION_ID}`,
      ),
    ).toBeNull();
    expect(router.state.location.pathname).toBe("/operations/automation");
    expect(
      table.getByRole("button", { name: "Nightly automation copy" }),
    ).toBeVisible();
  });

  it("keeps an incomplete durable Copy evidence read unknown and never releases the block", async () => {
    const user = userEvent.setup();
    window.sessionStorage.setItem(
      `${LEGACY_PREFIX}${principalIdStorageSegment(PRINCIPAL)}`,
      JSON.stringify({
        sourceId: DEFINITION_ID,
        authority: {
          revisionId: ACTIVE_REVISION,
          version: AS_ACTIVE_VERSION,
          digest: DIGEST,
        },
      }),
    );
    recordingFetch((call) => {
      if (
        call.url.includes(
          `/automation/definitions/${DEFINITION_ID}/copy-intent`,
        )
      ) {
        // Zero observed commands, but the read could not be completed: absence
        // is not evidence of non-publication.
        return jsonResponse(
          copyIntentDocument({
            evidenceComplete: false,
            nextAction:
              "the submitted copy outcome is unknown: the durable command evidence could not be read completely",
          }),
        );
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();

    // The retired edit card's principal-scoped entry stays readable.
    expect(await within(row(table)).findByText(/复制结果待核对/)).toBeVisible();
    expect(copyEntry(table)).toHaveAttribute("aria-disabled", "true");
    await user.click(
      within(row(table)).getByRole("button", { name: "核对复制结果" }),
    );
    expect(await within(row(table)).findByText(/无法完整读取/)).toBeVisible();
    expect(within(row(table)).queryByText(/已核对：未发布副本/)).toBeNull();
    expect(copyEntry(table)).toHaveAttribute("aria-disabled", "true");
    expect(
      window.sessionStorage.getItem(
        `${LEGACY_PREFIX}${principalIdStorageSegment(PRINCIPAL)}`,
      ),
    ).not.toBeNull();
  });

  it("releases the block only for a complete, command-free Copy evidence read", async () => {
    const user = userEvent.setup();
    window.sessionStorage.setItem(
      `${LEGACY_PREFIX}${principalIdStorageSegment(PRINCIPAL)}`,
      JSON.stringify({
        sourceId: DEFINITION_ID,
        authority: {
          revisionId: ACTIVE_REVISION,
          version: AS_ACTIVE_VERSION,
          digest: DIGEST,
        },
      }),
    );
    const calls = recordingFetch((call) => {
      if (
        call.url.includes(
          `/automation/definitions/${DEFINITION_ID}/copy-intent`,
        )
      ) {
        return jsonResponse(copyIntentDocument());
      }
      return baseResponder()(call);
    });
    const { table } = await renderConnected();
    expect(await within(row(table)).findByText(/复制结果待核对/)).toBeVisible();
    await user.click(
      within(row(table)).getByRole("button", { name: "核对复制结果" }),
    );
    expect(
      await within(row(table)).findByText("已核对：未发布副本"),
    ).toBeVisible();
    await waitFor(() =>
      expect(copyEntry(table)).toHaveAttribute("aria-disabled", "false"),
    );
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/copy"),
      ),
    ).toHaveLength(0);
    expect(
      window.sessionStorage.getItem(
        `${LEGACY_PREFIX}${principalIdStorageSegment(PRINCIPAL)}`,
      ),
    ).toBeNull();
  });

  it("keeps a copied definition reachable when the current page does not show it", async () => {
    const user = userEvent.setup();
    const calls = recordingFetch((call) => {
      if (call.method === "POST" && call.url.endsWith("/copy")) {
        return jsonResponse(copyPublication());
      }
      // The refreshed page still shows only the source: the copy is outside
      // this filter/page.
      return baseResponder()(call);
    });
    const { table, router } = await renderConnected();
    await user.click(copyEntry(table));

    expect(
      await within(row(table)).findByText(/已复制为停用副本/),
    ).toBeVisible();
    expect(
      within(row(table)).getByText(
        /副本不在当前筛选或分页中；可通过“编辑副本”打开/,
      ),
    ).toBeVisible();
    const editCopy = within(row(table)).getByRole("button", {
      name: "编辑副本",
    });
    // The operator stays on the same filtered page and keeps an explicit
    // entry to the copy that is not visible here.
    expect(router.state.location.search).toEqual({});
    await user.click(editCopy);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        "/operations/automation/lifecycle/auto-task-copy",
      ),
    );
    expect(
      calls.filter(
        (call) => call.method === "POST" && call.url.endsWith("/copy"),
      ),
    ).toHaveLength(1);
  });

  it("shows no Copy entry without backend permission and explains an unreadable authority", async () => {
    const denied = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse(formAuthority({ actions: { copy: false } }));
      }
      return baseResponder()(call);
    });
    const first = await renderConnected();
    expect(
      within(row(first.table)).queryByRole("button", { name: "复制" }),
    ).toBeNull();
    cleanup();
    authStore.clearToken();
    vi.unstubAllGlobals();

    const unreadable = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/automation/definitions" &&
        call.method === "GET"
      ) {
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      return baseResponder()(call);
    });
    const second = await renderConnected();
    expect(
      await screen.findByText(
        "复制暂不可用：无法读取当前配置授权；请刷新后重试。",
      ),
    ).toBeVisible();
    expect(
      within(row(second.table)).queryByRole("button", { name: "复制" }),
    ).toBeNull();
    // Reading the list never submits a command on its own.
    expect(
      [...denied, ...unreadable].some((call) => call.method !== "GET"),
    ).toBe(false);
  });
});
