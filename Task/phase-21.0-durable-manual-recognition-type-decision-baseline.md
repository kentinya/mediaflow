# Phase 21.0 — Durable Manual RecognitionType Decision Baseline

## Goal

Create a persistent, auditable manual-review path for files whose production Recognition result is
Unrecognized, then resume the existing pipeline with an explicitly selected configured
RecognitionType without changing RecognitionRuleEngine semantics.

## Scope

### 1. Recognition review domain and persistence

- Add immutable RecognitionReview, selectable configured type snapshot, selection and decision-audit
  models plus repository protocol.
- Add WAITING_RECOGNITION TaskItem state and SQLite persistence/migration.
- Snapshot only enabled configured RecognitionTypes with bounded stable fields; never infer or default
  a type and never persist media/provider payload or secrets.

### 2. Production waiting flow

- When Recognition status is Unrecognized in a tracked media workflow, persist one idempotent pending
  review, transition the item to WAITING_RECOGNITION and release its source lock.
- Ambiguous Recognition remains its existing outcome unless explicitly supported by a future phase.
- Untracked strategy-test/analyze behavior remains Unrecognized and non-persistent.

### 3. Explicit decision and resume

- Add `mediaflow recognition-reviews list|show|resolve REVIEW_ID --recognition-type TYPE`.
- Resolution must select an enabled type contained in the stored bounded snapshot, record actor/note,
  audit atomically, and return the TaskItem to PENDING.
- Existing explicit `mediaflow tasks resume TASK_ID` loads the resolved selection and re-enters the
  normal RecognitionTypePolicy → Metadata → Naming → Classification → Planner pipeline.
- Manual type selection is an application-level override of one Recognition result; do not add a
  hidden RecognitionRule or mutate configuration. RecognitionType C must remain C.

### 4. Safety and observability

- Review list/show/resolve and resume-selection loading construct no Storage/provider and perform zero
  media mutation. DryRun remains default and execute still needs original plus fresh authorization.
- Expose bounded review status/choices/decision audit through CLI and existing read-only operational
  observability where cleanly supported; never expose saved task scope, tokens or secrets.

## Boundaries

- No editing search title/year, Movie/TV switch, direct Provider ID, arbitrary candidate injection,
  rule creation, bulk actions, Web UI editing or Phase 21.1.
- Do not change RecognitionRuleEngine matching/scoring, MetadataProvider, Naming, Classification,
  Planner, OrganizerExecutor, Storage adapter or automation scheduling semantics.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Unrecognized tracked file creates one bounded pending review, waits and releases lock.
- Choices include only enabled configured types; no hidden default; invalid/disabled/stale selection
  fails atomically; duplicate resolve/create is rejected or idempotent as appropriate.
- CLI list/show/resolve works without Storage/provider credentials and redacts bounded fields.
- Explicit resume consumes the stored type and continues the existing pipeline; unresolved review is
  excluded from blind retry.
- A/B/C selection mappings work and C remains C through Metadata/Naming/Classification/Plan preview.
- Untracked Unrecognized behavior unchanged, zero Storage mutation, schema migration and complete
  existing review/Task/retry regressions.

## Validation

Run Phase 21.0 recognition review, metadata/classification/conflict review, Task pause/resume/retry,
Strategy/Recognition/Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage
adapters, DryRun and full offline suite. Run formatter, lint, compile, dependency, both configuration
validations, FFmpeg/FFprobe audit, wheel build and diff checks.

Update `README.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/progress.md`,
`docs/roadmap.md`, requirements status and product specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.0 Result

PASS / FAIL

## Review Workflow

## C Preservation

## Safety

## Regression

## Final Recommendation
