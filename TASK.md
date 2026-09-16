# Task 37.3 — Files Bounded Create, Rename, Text Edit and Delete

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.3
Parent Slice: 37
Status: READY FOR B REVIEW
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

Within the same Files-owned ResourceLibrary context, this Task also completes the explicitly
confirmed removal journey for an unreferenced ResourceLibrary configuration. That action removes
only the selected ResourceLibrary from MediaFlow's managed configuration and atomically activates
the successor; it never deletes the ResourceLibrary root or any Storage file/directory.

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

Operator review also established the missing entry and safety semantics for ResourceLibrary
removal. The selected ResourceLibrary card needs its own contextual `…` action entry, distinct from
the `更多` overflow selector. Removal must reuse managed-configuration reference protection and
atomic activation while making it unmistakable that Storage content is untouched. This is part of
the Files ResourceLibrary lifecycle and selection continuity already owned by this Task; it is not
file/directory Delete and must not be routed through OrganizerExecutor.

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
- Give the selected ResourceLibrary card its own keyboard- and touch-operable `…` action trigger,
  visually and semantically distinct from the terminal `更多` overflow selector. Opening the card
  menu does not change the selected library, browse state or Active configuration. The Task-required
  destructive item is `删除资源库`; if `编辑资源库` is also rendered as in the interaction mockup, it
  must continue to an already functional managed edit journey and must not be a dead control or
  expand this Task into a new ResourceLibrary editor.
- `删除资源库` opens one explicit confirmation bound to the currently selected ResourceLibrary and
  current Active revision. The dialog identifies its display name, configured Storage and
  ResourceLibrary-relative root path, reports whether Automation Task Definitions, recognition/
  organization rules or other managed objects reference it, and uses the exact safety explanation
  `只会删除 MediaFlow 中的资源库配置。不会删除 Storage 中的任何文件或文件夹。` Cancel, close and
  Escape perform zero mutation and return focus to the card action trigger.
- Implement ResourceLibrary removal as a managed-configuration command, not as direct file Delete:
  resolve the current Active snapshot, reject a missing/disabled/mismatched or stale selection,
  reuse authoritative reference evidence, create the bounded successor candidate without the exact
  ResourceLibrary, run complete validation and required checked activation, and publish the new
  immutable Active runtime atomically. Any reference, validation, Storage evidence, concurrency,
  activation or runtime-load failure preserves the prior Active and keeps the selected library and
  confirmation context available with an actionable next step.
- A referenced ResourceLibrary is not deletable. Show bounded, secret-free reference categories and
  names plus a route/action for resolving those references; do not weaken reference checks, cascade
  delete dependent configuration or silently disable Automation/rules. A confirmed unreferenced
  removal records actor, before/after identity, outcome and stable failure category in the existing
  configuration audit without logging credentials, host roots or raw exceptions.
- ResourceLibrary removal must perform zero Storage mutation: it never calls `Storage.delete`, any
  other mutating Storage method, or OrganizerExecutor. On success, close the dialog, remove only the
  deleted library card, clear its path/cursor/tree/file selection, refresh from the newly Active
  runtime and deterministically select another eligible ResourceLibrary. If none remains, render the
  already specified full-width zero-ResourceLibrary state. All real files and directories remain
  browseable again if the same Storage root is later configured as a ResourceLibrary.
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
- Use `task37.2体验bug-删除资源库入口示意.png` for the selected-card action-menu entry and
  `task37.2体验bug-删除资源库确认-修正版.png` for the confirmation hierarchy and wording. These are
  ignored interaction references, not assets to commit or pixel-copy. In product UI, the source
  object is always called `资源库`; keep the left-navigation `媒体库` label and the information
  banner's destination phrase `整理到对应的媒体库` unchanged because those refer to MediaLibrary.
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
- [ ] The selected ResourceLibrary card exposes its own accessible `…` action menu, separate from
      `更多`; choosing `删除资源库` opens the confirmation state without changing the selected
      library or starting any mutation. If an `编辑资源库` row is shown, it is functional through
      the existing managed edit journey rather than a placeholder.
- [ ] ResourceLibrary confirmation identifies the exact selected name, configured Storage and
      relative root; states that only MediaFlow configuration is removed and Storage files/folders
      are retained; and requires one explicit, current-revision-bound destructive submission.
      Cancel, close and Escape are zero-mutation, preserve Files context and restore focus.
