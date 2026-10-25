# NO ACTIVE IMPLEMENTATION TASK

Task46.2: **PASS**. B reviewed `6072f50d5b2e5268c35d6729290512d1ae986104..bb176f2f36c92d5f5298c19e8d1c9eed45c1a9e5`.
See [B Review Result](#b-review-result) for accepted delivery, actual validation and known limits.
Slice46 remains ACTIVE; RO-2/4/5 require subsequent Task planning. No next Task is authorized by
this notice. The reviewed Task contract/reports below are retained for handoff, not active work.

# Task 46.2 — Durable ordinary-file status on both library pages

Authority: committed [Slice46](SLICE.md) RO-3, AC-4 and the local ordinary-work portions of
AC-7/8; [Development Workflow](docs/development-workflow.md). Read the
[Developer experience](docs/agent-experience/developer-implementation-role.md) before implementation.

```text
Task ID: 46.2
Parent Slice: 46
Status: PASS
Task Base: 6072f50d5b2e5268c35d6729290512d1ae986104
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

An operator completes create-folder/text, Rename, bounded text Edit, Copy, Move and Delete on the
originating ResourceLibrary/MediaLibrary file page, and can reopen multiple durable operations,
independent results and existing safe controls after close/reload/reconnect/service restart.

Journey: submit an existing ordinary file command → read its result/progress → open header entry
**当前页面操作状态** → select the exact originating operation → inspect stage, source/destination,
known/partial/uncertain effects and permitted next action → explicitly use an existing safe control
if available → read the real outcome and refreshed live files. Closing the modal neither cancels
nor replays work. Empty/loading/read-error/denied/unavailable states have a safe read/recovery path.

Requirements: `V2-FILES-002/003/007`, applicable `V2-OPS-014`, `V2-AUTH-001–003`, `V2-SAFE-001`,
`UX-001–003/007/010`, `REQ-TASK-002/003/005–010`, `REQ-RECOVERY-002/006` and `REQ-SAFE-003–007/009`.
Read complete TARGET ordinary-file and CURRENT Real Storage Files/Common file maintenance/
MediaLibrary journeys in [Product Experience](docs/product-experience.md); affected TARGET local
readback and CURRENT admitted-transfer/direct-command/durable-Delete contracts in
[Architecture](docs/architecture.md); local ownership in [Task Center specification](docs/task-center-page-spec.md).

### Actual gap and reusable implementation

- `StorageFilesPage.tsx` / `MediaLibraryFilesPage.tsx` headers only expose the Add action. Each page
  holds one `admittedTransferId` in component state. A fresh page cannot enumerate prior operations.
- `delete-admission-session.ts` retains one non-authoritative Delete request per kind/library and
  clears it at settlement. This supports exact unknown-Delete readback, not a durable work index.
- `FileCommandDialogs.tsx` sends Delete inspection/recovery to `/operations/tasks/$taskId`.
  Page error guidance also refers ordinary work to Operations. `TransferDialog.tsx` already renders
  bounded progress/outcomes and backend-offered pause/cancel/resume; reuse that behavior locally.
- `direct_file_commands.py` persists single-command Tasks/TaskItems/Results; Delete and
  `direct_file_transfers.py` use durable `files_transfers` authority/claims/checkpoints. Exact kind
  identity is present in command semantics, namespaced item IDs and transfer/delete authority.
- `service_api.py` has kind/library-bound Delete and transfer reads and a durable-reader fallback
  when current Active is unavailable. `operations_runs_window` in `sqlite_runtime.py` reads mixed
  work; its display `source` filter is not an exact ordinary-work kind/library/source predicate.
  Do not fetch mixed pages and filter them in the browser or infer authority from display text.

Task46.1 PASS remains at `6072f50d5b2e5268c35d6729290512d1ae986104:TASK.md`; RO-1 is complete.
RO-2/4/5 remain incomplete. This Task completes the ordinary-file journey before later center
population removal; it does not claim delivery of organizing-only Task Center.

## Implementation Scope

1. Add bounded application/repository readback for ordinary work, exposed through authenticated
   library-scoped API behavior. These are reads to implement, not existing endpoints to probe.
   Reuse durable Tasks/items/results and transfer/Delete projections; no second catalog/queue.
   Scope supported direct/transfer/Delete command families and exact originating library kind/ID
   before counts/paging/detail. Derive source, target and pin from durable admitted evidence,
   including valid pre46 records, never filenames, labels, today's Active or heuristic Job links.
   Keep complete bounded paging rather than a permanent newest-N cutoff; per-item results must
   remain reachable beyond a first preview page. Preserve other consumers' existing query defaults.
2. Make originating library context explicit in the modal and its backend query. A directory change
   must not hide the library's known operations. Keep earlier origins reachable when selecting
   another library; show the selected/history scope rather than silently rebinding entries.
   Same IDs across kinds, roots or revisions cannot exchange source/target/pin/control authority.
   Missing historical context is labelled/restricted, never guessed; known work remains inspectable
   when current Active/library is disabled, removed or unavailable, using admitted evidence where
   valid. No current-Active reconstruction or Storage/Provider calls on status/history reads.
3. Add **当前页面操作状态** immediately left of 添加资源库 / 添加媒体库, with that Add button's
   style. It opens a shared centered accessible modal for that page kind's bounded ordinary work.
   Reuse `ModalDialog`, result presentation and typed API normalization where suitable. Provide
   independent operation selection, progress/results, exact original library/source/destination,
   factual stage/error/effect certainty, and available controls. Keep empty/loading/read-error,
   paging, Escape/close/focus return, desktop/narrow layout and readable disabled/focus states.
   Viewer read access must not depend on configuration/Add permission. There is no global center.
4. Connect all seven existing ordinary command kinds to local inspection. Preserve immediate
   result dialogs; replace their normal center links/copy with the local status entry/exact detail.
   Reopen from durable backend history without requiring a browser hint or remembered Task ID.
   Keep hints/cache principal-isolated and kind/library-bound; clear stale selected results on
   identity/scope changes. Opening, polling, refresh, close and reconnect never admit commands.
   Preserve Delete's exact request-ID reconciliation. For a lost response without a proved durable
   identity, show unknown outcome and local inspection; never select a guessed matching run from
   name/time, claim non-execution or replay. No general command/idempotency redesign is required.
5. Reuse only existing backend-permitted pause/cancel/safe continuation, with exact Task version,
   kind/library/source/pin and current execution permissions. Revalidate scope on the backend for
   selected detail and controls as well as list reads. A read grant, stale UI, forged URL/hint or
   successful peer command cannot grant new effects. Refused/stale/unknown control replies trigger
   durable reconciliation, not automatic repeat. Completed/uncertain siblings remain non-replayable;
   cross-Storage Move retains Copy → verify → Delete-source and explicit destructive intent.
   Refresh live source/destination after actual effects without dropping unrelated selections.
6. Make existing ordinary-file Task/run deep links resolve to the exact local inspection context
   when durable evidence proves it, or bounded permission/unavailable guidance when it does not.
   Reuse backend resolution; do not load a generic organizing recovery panel or guess a library.
   Keep organizing/preparation/Automation routes and administrative API/CLI behavior intact.
   Do not narrow center list/count/Attention populations in this Task; that is RO-4.
7. Cover the journeys below through existing page/command entry points and the isolated real-Python
   harness. Prefer extending `direct-files.python.spec.ts` and existing fixtures over new process
   tooling. Fixture gates may delay actual calls for races, but cannot fabricate successful product
   payloads or toggle DOM state to prove recovery. Update affected command guidance/consumer tests;
   any necessary additive persistence change must preserve old rows and include fresh/reopen/
   upgrade/failure-atomicity checks. Avoid schema changes if current durable evidence suffices.

## Acceptance Criteria

- [x] Both headers have the required adjacent, same-style status entry. Its centered modal works
  with mouse/keyboard at desktop 1536×1024 and narrow 390×844, including focus restoration,
  empty/loading/read-error/401/403 states. Viewing has no new work/media/Provider/Storage effects.
- [x] All seven ordinary operations show real outcomes locally. Multiple operations are independently
  selectable; switching entries/libraries does not overwrite siblings or mix either library kind.
  No normal ordinary-command result/recovery guidance requires Task Center.
- [x] Backend list/detail/counts/cursors use the same exact authorized ordinary scope before paging.
  Mixed organizing/notification/unknown work never leaks into it. Multiple pages and per-item results
  remain reachable; same-ID opposite-kind, foreign-library and foreign-principal cursor/hint/selection
  tampering is refused rather than rendered empty or rebound. Existing allowed read policy is preserved.
- [x] Closing/reloading/reconnecting and reopening API/SQLite retains multiple operations, including
  supported work admitted before this change and operations whose browser hints are absent. Changed/
  missing Active/root/library cannot overwrite the historical origin/pin; unprovable context explains
  restricted inspection/control. Browser state is neither authority nor the sole recovery index.
- [x] Actual queued/running/paused Copy/Move/Delete and mixed-success batches expose backend-legal
  controls and independent results. Safe continuation affects only known-safe remaining work;
  partial/uncertain/error/display-failure states retain their factual effects and legal next action.
  Read-only viewers and stale/concurrent controls cannot change media or expand authority.
- [x] Lost Delete admission and unknown command/control responses reconcile without automatic replay,
  guessed identity or false success. Successful/uncertain items do not replay after close/restart or
  duplicate control attempts. Cross-Storage Move verification failure preserves source.
- [x] Ordinary Task/run deep links reopen exact local inspection or bounded refusal with no mutation;
  organizing routes/returns and administrative consumers remain functional. Live refresh updates only
  affected browse/selection state. Required native screenshots and tests prove actual backend state.

## Required Tests

Follow [test levels and ownership](docs/development-workflow.md#6-test-levels). **T4** applies because
local recovery exposes destructive work, shared persistence projections, scope/permissions and
concurrent controls. Developer runs affected checks; B owns full regression and acceptance.

### Developer — affected tests

From repository root (the new module below is to be implemented for this Task):

```bash
python3 scripts/check_governance.py
git diff --check
.venv/bin/python -m unittest tests.test_library_file_operation_history
.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_media_library_direct_commands
.venv/bin/python -m unittest tests.test_direct_file_transfers.TransferApiTests
.venv/bin/python -m unittest tests.test_media_library_transfers.MediaLibraryTransferTests.test_equal_ids_cannot_exchange_transfer_authority tests.test_media_library_transfers.MediaLibraryTransferTests.test_media_transfer_pause_cancel_and_resume_stay_durable tests.test_media_library_transfers.MediaLibraryTransferTests.test_media_transfer_progress_survives_api_restart_during_active_outage
```

The new module exercises success, invalid scope/cursor, conflict/denial, read failure, mixed histories
across pages, pre-change persisted work/reopen, immutable origin and zero-mutation reads. Create work
through the supported application/API commands; do not invent a production entry to seed impossible
states. If shared run queries/detail or lifecycle code changes, also run:

```bash
.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_run_detail
```

From `web/`:

```bash
npm run test -- run src/features/library src/entities/library src/shared/api/library-api.test.ts src/shared/api/media-library-commands-api.test.ts src/shared/api/operations-api.test.ts src/routes/router.test.tsx
npm run typecheck
npm run lint
npm run build
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
```

Add new local-status/component/query/normalization coverage within those library directories and
run any new API test file explicitly if elsewhere. Apply ruff/Prettier checks to changed Python/Web
files and add directly affected route/lifecycle tests as needed; do not run B's full suites first.
Extend the native spec for both kinds: multiple ordinary results, lost Delete reply, hints cleared,
close/reload/reconnect, real queued Worker/paused continuation, independent batch effects and local
legacy-link return. Retain existing actual Copy/Move/Delete safety assertions. Backend reopening
must be real API/repository reconstruction over the same temporary SQLite data; a page reload alone
is not service-restart evidence. Reuse existing harness facilities; no new orchestration framework.

### B — acceptance and full regression

Independently review full Task Base..Head and reproduce local reopening on both page kinds, including
multiple operations, absent hints, exact old links, read denial, stale controls and real Worker effects.
Inspect desktop/narrow modal screenshots and actual read-only/disabled/focus behavior. From `web/`,
run the following real-Python regression for shared Task/detail navigation, results and center layout:

```bash
npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
```

Verify API/repository reopen and a real partial/uncertain non-replay case through supported command/
fault boundaries, not invented routes.

Run all applicable [shared full T4 gates](docs/development-workflow.md#shared-full-regression-commands):
full Python and Web regression/static checks, default E2E, wheel build/installed smoke and safety/
persistence gates. Run Docker/restart/security proof when deployment/runtime packaging is affected;
otherwise record that applicability decision, not a Docker success. If schema changes, verify fresh,
previous supported schema upgrade/reopen and failure atomicity. Preserve C→A identity and pin/fence/
completed/uncertain safety coverage. Unavailable required gates remain explicit and pending.

Record exact candidate/artifact, commands/results/skips and durable local evidence. Keep testing
wall time below **50%** of this round's elapsed work time, counting overlapping runs once; no deliberate
waiting, redundant full runs or shortened safety coverage. An actual blocker permits early FIX REQUIRED;
fixes stay Task46.2. Planning itself requires governance/document/whitespace checks only.

## Non-goals

- RO-2 early manual admission/source ownership and RO-4 organizing-only eight views/four-type counts,
  center block/creation removal remain later coherent work. Only ordinary local-link integration is here.
- RO-5 Automation detail/Enabled/grants/Run once/stability changes; unrelated Shell/Dashboard redesign.
- New file commands/providers/authority, cross-kind transfer, MediaLibrary organizing, universal retry/
  undo, uncertain replay, global file-operation center, history cleanup or Scan/Preview/FileIndex return.
- Queue/Worker supervision redesign, general idempotency framework, broad refactoring or governance tools.
- Slice/Roadmap boundaries, A closure or another Task plan.

## Workspace and handoff

Planning started on `main` at immutable Task Base above. Governance passed; workspace/Git/TASK.md
are writable. Preserve the pre-existing `docs/pics/操作与任务.png` deletion and all untracked reference
images/logs/OS/test artifacts. Only TASK.md is planned/checkpointed. Private configuration/databases
and user media are not fixtures; no push/publication is authorized or performed.
A-owned Slice/Roadmap/Progress first-Task pointers remain stale; this plan follows the committed
ACTIVE Contract and accepted46.1 result without changing their boundaries/status.

## Developer Completion Report (fix round — 2026-10-25)

```text
Candidate: dde88c77 (implementation; report checkpoint follows)
Range:     ad25d4379e6e13a6b21ea6ed1bbdb4dde84084ee..dde88c77
Status:    READY FOR B REVIEW — no self-PASS, no push, no publication
```

This round corrects the three B-blocking findings of the `eda53131` review
(B46.2-01/02/03) inside the same Task46.2 local status journey. Task Base, Goal,
Scope, T4 and acceptance are unchanged. No next Task, no Slice closure.

### B46.2-01 — per-item results and failure/effect evidence are now local

- `mediaflow/application/library_file_operations.py::detail` now also returns the
  exact per-item evidence of the selected operation: `items[]` with each item's
  `path`/`destination`, `status`, `stage`, `attempts`, `effect`,
  `effectCertainty`, `knownEffects`, a bounded `failure` document and its own
  `nextAction`, plus operation-level `durableState`, `effectCertainty`,
  `nextAction` and `itemsTruncated` with a hard `_MAX_DETAIL_ITEMS=100` /
  `_MAX_DETAIL_OUTCOMES=400` bound. Everything is rebuilt from durable
  TaskItem/Result rows only (no Storage, Provider or Active resolution), and the
  newest Result per item is used, so attempts stay history and never replay.
- A refused `PARTIAL`/`FAILED` item whose Result effect certainty is
  `attempted_unverified` is reported as `UNCERTAIN`/`effect: uncertain` — the
  same vocabulary the Delete/transfer projections already use — so the operator
  cannot read it as "nothing happened".
- Failure text goes through the existing `bounded_failure_document`, so a raw
  durable error is never published.
- Counts reconcile: `skippedItems`/`cancelledItems` are now counted from
  `SKIPPED`/`IGNORED`/`CANCELLED` items, and `OrdinaryFileOperationRow.item_pending`
  subtracts them, so a skipped/cancelled batch is settled instead of showing
  phantom pending items.
- `LibraryFileOperationsDialog.tsx` renders a 逐项结果 list (status, effect +
  certainty, recorded effects, bounded failure, per-item next action) and the
  operation-level 已记录影响/next action. `ModalDialog` gained a `wide` variant
  (960px, one scroll region, narrow viewport still 520px) so the two-column
  evidence is not hidden below the fold at 1536×1024.

### B46.2-02 — one shared deep-link resolver that reads the persisted kind

- The `GET /api/v1/files/operation-origin/{taskId}` route no longer hardcodes
  `media_library=False`. `LibraryFileOperationHistoryService.resolve` now derives
  the kind from the Task's own durable command (`_origin_for`), so a
  MediaLibrary Task resolves to its MediaLibrary page and a ResourceLibrary Task
  to its ResourceLibrary page. `media_library=None` means "read the persisted
  kind"; an explicit caller kind still refuses the other kind's work.
- `normalizeLibraryFileOperationOrigin(payload)` no longer takes an asserted kind:
  the published `libraryKind` is part of the result, and a split/unknown identity
  still fails closed.
- `TaskDetailPage` makes one origin read instead of a resource-then-media pair,
  and builds the return link from the published kind.
- `destination-model.ts` now replays a bounded `operationTaskId`
  (`/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/`) through authentication continuation
  on both `/resourcelib/files` and `/medialib/files`, so reconnecting on an exact
  local-work URL no longer drops the parameter and opens no inspection.

### B46.2-03 — a historical inspection scope that survives a disabled library

- New bounded repository read `SQLiteTaskRepository.library_file_operation_origins`
  (distinct persisted scoped identities per kind, decided by the `media:` namespace),
  new application read `LibraryFileOperationHistoryService.origins`, and the
  authenticated routes `GET /api/v1/resource-libraries/operation-origins` and
  `/api/v1/media-libraries/operation-origins` (`limit` 1..100). They are durable
  reads: no Active resolution, no Storage, no Provider; the audit template carries
  no library or Task identity.
- Both pages now carry an explicit `originId` in the `operations` dialog state and
  pass `onSelectOrigin`, so the dialog lists exactly the selected historical
  library's work. The dialog shows a bounded 历史操作所属库 selector whenever the
  index holds more than one origin or the current origin is not in it, and its
  header explains when the current library holds no records.
- The proven deep link seeds `originId` from the URL's own proven library identity
  instead of today's first enabled library, so a disabled origin reopens from its
  Task link.
- Reading a disabled origin never re-enables it, never rebinds the live browse
  location and never creates work; the live page heading and library cards stay
  exactly as before.

### Actual commands and results (this round, from the stated cwd)

| Area | Command | Result |
|---|---|---|
| Governance | `python3 scripts/check_governance.py` | PASS |
| Whitespace | `git diff --check` | clean |
| Python static | `.venv/bin/ruff format --check mediaflow tests scripts`; `.venv/bin/ruff check mediaflow tests scripts` | 357 formatted, 0 findings |
| Python compile | `.venv/bin/python -m compileall -q mediaflow tests scripts` | OK |
| New/affected Python | `.venv/bin/python -m unittest tests.test_library_file_operation_history` | 17 tests OK (was 13) — still the only module change |
| Affected Python | `.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_media_library_direct_commands` | 88 tests OK |
| Affected Python | `.venv/bin/python -m unittest tests.test_direct_file_transfers.TransferApiTests` | 7 tests OK |
| Affected Python | `.venv/bin/python -m unittest tests.test_media_library_transfers.MediaLibraryTransferTests.{test_equal_ids_cannot_exchange_transfer_authority,test_media_transfer_pause_cancel_and_resume_stay_durable,test_media_transfer_progress_survives_api_restart_during_active_outage}` | 3 tests OK |
| Shared read | `.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_run_detail` | 76 tests OK |
| Web focused | `npm run test -- run src/features/library src/entities/library src/shared/api/library-api.test.ts src/shared/api/media-library-commands-api.test.ts src/shared/api/operations-api.test.ts src/routes/router.test.tsx` (cwd `web/`) | 18 files / 279 tests passed |
| Web adjacent | `npx vitest run src/features/operations src/shared/navigation` (cwd `web/`) | 24 files / 278 tests passed |
| Web static | `npm run typecheck`; `npm run lint`; `npm run format:check`; `npm run build` | all clean; artifact `index-ak474z5z.js` / `index-BFNi4meT.css` |
| Native real Python | `npx playwright test --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` (cwd `web/`) | **15 passed** |

### Native evidence produced this round

Both library kinds, real page controls, real Worker, same temporary SQLite file:

- **Mixed/uncertain batch (new, both kinds).** Select two real files → the harness
  refuses exactly one *actual* `LocalStorage.delete` → run the production
  `FilesTransferWorker` → the local detail names both files, the refused one with
  its bounded `workflow_failure` reason, `来源保留`/无变更 effect and per-item next
  action, the successful sibling as `已完成变更`/已核实完成, and the operation-level
  next action. Filesystem proves `Keep` still exists and `Remove` is gone. Then a
  real `POST /__harness__/restart` (repository + API reopen over the same SQLite
  file) + full page reload with no remembered Task ID reproduces the same evidence,
  the count is unchanged, and neither source state changed.
  Artifacts: `resource|media-mixed-operation-evidence{,-desktop}.png`
  (desktop is a real 1536×1024 viewport capture).
- **Disabled origin (new).** A real unreferenced ResourceLibrary is added through
  the supported `save_resource_library` command, work is created through the page,
  and the library is disabled through a real managed successor publication
  (draft → edit → validate → activate). After reload the live list no longer offers
  it, its `/file-operations` total is unchanged, `operation-origins` still names it,
  the 历史操作所属库 selector lists it, and selecting it shows the real operation.
  The exact Task's shared deep link then resolves `matched: true`,
  `libraryKind: resource`, `resourceLibraryId: b-review-history` and reopening that
  URL reopens local inspection with the exact operation preselected.
  Artifacts: `resource-disabled-origin-history{,-desktop}.png`,
  `resource-disabled-origin-deep-link.png`.
- Both kinds' existing `reopens its own durable operation status` journeys still
  pass, with the narrow capture now a real 390×844 viewport shot.

### Added/extended coverage (success / invalid / conflict / failure / edge)

Python (`tests/test_library_file_operation_history.py`, 13 → 17): mixed two-file
Delete with one real Storage refusal asserting per-item dispositions, effects,
bounded failure, per-item and operation next actions, count reconciliation,
no absolute path/token leakage, and byte-identical evidence from a fresh
repository with no Active binding; skipped/cancelled reconciliation; the
per-kind origin index (both kinds, viewer read, invalid limits, zero Storage
mutation) including a disabled unreferenced library staying in the index and
readable; and the corrected kind-resolving deep link (resource + media +
unknown Task).

Web: entity model/detail normalization for per-item evidence and the closed
`durableState`/`effectCertainty` vocabularies; the untouched-origin index model
refusing the other kind; client URL/refusal contracts for the origin index and
the kind-publishing origin read; the mounted-page dialog showing real per-item
evidence of a mixed batch (failed/uncertain + successful sibling, no mutating
control) and the disabled historical origin selector; and
`destination-model.test.ts` proving `operationTaskId` survives reconnect while a
tampered/credential-shaped value is dropped.

Harness additions (`scripts/direct_files_browser_harness.py`): a bounded
`POST /__harness__/arm-files-delete-fault` that arms one real `LocalStorage.delete`
refusal for the next Worker run (cleared by posting no name), and
`POST /__harness__/add-unreferenced-origin` +
`POST /__harness__/disable-resource-library` that publish a real managed successor
Active. Both are test-only fixtures over temporary roots; no product payload is
fabricated and no DOM state is toggled to prove recovery.

### Known risks and remaining Slice outcomes

- The `Shift+F10` keyboard row-menu helper is still order/timing sensitive: in a
  full-spec run this round it passed all 15 cases, while in an earlier run
  `MediaLibrary Files renames…` timed out at the same `menuitem "重命名"` click.
  Reproduced at Task Base `6072f50d` in an isolated worktree (its own venv, built
  artifact and the committed harness) and it fails there too, so it is pre-existing
  and outside this Task's surface. It remains visible rather than retried or
  relaxed.
- Per-item evidence is bounded (`_MAX_DETAIL_ITEMS`/`_MAX_DETAIL_OUTCOMES`) rather
  than paged. An ordinary command admits one item per selected source and the
  domain caps a selection at `MAX_TRANSFER_PATHS`/`MAX_DELETE_PATHS` (50), so the
  bound is defensive; `itemsTruncated` is explicit if it ever applies. If B wants
  per-item cursor paging inside the modal, that is a follow-up within RO-3.
- `origins` returns up to 100 origins per kind ordered by persisted identity,
  with `truncated`. The selector is a bounded `<select>`; a library with hundreds
  of historical origins would need search/paging (not required by the Task).
- Still not delivered (outstanding Slice outcomes): RO-2 manual admission before
  rule resolution, RO-4 organizing-only Task Center population/views, RO-5
  Automation semantics. Center list/count/Attention populations were deliberately
  not narrowed here.
- No schema change was needed: `operations_run_display`, `task_items`,
  `task_results` and `files_transfers` already carried every fact used.

### Workspace

All pre-existing untracked artifacts, the `docs/pics/操作与任务.png` deletion,
reference images, logs and `web/test-results*` builds are preserved and not
committed. Native screenshots/artifacts from this round are held locally under
the ignored `.git/validation-evidence/task46.2-fixes/`. No push, no publication.

Full acceptance, full regression and any PASS/FIX decision remain B-owned.

## B Review Result

```text
Reviewed Task range: 6072f50d5b2e5268c35d6729290512d1ae986104..bb176f2f36c92d5f5298c19e8d1c9eed45c1a9e5
Implementation: 2541d0c89d70a965cfac4d9f45580fb6147a71cb
Decision: PASS — 2026-10-25
Task blockers: NONE; B46.2-01/02/03/04 corrected
Slice Required Outcomes / Surfaces all satisfied: NO
Next: NEXT TASK for remaining RO-2/4/5; no next implementation Task planned here
```

B independently reviewed the complete 28-file Task Base..Head range and the latest live-snapshot
repair against the committed Slice. The report-only successor `2541d0c8..bb176f2f` changes only
`TASK.md`; executable inputs match the implementation checkpoint. Task Base, Goal, Scope, Difficulty
and T4 are unchanged. The superseded FIX REQUIRED and repair guide remain in Git at
`d9bc34e6:TASK.md`. This review changes only B-owned `TASK.md`; it does not close Slice46.

### Delivery and corrections accepted

- **Live state / B46.2-01:** the selected operation has an independently polled durable snapshot
  for stage, whole-operation counts/effects/next action and lifecycle/version. Item pagination no
  longer stops that polling. When snapshot and item evidence disagree, bounded rereads refresh the
  loaded evidence; a known terminal snapshot cannot regress to an unfinished one. Both new native
  61-item queued-to-completed cases pass. B also used the existing page Delete and real Worker on
  separate 121-item directories of both kinds: the same open panel reaches success 121 / pending 0,
  verified-complete effects, no queued loaded items and all 121 results, without closing/reopening.
  Resource continuation was read across the actual Worker transition. Media's old Cancel was
  rejected after real completion and the panel reconciled to terminal state; it was not repeated.
- **Complete effects/items:** the real 121-item partial-Delete cases retain success 119 / failed 2,
  operation-wide uncertainty and every item's reachable result. The real refused file remains at
  source. Paused folder Move shows actual completed child effects and safe remaining-work guidance.
  The shared effect interpretation preserves existing transfer projections; reads do not execute.
- **Scope/reopening / B46.2-02/03:** durable command kind and admitted item/library identity scope
  history before paging; cursor validation binds kind/library/principal/Task. Both page headers
  expose the same-style local entry beside Add. Multiple independent commands, absent browser hints,
  reload/reconnect, fresh repository/API over the same SQLite data, pre-change records and disabled
  historical origins remain inspectable. No current-Active reconstruction or Storage/Provider read
  is added to durable history. Existing admission, claims, pins and execution authority stay intact.
- **Old links and permissions:** with fresh browser contexts and the existing read principal lacking
  configuration/execute grants, both real ordinary Task links return to the exact kind/library/
  `operationTaskId` and display the correct completed operation. Existing selected-run links traverse
  their actual **打开 Task 详情 → 返回发起它的库文件页** route to the same local inspection. Captured
  navigation/read requests contain zero writes. The existing missing-directory recovery remains
  available when the operation has deleted its original directory; history itself remains readable.
  Backend/component coverage also checks read denial, malformed/foreign scope and withheld controls.
- **Read errors / B46.2-04 and presentation:** both native first-detail transport failures show a
  bounded error and explicit reread, then recover the same operation without replay. Inspected actual
  desktop/narrow local modals, mixed/paused evidence, first-read error, viewer deep links and shared
  center/creation screenshots. Existing modal focus/dismissal tests pass. Close, inspect and refresh
  are reads; the UI adds no retry/undo authority and successful/uncertain work is not resubmitted.

The seven acceptance criteria above are accepted within this Task's scope, with the pre-existing
row-menu issue and exact validation limits below explicitly retained.

### Independent validation

Evidence: `.git/validation-evidence/bb176f2f/b46.2-review/` (ignored, local only). Native artifacts,
raw logs, independent probe sources/JSON and screenshots are retained there; shared screenshots
were copied into `shared-visual/`. All probes use existing routes, native page controls, supported
commands and existing test-only Worker hooks against temporary SQLite/Storage. No production media,
private configuration, invented endpoint or fabricated successful product response was used.

| Command / cwd | Actual result |
| --- | --- |
| `python3 scripts/check_governance.py`; full-range `git diff --check` | PASS / clean |
| `.venv/bin/python -m unittest tests.test_library_file_operation_history` | 21 passed, 2.643s (`history-tests.log`) |
| `.venv/bin/python -m unittest discover -s tests` | 2826 run; OK, 7 skipped; 342.507s (`python-full.log`) |
| `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .`; compileall; pip check; both documented example-config validations | 387 formatted / all exit 0 (`python-quality.log`); forbidden-dependency search has no match |
| `npm run typecheck`; `npm run lint`; `npm run format:check`; `npm run build` (`web/`) | PASS; production assets `index-BU1rCvjP.js` / `index-BFNi4meT.css`; existing chunk warning |
| `npm run test -- run` (`web/`) | 87 files / 1260 passed, 107.36s (`web-full.log`); jsdom scrollTo notices retained |
| `npm run test:e2e -- --output=<evidence>/default-e2e-artifacts` (`web/`) | 242 passed, 2.0m (`default-e2e.log`) |
| `npx playwright test --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --output=<evidence>/native-artifacts` (`web/`) | 21 passed / 1 failed, 53.8s (`native.log`); see known issue below |
| `npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts --workers=1 --output=<evidence>/operations-native-artifacts` (`web/`) | 41 passed, 1.6m (`operations-native.log`) |
| `npx playwright test --config=playwright.python.config.ts tests/e2e/operations-task-center-visual.python.spec.ts --workers=1 --output=<evidence>/visual-native-artifacts` (`web/`) | 2 passed, 9.4s (`visual-native.log`); isolated fixture verifies the previously pending creation-summary journey |
| `.venv/bin/python -m pip wheel . --no-deps -w <evidence>/wheels`; installed `scripts/wheel_smoke_test.py <exact-wheel>` | Both exit 0; installed consumers outside source, configuration and backup/rehearsal/restore/upgrade checks pass (`wheel-build.log`, `wheel-smoke.log`) |
| Independent live/links probes | Both kinds' 121-item convergence JSON/screenshots; Media one refused stale control; both Task/run return paths and zero-write viewer reads (`resource-convergence.json`, `media-convergence.json`, `viewer-links-probe-final.log`, `*-viewer-readonly.json`) |

`<evidence>` is the directory above; native output paths are passed relative to `web/` as
`../.git/validation-evidence/bb176f2f/b46.2-review/...`. Wheel SHA-256:
`20a05c558ff97f3743f63d43b2f4afb7dd3b9ec3122f62b8fbe4baa8e6856a73`.
Full Python includes the applicable RBAC, identity C→A, confinement, pin/fence, persisted reopening,
Copy→verify→Delete-source and completed/uncertain non-replay coverage. No schema, dependency,
deployment or production-runtime packaging change: Docker deployment/restart/security proof is
**not applicable**, not claimed passed. SQLite/API reconstruction is covered by the actual history
integration tests, not inferred from browser reload. No required gate remains unexecuted.

### Known non-blocking issue and evidence limits

The full direct-files native run is **not all green**. Resource Rename fails at spec helper line318:
after `Shift+F10`, the menu is not visible, before the Rename command is sent. A focused isolated
rerun also fails at that assertion (`rename-isolated.log`). A separate existing pointer-menu journey
reaches the Rename menuitem but it becomes unstable/detached before click (`rename-pointer-probe.log`).
Neither attempt establishes a successful Resource Rename; they are not counted as passes.

B's prior independent original-Base build/run is retained at
`.git/validation-evidence/79f67b4d/b46.2-review/base-native.log` and `base-native-artifacts/`:
8 passed / 2 failed, including the same Resource Rename journey and menuitem instability/detachment
before submission. `RowActionMenu.tsx` and the existing entry keyboard/context-menu handlers are
unchanged in this Task range. The current keyboard failure stack differs from that Base click
failure, so exact equality of those stacks/root causes is not claimed. B accepts this as the known
pre-existing row-menu interaction issue outside the new durable-status delivery, not a reason to
expand this Task into menu redesign. Candidate Media Rename and the new status/recovery cases pass;
backend/consumer regression covers unchanged command/result semantics. No assertion, timeout or
retry was weakened to hide the failure.

Independent probe attempts also retain their actual limits: an initial pagination helper clicked
again after the final continuation disappeared; another same-tab return first restored the exact
saved Delete result, which offers the existing local-inspection button. Fresh-context link runs
then verify the durable deep-link path independently. Two viewer helpers incorrectly expected Add
to be absent/disabled; the pre-existing Add CTA remains available in that fixture, while backend
configuration authority is separate. Those helper assertions are not product requirements and are
not reported as permission failures or successful acceptance runs. Final viewer evidence proves
read access without configuration/execute grants, correct scope and zero write requests; it does
not claim the old Add CTA is hidden. These attempts and the focused menu checks count in test time.

Review work started at 11:00:40 UTC. Build/full regression overlaps from approximately 11:01:40
through 11:09:37; later short acceptance/failure probes are counted in addition, including failed
helpers. Total testing/build/probe wall time is conservatively below 9.5 minutes, counting overlap
once. Code/contract review, visual/evidence inspection and Task reconciliation continue beyond
11:19:40 UTC, keeping testing below 50% of elapsed work. There was no deliberate waiting, repeated
full suite or reduced safety coverage to meet that allocation.

### All Slice outcomes reevaluated

| Outcome | Current assessment |
| --- | --- |
| RO-1 readable shared actions | Accepted Task46.1 retained; new modal uses the shared palette |
| RO-2 Files-only early manual organizing admission | Incomplete; not implemented by Task46.2 |
| RO-3 ordinary-file progress/results/recovery stay local | Complete for Task46.2; PASS with the known baseline issue above |
| RO-4 organizing-only center and truthful eight-view queries | Incomplete; center population/block removal is not this Task |
| RO-5 Automation detail/Enabled/Run once | Incomplete; not this Task |

Decision after Task PASS: **NEXT TASK**, not SLICE READY FOR A REVIEW and not Slice closure.
No new implementation unit is planned in this review. A-owned Slice/Roadmap/Progress boundaries
and stale first-Task pointers are preserved; no product code, push or publication is included.
Branch `main`; the pre-existing `docs/pics/操作与任务.png` deletion and all untracked/private/
reference/log/test artifacts remain untouched and unstaged.

## Developer Completion Report (B46.2-01 repair round — 2026-10-25)

```text
Candidate: 1fa4bf55 (implementation; report checkpoint follows)
Task Base: 6072f50d5b2e5268c35d6729290512d1ae986104
Status:    READY FOR B REVIEW — no self-PASS, no push, no publication
```

Same Task46.2, same Goal/Scope/T4/acceptance. This round closes the two
B46.2-01 / P1 blockers raised in the `511a0d9a` review (per-item access for a
real directory Delete; truthful effects from durable transfer checkpoints) plus
the aggregate-certainty defect in the native mixed-Delete screenshot. No next
Task, no Slice closure, no RO-2/RO-4/RO-5 work.

### 1 — every admitted item is now locally reachable (finding 1)

- `SQLiteTaskRepository.library_file_operation_items_window` is a new bounded
  read: one `(created_at, item_id)`-ordered page of one Task's TaskItems plus
  that page's page-independent total and its newest Result per item, all inside
  one read transaction. It resolves no configuration, opens no Storage and
  writes nothing.
- `LibraryFileOperationHistoryService.detail(..., limit, after)` pages over it
  instead of returning a fixed 100-item prefix, and publishes
  `itemTotal` (the operation's real admitted item count) and a
  `nextItemPosition`. The old `itemsTruncated`-with-no-continuation advice is
  gone; `itemsTruncated` now means exactly "another page exists".
- `GET .../files/operations/{taskId}` accepts `limit`/`cursor` through the
  shared scoped-cursor machinery under a new `library_file_operation_items`
  kind whose scope binds `media=<kind>;principal=<id>;library=<id>;task=<id>`.
  A cursor from another kind, library, Task or principal is refused as an
  invalid cursor; a previous-direction cursor (never minted by this
  forward-only surface) is refused instead of being re-read as a forward
  position. Other consumers' query defaults are unchanged.
- `LibraryFileOperationsDialog` reads the detail with `useInfiniteQuery`, shows
  `已显示 N / M 项逐项证据`, and offers 加载更多逐项结果 until the backend stops
  publishing a continuation. Aggregate facts come from the newest page, so a
  continued list and the operation-level facts cannot disagree.

### 2 — one shared interpretation of durable effects (finding 2)

- New read-only module `mediaflow/application/direct_file_effects.py` now owns
  the item disposition, the per-entry child outcomes (progress snapshot while
  unfinished, Result annotations once terminal) and the effect certainty.
  `direct_file_transfers.py` and the local detail read both use it, so a paused
  folder Move has exactly one set of children and one vocabulary everywhere;
  the previous duplicate implementations in `direct_file_transfers.py` were
  removed (its behavior is unchanged, proven by its 100 tests).
- An unfinished item that already recorded a real mutation reports
  `effect: partial` / `effectCertainty: partial` and keeps its recorded
  children (created directory, each moved file, each skipped/refused child)
  with their own destinations, statuses and executor checkpoints. The B-reported
  paused Move now shows `show`, `show/ep00.mkv`, `show/ep01.mkv`,
  `show/ep02.mkv` as completed children instead of one opaque directory.
- `aggregate_effect_certainty` replaces the old branch that collapsed every
  non-all-verified set to `none`: uncertain dominates, all-verified is
  `verified_complete`, a known change mixed with anything else is `partial`,
  `none` requires every settled item to record no effect, and unproven admitted
  work is `unknown`. A verified success beside a refused sibling can no longer
  read as 无变更.
- Failure evidence also carries the durable `retryCategory` when one exists,
  still routed through `bounded_failure_document` (no raw durable text).

### Actual commands and results (this round)

| Area | Command | Result |
|---|---|---|
| Governance | `python3 scripts/check_governance.py` | PASS |
| Whitespace | `git diff --check` | clean |
| Python static | `.venv/bin/ruff format --check mediaflow tests scripts`; `.venv/bin/ruff check --no-cache mediaflow tests scripts` | 358 formatted, 0 findings |
| New/affected Python | `.venv/bin/python -m unittest tests.test_library_file_operation_history` | **20 tests OK** (was 17) |
| Affected Python | `... tests.test_direct_file_operations tests.test_media_library_direct_commands` | 88 OK |
| Affected Python | `... tests.test_direct_file_transfers.TransferApiTests` | 7 OK |
| Affected Python | `... tests.test_direct_file_transfers` (whole module) | 100 OK |
| Affected Python | `... tests.test_direct_file_transfers.PauseCancelResumeTests.test_pause_inside_one_directory_is_observed_and_resumed` | 1 OK |
| Affected Python | `... tests.test_media_library_transfers.MediaLibraryTransferTests.{test_equal_ids_cannot_exchange_transfer_authority,test_media_transfer_pause_cancel_and_resume_stay_durable,test_media_transfer_progress_survives_api_restart_during_active_outage}` | 3 OK |
| Shared read | `... tests.test_operations_run_inventory tests.test_operations_run_detail` | 76 OK |
| Web focused | `npm run test -- run src/features/library src/entities/library src/shared/api/{library-api,media-library-commands-api,operations-api}.test.ts src/routes/router.test.tsx` (cwd `web/`) | 18 files / 281 tests passed |
| Web adjacent | `npx vitest run src/features/operations src/shared/navigation` | 24 files / 278 passed |
| Web static | `npm run typecheck`; `npm run lint`; `npm run format:check`; `npm run build` | all clean; artifact `index-DJVQCfUt.js` / `index-BFNi4meT.css` |
| Native real Python | `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` | **18 passed** (36.5s) |

### Native evidence produced this round

Both library kinds, real page controls, real Worker, one temporary SQLite file:

- **121-item directory Delete (new, both kinds).** Select one real 120-file
  directory through the page, Delete it, and the harness refuses exactly one
  *actual* `LocalStorage.delete` near the end of the listing. The local dialog
  states `已显示 50 / 121`, 加载更多逐项结果 continues to 100 and then 121, and
  the refused child (`bulk-117.txt`) is reachable with its own bounded failure
  and next action. Filesystem proves exactly one surviving file. Then a real
  `POST /__harness__/restart` (repository + API reopen over the same SQLite
  file) plus full page reload with no remembered Task ID reproduces the same
  121-item population and the same refused child, with the source state
  unchanged.
  Artifacts: `resource|media-bulk-directory-evidence{,-desktop}.png`.
- **Paused folder Move (new).** The harness gates the real destination
  `LocalStorage.write` after three children of a six-file directory, the page
  requests a pause, and the production Worker settles it `paused`. The local
  status read shows `已记录影响: 部分已变更（其余尚未完成）` (never 无变更) and the
  item lists its 4 recorded children — the created destination directory plus
  the three really moved files, each `已完成变更`. A real
  `POST /api/v1/tasks/{id}/resume` with the version just read then moves only
  the remaining three; the filesystem ends with 6 moved and 0 remaining.
  Artifacts: `resource-paused-move-known-effects{,-desktop}.png` and the
  item-level `resource-paused-move-item-evidence.png`.
- Both kinds' existing two-file mixed-batch/reopen and disabled-origin journeys
  still pass unchanged.

### Added/extended coverage (success / invalid / conflict / failure / edge)

Python (`tests/test_library_file_operation_history.py`, 17 → 20):
both kinds' 120-file directory Delete with a real refusal beyond page one,
complete three-page traversal, no duplicated item across pages, the complete
refused-child evidence, no absolute path/token leakage and zero-mutating reads;
item-cursor scope refusal (foreign kind/library/Task, backward direction,
invalid limits/queries) plus a read that leaves Task/item/Result rows byte
identical; and the real gated-Storage paused folder Move with its recorded
children, `partial` certainty, resume through the shared lifecycle route and
exactly-once remaining work. The missing-reader case now covers both the list
reader and the item reader.

Web: entity model normalization for the child-entry list (closed status/effect
vocabularies, `itemTotal`/`nextCursor`, contradiction and malformed-child
refusal); client validation/URL contract for the item page (limit and cursor
bounds, exact query string); and a mounted-page journey that starts at page 1,
shows `已显示 50 / 121`, clicks 加载更多逐项结果 and then names the refused child
that only exists on page 2 — with no mutating control submitted.

Harness additions (`scripts/direct_files_browser_harness.py`): `bulkName` on the
existing arm-fault route (one real `LocalStorage.delete` refusal inside the
large directory), `mode: "move"` on the existing gated-worker route (one real
destination `LocalStorage.write` gate, no DOM or product payload fabrication),
plus the 120-file and six-file fixtures and their filesystem state keys. All
fixtures are test-only data over temporary roots.

### Known risks and remaining scope

- The `Shift+F10` rename row-menu helper remains order/timing sensitive
  (`element was detached from the DOM`). Reproduced again this round in an
  isolated worktree at Task Base `6072f50d` with its own build, so it is
  pre-existing and outside this Task's surface; it is reported, not retried or
  relaxed. In the final full-spec run all 18 cases passed.
- Per-item paging is bounded at 100 items per read and continues through the
  cursor; the modal shows one explicit 加载更多 step per page rather than
  virtualizing a very large list. A Delete of a 5000-entry directory therefore
  needs ~50 explicit steps — honest and complete, but not a single-click
  overview.
- Child outcomes within one item reuse the existing transfer progress bound
  (`MAX_TRANSFER_PROGRESS_ENTRIES`); `childrenTruncated` names the case where a
  recorded payload was already truncated.
- Still not delivered (outstanding Slice outcomes, unchanged): RO-2 manual
  admission before rule resolution, RO-4 organizing-only Task Center
  population/views, RO-5 Automation semantics.
- No schema change: `task_items`, `task_results` and the progress payload
  already carried every fact used.

### Workspace

Pre-existing `docs/pics/操作与任务.png` deletion, untracked reference images,
logs, `web/test-results*` and OS artifacts are preserved and not committed.
This round's screenshots/traces are held locally under the ignored
`.git/validation-evidence/task46.2-fixes-round2/`. No push, no publication.

Full acceptance, full regression and any PASS/FIX decision remain B-owned.

## Developer Completion Report (B46.2-01 / B46.2-04 repair round — 2026-10-25)

```text
Candidate: 884c88f75d17c3d2e9960f055280a241a6bc8158
Range:     8049549b0955390a5461bda17f53cd9109bccfe3..884c88f7
Task Base: 6072f50d5b2e5268c35d6729290512d1ae986104
Status:    READY FOR B REVIEW — no self-PASS, no push, no publication
```

Same Task46.2, same Goal/Scope/T4/acceptance. This round fixes only the two
P1 blockers of the `8049549b` review (B46.2-01 page-dependent aggregate,
B46.2-04 unreachable detail read-error recovery). No next Task, no Slice
closure, no RO-2/RO-4/RO-5 work.

### B46.2-01 — operation effects are independent of the selected item page

- `EffectCertaintyFold` in `mediaflow/application/direct_file_effects.py` now
  owns the one precedence rule (uncertain → verified_complete → partial → none →
  unknown) as a *streaming* fold, so an operation can be folded over any number
  of items in bounded batches. `aggregate_effect_certainty` is the list form of
  the same fold; there is no second implementation that can drift.
- New read `SQLiteTaskRepository.library_file_operation_item_signals` pages over
  the same `(created_at, item_id)` ordering as the item window in batches of 100,
  each in its own short read transaction, returning every item with its newest
  Result. It resolves no configuration, opens no Storage, calls no Provider and
  writes nothing — so an operation of any size is folded without one unbounded
  query or an unbounded in-memory document.
- `LibraryFileOperationHistoryService.detail` now delivers the bounded item page
  *and* folds `durableState` / `effectCertainty` / `nextAction` over **all**
  admitted items. `_durable_state` and `_operation_next_action` take the fold, and
  `fold.any_failed` replaces the page-local failed scan.
- A repository without the batch reader is folded page-by-page through the same
  item window (`_folded_item_pages`), i.e. still the complete population — never
  the delivered page. A new test proves both paths publish identical facts.
- `LibraryFileOperationsDialog` reads the operation-level facts from the first
  page (they are now page-independent by construction) instead of
  `lastDetail ?? detail`, so loading more items cannot change the asserted
  effect. `lastDetail` remains only the page that knows the continuation.
- Counts were already whole-operation; they stay unchanged (119/2/121 in B's
  reproduction) and now agree with the certainty instead of contradicting it.

### B46.2-04 — a failed first detail read reaches error and recovery

- `OperationDetail` in `LibraryFileOperationsDialog.tsx` now distinguishes
  *pending* from *completed-but-failed* reads: the failure branch is evaluated
  before the loading branch, so the existing bounded
  `readFailureMessage(...)` explanation and **重新读取该操作** are reachable. The
  button is disabled while a re-read is in flight and labels itself
  正在重新读取该操作….
- A query that *threw* instead of answering with a bounded failure document (the
  exact shape of an aborted detail GET) is treated as `transport_unavailable`
  when no page has arrived, so a real transport failure is never rendered as an
  endless loading hint.
- Already-loaded evidence is never discarded: pages exist ⇒ `readFailureCode` is
  null, and a failed *continuation* is disclosed separately with
  **重新读取后续逐项结果** while the loaded item results stay on screen.
- Selection, library identity and durable work are untouched by any of this; no
  new retry/execute engine, no replay, no fabricated success.

### Actual commands and results (this round, from the stated cwd)

| Area | Command | Result |
|---|---|---|
| Governance | `python3 scripts/check_governance.py` | PASS |
| Whitespace | `git diff --check` | clean |
| Python static | `.venv/bin/ruff format --check mediaflow tests`; `.venv/bin/ruff check --no-cache mediaflow tests` | 329 formatted, 0 findings |
| New/affected Python | `.venv/bin/python -m unittest tests.test_library_file_operation_history` | **21 tests OK** (was 20) |
| Affected Python | `... tests.test_direct_file_operations tests.test_media_library_direct_commands` | 88 OK |
| Affected Python | `... tests.test_direct_file_transfers` (whole module) | 100 OK |
| Affected Python | `... tests.test_media_library_transfers` (whole module) | 27 OK |
| Shared read | `... tests.test_operations_run_inventory tests.test_operations_run_detail` | 76 OK |
| Web focused | `npm run test -- run src/features/library src/entities/library src/shared/api/{library-api,media-library-commands-api,operations-api}.test.ts src/routes/router.test.tsx` (cwd `web/`) | 18 files / 284 tests passed |
| Web static | `npm run typecheck`; `npm run lint`; `npm run format:check`; `npm run build` | all clean; artifact `index-BYlwlmy9.js` / `index-BFNi4meT.css` |
| Native real Python | `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` | **18 passed, 2 failed** (see risk below); the 18 include both new journeys |
| Native focused | `npx playwright test ... -g 'recovers from a failed first detail read\|reaches every item of a large directory Delete\|mixed batch'` | **6 passed** (17.9s) |

### Native evidence produced this round

Real page controls, real Worker, same temporary SQLite file, both kinds:

- **121-item directory Delete aggregate (extended).** After the real refused
  child settles, the dialog's 已记录影响 is asserted *not* to be 已核实完成 /
  无变更 on the first page, captured, then re-asserted byte-identical after
  加载更多 → 121/121. Filesystem still proves exactly one surviving file; restart
  + reload reproduces the same population. Artifacts
  `resource|media-bulk-directory-evidence{,-desktop}.png`.
- **Failed first detail read (new, both kinds).** Create a folder through the
  real dialog, open the header entry, then abort only `**/files/operations/*` at
  the browser transport boundary. The panel shows the bounded alert
  (无法连接服务…) with 重新读取该操作, never 正在读取…; restoring the transport and
  clicking it reads the same selected operation and shows the real
  `成功 1 / 失败 0`. A request listener asserts **zero non-GET requests** across
  the whole journey. Artifacts `resource|media-detail-read-failure.png`
  (inspected: alert + re-read button visible, no loading hint).
- The existing mixed-batch, paused-Move, disabled-origin and status-reopen
  journeys pass unchanged; the mixed-batch journey additionally asserts the
  aggregate is not 已核实完成.

### Added/extended coverage (success / invalid / conflict / failure / edge)

Python (20 → 21): the 121-item Delete now asserts the same whole-operation
certainty/state/next action on page 1, page 2, page 3 and with `limit=100`,
that a page of pure successes never reads 已核实完成, that a fresh repository over
the same database reproduces it, and that the whole fold plus reopen left Task,
item and Result rows byte-identical; plus a new case proving the page-by-page
fold (no batch reader) equals the batched fold on the same real mixed Delete.

Web (12 in this file): aggregate stays 效果不确定 across 加载更多; first-read
transport failure renders the alert + 重新读取该操作 with zero POSTs; a failed
continuation keeps the loaded `shows/a` row and explains the failure.

### Known risks and remaining scope

- **Pre-existing native flake (not this Task).** In the full-spec run two
  `Shift+F10` row-menu cases fail intermittently — `MediaLibrary Files renames…`
  and (this run) `ResourceLibrary Files confirms once…` — with
  `element was detached from the DOM` / `element is not stable` at the
  `menuitem` click. Reproduced at the unmodified HEAD `8fa3fd0c` in an isolated
  worktree with its own build and harness (2 failed there too:
  `MediaLibrary Files confirms once…`, `MediaLibrary Files renames…`), and each
  also passes when run in isolation. It is a test-helper timing issue in
  `RowActionMenu`'s portal measurement, outside this Task's surface; it remains
  visible rather than retried or relaxed. Logs/traces are kept under the ignored
  `.git/validation-evidence/task46.2-fixes-round3/` (including
  `base-8fa3fd0c-test-results/`).
- The whole-operation fold is read on every detail request (one bounded batch
  query per 100 items). For the domain-capped selection
  (`MAX_TRANSFER_PATHS`/`MAX_DELETE_PATHS` = 50 top-level, one item per child)
  this is a handful of indexed reads; no cache or paging of the aggregate is
  introduced, because a stale aggregate would be the very defect being fixed.
- Per-item evidence remains paged at 100 per read with explicit 加载更多
  (unchanged from the previous accepted round).
- Still not delivered (outstanding Slice outcomes, unchanged): RO-2 manual
  admission before rule resolution, RO-4 organizing-only Task Center
  population/views, RO-5 Automation semantics.
- No schema change: `task_items`, `task_results` and the progress payload already
  carried every fact used.

### Workspace

Branch `main`, candidate `884c88f7`. Pre-existing `docs/pics/操作与任务.png`
deletion, untracked reference images/logs/OS files and `web/test-results*` are
preserved and not committed. The temporary base-check worktree used to prove the
flake was removed. Screenshots/traces are held locally under the ignored
`.git/validation-evidence/task46.2-fixes-round3/`. No push, no publication.

**Testing wall time:** the affected static/Python/Web/native runs above total
roughly 8 minutes of subprocess time inside a round of about 40 minutes elapsed,
i.e. below the 30% ceiling. Full T4 regression remains B-owned.

Full acceptance, full regression and any PASS/FIX decision remain B-owned.

## Developer Completion Report (B46.2-01 live-snapshot repair — 2026-10-25)

```text
Candidate: 2541d0c8 (implementation; report checkpoint follows)
Task Base: 6072f50d5b2e5268c35d6729290512d1ae986104
Range:     d9bc34e6..2541d0c8
Status:    READY FOR B REVIEW — no self-PASS, no push, no publication
```

Same Task46.2, same Goal/Scope/T4/acceptance. This round repairs the one open
B46.2-01 / P1 blocker from the `d9bc34e6` review — the panel froze on an older
snapshot after real execution — plus the sibling freeze of the operation-list
counts. No next Task, no Slice closure, no RO-2/RO-4/RO-5 work.

### Cause and correction

- **Cause.** `OperationDetail` derived stage/counts/certainty/controls from the
  *first* item page while polling was decided by the *last* one, and the
  `884c88f7` repair pinned the aggregate to page one. Once a continuation
  returned a newer terminal page, polling stopped and the older first-page facts
  became permanent: 排队等待 Worker / 成功 0 / 待处理 121 / 效果未知 with only
  queued items, exactly as B reproduced on both kinds.
- **One snapshot owns the operation facts.** The selected operation now has a
  dedicated `library-file-operation-snapshot` read of the same authenticated
  route. It supplies stage, whole-operation counts, effect certainty, next
  action, Task version and therefore the lifecycle controls, and it polls by
  *its own* terminal flag (2 s). A queued operation can no longer be frozen by an
  item page, and a terminal one stops polling.
- **The item evidence is a separate, non-polling bounded page read.** Items stay
  independently paged through the backend continuation, so a background read can
  never cancel 加载更多 and every admitted item stays reachable.
- **Stale evidence is re-read, not left standing.** When the snapshot and the
  loaded evidence describe different whole-operation facts
  (`libraryOperationSnapshotKey`: Task, status, terminal flag and every count),
  both are re-read — bounded to two attempts per state pair, after which the
  disagreement is disclosed with an explicit 重新读取逐项结果 action. Newly read
  pages therefore also show their real post-execution outcome.
- **Out-of-order answers cannot regress.** `isOlderLibraryOperationSnapshot`
  refuses an answer that would turn a terminal Task back into an unfinished one
  or shrink its admitted population; the guard sits inside the snapshot queryFn,
  so no render path and no control can be fed a regressed snapshot. Another
  Task's snapshot always replaces the view.
- **The list follows the same state.** The bounded operation list is re-read when
  the snapshot key changes, so a selected row cannot keep advertising older
  counts beside a converged panel.
- **Read failures stayed truthful and are now separated.** The snapshot read and
  the evidence read have independent bounded failures: nothing readable keeps the
  existing alert + 重新读取该操作; an unreadable snapshot behind a known older
  answer is disclosed as 上一次成功读取的结果 rather than silently shown as
  current; a failed evidence page keeps the loaded items with one explicit
  re-read.
- No backend/API/schema change was needed: the aggregate was already folded over
  every admitted item, the continuation was already exact and the lifecycle
  projection already came from the durable Task.

### Actual commands and results (this round)

| Area | Command | Result |
|---|---|---|
| Governance | `python3 scripts/check_governance.py` | PASS |
| Whitespace | `git diff --check` (pre-commit) | clean |
| Python static | `.venv/bin/ruff format --check mediaflow tests scripts`; `.venv/bin/ruff check mediaflow tests scripts` | 358 formatted, 0 findings |
| Python compile | `.venv/bin/python -m compileall -q mediaflow tests scripts` | OK |
| New/affected Python | `.venv/bin/python -m unittest tests.test_library_file_operation_history` | 21 tests OK (unchanged module) |
| Affected Python | `.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_media_library_direct_commands` | 88 tests OK |
| Affected Python | `.venv/bin/python -m unittest tests.test_direct_file_transfers.TransferApiTests` | 7 tests OK |
| Affected Python | `.venv/bin/python -m unittest tests.test_media_library_transfers.MediaLibraryTransferTests.{test_equal_ids_cannot_exchange_transfer_authority,test_media_transfer_pause_cancel_and_resume_stay_durable,test_media_transfer_progress_survives_api_restart_during_active_outage}` | 3 tests OK |
| Shared read | `.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_run_detail` | 76 tests OK |
| Web focused | `npm run test -- run src/features/library src/entities/library src/shared/api/library-api.test.ts src/shared/api/media-library-commands-api.test.ts src/shared/api/operations-api.test.ts src/routes/router.test.tsx` | 18 files / 286 tests passed (was 279) |
| Web adjacent | `npx vitest run src/features/operations src/shared/navigation` | 24 files / 278 tests passed |
| Web static | `npm run typecheck`; `npm run lint`; `npx prettier --check` (changed files); `npm run build` | all clean; artifact `index-BU1rCvjP.js` / `index-BFNi4meT.css` |
| Native real Python | `npx playwright test --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` | **19 passed / 3 failed** — see below |

### Native evidence and the pre-fix reproduction

New journey on both kinds (real page confirmation → real production
`FilesTransferWorker` → the same open panel):

1. Confirm Delete of the 60-file `Browser-Live-{Resource,Media}-Directory`
   through the page (61 admitted items); exactly one admission POST.
2. Open **当前页面操作状态** while the Task is still `pending`: 阶段 排队等待
   Worker, 成功 0 / 待处理 61 / 共 61 项, 已记录影响 效果未知, and the
   backend-legal **取消** button.
3. Run the harness Worker; temporary Storage really loses the directory.
4. Click 加载更多逐项结果 (a continuation that already reports the terminal Task).
5. The same open panel reaches 已完成, 成功 61 / 失败 0 / 待处理 0 / 共 61 项,
   已核实完成, 已无待处理条目; **取消/请求暂停 disappear** and the unavailable
   explanation appears; no item still says 排队中; the previously queued items
   now read 已完成变更; 已显示 61 / 61 项逐项证据 after the final page.
6. Reading converged the panel: mutation count unchanged (still one), the
   directory is gone, no second admission or control POST.

Verified against pre-fix code with the same test file and a rebuilt artifact:
**both kinds fail** at `阶段` (`排队等待 Worker` vs `已完成`) after 21 s, i.e. the
new case reproduces B's blocker rather than passing on both revisions.
Artifacts (ignored, local): `.git/validation-evidence/task46.2-live-snapshot/`
with `{resource,media}-live-operation-{queued,converged,converged-facts,converged-desktop}.png`
and `pre-fix-repro/`.

### Web coverage added

- `LibraryFileOperationsDialog.test.tsx` (12 → 14): a `live` operation whose
  durable facts change between reads — queued 阶段/计数/效果未知 with 请求暂停 →
  the next continuation reports terminal → the same mounted page converges to
  已完成 / 成功 2 / 待处理 0 / 已核实完成 / 已无待处理条目, the pause control
  disappears, the unavailable-control explanation appears and both loaded items
  read 已完成变更 with 已显示 2 / 2; and a unit case proving
  `isOlderLibraryOperationSnapshot` refuses a terminal→in-flight or shrinking
  answer while another Task is never treated as older.

### Known risks and remaining Slice outcomes

- Convergence relies on the 2 s snapshot poll plus the bounded re-read pair; a
  provisional 逐项证据仍早于该操作的当前状态 hint is shown while a re-read is in
  flight (and stays if it does not answer), rather than silently mixing states.
  That state is simply "read again"; it never executes anything.
- Three native cases failed in this round's full-spec run and in an independent
  pre-fix run of the same cases at the same file state: MediaLibrary
  confirms-once/renames and ResourceLibrary lost-admission Delete, all at the
  `RowActionMenu` Shift+F10 `menuitem` click (detached/unstable element). Already
  attributed to Base in the previous round and outside this Task's surface; they
  are reported, not retried or relaxed. The other 19 cases pass, including the
  six new/repaired operation-status journeys.
- Provided the fix stays inside RO-3; RO-2 manual admission, RO-4
  organizing-only Task Center population and RO-5 Automation semantics remain
  outstanding and untouched. Center list/count/Attention populations were not
  narrowed.
- No schema or packaging change: Docker/deployment proof is not applicable to
  this round's inputs and is not claimed.

### Workspace

Branch `main`, implementation checkpoint `2541d0c8`. Pre-existing
`docs/pics/操作与任务.png` deletion, untracked reference images/logs/OS files and
`web/test-results*` are preserved and not committed. Native screenshots/traces
are held under the ignored `.git/validation-evidence/task46.2-live-snapshot/`.
No push, no publication.

**Testing wall time:** the affected static/Python/Web/native commands above,
including the three pre-fix reproduction runs, total roughly 12 minutes of
subprocess time inside a round of about 45 minutes elapsed, i.e. below the 30%
ceiling. No deliberate waiting; full T4 regression remains B-owned.

Full acceptance, full regression and any PASS/FIX decision remain B-owned.
