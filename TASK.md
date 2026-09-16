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

## Developer Completion Report — SECOND CORRECTION LOOP (Task 37.3 FIX REQUIRED)

This is the second correction-loop report for the same Task 37.3 (Task Base,
Goal and Scope unchanged). Only the blockers listed in the current
`## B Review Result` section and their direct root causes were fixed, plus the
test and fake updates those fixes require.

### Changed Files

Correction-loop changes on top of `1bf47b7`:

Backend:

- `mediaflow/domain/direct_files.py` — `EntryVersionEvidence` and
  `DirectFileImpactEntry` carry the provider's optional stable identity
  (`fingerprint`); the fingerprint participates in the Delete scope digest but
  is deliberately not emitted in the browser-facing impact document.
- `mediaflow/application/direct_file_commands.py` — impact enumeration,
  confirmed-execution re-enumeration and the scope digest now include each
  entry's provider fingerprint; Delete responses carry a bounded,
  never-truncated `knownEffects` contract (one entry per confirmed top-level
  target).
- `mediaflow/application/organizer.py` — `_direct_exists_preflight` fences
  directories on the provider's stable identity (the inode segment of the
  Local fingerprint, which survives the confirmed deletion of the directory's
  own children but changes on a same-name `rmdir`+`mkdir` replacement); for
  providers without a fingerprint the confirmed directory must be empty before
  removal; file fencing additionally compares the full provider fingerprint.
  New `_directory_fingerprint_identity` helper.
- `tests/test_direct_file_operations.py` — replaced-empty-directory,
  replaced-recursive-parent and secret-free impact regressions; a large
  (>200-entry) directory Delete known-effect regression; the Save/Rename/Delete
  pre-mutation race tests now really act inside the executor's preflight window
  and assert zero erroneous mutation.

Web:

- `web/src/entities/library/direct-files.ts` — `DirectFileKnownEffect` model and
  strict `knownEffects` normalizer.
- `web/src/features/library/StorageFilesPage.tsx` — Delete reconciliation now
  prunes exactly the top-level targets the backend reports as
  `effect: "deleted"` (never a truncated per-item outcome list); partial or
  failed targets keep their rows, selections and outcomes.
- `web/src/features/library/FileCommandDialogs.tsx` — the bounded text editor
  keeps the local draft separately, preserves it across the explicit
  reload, lets the operator reapply it, and only then saves with the freshly
  loaded evidence.
- `web/src/entities/library/direct-files.test.ts`,
  `web/src/features/library/StorageFilesPage.test.tsx`,
  `web/tests/fake-server.mjs` — contract and journey coverage for the new
  known-effect contract, the stale→reload→reapply→save loop, and real
  selection/directory-tree reconciliation (selected file, selected and
  visited directory, directory rename, >200-entry Delete).

### Implemented

- **Directory Delete identity fencing.** `_direct_exists_preflight` no longer
  degrades directories to a bare entry-type comparison. With a provider
  fingerprint it compares the directory's stable identity segment (Local
  inode), so a directory that was replaced between the operator's confirmation
  and the mutating Storage call is refused; the confirmed deletion of the
  directory's own children legitimately moves its `ctime` but not its inode,
  so recursive Delete of the confirmed scope still succeeds. Providers without
  a fingerprint (SMB/OpenList entries, S3 directory markers) instead require
  the confirmed directory to be empty at the mutation boundary, which refuses
  any replacement that carries content. The impact scope digest also includes
  each entry's fingerprint, so a replacement is additionally refused at
  `execute_delete` admission. Regressions: the B probe scenario
  (empty-directory replacement → `FAILED`, `replacement_deleted: False`),
  a replaced recursive parent with unconfirmed children (refused, new child
  retained), and confirmed recursive Delete still succeeding.
- **Real pre-mutation race tests.** The Save race test now performs the
  same-size swap inside the executor's own preflight window (the file still
  matches the admitted evidence at application admission) and asserts the
  executor fence refuses the write, returning `status=FAILED`,
  `errorCategory=source_changed` with the editor content never written.
  Equivalent new tests cover Rename and Delete. The previous test's patch of
  `mediaflow.application.direct_file_commands.OrganizerExecutor` (applied after
  the service was already constructed, so it never replaced
  `service._executor`) and its swap-before-call timing are gone.
- **Text editor stale recovery loop.** The editor now keeps the local draft in
  a separate state slot: a stale Save keeps it untouched, the explicit
  "确认放弃本地修改并重新加载" fetches the authoritative content/evidence, and
  after the reload the dialog offers "重新应用我的编辑" so the operator can
  reapply the draft and save with the new evidence. The Web regression keeps
  the old evidence failing 409 twice (a naive retry does not fabricate
  success), verifies the draft survives, then reloads, reapplies and only then
  succeeds with the fresh `size`/`digest`.
