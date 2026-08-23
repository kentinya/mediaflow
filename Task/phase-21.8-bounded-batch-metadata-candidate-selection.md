# Phase 21.8 — Bounded Batch Metadata Candidate Selection

## Goal

Add a bounded, auditable batch path for pending Metadata NeedConfirm/Ambiguous candidate reviews
while preserving the same candidate-rank validation, persisted snapshot, explicit Task resume
semantics, and zero-mutation command boundary as Phase 18.9/18.10. This is the first batch Metadata
candidate selection and does not introduce a generic batch framework or a Web/API write endpoint.

## Scope

### 1. Decision and persistence

- Reuse the existing immutable `MetadataReview`, `MetadataReviewCandidate`, and
  `MetadataReviewDecisionAudit` models.
- Atomically resolve a bounded, oldest-first selection of pending MetadataReviews whose TaskItems
  are still `WAITING_METADATA`.
- Persist the selected candidate rank/provider/provider ID/media type and one bounded actor/note
  audit per review. No SQLite schema bump is required for this batch operation.

### 2. Operator workflow

- Add `mediaflow metadata-reviews resolve-pending --candidate-rank RANK --actor ACTOR
  [--note NOTE] [--limit N] [--task-id TASK_ID]`.
- Require a positive bounded limit, an integer candidate rank, and bounded actor/note.
- Filter only pending, matching, still-waiting reviews; optional `--task-id` scopes selection to
  one Task.
- Reject empty selection, invalid/absent candidate rank, wrong-state, stale/concurrent changes and
  injected audit failures atomically as a whole batch.
- Existing `mediaflow tasks resume ORIGINAL_TASK_ID` consumes the stored MetadataSelection and
  re-enters the normal policy pipeline.

### 3. Metadata semantics

- Batch selection never calls a provider or constructs Storage.
- The selected candidate must be one of the persisted bounded candidate snapshots.
- RecognitionType and all resolved downstream policy references remain unchanged, including
  C -> Metadata C / Naming A / Classification A / Organize A.

### 4. Safety

- The batch command constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow and performs no network/media mutation.
- Actual media workflow remains DryRun by default; batch candidate selection cannot grant execute
  authority.
- Persist only the selected candidate identity, review ID, actor and note; never persist provider
  payloads, credentials, or arbitrary MediaIdentity.

## Boundaries

- No generic batch framework, batch Metadata query correction, batch RecognitionType setting, batch
  ignore, arbitrary candidate injection, API/UI write endpoint, configuration write, or Phase 21.9.
- Do not redesign CandidateMatcher, MetadataProvider adapters, policy engines, Naming,
  Classification, Planner, OrganizerExecutor, Storage, Scanner or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- A bounded oldest-first pending Metadata NeedConfirm/Ambiguous set can be resolved atomically with
  the same candidate rank.
- Every selected review is RESOLVED, every TaskItem returns to PENDING, and every decision audit
  records the bounded rank/provider/provider ID/media type/actor/note.
- Empty/oversized/limited selection, invalid/absent rank, wrong-state, stale/concurrent decisions
  and injected audit failure fail as one atomic batch.
- Optional task filtering selects only pending reviews in the specified Task.
- Retry/resume selection includes resolved items and loads the stored MetadataSelection.
- C remains C through Metadata and downstream A policy reuse.
- CLI batch selection requires no Storage/provider credentials and performs zero network/media
  mutation.
- DryRun/execution authorization, existing single candidate selection/ignore/retry and schema
  migration regressions pass.

## Validation

Run Phase 21.8, every review/correction/ignore queue, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.8 Result

PASS / FAIL

## Batch Metadata Candidate Workflow

## C Preservation

## Safety

## Regression

## Final Recommendation
