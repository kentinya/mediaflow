# Task 37.3 — Files Bounded Create, Rename, Text Edit and Delete

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.3
Parent Slice: 37
Status: PLANNED
Task Base: e33a030055a81011a32de507bef6758d48607c9a
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Advance Slice 37 **RO-6 Complete common file management** and **RO-7 Direct-operation safety** by
delivering a Web-native, backend-authoritative journey for Create Folder, Create Text File, Rename,
bounded text Edit and Delete from the existing Files workspace. These ordinary file operations
stay in the current file context, use OrganizerExecutor as the only Storage-mutation boundary, and
provide safe conflict, stale-state, confirmation, outcome and recovery behavior without forcing
users through media-organize Preview/Execute ceremony.

This Task also advances **RO-9 Actionable recovery**, **RO-11 Test reconciliation** and **RO-12
Security model continuity**. It establishes the direct-file-command boundary for later work but
does not implement Copy, Move, Upload or Download.

## Why This Task Exists

Tasks 37.1 and 37.2 delivered the Files shell, authoritative browsing and ResourceLibrary Save, but
the workspace still has no ordinary file-maintenance actions. Create, Rename, text Edit and Delete
share one coherent safety model: an exact Active ResourceLibrary and Storage, confined relative
paths, capability checks, explicit mutation intent, conflict/stale rejection, OrganizerExecutor-only
mutation and truthful post-operation refresh.

Post-PASS operator evidence also exposed a ResourceLibrary continuity defect in the same Files
context: the native selector can be obscured, the page visually presents only the current library,
and a remount prefers the legacy `source` ID so a newly saved or selected library appears to have
disappeared. Task 37.3 already owns Files toolbar/context state and authoritative refresh, so this
required RO-1/RO-4 correction belongs in the current vertical unit rather than a standalone visual
or field-sized Task.

The same evidence shows that Files currently initializes the Add ResourceLibrary drawer as open,
turning an explicit creation workflow into the default page state and unnecessarily narrowing the
browse workspace. The normal entry state must be the complete Files workspace; the drawer is an
operator-invoked action state only.

Delete adds material risk and therefore needs bounded impact discovery, explicit confirmation and
durable long-running/batch behavior. Keeping these related same-library operations together avoids
field-sized Tasks while leaving transfer-specific destination selection and byte-stream work for
later independently testable units.

## Implementation Scope

```text
Files command model → application admission/results → OrganizerExecutor → authenticated API → Files UI → tests
```

- Add bounded direct-file commands for `CREATE_DIRECTORY`, `CREATE_TEXT`, `RENAME`, `SAVE_TEXT`
  and `DELETE`. Browser requests identify only the Active ResourceLibrary, Storage-relative path,
  operation-specific basename or text, and server-issued stale/confirmation evidence needed for
  the exact command; host paths, credentials and implementation tokens remain hidden.
- Resolve the exact immutable Active ResourceLibrary and referenced enabled Storage at admission.
  Recheck confinement, symlink/path-escape rules, root protection, existence/type, capability,
  operation limits and stale state on the backend immediately before mutation.
- Reuse current RBAC, authenticated principal and audit behavior. Application/API code may perform
  bounded reads for admission and impact calculation but must not call mutating Storage methods.
  Every mutation passes through OrganizerExecutor; do not invoke Scan, Parser, Recognition,
  Metadata, Naming, Classification or media-organize planning for these commands.
- Extend or compose OrganizerExecutor narrowly to execute the five operations with explicit intent
  and structured per-item results. Rename is same Storage and ResourceLibrary only and never
  silently falls back to Copy, Move or another operation.
- Create Folder accepts one validated basename and creates exactly one directory. Create Text File
  accepts a validated basename with an allowlisted text extension and bounded initial content,
  rejects an existing target without replacement, and opens/selects the successful file.
- Add a bounded zero-mutation text read. Admit only regular allowlisted text files within configured
  size and encoding limits. Save only the exact version loaded; a changed or missing file fails
  stale without overwrite and retains edited content for explicit refresh, reconcile or retry.
- Rename one exact non-root file or directory to one validated basename. Existing destination,
  stale source, unsupported capability or invalid path fails with zero mutation. Success refreshes
  the directory and clears or remaps stale selection/tree/detail state.
- Delete supports one item and bounded multi-selection. Before mutation, enumerate the full effect
  of directories within explicit item/depth/size limits, show a human-readable impact summary, and
  require one confirmation bound to the exact server-validated scope/version. Reject ResourceLibrary
  roots, stale confirmation, escaped links and any unbounded impact.
