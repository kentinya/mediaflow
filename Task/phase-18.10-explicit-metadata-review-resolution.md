# Phase 18.10 — Explicit Metadata Review Resolution and Recovery

## Goal

Allow an authorized operator to explicitly select one candidate already captured by Phase 18.9,
record an immutable decision audit, and make the waiting TaskItem eligible for a later explicit
resume. Selection itself must remain persistence-only: no provider/network request, Job creation,
Task resume, Storage mutation, planning, or execution.

## 1. Resolution domain and persistence

- Extend MetadataReview with resolved status, selected candidate identity, decision time, and actor.
- Add immutable MetadataReviewDecisionAudit records and repository operations.
- Selection accepts only a candidate rank/provider identity present in the persisted review.
- Atomically resolve one pending review, append its audit, and transition its TaskItem from
  `waiting_metadata` to `pending`.
- Concurrent or repeated resolution must allow exactly one commit; failed audit/item persistence
  must roll back the whole decision.
- Add a compatible SQLite v11 migration and restart-safe deterministic reads.

## 2. Explicit recovery integration

- `tasks resume TASK_ID` may include an explicitly resolved metadata item because it is pending.
- During only that explicit retry, map the stored selection by source Storage/path into the existing
  production strategy pipeline.
- Re-run Parser, Recognition, and RecognitionTypePolicy normally, then verify the current
  RecognitionType, MetadataPolicy, provider, and media type remain compatible with the decision.
- Fetch canonical identity through the existing MetadataIdentificationService
  `identify_by_provider_id`; do not reconstruct MediaIdentity from the review snapshot.
- Continue through unchanged Naming, Classification, Planner, and DryRun/explicit-execute boundaries.
- A resolution never grants execute authority. A DryRun origin cannot be upgraded to execute.
- RecognitionType C must remain C.

## 3. CLI and API

- Add `mediaflow metadata-reviews resolve REVIEW_ID --candidate-rank N [--actor ID] [--note TEXT]`.
- Show selected candidate and bounded immutable decision audit in review detail output.
- Add `POST /api/v1/metadata-reviews/{id}/resolve` accepting exactly `candidateRank`.
- Add a dedicated `resolve_metadata_review` permission for operator/executor/admin; viewer/auditor
  remain read-only. API actor is always the authenticated principal.
- Resolution endpoints use normalized Phase 18.6 security audit records and return stable errors
  without leaking internals.

## 4. Safety and privacy

- Resolution performs zero Storage construction/mutation and zero provider/network calls.
- It creates no Task, Job, execution authorization, plan, or execution result and never resumes
  automatically.
- Provider detail lookup occurs only after a separate explicit Task resume and remains bounded by
  the configured provider policy/cache/timeout behavior.
- Never accept arbitrary provider IDs, titles, paths, policy IDs, RecognitionTypes, execute flags,
  or actor identity from API clients.
- Preserve conflict confirmation, no-overwrite/delete, Scheduler, DryRun, and OrganizerExecutor
  boundaries.

## Required tests

- Resolve by valid persisted rank; selected provider/media type and C identity are preserved.
- Invalid rank, missing review/candidate, already resolved, and non-waiting item fail safely.
- Decision, audit, and TaskItem transition are atomic; injected failure rolls back all state.
- Concurrent resolution commits once and restart preserves decision/audit.
- Explicit retry uses existing provider detail lookup and continues the real pipeline.
- Changed RecognitionType/MetadataPolicy/provider/media type rejects stale incompatible selection.
- Provider failure during retry remains a normal item failure and does not alter the decision.
- CLI/API resolution, permission matrix, input-field rejection, actor protection, redaction, and
  normalized security audit.
- Resolution itself has zero Storage/provider/network calls and creates no Job/Task/execution.
- Resumed DryRun has zero Storage mutation; execute authority rules remain unchanged.
- All Metadata, strategy, Naming, Classification, Planner/Executor, Task, API/RBAC, Dashboard,
  conflict, notification, Scanner/FileIndex, Storage, and DryRun regressions.

## Documentation and validation

Update README, architecture, configuration where relevant, progress, roadmap, and product status.
Run all tests plus formatter, lint, compile, dependency, build, configuration, FFprobe/FFmpeg, and
diff checks.

## Out of scope

- Automatic resume/retry or Job creation, candidate search/edit, arbitrary provider-ID entry,
  classification correction, Web UI, remote Overwrite, database users/OIDC, scheduled execute,
  Rollback, and changes to matcher thresholds/provider semantics.

## Final report

## Phase 18.10 Result

PASS / FAIL

## Metadata Resolution

## Explicit Recovery

## CLI and API

## Privacy and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
