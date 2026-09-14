# Task 37.1 — Files Reference Composition and Bounded Browse

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.1
Parent Slice: 37
Status: FIX REQUIRED
Task Base: d48937485834502eaa186f29e710a4b44e7110fe
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## B Contract Reconciliation — 2026-09-14

The A-owned Slice Contract was materially expanded and checkpointed at
`63056c3b1e743f71611eb17d5420061a9160a030` while this Task was in its fix loop. Task ID, Task Base
and the read-only Files browse/selection Goal remain unchanged. Task 37.1 now owns the coherent
frontend presentation boundary needed by that Goal: the replacement shared V2 shell plus the exact
Files read-only composition inside it. It does not absorb the new Storage-mutation commands.

The A checkpoint is an interleaved governance checkpoint, not a moved Task Base and not a Developer
PASS. Developer continues the same Task, produces a new correction checkpoint after the current
Head, updates the completion report with the actual cumulative state, and does not amend or hide the
earlier rejected checkpoint.

## Goal

Complete the Files page's reference-aligned, read-only browse and selection behavior: an
authorized operator can enter `/ui-v2/library/files`, understand the selected ResourceLibrary,
navigate its Storage-relative directories, inspect the live file table, refresh or change
presentation, select and clear bounded files, and recover from bounded read failures without
leaving the page or fabricating file state.

Under the revised Contract, “reference-aligned” includes the shared light rail/top bar that frames
Files; preserving the former dark shell cannot satisfy this Goal. This Task advances Slice Required
Outcomes **RO-1 Pixel-exact reference fidelity**, **RO-2 Shared V2 shell replacement**, **RO-3 Exact
Files composition**, **RO-5 Storage-authoritative Files data**, **RO-9 Actionable recovery** and
**RO-11 Test reconciliation**. It establishes the frontend base needed by later ResourceLibrary
activation, common file-management and organize-result synchronization Tasks.

## Why This Task Exists

The current route and Storage API boundary exist, and the rejected checkpoint introduced much of
the page-local Files composition. The current shared AppShell still renders the former dark
horizontal `MEDIAFLOW / Operator workspace` frame, however, so the full screenshot remains far from
the canonical reference. The current selection helper also conflates general row selection with
backend organize eligibility: it derives eligibility from file type and ignores
`entry.selectable`, so an entry the backend excludes can still reach Preview.

The replacement shared shell and Files read-only page are one coupled, reviewable frontend boundary:
the canonical full-page screenshot cannot be accepted while Files is nested inside the old shell,
and a Files-only shell would violate the parent Contract. ResourceLibrary activation, common
file-management mutations/transfers and terminal FileIndex synchronization cross separate
application/Storage/persistence boundaries and remain later vertical Tasks.

## Implementation Scope

```text
Shared AppShell/navigation → Files route/page → read-only view models → deterministic browser evidence → tests
```

- Replace the Files route's generic presentation with the exact page-local composition defined by
  [`docs/file-page-visual-spec.md`](docs/file-page-visual-spec.md) and the unchanged
  [`docs/pics/文件页.png`](docs/pics/文件页.png): Chinese labels, search bar, ResourceLibrary
  summary, information banner, directory tree, breadcrumb, toolbar, table, row values/status
  presentation, selection footer and pagination.
- Replace the former dark horizontal AppShell with the canonical light left rail/top bar through the
  single shared shell used by all V2 routes. Preserve route identity, active navigation,
  memory-only authentication, deep-link continuation, 401/403 recovery, narrow navigation and
  non-Files business behavior. Do not create a Files-only shell or retain a nested old-shell frame.
- Continue to read physical entries from the existing authenticated, ResourceLibrary-relative
  Storage endpoint. Directory navigation, breadcrumb navigation, refresh, pagination and
  presentation switching must use bounded query state and reset incompatible selection/cursor
  state.
- Keep one bounded general row-selection model local to Files and expose a clear selected count,
  selected-row styling, select-all and clear-selection action. General selection may include a live
  file or directory for later file-management commands and grants no mutation authority by itself.
  Derive a separate organize-eligible subset from backend `entry.selectable === true`; only that
  subset may affect organize eligibility/counts or enter Preview. A selected but organize-ineligible
  entry stays available to future command-specific capability checks rather than losing its
  checkbox. Reads, navigation and selection remain zero-mutation and create no work.
