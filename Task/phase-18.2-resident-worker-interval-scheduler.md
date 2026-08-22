# Phase 18.2 — Resident Worker + Cooperative Cancellation + Interval Scheduler

## Goal

Complete the safe scan/preview automation loop with a controlled resident Worker, cooperative
cancellation, explicit stale recovery, and persistent interval schedules.

## Scope

- Pending cancellation is immediate; running cancellation is durable and cooperative between items.
- `worker run` uses bounded polling, atomic claim, failure isolation, and graceful signal shutdown.
- Stale running jobs require explicit age-guarded operator requeue.
- Configuration-driven, restart-idempotent interval schedules queue only scan/preview jobs.
- CLI/API expose cancellation and read-only schedule state.
- Preview and every scheduled path remain zero-mutation DryRun.

## Out of scope

Cron/time-zone schedules, remote execute, Webhooks/notifications, Web UI, forced request/process
termination, and strategy/Storage/Planner/Executor redesign.

## Validation

SQLite migration, cancellation, Worker loop, Scheduler idempotency, stale recovery, API, zero
mutation, full regressions, quality checks, examples, and documentation.
