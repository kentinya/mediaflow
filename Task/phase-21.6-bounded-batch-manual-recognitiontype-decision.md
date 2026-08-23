# Phase 21.6 — Bounded Batch Manual RecognitionType Decision

## Goal

Add a bounded, auditable batch path for pending Unrecognized manual reviews while preserving the
same explicit RecognitionType selection, current-configuration validation, C-identity, and
zero-mutation safety as Phase 21.0. This is the first batch RecognitionType decision and does not
introduce a generic batch framework or a Web/API write endpoint.

## Scope

### 1. Decision and persistence

- Reuse the existing immutable `RecognitionReview`, `RecognitionReviewChoice`, and
  `RecognitionReviewDecisionAudit` models.
- Atomically resolve a bounded, oldest-first selection of pending RecognitionReviews whose
  TaskItems are still `WAITING_RECOGNITION`.
- Persist the selected type and one bounded actor/note audit per review. No SQLite schema bump is
  required for this batch operation.

### 2. Operator workflow

- Add `mediaflow recognition-reviews resolve-pending --recognition-type TYPE --actor ACTOR
  [--note NOTE] [--limit N] [--task-id TASK_ID]`.
- Require a positive bounded limit, a currently enabled configured RecognitionType, and bounded
  actor/note.
- Filter only pending, matching, still-waiting reviews; optional `--task-id` scopes selection to
  one Task.
- Reject empty selection, disabled/unknown type, type missing from a stored snapshot, wrong-state,
  stale/concurrent changes and injected audit failures atomically as a whole batch.
- Existing explicit `mediaflow tasks resume ORIGINAL_TASK_ID` consumes the stored
  RecognitionSelection and re-enters the normal policy pipeline.

### 3. Recognition semantics

- Batch selection does not mutate RecognitionRuleEngine or configuration.
- Selected reviews carry a visible manual-review RecognitionResult with the explicitly selected
  configured type.
- RecognitionType C and its configured C -> Metadata C / Naming A / Classification A / Organize A
  mapping remain unchanged.

### 4. Safety

- The batch command constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow and performs no network/media mutation.
- Actual media workflow remains DryRun by default; batch recognition decisions cannot grant execute
  authority.
- Persist only the selected configured type, review ID, actor and note; never persist provider
  payloads, credentials, rules, or arbitrary policy edits.

## Boundaries

- No generic batch framework, batch Metadata decision, batch ignore, batch Recognition
  re-evaluation, rule editor/creation, configuration write, API/UI write endpoint, or Phase 21.7.
- Do not redesign RecognitionRuleEngine, policy engines, Metadata, Naming, Classification, Planner,
  OrganizerExecutor, Storage, Scanner or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- A bounded oldest-first pending set can be resolved atomically with the same configured type.
- Every selected review is RESOLVED, every TaskItem returns to PENDING, and every decision audit
  records the bounded type/actor/note.
- Disabled/unknown type, type missing from any snapshot, empty/oversized/limited selection,
  wrong-state, stale/concurrent decisions and injected audit failure fail as one atomic batch.
- Optional task filtering selects only pending reviews in the specified Task.
- Retry/resume selection includes resolved items and loads the stored RecognitionSelection.
- Updated rules resolve A/B/C and C remains C through Metadata and downstream A policy reuse.
- CLI batch resolve requires no Storage/provider credentials and performs zero network/media mutation.
- DryRun/execution authorization, existing single resolve/ignore/retry and schema migration
  regressions pass.

## Validation

Run Phase 21.6, every review/correction/ignore queue, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.6 Result

PASS / FAIL

## Batch RecognitionType Workflow

## C Preservation

## Safety

## Regression

## Final Recommendation
