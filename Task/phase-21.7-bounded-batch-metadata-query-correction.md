# Phase 21.7 — Bounded Batch Metadata Query Correction

## Goal

Add a bounded, auditable batch path for pending Metadata NOT_FOUND correction reviews while
preserving the same explicit query/year/media-type/provider-ID validation, current-policy checks,
zero-mutation command boundary, and separate Task resume semantics as Phase 21.1. This is the first
batch Metadata correction operation and does not introduce a generic batch framework or a Web/API
write endpoint.

## Scope

### 1. Decision and persistence

- Reuse the existing immutable `MetadataCorrectionReview` and
  `MetadataCorrectionDecisionAudit` models.
- Atomically resolve a bounded, oldest-first selection of pending MetadataCorrectionReviews whose
  TaskItems are still `WAITING_METADATA_CORRECTION`.
- Persist the same corrected query/year/media-type/provider-ID and one bounded actor/note audit per
  review. No SQLite schema bump is required for this batch operation.

### 2. Operator workflow

- Add `mediaflow metadata-corrections resolve-pending --media-type movie|tv
  [--query QUERY | --provider-id PROVIDER_ID] [--year YEAR] --actor ACTOR [--note NOTE]
  [--limit N] [--task-id TASK_ID]`.
- Require a non-empty corrected query unless a valid direct provider ID is supplied, a valid
  movie/tv media type, bounded year/actor/note, and a positive bounded limit.
- Filter only pending, matching, still-waiting corrections; optional `--task-id` scopes selection to
  one Task.
- Reject empty selection, disabled/stale policy/provider, invalid query/year/media type/provider ID,
  wrong-state, stale/concurrent changes and injected audit failures atomically as a whole batch.
- Existing `mediaflow tasks resume ORIGINAL_TASK_ID` reruns the real MetadataProvider path using the
  stored correction.

### 3. Metadata semantics

- Corrected text uses the existing provider search/matcher behavior; direct provider ID uses the
  existing configured-provider detail path.
- The effective Movie/TV query type applies only to this correction attempt and does not mutate the
  configured MetadataPolicy.
- RecognitionType and all resolved downstream policy references remain unchanged, including
  C -> Metadata C / Naming A / Classification A / Organize A.

### 4. Safety

- The batch command constructs no Storage, Scanner, MetadataProvider, Planner, OrganizerExecutor or
  workflow and performs no network/media mutation.
- Actual metadata lookup occurs only on separate explicit Task resume and remains DryRun by default.
- Real execution cannot gain authority beyond the existing original-plus-fresh authorization rules.

## Boundaries

- No generic batch framework, batch Metadata candidate selection, batch RecognitionType setting,
  batch ignore, arbitrary provider switching, arbitrary MediaIdentity injection, API/UI write
  endpoint, configuration write, or Phase 21.8.
- Do not redesign CandidateMatcher, MetadataProvider adapters, policy engines, Naming,
  Classification, Planner, OrganizerExecutor, Storage, Scanner or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- A bounded oldest-first pending Metadata NOT_FOUND correction set can be resolved atomically with
  the same validated corrected inputs.
- Every selected correction is RESOLVED, every TaskItem returns to PENDING, and every decision audit
  records bounded query/year/media-type/provider-ID/actor/note.
- Empty/oversized/limited selection, disabled/stale policy/provider, invalid query/year/media
  type/provider ID, wrong-state, stale/concurrent decisions and injected audit failure fail as one
  atomic batch.
- Optional task filtering selects only pending corrections in the specified Task.
- Retry/resume selection includes resolved items and loads the stored MetadataCorrectionSelection.
- C remains C through corrected Metadata and downstream A policy reuse.
- CLI batch correction requires no Storage/provider credentials and performs zero network/media
  mutation.
- DryRun/execution authorization, existing single correction/ignore/retry and schema migration
  regressions pass.

## Validation

Run Phase 21.7, every review/correction/ignore queue, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.7 Result

PASS / FAIL

## Batch Metadata Correction Workflow

## Direct ID and C Preservation

## Safety

## Regression

## Final Recommendation
