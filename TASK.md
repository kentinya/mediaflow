# Task 39.3 — Checked Storage copy, enable/disable and configuration removal

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 39.3
Parent Slice: 39
Status: FIX REQUIRED
Task Base: 6bb70ebcf7a3f718ce3bd88b5e91e474d62a00a9
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice RO-4 through matching application/API and `/ui-v2/storage` actions: copy a Storage
configuration under an explicit new identity, enable or disable it safely, or remove an unreferenced
configuration while leaving physical contents and historical snapshots intact. Every successful
operation publishes one checked immutable Active successor. Finish the required row-action surface
under RO-1 and preserve RO-2/RO-3/RO-5/RO-6/RO-7 throughout these journeys.

## Why This Task Exists

The reviewed inventory, detail, read-check and typed Add/Edit journeys already use the managed
configuration authority. The current table has View/Edit but no More menu, and the existing
`copy_storage`, `set_storage_enabled` and generic object removal helpers only edit Drafts. They do
not deliver RO-4's page-local publication, removal confirmation, refreshed Active list or recovery.
Copy, state changes and removal form the remaining coherent Storage lifecycle unit; they share the
same selection authority, reference explanation and checked publication boundary. Do not split them
into separate Tasks for menus, fields, individual assertions or error text.

Planning basis: Task 39.2 passed B review at
`764a56eb74e2eb311fd9e685699c8cad4e24f3af` (Task Base
`2d012c07f049fb2e0831a39b721b1aa465e3888e`). Its original multi-Storage recovery failure was
reproduced as fixed with real Local adapters, including successful explicit continuation.
RO-2, RO-3 and RO-5 are complete; RO-1 still needs the More menu; RO-4 is incomplete;
RO-6/RO-7 are verified for existing surfaces and still need the RO-4 journeys. Therefore:
`Decision: PASS; Slice Required Outcomes all satisfied: NO; Next: NEXT TASK`.
The new Task Base is the actual current committed HEAD, including the correction report; it does
not move the previous Task Base or Slice Base. This is the third coherent Task in Slice 39.

## Implementation Scope

Application / existing persistence authority → typed API → V2 row actions and recovery → Tests.
Reuse existing domain validation, configuration repositories, reference evidence, read-only checks,
offline strategy/destination checks and runtime binding; no second configuration authority.

- Add working, accessible `更多` actions after `查看 / 编辑` in each row. Offer applicable copy,
  enable/disable, read-check and configuration removal using backend-authoritative permissions.
  Reuse the existing detail/read-check behavior. Keep the shared search, provider filters, bounded
  inventory, separate enabled/check state and four-step Add/Edit drawer intact.
- Copy opens a focused typed journey from one exact Active source. Require an explicit new ID and
  name and show what configuration will be copied, including enabled/read-only intent. Retain all
  supported provider options and approved secret references without secret values. The source and
  other objects remain unchanged. Reusing the Add drawer is appropriate; copy must still retain
  source identity for concurrency and audit. Validation, checks and atomic activation happen on
  explicit Save, never on menu opening or form navigation.
- Enable/disable is a bounded command on the selected Storage, with an explicit intended state.
  Preserve every other option and object. Enabling obtains applicable checks for the enabled
  Storage. Disabling rejects any enabled ResourceLibrary/MediaLibrary binding that would become
  invalid, identifies affected dependents and offers repoint/re-enable recovery. Keep full graph
  validation; do not rewrite references or silently disable libraries.
- Removal opens one explicit confirmation naming the selected Storage and explaining that only its
  configuration is removed and physical files remain. Show bounded current ResourceLibrary and
  MediaLibrary impact, including disabled dependents and honest truncation. Backend rechecks the
  complete reference graph, not just displayed entries, and rejects every remaining reference.
  Unreferenced enabled or disabled Storage can be removed without first making its own root or
  credentials available. Do not require a check against the removed Storage merely to remove it.
