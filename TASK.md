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

- `tests/test_storage_page_local_save.py`: lifecycle publication/read-check sequence and concurrent stale-removal regressions.
- `web/src/features/storage/StorageManagementPage.tsx`: compare the displayed row's Active fence with current authority before confirmation, and send revision sequence for read checks.
- `web/src/features/storage/StorageManagementPage.test.tsx`: pre-confirmation stale-row and during-confirmation fence regressions, plus sequence/version read-check coverage.
- `web/src/shared/api/storage-management-api.test.ts`: typed lifecycle request and recovery regressions.
- `web/tests/fake-server.mjs`: configuration-only copy, enable/disable and removal behavior for browser lifecycle coverage.

### Implemented

- Copy preserves provider options and approved secret references under an explicit new identity; it never copies physical contents.
- Enable/disable publishes only a checked successor and rejects disabling Storage with enabled ResourceLibrary or MediaLibrary dependents.
- Removal rechecks the complete Active reference graph, preserves physical contents and historical snapshots, and publishes only after remaining configuration gates pass.
- All commands keep the previous Active and actionable context on stale, reference, validation, evidence, persistence or runtime failures.
- Correction loop: lifecycle API requests now match the typed contracts and fence on `revisionSequence`; removal keeps the authority captured before confirmation; Copy uses retained controlled input instead of transient prompts.
- Correction loop: unknown lifecycle outcomes now require explicit Active verification and do not claim that the prior Active survived or automatically replay a command.
- Correction loop: lifecycle actions now refuse to pair a stale displayed row with a newer authority, while removal during a concurrent change submits the originally reviewed fence and surfaces the backend conflict.
- Correction loop: the Web read-check caller uses `active.revisionSequence` when it differs from document `version`.

### Tests and Results

