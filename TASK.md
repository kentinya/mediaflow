# Task 37.7 — Formal Destination Parity and Direct Files Upload/Download Removal

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). A has explicitly expanded the current correction Task to
include removal of the Files direct browser Upload/Download surface; this is an authorized
product-boundary correction, not an invitation to redesign the remaining Files workspace.

```text
Task ID: 37.7
Parent Slice: 37
Status: PLANNED
Task Base: 1eb43931219b58d84216fe6d6a7b359c815b6503
Difficulty: High
Test Level: T4
Planner / Reviewer: B (delegated to A for this turn); A-owned scope revision on 2026-09-20
```

## Goal

Make the formal media-organization destination semantics identical to the local `strategy-test`
CLI: `ClassificationRule.result.library` is the first relative destination prefix, followed by
the rule's relative `path`, naming directory segments and naming filename.

For this rule:

```json
{
  "mediaLibraryId": "Test_Target",
  "library": "Movies",
  "path": ["其他电影"]
}
```

the formal Plan, Preview, precheck and execution target must contain:

```text
Movies/其他电影/<naming directory>/<naming filename>
```

`mediaLibraryId` remains the sole authority for resolving the configured MediaLibrary, Storage and
MediaLibrary root. `library` changes only the relative path composed beneath that root.

This advances Slice 37 outcomes RO-8 and RO-8C and closes the P1 mismatch recorded in the
reactivated Slice Contract.

The same Task also removes direct browser Upload/Download from the Files journey. After the
correction, Files retains browsing, ResourceLibrary activation, Create Folder/Text File, Rename,
Copy, Move, Delete, bounded text Edit and Organize continuation, but exposes no direct Upload or
Download command.

The same Task also repairs the Files-originated Save Choice path. A live Storage source selected
from Files must be able to save a valid Choice without a corresponding FileIndex row; the current
FileIndex-originated intent path remains unchanged.

## Why This Task Exists

The CLI currently constructs its plan with a temporary MediaLibrary whose root path is
`classification.library`, so it previews `Movies/其他电影/...`. The formal Organizer and
destination-preview paths currently compose only `classification.relative_path`, so the same
configuration produces `其他电影/...` beneath the configured MediaLibrary root. This violates the
operator's expectation that Preview and execution describe and perform the same target.

The defect crosses the shared destination-composition boundary and its callers. It must be fixed
as one coherent task so Organize Plan, configuration Destination Preview/precheck, manual and
automation projections, execution result evidence and local CLI behavior cannot drift again.

## A-authorized Product-Boundary Correction

The operator does not need direct browser Upload or Download from Files. The current Task therefore
removes that journey vertically:

- Web controls, dialogs, state, polling, download saving and client API functions are removed.
- Upload/Download HTTP routes, API binding fields, application services, direct domain projections
  and dedicated tests are removed.
- The upload-specific Task command constant and upload/download-only models are removed when no
  longer referenced.
- Storage `Read`/`Write`, OpenList/S3 transfer primitives, Copy/Move behavior, text Edit and
  `OrganizerExecutor` remain unchanged.
- Historical persisted Task/Result rows are not deleted and no schema migration is introduced.

The removal is intentionally direct. No feature flag, compatibility endpoint, replacement transfer
workflow, deprecation layer or broader Files redesign is part of this Task.

## Related Defect Recorded During Investigation

### Files-originated Save Choice rejects a live source as `source_missing`

On 2026-09-20, the Files-originated manual Organize journey was traced through:

```text
Files live-Storage admission
→ durable ManualOrganizeIntent
→ Operations Organize Intent
→ Save Choice
```

The observed failure is:

```text
Choice not saved
The choice was rejected (source_missing). Nothing was changed.
```

This P1 correction is now explicitly included in Task 37.7 by the A-owned scope decision recorded
above. It is implemented together with the formal destination correction and direct
Upload/Download removal because all three changes preserve the existing Files/Organize authority
boundary without adding a new product surface.

#### Confirmed root cause

- `ManualOrganizePreviewService._source_identity_from_storage()` creates the Files source identity
  from the current Storage entry. Its `file_id` is a deterministic hash of ResourceLibrary,
  Storage, path and Storage fingerprint; this path intentionally does not require a FileIndex row.
- `ManualOrganizeIntentService.update_choice()` currently re-resolves every item through
  `ManualOrganizeIntentService._resolve_file(item.source.file_id)`.
- `_resolve_file()` searches the current FileIndex and maps a missing row to `source_missing`.
- Consequently, a Files-created intent can contain a valid live Storage source while Save Choice
  incorrectly treats its derived Storage identity as a missing FileIndex identity.
- The rejection is atomic: the current intent and item versions remain unchanged, and no Storage
  mutation is attempted. The existing FileIndex-originated intent path is not affected by this
  specific mismatch.

The required authority rule is already stated by the product contract: Files physical source
selection and source authority come from the selected Active ResourceLibrary and live Storage;
FileIndex is display/reconciliation state and must not become the source authority for this path.

#### Included correction plan

