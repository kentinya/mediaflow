import { describe, expect, it } from "vitest";
import {
  normalizeAutomationAction,
  normalizeAutomationDefinitionsPage,
  normalizeAutomationDraftState,
  normalizeAutomationEligibility,
  normalizeAutomationGrantState,
  normalizeAutomationPreview,
  AutomationNormalizationError,
  type AutomationPreviewModel,
} from "./automation";

/**
 * Focused normalization regressions for the V2 Automation operator documents.
 *
 * Every action transport is bound to its exact owned route, method and
 * URI-safe identity (the draft-save parameter is pinned to the exact
 * definition identity), every contradictory state block fails closed, and the
 * whole page is malformed when any embedded evidence disagrees with itself.
 */

function offeredAction(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    available: true,
    reason: null,
    method: "POST",
    path: "/api/v1/automation/task-definitions/auto-task/grant",
    requiresConfirmation: true,
    sideEffects: "none",
    durableOutcome: "a persistent scoped unattended execution grant is stored",
    nextAction: "review the grant eligibility and explicitly confirm",
    ...overrides,
  };
}

describe("normalizeAutomationAction transport binding", () => {
  it("binds the grant action to the exact definition route and confirmation", () => {
    const model = normalizeAutomationAction(
      offeredAction(),
      "actions.grant",
      "definition-grant",
      "auto-task",
    );
    expect(model.available).toBe(true);
    expect(model.requiresConfirmation).toBe(true);
    expect(model.path).toBe(
      "/api/v1/automation/task-definitions/auto-task/grant",
    );
  });

  it("rejects a non-URI-safe identity and its matching route", () => {
    for (const identity of ["<definition>", "auto/{task}", "..", "."]) {
      expect(() =>
        normalizeAutomationAction(
          offeredAction({
            path: `/api/v1/automation/task-definitions/${identity}/grant`,
          }),
          "actions.grant",
          "definition-grant",
          identity,
        ),
      ).toThrow(AutomationNormalizationError);
    }
  });

  it("rejects wrong suffixes, methods, other objects and unpinned parameters", () => {
    const cases: Array<{
      path: string;
      method?: string;
      kind: Parameters<typeof normalizeAutomationAction>[2];
      identity: string | null;
      parameter?: string | null;
    }> = [
      {
        // The definition read route without /grant is never the mutation.
        path: "/api/v1/automation/task-definitions/auto-task",
        kind: "definition-grant",
        identity: "auto-task",
      },
      {
        // Another object's route is never this action's transport.
        path: "/api/v1/automation/task-definitions/other-task/grant",
        kind: "definition-grant",
        identity: "auto-task",
      },
      {
        // A safe method never carries a mutating confirmation.
        path: "/api/v1/automation/task-definitions/auto-task/grant",
        method: "GET",
        kind: "definition-grant",
        identity: "auto-task",
      },
      {
        // A wrong fixed suffix is malformed too.
        path: "/api/v1/automation/task-definitions/auto-task/grants",
        kind: "definition-grant",
        identity: "auto-task",
      },
      {
        // The draft-save parameter must name the exact definition.
        path: "/api/v1/configuration/revisions/rev-1/objects/automationTaskDefinitions/other-task",
        kind: "draft-save",
        identity: "rev-1",
        parameter: "auto-task",
      },
      {
        // A non-URI-safe parameter segment is malformed even when unpinned.
        path: "/api/v1/configuration/revisions/rev-1/objects/automationTaskDefinitions/<task>",
        kind: "draft-save",
        identity: "rev-1",
      },
    ];
    for (const item of cases) {
      expect(() =>
        normalizeAutomationAction(
          offeredAction({ path: item.path, method: item.method ?? "POST" }),
          "actions.x",
          item.kind,
          item.identity,
          item.parameter ?? null,
        ),
      ).toThrow(AutomationNormalizationError);
    }
  });

  it("accepts the collection-level create transport without an identity", () => {
    const model = normalizeAutomationAction(
      offeredAction({
        method: "POST",
        path: "/api/v1/automation/task-definitions",
        requiresConfirmation: false,
      }),
      "actions.create",
      "list-create",
    );
    expect(model.available).toBe(true);
    expect(model.path).toBe("/api/v1/automation/task-definitions");
    expect(() =>
      normalizeAutomationAction(
        offeredAction({
          method: "POST",
          path: "/api/v1/automation/task-definitions/extra",
          requiresConfirmation: false,
        }),
        "actions.create",
        "list-create",
      ),
    ).toThrow(AutomationNormalizationError);
  });
});