- [ ] A referenced, missing, disabled, mismatched or stale ResourceLibrary cannot be removed.
      Reference conflicts show bounded actionable evidence without cascade deletion. Every
      validation/check/activation/runtime failure leaves the prior immutable Active authoritative,
      keeps real Storage untouched and supports a safe correction/retry.
- [ ] Successful unreferenced ResourceLibrary removal atomically publishes the validated successor,
      records a bounded secret-free configuration audit, closes the dialog, removes only that card,
      clears incompatible browse state and selects a deterministic eligible fallback. Removing the
      final enabled library enters the defined full-width empty state without issuing a fabricated
      ResourceLibrary-scoped Files request.
- [ ] ResourceLibrary removal never invokes OrganizerExecutor or any mutating Storage operation;
      automated evidence proves files and directories under its configured root are byte-for-byte
      and name-for-name unchanged. File/directory Delete remains the separate OrganizerExecutor-only
      operation with bounded impact confirmation.
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
- `.venv/bin/python -m unittest tests.test_resource_library_activation tests.test_configuration_objects`
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
- ResourceLibrary reorder, pin/favorite semantics, a new Files-local ResourceLibrary edit form,
  cascade deletion of referenced configuration, deletion of ResourceLibrary Storage content,
  hard-coded sample library records, a fixed four/five-library maximum, or committing/generated
  rewriting of the local `web/test-results/` interaction references.

## Developer Completion Report — CORRECTION LOOP (Task 37.3 FIX REQUIRED)

This is the correction-loop report for the same Task 37.3. It replaces the
previous report's Checkpoint; Task ID, Task Base, Goal and Scope are unchanged.
Only the blockers listed under the `B Review Result` section and their direct
root causes were fixed, plus the test/fake contract updates those fixes require.

### Changed Files

Correction-loop changes on top of `75abfe3` + `a11292e`:

Backend:

- `mediaflow/application/direct_file_commands.py` — Save evidence now carries
  the exact loaded `modifiedAt` into `EntryVersionEvidence`; Delete execution
  passes per-entry server-issued evidence to the executor; Delete responses
  always carry the stable `status` (`SUCCESS`/`PARTIAL`/`FAILED`/`PAUSED`/
  `CANCELLED`/`UNCERTAIN`) naming the known durable effect; single-command
  results persist the exact logical `target` path.
- `mediaflow/application/organizer.py` — `execute_direct_write` re-verifies the
  loaded digest/size at the last safe boundary before an overwrite write;
  `execute_direct_rename` re-verifies observed source size/mtime;
  `execute_direct_delete` re-verifies confirmed entry evidence (files: exact
  size+mtime; directories: entry type, because a directory's mtime legitimately
  changes while its confirmed children are deleted).
- `mediaflow/application/task_runtime.py` — `complete_direct_item` accepts the
  bounded logical target and persists `destination_path` truthfully (Rename no
  longer records the source as its own destination); the durable
  source/target are ResourceLibrary-relative, never host roots.
- `mediaflow/application/configuration_objects.py` — `remove_resource_library`
  binds the confirmation to the exact previewed Active revision
  (`expected_revision_id`/`expected_version`/`expected_digest`) and the
  selected library identity, and refuses a disabled ResourceLibrary before any
  successor is constructed.
- `mediaflow/interfaces/service_api.py` — the removal `DELETE` route requires
  exactly the four confirmation fields; Rename requires the `expected` observed
  evidence; the removal preview already publishes `active` (revisionId/
  version/digest) from `configuration_objects`.
- `mediaflow/domain/direct_files.py` — `EntryVersionEvidence` mutation-fencing
  model; `DirectFileImpactEntry.modified_at` participates in the scope digest
  so a same-size replacement between preview and confirmation is stale.
- `tests/test_direct_file_operations.py` — updated to the strict contracts and
  extended with the correction-loop regressions listed under Tests.

Web:

- `web/src/entities/library/direct-files.ts` — `normalizeRemovalPreview` now
  requires the `active` revision identity (fails closed without it).
- `web/src/entities/library/direct-files.test.ts` (new) — contract regression
  feeding the real backend Delete payloads (success/partial/paused/cancelled/
  failed/uncertain, no hand-added `status`) and the real removal-preview
  payload through the strict normalizers; proves a `status`-less legacy
  response fails closed.
