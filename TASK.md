# Task 37.9 — Files Refresh Truthful State and Focused Presentation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.9
Parent Slice: 37
Status: PLANNED
Task Base: 65d2a5c641b5f0d61983b21b5f1286cc5254c6bc
Difficulty: Medium
Test Level: T2
Planner / Reviewer: B
```

## Goal

Restore a truthful Files refresh journey for live ResourceLibrary browsing. When an operator
deletes or moves a directory outside the Web page, then clicks `刷新`, the refreshed Files view
must stop presenting that directory as a current directory-tree entry or as a selected stale
target. In the same focused Web boundary, remove the Files-page presentation of the business
concepts `识别结果` and `整理状态` while retaining the explicit `整理` action and its existing
server-authoritative continuation. This advances Slice 37 Required Outcomes RO-3, RO-5, RO-9 and
RO-11. The related CI/test quality correction is already complete and is a required green baseline
for this remaining Web implementation.

## Why This Task Exists

The V2 Files API already reads the configured ResourceLibrary's live Storage and does not use
FileIndex as its browsing authority. The Web page currently passes the query's `refetch()` directly
to the refresh button, but retains `knownDirectoryPaths` and `visitedDirectories`. The directory
tree builder merges those old paths back into the refreshed model, so a path such as
`source/电影/SSH` can remain visible after it no longer exists in Storage.

This is a P1 user-visible state and recovery defect: the operator is told that the page reflects
current source state, but a visible navigation target can lead to a path that is gone. The quality
test contract and Python matrix timeout correction were completed before the Web implementation
checkpoint: GitHub quality run `#118` passed on commit
`320d8437a8872f7a08ee84295a0f900a39f84a7d`, including Python 3.11/3.12/3.13 and wheel smoke.
The remaining implementation unit is therefore one focused Web-state correction plus focused Web
regression coverage, including the Files presentation boundary. No backend authority, Storage
behavior, recognition/metadata pipeline or production fencing needs to change.

## Current Developer Baseline

The following CI work is already complete and must be preserved, not repeated or redesigned:

- The two Local directory replacement tests branch on stable directory identity and preserve the
  accepted residual-risk semantics without skips.
- `.github/workflows/quality.yml` keeps Python 3.11, 3.12 and 3.13, retains `fail-fast: false`,
  and uses a 30-minute timeout only for the Python test matrix; the wheel job remains 10 minutes.
- GitHub quality run `#118` is green on `320d8437a8872f7a08ee84295a0f900a39f84a7d`.
- The active-Task release-quality command inventory is present and the release-security policy test
  passes.

## User Journey

```text
Goal:
  See the current contents and navigable directories of one enabled ResourceLibrary.
Entry:
  V2 Files at /ui-v2/library/files with a selected ResourceLibrary.
Visible state:
  ResourceLibrary card, current directory listing, directory tree, breadcrumbs and selection. The
  Files page does not display `识别结果` or `整理状态`; the explicit `整理` action remains
  available.
Action:
  The operator changes the source outside MediaFlow, then clicks 刷新.
Success:
  The current listing and directory tree are derived from the new live Storage read; a removed
  directory is absent and no stale selection remains. The same ResourceLibrary/path context is
  preserved when the current directory still exists.
Failure:
  If the current directory disappeared or the read fails, the existing bounded Files failure state
  identifies the read failure and does not fabricate rows or silently navigate to another library.
Recovery:
  The operator can use the existing retry or 返回资源库根目录 action. Retrying repeats only the
  read; no Scan, FileIndex operation, Storage mutation or automatic organize replay is started.
```

## Implementation Scope

- Update the Files page refresh handling in `web/src/features/library/StorageFilesPage.tsx` so a
  successful refresh cannot re-render directory paths retained only in local tree state.
- Update the Files page presentation in `web/src/features/library/StorageFilesPage.tsx` so the
  information banner, table headers/cells and row status presentation do not expose `识别结果`
  or `整理状态`. Keep `organizeEligible`, the `整理` action, single-item Preview and bounded
  batch continuation intact.
- Update `web/src/shared/ui/styles.css` for the six-column Files table and remove status-only
  presentation styles that become unused. Do not remove generic action or enabled-state styles.
- Reconcile or clear `knownDirectoryPaths`, `visitedDirectories` and stale selection state at the
  refresh boundary. The implementation may use a small page-local helper or a result reconciliation
  effect, but must preserve the selected ResourceLibrary and current path when the refreshed read
  remains valid.
- Preserve the existing live query and API contract in
  `web/src/features/library/storage-files-query.ts` and `web/src/shared/api/api-client.ts`.
  Refresh must continue to issue the same bounded GET request; do not add a cache-busting API field
  or a second browsing authority.
- Preserve the existing error boundary and recovery behavior when the current directory is missing,
  invalid, unauthorized or temporarily unavailable.
- Add focused Web regression coverage in `web/src/features/library/StorageFilesPage.test.tsx` for:
  - a previously discovered nested directory that is absent from the post-refresh live listing;
  - removal of any stale selection/tree presentation after refresh;
  - preservation of ResourceLibrary/path context for a still-valid refresh;
  - GET-only behavior with no `/file-index` request.
