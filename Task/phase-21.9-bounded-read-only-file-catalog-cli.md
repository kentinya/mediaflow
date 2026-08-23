# Phase 21.9 — Bounded Read-Only File Catalog CLI

## Goal

Add the first bounded, read-only file-browser capability for the durable FileIndex so operators can
inspect indexed files without constructing Storage, Scanner, providers, or any media workflow. This
is not a full UI; it is a CLI visibility boundary for §94/§95 file list and search.

## Scope

### 1. File catalog service

- Add a pure application service that queries the FileIndex only through existing
  `list_by_resource_library` operations.
- Support bounded filters for ResourceLibrary, Storage, FileScanStatus, and path/filename substring
  query.
- Stable ordering by `updated_at DESC, file_id DESC` and a positive bounded result limit.
- Show one indexed record by file ID without Storage/provider access.

### 2. Operator workflow

- Add `mediaflow files list [--resource-library ID] [--storage ID] [--scan-status STATUS]
  [--query TEXT] [--limit N]`.
- Add `mediaflow files show FILE_ID`.
- Require valid bounded limit and enum status; reject unknown resource library/storage IDs.
- Return no Storage/provider construction and zero media mutation.

### 3. Observability

- Output only indexed fields: file ID, Storage, ResourceLibrary, path, filename, extension, size,
  modified/stable/missing timestamps, scan status, change, and last scan ID.
- Never output provider payloads, secrets, credentials, Storage URLs/endpoints, or raw errors.

### 4. Safety

- File catalog commands construct no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor
  or workflow.
- They perform zero network/media mutation and cannot grant execute authority.
- They never trigger scanning or reconcile missing files.

## Boundaries

- No UI, API write endpoint, file contents, thumbnail/poster, provider lookup, metadata enrichment,
  sorting UI beyond stable FileIndex order, arbitrary SQL, recursive filesystem access, or Phase
  21.10.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- File catalog lists only records from configured ResourceLibraries with stable bounded ordering.
- ResourceLibrary, Storage, scan status and query filters are applied without loading unrelated
  records.
- Invalid/empty limit, unknown IDs/status, missing file ID and out-of-scope file ID fail closed.
- CLI list/show works without Storage/provider credentials and performs zero network/media mutation.
- SQLite and in-memory FileIndex behavior are covered with representative records.
- Existing Scanner, Dashboard, Task, review/ignore/retry, DryRun, Storage and schema migration
  regressions pass.

## Validation

Run Phase 21.9, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.9 Result

PASS / FAIL

## File Catalog Workflow

## Safety

## Regression

## Final Recommendation
