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

- `mediaflow/application/configuration_objects.py`: checked Active-bound Storage copy, state-change and configuration-only removal commands with full successor validation and reference protection.
- `mediaflow/interfaces/service_api.py`: typed Storage lifecycle routes with RBAC, exact Active fencing, runtime preparation and publication.
- `web/src/shared/api/api-client.ts`: typed copy, enable/disable and removal clients.
- `web/src/features/storage/StorageManagementPage.tsx`: accessible row-local More menu and recovery-aware lifecycle actions.

### Implemented

- Copy preserves provider options and approved secret references under an explicit new identity; it never copies physical contents.
- Enable/disable publishes only a checked successor and rejects disabling Storage with enabled ResourceLibrary or MediaLibrary dependents.
- Removal rechecks the complete Active reference graph, preserves physical contents and historical snapshots, and publishes only after remaining configuration gates pass.
- All commands keep the previous Active and actionable context on stale, reference, validation, evidence, persistence or runtime failures.
- Correction loop: lifecycle API requests now match the typed contracts and fence on `revisionSequence`; removal keeps the authority captured before confirmation; Copy uses retained controlled input instead of transient prompts.
- Correction loop: unknown lifecycle outcomes now require explicit Active verification and do not claim that the prior Active survived or automatically replay a command.

### Tests and Results

- PASS — `python3 -m py_compile mediaflow/application/configuration_objects.py mediaflow/interfaces/service_api.py`.
- PASS — `.venv/bin/python -m unittest tests.test_configuration_objects tests.test_storage_configuration_management tests.test_storage_setup_check tests.test_v2_storage_operations tests.test_storage_page_local_save` (126 tests, 0 failures).
- PASS — `cd web && npm run typecheck`.
- PASS — `cd web && npm test -- --run src/features/storage/StorageManagementPage.test.tsx src/shared/api/storage-management-api.test.ts` (42 tests, 0 failures; jsdom reports existing `scrollTo` notices).
- PASS — `python3 scripts/check_governance.py`; `git diff --check`.
- PASS — `.venv/bin/python -m unittest discover -s tests` (1,834 tests, 7 skips for existing external/endurance profiles).
- PASS — `cd web && npm test -- --run` (694 tests, 47 files).
- PASS — `cd web && npm run test:e2e -- --grep 'Storage management'` (22 Chromium tests).
- PASS — `cd web && npm run lint && npm run typecheck && npm run format:check && npm run build`.
- PASS — `.venv/bin/ruff format --check . && .venv/bin/ruff check .`; `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-3-validation` (release-security smoke acceptance passed).

### Decisions

- Reused the existing checked successor/runtime-binding authority rather than exposing Draft-only generic object mutation.
- Removal does not require a read check against the removed Storage; only the remaining configuration is admitted.
- Lifecycle commands use the established Active `revisionSequence` as the optimistic version, while retaining revision ID and digest fencing.

### Remaining In-Slice Work

- B review may require broader lifecycle-specific API/Web and full T4 regression coverage.

### Risks / Deviations

