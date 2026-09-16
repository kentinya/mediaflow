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
- Rename version admission and last-boundary fencing must not read or hash the complete file and
  must not invoke duplicate-detection `FULL` Hash. Use provider-verifiable stable entry/version
  evidence or a provider-native conditional operation; when the exact observed version cannot be
  proved without a complete content read, fail closed with an actionable unsupported-evidence
  recovery instead of scanning the file or weakening stale detection.
- Delete supports one item and bounded multi-selection. Before mutation, enumerate the full effect
  of directories within explicit item/depth/size limits, show a human-readable impact summary, and
  require one confirmation bound to the exact server-validated scope/version. Reject ResourceLibrary
  roots, stale confirmation, escaped links and any unbounded impact.
- Delete impact, confirmation and OrganizerExecutor last-boundary fencing must not read or hash the
  complete contents of any selected file and must not invoke duplicate-detection `FULL` Hash. Bind
  confirmation to provider-verifiable stable entry/version evidence or a provider-native conditional
  operation; when that proof is unavailable, reject before Task creation or Storage mutation with an
  actionable explanation. Size, `mtime` or a content prefix alone is not exact version evidence.
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
- [ ] Rename and Delete never read/hash an entire file for admission, confirmation, stale detection
      or last-boundary fencing, and never call the configurable duplicate-detection `FULL` Hash path.
      Exact provider version/identity evidence or a native conditional operation is used when
      available; otherwise the operation fails closed before Task creation or mutation. Bounded
      allowlisted text open/save remains the separate content-editing journey capped by
      `MAX_TEXT_BYTES`, not evidence authority for Rename/Delete.
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

The focused direct-file tests must include read-spy providers that fail the test if Rename evidence,
Rename admission, Rename execution, Delete impact, Delete confirmation or Delete execution calls
`Storage.read()`. They must prove stable provider evidence succeeds without a content read, while a
provider with no sufficient exact-version evidence fails closed with zero Task and zero mutation.
Same-size/same-`mtime` replacement regressions remain mandatory and must not be weakened into prefix
sampling. These constraints do not redefine Copy/Move transfer I/O or the separately configured
media-organize duplicate-detection policy, both of which remain outside this Task.

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

## Developer Completion Report — SIXTH CORRECTION LOOP (Task 37.3 FIX REQUIRED)

This is the sixth correction-loop report for the same Task 37.3 (Task Base, Goal and Scope
unchanged). Only the blocker listed in the current B review result and its direct root cause were
fixed, plus the tests that fix requires. The review result and fix-direction sections below are
B-owned and were left untouched.

### Changed Files

Correction-loop changes on top of `59db3a0`:

Backend:

- `mediaflow/domain/direct_files.py` — the complete-content Rename evidence chain is removed
  (`stream_content_digest()`, `RENAME_DIGEST_CHUNK_BYTES` deleted; `entry_version_token()` no longer
  takes or binds a content digest). `EntryVersionEvidence` is now explicitly the bounded
  *text-document* fence only, and new `DirectEntryEvidence` (size, `modified_at`, entry type and a
  mandatory non-empty provider `fingerprint`) is the metadata-only exact-version evidence for
  Rename and Delete. `DirectFileImpactEntry.fingerprint` is now mandatory.
- `mediaflow/application/direct_file_commands.py` — `_content_digest()` and every `Storage.read()`
  call of the Rename path are deleted; `_observed_entry_evidence()` is metadata-only. One shared
  `_require_entry_identity()` now gates Rename evidence, Rename admission and every Delete impact
  entry (including enumerated children), failing closed with `files_direct_entry_identity_unavailable`.
  Delete confirmation re-enumerates the whole scope from `stat`/`list` and hands the executor
  `DirectEntryEvidence`.
- `mediaflow/application/organizer.py` — `execute_direct_rename()` and `execute_direct_delete()` take
  `DirectEntryEvidence` and require it; the digest re-hash in the Rename preflight is deleted. A new
  module-level `_direct_entry_version_mismatch()` performs the last-boundary comparison with one
  `stat`: type + provider identity for every entry, plus size/`mtime` for files, and the stable
  identity segment for directories (whose Local ctime legitimately moves as confirmed children are
  deleted).

Docs:

