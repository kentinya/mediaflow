# Task 29.5 — Image Upgrade, Backup and Migration Recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 29.5
Parent Slice: 29
Parent Slice Name: Docker Production Self-hosted Release
Parent Required Outcomes: RO-6 — Backup, upgrade and migration recovery
Status: PLANNED
Task Base: 776d2d102b31df787073aaa6bcd9ba20fbcfca9d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the image-to-image upgrade and recovery journey for the Compose product: an operator can
create and verify a local `/data` backup, run read-only compatibility/preflight and an isolated
migration rehearsal with a new image, upgrade only after the gate passes, and recover from an
injected migration failure while retaining the prior live authority, verified backup and previous
artifact. This advances Slice 29 Required Outcome RO-6.

## Why This Task Exists

Tasks 29.2–29.4 established the image/process topology, production serving, local `/data` boundary,
health/readiness signals and restart-safe durable operation. The repository already has online SQLite
backup, integrity verification, non-overwriting restore, upgrade preflight and isolated migration
rehearsal primitives, but no vertical Compose journey proves them across an older and newer image or
proves fail-closed recovery when migration cannot complete. The largest reasonable next unit is one
upgrade lifecycle harness plus the operator runbook and regression tests; release-wide secret/network
validation remains the following RO-7 Task.

## Operator Journey Contract

- Entry: keep the current Compose deployment and a retained prior image, create a backup under the
  local `/data`/backup boundary, and prepare a candidate image.
- Visible state: backup path, schema/version, integrity digest and age; old/new image identity;
  preflight and rehearsal result; migration status; retained live database, backup and prior image;
  service/management/runtime readiness and the next recovery action.
- Action: stop the stack at the documented boundary, create/verify the backup, run read-only
  preflight and rehearsal against a disposable copy, then start the candidate image only when the
  compatibility gate passes; inject or observe a bounded migration failure and choose restore or
  rollback recovery explicitly.
- Success: the upgraded stack starts with representative durable state and exact Active identity
  preserved; the backup and prior artifact remain available; no migration or preflight mutates live
  media or grants execution authority.
- Failure/recovery: a stale/invalid backup, incompatible schema, rehearsal failure or migration
  failure blocks upgrade before media work, leaves live state and the verified backup/prior artifact
  intact, and exposes whether restore/retry is safe plus the explicit next action. Recovery never
  overwrites an occupied destination or silently discards the old authority.

## Implementation Scope

```text
Backup/verify and upgrade-preflight application boundary
→ disposable old-image/new-image Compose migration rehearsal
→ fail-closed migration failure and restore/recovery harness
→ API/Web and CLI operational evidence/documentation
→ focused, integration and full regression tests
```

Expected ownership/surfaces:

- Add an isolated upgrade acceptance harness using temporary directories, a throwaway `/data`
  volume and explicit media mounts. Build or obtain two local image identities representing the
  supported old and candidate revisions without contacting a registry or using production data.
- Seed representative managed configuration, Active snapshot identity, FileIndex, Jobs,
  Tasks/TaskItems/Results, automation/occurrence, notification, audit and operational-log records
  in the old deployment. Create a verified local SQLite backup and retain its digest, schema and
  artifact identity.
- Run the installed old/new image `upgrade check`/preflight and migration rehearsal only against a
  disposable copy. Assert current-schema and older-supported-schema paths, preserved representative
  counts/identities, bounded output and zero Storage/Provider/notification/mutation side effects.
- Exercise a controlled migration failure (for example an isolated migration hook or invalid
  disposable copy) and prove the live `/data` database, verified backup, prior image and last-known
  Active authority remain unchanged and available. Recovery must use the existing non-overwriting
  restore procedure or an explicit retry after repair; do not add automatic rollback or replay.
- Exercise a successful old-image → candidate-image upgrade on the disposable/isolated deployment,
  restart the Compose services, and verify authenticated API/Web readiness plus representative
  durable records and per-item dispositions remain intact.
- Update only deployment/release documentation and test tooling needed for backup, preflight,
  rehearsal, upgrade and migration-failure recovery. No production credentials, remote
  Storage/Provider service, registry publication or host data may be used.

Frozen unless B authorizes a scope correction:

- `SLICE.md`, `docs/roadmap.md`, canonical requirements, and Task 29.2–29.4 image/WSGI/mount,
  health/readiness and restart/fencing contracts.
- Jobs/Preview/Organize execution authority, OrganizerExecutor mutation boundary, Storage
  operations, Scheduler/Worker/Notification semantics and all closed Slice 26–28 behavior.