Implement the following bounded correction in this Task:

- Preserve the source-authority distinction when an intent is created:
  - FileIndex-originated intents continue to validate against the current scoped FileIndex
    occurrence.
  - Files-originated intents continue to validate against the pinned Active ResourceLibrary and
    Storage source identity, without requiring a matching FileIndex row.
- Introduce an explicit application-level source validation boundary, backed by the Storage
  interface and the pinned runtime snapshot. Do not add direct filesystem/provider calls to the
  intent service, and do not accept browser-supplied absolute paths or Storage credentials.
- Reuse the same exact source evidence rules already used by Files admission and Preview:
  path confinement, regular-file requirement, verified fingerprint and occurrence identity.
- On Save Choice:
  - unchanged live Storage source: persist the choice;
  - source no longer present: return `source_missing`;
  - source path/content occurrence changed: return `source_stale`;
  - all rejection cases: preserve the previous intent/item versions and perform zero mutation.
- Keep the existing optimistic intent/item version checks, configuration snapshot pinning, policy
  compatibility validation, audit behavior and Preview invalidation semantics unchanged.
- Keep the Web error contract action-oriented. A source rejection must identify that the Files
  selection is no longer current and direct the operator to refresh Files and create/reopen the
  intent; it must not expose internal identity implementation details.

#### Included acceptance criteria

- A live Storage file selected from Files can open its Intent and save a valid Choice even when no
  corresponding FileIndex row exists.
- A FileIndex-originated Intent retains its existing scoped FileIndex validation behavior.
- Removing the Files source before Save Choice returns `source_missing` with no durable choice
  change.
- Replacing or changing the Files source before Save Choice returns `source_stale` with no durable
  choice change.
- A routine FileIndex rescan or display-only reconciliation does not falsely reject an unchanged
  Files source.
- Save Choice remains zero-Storage-mutation; later Preview and execution continue to perform their
  own exact live-source validation before any mutation authority is granted.
- Tests cover the complete Files admission → Intent → Save Choice path, missing source,
  replacement/stale source, no FileIndex row, optimistic concurrency and preservation of the
  legacy FileIndex path.

#### Required evidence

At minimum, this Task should add or update focused coverage in:

```text
tests/test_v2_manual_organize.py
tests/test_manual_organize_preview.py
tests/test_manual_organize_intent.py
```

The Task review must record the exact source-authority decision, the zero-mutation proof, the
per-item durable-state result and the full regression command.

### Docker-verified incorrect content-byte limit and 413 masking

On 2026-09-20, the production Docker stack under `/opt/mediaflow` was inspected read-only. The
API received repeated requests for:

```text
/api/v1/resource-libraries/source2/files/transfer-impact
```

The active managed configuration binds `source2` to `/media/Media/剧集`. The selected directory
tree exceeded the implementation's current aggregate-content limit:

```text
MAX_TRANSFER_BYTES = 20 GiB
MAX_TRANSFER_ENTRIES = 5000
MAX_TRANSFER_DEPTH = 32
```

Transfer admission raises `files_transfer_size_limit_exceeded` while enumerating metadata, even
though media content byte size does not materially determine the manifest's memory size. The
running API image then also fails to serialize the intended HTTP 413 response because `_response()`
has no `413` status label, producing `KeyError: 413` and masking the original rejection.

This correction is included in Task 37.7. It clarifies and repairs the existing bounded transfer
path without adding a new task hierarchy or a provider-specific fast path.

#### Included correction plan

- Add the missing `413 Payload Too Large` response label. The existing error code and
  action-oriented frontend mapping remain authoritative.
- Keep directory enumeration metadata-only: it may read directory entries, sizes, timestamps and
  provider validators, but must not read media bytes during Impact/admission.
- Remove aggregate source media bytes as a Copy/Move admission rejection. Keep calculating and
  displaying `totalBytes`; it is impact/progress information only.
- Preserve the existing top-level selection, recursively enumerated entry-count, directory-depth,
  safe-path and bounded manifest/checkpoint/projection limits. These are the control-plane bounds
  that protect memory, persistence and API documents.
- Preserve the existing one Transfer Task, Worker claim/fence, per-item checkpoints, conflict
  handling, pause/cancel/restart and no-automatic-replay behavior.
- Keep same-Storage Copy/Move and cross-Storage Copy/Move on their existing execution paths.
  Cross-Storage Move remains `Copy -> verify -> Delete source`.
- Do not introduce multi-batch orchestration, child Tasks, parallel batch execution, a native
  directory Move bypass, a new Storage capability or any implicit operation fallback.

#### Included acceptance criteria

- A file or directory is not rejected solely because its aggregate media content exceeds 20 GiB.
- A bounded large-media directory remains one existing Transfer Task and follows the current
  per-item execution/checkpoint path; no media content is read during Impact/admission.
- Selection-count, entry-count, depth, path or bounded control-plane evidence violations return a
  normal actionable error. Any legitimate HTTP 413 serializes as JSON instead of `KeyError: 413`.