- Each command binds to the exact Active authority used for the operator's decision, rechecks
  management/activation permissions, composes one complete successor, validates all dependencies,
  obtains applicable exact-successor read-only Storage evidence and offline strategy/destination
  evidence, prepares runtime binding, and atomically checked-activates. Removal checks the
  remaining configuration. Persist bounded secret-free actor/action/before/after/result evidence;
  report success only after the successor is actual runtime Active.
- Refresh inventory, counts, references and selected detail from resulting Active truth after
  success. Failed admission preserves previous Active, physical contents and correctable copy
  input or removal context. Explain the actual affected object/dependency, cause, durable state
  and next action. Stale decisions require refreshing and reviewing current context; unknown
  outcomes require explicit Active-state verification before another manual attempt. Never
  automatically replay a configuration command or infer success from a local row removal.
- Preserve V1/general Configuration, Storage Browser, Files/MediaLibrary, existing Add/Edit,
  diagnostics, adapters and OrganizerExecutor. Freeze the A-owned Contract/Roadmap, committed
  `docs/pics/储存管理.png`, unrelated `docs/pics/` changes and private configuration.

## Acceptance Criteria

- [ ] An authenticated authorized operator reaches working Copy, Enable/Disable, read-check and
      configuration removal through the accessible `更多` menu at `/ui-v2/storage`. View/Edit/More
      retain their required order. Menus and dialogs support keyboard, Escape, reachable narrow
      layouts and focus return; opening/cancelling them never saves or mutates Storage. Normal
      entry/reload/reconnect leaves the Add/Edit drawer closed.
- [ ] Copy accepts a valid explicit new ID/name, preserves supported provider settings and approved
      references, never exposes credential values and never copies media. Source configuration is
      unchanged. Duplicate/invalid identity, stale source/Active, unavailable evidence and denied
      authority fail with retained input and actionable recovery. All six supported provider types
      retain their distinct typed configuration semantics.
- [ ] Enable/disable changes only the selected object's intended state via checked activation.
      An enabled library cannot remain bound to a disabled Storage; failures identify the blocking
      references and preserve the previous Active. A successful enabled or disabled state is
      immediately reflected in Active inventory and detail, separately from connection health.
- [ ] Removal uses one explicit configuration-only confirmation and exact Active fencing. Backend
      rejects every ResourceLibrary/MediaLibrary reference, including disabled dependents and
      references outside a truncated display. Stale/concurrent decisions cannot remove a newly
      referenced or changed object. No cascade or automatic reference rewrite occurs.
- [ ] Removing an unreferenced enabled or disabled Storage succeeds through complete checked
      successor publication, even when that removed Storage's root is unavailable, provided the
      remaining configuration passes its applicable gates. The refreshed Active list/counts omit
      the removed entry only after publication. Historical snapshots, other configuration objects,
      admitted work's snapshot identity and all physical contents remain intact.
- [ ] Copy/state-change/removal share application behavior across API/Web and retain full graph
      validation, exact evidence, runtime preparation, RBAC, concurrency and secret-free audit.
      Validation/evidence/persistence/runtime failures retain prior Active and correctable context.
      Unknown outcomes never auto-replay; successful verification shows current truth before any
      new explicit action. No command starts a media Task, scan, live Metadata request or Storage
      mutation, and no read check implies write capability.
- [ ] Existing routes and the accepted inventory/Add/Edit/read-check journeys remain compatible.
      Assigned T4 checks pass with truthful counts/skips/unavailable evidence; the checkpoint
      contains only this Task and leaves the Contract and unrelated/private files untouched.

## Required Tests

Use temporary roots, real Local adapters where relevant, fake/local remote services and synthetic
secret references. Never use production SMB/OpenList/S3/TMDB, credentials or user media. Record
exact commands, totals, skips and unavailable external gates.

