# Task 26.4 — Storage Browser and Bounded Path Selection

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 26.4
Parent Slice: 26 — Web-first Fresh Setup and Storage Completion
Status: READY FOR B REVIEW
Task Base: b662c9073c17d724045488db378d78174ed71abe
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the provider-neutral setup portion of Slice 26 RO-5 and advance RO-6: an authenticated
operator can lazily browse one configured Storage directory through API and Operator Web, navigate
only within that Storage root, and choose a bounded Storage-relative directory for ResourceLibrary
or MediaLibrary setup. The browser and picker remain read-only and never become the File Catalog or
a general host-filesystem browser.

## Operator Journey

- **User goal:** choose safe source and destination directories during first setup without
  hand-authoring host paths or browsing outside a configured Storage root.
- **Entry:** open a Storage Browser from a Draft or Validated setup revision, or open the directory
  picker from the ResourceLibrary or MediaLibrary guided form.
- **Visible state:** selected Storage, canonical Storage-relative path, root and breadcrumbs,
  bounded immediate-child entries, continuation state, directory-only selection affordances, and
  bounded failure evidence when a read cannot complete.
- **Action:** navigate one directory at a time, continue a bounded page, return through breadcrumbs,
  retry a safe read, or select the current directory and submit the existing version-checked Draft
  mutation.
- **Success:** API and Web show the selected Storage-relative directory in the correct library form;
  the Draft contains the selection and remains the only changed configuration state.
- **Failure:** invalid or escaping input, stale/cross-boundary cursor, unavailable Storage,
  permission/authentication/timeout/not-found failure, or concurrent Draft change blocks the read or
  selection and does not discard the Draft or alter the prior Active revision.
- **Recovery:** correct the displayed path, credentials/reference readiness, Storage/root or Draft
  version as indicated; then retry the bounded read or refresh and resubmit the same selection.

## Why This Task Exists

Task 26.3 makes configured Storage reachability and read-only evidence visible, but the first setup
journey still cannot inspect a configured root or select source and destination directories without
hand-entering paths. The existing Storage ports and adapters expose directory-level list/stat
operations, while the managed object forms already persist Storage-relative library paths. The next
largest independent unit is therefore one shared bounded browser plus the path-selection flow that
feeds those existing library mutations.

This unit must establish a stable provider-neutral browser contract for later Slice 27 reuse. It
does not turn the current File Catalog into a Storage-backed Files surface and does not implement
the later scan/Preview/Organize lifecycle.

## Implementation Scope

Implement one read-only setup vertical path:

```text
bounded Storage page/cursor contract and path normalization
→ Storage adapter pagination/confinement hooks where required
→ shared Application Storage Browser and directory-selection behavior
→ authenticated typed API browse/select surfaces
→ Operator Web browser, breadcrumbs and ResourceLibrary/MediaLibrary picker integration
→ focused, safety, RBAC, integration and full regression
```

Required behavior:

- Browse a selected Storage from a Draft or Validated setup revision using the configured Storage
  abstraction only. The request identifies one Storage and one Storage-relative directory; the root
  is represented canonically and no host-absolute path is accepted as a browser path.
- Return a bounded, deterministic listing of immediate child entries (files and directories) with a
  provider-neutral opaque cursor or equivalent page boundary when the directory exceeds the server
  limit. The cursor is integrity-protected or otherwise unforgeable, bound to the exact revision
  identity, Storage, normalized path and page request, contains no secret or raw provider token, and
  rejects malformed, expired, cross-Storage, cross-path, cross-revision or out-of-range use before
  contacting a provider. Do not recursively scan, read file contents, create jobs/tasks or persist
  browser state.
- Keep the browser response contract explicit and bounded: canonical root/path, breadcrumb segments,
  entry name/type/path metadata, server-enforced page limit, and continuation/exhaustion state. If a
  remote adapter would otherwise load an unbounded directory, add a read-only page hook at the
  adapter boundary rather than hiding an unbounded fetch behind application pagination.
- Keep navigation root-confined. Breadcrumbs are derived from normalized relative path segments;
  absolute paths, backslashes, NULs, parent traversal, path escapes and arbitrary host paths fail
  closed with bounded safe errors before any adapter read. Local symlink entries may be displayed as
  bounded metadata but must not be traversable or selectable when they are not safe directories;
  hostile names are rendered as text-safe bounded metadata.
- Normalize adapter failures into stable categories such as invalid path, not found, permission
  denied, authentication failed, connection failed, timeout, rate limited and unknown. Responses
  and logs must not expose credentials, raw provider payloads, unbounded exception text or host
  mount details beyond the documented execution-environment-visible Local root semantics.
