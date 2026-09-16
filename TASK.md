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

## Developer Completion Report — THIRD CORRECTION LOOP (Task 37.3 FIX REQUIRED)

This is the third correction-loop report for the same Task 37.3 (Task Base, Goal and Scope
unchanged). Only the two blockers listed in the current `## B Review Result` and their direct root
causes were fixed, plus the tests those fixes require. The review result section itself is B-owned
and was left untouched.

### Changed Files

Correction-loop changes on top of `7fe5868`:

Backend:

- `mediaflow/application/organizer.py` — `_direct_exists_preflight()` fails a bound-evidence
  directory Delete closed whenever the confirmed evidence or the observed entry carries no
  verifiable directory identity, instead of accepting "it is still a directory" or "it is empty"
  as identity; `_execution_log_category()` classifies that refusal as `unsupported_capability`.
- `mediaflow/application/direct_file_commands.py` — new `_require_directory_identity()` admission
  refusal with a stable code/category/status/next action; the impact preview and the confirmed
  execution now build their bounded scope through one shared `_impact_entries()` helper, so
  folder-delete admission cannot diverge between the two entry points; `_enumerate_into()` applies
  the same rule to nested directories; `_result_error_category()` maps the executor's
  last-boundary refusal for durable item outcomes.

Web:

- `web/src/features/library/StorageFilesPage.tsx` — Files explains
  `files_direct_directory_identity_unavailable` (and the executor's `unsupported_capability`
  outcome) with an actionable reason instead of a generic command failure.
- `web/src/features/library/StorageFilesPage.test.tsx` — focused regression for that refusal: the
  Delete dialog shows the reason, keeps the confirmation unavailable and never submits a command.

Tests:

- `tests/test_direct_file_operations.py` — the Ruff-non-compliant assertion at the location B
  reported is formatted; new `_FingerprintlessStorage` provider-neutral fake (Local with every
  entry fingerprint removed, standing in for SMB/OpenList entries and S3 directory entries) plus
  two regressions: the executor probe and the application/API journey.

### Implemented

