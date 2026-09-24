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

Correction checkpoint for B's `FIX REQUIRED` review of
`8cfddad289d2883a17f915e96162ae9e52724140..d0470747c5767fea195a272cc4869057a7d42160`.
Fixing scope is exactly the two P1 blockers B listed; the Task ID, Task Base, Goal and Scope are
unchanged and the earlier checkpoint `d0470747c5767fea195a272cc4869057a7d42160` was not amended.

### Changed Files

Correction checkpoint (follows `d0470747c5767fea195a272cc4869057a7d42160`).

Python:

- `mediaflow/application/direct_file_transfers.py`
  - `_ResumeContext` now carries the resolved `source` library, so a continuation resolves the
    source endpoint once and uses exactly that object for the item acquisition and execution.
  - New `_started_item_library(item, *, mutated)` decodes the persisted durable identity
    (`split_library_identity`) and resolves only the configured ID against the pinned Active
    snapshot. A row of the other kind (or an unknown ID) fails closed as a `scope_changed`
    continuation stop instead of being resolved, claimed or replayed under the wrong authority.
  - `_resume_item_plan` uses that helper for its source lookup; the destination-refusal message no
    longer claims a specific kind's library type.
  - `requeue_transfer` now refuses every non-`PAUSED` durable state with the bounded
    `files_transfer_resume_running` / `resume_running` 409 reason (a live claim keeps its exact
    pre-existing message) instead of leaking the repository's internal `ValueError` as an
    unrelated 400.
- `mediaflow/application/operations_lifecycle.py`
  - `TaskExecutionContext.durable_continuation` records that a bounded transfer owns a durable
    continuation authority independent of its current state.
  - `task_lifecycle_document` distinguishes "the authority exists but this state offers nothing to
    continue" (queued/running/terminal) from "no durable continuation exists at all". A transfer
    Task therefore always describes its real continuation instead of presenting a false
    CLI-only refusal.
- `mediaflow/interfaces/service_api.py` — the accepted kind-routed transfer resume returns the
  durable transfer projection **plus** the same `action`/`task`/`lifecycle`/`durableOutcome`
  envelope every other accepted control returns.

Tests and frontend fixtures:

- `tests/test_media_library_transfers.py` (+3 tests, +2 extended assertions): real mid-directory
  pause/resume for Copy and Move through a gated provider, the other-kind refusal, and the accepted
  resume envelope plus stale/duplicate and read-only-denied outcomes.
- `web/src/shared/api/operations-api.test.ts` (+1 test): the real 202 resume document is an applied
  control for `mutateLifecycle`, not `malformed_response`.
- `web/src/features/operations/OperationsRouter.test.tsx` (+1 test): the Operations Task detail
  reports an accepted paused-transfer resume as `Control accepted`.
- `web/tests/e2e/medialib-transfers.spec.ts` (+1 journey) and `web/tests/fake-server.mjs`: a paused
  media transfer is revisited in Operations and resumed there.
- `TASK.md` — this report.

### Implemented

- **P1 (started MediaLibrary directory transfer cannot resume).** Root cause: the durable per-item
  identity is persisted as `media:<configured ID>` while the pinned Active configuration names the
  same MediaLibrary by its bare ID. `_continue_item` and `_resume_item_plan` passed the persisted
  value straight into `DirectFileCommandService.library(...)`, so the lookup failed as soon as a
  real item had begun and the whole continuation converged to `FAILED` while the item projection
  stayed `PAUSED`. Both lookups now decode the recorded kind first and resolve only the configured
  ID; the destination lookup is unchanged because the authority already stores the configured ID.
  A genuinely started Copy and a genuinely started Move now pause at a per-entry boundary and
  resume through the authenticated API, continuing only the remaining entries, keeping completed
  effects terminal, and (for Move) removing the emptied source tree only through the verified
  continuation.
- **P1 (Operations reports an accepted media transfer Resume as unapplied).** Root cause: the
  kind-routed resume branch returned only the transfer projection, while the Operations page calls
  `mutateLifecycle`, which requires `{task, lifecycle}`. The real client therefore returned
  `malformed_response` and rendered `Control was not applied` while the durable transfer was
  already `QUEUED`. The accepted branch now returns the transfer projection and the standard
  Task/lifecycle envelope under HTTP 202, and a bounded transfer's lifecycle projection truthfully
  names its own durable continuation authority in every state. The Operations revisit → Resume
  journey now reports an applied control with durable state `pending` and submits exactly once.
- Kind isolation, mutation boundaries, zero-mutation admission/denial and no-replay semantics are
  unchanged; the correction touched only the two continuation lookups and the resume response.

### Tests and Results

All commands run from the repository root unless a `web/` prefix is shown. `PASS` means the command
actually ran in this session at this checkpoint.