- Expose the same browse behavior and validation through API and Operator Web. Read-only principals
  may inspect a configured browser; only configuration managers may use a selected directory to
  mutate a Draft, and the existing optimistic version/audit/reference rules remain authoritative.
  Selection must identify the target library and field explicitly and reuse the existing managed
  object mutation service; it must not create a second configuration source or browser state store.
- Integrate a usable Web picker into the existing ResourceLibrary and MediaLibrary guided forms.
  Selected values are Storage-relative paths and directory-only selections; validated text input uses
  the same Application path rules. The UI must explain that Local `rootPath` is an absolute path
  visible inside the MediaFlow execution environment, not an arbitrary host path. Guidance must cover
  future Docker bind mounts, read-only/read-write intent, ownership/permission failures, and the
  unsupported cases of unmapped host paths, host `/`, the Docker socket and arbitrary host
  filesystem access. Recovery guidance for missing, unmapped or permission-denied roots remains
  visible after reload.
- Preserve the Storage check guarantees from Task 26.3: browser and picker paths perform no Storage
  mutation, no mutation probe, no Provider request, and no workflow work. The configured Storage
  adapter remains the only filesystem/network boundary.

Frozen:

- `SLICE.md` User Goal, Required Outcomes, Required Surfaces, Safety Invariants and Base.
- Storage-check evidence, capability semantics, credential readiness and failure redaction from
  Task 26.3, except for the minimum shared path/error helper required by this browser.
- The current File Catalog/FileIndex surface, processing disposition, source occurrence identity,
  Reprocess, manual Scan/Preview/Organize, Preview findings, conflict/review continuation and
  processing-Worker readiness.
- Complete Recognition/TMDB Metadata/Naming/Classification/Organize graph setup, checked activation
  orchestration and first-runtime completion beyond the library path-selection integration.
- `config/alist.json`, real credentials, production endpoints and user media.

## Acceptance Criteria

- [ ] Each supported Storage kind uses one shared authenticated Application browser behavior; the
      application has no provider-specific browser or path-selection fork.
- [ ] Root, nested directories, empty directories, deterministic ordering, server-bounded limits,
      cursor/page continuation and cursor exhaustion work through API and Operator Web. The response
      exposes canonical root/path, breadcrumbs, immediate-child metadata and exact continuation state;
      the picker selects directories only and shows the exact Storage-relative path after selection.
- [ ] Cursor use is opaque and bound to revision identity, Storage, path and page request. Malformed,
      expired, cross-boundary, cross-revision and out-of-range cursors are rejected before an adapter
      read, and Local root confinement remains authoritative.
- [ ] Absolute paths, backslashes, NULs, traversal, symlink escapes and arbitrary host paths are
      rejected before an adapter read. Safe symlink entries remain non-traversable/non-selectable,
      and hostile names cannot cause markup or layout injection in the Web.
- [ ] Permission, authentication, timeout, connection, not-found, invalid-root and malformed-entry
      failures have stable bounded categories, affected Storage/path identity, durable-state
      statement, side-effect statement, retry safety and an explicit recovery action without raw
      provider payloads, credentials, host mount details or unbounded exception text.
- [ ] Listing and selection are bounded and lazy: no recursive scan, file-content read, Job/Task/
      Automation creation, Provider request or Storage mutator is reached; remote adapters do not
      hide an unbounded directory fetch behind an application page size.
- [ ] Read-only and configuration-management RBAC matches API and Web. Selecting a path only changes
      the current Draft through the existing version-checked managed configuration behavior; prior
      Active and unrelated Draft state remain unchanged on failure or stale admission.
- [ ] Operator Web provides discoverable breadcrumbs, retry/error recovery, hostile-name-safe
      rendering, execution-environment-visible Local root guidance and picker controls in both
      ResourceLibrary and MediaLibrary setup forms. The UI does not present the browser as File
      Catalog or claim arbitrary host access; the path semantics are also documented for self-hosted
      deployment.
- [ ] The checkpoint contains only this Task and all assigned T4 validation passes, with unavailable
      production Storage checks explicitly reported as `SKIP / UNAVAILABLE`.

## Required Tests

Add focused automated coverage in a new browser test module or the repository's equivalent for:

- Local, SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible browse success using a
  temporary Local root, fake adapters and fake/local services;
- root and nested directory listing, empty directories, deterministic ordering, bounded limits,
  cursor/page continuation, cursor exhaustion and malformed/cross-path/cross-Storage cursors;
- absolute/traversal/NUL/backslash rejection, Local symlink listing and escape rejection, hostile
  names, directory-only selection and execution-environment-visible Local root guidance;
- permission, authentication, timeout, connection, not-found, invalid-root and malformed-entry
  failures with safe bounded responses, retry safety, recovery actions and no raw path/provider data;
- API/Web parity, read-only versus management RBAC, optimistic version admission, Draft mutation
  on selection, prior Active preservation and audit behavior;