- Route recursive, multi-item or otherwise long-running Delete through the existing Task system and
  persist independent per-item success/failure/recovery. A short single-item operation may complete
  inline only within the same application behavior and durable result/audit model. Partial success
  never hides remaining items or makes uncertain items auto-retryable.
- Persist bounded, secret-free result and audit evidence for every attempted command, including
  operation, logical source/target, status and actionable stable error category. Never persist or
  log text contents, host roots, credentials, authorization material or raw exception details.
- Expose authenticated API behavior with the same validation, permissions, confirmation and result
  semantics used by Web. Return stable action-oriented errors for invalid input, forbidden access,
  unsupported capability, conflict, stale state, exceeded bounds and partial/failed execution.
- Replace the obscurable native ResourceLibrary selector with a directly visible responsive strip
  of configured enabled ResourceLibrary cards. Show as many complete cards as fit at the current
  width and use one `更多` entry only when additional libraries overflow; do not impose a fixed
  presentation-only library count or truncate an operator's access to remaining eligible libraries.
- `更多` opens an anchored, unclipped, keyboard- and touch-operable popover containing the remaining
  libraries in a bounded scrollable list with local search. It exposes expanded state, closes on
  selection, Escape or outside activation, and does not cover the visible ResourceLibrary cards.
  Selecting an overflow library promotes that current selection into the last visible card slot
  before `更多`; the previously promoted overflow item returns to the searchable overflow list.
- ResourceLibrary selection is one coherent state transition: selected-card styling, logical
  ResourceLibrary identity, root/path summary, directory tree, breadcrumb, file query/table,
  cursor and selection state must all resolve from the same selected library. Never show a new card
  with old-library path or rows. Clear incompatible path/cursor/file selection before loading the
  newly selected library, while keeping unrelated Files controls stable.
- Keep the selected ResourceLibrary in Files-owned route state so an in-app revisit, deep link or
  reload followed by normal authentication recovery selects it again when it remains enabled.
  Missing/disabled selections fall back deterministically to an eligible library with current
  state refreshed; never hard-code `source` as the preferred default. After ResourceLibrary Save,
  both prior and new enabled libraries remain discoverable and the new library is selected without
  making the prior one appear deleted.
- Use the existing local interaction images under `web/test-results/` as review references:
  `task37.2体验bug.png`, `task37.2体验bug-正确效果.png`,
  `task37.2体验bug-点击更多.png`, `task37.2体验bug-选择媒体库D.png` and
  `task37.2体验bug-选择媒体库E.png`. Also use `task37.2体验bug2-2.png` as the normal drawer-closed
  Files entry reference and `task37.2体验bug2-1.png` only as the explicit Add ResourceLibrary
  action-state reference. Use `task37.2体验bug2-无资源库.png` as the empty ResourceLibrary reference
  when Active configuration has eligible Storage but no enabled ResourceLibrary. The labels
  `媒体库A` through `媒体库E` are illustrative data, not fixtures or a count limit, and the
  hand-drawn black rectangle is review annotation rather than product UI. These ignored reference
  images must not be staged or rewritten by Developer.
- Initialize Files with the Add ResourceLibrary drawer closed. Mount, route entry/re-entry, query
  refresh, authentication recovery and ordinary browsing must not open it automatically. The
  complete-width browse workspace remains the default even when no enabled ResourceLibrary exists;
  that recovery state explains the prerequisite and keeps the explicit `+ 添加资源库` action
  available when eligible Storage exists.
- When Active configuration has eligible Storage but no enabled ResourceLibrary, render the
  complete-width empty state from `task37.2体验bug2-无资源库.png`: retain the Files header and
  top-level `+ 添加资源库`, replace the information copy with `尚未添加资源库。添加后即可在这里浏览和整理文件。`,
  and show a centered folder/add illustration, `尚未添加资源库` heading, `请先添加一个资源库，选择存储位置和文件根路径。`
  guidance and a second explicit `+ 添加资源库` entry. Both entry points open the same drawer
  behavior and permissions.
- The empty state must omit ResourceLibrary cards, paths, directory tree, breadcrumb, file toolbar,
  table and rows. It must not fabricate `source`, a Storage root, directory or file, and must not
  issue a ResourceLibrary-scoped Files request without an exact enabled ResourceLibrary. If no
  eligible Storage exists, replace the add action with the existing actionable Storage prerequisite
  rather than enabling a Save journey that cannot succeed.