| Command | Result |
|---|---|
| `python3 scripts/check_governance.py` | PASS — `governance check: PASS` |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_transfers.py'` | PASS — 25 tests (was 22) |
| `.venv/bin/python -m unittest discover -s tests -p 'test_direct_file_transfers.py'` | PASS — 94 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_media_library_direct_commands.py'` | PASS — 21 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_operations_workspace.py'` | PASS — 20 tests |
| `.venv/bin/python -m unittest discover -s tests -p 'test_api_security.py'` | PASS — 13 tests |
| `.venv/bin/python -m unittest discover -s tests` | PASS — 1791 tests, 7 skipped |
| `npm --prefix web run test -- --run` | PASS — 601 tests in 43 files (was 599) |
| `npm --prefix web run test:e2e -- tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts tests/e2e/medialib-transfers.spec.ts` | PASS — 32 tests (was 31) |
| `npm --prefix web run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/library-files.spec.ts` | PASS — 54 tests (affected regression) |
| `npm --prefix web run typecheck` | PASS |
| `npm --prefix web run lint` | PASS |
| `npm --prefix web run format:check` | PASS |
| `npm --prefix web run build` | PASS |
| `.venv/bin/ruff format --check .` | PASS — 314 files |
| `.venv/bin/ruff check .` | PASS |
| `.venv/bin/python -m compileall -q mediaflow tests scripts` | PASS |
| `.venv/bin/python -m pip check` | PASS — no broken requirements |
| `.venv/bin/mediaflow --config config/strategy.example.json config validate` | PASS |
| `.venv/bin/mediaflow --config config/phase13.2.example.json config validate` | PASS |
| FFmpeg/FFprobe exclusion grep (`test -z "$(grep -rn -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml)"`) | PASS — no match |
| `TMPDIR=/root/mediaflow/.smoke-tmp .venv/bin/python scripts/docker_release_security_smoke_test.py` | PASS — "Release-security smoke acceptance passed." |
| `git diff --check` | PASS — no whitespace or conflict errors |

Re-running B's reproduction:

- B's P1-1 reproduction was first reproduced at `d0470747c5767fea195a272cc4869057a7d42160` with an
  independent probe (real SQLite/API/Worker and a `_GatedMediaStorage` that inherits
  `LocalStorage` and only gates the timing of one native copy/move): pause HTTP 200, item identity
  `media:movies`, resume HTTP 202 / QUEUED, final transfer `FAILED`, item projection `PAUSED`,
  destination containing only the first entry. After the fix the same probe ends `SUCCESS`,
  Task `completed`, item `success`, and every entry transferred for both `copy` and `move`.
- B's P1-2 was verified at the real HTTP boundary: the 202 body now contains
  `action`/`task`/`lifecycle`/`durableOutcome` alongside the media projection, and the real
  TypeScript `mutateLifecycle` consumes it as an applied control
  (`operations-api.test.ts` + `OperationsRouter.test.tsx` + the browser journey).

Focused new coverage:

- `test_a_started_media_copy_pauses_and_resumes_from_its_own_checkpoints` — a genuinely started
  Copy pauses mid-directory, resumes through `/api/v1/tasks/{id}/resume`, performs zero Storage
  work on the resume request itself, then completes with only the remaining entries transferred.
- `test_a_started_media_move_pauses_and_resumes_and_removes_only_after_copy` — the same for the
  destructive Move, including exactly-once removal of the emptied source tree.
- `test_a_started_item_of_the_other_kind_is_never_continued` — a bare ResourceLibrary identity in a
  media transfer's item row is an explicit investigation outcome, never a wrong-authority
  continuation.
- `test_operations_lifecycle_resumes_a_paused_media_transfer_through_its_own_kind` — extended with
  the accepted envelope, the stale/duplicate resume refusal, and the read-only denial.
- `web/src/shared/api/operations-api.test.ts`, `web/src/features/operations/OperationsRouter.test.tsx`
  and `web/tests/e2e/medialib-transfers.spec.ts` — the real 202 document shape through
  `mutateLifecycle`, the rendered Operations control, and the browser journey.

### Decisions

- Fixed the continuation by decoding the persisted kind at the lookup rather than by changing what
  is persisted. The `media:` namespace is the durable isolation evidence this Task's Acceptance
  Criteria require (equal IDs must never exchange work), so the defect belonged in the reader.
- Resolved the source endpoint once in `_resume_item_plan` and carried it in `_ResumeContext`
  instead of resolving it twice, so the acquisition and the execution provably use the same
  library object.
- A row whose recorded kind is not this service's kind stops as `scope_changed` with the
  fully-recorded `mutated` evidence rather than silently becoming a resource lookup.
- Kept the transfer-projection bytes on the accepted resume response (the Files workspace contract
  is unchanged) and added the Operations envelope alongside them, so both surfaces read one
  truthful document from one request.
- Extended the lifecycle projection's own vocabulary (`durable_continuation`) instead of leaving a
  false "no durable queued command reproduces it" refusal on a Task that really has one.
- Hardened the duplicate/live-claim refusal into a bounded 409 reason; the previous internal
  `ValueError` surfaced as a 400 with internal wording through the same resume path B asked to
  cover. `tests/test_direct_file_transfers.py` was left unchanged: its live-claim refusal assertion
  still matches because that exact message is preserved when a live claim really owns the row.

### Remaining In-Slice Work

Not part of this Task and not planned here: the remaining RO-1..RO-4 and RO-8 evidence beyond what
exists, the controlled Slice screenshots, and Slice-final regression or closure preparation.
Ordinary ResourceLibrary↔MediaLibrary cross-kind transfers, transfer Replace mode, thumbnails and
MediaLibrary Organize/Scan remain deferred by the Contract.

### Risks / Deviations

- No unavailable or skipped gate in this correction round: every command in the table above actually
  ran and passed at this checkpoint.
- No test was deleted, skipped or weakened. `tests/test_direct_file_transfers.py` (94/94) and
  `tests/test_operations_workspace.py` (20/20) pass unchanged, including their existing resume,
  live-claim refusal and CLI-resume-withheld assertions.
- The transfer-resume response now carries both the transfer projection keys and the
  `action`/`task`/`lifecycle`/`durableOutcome` keys. The ResourceLibrary compatibility assertions
  (`test_resource_library_transfer_journey_remains_compatible`,
  `web/tests/fixtures/files-transfer-admission.json`) are unchanged and pass; the admission (202
  `transfers`) document bytes are untouched.
- The pre-existing dirty `docs/pics/文件页.png` was left untouched and unstaged. `web/test-results/`
  and `.smoke-tmp/` are ignored artifacts and are not part of the checkpoint. `config/alist.json`
  remains ignored, untracked and unstaged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 516d62f27f943c1008a14fc6582ebd99d7ff32ed
```

