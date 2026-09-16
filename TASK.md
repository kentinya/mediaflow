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

## Developer Completion Report — FIFTH CORRECTION LOOP (Task 37.3 FIX REQUIRED)

This is the fifth correction-loop report for the same Task 37.3 (Task Base, Goal and Scope
unchanged). Only the blocker listed in the current B review result and its direct root cause were
fixed, plus the tests that fix requires. The review result section below is B-owned and was left
untouched.

### Changed Files

Correction-loop changes on top of `c8c0ac2`:

Backend:

- `mediaflow/domain/direct_files.py` — the bounded-prefix evidence helpers
  (`MAX_RENAME_SAMPLE_BYTES`, `rename_sample_size()`, `read_bounded_prefix()`) are removed and
  replaced by `RENAME_DIGEST_CHUNK_BYTES` plus `stream_content_digest()`, which returns the SHA-256
  digest **and the byte count** of one complete provider stream; the `EntryVersionEvidence.digest`
  and `RenameEvidence` contracts now state that a Rename digest always covers the complete content.
- `mediaflow/application/direct_file_commands.py` — `_content_digest()` hashes the complete content
  of the observed file and refuses a stream whose byte count no longer matches the observed size;
  the evidence route and the command admission both use it.
- `mediaflow/application/organizer.py` — the last-safe-boundary `_direct_rename_preflight()` re-hashes
  the complete content and compares both the digest and the byte count against the evidence.

Tests:

- `tests/test_direct_file_operations.py` — two deterministic large-file regressions on a provider
  that publishes no fingerprint: a swap beyond the evidence prefix refused at admission, and the
  same swap refused at the executor's last safe boundary.

No Web file changed in this loop: the evidence contract shape is unchanged, and the browser still
only echoes the opaque token the backend issued.

### Implemented

