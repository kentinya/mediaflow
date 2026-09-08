# Task 29.3 — Container Health, Readiness and Fail-Closed Diagnostics

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 29.3
Parent Slice: 29
Parent Slice Name: Docker Production Self-hosted Release
Parent Required Outcomes: RO-4 — Distinct operational health and recovery visibility
Status: PLANNED
Task Base: 3681d1dc9214bf31a0363c2b1913f6ebaec19e19
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the deployment health journey: an operator can distinguish process liveness, management/API
readiness and business/processing-Worker readiness for the Compose installation, and receives a
bounded, secret-free, actionable failure when configuration authority, Active runtime, required
mounts, permissions, deployment secrets or a processing Worker is unavailable. Health and readiness
probes remain side-effect free and never create work, contact Providers, send notifications or
mutate Storage. This advances Slice 29 Required Outcome RO-4.

## Why This Task Exists

Task 29.2 delivered the image, four process boundaries, production WSGI serving and basic startup
path checks, but Compose has no verified health model. The public `/health` liveness response,
authenticated management readiness and Worker readiness already exist in the application, yet the
deployment does not expose or validate them as a coherent operator journey. A missing Active
snapshot, an unavailable Worker or a failed mount can therefore be confused with a healthy process.
The largest reasonable next unit is to wire these three signals through the container/API/Web
surfaces and prove their failure and recovery semantics together; restart-fault and upgrade work
remain separate Tasks.

## Operator Journey Contract

- Entry: start the Compose stack and inspect service health, the public liveness endpoint, and the
  authenticated management and Worker readiness projections.
- Visible state: process liveness, management/setup/recovery state, exact Active identity when
  present, Worker availability/snapshot condition, bounded next action and durable-state note.
- Action: correct the named configuration, mount, permission, secret or Worker process and rerun
  the bounded probe/start action.
- Success: the three signals remain distinct; a process can be alive while management or business
  readiness is false, and a ready result reflects the exact immutable runtime consumed by the
  process.
- Failure/recovery: probes fail closed with stable, secret-free diagnostics and never create a Job,
  Task, notification or media mutation. Correcting the reported dependency and restarting/reloading
  the affected service is the explicit recovery path.

## Implementation Scope

```text
Container probe/health boundary
→ Compose healthcheck and service-state wiring
→ existing API liveness/management/Worker readiness projections
→ Web/operator visibility and bounded diagnostic text
→ side-effect and failure/recovery tests
```

Expected ownership/surfaces:

- Add a bounded probe interface usable by Compose that can report process liveness separately from
  authenticated management and business/Worker readiness. Probe timeouts and output must be
  bounded; secret values, authorization headers, cookies and provider credentials must never be
  printed or embedded in Compose-rendered evidence.
- Wire only the required healthchecks/diagnostics into `compose.yaml` and the container startup
  boundary. Each service remains one process with independent failure/restart behavior; no
  supervisor or implicit second service is introduced.
- Preserve and, where necessary, complete the shared API/Web projections for `/health`,
  `/api/v1/management/readiness` and `/api/v1/workers/readiness`. They must expose actionable
  missing Active/configuration, mount/permission/secret and Worker conditions without probing
  Storage, calling Metadata Providers, creating work or mutating media.
- Add an isolated Compose harness and unit/integration coverage for healthy, setup-required,
  Active-unavailable, missing-secret, missing/inaccessible-mount, no-Worker, stale-Worker and
  snapshot-mismatch states. Use temporary paths and fakes; no production data or external service.
- Update only deployment/operator documentation needed to explain the three signals, failure
  meanings, bounded recovery actions and the TLS/reverse-proxy boundary already defined by Slice
  29.

Frozen unless B authorizes a scope correction:

- `SLICE.md`, `docs/roadmap.md`, canonical requirements, and the Task 29.2 image/WSGI/mount
  contract.
