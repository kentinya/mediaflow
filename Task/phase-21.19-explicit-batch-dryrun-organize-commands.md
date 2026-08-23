# Phase 21.19 — Explicit Batch DryRun/Organize Commands

## Goal

Expose explicit `mediaflow batch preview` and `mediaflow batch organize` commands that reuse the
existing no-path all-ResourceLibrary pipeline, making the batch business closure unambiguous.

## Scope

### 1. CLI commands

- Add `mediaflow batch preview [--limit N]`.
- Add `mediaflow batch organize [--limit N] [--execute]`.
- Map each batch command to the existing no-path `preview`/`organize` pipeline without duplicating
  workflow logic.

### 2. Safety

- `batch organize` remains DryRun unless `--execute` is present.
- Original-plus-fresh execute authorization boundaries remain unchanged.
- No new Storage/Scanner/Provider construction is introduced by the command mapping.

## Boundaries

- No per-file selection UI, no new organize engine, no automation scheduling, or Phase 21.20.
- Do not redesign Scanner, Storage, Metadata, Planner, OrganizerExecutor or policy engines.
- Do not add FFmpeg/FFprobe.

## Required Tests

- `batch preview` delegates to the existing all-ResourceLibrary DryRun path.
- `batch organize` delegates to the existing all-ResourceLibrary organize path and rejects execute
  without authorization.
- Existing preview/organize, DryRun, Storage and full offline regressions pass.

## Validation

Run Phase 21.19, all review/correction/ignore queues, Task pause/resume/retry, Recognition/Strategy,
Metadata/Naming/Classification/Planner/Organizer, Scanner/FileIndex, all Storage adapters, DryRun and
the full offline suite. Run formatter, lint, compile, dependency, example/user configuration
validation, FFmpeg/FFprobe audit, wheel build and diff checks.

Update README, architecture, configuration, progress, roadmap, requirements status and product
specification with exact non-claims.

## Completion Report

Use AGENTS.md structure and additionally report:

## Phase 21.19 Result

PASS / FAIL

## Batch Command Workflow

## Safety

## Regression

## Final Recommendation
