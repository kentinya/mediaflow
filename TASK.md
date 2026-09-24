# Task 38.4 — 完成 MediaLibrary 有界 Copy/Move 与恢复

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.4
Parent Slice: 38
Status: PLANNED
Task Base: 8cfddad289d2883a17f915e96162ae9e52724140
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An authorized operator can explicitly Copy or Move bounded files/directories from the selected
MediaLibrary to the current or another enabled MediaLibrary, including different supported
Storages, with exact endpoint authority, conflict choices, durable per-item progress and safe
recovery. This advances Slice 38 RO-5, RO-6 and RO-7 and completes the MediaLibrary transfer part
of the ordinary Files journey while preserving ResourceLibrary transfer behavior.

## Why This Task Exists

Task 38.3 completed the MediaLibrary direct maintenance commands, but Copy/Move remains the main
missing ordinary action in RO-5. The repository already has a bounded ResourceLibrary transfer
manifest, OrganizerExecutor boundary, cross-Storage verification and Worker lifecycle. The next
coherent unit is to extend that mechanism with a MediaLibrary-only authority and a real Web/API
journey rather than introducing a second transfer state machine or allowing a MediaLibrary ID to
enter the ResourceLibrary path.

## Implementation Scope

```text
Domain / transfer application / persistence
  → MediaLibrary-scoped manifest, task and recovery authority
  → media transfer API and audit routes
  → MediaLibrary Web destination picker and transfer dialog
  → Worker/Operations projections and focused, integration, browser tests
```

- Parameterize the existing bounded transfer service for a MediaLibrary source and MediaLibrary
  destination. Resolve both endpoints, enabled Storages and roots from the same immutable Active
  snapshot; client-supplied Storage IDs, host roots and raw paths never become authority.
- Add media-scoped `transfer-impact`, transfer submission and durable transfer-status API routes
  under `/api/v1/media-libraries/{id}/files/...`. Preserve the ResourceLibrary route names,
  request/response compatibility and existing ResourceLibrary task reconstruction.
- Keep Copy/Move bounds, safe relative paths, physical self/ancestor overlap detection through
  resolved Storage identity, no-overwrite conflict default and supported `fail`/`skip`/`keep_both`
  choices. Protect both library roots and reject traversal, symlink/alias escapes, unsupported
  entries, stale manifests, changed Active snapshots and unavailable/disabled bindings.
- Preserve same-Storage provider capability semantics. For cross-Storage Move, execute only the
  explicit Copy → verify → Delete-source sequence through `OrganizerExecutor`; failed verification
  leaves the source intact. Never fall back from Copy to Move or replay an uncertain mutation.
- Persist source and destination library kind/IDs, pinned revision evidence, per-item checkpoints,
  known effects and safe next actions without exposing host roots, credentials, claim tokens or
  raw provider errors. A media transfer cannot be claimed or reconstructed by a ResourceLibrary
  transfer service, even when IDs collide.
- Connect the resident Worker and existing Operations lifecycle for media transfer progress,
  pause/resume/cancel where advertised, reconnect/revisit and in-flight uncertain recovery. The
  Web must poll the durable projection and never resubmit on refresh or transport ambiguity.
- Extend the MediaLibrary Files page and shared transfer dialog with explicit destination
  MediaLibrary selection and bounded destination-directory browsing. Keep source selection,
  destination context and correctable inputs after recoverable failures; close/cancel never implies
  rollback; reconcile only backend-advertised known effects in fresh live source/destination
  listings. Ordinary cross-kind ResourceLibrary↔MediaLibrary transfers remain out of scope.
- Keep the existing ResourceLibrary Files page, Organize journey, direct commands, configuration
  routes and API response bytes compatible. Do not modify `docs/pics/文件页.png`,
  `docs/pics/媒体库页.png`, `config/alist.json` or credentials.

## Acceptance Criteria