- `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_configuration_management tests.test_storage_setup_check tests.test_v2_storage_operations tests.test_storage_page_local_save` plus the new focused lifecycle-command tests. Cover copy/provider option preservation and secrets; successful enabled/disabled state changes; enabled-dependent disable rejection; all-reference removal blocking including disabled/truncated dependents; and exact Active concurrency across all commands.
- Prove unreferenced removal with a real unavailable Local root without touching its contents,
  successful checked runtime publication, unchanged historical snapshots, and failures at graph,
  Storage/strategy/destination evidence, persistence and runtime preparation boundaries. Include
  an unrelated Storage check failure that identifies the actual dependency, correction and an
  explicit successful continuation. Prove zero Storage mutation and no media-work admission.
- `.venv/bin/python -m unittest discover -s tests` for the T4 full Python regression.
- `cd web && npm test -- --run` plus focused entity/API/component tests for typed commands,
  permission states, menu/focus behavior, copy input, reference explanations, confirmation,
  refreshed list/counts, known failures and unknown-outcome verification without replay.
- `cd web && npm run test:e2e -- --grep 'Storage management'`: authenticated copy, enable/disable,
  referenced removal including disabled dependents, successful configuration-only removal,
  stale/failed publication and unknown-outcome recovery, plus retained Add/Edit/read-check/search
  behavior. Capture controlled `1536 x 1024` drawer-open/closed and More/removal evidence; cover
  narrow layout, keyboard and focus. Use the unchanged reference with the no-notes override.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .` and
  `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- `python3 scripts/check_governance.py`, `git diff --check`, checkpoint manifest/private-file and
  secret-output audit, and FFmpeg/FFprobe exclusion audit.
- `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-3-validation`
  against the exact committed candidate for the authenticated API/Web composition. If external
  infrastructure is unavailable, report the exact failure and which validation did not run.
  Assess additional migration/packaging gates from the actual diff; do not claim unnecessary or
  unavailable gates passed.

## Non-goals

- Work beyond Slice 39 or any change to its Base, Required Outcomes, Required Surfaces or Safety
  Invariants; declaring the Slice complete belongs to A after B's closure preparation.
- Physical file copy/move/delete, Storage root migration, write probes, new adapters/providers,
  media-processing work, Storage notes, arbitrary host browsing or secret-value entry.
- General Configuration redesign, bulk multi-object editing, automatic reference rewrites,
  rewriting historical snapshots, new identity/session systems or automatic uncertain replay.
- Optional polish, unrelated refactors, per-field/test micro-Tasks and changes to reference images
  or pre-existing unrelated/private files.

## Developer Completion Report

### Changed Files

- `web/src/features/storage/StorageManagementPage.tsx`: structured lifecycle dependency/state recovery feedback and explicit stale-copy review state preserving entered ID/name.
- `web/src/features/storage/StorageManagementPage.test.tsx`: dependency failure and retained stale-copy review regressions.
- `web/tests/e2e/storage-management.spec.ts`: real browser dependency-failure, stale-copy review and bounded-page exact-ID recovery journeys.

### Implemented

- Copy preserves provider options and approved secret references under an explicit new identity; it never copies physical contents.
- Enable/disable publishes only a checked successor and rejects disabling Storage with enabled ResourceLibrary or MediaLibrary dependents.
- Removal rechecks the complete Active reference graph, preserves physical contents and historical snapshots, and publishes only after remaining configuration gates pass.
- All commands keep the previous Active and actionable context on stale, reference, validation, evidence, persistence or runtime failures.
- Correction loop: lifecycle API requests now match the typed contracts and fence on `revisionSequence`; removal keeps the authority captured before confirmation; Copy uses retained controlled input instead of transient prompts.
- Correction loop: unknown lifecycle outcomes now require explicit Active verification and do not claim that the prior Active survived or automatically replay a command.
- Correction loop: lifecycle actions now refuse to pair a stale displayed row with a newer authority, while removal during a concurrent change submits the originally reviewed fence and surfaces the backend conflict.
- Correction loop: the Web read-check caller uses `active.revisionSequence` when it differs from document `version`.
- Correction loop: lifecycle failures now preserve bounded affected Storage, failure category, candidate state and durable Active state, with page-appropriate recovery guidance.
- Correction loop: stale Copy disables submission until the operator explicitly refreshes and reviews the current source authority; entered new ID/name remain unchanged and no command is replayed automatically.
- Correction loop: the browser fake now validates read checks against `revisionSequence`, matching the production protocol.
- Correction loop: stale Copy review now resolves the selected source through the exact `/edit` projection by stable ID, so a valid source outside the first bounded inventory page is not mistaken for deletion.