- Render bounded business/status text only when it is present in the existing safe response
  projection; do not add FileIndex lookup, raw FileIndex identifiers, fingerprints, occurrence
  IDs, claims or authority fields to the page. Physical rows and paths remain Storage-authoritative.
- Preserve the existing single-file server-authoritative Preview continuation where it already
  exists; this Task may adapt its page-local trigger to the new composition but must not move
  source identity or execution authority into the browser.
- Add deterministic fake-server fixtures and browser/component coverage for the full reference
  success state, shared-shell route/auth/responsive behavior, general selection versus
  backend-authoritative organize eligibility, and the page-local loading, empty, malformed,
  unavailable, unauthorized/forbidden and invalid-path recovery states required by the Contract.
- The `添加资源库` drawer's save/activation behavior, backend mutation, terminal Organize
  FileIndex synchronization and all common file-management commands are outside this Task.

## Acceptance Criteria

- [ ] `/ui-v2/library/files` retains the existing API-principal authentication and authorization
      boundary, and an authorized principal reaches the Files page without CLI, raw token transfer
      or implementation-identifier ceremony.
- [ ] At the controlled `1536 x 1024` browser viewport after fonts/assets load, the full Files
      success screenshot matches `docs/pics/文件页.png` pixel for pixel with zero unexplained
      difference. The canonical reference image is not modified.
- [ ] The former dark horizontal shell is absent. One shared reference-aligned light left rail/top
      bar frames Files and all other V2 routes while preserving existing auth, deep-link, active
      route, 401/403, narrow-menu and non-Files business behavior.
- [ ] The visible labels, row values, table status/action presentation, selected state and
      control order are sourced from the visual specification rather than the existing generic
      English card/list copy. Text fits its containers without overlap at the reference viewport
      and remains usable at the existing supported responsive viewport.
- [ ] The operator can select an enabled ResourceLibrary, open a traversable directory, use a
      breadcrumb or root control to return, refresh the current directory, switch list/grid
      presentation, select and clear files, and advance through bounded pagination. Incompatible
      path, cursor and selection state is cleared when the scope changes.
- [ ] General row selection is independent from organize eligibility: an entry with
      `entry.selectable: false` remains selectable for future file-management commands, but is
      excluded from the organize-eligible subset, organize counts/actions and every Preview request.
      Mixed and wholly ineligible selections explain the eligible result instead of silently
      granting or fabricating organize authority.
- [ ] Future Rename/Copy/Move/Delete/Edit/Upload/Download Tasks can attach their own backend
      permission/capability decisions to the general selection model; `entry.selectable` is not
      reused as a delete or other file-operation permission.
- [ ] Physical file and directory rows come from the live Storage/ResourceLibrary-scoped response.
      The implementation does not enumerate from FileIndex, use FileIndex for source identity or
      path validation, or display raw FileIndex authority fields. Any displayed business/status
      feedback is bounded and display-only.
- [ ] Loading, empty, unauthorized, forbidden, unavailable, malformed-response and invalid-path
      states preserve Files page context, explain the affected read and provide a safe next action
      such as retry or return to the ResourceLibrary root. No failure state fabricates reference
      rows or automatically replays an uncertain mutation.
- [ ] Every Files read, refresh, directory navigation, presentation switch and selection action is
      zero-side-effect; the browser evidence proves that these actions issue no Storage mutation,
      task/job creation, Provider request or organize execution request.
- [ ] Existing single-file Preview, when invoked from Files, still submits only the
      ResourceLibrary identity and relative path to the existing server-authoritative flow; this
      Task introduces no new mutation authority or fallback from unsupported operations.
- [ ] Focused tests cover success, invalid/malformed input, empty data, read failures, selection
      reset, general selection versus backend-authoritative organize eligibility, shared-shell
      route/auth behavior and important navigation edge cases; the assigned T3 commands pass.
- [ ] The Developer correction after the documented interleaved A checkpoint contains only Task
      37.1 shell/Files work, focused test/evidence changes and the completion-report update. The
      report names the actual new Head and reports the complete current results rather than the old
      rejected checkpoint.

