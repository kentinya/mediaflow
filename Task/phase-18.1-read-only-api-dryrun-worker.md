# Phase 18.1 — Read-only REST API + Persistent DryRun Worker

## Goal

Establish the first service boundary for MediaFlow: a versioned REST API for read-only runtime
state and a persistent background queue for scan/preview DryRun work. Reuse existing Application
Services and persistent repositories. Do not expose real organization execution remotely.

## Scope

- Durable `scan`/`preview` AutomationJob persistence with atomic claiming.
- One-job Worker delegating the existing production workflows.
- Job list/show/submit/pending-cancel CLI.
- Authenticated WSGI Task/Job/Confirmation queries and scan/preview submissions.
- Environment-owned bearer token and stable redacted errors.
- Reject organize, execute, overwrite, delete, and conflict-decision mutation requests.
- Preserve complete DryRun zero-mutation behavior.

## Required validation

SQLite migration, persistence, atomic claim, ordering, cancellation, worker delegation, API auth,
serialization and error tests; complete regressions and quality checks; documentation updates.

## Out of scope

Remote execute, Scheduler/Cron, Webhook/notifications, Web UI/users/roles/TLS, and strategy or
Organizer redesign.

## Final report

Phase result, API, Worker, security/safety, regression, changed files, decisions, remaining work,
risks, and recommendation.
