# Task 37.1 — Files Reference Composition and Bounded Browse

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.1
Parent Slice: 37
Status: READY FOR B REVIEW
Task Base: d48937485834502eaa186f29e710a4b44e7110fe
Difficulty: Medium
Test Level: T3
Planner / Reviewer: B
```

## Goal

Complete the Files page's reference-aligned, read-only browse and selection behavior: an
authorized operator can enter `/ui-v2/library/files`, understand the selected ResourceLibrary,
navigate its Storage-relative directories, inspect the live file table, refresh or change
presentation, select and clear bounded files, and recover from bounded read failures without
leaving the page or fabricating file state.

This Task advances Slice Required Outcomes **RO-1 Reference fidelity**, **RO-2 Exact Files
composition**, **RO-5 Files data and status** by preserving the Storage-authoritative physical
listing, and **RO-7 Actionable recovery**. It establishes the visual and interaction base needed by
the later ResourceLibrary Save/activation and organize-result synchronization Tasks.

## Why This Task Exists

The current route and Storage API boundary already exist, but `StorageFilesPage` still renders a
generic English card/list view. It does not provide the approved Files hierarchy: page header and
search affordance, ResourceLibrary summary, information banner, directory tree, breadcrumb,
toolbar, table columns, selected-row state, selection footer, pagination or the reference
presentation controls. Its loading, empty and error states also do not preserve the reference page
context.

A page-local visual and browse baseline is the largest reasonable first implementation unit because
it can be reviewed independently against the supplied `1536 x 1024` reference and uses the
existing authenticated ResourceLibrary-scoped Storage read. ResourceLibrary persistence/activation
and terminal FileIndex synchronization cross additional application and persistence boundaries and
must be planned as separate vertical behavior rather than hidden in a visual task.

## Implementation Scope

```text
Web route/page → page-local styles and view models → deterministic fake API/browser evidence → tests
```

- Replace the Files route's generic presentation with the exact page-local composition defined by
  [`docs/file-page-visual-spec.md`](docs/file-page-visual-spec.md) and the unchanged
  [`docs/pics/文件页.png`](docs/pics/文件页.png): Chinese labels, search bar, ResourceLibrary
  summary, information banner, directory tree, breadcrumb, toolbar, table, row values/status
  presentation, selection footer and pagination.
- Keep the shared shell, navigation semantics, authentication boundary and all non-Files routes
  unchanged. Any CSS needed for this Task must be scoped to the Files surface or demonstrably
  preserve existing frozen-page behavior.
- Continue to read physical entries from the existing authenticated, ResourceLibrary-relative
  Storage endpoint. Directory navigation, breadcrumb navigation, refresh, pagination and
  presentation switching must use bounded query state and reset incompatible selection/cursor
  state.
- Keep selection local to the page and expose a clear selected count, selected-row styling and
  clear-selection action. Reads, refreshes, navigation, presentation changes and selection must
  remain zero-mutation and must not create Tasks, Jobs, Provider requests or organize work.
- Render bounded business/status text only when it is present in the existing safe response
  projection; do not add FileIndex lookup, raw FileIndex identifiers, fingerprints, occurrence
  IDs, claims or authority fields to the page. Physical rows and paths remain Storage-authoritative.
- Preserve the existing single-file server-authoritative Preview continuation where it already
  exists; this Task may adapt its page-local trigger to the new composition but must not move
  source identity or execution authority into the browser.
- Add deterministic fake-server fixtures and browser/component coverage for the success state and
  the page-local loading, empty, malformed, unavailable, unauthorized/forbidden and invalid-path
  recovery states required by the parent Contract.
- The `添加资源库` drawer's save/activation behavior, backend mutation, terminal Organize
  FileIndex synchronization and unrelated page redesign are outside this Task.

## Acceptance Criteria

- [ ] `/ui-v2/library/files` retains the existing API-principal authentication and authorization
      boundary, and an authorized principal reaches the Files page without CLI, raw token transfer
      or implementation-identifier ceremony.
- [ ] At the controlled `1536 x 1024` browser viewport, the Files success state has the reference
      page hierarchy and order: shell context, Files header/search, ResourceLibrary summary,
      banner, directory tree, breadcrumb, toolbar, table, selected-row/selection footer and
      pagination. The canonical reference image is not modified.
- [ ] The visible labels, row values, table status/action presentation, selected state and
      control order are sourced from the visual specification rather than the existing generic
      English card/list copy. Text fits its containers without overlap at the reference viewport
      and remains usable at the existing supported responsive viewport.
- [ ] The operator can select an enabled ResourceLibrary, open a traversable directory, use a
      breadcrumb or root control to return, refresh the current directory, switch list/grid
      presentation, select and clear files, and advance through bounded pagination. Incompatible
      path, cursor and selection state is cleared when the scope changes.
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
      reset and important navigation edge cases; the assigned T3 test commands pass.
- [ ] The checkpoint contains only Task 37.1 Files-page work, focused test/evidence changes and
      the required Task completion report.

## Required Tests

- `python3 scripts/check_governance.py`
- `cd web && npm run format:check`
- `cd web && npm run typecheck`
- `cd web && npm run lint`
- `cd web && npm run test -- --run src/shared/api/library-api.test.ts src/entities/library/storage-files.test.ts`
- `cd web && npm run test:e2e -- tests/e2e/library-files.spec.ts`
- `git diff --check`
- A deterministic Playwright screenshot at `1536 x 1024` with the canonical image left unchanged;
  report the comparison method and any unexplained visual difference in the Developer Completion
  Report.

No production SMB/OpenList/S3/TMDB service, production credential, real media directory or
external provider is permitted for these tests.

## Non-goals

- Work outside the V2 Files route and its page-local browse/selection presentation.
- ResourceLibrary creation, validation, checked activation, runtime rebinding or persistence
  mutation.
- New API authentication, identity, session, RBAC, execution-token or security model.
- New Storage adapters/capabilities, schema migrations, persistence rewrites, FFprobe/FFmpeg,
  content probing or provider calls.
- Terminal Organize-result persistence or FileIndex synchronization; those require a later
  cross-layer Task.
- General Configuration, Dashboard, Operations, Review, Notifications, Settings, V1 `/ui` or
  shared-shell redesign.
- Upload, download, edit, delete, content preview, arbitrary host-path browsing, batch Preview or
  silent fallback from unsupported operations.
- Optional copy polish, unrelated refactors, test-only probes and P2/P3 cleanup.

## Developer Completion Report

### Changed Files

- `web/src/features/library/StorageFilesPage.tsx`
- `web/src/entities/library/storage-files.ts`
- `web/src/entities/library/storage-files.test.ts`
- `web/src/shared/ui/styles.css`
- `web/tests/fake-server.mjs`
- `web/tests/e2e/library-files.spec.ts`

### Implemented

- Replaced the generic Files presentation with the Chinese reference-aligned header, search,
  ResourceLibrary summary, information banner, directory tree, breadcrumbs, table, row status and
  action presentation, selection footer, pagination, list/grid controls and page-local add-library
  drawer presentation.
- Kept physical rows ResourceLibrary/Storage-authoritative. Added only bounded optional
  `fileCount`, `totalSize`, `recognitionResult` and `businessStatus` display projections; no
  FileIndex enumeration or authority fields enter the page.
- Added safe URL-relative path validation, bounded directory discovery/navigation, cursor history,
  selection reset on scope changes, read-only refresh, empty/failure/malformed recovery states and
  the existing single-file server-bound Preview trigger.
- Added deterministic `source`/`source-storage` fixtures and browser coverage for success,
  selection, navigation, pagination, empty, unauthorized/forbidden, unavailable, malformed and
  invalid-path states. Drawer save/activation remains intentionally presentation-only per this
  Task's non-goal.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `cd web && npm run format:check` — PASS.
- `cd web && npm run typecheck` — PASS.
- `cd web && npm run lint` — PASS.
- `cd web && npm run test -- --run src/shared/api/library-api.test.ts src/entities/library/storage-files.test.ts` — PASS, 2 files / 31 tests.
- `cd web && npm run build` — PASS (Vite emitted the existing large-chunk warning).
- `cd web && npm run test:e2e -- tests/e2e/library-files.spec.ts` — PASS, 11 tests.
- `git diff --check` — PASS.
- Playwright Canvas pixel comparison of `docs/pics/文件页.png` and
  `web/test-results/files-success-1536x1024.png` — PASS / comparison executed; both are
  1536x1024, with 1,555,583 differing pixels. The canonical image was not modified.

### Decisions

- Business/status cells use only optional bounded response projection fields. Physical paths,
  rows and Preview identity remain Storage/ResourceLibrary-authoritative.
- Presentation and selection remain local state only; browsing, refresh, navigation and drawer
  interaction issue no mutation request. The add-library `保存` control is disabled until the
  separate validation/activation Task supplies its backend behavior.
- The fake server keeps the legacy `resources` fixture for unrelated routes and adds a separate
  deterministic `source` fixture for the approved reference state.

### Remaining In-Slice Work

- ResourceLibrary creation, validation, checked activation and runtime rebinding are outside this
  Task. Terminal Organize-result synchronization to FileIndex is also deferred as specified.
- Exact visual parity for the frozen shared shell remains outside this page-local implementation.

### Risks / Deviations

- The screenshot comparison is intentionally non-zero: the current shared shell is the frozen
  dark horizontal shell, while the canonical asset uses a light vertical rail/top bar; the
  existing font/icon/thumbnail assets also differ. The Files page composition and drawer are
  present within the unchanged shell, but this Task does not redesign that frozen surface.
- Pre-existing unrelated worktree edits were preserved and are not in this checkpoint:
  `web/src/entities/library/system-status.test.ts`, `web/src/entities/library/system-status.ts`,
  `web/src/features/entry/EntryPage.test.tsx`, `web/src/features/operations/PreviewNewPage.tsx`,
  `web/src/shared/api/api-client.ts`, `web/src/shared/api/library-api.test.ts`,
  `web/src/shared/auth/AuthBoundary.test.tsx`, `web/src/shared/navigation/destination-model.test.ts`
  and `web/src/shared/ui/AppShell.test.tsx`.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: e9f3c08a032410c28f642968b6e12bd901362160
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
