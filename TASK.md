# Phase 18.1 — Read-only REST API + Persistent DryRun Worker

## Goal

Establish the first service boundary for MediaFlow: a versioned REST API for read-only runtime
state and a persistent background queue for scan/preview DryRun work. Reuse existing Application
Services and persistent repositories. Do not expose real organization execution remotely.

## 1. Persistent background jobs

Add a provider-neutral job model and repository port with:

- command: `scan` or `preview`
- status: `pending`, `running`, `completed`, `failed`, `cancelled`
- optional positive limit
- timestamps, related persistent task ID, and redacted error

Upgrade SQLite compatibly. Claiming must be atomic so two workers cannot process the same job.

## 2. Worker and CLI

Add a bounded worker which claims one job and invokes an injected workflow handler. Production CLI
wiring must reuse existing `scan` and `preview` workflows, never duplicate their business logic.

Add `mediaflow jobs list|show|submit|cancel` and `mediaflow worker run-next`. Only `scan` and
`preview` are accepted; preview is always DryRun and pending-only cancellation is supported.

## 3. REST API

Provide a versioned WSGI application and `mediaflow api serve --host 127.0.0.1 --port 8787`.
Required endpoints are health; task/job/confirmation listing and lookup; scan/preview job submit;
and pending job cancellation. JSON must be deterministic UTF-8 with stable errors.

## 4. API authorization

- Health may be public; all `/api/v1` endpoints require a bearer token.
- Configuration names the token environment variable; validation does not require its value.
- Server startup fails clearly when the secret is absent.
- Never log or return credentials or Authorization headers.

## 5. Execution boundary

- Reject `organize`, execute, overwrite, delete, and conflict-decision mutation requests.
- API requests never directly access Storage.
- Worker preview retains complete DryRun zero-mutation behavior.
- OrganizerExecutor is never invoked in execute mode by this phase.

## Required tests

- SQLite migration, persistence, atomic claim, ordering, cancellation, and failure records.
- Worker handler reuse and failure isolation.
- API health/auth/serialization/invalid JSON/unknown route behavior.
- Rejection of unsupported commands and execute attempts; secret redaction.
- Zero Storage mutations and all existing regressions.

## Documentation and validation

Update README, examples, architecture, progress, roadmap, and product status. Run all tests,
formatter, linter, compile check, dependency check, wheel build, configuration validation,
FFprobe/FFmpeg audit, and diff check.

## Out of scope

- Remote `organize --execute`, Scheduler/Cron, webhooks/notifications, Web UI/users/roles/TLS.
- Changes to strategy engines, Storage adapters, Planner, or OrganizerExecutor.

## Final report

## Phase 18.1 Result

PASS / FAIL

## API

## Worker

## Security and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
