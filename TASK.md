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
Candidate: <to be filled after checkpoint>
Range:     ad25d4379e6e13a6b21ea6ed1bbdb4dde84084ee..<Head>
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

**FIX REQUIRED — 2026-10-25.** Independently reviewed the complete
`6072f50d5b2e5268c35d6729290512d1ae986104..eda531317659f3107b602239d47f683545908cf0`
range (24 changed files), including implementation `aa4b6d2be78a497158c5e84301d42f6dec76637d`
and its report-only handoff. Task Base/goal/scope/T4 remain unchanged. No next Task or Slice closure.

### Required corrections — same Task

1. **B46.2-01 / P1 — local inspection loses per-item results and failure/effect evidence.**
   `library_file_operations.py::_row_document` and
   `service_api.py::_library_file_operation_detail` return aggregates plus lifecycle actions;
   `LibraryFileOperationsDialog.tsx::OperationDetail` renders those aggregates, but no item/result
   list or bounded failure explanation. The backend never supplies the top-level `durableState`
   or `nextAction` read by this component, and it does not render lifecycle `knownEffects` or
   `effectCertainty`. Independently reproduced for **both** library kinds: admit a real two-file
   Delete, refuse one actual LocalStorage Delete through the existing test fault boundary, run
   the real Worker. Durable items are one success and one failure, the successful source is gone,
   and the failed source remains; local detail exposes neither item's evidence. Closing/restarting
   leaves only totals, so the operator cannot identify the failed file or its safe next step.
   Reuse the existing kind-scoped Delete/transfer projections and bounded item/result/checkpoint
   readers inside this local modal. Keep complete paging and exact scope; display each item's
   source/target, stage, known/uncertain effects, bounded refusal and permitted next action without
   requiring Task Center. Reconcile skipped/cancelled/settled counts with actual terminal items.
   Add real mixed/uncertain and close/reopen evidence for both kinds, preserving successful and
   uncertain non-replay and backend-only control authority.
2. **B46.2-02 / P1 — ordinary deep links do not reliably reach exact local inspection.**
   The sole `GET /api/v1/files/operation-origin/{taskId}` dispatch hardcodes
   `media_library=False`; both frontend kind reads use that same URL. A real MediaLibrary command
   therefore returns `matched=false / not_ordinary_file_work` for both reads. Native browser
   reproduction of its existing Task detail shows zero “返回发起它的库文件页” links.
   Also, `destination-model.ts`'s Files/MediaLibrary authentication continuation omits the new
   `operationTaskId`: opening an exact existing local-work URL and reconnecting drops that
   parameter and opens no inspection modal. Resolve the actual persisted kind in a supported
   backend contract and normalize it consistently; preserve bounded exact operation selection
   across authentication/refresh. Verify existing Task and selected-run entry paths for both kinds,
   including foreign/stale/denied context, without a guessed library or generic organizing recovery.
3. **B46.2-03 / P1 — historical origin is replaced by today's enabled-library selection.**
   Both pages pass `activeLibraryId` to the modal, derived only from current eligible libraries
   with a first-library fallback. Independent reproduction uses supported Add/Edit commands for
   an unreferenced ResourceLibrary, a real page-created folder, then successful disable. Its
   historical backend list remains HTTP 200 / total 1. Reopening the originating page and header
   status instead requests `/resource-libraries/destination/file-operations` and displays
   “Destination / 共 0 条记录”. It cannot find the known operation. Preserve a separate exact
   historical inspection scope and a bounded local way to select/reopen known origins when the
   live library is disabled/removed/unavailable; do not bind status to a live browse fallback or
   require re-enabling it. Cover both kinds and missing Active/current library, including reload/
   restart with absent browser hints; historical pin/control restrictions must remain truthful.

Implement these as one complete correction to the existing local status journey. Extend current
tests/harnesses, not a new process framework. Developer runs failing/new/directly affected checks
and relevant static checks; B retains full T4 and native acceptance ownership. The Required Tests
commands above now use the existing direct-files harness config for that spec; inventory/center
specs keep their own existing config. This corrects the planning command mismatch, not product scope.

### Independent evidence and outstanding gates

Local evidence: `.git/validation-evidence/eda53131/b46.2-review/` (ignored, local only). It includes
the isolated reproduction script/log, command logs, native screenshots and the disabled-origin
1536×1024 screenshot; all work used temporary roots/example configuration, no user media or secrets.

- Governance and complete-range whitespace check: PASS/clean.
- `.venv/bin/python -m unittest tests.test_library_file_operation_history`: **13 passed**.
- `npm run build` (cwd `web/`): PASS; produced `index-C7I0gcBz.js` / `index-YjIez-Bj.css`.
- `npx playwright test --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts -g 'reopens its own durable operation status' --output=../.git/validation-evidence/eda53131/b46.2-review/native-artifacts`
  (cwd `web/`): **2 passed**, real API/repository reopen and Worker effects. These prove successful
  operation enumeration, not the failed/mixed/uncertain/control/old-link acceptance still missing.
  Inspected both kinds' captured detail/narrow screenshots; the existing first detail capture is
  760×900, so it is not evidence of the required 1536×1024 detail state.
- Supported command/API fault reproduction confirms B46.2-01 for both kinds and B46.2-02's media
  resolver failure. Native browser checks confirm the missing media return link, dropped operation
  parameter on reconnect and B46.2-03's foreign-library empty history. The first attempt to disable
  a referenced source was correctly refused (422); the unreferenced library disable succeeded
  (200). Intermediate locator timeouts remain in raw logs; final captures show the actual state.
- Test/build/probe subprocess times total **under 65 seconds** (overlap counted conservatively
  twice); recorded review accounting began 05:56:47 UTC, before these runs. Testing is below 50%
  of this review round. No deliberate waiting or redundant full-suite runs.
- Early FIX REQUIRED: B's full Python/Web/default E2E, full native regression, packaging/installed
  smoke and remaining safety/acceptance gates are **pending**, not waived or inherited from the
  Developer report. Deployment/package/schema inputs did not change: Docker/security-image and
  schema-upgrade proofs are not newly applicable for this candidate. No claim is made about the
  Developer's reported parent keyboard flake; it was not independently rerun this round.

### All Slice outcomes reevaluated

RO-1 retains accepted Task46.1 coverage; no new shared action-color change was made here. RO-3 is
partly delivered (durable scoped index, local entry and successful reopen), but incomplete for the
three required corrections above. RO-2 early organizing admission, RO-4 organizing-only center/
four-type population and RO-5 Automation remain incomplete and outside this Task. Preserve the
existing dirty/untracked user artifacts. Only this B-owned Task review is checkpointed; A-owned
Slice/Roadmap/Progress boundaries and their stale first-Task pointers remain unchanged.
