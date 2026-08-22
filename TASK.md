# Phase 19.15 — Isolated Runtime Schema Migration Rehearsal

## Goal

Exercise the real SQLite forward-migration path against a private copy of an explicit verified backup,
then discard the copy. Give operators evidence that the target MediaFlow artifact can migrate their
data before it ever opens the production runtime database.

## 1. Rehearsal service

- Add a local infrastructure service accepting an explicit backup.
- Verify the backup with Phase 19.10 rules, copy it through SQLite into an owner-only temporary database,
  and record the source schema.
- Open only the temporary database through the production `SQLiteTaskRepository` migration path.
- Reopen/verify the migrated copy, require the current schema, and confirm representative core table
  counts remain readable before reporting PASS.
- Return source/target schema, migration-required/performed flags, backup SHA-256/size, temporary cleanup
  status, UTC completion time, and application version.

## 2. Cleanup and failure safety

- Always close the repository and remove only the rehearsal-owned temporary database plus its own
  `-wal`, `-shm`, and `-journal` sidecars.
- Preserve backup and configured Runtime hash/mtime/size on success and every injected failure.
- Reject missing, empty, malformed, symlink, unsupported/newer backup, unsafe parent, and NUL paths.
- A migration failure must return a clear local error and leave no rehearsal files.
- Never publish, restore, replace, migrate, or open the configured Runtime database.

## 3. CLI and release integration

- Add `mediaflow upgrade rehearse --backup /safe/backups/runtime.sqlite3`.
- Resolve the configured Runtime only for the existing shared cooperative lease; do not read/open it.
- Output safe schema/count/checksum facts only; never configuration, credentials, paths from records,
  task errors, titles, provider data, or media paths.
- Add rehearsal after backup/preflight in the release checklist and installed-wheel smoke test.

## 4. Boundaries

- Construct no media Storage, MetadataProvider, Scanner, workflow, Scheduler, Notification worker,
  API, or OrganizerExecutor.
- Do not add new migration semantics or alter existing migration SQL except for a proven defect.
- Do not implement in-place upgrade, rollback, replacement, automatic restore, API/UI, or scheduling.
- Preserve RecognitionType C and every accepted media pipeline behavior.

## Required tests

- Current-schema rehearsal is a verified no-op copy exercise.
- Representative older-schema backup migrates to current and preserves Task/Result/audit/log records.
- Missing/malformed/empty/symlink/newer backup and invalid path fail without residue.
- Injected copy, repository migration, verification, and cleanup-adjacent failures preserve source data
  and remove owned database/sidecars.
- Backup and configured Runtime hash/mtime/size stay unchanged; Runtime repository is never opened.
- CLI holds shared lease, creates no media services, and emits secret-free bounded output.
- Installed-wheel rehearsal passes outside the checkout.
- Full existing regression and quality gates pass.

## Documentation

Update README, requirements, architecture, progress, roadmap, release checklist, and configuration
operations documentation.

## Out of scope

Production/in-place migration orchestration, rollback, database replacement, automatic restore,
maintenance shutdown, remote backups, encryption, retention, API/UI, deployment, and media Storage.

## Final report

## Phase 19.15 Result

PASS / FAIL

## Migration Rehearsal

## Data Preservation

## CLI

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