### Tests and Results

- PASS — `python3 -m py_compile mediaflow/application/configuration_objects.py mediaflow/interfaces/service_api.py`.
- PASS — `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_configuration_management tests.test_storage_setup_check tests.test_v2_storage_operations tests.test_storage_page_local_save` (126 tests, 0 failures).
- PASS — `cd web && npm run typecheck`.
- PASS — `cd web && npm test -- --run src/features/storage/StorageManagementPage.test.tsx src/shared/api/storage-management-api.test.ts` (46 tests, 0 failures; jsdom reports existing `scrollTo` notices).
- PASS — `python3 scripts/check_governance.py`; `git diff --check`.
- PASS — `.venv/bin/python -m unittest discover -s tests` (1,836 tests, 7 skips for existing external/endurance profiles; existing SQLite ResourceWarnings only).
- PASS — `cd web && npm test -- --run` (701 tests, 47 files; existing jsdom `scrollTo` notices only).
- PASS — `cd web && npm run test:e2e -- --grep 'Storage management'` (24 Chromium tests).
- PASS — `cd web && npm run lint && npm run typecheck && npm run format:check && npm run build` (existing Vite bundle-size advisory only).
- PASS — `.venv/bin/ruff format --check . && .venv/bin/ruff check .`; `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-3-r4-validation` against the exact committed candidate (release-security smoke acceptance passed).

### Decisions

- Reused the existing checked successor/runtime-binding authority rather than exposing Draft-only generic object mutation.
- Removal does not require a read check against the removed Storage; only the remaining configuration is admitted.
- Lifecycle commands use the established Active `revisionSequence` as the optimistic version, while retaining revision ID and digest fencing.

### Remaining In-Slice Work

- No known remaining implementation work from the current B blocker list; B review and any further Slice work remain outside this Developer report.

### Risks / Deviations

