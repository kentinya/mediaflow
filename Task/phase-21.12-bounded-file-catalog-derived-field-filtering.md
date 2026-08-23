# Phase 21.12 — Bounded File Catalog Derived-Field Filtering

## Goal

Extend `mediaflow files list` with bounded filters over the latest persisted Task result for the
same source Storage/path, while preserving the read-only FileIndex boundary. No Storage, Scanner,
provider, Planner or OrganizerExecutor is constructed, and no file contents are read.

## Scope

### 1. Derived filter model

- Add optional RecognitionType, Provider, Provider ID, Title, Task ID, and Year filters to
  `FileCatalogFilter`.
- Apply existing FileIndex filters first, then latest-result derived filters, then stable cursor
  filtering and truncation.
- When any derived filter is present, records without a matching latest Task result are excluded.
- Missing task repository with derived filters fails closed.

### 2. Operator workflow

- Add `--recognition-type TYPE`, `--provider PROVIDER`, `--provider-id ID`, `--title TEXT`,
  `--task-id TASK_ID`, and `--year YEAR` to `mediaflow files list`.
- Preserve all existing list/show filters, cursors and bounded ordering.

### 3. Safety

- Derived-filter commands construct no Storage, Scanner, MetadataProvider, Planner,
  OrganizerExecutor or workflow.
- They perform zero network/media mutation and cannot grant execute authority.
- They never trigger scanning, reconcile, file-content access, or arbitrary SQL.

## Boundaries

- No derived-field sorting, no full media detail API/UI, no arbitrary SQL, no provider lookup, no
  thumbnail/poster, or Phase 21.13.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Each derived filter excludes non-matching records and preserves existing FileIndex filters/cursor.
- Missing latest result is excluded when derived filters are present.
- Derived filters without a task repository fail closed.
- Invalid year and unknown CLI values are rejected by existing argument validation where applicable.
- Existing file list/show, cursor and full offline regressions pass.

## Validation

Run Phase 21.12, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.12 Result

PASS / FAIL

## Derived Filter Workflow

## Safety

## Regression

## Final Recommendation
