# Phase 21.10 — Bounded File Catalog Cursor Pagination

## Goal

Add stable, bounded keyset pagination to the read-only FileIndex catalog introduced in Phase 21.9.
The catalog remains a pure FileIndex query surface with no Storage, Scanner, provider, workflow, or
media mutation.

## Scope

### 1. Cursor model and service

- Extend `FileCatalogFilter` with mutually exclusive `after`/`before` keyset cursors using the same
  stable order as Phase 21.9: `(updated_at DESC, file_id DESC)`.
- Apply ResourceLibrary/Storage/scan-status/query filters before cursor filtering and truncation.
- Return at most the bounded configured limit; reject invalid/mutually-exclusive cursors and unknown
  IDs exactly as Phase 21.9.

### 2. Operator workflow

- Add `--after ISO_TIMESTAMP --cursor-file-id FILE_ID` and
  `--before ISO_TIMESTAMP --cursor-file-id FILE_ID` to `mediaflow files list`.
- Require both timestamp and file ID when either cursor direction is supplied.
- Preserve all existing `files list` and `files show` behavior and output.

### 3. Safety

- File catalog cursor commands construct no Storage, Scanner, MetadataProvider, Planner,
  OrganizerExecutor or workflow.
- They perform zero network/media mutation and cannot grant execute authority.
- They never trigger scanning, reconcile, file-content access, or arbitrary SQL.

## Boundaries

- No offset pagination, dynamic filters, UI, API write endpoint, derived pipeline fields, file
  contents, thumbnail/poster, provider lookup, or Phase 21.11.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Stable cursor filtering returns the expected older/newer pages in the established order.
- ResourceLibrary/Storage/scan-status/query filters are applied before cursor filtering and limit.
- Invalid/mutually-exclusive/missing cursor components and unknown IDs fail closed.
- Existing Phase 21.9 list/show, bounded limit, ordering and zero-Storage CLI regressions pass.
- Full offline suite and all quality gates pass.

## Validation

Run Phase 21.10, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.10 Result

PASS / FAIL

## File Catalog Cursor Workflow

## Safety

## Regression

## Final Recommendation
