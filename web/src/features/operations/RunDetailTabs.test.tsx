/**
 * Component journeys for the selected-run detail tabs (Slice 42 RO-3).
 *
 * The tests drive the real route tree with a stubbed API boundary and prove
 * the operator-facing promises of the Task: 任务详情/操作记录 tabs with
 * truthful progress, server-filtered and server-paged items and records,
 * exact item evidence, the scoped result-package download, and distinct
 * bounded failures for 401/403/404/malformed reads.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";

const TOKEN = "detail-token";

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
  authStore.clearToken();
  authStore.clearIntendedPath();
  vi.unstubAllGlobals();
});

function progressDocument(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    kind: "organize",
    unit: "主条目",
    unit_key: "task_items",
    basis: "整理计数:成功表示已验证的存储操作结果。",
    success_means: "已验证的存储操作成功",
    known_total: 4,
    indeterminate: false,
    processed: 3,
    dispositions: {
      pending: 1,
      active: 0,
      waiting: 1,
      success: 2,
      skipped: 0,
      failed_partial: 0,
      ignored: 0,
      cancelled: 0,
    },
    confirmed_success: 1,
    uncertain_success: 1,
    scan_errors: 0,
    scan_discovery_complete: null,
    scan_progress: {},
    attachment_steps: 2,
    effect_counts: { verified_complete: 1, attempted_unverified: 1 },
    results_total: 2,
    results_complete: true,
    sideEffects: "none",
    ...overrides,
  };
}

function overviewDocument(overrides: Record<string, unknown> = {}) {
  return {
    run_kind: "task",
    run_id: "task-001",
    command: "organize",
    command_label: "整理",
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
    pause_requested: false,
    attention: false,
    configuration_snapshot_id: "snap-1",
    worker_id: null,
    sideEffects: "none",
    progress: progressDocument(),
    ...overrides,
  };
}

function itemRow(overrides: Record<string, unknown> = {}) {
  return {
    item_id: "item-1",
    task_id: "task-001",
    status: "success",
    stage: "organize",
    attempts: 1,
    storage_id: "source",
    resource_library_id: "movies",
    source_path: "movies/a.mkv",
    destination_storage_id: "target",
    destination_path: "Movies/a.mkv",
    execution_status: null,
    created_at: "2026-08-22T12:00:00+00:00",
    updated_at: "2026-08-22T12:00:00+00:00",
    failure: null,
    checkpoint: null,
    ...overrides,
  };
}

const WAITING_ITEM = itemRow({
  item_id: "item-2",
  status: "waiting_metadata",
  stage: "metadata",
  source_path: "movies/b.mkv",
  checkpoint: {
    status: "waiting_metadata",
    stage: "waiting",
    raw_stage: "metadata",
    blocker_kind: "metadata_review",
    blocker_id: "review-1",
    effect_certainty: "unknown",
    retry_safety: "unknown",
    refusal_reason: null,
    checkpoint_version: "v1",
    permitted_action_ids: ["decide"],
  },
});

function itemsPageDocument(overrides: Record<string, unknown> = {}) {
  const items = (overrides["items"] as unknown[] | undefined) ?? [
    itemRow(),
    WAITING_ITEM,
  ];
  const total = typeof overrides["total"] === "number" ? overrides["total"] : 4;
  return {
    run_id: "task-001",
    task_id: "task-001",
    filter: { status: null },
    limit: 20,
    items,
    total,
    matching_total:
      typeof overrides["matching_total"] === "number"
        ? overrides["matching_total"]
        : total,
    dispositions: {
      pending: 1,
      active: 0,
      waiting: 1,
      success: 2,
      skipped: 0,
      failed_partial: 0,
      ignored: 0,
      cancelled: 0,
    },
    uncertain_success: 1,
    truncated: false,
    previous_cursor: null,
    next_cursor: null,
    sideEffects: "none",
    ...overrides,
  };
}

function recordsPageDocument(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "task-001",
    task_id: "task-001",
    job_id: null,
    filter: { kind: null },
    limit: 20,
    records: [
      {
        record_id: "result:result-1",
        kind: "result",
        kind_label: "执行结果",
        occurred_at: "2026-08-22T12:01:00+00:00",
        item_id: "item-1",
        level: null,
        event: null,
        component: null,
        status: null,
        plan_id: null,
        action: null,
        state: null,
        actor: null,
        parent_id: null,
        result: {
          result_id: "result-1",
          task_id: "task-001",
          item_id: "item-1",
          source_storage_id: "source",
          source_path: "movies/a.mkv",
          destination_storage_id: "target",
          destination_path: "Movies/a.mkv",
          recognition_type: "C",
          provider: "tmdb",
          provider_id: "101",
          metadata_policy_id: "C",
          naming_policy_id: "A",
          classification_policy_id: "A",
          organize_policy_id: "A",
          operation: "MOVE",
          status: "success",
          created_at: "2026-08-22T12:01:00+00:00",
          title: "A",
          failure: null,
          completed_operations: ["move"],
          effect_certainty: "verified_complete",
          uncertain_effects: [],
          cleanup_status: "cleaned",
        },
        evidence: null,
      },
      {
        record_id: "log:log-1",
        kind: "log",
        kind_label: "运行日志",
        occurred_at: "2026-08-22T12:02:00+00:00",
        item_id: null,
        level: "INFO",
        event: "organizer.execution_result",
        component: "workflow",
        status: "success",
        plan_id: "plan-1",
        action: null,
        state: null,
        actor: null,
        parent_id: null,
        result: null,
        evidence: null,
      },
    ],
    matching_total: 4,
    kind_counts: { result: 3, evidence: 1, log: 0, audit: 0 },
    truncated: false,
    previous_cursor: null,
    next_cursor: null,
    sideEffects: "none",
    ...overrides,
  };
}

/**
 * The real durable reviewed-plan projection of a manually executed item
 * (`manual_execution_plan_evidence_operator` through `_bounded_preview_plan`
 * in the Python Operations surface): camelCase ids, the persisted effect rows
 * and the exact reviewed Preview plan document.
 */