- Cross-Storage Move never deletes a source entry before its corresponding destination entry is
  verified.
- Pause, cancel, failure and restart preserve existing completed-item outcomes without hiding
  partial effects or introducing batch semantics.
- Existing small-file and small-folder Copy/Move behavior, conflict modes and direct-file
  permission/capability checks remain unchanged.

#### Required evidence

At minimum, focused coverage must include:

```text
tests/test_direct_file_transfers.py
tests/test_runtime_files_browser.py
web/src/features/library/StorageFilesPage.test.tsx
web/tests/e2e/library-files.spec.ts
```

The Task review must record the original Docker `source2` evidence and a read-only corrected Impact
result showing that aggregate content bytes no longer cause rejection. Mutation behavior is proven
with temporary/fake Storage: one large-byte single file, one large-byte bounded directory,
entry/depth/control-plane limit rejection, same- and cross-Storage Copy/Move, restart continuation
and no duplicate mutation evidence. Production media must not be mutated for validation.

## Implementation Scope

Implement the correction across the shared formal target-path boundary:

- validate `ClassificationRule.library` as a bounded safe relative path prefix, with no absolute
  path, traversal component, backslash, empty component or NUL;
- compose `library/path/naming-directory/naming-filename` through one shared safe destination
  calculation;
- update Organizer planning and every formal destination Preview/precheck caller to pass the
  classification library prefix;
- keep `mediaLibraryId`-based MediaLibrary and Storage resolution unchanged;
- update bounded destination/result evidence where the composed path is surfaced so the operator
  can see the exact target and its contributing prefix;
- preserve the CLI's existing `Movies/...` behavior while making formal and CLI target results
  equal;
- add focused regression coverage for movie and TV-style paths, safe multi-segment prefixes,
  invalid prefixes, unresolved MediaLibrary behavior, DryRun zero mutation and execution target
  parity.
- remove the Files Upload/Download UI, client and backend vertical without removing the Storage
  capabilities required by remaining workflows;
- remove upload/download-only domain constants, projections, bindings and dedicated tests, while
  preserving generic historical Task/Result persistence and Copy/Move transfer behavior;
- add focused absence checks for Files controls, client calls, HTTP routes and application services,
  plus preservation checks for Storage/provider primitives and supported direct file commands.
- repair Files-originated Save Choice source validation so live Storage authority does not require a
  FileIndex row, while preserving the existing FileIndex-originated path;
- add focused coverage for unchanged, missing and stale Files sources, zero mutation on rejection,
  optimistic concurrency and durable Choice preservation.
- repair Copy/Move admission so aggregate source media bytes are informational rather than a
  rejection limit, while preserving the existing Task/execution model and adding the missing 413
  response mapping.

Production code, tests and only the directly necessary configuration/architecture guidance are in
scope. Files browsing/layout, the remaining direct file-management commands, metadata/provider
behavior, RecognitionType identity, Storage adapters, persistence schema and
conflict/destructive-operation semantics are frozen.

## Acceptance Criteria

- [ ] A configured `library = "Movies"` and `path = ["其他电影"]` produces
      `Movies/其他电影/...` in formal OrganizePlan output.
- [ ] Formal destination Preview, read-only destination precheck, manual/automation preview
      projections, execution and persisted/result evidence use the same composed target.
- [ ] The CLI and formal target calculations agree for the same resolved strategy input.
- [ ] `mediaLibraryId` still resolves the actual configured MediaLibrary and Storage root; changing
      `library` cannot select a different MediaLibrary or Storage.
- [ ] `library` is rejected fail-closed for absolute paths, traversal, backslashes, empty path
      components, NULs and other unsafe destination contributions before Storage mutation.
- [ ] DryRun/Preview and all analysis stages remain zero-mutation, and OrganizerExecutor remains
      the only Storage mutation boundary.
- [ ] Existing classification, naming, conflict, attachment, source-cleanup and recovery semantics
      remain unchanged apart from the intended destination-prefix correction.
- [ ] Files exposes no direct Upload or Download control, dialog, client call or selection action.
- [ ] The backend exposes no direct Files Upload/Download route and no binding/application service
      remains reachable for those commands.
- [ ] Upload/Download-only domain constants, projections, client models and dedicated tests are
      removed without deleting historical Task/Result rows or adding a schema migration.
- [ ] Storage `Read`/`Write`, OpenList/S3 provider transfer primitives, Copy/Move, text Edit and
      OrganizerExecutor behavior remain available and their focused tests pass.
- [ ] A repository search finds no direct Files Upload/Download references outside intentionally
      retained lower-level Storage/provider transfer primitives and historical governance evidence.
- [ ] A live Files-originated source can save a valid Choice without a FileIndex row.
- [ ] A missing Files source returns `source_missing`; a changed/replaced source returns
      `source_stale`; both preserve the previous Choice and item/intent versions.
- [ ] FileIndex-originated intents retain their existing scoped validation behavior.
- [ ] Save Choice performs zero Storage mutation on success and every rejection path; later Preview
      and execution retain their own live-source validation.