## B Review Result

```text
Reviewed: 8cfddad289d2883a17f915e96162ae9e52724140..d0470747c5767fea195a272cc4869057a7d42160
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — An actually started MediaLibrary directory transfer cannot resume.**
  `mediaflow/application/direct_file_transfers.py:2308` (`_resume_item_plan`) and `:1779`
  (`_continue_item`) pass the persisted `item.resource_library_id` directly to
  `self._direct.library(...)`. This Task persists media items as `media:movies`, while the
  pinned configuration identifies that MediaLibrary as `movies`. The lookup therefore fails
  after a real item has begun. This breaks the Task's durable continuation criteria and Slice
  RO-6/RO-7 (supported pause/resume and kind-correct reconstruction).
  Evidence: ran `PYTHONPATH=/root/mediaflow .venv/bin/python
  /tmp/mediaflow-b-38-4-resume-probe.py` and the same command with argument `move` against
  this checkpoint. Both probes use the existing checked-Active fixture, real SQLite/API/Worker
  and `_GatedSource`, which inherits the production LocalStorage implementation and only gates
  the timing of a native copy/move; no capability is removed and no Task state is fabricated.
  Reproduction: create `Movies/show/{one,two,three}.mkv`; admit `movies` → `tv`; pause through
  `/api/v1/tasks/{id}/pause` while the first native operation is in progress; release it and
  observe a genuinely PAUSED item; resume through the API; run the Worker again. Observed:
  pause HTTP 200, item identity `media:movies`, resume HTTP 202 / QUEUED, final transfer FAILED,
  item projection still PAUSED, mutation count remains 1, destination contains only `one.mkv`.
  Fix direction: validate/decode the persisted kind and configured ID at every started-item
  continuation lookup, preserve the pinned MediaLibrary authority and completed checkpoints,
  and continue only the remaining entries. Add real mid-directory pause/resume coverage for
  Copy and Move; the current test that manually pauses an unstarted row does not exercise this
  path. Keep completed effects non-replayable and terminal/per-item projections truthful.

- **P1 — Operations reports an accepted media transfer Resume as an unapplied control.**
  `mediaflow/interfaces/service_api.py:6624` returns the media transfer projection with HTTP 202
  from the new kind-routed resume branch, while the existing Operations page calls
  `mutateLifecycle` (`web/src/shared/api/api-client.ts:1036`), which requires a `{task,
  lifecycle}` document. The transfer response has neither field, so the real client returns
  `malformed_response`; `TaskDetailPage.tsx` displays `Control was not applied` even though
  the transfer has already been queued. This affects the supported
  `/ui-v2/operations/tasks/{id}` revisit → Resume journey and violates the Task's Operations
  recovery/known-state criteria and Slice RO-6 / Required Surface for Operations lifecycle.
  Evidence: the same LocalStorage/API probe feeds the actual 202 resume response unchanged
  into the production `mutateLifecycle` function via
  `/tmp/mediaflow-b-38-4-client-probe.cjs`. Result:
  `{"ok":false,"status":202,"code":"malformed_response"}` while the durable transfer is QUEUED.
  The Node harness only transpiles the actual TypeScript and supplies the captured HTTP
  response; it does not invent a different server payload or weaken production capabilities.
  Fix direction: make Operations consume the successful transfer continuation response
  truthfully (or reconcile through the authoritative Task projection), refresh its state
  without resubmitting, and preserve both library kinds' existing dialog/API contracts. Cover
  Operations revisit → Resume with the real backend response shape, including accepted,
  denied/stale and uncertain outcomes.