- **Bounded known-effect Delete contract.** Every Delete response now carries
  `knownEffects`: one entry per confirmed top-level target with
  `effect` ∈ {deleted, partial, retained, uncertain}. It is bounded by
  `MAX_DELETE_PATHS` at admission and is never truncated, unlike the
  diagnostic `outcomes` list (capped at `MAX_DELETE_PATHS * 4 = 200`). The Web
  reconciles selection and directory-tree state from `knownEffects` only, so a
  directory with more than 200 entries no longer leaves hidden selection/tree
  state behind, while partial and failed siblings keep their own state.
  Coverage: backend >200-entry Delete (`outcomesTruncated: true` +
  `knownEffects: [{path: big-dir, effect: deleted}]`), Web tests for a selected
  file, a selected and visited directory, a directory rename (selection and
  visited tree node remapped to the new identity) and a partial Delete
  (retained target stays selected).

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS (304 files).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m unittest tests.test_direct_file_operations` — PASS
  (46 tests, including the new directory-replacement fences, the corrected
  pre-mutation race tests, the >200-entry known-effect regression and the
  secret-free impact-document regression).
- `.venv/bin/python -m unittest tests.test_resource_library_activation
  tests.test_configuration_objects` — PASS (85 tests).
- `.venv/bin/python -m unittest tests.test_organizer
  tests.test_organizer_mutation_authority tests.test_organizer_rollback
  tests.test_runtime_files_browser tests.test_api_security` — PASS.
- `.venv/bin/python -m unittest tests.test_local_storage
  tests.test_smb_storage tests.test_openlist_storage tests.test_s3_storage` —
  PASS.
- Combined targeted suites (288 tests) — PASS.
- `.venv/bin/python -m unittest discover -s tests` — 1583 tests: PASS except 3
  failures, the same pre-existing set documented in the previous report and
  reproduced identically on pristine checkouts (`FAIL / PRE-EXISTING /
  UNRELATED`):
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
  PASS (verified with `grep`; `rg` is not installed in this environment and the
  matched set is empty either way).
- `cd web && npm run format:check` / `npm run typecheck` / `npm run lint` —
  PASS.
- `cd web && npx vitest run src/features/library/StorageFilesPage.test.tsx` —
  PASS (22 tests).
- `cd web && npx vitest run src/entities/library/direct-files.test.ts` — PASS
  (11 tests).
- `cd web && npm run test -- --run` — PASS (438 tests / 33 files).
- `cd web && npm run build` — PASS.
- `cd web && npx playwright test tests/e2e/library-files.spec.ts
  --project=chromium` — PASS (23 tests).
- `cd web && npm run test:e2e` — 101 PASS; 10 failures, all in
  `library-file-detail.spec.ts` (7) and `manual-operations.spec.ts` (3).
  Re-verified this round: reproduced serially (`--workers=1`) on a pristine
  `1bf47b7` worktree with identical test names and counts (10 failed / 9 passed
  on both), so they are `FAIL / PRE-EXISTING / UNRELATED`. Root cause (unchanged
  from the previous report): the FileIndex detail routes were removed from the
  router in `b507edb`, before this Task's base `e33a030`, while
  `library-file-detail.spec.ts` still navigates to `/ui-v2/library/file-index*`
  and the fake server answers with the "Route not found" boundary.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w <tmp>` +
  `.venv/bin/python scripts/wheel_smoke_test.py` — PASS (Status: PASS, backup
  SHA-256 `27225bd2c66d...`); the wheel and build outputs were removed
  afterwards and are not committed.
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE in this
  environment: the Docker daemon cannot see bind-mount sources created by this
  session (`invalid mount config for type "bind": bind source path does not
  exist` for `/tmp` paths, reproduced again this round and previously on a
  pristine worktree). The script's build/config stages complete; the failure is
  at `docker compose up` mount time and is an environment/daemon
  mount-visibility limitation, not a code change.
- `git diff --check` — PASS. Staged manifest inspected (10 files listed above):
  `config/alist.json`, the dirty `docs/pics/文件页.png`, credentials,
  `web/test-results/` references and unrelated files are absent.

### Decisions

