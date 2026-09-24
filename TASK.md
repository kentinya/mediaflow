# Task 38.4 — 完成 MediaLibrary 有界 Copy/Move 与恢复

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.4
Parent Slice: 38
Status: READY FOR B REVIEW
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

Implementation checkpoint `d0470747c5767fea195a272cc4869057a7d42160` (`Task Base..Head`).

Python (domain / application / interface):

- `mediaflow/domain/direct_files.py` — `TransferManifest.library_kind` plus kind-scoped
  `TransferImpact.document()` identity keys.
- `mediaflow/domain/task_persistence.py` — documents the `media_`-prefixed transfer
  command.
- `mediaflow/application/direct_file_transfers.py` — kind-pinned admission/execution:
  kind-aware error identity, media-only `libraryKind` in the manifest digest payload,
  kind in the persisted authority with kind-checked reconstruction, media Task command,
  `media:`-namespaced durable item identity, kind-aware projection identity keys.
- `mediaflow/application/files_transfer_worker.py` — one Worker dispatches each claimed
  transfer by its own durable Task command; an incompatible kind returns the claim to
  the queue with readiness evidence instead of consuming it.
- `mediaflow/application/operations_lifecycle.py` — `is_files_transfer_task_command`
  makes both kinds' transfers equally resumable.
- `mediaflow/interfaces/service_api.py` — `direct_media_transfers` binding, media
  `transfer-impact` / `transfers` / `transfers/{taskId}` routes, media audit template,
  kind-routed Task resume.
- `mediaflow/final_cli.py` — the resident Worker composes both kind-pinned boundaries
  and reconstructs each pinned revision in its own kind.

Web:

- `web/src/entities/library/direct-files.ts` — kind-discriminated transfer models and
  strict kind-scoped normalizers.
- `web/src/shared/api/api-client.ts` — media transfer impact/projection/submission, and
  a kind parameter on the shared lifecycle control.
- `web/src/features/library/TransferDialog.tsx` — one shared dialog driven by `kind`
  (route, browse cache, destination list, labels).
- `web/src/features/library/MediaLibraryFilesPage.tsx` — Copy/Move entry points, media
  admission mutation, durable-projection following and terminal reconciliation.

Tests and fixtures:

- `tests/test_media_library_transfers.py` (new, 22 tests).
- `web/src/features/library/MediaLibraryTransfers.test.tsx` (new, 5 tests).
- `web/src/entities/library/direct-files.test.ts` (+3 kind-isolation tests).
- `web/src/features/library/MediaLibraryCommands.test.tsx` — the superseded "no
  Copy/Move entry point" assertion is replaced by this Task's bounded-transfer
  expectations.
- `web/tests/fake-server.mjs` — media transfer routes and session state.
- `web/tests/e2e/medialib-transfers.spec.ts` (new, 7 journeys).

### Implemented

- A MediaLibrary-scoped bounded Copy/Move journey built on the existing kind-pinned
  `DirectFileCommandService(library_kind=MEDIA)` rather than a second transfer state
  machine. Both endpoints resolve only from the exact Active MediaLibrary snapshot and
  its enabled Storages; client-supplied Storage IDs, host roots and raw paths are never
  authority.
- Equal-ID isolation at every layer: the kind travels in the opaque manifest digest,
  the persisted admission authority, the durable Task command (`media_files_transfer`),
  the namespaced `media:` item identity, the projection identity keys
  (`mediaLibraryId`/`destinationMediaLibraryId`) and the API routes. A media transfer
  Task can never be read, re-queued or executed as ResourceLibrary work — or the
  reverse.
- Media routes `/api/v1/media-libraries/{id}/files/transfer-impact`,
  `.../transfers` (POST 202) and `.../transfers/{taskId}` (GET) share one application
  behavior and the same permissions as Files; ResourceLibrary routes and response bytes
  are unchanged.
- Copy/Move bounds, safe relative paths, resolved-Storage self/ancestor overlap,
  no-overwrite default with `fail`/`skip`/`keep_both`, root protection, symlink and
  unsupported-entry refusal, stale-manifest refusal and disabled/unknown endpoint
  refusal all fail closed with zero mutation and start no analysis work.
- Same-Storage native capability semantics and the explicit cross-Storage
  Copy→verify→Delete-source sequence are preserved; a failed verification leaves the
  source byte-identical, and an uncertain effect is durable and never replayed.
- One resident Worker serves both kinds, selecting the boundary from the claimed
  Task's durable command; Operations resume dispatches by the same command, so
  pause/resume/cancel stay durable and per-item for media work too.
- Web: explicit destination MediaLibrary and bounded destination-directory browsing,
  exact impact preview, advertised conflict choice, one explicit submit, durable
  projection polling with backend-advertised lifecycle controls, retained correctable
  context after recoverable failures, and no resubmission on refresh or reconnect.

### Tests and Results

All commands run from the repository root unless a `web/` prefix is shown.