- [ ] An authorized operator can select bounded MediaLibrary files/directories, choose the current
      or another enabled MediaLibrary and destination directory, preview the exact Copy/Move
      impact, select an advertised conflict mode, explicitly submit once, and follow the durable
      result from `/ui-v2/medialib/files` through success, partial, denied and recovery states.
- [ ] MediaLibrary transfer API and Web use one application behavior and the same permissions;
      every media route resolves both endpoints from exact Active authority, and equal or
      overlapping ResourceLibrary IDs/roots cannot exchange manifests, evidence or task claims.
      ResourceLibrary transfer routes and documents remain compatible.
- [ ] Every Storage mutation crosses `OrganizerExecutor`. Impact, destination browsing, manifest
      creation, stale/invalid/denied admission and failed verification perform zero mutation and
      start no Scanner, Parser, Recognition, Metadata, Naming, Classification or Organize work.
- [ ] Same-Storage capability rules and cross-Storage Copy→verify→Delete-source semantics are
      enforced. A failed verification preserves the source; roots, traversal, aliases, symlinks,
      unsupported entries, stale manifests, conflicts and disabled/unavailable endpoints fail
      closed without silent fallback or overwrite.
- [ ] Durable media transfer rows, TaskItems, Result records and Operations projections preserve
      source/destination kind, pinned snapshot, independent per-item progress, checkpoints,
      known effects and action-oriented recovery. Pause/resume/cancel are offered only when
      advertised; uncertain effects are visible and never automatically replayed.
- [ ] Refresh, reconnect and revisit do not submit a second mutation. Fresh live listings
      reconcile only known successful effects, while failed, partial and uncertain siblings retain
      independent outcomes and safe next actions.
- [ ] Focused transfer, affected ResourceLibrary regression, T4 quality gates and MediaLibrary
      desktop/narrow browser journeys pass with actual totals, skips and unavailable gates. The
      checkpoint contains only this Task, no credentials or forbidden files, and no tests are
      deleted or weakened.

## Required Tests

Run from the repository root unless a `web/` prefix is shown. Use local fakes and temporary
Storage only; never use production services, credentials or user media.

- `python3 scripts/check_governance.py`
- Add and run focused MediaLibrary transfer tests for same/cross-Storage Copy/Move, exact Active
  endpoint authority, equal-ID isolation, overlap/alias rejection, conflicts, stale manifests,
  capability failures, verification failure source preservation, per-item partial/uncertain
  outcomes, durable attribution and Worker reconstruction/lifecycle.
- `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_transfers.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_transfers.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_direct_commands.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_operations_workspace.py'`
- `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'`
- `.venv/bin/python -m unittest discover -s tests`
- Add and run focused frontend API/model/dialog/page tests for media destination selection,
  manifest confirmation, retained input, no automatic replay, lifecycle controls and independent
  result reconciliation.
- `npm --prefix web run test -- --run`
- `npm --prefix web run test:e2e -- tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts tests/e2e/medialib-transfers.spec.ts`
  including desktop and supported narrow viewport success, denied, conflict, partial and recovery
  journeys.
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web run format:check`
- `npm --prefix web run build`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- Confirm the FFmpeg/FFprobe exclusion with the repository-available grep command.
- `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py`
- Inspect `git diff --check`, the complete Task Base..Head manifest, private files and both
  reference images. Preserve the pre-existing dirty Files image.

## Non-goals

- ResourceLibrary↔MediaLibrary transfers, MediaLibrary Organize/Scan/Preview, recognition,
  metadata, naming, classification, thumbnails, playback, Upload/Download or arbitrary binary,
  image or video editing.
- New Storage providers/capabilities, transfer Replace overwrite mode, universal rollback,
  automatic uncertain replay, unbounded recursion/global search or new directory-creation policy.
- Broad schema/configuration migration, identity-system changes, V1 cutover, shared shell redesign,
  unrelated ResourceLibrary behavior changes or changes to the A-owned Slice Contract/Roadmap.
- Controlled Slice screenshots, remaining RO-8 integration evidence and Slice Final.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
