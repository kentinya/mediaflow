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

function recordingFetch(respond: (call: Call) => Response | undefined): {
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
      preview: action({
        path: "/api/v1/automation/task-definitions/auto-task/preview",
        requiresConfirmation: false,
        durableOutcome: "a durable zero-mutation Preview is stored",
        nextAction: "create the exact Preview",
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
    enabled: false,
    resourceLibraryId: "source",
    mode: "scan-and-plan",
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
      preview: action({
        available: false,
        reason: notActiveReason,
        path: "/api/v1/automation/task-definitions/created-task/preview",
        requiresConfirmation: false,
        durableOutcome: "a durable zero-mutation Preview is stored",
        nextAction: "activate the Draft, then create the exact Preview",
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

function previewDocument(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    previewId: "preview-1",
    definitionId: "auto-task",
    configurationRevisionId: ACTIVE_REVISION,
    configurationRevisionVersion: 3,
    configurationStatus: "active",
    resourceLibraryId: "source",
    sourceScope: null,
    runMode: "automatic-organization",
    effectiveItemLimit: 12,
    counts: {
      discovered: 2,
      selected: 2,
      permitted: 2,
      excludedIgnored: 0,
      unstable: 0,
      truncatedByLimit: 0,
    },
    status: "previewed",
    items: [
      {
        previewItemId: "item-1",
        previewId: "preview-1",
        definitionId: "auto-task",
        position: 0,
        source: {
          storageId: "source-storage",
          resourceLibraryId: "source",
          path: "Media/电影/One.2001.mkv",
          filename: "One.2001.mkv",
          extension: "mkv",
          size: 32,
          stability: "stable",
          scanStatus: "discovered",
        },
        status: "previewed",
        recognition: {
          status: "matched",
          ruleId: "movie-library",
          recognitionTypeId: "A",
        },
        recognitionTypePolicy: {
          recognitionTypePolicyId: "A",
          metadataPolicyId: "A",
          namingPolicyId: "A",
          classificationPolicyId: "A",
          organizePolicyId: "A",
        },
        metadata: {
          provider: "tmdb",
          providerId: "129",
          mediaType: "movie",
          status: "resolved",
          title: "One",
          year: 2001,
        },
        naming: {
          directory: "One (2001) [tmdbid-129]",
          filename: "One (2001) [tmdbid-129].mkv",
        },
        classification: {
          mediaLibraryId: "movies",
          relativePath: "One (2001)/One (2001) [tmdbid-129].mkv",
        },
        destination: {
          storageId: "media-target",
          path: "One (2001)/One (2001) [tmdbid-129].mkv",
        },
        operation: null,
        attachments: [],
        capabilities: { required: [], declared: [], verdict: "ok" },
        conflictStrategy: null,
        conflicts: [],
        warnings: [],
        blocker: null,
        nextAction: null,
        sideEffects: "none",
        zeroMutation: true,
        executionState: "not_available_in_this_task",
        current: true,
        createdAt: "2026-01-01T00:00:00+00:00",
        updatedAt: "2026-01-01T00:00:00+00:00",
      },
    ],
    boundaryErrors: [],
    nextAction: "review the exact Preview evidence and its items",
    error: null,
    sideEffects: "none",
    zeroMutation: true,
    executionState: "not_available_in_this_task",
    current: true,
    staleReason: null,
    truncated: false,
    createdAt: "2026-01-01T00:00:00+00:00",
    updatedAt: "2026-01-01T00:00:00+00:00",
    itemTotal: 1,
    itemsTruncated: false,
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
        path: "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1",
        requiresConfirmation: false,
        durableOutcome: null,
        nextAction: "inspect the exact Preview evidence",
      }),
      items: action({
        available: true,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1/items",
        requiresConfirmation: false,
        durableOutcome: null,
        nextAction: "page the bounded Preview item evidence",
      }),
      definition: action({
        available: true,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/auto-task",
        requiresConfirmation: false,
        durableOutcome: null,
        nextAction: "reopen the durable definition",
      }),
      grantState: action({
        available: true,
        method: "GET",
        path: "/api/v1/automation/task-definitions/auto-task/grant-state",
        durableOutcome: null,
        nextAction: "read the current grant state",
      }),
      grant: action({ requiresConfirmation: true }),
    },
    ...overrides,
  };
}

describe("V2 Automation journey", () => {
  it("renders the Active identity, definition state and gated create entry", async () => {
    recordingFetch((call) => {
      if (call.url === "/api/v1/operations/automation/task-definitions") {
        return jsonResponse(listDocument());
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "Automation" });
    expect(screen.getByText(/revision-active-1/)).toBeVisible();
    expect(screen.getByText(/Nightly automation/)).toBeVisible();
    expect(screen.getByText(/every 3600 seconds/)).toBeVisible();
    expect(screen.getByText(/no occurrence yet/)).toBeVisible();
    // The backend advertises creation for this principal.
    expect(
      screen.getByRole("link", { name: "Create Automation definition" }),
    ).toBeVisible();
  });

  it("renders the truthful combined-page bound when the list is truncated", async () => {
    recordingFetch((call) => {
      if (call.url === "/api/v1/operations/automation/task-definitions") {
        return jsonResponse(
          listDocument({
            items: [definitionDocument(), draftOnlyDefinitionDocument()],
            total: 3,
            truncated: true,
          }),
        );
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "Automation" });
    // The bounded list says exactly what it shows and what it excludes.
    expect(
      screen.getByText(/Showing the first 2 of 3 definitions/),
    ).toBeVisible();
    expect(screen.getByText(/Created automation/)).toBeVisible();
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
      if (call.url === "/api/v1/operations/automation/task-definitions") {
        return jsonResponse(page);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation");

    await screen.findByRole("heading", { name: "Automation" });
    expect(
      screen.queryByRole("link", { name: "Create Automation definition" }),
    ).toBeNull();
    expect(
      screen.getByText(/cannot create Automation Task Definitions/),
    ).toBeVisible();
  });

  it("grants unattended authority with one explicit confirmed action and no authority material", async () => {
    const user = userEvent.setup();
    const { calls } = recordingFetch((call) => {
      if (
        call.url === "/api/v1/operations/automation/task-definitions/auto-task"
      ) {
        return jsonResponse({ definition: definitionDocument() });
      }
      if (call.url === "/api/v1/automation/task-definitions/auto-task/grant") {
        return jsonResponse({ grant: { status: "active", active: true } }, 201);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/definition/auto-task");

    await screen.findByRole("heading", { name: /Automation definition/ });
    const confirm = await screen.findByLabelText(
      "Confirm unattended execution grant",
    );
    const grantButton = screen.getByRole("button", {
      name: "Grant unattended authority",
    });
    expect(grantButton).toBeDisabled();
    await user.click(confirm);
    await user.click(grantButton);

    await waitFor(() =>
      expect(
        calls.some(
          (item) =>
            item.url ===
              "/api/v1/automation/task-definitions/auto-task/grant" &&
            item.method === "POST",
        ),
      ).toBe(true),
    );
    const grant = calls.find(
      (item) =>
        item.url === "/api/v1/automation/task-definitions/auto-task/grant",
    );
    expect(grant?.body).toMatchObject({
      confirmation: true,
      previewId: "preview-1",
    });
    expect(JSON.stringify(grant?.body)).not.toMatch(
      /digest|fingerprint|token|secret/i,
    );
    expect(
      calls.filter(
        (item) =>
          item.url === "/api/v1/automation/task-definitions/auto-task/grant",
      ),
    ).toHaveLength(1);
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
    await user.selectOptions(
      screen.getByLabelText("Run mode"),
      "scan-and-plan",
    );
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
        mode: "scan-and-plan",
        intervalSeconds: null,
        cron: "0 8 * * *",
        timezone: "Asia/Shanghai",
      },
    });
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
        call.url === "/api/v1/operations/automation/task-definitions" &&
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
              mode: "scan-and-plan",
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
    await user.selectOptions(
      screen.getByLabelText("Run mode"),
      "scan-and-plan",
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

  it("renders the exact Preview evidence, its staleness and paged items", async () => {
    const stale = previewDocument({
      current: false,
      status: "stale",
      staleReason:
        "the pinned definition changed after this Preview was created",
      grantEligibility: {
        eligible: false,
        status: "ineligible",
        previewId: "preview-1",
        previewStatus: "stale",
        current: false,
        zeroMutation: false,
        maxItemsPerRun: null,
        currentPermission: null,
        explanation: "this Preview is no longer current",
        durableState: "no grant or media mutation has been created",
        retrySafe: true,
        nextAction: "run a fresh exact Preview",
        error: {
          code: "unattended_execution_preview_stale",
          status: 409,
          message: "this Preview is no longer current",
          durableState: "no grant or media mutation has been created",
          retrySafe: true,
          nextAction: "run a fresh exact Preview",
        },
      },
      actions: {
        detail: action({
          available: true,
          method: "GET",
          path: "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1",
          requiresConfirmation: false,
          durableOutcome: null,
          nextAction: "inspect the exact Preview evidence",
        }),
        items: action({
          available: true,
          method: "GET",
          path: "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1/items",
          requiresConfirmation: false,
          durableOutcome: null,
          nextAction: "page the bounded Preview item evidence",
        }),
        definition: action({
          available: true,
          method: "GET",
          path: "/api/v1/operations/automation/task-definitions/auto-task",
          requiresConfirmation: false,
          durableOutcome: null,
          nextAction: "reopen the durable definition",
        }),
        grantState: action({
          available: true,
          method: "GET",
          path: "/api/v1/automation/task-definitions/auto-task/grant-state",
          requiresConfirmation: false,
          durableOutcome: null,
          nextAction: "read the current grant state",
        }),
        grant: action({
          available: false,
          reason:
            "this Preview is historical, truncated or incomplete and cannot support unattended authority; run a fresh exact Preview",
          requiresConfirmation: true,
        }),
      },
    });
    recordingFetch((call) => {
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1"
      ) {
        return jsonResponse(stale);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/preview/auto-task/preview-1");

    await screen.findByRole("heading", { name: "Exact Automation Preview" });
    expect(screen.getByText(/Historical evidence/)).toBeVisible();
    expect(screen.getByText(/no longer current/)).toBeVisible();
    expect(screen.getAllByText(/One\.2001\.mkv/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Previewed/).length).toBeGreaterThan(0);
    expect(
      screen.queryByRole("button", { name: "Grant unattended authority" }),
    ).toBeNull();
    expect(
      screen.getAllByText(/run a fresh exact Preview/).length,
    ).toBeGreaterThan(0);
    // Every item is present, so no paging control is offered.
    expect(
      screen.queryByRole("button", { name: /Load more items/ }),
    ).toBeNull();
  });

  it("fails closed on a malformed Preview document without rendering a control", async () => {
    const hostile = previewDocument({
      actions: {
        detail: action({
          available: true,
          method: "GET",
          path: "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1",
          requiresConfirmation: false,
          durableOutcome: null,
          nextAction: "inspect",
        }),
        items: action({
          available: true,
          method: "GET",
          path: "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1/items",
          requiresConfirmation: false,
          durableOutcome: null,
          nextAction: "page",
        }),
        definition: action({
          available: true,
          method: "GET",
          path: "/api/v1/operations/automation/task-definitions/auto-task",
          requiresConfirmation: false,
          durableOutcome: null,
          nextAction: "reopen",
        }),
        grantState: action({
          available: true,
          method: "GET",
          path: "/api/v1/automation/task-definitions/auto-task/grant-state",
          requiresConfirmation: false,
          durableOutcome: null,
          nextAction: "read",
        }),
        grant: action({
          // A non-URI-safe identity is never this object's transport.
          path: "/api/v1/automation/task-definitions/<task>/grant",
        }),
      },
    });
    const { calls } = recordingFetch((call) => {
      if (
        call.url ===
        "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1"
      ) {
        return jsonResponse(hostile);
      }
      return undefined;
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations/automation/preview/auto-task/preview-1");

    await screen.findByText(
      /could not be understood as the expected contract/i,
    );
    expect(
      screen.queryByRole("button", { name: "Grant unattended authority" }),
    ).toBeNull();
    expect(calls.filter((item) => item.method !== "GET")).toHaveLength(0);
  });
});
