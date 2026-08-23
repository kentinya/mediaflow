# Phase 21.25 — File Detail Re-recognize and Re-plan Web UI/API

## Goal

Expose the existing file-level re-recognize and re-plan request services through authenticated API
endpoints and read-only Files UI buttons. Actual media re-evaluation/re-planning remains explicit
Task resume.

## Scope

### 1. API endpoints

- Add `POST /api/v1/files/{file_id}/re-recognize` with an empty body or optional note.
- Add `POST /api/v1/files/{file_id}/re-plan` with an empty body or optional note.
- Use the authenticated principal as actor and existing bounded services.

### 2. Web UI

- In Files detail, show Re-recognize when a pending RecognitionReview exists.
- Show Re-plan when the latest persisted result is FAILED or PARTIAL.
- Preserve read-only navigation and no execute/Storage mutation UI.

### 3. Safety

- No Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or workflow construction.
- No execute authority can be granted.
- Actual work remains `mediaflow tasks resume ORIGINAL_TASK_ID`.

## Boundaries

- No re-match form yet, no review resolution from file detail, no batch UI, or Phase 21.26.
- Do not redesign Recognition/Policy/Metadata/Planner/OrganizerExecutor/Storage/Scanner.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Authenticated file re-recognize and re-plan endpoints invoke existing services and fail closed for
  missing/invalid states.
- Files UI script renders action buttons only for supported states and no write/execute endpoints.
- Existing operator UI, API security, file catalog and full offline regressions pass.

## Validation

Run Phase 21.25, full offline suite, Ruff, compile, dependency, both example configuration
validations, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.25 Result

PASS / FAIL

## File Detail Web Action Workflow

## Safety

## Regression

## Final Recommendation
