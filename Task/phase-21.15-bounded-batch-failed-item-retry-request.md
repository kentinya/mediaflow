# Phase 21.15 — Bounded Batch Failed-Item Retry Request

## Goal

Add a bounded, auditable batch request that returns selected FAILED/PARTIAL TaskItems to PENDING so
operators can later run the existing explicit Task resume path. The request itself is database-only
and never executes media workflows.

## Scope

### 1. Decision and persistence

- Add an immutable bounded `TaskRetryRequestDecision` audit model and a new SQLite audit table.
- Select a bounded oldest-first set of FAILED/PARTIAL TaskItems across all Tasks or one optional
  Task.
- Atomically transition each selected item to PENDING with stage `task_retry_requested`.

### 2. Operator workflow

- Add `mediaflow tasks retry-request --actor ACTOR [--note NOTE] [--limit N] [--task-id TASK_ID]`.
- Require bounded actor/note and a positive bounded limit.
- Reject empty selection, stale/concurrent changes and injected audit failures atomically.
- Existing `mediaflow tasks resume ORIGINAL_TASK_ID` performs the actual retry.

### 3. Safety

- The command constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow and performs no network/media mutation.
- DryRun remains default; the request cannot grant execute authority.
- Preserve existing original-plus-fresh execute authorization boundaries.

## Boundaries

- No batch ignore/resolve/re-evaluation, no automatic retry execution, no Web/API write endpoint,
  or Phase 21.16.
- Do not redesign Task coordinator, policy engines, Metadata, Planner, OrganizerExecutor, Storage,
  Scanner or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Bounded FAILED/PARTIAL items are selected oldest-first and atomically returned to PENDING.
- Every selected item audit records bounded actor/note; empty/oversized/limited selection,
  wrong-state, stale/concurrent changes and injected audit failure fail as one atomic batch.
- Optional Task scoping selects only that Task's failed/partial items.
- Existing resume selection includes requested items without changing execute authority.
- CLI retry request requires no Storage/provider credentials and performs zero network/media
  mutation.
- Schema migration and full offline regressions pass.

## Validation

Run Phase 21.15, every review/correction/ignore queue, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.15 Result

PASS / FAIL

## Batch Retry Request Workflow

## Safety

## Regression

## Final Recommendation
