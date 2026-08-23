# Phase 21.23 — File Detail Re-plan/Retry Request

## Goal

Allow an operator to request re-planning/retry for one indexed file whose latest persisted
TaskResult is FAILED or PARTIAL, by atomically returning that specific TaskItem to PENDING. Actual
re-planning and optional organization remain explicit Task resume actions.

## Scope

### 1. Specific-item retry service

- Extend TaskRetryRequestService with a single-item request method for a given TaskItem ID.
- Require the item to be FAILED or PARTIAL and record the existing immutable task retry audit.

### 2. File-level CLI

- Add `mediaflow files re-plan FILE_ID --actor ACTOR [--note NOTE]`.
- Resolve the file's latest TaskResult and request retry for its item.
- Reject missing file, missing latest result, non-failed/partial result, and invalid actor/note.

### 3. Safety

- The command constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow and performs zero network/media mutation.
- Actual re-planning occurs only on `mediaflow tasks resume ORIGINAL_TASK_ID`.
- Cannot grant execute authority.

## Boundaries

- No automatic execution, no new plan generation in the command, no API/UI write endpoint, or
  Phase 21.24.
- Do not redesign Task coordinator, policy engines, Metadata, Planner, OrganizerExecutor, Storage,
  Scanner or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- A file with latest FAILED/PARTIAL result can request re-plan and returns its item to PENDING.
- Missing file/result, non-failed/partial result, invalid actor/note and concurrent/duplicate
  requests fail closed.
- CLI re-plan requires no Storage/provider credentials and performs zero network/media mutation.
- Existing Task retry, file catalog, DryRun/execution and schema migration regressions pass.

## Validation

Run Phase 21.23, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.23 Result

PASS / FAIL

## File Re-plan Workflow

## Safety

## Regression

## Final Recommendation