- `docs/architecture.md` — one paragraph added to the existing UI-V2 direct file-management section
  recording the now-current boundary: Rename/Delete are fenced by provider metadata only, providers
  without a verifiable entry identity fail closed, and the bounded text Read/Write keeps its separate
  loaded-version digest fence.

Tests:

- `tests/test_direct_file_operations.py` — new `_ReadSpyStorage` (fails the test on any content read,
  with a controllable provider identity), fail-closed regressions for Rename and Delete on a provider
  with no entry identity, a zero-read/zero-`FULL`-Hash end-to-end regression, a fingerprint v1→v2
  replacement regression (stale Rename evidence, stale Delete scope, fresh evidence still succeeds),
  a post-admission last-boundary regression for both commands, and an executor-level empty-identity
  regression. The previous complete-content large-file and prefix regressions were replaced, and the
  outdated "plain file operations still work without a fingerprint" expectations were inverted.
- `tests/test_s3_storage.py` — the S3 double now returns the content-derived object validator that
  real S3 returns for a simple PUT (`etag-<md5>` instead of `etag-<size>`), plus a focused test
  proving a same-size replacement changes the published fingerprint, which is what the no-read fence
  relies on for S3-backed libraries.

Web:

- `web/src/features/library/StorageFilesPage.tsx` — one stable `files_direct_entry_identity_unavailable`
  explanation now covers Rename and Delete (the folder-only code is gone), keeping the exact
  actionable recovery copy the backend error carries. No layout, control or flow change.
- `web/src/features/library/StorageFilesPage.test.tsx` — the two provider-refusal tests assert the
  unified reason copy for Delete and Rename.

### Implemented