## Required Tests

- `python3 scripts/check_governance.py`
- `cd web && npm run format:check`
- `cd web && npm run typecheck`
- `cd web && npm run lint`
- `cd web && npm run test -- --run src/shared/api/library-api.test.ts src/entities/library/system-status.test.ts src/entities/library/storage-files.test.ts src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts`
- `cd web && npm run build`
- `cd web && npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/deep-link.spec.ts`
- `git diff --check`
- A deterministic Playwright screenshot at `1536 x 1024` with the canonical image left unchanged;
  report the comparison method and any unexplained visual difference in the Developer Completion
  Report.

No production SMB/OpenList/S3/TMDB service, production credential, real media directory or
external provider is permitted for these tests.

## Non-goals

- Non-Files page-body/business redesign. Shared shell chrome and only the layout adaptation required
  to keep existing pages functional are in scope.
- ResourceLibrary creation, validation, checked activation, runtime rebinding or persistence
  mutation.
- New API authentication, identity, session, RBAC, execution-token or security model.
- New Storage adapters/capabilities, schema migrations, persistence rewrites, FFprobe/FFmpeg,
  content probing or provider calls.
- Terminal Organize-result persistence or FileIndex synchronization; those require a later
  cross-layer Task.
- General Configuration, Dashboard, Operations, Review, Notifications or Settings business-feature
  changes, and any V1 `/ui` change.
- Create Folder/Text File, rename, copy, move, delete, edit, upload, download, destination picker,
  transfer progress, arbitrary host-path browsing, batch Preview or silent fallback. Those common
  file-management journeys belong to later Slice 37 Tasks.
- Optional copy polish, unrelated refactors, test-only probes and P2/P3 cleanup.

## Developer Completion Report

### Changed Files

- `TASK.md`
- `web/src/entities/library/storage-files.ts`
- `web/src/entities/library/storage-files.test.ts`
- `web/src/features/library/StorageFilesPage.tsx`
- `web/src/shared/auth/AuthControls.tsx`
- `web/src/shared/navigation/destination-model.ts`
- `web/src/shared/ui/AppShell.tsx`
- `web/src/shared/ui/Icons.tsx`
- `web/src/shared/ui/styles.css`
- `web/tests/fake-server.mjs`
- `web/tests/e2e/deep-link.spec.ts`
- `web/tests/e2e/library-files.spec.ts`

### Implemented

- Replaced the former dark horizontal frame at the shared `AppShell` layer with the canonical
  light rail/top bar, Chinese navigation labels, route-compatible accessible names, account
  control, shared Files search slot and responsive narrow-menu behavior. Existing route, auth,
  deep-link, 401/403 and V1 handoff behavior remains covered.
- Replaced the generic Files presentation with the reference-aligned header, ResourceLibrary
  summary, banner, directory tree, breadcrumbs, live Storage table, status/action cells, selection
  footer, pagination, list/grid controls and page-local add-library drawer presentation. The
  drawer remains presentation-only; save/activation is deferred by this Task.
- Kept physical rows and Preview identity ResourceLibrary/Storage-authoritative. Bounded optional
  `fileCount`, `totalSize`, `recognitionResult` and `businessStatus` remain display-only; no
  FileIndex enumeration or authority fields enter the page.
- Separated general row selection from organize eligibility. Every live row keeps a checkbox for
  future command-specific file operations, while organize counts/actions and Preview paths use
  only entries with `entry.selectable === true`. Mixed and wholly ineligible selections explain
  the admitted subset and never send an ineligible path.
- Preserved safe URL-relative path validation, bounded directory discovery/navigation, cursor
  history, query/scope selection reset, read-only refresh, empty/failure/malformed recovery and
  the existing single-file server-bound Preview trigger.
- Added deterministic `source`/`source-storage` fixtures and browser coverage for the reference
  success state, shared-shell route/auth/responsive behavior, selection authority, pagination,
  empty, unauthorized/forbidden, unavailable, malformed and invalid-path states.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `cd web && npm run format:check` — PASS.
