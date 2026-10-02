/**
 * Contract tests for the selected-run detail models (Slice 42 RO-3).
 *
 * The normalizers are fail-closed: they must prove the backend's arithmetic
 * (a partition that reconciles to the known total, a success split that adds
 * up, a filtered count that equals its kind's population, a truncated export
 * that says so) and refuse any payload that breaks it — including a
 * configuration digest or fingerprint reaching a detail document.
 */

import { describe, expect, it } from "vitest";
import {
  normalizeRunExportPackage,
  normalizeRunItemEvidence,
  normalizeRunItemsPage,
  normalizeRunProgress,
  normalizeRunRecordsPage,
  RUN_DISPOSITIONS,
  RUN_PLAN_EVIDENCE_UNAVAILABLE_LABELS,
  RUN_RECORD_KINDS,
  UNAVAILABLE_PLAN_REASON,
} from "./run-detail";
import { normalizeRunOverview } from "./run";

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
      waiting: 0,
      success: 2,
      skipped: 0,
      failed_partial: 1,
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

function itemRow(overrides: Record<string, unknown> = {}) {
  return {
    item_id: "item-1",
    task_id: "task-1",
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

function resultRow(overrides: Record<string, unknown> = {}) {
  return {
    result_id: "result-1",
    task_id: "task-1",
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
    ...overrides,
  };
}

function itemsPageDocument(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "task-1",
    task_id: "task-1",
    filter: { status: null },
    limit: 20,
    items: [itemRow()],
    total: 4,
    matching_total: 4,
    dispositions: {
      pending: 1,
      active: 0,
      waiting: 0,
      success: 2,
      skipped: 0,
      failed_partial: 1,
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
    run_id: "task-1",
    task_id: "task-1",
    job_id: null,
    filter: { kind: null },
    limit: 20,
    records: [],
    matching_total: 4,
    kind_counts: { result: 3, evidence: 1, log: 0, audit: 0 },
    truncated: false,
    previous_cursor: null,
    next_cursor: null,
    sideEffects: "none",
    ...overrides,
  };
}

function evidenceDocument(overrides: Record<string, unknown> = {}) {
  return {
    run_id: "task-1",
    task_id: "task-1",
    item_id: "item-1",
    item: itemRow({ status: "failed" }),
    checkpoint: {
      status: "failed",
      stage: "failed",
      raw_stage: "organize",
      attempts: 1,
      source_storage_id: "source",
      resource_library_id: "movies",
      source_path: "movies/a.mkv",
      plan_id: "plan-1",
      destination_storage_id: null,
      destination_path: null,
      configuration: {
        snapshot_id: "snap-1",
        resolvable: true,
        reason: null,
      },
      latest_result: null,
      prior_results: [],
      blockers: [],
      blocker: null,
      audits: [
        {
          audit_id: "audit-1",
          kind: "task_retry",
          occurred_at: "2026-08-22T12:03:00+00:00",
          actor: "operator",
        },
      ],
      recovery_requests: [],
      recovery_request: null,
      recovery_continuation: null,
      effects: {
        certainty: "unknown",
        completed_operations: [],
        uncertain_effects: [],
      },
      error_category: "workflow_failure",
      retry_safety: "unsafe",
      failureExplanation: {
        category: "provider_failure",
        message: "m",
        durableState: "d",
        sideEffects: "none",
        retrySafe: true,
        nextAction: "n",
      },
      nextAction: "inspect the checkpoint",
      actions: [],
      permitted_action_ids: ["investigate"],
      refusal_reason: "automatic_replay_refused",
      checkpoint_version: "v1",
      updated_at: "2026-08-22T12:02:00+00:00",
    },
    results: [resultRow()],
    evidence: [
      {
        evidenceId: "ev-1",
        attempts: 1,
        outcome: "failed",
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
    logs: [
      {
        record_id: "log:log-1",
        kind: "log",
        kind_label: "运行日志",
        occurred_at: "2026-08-22T12:03:00+00:00",
        item_id: null,
        level: "ERROR",
        event: "workflow.failed",
        component: "workflow",
        status: "failed",
        plan_id: "plan-1",
        action: null,
        state: null,
        actor: null,
        parent_id: null,
        result: null,
        evidence: null,
      },
    ],
    sideEffects: "none",
    ...overrides,
  };
}

/**
 * The real `planEvidence` projection a Manual-Organize-executed item publishes
 * (`manual_execution_plan_evidence_operator` composed through
 * `_bounded_preview_plan` in `operations_lifecycle.py`): camelCase ids, the
 * durable effect rows and the exact reviewed Preview plan document.
 */
function planEvidencePayload(overrides: Record<string, unknown> = {}) {
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
        originalTitle: null,
        episodeTitle: null,
        matchedBy: "candidate_matcher",
        recognitionTypeId: "C",
        year: 2001,
        season: null,
        episode: null,
        episodes: [],
        genres: ["Animation"],
        countries: ["JP"],
        languages: [],
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
          season: null,
          episode: null,
          episodes: [],
          resolution: null,
          source: null,
          videoCodec: null,
          audio: null,
          hdr: null,
          version: null,
          releaseGroup: null,
          evidence: [],
          warnings: [],
        },
        recognition: {
          status: "recognized",
          recognitionTypeId: "C",
          ruleId: "movie-year",
          score: 100,
          confidence: "1.0",
          reasons: [],
          warnings: [],
        },
        metadata: {
          available: true,
          status: "matched",
          query: "One",
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
            reasons: [],
            warnings: [],
            candidateCount: 1,
            candidates: [],
          },
        },
        naming: {
          available: true,
          reason: null,
          policyId: "A",
          recognitionTypeId: "C",
          directory: "One (2001)",
          directorySegments: ["One (2001)"],
          filename: "One (2001).mkv",
          warnings: [],
          sanitizationChanges: [],
        },
        classification: {
          available: true,
          reason: null,
          status: "classified",
          policyId: "A",
          recognitionTypeId: "C",
          mediaLibraryId: "movies",
          relativePath: "Movies",
          matchedRuleId: null,
          matchedRuleName: null,
          evidence: [],
          warnings: [],
        },
      },
      destination: {
        storageId: "target",
        relativePath: "Movies/One (2001)/One (2001).mkv",
        filename: "One (2001).mkv",
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
      // Fidelity extras the backend projection always publishes; the shared
      // validator intentionally ignores unknown fields.
      zeroMutation: true,
      bounded: true,
      deterministic: true,
    },
    ...overrides,
  };
}