function planEvidenceDocument(overrides: Record<string, unknown> = {}) {
  return {
    available: true,
    previewId: "preview-1",
    executionId: "exec-1",
    status: "success",
    stage: "completed",
    effectCertainty: "verified_complete",
    completedOperations: ["CREATE_DIRECTORY", "MOVE"],
    uncertainEffects: [],
    effects: [
      {
        action: "MOVE",
        sourceStorageId: "source",
        sourceLocation: "One (2001)/One (2001).mkv",
        destinationStorageId: "target",
        destinationLocation: "One (2001)/One (2001).mkv",
        verified: true,
        certainty: "verified_complete",
        rollback: false,
        occurredAt: "2026-08-22T12:03:00+00:00",
      },
    ],
    plan: {
      recognitionType: "C",
      mediaIdentity: {
        provider: "tmdb",
        providerId: "101",
        mediaType: "movie",
        title: "One",
        year: 2001,
      },
      policies: {
        recognitionTypePolicyId: "type-C",
        metadataPolicyId: "C",
        namingPolicyId: "A",
        classificationPolicyId: "A",
        organizePolicyId: "A",
      },
      analysis: {
        parse: {
          titleCandidate: "One",
          year: 2001,
          evidence: [],
          warnings: [],
        },
        recognition: {
          status: "recognized",
          recognitionTypeId: "C",
          ruleId: "movie-year",
          reasons: [],
          warnings: [],
        },
        metadata: {
          available: true,
          status: "matched",
          match: {
            status: "matched",
            candidates: [],
            reasons: [],
            warnings: [],
            candidateCount: 1,
          },
        },
        naming: {
          available: true,
          policyId: "A",
          directory: "One (2001)",
          directorySegments: ["One (2001)"],
          filename: "One (2001).mkv",
          warnings: [],
          sanitizationChanges: [],
        },
        classification: {
          available: true,
          status: "classified",
          policyId: "A",
          mediaLibraryId: "movies",
          relativePath: "Movies",
          evidence: [],
          warnings: [],
        },
      },
      destination: {
        storageId: "target",
        relativePath: "Movies/One (2001)/One (2001).mkv",
      },
      operation: "MOVE",
      operationPolicy: "MOVE",
      attachments: [],
      capabilities: {
        verdict: "ok",
        required: ["can_move", "can_delete"],
        declared: ["can_move", "can_delete"],
        missing: [],
      },
      conflicts: [],
      warnings: [],
      planStatus: "organized",
      destructiveImplications: {
        overwriteRequired: false,
        sourceCleanupRequired: false,
        statement:
          "this exact plan replaces and deletes nothing; source media is preserved by the reviewed operation",
      },
      cleanupProjection: {
        mode: "empty_only",
        parent: "source/Season 1",
        ignorePatterns: ["*.nfo"],
        maxParentDirectories: 3,
        maxEntries: 24,
        matchedFiles: ["One.2001.mkv"],
        blockingEntries: [],
        expectedDirectoryOutcome: "remove_empty",
        permanentDelete: false,
      },
    },
    ...overrides,
  };
}