- [ ] Copy/Move does not reject directly selected files or bounded directories solely because
      aggregate source media bytes exceed 20 GiB.
- [ ] Impact/admission remains metadata-only; aggregate bytes remain visible while selection,
      entry/depth/path and control-plane evidence stay bounded.
- [ ] Legitimate 413 responses serialize as bounded JSON and never produce `KeyError: 413`.
- [ ] The existing one-Task/per-item execution, source locks/claims, conflict revalidation,
      checkpoints, restart and uncertain-effect behavior remain unchanged.
- [ ] No multi-batch orchestration, native directory Move bypass, new Storage capability or
      implicit fallback is introduced.
- [ ] Focused tests cover success, invalid input, unresolved destination, path safety and parity;
      assigned T4 validation passes with actual evidence.
- [ ] The checkpoint contains only this Task and required evidence, preserving the pre-existing
      dirty reference image.

## Required Tests

Run and record:

```bash
python3 scripts/check_governance.py
.venv/bin/pytest -q tests/test_organizer.py tests/test_configuration_destination.py tests/test_strategy_cli.py
.venv/bin/pytest -q tests/test_classification.py tests/test_runtime_strategy_configuration.py tests/test_configuration_destination_activation.py
.venv/bin/pytest -q tests/test_direct_file_commands.py tests/test_direct_file_transfers.py tests/test_file_catalog_api.py tests/test_runtime_files_browser.py
.venv/bin/pytest -q tests/test_v2_manual_organize.py tests/test_manual_organize_preview.py tests/test_manual_organize_intent.py
.venv/bin/ruff check mediaflow tests
.venv/bin/python -m compileall -q mediaflow
cd web && npm run format:check && npm run typecheck && npm run lint && npm run test -- --run && npm run build
cd ..
rg -n -S "FilesUploadDialog|uploadFiles|resumeUpload|fetchUploadProjection|downloadFiles|saveDownloadedFile|files/uploads|files/download|DirectFileUploadService|DirectFileDownloadService|direct_uploads|direct_downloads|FILES_UPLOAD_TASK_COMMAND" mediaflow web/src tests --glob '!web/node_modules/**' --glob '!**/__pycache__/**'
git diff --check
```

Before Task review, run the Slice-level relevant regression and safety gates:

```bash
.venv/bin/pytest -q
```

No production TMDB, SMB, OpenList, S3 or R2 service is required. Use fakes, temporary directories
and existing read-only Storage guards.

## Non-goals

- Reopening or redesigning the Files workspace, V2 shell or the remaining direct file-management
  journey.
- Adding a replacement browser transfer workflow, feature flag, compatibility endpoint or
  deprecation layer for Upload/Download.
- Changing `mediaLibraryId` resolution, MediaLibrary roots, Storage adapters or path authority.
- Adding classification conditions, providers, metadata fields or new policy types.
- Changing NamingPolicy output, conflict handling, attachment handling, cleanup or mutation policy.
- Replacing the local CLI or making CLI-only behavior a new operator journey.
- Removing Storage `Read`/`Write`, OpenList/S3 transfer primitives, Copy/Move, text Edit or
  OrganizerExecutor capabilities used by supported workflows.
- Redesigning ManualOrganizeIntent, changing FileIndex-originated source semantics or weakening
  optimistic concurrency, snapshot pinning, audit or later Preview/execution validation.
- Adding multi-batch transfer orchestration, child transfer Tasks, a native directory Move fast
  path or new Storage capabilities.
- Broad documentation reconciliation, unrelated P2 cleanup or redesigning closed Slice outcomes.

## Developer Completion Report

### Changed Files

Production:

- `mediaflow/domain/organizer.py` — `compose_destination()` takes an optional
  `classification_library_prefix` and validates it as the first relative contribution;
  `safe_destination_root()` accepts the single-segment `.` "no root prefix" marker.
- `mediaflow/application/organizer.py` — `OrganizePlanner` composes the classification
  `library` prefix; the `.`-root plan target and `_resolved_execution_target()` agree on the
  root-relative destination.
- `mediaflow/domain/classification.py` — `ClassificationRule.library` is validated with the same
  bounded safe-relative-path rules as the rule's relative path (absolute, traversal, backslash,
  empty component, NUL all rejected fail-closed).
- `mediaflow/application/configuration_objects.py` — `destination_preview` and
  `_resolve_destination` compose and attribute the `classification.library` contribution; the
  preview result surfaces `classificationLibrary`.
- `mediaflow/application/strategy_test.py` — the CLI's temporary MediaLibrary pins the `.` root so
  its plan target is exactly the formal root-relative destination.
- `mediaflow/application/manual_source_validation.py` (new) — the explicit application-level
  live-Storage source-validation boundary for Files-originated manual intents.
- `mediaflow/application/manual_organize.py` — `update_choice` routes source validation by
  authority: FileIndex-originated items keep scoped FileIndex validation, Files-originated items
  are re-observed against pinned Active Storage without needing a FileIndex row.
