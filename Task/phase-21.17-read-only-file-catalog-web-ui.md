# Phase 21.17 — Read-Only File Catalog Web UI

## Goal

Expose the existing read-only FileCatalog CLI capabilities through the existing dependency-free
operator Web UI and authenticated API, without adding any write, execute, organize, or workflow
control.

## Scope

### 1. API

- Add `GET /api/v1/files` with bounded filters matching the CLI: ResourceLibrary, Storage,
  scan status, query, cursor, limit, and derived latest-Task-result filters.
- Add `GET /api/v1/files/{file_id}` with indexed fields plus latest persisted Task result when
  present.
- Add `GET /api/v1/files/stats` with total and scan-status counts.
- Require an existing read permission; reject write/execute fields and unknown IDs/status.

### 2. Web UI

- Add a read-only Files view to the existing operator UI with filters, stable Previous/Next cursor
  navigation, and a file detail view.
- No UI form may submit a write endpoint or construct Storage/provider adapters.

### 3. Safety

- The API/UI never constructs Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow and performs zero media mutation.

## Boundaries

- No file list editing, re-recognize/re-match/re-plan actions, upload, delete, execute, configuration
  write, or Phase 21.18.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Authenticated files list/detail/stats APIs honor filters, cursor, and bounded limits.
- Read permission is required; write/execute fields and unknown IDs/status fail closed.
- UI script renders only read-only Files endpoints and no write/execute/Storage construction.
- Existing operator UI, API security, file catalog, scanner, Dashboard and full offline regressions
  pass.

## Validation

Run Phase 21.17, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.17 Result

PASS / FAIL

## File Catalog Web UI Workflow

## Safety

## Regression

## Final Recommendation