- Extend or add the focused Files Playwright coverage in
  `web/tests/e2e/library-files.spec.ts` when the fake-server fixture can express the external
  removal. The browser assertion must cover the visible directory-tree outcome, not only a query
  invocation.
- Update the focused Files table assertions in
  `web/tests/e2e/library-files.spec.ts` and `web/tests/e2e/library-file-detail.spec.ts` to assert
  that `识别结果` and `整理状态` are absent as visible page concepts, while the `整理` action and
  the remaining physical-file columns remain present.
- Reconcile `docs/file-page-visual-spec.md` with the current Slice presentation boundary before
  Task completion; the old two-column wording must not remain as the active visual contract.
- Keep the change limited to the Files Web state/presentation, its focused tests and the visual
  specification. Do not alter the Python Storage browser, FileIndex repository, API routes,
  mutation services, OrganizerExecutor production code or configuration authority.

## Acceptance Criteria

- [ ] After an external deletion of a previously discovered ResourceLibrary directory, clicking
      `刷新` causes the directory tree to stop showing that path once the live read succeeds.
- [ ] The refreshed table/grid contains only entries returned by the current live Storage read;
      no stale local path is presented as a navigable or selectable current entry.
- [ ] Refresh cannot leave a selection referring to an entry that the refreshed listing no longer
      contains. Clearing the current selection during refresh is acceptable if it is the simplest
      fail-closed behavior.
- [ ] When the current ResourceLibrary and directory still exist, refresh keeps that context and
      does not silently switch libraries, invoke Scan/Preview, or route through FileIndex.
- [ ] When the current directory no longer exists or the read fails, the existing bounded error
      and recovery state remains truthful: no fabricated row/tree entry, no automatic mutation and
      no automatic retry loop.
- [ ] The Files page does not render `识别结果` or `整理状态` in the information banner, table
      headers, row cells or status pills.
- [ ] The Files table retains the physical/action columns
      `选择 | 名称 | 类型 | 大小 | 修改时间 | 操作`, and the `整理` action remains available
      for eligible entries and continues into the existing zero-mutation Preview path.
- [ ] The API/FileIndex/recognition/metadata/organize data contracts remain unchanged; the
      presentation removal does not remove backend authority or result synchronization.
- [ ] The refresh request remains the existing authenticated bounded GET request, and focused
      tests prove there is no POST/PUT/DELETE request and no `/file-index` request for this journey.
- [ ] Existing Files navigation, pagination, search, direct file commands, Organize continuation,
      ResourceLibrary activation and non-Files routes remain behaviorally unchanged.
- [ ] The assigned T2 tests and quality checks pass with actual evidence.
- [x] The two accepted Local directory replacement tests pass on the stable-identity branch
      semantics, with non-reused identity still failing closed and reused identity reported
      truthfully without a skip.
- [x] The GitHub quality workflow completes Python 3.11, 3.12 and 3.13 without timeout
      cancellation, and the dependent wheel job is eligible to run; quality run `#118` is green.
- [x] `TASK.md` contains the repository-required release-quality command inventory and the release
      security policy test passes for the active Task.
- [ ] The implementation checkpoint contains only Task 37.9 work; the pre-existing
      `docs/pics/文件页.png` change remains untouched and uncommitted.

## Required Tests

Run from the repository root unless noted otherwise:

1. `python3 scripts/check_governance.py`
2. `cd web && npm run test -- --run src/features/library/StorageFilesPage.test.tsx`
3. `cd web && npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/library-file-detail.spec.ts`
4. `cd web && npm run typecheck`
5. `cd web && npm run lint`
6. `cd web && npm run format:check`
7. `git diff --check`

The repository's active-Task release-quality policy also requires this exact command inventory to
remain documented in this file:

```text
python3 scripts/check_governance.py
scripts/docker_release_security_smoke_test.py
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q mediaflow tests scripts
```

The Developer must report actual pass/fail counts and any unavailable browser/runtime prerequisite.
No production Storage, FileIndex, TMDB, SMB, OpenList, S3 or R2 service is required.

## Non-goals

- Any Python/API/Storage/FileIndex/OrganizerExecutor production implementation change.
- A new scan, index synchronization job, cache layer, polling loop or refresh endpoint.
- ResourceLibrary configuration, Active snapshot, RBAC, authentication or route redesign.
- New direct file commands, OrganizerExecutor behavior, conflict policy or mutation capability.
- Changing the existing current-directory error/recovery semantics beyond removing stale local
  presentation.
- Reworking the shared shell or unrelated V2 routes. The scoped removal of Files recognition/status
  feedback is included in this Task.
- Removing recognition, metadata, FileIndex or organize fields from API/domain contracts, or
  changing OrganizerExecutor/result synchronization behavior.
- Full Python regression or unrelated legacy test cleanup unless a focused failure demonstrates a
  Task 37.9 regression.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING | PASS | FIX REQUIRED
Slice Required Outcomes all satisfied: PENDING | YES | NO
Next: PENDING | SAME TASK FIX LOOP | NEXT TASK | SLICE READY FOR A REVIEW
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