- Open the drawer only from explicit activation of `+ 添加资源库`. Close icon, Cancel and successful
  Save close it and restore the normal Files layout; a later explicit open starts a fresh candidate.
  Validation or Save failure keeps the drawer open at the relevant step with the entered candidate
  intact and actionable recovery, without converting the failed action state into a future default.
- Drawer-open layout may narrow the browse workspace as shown in the action-state reference, but it
  must preserve useful current Files context and must not fabricate a ResourceLibrary or change the
  selected library merely by opening or closing. Focus returns to the invoking control on Cancel or
  close, and moves to a useful selected-library/browse target after successful Save.
- Add Files toolbar, row-overflow and selection actions without changing the closed reference shell.
  Dialog/editor/impact states are keyboard operable and touch usable, preserve input on recoverable
  failure, prevent duplicate submission and avoid redundant confirmation for safe operations.
- After success, refresh authoritative directory/tree/detail state and expose the durable result.
  After failure or partial success, refresh enough state to show current truth and give an explicit
  next action; never automatically replay an uncertain mutation.
- Preserve ResourceLibrary Save, browse/search/sort/paging/view modes, media-organize Preview,
  non-Files V2 routes and V1 `/ui` behavior.
- Preserve the pre-existing working-tree modification to `docs/pics/文件页.png`; it is outside this
  Task and must not be staged, reverted, overwritten or used to hide a functional failure.

## Acceptance Criteria

- [ ] An authorized operator can Create Folder, Create Text File, Rename, open/edit/save eligible
      text and Delete one or a bounded selection entirely from `/ui-v2/library/files`, without CLI,
      raw implementation identifiers or media-organize ceremony.
- [ ] Create and Rename accept only safe single basenames, remain confined to the exact Active
      ResourceLibrary, enforce Storage capabilities and reject an existing target with zero silent
      replacement or operation fallback.
- [ ] Text open is zero-mutation and rejects directories, binary/disallowed extensions, unsupported
      encoding and oversized content. Save runs only through OrganizerExecutor and rejects a file
      changed since load without overwriting it or discarding edited content.
- [ ] Delete shows a complete bounded impact summary and requires one confirmation tied to the exact
      validated scope/version. ResourceLibrary-root deletion, stale confirmation, path escape and
      item/depth/size-limit overflow fail before mutation.
- [ ] Recursive, multi-item or long-running Delete uses Tasks with durable independent per-item
      outcomes and explicit recovery. Partial or uncertain outcomes are not hidden or auto-replayed.
- [ ] All command mutations occur only through OrganizerExecutor after backend authorization,
      Active-snapshot, confinement, capability, conflict/stale and operation-specific checks. No
      media pipeline stage mutates files and no unsupported operation silently falls back.
- [ ] Success refreshes authoritative directory/tree/detail/selection state. Conflict, stale,
      unsupported, limit, execution and partial failures retain useful context, explain durable
      state and provide a concrete safe next action.
- [ ] Actions appear in applicable toolbar/row/selection contexts, are keyboard and touch operable,
      preserve the closed reference shell and add no redundant confirmation to safe operations.
- [ ] Every enabled configured ResourceLibrary remains directly discoverable: complete cards fill
      the available width, overflow is reachable through an unclipped `更多` popover with search and
      bounded scrolling, and no native selector menu obscures the ResourceLibrary summary.
- [ ] Selecting an overflow library closes `更多`, promotes the selection into a visible card and
      returns the previous promoted item to overflow. Repeating the journey for another library
      replaces that visible overflow slot rather than accumulating a fixed or unbounded card row.
- [ ] Selecting, saving or restoring a ResourceLibrary updates its visible active state, identity,
      path, tree, breadcrumb and live file query as one transition. Old-library rows/path cannot be
      mixed with the new selection, and all prior/new enabled libraries remain available.
- [ ] A valid selection survives Files route re-entry, deep link and reload/auth recovery without
      silently reverting to a hard-coded `source`. A missing or disabled selection falls back to a
      current eligible library with incompatible browse state cleared and current truth explained.
- [ ] The ResourceLibrary strip and `更多` journey remain usable at the controlled `1536 x 1024`
      viewport and responsive widths with keyboard, touch, Escape and outside-close behavior. Names
      and counts come from authoritative runtime data; example A/B/C/D/E labels and the black review
      rectangle are not rendered or hard-coded.
- [ ] Initial Files entry, route re-entry, refresh and authentication recovery render the normal
      drawer-closed workspace represented by `task37.2体验bug2-2.png`; no lifecycle or empty-library
      condition silently opens the Add ResourceLibrary drawer.
