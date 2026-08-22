# Phase 19.24 — Isolated Samba and MinIO S3 Acceptance Matrices

## Goal

Deploy operator-authorized isolated Samba and MinIO services and execute
production SMBStorage/S3Storage plus OrganizerExecutor lifecycle and transfer
matrices. Retain honest, non-secret evidence and destroy all temporary services,
credentials, shares, buckets, prefixes, and generated objects afterward.

## Scope

### 1. Fail-closed real-test gates

- Replace the unsafe optional S3/R2 integration defaults with explicit URL or
  host/port, dedicated credentials, share/bucket, no-default acceptance root or
  prefix, exact destructive confirmation, and a new absolute JSON report path.
- Samba root and S3 prefix final component must start with
  `mediaflow-acceptance-` and be proven empty before mutation.
- Missing/partial prerequisites are BLOCKED/NOT RUN, never PASS.
- Never use runtime/user configuration or `config/alist.json`.

### 2. Isolated deployments

- Pin a Samba image/version and a MinIO release image/digest.
- Bind services only to host loopback or an isolated Docker network.
- Generate new run-scoped credentials and temporary host data.
- Samba exposes one dedicated share; MinIO exposes one dedicated bucket/prefix.
- Do not mount repository or media-library paths.

### 3. Production matrices

Using production adapters and OrganizerExecutor, cover:

- health/connect, list, stat, read, write, no-overwrite, copy, move, delete
- Local → SMB COPY/MOVE and SMB → Local COPY/MOVE
- SMB → SMB Organizer COPY/MOVE
- Local → S3 COPY/MOVE and S3 → Local COPY/MOVE
- S3 → S3 Organizer COPY/MOVE
- content, size, destination and MOVE source-state verification
- safe allowlisted cleanup with no unknown-object deletion

Cross-provider SMB↔S3 is not required unless existing Organizer behavior makes
it a small reuse-only extension.

### 4. Evidence

- Produce separate bounded, secret-free Samba and MinIO JSON records.
- Record pinned image/version, UTC time, planned/completed operations, empty-root
  preflight, result, cleanup, and normalized error category.
- A discovered production defect is FAIL and belongs to a separate repair task;
  do not mix adapter repair into the acceptance commit.
- MinIO certifies generic S3-compatible behavior, not AWS or Cloudflare service.

### 5. Cleanup and status

- Stop/remove containers and delete generated credentials/data after inspection.
- Retain only non-secret reports outside Git and normalized documentation.
- Phase 19.24 PASS requires both Samba and MinIO full matrices plus cleanup PASS.

## Boundaries

Do not change Parser, Scanner, Recognition, Metadata, Naming, Classification,
Planner/Organizer policy semantics, UI, API, or user configuration. Do not start
long-duration/large-object Phase 19.25 work.

## Validation

Run focused SMB/S3/Organizer/Storage tests, full offline tests, formatter, lint,
compile, dependency/configuration and FFmpeg/FFprobe checks, isolated wheel
smoke, and both explicitly gated real matrices.

## Completion Report

Finish with:

## Phase 19.24 Result

PASS / BLOCKED / FAIL

## Samba Matrix

## MinIO Matrix

## Evidence

## Cleanup

## Safety

## Regression

## Changed Files

## Remaining Work

## Risks

## Final Recommendation
