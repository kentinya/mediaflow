# Task 38.7 — Files/MediaLibrary 统一单项右键菜单与文件夹打开交互

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [Slice Contract](SLICE.md).

```text
Task ID: 38.7
Parent Slice: 38
Status: READY FOR B REVIEW
Task Base: f888cb76ca09780374562305f29b1c1aa8bcdc56
Difficulty: Medium
Test Level: T2
Planner / Reviewer: A acting for B
```

## Goal

Give ResourceLibrary Files and MediaLibrary one coherent single-entry command surface: remove the
persistent operation column, expose applicable commands through an accessible controlled context
menu, and make folder left click open directly without a duplicate inline Open button. This advances
Slice 38 RO-1/RO-2/RO-5 while preserving all delivered command safety and recovery behavior.

## Why This Task Exists

Both browse tables currently devote a persistent column to row buttons and overflow controls. Folder
rows duplicate navigation through an inline `打开` button even though direct left-click navigation is
the intended primary interaction. The A-approved correction consolidates already-delivered commands
into one predictable entry menu shared by Files and MediaLibrary without changing APIs, authority,
mutation semantics or batch workflows. This is the largest coherent Web interaction unit: table
structure, list/grid behavior, context-menu accessibility and regression coverage must change
together.

## Implementation Scope

```text
Shared entry interaction/presentation
  → five-column Files and MediaLibrary tables
  → list/grid controlled context menu
  → folder direct left-click navigation
  → existing dialogs/commands and selection bars
  → component and browser regression coverage
```

- Remove the `操作` header/cell and every persistent row-level Open/action/overflow button from the
  ResourceLibrary and MediaLibrary list tables. Keep exactly
  `选择 | 名称 | 类型 | 大小 | 修改时间` with stable responsive column geometry.
- Add or extend one shared controlled entry context-menu component used by both pages and suitable
  list/grid entries. Open it from mouse right-click, the Context Menu key, `Shift+F10`, and an
  equivalent touch/focus interaction that does not restore a persistent operation column.
- Folder menus expose applicable `打开`, `重命名`, `复制`, `移动`, `删除`. Files menus expose
  applicable `打开/编辑`, `重命名`, `复制`, `移动`, `删除`; ResourceLibrary eligible media may also
  expose `整理`, while MediaLibrary never exposes Organize.
- A left click on a folder name, icon or non-checkbox/non-menu row area opens that exact folder.
  Checkbox interaction only changes selection and must not navigate. File left click must not admit
  a mutation or silently invent a new action.
- Reuse the current dialogs, version evidence, RBAC/capability filtering, stale/conflict handling,
  destructive confirmation and OrganizerExecutor-backed requests. Opening/dismissing a menu is a
  zero-mutation UI action and must not issue command requests.
- Preserve bounded multi-selection and existing batch action bars, including ResourceLibrary batch
  Organize and both pages' batch Copy/Move/Delete. A context-menu command targets the invoked entry;
  it must not silently reinterpret an existing multi-selection as a batch command.
- Provide deterministic menu placement, viewport confinement, outside-click/Escape dismissal,
  keyboard traversal, focus return, accessible labels and usable narrow-screen behavior.
- Keep route state, directory tree, breadcrumbs, paging, Add/remove library configuration, disabled
  filtering and backend/API payloads unchanged.

## Acceptance Criteria

- [ ] Both browse tables render exactly five headers in this order:
      `选择 | 名称 | 类型 | 大小 | 修改时间`; no `操作` header, inline `打开`, primary Organize row
      button or row overflow button remains.
- [ ] Right-clicking an eligible list/grid entry opens a menu anchored to that entry without
      navigating, selecting unrelated entries or sending a mutation; Context Menu key, `Shift+F10`
      and the touch/focus equivalent reach the same command set.
- [ ] Folder left click opens the exact folder from name/icon/non-checkbox row space; checkbox click
      changes selection only. Folder menu retains applicable Open/Rename/Copy/Move/Delete, including
      root protection and existing capability/stale checks.
