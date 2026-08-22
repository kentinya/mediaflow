# Phase 18.3 — Cron/Timezone Scheduler + Persistent Schedule Audit

## Goal

Extend Scheduler with a bounded five-field numeric Cron subset, IANA time zones, deterministic DST
semantics, concurrent/restart-safe emission, and immutable SQLite schedule audit. Preserve interval
schedules and the scan/preview-only boundary.

## Scope

- Wildcard/list/range/step Cron fields with strict bounds and no shell/macros/seconds.
- UTC persistence plus IANA local-time evaluation; nonexistent DST times skip and ambiguous times
  emit once.
- Exactly one interval or Cron timing mode; missed occurrences coalesce without backlog.
- Append-only occurrence/job/next-run audit and CLI/authenticated read-only API access.
- Zero Storage/provider calls and no remote organize/execute.

## Validation

Parser matrix, calendar/leap/DST, current/future/missed/concurrent ticks, v5-to-v6 migration,
audit filter/limit/API/CLI, zero mutation, all regressions, quality checks, examples, and docs.