- **Blocker 1 — fingerprint-less directory Delete fails closed.** A directory Delete is now
  admitted only when the provider exposes a verifiable per-directory identity:
  - The executor re-verifies the confirmed evidence at the last safe boundary. When either the
    confirmed evidence or the observed entry has no directory identity segment the mutation is
    refused with the stable, secret-free reason `directory delete requires a verifiable directory
    identity from this Storage provider`; the result is `FAILED` with
    `effect_certainty=NONE` and no uncertain effect, i.e. the mutating Storage call never runs.
    The previous emptiness fallback is removed: an empty directory is not proof that it is the
    confirmed directory.
  - The application refuses the whole command at admission with
    `files_direct_directory_identity_unavailable` / category `directory_identity_unavailable` /
    `400` / `sideEffects: none` / `durableState: storage_unchanged` and an actionable
    `nextAction`, before a Task exists and before any Storage mutation. Both the impact preview
    and the confirmed execution use the same shared enumeration, and the rule also covers nested
    directories inside a confirmed recursive scope, so a mixed selection mutates nothing at all.
  - Local-backed ResourceLibraries (fingerprints present) keep the existing behavior: the
    replaced-directory, replaced-recursive-parent and confirmed recursive-delete regressions all
    still pass, and the `failure_retained`/`knownEffects` contracts are unchanged.
  - Regression evidence: a fingerprint-less fake proves that old evidence cannot delete a same-name
    replacement directory (`status='FAILED'`, replacement retained, exactly one Storage delete in
    the whole test — the probe's own), that the application and the API refuse with zero mutation
    and zero Tasks, and that plain file Delete still succeeds on the same provider, so the refusal
    is bounded to directories whose identity cannot be verified.
  - Independent before/after reproduction outside the test double: a delegating provider-neutral
    wrapper around Local Storage that drops every identity token was run against a pristine
    detached worktree of `7fe5868` and against this checkpoint. Before →
    `status='SUCCESS'`, `replacement_directory_deleted=True` and two Storage deletes (the probe's
    own plus the erroneous executor delete), i.e. B's reported evidence. After →
    `status='FAILED'`, `errors=('directory delete requires a verifiable directory identity from
    this Storage provider',)`, `replacement_directory_deleted=False` and the only Storage delete
    is the probe's own: zero erroneous mutation.
- **Blocker 2 — truthful gates.** The actual Ruff violation is fixed at its source (only the
  reported test fragment was reformatted; no assertion was weakened, deleted or skipped), and the
  results below are the ones this loop actually observed, including the environment-specific facts.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `.venv/bin/ruff format --check .` — PASS (exit 0, `304 files already formatted`). This is the
  gate B reported: before the fix it exited 1 on `tests/test_direct_file_operations.py:877`.
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m unittest tests.test_direct_file_operations` — PASS (48 tests; the 46
  previous tests plus the 2 new fingerprint-less regressions).
- Independent provider-neutral probe (not a repository test double): a delegating wrapper around
  Local Storage that removes every entry fingerprint, executed with the pristine worktree and this
  checkpoint on the import path. Before (`7fe5868`): `status='SUCCESS'`,
  `replacement_directory_deleted=True`, two Storage deletes. After (this checkpoint):
  `status='FAILED'` with the verifiable-directory-identity refusal,
  `replacement_directory_deleted=False`, one Storage delete (the probe's own). B's probe evidence
  no longer reproduces.
- `.venv/bin/python -m unittest tests.test_resource_library_activation
  tests.test_configuration_objects` — PASS (85 tests).
- `.venv/bin/python -m unittest tests.test_organizer
  tests.test_organizer_mutation_authority tests.test_organizer_rollback
  tests.test_runtime_files_browser tests.test_api_security` — PASS (64 tests).
- `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage
  tests.test_openlist_storage tests.test_s3_storage` — PASS (93 tests).
- `.venv/bin/python -m unittest discover -s tests` — 1585 tests: 3 failures, 7 skips (the 7 skips
  are the pre-existing real-service acceptance skips). The three failures are the same
  `test_configuration_status.ConfigurationSnapshotTests.
  test_hostile_configuration_content_is_never_exposed`,
  `test_manual_operations_contract.ManualOperationsContractTests.
  test_real_api_documents_carry_no_forbidden_evidence` and
  `test_manual_operations_contract.ManualOperationsContractTests.
  test_real_api_documents_match_the_frontend_fixture` documented before. Re-verified this round
  against a pristine detached worktree of `7fe5868`
  (`git worktree add --detach /tmp/pristine37 7fe5868` →
  `.venv/bin/python -m unittest tests.test_configuration_status
  tests.test_manual_operations_contract` → `Ran 10 tests ... FAILED (failures=3)`), so they are
  `FAIL / PRE-EXISTING / UNRELATED`.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (`No broken requirements found`).
- `test -z "$(grep -rn -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"` — PASS (empty match
  set; `rg` is not installed in this environment, so the equivalent `grep` was used).
- `python3 scripts/docker_release_security_smoke_test.py` — UNAVAILABLE in this environment. The
  script's own build/config stages complete; `docker compose up` fails at mount time with
  `invalid mount config for type "bind": bind source path does not exist:
  /tmp/mediaflow-smoke-security-it2x3gtg/deployment.env` (and the two sibling mounts), the same
  daemon bind-mount visibility limitation recorded in the previous report, reproduced again this
  round on a pristine worktree. Not a code change; reported as UNAVAILABLE rather than PASS.
- `cd web && npm run format:check` / `npm run typecheck` / `npm run lint` — PASS.
- `cd web && npx vitest run src/features/library/StorageFilesPage.test.tsx` — PASS (23 tests,
  including the new refusal regression) when run with `NODE_ENV=test`. Truthfulness note: run
  verbatim in this session's shell the command fails 22/22 with `TypeError: React.act is not a
  function`, because the harness exports `NODE_ENV=production` and react-dom then resolves its
  production build. The same failure reproduces identically on an untouched spec
  (`src/features/dashboard/DashboardPage.test.tsx`, 9/9 failed, same error), so it is an
  environment artifact of this shell rather than a Task regression. `npm run test` sets
  `NODE_ENV=test` itself, which is why the suite command below is green.
- `cd web && npm run test -- --run` — PASS (439 tests / 33 files).
- `cd web && npm run build` — PASS.
- `cd web && npx playwright test tests/e2e/library-files.spec.ts --project=chromium` — PASS
  (23 tests).
- `cd web && npm run test:e2e` — 101 PASS; 10 failures, all in `library-file-detail.spec.ts` (7)
  and `manual-operations.spec.ts` (3). These are the pre-existing divergence documented before:
  the FileIndex detail routes were removed from the router in `b507edb`, before this Task's base
  `e33a030`, while those specs still navigate to `/ui-v2/library/file-index*`. This loop's diff
  touches no route, router or FileIndex file, so they are `FAIL / PRE-EXISTING / UNRELATED`.
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist` +
  `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl` — PASS
  (`Status: PASS`, backup SHA-256 `27225bd2c66d0246a3e08212f3807b37929f66909e266f2bd2e9fd04ff3c9a37`);
  `dist/` was removed afterwards and is not committed.
- `git diff --check` — PASS. The staged manifest contains only the five files listed above;
  `config/alist.json`, credentials, the dirty `docs/pics/文件页.png`, `web/test-results/`
  references and unrelated files are absent.

### Decisions

- **Refuse, do not guess.** For a provider without a verifiable directory identity the folder
  Delete is refused outright (B's first correction direction) instead of inventing identity
  evidence. Adding a new provider identity/capability to the SMB/OpenList/S3 adapters is outside
  this Task ("New Storage adapters/capabilities, broad Storage redesign" is an explicit non-goal),
  and no local heuristic can separate a same-name empty replacement from the confirmed directory
  at the last safe boundary without a provider-side conditional delete. The refusal is explicit,
  stable, bounded, actionable and zero-mutation, and it is scoped to directories: file Delete,
  Create Folder/Text, Rename, bounded text Edit, ResourceLibrary Save and ResourceLibrary removal
  are unchanged.
- **Two fences, one rule.** Admission refuses the command before a Task or any mutation exists,
  and the executor fails closed again at the last safe boundary if it is ever reached with such
  evidence, so the safety invariant does not rest on a single layer. The shared `_impact_entries()`
  helper exists so the impact preview and the confirmed execution cannot drift apart on admission
  rules.
- The new refusal is a normal, explainable application failure: stable code, category, durable
  state, side-effect and retry facts plus an actionable next action (delete files individually, or
  use a provider that verifies directory identity), and Files renders that reason in place of a
  generic failure.

### Remaining In-Slice Work

- Copy, Move, cross-Storage transfer, destination picker and transfer fallback (RO-6 remainder).
- Upload and Download bounded journeys.
- Folder (directory) Delete on SMB/OpenList/S3-backed ResourceLibraries stays unavailable until
  those adapters expose a comparable stable directory identity or conditional delete; file-level
  Delete works there. This is a provider-capability gap, not a new Task here.
- Multi-item media Organize execution from the Files selection footer and broader FileIndex
  reconciliation.
- The pre-existing `library-file-detail` / `manual-operations` e2e divergence (FileIndex detail
  routes removed from the router while their e2e specs and fake fixtures remain) predates this Task
  and needs a B/A contract decision (replace the specs per RO-11 or restore the routes).
- Slice-level final validation (1536x1024 reference screenshot report, full shell smoke) remains
  with B/A per the Contract.

### Risks / Deviations

- Product-visible change: folder Delete is now refused with an actionable reason and zero mutation
  on Storage providers that publish no directory identity (SMB, OpenList, S3 directory entries).
  File-level Delete keeps working on those providers. If B/A consider folder Delete with a weaker
  fence preferable, the resolution requires the provider identity/capability work this Task
  explicitly defers.
- The three pre-existing Python failures and the ten pre-existing non-Files e2e failures are
  documented with this round's pristine-worktree reproduction; the judgment about their impact on
  Task PASS belongs to B.
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
Head SHA: e26d1bfe9899cf1594d52c5a5b750ef4b812884f
Commit: e26d1bf fix(files): fail closed on folder deletes without provider identity
Working tree: clean except the pre-existing dirty docs/pics/文件页.png and
ignored artifacts (web/dist/, web/test-results/, config/alist.json)
```

## B Review Result

```text
Reviewed: e33a030055a81011a32de507bef6758d48607c9a..7fe58685d05c06e4c03aff7cd4d51060873159f5
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Directory Delete 在不提供 fingerprint 的 Storage provider 上仍会删除确认后替换进来的新空
  目录，未满足 exact source/scope/version 和 changed-source fail-closed。证据：SMB 与 OpenList
  adapter 构造的 `StorageEntry` 没有 fingerprint，S3 目录条目也没有稳定目录 fingerprint；当前
  `_direct_exists_preflight()` 对这种目录只要求 `storage.list(path)` 为空。独立 provider-neutral
  探针用一个去除 Local fingerprint 的 Storage，取得原空目录 evidence 后以同路径新空目录替换，
  再提交旧 evidence；结果为
  `status='SUCCESS', replacement_directory_deleted=True, race_rejected=False`。Developer 报告也明确
  承认 fingerprint-less provider 无法区分该 replacement；把它记录为 provider limitation 不能
  放宽 Slice 的无错误删除安全不变式。修正方向：没有可验证稳定目录身份时必须在 mutation admission
  fail closed（例如把该目录 Delete 明确判为当前 provider 不支持，并给出可操作原因），或让对应
  provider 提供足以比较的稳定身份/条件删除能力；新增 fingerprint-less 空目录 replacement 回归，
  证明旧确认不会删除新目录。不得因为目录为空就推定它仍是用户确认的对象。
- Required Test 结果不实且当前 gate 未通过。证据：独立运行
  `.venv/bin/ruff format --check .` 返回非零，指出
  `tests/test_direct_file_operations.py:877` 的三行 `self.assertEqual(...)` 应格式化为单行；Developer
  Completion Report 将同一命令记录为 `PASS (304 files)`。Task 的 T4 Acceptance 明确要求全部
  assigned gates 通过且结果如实。修正方向：仅格式化该测试文件的实际不合规片段，重新运行并如实
  记录 Ruff format/check 及受影响聚焦测试；不得放宽或删除断言。