- Directory fencing uses the strongest evidence the provider actually offers:
  the inode segment of the Local fingerprint for providers with fingerprints,
  and an emptiness check plus the scope-digest fence for providers that publish
  no per-entry identity. A same-name *empty* directory replacement on a
  fingerprint-less provider is not distinguishable from the original at the
  mutation boundary; the admission-time scope digest (which includes the
  entry's mtime and fingerprint) still refuses it whenever the replacement is
  observable before admission, and the executor fails closed for any
  replacement that carries content. This is recorded as a provider limitation,
  not a silent degrade.
- The provider fingerprint is part of the Delete scope digest but is not sent
  to the browser: the client needs only the bounded path/size/mtime summary and
  the digest, so Files results stay secret-free and free of host identity
  details.
- `knownEffects` is the reconciliation contract and `outcomes` stays the
  diagnostic contract: only `knownEffects` is bounded by the confirmed
  selection and never truncated, and the Web prunes state from it only for
  `effect: "deleted"`.
- The editor keeps the draft in its own state slot instead of mutating the
  server document: the reload may adopt the authoritative content, but the
  draft is only abandoned when the operator explicitly re-applies or replaces
  it, so a stale failure never silently discards local edits.

### Remaining In-Slice Work

- Copy, Move, cross-Storage transfer, destination picker and transfer fallback
  (RO-6 remainder).
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
  pre-existing non-Files e2e failures are documented with pristine-checkout
  serial reproduction evidence; the judgment about their impact on Task PASS
  belongs to B.
- The docker release security smoke test could not run to completion in this
  environment (daemon bind-mount visibility); it is reported UNAVAILABLE with
  evidence rather than PASS.
- A fingerprint-less provider cannot distinguish an empty-directory
  replacement at the last safe boundary; the fail-closed cases (content
  present, observable replacement before admission) are covered by tests, and
  the residue is documented above under Decisions.
- Recursive Delete of a bounded directory still executes per-entry Storage
  deletions synchronously inside the request (unchanged; documented behavior,
  not an auto-replay).
- The pre-existing `web/test-results/` interaction reference images and the
  dirty `docs/pics/文件页.png` were neither staged nor modified.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: d70b5177e36c19bdbc694df6c78991b31440c09e
Commit: d70b517 fix(files): fence directory deletes, complete text reload and bound delete effects
Working tree: clean except the pre-existing dirty docs/pics/文件页.png and
ignored artifacts (web/dist/, web/test-results/, config/alist.json)
```

## B Review Result

```text
Reviewed: e33a030055a81011a32de507bef6758d48607c9a..1bf47b71d61074260fbd5c2c72c61a26b5786532
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Delete 对目录仍没有绑定 exact source/scope/version，能够删除确认后替换进来的新目录。
  证据：`OrganizerExecutor._direct_exists_preflight()` 对目录明确只比较 entry type，完全忽略已
  传入的 `modified_at`；独立临时 Local Storage 探针取得原空目录 evidence 后删除并在同路径创建
  一个新空目录，再以旧 evidence 调用 `execute_direct_delete()`，结果为
  `status='SUCCESS', replacement_directory_deleted=True, race_rejected=False`。此外新增的 Save
  “pre-mutation race”测试并未覆盖其声称的窗口：文件在 `service.save_text()` 调用前就被替换，
  且 patch `OrganizerExecutor` 发生在 service 已构造之后，不会替换 `service._executor`，所以它只
  证明 application admission 能发现旧 digest。修正方向：目录也必须使用 provider 可提供的稳定
  身份/版本证据在最后安全 mutation 边界 fail closed，不能普遍退化为“仍是目录”；补齐空目录
  replacement、递归父目录 replacement，以及真正发生在 application admission 之后、executor
  preflight 之前的 Save/Rename/Delete 竞态测试，断言错误对象零 mutation。
- 文本 stale recovery 仍没有完成所要求的 reload/reapply 闭环，现有测试靠不真实的 fake 获得
  通过。证据：`TextEditorDialog` 第一次点击“重新加载最新内容”只显示放弃确认，第二次才调用
  `onReload()`；该回调清除 stale 并 refetch，而 digest 变化后 effect 直接以服务端内容覆盖本地
  `content`，没有保存或重新应用 stale draft。新增测试在第一次点击后根本没有确认 reload/refetch，
  随即用原 `size=5,digest=digest-1` 再次 Save，fake 却无条件返回 SUCCESS；真实后端会再次返回
  stale。修正方向：保留独立本地 draft，显式取得最新 content/evidence 后提供可理解的 reapply/
  reconcile 动作，再以新 evidence Save；测试必须让旧 evidence 持续 409，并实际走完
  stale→确认 reload→取得新 evidence→reapply→成功 Save，同时证明本地编辑在用户明确放弃前不丢失。
- Delete 后的 browse-state reconciliation 依赖被截断的逐项 outcomes，大目录已删除后仍会留下
  隐藏的 selection/tree 状态。证据：后端允许最多 5000 个 impact entries，却把响应 outcomes
  截为 `MAX_DELETE_PATHS * 4 = 200`；Web 只从这段返回值中提取 `SUCCESS` path 做 prune。独立探针
  删除含 201 个文件的目录得到
  `impact_entries=202, succeeded_items=202, returned_outcomes=200,
  outcomes_truncated=True, top_level_outcome_returned=False, directory_deleted=True`，所以选中的顶层
  目录不会被清理。新增 Web 测试也没有先选择被删文件/目录或建立并断言 visited/known tree state，
  因而没有覆盖上轮要求的隐藏状态。修正方向：在可截断逐项诊断之外返回一个不丢失的、有界顶层
  known-effect/reconciliation 契约（最多 50 个确认目标），Web 只清理已知完全删除的顶层范围并
  保留 partial/failed sibling；用真实选中文件、选中目录、目录 Rename、>200-entry Delete 和
  partial Delete 覆盖 selection/visited/known state。