function evidenceResultRow(overrides: Record<string, unknown> = {}) {
  return {
    result_id: "result-1",
    task_id: "task-001",
    item_id: "item-1",
    source_storage_id: "source",
    source_path: "movies/b.mkv",
    destination_storage_id: "target",
    destination_path: "Movies/Two (2002)/Two (2002).mkv",
    recognition_type: "C",
    provider: "tmdb",
    provider_id: "102",
    metadata_policy_id: "C",
    naming_policy_id: "A",
    classification_policy_id: "A",
    organize_policy_id: "A",
    operation: "MOVE",
    status: "success",
    created_at: "2026-08-22T12:03:00+00:00",
    title: "Two",
    failure: null,
    completed_operations: ["move"],
    effect_certainty: "verified_complete",
    uncertain_effects: [],
    cleanup_status: "disabled",
    ...overrides,
  };
}

function evidenceDocument(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "task-001",
    task_id: "task-001",
    item_id: "item-2",
    item: WAITING_ITEM,
    checkpoint: {
      status: "waiting_metadata",
      stage: "waiting",
      raw_stage: "metadata",
      attempts: 1,
      source_storage_id: "source",
      resource_library_id: "movies",
      source_path: "movies/b.mkv",
      plan_id: null,
      destination_storage_id: null,
      destination_path: null,
      configuration: { snapshot_id: "snap-1", resolvable: true, reason: null },
      latest_result: null,
      prior_results: [],
      blockers: [],
      blocker: {
        kind: "metadata_review",
        id: "review-1",
        status: "pending",
        task_id: "task-001",
        item_id: "item-2",
        resolution_path: "/review",
      },
      audits: [],
      recovery_requests: [],
      recovery_request: null,
      recovery_continuation: null,
      effects: {
        certainty: "unknown",
        completed_operations: [],
        uncertain_effects: [],
      },
      error_category: "workflow_failure",
      retry_safety: "unknown",
      failureExplanation: null,
      nextAction: "choose a metadata candidate",
      actions: [],
      permitted_action_ids: ["decide"],
      refusal_reason: "waiting_for_decision",
      checkpoint_version: "v2",
      updated_at: "2026-08-22T12:02:00+00:00",
    },
    results: [],
    evidence: [],
    // A waiting item never came through the reviewed Manual execution, so the
    // durable plan section says so with its reason code (Task 42.2).
    planEvidence: { available: false },
    logs: [],
    sideEffects: "none",
    ...overrides,
  };
}

/**
 * The evidence document of a **standalone processing-chain** item (the
 * supported `organize --execute` path): a real durable Result with persisted
 * completed steps, an uncertain sibling effect, one captured pipeline
 * document whose `operation` section holds the executor's bounded step lists
 * — and *no* Manual execution linkage, so `planEvidence` says unavailable.
 */
function standaloneExecutionEvidenceDocument(
  overrides: Record<string, unknown> = {},
) {
  return evidenceDocument({
    item_id: "item-9",
    item: itemRow({
      item_id: "item-9",
      source_path: "movies/standalone.mkv",
      destination_path: "Movies/Two (2002)/Two (2002).mkv",
      execution_status: "SUCCESS",
    }),
    checkpoint: {
      status: "success",
      stage: "completed",
      raw_stage: "organize",
      attempts: 1,
      source_storage_id: "source",
      resource_library_id: "movies",
      source_path: "movies/standalone.mkv",
      plan_id: "plan-9",
      destination_storage_id: "target",
      destination_path: "Movies/Two (2002)/Two (2002).mkv",
      configuration: { snapshot_id: "snap-1", resolvable: true, reason: null },
      latest_result: null,
      prior_results: [],
      blockers: [],
      blocker: null,
      audits: [],
      recovery_requests: [],
      recovery_request: null,
      recovery_continuation: null,
      // The exact durable facts B's repro proved the API returns for a
      // non-Manual item: the aggregate hides them unless the view reads them.
      effects: {
        certainty: "verified_complete",
        completed_operations: ["CREATE_DIRECTORY", "MOVE"],
        uncertain_effects: [],
      },
      error_category: null,
      retry_safety: "safe",
      failureExplanation: null,
      nextAction: null,
      actions: [],
      permitted_action_ids: [],
      refusal_reason: null,
      checkpoint_version: "v1",
      updated_at: "2026-08-22T12:03:00+00:00",
    },
    results: [
      evidenceResultRow({
        item_id: "item-9",
        completed_operations: ["CREATE_DIRECTORY", "MOVE"],
        effect_certainty: "verified_complete",
        uncertain_effects: [],
      }),
      evidenceResultRow({
        result_id: "result-2",
        item_id: "item-9",
        completed_operations: ["copy_written", "destination_verified"],
        effect_certainty: "attempted_unverified",
        uncertain_effects: ["source_deletion"],
        cleanup_status: null,
      }),
    ],
    evidence: [
      {
        evidenceId: "ev-9",
        attempts: 1,
        outcome: "success",
        capturedAt: "2026-08-22T12:02:00+00:00",
        truncated: false,
        sections: {
          operation: {
            available: true,
            truncated: false,
            value: {
              status: "SUCCESS",
              operation: "MOVE",
              createdDirectories: ["Movies/Anime/Two (2002)"],
              completedOperations: ["CREATE_DIRECTORY", "MOVE"],
              uncertainEffects: ["source_deletion"],
              cleanupStatus: "disabled",
            },
            items: [],
            warnings: [],
          },
        },
      },
    ],
    // A standalone item never joined the reviewed Manual journey: the honest
    // unavailable statement stays, and the durable block below carries the
    // explanation instead (Task 42.2 P1 / AC-T4).
    planEvidence: { available: false },
    logs: [],
    ...overrides,
  });
}

