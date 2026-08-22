# Phase 19.8 — Persistent Redacted Operational Log Foundation

## Goal

Introduce a durable, bounded, structured operational logging boundary for the production workflow.
Persist only controlled event metadata, enforce retention, and provide local read-only retrieval
without leaking paths, raw errors, arbitrary context, credentials, or media/provider data.

## 1. Domain and persistence

- Add immutable `OperationalLogRecord` and repository contracts separate from result/security audit.
- Fields: stable ID, UTC timestamp, level, component, event code, optional task/job/plan ID and status.
- Add SQLite v13 storage with newest-first deterministic bounded reads and useful indexes.
- Never persist free-form context, source/destination paths, titles, provider IDs, HTTP data, exception
  text, tokens, passwords, authorization values, cookies, signatures, or secret-derived identifiers.

## 2. Safe Logger adapter

- Implement the existing domain `Logger` protocol as an infrastructure adapter.
- Map bounded fixed application messages to validated event codes; reject/drop unknown unsafe fields.
- Whitelist only task/job/plan/status identifiers with strict length/character validation.
- Respect configured minimum level. Logging failure must not widen execution authority or mutate media.
- Wire the same logger into production Scanner, MediaOrganizerService, and OrganizerExecutor only;
  do not move logging policy into those engines.

## 3. Configuration and retention

- Add optional `operationalLogging` runtime configuration with `enabled`, `minimumLevel`,
  `retentionDays`, and `maximumRecords`, using safe disabled defaults.
- Validate booleans/types/ranges and reject unknown/literal-secret fields.
- Enforce both age and record-count retention through an explicit local maintenance operation.
- Retention deletes only operational log rows, never media, Tasks, Results, history, or security audit.

## 4. Local retrieval

- Add `mediaflow logs list --limit N [--level LEVEL]` as a local read-only bounded command.
- Add `mediaflow logs prune` as an explicit database-maintenance command with removed-row count.
- Output only persisted safe fields. Do not construct Storage, Provider, Scanner, workflow, or Executor.
- Do not add Web/API/UI log visibility in this phase.

## Required tests

- SQLite v12→v13 migration, append, deterministic order, level filter, bounded SQL read, and reopen.
- Logger minimum-level behavior, fixed-event normalization, identifier whitelist, unknown context drop.
- Secret/path/raw-error/title/provider/HTTP payload values cannot reach persisted rows or CLI output.
- Valid/invalid logging configuration, disabled default, record-count and age retention, prune isolation.
- Production workflow wiring emits safe scan/workflow/execution events without changing outcomes.
- Logging persistence failure does not trigger Storage mutation, retry, authority widening, or deletion.
- CLI list/prune bounds and validation; read-only list constructs no Storage/provider/workflow.
- Existing Storage, Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner, Executor,
  Task/History, API/UI, Scheduler/Notification, DryRun, and full regressions.
- Formatter, lint, compile, dependency/build/configuration, FFprobe/FFmpeg, and diff checks.

## Documentation

Update README, requirements status, example configuration, configuration guide, architecture,
progress, and roadmap with event schema, redaction, retention, commands, and limitations.

## Out of scope

Web/API log UI, full-text search, arbitrary context JSON, media-path debugging, remote log shipping,
OpenTelemetry, live tail/SSE/WebSocket, audit replacement, OIDC, Secret Store, and TLS termination.

## Final report

## Phase 19.8 Result

PASS / FAIL

## Operational Log Model

## Redaction and Retention

## CLI

## Workflow Wiring

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
