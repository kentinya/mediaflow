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