- [ ] File menus expose only currently supported operations. Supported text uses the existing
      Open/Edit flow; ResourceLibrary eligible media retains Organize; MediaLibrary exposes no
      Organize/Scan/Preview action.
- [ ] Invoking Rename/Copy/Move/Delete/Edit/Organize from the menu reaches the same existing dialogs,
      permissions, evidence, confirmation, durable results and recovery behavior as before; no
      command is weakened, silently retried or moved outside OrganizerExecutor.
- [ ] Batch selection bars and independent per-item/batch behavior remain functional and are not
      implicitly triggered by a single-entry context-menu command.
- [ ] Menus dismiss on Escape/outside click, remain viewport-confined, restore useful focus and work
      at supported narrow widths without text/control overlap.
- [ ] The checkpoint changes only this interaction unit and its tests; no reference image,
      configuration schema, API contract, Storage binding or unrelated page is changed.
- [ ] Required regression and repository quality/security gates pass with actual totals/skips and no
      deleted tests, weakened assertions or hidden skips.

## Required Tests

- Add/update focused component tests for both list and grid: five-column structure, folder left-click,
  checkbox isolation, menu contents by entry/page capability, keyboard/context/touch entry,
  dismissal/focus and zero-request menu open.
- `npm --prefix web run test -- --run`
- `npm --prefix web run build`
- `npm --prefix web run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts`
- `npm --prefix web run test:e2e`
- `npm --prefix web run typecheck`
- `npm --prefix web run lint`
- `npm --prefix web run format:check`
- `python3 scripts/check_governance.py`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m unittest discover -s tests`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python scripts/docker_release_security_smoke_test.py`
- `git diff --check`

## Non-goals

- New file commands, batch Rename, Upload/Download, arbitrary media editing, MediaLibrary Organize,
  cross-kind transfer or transfer Replace mode.
- API, persistence, managed configuration, Storage provider, RBAC, evidence, concurrency or mutation
  behavior changes.
- Removing existing confirmation/recovery dialogs, weakening stale/conflict checks or making
  right-click/touch/keyboard menu opening itself select, mutate or submit work.
- Redesigning library cards, selected-library context, directory tree, toolbar, selection footer,
  paging, Add drawers, shell or supplied reference images.
- Declaring Slice 38 PASS/CLOSED; B review and Slice-final validation remain required.

## Developer Completion Report

### Changed Files

- `web/src/features/library/RowActionMenu.tsx`
- `web/src/features/library/StorageFilesPage.tsx`
- `web/src/features/library/MediaLibraryFilesPage.tsx`
- `web/src/features/library/StorageFilesPage.test.tsx`
- `web/src/features/library/MediaLibraryFilesPage.test.tsx`
- `web/src/features/library/MediaLibraryCommands.test.tsx`
- `web/src/features/library/MediaLibraryTransfers.test.tsx`
- `web/src/shared/ui/styles.css`
- `web/tests/e2e/library-file-detail.spec.ts`
- `web/tests/e2e/library-files.spec.ts`
- `web/tests/e2e/manual-operations.spec.ts`
- `web/tests/e2e/medialib-files.spec.ts`
- `web/tests/e2e/medialib-commands.spec.ts`
- `web/tests/e2e/medialib-transfers.spec.ts`
- `TASK.md`

### Implemented

- Removed the persistent `操作` column and row Open/Organize/overflow controls from both five-column
  browse tables while retaining stable responsive column geometry.
- Added one shared portal-backed entry menu opened from right-click, Context Menu, `Shift+F10` or
  focused Enter in both list and grid views, with viewport confinement, first-item focus, arrow-key
  traversal, Escape/outside dismissal and focus restoration.
- Made folder name/icon and non-control row space open the exact folder; checkbox interaction remains
  selection-only and file left-click does not create a command.