- `web/src/shared/api/api-client.ts` — `removeResourceLibrary` submits the
  confirmation binding (`expectedRevisionId`/`expectedVersion`/`expectedDigest`/
  `expectedLibraryId`); Rename submits the observed `expected` evidence.
- `web/src/features/library/StorageFilesPage.tsx` — stale text Save keeps the
  local edits and explicitly enters the reloadable editor state; a successful
  Save refetches the `files-text` query so the next Save submits fresh
  evidence; Rename/Delete success prunes or remaps `selectedFiles`,
  `knownDirectoryPaths` and `visitedDirectories` (siblings keep their own
  independent selections); Delete outcomes prune only successfully deleted
  paths; removal stale/conflict failures invalidate the preview so the operator
  can re-review and confirm again.
- `web/src/features/library/DeleteResourceLibraryDialog.tsx` — blocks the
  confirmation while the preview is loading, mismatched with the selection, or
  the library is disabled; offers 重新获取预览并重审 after a stale refusal.
- `web/src/features/library/LibraryCardStrip.tsx` — removed the hard-coded
  12-item popover cap; the bounded scroll list now renders every authoritative
  overflow entry (search still filters it).
- `web/src/features/library/StorageFilesPage.test.tsx` — fixtures updated to
  the strict preview contract; new tests for 13+ library discovery/selection,
  stale save recovery, consecutive-save evidence refresh, partial-Delete
  durable outcome.
- `web/tests/e2e/library-files.spec.ts`, `web/tests/fake-server.mjs` — fake
  preview exposes the full `active` identity; the fake removal `DELETE`
  validates the confirmation binding and returns the real
  `resource_library_removal_stale` 409 contract; new e2e journey for a stale
  removal confirmation (dialog stays open with the re-review action, library
  remains configured).

### Implemented

- Delete result contract: every terminal Delete response now carries a stable
  `status` that names the known durable effect, so `normalizeDirectFileCommandResult()`
  succeeds on the real API response and the Web result view shows the true
  durable outcome (per-item outcomes, partial failures and uncertainty stay
  visible and are never auto-replayed). A contract regression feeds the real
  backend payload shapes through the frontend normalizer; the fakes no longer
  invent a `status` the backend never sent.
- Exact source/scope/version fencing: Rename requires and re-verifies
  server-issued observed evidence (size + mtime); Delete impact entries carry
  `modifiedAt` into the scope digest, and the executor re-verifies each
  confirmed entry (files: size+mtime; directories: entry type) immediately
  before mutation; text Save re-verifies the exact loaded digest+size inside
  `OrganizerExecutor` at the last safe boundary. Same-size source replacement
  between preview/admission and mutation now fails stale with zero erroneous
  mutation, including a simulated pre-mutation race.
- ResourceLibrary removal confirmation binding: the preview publishes the exact
  Active `revisionId`/`version`/`digest`; the `DELETE` request must carry that
  identity plus the selected library id; the backend rejects stale,
  mismatched, missing or disabled confirmations with 409
  `resource_library_removal_stale` / `resource_library_disabled` before any
  successor work, preserving the prior Active; the Web keeps the confirmation
  context open with a refresh-and-re-review action.
- Text editor recovery: stale Save keeps local edits and renders the explicit
  reload state; a successful Save refetches the authoritative text so the next
  Save submits the new version (stale→reload/reapply and consecutive-save
  covered by unit tests).
- Rename/Delete browse-state hygiene: known-success results prune or remap the
  affected `selectedFiles`/`knownDirectoryPaths`/`visitedDirectories`; renamed
  paths are remapped to their new identity; unaffected siblings keep their own
  selections and outcomes.
- Durable Rename target: `complete_direct_item` persists the exact bounded
  logical target, so the durable Result records `rename-me.txt -> renamed.txt`
  (covered for Create/Rename/Save/Delete; host roots never enter the record).
- `更多` discoverability: the hard-coded 12-item popover cap is gone; every
  authoritative overflow entry stays reachable in the bounded scroll list with
  local search; covered by a 13-library unit journey (discovery, selection,
  promotion beyond the previous cap).
