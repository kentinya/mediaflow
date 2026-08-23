# Phase 21.5 — Bounded Batch Manual Ignore

## Goal

Add a bounded, auditable batch path for pending Recognition and Metadata manual-review waits while
preserving the same terminal, credential-independent, zero-mutation safety as Phase 21.2. This is
the first batch ignore operation and does not introduce a generic batch framework or a Web/API
write endpoint.

## Scope

### 1. Decision and persistence

- Reuse the existing immutable `ManualIgnoreDecision` audit model and `ManualReviewKind`.
- Atomically transition a bounded, oldest-first selection of TaskItems in supported waiting states
  plus their matching pending RecognitionReview, MetadataReview, or MetadataCorrectionReview.
- Preserve every existing single-ignore, review resolution, resume, retry, and schema migration
  semantic. No SQLite schema bump is required for this batch operation.

### 2. Operator workflow

- Add `mediaflow tasks ignore-pending --actor ACTOR [--note NOTE] [--limit N] [--task-id TASK_ID]`.
- Require a positive bounded limit and bounded actor/note.
- Filter only TaskItems currently in `WAITING_RECOGNITION`, `WAITING_METADATA`, or
  `WAITING_METADATA_CORRECTION` with a matching pending review; optional `--task-id` scopes
  selection to one Task.
- Reject empty selection, wrong-state, missing/mismatched review, stale/concurrent changes and
  injected audit failures atomically as a whole batch.
- Existing Task/review output and summary semantics remain visible: ignored items are terminal,
  excluded from resume/retry, and prevent a Task from appearing fully completed without surfacing
  ignored count.

### 3. Runtime semantics

- Every selected item is marked `IGNORED` and its matching review is marked ignored.
- Ignored items are excluded from resume, retry-failed, and blind workflow retry.
- Ignored is not success, failure, cancellation, or deletion; no FileIndex deletion, rule creation,
  configuration edit, or future-scan suppression occurs.

### 4. Safety

- The batch command constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor,
  or workflow and performs no network/media mutation.
- Actual media workflow remains DryRun by default; batch ignore cannot grant execute authority.
- Persist only bounded review kind, review ID, actor, and note; never persist provider payloads,
  paths beyond the existing TaskItem/review snapshot, credentials, or secrets.

## Boundaries

- No generic batch framework, batch Metadata re-search, batch Recognition re-evaluation,
  batch RecognitionType setting, classification/conflict ignore, API/UI write endpoint, rule
  creation, persistent path suppression, or Phase 21.6.
- Do not redesign Recognition, Metadata, Naming, Classification, Planner, OrganizerExecutor,
  Storage, Scanner, or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- A bounded oldest-first pending set across Recognition, Metadata candidate and Metadata NOT_FOUND
  correction waits can be ignored atomically.
- Every selected TaskItem and matching review transitions atomically; audit records bounded
  kind/review/actor/note.
- Empty/oversized/limited selection, wrong task/item, unsupported state, missing/mismatched review,
  stale/concurrent decisions and injected audit failure fail as one atomic batch.
- Optional task filtering selects only pending reviews in the specified Task.
- Ignored items are excluded from resume/retry and remain visible in Task/review output and summary.
- CLI batch ignore requires no Storage/provider credentials and performs zero network/media mutation.
- Existing resolve behavior, C preservation, DryRun and execution authorization remain unchanged.
- Schema migration and full offline regression pass.

## Validation

Run Phase 21.5, every review/correction/ignore queue, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.5 Result

PASS / FAIL

## Batch Ignore Workflow

## Terminal Semantics

## Safety

## Regression

## Final Recommendation