| Command | Result |
|---|---|
| `python3 scripts/check_governance.py` | PASS |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_transfers.py'` | PASS — 22 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_transfers.py'` | PASS — 94 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_direct_commands.py'` | PASS — 21 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_operations_workspace.py'` | PASS — 20 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'` | PASS — 13 tests |
| `.venv/bin/python -m unittest discover -s tests` | PASS — 1788 tests, 7 skipped |
| `npm --prefix web run test -- --run` | PASS — 599 tests in 43 files |
| `npm --prefix web run test:e2e -- tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts tests/e2e/medialib-transfers.spec.ts` | PASS — 31 tests, including 7 new media transfer journeys |
| `npm --prefix web run typecheck` | PASS |
| `npm --prefix web run lint` | PASS |
| `npm --prefix web run format:check` | PASS |
| `npm --prefix web run build` | PASS |
| `.venv/bin/ruff format --check .` | PASS — 314 files |
| `.venv/bin/ruff check .` | PASS |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | PASS |
| `.venv/bin/python -m pip check` | PASS — no broken requirements |
| `.venv/bin/mediaflow --config config/strategy.example.json config validate` | PASS |
| `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` | PASS |
| FFmpeg/FFprobe exclusion grep | PASS — only the documentation prohibition and the `test_container_deployment.py` Dockerfile assertion match; no dependency, import or pipeline use |
| `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py` | PASS — "Release-security smoke acceptance passed." |
| `git diff --check` | PASS — no whitespace or conflict errors |

Focused evidence highlights:

- `tests/test_media_library_transfers.py` covers Active-only endpoint resolution,
  disabled/unknown refusal, equal-ID authority isolation in both directions, cross-kind
  manifest refusal, the manifest digest separating the kinds by evidence, zero-mutation
  impact and denial (including traversal, root and missing-directory paths), no media
  pipeline work, same-Storage native Copy/Move with keep-both, genuine cross-Storage
  Copy→verify→Delete-source with all three compound checkpoints, failed-verification
  source preservation, conflict fail/skip without overwrite, independent per-item
  partial outcomes, uncertain-effect durability without replay, the API/RBAC surface,
  the ResourceLibrary compatibility check, Worker routing/reconstruction/kind refusal,
  durable pause/resume through the media projection, and in-flight mutation resolution
  without replay.
- `web/tests/e2e/medialib-transfers.spec.ts` proves the browser journey: Copy success
  with exactly one submission on the media routes only, Move with an explicit conflict
  choice, denied admission with retained correctable input, a partial result with
  per-item outcomes, no resubmission after reload/reconnect, read-only principal
  behaviour, and a supported narrow viewport.

### Decisions

- Extended the existing bounded transfer mechanism, matching the Task's stated intent,
  instead of introducing a second transfer state machine.
- Added `libraryKind` to the manifest digest payload **only for the media kind**. Every
  already-issued ResourceLibrary `manifestDigest` therefore keeps its exact value while
  the two kinds still carry deliberately different payload shapes and can never admit
  each other's transfer.
- The persisted authority always records the kind, and a missing value reads as
  ResourceLibrary, so pre-existing durable transfers remain executable and
  reconstructable.
- Kept one shared `TransferDialog` parameterized by `kind` rather than duplicating the
  journey; the ResourceLibrary page, routes and response bytes are untouched.
- Made `FilesTransferWorker` command-routed so a single resident Worker serves both
  kinds. A claimed transfer this Worker cannot lawfully execute is returned to the
  claimable queue with readiness evidence — never converged into a business failure and
  never executed by the wrong boundary.
- Replaced the single superseded 38.3 assertion ("no Copy/Move entry point in this
  Task") in `MediaLibraryCommands.test.tsx` with this Task's required behavior. That
  assertion encoded the previous Task's exclusion and is directly contradicted by this
  Task's Acceptance Criteria; no other test was deleted, skipped or weakened.

### Remaining In-Slice Work

Not part of this Task and not planned here: remaining RO-1..RO-4 and RO-8 evidence
beyond what already exists, the controlled Slice screenshots, and Slice-final
regression or closure preparation. Ordinary ResourceLibrary↔MediaLibrary cross-kind
transfers, transfer Replace mode, thumbnails/statistics and MediaLibrary
Organize/Scan remain deferred by the Contract.

### Risks / Deviations

- Deviating gate note (not a Task defect): `scripts/docker_release_security_smoke_test.py`
  failed twice before passing. The script renders a Compose topology that binds
  `$MEDIAFLOW_ENV_FILE`, and the required `TMPDIR=/root/mediaflow/.smoke-tmp` did not
  exist, so the first attempt left a stale rendered path and the second failed to mount
  `/tmp/.../deployment.env`. After `mkdir -p .smoke-tmp` the gate passed completely; the
  directory was removed again afterwards. No repository file was changed for this, and
  the smoke builds from `git archive HEAD`.
- Disclosed behavioural change: `MediaLibraryCommands.test.tsx` no longer asserts the
  absence of Copy/Move on the MediaLibrary page, because this Task's Acceptance
  Criteria require those commands to exist.
- `tests/test_direct_file_transfers.py` passes unchanged (94/94), including the shared
  admission-contract fixture comparison, confirming the ResourceLibrary transfer
  document bytes remain compatible.
- The pre-existing dirty `docs/pics/文件页.png` was left untouched and unstaged, as the
  Task requires. `web/test-results/` and `.smoke-tmp/` are ignored artifacts and are
  not part of the checkpoint.
- No unavailable gate: every command listed above actually ran and passed.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: d0470747c5767fea195a272cc4869057a7d42160
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
