# Phase 21.22 — File Detail Metadata Re-match/Correction

## Goal

Allow an operator to correct/re-match Metadata for one indexed file that currently has a pending
MetadataCorrectionReview, using the existing `MetadataCorrectionService`. Actual provider lookup
still occurs on explicit Task resume.

## Scope

### 1. CLI command

- Add `mediaflow files re-match FILE_ID --media-type movie|tv
  [--query QUERY | --provider-id PROVIDER_ID] [--year YEAR] --actor ACTOR [--note NOTE]`.
- Resolve the file, find a pending MetadataCorrectionReview, and atomically resolve it with bounded
  validated inputs.
- Reject missing file, missing pending review, invalid query/year/media-type/provider-ID and
  stale/concurrent changes.

### 2. Safety

- The command constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow and performs no network/media mutation.
- Actual provider access occurs only on `mediaflow tasks resume ORIGINAL_TASK_ID`.
- Cannot grant execute authority.

## Boundaries

- No arbitrary provider switching, candidate injection, recognition/Naming/Classification edits,
  API/UI write endpoint, or Phase 21.23.
- Do not redesign MetadataProvider, policy engines, Planner, OrganizerExecutor, Storage, Scanner or
  automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- A file with a pending MetadataCorrectionReview can be corrected/re-matched and returns its item to
  PENDING.
- Missing file/review, invalid query/year/media-type/provider-ID and stale/concurrent changes fail
  closed.
- CLI re-match requires no Storage/provider credentials and performs zero network/media mutation.
- Existing metadata correction, file catalog, DryRun/execution and schema migration regressions
  pass.

## Validation

Run Phase 21.22, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.22 Result

PASS / FAIL

## File Metadata Re-match Workflow

## Safety

## Regression

## Final Recommendation
