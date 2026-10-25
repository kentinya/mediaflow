# Task 46.2 — Durable ordinary-file status on both library pages

Authority: committed [Slice46](SLICE.md) RO-3, AC-4 and the local ordinary-work portions of
AC-7/8; [Development Workflow](docs/development-workflow.md). Read the
[Developer experience](docs/agent-experience/developer-implementation-role.md) before implementation.

```text
Task ID: 46.2
Parent Slice: 46
Status: READY FOR B REVIEW
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
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/direct-files.python.spec.ts
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
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/direct-files.python.spec.ts tests/e2e/operations-inventory.python.spec.ts tests/e2e/operations-task-center-visual.python.spec.ts
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

## Developer Completion Report

```text
Candidate: aa4b6d2be78a497158c5e84301d42f6dec76637d
Range:     6072f50d5b2e5268c35d6729290512d1ae986104..aa4b6d2b  (Task Base..Head)
Status:    READY FOR B REVIEW — no self-PASS, no push, no publication
```

### Changed behavior

- **Durable per-library ordinary work index.** New
  `mediaflow/domain/file_operation_history.py` names the closed ordinary command
  families (`files_direct_command`, `files_transfer`, `files_delete` plus their
  `media_` twins), their derived `<family>:<identity>` continuations, the exact
  origin identity every admitted TaskItem already records and the operator
  wording of one persisted operation value (including the `WRITE` ambiguity,
  resolved only by the recorded display scope). `SQLiteTaskRepository`
  `library_file_operations_window` / `library_file_operation_display` decide
  membership *before* paging from that durable evidence only — never a Result
  path, display label, filename, Job link or today's Active — and return a
  count/page-consistent, both-direction, bounded page.
- **Bounded application read.** `mediaflow/application/library_file_operations.py`
  is a kind-pinned, side-effect-free reader: it resolves no library, opens no
  Storage, calls no Provider. `window`, `detail` and `resolve` refuse a foreign
  kind, foreign library, mixed-origin or unknown Task rather than rebind it; the
  detail adds the backend-computed lifecycle projection for the exact Task and
  principal, so a control exists only when the backend advertises it.
- **API routes** on both kinds: `GET /resource-libraries/{id}/file-operations` and
  `/media-libraries/{id}/file-operations`, `.../files/operations/{taskId}` and
  `GET /files/operation-origin/{taskId}`. All are READ-permission durable reads
  that skip the Active refresh, so a removed, disabled, root-changed or
  currently-unavailable library keeps its history; the page cursor is bound to
  kind + library + principal through the shared scoped cursor kind
  `library_file_operations`. Audit routes are templated (no Task identity).
- **Web.** New strict kind-bound entity (`entities/library/file-operations`) and
  client reads refuse a foreign kind/library document; the shared
  `LibraryFileOperationsDialog` reuses `ModalDialog` (centered, Escape, focus
  return), lists only this library's operations, keeps independent selection,
  shows stage/source/destination/per-item results and offers only advertised
  pause/cancel/resume. Both headers now have **当前页面操作状态** immediately left
  of Add with the Add button's exact class; reading never depends on the Add
  permission or a resolvable Storage. Ordinary Delete and Copy/Move results now
  offer local inspection instead of a Task Center link, and an existing
  ordinary Task/run deep link resolves to its proven library page or keeps
  bounded guidance. Delete's request-ID reconciliation is unchanged.

### Actual commands and results (this round)

Every command below was run in this round from the stated cwd; nothing is quoted
from an earlier round.

| Area | Command | Result |
|---|---|---|
| Governance | `python3 scripts/check_governance.py` | PASS (before and after the checkpoint) |
| Whitespace | `git diff --check` | clean |
| Python formatting/lint | `.venv/bin/ruff format --check mediaflow tests scripts`; `.venv/bin/ruff check mediaflow tests scripts` | 357 formatted, 0 findings |
| Python compile | `.venv/bin/python -m compileall -q mediaflow tests scripts` | OK |
| New module | `.venv/bin/python -m unittest tests.test_library_file_operation_history` | 13 tests, OK |
| Affected Python | `.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_media_library_direct_commands` | 88 tests, OK |
| Affected Python | `.venv/bin/python -m unittest tests.test_direct_file_transfers.TransferApiTests` | 7 tests, OK |
| Affected Python | `.venv/bin/python -m unittest tests.test_media_library_transfers.MediaLibraryTransferTests.test_equal_ids_cannot_exchange_transfer_authority tests...test_media_transfer_pause_cancel_and_resume_stay_durable tests...test_media_transfer_progress_survives_api_restart_during_active_outage` | 3 tests, OK |
| Shared read | `.venv/bin/python -m unittest tests.test_operations_run_inventory tests.test_operations_run_detail` | 76 tests, OK |
| Python full | `.venv/bin/python -m unittest discover -s tests -t .` | 2818 tests, OK (7 skipped) — run after the affected set, incidental to this round's 30% budget |
| Web focused | `npm run test -- run` (cwd `web/`) | 87 files / 1245 tests, passed |
| Web static | `npm run typecheck`; `npm run lint`; `npm run format:check`; `npm run build` | all clean |
| Web default E2E | `npm run test:e2e` (cwd `web/`) | 242 passed |
| Native real Python | `npx playwright test --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` | 10 passed, 2 failed |

### Native E2E: exact failures, and the parent-reproduction evidence

The two failures are pre-existing headless-macOS keyboard flakes in the
`Shift+F10` row-menu helper (`renameThroughNativePage`), not this Task's
behavior:

- `MediaLibrary Files confirms once, waits for the real Worker, and refreshes`
- `MediaLibrary Files renames a file and directory through real Python commands`

Reproduced at the planning HEAD (`0e3b50e6`, clean worktree, same built artifact
and harness) with `npx playwright test --config=playwright.direct-files.python.config.ts
tests/e2e/direct-files.python.spec.ts -g "MediaLibrary Files renames a file"` →
same 30 s timeout at the same `menuitem "重命名"` click. The identical Resource
MediaLibrary Delete/Copy-Move journeys, the two new `...reopens its own durable
operation status` journeys and all Resource journeys pass. The new journeys
deliberately use toolbar/footer controls rather than the flaky keyboard menu.

Note: `--config=playwright.python.config.ts` (the config named in Required Tests)
starts the operations-inventory harness, which does not mount the direct-files
fixtures, so `/__harness__/register-files-worker` answers 503 there for *every*
case including unchanged ones. The direct-files spec's own committed config is
`playwright.direct-files.python.config.ts`; that is what was run. This is a
fingerprint mismatch in the Task text, not a product defect — B should decide
whether to fix the command or the doc.

### Durable-reopen evidence produced by the new native journeys

For each kind: real creation through the toolbar → real Worker-owned batch
Delete of two dedicated files → status dialog lists both → exact detail read
(source, destination, stage, `成功 1 / 失败 0`, no invented control for a
terminal creation) → narrow 390×844 and desktop 1536×1024 screenshots with no
horizontal overflow → close → `POST /__harness__/restart` (real repository + API
reopen over the same SQLite file) → full page reload with no remembered Task ID
→ the same operations are readable again and the authorized list `total` is
unchanged. `tests/test_library_file_operation_history.py` additionally proves
reopen from a fresh `SQLiteTaskRepository` + `MediaFlowApi` with **no** Active
binding at all.

### Added test coverage (success / invalid / conflict / failure / edge)

Python (13): both kinds keep their own operations with kind-specific identity
fields; equal IDs cannot exchange history/detail; unknown library reads empty and
is never rebound; mixed ordinary work pages correctly with a real organizing Job
in the same runtime and the shared run inventory is not narrowed; an ordinary
Delete joins the population; the cursor is refused across kind/library/principal
and accepted for its own scope; invalid query/limit/Task identities fail closed;
a repository without the reader answers one bounded 503; a viewer reads and the
read mutates no Task/item/Result; history survives a real Active successor that
removes the library; a pre-change row without display evidence stays readable
with no invented scope; reopen from a fresh repository/API with no Active
binding; deep-link resolution matches or explains; reads never touch Storage
(`MutationFreeStorage`).

Web: model normalization (foreign kind/library/split identity/unknown
operation/negative counts/mutation claim/mismatched Task), state copy (never
claims completion for a non-successful terminal Task), client URL and
normalization contracts, and the mounted-page dialog journeys (entry placement
and style, multiple operations, exact detail, only advertised controls, empty,
403 read error with real retry, reopen with no hint, unavailable control
projection).

### Known risks and remaining Slice outcomes

- The `Shift+F10` keyboard-menu flake above is pre-existing and outside this
  Task's surface; it remains visible rather than being retried or relaxed.
- The Task's `playwright.python.config.ts` command cannot serve the direct-files
  fixtures (harness mismatch described above). B owns the call on correcting the
  Task text; no product behavior depends on it.
- `OperationDetail` polls every 2 s only while the selected operation is
  non-terminal; a terminal selection performs a single read. No polling admits
  commands.
- The dialog lists the current page's operations; older pages are reachable by
  explicit paging, not by an infinite scroll. If B expects a first-preview plus
  census hybrid, that is a follow-up within RO-3.
- Centre list/count/Attention population narrowing (RO-4), RO-2 early manual
  admission, RO-5 Automation changes and the organizing-only Task Center are
  **not** delivered here and remain outstanding Slice outcomes.
- Pre-existing untracked artifacts (`.DS_Store`, `*.log`, `15`,
  `output/imagegen/*.zip`, `web/test-results-*`), the `docs/pics/操作与任务.png`
  deletion and all untracked reference images were preserved and are **not**
  committed. `mediaflow/.DS_Store` was accidentally staged and then unstaged.

Full acceptance, regression ownership and any PASS/FIX decision are B-owned.

## B Review Result

Pending implementation and independent Base..Head review. No product test or acceptance is claimed
by this planning checkpoint. After PASS, reevaluate all Slice outcomes before selecting more work.
