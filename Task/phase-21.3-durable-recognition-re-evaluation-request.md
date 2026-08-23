# Phase 21.3 — Durable Recognition Re-evaluation Request

## Goal

Allow an operator to explicitly request re-evaluation of one Unrecognized waiting item after
external recognition configuration changes, then use the existing Task resume pipeline.

## Scope

### 1. Decision and persistence

- Add an immutable bounded RecognitionRetryDecision audit model and a visible
  `retry_requested` RecognitionReview status.
- Atomically transition only a pending RecognitionReview plus its matching
  `WAITING_RECOGNITION` TaskItem back to `PENDING`.
- Bump and migrate SQLite schema; preserve historical choices, decisions and ignore audits.

### 2. Operator workflow

- Add `mediaflow recognition-reviews retry REVIEW_ID --actor ACTOR [--note NOTE]`.
- Require the review/item/task relationship, pending/waiting state and bounded actor/note.
- Reject resolved, ignored, duplicate, stale, missing and concurrent retry requests atomically.
- Existing `mediaflow tasks resume ORIGINAL_TASK_ID` must rerun the production parser/recognition
  pipeline without injecting a RecognitionSelection.

### 3. Recognition semantics

- Re-evaluation consumes the current externally loaded RecognitionRules and ResourceLibrary context.
- If a new rule matches, continue through the existing policy/Metadata/DryRun pipeline.
- If no rule matches, remain Unrecognized and create a new waiting review in the continuation Task.
- Never default to A, mutate rules/configuration, or preserve a stale manual selection.
- RecognitionType C and its configured C -> Metadata C / Naming A / Classification A / Organize A
  mapping remain unchanged when a current rule resolves C.

### 4. Safety

- The retry-request command constructs no Storage, Scanner, provider or workflow and performs no
  network/media mutation.
- Actual re-evaluation occurs only on separate explicit Task resume and is DryRun by default.
- Real execution cannot gain authority beyond the existing original-plus-fresh authorization rules.

## Boundaries

- No rule editor/creation, configuration write, automatic config reload, batch retry, Metadata
  re-search command, API/UI write endpoint or Phase 21.4.
- Do not redesign RecognitionRuleEngine, policy engines, Metadata, Planner, OrganizerExecutor,
  Storage, Scanner or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Pending RecognitionReview can atomically request retry and returns its item to PENDING.
- Audit records bounded actor/note; stale/resolved/ignored/wrong-state/missing/concurrent requests fail.
- Retry request is included by resume selection but injects no manual RecognitionType.
- Updated rule configuration resolves A/B/C; unchanged unmatched configuration waits again.
- C remains C through Metadata and downstream A policy reuse.
- CLI retry request requires no Storage/provider credentials and performs zero network/media mutation.
- DryRun/execution authorization, existing manual selection/ignore and schema migration regressions pass.

## Validation

Run Phase 21.3, every review/correction/ignore queue, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.3 Result

PASS / FAIL

## Re-evaluation Workflow

## Recognition and C Preservation

## Safety

## Regression

## Final Recommendation