- `mediaflow/domain/manual_organize.py` — `ManualSourceIdentity.is_storage_source` states the
  Files-vs-FileIndex authority distinction once.
- `mediaflow/application/direct_file_transfers.py` — the `413 Payload Too Large` path; aggregate
  source media bytes are no longer a Copy/Move admission ceiling.
- Removed upload/download vertical: `mediaflow/application/direct_file_uploads.py`,
  `mediaflow/application/direct_file_downloads.py` (deleted);
  `mediaflow/interfaces/service_api.py` (routes, binding fields, helpers, imports);
  `mediaflow/domain/direct_files.py` (upload/download models and constants);
  `mediaflow/domain/task_persistence.py` (`FILES_UPLOAD_TASK_COMMAND`).

Tests:

- `tests/test_organizer.py`, `tests/test_configuration_destination.py`,
  `tests/test_configuration_destination_precheck.py`, `tests/test_configuration_snapshot.py`,
  `tests/test_resource_library_pipeline.py`, `tests/test_automation_definition_execution.py`,
  `tests/test_automation_task_definition_preview.py`, `tests/test_manual_preview.py`,
  `tests/test_manual_organize_execution.py` — updated to the corrected `library/path/...`
  composition and added focused parity/prefix/zero-mutation coverage.
- `tests/test_v2_manual_organize.py` — four new Files-originated Save Choice tests.
- `tests/test_direct_file_transfers.py` — control-plane bound tests (large bytes admitted,
  entry and depth limits reject truthfully with JSON 413).
- Deleted `tests/test_direct_file_uploads.py`, `tests/test_direct_file_downloads.py`.

Web:

- `web/src/features/library/FilesUploadDialog.tsx` (deleted),
  `web/src/features/library/StorageFilesPage.tsx`, `web/src/features/library/StorageFilesPage.test.tsx`,
  `web/src/shared/api/api-client.ts`, `web/src/entities/library/direct-files.ts`,
  `web/tests/e2e/library-files.spec.ts`, `web/tests/fake-server.mjs`, `web/tests/setup.ts`.

Correction round (B `FIX REQUIRED`, single blocker — Web gate not passing):

- `web/src/features/library/StorageFilesPage.test.tsx` — added a `beforeEach` URL reset, a
  `renderDrawer` harness that mounts the presentational drawer under the shared query provider
  without the route tree, a `setFilesRouteState` helper that states the Files deep-link entry
  state explicitly, and converted the three component-only drawer tests to `renderDrawer`. Test
  count (33) and assertion count (201) are unchanged; no skip, no timeout change.

### Implemented

1. **Formal destination parity (`library/path/naming-directory/naming-filename`).** One shared
   `compose_destination()` now takes the classification `library` as the first relative
   contribution, so Organize Plan, destination Preview, read-only precheck, manual/automation
   projections, execution and result evidence all compose the same target.
   `mediaLibraryId` remains the sole MediaLibrary/Storage/root authority: `library` only prefixes
   the relative path beneath that root (regression-tested).
2. **CLI/formal agreement.** The local `strategy-test` CLI now pins a `.` MediaLibrary root, so
   `plan.target` is the root-relative destination and equals the formal composition for the same
   resolved input. `Movies/Anime/...` CLI behavior is preserved.
3. **Fail-closed prefix validation.** `ClassificationRule.library` is validated in the domain and
   again in the shared composition, so absolute paths, traversal, backslashes, empty components
   and NULs are rejected before any Storage mutation or Storage adapter construction.
4. **Direct Files Upload/Download removed vertically.** Web controls, dialog, state, client calls
   and mocks; the HTTP routes, binding fields and helpers; both application services; the
   upload-only Task command constant and the upload/download-only domain models are gone. Storage
   `Read`/`Write`, provider transfer primitives, Copy/Move, text Edit and `OrganizerExecutor`
   remain. No historical Task/Result rows are deleted and no schema migration is introduced.
5. **Files-originated Save Choice repaired.** A live Storage source selected from Files can now
   save a valid Choice with no FileIndex row. The new boundary reuses the exact Files
   admission/Preview evidence rules (path confinement, regular-file requirement, verified
   fingerprint, occurrence identity) against the pinned Active runtime, performs zero Storage
   mutation, and preserves intent/item versions on every rejection. The FileIndex-originated
   path keeps its scoped FileIndex validation unchanged.
6. **Copy/Move control-plane bounds corrected.** The missing `413 Payload Too Large` response
   label is added, so a legitimate bounded-limit breach serializes as truthful JSON instead of
   `KeyError: 413`. Aggregate source media bytes are removed as a Copy/Move admission ceiling
   while `totalBytes` stays visible as impact/progress information; selection count, enumerated
   entry count, depth, safe-path and manifest/checkpoint/projection bounds are unchanged. No
   batch orchestration, child Task, native directory-Move bypass, new capability or implicit
   fallback was introduced.
