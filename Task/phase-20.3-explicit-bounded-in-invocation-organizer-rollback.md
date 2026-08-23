# Phase 20.3 — Explicit Bounded In-Invocation Organizer Rollback

## Goal

Add an opt-in, fail-closed compensation path to OrganizerExecutor so a failed multi-step execution
can reverse only the effects created and recorded by that same invocation.

## Scope

### 1. Rollback domain policy and evidence

- Add immutable RollbackPolicy, status, step/evidence and ExecutionResult rollback fields.
- Rollback defaults disabled. Enabling it is explicit OrganizePolicy configuration.
- Record attempted action, Storage identities, relative paths, outcome and bounded error category;
  never record media content, credentials or secret-derived values.

### 2. Owned-effect execution journal

- OrganizerExecutor records each successfully created target and directory as execution proceeds.
- Capture a bounded target fingerprint from Storage stat after mutation and verify it again before
  compensation. A changed/unverifiable target is unknown and must not be deleted or moved.
- Journal only this invocation. Never infer ownership from historical paths, scan results, naming,
  or a failed operation that produced no verifiable target.

### 3. Reverse-order compensation

- COPY/HARDLINK/SYMLINK: delete only the invocation-owned destination.
- Same-storage MOVE: move the invocation-owned destination back only when source is absent.
- Cross-storage MOVE: if source still exists after copy/delete failure, remove only the owned target;
  if source was deleted, restore it by bounded Storage transfer and verification before removing the
  target. Never overwrite a reappeared source.
- Roll back attachments and primary in strict reverse completion order, then optionally delete only
  directories created by this invocation; non-empty/changed directories are left with explicit error.

### 4. Result and status semantics

- Original execution failure remains visible. Successful compensation returns FAILED with rollback
  status SUCCESS; failed/incomplete compensation returns PARTIAL.
- Failure before an owned mutation returns FAILED with rollback NOT_NEEDED.
- Successful execution and DryRun never run rollback. DryRun remains zero mutation.
- Persist rollback operation markers through existing completed-operation/result evidence and emit
  structured redacted logs without changing Task retry semantics.

### 5. Safety/configuration

- Reject rollback-enabled execution with overwrite authorization because the previous destination
  cannot be reconstructed safely.
- Add optional `rollback: {"enabled": false, "cleanupCreatedDirectories": true}` to external
  OrganizePolicy configuration. Validate unknown fields and non-booleans at startup.
- Only OrganizerExecutor may perform compensation mutations, through Storage interfaces only.

## Boundaries

- No arbitrary historical/manual rollback command, unknown-file cleanup, recursive delete, automatic
  retry, Task pause/resume, empty source-directory cleanup, or distributed transaction claim.
- Do not change Parser, Recognition, Metadata, Naming, Classification or Scanner/FileIndex semantics.
- Do not add FFmpeg/FFprobe and do not begin Phase 20.4.

## Required Tests

- Default disabled compatibility and DryRun zero mutation.
- COPY/LINK target compensation, same-storage MOVE restore, cross-storage MOVE copy-failure cleanup
  and post-delete restore, attachment reverse order and created-directory cleanup.
- No-effect failure, overwrite rejection, source reappeared, target fingerprint changed, unknown
  target, rollback mutation failure, non-empty directory and partial rollback.
- ExecutionResult/log/persistent completed-operation evidence and deterministic bounded errors.
- LocalStorage integration plus fake Storage fault injection; C identity and prior plan unchanged.

## Validation

Run Phase 20.3, Organizer/attachments/conflict/Task persistence, all Storage, DryRun, Strategy,
Metadata, Recognition, Parser/NFO, Scanner/FileIndex and complete offline regressions. Run formatter,
lint, compile, configuration validation, dependency/build checks, FFmpeg/FFprobe audit and diff.

Update `README.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/progress.md`,
`docs/roadmap.md`, and requirements status with exact rollback non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 20.3 Result

PASS / FAIL

## Rollback Semantics

## Compensation Matrix

## Safety

## Regression

## Final Recommendation
