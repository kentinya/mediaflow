# Phase 19.12 — Read-only Upgrade Preflight and Compatibility Report

## Goal

Provide a local, fail-fast pre-upgrade check that proves the configured runtime database and an
operator-supplied backup are readable and compatible before any application upgrade. The command is
strictly observational: it must not migrate, restore, replace, or mutate any database or media Storage.

## 1. Upgrade preflight service

- Add an infrastructure/application boundary that inspects the configured runtime database and one
  explicit backup through read-only SQLite connections.
- Reuse the Phase 19.10 verification rules rather than duplicating SQLite integrity/schema semantics.
- Report application version, running Python version/support, current supported schema, runtime schema,
  backup schema, backup age, size, SHA-256, and readiness status.
- Require runtime and backup schema versions to agree and be supported; older supported schemas may be
  reported as migration-required but must not be migrated during preflight.
- Require a configurable positive maximum backup age and use filesystem UTC modification time only as
  operational freshness evidence, not database identity proof.

## 2. CLI

- Add `mediaflow upgrade check --backup /safe/backups/runtime.sqlite3`.
- Add optional `--max-backup-age-hours` with a safe 24-hour default and bounded positive value.
- Resolve the runtime database only from configured `persistence.databasePath`.
- Return success only when Python, runtime database, backup integrity/schema, schema agreement, and
  backup freshness all pass. Fail with a clear local configuration/compatibility error otherwise.
- Output only local compatibility facts; never print configuration content, tokens, passwords, URLs,
  media paths, task errors, titles, or provider data.

## 3. Read-only guarantees

- Do not instantiate SQLiteTaskRepository or any adapter that can run migrations.
- Hash/mtime/size of runtime and backup must remain unchanged and no `-wal`/`-shm` sidecars may be
  created by preflight.
- Construct no Storage, MetadataProvider, Scanner, workflow, Scheduler, Notification worker, API, or
  OrganizerExecutor.
- Do not create a backup automatically; the operator must explicitly create and identify it.

## 4. Documentation and release integration

- Add the preflight command to the release checklist after backup creation and before upgrade.
- Document that PASS is compatibility evidence only, not service shutdown, restore, rollback, or live
  Storage/provider validation.
- Exercise preflight in the isolated installed-wheel smoke test using temporary local databases.

## Required tests

- Ready current-schema source plus verified fresh backup.
- Older matching schema reports migration-required without changing either file.
- Runtime/backup schema mismatch, newer schema, missing/malformed/empty backup, stale/future-dated
  backup, missing runtime, same source/backup, and invalid age bounds fail clearly.
- Python support and installed/development version reporting are deterministic and secret-free.
- Hash, mtime, size, and sidecar absence prove read-only behavior on success and failure.
- CLI exits correctly and creates no Storage/provider/workflow objects.
- Installed-wheel smoke test includes a successful upgrade preflight.
- Full existing regression and quality gates pass.

## Documentation

Update README, requirements, architecture, progress, roadmap, and release checklist.

## Out of scope

Database migration execution, restore/replacement, rollback, automatic backup, service-stop detection,
retention, remote upload, encryption, API/UI exposure, release publishing, deployment, and live
provider/storage tests.

## Final report

## Phase 19.12 Result

PASS / FAIL

## Preflight

## Compatibility

## CLI

## Read-only Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