/** The evidence document of the successfully executed 手动整理 item-1. */
function manualExecutionEvidenceDocument(
  overrides: Record<string, unknown> = {},
) {
  return evidenceDocument({
    item_id: "item-1",
    item: itemRow(),
    checkpoint: {
      status: "success",
      stage: "completed",
      raw_stage: "organize",
      attempts: 1,
      source_storage_id: "source",
      resource_library_id: "movies",
      source_path: "movies/a.mkv",
      plan_id: "plan-1",
      destination_storage_id: "target",
      destination_path: "Movies/a.mkv",
      configuration: { snapshot_id: "snap-1", resolvable: true, reason: null },
      latest_result: null,
      prior_results: [],
      blockers: [],
      blocker: null,
      audits: [],
      recovery_requests: [],
      recovery_request: null,
      recovery_continuation: null,
      effects: {
        certainty: "verified_complete",
        completed_operations: ["MOVE"],
        uncertain_effects: [],
      },
      error_category: null,
      retry_safety: "safe",
      failureExplanation: null,
      nextAction: null,
      actions: [],
      permitted_action_ids: [],
      refusal_reason: null,
      checkpoint_version: "v1",
      updated_at: "2026-08-22T12:03:00+00:00",
    },
    results: [evidenceResultRow()],
    evidence: [
      {
        evidenceId: "ev-1",
        attempts: 1,
        outcome: "success",
        capturedAt: "2026-08-22T12:02:00+00:00",
        truncated: false,
        sections: {
          plan: {
            available: true,
            truncated: false,
            value: { operation: "MOVE" },
            items: [{ field: "ext", value: "mkv" }],
            warnings: ["w"],
          },
          metadata: {
            available: false,
            unavailableReason: "legacy evidence",
            truncated: false,
          },
        },
      },
    ],
    planEvidence: planEvidenceDocument(),
    logs: [],
    ...overrides,
  });
}

function exportPackageDocument(overrides: Record<string, unknown> = {}) {
  return {
    packageKind: "mediaflow.results.v1",
    packageSchemaVersion: 1,
    packageVersion: 1,
    generatedAt: "2026-08-22T12:05:00+00:00",
    producer: { id: "mediaflow" },
    source: {
      scope: "task",
      taskId: "task-001",
      taskCommand: "organize",
      ordering: "created_at_asc,result_id_asc",
      limit: 500,
    },
    redaction: {
      scope: "persisted_task_result_projection",
      entryCount: 0,
      entries: [],
    },
    results: [
      {
        resultId: "result-1",
        taskId: "task-001",
        itemId: "item-1",
        sourceStorageId: "source",
        sourcePath: "movies/a.mkv",
        destinationStorageId: "target",
        destinationPath: "Movies/a.mkv",
        recognitionType: "C",
        provider: "tmdb",
        providerId: "101",
        metadataPolicyId: "C",
        namingPolicyId: "A",
        classificationPolicyId: "A",
        organizePolicyId: "A",
        operation: "MOVE",
        status: "success",
        createdAt: "2026-08-22T12:01:00+00:00",
        title: "A",
        error: null,
        completedOperations: ["move"],
        attachmentCount: 0,
        retryAttempts: 0,
        retryCategory: null,
        cleanupStatus: "cleaned",
        cleanupStepCount: 0,
        effectCertainty: "verified_complete",
        uncertainEffects: [],
        sourceOccurrenceId: null,
        sourceFingerprint: null,
        sourceFingerprintState: "unverified",
      },
    ],
    truncated: false,
    warning: [],
    packageDigest: "abc123",
    ...overrides,
  };
}