- Production SMB/OpenList/S3/TMDB acceptance was not run; no production credentials or external provider was available or required for this correction.
- Existing SQLite ResourceWarnings, jsdom `scrollTo` notices and the Vite bundle-size advisory remain non-fatal.
- Existing unrelated `TASK.md` and `docs/pics/` worktree changes were preserved and are not part of the implementation commit.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: ee1ae01d0b426dfe50a704bfb1e97d1b42e8c028
```

## B Review Validation

Review round: 4 (third correction checkpoint). Reviewed implementation:
`124a6f74f1b4f92eeda487b7bbe500e25d0f16cd`; repository HEAD:
`c277057eb5c11fef8092979d37958879454a216a`. The subsequent commit changes only `TASK.md`.
Task Base remains `6bb70ebcf7a3f718ce3bd88b5e91e474d62a00a9`.

B inspected the cumulative Task and correction diffs. The prior dependency message now names
`media-target`, its failure category and durable state; restoring that real Local target root
allows the retained copy submission to succeed. With a normal three-Storage inventory, stale
Copy now retains ID/name, explicitly refreshes the source, displays its changed name and succeeds
on a new explicit Save. Both paths were reproduced with the built Web, real `MediaFlowApi`, SQLite
configuration and real Local adapters. They are not retained as blockers.

The remaining reproduction uses a valid 108-Storage configuration, with 105 disabled Local
Storage entries and the three normal source/target/spare entries. The existing bounded inventory
returns 100 entries and explicitly reports `truncated: true`, `hasMore: true`. The operator finds
`spare` through the supported top-bar search. No adapter, permission, API or runtime capability is
hidden or replaced; all roots and credentials belong to the temporary synthetic review fixture.

### Whole-task complexity reassessment

This fourth review follows three correction checkpoints, so B reassessed the approach as a whole.
The lifecycle goal remains one appropriately bounded Task; there is no need to expand the Slice,
add a new Task, relax concurrency or introduce a new configuration abstraction. The recurring
integration problem is reconstructing one selected object's authority from separate generic list
and authority reads. Prefer the existing exact-ID Storage projection with its immutable Active
identity for copy review, following the established Add/Edit pattern. A paginated inventory is a
discovery surface and cannot establish that a specific selected object was deleted. Simplifying
this data access is sufficient for the remaining fix; a broad refactor is not required.

### Independent validation

- `.venv/bin/python -m unittest discover -s tests`: PASS, 1,836 tests, 7 skips,
  331.089 seconds; existing external/endurance profiles remain unavailable.
- `cd web && npm test -- --run`: PASS, 700 tests across 47 files.
- `cd web && npm run test:e2e -- --grep 'Storage management'` against the rebuilt candidate:
  PASS, 23 Chromium tests. The previous three read-check fixture failures are corrected.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build`:
  PASS; existing bundle-size advisory only.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .`: PASS, 316 files formatted.
  `.venv/bin/python -m compileall -q mediaflow tests scripts`: PASS.
- `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:b39-3-r4-review`:
  PASS, release-security smoke acceptance passed against the clean committed candidate.
- Governance and whitespace checks pass. No tests/assertions were removed or weakened and no skips
  were added. The cumulative manifest contains only this Task's production, test and report files.
  `config/alist.json` remains ignored and untracked. Slice Contract, reference image and unrelated
  image changes remain untouched. No Storage mutation or FFmpeg/FFprobe dependency was added.

Logs: `/tmp/mediaflow-b393-r4-{corrections,bounded,python,web,e2e,docker}.log`.
Reproduction commands for the corrected ordinary flow:
`PYTHONPATH=. .venv/bin/python /tmp/mediaflow-b393-r4-server.py`, followed by
`node /tmp/mediaflow-b393-r4-corrections.mjs` on a fresh temporary instance.
For the remaining defect, start
`PYTHONPATH=. .venv/bin/python /tmp/mediaflow-b393-r4-bounded-server.py`, then run
`node /tmp/mediaflow-b393-r4-bounded.mjs`.
Browser evidence: `/tmp/mediaflow-b393-r4-bounded.png`.

B did not run Slice Final: the supported bounded-inventory Copy recovery under RO-2/RO-4/RO-6
and Task acceptance remains incomplete.

## B Review Result

```text
Reviewed: 6bb70ebcf7a3f718ce3bd88b5e91e474d62a00a9..124a6f74f1b4f92eeda487b7bbe500e25d0f16cd
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Copy review treats absence from the first inventory page as deletion
  (Task Acceptance Criteria 2/6; Slice RO-2/RO-4/RO-6).**
  `StorageManagementPage.tsx:reviewCopy` calls unfiltered `fetchStorageInventory(token)` and
  searches only `current.items`. In the current supported 108-Storage configuration, the operator
  searches for `spare`, opens Copy and enters a new ID/name. Another authorized edit succeeds
  (HTTP 200), so Copy correctly rejects the old authority (HTTP 409). Clicking
  `刷新并审核复制源` then fetches the first 100 of 108 entries, with `truncated=true` and
  `hasMore=true`; `spare` is outside that page. The UI incorrectly says
  `当前复制源已不在 Active 配置中` and keeps Save disabled. A simultaneous exact-ID GET
  `/api/v1/storages/spare/edit` returns HTTP 200 with the current name `Changed Spare`.
  Thus an operator who legitimately found the source through search cannot finish the promised
  retained-input recovery, even though the source still exists. Read the selected source by its
  stable ID using the existing exact-object projection/authority path, distinguish actual absence
  from bounded-list omission, retain the proposed ID/name and show the current source for review
  before a new explicit Save. Add the supported beyond-first-page search → stale Copy → explicit
  review → successful submission regression and rerun the assigned T4 checks against the corrected
  checkpoint. Keep Task ID/Base/Goal/Scope unchanged.
