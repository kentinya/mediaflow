# Task 37.6 — Files Multi-item Organize Continuation and FileIndex Reconciliation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.6
Parent Slice: 37
Status: IN PROGRESS
Task Base: f1e157cd9488f742958339a477373c639dad0257
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete **RO-8 Organize workflow continuity** and its **RO-9 Actionable recovery** boundary: from
`/ui-v2/library/files`, an authorized operator can select one or several eligible regular files,
enter the existing durable Organize Intent → exact Preview → explicit Execute journey using
server-resolved live Storage identity, inspect every terminal item independently, and see the
matching FileIndex occurrence reconciled from the durable Result without replaying any Storage
mutation.

This Task also closes the remaining RO-5/RO-7 authority edge and advances RO-11/RO-12 by proving
that Files and API use the existing Organize application behavior, RBAC, pinned Active snapshot,
`OrganizerExecutor` mutation authority and exact occurrence fencing. It does not create a second
Files-specific organize state machine.

## Why This Task Exists

Tasks 37.1–37.5 delivered the shared shell, Files workspace, ResourceLibrary activation and the
complete direct file-management set. The remaining Slice gap is observable in the current
production assembly:

- `RuntimeFilesBrowserService` inherits the generic Storage browser's directory-picker
  `selectable` value, while the Files table treats directories as navigation and regular files as
  Organize candidates. Real regular-file rows therefore cannot reliably enter Organize even though
  Web fixtures make them selectable.
- The current Files mutation rejects every selection except exactly one path, creates a read-only
  current-source Preview and navigates to `/operations/preview/{id}`. It neither admits a bounded
  multi-file Intent nor continues to the existing exact Preview/Execute pages.
- The existing V2 Organize Intent API accepts FileIndex item IDs for a library selection. Files must
  instead submit only the selected ResourceLibrary identity and ResourceLibrary-relative paths;
  the backend must derive immutable SourceIdentity from the pinned Active Storage.
- terminal Result persistence already contains a FileIndex projection hook, but execution
  TaskItems/Results must carry the exact live source occurrence and fingerprint. Path-only binding
  must never attach a Result to a different or stale FileIndex occurrence, and a reconciliation
  miss must be visible and recoverable without repeating the Organize mutation.

This is one coherent final vertical journey rather than separate Tasks for a route, field, link or
test. The existing Organize pages and state machine are reused; only the missing Files admission
and exact terminal reconciliation boundary are added.

## Implementation Scope

```text
Live ResourceLibrary selection
→ existing Manual Organize Intent
→ existing exact Preview and explicit Execute
→ existing OrganizerExecutor / durable per-item Results
→ exact-occurrence FileIndex reconciliation
→ Files and execution recovery UI
→ tests
```

- **Files eligibility and selection:** in the ResourceLibrary-scoped runtime Files projection,
  expose regular non-symlink files as Organize-eligible and keep directories as navigation only.
  General Files selection remains available to direct commands, but only eligible regular files
  enter Organize. Do not consult FileIndex to decide physical existence, path confinement or
  execution authority.
- **Live-Storage Intent admission:** add one bounded authenticated Files admission that accepts an
  enabled ResourceLibrary ID plus an ordered, unique list of normalized ResourceLibrary-relative
  file paths. Enforce the existing manual-organize item bound. Resolve the exact pinned Active
  ResourceLibrary/Storage server-side, stat each path, reject directories/symlinks/missing,
  escaped, duplicate, unverifiable or changed entries with stable per-selection recovery, build
  immutable `ManualSourceIdentity` values, and call the existing
  `ManualOrganizeIntentService.create_from_sources`. The browser must not submit FileIndex IDs,
  occurrence IDs, fingerprints, Storage roots, credentials, execution tokens or raw plans.
- **Existing workflow reuse:** return the ordinary bounded Organize Intent document and navigate
  automatically to the existing Intent page. Choice editing, exact zero-mutation Preview,
  destructive implications, explicit Execute authorization, durable Task/Result projection,
  resident Worker ownership and recovery continue through the existing application/API/Web
  journey. Do not create a Files-only Preview, execution protocol, token or state machine.
