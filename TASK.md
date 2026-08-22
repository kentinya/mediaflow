# Phase 18.2 — Resident Worker + Cooperative Cancellation + Interval Scheduler

## Goal

Complete the safe automation loop for scan and preview: add a controlled resident Worker,
cooperative cancellation at batch/scan boundaries, and persistent interval schedules. Reuse the
Phase 18.1 queue and existing Application Services. Do not expose real organization execution.

## 1. Cooperative job cancellation

- A pending job is cancelled immediately.
- A running job records `cancellationRequested` durably and the Worker observes it through a
  cancellation probe.
- Pass the probe into existing scan/batch orchestration so discovery stops before starting another
  file. Do not move cancellation logic into Parser, strategy engines, or Storage adapters.
- Cancellation is cooperative: an in-flight provider or Storage read may finish, but no new item is
  started afterward.
- A cancelled workflow ends as `cancelled`, not `failed`, and retains its related Task audit.

## 2. Resident Worker

- Add `mediaflow worker run` with configurable bounded polling and graceful SIGINT/SIGTERM stop.
- Keep `worker run-next` for deterministic operations and tests.
- Only one job is processed at a time per Worker; SQLite atomic claiming still prevents duplicate
  work across multiple processes.
- Add explicit stale-running-job inspection/requeue. Never silently requeue a possibly completed
  job. Requeue requires an age threshold and operator command.
- Worker errors remain isolated and redacted; one failed job does not terminate resident mode.

## 3. Persistent interval schedules

- Load schedules from RuntimeConfiguration.
- A schedule has unique ID, `scan` or `preview`, positive `intervalSeconds`, optional positive limit,
  enabled flag, and a persisted next-run timestamp.
- `mediaflow scheduler tick` evaluates due schedules once and queues jobs idempotently.
- `mediaflow scheduler run` performs bounded polling and graceful shutdown.
- Restart must not duplicate an already emitted occurrence.
- Scheduling always creates DryRun-safe commands; organize/execute is invalid configuration.

## 4. CLI and API

- Existing `jobs cancel` and `POST /api/v1/jobs/{id}/cancel` request cancellation for pending or
  running jobs.
- Add job cancellation state to API/CLI output.
- Add read-only `GET /api/v1/schedules`.
- Scheduling configuration validation and listing never construct Storage or require TMDB secrets.

## 5. Safety

- Only scan and preview may be queued or scheduled.
- Preview remains DryRun; zero Storage mutations under normal, cancelled, failed, and stale-requeue
  paths.
- No implicit overwrite/delete and no remote OrganizerExecutor execute mode.
- RecognitionType C and all accepted pipeline behavior remain unchanged.

## Required tests

- SQLite migration for cancellation and schedules.
- Pending cancellation, running cancellation request, cooperative stop between items, and cancelled
  terminal state.
- Resident Worker idle polling, multiple jobs, failure isolation, graceful stop, and no busy loop.
- Schedule validation, due/not-due/disabled evaluation, restart idempotency, and multiple schedules.
- Stale inspection and explicit safe requeue; non-stale/unknown/completed rejection.
- API cancellation and read-only schedule output.
- Zero mutation for Worker/Scheduler/API and complete existing regressions.

## Documentation and validation

Update README, example/catalog configuration, architecture, progress, roadmap, and product status.
Run all tests, formatter, linter, compile, dependency, wheel, configuration, FFprobe/FFmpeg, and
diff checks.

## Out of scope

- Cron expressions and calendar/time-zone schedules.
- Remote organize/execute, Webhooks/notifications, Web UI, user/role/TLS work.
- Forced interruption of an in-flight network request or process killing.
- Strategy, Storage, Planner, or OrganizerExecutor redesign.

## Final report

## Phase 18.2 Result

PASS / FAIL

## Cancellation

## Worker

## Scheduler

## Security and Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
