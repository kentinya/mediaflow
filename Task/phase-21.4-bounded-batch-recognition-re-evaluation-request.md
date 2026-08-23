# Phase 21.4 — Bounded Batch Recognition Re-evaluation Request

## Goal

Add a bounded, auditable batch path for pending Unrecognized manual reviews while preserving the
same per-review atomic, credential-independent, zero-mutation safety as Phase 21.3. This is the
first explicitly scoped batch manual-workflow operation and does not introduce a generic batch
system or a Web/API write endpoint.

## Scope

### 1. Batch decision and persistence

- Reuse the existing immutable `RecognitionRetryDecision` audit model and
  `retry_requested` RecognitionReview status.
- Atomically transition a bounded, oldest-first selection of pending RecognitionReviews whose
  TaskItems are still `WAITING_RECOGNITION` back to `PENDING`.
- Preserve every existing single-retry, manual selection, ignore, schema migration, and resume
  semantic. No SQLite schema bump is required for this batch operation.

### 2. Operator workflow

- Add `mediaflow recognition-reviews retry-pending --actor ACTOR [--note NOTE] [--limit N]
  [--task-id TASK_ID]`.
- Require a positive bounded limit and bounded actor/note.
- Filter only pending, matching, still-waiting reviews; optional `--task-id` scopes selection to
  one Task.
- Reject empty selection, stale/resolved/ignored/wrong-state/missing and concurrent changes
  atomically as a whole batch.
- Existing `mediaflow tasks resume ORIGINAL_TASK_ID` reruns the production parser/recognition
  pipeline without injecting a `RecognitionSelection`.

### 3. Recognition semantics

- Re-evaluation consumes current externally loaded RecognitionRules and original ResourceLibrary
  context, exactly as Phase 21.3.
- A current match continues through policy/Metadata/DryRun; an unchanged miss remains Unrecognized
  and creates a new waiting review in the continuation Task.
- Never default to A, mutate rules/configuration, or preserve a stale manual selection.
- RecognitionType C and its configured C -> Metadata C / Naming A / Classification A / Organize A
  mapping remain unchanged when a current rule resolves C.

### 4. Safety

- The batch command constructs no Storage, Scanner, provider, Planner, OrganizerExecutor or
  workflow and performs no network/media mutation.
- Actual re-evaluation occurs only on separate explicit Task resume and remains DryRun by default.
- Real execution cannot gain authority beyond existing original-plus-fresh authorization rules.

## Boundaries

- No generic batch framework, batch ignore, batch metadata re-search, batch RecognitionType
  setting, API/UI write endpoint, rule editor/creation, configuration write, automatic config
  reload, or Phase 21.5.
- Do not redesign RecognitionRuleEngine, policy engines, Metadata, Planner, OrganizerExecutor,
  Storage, Scanner or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- A bounded oldest-first pending set can atomically request retry and every matching item returns
  to PENDING.
- Audit records bounded actor/note for every selected review; empty/oversized/limited selection,
  wrong-state, resolved/ignored/missing and injected audit failure fail as one atomic batch.
- Optional task filtering selects only pending reviews in the specified Task.
- Retry-requested items are included by resume selection but inject no manual RecognitionType.
- Updated rules resolve A/B/C and an unchanged unmatched configuration waits again.
- C remains C through Metadata and downstream A policy reuse.
- CLI batch retry requires no Storage/provider credentials and performs zero network/media mutation.
- DryRun/execution authorization, existing manual selection/ignore/single-retry and schema migration
  regressions pass.

## Validation

Run Phase 21.4, every review/correction/ignore queue, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.4 Result

PASS / FAIL

## Batch Re-evaluation Workflow

## Recognition and C Preservation

## Safety

## Regression

## Final Recommendation