/** One `mediaflow.results.v1` package row: the committed camelCase interchange format. */
function packageResultRow(overrides: Record<string, unknown> = {}) {
  return {
    resultId: "result-1",
    taskId: "task-1",
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
    ...overrides,
  };
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
      taskId: "task-1",
      taskCommand: "preview",
      ordering: "created_at_asc,result_id_asc",
      limit: 500,
    },
    redaction: {
      scope: "persisted_task_result_projection",
      entryCount: 0,
      entries: [],
    },
    results: [packageResultRow()],
    truncated: false,
    warning: [],
    packageDigest: "abc123",
    ...overrides,
  };
}

describe("run progress normalization", () => {
  it("normalizes a reconciling partition and its success split", () => {
    const progress = normalizeRunProgress(progressDocument());
    expect(progress.available).toBe(true);
    if (!progress.available) return;
    expect(progress.knownTotal).toBe(4);
    expect(progress.processed).toBe(3);
    expect(progress.confirmedSuccess + progress.uncertainSuccess).toBe(
      progress.dispositions.success,
    );
    expect(progress.successMeans).toContain("存储操作");
    expect(progress.attachmentSteps).toBe(2);
  });

  it("rejects a partition that does not reconcile to its known total", () => {
    expect(() =>
      normalizeRunProgress(
        progressDocument({
          known_total: 5,
          processed: 4,
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects a success split that does not add up", () => {
    expect(() =>
      normalizeRunProgress(progressDocument({ confirmed_success: 2 })),
    ).toThrow(/invalid field|did not match the contract/);
    expect(() =>
      normalizeRunProgress(progressDocument({ uncertain_success: 2 })),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects processed values that are not processed arithmetic", () => {
    expect(() =>
      normalizeRunProgress(progressDocument({ processed: 4 })),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("proves the indeterminate state keeps its total and processed null", () => {
    const progress = normalizeRunProgress(
      progressDocument({
        indeterminate: true,
        known_total: null,
        processed: null,
        scan_discovery_complete: false,
        dispositions: {
          pending: 0,
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
      }),
    );
    expect(progress.available).toBe(true);
    if (!progress.available) return;
    expect(progress.indeterminate).toBe(true);
    expect(progress.knownTotal).toBeNull();
    expect(progress.processed).toBeNull();
    // An indeterminate state may not smuggle a total back in.
    expect(() =>
      normalizeRunProgress(
        progressDocument({
          indeterminate: true,
          known_total: 4,
          processed: null,
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("normalizes the explicit unavailable state", () => {
    const progress = normalizeRunProgress({
      available: false,
      reason: "this run has no linked Task yet",
    });
    expect(progress.available).toBe(false);
    if (progress.available) return;
    expect(progress.reason).toContain("no linked Task");
  });

  it("rejects an unknown disposition key in the partition", () => {
    expect(() =>
      normalizeRunProgress(
        progressDocument({
          dispositions: { ...progressDocument()["dispositions"], surprise: 1 },
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });
});

describe("run overview carries its progress", () => {
  it("parses the progress projection from the overview document", () => {
    const overview = normalizeRunOverview(
      Object.assign(
        {
          run_kind: "task",
          run_id: "task-1",
          command: "organize",
          command_label: "整理",
          recognized_command: true,
          status: "running",
          trigger: "manual",
          created_at: "2026-08-22T12:00:00+00:00",
          updated_at: "2026-08-22T12:00:00+00:00",
          job_id: null,
          task_id: "task-1",
          schedule_id: null,
          definition_id: null,
          source_scope: null,
          target_scope: null,
          library_kind: "resource",
          total_items: 4,
          completed_items: 1,
          failed_items: 0,
          pause_requested: false,
          attention: false,
          configuration_snapshot_id: null,
          worker_id: null,
          sideEffects: "none",
        },
        { progress: progressDocument() },
      ),
    );
    expect(overview.progress?.available).toBe(true);
  });

  it("rejects an overview whose progress breaks the arithmetic", () => {
    expect(() =>
      normalizeRunOverview(
        Object.assign(
          {
            run_kind: "task",
            run_id: "task-1",
            command: "organize",
            command_label: "整理",
            recognized_command: true,
            status: "running",
            trigger: "manual",
            created_at: "2026-08-22T12:00:00+00:00",
            updated_at: "2026-08-22T12:00:00+00:00",
            job_id: null,
            task_id: "task-1",
            schedule_id: null,
            definition_id: null,
            source_scope: null,
            target_scope: null,
            library_kind: "resource",
            total_items: 4,
            completed_items: 1,
            failed_items: 0,
            pause_requested: false,
            attention: false,
            configuration_snapshot_id: null,
            worker_id: null,
            sideEffects: "none",
          },
          { progress: progressDocument({ known_total: 9 }) },
        ),
      ),
    ).toThrow();
  });
});

describe("run items page normalization", () => {
  it("normalizes a filtered page with page-independent population totals", () => {
    const page = normalizeRunItemsPage(
      itemsPageDocument({
        filter: { status: "waiting" },
        matching_total: 1,
        items: [itemRow({ status: "waiting_metadata" })],
      }),
    );
    expect(page.statusFilter).toBe("waiting");
    expect(page.total).toBe(4);
    expect(page.matchingTotal).toBe(1);
    expect(page.items[0]?.status).toBe("waiting_metadata");
  });

  it("rejects a partition that does not sum to the reported total", () => {
    expect(() =>
      normalizeRunItemsPage(itemsPageDocument({ total: 9 })),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects an unfiltered page whose matching total differs", () => {
    expect(() =>
      normalizeRunItemsPage(itemsPageDocument({ matching_total: 3 })),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects an unmodelled disposition filter", () => {
    expect(() =>
      normalizeRunItemsPage(
        itemsPageDocument({ filter: { status: "half_done" } }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("models the explicit pre-Task unavailability as a real page", () => {
    const page = normalizeRunItemsPage(
      itemsPageDocument({
        task_id: null,
        items: [],
        total: 0,
        matching_total: 0,
        dispositions: {
          pending: 0,
          active: 0,
          waiting: 0,
          success: 0,
          skipped: 0,
          failed_partial: 0,
          ignored: 0,
          cancelled: 0,
        },
        uncertain_success: 0,
        unavailable: "this run has no linked Task yet",
      }),
    );
    expect(page.unavailable).toContain("no linked Task");
    expect(page.items).toHaveLength(0);
  });
});

describe("run records page normalization", () => {
  it("normalizes the kind partition of the whole stream", () => {
    const page = normalizeRunRecordsPage(recordsPageDocument());
    expect(page.kindFilter).toBeNull();
    expect(page.kindCounts.result).toBe(3);
    expect(page.matchingTotal).toBe(4);
  });

  it("proves a filtered total equals that kind's population count", () => {
    const page = normalizeRunRecordsPage(
      recordsPageDocument({
        filter: { kind: "log" },
        kind_counts: { result: 0, evidence: 0, log: 0, audit: 0 },
        matching_total: 0,
      }),
    );
    expect(page.kindFilter).toBe("log");
    expect(() =>
      normalizeRunRecordsPage(
        recordsPageDocument({
          filter: { kind: "log" },
          matching_total: 2,
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects a kind partition that does not sum to the unfiltered total", () => {
    expect(() =>
      normalizeRunRecordsPage(recordsPageDocument({ matching_total: 5 })),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("normalizes a result record and proves its item linkage", () => {
    const page = normalizeRunRecordsPage(
      recordsPageDocument({
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
            result: resultRow(),
            evidence: null,
          },
        ],
        matching_total: 1,
        kind_counts: { result: 1, evidence: 0, log: 0, audit: 0 },
      }),
    );
    expect(page.records[0]?.result?.recognitionType).toBe("C");
    expect(page.records[0]?.result?.namingPolicyId).toBe("A");
    expect(page.records[0]?.result?.classificationPolicyId).toBe("A");
  });

  it("rejects a result record whose payload names another item", () => {
    expect(() =>
      normalizeRunRecordsPage(
        recordsPageDocument({
          records: [
            {
              record_id: "result:result-1",
              kind: "result",
              kind_label: "执行结果",
              occurred_at: "2026-08-22T12:01:00+00:00",
              item_id: "item-2",
              level: null,
              event: null,
              component: null,
              status: null,
              plan_id: null,
              action: null,
              state: null,
              actor: null,
              parent_id: null,
              result: resultRow(),
              evidence: null,
            },
          ],
          matching_total: 1,
          kind_counts: { result: 1, evidence: 0, log: 0, audit: 0 },
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects an unknown record kind", () => {
    expect(() =>
      normalizeRunRecordsPage(
        recordsPageDocument({
          records: [
            {
              record_id: "x:1",
              kind: "mystery",
              kind_label: "?",
              occurred_at: "2026-08-22T12:01:00+00:00",
              item_id: null,
            },
          ],
          matching_total: 1,
          kind_counts: { result: 0, evidence: 0, log: 0, audit: 1 },
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });
});

describe("run item evidence normalization", () => {
  it("composes checkpoint, results, evidence and exact-linked logs", () => {
    const evidence = normalizeRunItemEvidence(evidenceDocument());
    expect(evidence.itemId).toBe("item-1");
    expect(evidence.results[0]?.recognitionType).toBe("C");
    expect(evidence.results[0]?.namingPolicyId).toBe("A");
    expect(evidence.checkpoint.refusalReason).toContain("replay");
    expect(evidence.checkpoint.audits[0]?.kind).toBe("task_retry");
    expect(evidence.evidence[0]?.sections).toHaveLength(2);
    expect(evidence.evidence[0]?.sections[1]?.available).toBe(false);
    expect(evidence.logs[0]?.level).toBe("ERROR");
  });

  it("rejects a checkpoint configuration digest reaching the document", () => {
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument({
          checkpoint: {
            ...evidenceDocument()["checkpoint"],
            configuration: {
              snapshot_id: "snap-1",
              snapshot_digest: "deadbeef",
              resolvable: true,
              reason: null,
            },
          },
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects evidence whose sections carry a snapshot digest", () => {
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument({
          evidence: [
            {
              evidenceId: "ev-1",
              attempts: 1,
              outcome: "failed",
              capturedAt: "2026-08-22T12:02:00+00:00",
              truncated: false,
              configurationSnapshotDigest: "deadbeef",
              sections: {},
            },
          ],
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects a non-log record inside the log list", () => {
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument({
          logs: [
            {
              record_id: "result:r",
              kind: "result",
              kind_label: "执行结果",
              occurred_at: "2026-08-22T12:01:00+00:00",
              item_id: "item-1",
            },
          ],
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });
});

describe("run item plan evidence (Task 42.2)", () => {
  it("normalizes the durable reviewed-plan projection of a manually executed item", () => {
    const evidence = normalizeRunItemEvidence(
      evidenceDocument({ planEvidence: planEvidencePayload() }),
    );
    const planEvidence = evidence.planEvidence;
    expect(planEvidence.available).toBe(true);
    expect(planEvidence.reason).toBeNull();
    expect(planEvidence.previewId).toBe("preview-1");
    expect(planEvidence.executionId).toBe("exec-1");
    expect(planEvidence.status).toBe("success");
    expect(planEvidence.stage).toBe("completed");
    expect(planEvidence.effectCertainty).toBe("verified_complete");
    expect(planEvidence.completedOperations).toEqual([
      "CREATE_DIRECTORY",
      "MOVE",
    ]);
    expect(planEvidence.uncertainEffects).toEqual([]);
    expect(planEvidence.effects).toHaveLength(1);
    expect(planEvidence.effects[0]).toEqual({
      action: "MOVE",
      sourceStorageId: "source",
      sourceLocation: "One (2001)/One (2001).mkv",
      destinationStorageId: "target",
      destinationLocation: "One (2001)/One (2001).mkv",
      verified: true,
      certainty: "verified_complete",
      rollback: false,
      occurredAt: "2026-08-22T12:03:00+00:00",
    });
    const plan = planEvidence.plan;
    expect(plan).not.toBeNull();
    expect(plan?.recognitionType).toBe("C");
    expect(plan?.mediaIdentity?.provider).toBe("tmdb");
    expect(plan?.mediaIdentity?.providerId).toBe("101");
    expect(plan?.mediaIdentity?.mediaType).toBe("movie");
    expect(plan?.mediaIdentity?.title).toBe("One");
    // The permanent recognition regression holds on the durable plan too:
    // RecognitionType C stays C under NamingPolicy A / ClassificationPolicy A.
    expect(plan?.policies?.recognitionTypePolicyId).toBe("type-C");
    expect(plan?.policies?.metadataPolicyId).toBe("C");
    expect(plan?.policies?.namingPolicyId).toBe("A");
    expect(plan?.policies?.classificationPolicyId).toBe("A");
    expect(plan?.policies?.organizePolicyId).toBe("A");
    expect(plan?.recognitionType).toBe("C");
    expect(plan?.analysis?.parse?.titleCandidate).toBe("One");
    expect(plan?.analysis?.parse?.year).toBe(2001);
    expect(plan?.analysis?.recognition?.status).toBe("recognized");
    expect(plan?.analysis?.recognition?.ruleId).toBe("movie-year");
    expect(plan?.analysis?.metadata?.status).toBe("matched");
    expect(plan?.analysis?.metadata?.match?.candidateCount).toBe(1);
    expect(plan?.analysis?.naming?.filename).toBe("One (2001).mkv");
    expect(plan?.analysis?.classification?.mediaLibraryId).toBe("movies");
    expect(plan?.operation).toBe("MOVE");
    expect(plan?.destination?.relativePath).toBe(
      "Movies/One (2001)/One (2001).mkv",
    );
    expect(plan?.targetStorageId).toBe("target");
    expect(plan?.targetPath).toBe("Movies/One (2001)/One (2001).mkv");
    expect(plan?.organizePolicy).toBe("A");
    expect(plan?.planStatus).toBe("organized");
    expect(plan?.attachments).toEqual([]);
    expect(plan?.capabilities?.verdict).toBe("ok");
    expect(plan?.conflicts).toEqual([]);
    expect(plan?.warnings).toEqual([]);
    expect(plan?.cleanupProjection).toEqual({
      mode: "empty_only",
      parent: "source/Season 1",
      ignorePatterns: ["*.nfo"],
      maxParentDirectories: 3,
      maxEntries: 24,
      matchedFiles: ["One.2001.mkv"],
      blockingEntries: [],
      expectedDirectoryOutcome: "remove_empty",
      permanentDelete: false,
    });
    expect(plan?.destructiveImplications?.overwriteRequired).toBe(false);
    expect(plan?.destructiveImplications?.sourceCleanupRequired).toBe(false);
  });

  it("treats an absent planEvidence section as the honest unavailable default", () => {
    const evidence = normalizeRunItemEvidence(evidenceDocument());
    expect(evidence.planEvidence).toEqual({
      available: false,
      reason: UNAVAILABLE_PLAN_REASON,
      previewId: null,
      executionId: null,
      status: null,
      stage: null,
      effectCertainty: null,
      completedOperations: [],
      uncertainEffects: [],
      effects: [],
      plan: null,
    });
    expect(UNAVAILABLE_PLAN_REASON).toBe("no_reviewed_manual_execution_plan");
    expect(
      RUN_PLAN_EVIDENCE_UNAVAILABLE_LABELS[UNAVAILABLE_PLAN_REASON],
    ).toContain("没有可展示的持久审核计划");
  });

  it("treats a null planEvidence the same as an absent one", () => {
    const evidence = normalizeRunItemEvidence(
      evidenceDocument({ planEvidence: null }),
    );
    expect(evidence.planEvidence.available).toBe(false);
    expect(evidence.planEvidence.reason).toBe(UNAVAILABLE_PLAN_REASON);
    expect(evidence.planEvidence.plan).toBeNull();
    expect(evidence.planEvidence.effects).toEqual([]);
  });

  it("defaults an explicit unavailable section without a reason to the standard code", () => {
    const evidence = normalizeRunItemEvidence(
      evidenceDocument({ planEvidence: { available: false } }),
    );
    expect(evidence.planEvidence.available).toBe(false);
    expect(evidence.planEvidence.reason).toBe(UNAVAILABLE_PLAN_REASON);
    expect(evidence.planEvidence.plan).toBeNull();
    expect(evidence.planEvidence.previewId).toBeNull();
  });

  it("keeps a documented unavailable reason instead of rewriting it", () => {
    const evidence = normalizeRunItemEvidence(
      evidenceDocument({
        planEvidence: {
          available: false,
          reason: "legacy_history_without_manual_execution",
        },
      }),
    );
    expect(evidence.planEvidence.reason).toBe(
      "legacy_history_without_manual_execution",
    );
  });

  it("keeps available:true with an absent plan visible without inventing findings", () => {
    const evidence = normalizeRunItemEvidence(
      evidenceDocument({
        planEvidence: planEvidencePayload({ plan: null }),
      }),
    );
    expect(evidence.planEvidence.available).toBe(true);
    expect(evidence.planEvidence.previewId).toBe("preview-1");
    expect(evidence.planEvidence.effects).toHaveLength(1);
    // The shared validator models an absent plan as an all-null plan finding
    // set, never a fabricated reviewed plan.
    expect(evidence.planEvidence.plan?.recognitionType).toBeNull();
    expect(evidence.planEvidence.plan?.mediaIdentity).toBeNull();
    expect(evidence.planEvidence.plan?.policies).toBeNull();
    expect(evidence.planEvidence.plan?.analysis).toBeNull();
    expect(evidence.planEvidence.plan?.destination).toBeNull();
    expect(evidence.planEvidence.plan?.capabilities).toBeNull();
    expect(evidence.planEvidence.plan?.attachments).toEqual([]);
    expect(evidence.planEvidence.plan?.conflicts).toEqual([]);
    expect(evidence.planEvidence.plan?.warnings).toEqual([]);
  });

  it("refuses an effects list beyond the bounded 32 durable steps", () => {
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument({
          planEvidence: planEvidencePayload({
            effects: Array.from({ length: 33 }, () => ({
              action: "MOVE",
              verified: true,
              rollback: false,
            })),
          }),
        }),
      ),
    ).toThrow(/invalid field|did not match/);
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument({
          planEvidence: planEvidencePayload({ effects: "not-array" }),
        }),
      ),
    ).toThrow(/invalid field|did not match/);
  });

  it("refuses an effect without its required verified or rollback boolean", () => {
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument({
          planEvidence: planEvidencePayload({
            effects: [{ action: "MOVE" }],
          }),
        }),
      ),
    ).toThrow(/invalid field|did not match/);
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument({
          planEvidence: planEvidencePayload({
            effects: [{ action: "MOVE", verified: true }],
          }),
        }),
      ),
    ).toThrow(/invalid field|did not match/);
  });

  it("refuses a malformed reviewed plan document instead of showing a half-truth", () => {
    const conflicts = planEvidencePayload();
    (conflicts.plan as Record<string, unknown>)["conflicts"] = "x";
    expect(() =>
      normalizeRunItemEvidence(evidenceDocument({ planEvidence: conflicts })),
    ).toThrow(/invalid field|did not match/);

    const verdict = planEvidencePayload();
    (verdict.plan as Record<string, unknown>)["capabilities"] = {
      verdict: { nested: "object" },
      required: [],
      declared: [],
      missing: [],
    };
    expect(() =>
      normalizeRunItemEvidence(evidenceDocument({ planEvidence: verdict })),
    ).toThrow(/invalid field|did not match/);

    const operation = planEvidencePayload();
    (operation.plan as Record<string, unknown>)["operation"] = "DELETE_ALL";
    expect(() =>
      normalizeRunItemEvidence(evidenceDocument({ planEvidence: operation })),
    ).toThrow(/invalid field|did not match/);

    const attachments = planEvidencePayload();
    (attachments.plan as Record<string, unknown>)["attachments"] = "x";
    expect(() =>
      normalizeRunItemEvidence(evidenceDocument({ planEvidence: attachments })),
    ).toThrow(/invalid field|did not match/);

    const warnings = planEvidencePayload();
    (warnings.plan as Record<string, unknown>)["warnings"] = "x";
    expect(() =>
      normalizeRunItemEvidence(evidenceDocument({ planEvidence: warnings })),
    ).toThrow(/invalid field|did not match/);
  });

  it("refuses a non-record planEvidence or an unmodelled available flag", () => {
    expect(() =>
      normalizeRunItemEvidence(evidenceDocument({ planEvidence: "x" })),
    ).toThrow(/invalid field|did not match/);
    expect(() =>
      normalizeRunItemEvidence(evidenceDocument({ planEvidence: {} })),
    ).toThrow(/invalid field|did not match/);
  });

  it("preserves the bounded detail the backend captured on evidence sections", () => {
    const evidence = normalizeRunItemEvidence(evidenceDocument());
    const sections = evidence.evidence[0]?.sections ?? [];
    expect(sections).toHaveLength(2);
    const plan = sections[0];
    expect(plan?.name).toBe("plan");
    expect(plan?.available).toBe(true);
    expect(plan?.value).not.toBeNull();
    expect(plan?.value?.["operation"]).toBe("MOVE");
    expect(plan?.items).toHaveLength(1);
    expect(plan?.items[0]?.["field"]).toBe("ext");
    expect(plan?.items[0]?.["value"]).toBe("mkv");
    expect(plan?.warnings).toEqual(["w"]);
    const metadata = sections[1];
    expect(metadata?.available).toBe(false);
    expect(metadata?.unavailableReason).toBe("legacy evidence");
    expect(metadata?.value).toBeNull();
    expect(metadata?.items).toEqual([]);
    expect(metadata?.warnings).toEqual([]);
  });

  it("models a detail-free legacy section as captured-but-empty", () => {
    const evidence = normalizeRunItemEvidence(
      evidenceDocument({
        evidence: [
          {
            evidenceId: "ev-legacy",
            attempts: 1,
            outcome: "failed",
            capturedAt: "2026-08-22T12:02:00+00:00",
            truncated: false,
            sections: {
              parse: { available: true, truncated: false },
            },
          },
        ],
      }),
    );
    const section = evidence.evidence[0]?.sections[0];
    expect(section?.name).toBe("parse");
    expect(section?.value).toBeNull();
    expect(section?.items).toEqual([]);
    expect(section?.warnings).toEqual([]);
  });

  it("refuses malformed evidence-section detail", () => {
    const sectionDocument = (section: Record<string, unknown>) => ({
      evidence: [
        {
          evidenceId: "ev-1",
          attempts: 1,
          outcome: "failed",
          capturedAt: "2026-08-22T12:02:00+00:00",
          truncated: false,
          sections: { plan: section },
        },
      ],
    });
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument(
          sectionDocument({
            available: true,
            truncated: false,
            value: "string",
          }),
        ),
      ),
    ).toThrow(/invalid field|did not match/);
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument(
          sectionDocument({
            available: true,
            truncated: false,
            items: ["not-a-record"],
          }),
        ),
      ),
    ).toThrow(/invalid field|did not match/);
    expect(() =>
      normalizeRunItemEvidence(
        evidenceDocument(
          sectionDocument({
            available: true,
            truncated: false,
            items: Array.from({ length: 65 }, () => ({ field: "x" })),
          }),
        ),
      ),
    ).toThrow(/invalid field|did not match/);
  });
});

describe("run export package normalization", () => {
  it("normalizes a complete bounded package with a truthful digest", () => {
    const pkg = normalizeRunExportPackage(exportPackageDocument());
    expect(pkg.packageKind).toBe("mediaflow.results.v1");
    expect(pkg.taskId).toBe("task-1");
    expect(pkg.truncated).toBe(false);
    expect(pkg.resultCount).toBe(1);
    expect(pkg.ordering).toBe("created_at_asc,result_id_asc");
  });

  it("requires a truncated package to carry its truncation warning", () => {
    expect(() =>
      normalizeRunExportPackage(exportPackageDocument({ truncated: true })),
    ).toThrow(/invalid field|did not match the contract/);
    const ok = normalizeRunExportPackage(
      exportPackageDocument({
        truncated: true,
        warning: [{ code: "results_truncated", message: "bounded" }],
      }),
    );
    expect(ok.truncated).toBe(true);
    expect(ok.warningCodes).toContain("results_truncated");
  });

  it("rejects a package whose ordering is not the exact contract", () => {
    expect(() =>
      normalizeRunExportPackage(
        exportPackageDocument({
          source: {
            scope: "task",
            taskId: "task-1",
            taskCommand: "preview",
            ordering: "arbitrary",
            limit: 500,
          },
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects operator snake_case documents posing as package rows", () => {
    // The package is the committed camelCase interchange format; an operator
    // document (or a tampered row) must not validate as a package row.
    expect(() =>
      normalizeRunExportPackage(
        exportPackageDocument({ results: [resultRow()] }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects a row belonging to another Task", () => {
    expect(() =>
      normalizeRunExportPackage(
        exportPackageDocument({
          results: [packageResultRow({ taskId: "task-999" })],
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects an unknown package kind or schema version", () => {
    expect(() =>
      normalizeRunExportPackage(
        exportPackageDocument({ packageKind: "something.else" }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
    expect(() =>
      normalizeRunExportPackage(
        exportPackageDocument({ packageSchemaVersion: 2 }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });

  it("rejects an oversized result payload", () => {
    expect(() =>
      normalizeRunExportPackage(
        exportPackageDocument({
          results: Array.from({ length: 501 }, () => packageResultRow()),
        }),
      ),
    ).toThrow(/invalid field|did not match the contract/);
  });
});

describe("detail constants", () => {
  it("publishes exactly the modelled disposition and record-kind sets", () => {
    expect([...RUN_DISPOSITIONS]).toEqual([
      "pending",
      "active",
      "waiting",
      "success",
      "skipped",
      "failed_partial",
      "ignored",
      "cancelled",
    ]);
    expect([...RUN_RECORD_KINDS]).toEqual([
      "result",
      "evidence",
      "log",
      "audit",
    ]);
  });
});
