# Phase 21.11 — Bounded File Catalog Detail Enrichment

## Goal

Enrich `mediaflow files show` with the latest persisted Task result for the same source Storage and
path, while preserving the read-only FileIndex boundary. No Storage, Scanner, provider, Planner or
OrganizerExecutor is constructed, and no file contents are read.

## Scope

### 1. Detail model and repository

- Add a repository method that returns the latest persisted `PersistentResultRecord` for a given
  source Storage ID and source path.
- Add an immutable detail view containing the indexed FileIndexRecord plus that optional latest
  result.
- Never expose provider payloads, credentials, Storage URLs/endpoints, raw errors, or result rows
  outside the selected source.

### 2. Operator workflow

- Extend `mediaflow files show FILE_ID [--resource-library ID]` to render available indexed fields
  plus latest Task result fields when present.
- Preserve all existing `files list` cursor/filter behavior unchanged.

### 3. Safety

- The detail path constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow.
- It performs zero network/media mutation and cannot grant execute authority.
- It never triggers scanning, reconcile, file-content access, or arbitrary SQL.

## Boundaries

- No list filtering by derived fields, no file list enrichment, no UI/API write endpoint, no
  thumbnail/poster, no provider lookup, no media metadata re-search, or Phase 21.12.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- File detail returns the matching indexed record plus the latest persisted Task result for the same
  source Storage/path.
- Missing source result produces an explicit absent detail without failure or fallback.
- Unknown/out-of-scope file ID and invalid resource library still fail closed.
- CLI detail works without Storage/provider credentials and performs zero network/media mutation.
- Existing file list cursor/filter and full offline regressions pass.

## Validation

Run Phase 21.11, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.11 Result

PASS / FAIL

## File Detail Workflow

## Safety

## Regression

## Final Recommendation