- [ ] With eligible Storage and zero enabled ResourceLibraries, Files matches
      `task37.2体验bug2-无资源库.png`: the full-width empty state shows the specified explanation and
      both explicit add entry points, while ResourceLibrary summary/path, tree, breadcrumb, file
      toolbar/table/rows and any fabricated `source` identity are absent.
- [ ] The zero-ResourceLibrary state performs no ResourceLibrary-scoped Files request, Scan,
      Provider call, Task creation or Storage mutation. Either add entry opens the same authorized
      drawer; absence of eligible Storage instead presents the truthful Storage prerequisite.
- [ ] Only explicit `+ 添加资源库` activation enters the drawer-open state represented by
      `task37.2体验bug2-1.png`. Close and Cancel discard that candidate and restore the normal layout;
      successful Save closes the drawer and selects the saved enabled library.
- [ ] Client validation or backend Save failure keeps the drawer, affected step and entered values
      visible with a safe next action. After the operator closes/cancels that failure state, a later
      Files visit remains closed and a later explicit open starts a fresh candidate.
- [ ] Drawer open/close changes no Active configuration, selected ResourceLibrary or Storage state
      by itself. Keyboard/touch activation, Escape/close behavior and focus restoration are covered
      without weakening the existing Save authorization, atomic activation or failure semantics.
- [ ] API and Web share application behavior, RBAC and safety semantics. Results/audit are bounded
      and secret-free; text, credentials, host roots and raw exceptions never enter them.
- [ ] ResourceLibrary Save, Files browse/search/sort/paging/views, media-organize Preview, non-Files
      V2 routes and V1 `/ui` remain functional.
- [ ] Focused tests cover success, invalid input, permission denial, conflict, stale source/editor/
      confirmation, root/path escape, capability denial, limits, recursive/partial Delete, injected
      failures, recovery, redaction and OrganizerExecutor-only mutation. T4 gates pass without
      weakened assertions or hidden skips.
- [ ] The checkpoint contains only Task 37.3 implementation, tests and completion report. The dirty
      reference image, private configuration, credentials and unrelated files remain excluded.

## Required Tests

- `python3 scripts/check_governance.py`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m unittest tests.test_direct_file_operations`
- `.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_organizer_rollback tests.test_runtime_files_browser tests.test_api_security`
- `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage tests.test_openlist_storage tests.test_s3_storage`
- `.venv/bin/python -m unittest discover -s tests`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `python3 scripts/docker_release_security_smoke_test.py`
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"`
- `cd web && npm run format:check`
- `cd web && npm run typecheck`
- `cd web && npm run lint`
- `cd web && npx vitest run src/features/library/StorageFilesPage.test.tsx`
- `cd web && npx playwright test tests/e2e/library-files.spec.ts --project=chromium`
- `cd web && npm run test -- --run`
- `cd web && npm run build`
- `cd web && npm run test:e2e`
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist`
- `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl`
- `git diff --check`
- Inspect `git status --short`, the exact Task Base..Head diff and staged manifest; confirm
  `config/alist.json`, credentials, the dirty `docs/pics/文件页.png` and unrelated files are absent.

All tests use mocks, fakes, temporary roots and local test servers only. No production
SMB/OpenList/S3/TMDB service, production credential or real media directory is permitted.

## Non-goals

- Copy, Move, cross-Storage transfer, destination picker, transfer progress or transfer fallback.
- Upload, Download, browser streaming, resumable/chunked transfer or archive handling.
- Multi-item media Organize execution, FileIndex browsing, terminal organize reconciliation or
  broad index repair; this Task only keeps its own results and live Files state truthful.
- Replace for Create or Rename. Text Save may replace only its exact loaded version; Delete remains
  a separate explicitly confirmed operation.
- Arbitrary binary/media editing, media probing, FFmpeg/FFprobe, unbounded/root deletion, host-path
  access, undelete, trash policy or cross-operation rollback.
- New Storage adapters/capabilities, broad Storage redesign, identity/configuration redesign,
  non-Files body redesign, unrelated refactors, optional proof or P2/P3 cleanup.
- ResourceLibrary reorder, pin/favorite semantics, edit/delete management, hard-coded sample library
  records, a fixed four/five-library maximum, or committing/generated rewriting of the local
  `web/test-results/` interaction references.

## Developer Completion Report

### Changed Files

- Pending.

### Implemented

- Pending.

### Tests and Results

- Pending.

### Decisions

- Pending.

### Remaining In-Slice Work

- Pending.

### Risks / Deviations

- Pending.

### Checkpoint

```text
Status: NOT STARTED
Head SHA: N/A
Commit: N/A
Working tree: N/A
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