- **Blocker — large-file Rename evidence did not bind the exact source version.** The evidence,
  admission and last-boundary fences all hashed only the leading 256 KiB of a file, so on a provider
  without a fingerprint a same-size change *beyond* that prefix, with the modification time restored,
  left the evidence matching and the replacement was renamed away.
  - **Complete streamed digest.** Every renamable file is now anchored by the SHA-256 digest of its
    complete content at all three layers (server-issued evidence, application admission, executor
    last safe boundary). Nothing about a version can change outside the evidence any more; the read
    is streamed in 1 MiB chunks, so memory stays constant and no prefix, offset or size is excluded.
  - **Byte-count invariant.** `stream_content_digest()` also returns the number of bytes it hashed,
    and both the admission and the last boundary require that count to equal the observed size, so a
    file that grows or shrinks while it is being read is refused as a changed source instead of being
    hashed into an ambiguous value. `rename_sample_size()`/`MAX_RENAME_SAMPLE_BYTES` and the
    prefix-reader helper are deleted rather than left unused.
  - **Uniform for every provider.** The complete-content fence is applied whether or not the provider
    publishes a fingerprint: Local's `inode:…:ctime:…` token does not change when a file is rewritten
    in place inside the same timestamp tick either, so a fingerprint-only path would keep the same
    hole. Providers without a fingerprint keep a working Rename instead of failing closed.
  - **Regressions** (`tests/test_direct_file_operations.py`): a >256 KiB file whose leading block,
    size and mtime are all kept identical while only bytes beyond the block change is refused with
    `files_direct_stale_source` / 409, zero Tasks and zero mutations at admission, and refused as
    `FAILED` / `source_changed` when the same swap happens inside the executor's preflight window.
    Both run on the provider-neutral fingerprint-less fake, so they are deterministic on any
    filesystem timestamp granularity.
  - **Independent probe (B's exact scenario).** A provider-neutral adapter around Local that drops
    every fingerprint, a 320 KiB file, evidence obtained from the API, then only the bytes beyond the
    256 KiB prefix replaced with same-size content and the original `mtime` restored via
    `os.utime(..., ns=…)`:
    - Before (`c8c0ac2`, the reviewed checkpoint): `rejected=false`, `http_status=200`,
      `status='SUCCESS'`, `source_exists=false`, `target_exists=true`, `target_tail='new-tail'`,
      `storage_moves=1` — B's reported evidence reproduces exactly.
    - After (this checkpoint): `rejected=true`, `http_status=409`,
      `error_code='files_direct_stale_source'`, `source_exists=true`, `target_exists=false`,
      `source_tail='new-tail'`, `storage_moves=0`, with `head_unchanged=true` (the whole leading
      block is byte-identical), so only the complete-content digest can be what refused it.
    - The small-file probe from the previous loop still refuses the same-size/same-mtime swap with
      `409 files_direct_stale_source`, so the earlier determinism is preserved.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS (exit 0, `304 files already formatted`).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m unittest tests.test_direct_file_operations` — PASS (53 tests: the 51 previous
  plus the 2 new large-file regressions).
- `.venv/bin/python -m unittest tests.test_resource_library_activation tests.test_configuration_objects`
  — PASS (85 tests).
- `.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority
  tests.test_organizer_rollback tests.test_runtime_files_browser tests.test_api_security` — PASS
  (64 tests).
- `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage
  tests.test_openlist_storage tests.test_s3_storage` — PASS (93 tests).
- `.venv/bin/python -m unittest discover -s tests` — 1590 tests: 3 failures, 7 skips (the 7 skips are
  the pre-existing real-service acceptance skips). The three failures are the same
  `test_configuration_status.ConfigurationSnapshotTests.test_hostile_configuration_content_is_never_exposed`,
  `test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_carry_no_forbidden_evidence`
  and `test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_match_the_frontend_fixture`
  documented before; re-verified this round against a pristine detached worktree of this Task's base
  (`git worktree add --detach /tmp/pristine37_base e33a0300` → `.venv/bin/python -m unittest
  tests.test_configuration_status tests.test_manual_operations_contract` → `Ran 10 tests ... FAILED
  (failures=3)`) → `FAIL / PRE-EXISTING / UNRELATED`.
- Independent provider-neutral large-file probe (see above) — before/after evidence recorded.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (`No broken requirements found`).
- `test -z "$(grep -rn -i -E 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"` — PASS (empty match
  set; `rg` is not installed in this environment, so the equivalent `grep` was used).
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE in this environment. The
  script's own build/config stages complete; `docker compose up` fails at mount time with
  `invalid mount config for type "bind": bind source path does not exist:
  /tmp/mediaflow-smoke-security-tf_uqg_8/mediaflow.json` (and the sibling mounts), the same daemon
  bind-mount visibility limitation recorded in the previous reports. Not a code change; reported as
  UNAVAILABLE rather than PASS.
- `cd web && npm run format:check` — PASS (`All matched files use Prettier code style!`).
- `cd web && npm run typecheck` / `npm run lint` — PASS.
- `cd web && NODE_ENV=test npx vitest run src/features/library/StorageFilesPage.test.tsx
  src/entities/library/direct-files.test.ts` — PASS (38 tests / 2 files). Truthfulness note: run
  verbatim without `NODE_ENV=test` in this shell the command fails (`TypeError: React.act is not a
  function`) because the harness exports `NODE_ENV=production` and react-dom then resolves its
  production build; the same failure reproduces on an untouched spec
  (`src/features/dashboard/DashboardPage.test.tsx`, 9/9). It is an environment artifact, not a Task
  regression; `npm run test` sets `NODE_ENV=test` itself.
- `cd web && npm run test -- --run` — PASS (443 tests / 33 files).
- `cd web && npm run build` — PASS.
- `cd web && npx playwright test tests/e2e/library-files.spec.ts --project=chromium` — PASS
  (23 tests).
- `cd web && npm run test:e2e` — 101 PASS; the same 10 pre-existing failures, all in
  `library-file-detail.spec.ts` (7) and `manual-operations.spec.ts` (3). Those specs navigate to
  `/ui-v2/library/file-index*`, whose destinations no longer exist in the navigation model because
  the FileIndex detail routes were removed in `b507edb` (an ancestor of this Task's base). This
  loop's diff touches no route, router or FileIndex file, so they are
  `FAIL / PRE-EXISTING / UNRELATED`.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist` +
  `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl` — PASS (backup SHA-256
  `27225bd2c66d0246a3e08212f3807b37929f66909e266f2bd2e9fd04ff3c9a37`); `dist/` was removed
  afterwards and is not committed.
- `git diff --check` — PASS. The implementation commit contains only the four files listed above;
  `config/alist.json`, credentials, the dirty `docs/pics/文件页.png`, `web/test-results/` references
  and unrelated files are absent.

### Decisions

- **Complete content, not a sample.** B's blocker is correct: no prefix can prove the version of a
  file whose remaining bytes changed, and on a provider without a fingerprint nothing else in the
  evidence moves. The fix is the complete streamed digest B listed first among the acceptable
  directions, applied uniformly, rather than a fail-closed restriction that would remove Rename from
  SMB/OpenList-backed libraries entirely.
- **Streaming keeps the read memory-bounded.** The digest is computed chunk by chunk
  (`RENAME_DIGEST_CHUNK_BYTES`), so a Rename never buffers a file in memory; the byte count returned
  by the same pass adds a cheap growth/shrink invariant the prefix reader could not express.
- **One rule, three layers, unchanged shape.** The evidence token, the API document, the
  `expected.{size, modifiedAt, evidence}` request and the Web dialog are all unchanged, so this
  correction narrows the fence without changing the contract B reviewed.
- **Folder Rename keeps its existing fail-closed rule** (a directory has no content to hash; a
  provider without a directory identity cannot prove the folder), exactly as in the previous loop.
- **Delete was not changed.** B's blocker is scoped to Rename. The bounded Delete impact enumerates
  up to 5000 entries, so hashing every selected file's complete content there would change that
  journey's cost model materially; that is B's/A's call, and it is recorded under Risks instead of
  being changed unrequested.

### Remaining In-Slice Work

- Copy, Move, cross-Storage transfer, destination picker and transfer fallback (RO-6 remainder).
- Upload and Download bounded journeys.
- Folder Rename and folder Delete on SMB/OpenList/S3-backed ResourceLibraries stay unavailable until
  those adapters expose a comparable stable directory identity. File Rename and file Delete work
  there.
- Multi-item media Organize execution from the Files selection footer and broader FileIndex
  reconciliation.
- The pre-existing `library-file-detail` / `manual-operations` e2e divergence predates this Task and
  needs a B/A contract decision (replace the specs per RO-11 or restore the routes).
- Slice-level final validation (1536x1024 reference screenshot report, full shell smoke) remains
  with B/A per the Contract.

### Risks / Deviations

- **Cost of the complete-content fence.** Issuing, admitting and last-boundary-verifying one Rename
  now reads the file three times end to end (bounded memory, I/O proportional to file size), which
  is noticeable for very large media on remote Storage. That is the price of provable version binding
  while no provider exposes a conditional move or a stable per-version token; if one is added later,
  the digest can be replaced by that evidence without changing the surrounding contract.
- **File-level Delete evidence on fingerprint-less providers is still size + mtime** (the design B
  accepted in the earlier loops); this Task's Rename is now stricter than Delete for the same file.
  Flagged for B's judgment; not changed here because the blocker was scoped to Rename and the bounded
  Delete impact has a different cost model.
- The three pre-existing Python failures and the ten pre-existing non-Files e2e failures are
  documented with the base-worktree reproduction; the judgment about their impact on Task PASS
  belongs to B.
- The docker release security smoke test could not run to completion in this environment (daemon
  bind-mount visibility); it is reported UNAVAILABLE with evidence rather than PASS.
- The literal `npx vitest` gate from the Required Tests list is sensitive to this shell's exported
  `NODE_ENV=production`; the environment artifact is recorded above instead of being reported as an
  untrue PASS.
- The pre-existing `web/test-results/` interaction references and the dirty `docs/pics/文件页.png`
  were neither staged nor modified.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 0a441b49004760e223efb3322eae55089d77cbbf
Commit: fix(files): prove the complete rename source version
Working tree: clean except the pre-existing dirty docs/pics/文件页.png and the ignored build/test
artifacts web/dist/ and web/test-results/ (config/alist.json does not exist in this environment;
no credential or private-path file is staged or committed)
```

## B Review Result

```text
Reviewed: e33a030055a81011a32de507bef6758d48607c9a..d3caebc5b3a720e05fe30f7014f2c6d7bf2c0fdd
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Rename 的大文件 evidence 仍未绑定 exact source/version，未满足 changed-source
  fail-closed 和 Task 的 stale-source Acceptance。证据：独立 provider-neutral 探针使用不提供
  fingerprint 的 Storage，对大于 256 KiB 的文件取得 Rename evidence 后，仅将前缀之后的
  `old-tail` 改为同尺寸 `new-tail` 并恢复原 `mtime`；旧 evidence 仍被接受，实际结果为
  `status='SUCCESS', source_exists=False, target_exists=True, target_tail='new-tail'`。根因是
  `MAX_RENAME_SAMPLE_BYTES = 256 * 1024` 且 `rename_sample_size()` 只哈希文件前缀；当 provider
  无 fingerprint 时，后续内容不在 admission 或 OrganizerExecutor 的最后安全边界证据中。
  修正方向：对所有可 Rename 的文件绑定并复验能证明完整条目版本的服务端 evidence
  （完整流式 digest、provider 条件操作/稳定版本证据，或在无法可靠验证时 fail closed）；
  增加超过 256 KiB、改变前缀之后内容、同尺寸同 `mtime` 且无 provider fingerprint 的
  确定性 admission 与最后边界回归，证明旧 evidence 不会移动新版本，不得放宽 stale 断言。
