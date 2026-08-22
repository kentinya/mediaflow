# Phase 19.24.1 — SMB errno Mapping, Cleanup Repair, and Rerun

## Goal

Repair the real Samba failure recorded in Phase 19.24 by mapping standard
SMBOSError/OSError errno values to stable SMB domain categories, then redeploy
the pinned isolated Samba service and complete the full production matrix and
allowlisted cleanup.

## Scope

### 1. Structured errno mapping

- Map `EEXIST` to `ALREADY_EXISTS` for no-overwrite safety.
- Map `ENOENT` to `NOT_FOUND`; `EACCES`/`EPERM` to `PERMISSION_DENIED`.
- Map standard timeout and connection errno values to the existing timeout,
  connection-lost, or connection-failed categories without parsing messages.
- Preserve subclass and smbprotocol type-name fallbacks where errno is absent.
- Public errors remain normalized and secret-free.

### 2. Cleanup diagnosis

- Add deterministic unit coverage for errno mapping and delete failures.
- Rerun the existing allowlisted real cleanup after the no-overwrite assertion.
- Do not recursively delete or hide unknown objects.
- If cleanup still fails, record the exact normalized category and stop.

### 3. Real Samba rerun

- Reuse pinned Samba 4.20.6, loopback-only port, new credentials, temporary
  Share, and new empty `mediaflow-acceptance-*` root/report.
- Execute lifecycle/no-overwrite, Local↔SMB COPY/MOVE, SMB↔SMB Organizer
  COPY/MOVE, content/size/source verification, and allowlisted cleanup.
- Retain a new non-secret report and destroy container/credentials/backend.

### 4. Status

- Phase 19.24 becomes PASS only when the Samba rerun and prior MinIO evidence are
  both PASS.
- Do not rerun or alter MinIO production behavior unnecessarily.
- Do not begin Phase 19.25 until Samba is closed.

## Boundaries

Do not change Parser, Scanner, Recognition, Metadata, Naming, Classification,
Planner/Organizer policy semantics, S3/OpenList behavior, UI, API, or user
configuration. Do not use `config/alist.json`.

## Validation

Run focused SMB real/unit/Organizer/Storage tests, full offline tests, formatter,
lint, compile, dependency/config checks, FFmpeg/FFprobe audit, isolated wheel
smoke, and the explicit real Samba matrix.

## Completion Report

Finish with:

## Phase 19.24.1 Result

PASS / FAIL

## Errno Mapping

## Samba Matrix

## Evidence

## Cleanup

## Safety

## Regression

## Changed Files

## Remaining Work

## Risks

## Final Recommendation