- Production SMB/OpenList/S3/TMDB acceptance was not run; no production credentials or external provider was available or required for this correction.
- Existing SQLite ResourceWarnings, jsdom `scrollTo` notices and the Vite bundle-size advisory remain non-fatal.
- Existing unrelated `TASK.md` and `docs/pics/` worktree changes were preserved and are not part of the implementation commit.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: e887987cd954d3da5d07563cb0180ba4c98d02e5
```

## B Review Validation

Review round: 1. The explicit implementation checkpoint is
`a5f01937f8a8d1b19d2e19e708b55b8d0cc70b72`; repository HEAD is
`8a16fad10c2bae4b6150b8744c8fbf2361053b04`. The subsequent three commits change only
`TASK.md`. The implementation diff contains four production files and no added or changed tests.
Task ID, Task Base, Goal and Implementation Scope remain unchanged.

B reproduced the failures below using the current application/API, SQLite managed configuration,
real Local adapters and temporary roots, then the actual built V2 page served by `MediaFlowApi`.
The browser response-loss test lets the real server commit before dropping its response; it does
not hide or remove a production adapter capability. All credentials used by these local probes
are synthetic.

Reproduction artifacts in this review workspace:

- `PYTHONPATH=. .venv/bin/python /tmp/mediaflow-b393-api-probe.py`;
  output: `/tmp/mediaflow-b393-api-probe.log`.
- Temporary real API server: `PYTHONPATH=. .venv/bin/python /tmp/mediaflow-b393-server.py`.
  Start a fresh instance for each of the stale-decision and response-loss scenarios.
  `node /tmp/mediaflow-b393-ui-stale.mjs` and
  `node /tmp/mediaflow-b393-ui-unknown.mjs`; outputs:
  `/tmp/mediaflow-b393-ui-stale.log` and `/tmp/mediaflow-b393-ui-unknown.log`.
- `node /tmp/mediaflow-b393-ui-copy.mjs` on the response-loss scenario's instance;
  output: `/tmp/mediaflow-b393-ui-copy.log`.
- Browser evidence: `/tmp/mediaflow-b393-stale-removal.png` and
  `/tmp/mediaflow-b393-unknown-outcome.png`.

B ran `cd web && npm run build` successfully. B's `.venv/bin/ruff check .` reports
15 errors in the two changed Python files; `.venv/bin/ruff format --check .` reports those
two files unformatted; `cd web && npm run format:check` reports the two changed Web files
unformatted. The reported 126 Python / 42 Web tests are Developer results, not independently
rerun full-regression results. The assigned new lifecycle tests, full Python/Web regression,
Storage management E2E and Docker security smoke are absent from this checkpoint's evidence.
B did not run Slice Final or claim those gates passed.

## B Review Result

```text
Reviewed: 6bb70ebcf7a3f718ce3bd88b5e91e474d62a00a9..a5f01937f8a8d1b19d2e19e708b55b8d0cc70b72
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Lifecycle request and Active-version contracts break normal commands
  (Acceptance Criteria 2/3/5/6/7; Slice RO-4/RO-7).**
  `api-client.ts` sends `storageId` in the copy body, while `service_api.py` rejects that extra
  field: the exact browser request returns HTTP 400 `invalid_request`, so Web Copy cannot
  succeed. Independently, `_require_storage_command_active` compares `expectedVersion` against
  `active.version`, while the existing authority/form contract supplies `revisionSequence`.
  The real Local API probe performs a successful copy with the accepted body and a normal Edit,
  reaching sequence 3 / version 2. Fresh authority then yields HTTP 409 `storage_copy_stale`,
  `storage_disable_stale` and `storage_remove_stale` for otherwise valid actions, including an
  unreferenced selected Storage. Align Web/API payloads and the established authority semantics
  while preserving revision/digest fencing. Add the required lifecycle API/Web regressions for
  successful commands and repeated publication where sequence differs from document version.
  Complete the already assigned T4 Required Tests before resubmission, including the missing
  lifecycle/E2E coverage and failing Ruff/format gates identified above; report actual counts,
  skips and any unavailable external gate. The existing tests alone do not verify these commands.
- **P1 — Removal silently adopts authority newer than the operator's confirmation
  (Acceptance Criterion 4; Slice RO-4 and Safety Invariant 8).**
  `StorageManagementPage.tsx:runLifecycleAction` fetches authority after `window.confirm`.
  In the real browser reproduction, the confirmation names `Spare Original`; another authorized
  API Edit changes it to `Spare Changed After Decision` while the dialog is open (HTTP 200).
  Accepting the old confirmation then deletes the changed object (HTTP 200; subsequent Edit
  lookup HTTP 404), instead of rejecting the stale decision. Bind the displayed selected object
  and confirmation to one exact Active authority before the decision, submit that same fence,
  and require explicit review of refreshed context after a conflict. Do not silently rebase
  removal on a post-confirmation authority fetch. Cover this actual two-writer journey in the
  lifecycle browser regression.
- **P1 — Failure recovery loses copy input and misreports a committed unknown outcome
  (Acceptance Criteria 2/6; Slice RO-4/RO-6).**
  The real disable request commits successfully (HTTP 200); dropping only its response makes the
  page display `操作未完成: transport_unavailable。当前 Active 未改变`, although a fresh real API
  read reports `enabled=false` at Active sequence 2. The stale row still offers an enabled
  `停用` action and there is no outcome-verification control. Separately, entering
  `retained-copy-id` / `Retained Copy Name` and receiving the actual copy rejection loses both
  values: reopening Copy shows `spare-copy` / `Spare Original copy`. Replace the transient prompt
  flow with retained, correctable copy state and give lifecycle failures meaningful durable-state
  recovery. Distinguish known rejection from response loss; an unknown result must offer explicit
  Active-state verification and show current truth before a new manual submission, without
  claiming the previous Active necessarily survived or replaying automatically. Add browser
  coverage for retained failed-copy input and real committed-but-response-lost recovery.