- **Files Web journey:** both a row action and the selection footer can start the same admission.
  Multi-selection includes only the visibly eligible selected files, states how many other selected
  entries remain excluded, prevents duplicate submission and preserves the ResourceLibrary,
  directory and selection on admission failure. Stable errors distinguish missing/changed source,
  unsupported entry, invalid/escaped selection, limit overflow, permission denial and service
  unavailability. The ordinary user is navigated through the existing pages without copying raw
  identifiers. Provide a bounded return-to-Files action that restores the ResourceLibrary and
  directory context after review/execution.
- **Exact Result identity:** carry each server-derived source occurrence ID, fingerprint and
  verified fingerprint state into the admitted TaskItem and terminal `PersistentResultRecord`.
  Never replace that identity by looking up whichever FileIndex row currently occupies the same
  path. Existing live-Storage revalidation before `OrganizerExecutor` remains mandatory.
- **FileIndex reconciliation:** when a terminal Result is durably published, update only a current
  FileIndex occurrence whose Storage, ResourceLibrary, path, occurrence ID and fingerprint all
  match the executed source. Perform this display-state reconciliation atomically with the Result
  where the current persistence boundary supports it. Each execution item/document must expose a
  bounded, secret-free reconciliation state (for example synchronized, no matching occurrence, or
  attention required) and a safe next action. A missing/stale FileIndex occurrence must never
  authorize, redirect or invalidate the already-known Storage effect and must never trigger an
  automatic Organize replay; recovery is a bounded FileIndex refresh/rescan/reconciliation action
  against the durable Result.
- **Independent outcomes:** one blocked, failed, uncertain or unreconciled item cannot hide or
  rewrite a sibling's Preview, execution Result or FileIndex state. Known-success and known-failure
  results reconcile independently; uncertain effects retain unknown retry safety and direct the
  operator to inspect live Storage before any new intent.
- **Security and redaction:** preserve existing MANAGE_MANUAL_ORGANIZE/RBAC checks, immutable Active
  snapshot pinning, audit, path confinement, lock/claim fences and OrganizerExecutor-only Storage
  mutation. Read-only Files browsing, Intent creation and Preview remain zero Storage mutation.
  Operator/API documents contain only bounded logical paths and explanations, never credentials,
  host paths, provider payloads, lock tokens or authorization internals.
- **Compatibility:** preserve Tasks 37.1–37.5 behavior, all direct file commands, Upload/Download,
  single-item Organize capability through the new common admission, non-Files Organize entry points,
  shared V2 routes and V1 `/ui`. Preserve the pre-existing dirty `docs/pics/文件页.png`.

## Acceptance Criteria

- [ ] In a legal Active runtime, an authorized operator can select one eligible regular file in
      Files, choose `整理`, and arrive at the existing durable Organize Intent page created from
      that file's server-resolved live Storage identity.
- [ ] The same Files action accepts a bounded selection of several eligible regular files in one
      Intent. Every item remains independent through choice, exact Preview, Execute and terminal
      Result; an ineligible directory, symlink or unrelated selected row is visibly excluded rather
      than smuggled into or allowed to block the eligible selection.
- [ ] Files submits only ResourceLibrary identity and normalized relative paths. Absolute paths,
      traversal, root selection, duplicate paths, directories, symlinks, missing/changed entries,
      unverifiable identity and over-limit selections fail closed before Intent creation or Storage
      mutation with a stable reason and safe next action.
- [ ] The backend pins the exact Active snapshot and builds every `ManualSourceIdentity` from the
      selected ResourceLibrary's live Storage. FileIndex rows and browser-supplied identifiers never
      supply physical path, source identity, Preview or execution authority.
- [ ] The new Files entry reuses the existing Intent → Preview → Execute implementation,
      permissions and operator pages. Intent and Preview perform zero Storage mutation; only the
      existing `OrganizerExecutor` execution boundary can mutate Storage after explicit reviewed
      authorization.
- [ ] Files preserves its current ResourceLibrary, directory and unaffected selection on admission
      failure, prevents duplicate submission, presents actionable bounded errors, and provides a
      direct return to the originating Files context after review/execution without requiring the
      operator to copy IDs or tokens.
- [ ] Every admitted TaskItem and terminal Result retains the exact live source occurrence ID,
      fingerprint and verified state used by Preview/execution. A same-path replacement or stale
      FileIndex row can never receive another occurrence's Result.