describe("automation state block fail-closed contracts", () => {
  it("rejects a draft state that contradicts its own identity", () => {
    expect(() =>
      normalizeAutomationDraftState({
        present: true,
        reason: null,
        revisionId: null,
        revisionVersion: null,
        revisionStatus: "draft",
        baseActiveRevisionId: null,
        updatedAt: null,
        validatedAt: null,
        validationErrors: [],
      }),
    ).toThrow(AutomationNormalizationError);
    expect(() =>
      normalizeAutomationDraftState({
        present: false,
        reason: "no draft",
        revisionId: "rev-1",
        revisionVersion: 2,
        revisionStatus: null,
        baseActiveRevisionId: null,
        updatedAt: null,
        validatedAt: null,
        validationErrors: [],
      }),
    ).toThrow(AutomationNormalizationError);
  });

  it("rejects a grant state with none status but grant authority evidence", () => {
    expect(() =>
      normalizeAutomationGrantState({
        status: "none",
        active: true,
        grantId: "grant-1",
        definitionId: "auto-task",
        definitionChangedSinceGrant: false,
        nextAction: "review",
      }),
    ).toThrow(AutomationNormalizationError);
    const model = normalizeAutomationGrantState({
      status: "active",
      active: true,
      grantId: "grant-1",
      definitionId: "auto-task",
      definitionChangedSinceGrant: false,
      nextAction: "inspect occurrences",
      maxItemsPerRun: 5,
      previewId: "preview-1",
      grantingPrincipal: "admin",
      grantedAt: "2026-01-01T00:00:00+00:00",
      revokedAt: null,
      reason: null,
      currentPermission: {
        principalId: "admin",
        status: "valid",
        allowed: true,
      },
    });
    expect(model.active).toBe(true);
    expect(model.currentPermission?.allowed).toBe(true);
  });

  it("rejects eligibility whose status label contradicts the decision", () => {
    expect(() =>
      normalizeAutomationEligibility({
        eligible: true,
        status: "ineligible",
        previewId: "preview-1",
        current: true,
        zeroMutation: true,
        maxItemsPerRun: 5,
        currentPermission: null,
        explanation: "ok",
        durableState: "no grant",
        retrySafe: true,
        nextAction: "confirm",
        error: null,
      }),
    ).toThrow(AutomationNormalizationError);
    expect(() =>
      normalizeAutomationEligibility({
        eligible: false,
        status: "ineligible",
        previewId: null,
        current: false,
        zeroMutation: false,
        maxItemsPerRun: null,
        currentPermission: null,
        explanation: "no preview",
        durableState: "no grant",
        retrySafe: true,
        nextAction: "run a fresh Preview",
        error: null,
      }),
    ).toThrow(AutomationNormalizationError);
  });
});

