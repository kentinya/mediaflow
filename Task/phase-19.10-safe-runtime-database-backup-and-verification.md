# Phase 19.10 — Safe Runtime Database Backup and Verification

## Goal

Protect the production SQLite runtime state introduced through Phases 14–19 with consistent online
backups and read-only verification. Provide local operator commands only. Do not implement restore or
touch media Storage.

## 1. Backup adapter

- Add an infrastructure backup service using SQLite's online backup API so WAL/uncommitted file-copy
  assumptions cannot produce inconsistent snapshots.
- Back up the configured runtime database to an explicit local destination through a temporary file,
  verify it, then publish atomically.
- Refuse source=destination, directories, symlinks, existing targets, unsafe NUL paths, and unsupported
  parent state. Never overwrite a backup.
- Clean up only the service-owned temporary file after failure; never delete source or target data.
- Return a structured result with UTC time, source schema version, byte size, SHA-256, and destination.

## 2. Verification

- Open candidate backups read-only and run bounded SQLite integrity/schema checks.
- Require the runtime schema marker and reject newer-than-supported, missing, malformed, empty,
  truncated, or non-SQLite files with clear local errors.
- Verification must not migrate or otherwise modify the candidate.

## 3. CLI

- Add `mediaflow database backup --output /safe/path/runtime.sqlite3`.
- Add `mediaflow database verify /safe/path/runtime.sqlite3`.
- Resolve the source only from configured `persistence.databasePath`; no arbitrary source option.
- Commands construct no Storage, Provider, Scanner, workflow, Scheduler, Notification worker, API, or
  OrganizerExecutor and never expose configuration secrets.

## 4. Safety and concurrency

- Existing readers/writers may continue during online backup; snapshot must pass integrity verification.
- Backup/verify performs zero media Storage mutation and never changes Tasks, Results, audit, logs,
  FileIndex, execution authorization, or source SQLite state.
- No API/Web endpoint, scheduled backup, retention deletion, upload, encryption, or restore in this phase.

## Required tests

- Successful online backup includes current schema and representative Task/Result/audit/log records.
- WAL/concurrent-write snapshot remains internally consistent and source remains usable.
- SHA-256/size/schema result correctness and deterministic verification output.
- Existing target, same path, directory, symlink, missing parent/source, NUL, malformed/truncated/empty,
  missing schema marker, and newer schema rejection.
- Injected backup/integrity/publish failures leave source intact, never overwrite target, and remove only
  owned temporary files.
- Verify is provably read-only (mtime/hash unchanged) and creates no sidecar/WAL files.
- CLI argument/config errors and output contain no secrets; no Storage/provider/workflow construction.
- SQLite migration, Task/History, logs, API/UI, Scheduler/Notification, Storage, DryRun, and full regressions.
- Formatter, lint, compile, dependency/build/configuration, FFprobe/FFmpeg, and diff checks.

## Documentation

Update README, requirements, configuration, architecture, progress, and roadmap with commands,
snapshot semantics, verification, operational procedure, and explicit restore/encryption limitations.

## Out of scope

Restore, automatic scheduling, backup retention/deletion, remote/object-storage upload, encryption/key
management, compression, incremental backup, API/UI controls, OIDC, Secret Store, and TLS.

## Final report

## Phase 19.10 Result

PASS / FAIL

## Backup

## Verification

## CLI

## Safety and Failure Handling

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
