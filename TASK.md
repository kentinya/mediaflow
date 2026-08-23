# Phase 20.6 — Bounded Safe Source Directory Cleanup

## Goal

Add an opt-in, policy-driven source directory cleanup step after a fully successful MOVE while
preserving fail-closed boundaries and never deleting unknown content.

## Scope

### 1. Cleanup policy and evidence

- Add immutable cleanup policy/mode/result evidence to OrganizePolicy/ExecutionResult.
- Modes: `none` (default), `empty`, and `ignorable`.
- Configure a bounded upward directory count and, only for `ignorable`, explicit basename glob
  patterns. Reject unsafe/unbounded configuration at startup.

### 2. Source boundary semantics

- Preserve the ResourceLibrary Storage-relative root in OrganizePlan as a cleanup boundary.
- Cleanup may inspect only ancestors of the successfully moved primary source, never the source
  library root itself, Storage root, destination tree, unrelated path, absolute path, or traversal.
- Stop at the first non-empty, changed, invalid, inaccessible, or unverified directory.

### 3. OrganizerExecutor-only mutation

- Run cleanup only after MOVE plus attachment transfer and verification fully succeeds, only with
  explicit execute authority, and only inside OrganizerExecutor.
- `empty` deletes only a directory proven empty immediately before deletion.
- `ignorable` may delete only ordinary files whose basenames match configured patterns, with a
  bounded entry count and stat-before-delete validation; any unknown entry prevents all cleanup in
  that directory.
- Cleanup failure produces bounded evidence and PARTIAL rather than hiding failure or replaying the
  organize operation.

### 4. Safety exclusions

- COPY/LINK/SKIP/NOOP, DryRun, failed/partial execution, conflicts and rollback never run cleanup.
- Never follow or delete symlinks, recursively delete, delete a non-empty directory through provider
  semantics, clean destination directories, silently broaden patterns, or auto retry cleanup.

## Boundaries

- Do not implement historical cleanup, periodic cleanup, orphan discovery, cross-task rollback,
  Hash persistence, Phase 21 UI/manual correction, or Phase 22 configuration CRUD.
- Do not change Parser, Recognition, Metadata, Naming, Classification, Storage adapter semantics or
  execution authorization.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Default none and configuration validation, empty and ignorable modes, bounded upward cleanup.
- Source library root/storage root preservation, traversal/absolute boundary rejection, direct-root
  source preservation, symlink/unknown/subdirectory refusal and stat/list race failure.
- MOVE success cleanup, attachment cleanup, COPY/LINK/DryRun/failure/conflict/rollback zero cleanup.
- Local, fake SMB/OpenList/S3 capability behavior without production services; Storage mutation call
  accounting and no recursive delete assumption.
- Persistent Execution/Task evidence, stable bounded errors, C identity preservation and complete
  existing regressions.

## Validation

Run Phase 20.6, Organizer/rollback, Task/retry, all Storage adapters and isolated acceptance-unit
profiles, Scanner/FileIndex, DryRun, Strategy/Metadata/Recognition/Parser/NFO and full offline suite.
Run formatter, lint, compile, dependency, both configuration validations, FFmpeg/FFprobe audit,
wheel build and diff checks.

Update `README.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/progress.md`,
`docs/roadmap.md`, requirements status and product specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 20.6 Result

PASS / FAIL

## Cleanup Matrix

## Boundary Evidence

## Safety

## Regression

## Final Recommendation
