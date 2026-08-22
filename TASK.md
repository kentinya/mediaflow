# Phase 18.3 — Cron/Timezone Scheduler + Persistent Schedule Audit

## Goal

Extend the accepted Scheduler with deterministic five-field Cron schedules, IANA time zones, and
persistent immutable emission audit. Preserve interval schedules and the scan/preview-only queue.
Do not expose real organization execution or add notification delivery.

## 1. Cron expression model

- Support exactly five fields: minute, hour, day-of-month, month, day-of-week.
- Support `*`, comma lists, inclusive ranges, and positive `/step` syntax.
- Validate bounds and reject names, macros, seconds fields, empty fields, reversed ranges, zero
  steps, and pathological expressions.
- Define day-of-month/day-of-week combination semantics explicitly and test them.
- Parsing/evaluation must be deterministic, bounded, and use no shell or external cron process.

## 2. Time zones and calendar behavior

- Configure an IANA time-zone ID per Cron schedule and validate it with standard-library zoneinfo.
- Persist schedule instants in UTC; render both UTC and configured local schedule information.
- Skip nonexistent local wall times during DST transitions.
- Emit an ambiguous repeated local wall time once, with documented deterministic fold behavior.
- Next-run calculation must be bounded and correctly cross month/year/leap-day boundaries.

## 3. Scheduler integration and persistence

- Runtime configuration accepts either `intervalSeconds` or `cron` plus `timezone`, never both.
- Preserve existing interval behavior and persisted state compatibility.
- First Cron evaluation queues the current matching minute once or persists the next future match.
- Atomic tick/restart behavior must prevent duplicate jobs across multiple Scheduler processes.
- Missed Cron occurrences are coalesced into one current job; do not create unbounded backlog.
- Upgrade SQLite compatibly and retain existing jobs/schedule states.

## 4. Immutable schedule audit

- Persist every emitted occurrence with audit ID, schedule ID, occurrence UTC, emitted timestamp,
  job ID, command, and next-run UTC.
- Audit records are append-only and contain no secrets or Storage access details.
- Add `mediaflow scheduler audit [SCHEDULE_ID] [--limit N]`.
- Add authenticated read-only `GET /api/v1/schedules/{id}/audit`.
- Unknown schedule IDs fail clearly; listing/audit never constructs Storage.

## 5. Safety and compatibility

- Cron schedules may queue only scan and preview; organize/execute remains invalid.
- Scheduler and audit perform zero Storage mutations and no provider/network calls.
- Preview remains DryRun under interval and Cron scheduling.
- No implicit overwrite/delete and no remote OrganizerExecutor execute mode.
- Existing Worker cancellation/stale recovery and RecognitionType C behavior remain unchanged.

## Required tests

- Cron parser valid/invalid matrix, bounds, lists, ranges, and steps.
- UTC and non-UTC time zones, day-field semantics, month/year/leap-day transitions.
- DST nonexistent and ambiguous wall-time behavior.
- Current-minute, future, missed occurrence coalescing, disabled, restart, and concurrent tick cases.
- Interval compatibility and SQLite v5-to-v6 migration.
- Immutable audit ordering/filter/limit, CLI/API serialization, unknown IDs, and zero mutation.
- All Phase 18.1/18.2 and complete existing regressions.

## Documentation and validation

Update README, example/catalog configuration, architecture, progress, roadmap, and product status.
Run all tests and all configured quality/build/security checks.

## Out of scope

- Remote organize/execute, Webhooks/notifications, Web UI, user/role/TLS work.
- Cron names/macros/seconds, holiday calendars, catch-up backlogs, and notification delivery.
- Strategy, Storage, Planner, or OrganizerExecutor redesign.

## Final report

## Phase 18.3 Result

PASS / FAIL

## Cron and Time Zones

## Schedule Audit

## Scheduler

## Security and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