- Release-wide image/build-context/private-state/secret/network scans and non-root/API-token/TLS
  validation (RO-7); only regression-fence existing boundaries as needed for the upgrade journey.
- New migration schema features, automatic rollback, uncertain-mutation replay, historical rollback,
  remote databases, distributed workers and any new identity or Secret Store integration.

## Acceptance Criteria

- [ ] An isolated fresh old-image Compose deployment on temporary paths writes representative managed
      configuration, Active identity, FileIndex, Job/Task/TaskItem/Result, schedule/occurrence,
      notification, audit and operational-log state; a local `/data` backup is created, integrity-
      verified and recorded with schema, digest, age and retained artifact identity.
- [ ] Read-only upgrade preflight rejects missing, stale, corrupt, newer-incompatible or
      mismatched-schema backups with bounded, actionable diagnostics and never changes the live
      database, configuration authority, media, notifications or execution authority.
- [ ] Migration rehearsal runs the candidate image's real repository migration path only on a
      disposable copy, covers current and at least one older supported schema, preserves
      representative record counts/identities and leaves the source backup byte-for-byte unchanged.
- [ ] A controlled migration failure is fail-closed: no candidate service resumes media work, the
      live `/data` database and exact Active identity remain unchanged, and the verified backup and
      previous image/artifact remain available for the documented non-overwriting restore/retry path.
- [ ] A successful isolated old-image → candidate-image upgrade starts the four-service Compose
      topology, passes authenticated management and Worker readiness, and preserves representative
      configuration, FileIndex, automation/occurrence, Task/TaskItem/Result, notification, audit
      and operational-log identities across restart.
- [ ] Restore/recovery refuses occupied destinations and sidecars, requires explicit confirmation,
      never overwrites live state implicitly, and records a bounded next action for both success and
      failure cases.
- [ ] API/Web and CLI upgrade/recovery evidence is secret-free, bounded and clearly distinguishes
      process/service state, management/runtime readiness, migration state, durable state and the
      retained backup/prior artifact; viewing status performs no Storage scan, Provider call, work
      creation, notification delivery or media mutation.
- [ ] The checkpoint contains only RO-6 backup/upgrade/migration behavior and tests, uses temporary
      isolated paths, introduces no production credentials/private state, and passes all required T4
      gates.

## Required Tests

### Focused and integration tests

- Backup integrity, age/schema compatibility, digest preservation, non-overwriting restore and
  occupied-destination/sidecar rejection tests.
- Upgrade preflight tests for current, older-supported, stale, corrupt and schema-mismatch backups.
- Migration rehearsal tests proving real-copy migration, representative record preservation,
  source immutability and deterministic failure cleanup.
- Isolated Docker old-image/new-image acceptance covering fresh bootstrap, backup/verify,
  preflight/rehearsal, injected migration failure, explicit recovery and successful upgrade with
  API/Web readiness and durable identity checks.
- Existing backup, restore, migration, upgrade-preflight, deployment, health/readiness,
  restart/fencing, notification, Task/recovery, authentication and OrganizerExecutor regression
  suites.

### Required commands

```bash
python3 scripts/check_governance.py
.venv/bin/python -m unittest <focused backup/restore/upgrade/migration tests>
.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m pip wheel . --no-deps -w /tmp/mediaflow-wheel-check
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-wheel-check/mediaflow-*.whl
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml Dockerfile compose.yaml scripts || true)"
git diff --check
```

The full regression may retain only the known pre-existing Storage Browser failure and environment-
unavailable external-service skips when reproduced at this Task Base with exact evidence. Docker or
external Storage/Provider/reverse-proxy gates unavailable in the validation environment must be
reported as `SKIP`/`UNAVAILABLE`, not converted into a production claim.

## Non-goals

- Release-wide secret/private-state/image/network scans, TLS/reverse-proxy deployment, non-root and
  API-token certification beyond regression-fencing the existing boundaries (RO-7).
- New schema/product features, automatic rollback, historical rollback, uncertain-mutation replay,
  power-loss guarantees, distributed transactions or in-place destructive restore.
- New Scheduler/Automation definitions, execution authority, Worker fencing, Notification semantics,
  OrganizerExecutor behavior or Storage operations.
- Remote databases/volumes, external registries, production media/credentials, hosted deployment,
  Docker Secrets/Secret Store integration or automatic artifact publication.
- Jobs/Preview/Organize execution-boundary redesign, Configuration/Files/FileIndex redesign,
  dashboard/copy polish or unrelated refactors.

## Developer Completion Report