- **Blocker — Rename still scanned the complete file, and Delete still trusted size/`mtime`.**
  Both halves are fixed, and both are now bounded by metadata only.
  - **Rename is metadata-only at every layer.** Evidence issuance, command admission and the executor's
    last safe boundary now compare entry type, size, modified time and the provider's verifiable entry
    identity, each from one `stat`. `_content_digest()`, `stream_content_digest()`,
    `RENAME_DIGEST_CHUNK_BYTES`, the digest field of the Rename token and the executor's re-hash are all
    deleted, so no code path can scan a file for a Rename.
  - **Delete binds the same provider identity.** `_require_entry_identity()` is now shared by Rename and
    Delete and is applied to the selected targets *and* every enumerated child; the scope digest already
    bound path, type, size, `mtime` and the identity, and it is now guaranteed that all of those carry a
    non-empty provider token. A provider without one fails the whole impact before any Task exists.
  - **Fail closed, never fall back.** An entry the provider cannot identify is refused with
    `files_direct_entry_identity_unavailable` / `entry_identity_unavailable` (400) plus an actionable
    next action, before Task creation, before any `OrganizerExecutor` call and before any Storage
    mutation. Size + `mtime`, a content prefix, a standalone token or a full content read are no longer
    accepted as degraded evidence anywhere.
  - **Both commands now use one structural evidence type.** `DirectEntryEvidence` cannot carry a content
    digest at all, and the executor requires it (a `None` or empty identity is refused), so the previous
    "evidence present but unchecked" and "size/`mtime` fallback" paths are gone rather than merely
    unused. `EntryVersionEvidence` remains the fence of the bounded allowlisted text Save, which is
    capped by `MAX_TEXT_BYTES`.
  - **Per-adapter facts, not fabricated support.** Local publishes `inode:<ino>:ctime:<ns>` for files and
    directories, so its Rename/Delete work with no content read; S3/R2 publish the object validator for
    files, whose version-change semantics are now proven by a test at the adapter level; SMB and
    OpenList publish no identity, so their Rename/Delete fail closed with the actionable error, while
    their bounded text Read/Save keeps working through the separate text fence. Folder Rename/Delete on
    S3 stays unavailable (a directory entry publishes no identity).
  - **Regressions** (`tests/test_direct_file_operations.py`): a read-spy provider whose `read()` fails
    the test, used to prove Rename evidence/admission/execution and Delete impact/confirmation/execution
    are zero-content-read with a stable identity, and to prove the duplicate-detection `FULL` Hash entry
    (`StorageHasher.calculate`) is called zero times; the same provider with an empty identity proves
    zero Task, zero mutation and the stable refusal for a file *and* a folder through the application
    and the API; moving only the fingerprint from v1 to v2 with identical size and `mtime` invalidates
    old Rename evidence (`stale_source`) and an old Delete scope (`stale_confirmation`) with zero reads
    and zero mutations, while freshly issued evidence still completes both; and an executor double that
    moves the identity inside the preflight window proves the post-admission last-boundary refusal for
    Rename and Delete while the original entry stays in place.
  - **Independent probe (B's exact scenario).** A provider-neutral adapter around Local, run from outside
    the test suite, on the previous reviewed checkpoint (`0a441b4`) and on this one:
    - Before (`0a441b4`): a provider publishing no fingerprint issues Rename evidence and a Delete
      impact (2 content reads), then a same-size, same-`mtime` `old-version` → `new-version` swap leaves
      the old Delete confirmation valid: `delete_status='SUCCESS'`, `delete_succeededItems=1`,
      `victim_exists=false`, `storage_mutations=['delete:victim.bin']` — B's reported evidence reproduces
      exactly. On the verifiable provider the same journeys read the file content three times
      (`storage_reads=3`).
    - After (this checkpoint): the fingerprint-less provider refuses both requests with
      `files_direct_entry_identity_unavailable` and reports `storage_reads=0`, `tasks=0`,
      `storage_mutations=[]`, `victim_exists=true`, `victim_bytes='old-version'`. On the verifiable
      provider both journeys complete with `storage_reads=0` and `full_hash_calls=0`.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS (`304 files already formatted`).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m unittest tests.test_direct_file_operations` — PASS (55 tests). Focused additions:
  `test_rename_fails_closed_without_provider_entry_identity`,
  `test_delete_fails_closed_without_provider_entry_identity`,
  `test_rename_and_delete_never_read_content_or_hash_duplicates`,
  `test_provider_identity_change_invalidates_rename_and_delete_evidence`,
  `test_rename_and_delete_refuse_a_version_change_at_the_last_boundary`,
  `test_rename_and_delete_require_provider_version_evidence`,
  `test_executor_refuses_delete_evidence_without_provider_identity`.
- `.venv/bin/python -m unittest tests.test_resource_library_activation tests.test_configuration_objects`
  — PASS (85 tests).
- `.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority
  tests.test_organizer_rollback tests.test_runtime_files_browser tests.test_api_security` — PASS
  (64 tests).
- `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage tests.test_openlist_storage
  tests.test_s3_storage` — PASS (94 tests; includes the new S3 validator regression).
- `.venv/bin/python -m unittest discover -s tests` — 1593 tests: 3 failures, 7 skips (the 7 skips are
  the pre-existing real-service acceptance skips). The three failures are the same
  `test_configuration_status.ConfigurationSnapshotTests.test_hostile_configuration_content_is_never_exposed`,
  `test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_carry_no_forbidden_evidence`
  and `test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_match_the_frontend_fixture`
  documented before; re-verified this round against a pristine detached worktree of this Task's base
  (`git worktree add --detach /tmp/pristine37_base e33a0300` → `.venv/bin/python -m unittest
  tests.test_configuration_status tests.test_manual_operations_contract` → `Ran 10 tests ... FAILED
  (failures=3)`) → `FAIL / PRE-EXISTING / UNRELATED`.
- Independent provider-neutral probe (see above) — before/after evidence recorded.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (`No broken requirements found`).
- `test -z "$(grep -rn -i -E 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"` — PASS (empty match
  set; `rg` is not installed in this environment, so the equivalent `grep` was used).
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE in this environment (exit 1).
  The script's own build/config stages complete; `docker compose up` fails at mount time with
  `service:worker:1 Error response from daemon: invalid mount config for type "bind": bind source path
  does not exist: /tmp/mediaflow-smoke-security-…/mediaflow.json`, the same daemon bind-mount
  visibility limitation recorded in the previous reports. Not a code change; reported as UNAVAILABLE
  rather than PASS.
- `cd web && npm run format:check` — PASS (`All matched files use Prettier code style!`).
- `cd web && npm run typecheck` — PASS.
- `cd web && npm run lint` — PASS.
- `cd web && NODE_ENV=test npx vitest run src/features/library/StorageFilesPage.test.tsx` — PASS
  (25 tests). Truthfulness note: the literal Required Tests command is run without `NODE_ENV=test`; in
  this shell the harness exports `NODE_ENV=production` and react-dom then resolves its production
  build, so the same command fails with `TypeError: React.act is not a function` on an untouched spec as
  well. It is an environment artifact, not a Task regression; `npm run test` sets `NODE_ENV=test`
  itself and passes.
- `cd web && npm run test -- --run` — PASS (443 tests / 33 files).
- `cd web && npm run build` — PASS.
- `cd web && npx playwright test tests/e2e/library-files.spec.ts --project=chromium` — PASS (23 tests).
- `cd web && npm run test:e2e` — 101 PASS; the same 10 pre-existing failures, all in
  `library-file-detail.spec.ts` (7) and `manual-operations.spec.ts` (3). Those specs navigate to
  `/ui-v2/library/file-index*`, whose destinations no longer exist in the navigation model because the
  FileIndex detail routes were removed in `b507edb` (an ancestor of this Task's base). This loop's diff
  touches no route, router or FileIndex file, so they are `FAIL / PRE-EXISTING / UNRELATED`.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist` +
  `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl` — PASS (backup SHA-256
  `27225bd2c66d0246a3e08212f3807b37929f66909e266f2bd2e9fd04ff3c9a37`, identical to the previous loop);
  `dist/` was removed afterwards and is not committed.
- `git diff --check` — PASS. The implementation commit contains only the files listed above;
  `config/alist.json`, credentials, the dirty `docs/pics/文件页.png`, `web/test-results/` references and
  unrelated files are absent.

### Decisions

- **Remove the content digest instead of keeping it for providers without a fingerprint.** B's first
  acceptable direction — a uniform, provider-verifiable metadata fence — is what a bounded
  file-management command needs: the cost of Rename/Delete must not scale with media size. The third
  direction (keep hashing when no fingerprint exists) was rejected because it preserves the unbounded
  read and makes the same command cost wildly different amounts on different providers.
- **One evidence type per journey.** `DirectEntryEvidence` is structurally metadata-only and is
  mandatory at the executor, so a future caller cannot reintroduce a digest fence or run Rename/Delete
  without a proved entry. `EntryVersionEvidence` keeps the digest only for the bounded text Save, whose
  content *is* the object under edit and is capped by `MAX_TEXT_BYTES`.
- **One stable identity-refusal code.** Rename and Delete share
  `files_direct_entry_identity_unavailable`, because they now share exactly the same admission rule;
  the Web maps it to one explanation that covers both operations and keeps the operator's context.
- **Directory fences keep the stable identity segment.** A confirmed recursive Delete removes the
  directory's own children first, which legitimately moves the rest of Local's token (ctime), so the
  inode segment is the identity that survives; a same-name replacement always yields a new inode. Files
  additionally re-check size and `mtime`, which no longer carry any authority by themselves.
- **S3 is enabled on proven adapter semantics, not on faith.** The S3 double previously published
  `etag-<size>`, which cannot separate a same-size replacement, so the adapter's fingerprint could not
  honestly be used as version evidence. The double now models what real S3 returns for a simple PUT
  (`MD5` of the stored bytes; multipart ETags are content-derived composites too) and a test proves the
  validator moves when a same-size replacement is written. SMB and OpenList still publish nothing and
  therefore fail closed.
- **Text Save was not changed.** B scoped the blocker to Rename/Delete; the bounded editor keeps its
  loaded-version digest fence, which is the deliberate content-editing journey.

### Remaining In-Slice Work

- Copy, Move, cross-Storage transfer, destination picker and transfer fallback (RO-6 remainder).
- Upload and Download bounded journeys.
- Rename and Delete (files and folders) stay unavailable on SMB/OpenList-backed ResourceLibraries and
  folder operations stay unavailable on S3-backed ones until those adapters expose a trusted entry
  identity, a version token or a native conditional operation. Bounded text Read/Save and Create remain
  available there.
- Multi-item media Organize execution from the Files selection footer and broader FileIndex
  reconciliation.
- The pre-existing `library-file-detail` / `manual-operations` e2e divergence predates this Task and
  needs a B/A contract decision (replace the specs per RO-11 or restore the routes).
- Slice-level final validation (1536x1024 reference screenshot report, full shell smoke) remains with
  B/A per the Contract.

### Risks / Deviations

- **Rename/Delete availability narrowed on SMB/OpenList.** Those adapters publish no entry identity, so
  Rename and Delete now fail closed there instead of working with a whole-file read. That is the
  behavior B's direction requires; it is a user-visible capability reduction for those providers and is
  recorded here as a deviation from the previous loops, not as a silent change.
- **Local's fence is `inode + ctime`, not a content digest.** A rewrite inside the same filesystem
  timestamp tick still moves ctime, so the same-size/same-`mtime` swap is refused deterministically;
  a filesystem that reuses an inode *and* reports an unchanged ctime for different content would be
  indistinguishable from the provider's own perspective — that is the limit of metadata-only evidence
  and the reason a native conditional operation is the preferred future upgrade.
- **S3 trust rests on real-provider ETag semantics.** The test double now models the documented AWS
  behavior; a deployment behind SSE-KMS or an exotic S3-compatible implementation whose validator does
  not change on replacement would weaken the fence. It is recorded here for B's judgment rather than
  silently assumed.
- The three pre-existing Python failures and the ten pre-existing non-Files e2e failures are documented
  with the base-worktree reproduction; the judgment about their impact on Task PASS belongs to B.
- The docker release security smoke test could not run to completion in this environment (daemon
  bind-mount visibility); it is reported UNAVAILABLE with evidence rather than PASS.
- The pre-existing `web/test-results/` interaction references and the dirty `docs/pics/文件页.png` were
  neither staged nor modified.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: f7fe4b02c94627de6b1db7d6d0fca9dc3ebf876b
Commit: fix(files): fence rename and delete with provider entry identity
Working tree: clean except the pre-existing dirty docs/pics/文件页.png and the ignored build/test
artifacts web/dist/ and web/test-results/ (config/alist.json does not exist in this environment;
no credential or private-path file is staged or committed)
```

## B Review Result

```text
Reviewed: e33a030055a81011a32de507bef6758d48607c9a..0a441b49004760e223efb3322eae55089d77cbbf
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Rename 和 Delete 的 exact-version 安全边界仍未同时满足，且不得通过完整读取/哈希
  媒体文件来修复。Rename 当前在 evidence 签发、应用准入和 OrganizerExecutor 最后边界
  均调用 `stream_content_digest()` 扫描完整文件；这不满足本 Task 新明确的有界、低摩擦
  要求。Delete 则在无 provider fingerprint 时仍只复验 path、type、size 和 `mtime`；
  独立 `_FingerprintlessStorage` 探针在 impact 后将 `old-version` 替换为同尺寸、同
  `mtime` 的 `new-version`，使用旧 `scope_digest` 仍得到
  `status='SUCCESS', victim_exists=False, storage.delete=['victim.bin']`。修正方向：删除
  Rename 的完整内容 digest 证据链；Rename/Delete 统一改用 provider 可验证的稳定
  entry/version evidence 或 provider-native conditional operation，无法证明 exact version 时在创建
  Task 或调用 mutation 前 fail closed。增加 read-spy 回归，证明两个操作的 evidence、
  admission、confirmation 和执行器边界都不调用 `Storage.read()`；同时保留同尺寸同
  `mtime` 替换必须拒绝、零 Task、零 mutation 的确定性断言。

## B Fix Implementation Direction

下面是当前 `SAME TASK FIX LOOP` 的推荐实现路径，用于消除上述唯一 blocker；它不改变
Task ID、Task Base、Goal、Implementation Scope 或 Slice Contract，也不授权 Copy、Move、
duplicate `FULL` Hash 或 Storage redesign。

1. **移除 Rename 的完整内容证据链。** 删除 Rename evidence、Rename admission 和
   `OrganizerExecutor` Rename preflight 对 `stream_content_digest()`、`_content_digest()` 和
   `Storage.read()` 的调用；Rename 生成 token 时传入 `content_digest=None`。如果
   `stream_content_digest()` 和 Rename digest 常量不再有其他合法调用，应一并删除，防止以后
   误用。`EntryVersionEvidence.digest` 可以继续只服务于受 `MAX_TEXT_BYTES` 限制的文本 Save，
   不得再作为 Rename/Delete 的证据。
2. **统一使用 metadata-only provider validator。** 复用现有可选
   `StorageEntry.fingerprint` 作为本 Task 的 provider entry/version evidence 槽位。Rename token
   与 Delete `scopeDigest` 必须至少绑定 Active ResourceLibrary、规范化相对路径、entry type、
   size、`modified_at` 和非空 fingerprint；fingerprint 不返回给浏览器，只进入服务端 evidence。
   `size + mtime`、单独 ETag 文本、路径存在性或文件内容前缀都不能在缺少可信 provider
   validator 时充当降级证据。
3. **在准入阶段 fail closed。** 抽取一个 Rename/Delete 共用的 exact-entry-evidence 校验。
   Rename evidence 请求遇到空 fingerprint 时立即返回稳定的
   `files_direct_entry_identity_unavailable`（或等价稳定分类）。Delete impact 枚举出的每个文件
   和目录都必须通过相同校验；任一项没有可信 fingerprint，整次 impact/confirmation 失败，且
   不创建 Task、不调用 `OrganizerExecutor`、不执行 Storage mutation。错误要说明当前 Storage
   无法验证该 entry 的版本，并给出更换/完善支持该 validator 的 Storage provider 等安全下一步。
4. **在所有安全边界只重新 `stat/list`。** Rename 在 evidence 签发、提交 admission 和
   `execute_direct_rename()` 调用 `Storage.move()` 前重新 `stat()` 并比较上述完整 metadata
   evidence。Delete 在 impact、确认提交时的全 scope 重枚举，以及每个
   `execute_direct_delete()` mutation 的最后边界重新 `stat/list`；fingerprint、type、路径或其他
   被绑定字段不一致即 stale。证据缺失与 stale 都不能触发内容读取、prefix sampling、duplicate
   hashing 或 mutation。
5. **按现有 adapter 事实决定是否可用，不伪造支持。** Local 当前提供
   `inode + ctime_ns` fingerprint，可以走无内容读取的验证路径。S3/R2 当前把对象 validator
   放入 fingerprint；只有该 validator 满足 adapter 已声明并由测试证明的版本变化语义时才能
   使用，若需要严格对象世代而现有 token 无法证明，则同样 fail closed，未来可另行采用
   VersionId/native conditional operation。SMB 和 OpenList 当前没有 fingerprint，必须暂时走
   actionable fail-closed 路径；不得用完整读取、size/mtime 或自行拼接弱 token 来“恢复”按钮。
   后续 provider 若能从 metadata/API 暴露可信 file ID、change token、VersionId 或原生条件
   Rename/Delete，才可在不读取内容的前提下启用。
6. **保持 Web/API 行为一致。** 无 validator 时，API 返回上述稳定错误和恢复动作；Web 在
   evidence/impact 请求失败后保留当前选择和目录状态，展示同一可执行说明，不进入确认或伪造
   成功状态。浏览器仍只持有 opaque Rename evidence / Delete `scopeDigest`，不暴露 provider
   token。
7. **增加确定性回归。** 使用一个 `read()` 会立即使测试失败的 read-spy Storage，分别证明
   Rename evidence/admission/execution 和 Delete impact/confirmation/execution 的成功及失败
   路径均为零内容读取，并证明 duplicate `FULL` Hash 入口调用次数为零。稳定 fingerprint 路径
   应成功；空 fingerprint 应为零 Task、零 mutation；在保持 size、`mtime` 不变时将 fingerprint
   从 v1 换为 v2，旧 Rename evidence 和旧 Delete scope 必须失效。还要覆盖 admission 后、
   executor mutation 前发生版本变化的最后边界拒绝，并断言原 entry 未被 Rename/Delete。

实现后的预期成本只与 metadata 查询和 Delete 的有界目录枚举有关，不与单个文件字节大小
相关；因此 1 KB 与 100 GB 文件的 Rename/Delete 版本验证都不读取文件内容。Copy/Move 自身的
传输 I/O、bounded text open/save 和显式配置的 duplicate `FULL` Hash 仍按各自独立语义处理，
不属于这个 blocker 的实现范围。
