# Phase 21.1 — Durable Manual Metadata Query Correction

## Goal

Persist a bounded operator correction for Metadata NOT_FOUND, then explicitly resume the existing
provider pipeline with corrected title/year/media type or a direct configured-provider ID.

## Scope

### 1. Correction review and persistence

- Add immutable MetadataCorrectionReview, MetadataCorrectionSelection and decision-audit models.
- Add WAITING_METADATA_CORRECTION TaskItem state and SQLite schema/migration.
- Snapshot RecognitionType, MetadataPolicy ID, configured provider ID, original query/year/media type
  and bounded outcome; never persist provider payload, credentials or arbitrary MediaIdentity.

### 2. Production waiting flow

- A tracked Metadata NOT_FOUND outcome creates one pending correction, waits and releases the source
  lock. Existing NeedConfirm/Ambiguous continues using MetadataReview unchanged.
- Provider/configuration/transient errors remain errors/retry outcomes and must not be disguised as a
  query correction.
- Untracked strategy-test behavior remains unchanged and non-persistent.

### 3. Explicit correction and resume

- Add `mediaflow metadata-corrections list|show|resolve REVIEW_ID` with bounded `--query`, optional
  `--year`, required `--media-type movie|tv`, and optional `--provider-id`.
- Require a non-empty corrected query unless provider ID is supplied. Validate year and ID limits,
  actor/note, current MetadataPolicy/provider/type availability, pending state and stale decisions.
- Existing explicit Task resume loads the correction, reruns the real MetadataProvider path, and then
  continues Naming/Classification/Plan. Direct ID must call existing `identify_by_provider_id`.
- RecognitionType and RecognitionTypePolicy remain unchanged; C must remain C.

### 4. Safety

- Correction commands construct no Storage/provider, make no network request and mutate no media.
- Resume remains DryRun by default; real execution still requires original and fresh execute authority.
- Persist decision intent, not provider secrets, raw responses, authorization headers or arbitrary
  output identity.

## Boundaries

- No arbitrary provider switching, candidate injection, editing Recognition/Naming/Classification,
  bulk correction, ignore action, Web UI editing or Phase 21.2.
- Do not redesign CandidateMatcher, MetadataProvider adapters, policy engines, Planner,
  OrganizerExecutor, Storage adapters or automation scheduling.
- Do not add FFmpeg/FFprobe.

## Required Tests

- NOT_FOUND tracked item creates one bounded pending correction, waits and releases lock.
- NeedConfirm/Ambiguous remains MetadataReview; provider/configuration/transient error creates no
  correction. Unresolved correction is excluded from blind retry.
- Query/year/movie-TV correction reaches the fake provider and changes the result deterministically.
- Direct Provider ID uses the configured provider detail method and bypasses text-search ambiguity.
- Invalid/empty/oversized query, invalid year/media type/provider ID, stale policy/provider/type,
  duplicate resolution and wrong item state fail atomically.
- CLI list/show/resolve works without Storage/provider credentials; zero network/media mutation.
- C remains C through corrected Metadata, Naming, Classification and Plan preview.
- Schema migration and all existing review/Task/retry/Storage/DryRun regressions pass.

## Validation

Run Phase 21.1 correction, Metadata/CandidateMatcher/TMDB, all review queues, Task pause/resume/retry,
Strategy/Recognition/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters,
DryRun and full offline suite. Run formatter, lint, compile, dependency, both configuration
validations, FFmpeg/FFprobe audit, wheel build and diff checks.

Update `README.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/progress.md`,
`docs/roadmap.md`, requirements status and product specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.1 Result

PASS / FAIL

## Correction Workflow

## Direct ID and C Preservation

## Safety

## Regression

## Final Recommendation
