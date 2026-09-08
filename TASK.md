# Task 29.4 — Restart-Safe Durable Operation and Fault Fencing

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 29.4
Parent Slice: 29
Parent Slice Name: Docker Production Self-hosted Release
Parent Required Outcomes: RO-5 — Restart-safe durable operation
Status: PLANNED
Task Base: 53f7584a55d3f4224d4032aedf0fc8f951cf3d5a
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the restart and fault-recovery journey for the Compose product: an operator can restart or
stop an individual API, Worker, Scheduler or Notification Worker service and retain durable state,
while controlled fault tests prove duplicate scheduled occurrences are suppressed, stale Worker
owners cannot commit over a newer owner, and uncertain media mutations are never replayed
automatically. Existing per-item failure and recovery semantics remain inspectable after restart.
This advances Slice 29 Required Outcome RO-5.

## Why This Task Exists

Tasks 29.2 and 29.3 established the image/process topology, local `/data` boundary and distinct
health/readiness signals, but their smoke journeys only restart the API and do not exercise the
durable Scheduler, Worker ownership or mutation-uncertainty guarantees. Those guarantees already
exist in application foundations and must now be proven across real service stop/start boundaries.
The largest reasonable next unit is one fault matrix spanning persistence, Scheduler, Worker,
notification state and the existing per-item checkpoint/recovery path; backup/upgrade work belongs
to the following Task.

## Operator Journey Contract

- Entry: run the documented Compose stack with a fresh local `/data` volume, then inspect and
  restart one service at a time.
- Visible state: configuration and Active identity, FileIndex, Job/Task/TaskItem/Result, schedule
  and occurrence history, notification delivery state, audit/log records, Worker owner/heartbeat,
  effect certainty and each item's next recovery action.
- Action: stop/restart the affected service or inject a bounded process/claim/mutation fault; inspect
  the durable evidence and choose the explicit recovery action offered by the existing application.
- Success: state survives restart; one occurrence is emitted once; only the live current Worker may
  commit; an uncertain mutation remains investigation/recovery state and is not silently replayed.
- Failure/recovery: the affected item or service reports a bounded durable failure and safe next
  action. Restart, retry or continuation never hides successful siblings, overwrites a newer owner,
  or assumes an unknown mutation was undone.

## Implementation Scope

```text
SQLite durable state and existing lease/claim/checkpoint boundaries
→ Scheduler/Worker/Notification service restart wiring
→ Compose fault-injection and persistence harness
→ API/Web task/result/recovery evidence
→ duplicate, fencing and uncertain-mutation regression tests
```

Expected ownership/surfaces:

- Add an isolated Compose restart/fault harness using temporary `/data` and media mounts. Record
  representative managed configuration, FileIndex, Jobs, Tasks/TaskItems/Results, schedules and
  occurrences, notification rows, audit and operational logs; restart each relevant service and
  verify the records and identities remain durable.
- Exercise Scheduler restart around the same due occurrence and assert idempotent occurrence/Job
  emission—never two occurrences for one schedule/time slot. Keep scheduler behavior bounded and
  do not redesign schedule definitions or cron/interval semantics.
- Exercise Worker claim/heartbeat/commit fencing with a controlled newer claim or process restart.
  A stale owner must be rejected for heartbeat and result commit, while the newer owner remains the
  only authority. Preserve existing queue admission and per-item state semantics.
- Exercise an OrganizerExecutor boundary fault that leaves mutation effect certainty unknown. After
  service restart, verify no automatic replay occurs; the durable checkpoint/result exposes known
  effects, certainty and an explicit investigation or safe recovery action. Do not add rollback or
  automatic replay semantics.
- Prove notification delivery state is durable and at-least-once across restart without silently
  deleting or hiding a failed/dead-letter delivery. API/Web task and recovery views must retain
  independent per-item outcomes.
- Update only deployment/release documentation and test tooling needed to run this fault matrix.
  No production credentials, remote Storage/Provider service or host data may be used.

Frozen unless B authorizes a scope correction:

- `SLICE.md`, `docs/roadmap.md`, canonical requirements, Task 29.2 packaging/WSGI/mount contract
  and Task 29.3 health/readiness semantics.
- Backup/restore, image-to-image upgrade, migration rehearsal/failure recovery and release-secret
  scans (RO-6/RO-7).
- Scheduler definition model, Worker ownership model, OrganizerExecutor authority, mutation
  operation semantics, TaskItem state model, Jobs/Preview/Organize execution boundary and all
  closed Slice 26–28 behavior.

## Acceptance Criteria

- [ ] An isolated fresh-volume Compose run writes representative configuration, FileIndex,
      Job/Task/TaskItem/Result, schedule/occurrence, notification, audit and operational-log state;
      restarting API, Worker, Scheduler and Notification Worker preserves the records, identities,
      Active snapshot and per-item dispositions.
- [ ] Scheduler stop/start or duplicate-emission fault injection produces at most one durable
      occurrence and linked Job for a given schedule/occurrence identity; no duplicate work or
      mutation is created by restart.
- [ ] A controlled Worker claim race/restart proves a stale owner cannot heartbeat, complete or
      overwrite a newer Worker claim/result. The current owner and rejection reason remain durable
      and actionable.
- [ ] A controlled OrganizerExecutor fault with unknown effect certainty remains durable as an
      uncertain/investigation state after restart; startup and retry do not automatically replay the
      media mutation, and the existing explicit recovery path remains available.
- [ ] Notification delivery/outbox state and dead-letter/retry evidence survive restart with
      at-least-once semantics; no delivery is silently erased or falsely marked successful.
- [ ] API/Web task, result and recovery projections preserve independent per-item success, failure,
      skipped and uncertain outcomes after service restart; no viewing/restart path creates media
      work, calls a Provider or mutates Storage.
- [ ] The checkpoint contains only this restart/fault journey and its tests, uses temporary isolated
      paths and secret-free output, and passes all required T4 gates.

## Required Tests

### Focused and integration tests

- Scheduler idempotence tests around restart/duplicate emission and linked Job identity.
- Worker lease/claim fencing tests for stale heartbeat, stale completion and newer-owner result
  preservation, including process-stop/restart timing boundaries.
- OrganizerExecutor uncertain-effect checkpoint tests proving no automatic replay and explicit safe
  recovery evidence.
- Notification outbox/delivery restart tests covering pending, delivered, failed and dead-letter
  records.
- Isolated Docker restart/fault acceptance using temporary paths, representative durable records,
  service stop/start and API/Web evidence. Record `SKIP`/`UNAVAILABLE` only for unavailable Docker
  or external services; do not infer production guarantees from unit tests alone.
- Existing Task 29.2/29.3 deployment, health/readiness, authentication, Scheduler, Worker,
  notification, Task/recovery and OrganizerExecutor regression suites.

### Required commands

```bash
python3 scripts/check_governance.py
.venv/bin/python -m unittest <focused restart/scheduler/worker/notification/recovery tests>
.venv/bin/python scripts/docker_restart_fault_smoke_test.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m pip wheel . --no-deps -w /tmp/mediaflow-wheel-check
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-wheel-check/mediaflow-*.whl
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml Dockerfile compose.yaml scripts || true)"
git diff --check
```

The full regression may retain only the known pre-existing Storage Browser failure and environment
unavailable external-service skips when reproduced at this Task Base with exact evidence.

## Non-goals

- Backup/restore, image upgrade, schema migration rehearsal or migration-failure recovery (RO-6).
- Release-wide secret/private-state scans, TLS/reverse-proxy deployment or registry publication
  beyond regression-fencing the existing boundaries (RO-7).
- New rollback, automatic uncertain-mutation replay, historical rollback, distributed transactions,
  HA/distributed workers or power-loss guarantees.
- New Scheduler/Automation definitions, execution authority, TaskItem states, OrganizerExecutor or
  Storage operations; no silent fallback, overwrite or source deletion.
- Optional dashboard/copy cleanup, unrelated refactors or production deployment data.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update
Roadmap.
