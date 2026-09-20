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

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING | PASS | FIX REQUIRED
Slice Required Outcomes all satisfied: PENDING | YES | NO
Next: PENDING | SAME TASK FIX LOOP | NEXT TASK | SLICE READY FOR A REVIEW
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
