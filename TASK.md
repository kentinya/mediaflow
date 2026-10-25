# Task 46.2 — Durable ordinary-file status on both library pages

Authority: committed [Slice46](SLICE.md) RO-3, AC-4 and the local ordinary-work portions of
AC-7/8; [Development Workflow](docs/development-workflow.md). Read the
[Developer experience](docs/agent-experience/developer-implementation-role.md) before implementation.

```text
Task ID: 46.2
Parent Slice: 46
Status: FIX REQUIRED
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

- [ ] Both headers have the required adjacent, same-style status entry. Its centered modal works
  with mouse/keyboard at desktop 1536×1024 and narrow 390×844, including focus restoration,
  empty/loading/read-error/401/403 states. Viewing has no new work/media/Provider/Storage effects.
- [ ] All seven ordinary operations show real outcomes locally. Multiple operations are independently
  selectable; switching entries/libraries does not overwrite siblings or mix either library kind.
  No normal ordinary-command result/recovery guidance requires Task Center.
- [ ] Backend list/detail/counts/cursors use the same exact authorized ordinary scope before paging.
  Mixed organizing/notification/unknown work never leaks into it. Multiple pages and per-item results
  remain reachable; same-ID opposite-kind, foreign-library and foreign-principal cursor/hint/selection
  tampering is refused rather than rendered empty or rebound. Existing allowed read policy is preserved.
- [ ] Closing/reloading/reconnecting and reopening API/SQLite retains multiple operations, including
  supported work admitted before this change and operations whose browser hints are absent. Changed/
  missing Active/root/library cannot overwrite the historical origin/pin; unprovable context explains
  restricted inspection/control. Browser state is neither authority nor the sole recovery index.
- [ ] Actual queued/running/paused Copy/Move/Delete and mixed-success batches expose backend-legal
  controls and independent results. Safe continuation affects only known-safe remaining work;
  partial/uncertain/error/display-failure states retain their factual effects and legal next action.
  Read-only viewers and stale/concurrent controls cannot change media or expand authority.
- [ ] Lost Delete admission and unknown command/control responses reconcile without automatic replay,
  guessed identity or false success. Successful/uncertain items do not replay after close/restart or
  duplicate control attempts. Cross-Storage Move verification failure preserves source.
- [ ] Ordinary Task/run deep links reopen exact local inspection or bounded refusal with no mutation;
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
Reviewed Task range: 6072f50d5b2e5268c35d6729290512d1ae986104..79f67b4d1670cedd94371978b0b0e8cfa97c11da
Implementation: 884c88f75d17c3d2e9960f055280a241a6bc8158
Decision: FIX REQUIRED — 2026-10-25
Task blocker: B46.2-01 / P1 (live operation snapshot freezes across item pages)
B46.2-04: corrected (first detail read-error recovery)
Slice Required Outcomes / Surfaces all satisfied: NO
Next: SAME TASK FIX LOOP
```

Independent review covers the complete 28-file Task Base..Head range, including original scope,
history, controls and deep-link paths, plus the current repair. The report-only successor
`884c88f7..79f67b4d` changes only `TASK.md`; executable review/test inputs match the implementation.
Task Base, Goal, Scope, Difficulty and T4 remain unchanged. Previous review/guidance is retained
in Git at `8fa3fd0c:TASK.md`. This checkpoint changes only B-owned `TASK.md`.

### Corrections verified

- **B46.2-01, whole-operation backend aggregate:** the real 121-item directory Delete with one
  actual Storage refusal now returns the same `uncertain` certainty, durable state, next action
  and totals (success 119 / failed 2 / total 121) on all three pages for both library kinds.
  The refused `batch/file-117.txt` is the only remaining file. Detail reads leave Task/item/Result
  rows unchanged. The independent history module and both native large-directory/reopen cases
  pass. Complete item access, paused folder Move child effects and mixed batches also pass.
  This corrects static page-dependent aggregation; the live update defect below remains open.
- **B46.2-04:** both native pages now show the bounded error and explicit **重新读取该操作**
  after an aborted first detail GET. Restoring transport and rereading retrieves the same real
  operation without mutation. Inspected the actual failure screenshot; the loading-only branch
  is corrected.
- **B46.2-02 / -03:** exact-kind deep-link and historical-origin causes remain corrected on
  complete-range inspection. Disabled-origin/reopen native cases pass. Remaining comprehensive
  link/permission/control acceptance and the full T4 gate are not declared complete.

### Required correction — B46.2-01 / P1

**A newer terminal item page stops polling while the selected operation retains an older snapshot.**

Real operator trigger, reproduced on both ResourceLibrary and MediaLibrary:

1. Through the existing file page, confirm Delete of the existing temporary 120-file directory
   (121 admitted items including the directory). Close Delete progress, open **当前页面操作状态**
   and select this queued operation before Worker executes. The first detail page reports
   `pending`, success 0 / pending 121, `unknown` effects.
2. Run the existing harness Worker against that admitted command; it completes the real Delete.
   Before the next normal poll, click **加载更多逐项结果** in the same open dialog.
3. That cursor GET reports `completed`, `terminal=true`, success 121 / pending 0 and
   `verified_complete`. The selected panel nevertheless remains **排队等待 Worker**,
   **成功 0 / 待处理 121**, **效果未知**, and its earlier loaded items remain queued.
   Observe another 4.5 seconds (more than two configured polling intervals): there are still
   only the two detail requests. No closing/reopening or fabricated product response is involved.

Cause: `LibraryFileOperationsDialog.tsx::OperationDetail` stops polling from the **last** page's
`terminal` (lines 260–266), but derives `detail`, `lifecycle` and aggregate from the **first** page
(lines 270–284, 367–371), and concatenates stale earlier item pages. Global summaries are independent
of item-page scope **at the same durable state**; snapshots read before and after real execution
need not be identical. The `884c88f7` change (2026-10-25 17:18:06 +08:00) newly pins aggregate effects
to page one. First-page stage/lifecycle and last-page polling termination already existed in
`1fa4bf55`; their combination now also permanently freezes the repaired aggregate. This is an
unmet RO-3 / AC-4 live progress/effect/recovery result, not a request for another Task or new authority.

### Developer repair guide — same Task

1. 修正 `OperationDetail` 的快照更新关系：阶段、全操作计数、效果确定性、下一步和
   lifecycle/version 必须来自一致且会更新的操作快照。保留后端全操作折叠与精确作用域分页；
   不要将“与页范围无关”解释成“第一页数据永不变化”。新页读到较新终态时，不能一边据此停止
   轮询，一边继续展示旧快照/旧控制；并发读取也不能让旧响应覆盖已知的新状态。
2. 同步已加载逐项证据，再结束更新。采用现有查询/重读能力协调刷新或失效旧页，使先前排队的
   项目最终显示真实结果；不要只换 aggregate 为末页而留下旧 stage、lifecycle 或 item。
   保留逐项完整可达、已有失败读取提示、所选操作/库身份和只读重读语义，不新增执行重试、
   自动重放或全局中心，也不为修复引入通用进程工具。
3. 扩展现有 dialog/query 测试：第一页 pending → 后端完成 → continuation 返回 terminal，
   断言不关闭弹窗即可收敛到终态、正确全量计数/效果/下一步、最新合法控制与已加载 item。
   覆盖一次读取跨越状态变化，以及旧响应不能回退已知终态；静止操作跨页聚合仍应一致。
4. 扩展 `direct-files.python.spec.ts` 中两类库的真实目录 Delete：通过现有页面提交，先打开
   pending 明细，再用既有 harness Worker 完成，加载更多并检查同一弹窗自动更新。核对真实
   临时文件效果、所有页可达、没有额外 admission/control mutation；不能只测试 Worker 完成后
   才打开详情。保留部分失败/不确定、暂停 Move、安全继续、首次读取失败与 reopen 回归。

Developer 只运行新增、修改、直接受影响测试及相关静态检查，提交连贯 checkpoint 并报告实际
结果后交 **READY FOR B REVIEW**。完整回归、原生证据和未完成验收仍由 B 负责。

### Independent acceptance this round

Evidence: `.git/validation-evidence/79f67b4d/b46.2-review/` (ignored, local only). It contains raw logs,
`paging_probe.py`, `live_paging_probe.mjs`, both kinds' live-stale JSON/screenshots and native traces.
Inspected the live-stale screenshots and corrected read-error UI. Probes use existing commands,
actual page controls/routes and existing test-only Worker hooks, temporary SQLite/Storage roots;
no invented product entry, impossible seeded row, user media or production service is used.

