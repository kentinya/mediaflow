# Phase 21.20 — File Detail Related Task/Review Linkage

## Goal

Enrich `files show` / File detail with read-only links to the latest persisted Task and any matching
Recognition/Metadata review queues for the same source Storage/path, so an operator can navigate
from file detail to the correct action queue without constructing Storage or providers.

## Scope

### 1. Related review query

- Add a bounded query that returns RecognitionReview, MetadataReview, and
  MetadataCorrectionReview records whose `source_storage_id` and `source_path` match a file.
- Include only safe fields: kind, review ID, status, Task ID.

### 2. Detail integration

- Extend FileCatalogDetail with related review links.
- Expose them in `GET /api/v1/files/{file_id}` and render them in the Files UI.

### 3. Safety

- No Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or workflow is constructed.
- No review mutation or provider lookup is performed.

## Boundaries

- No re-recognize/re-match/re-plan actions, no review resolution from file detail, or Phase 21.21.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- File detail returns matching review links for Recognition/Metadata review types and empty links
  when none exist.
- API file detail includes related reviews and no unsafe review fields.
- UI script renders related review IDs without write endpoints.
- Existing file catalog, operator UI, API security and full offline regressions pass.

## Validation

Run Phase 21.20, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.20 Result

PASS / FAIL

## File Detail Linkage Workflow

## Safety

## Regression

## Final Recommendation