7. **Correction round — Files journey determinism (B blocker).** The Web gate failure was a
   test-file shared-state defect, not a drawer interaction or assertion defect:

   - *Root cause 1 — leaked Files route state.* `StorageFilesPage` persists the selected
     ResourceLibrary into the real jsdom URL via
     `window.history.replaceState("?resourceLibraryId=...")`. Nothing reset it between tests, so
     every later test silently inherited the previously selected library. The overflow journey
     (`keeps every overflow library discoverable in the searchable 更多 list`) was passing only
     because an earlier test had left a non-first library selected; run alone on a clean URL it
     fails, because with the first card selected the promoted card is `资源库C` (a visible card)
     rather than an overflow entry. The file now resets the URL in `beforeEach`, and that journey
     states its own entry state explicitly through `setFilesRouteState` — the product's real Files
     deep-link input rather than an accident of test order.
   - *Root cause 2 — unrelated router mount.* `AddResourceLibraryDrawer` is a presentational form
     that resolves no route, query or router context. Its three component-only tests nevertheless
     mounted the full route tree via `renderWithProviders`, paying ~590 ms of first-query cost
     against ~86 ms under the shared query provider alone. They now render through `renderDrawer`;
     the page-level test that genuinely exercises the route tree keeps `renderWithProviders`.
   - Verified without hiding, skipping or weakening anything: the named test passes 10/10 runs
     under 6× CPU oversubscription at 2295–3008 ms (limit 5000 ms), the whole file passes 10/10
     under that load, and six shuffled-order runs pass 6/6 where the pre-fix file failed 4 of 5.

### Tests and Results

Correction round re-run (every gate below was re-executed on the corrected working tree; the
counts are identical to the round-1 report because this correction changes only how the Web test
file manages shared state):

```text
python3 scripts/check_governance.py                                      PASS
pytest -q tests/test_organizer.py tests/test_configuration_destination.py
          tests/test_strategy_cli.py                                     57 passed, 47 subtests
pytest -q tests/test_classification.py tests/test_runtime_strategy_configuration.py
          tests/test_configuration_destination_activation.py             28 passed, 24 subtests
pytest -q tests/test_direct_file_operations.py tests/test_direct_file_transfers.py
          tests/test_file_catalog_api.py tests/test_runtime_files_browser.py
                                                                         159 passed, 13 subtests
pytest -q tests/test_v2_manual_organize.py tests/test_manual_organize_preview.py
          tests/test_manual_organize_intent.py                           53 passed, 7 subtests
ruff check mediaflow tests                                               PASS
python3 -m compileall -q mediaflow                                       PASS
web: npm run format:check && typecheck && lint                           PASS
web: npm run test -- --run                                               455 passed (33 files), 0 failed
web: npm run build                                                       PASS (pre-existing chunk-size warning)
required upload/download absence grep (grep -rn -E, rg not installed)    0 matches
focused Files Playwright tests/e2e/library-files.spec.ts                 31 passed
git diff --check                                                         PASS
```

Web gate, the exact command B reported failing (`cd web && npm run test -- --run`):

```text
Test Files  33 passed (33)
     Tests  455 passed (455)
  Duration  151.64s
```

Determinism evidence for the named blocker
(`StorageFilesPage.test.tsx > AddResourceLibraryDrawer > keeps step validation ordered and submits
the bounded candidate once`):

```text
corrected file, 10 runs under 6x CPU oversubscription  -> 33 passed (33) x10, drawer test 2295-3008 ms
corrected file, --sequence.shuffle x6 (seeds 777..4662) -> 33 passed (33) x6
pre-fix file,   --sequence.shuffle                      -> failed 4 of 5 shuffled runs
pre-fix file,   overflow journey alone on a clean URL   -> FAIL (Unable to find /资源库C/);
                                                           passes in-file only via leaked URL state
```

The 10-run and shuffle evidence is the reason this is reported as a fix rather than a lucky pass:
the same stress and shuffle conditions that reproduced the order-dependence on the reviewed Head
pass repeatedly on the corrected tree.

Required gates (round 1, unchanged re-verified above; `tests/test_direct_file_commands.py` is
listed by the Task but does not exist in this repository or in its history —
`tests/test_direct_file_operations.py` is the real direct-file command module and is run in its
place):

```text
python3 scripts/check_governance.py                                      PASS
pytest -q tests/test_organizer.py tests/test_configuration_destination.py
          tests/test_strategy_cli.py                                     57 passed, 47 subtests
pytest -q tests/test_classification.py tests/test_runtime_strategy_configuration.py
          tests/test_configuration_destination_activation.py             28 passed, 24 subtests
pytest -q tests/test_direct_file_operations.py tests/test_direct_file_transfers.py
          tests/test_file_catalog_api.py tests/test_runtime_files_browser.py
                                                                         159 passed, 13 subtests
pytest -q tests/test_v2_manual_organize.py tests/test_manual_organize_preview.py
          tests/test_manual_organize_intent.py                           53 passed, 7 subtests
ruff check mediaflow tests                                               PASS
python3 -m compileall -q mediaflow                                       PASS
web: npm run format:check && typecheck && lint                           PASS
web: npm run test -- --run                                               455 passed (33 files)
web: npm run build                                                       PASS (pre-existing chunk-size warning)
required upload/download absence grep                                    0 matches
git diff --check                                                         PASS
```