- Report SHA: this checkpoint's Head SHA below is the exact resolvable commit
  containing the report itself.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS (304 files).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m unittest tests.test_direct_file_operations` — PASS
  (38 tests, including new correction-loop regressions: rename stale-source
  fencing, same-size delete-scope swap refusal, save boundary re-verification
  with an injected pre-mutation race, delete `status` contract for
  SUCCESS/PARTIAL, durable source/target identity for Create/Rename/Save/
  Delete, rename API evidence enforcement, stale/mismatched/disabled/incomplete
  removal refusals).
- `.venv/bin/python -m unittest tests.test_resource_library_activation
  tests.test_configuration_objects` — PASS.
- `.venv/bin/python -m unittest tests.test_organizer
  tests.test_organizer_mutation_authority tests.test_organizer_rollback
  tests.test_runtime_files_browser tests.test_api_security` — PASS.
- `.venv/bin/python -m unittest tests.test_local_storage
  tests.test_smb_storage tests.test_openlist_storage tests.test_s3_storage` —
  PASS.
- Combined targeted suites (281 tests) — PASS.
- `.venv/bin/python -m unittest discover -s tests` — 1576 tests: PASS except 3
  failures, each reproduced identically on a pristine `a11292e` worktree and
  therefore `FAIL / PRE-EXISTING / UNRELATED`:
  `test_configuration_status.ConfigurationSnapshotTests.
  test_hostile_configuration_content_is_never_exposed`,
  `test_manual_operations_contract.ManualOperationsContractTests.
  test_real_api_documents_carry_no_forbidden_evidence`,
  `test_manual_operations_contract.ManualOperationsContractTests.
  test_real_api_documents_match_the_frontend_fixture`. 7 skips are the
  pre-existing real-service acceptance skips.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"` —
  PASS (verified with grep; `rg` is not installed in this environment, the
  matched set is empty either way).
- `cd web && npm run format:check` / `npm run typecheck` / `npm run lint` —
  PASS.
- `cd web && npx vitest run src/features/library/StorageFilesPage.test.tsx` —
  PASS (18 tests).
- `cd web && npx vitest run src/entities/library/direct-files.test.ts` — PASS
  (10 tests, real-payload contract regression).
- `cd web && npm run test -- --run` — PASS (433 tests / 33 files).
- `cd web && npm run build` — PASS.
- `cd web && npx playwright test tests/e2e/library-files.spec.ts
  --project=chromium` — PASS (23 tests, including the new stale-removal
  confirmation journey and 13+-library overflow discoverability is covered in
  unit tests; e2e covers strip/更多 promotion, empty state, create/rename/
  edit/delete and removal journeys).
