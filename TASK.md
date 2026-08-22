# Phase 15 — Conflict Decisions + Persistent NeedConfirm

## Goal

Complete conflict decision handling without redesigning accepted Parser, Recognition, Metadata,
Naming, Classification, Planner, Executor, Scanner, or Storage behavior. Persist every decision so
that process restarts never turn an unresolved conflict into an implicit mutation.

## Required implementation

### 1. Domain decisions

- Define persistent confirmation records and statuses for organize-plan conflicts.
- Support explicit `skip`, `rename`, `manual`, and `overwrite` decisions.
- `manual` remains unresolved until a later concrete decision.
- Invalid destinations are never overridable.
- Rename generates a deterministic, traversal-safe destination without mutating Storage.
- Overwrite requires both an overwrite-enabled OrganizePolicy and fresh high-risk authorization.

### 2. Runtime configuration

- `organizePolicies[].conflictStrategy` accepts `skip`, `rename`, `manual`, or `overwrite`.
- Preserve legacy `overwrite: true` compatibility, but reject contradictory settings.
- Default remains `manual`; no hidden Move, Skip, Rename, or Overwrite fallback.
- Validate values before scanning and produce zero Storage mutations.

### 3. Persistent NeedConfirm queue

- Persist conflict type, plan/source/destination identity, proposed decision, timestamps, actor,
  note, and overwrite authorization.
- Upgrade the SQLite runtime schema through an explicit forward migration.
- Conflicted task items become `waiting_confirm`, not ordinary media failures.
- Waiting-confirm items are not retried until explicitly resolved.
- Preserve an append-only decision audit trail.

### 4. Application resolution

- Keep conflict logic outside Naming, Classification, Storage adapters, and strategy engines.
- Apply configured automatic `skip` or `rename` deterministically.
- Queue `manual` and `overwrite` decisions when confirmation is required.
- A resolved decision creates a safe replacement plan; it does not mutate Storage itself.
- OrganizerExecutor remains the sole mutation boundary.

### 5. CLI

Add read/decision commands:

```text
mediaflow confirmations list
mediaflow confirmations show CONFIRMATION_ID
mediaflow confirmations resolve CONFIRMATION_ID --strategy skip|rename|manual|overwrite
  [--confirm-overwrite] [--actor NAME] [--note TEXT]
```

- Listing/showing/resolving records performs zero Storage mutation.
- Overwrite resolution without `--confirm-overwrite` fails clearly.
- Commands never print secrets.

### 6. Duplicate evidence

- Keep provider ID as provider-neutral duplicate evidence.
- Include media type, season, and episode set in duplicate identity so distinct TV episodes do not
  collide solely because they share a series provider ID.
- Hash evidence remains optional and must not trigger file reads unless explicitly configured.

## Safety

- Default behavior remains DryRun.
- No silent overwrite or delete.
- Configuration validation and confirmation commands make zero Storage mutations.
- RecognitionType C remains C while reusing A downstream policies.
- Phase 15 must not implement attachments, NFO parsing, API, Web UI, Scheduler, or Phase 16 work.

## Required tests

- Configured Skip, Rename, Manual, and Overwrite behavior.
- Rename collision sequence and traversal/absolute-path rejection.
- Explicit overwrite authorization and default denial.
- SQLite schema v1→v2 migration, confirmation persistence, reopen, and audit history.
- Waiting-confirm task status, retry exclusion, explicit resolution.
- Duplicate identity distinguishes TV season/episode sets.
- CLI list/show/resolve, malformed IDs/options, and zero mutation.
- Parser, Recognition/C, Metadata, Naming, Classification, Planner, Executor, Strategy CLI,
  Scanner/FileIndex, Storage adapters, Task recovery, and DryRun regressions.

## Documentation

Update README, configuration, architecture, progress, roadmap, and example configuration. Document
decision lifecycle, overwrite authorization, CLI use, migration, and limitations.

## Validation

Run all tests, formatter, linter, compile check, dependency check, build, configuration validation,
FFprobe/FFmpeg audit, and diff check. Fix every Phase 15 failure before reporting PASS.

## Final report

## Phase 15 Result

PASS / FAIL

## Conflict Decisions

## NeedConfirm Persistence

## CLI

## Safety

## Regression

## Changed Files

## Decisions

## Remaining Work

## Risks

## Final Recommendation
