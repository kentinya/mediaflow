# Phase 19.13 — Non-overwriting Offline Runtime Database Restore

## Goal

Restore a verified local SQLite backup only into a missing configured runtime database path. Preserve
the existing no-overwrite safety model: MediaFlow must never replace, rename, delete, or migrate an
existing runtime database during restore.

## 1. Restore service

- Add a local infrastructure restore service that accepts an explicit backup and the configured
  `persistence.databasePath` destination.
- Verify the backup with the existing Phase 19.10 integrity/schema rules before staging.
- Copy through SQLite's online backup API into a private temporary file in the destination directory,
  verify the staged database, fsync it, and atomically publish only if the destination is still absent.
- Preserve backup content/mtime/hash and return destination, restored schema, byte size, SHA-256, UTC
  completion time, and whether a later repository open will require migration.
- Apply restrictive owner-only file permissions where supported.

## 2. Fail-closed destination rules

- Refuse an existing file, directory, symlink, same backup/destination, missing/symlink parent, NUL,
  or any existing destination `-wal`, `-shm`, or `-journal` sidecar.
- Never overwrite or remove any destination/sidecar, even after a race.
- On verification/copy/fsync/publish failure, remove only the service-owned temporary file.
- An existing/corrupt runtime database must be moved aside manually after services are stopped; this
  command does not automate that destructive operator decision.

## 3. CLI and explicit confirmation

- Add `mediaflow database restore BACKUP --confirm-empty-destination`.
- Resolve destination only from configured `persistence.databasePath`; expose no arbitrary destination.
- Without the exact confirmation flag, fail before validating/copying or creating any file.
- Output no configuration content, credentials, task errors, titles, provider data, or media paths.
- Construct no media Storage, MetadataProvider, Scanner, workflow, Scheduler, Notification worker,
  API, or OrganizerExecutor.

## 4. Operational boundary

- Document the required sequence: stop all MediaFlow processes, verify backup, manually preserve/move
  any existing runtime and sidecars, restore into the empty configured path, verify, then start one
  process and allow normal repository migration if reported.
- Do not claim to detect service shutdown. Refusal of destination and sidecars is a safety guard, not
  a complete process-liveness proof.
- Exercise restore in the isolated installed-wheel smoke test using temporary local state only.

## Required tests

- Successful current-schema restore preserves representative Task/Result/audit/log records and backup.
- Older supported backup restores unchanged and reports migration-required without migrating.
- Confirmation missing, existing destination file/directory/symlink, same path, sidecars, missing or
  symlink parent, NUL, malformed/empty/missing/newer backup fail before publication.
- Destination race and injected verify/copy/fsync/publish failures never overwrite data and clean only
  owned temporary files.
- Restored file mode is owner-only where supported; result size/hash/schema are correct and reopen works.
- CLI uses configured destination, constructs no media services, and has secret-free errors/output.
- Installed-wheel smoke test restores to a second missing temporary runtime and verifies it.
- Full existing regression and quality gates pass.

## Documentation

Update README, requirements, architecture, progress, roadmap, release checklist, and configuration
operations documentation.

## Out of scope

Replacing an existing database, automatic rollback backup, moving/deleting old runtime files,
service-stop detection, in-place migration, remote backup/restore, encryption, retention, API/UI,
scheduling, release publishing, deployment, and media Storage operations.

## Final report

## Phase 19.13 Result

PASS / FAIL

## Restore

## CLI

## Safety and Failure Handling

## Operational Procedure

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