- [ ] A terminal Result synchronizes only its exact matching current FileIndex occurrence. Success,
      skipped, failed and uncertain items project their truthful disposition/effect certainty and
      retry safety independently; newer/stale/missing occurrences remain untouched.
- [ ] A FileIndex reconciliation miss/failure is visible on the affected execution item with the
      durable Organize outcome, known Storage effect and one safe bounded reconciliation action.
      It does not change a successful Result into failure, fabricate an index row, replay
      `OrganizerExecutor`, or automatically retry an uncertain mutation.
- [ ] Concurrent source change, Active revision change, duplicate submit, stale Intent/Preview,
      Worker claim loss and reconciliation races retain the existing fail-closed behavior and do
      not cross-bind Result or FileIndex state.
- [ ] Existing FileIndex-based/non-Files Organize entry points, direct Files operations,
      Upload/Download, ResourceLibrary lifecycle, V2 shell/routes and V1 `/ui` retain their current
      behavior and safety assertions.
- [ ] The T4 focused, integration, full regression, Web, browser, package and security gates pass;
      any pre-existing/unrelated failure or unavailable external gate is reproduced and reported
      truthfully without deleting, weakening or skipping a safety test.
- [ ] The checkpoint contains only this Task's implementation, tests and completion report. It
      excludes `config/alist.json`, credentials, the dirty reference image, ignored artifacts and
      unrelated changes.

## Required Tests

- `python3 scripts/check_governance.py`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m unittest tests.test_runtime_files_browser tests.test_manual_organize_intent tests.test_manual_organize_preview`
- `.venv/bin/python -m unittest tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_file_index_lifecycle`
- `.venv/bin/python -m unittest tests.test_task_persistence tests.test_api_security`
- `.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_organizer_rollback`
- `.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers tests.test_direct_file_uploads tests.test_direct_file_downloads`
- `.venv/bin/python -m unittest discover -s tests`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `.venv/bin/python -m pip check`
- `python3 scripts/docker_release_security_smoke_test.py` (if the environment permits the release
  fixture; otherwise record the exact reproduced failure and its Base comparison)
- `test -z "$(grep -rn -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml || true)"`
- `cd web && npm run format:check`
- `cd web && npm run typecheck`
- `cd web && npm run lint`
- `cd web && NODE_ENV=test npx vitest run src/features/library/StorageFilesPage.test.tsx src/features/operations/OrganizeRouter.test.tsx`
- `cd web && npx playwright test tests/e2e/library-files.spec.ts tests/e2e/manual-organize.spec.ts --project=chromium`
- `cd web && NODE_ENV=test npm run test -- --run`
- `cd web && npm run build`
- `cd web && npm run test:e2e`
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist`
- `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl`
- `git diff --check`
- Inspect Task Base..Head, the commit manifest and `git status --short`; confirm no test deletion or
  weakened assertion, hidden skip, silent fallback, `config/alist.json`, credential, dirty
  `docs/pics/文件页.png`, ignored artifact or unrelated file entered the checkpoint.

Focused tests must include real current WSGI routing with temporary/fake Storage and persistence:
one-file and multi-file Files admission; regular-file eligibility; directory/symlink exclusion;
invalid/escaped/duplicate/over-limit input; permission and Active-snapshot refusal; same-path
replacement; exact matching, stale, missing and concurrent FileIndex occurrences; independent
mixed terminal outcomes; no replay on uncertain/reconciliation failure; and preservation of the
existing non-Files Organize journey. Browser tests must prove the row and selection-footer paths,
failure context retention, automatic navigation through the existing workflow and return to the
originating Files context without raw-ID ceremony.

All tests use fakes, mocks, temporary roots and local test servers only. No production
SMB/OpenList/S3/TMDB service, credential or real media directory is permitted.

## Non-goals

- A new Organize planner, Files-specific Preview/execution state machine, alternate execution API,
  raw execution-token handoff or bypass of the existing Intent/Preview/Worker flow.
- Organizing directories recursively, unbounded selections, arbitrary host paths, FileIndex-based
  physical authority or automatic resubmission/replay of any Storage mutation.
