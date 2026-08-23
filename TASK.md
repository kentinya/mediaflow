# Phase 20.5 — Unified Bounded Read-Only Workflow Retry

## Goal

Add one configuration-driven retry policy and reusable application controller for explicitly
transient pre-execution failures, while forbidding automatic replay of Organizer mutations or
uncertain execution outcomes.

## Scope

### 1. Policy, decision and evidence

- Add immutable WorkflowRetryPolicy, RetryCategory, RetryEvent and RetryOutcome models.
- Configure optional runtime `workflowRetry` with enabled, maximum attempts, bounded exponential
  backoff, maximum delay and jitter ratio. Default is disabled for backward compatibility.
- Validate unknown fields, booleans-as-numbers, invalid ranges and unbounded values at startup.
- Record only stable category, stage, attempt and delay; never raw provider response, URL, path,
  credential or exception text.

### 2. Central retry controller

- Implement one reusable controller with injected clock/sleeper/random source for deterministic tests.
- Retry only errors classified as transient: timeout, connection failure/loss, rate limit, and
  temporary provider unavailable.
- Never retry authentication, permission, invalid path/configuration/request, malformed response,
  not-found, unsupported operation, ambiguity, NeedConfirm, conflict or unknown errors.
- Respect cancellation and Task pause before every attempt and during bounded waiting.

### 3. Production workflow integration

- Apply the controller only to the read-only strategy/metadata/NFO portion before planning and before
  OrganizerExecutor is entered.
- Do not add a second retry layer around successful adapter/provider internal attempts; workflow retry
  begins only after those bounded attempts are exhausted and surfaced as normalized errors.
- Persist retry count in Task result evidence and emit structured redacted operational events.
- RecognitionType C and all downstream policy mappings remain unchanged across retries.

### 4. Fail-closed execution boundary

- Never automatically retry OrganizerExecutor MOVE/COPY/HARDLINK/SYMLINK, PARTIAL/FAILED execution,
  rollback failure, conflict resolution, overwrite, source delete, or an outcome that may have
  mutated Storage.
- DryRun remains zero mutation. Enabling workflow retry does not grant execute authority and does not
  schedule background work.

## Boundaries

- Do not replace existing provider/adapter-local retry internals in this Phase.
- No automatic Task requeue, Scheduler execute, dead-letter redesign, historical rollback,
  empty-directory cleanup, distributed retry claim or Phase 20.6.
- Do not change Parser, Recognition, Naming, Classification, Planner, Storage adapter or
  OrganizerExecutor domain semantics.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Policy validation/default compatibility, deterministic exponential backoff/jitter and maximum bound.
- Transient Metadata timeout/connection/rate-limit/provider-unavailable retries then succeeds.
- Transient read-only Storage failure retries; permanent/unknown/configuration/malformed/not-found and
  ambiguous/NeedConfirm results do not retry.
- Cancellation/pause stops before next attempt and during wait.
- Exhaustion persists bounded attempts/category without raw secret-bearing messages.
- Execute-mode failure/partial/rollback/conflict never auto retries; OrganizerExecutor call count is one.
- DryRun zero mutation, Task result retry evidence, operational log evidence and C identity regression.

## Validation

Run Phase 20.5 retry tests, Task pause/resume and persistence, Metadata/TMDB, Storage adapter retry,
Organizer/rollback, Scanner/FileIndex, DryRun, Strategy/Recognition/Parser/NFO and the full offline
suite. Run formatter, lint, compile, dependency, both configuration validations, FFmpeg/FFprobe
audit, wheel build and diff checks.

Update `README.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/progress.md`,
`docs/roadmap.md`, requirements status and the product specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 20.5 Result

PASS / FAIL

## Retry Matrix

## Backoff and Evidence

## Safety

## Regression

## Final Recommendation