| Command / cwd | Actual result |
| --- | --- |
| `python3 scripts/check_governance.py`; complete-range `git diff --check` | PASS / clean |
| `.venv/bin/python -m unittest tests.test_library_file_operation_history` | 21 passed, 2.294s (`history-tests.log`) |
| `PYTHONPATH=. .venv/bin/python .git/validation-evidence/79f67b4d/b46.2-review/paging_probe.py` | Both kinds: all three pages retain global uncertainty and 119/2/121 totals; actual retained file and zero-write reads verified |
| `node .git/validation-evidence/79f67b4d/b46.2-review/live_paging_probe.mjs` | Both kinds reproduce the persistent live-state defect above (`live-paging-probe.log`, JSON and PNG); reproduction success is not product PASS |
| `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .` | 387 formatted / PASS |
| `.venv/bin/python -m compileall -q mediaflow tests scripts`; `.venv/bin/python -m pip check`; both documented example config validations; forbidden-dependency search | PASS; no FFmpeg/FFprobe match |
| `npm run typecheck`; `npm run lint`; `npm run format:check`; `npm run build` (`web/`) | PASS; `index-BYlwlmy9.js` / `index-BFNi4meT.css`; existing chunk-size warning |
| `npm run test -- run` (`web/`) | 87 files / 1258 passed, 111.95s (`web-full.log`); existing jsdom scrollTo notices |
| `npm run test:e2e -- --output=<evidence>/default-e2e-artifacts` (`web/`) | 242 passed, 2.0m (`default-e2e.log`) |
| `npx playwright test --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts --output=<evidence>/native-artifacts` (`web/`) | 19 passed / 1 failed, 1.3m (`native.log`); failure described below |
| `npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts --workers=1 --output=<evidence>/operations-native-artifacts-serial` (`web/`) | 42 passed / 1 failed, 2.2m (`operations-native.log`); failure described below |
| `.venv/bin/python -m unittest discover -s tests` | Interrupted on confirmed blocker, no final totals or PASS (`python-full.log`); full Python remains pending |
| `.venv/bin/python -m pip wheel . --no-deps -w <evidence>/wheels`; `.venv/bin/python scripts/wheel_smoke_test.py <exact-wheel>` | Both exit 0 (`wheel-build.log`, `wheel-smoke.log`); installed consumers run outside source; wheel SHA-256 `1fb58c1b550d0dea13263734e604f7dc4f17b63aa0660684a3e1660c127a5bf5` |

`<evidence>` denotes the directory above; native `--output` paths were relative to `web/` as
`../.git/validation-evidence/79f67b4d/b46.2-review/...`. Packaging/deployment/schema/dependency inputs
are unchanged; Docker deployment/restart/security proof is **not applicable**, not claimed passed.

Actual failures and limits remain visible:

- Direct-files native MediaLibrary Rename fails at the menuitem click (spec line 322), detached/
  unstable element before the command is sent. Independently archived original Task Base `6072f50d`,
  built its own assets, and ran its own ten-case spec against an isolated harness: **8 passed / 2
  failed**, including the same row-menu detachment/instability mechanism in ResourceLibrary Rename
  and MediaLibrary confirmation (`base-native.log`, `base-native-artifacts/`, `base-build.log`).
  `RowActionMenu.tsx` is unchanged in Base..Head. This supports an existing menu issue; it does not
  turn the candidate's failed case into PASS. No assertions/retries/timeouts were weakened.
- Shared real-Python inventory/visual run: all 41 inventory tests and the first visual case pass;
  the final creation-summary journey cannot find **选择 Three.2003.mkv** at line 233 after preceding
  tests mutate the shared fixture. Base attribution is not established. The gate is **not passed**;
  B must verify that journey with an isolated fixture on the corrected candidate. This is not an
  additional speculative product blocker or a new Developer process-tool assignment.
- Two earlier shared-harness invocations were stopped (one had an extra spec with another port;
  one overlapped fixture-mutating files). Their retained logs are not acceptance evidence. Their
  elapsed time is included in test accounting; successful totals above refer to the serial run.
- Full Python was stopped at 09:45:46 UTC under workflow §6 early FIX REQUIRED, with no complete
  result. Remaining Task-link/permission/stale-control coverage and all missing T4 safety/full
  gates remain **pending**. They are not waived or inherited from Developer/another candidate.

Test/build/probe wall time is conservatively under six minutes, counting overlapping execution
once, including the interrupted/abandoned runs and independent Base build/run. Conservative elapsed
review accounting starts at 09:39:27 UTC after initial reading; code/evidence reconciliation and
Task writing continue after all test processes stop. Testing remains below 50% of this round;
there is no deliberate waiting or reduction of the required PASS coverage.

### All Slice outcomes reevaluated

RO-1 retains accepted Task46.1 coverage; additive modal styles preserve the shared palette on
inspection. RO-3 now has complete paged item access, whole-operation backend effects, paused child
evidence and explicit first-read failure recovery, but remains **incomplete** for live progress,
effect and legal-control snapshot freshness. RO-2 early manual admission, RO-4 organizing-only
views/population and RO-5 Automation semantics remain incomplete and outside Task46.2. Keep the
same Task; no next Task or Slice closure. A-owned Slice/Roadmap/Progress boundaries and stale
first-Task pointers are unchanged. Branch `main`, reviewed candidate `79f67b4d`; the pre-existing
`docs/pics/操作与任务.png` deletion and all untracked/private/reference/log/test artifacts are
preserved. No product code change, push or publication is part of this B checkpoint.


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