- PASS — `python3 -m py_compile mediaflow/application/configuration_objects.py mediaflow/interfaces/service_api.py`.
- PASS — `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_configuration_management tests.test_storage_setup_check tests.test_v2_storage_operations tests.test_storage_page_local_save` (126 tests, 0 failures).
- PASS — `cd web && npm run typecheck`.
- PASS — `cd web && npm test -- --run src/features/storage/StorageManagementPage.test.tsx src/shared/api/storage-management-api.test.ts` (46 tests, 0 failures; jsdom reports existing `scrollTo` notices).
- PASS — `python3 scripts/check_governance.py`; `git diff --check`.
- PASS — `.venv/bin/python -m unittest discover -s tests` (1,836 tests, 7 skips for existing external/endurance profiles; existing SQLite ResourceWarnings only).
- PASS — `cd web && npm test -- --run` (698 tests, 47 files; existing jsdom `scrollTo` notices only).
- PASS — `cd web && npm run test:e2e -- --grep 'Storage management'` (22 Chromium tests).
- PASS — `cd web && npm run lint && npm run typecheck && npm run format:check && npm run build` (existing Vite bundle-size advisory only).
- PASS — `.venv/bin/ruff format --check . && .venv/bin/ruff check .`; `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-3-validation` (release-security smoke acceptance passed).

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
Head SHA: bd80736c9be66f4d38679a7e340830d91d8e6be2
```

## B Review Validation

Review round: 2 (first Developer correction). Reviewed implementation checkpoint:
`e887987cd954d3da5d07563cb0180ba4c98d02e5`; repository HEAD:
`2514fc5503043f9cc9a7f7a4150a3690a0b06724`. The later commit changes only `TASK.md`.
Task Base remains `6bb70ebcf7a3f718ce3bd88b5e91e474d62a00a9`.

B inspected both the cumulative Task diff and the correction diff. The copy request fields and
lifecycle sequence comparison are corrected. A real Local API reproduction successfully publishes
copy, disable, enable and removal in sequence. A real browser reproduction confirms duplicate-copy
input remains correctable, the corrected copy succeeds, and a committed disable with its response
lost offers explicit verification that displays the current enabled state. These prior findings
are not retained in the blocker list. The remaining stale-decision case and the newly introduced
read-check regression below are reachable with the actual API, SQLite managed configuration,
real Local adapters, temporary roots and the current built V2 page. No production capability was
removed or weakened to manufacture either reproduction.

Independent B validation:

- `.venv/bin/python -m unittest discover -s tests`: PASS, 1,834 tests, 7 skips,
  312.186 seconds; existing external/endurance profiles remain unavailable.
- `cd web && npm test -- --run`: PASS, 694 tests across 47 files.
- `cd web && npm run test:e2e -- --grep 'Storage management'`: PASS, 22 Chromium tests.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build`:
  PASS; the existing bundle-size advisory remains non-fatal.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .`: PASS, 316 files formatted.
  `.venv/bin/python -m compileall -q mediaflow tests scripts`: PASS.
- `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:b39-3-r2-review`:
  PASS, release-security smoke acceptance passed against the clean committed candidate.
- Governance and whitespace checks pass. The cumulative checkpoint changes only `TASK.md` and
  the four in-scope production files. No tests or assertions were removed, weakened or skipped;
  however, no lifecycle regression tests were added either. `config/alist.json` remains ignored
  and untracked. The Slice Contract, reference image and pre-existing unrelated image changes
  remain untouched. The production diff adds no Storage mutation or FFmpeg/FFprobe dependency.

Evidence logs: `/tmp/mediaflow-b393-r2-{api,stale,recovery,readcheck,python,web,e2e,docker}.log`.
Reproduction commands:

- `PYTHONPATH=. .venv/bin/python /tmp/mediaflow-b393-r2-api.py`.
- Start `PYTHONPATH=. .venv/bin/python /tmp/mediaflow-b393-r2-server.py`, then run
  `node /tmp/mediaflow-b393-r2-stale.mjs`.
- Start a fresh `PYTHONPATH=. .venv/bin/python /tmp/mediaflow-b393-r2b-server.py`, then run
  `node /tmp/mediaflow-b393-r2-recovery.mjs` followed by
  `node /tmp/mediaflow-b393-r2-readcheck.mjs`.

B did not run Slice Final: Task acceptance and Slice RO-4/RO-5/RO-7 remain unmet.

## B Review Result

```text
Reviewed: 6bb70ebcf7a3f718ce3bd88b5e91e474d62a00a9..e887987cd954d3da5d07563cb0180ba4c98d02e5
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Removal still combines an old displayed object with newer authority
  (Acceptance Criterion 4; Slice RO-4 and Safety Invariant 8).**
  `StorageManagementPage.tsx:runLifecycleAction` now fetches authority before confirmation,
  but continues to use `item` from the previously loaded inventory without checking that they
  describe the same Active. In the real browser reproduction, load the `Spare Original` row,
  use another authorized API request to edit it to `Spare Changed After Decision` (HTTP 200),
  then click removal on the old row. The confirmation still names `Spare Original`; accepting
  it removes the changed configuration (DELETE HTTP 200; subsequent lookup HTTP 404).
  Moving the fetch earlier only closes the during-dialog case. Bind the displayed object and
  operator decision to the same exact authority: either submit the inventory's original fence,
  or refresh the selected object's actual decision context before presenting confirmation.
  Reject stale context and require review; never silently pair an old row with a newer fence.
  Add browser/API regression coverage for edits both before opening and during confirmation.
- **P1 — The correction breaks read checks after normal lifecycle publication
  (Acceptance Criteria 1/6/7; Slice RO-5/RO-7).**
  `_storage_check_operator_document` now compares `expectedVersion` with `revisionSequence`,
  but `StorageManagementPage.tsx:runCheck` still submits `inventory.active.version` and the
  inventory exposes both values distinctly. The real Local API sequence copy → disable →
  enable → remove reaches sequence 5 / version 2. The exact current Web request returns HTTP
  409 `configuration_version_conflict`; a request using sequence 5 succeeds (HTTP 200), proving
  the Storage and read capability are available. The real built page also reproduces HTTP 409
  via View → `运行只读检查` after copy/disable, incorrectly telling the operator Active changed.
  Reloading cannot reconcile this protocol mismatch. Restore one consistent version contract
  for the existing read-check API and Web caller while preserving stale rejection. Add a
  real publication → inventory → Web read-check regression where sequence differs from version,
  alongside the lifecycle coverage already required by this Task. No lifecycle-specific tests
  were added in either checkpoint; the existing 1,834/694/22 tests passing does not satisfy that
  explicit Required Tests obligation. Complete the assigned lifecycle tests and rerun T4 gates
  for the corrected checkpoint, recording actual totals, skips and unavailable gates.