Slice-level regression:

```text
pytest -q                                                                1703 passed, 7 skipped, 4 failed
```

The 4 failures are `FAIL / PRE-EXISTING / UNRELATED`; each reproduces unchanged at Task Base
`1eb43931` and none touches a file this Task changed:

- `tests/test_configuration_status.py::...test_hostile_configuration_content_is_never_exposed`
- `tests/test_manual_operations_contract.py::...test_real_api_documents_carry_no_forbidden_evidence`
- `tests/test_manual_operations_contract.py::...test_real_api_documents_match_the_frontend_fixture`
- `tests/test_release_security.py::...test_release_quality_gate_commands_are_documented_for_task_execution`
  (this one asserts TASK.md documents `scripts/docker_release_security_smoke_test.py`, which B's
  Task text does not contain)

Focused browser evidence: `npx playwright test tests/e2e/library-files.spec.ts` → 31 passed.

`UNAVAILABLE`: the Docker `source2` reproduction the Task asks the review to record. The running
stack under `/opt/mediaflow` is a separate checkout at `7269d03` whose `TASK.md` reads
`NO ACTIVE IMPLEMENTATION TASK`, so it predates this correction and cannot demonstrate the fixed
behaviour without deploying an unbuilt candidate image. The correction is instead proven by the
WSGI-level tests above, which exercise the real `MediaFlowApi` 413 serialization and the real
admission path.

### Decisions

- **`library` is a relative prefix, not a root selector.** It is composed after the configured
  MediaLibrary root; `mediaLibraryId` continues to resolve the MediaLibrary, Storage and root.
  This matches the CLI's `Movies/...` preview and is asserted by a test that a different
  `library` cannot re-route the plan to another MediaLibrary.
- **`library` reuses the existing bounded safe-relative-path validator** rather than a second
  implementation, so prefix and rule path cannot drift. The domain rejects it at construction and
  `compose_destination()` re-checks it as a defence in depth.
- **`. ` as the no-root marker.** A caller with no configured root needs `plan.target` to be the
  root-relative destination. `.` is accepted as a single-segment root that contributes no prefix,
  which keeps `OrganizePlan.target` byte-identical between the CLI and the formal composition
  without inventing a second plan type.
- **Source authority is decided by the identity, not the caller.** `ManualSourceIdentity` records
  whether it came from live Storage (`is_storage_source`), and `update_choice` branches on that.
  This keeps the FileIndex path's scoped validation intact while letting the Files path use its
  pinned Storage authority, and it needs no new persistence column.
- **The live-Storage validator always wraps the adapter in `ReadOnlyStorageGuard`.** Save Choice
  therefore cannot cross a Storage mutation boundary even if a caller supplies a
  mutation-capable adapter.
- **`source_stale` is HTTP 409** to match the existing Preview/manual-step contract, so the Web
  error mapping stays consistent.
- **Upload/download were removed, not disabled.** No feature flag, compatibility route,
  deprecation layer or replacement workflow was added, per the Slice Contract.
- **The aggregate-byte ceiling was removed, not raised.** Media content size does not determine
  manifest memory size; the entry-count and depth bounds are the control-plane protections that
  actually bound memory, persistence and API documents.
- **`execute_direct_write_stream` was kept.** It is a generic streamed Storage `write` boundary;
  the Task requires Storage `Read`/`Write` and `OrganizerExecutor` capabilities to remain.
- **Correction round: the blocker was test shared state, not the drawer.** `AddResourceLibraryDrawer`
  and the failing test body are byte-identical at Task Base `1eb43931` and at the reviewed Head
  `694e707` (`git show <rev>:…` compared by hash), and the drawer journey costs ~1.3 s when run
  alone. The failure was therefore in how the file shared state across tests, which is exactly the
  "suite-order/shared-state" category B named. I fixed that rather than touching the component.
- **The URL reset is a correctness fix, not a convenience.** Files route state
  (`?resourceLibraryId=`) is written to the real jsdom URL by the page and nothing reset it, so a
  test could silently depend on a previous test's selection. Resetting in `beforeEach` makes each
  test's entry state explicit. This immediately surfaced a latent issue in the overflow journey,
  which had been passing only via leaked state; that journey now declares its own entry state
  through `setFilesRouteState`, preserving every original assertion and intent.
- **Only the component-only drawer tests left the router harness.** The three tests that render
  `AddResourceLibraryDrawer` directly do not exercise routing, so mounting the route tree only
  added unrelated state and cost. The page-level test that does exercise the route tree still uses
  `renderWithProviders`, so route-tree coverage was not reduced.
- **I did not raise any timeout and did not add a skip.** The file still has 33 tests and 201
  assertions — identical to the reviewed Head — and the corrected tree passes the full suite
  repeatedly, including under 6× CPU oversubscription and under shuffled order.

