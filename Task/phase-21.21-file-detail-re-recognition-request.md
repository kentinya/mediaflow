# Phase 21.21 — File Detail Re-recognition Request

## Goal

Allow an operator to request re-recognition for one indexed file that currently has a pending
RecognitionReview, using the existing `RecognitionRetryService`. Actual re-evaluation remains a
separate explicit Task resume.

## Scope

### 1. CLI command

- Add `mediaflow files re-recognize FILE_ID --actor ACTOR [--note NOTE]`.
- Resolve the FileIndex record, find a pending related RecognitionReview, and atomically request
  retry.
- Reject missing file, missing latest result, no pending RecognitionReview, and invalid actor/note.

### 2. Safety

- The command constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow and performs zero network/media mutation.
- Actual re-evaluation occurs only on `mediaflow tasks resume ORIGINAL_TASK_ID`.
- Cannot grant execute authority.

## Boundaries

- No API/UI write endpoint yet, no metadata re-match or re-plan, no rule/configuration write, or
  Phase 21.22.
- Do not redesign RecognitionRuleEngine, policy engines, Metadata, Planner, OrganizerExecutor,
  Storage, Scanner or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- A file with a pending RecognitionReview can request re-recognition and returns its TaskItem to
  PENDING.
- Missing file, missing pending RecognitionReview, invalid actor/note and duplicate/concurrent
  requests fail closed.
- CLI re-recognize requires no Storage/provider credentials and performs zero network/media
  mutation.
- Existing file catalog, recognition review/retry, DryRun/execution and schema migration regressions
  pass.

## Validation

Run Phase 21.21, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.21 Result

PASS / FAIL

## File Re-recognition Workflow

## Safety

## Regression

## Final Recommendation