- exact cursor binding to revision/version/digest, Storage, normalized path and page request,
  invalidation before provider contact, response bounds and no persisted browser state;
- mutation guards and fake clients proving listing/selection never calls write, create-directory,
  move, copy, delete, hard-link or soft-link and never creates Job/Task/Automation/Provider work.

Run and report:

```bash
.venv/bin/python -m unittest tests.test_storage_browser \
  tests.test_storage_setup_check tests.test_guided_storage_lifecycle \
  tests.test_configuration_objects tests.test_configuration_snapshot \
  tests.test_configuration_status tests.test_configuration_destination_precheck \
  tests.test_configuration_destination_activation tests.test_api_security \
  tests.test_operator_ui tests.test_management_setup
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
git diff --check
```

For the changed Storage/Application/API/Web package surface, also run an isolated wheel build and
smoke test using a temporary output directory:

```bash
release_dir=$(mktemp -d /tmp/mediaflow-task-26-4.XXXXXX)
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$release_dir"
.venv/bin/python scripts/wheel_smoke_test.py "$release_dir"/mediaflow-*.whl
```

Use temporary Local directories, temporary SQLite databases, fake adapters/local services and fake
environment references only. Production SMB, OpenList, S3/R2 credentials and user media are
forbidden. Unavailable real services must remain `SKIP / UNAVAILABLE`, never a fake production PASS.

## Non-goals

- The current Files/File Catalog rename or redesign, processing disposition, source occurrence,
  Reprocess, repository-level Scan/Preview/Organize or processing-Worker readiness.
- Recursive Storage scans, file-content reads, media streaming, metadata/provider calls or any
  Storage mutation or mutation-based capability probe.
- Completing the full ResourceLibrary/MediaLibrary and Recognition/TMDB/Naming/Classification/
  Organize graph, checked activation or the first Active runtime beyond path selection.
- Docker/Compose, production WSGI, built-in identity, a general Secret Store or Provider switching.
- Changing Slice boundaries, Required Outcomes, Required Surfaces, Safety Invariants or the Slice
  Base; unrelated adapter rewrites and P2 cleanup.

## Previous Task Review

Task 26.3 — Read-only Storage Checks and Capability Evidence:

