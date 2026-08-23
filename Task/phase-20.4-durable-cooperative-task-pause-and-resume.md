# Phase 20.4 — Durable Cooperative Task Pause and Resume

## Goal

Add an explicit, persistent pause request and safe continuation state machine for long-running
MediaFlow Tasks without interrupting an in-flight media operation or weakening execution authority.

## Scope

### 1. Persistent state and migration

- Add PAUSED Task/TaskItem states and a durable pause-request flag through a forward-only SQLite
  migration. Existing databases and records remain readable.
- Expose repository operations that atomically request pause and inspect the request.
- Persist the safe checkpoint transition, timestamps and bounded reason without storing secrets.

### 2. Cooperative safe checkpoints

- A pause request is observed only before scheduling the next media item or Scanner unit of work.
- Never interrupt Parser/Metadata/Naming/Classification/Planner or OrganizerExecutor mid-call.
- An in-flight item may finish normally; no rollback is triggered merely because pause was requested.
- Once acknowledged, pending/processing work becomes PAUSED, Task locks are released, and the Task
  becomes PAUSED rather than Completed/Cancelled/Failed.

### 3. Explicit continuation

- Add `mediaflow tasks pause <task-id>` and preserve `mediaflow tasks resume <task-id>` as the only
  explicit continuation entry point.
- Resume accepts PAUSED Tasks, selects only paused/retryable unfinished items, creates a new auditable
  continuation Task, and never repeats an item with a persisted successful/DryRun/skipped result.
- Resume never increases execute authority: an original DryRun cannot become execute; an authorized
  organize continuation still requires a fresh `--execute`.
- Invalid transitions fail clearly and do not access Storage.

### 4. Boundary and observability

- Task list/show output displays paused state and pause-request status without exposing claim tokens,
  paths beyond existing authorized output, or secrets.
- Pause is distinct from cancellation, retry, rollback, Automation Job cancellation and claim loss.
- Existing Automation Job claim fencing/heartbeat and Organizer rollback behavior remain unchanged.

## Safety Boundaries

- No forced thread/process termination, signal injection, Storage cancellation mid-mutation,
  automatic retry, unattended execute, historical rollback, empty-directory cleanup or Phase 20.5.
- No Parser, Recognition, Metadata, Naming, Classification, Planner, Scanner traversal, Storage
  adapter or OrganizerExecutor semantic redesign.
- Pause/resume control itself performs zero Storage/network operations and zero media mutations.
- Do not add FFmpeg/FFprobe.

## Required Tests

- SQLite migration, persistence across reopen, atomic/idempotent pause request and invalid transitions.
- Pause before first item, between items, and request during an in-flight item; the item finishes and
  no next item starts.
- Paused item/lock handling, explicit resume selection, successful-result exclusion and attempt count.
- DryRun authority preservation, authorized execute requiring fresh `--execute`, cancellation
  distinction, concurrent pause/checkpoint behavior and bounded output.
- Pause command zero Storage/network mutation; C identity, Organizer rollback and existing Task/Job
  claim fencing regressions remain unchanged.

## Validation

Run Phase 20.4 Task/CLI/persistence tests, Automation claim/cancellation regressions, Organizer and
rollback, Scanner/FileIndex, all Storage, DryRun, Strategy/Metadata/Recognition/Parser/NFO and the
complete offline suite. Run formatter, lint, compile, dependency, both configuration validations,
FFmpeg/FFprobe audit, wheel build and diff checks.

Update `README.md`, `docs/architecture.md`, `docs/progress.md`, `docs/roadmap.md`, requirements status
and the product specification with exact pause/resume non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 20.4 Result

PASS / FAIL

## Pause Semantics

## Resume Semantics

## Safety

## Regression

## Final Recommendation
