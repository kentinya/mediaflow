# Phase 20.2 — Configurable Read-Only Hash Duplicate Detection

## Goal

Add configuration-driven file Hash evidence to duplicate detection without changing the default
zero-read planning behavior or weakening existing conflict and execution safety.

## Scope

### 1. Provider-neutral Hash model and policy

- Add immutable Hash mode, policy, digest/evidence, status, and duplicate comparison result models.
- Support `NONE`, `FAST`, and `FULL`; default is `NONE`.
- Configure FAST sample bytes, FULL maximum file size, and streaming chunk size with validated,
  bounded values. Algorithm/version identifiers must make FAST and FULL evidence unambiguous.

### 2. Storage-only Hash calculation

- Depend only on the Storage interface; never use concrete adapter or filesystem APIs.
- `NONE` performs no `stat` or `read`.
- `FAST` hashes file size plus a bounded leading sample and never claims to be a full-content hash.
- `FULL` streams the complete object in bounded chunks after enforcing the configured size limit.
- Detect premature EOF, over-read/inconsistent size, Storage failures, and cancellation explicitly.
- Hash calculation performs zero Storage mutations and does not cache secrets or log content.

### 3. Duplicate comparison and planning integration

- Compare source and destination only when configured; size mismatch is `UNIQUE` without content
  reads, matching size+digest is `DUPLICATE`, and unavailable/incomplete evidence is
  `INDETERMINATE`, never silently unique or duplicate.
- Integrate after deterministic OrganizePlan destination calculation and before conflict resolution.
- A duplicate adds/retains `DUPLICATE_MEDIA`; indeterminate configured Hash adds an explicit
  fail-closed `UNKNOWN` conflict. Existing destination/provider duplicate conflicts remain intact.
- Hash evidence must not automatically resolve Skip/Overwrite/Rename/Manual, alter the requested
  organize operation, delete a source, or execute Storage mutations.

### 4. Runtime configuration

- Extend external `organizePolicies` with an optional `duplicateDetection` object containing mode
  and bounded resource options. Existing configurations load as `NONE` without reads.
- Reject unknown fields, unsupported modes, booleans masquerading as integers, unsafe limits, and
  malformed policy values during startup validation.
- Update example configuration with explicit `NONE` and documented FAST/FULL examples without
  enabling expensive hashing by default.

### 5. Boundaries

- Do not modify Scanner incremental semantics or FileIndex schema in this phase.
- Do not persist Hashes, add background hashing, implement Rollback/retry/pause/empty-directory
  cleanup, or begin Phase 20.3.
- Do not call Metadata providers or FFmpeg/FFprobe. RecognitionType C must remain C.

## Required Tests

- NONE zero read/stat; FAST bounded prefix; FULL bounded streaming; empty and small files.
- Same content, different content with same size, size mismatch, premature EOF, excess data,
  Storage stat/read errors, size limit, cancellation, and deterministic digest/version.
- Local and fake remote Storage behavior without requiring production services.
- Configuration default/backward compatibility, FAST/FULL parsing, invalid/unknown values.
- Planner/MediaOrganizer duplicate and indeterminate conflicts, unchanged operation, DryRun and
  zero mutation.
- Cross-storage comparison and RecognitionType C preservation.

## Validation

Run Phase 20.2 tests, Organizer/Planner/conflict, runtime configuration, Strategy, Parser/NFO,
Scanner/FileIndex, all Storage and DryRun regressions, then the full offline suite. Run formatter,
lint, compile, configuration validation, dependency/build checks, FFmpeg/FFprobe audit and diff.

Update `README.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/progress.md`,
`docs/roadmap.md`, and requirements status. Do not claim cryptographic duplicate certainty for FAST.

## Completion Report

Use the AGENTS.md completion structure and additionally report:

## Phase 20.2 Result

PASS / FAIL

## Hash Modes

## Duplicate Semantics

## Safety

## Regression

## Final Recommendation