### Remaining In-Slice Work

None known that belongs to this Task. Slice-level items I am aware of but did not touch:

- the three pre-existing Python assertion debts and the legacy Playwright route assertions
  already recorded as non-blocking P2 in the Slice closure packet;
- `scripts/docker_release_security_smoke_test.py` is asserted by `test_release_security.py` but
  is not named in the current TASK.md quality-gate documentation.

### Risks / Deviations

- **Correction-round scope:** this round changes exactly one test file
  (`web/src/features/library/StorageFilesPage.test.tsx`) and nothing else. No production code,
  application service, route, domain model or other test was touched, because the blocker's cause
  was test shared state rather than product behaviour.
- **Latent test defect surfaced, not introduced.** Making the entry state explicit revealed that
  the overflow journey had been relying on leaked URL state. It now sets that state itself. This
  is a strengthening of the test's precondition, not a change to what it asserts; its assertions
  are unchanged.
- **Remaining flakiness under extreme CPU oversubscription is pre-existing and unrelated.**
  Under a deliberately hostile 6× CPU oversubscription I observed failures in
  `ManualOperationsRouter.test.tsx`, `AutomationRouter.test.tsx` and `OrganizeRouter.test.tsx`
  (missing page heading after `renderApp`). I ran the same three files, same load, 8 iterations
  each against Task Base `1eb43931` in a clean worktree and against the corrected tree: Base
  failed 6 of 8, corrected failed 8 of 8. These files are not touched by this Task, the failure
  mode is independent of the Files drawer, and it reproduces at the Task Base commit, so it is
  `FAIL / PRE-EXISTING / UNRELATED`. The required gate command is run at normal load, where it is
  green; I am recording this because it is real, not because I claim it is irrelevant — that
  judgement is B's.
- **Task-document deviation:** `tests/test_direct_file_commands.py` does not exist and never has
  in this repository's history; the real direct-file command module
  `tests/test_direct_file_operations.py` was run instead and every other file in that command was
  run exactly as written.
- **Evidence deviation (UNAVAILABLE):** the Docker `source2` reproduction described above. This is
  a real gap in the requested evidence, not a claim of success.
- **Behaviour change with a wide blast radius:** the composed destination now includes the
  `library` prefix, so nine existing test modules that had frozen the old
  `root/relative-path` target were updated to the corrected composition. Every change was an
  expectation update to the new contract, verified against `git diff`; no assertion was deleted
  or weakened and no skip was added.
- **Pre-existing failures:** the 4 failures above are unchanged from Task Base. I am not
  claiming they do not affect the Task; that judgement is B's.
- The pre-existing dirty `docs/pics/文件页.png` remains modified in the working tree exactly as
  found and is excluded from this checkpoint.
- `ruff format` was run across `mediaflow` and `tests` because the repository's CI gate is
  `ruff format --check .`; at Task Base one file already drifted, and the formatter only touched
  files this Task had already modified.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 55620d26ccd22e1a6cd79ad8dca7b9ac6dc58a19
(correction round; the completion report is committed as the direct child of this checkpoint)
```

Corrected change range: `694e7076ffcd423a690a60bcff1000a0a4ce28ad..55620d2` (B's reviewed Head through
this correction). The full Task range remains `1eb43931219b58d84216fe6d6a7b359c815b6503..HEAD`.

No accepted history was amended or rewritten. The correction is a new commit on top of the
reviewed checkpoint `694e707`, which itself sits on the round-1 implementation commit `7c0d29f`:

```text
55620d2 fix(task-37.7): make the Files drawer journey deterministic under the full Web suite
694e707 docs(task): report Task 37.7 completion and review range
7c0d29f fix(task-37.7): formal destination parity, remove Files upload/download, ...
68d0225 docs(slice): clarify Copy Move control-plane bounds
e3a60d7 docs(slice): revise Files transfer scope
313169b docs(task): plan formal classification destination parity
1eb43931 (Task Base)
```

## B Review Result

```text
Reviewed: 1eb43931219b58d84216fe6d6a7b359c815b6503..694e7076ffcd423a690a60bcff1000a0a4ce28ad
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Blockers:

- The required Web regression gate is not passing on the reviewed Head. `cd web && npm run test
  -- --run` produced `454 passed, 1 failed`; the failure is
  `src/features/library/StorageFilesPage.test.tsx > AddResourceLibraryDrawer > keeps step
  validation ordered and submits the bounded candidate once`, which timed out at 5000 ms during
  the full suite. This file and drawer behavior are part of the reviewed Task change, so the
  failure is a current Task/Files-journey reliability defect, not an unrelated pre-existing
  failure.
  Required correction: make the Add ResourceLibrary drawer journey deterministic under the full
  Web suite and rerun the complete `npm run test -- --run` gate with zero failures; do not merely
  hide the test, weaken its assertions, or increase the timeout without fixing the underlying
  suite-order/shared-state or interaction problem.

This result does not close the Slice or update Roadmap. Fixes remain in Task 37.7.
