# Phase 21.16 — Bounded Read-Only File Catalog Status Counts

## Goal

Add a read-only `mediaflow files stats` command that summarizes the durable FileIndex by
ResourceLibrary, Storage, and FileScanStatus without constructing Storage, Scanner, provider,
Planner, OrganizerExecutor or workflow.

## Scope

### 1. Statistics model and service

- Add immutable count data for total files and per-status counts.
- Support optional ResourceLibrary and Storage scoping.
- Reuse existing FileIndex repository reads; no FileIndex schema change.

### 2. Operator workflow

- Add `mediaflow files stats [--resource-library ID] [--storage ID]`.
- Reject unknown ResourceLibrary/Storage IDs.
- Print total and status counts in a stable order.

### 3. Safety

- The command constructs no Storage or provider and performs zero media mutation.
- It never triggers scanning, reconcile, file-content access, or arbitrary SQL.

## Boundaries

- No historical trend, no derived Task Result fields, no UI/API write endpoint, or Phase 21.17.
- Do not redesign Scanner, FileIndex storage schema, Storage adapters, policy engines, Planner,
  OrganizerExecutor or automation.
- Do not add FFmpeg/FFprobe.

## Required Tests

- Stats reflect FileIndex counts and honor ResourceLibrary/Storage scoping.
- Unknown IDs fail closed.
- CLI stats requires no Storage/provider credentials and performs zero network/media mutation.
- Existing file catalog list/show/cursor/derived filtering and full offline regressions pass.

## Validation

Run Phase 21.16, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.16 Result

PASS / FAIL

## File Catalog Stats Workflow

## Safety

## Regression

## Final Recommendation