```text
Reviewed: b81729f74742d38d5ec61d641c4a2ca13b5a8a40..eba865bb75e5c08b9053dd2770b450fb6bfe6882
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

Evidence: focused regression passed with 213 tests; the full suite had 6 pre-existing/unrelated
failures and 7 skips, all six failures reproduced at the Task Base. Formatting, lint, compileall,
pip check, canonical configuration validation, forbidden-tool scan, diff check and isolated wheel
smoke passed. RO-5 and RO-6 remain incomplete, and first-runtime policy setup/activation remains
for a later Task.

## Developer Completion Report

### Changed Files

- `mediaflow/application/storage_browser.py`
- `mediaflow/application/configuration_objects.py`
- `mediaflow/application/read_only_storage.py`
- `mediaflow/domain/storage.py`
- `mediaflow/infrastructure/local_storage.py`
- `mediaflow/infrastructure/openlist_storage.py`
- `mediaflow/infrastructure/s3_storage.py`
- `mediaflow/infrastructure/smb_storage.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_storage_browser.py`
- `docs/architecture.md`
- `docs/product-experience.md`

### Implemented

- Added one shared Application Storage Browser for Local, SMB, OpenList, AWS S3, Cloudflare R2
  and generic S3-compatible Storage definitions, with bounded immediate-child pages, canonical
  Storage-relative paths, breadcrumbs, safe entry metadata and read-only adapter access.
- Added adapter-level bounded page hooks and deterministic continuation handling; remote adapters
  no longer hide a complete directory fetch behind Application pagination.
- Added an authenticated, encrypted and integrity-protected stateless cursor bound to the exact
  revision ID/version/digest, Storage, normalized path and page limit, with expiry and pre-adapter
  validation for malformed, tampered and cross-context continuation.
- Added safe path/root confinement, Local symlink display-only behavior, stable redacted failure
  categories and recovery details, plus Draft/Validated directory validation.
- Added API browse/select routes with READ versus MANAGE_CONFIGURATION enforcement. Directory
  selection reuses the existing version-checked managed object mutation and audit path for both
  ResourceLibrary.storagePath and MediaLibrary.rootPath.
- Added Operator Web standalone browsing and picker controls with breadcrumbs, bounded paging,
  retry recovery, directory-only selection, text-safe hostile-name rendering and Local execution
  environment/Docker mount and UID/GID guidance. Documented the same path semantics.

### Fix Loop (FIX REQUIRED correction)

- Replaced the permissive `base64.urlsafe_b64decode` cursor path with strict URL-safe Base64
  validation (`validate=True`) plus a canonical re-encode equality check in
  `StorageBrowserCursorCodec.decode`, so malformed, non-ASCII, non-canonical or alphabet-invalid
  cursor input is rejected before HMAC/context processing and before any Storage/provider read.
- Added an Application-level regression test asserting that appended invalid/whitespace
  characters, an inserted invalid/padding character, a substituted standard-alphabet character
  and padded non-canonical input are all rejected without increasing fake Storage `list_page`
  call counts. Existing opaque-cursor binding, tamper, expiry and context checks are unchanged.

### Tests and Results

- PASS — fix-loop focused regression rerun: `.venv/bin/python -m unittest
  tests.test_storage_browser tests.test_storage_setup_check
  tests.test_guided_storage_lifecycle tests.test_configuration_objects
  tests.test_configuration_snapshot tests.test_configuration_status
  tests.test_configuration_destination_precheck tests.test_configuration_destination_activation
  tests.test_api_security tests.test_operator_ui tests.test_management_setup` — 225 tests.
- FAIL / PRE-EXISTING / UNRELATED — fix-loop full-suite rerun:
  `.venv/bin/python -m unittest discover -s tests` — 1156 tests,
  6 failures, 7 skipped. The failures are the previously recorded state-dependent API credential,
  final-analyze, ResourceLibrary scan, and runtime Storage list/check cases; the Task Base report
  records the same six failures and the new Storage Browser malformed-cursor regression passed.
- PASS — `.venv/bin/ruff format --check .` — 361 files already formatted.
- PASS — `.venv/bin/ruff check .`.
- PASS — `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- PASS — `.venv/bin/python -m pip check` — no broken requirements.
- PASS — `.venv/bin/mediaflow --config config/strategy.example.json config validate`.
- PASS — `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- PASS — `if rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml; then exit 1; else echo
  'No ffprobe/ffmpeg matches'; fi`.
- PASS — fix-loop rerun of `git diff --check`.
- PASS — fix-loop isolated `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w
  "$release_dir"` followed by `.venv/bin/python scripts/wheel_smoke_test.py
  "$release_dir"/mediaflow-*.whl`; wheel smoke backup, migration, restore, verify and
  upgrade-preflight checks completed.
- SKIP / UNAVAILABLE — production SMB, OpenList, AWS S3, Cloudflare R2 and generic S3-compatible
  checks; approved production credentials/endpoints are forbidden for this Task, so temporary
  Local roots and fake adapters/services were used.

### Decisions

- Kept browser and selection behavior in one Application service; API and Web call the same
  revision, path, read-only and mutation rules.
- Added `StoragePage` at the Storage boundary so Local and remote adapters can enforce bounded
  reads before returning to the Application. Provider tokens remain inside the encrypted cursor.
- Kept Local roots execution-environment-visible and Storage-relative browser paths separate; the
  browser never exposes the host root or becomes the File Catalog.
- Kept selection on the existing managed configuration mutation/audit path so failures preserve
  the Draft and prior Active revision.
- Used strict decoded-then-re-encoded canonical Base64 equality rather than accepting Python's
  permissive unpadded decode, keeping the emitted opaque cursor format unchanged.

### Remaining In-Slice Work

- Slice 26 work outside Task 26.4 remains, including the remaining first-runtime policy setup and
  checked activation/other required setup outcomes covered by the Slice Contract.

### Risks / Deviations

- The six full-suite failures are recorded as `FAIL / PRE-EXISTING / UNRELATED`; they match the
  failures recorded at the Task Base and were not changed or hidden.
- Real external Storage acceptance remains `SKIP / UNAVAILABLE` because no production credentials
  or endpoints were used. Production behavior was covered only by fake adapters and temporary
  Local directories.
- `config/alist.json` remains ignored, untracked and unstaged; no real credentials or private
  paths were added.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 78a77a3031c18f95f7c476d575d6f959c405f4e5
```

## B Review Result

```text
Reviewed: b662c9073c17d724045488db378d78174ed71abe..33a27bbaf6c34902dc5dd9b0de55f50baccb94ff
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- Cursor malformed-input rejection is not satisfied. `StorageBrowserCursorCodec.decode` at
  `mediaflow/application/storage_browser.py:155-162` uses the permissive
  `base64.urlsafe_b64decode` path without strict alphabet/canonical-input validation, so an
  invalid character can be inserted into an otherwise valid cursor and still be accepted.
  Evidence: an Application-level browse with `first["nextCursor"] + "!"` returned the next page
  successfully, and the fake Storage `list_page` call count increased from `1` to `2`.
  Required fix direction: reject non-canonical/invalid Base64 cursor input before HMAC/context
  processing and before any Storage/provider call, while preserving the existing opaque cursor
  binding and expiry checks; add a regression assertion for inserted, appended and otherwise
  malformed characters.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
