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
import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../../tests/utils";
import { authStore } from "../../shared/api/auth-store";
import manualOperationsFixture from "../../entities/operations/__fixtures__/manual-operations.json";

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
  vi.restoreAllMocks();
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
    completed_items: 3,
    failed_items: 2,
    processed_items: 3,
    success_items: 1,
    partial_items: 1,
    uncertain_effect_items: 1,
    missing_result_items: 1,
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
          identity: {
            provider: "tmdb",
            providerId: "101",
            mediaType: "movie",
            title: "One",
            year: 2001,
          },
          match: {
            status: "matched",
            score: 100,
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
          relativePath: "Anime",
          matchedRuleId: "anime-movie",
          matchedRuleName: "Japanese Animation",
          evidence: ["media_type=movie", "genre=Animation", "country=JP"],
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

/** One exact native item recovery the evidence panel reads below. */
function recognitionRecoveryDocument(overrides: Record<string, unknown> = {}) {
  return {
    task_id: "task-001",
    item_id: "item-2",
    checkpoint: {
      status: "pending",
      stage: "queued",
      raw_stage: "recognition_resolved",
      effects: { certainty: "none" },
      retry_safety: "safe",
      checkpoint_version: "b".repeat(64),
      blocker: null,
      permitted_action_ids: [],
      refusal_reason: null,
      next_action: "inspect the current item state",
    },
    decision: null,
    native_analysis: {
      task_id: "task-001",
      item_id: "item-2",
      readable: true,
      queue_state: "waiting_human",
      machine_stage: null,
    },
    manualRecoveryAvailable: false,
    recoveryKind: "business_problem",
    next_action: "inspect the current item state",
    ...overrides,
  };
}

/** The same item before its recognition decision was saved. */
function pendingRecognitionRecoveryDocument(): Record<string, unknown> {
  return recognitionRecoveryDocument({
    checkpoint: {
      status: "waiting_recognition",
      stage: "waiting_recognition",
      raw_stage: "waiting_recognition",
      effects: { certainty: "none" },
      retry_safety: "unsafe",
      checkpoint_version: "b".repeat(64),
      blocker: { kind: "recognition", blocker_id: "review-1" },
      permitted_action_ids: ["resolve_recognition", "ignore"],
      refusal_reason: null,
      next_action: "choose a RecognitionType",
    },
    decision: {
      kind: "recognition",
      review_id: "review-1",
      status: "pending",
      choices: [
        {
          recognition_type_id: "C",
          name: "Special",
          description: "Keep RecognitionType C",
        },
      ],
    },
    next_action: "choose a RecognitionType",
  });
}

/** The exact same waiting item with a metadata-correction decision form. */
function metadataCorrectionRecoveryDocument(): Record<string, unknown> {
  return {
    task_id: "task-001",
    item_id: "item-2",
    checkpoint: {
      status: "waiting_metadata_correction",
      stage: "waiting_metadata_correction",
      raw_stage: "waiting_metadata_correction",
      effects: { certainty: "none" },
      retry_safety: "unsafe",
      checkpoint_version: "c".repeat(64),
      blocker: { kind: "metadata_correction", blocker_id: "correction-1" },
      permitted_action_ids: ["resolve_metadata_correction", "ignore"],
      refusal_reason: null,
      next_action: "correct the metadata search",
    },
    decision: {
      kind: "metadata_correction",
      review_id: "correction-1",
      status: "pending",
      query: "Movie.01",
      year: 2001,
      media_type: "movie",
      can_search: true,
      choices: [],
      allowed_strategies: [],
      conflict_types: [],
    },
    manualRecoveryAvailable: false,
    recoveryKind: "business_problem",
    next_action: "correct the metadata search",
  };
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

/** The same-page plan Preview that a prepared recovery summary reads here. */
function recoveryPreviewDocument(): Record<string, unknown> {
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
  const actions = preview["actions"] as Record<string, Record<string, unknown>>;
  actions["execute"]!["path"] =
    "/api/v1/operations/organize/previews/preview-1/execute";
  return preview;
}

/** The analyzed item whose zero-change summary waits for an explicit confirm. */
function manualReadyRecoveryDocument(
  preparation: Record<string, unknown> | null,
): Record<string, unknown> {
  return recognitionRecoveryDocument({
    checkpoint: {
      status: "pending",
      stage: "queued",
      raw_stage: "recognition_resolved",
      effects: { certainty: "none" },
      retry_safety: "safe",
      checkpoint_version: "b".repeat(64),
      blocker: null,
      permitted_action_ids: [],
      refusal_reason: null,
      next_action: "review the current plan summary and confirm",
      recovery_continuation: {
        status: "completed",
        new_task_id: "analysis-task-1",
        new_item_id: "analysis-item-1",
        new_result_id: "analysis-result-1",
      },
    },
    decision: null,
    manualRecoveryAvailable: true,
    manualRecoveryPreparation: preparation,
    next_action: "review the current plan summary and confirm",
  });
}

function preparedSummaryDocument(status: "prepared" | "confirmed") {
  return {
    preparation_id: "preparation-1",
    status,
    preview_id: "preview-1",
    intent_id: "intent-1",
    source_task_id: "task-001",
    source_item_id: "item-2",
    checkpoint_version: "b".repeat(64),
    configuration_snapshot_id: "snap-1",
    configuration_snapshot_digest: "d".repeat(64),
    actor: "test-principal",
    authorization_id: status === "confirmed" ? "authorization-1" : null,
    execution_id: status === "confirmed" ? "execution-1" : null,
    selected_item_ids: status === "confirmed" ? ["item-2"] : [],
    allow_overwrite: false,
    allow_source_cleanup: false,
    hasExecutionAuthority: false,
    next_action: "review the current plan summary and confirm",
  };
}

interface DetailJourneyOptions {
  /** One exact item-1 evidence document, when a test needs a specific result. */
  readonly evidenceItem1?: unknown;
  /** The exact native recovery read of item-1, when a test drives it. */
  readonly recoveryItem1?: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Promise<Response>;
  /** The exact native recovery reads/commands of item-2, when a test drives
   * them.  Without it the existing 404 fallback is unchanged. */
  readonly recovery?: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Promise<Response>;
  /** The same-page plan-summary read/confirm endpoints (the fixed Preview
   * GET and the manual-recovery-preparation confirm POST), when a test drives
   * the same-page confirmation after a prepared summary. */
  readonly planSummary?: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Promise<Response>;
}

/** One fetch stub covering the whole selected-run detail journey. */
function stubDetailJourney(
  requested: string[] = [],
  options: DetailJourneyOptions = {},
) {
  return stubFetch(async (input, init) => {
    const url = String(input);
    requested.push(url);
    if (url === "/api/v1/auth/principal") {
      return jsonResponse({ principal_id: "test-principal" });
    }
    if (url.startsWith("/api/v1/tasks/task-001/items/item-1/recovery")) {
      if (options.recoveryItem1 !== undefined) {
        return options.recoveryItem1(input, init);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    }
    if (url.startsWith("/api/v1/tasks/task-001/items/item-2/recovery")) {
      if (options.recovery !== undefined) {
        return options.recovery(input, init);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    }
    if (
      url.startsWith("/api/v1/operations/organize/previews/") ||
      url.startsWith("/api/v1/manual-recovery-preparations/")
    ) {
      if (options.planSummary !== undefined) {
        return options.planSummary(input, init);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
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
    if (url === "/api/v1/operations/runs/task-001") {
      return jsonResponse(overviewDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/items/item-2")) {
      return jsonResponse(evidenceDocument());
    }
    if (url.startsWith("/api/v1/operations/runs/task-001/items/item-1")) {
      return jsonResponse(
        options.evidenceItem1 ?? manualExecutionEvidenceDocument(),
      );
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

async function findInlineEvidence(detail: HTMLElement) {
  await waitFor(() => {
    const region = within(detail).getByRole("region", { name: "条目证据" });
    expect(region.closest("table")).not.toBeNull();
  });
  return within(detail).getByRole("region", { name: "条目证据" });
}

describe("selected-run detail tabs", () => {
  it("renders the item table with its reading-area column hooks (B50.2-03)", async () => {
    stubDetailJourney();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const items = await within(detail).findByRole("region", { name: "主条目" });
    await within(items).findByText(/source:movies\/a.mkv/);
    // The detail card's fixed-layout table assigns each of the eight item
    // columns its own reading area; these classes are the CSS hooks that keep
    // a long source path inside the source column instead of painting over
    // the status/stage neighbors (B50.2-03). The geometry itself is proved
    // against the real browser in task-center-layout.spec.ts.
    for (const className of [
      "mf-run-item-col-source",
      "mf-run-item-col-status",
      "mf-run-item-col-stage",
      "mf-run-item-col-attempts",
      "mf-run-item-col-target",
      "mf-run-item-col-failure",
      "mf-run-item-col-actions",
      "mf-run-item-col-batch",
    ]) {
      expect(
        document.querySelector(`.mf-run-detail-card th.${className}`),
      ).not.toBeNull();
    }
  });
  it("reads flow status, processed range and independent file results without standing tutorials", async () => {
    stubDetailJourney();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    // The first block answers where the flow is; the processed range follows;
    // the independent file outcomes come after it.
    const flow = await within(detail).findByRole("region", {
      name: "状态与流程",
    });
    expect(within(flow).getByText("流程状态")).toBeVisible();
    const progress = await within(detail).findByRole("region", {
      name: "处理进度",
    });
    expect(within(progress).getByText(/已处理 3 \/ 4 个主条目/)).toBeVisible();
    const results = await within(detail).findByRole("region", {
      name: "文件结果",
    });
    expect(within(results).getByText("成功")).toBeVisible();
    expect(within(results).getByText("部分成功")).toBeVisible();
    expect(within(results).getByText("失败")).toBeVisible();
    expect(
      within(results).getByText(/目标文件结果尚未确认 1 个/),
    ).toBeVisible();
    expect(
      within(results).getByText(/文件处理已结束，结果未记录 1 个/),
    ).toBeVisible();
    // The removed standing explanations stay gone; the remaining text states
    // facts, not the accounting rules behind them.
    expect(within(detail).queryByText(/口径:/)).toBeNull();
    expect(within(detail).queryByText(/成功含义:/)).toBeNull();
    expect(within(detail).queryByText(/非成功率/)).toBeNull();
    expect(within(detail).queryByText(/单独计数/)).toBeNull();
    expect(within(detail).queryByText(/不代表整理成功/)).toBeNull();
    // The tabs the reference promises.
    expect(
      within(detail).getByRole("button", { name: "任务详情" }),
    ).toBeVisible();
    expect(
      within(detail).getByRole("button", { name: "操作记录" }),
    ).toBeVisible();
  });

  it("PATCH-20261107-1 keeps flow, processed range and independent file results in reading order", async () => {
    stubDetailJourney();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const flow = await within(detail).findByRole("region", {
      name: "状态与流程",
    });
    const progress = await within(detail).findByRole("region", {
      name: "处理进度",
    });
    const results = await within(detail).findByRole("region", {
      name: "文件结果",
    });
    await within(results).findByText("成功");
    // The first screen reads top-down: flow state, processed range, then the
    // independent file outcomes.
    expect(
      flow.compareDocumentPosition(progress) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      progress.compareDocumentPosition(results) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // Completed flow plus a mixed file population is stated directly, with no
    // tutorial paragraph re-explaining the numbers.
    expect(within(results).getByText("部分成功")).toBeVisible();
    expect(within(results).getByText("失败")).toBeVisible();
    expect(
      within(results).getByText(/目标文件结果尚未确认 1 个/),
    ).toBeVisible();
    expect(
      within(results).getByText(/文件处理已结束，结果未记录 1 个/),
    ).toBeVisible();
    expect(
      within(detail).queryByText(/口径:|成功含义:|非成功率|单独计数/),
    ).toBeNull();
  });

  it("PATCH-20261107-1 keeps a successful main file and a failed subtitle as independent results", async () => {
    const withAttachment = manualExecutionEvidenceDocument({
      results: [
        evidenceResultRow({
          primary_completed: true,
          attachment_results: [
            {
              type: "subtitle",
              language: "zh",
              operation: "copy",
              status: "failed",
              reason: "verification_failed",
              source_storage_id: "source",
              source_path: "movies/a.zh.srt",
              destination_storage_id: "target",
              destination_path: "Movies/a.zh.srt",
              effect_certainty: "attempted_unverified",
              completed_operations: ["copy_written"],
              next_action: "verify the subtitle target before retrying",
            },
          ],
        }),
      ],
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items/item-1")) {
        return jsonResponse(withAttachment);
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return jsonResponse(itemsPageDocument({ items: [itemRow()] }));
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&item=item-1");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const evidence = await findInlineEvidence(detail);
    await within(evidence).findByText("文件证据：a.mkv");
    // The file's own result is readable first…
    expect(within(evidence).getByText("文件已整理")).toBeVisible();
    // …and the main file and subtitle keep separate outcomes.
    expect(
      within(evidence).getByText("主文件已完成；附件有警告"),
    ).toBeVisible();
    expect(within(evidence).getByText(/subtitle（zh）/)).toBeVisible();
    expect(within(evidence).getByText(/附件效果尚未验证/)).toBeVisible();
    // The removed tutorial copy stays out of the readable body.
    expect(within(evidence).queryByText(/口径|成功含义|非成功率/)).toBeNull();
  });

  it("PATCH-20261107-1 distinguishes an unconfirmed target from an ended attempt without a result", async () => {
    const unknown = manualExecutionEvidenceDocument();
    // A persisted Result whose Storage effect is still unverified: the file
    // is not presented as confirmed success.
    (
      unknown as { checkpoint: { effects: { certainty: string } } }
    ).checkpoint.effects.certainty = "attempted_unverified";
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items/item-1")) {
        return jsonResponse(unknown);
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return jsonResponse(itemsPageDocument({ items: [itemRow()] }));
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&item=item-1");
    let detail = await screen.findByRole("dialog", { name: "运行详情" });
    let evidence = await findInlineEvidence(detail);
    await within(evidence).findByText("文件证据：a.mkv");
    expect(within(evidence).getByText("目标文件结果尚未确认")).toBeVisible();

    cleanup();
    const missing = manualExecutionEvidenceDocument({ results: [] });
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument({ status: "completed" }));
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items/item-1")) {
        return jsonResponse(missing);
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return jsonResponse(itemsPageDocument({ items: [itemRow()] }));
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    renderApp("/ui-v2/operations?run=task-001&item=item-1");
    detail = await screen.findByRole("dialog", { name: "运行详情" });
    evidence = await findInlineEvidence(detail);
    await within(evidence).findByText("文件证据：a.mkv");
    // A settled attempt with no Result row is not backfilled into a success.
    expect(
      within(evidence).getByText("文件处理已结束，结果未记录"),
    ).toBeVisible();
    // The missing-result truth and the checkpoint's known steps stay in the
    // file's one execution history instead of a fabricated result.
    expect(
      within(evidence).getByText("该文件还没有持久执行结果。"),
    ).toBeVisible();
    expect(within(evidence).getByText("已完成：移动（MOVE）")).toBeVisible();
  });

  it("keeps failure-record and checkpoint next steps distinguishable in the one diagnostics entry", async () => {
    const failedItem = itemRow({
      status: "failed",
      failure: {
        category: "storage_failure",
        message: "the destination write did not commit",
        durableState: "destination unchanged",
        sideEffects: "none",
        retrySafe: true,
        nextAction: "verify the destination storage",
      },
    });
    const renderFailedEvidence = async (
      document: ReturnType<typeof manualExecutionEvidenceDocument>,
    ) => {
      stubFetch(async (input) => {
        const url = String(input);
        if (url.startsWith("/api/v1/operations/runs/task-001/items/item-1")) {
          return jsonResponse(document);
        }
        return stubDetailJourneyResponse(url);
      });
      authStore.setToken(TOKEN);
      renderApp("/ui-v2/operations?run=task-001&item=item-1");
      const detail = await screen.findByRole("dialog", { name: "运行详情" });
      const evidence = await findInlineEvidence(detail);
      await within(evidence).findByText("文件证据：a.mkv");
      return evidence;
    };

    const different = manualExecutionEvidenceDocument({ item: failedItem });
    (different.checkpoint as { nextAction: string | null }).nextAction =
      "check the pinned snapshot before continuing";
    const differentEvidence = await renderFailedEvidence(different);
    // The current conclusion, its central reason and the raw checkpoint stay
    // in their own levels of the same file evidence.
    expect(within(differentEvidence).getByText("处理失败")).toBeVisible();
    expect(
      within(differentEvidence).getByText("存储操作未完成。"),
    ).toBeVisible();
    await userEvent
      .setup()
      .click(
        within(differentEvidence).getByText(
          /技术诊断（检查点、计划、日志与审计/,
        ),
      );
    // Same-kind fields from different sources stay distinguishable instead
    // of collapsing into one ambiguous 服务下一步.
    expect(
      within(differentEvidence).getByText("服务下一步（失败记录）"),
    ).toBeVisible();
    expect(
      within(differentEvidence).getByText("服务下一步（检查点）"),
    ).toBeVisible();
    expect(
      within(differentEvidence).getByText("verify the destination storage"),
    ).toBeVisible();
    expect(
      within(differentEvidence).getByText(
        "check the pinned snapshot before continuing",
      ),
    ).toBeVisible();

    cleanup();
    // The checkpoint's next action is the same durable failure's projection:
    // an identical value is one fact, not two next steps.
    const shared = manualExecutionEvidenceDocument({ item: failedItem });
    (shared.checkpoint as { nextAction: string | null }).nextAction =
      "verify the destination storage";
    const sharedEvidence = await renderFailedEvidence(shared);
    await userEvent
      .setup()
      .click(
        within(sharedEvidence).getByText(/技术诊断（检查点、计划、日志与审计/),
      );
    expect(
      within(sharedEvidence).getByText("服务下一步（失败记录与检查点一致）"),
    ).toBeVisible();
    expect(
      within(sharedEvidence).queryByText("服务下一步（失败记录）"),
    ).toBeNull();
    expect(
      within(sharedEvidence).queryByText("服务下一步（检查点）"),
    ).toBeNull();
    expect(
      within(sharedEvidence).getAllByText("verify the destination storage"),
    ).toHaveLength(1);

    cleanup();
    // Only the item's failure carries guidance: keep its exact source label.
    const failureOnly = manualExecutionEvidenceDocument({ item: failedItem });
    const failureOnlyEvidence = await renderFailedEvidence(failureOnly);
    await userEvent
      .setup()
      .click(
        within(failureOnlyEvidence).getByText(
          /技术诊断（检查点、计划、日志与审计/,
        ),
      );
    expect(
      within(failureOnlyEvidence).getByText("服务下一步（失败记录）"),
    ).toBeVisible();
    expect(
      within(failureOnlyEvidence).queryByText("服务下一步（检查点）"),
    ).toBeNull();
    expect(
      within(failureOnlyEvidence).getByText("verify the destination storage"),
    ).toBeVisible();

    cleanup();
    // Only the checkpoint carries guidance: do not borrow the failure label.
    const checkpointOnly = manualExecutionEvidenceDocument({
      item: itemRow({ status: "failed" }),
    });
    (checkpointOnly.checkpoint as { nextAction: string | null }).nextAction =
      "inspect the exact checkpoint";
    const checkpointOnlyEvidence = await renderFailedEvidence(checkpointOnly);
    await userEvent
      .setup()
      .click(
        within(checkpointOnlyEvidence).getByText(
          /技术诊断（检查点、计划、日志与审计/,
        ),
      );
    expect(
      within(checkpointOnlyEvidence).queryByText("服务下一步（失败记录）"),
    ).toBeNull();
    expect(
      within(checkpointOnlyEvidence).getByText("服务下一步（检查点）"),
    ).toBeVisible();
    expect(
      within(checkpointOnlyEvidence).getByText("inspect the exact checkpoint"),
    ).toBeVisible();
  });

  it("PATCH-20261107-1 explains a successful file in business terms and keeps terminal refusal in diagnostics", async () => {
    const user = userEvent.setup();
    const success = manualExecutionEvidenceDocument({
      results: [evidenceResultRow({ status: "SUCCESS" })],
    });
    (success.checkpoint as Record<string, unknown>)["refusal_reason"] =
      "replay_not_offered: item has a terminal outcome";
    const successRecovery = {
      task_id: "task-001",
      item_id: "item-1",
      checkpoint: {
        status: "success",
        stage: "completed",
        raw_stage: "completed",
        effects: { certainty: "verified_complete" },
        retry_safety: "unsafe",
        checkpoint_version: "a".repeat(64),
        blocker: null,
        permitted_action_ids: [],
        refusal_reason: "replay_not_offered: item has a terminal outcome",
        next_action: null,
      },
      decision: null,
      manualRecoveryAvailable: false,
      recoveryKind: "technical_history",
      next_action: "none",
    };
    stubDetailJourney([], {
      evidenceItem1: success,
      recoveryItem1: async () => jsonResponse(successRecovery),
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&item=item-1");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const evidence = await findInlineEvidence(detail);
    await within(evidence).findByText("文件证据：a.mkv");
    expect(within(evidence).getByText("文件已整理")).toBeVisible();
    // The real API returns an uppercase SUCCESS status; it reads as the same
    // business fact as the lowercase item status, inside the file's one
    // merged execution history.
    expect(within(evidence).getByText(/执行记录 1（.*）：成功/)).toBeVisible();

    // Recognition, metadata, naming and classification are readable without
    // opening the raw plan or querying current configuration.
    expect(
      within(evidence).getByText("从文件名识别为《One》 (2001)；识别类型 C"),
    ).toBeVisible();
    expect(
      within(evidence).getByText(
        "匹配 tmdb #101，One (2001)，电影，匹配分 100",
      ),
    ).toBeVisible();
    expect(
      within(evidence).getByText("目录 One (2001)；文件名 One (2001).mkv"),
    ).toBeVisible();
    expect(
      within(evidence).getByText(
        "媒体库 movies，相对路径 Anime；规则 Japanese Animation（anime-movie）命中；依据 媒体类型 电影、类型 Animation、国家/地区 JP",
      ),
    ).toBeVisible();

    // A completed successful technical-history file renders no 审核与恢复
    // area in the evidence host: no no-op conclusion and no empty region.
    // The recovery read still happened; the settled facts live in the body
    // and the one unified diagnostics entry.
    await waitFor(() =>
      expect(
        within(evidence).queryByRole("region", { name: "条目审核与恢复" }),
      ).toBeNull(),
    );
    expect(within(evidence).queryByText(/没有待处理操作/)).toBeNull();
    expect(within(evidence).queryByText(/技术失败条目/)).toBeNull();
    expect(within(evidence).queryByText(/需处理原因/)).toBeNull();

    // The terminal refusal and the raw entry/checkpoint stay in the single
    // collapsed technical diagnostics, not in the primary body.
    await user.click(
      within(evidence).getByText(/技术诊断（检查点、计划、日志与审计/),
    );
    expect(
      await within(evidence).findByText(/已结束的条目不再提供重放/),
    ).toBeVisible();
    expect(
      within(evidence).getByText(
        /replay_not_offered: item has a terminal outcome/,
      ),
    ).toBeVisible();
    expect(within(evidence).getByText("safe")).toBeVisible();
    expect(within(evidence).getByText("verified_complete")).toBeVisible();
    expect(within(evidence).getByText("1 次")).toBeVisible();
    expect(within(evidence).getByText("可用操作标识")).toBeVisible();
  });

  it("submits the item disposition filter to the server and keeps the population totals", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubDetailJourney(requested);
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);

    // The unfiltered read states one population count, not two equal numbers.
    expect(await screen.findByText(/共 4 条/)).toBeVisible();
    const statusSelect = screen.getByLabelText("状态筛选");
    expect(
      within(statusSelect).getByRole("option", { name: "全部状态" }),
    ).toBeVisible();
    expect(
      within(statusSelect).queryByRole("option", { name: /服务器筛选/ }),
    ).toBeNull();

    await user.selectOptions(screen.getByLabelText("状态筛选"), "waiting");
    await waitFor(() =>
      expect(requested.some((url) => url.includes("status=waiting"))).toBe(
        true,
      ),
    );
    // The filter narrows the page; the count names both the matches and the
    // whole-run population.
    expect(await screen.findByText(/匹配 1 \/ 共 4 条/)).toBeVisible();
    expect(await screen.findByText(/movies\/b\.mkv/)).toBeVisible();
    // The filter state is in the URL so refresh/history/reconnect restore it.
    const detailRequest = requested.find((url) =>
      url.includes("status=waiting"),
    );
    expect(detailRequest).toContain("/api/v1/operations/runs/task-001/items");
  });

  it("PATCH-20261111-4 keeps the same file's unsaved title across an item filter change", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubDetailJourney(requested, {
      recovery: async (_input, init) =>
        (init?.method ?? "GET") === "GET"
          ? jsonResponse(metadataCorrectionRecoveryDocument())
          : jsonResponse({ error: { code: "not_found" } }, 404),
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      within(detail).getAllByRole("button", { name: "查看证据" })[1]!,
    );
    const recovery = await within(detail).findByRole("region", {
      name: "条目审核与恢复",
    });
    const title = await within(recovery).findByLabelText("搜索标题");
    expect(title).toHaveValue("Movie.01");
    await user.clear(title);
    await user.type(title, "Operator edited metadata title");
    expect(title).toHaveValue("Operator edited metadata title");

    await user.selectOptions(screen.getByLabelText("状态筛选"), "waiting");
    await waitFor(() =>
      expect(requested.some((url) => url.includes("status=waiting"))).toBe(
        true,
      ),
    );
    // The filtered server page still contains this exact file, so the panel
    // moves back under its own row without dropping the unsaved title.
    const inline = await findInlineEvidence(detail);
    expect(inline.closest("tr")!.previousElementSibling).toHaveTextContent(
      "movies/b.mkv",
    );
    expect(within(inline).getByLabelText("搜索标题")).toHaveValue(
      "Operator edited metadata title",
    );
    expect(
      within(detail).getAllByRole("region", { name: "条目证据" }),
    ).toHaveLength(1);
  });

  it("switches to 操作记录 with its server page and kind filter", async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    stubDetailJourney(requested);
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await user.click(
      await within(detail).findByRole("button", { name: "操作记录" }),
    );
    expect(await screen.findByLabelText("操作记录")).toBeVisible();
    expect(await screen.findByText(/organizer.execution_result/)).toBeVisible();
    // The tab name is not repeated as a visible heading, the default option
    // is plain, and the unfiltered count is one population total plus the
    // backend kind counts without the standing server tutorial.
    expect(
      within(detail).queryByRole("heading", { name: "操作记录" }),
    ).toBeNull();
    expect(within(detail).queryByText(/服务器分页/)).toBeNull();
    const kindSelect = screen.getByLabelText("类型筛选");
    expect(
      within(kindSelect).getByRole("option", { name: "全部类型" }),
    ).toBeVisible();
    expect(
      within(kindSelect).queryByRole("option", { name: /服务器筛选/ }),
    ).toBeNull();
    expect(
      screen.getByText(/共 4 条记录 · 结果 3 · 证据 1 · 日志 0 · 审计 0/),
    ).toBeVisible();

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

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    const inspectButtons = within(detail).getAllByRole("button", {
      name: "查看证据",
    });
    await user.click(inspectButtons[1]);
    const evidence = await within(detail).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("文件证据：b.mkv");
    // The readable body names the concrete blocker and the file's own result
    // instead of surfacing the raw review tokens as the primary facts.
    expect(within(evidence).getByText(/当前阻塞/)).toBeVisible();
    expect(within(evidence).getByText(/等待元数据决定/)).toBeVisible();
    // The technical next action, refusal token and fixed configuration stay
    // reachable inside the collapsed diagnostics instead of the readable body.
    await user.click(within(evidence).getByText(/技术诊断/));
    expect(within(evidence).getByText(/等待处理决定/)).toBeVisible();
    expect(
      within(evidence).getByText(/choose a metadata candidate/),
    ).toBeVisible();
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

  it("PATCH-20261111-4 places one evidence region under its own item and follows the selection", async () => {
    const user = userEvent.setup();
    const fetchMock = stubDetailJourney();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const items = await within(detail).findByRole("region", { name: "主条目" });
    const table = await within(items).findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    const firstRow = rows[1]!;
    const secondRow = rows[2]!;
    const firstTrigger = within(firstRow).getByRole("button", {
      name: "查看证据",
    });
    await user.click(firstTrigger);
    const firstEvidence = await within(items).findByRole("region", {
      name: "条目证据",
    });
    await within(firstEvidence).findByText("文件证据：a.mkv");
    const firstEvidenceRow = firstEvidence.closest("tr");
    expect(firstEvidenceRow).not.toBeNull();
    expect(firstEvidenceRow!.previousElementSibling).toBe(firstRow);
    expect(firstEvidenceRow!.children).toHaveLength(1);
    expect(firstEvidenceRow!.children[0]).toHaveAttribute("colspan", "8");
    expect(firstTrigger).toHaveAttribute("aria-expanded", "true");
    expect(firstTrigger).toHaveAttribute("aria-controls", firstEvidence.id);
    expect(
      within(items).getAllByRole("region", { name: "条目证据" }),
    ).toHaveLength(1);

    const secondTrigger = within(secondRow).getByRole("button", {
      name: "查看证据",
    });
    await user.click(secondTrigger);
    const secondEvidence = await within(items).findByRole("region", {
      name: "条目证据",
    });
    await within(secondEvidence).findByText("文件证据：b.mkv");
    const secondEvidenceRow = secondEvidence.closest("tr");
    expect(secondEvidenceRow).not.toBeNull();
    expect(secondEvidenceRow!.previousElementSibling).toBe(secondRow);
    expect(secondTrigger).toHaveAttribute("aria-expanded", "true");
    expect(firstTrigger).toHaveAttribute("aria-expanded", "false");
    expect(within(items).queryByText("文件证据：a.mkv")).toBeNull();
    expect(
      within(items).getAllByRole("region", { name: "条目证据" }),
    ).toHaveLength(1);

    await user.click(
      within(secondEvidence).getByRole("button", { name: "关闭证据" }),
    );
    await waitFor(() =>
      expect(
        within(items).queryByRole("region", { name: "条目证据" }),
      ).toBeNull(),
    );
    expect(secondTrigger).toHaveFocus();
    const writes = fetchMock.mock.calls.filter(
      ([, init]) =>
        ((init as RequestInit | undefined)?.method ?? "GET") !== "GET",
    );
    expect(writes).toHaveLength(0);
  });

  it("PATCH-20261111-4 keeps an exact off-page item evidence before the current page", async () => {
    const requested: string[] = [];
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items/item-9")) {
        return jsonResponse(standaloneExecutionEvidenceDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return jsonResponse(itemsPageDocument({ items: [itemRow()] }));
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&item=item-9");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const items = await within(detail).findByRole("region", { name: "主条目" });
    const table = await within(items).findByRole("table");
    const notice = await within(items).findByText(/所选条目不在当前列表页/);
    const evidence = await within(items).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("文件证据：standalone.mkv");
    expect(evidence.closest("table")).toBeNull();
    expect(
      evidence.compareDocumentPosition(table) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      notice.compareDocumentPosition(evidence) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(within(items).getAllByRole("row")).toHaveLength(2);
    expect(requested).toContain(
      "/api/v1/operations/runs/task-001/items/item-9",
    );
  });

  it("PATCH-20261111-4 keeps exact item evidence readable while the item page is loading", async () => {
    const requested: string[] = [];
    let releaseItems: ((response: Response) => void) | undefined;
    const itemsGate = new Promise<Response>((resolve) => {
      releaseItems = resolve;
    });
    stubFetch(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items/item-2")) {
        return jsonResponse(evidenceDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return itemsGate;
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&item=item-2");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const items = await within(detail).findByRole("region", { name: "主条目" });
    const evidence = await within(items).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("文件证据：b.mkv");
    expect(within(items).getByText(/条目列表正在加载/)).toBeVisible();
    expect(evidence.closest("table")).toBeNull();

    await act(async () => {
      releaseItems?.(jsonResponse(itemsPageDocument()));
    });
    const table = await within(items).findByRole("table");
    await waitFor(() => {
      const moved = within(items).getByRole("region", { name: "条目证据" });
      expect(moved.closest("table")).toBe(table);
      expect(within(moved).getByText("文件证据：b.mkv")).toBeVisible();
    });
    expect(
      within(items).getAllByRole("region", { name: "条目证据" }),
    ).toHaveLength(1);
  });

  it("PATCH-20261111-4 keeps exact item evidence when the item-list read fails", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items/item-2")) {
        return jsonResponse(evidenceDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return jsonResponse({ error: { code: "unavailable" } }, 503);
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001&item=item-2");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const items = await within(detail).findByRole("region", { name: "主条目" });
    const notice = await within(items).findByText(/条目列表暂不可用/);
    expect(notice).toBeVisible();
    const evidence = await within(items).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("文件证据：b.mkv");
    expect(evidence.closest("table")).toBeNull();
    expect(within(items).queryByRole("table")).toBeNull();
  });

  it("PATCH-20261111-4 ignores a late former item's evidence after the selection moved", async () => {
    const user = userEvent.setup();
    let releaseFormer: ((response: Response) => void) | undefined;
    const formerGate = new Promise<Response>((resolve) => {
      releaseFormer = resolve;
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items/item-1")) {
        return formerGate;
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items/item-2")) {
        return jsonResponse(evidenceDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return jsonResponse(itemsPageDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const items = await within(detail).findByRole("region", { name: "主条目" });
    const table = await within(items).findByRole("table");
    const rows = within(table).getAllByRole("row");
    await user.click(
      within(rows[1]!).getByRole("button", { name: "查看证据" }),
    );
    const loading = await within(items).findByRole("region", {
      name: "条目证据",
    });
    expect(within(loading).getByText(/正在加载条目证据/)).toBeVisible();

    await user.click(
      within(rows[2]!).getByRole("button", { name: "查看证据" }),
    );
    const current = await within(items).findByRole("region", {
      name: "条目证据",
    });
    await within(current).findByText("文件证据：b.mkv");
    await act(async () => {
      releaseFormer?.(jsonResponse(manualExecutionEvidenceDocument()));
    });
    await waitFor(() =>
      expect(within(current).queryByText("文件证据：a.mkv")).toBeNull(),
    );
    expect(within(current).getByText("文件证据：b.mkv")).toBeVisible();
    expect(current.closest("tr")!.previousElementSibling).toBe(rows[2]);
    expect(
      within(items).getAllByRole("region", { name: "条目证据" }),
    ).toHaveLength(1);
  });

  it("keeps an in-flight native decision waiting across card close and reopen", async () => {
    const user = userEvent.setup();
    let current = pendingRecognitionRecoveryDocument();
    let decisionPosts = 0;
    let releaseDecision: ((response: Response) => void) | undefined;
    const decisionGate = new Promise<Response>((resolve) => {
      releaseDecision = resolve;
    });
    stubDetailJourney([], {
      recovery: async (_input, init) => {
        if ((init?.method ?? "GET") === "GET") {
          return jsonResponse(current);
        }
        decisionPosts += 1;
        return decisionGate;
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(
      within(table).getByRole("button", { name: "Movies，整理详情" }),
    );
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      within(detail).getAllByRole("button", { name: "查看证据" })[1]!,
    );
    const recovery = await within(detail).findByRole("region", {
      name: "条目审核与恢复",
    });
    await user.click(
      await within(recovery).findByRole("radio", { name: /Special/ }),
    );
    await user.click(
      within(recovery).getByRole("button", {
        name: "保存并重新分析",
      }),
    );
    expect(
      within(recovery).getByRole("button", {
        name: "正在保存并重新分析…",
      }),
    ).toBeDisabled();
    expect(decisionPosts).toBe(1);

    // Closing the card does not release the request or its exact identity.
    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    await user.click(
      within(table).getByRole("button", { name: "Movies，整理详情" }),
    );
    const reopened = await screen.findByRole("dialog", { name: "运行详情" });
    await within(reopened).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      within(reopened).getAllByRole("button", { name: "查看证据" })[1]!,
    );
    const reopenedRecovery = await within(reopened).findByRole("region", {
      name: "条目审核与恢复",
    });
    // The original request is still in flight and the reopened panel waits
    // with the form disabled instead of offering a second submission.
    expect(
      await within(reopenedRecovery).findByText(/请求尚未返回/),
    ).toBeVisible();
    expect(
      within(reopenedRecovery).getByRole("button", {
        name: "正在保存并重新分析…",
      }),
    ).toBeDisabled();
    expect(decisionPosts).toBe(1);

    // The late outcome lands in the reopened panel, not in the closed card.
    current = recognitionRecoveryDocument();
    await act(async () => {
      releaseDecision?.(jsonResponse(current));
    });
    expect(
      await within(reopenedRecovery).findByText(/选择已保存|决策已保存/),
    ).toBeVisible();
    expect(
      within(reopenedRecovery).queryByRole("button", {
        name: /重新读取条目后再继续/,
      }),
    ).toBeNull();
    expect(decisionPosts).toBe(1);
  });

  it("keeps an unknown native decision reconcilable across card close and reopen", async () => {
    const user = userEvent.setup();
    let current = pendingRecognitionRecoveryDocument();
    let decisionPosts = 0;
    stubDetailJourney([], {
      recovery: async (input, init) => {
        if (String(input).includes("/items/item-1/recovery")) {
          return jsonResponse(
            recognitionRecoveryDocument({ item_id: "item-1" }),
          );
        }
        if ((init?.method ?? "GET") === "GET") {
          return jsonResponse(current);
        }
        decisionPosts += 1;
        throw new TypeError("network down");
      },
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(
      within(table).getByRole("button", { name: "Movies，整理详情" }),
    );
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      within(detail).getAllByRole("button", { name: "查看证据" })[1]!,
    );
    const recovery = await within(detail).findByRole("region", {
      name: "条目审核与恢复",
    });
    await user.click(
      await within(recovery).findByRole("radio", { name: /Special/ }),
    );
    await user.click(
      within(recovery).getByRole("button", {
        name: "保存并重新分析",
      }),
    );
    expect(await within(recovery).findByText(/请求响应未送达/)).toBeVisible();
    expect(decisionPosts).toBe(1);

    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    await user.click(
      within(table).getByRole("button", { name: "Movies，整理详情" }),
    );
    const reopened = await screen.findByRole("dialog", { name: "运行详情" });
    await within(reopened).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      within(reopened).getAllByRole("button", { name: "查看证据" })[1]!,
    );
    const reopenedRecovery = await within(reopened).findByRole("region", {
      name: "条目审核与恢复",
    });
    // The unknown outcome keeps its original reconciliation entry and lock.
    expect(
      await within(reopenedRecovery).findByText(/请求响应未送达/),
    ).toBeVisible();
    expect(
      within(reopenedRecovery).getByRole("button", {
        name: "保存并重新分析",
      }),
    ).toBeDisabled();
    expect(
      within(reopenedRecovery).getByRole("button", {
        name: /重新读取条目后再继续/,
      }),
    ).toBeEnabled();

    // A different item has its own session: switching evidence does not show
    // this item's unknown outcome, and returning keeps it isolated.
    await user.click(
      within(reopened).getByRole("button", { name: "关闭证据" }),
    );
    await user.click(
      within(reopened).getAllByRole("button", { name: "查看证据" })[0]!,
    );
    const otherRecovery = await within(reopened).findByRole("region", {
      name: "条目审核与恢复",
    });
    await within(otherRecovery).findByText(/审核与恢复/);
    expect(within(otherRecovery).queryByText(/请求响应未送达/)).toBeNull();
    await user.click(
      within(reopened).getByRole("button", { name: "关闭证据" }),
    );
    await user.click(
      within(reopened).getAllByRole("button", { name: "查看证据" })[1]!,
    );
    const backToItem = await within(reopened).findByRole("region", {
      name: "条目审核与恢复",
    });
    expect(await within(backToItem).findByText(/请求响应未送达/)).toBeVisible();

    // The explicit reconciliation reads the current durable state; it never
    // resubmits the original decision.
    current = recognitionRecoveryDocument();
    (current["checkpoint"] as Record<string, unknown>)["permitted_action_ids"] =
      ["retry"];
    await user.click(
      within(backToItem).getByRole("button", {
        name: /重新读取条目后再继续/,
      }),
    );
    expect(
      await within(backToItem).findByText(/已重新读取此 TaskItem 的持久状态/),
    ).toBeVisible();
    expect(decisionPosts).toBe(1);
  });

  it("keeps a late confirmation success from navigating a closed card", async () => {
    const user = userEvent.setup();
    let current = manualReadyRecoveryDocument(null);
    let confirmPosts = 0;
    let releaseConfirm: ((response: Response) => void) | undefined;
    const confirmGate = new Promise<Response>((resolve) => {
      releaseConfirm = resolve;
    });
    stubDetailJourney([], {
      recovery: async (_input, init) => {
        if ((init?.method ?? "GET") === "GET") {
          return jsonResponse(current);
        }
        // Prepare-summary is the deliberate same-page summary creation.
        current = manualReadyRecoveryDocument(
          preparedSummaryDocument("prepared"),
        );
        return jsonResponse(preparedSummaryDocument("prepared"), 201);
      },
      planSummary: async (input) => {
        const url = String(input);
        if (url === "/api/v1/operations/organize/previews/preview-1") {
          return jsonResponse(recoveryPreviewDocument());
        }
        confirmPosts += 1;
        return confirmGate;
      },
    });
    authStore.setToken(TOKEN);
    const { router } = renderApp("/ui-v2/operations");

    const table = await screen.findByRole("table");
    await user.click(
      within(table).getByRole("button", { name: "Movies，整理详情" }),
    );
    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      within(detail).getAllByRole("button", { name: "查看证据" })[1]!,
    );
    const recovery = await within(detail).findByRole("region", {
      name: "条目审核与恢复",
    });
    await user.click(
      await within(recovery).findByRole("button", {
        name: "生成计划摘要并在此确认",
      }),
    );
    const summary = await within(detail).findByRole("region", {
      name: "新计划摘要",
    });
    await user.click(
      await within(summary).findByRole("button", {
        name: "确认继续整理 1 项",
      }),
    );
    expect(
      within(summary).getByRole("button", { name: "正在受理…" }),
    ).toBeDisabled();
    expect(confirmPosts).toBe(1);

    // Switching to another item leaves the exact confirmation session with
    // item-2: the other item's panel never shows this confirmation.
    await user.click(within(detail).getByRole("button", { name: "关闭证据" }));
    await user.click(
      within(detail).getAllByRole("button", { name: "查看证据" })[0]!,
    );
    const otherRecovery = await within(detail).findByRole("region", {
      name: "条目审核与恢复",
    });
    await within(otherRecovery).findByText(/审核与恢复/);
    expect(within(otherRecovery).queryByText(/本次确认已经受理/)).toBeNull();
    await user.click(within(detail).getByRole("button", { name: "关闭证据" }));

    // Closing the card while the confirmation is in flight is a legal exit:
    // the list context is restored and the request is never cancelled.
    await user.click(within(detail).getByRole("button", { name: "关闭详情" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull(),
    );
    expect(router.history.location.pathname).toBe("/ui-v2/operations");
    // The closed card's selection is dropped from the URL, so nothing about
    // the in-flight confirm can restore it behind the operator's back.
    expect(router.history.location.search).not.toContain("run=");

    // The late 202 success must not navigate on behalf of the closed card.
    await act(async () => {
      current = manualReadyRecoveryDocument(
        preparedSummaryDocument("confirmed"),
      );
      releaseConfirm?.(
        jsonResponse(
          {
            executionId: "execution-1",
            taskId: "execution-task-1",
            status: "admitted",
            selectedItemIds: ["item-2"],
            nextAction: "track the durable Worker execution",
          },
          202,
        ),
      );
    });
    expect(confirmPosts).toBe(1);
    expect(router.history.location.pathname).toBe("/ui-v2/operations");
    expect(router.history.location.pathname).not.toContain(
      "organize/execution",
    );
    expect(screen.queryByRole("dialog", { name: "运行详情" })).toBeNull();

    // Reopening reads the persisted admission instead of resubmitting it; the
    // panel states the known admission fact and offers no execution-page
    // navigation.
    await user.click(
      within(table).getByRole("button", { name: "Movies，整理详情" }),
    );
    const reopened = await screen.findByRole("dialog", { name: "运行详情" });
    await within(reopened).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      within(reopened).getAllByRole("button", { name: "查看证据" })[1]!,
    );
    const reopenedRecovery = await within(reopened).findByRole("region", {
      name: "条目审核与恢复",
    });
    expect(
      await within(reopenedRecovery).findByText(
        /已受理 1 项；常驻 Worker 将执行已确认的精确子集/,
      ),
    ).toBeVisible();
    expect(
      within(reopenedRecovery).queryByRole("button", {
        name: "查看关联执行结果",
      }),
    ).toBeNull();
    expect(confirmPosts).toBe(1);
  });

  it("renders the durable reviewed plan, effects and section detail for a manually executed item", async () => {
    const user = userEvent.setup();
    stubDetailJourney();
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    const inspectButtons = within(detail).getAllByRole("button", {
      name: "查看证据",
    });
    await user.click(inspectButtons[0]);
    const evidence = await within(detail).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("文件证据：a.mkv");
    await user.click(within(evidence).getByText(/技术诊断/));

    // The captured reviewed plan stays reachable inside the diagnostics group;
    // its business explanation is preserved rather than flattened away.
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
    expect(
      within(evidence).getByText("创建目录（CREATE_DIRECTORY）、移动（MOVE）"),
    ).toBeVisible();
    expect(within(evidence).getByText("已验证")).toBeVisible();
    // "已验证完成" appears in the merged execution history and in the
    // durable step table; both must speak the same label.
    expect(within(evidence).getAllByText("已验证完成").length).toBeGreaterThan(
      1,
    );

    // The durable result row explains the cleanup outcome instead of leaving
    // the known `disabled` fact unknown.
    expect(
      within(evidence).getByText(/未启用\(本次执行没有获得源目录清理授权\)/),
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

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const evidence = await within(detail).findByRole("region", {
      name: "条目证据",
    });
    await within(evidence).findByText("文件证据：standalone.mkv");
    await userEvent.setup().click(within(evidence).getByText(/技术诊断/));

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
      within(completedRow as HTMLElement).getByText(
        "创建目录（CREATE_DIRECTORY）、移动（MOVE）",
      ),
    ).toBeVisible();
    // Each durable result states its own persisted steps and effect —
    // including the second, uncertain result — not just the aggregate. Both
    // attempts stay as separate merged history entries with their own time,
    // result, operation, steps, cleanup and exceptions.
    expect(within(evidence).getByText(/执行记录 1（/)).toBeVisible();
    expect(within(evidence).getByText(/执行记录 2（/)).toBeVisible();
    expect(
      within(evidence).getByText(
        "已完成：创建目录（CREATE_DIRECTORY）、移动（MOVE）",
      ),
    ).toBeVisible();
    expect(
      within(evidence).getByText(
        "已完成：写入副本（copy_written）、核对目标（destination_verified）",
      ),
    ).toBeVisible();
    expect(
      within(evidence).getAllByText(/删除来源（source_deletion）/).length,
    ).toBeGreaterThan(0);
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

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
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

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
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

  it("explains when browser storage cannot preserve a batch command identity", async () => {
    const getItem = Storage.prototype.getItem;
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(function (
      this: Storage,
      key: string,
    ) {
      if (
        key === "mediaflow.operations.recovery-batch:v2:test-principal:task-001"
      ) {
        throw new Error("session storage unavailable");
      }
      return getItem.call(this, key);
    });
    const requested: string[] = [];
    stubDetailJourney(requested);
    authStore.setToken(TOKEN);
    const { queryClient } = renderApp("/ui-v2/operations?run=task-001");

    await waitFor(() => expect(requested).toContain("/api/v1/auth/principal"));
    await waitFor(() =>
      expect(
        queryClient.getQueryData([
          "authenticated-principal",
          authStore.getGeneration(),
        ]),
      ).toEqual({ principalId: "test-principal" }),
    );

    const batch = await screen.findByRole("region", {
      name: "批量失败分析恢复",
    });
    expect(
      await within(batch).findByRole("heading", { name: "批量恢复不可用" }),
    ).toBeVisible();
    expect(
      await within(batch).findByText(/批量提交已关闭，避免响应丢失后无法核对/),
    ).toBeVisible();
  });

  it("offers batch recovery only for the mixed run's own four-type items", async () => {
    const technical = itemRow({
      item_id: "tech-1",
      status: "failed",
      stage: "failed",
      source_path: "movies/broken.mkv",
      failure: {
        category: "storage_permission_denied",
        message: "the destination Storage rejected the write",
        durableState: "no_media_moved",
        sideEffects: "none",
        retrySafe: true,
        nextAction:
          "repair the destination Storage permission, then re-check this item",
      },
      checkpoint: {
        status: "failed",
        stage: "failed",
        raw_stage: "failed",
        blocker_kind: null,
        blocker_id: null,
        effect_certainty: "none",
        retry_safety: "safe",
        refusal_reason: null,
        checkpoint_version: "v-tech",
        permitted_action_ids: ["retry"],
      },
      recoveryKind: "technical_history",
    });
    const business = itemRow({
      item_id: "biz-1",
      status: "failed",
      stage: "task_retry_requested",
      source_path: "movies/business.mkv",
      checkpoint: {
        status: "pending",
        stage: "queued",
        raw_stage: "task_retry_requested",
        blocker_kind: null,
        blocker_id: null,
        effect_certainty: "none",
        retry_safety: "safe",
        refusal_reason: null,
        checkpoint_version: "v-biz",
        permitted_action_ids: ["retry"],
      },
      recoveryKind: "business_problem",
    });
    const itemsPage = itemsPageDocument({
      items: [technical, business],
      total: 2,
      matching_total: 2,
      dispositions: {
        pending: 0,
        active: 0,
        waiting: 0,
        success: 0,
        skipped: 0,
        failed_partial: 2,
        ignored: 0,
        cancelled: 0,
      },
    });
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "test-principal" });
      }
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse({
          items: [
            overviewDocument({
              attention: true,
              attention_reason: "task_problem",
              problem_types: ["recognition"],
            }),
          ],
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
          attention_count: 1,
          population: "unified job/task run inventory",
          sideEffects: "none",
          previous_cursor: null,
          next_cursor: null,
        });
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(
          overviewDocument({
            attention: true,
            attention_reason: "task_problem",
            problem_types: ["recognition"],
          }),
        );
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return jsonResponse(itemsPage);
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    const items = await within(detail).findByRole("region", { name: "主条目" });
    await within(items).findByText(/broken\.mkv/);
    expect(
      within(items).queryByLabelText("选择 tech-1 进行单项分析恢复"),
    ).toBeNull();
    expect(
      within(items).getByLabelText("选择 biz-1 进行单项分析恢复"),
    ).toBeInTheDocument();
    expect(
      within(items).getByText(
        "storage_permission_denied: the destination Storage rejected the write",
      ),
    ).toBeVisible();
    expect(
      within(items).queryByText(/repair the destination Storage permission/),
    ).toBeNull();
    expect(
      screen.getByRole("region", { name: "批量失败分析恢复" }),
    ).toBeInTheDocument();
  });

  it("keeps a saved batch's technical-history child read-only", async () => {
    const batchId = "22222222-2222-2222-2222-222222222222";
    const childRow = (itemId: string, recoveryKind: string) =>
      itemRow({
        item_id: itemId,
        status: "failed",
        stage: "failed",
        source_path: `movies/${itemId}.mkv`,
        recoveryKind,
        checkpoint: {
          status: "failed",
          stage: "failed",
          raw_stage: "failed",
          blocker_kind: null,
          blocker_id: null,
          effect_certainty: "none",
          retry_safety: "safe",
          refusal_reason: null,
          checkpoint_version: "a".repeat(64),
          permitted_action_ids: ["retry"],
        },
      });
    const itemsPage = itemsPageDocument({
      items: [childRow("tech-child", "technical_history")],
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
    });
    window.sessionStorage.setItem(
      "mediaflow.operations.recovery-batch:v2:test-principal:task-001",
      JSON.stringify({
        batchId,
        items: [
          { itemId: "tech-child", expectedCheckpointVersion: "a".repeat(64) },
        ],
      }),
    );
    stubFetch(async (input) => {
      const url = String(input);
      if (url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "test-principal" });
      }
      if (url.startsWith("/api/v1/operations/runs?")) {
        return jsonResponse({
          items: [
            overviewDocument({
              attention: true,
              attention_reason: "task_problem",
              problem_types: ["recognition"],
            }),
          ],
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
          attention_count: 1,
          population: "unified job/task run inventory",
          sideEffects: "none",
          previous_cursor: null,
          next_cursor: null,
        });
      }
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(
          overviewDocument({
            attention: true,
            attention_reason: "task_problem",
            problem_types: ["recognition"],
          }),
        );
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items?")) {
        return jsonResponse(itemsPage);
      }
      if (url.includes(`/recovery-batches/${batchId}`)) {
        return jsonResponse({
          batch_id: batchId,
          source_task_id: "task-001",
          actor: "test-principal",
          status: "completed",
          next_action: "inspect each item outcome",
          items: [
            {
              batch_item_id: "bi-tech",
              batch_id: batchId,
              source_task_id: "task-001",
              source_item_id: "tech-child",
              checkpoint_version: "a".repeat(64),
              status: "completed",
              continuation_id: "continuation-tech",
              job_id: "job-tech",
              new_task_id: "analysis-task-tech",
              new_result_id: "analysis-result-tech",
              reason: null,
              error: null,
              next_action:
                "repair the dependency, then continue this item through a fresh pinned DryRun",
              manualRecoveryPreparation: null,
              currentCheckpointVersion: "a".repeat(64),
              recoveryContinuationStatus: "completed",
              manualRecoveryAvailable: true,
              recoveryKind: "technical_history",
            },
          ],
        });
      }
      return jsonResponse({ error: { code: "not_found" } }, 404);
    });
    authStore.setToken(TOKEN);
    const { queryClient } = renderApp("/ui-v2/operations?run=task-001");
    await waitFor(() =>
      expect(
        queryClient.getQueryData([
          "authenticated-principal",
          authStore.getGeneration(),
        ]),
      ).toEqual({ principalId: "test-principal" }),
    );

    const batch = await screen.findByRole("region", {
      name: "批量失败分析恢复",
    });
    expect(await within(batch).findByText(/技术历史，仅只读/)).toBeVisible();
    expect(within(batch).queryByText(/repair the dependency/)).toBeNull();
    expect(
      within(batch).queryByRole("button", {
        name: "在当前界面生成并确认摘要",
      }),
    ).toBeNull();
  });

  it("keeps an unknown batch confirmation locked until its exact durable outcome is read", async () => {
    const user = userEvent.setup();
    const batchId = "11111111-1111-1111-1111-111111111111";
    const checkpointVersion = "c".repeat(64);
    const confirmPosts: { url: string; body: unknown }[] = [];
    let committed = false;
    let releaseBatchRead: ((response: Response) => void) | undefined;
    const delayedBatchRead = new Promise<Response>((resolve) => {
      releaseBatchRead = resolve;
    });
    const previewFor = (itemId: string) => {
      const preview = JSON.parse(
        JSON.stringify(
          (manualOperationsFixture as Record<string, unknown>)[
            "organizePreviewDetail"
          ],
        ),
      ) as Record<string, unknown>;
      preview["previewId"] = `preview-${itemId}`;
      preview["intentId"] = `intent-${itemId}`;
      preview["intentVersion"] = 4;
      preview["executionCandidateItemIds"] = [itemId];
      const previewItems = preview["items"] as Record<string, unknown>[];
      previewItems[0]!["itemId"] = itemId;
      previewItems[0]!["previewItemId"] = `preview-item-${itemId}`;
      (preview["selection"] as Record<string, unknown>)["selectedItemIds"] = [
        itemId,
      ];
      (preview["selection"] as Record<string, unknown>)["unselectedItemIds"] =
        [];
      const previewActions = preview["actions"] as Record<
        string,
        Record<string, unknown>
      >;
      previewActions["execute"]!["path"] =
        `/api/v1/operations/organize/previews/preview-${itemId}/execute`;
      return preview;
    };
    const prep = (
      itemId: string,
      status: "prepared" | "confirmed" = "prepared",
    ) => ({
      preparation_id: `preparation-${itemId}`,
      status,
      preview_id: `preview-${itemId}`,
      intent_id: `intent-${itemId}`,
      source_task_id: "task-001",
      source_item_id: itemId,
      checkpoint_version:
        itemId === "child-1" ? checkpointVersion : "e".repeat(64),
      configuration_snapshot_id: "snap-1",
      configuration_snapshot_digest: "d".repeat(64),
      actor: "test-principal",
      authorization_id: status === "confirmed" ? "authorization-child-1" : null,
      execution_id: status === "confirmed" ? "execution-child-1" : null,
      selected_item_ids: status === "confirmed" ? ["child-1"] : [],
      allow_overwrite: false,
      allow_source_cleanup: false,
      hasExecutionAuthority: false,
      next_action: "review and confirm",
    });
    const batchDocument = (childOneStatus: "prepared" | "confirmed") => ({
      batch_id: batchId,
      source_task_id: "task-001",
      actor: "test-principal",
      status: "completed",
      selected_count: 2,
      unchanged_count: 0,
      ignored_count: 0,
      counts: { completed: 2 },
      next_action: "inspect each item outcome",
      items: [
        {
          batch_item_id: "bi-1",
          batch_id: batchId,
          source_task_id: "task-001",
          source_item_id: "child-1",
          checkpoint_version: checkpointVersion,
          status: "completed",
          request_id: "request-1",
          continuation_id: "continuation-1",
          job_id: "job-1",
          new_task_id: "analysis-task-1",
          new_result_id: "analysis-result-1",
          reason: null,
          error: null,
          next_action: "review the current summary",
          manualRecoveryPreparation: prep("child-1", childOneStatus),
          currentCheckpointVersion: checkpointVersion,
          recoveryContinuationStatus: "completed",
          manualRecoveryAvailable: true,
          recoveryKind: "recovery_lineage",
        },
        {
          batch_item_id: "bi-2",
          batch_id: batchId,
          source_task_id: "task-001",
          source_item_id: "child-2",
          checkpoint_version: "e".repeat(64),
          status: "completed",
          request_id: "request-2",
          continuation_id: "continuation-2",
          job_id: "job-2",
          new_task_id: "analysis-task-2",
          new_result_id: "analysis-result-2",
          reason: null,
          error: null,
          next_action: "review the current summary",
          manualRecoveryPreparation: prep("child-2"),
          currentCheckpointVersion: "e".repeat(64),
          recoveryContinuationStatus: "completed",
          manualRecoveryAvailable: true,
          recoveryKind: "recovery_lineage",
        },
      ],
    });
    window.sessionStorage.setItem(
      "mediaflow.operations.recovery-batch:v2:test-principal:task-001",
      JSON.stringify({
        batchId,
        items: [
          { itemId: "child-1", expectedCheckpointVersion: checkpointVersion },
          { itemId: "child-2", expectedCheckpointVersion: "e".repeat(64) },
        ],
      }),
    );
    stubFetch(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (method === "POST") {
        confirmPosts.push({
          url,
          body:
            typeof init?.body === "string"
              ? (JSON.parse(init.body) as unknown)
              : null,
        });
        if (url.endsWith("/confirm")) {
          committed = true;
          throw new Error("connection closed after durable commit");
        }
        return jsonResponse({ error: { code: "not_found" } }, 404);
      }
      if (url === "/api/v1/auth/principal") {
        return jsonResponse({ principal_id: "test-principal" });
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
      if (url === "/api/v1/operations/runs/task-001") {
        return jsonResponse(overviewDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/items")) {
        return jsonResponse(itemsPageDocument());
      }
      if (url.startsWith("/api/v1/operations/runs/task-001/records")) {
        return jsonResponse(recordsPageDocument());
      }
      if (url.includes("/recovery-batches/")) {
        if (committed) {
          return delayedBatchRead;
        }
        return jsonResponse(batchDocument("prepared"));
      }
      if (url.endsWith("/preview-child-1")) {
        return jsonResponse(previewFor("child-1"));
      }
      if (url.endsWith("/preview-child-2")) {
        return jsonResponse(previewFor("child-2"));
      }
      if (url === "/api/v1/workers/readiness") {
        return jsonResponse({
          ready: true,
          condition: "ready",
          category: null,
          durableState: "ready",
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
    authStore.setToken(TOKEN);
    renderApp("/ui-v2/operations?run=task-001");

    const summary = await screen.findByRole("region", {
      name: "批量同页计划摘要",
    });
    await waitFor(() => {
      expect(within(summary).getAllByRole("checkbox")).toHaveLength(2);
    });
    const checkboxes = within(summary).getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(2);
    await user.click(checkboxes[1]!);
    const confirm = await within(summary).findByRole("button", {
      name: /确认继续整理所选 1 项/,
    });
    await user.click(confirm);
    await waitFor(() => expect(confirmPosts).toHaveLength(1));
    expect(confirmPosts[0]?.url).toBe(
      "/api/v1/manual-recovery-preparations/preparation-child-1/confirm",
    );
    expect(confirmPosts[0]?.body).toMatchObject({
      itemIds: ["child-1"],
      confirmation: true,
    });
    expect(committed).toBe(true);
    await within(summary).findByText(/结果未知/);
    expect(confirm).toBeDisabled();
    expect(
      within(summary).getByRole("heading", { name: "条目 child-2" }),
    ).toBeTruthy();
    expect(confirmPosts).toHaveLength(1);

    await act(async () => {
      releaseBatchRead?.(jsonResponse(batchDocument("confirmed")));
      await delayedBatchRead;
    });
    await within(summary).findByText(/持久状态已确认本次精确子集/);
    expect(confirmPosts).toHaveLength(1);
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

    const detail = await screen.findByRole("dialog", { name: "运行详情" });
    await within(detail).findAllByText(/source:movies\/a\.mkv/);
    await user.click(
      await within(detail).findByRole("button", { name: "操作记录" }),
    );
    await screen.findByText(/共 4 条记录/);

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
  if (url === "/api/v1/auth/principal") {
    return jsonResponse({ principal_id: "test-principal" });
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