/** One fetch stub covering the whole selected-run detail journey. */
function stubDetailJourney(requested: string[] = []) {
  return stubFetch(async (input) => {
    const url = String(input);
    requested.push(url);
    if (url.startsWith("/api/v1/operations/runs?")) {
      return jsonResponse({
        items: [overviewDocument()],
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
        population: "unified job/task run inventory",
        sideEffects: "none",
        previous_cursor: null,
        next_cursor: null,
      });
    }
    if (url === "/api/v1/operations/runs/task-001") {
      return jsonResponse(overviewDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/items/item-2")) {
      return jsonResponse(evidenceDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/items/item-1")) {
      return jsonResponse(manualExecutionEvidenceDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
      const status = new URLSearchParams(url.split("?")[1] ?? "").get("status");
      if (status === "waiting") {
        return jsonResponse(
          itemsPageDocument({
            items: [WAITING_ITEM],
            filter: { status: "waiting" },
            matching_total: 1,
            dispositions: {
              pending: 1,
              active: 0,
              waiting: 1,
              success: 2,
              skipped: 0,
              failed_partial: 0,
              ignored: 0,
              cancelled: 0,
            },
          }),
        );
      }
      return jsonResponse(itemsPageDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/items")) {
      return jsonResponse(itemsPageDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/records?")) {
      const kind = new URLSearchParams(url.split("?")[1] ?? "").get("kind");
      if (kind === "log") {
        return jsonResponse(
          recordsPageDocument({
            filter: { kind: "log" },
            records: [recordsPageDocument()["records"][1]],
            matching_total: 1,
            kind_counts: { result: 3, evidence: 1, log: 1, audit: 0 },
          }),
        );
      }
      return jsonResponse(recordsPageDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
      return jsonResponse(recordsPageDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/export")) {
      return jsonResponse(exportPackageDocument());
    }
    if (url === "/api/v1/workers/readiness") {
      return jsonResponse({
        ready: true,
        condition: "ready",
        category: null,
        durableState: "resident processing worker is live and ready",
        sideEffects: "none",
        retrySafe: true,
        nextAction: "none",
        activeWorkersCount: 1,
        activeSnapshotId: "snap-1",
        expectedRuntimeSchemaVersion: 42,
      });
    }
    if (url === "/api/v1/management/readiness") {
      return jsonResponse({
        available: true,
        infrastructureReady: true,
        asOf: "2026-08-22T12:00:00+00:00",
        sideEffects: "none",
        infrastructure: { services: {} },
      });
    }
    if (url.startsWith("/api/v1/operations/manual-actions")) {
      return jsonResponse({
        scopeKind: null,
        scopeId: null,
        fileId: null,
        resourceLibraryId: null,
        selectionRequired: true,
        source: null,
        resourceLibraries: [],
        runtime: { ready: true, condition: "ready", nextAction: null },
        actions: {
          scan: { available: false, reason: "not advertised" },
          preview: { available: false, reason: "not advertised" },
          organize: { available: false, reason: "not advertised" },
        },
        limits: { previewMaxItems: 100 },
      });
    }
    return jsonResponse({ error: { code: "not_found" } }, 404);
  });
}

describe("selected-run detail tabs", () => {
  it("renders truthful progress with its accounting basis and no invented percentage claims", async () => {
    stubDetailJourney();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    const progress = await within(detail).findByRole("region", {
      name: "整理进度",
    });
    // The processed ratio is labelled as processed work, never a success
    // percentage, and the accounting basis stays visible.
    expect(within(progress).getByText(/已处理 3 \/ 4 个主条目/)).toBeVisible();
    expect(within(progress).getByText(/处理进度,非成功率/)).toBeVisible();
    expect(within(progress).getByText(/已确认成功/)).toBeVisible();
    expect(within(progress).getByText(/效果未确认\(不计成功\)/)).toBeVisible();
    expect(within(progress).getByText(/口径:/)).toBeVisible();
    expect(within(progress).getByText(/附件步骤 2\(单独计数/)).toBeVisible();
    // The tabs the reference promises.
    expect(
      within(detail).getByRole("button", { name: "任务详情" }),
    ).toBeVisible();
    expect(
      within(detail).getByRole("button", { name: "操作记录" }),
    ).toBeVisible();
  });

  it("submits the item disposition filter to the server and keeps the population totals", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubDetailJourney(requested);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);

    await user.selectOptions(screen.getByLabelText("状态筛选"), "waiting");
    await waitFor(() =>
      expect(requested.some((url) => url.includes("status=waiting"))).toBe(
        true,
      ),
    );
    // The filter narrows the page but the reported population keeps its
    // whole-run partition.
    expect(await screen.findByText(/匹配 1 条/)).toBeVisible();
    expect(screen.getByText(/运行共 4 条/)).toBeVisible();
    expect(await screen.findByText(/movies\/b\.mkv/)).toBeVisible();
    // The filter state is in the URL so refresh/history/reconnect restore it.
    const detailRequest = requested.find((url) =>
      url.includes("status=waiting"),
    );
    expect(detailRequest).toContain("/api/v1/operations/runs/task-001/items");
  });

  it("switches to 操作记录 with its server page and kind filter", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubDetailJourney(requested);
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    await user.click(
      await within(detail).findByRole("button", { name: "操作记录" }),
    );
    expect(await screen.findByLabelText("操作记录")).toBeVisible();
    expect(await screen.findByText(/organizer.execution_result/)).toBeVisible();
    expect(screen.getByText(/匹配 4 条记录/)).toBeVisible();

    await user.selectOptions(screen.getByLabelText("类型筛选"), "log");
    await waitFor(() =>
      expect(requested.some((url) => url.includes("kind=log"))).toBe(true),
    );
    expect(await screen.findByText(/匹配 1 条记录/)).toBeVisible();
    // The URL carries the submitted tab and kind for reconnect.
    expect(router.history.location.search).toContain("tab=records");
    expect(router.history.location.search).toContain("rkind=log");
  });

  it("opens one item's exact evidence and closes it again", async () => {
    const user = userEvent.setup();
    stubDetailJourney();
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    const inspectButtons = within(detail).getAllByRole("button", {
      name: "查看证据",
    });
    await user.click(inspectButtons[1]);
    const evidence = await within(detail).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("条目证据:item-2");
    expect(
      within(evidence).getByText(/choose a metadata candidate/),
    ).toBeVisible();
    expect(within(evidence).getByText(/waiting_for_decision/)).toBeVisible();
    expect(within(evidence).getByText(/metadata_review/)).toBeVisible();
    expect(within(evidence).getByText(/固定配置/)).toBeVisible();
    // Task 42.2: an item that never came through the reviewed Manual Organize
    // journey shows the plan section as honestly 不可用 with its bounded
    // Chinese explanation, not as a silent blank or a false empty plan.
    expect(
      within(evidence).getByRole("heading", {
        name: "持久审核计划(不可用)",
      }),
    ).toBeVisible();
    expect(
      within(evidence).getByText(/没有可展示的持久审核计划/),
    ).toBeVisible();
    // The URL carries the inspected item in the URL so refresh/history/reconnect restore it.
    expect(router.history.location.search).toContain("item=item-2");

    await user.click(
      within(evidence).getByRole("button", { name: "关闭证据" }),
    );
    await waitFor(() =>
      expect(screen.queryByText("条目证据:item-2")).toBeNull(),
    );
  });

  it("renders the durable reviewed plan, effects and section detail for a manually executed item", async () => {
    const user = userEvent.setup();
    stubDetailJourney();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    const inspectButtons = within(detail).getAllByRole("button", {
      name: "查看证据",
    });
    await user.click(inspectButtons[0]);
    const evidence = await within(detail).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("条目证据:item-1");

    // The captured reviewed plan is stated up front, then explained.
    expect(
      within(evidence).getByRole("heading", {
        name: "持久审核计划(已捕获)",
      }),
    ).toBeVisible();
    expect(within(evidence).getByText("识别类型")).toBeVisible();
    // RecognitionType C survives the A naming/classification policies here too.
    const recognitionRow = within(evidence)
      .getByText("识别类型")
      .closest("div");
    expect(within(recognitionRow as HTMLElement).getByText("C")).toBeVisible();
    expect(
      within(evidence).getByText(/Naming A · Classification A · Organize A/),
    ).toBeVisible();
    expect(within(evidence).getByText(/Metadata C · Naming A/)).toBeVisible();
    expect(
      within(evidence).getByText(/tmdb \/ 101 · One · movie/),
    ).toBeVisible();
    expect(within(evidence).getByText(/title=One · year=2001/)).toBeVisible();
    expect(
      within(evidence).getByText(/recognized · 规则 movie-year/),
    ).toBeVisible();
    expect(
      within(evidence).getByText(/matched · 匹配分 .* · 候选 1/),
    ).toBeVisible();
    expect(
      within(evidence).getByText(
        /preview preview-1 · execution exec-1 · 持久状态 success/,
      ),
    ).toBeVisible();
    expect(
      within(evidence).getByText("target:Movies/One (2001)/One (2001).mkv"),
    ).toBeVisible();
    expect(within(evidence).getAllByText("无").length).toBeGreaterThan(0);
    expect(
      within(evidence).getByText(
        /模式 empty_only · 匹配 1 项 · 阻塞 0 项 · 预期 remove_empty/,
      ),
    ).toBeVisible();
    expect(within(evidence).getByText("执行步骤(持久)")).toBeVisible();
    expect(within(evidence).getByText("CREATE_DIRECTORY、MOVE")).toBeVisible();
    expect(within(evidence).getByText("已验证")).toBeVisible();
    // "已验证完成" appears both in the top checkpoint facts and in the durable
    // step table; both must speak the same label.
    expect(within(evidence).getAllByText("已验证完成").length).toBeGreaterThan(
      1,
    );

    // The durable result row explains the cleanup outcome instead of leaving
    // the known `disabled` fact unknown.
    expect(
      within(evidence).getByText("未启用(本次执行没有获得源目录清理授权)"),
    ).toBeVisible();

    // Pipeline sections now show their captured bounded detail, not just a
    // name, and unavailable sections stay visible with their reason.
    expect(within(evidence).getByText(/operation=MOVE/)).toBeVisible();
    expect(
      within(evidence).getByText(/条目1: field=ext, value=mkv/),
    ).toBeVisible();
    expect(within(evidence).getByText(/警告: w/)).toBeVisible();
    expect(within(evidence).getByText("不可用段")).toBeVisible();
    expect(
      within(evidence).getByText(/metadata\(legacy evidence\)/),
    ).toBeVisible();
  });

  it("shows the durable completed steps of a non-Manual executed item", async () => {
    // The Task 42.2 P1 regression: a standalone processing-chain item has no
    // reviewed Manual plan linkage, so 查看证据 used to hide its persisted
    // CREATE_DIRECTORY/MOVE steps behind "—".  The same bounded read must now
    // state the completed and unconfirmed steps from the durable
    // checkpoint/Result rows, keep the genuinely absent reviewed plan
    // explicitly unavailable, and never recompute anything.
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.includes("/items/item-9")) {
        return jsonResponse(standaloneExecutionEvidenceDocument());
      }
      if (url.includes("/items?") || url.endsWith("/items")) {
        return jsonResponse(itemsPageDocument({ items: [itemRow()] }));
      }
      if (url.includes("/records")) {
        return jsonResponse(recordsPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&item=item-9");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    const evidence = await within(detail).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("条目证据:item-9");

    // The reviewed-plan section keeps its honest unavailability…
    expect(
      within(evidence).getByRole("heading", {
        name: "持久审核计划(不可用)",
      }),
    ).toBeVisible();
    expect(
      within(evidence).getByText(/没有可展示的持久审核计划/),
    ).toBeVisible();
    // …while the durable execution steps now appear right beneath it.
    expect(
      within(evidence).getByText("持久执行步骤(检查点与结果聚合)"),
    ).toBeVisible();
    const completedRow = within(evidence)
      .getByText("已完成操作")
      .closest("div");
    expect(
      within(completedRow as HTMLElement).getByText("CREATE_DIRECTORY、MOVE"),
    ).toBeVisible();
    // The Result table states each row's own persisted steps and effects —
    // including the second, uncertain result — not just the aggregate.
    expect(
      within(evidence).getByText(/步: CREATE_DIRECTORY、MOVE/),
    ).toBeVisible();
    expect(
      within(evidence).getByText(/步: copy_written、destination_verified/),
    ).toBeVisible();
    expect(within(evidence).getByText("source_deletion")).toBeVisible();
    // The captured operation section renders its bounded lists instead of
    // collapsing arrays to "—" (the exact strings B observed as `—`).
    expect(
      within(evidence).getByText(
        /createdDirectories=Movies\/Anime\/Two \(2002\)/,
      ),
    ).toBeVisible();
    expect(
      within(evidence).getByText(/uncertainEffects=source_deletion/),
    ).toBeVisible();
  });

  it("downloads the eligible bounded result package and labels a truncated export", async () => {
    const user = userEvent.setup();
    stubDetailJourney();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    const exportButton = await within(detail).findByRole("button", {
      name: "导出结果 JSON",
    });
    await user.click(exportButton);

    const success = await screen.findByRole("heading", {
      name: "导出完成",
    });
    expect(success).toBeVisible();
    expect(screen.getByText(/已导出 1 条结果的完整结果包/)).toBeVisible();
  });

  it("keeps a failed export visible instead of an empty successful download", async () => {
    const user = userEvent.setup();
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items")) {
        return jsonResponse(itemsPageDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/export")) {
        return jsonResponse(
          { error: { code: "task_not_linked", message: "no task yet" } },
          409,
        );
      }
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse({
          items: [overviewDocument()],
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
          population: "unified job/task run inventory",
          sideEffects: "none",
          previous_cursor: null,
          next_cursor: null,
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    const exportButton = await within(detail).findByRole("button", {
      name: "导出结果 JSON",
    });
    await user.click(exportButton);
    const failure = await screen.findByRole("heading", { name: "导出失败" });
    expect(failure).toBeVisible();
    expect(screen.getByText(/未生成任何文件|暂无可导出/)).toBeVisible();
    expect(screen.queryByRole("heading", { name: "导出完成" })).toBeNull();
  });

  it("renders distinct bounded failures for forbidden and not-found detail reads", async () => {
    const requested: string[] = [];
    stubFetch(async (input) => {
      requested.push(String(input));
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse({ error: { code: "forbidden" } }, 403);
      }
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse({
          items: [overviewDocument()],
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
          population: "unified job/task run inventory",
          sideEffects: "none",
          previous_cursor: null,
          next_cursor: null,
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    expect(
      await screen.findByText(
        "The connected API principal does not have permission to view this area.",
      ),
    ).toBeVisible();
  });

  it("admits only GET requests while the detail journey runs", async () => {
    const user = userEvent.setup();
    const requested: { method: string; url: string }[] = [];
    stubFetch(async (input, init) => {
      const url = String(input);
      requested.push({
        method: init?.method ?? "GET",
        url,
      });
      return stubDetailJourneyResponse(url);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("region", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      await within(detail).findByRole("button", { name: "操作记录" }),
    );
    await screen.findByText(/匹配 4 条记录/);

    expect(requested.length).toBeGreaterThan(0);
    for (const call of requested) {
      expect(call.method).toBe("GET");
      expect(call.url.startsWith("/api/")).toBe(true);
    }
  });
});

/** Split out so the GET-only test can reuse the full stub's responses. */
function stubDetailJourneyResponse(url: string): Response {
  const notFound = jsonResponse({ error: { code: "not_found" } }, 404);
  if (url.startsWith("/api/v1/operations/runs?")) {
    return jsonResponse({
      items: [overviewDocument()],
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
      population: "unified job/task run inventory",
      sideEffects: "none",
      previous_cursor: null,
      next_cursor: null,
    });
  }
  if (url === "/api/v1/operations/runs/task-001") {
    return jsonResponse(overviewDocument());
  }
  if (url.startsWith("/api/v1/operations/runs/task-001/items/item-2")) {
    return jsonResponse(evidenceDocument());
  }
  if (url.startsWith("/api/v1/operations/runs/task-001/items/item-1")) {
    return jsonResponse(manualExecutionEvidenceDocument());
  }
  if (url.startsWith("/api/v1/operations/runs/task-001/items")) {
    return jsonResponse(itemsPageDocument());
  }
  if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
    return jsonResponse(recordsPageDocument());
  }
  if (url === "/api/v1/workers/readiness") {
    return jsonResponse({
      ready: true,
      condition: "ready",
      category: null,
      durableState: "resident processing worker is live and ready",
      sideEffects: "none",
      retrySafe: true,
      nextAction: "none",
      activeWorkersCount: 1,
      activeSnapshotId: "snap-1",
      expectedRuntimeSchemaVersion: 42,
    });
  }
  if (url === "/api/v1/management/readiness") {
    return jsonResponse({
      available: true,
      infrastructureReady: true,
      asOf: "2026-08-22T12:00:00+00:00",
      sideEffects: "none",
      infrastructure: { services: {} },
    });
  }
  if (url.startsWith("/api/v1/operations/manual-actions")) {
    return jsonResponse({
      scopeKind: null,
      scopeId: null,
      fileId: null,
      resourceLibraryId: null,
      selectionRequired: true,
      source: null,
      resourceLibraries: [],
      runtime: { ready: true, condition: "ready", nextAction: null },
      actions: {
        scan: { available: false, reason: "not advertised" },
        preview: { available: false, reason: "not advertised" },
        organize: { available: false, reason: "not advertised" },
      },
      limits: { previewMaxItems: 100 },
    });
  }
  return notFound;
}