function previewDocument(
  mutate?: (value: Record<string, unknown>) => void,
): Record<string, unknown> {
  const value: Record<string, unknown> = {
    previewId: "preview-1",
    definitionId: "auto-task",
    configurationRevisionId: "rev-1",
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
          ruleId: "movie",
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
          filename: "One (2001).mkv",
        },
        classification: {
          mediaLibraryId: "movies",
          relativePath: "One (2001)/One (2001).mkv",
        },
        destination: {
          storageId: "media-target",
          path: "One (2001)/One (2001).mkv",
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
    nextAction: "review the exact Preview evidence",
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
    grantEligibility: null,
    actions: {
      detail: {
        available: true,
        reason: null,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1",
        sideEffects: "none",
        durableOutcome: null,
        nextAction: "inspect the exact Preview evidence and its items",
      },
      items: {
        available: true,
        reason: null,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/auto-task/previews/preview-1/items",
        sideEffects: "none",
        durableOutcome: null,
        nextAction: "page the bounded Preview item evidence",
      },
      definition: {
        available: true,
        reason: null,
        method: "GET",
        path: "/api/v1/operations/automation/task-definitions/auto-task",
        sideEffects: "none",
        durableOutcome: null,
        nextAction: "reopen the durable definition behind this Preview",
      },
      grantState: {
        available: true,
        reason: null,
        method: "GET",
        path: "/api/v1/automation/task-definitions/auto-task/grant-state",
        sideEffects: "none",
        durableOutcome: null,
        nextAction: "read the current unattended grant state",
      },
      grant: {
        available: true,
        reason: null,
        method: "POST",
        path: "/api/v1/automation/task-definitions/auto-task/grant",
        requiresConfirmation: true,
        sideEffects: "none",
        durableOutcome:
          "a persistent scoped unattended execution grant is stored",
        nextAction: "review the grant eligibility and explicitly confirm",
      },
    },
  };
  mutate?.(value);
  return value;
}

describe("normalizeAutomationPreview", () => {
  it("normalizes the exact bounded Preview with its pinned transports", () => {
    const model: AutomationPreviewModel =
      normalizeAutomationPreview(previewDocument());
    expect(model.status).toBe("previewed");
    expect(model.zeroMutation).toBe(true);
    expect(model.current).toBe(true);
    expect(model.counts.discovered).toBe(2);
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.recognition.recognitionTypeId).toBe("A");
    expect(model.actions.grant.requiresConfirmation).toBe(true);
  });

  it("fails closed on unknown statuses, malformed items and hostile transports", () => {
    const variants: Array<(value: Record<string, unknown>) => void> = [
      (value) => {
        value["status"] = "hacked";
      },
      (value) => {
        (value["items"] as Array<Record<string, unknown>>)[0]["status"] =
          "hacked";
      },
      (value) => {
        value["counts"] = {
          ...((value["counts"] ?? {}) as object),
          discovered: "many",
        };
      },
      (value) => {
        const actions = value["actions"] as Record<string, unknown>;
        actions["grant"] = {
          ...(actions["grant"] as object),
          path: "/api/v1/automation/task-definitions/<task>/grant",
        };
      },
      (value) => {
        const actions = value["actions"] as Record<string, unknown>;
        actions["items"] = {
          ...(actions["items"] as object),
          path: "/api/v1/operations/automation/task-definitions/auto-task/previews/other/items",
        };
      },
    ];
    for (const mutate of variants) {
      expect(() => normalizeAutomationPreview(previewDocument(mutate))).toThrow(
        AutomationNormalizationError,
      );
    }
  });
});

describe("normalizeAutomationDefinitionsPage", () => {
  it("normalizes the bounded page with Active identity and Draft state", () => {
    const page = normalizeAutomationDefinitionsPage({
      activeConfiguration: {
        revisionId: "rev-1",
        version: 3,
        revisionSequence: 2,
        status: "active",
      },
      items: [],
      total: 0,
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
        create: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/automation/task-definitions",
          sideEffects: "none",
          durableOutcome: "stored in the open Draft",
          nextAction: "start or open a successor Draft",
        },
        createDraft: {
          available: true,
          reason: null,
          method: "POST",
          path: "/api/v1/configuration/revisions/rev-1/successor",
          sideEffects: "none",
          durableOutcome: "a successor Draft is stored",
          nextAction: "create or open the successor Draft",
        },
      },
    });
    expect(page.activeConfiguration?.revisionId).toBe("rev-1");
    expect(page.resourceLibraryOptions[0]?.id).toBe("source");
    expect(page.actions.create.available).toBe(true);
    expect(() =>
      normalizeAutomationDefinitionsPage({
        ...({ items: "many" } as unknown as Record<string, unknown>),
      }),
    ).toThrow(AutomationNormalizationError);
  });
});
