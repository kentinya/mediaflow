# Phase 21.18 — Files Web UI Search and Filter Enhancement

## Goal

Add a read-only search/filter form to the existing Files operator view using the already exposed
FileCatalog filters, without adding write/execute actions or constructing Storage/provider
adapters.

## Scope

### 1. UI filters

- Add bounded controls for ResourceLibrary, Storage, scan status, path/filename query, Recognition
  type, Provider, Provider ID, Title, Task ID, and Year.
- Build the `/api/v1/files` query string from only populated controls.
- Preserve the existing file list and detail rendering.

### 2. API validation

- Ensure all supported file catalog query fields are accepted once and rejected when repeated or
  invalid.
- Keep the endpoints read-only and authenticated.

### 3. Safety

- No UI/API write/execute action is added.
- No Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or workflow is constructed.

## Boundaries

- No pagination cursor UI beyond the existing bounded list, no full-text index, no saved searches,
  or Phase 21.19.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- UI script renders filter controls and `/api/v1/files?limit=100` plus supported filter parameters.
- API accepts supported file catalog filters and rejects duplicate/unknown fields.
- Existing file catalog list/detail/stats, operator UI, API security and full offline regressions
  pass.

## Validation

Run Phase 21.18, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.18 Result

PASS / FAIL

## Files Filter Workflow

## Safety

## Regression

## Final Recommendation