- `cd web && npm run typecheck` — PASS.
- `cd web && npm run lint` — PASS.
- `cd web && npm run test -- --run src/shared/api/library-api.test.ts src/entities/library/system-status.test.ts src/entities/library/storage-files.test.ts src/shared/ui/AppShell.test.tsx src/shared/navigation/destination-model.test.ts` — PASS, 5 files / 61 tests.
- `cd web && npm run build` — PASS (Vite emitted the existing large-chunk warning).
- `cd web && npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/deep-link.spec.ts` — PASS, 25 tests.
- `git diff --check` — PASS.
- Playwright Canvas `ImageData` exact RGBA comparison of `docs/pics/文件页.png` and
  `web/test-results/files-success-1536x1024.png` — FAIL / comparison executed; both are
  1536x1024, with 1,414,673 of 1,572,864 pixels differing (999,667 with maximum channel
  difference >= 2; 460,395 >= 5). The canonical image was not modified.

### Decisions

- `shellDestinations` owns the visible reference IA while preserving the existing route contract
  and accessible route names used by the current V2 journeys. All V2 pages continue to consume the
  one shared `AppShell`; Files search state is supplied through its shared top-bar slot.
- Inline deterministic SVG icons and CSS thumbnail treatments keep the shell and page self-contained
  without external services or untracked private assets.
- General selection is intentionally broader than organize admission. The UI explains the
  organize-eligible subset, and the existing server-bound Preview call receives only admitted
  ResourceLibrary-relative paths.
- Business/status cells use only optional bounded response projection fields. Physical paths, rows
  and Preview identity remain Storage/ResourceLibrary-authoritative.
- Presentation, browsing, refresh, navigation, search, selection and drawer interaction remain
  zero-mutation. The add-library `保存` control stays disabled until the separate
  validation/activation Task supplies its backend behavior.
- The fake server keeps the legacy `resources` fixture for unrelated routes and adds a separate
  deterministic `source` fixture for the approved reference state.

### Remaining In-Slice Work

- ResourceLibrary creation, validation, checked activation and runtime rebinding are outside this
  Task. Terminal Organize-result synchronization to FileIndex is also deferred as specified.
- Common file-management commands and transfer progress remain deferred to later Slice 37 Tasks.

### Risks / Deviations

- The exact screenshot comparison remains non-zero. The repository contains no source assets for
  the canonical photo thumbnails, so the implementation uses deterministic CSS/inline-SVG
  treatments; font and icon rasterization and small reference shadow/color differences also remain.
  This is reported as FAIL rather than waived or presented as pixel parity; the canonical image is
  unchanged.
- The interleaved A Contract checkpoint at `63056c3b1e743f71611eb17d5420061a9160a030` remains
  outside the correction commit. No unrelated files, private configuration, credentials or
  `config/alist.json` were staged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 4358eef2c35a3535651951bd3312f52d3bbbbd3c
```

## B Review Result

```text
Reviewed: d48937485834502eaa186f29e710a4b44e7110fe..63056c3b1e743f71611eb17d5420061a9160a030
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- The current shared `AppShell.tsx` still renders the obsolete dark horizontal `MEDIAFLOW /
  Operator workspace` shell, and the rejected completion report records 1,555,583 differing pixels
  against the canonical `1536 x 1024` image. The revised Slice makes the reference light left rail/
  top bar part of this Task's visual boundary. Replace the shell once at the shared AppShell layer,
  align the full Files success state to zero unexplained pixel difference, and prove existing V2
  route/auth/deep-link/responsive behavior remains functional rather than creating a Files-only
  shell.
- `StorageFilesPage.tsx` conflates general selection with organize eligibility:
  `isFileSelectable` derives the decision from regular-file/symlink type and ignores the backend
  `entry.selectable` value. Preserve a general checkbox/selection set for later Delete/Copy/Move
  and other command-specific capability checks, but derive the organize-eligible subset strictly
  from `entry.selectable === true`. Prove that mixed and ineligible selections never send an
  ineligible path to Preview or count it as organizable, while the same entry remains generally
  selectable for future file-management actions.
- The Developer Completion Report and checkpoint evidence still describe the superseded frozen-shell
  scope and old rejected Head `e9f3c08...`. After implementing the two blockers above, update the
  report to the actual cumulative behavior and rerun every reconciled T3 command from the new Head;
  do not report the interleaved A Contract checkpoint as Developer completion.
