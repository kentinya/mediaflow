# Phase 21.14 — Derived Filter Task Result Join Pushdown

## Goal

Push the latest-Task-result derived filters from `files list` into a parameterized SQLite join
between FileIndex and TaskResult rows, eliminating the per-file latest-result lookup while
preserving the read-only FileIndex boundary.

## Scope

### 1. Joined query and model

- Add an immutable `FileCatalogEnrichedRecord` containing a FileIndexRecord and optional latest
  PersistentResultRecord.
- Add a SQLite repository method that joins FileIndex to the latest TaskResult for the same source
  Storage/path in one query and applies derived filters in SQL.
- Preserve existing FileIndex filters, cursor semantics, stable ordering and bounded limit.

### 2. Application integration

- Update `FileCatalogService.list` to use the joined query when derived filters are present and the
  repository supports it; otherwise retain the previous fallback.
- Continue to fail closed when derived filters are requested without a Task repository.

### 3. Safety

- No Storage, Scanner, provider, Planner, OrganizerExecutor or workflow is constructed.
- No arbitrary SQL identifiers are interpolated.
- Zero media mutation and no file-content access.

## Boundaries

- No derived-filter sorting, no full-text index, no UI/API write endpoint, no schema change, or
  Phase 21.15.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- SQLite joined query returns the same filtered/ordered/limited pages as the fallback application
  filtering for each derived field.
- Missing latest result excludes records when derived filters are present.
- Derived filters without a Task repository still fail closed.
- Existing file catalog list/show, cursor, derived-filter and full offline regressions pass.

## Validation

Run Phase 21.14, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.14 Result

PASS / FAIL

## Join Pushdown Workflow

## Safety

## Regression

## Final Recommendation