- `cd web && npm run test:e2e` — 101 PASS; 10 failures, all in
  `library-file-detail.spec.ts` (7) and `manual-operations.spec.ts` (3).
  Reproduced serially (`--workers=1`) on both the working tree and a pristine
  `a11292e` worktree with identical test names and counts (10 failed / 9
  passed on both): `FAIL / PRE-EXISTING / UNRELATED`. Root cause evidence: the
  FileIndex detail routes were removed from the router in `b507edb` (before
  this Task's base `e33a030`), while `library-file-detail.spec.ts` still
  navigates to `/ui-v2/library/file-index*` and the fake server serves the
  "Route not found" boundary for them; the file-index fake fixtures were
  removed in the same commit and neither file was touched by Task 37.3.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w <tmp>` +
  `.venv/bin/python scripts/wheel_smoke_test.py` — PASS (Status: PASS, backup
  SHA-256 `27225bd2c66d...`); the wheel and `dist/` build outputs were removed
  afterwards and are not committed.
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE in this
  environment: the Docker daemon cannot see bind-mount sources created by this
  session (`invalid mount config for type "bind": bind source path does not
  exist`), reproduced identically for `/tmp` and `/var/tmp` paths and with the
  same script on a pristine `a11292e` worktree, so the failure is an
  environment/daemon mount-visibility limitation, not a code change. The
  script's earlier stages (image build context, config generation) complete;
  the failure occurs at `docker compose up` mount time.
- `git diff --check` — PASS. Staged manifest inspected (17 files listed above):
  `config/alist.json`, the dirty `docs/pics/文件页.png`, credentials,
  `web/test-results/` references and unrelated files are absent.

### Decisions

- Delete fencing keeps directories on entry-type-only re-verification (a
  directory's mtime changes legitimately while its confirmed children are
  deleted); files fence on exact size+mtime. Content replacement inside a
  confirmed file is still caught by the same-size scope-digest check plus the
  executor's per-entry size+mtime verification.
- The Delete `status` contract is derived once in
  `_delete_command_status` (uncertain > paused > cancelled > success/partial/
  failed) so the backend, not the UI, names the durable effect; `UNCERTAIN`
  also sets `durableState: mutation_effect_uncertain` as before.
- Rename/Delete browse-state cleanup runs from the response's known outcomes
  only: successfully deleted paths are pruned, renamed paths are remapped
  (including child paths), and a `FAILED`/`UNCERTAIN` item never prunes state.
- The stale-removal Web flow intentionally keeps the dialog open and refreshes
  the preview from the new Active (via query invalidation) rather than closing,
  so the operator re-reviews the exact current state before re-confirming.
- The popover cap was removed entirely rather than adding pagination: the
  bounded scroll container keeps the layout bounded while search narrows large
  lists, matching the Task's "all enabled libraries discoverable" requirement.
- The removal `DELETE` body is now mandatory and exact (`set(confirmation) ==
  required_confirmation`), mirroring the strict request contracts the API
  already applies to direct commands.

### Remaining In-Slice Work

- Copy, Move, cross-Storage transfer, destination picker and transfer
  fallback (RO-6 remainder).
- Upload and Download bounded journeys.
- Multi-item media Organize execution from the Files selection footer and
  broader FileIndex reconciliation.
- The pre-existing `library-file-detail` / `manual-operations` e2e divergence
  (FileIndex detail routes removed from the router while their e2e specs and
  fake fixtures remain) predates this Task and needs a B/A contract decision
  (replace the specs per RO-11 or restore the routes).
- Slice-level final validation (1536x1024 reference screenshot report, full
  shell smoke) remains with B/A per the Contract.

### Risks / Deviations

- The three pre-existing full-regression Python failures and the ten
  pre-existing non-Files e2e failures are documented with pristine-HEAD
  serial reproduction evidence; judgment about their impact on Task PASS
  belongs to B.
- The docker release security smoke test could not run to completion in this
  environment (daemon bind-mount visibility, reproduced identically on pristine
  HEAD); it is reported UNAVAILABLE with evidence rather than PASS.
- Recursive Delete of a bounded directory still executes per-entry Storage
  deletions synchronously inside the request (unchanged from the previous
  checkpoint; documented behavior, not an auto-replay).
- The pre-existing `web/test-results/` interaction reference images and the
  dirty `docs/pics/文件页.png` were neither staged nor modified.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 3f04b7cc1c850e482002d90de35d446bf8d7d677
Commit: 3f04b7c fix(files): bind direct-command evidence and removal confirmation
Working tree: clean except the pre-existing dirty docs/pics/文件页.png and
ignored artifacts (web/dist/, web/test-results/, config/alist.json)
```

## B Review Result

```text
Reviewed: e33a030055a81011a32de507bef6758d48607c9a..a11292ec1279ff4c4b6f71d864b933b75fd80e59
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Delete 的真实 API 与 Web 结果契约不一致，已经发生的破坏性效果会被 UI 误报成未知响应。
  证据：在临时 Local Storage 上依次调用真实 `delete-impact` 与 `files/commands`，HTTP 200
  且文件已删除，但响应键只有 `taskStatus` 等字段、没有
  `normalizeDirectFileCommandResult()` 强制要求的 `status`；探针输出
  `has_required_frontend_status: False, file_deleted: True`。当前 Vitest/E2E fake 自行补了
  `status: "SUCCESS"`，因此没有覆盖真实契约。修正方向：让 completed/partial/failed/paused/
  cancelled Delete 都返回与严格前端模型一致、能表达已知效果的稳定状态；Web 必须据此刷新并
  显示真实 durable outcome，并增加真实 API 响应到前端 normalizer 的契约回归，不能只修 fake。
- Direct mutation 的 stale fencing 未满足 Task 的“exact source/scope/version”要求。证据：临时
  Storage 探针先取得 `victim.txt` 的 Delete impact，再把 `v1` 替换为同大小的 `v2`；新旧
  `scopeDigest` 完全相同，旧确认随后返回 `completed` 并删除了新文件。Rename 请求只有
  `path + name`，没有任何已观察 source evidence；Save 的 digest 校验发生在创建 Task/
  Executor preflight 之前，而 overwrite executor 不再核对该 evidence。修正方向：为 Rename、
  Delete scope 和 Save 传递并绑定适合 provider 的 server-issued current-entry evidence，在最后
  安全的 mutation 边界重新校验；注入 preview/admission 后替换、同大小替换和 mutation 前竞争的
  测试必须证明零错误 mutation。
- ResourceLibrary 删除确认没有绑定预览时的 Active revision，也没有拒绝 disabled selection。
  证据：临时配置探针读取 removal preview，随后成功 Save 另一个 ResourceLibrary 使 Active
  revision 改变，再用仅含 library ID 的 `DELETE` 请求仍返回 200 并删除原 ResourceLibrary；
  `RemovalPreviewModel` 丢弃响应中的 `active`，客户端 DELETE body 为空，服务端
  `_active_resource_library()` 也不校验 `enabled`。修正方向：把 preview 的 revision/version/
  digest 和 selected-library identity 绑定到一次确认，后端在构造 successor 前拒绝 stale、
  mismatched、missing 或 disabled 请求，Web 保留当前确认上下文并提供刷新后重审动作；补齐这些
  failure-path 回归。
- 文本编辑的 Web recovery 断裂，而且一次成功 Save 后仍保留旧 evidence。证据：
  `commandMutation` 对 `files_direct_stale_content` 只设置通用 `commandError` 后返回，代码中
  `setEditorStale(true)` 从未出现；而“重新加载最新内容”按钮仅在 `state.stale` 为 true 时渲染。
  成功 Save 也没有更新/失效 `files-text` query，下一次 Save 会继续提交旧 digest。修正方向：
  stale 响应必须保留本地编辑并显式进入可 reload 的状态；成功 Save 后必须取得或写入新的权威
  content/evidence，再允许后续 Save；覆盖 stale→reload/reapply 以及连续两次 Save 的 Web 测试。
- Rename/Delete 成功后没有清除或重映射 Files 的相关选择和目录树状态。证据：成功分支只
  invalidate `storage-files`/`system-status` queries，未更新 `selectedFiles`、
  `knownDirectoryPaths` 或 `visitedDirectories`；被重命名/删除的 path 因而作为隐藏状态保留，
  同路径再次出现时会被意外重新选中，目录也可残留在树中。修正方向：按已知成功/逐项结果清理
  或重映射受影响状态，并测试 selected file、selected directory、directory rename 和 partial
  Delete，不能清掉未受影响 sibling 的独立选择/结果。
- durable direct-command Result 没有保存 Rename 的实际 target。证据：临时 Rename 探针读取
  `task_results`，得到 `source_path='rename-me.txt'` 且
  `destination_path='rename-me.txt'`，而实际目标是 `renamed.txt`；
  `complete_direct_item()` 当前无 target 参数并把 destination 固定成 source。修正方向：从
  OrganizerExecutor result/application outcome 传入并持久化 bounded logical source/target，保持
  secret-free，并对 Create/Rename/Delete/Save 的 Result identity 增加回归。
- `更多` 不能保证所有启用的 ResourceLibrary 可发现。证据：`LibraryCardStrip.tsx` 把过滤后的
  overflow 再执行 `.slice(0, POPOVER_MAX_ITEMS)`，其中上限硬编码为 12，且没有分页、继续加载或
  截断提示；第 13 个之后的未搜索条目不在 bounded scroll list 中。修正方向：保留有界可操作
  布局的同时让全部 authoritative overflow 条目可浏览（或提供真实分页/继续加载），并用超过
  12 个 ResourceLibrary 覆盖发现、搜索、选择和 promotion。
- Developer Completion Report 的完整 Head SHA
  `75abfe3c3f22cb451b80a7d9de2b21178274c78a` 无法由 Git 解析；实际实现提交是
  `75abfe30b9715853b9bdfe2fa7c044eb29b47cf1`，当前 completion-report commit 是
  `a11292ec1279ff4c4b6f71d864b933b75fd80e59`。修正方向：下一次 READY FOR B REVIEW 报告必须
  填写可解析、与实际修正 checkpoint 对应的完整 Head SHA，并如实更新实际测试结果。