- Redesigning the existing Intent, Preview, Execution, Review/Recovery or non-Files Operations
  pages beyond the minimal Files-origin context and reconciliation evidence/actions required here.
- Recognition, Metadata, Naming, Classification or Organize policy behavior changes; new Storage
  providers/capabilities; schema rewrites unrelated to exact result reconciliation.
- Further Upload/Download changes, resumable/chunked upload, drag-and-drop polish, direct-file
  command expansion or optional wording/cleanup.
- Slice-final screenshot/full closure work. B performs Slice Final only after this Task passes and
  all Required Outcomes are re-evaluated.

## Developer Completion Report

### Changed Files

- `mediaflow/application/storage_browser.py` — `RuntimeFilesBrowserService.browse_resource_library`
  now publishes an explicit `organizeEligible` flag (regular non-symlink files only) instead of
  letting the Files table inherit the generic directory-picker `selectable` semantics.
- `mediaflow/application/manual_organize_preview.py` — new bounded Files admission
  `ManualOrganizePreviewService.admit_storage_paths`: validates the ordered unique path list,
  enforces the existing manual-organize item bound, pins the exact Active snapshot, resolves the
  ResourceLibrary's live Storage, stats every path (rejecting directories, symlinks, missing,
  escaped, duplicate, unverifiable or changed entries), builds immutable `ManualSourceIdentity`
  values server-side and admits one durable intent through the existing
  `ManualOrganizeIntentService.create_from_sources`. `_source_identity_from_storage` now rejects
  symlinks explicitly with `source_symlink`.
- `mediaflow/application/manual_organize_execution.py` — terminal `PersistentResultRecord` now
  carries the exact admitted source occurrence ID, fingerprint and verified state; the execution
  document exposes a bounded, secret-free `fileIndexReconciliation` per item
  (`synchronized` / `no_matching_occurrence` / `attention_required` / `pending`) with one safe
  bounded action; new `reconcile_file_index` re-applies the durable Result to a current exact
  FileIndex occurrence without any Storage call or Organize replay.
- `mediaflow/application/operations_lifecycle.py` — operator projection whitelists the bounded
  `fileIndexReconciliation` evidence (state, next action, action envelope only; no occurrence IDs
  or fingerprints).
- `mediaflow/infrastructure/sqlite_runtime.py` — TaskItem/Result persistence stores the exact
  source occurrence identity; `file_index_reconciliation_state` reads the display state of one
  durable Result; `reconcile_result_to_file_index` re-applies the same atomic exact-occurrence
  reconciliation used at Result publication inside one `BEGIN IMMEDIATE` transaction.
- `mediaflow/interfaces/service_api.py` — new authenticated routes:
  `POST /api/v1/resource-libraries/{id}/files/organize` (paths-only admission, RBAC
  `MANAGE_MANUAL_ORGANIZE`, returns the ordinary bounded Intent document) and
  `POST /api/v1/operations/organize/executions/{id}/file-index-reconciliation` (display-only
  recovery); the execution document now flows through the service-level document so
  reconciliation evidence is included; `organize` added to the ResourceLibrary files capability
  envelope.
- `tests/test_runtime_files_browser.py` — projection eligibility test (regular file eligible,
  directory/symlink not, no FileIndex identity, zero Task work).
- `tests/test_v2_manual_organize.py` — six new real-WSGI journey tests: multi-file admission from
  live Storage, fail-closed ineligible/malformed selections, RBAC refusal, non-current Active
  refusal, exact-occurrence execution + reconciliation, same-path replacement never receiving the
  older occurrence's Result.
- `web/src/entities/library/storage-files.ts` — `organizeEligible` normalization with fail-closed
  type checks and a derived fallback.
- `web/src/entities/operations/organize.ts` — bounded `fileIndexReconciliation` model and
  normalization for execution items.
- `web/src/shared/navigation/files-return.ts` (new) — bounded, validated return-to-Files URL
  context (ResourceLibrary identity + relative directory only; no tokens, host paths or backend
  authority).
- `web/src/shared/api/api-client.ts` — `submitFilesOrganizeIntent` (paths-only POST) and
  `reconcileOrganizeExecutionFileIndex`; stable transport/error envelopes.