- Scheduler duplicate suppression, Worker ownership fencing, uncertain-mutation recovery,
  backup/restore, upgrade/preflight/migration rehearsal and release-candidate scans.
- Jobs/Preview/Organize authority and OrganizerExecutor mutation behavior, Automation definitions,
  Files/FileIndex Manual Preview and all closed Slice 26–28 behavior.

## Acceptance Criteria

- [ ] Compose and the documented deployment expose three distinct, bounded signals: public process
      liveness, authenticated management/API readiness, and authenticated business/Worker
      readiness. A liveness success never implies runtime or Worker readiness.
- [ ] Management readiness reports setup/recovery/Active/configuration state with an exact immutable
      snapshot identity when ready; missing, corrupt, unsupported or invalid Active state is
      actionable and fails closed without falling back to Draft/JSON/stale runtime.
- [ ] Worker readiness reports no Worker, stale Worker and snapshot/schema mismatch distinctly,
      with durable state, retry safety and a bounded next action; a live Worker bound to the exact
      Active snapshot is the only ready result.
- [ ] Container healthchecks/probes have bounded request/command timeouts, do not leak deployment
      secrets or private paths, and perform no Storage scan, Provider request, Job/Task creation,
      notification delivery or Storage mutation.
- [ ] Missing/inaccessible `/data` or media mount, missing referenced secret, and unavailable API or
      Worker process produce non-zero or non-ready state with an actionable diagnostic and an
      explicit correction/retry path; no root, host-root, Docker-socket or arbitrary-path fallback
      is possible.
- [ ] The authenticated API and Operator Web show the same readiness semantics and permissions as
      the non-container application; viewing or probing readiness is side-effect free.
- [ ] Isolated Docker acceptance demonstrates healthy, degraded and recovery transitions using
      temporary data/media paths, and the checkpoint contains no unrelated restart/upgrade work,
      credentials or generated deployment state.

## Required Tests

### Focused and integration tests

- Probe/unit tests for liveness, management readiness and Worker readiness, including setup,
  missing/invalid Active, secret/mount/permission failure, no Worker, stale Worker and snapshot
  mismatch; assert bounded, secret-free diagnostics and zero side effects.
- Compose schema tests for healthcheck commands, timeout/start-period/retry bounds, independent
  service commands and absence of supervisor, host-root or Docker-socket mappings.
- Isolated Docker health acceptance using temporary `/data` and media directories: start a healthy
  stack, observe each signal, induce a missing/invalid dependency, verify non-ready/actionable
  output, repair it and verify recovery. Record `SKIP`/`UNAVAILABLE` only when Docker is absent.
- Existing authentication, management setup, configuration status, Worker readiness, API/Web and
  Task 29.2 container deployment tests.

### Required commands

```bash
python3 scripts/check_governance.py
.venv/bin/python -m unittest <focused health/readiness/container tests>
.venv/bin/python scripts/docker_health_smoke_test.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m pip wheel . --no-deps -w /tmp/mediaflow-wheel-check
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-wheel-check/mediaflow-*.whl
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml Dockerfile compose.yaml scripts docs || true)"
git diff --check
```

The full regression may retain only the known pre-existing Storage Browser failure and environment
unavailable external-service skips when reproduced at this Task Base with exact evidence.

## Non-goals

- Scheduler duplicate-occurrence tests, stale-owner fencing, uncertain-mutation recovery or any
  automatic replay behavior (RO-5).
- Backup/restore, image-to-image upgrade, migration rehearsal or migration-failure recovery (RO-6).
- New identity/session systems, TLS termination, reverse-proxy identity, Docker Secrets ingestion,
  remote databases, distributed workers or registry publication.
- Redesign of Jobs/Preview/Organize execution authority, TaskItem state, OrganizerExecutor or
  Storage capability semantics.
- Optional health-dashboard polish, copy cleanup, unrelated refactors or production deployment
  data.

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
