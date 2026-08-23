# Phase 21.26 — File Detail Metadata Re-match Web UI/API and Phase 21 Closure

## Goal

Complete the final Phase 21 file-detail action by adding authenticated file-level Metadata re-match
API/UI and then mark the accepted Phase 21 manual workflow boundary as closed in documentation.

## Scope

### 1. API endpoint

- Add `POST /api/v1/files/{file_id}/re-match` with bounded `query`, optional `year`, required
  `mediaType`, optional `providerId`, and optional `note`.
- Use the authenticated principal as actor and existing FileMetadataCorrectionService.

### 2. Web UI

- Show a re-match action when a pending MetadataCorrectionReview exists.
- Render a minimal read-only form with query, media type, year, provider ID, and note.
- No Storage/provider/workflow construction.

### 3. Phase 21 closure

- Reconcile documentation to state that the accepted Phase 21 bounded scope is complete; remaining
  non-claims are Phase 22 and deployment-specific work.

## Boundaries

- No review resolution/execute/Storage mutation UI beyond existing requests.
- Do not redesign Metadata/Planner/Organizer/Storage/Scanner or policy engines.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Authenticated file re-match endpoint invokes the existing MetadataCorrectionService and fails
  closed for missing/invalid inputs.
- Files UI renders re-match form only for pending MetadataCorrectionReview.
- Existing operator UI/API, file catalog, metadata correction and full offline regressions pass.

## Validation

Run Phase 21.26, full offline suite, Ruff, compile, dependency, both example configuration
validations, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.26 Result

PASS / FAIL

## File Metadata Re-match Web UI Workflow

## Phase 21 Closure Status

## Safety

## Regression

## Final Recommendation