- Preserved the existing single-entry dialogs and command callbacks for Open/Edit, Rename, Copy,
  Move, Delete and ResourceLibrary Organize; MediaLibrary exposes no Organize command and batch bars
  retain their independent selection semantics.
- Updated component and built-artifact browser coverage for five-column structure, direct folder
  navigation, controlled menu entry and the existing command/recovery journeys.
- Correction: row/grid Enter handling now opens the menu only when the entry anchor itself owns the
  key event. Enter on a nested folder button retains native button activation and enters the exact
  folder on both ResourceLibrary and MediaLibrary pages; Context Menu and `Shift+F10` row entry are
  unchanged.
- Correction: added component and built-artifact regressions for both routes proving folder-button
  Enter navigation and the absence of an unintended `条目操作` menu.

### Tests and Results

- `npm --prefix web run test -- --run` — PASS (43 files, 603 tests).
- `npm --prefix web run build` — PASS (Vite emitted the existing chunk-size warning).
- `npm --prefix web run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts --grep "focused .* folder activation"` — PASS (2/2; B blocker reproduction).
- `npm --prefix web run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-files.spec.ts tests/e2e/medialib-commands.spec.ts` — PASS (60/60).
- `npm --prefix web run test:e2e` — PASS (170/170).
- `npm --prefix web run typecheck` — PASS.
- `npm --prefix web run lint` — PASS.
- `npm --prefix web run format:check` — PASS.
- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS (314 files).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m unittest discover -s tests` — PASS (1791 tests, 7 skipped).
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python scripts/docker_release_security_smoke_test.py` — PASS.
- `git diff --check` — PASS.

### Decisions

- `RowActionMenu` remains the shared controlled portal boundary; it accepts either an invoking-entry
  rectangle or pointer coordinates so keyboard and pointer entry use identical commands.
- Entry rows/grid cells are the focusable menu anchors. This removes persistent action chrome while
  providing an explicit focus interaction and reliable focus return after dismissal.
- Single-entry menu commands always receive the invoked row path directly; existing multi-selection
  is left untouched and is used only by the existing batch footer.
- Nested interactive controls retain their own Enter behavior; only an Enter targeted at the
  focusable row/grid anchor is treated as the focus-equivalent menu command.

### Remaining In-Slice Work

- No additional Task-local work is known; Slice completeness remains for B/A review.

### Risks / Deviations

- The worktree contained a pre-existing modified `docs/pics/文件页.png`; it was preserved and excluded
  from both Task commits.
- Python regression passed with the suite's existing `ResourceWarning` messages for unclosed test
  SQLite connections. No production Python code changed.
- The first full E2E run exposed three stale assertions/selectors for the removed action column and
  inline controls; they were updated, the focused 30-test reproduction passed, and the complete
  168-test suite then passed.
- During the correction, the first new ResourceLibrary browser assertion incorrectly expected route
  query state instead of the page's established live-listing/visible-breadcrumb proof. The folder
  had entered correctly; the assertion was corrected, then the focused, specified and full E2E
  gates passed.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 1ae0531212c1c5c585cc2970c03f9996c1eba949
```

## B Review Result

```text
Reviewed: f888cb76ca09780374562305f29b1c1aa8bcdc56..cefc76186c076d6c1919fb39ea3d1d83ea6f8dde
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Folder keyboard activation is broken on both `/ui-v2/resourcelib/files` and
  `/ui-v2/medialib/files`: in the built artifact, focus a traversable folder-name button and press
  `Enter`; the URL remains at the current directory and an `条目操作` menu opens instead of entering
  the folder. This is production-reachable through the supported table journey and violates the
  Task's folder left-click/direct activation and keyboard-accessible entry interaction criteria
  (and the Slice RO-1/RO-2 browse continuity). Update the row keyboard handler so an Enter generated
  by a nested interactive control (folder name/button or checkbox) is not reinterpreted as a row-menu
  request, while Context Menu/`Shift+F10` on the row itself still opens the menu; add a regression
  covering both routes or the shared interaction boundary and rerun the affected browser/component
  tests.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