### Changed Files

```text
TASK.md
docs/deployment.md
docs/release.md
scripts/docker_upgrade_recovery_smoke_test.py
```

### Implemented

```text
- Added an isolated Docker Compose upgrade/backup/migration recovery harness
  (`scripts/docker_upgrade_recovery_smoke_test.py`). It builds a local
  synthetic old-schema image (runtime marker 32) and the current candidate
  image (runtime marker 33), starts the old deployment on temporary `/data` and
  media mounts, activates managed configuration, seeds representative
  FileIndex/Job/Task/TaskItem/Result/schedule/notification/audit/log state,
  creates and verifies a backup, runs candidate upgrade preflight and
  migration rehearsal only on disposable copies, injects a deterministic
  schema-30 migration failure, proves the live database/backup/Active identity
  remain unchanged, probes non-overwriting restore/sidecar rejection, and
  successfully upgrades and restarts the four-service Compose topology.
- Updated deployment/release documentation with the backup, preflight,
  rehearsal, candidate upgrade and fail-closed recovery runbook and with the
  new acceptance command.
- No production application code or frozen domain behavior was changed; the
  existing SQLite backup/verify/restore, upgrade preflight and migration
  rehearsal boundaries are exercised end-to-end.
```

### Tests and Results

```text
python3 scripts/check_governance.py                                   -> PASS
.venv/bin/python -m unittest tests.test_sqlite_backup
  tests.test_sqlite_restore tests.test_upgrade_preflight
  tests.test_migration_rehearsal -v                                   -> PASS (18 tests)
.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py       -> PASS (Docker available)
.venv/bin/python -m unittest discover -s tests
  -> 1389 tests, 1 FAIL / PRE-EXISTING / UNRELATED:
     test_setup_picker_and_execution_environment_guidance_are_present
     ("Storage-relative breadcrumb" absent from served APP_JS), 7 SKIP
.venv/bin/python -m compileall -q mediaflow tests scripts             -> PASS
.venv/bin/python -m pip check                                        -> PASS
.venv/bin/python -m pip wheel . --no-deps -w <tmp>                   -> PASS
.venv/bin/python scripts/wheel_smoke_test.py <tmp>/mediaflow-*.whl   -> PASS
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
  Dockerfile compose.yaml scripts || true)"                           -> PASS
git diff --check                                                      -> PASS
```

The 7 skipped tests are the environment-unavailable real SMB/S3/OpenList and
isolated endurance gates (`SKIP / UNAVAILABLE`). The new harness file is
ruff-clean and formatted.

### Decisions

```text
- The repository has no historical Docker image at runtime schema 32 (the
  Dockerfile was introduced after the current schema marker became 33).  The
  isolated harness therefore builds a synthetic old-schema image from the same
  repository with only the runtime schema marker/defaults pinned to 32; this is
  a local test fixture, never a repository or production artifact, and lets the
  candidate image exercise a real 32 -> 33 repository open/migration path.
- Backup, preflight and rehearsal run through the installed CLI in one-off
  containers after the old stack is stopped, so the harness follows the
  documented stop/backup/gate/upgrade boundary and never relies on a live
  process to mutate the backup.
- Migration failure is injected with a minimal schema-30 backup containing a
  duplicate active unattended-execution grant, the same deterministic failure
  already covered by unit tests; the harness verifies the live database and
  backup digests remain unchanged.
- Existing API/Web status surfaces (System schema/version, management and
  Worker readiness) are used as the read-only upgrade/recovery evidence; no new
  API behavior or Web mutation was needed for this Task.
```

### Remaining In-Slice Work

```text
Slice 29 RO-7 release security/private-state/network validation and Slice-final
acceptance evidence are outside this Task. This Task advances RO-6 only and
does not plan the next Task.
```

### Risks / Deviations

```text
- The full-suite failure is the known pre-existing Storage Browser UI test,
  reproduced identically at Task Base (`mediaflow/interfaces/operator_ui.py`
  and `tests/test_storage_browser.py` are unchanged from Task Base); it is
  unrelated to this Task and is recorded as FAIL / PRE-EXISTING / UNRELATED.
- Whole-repo `ruff check` retains the same pre-existing
  `tests/test_system_settings_management.py` line-length issue; the new
  Task-changed file is clean.
- The synthetic old-schema image is a harness fixture and does not claim to be
  a real prior release artifact. Real older-schema migration paths are covered
  by the existing schema-30 unit tests and by the candidate image's 32 -> 33
  Compose upgrade in this harness.
```

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA after implementation checkpoint]
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
