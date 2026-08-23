# Phase 21.2 — Durable Manual Ignore Decision

## Goal

Allow an operator to explicitly and durably ignore one item waiting for Recognition or Metadata
human input, with an immutable audit record and zero media mutation.

## Scope

### 1. Domain and persistence

- Add `IGNORED` TaskItem status and immutable bounded `ManualIgnoreDecision` audit evidence.
- Support only items currently waiting in `WAITING_RECOGNITION`, `WAITING_METADATA`, or
  `WAITING_METADATA_CORRECTION`.
- Atomically mark the corresponding pending RecognitionReview, MetadataReview, or
  MetadataCorrectionReview as ignored and mark the TaskItem ignored.
- Bump and migrate the SQLite runtime schema without rewriting historical decisions.

### 2. Operator command

- Add `mediaflow tasks ignore-item TASK_ID ITEM_ID --actor ACTOR [--note NOTE]`.
- Validate task/item ownership, supported waiting state, matching pending review, bounded actor/note,
  duplicate/stale decisions and concurrent resolution.
- Show ignored status in existing Task and review queue output.

### 3. Runtime semantics

- Ignored items are terminal operator outcomes: exclude them from resume, retry-failed and blind
  workflow retry.
- An ignored item is not success, failure, cancellation or deletion. Batch/Task aggregation remains
  explicit and must not cause the Task to appear fully completed without surfacing ignored count.
- RecognitionType, policy configuration and provider results are not modified.

### 4. Safety

- Ignore constructs no Storage, Scanner, MetadataProvider, Planner or OrganizerExecutor.
- It performs no network request and zero media mutation.
- No source file deletion, FileIndex deletion, ignore-rule/configuration edit or future automatic
  suppression of newly scanned files.

## Boundaries

- No batch ignore, Classification/conflict ignore, Web/API write endpoint, UI editing, rule creation,
  persistent path suppression or Phase 21.3.
- Do not redesign existing Recognition, Metadata, Naming, Classification, Planner, Executor,
  Storage, Scanner or policy engines.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Recognition, Metadata candidate and Metadata NOT_FOUND correction waits can each be ignored.
- TaskItem and matching review transition atomically; audit preserves bounded actor/note and kind.
- Wrong task/item, unsupported state, missing/mismatched review, duplicate/stale/concurrent decisions
  fail atomically.
- Ignored items are excluded from resume/retry and remain visible in Task/review output and summary.
- CLI ignore works without Storage/provider credentials and performs zero network/media mutation.
- Existing resolve behavior, C preservation, DryRun and execution authorization remain unchanged.
- Schema migration and full offline regression pass.

## Validation

Run Phase 21.2 tests, all Recognition/Metadata/Correction/Classification/conflict reviews, Task
pause/resume/retry, Strategy/policy engines, Planner/Organizer, Scanner/FileIndex, every Storage
adapter, DryRun and the full offline suite. Run formatter, lint, compile, dependency, example/user
configuration validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and the product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.2 Result

PASS / FAIL

## Ignore Workflow

## Terminal Semantics

## Safety

## Regression

## Final Recommendation
