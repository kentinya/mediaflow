# Phase 21.13 — Repository-Native Bounded File Catalog Query

## Goal

Push the bounded FileIndex catalog query down into the FileIndex repository so `files list` no
longer loads every record from every configured ResourceLibrary before filtering and truncating.
Derived Task-result filters remain in the application layer where task persistence semantics live.

## Scope

### 1. Repository protocol and implementations

- Add a bounded query method to `FileIndexRepository` accepting multiple ResourceLibrary IDs,
  optional Storage/scan-status/query filters, stable cursor, and limit.
- Implement it in SQLiteFileIndexRepository with parameterized SQL and keyset cursor semantics.
- Implement it in InMemoryFileIndexRepository for tests and bootstrap behavior.

### 2. Application integration

- Update `FileCatalogService.list` to use the repository-native query for FileIndex filters/cursor/
  limit, then apply derived Task-result filters in memory.
- Preserve existing ordering, cursor, unknown-ID, and bounded-limit validation behavior.

### 3. Safety

- No Storage, Scanner, provider, Planner, OrganizerExecutor or workflow is constructed.
- No arbitrary SQL strings or user-controlled identifiers are interpolated.
- Zero media mutation and no file-content access.

## Boundaries

- No derived-field query pushdown, no full-text index, no UI/API write endpoint, no schema change,
  or Phase 21.14.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- SQLite and in-memory repository-native query return the same filtered/ordered/limited pages as the
  prior application filtering.
- Cursor, ResourceLibrary/Storage/scan-status/query filters and limit are enforced in the
  repository.
- Derived Task-result filters still work after repository-native FileIndex filtering.
- Unknown IDs and invalid cursors still fail closed.
- Existing file catalog list/show, scanner, Dashboard and full offline regressions pass.

## Validation

Run Phase 21.13, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.13 Result

PASS / FAIL

## Repository Query Workflow

## Safety

## Regression

## Final Recommendation