- `web/src/features/library/StorageFilesPage.tsx` — row action and selection footer both start the
  same admission; multi-selection includes only visibly eligible files and states how many other
  selected entries remain excluded; admission failure preserves ResourceLibrary/directory/selection
  with stable actionable messages; success navigates to the existing Intent page carrying the
  bounded return context.
- `web/src/features/operations/OrganizeIntentPage.tsx`,
  `web/src/features/operations/OrganizePreviewPage.tsx` — propagate the bounded return context and
  offer `返回文件` back to the originating Files directory.
- `web/src/features/operations/OrganizeExecutionPage.tsx` — per-item FileIndex reconciliation
  state label, next action and one bounded `重新核对文件索引` action; return-to-Files link.
- `web/tests/fake-server.mjs`, `web/tests/e2e/library-files.spec.ts`,
  `web/tests/e2e/manual-organize.spec.ts` — fixture support and browser tests for row/footer
  admission, exclusion of ineligible rows, failure context retention, automatic navigation through
  the existing workflow, return to Files, and the reconciliation-miss recovery without replay.

### Implemented

- Files-originated Organize admission: one or several eligible regular files from
  `/ui-v2/library/files` enter the existing durable Intent → exact Preview → explicit Execute
  journey with server-resolved live Storage identity. The browser submits only the ResourceLibrary
  identity and normalized relative paths — never FileIndex IDs, occurrence IDs, fingerprints,
  Storage roots, credentials or tokens.
- Exact Result identity: admitted TaskItems and terminal Results retain the live source occurrence
  ID, fingerprint and verified state; same-path replacement or stale FileIndex rows can never
  receive another occurrence's Result.
- FileIndex reconciliation: terminal Results synchronize only the exact matching current
  occurrence atomically at publication; each execution item exposes a bounded reconciliation state
  plus one safe bounded reconciliation action that never calls Storage, never fabricates an index
  row and never replays the Organize mutation.
- Files Web journey: eligibility flags, excluded-selection messaging, duplicate-submission
  prevention, failure context retention, automatic navigation and a bounded return-to-Files action
  on the Intent/Preview/Execution pages.
- Compatibility: existing FileIndex-based/non-Files Organize entry points (PreviewNewPage,
  `submitServerBoundPreview`), direct file commands, Upload/Download, V2 routes and V1 `/ui` are
  untouched.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS (`governance check: PASS`)
- `.venv/bin/ruff format --check .` — PASS (311 files already formatted)
- `.venv/bin/ruff check .` — PASS (one import-sort violation in `tests/test_v2_manual_organize.py`
  auto-fixed with `ruff check --fix`; final run: All checks passed)
- `.venv/bin/python -m unittest tests.test_runtime_files_browser tests.test_manual_organize_intent tests.test_manual_organize_preview` — PASS (26 tests)
- `.venv/bin/python -m unittest tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_file_index_lifecycle` — PASS (76 tests)
- `.venv/bin/python -m unittest tests.test_task_persistence tests.test_api_security` — PASS (26 tests)
- `.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_organizer_rollback` — PASS (45 tests)
- `.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_direct_file_transfers tests.test_direct_file_uploads tests.test_direct_file_downloads` — PASS (205 tests)
- `.venv/bin/python -m unittest discover -s tests` — FAIL / PRE-EXISTING / UNRELATED: 1758 passed,
  7 skipped, 3 failures, all three reproduced identically at Task Base
  `f1e157cd9488f742958339a477373c639dad0257` in a clean worktree with identical assertion output:
  - `tests.test_configuration_status.ConfigurationSnapshotTests.test_hostile_configuration_content_is_never_exposed`
    (`'root' unexpectedly found` — the `root_path` field name in the configuration snapshot
    projection)
  - `tests.test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_carry_no_forbidden_evidence`
    (`201 != 400` in the shared `_capture` helper)
  - `tests.test_manual_operations_contract.ManualOperationsContractTests.test_real_api_documents_match_the_frontend_fixture`
    (same shared `_capture` helper)
  These modules do not call the new Files admission or reconciliation routes; the same signature
  fails at the Task Base without any of this Task's changes.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS
- `.venv/bin/python -m pip check` — PASS (no broken requirements)
- `python3 scripts/docker_release_security_smoke_test.py` — FAIL / PRE-EXISTING / UNRELATED:
  `Error response from daemon: invalid mount config for type "bind": bind source path does not
  exist: /tmp/.../media/organized` (first run) and `.../deployment.env` (Base comparison run).
  Reproduced identically at Task Base `f1e157cd9488f742958339a477373c639dad0257` in a clean
  worktree; the harness failure is independent of this Task's changes (the Task touches no Docker,
  compose or smoke-script code).
- `test -z "$(grep -rn -i 'ffprobe\|ffmpeg' mediaflow pyproject.toml || true)"` — PASS
- `cd web && npm run format:check` — PASS (5 files initially failing were normalized with
  Prettier; final run clean)
- `cd web && npm run typecheck` — PASS
- `cd web && npm run lint` — PASS (two `no-useless-assignment` findings in
  `web/src/shared/api/api-client.ts` fixed; final run clean)
- `cd web && NODE_ENV=test npx vitest run src/features/library/StorageFilesPage.test.tsx src/features/operations/OrganizeRouter.test.tsx` — PASS (51 tests)
- `cd web && npx playwright test tests/e2e/library-files.spec.ts tests/e2e/manual-organize.spec.ts --project=chromium` — PASS on re-run (44 passed). The first full run had 2
  flaky failures (`list and grid presentation switch and bounded pagination`,
  `empty and recoverable failure states preserve the Files context`); both passed individually and
  the complete 44-test re-run passed. No assertion was weakened.
- `cd web && NODE_ENV=test npm run test -- --run` — PASS (460 tests)
- `cd web && npm run build` — PASS (chunk-size warning only, pre-existing)
- `cd web && npm run test:e2e` — PASS (112 passed)
- `PATH="$PWD/.venv/bin:$PATH" python -m pip wheel . --no-deps -w dist` — PASS
  (`mediaflow-2.0.0.dev0-py3-none-any.whl`; `dist/` is git-ignored and not committed)
- `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl` — PASS (schema 38)
- `git diff --check` — PASS
- Checkpoint manifest: only this Task's files staged; `config/alist.json` absent, no credentials,
  the dirty `docs/pics/文件页.png` left untouched and unstaged, no ignored artifacts included.

### Decisions

- Files admission lives on `ManualOrganizePreviewService.admit_storage_paths` rather than a new
  service: it is an admission boundary only and must reuse the existing snapshot pinning, Storage
  resolution and `create_from_sources` authority so no second Files-specific state machine exists.
- The ResourceLibrary Files projection publishes a new explicit `organizeEligible` flag instead of
  reinterpreting the generic Storage browser's directory-picker `selectable` value, keeping the
  directory-picker contract intact for setup flows.
- Reconciliation state is derived at document-read time from the durable Result identity plus the
  current exact FileIndex row, so a stale/missing occurrence can never rewrite an already-known
  Storage effect; the recovery action re-runs only the same display-only reconciliation.
- The return-to-Files context travels in the URL search projection (validated, bounded, no
  identifiers beyond ResourceLibrary ID and relative directory) so ordinary operators never copy
  raw IDs or tokens.
- Web table rows show `整理` for every organize-eligible regular file (previously gated on
  `businessStatus === "pending"`), because eligibility is a Storage-authoritative property while
  `businessStatus` is FileIndex display feedback.

### Remaining In-Slice Work

- The three pre-existing full-discovery failures and the pre-existing Docker release security
  smoke harness failure are unresolved; they reproduce at the Task Base and are outside this
  Task's scope. B must judge whether they block Slice closure or belong to a separate correction.
- Slice-final screenshot/closure work remains with B/A after this Task review.

### Risks / Deviations

- `FAIL / PRE-EXISTING / UNRELATED`: three unittest failures and the Docker security smoke failure
  listed above, each reproduced at the Task Base with identical signatures. This checkpoint does
  not claim they are non-blocking; that judgment belongs to B.
- The first focused Playwright run showed 2 flaky failures that passed on isolated and full
  re-runs; the complete focused re-run and the full `test:e2e` suite (112 tests) both pass.
- No test was deleted, no assertion weakened, no skip hidden; `docs/pics/文件页.png` remains dirty
  and unstaged as required.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
