# Phase 19.20 — Read-only Stale Running Automation Job Visibility

## Goal

Expose bounded, configuration-driven visibility into automation jobs that have
remained `Running` beyond an operator-defined age. This phase is diagnostic
only: it must not requeue, cancel, retry, recover, or execute a job.

## Scope

### 1. Runtime configuration

Add `automation.staleJobAgeSeconds`:

- default: `3600`
- minimum: `60`
- maximum: `604800`
- reject booleans, non-integers, and out-of-range values
- expose only the numeric threshold in the redacted system configuration
  snapshot

Update canonical example configuration and configuration documentation.

### 2. Bounded stale-job query

Extend the automation job repository/application service with a bounded,
deterministically ordered read query for jobs where:

- status is `Running`
- `updated_at` is older than the configured threshold

Requirements:

- accept a limit from `1` to `100`
- enforce the bound in the persistence query, not only after loading rows
- perform no job, task, history, or storage mutation
- preserve existing local CLI compatibility

### 3. Read-only API

Add:

`GET /api/v1/jobs/stale?limit=100`

Requirements:

- require existing API read permission
- reject unsupported methods and unknown/duplicate query parameters
- use `automation.staleJobAgeSeconds`; callers cannot supply an arbitrary age
- return the threshold and a strict allowlist of safe job fields
- do not expose request input, paths, errors, secrets, credentials, tokens, or
  authorization headers
- normalize the route in security audit records
- distinguish this route from the existing `/api/v1/jobs/{id}` route

### 4. Operator UI

Extend the existing Jobs view with an explicit `Show stale running jobs`
action.

Requirements:

- fetch only when the operator requests it; do not poll
- display a compact bounded table
- clearly mark execute-authorized organize jobs as
  `MUTATION_AUTHORIZED — MANUAL RECOVERY ONLY`
- explain that age is only an observation and is not proof the worker died
- provide no requeue, retry, force-cancel, delete, or execute controls
- display the configured stale threshold in System information

### 5. Safety

This phase must not call:

- Scanner or the media processing pipeline
- Metadata providers or network media services
- Naming, Classification, Planner, or OrganizerExecutor
- Storage read or mutation methods
- job requeue/cancel/retry methods

Existing security-audit persistence for authenticated API requests is allowed.

## Tests

Add focused automated tests covering:

- configuration default, accepted value, type/range rejection, and snapshot
- repository SQL limit and deterministic stale ordering
- non-stale and non-running jobs are excluded
- API authentication/authorization, method handling, strict query parsing,
  limit bounds, and audit-route normalization
- response allowlisting and secret/error/path redaction
- execute-authorized organize-job warning visibility
- UI explicit loading, threshold visibility, explanatory warning, and absence
  of recovery action controls
- zero Storage and workflow-service calls
- existing automation, API, task, CLI, and safety regressions

Run all tests plus configured formatter, linter, and type checker.

## Documentation

Update:

- `README.md`
- `docs/configuration.md`
- `docs/architecture.md`
- `docs/progress.md`
- `docs/roadmap.md`
- canonical example configuration files

## Out of Scope

- API/UI requeue, retry, cancellation, deletion, or forced recovery
- automatic stale-job recovery
- worker heartbeats, leases, fencing tokens, or distributed liveness
- changing active-job admission semantics
- media pipeline or Storage behavior changes
- UI redesign

## Completion Report

Finish with:

## Phase 19.20 Result

PASS / FAIL

## Stale Detection

## API and UI

## Authorization and Redaction

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
