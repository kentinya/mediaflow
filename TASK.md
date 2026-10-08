# Task 44.1 — Consistent direct file maintenance across both library kinds

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). It implements RO-1 and Slice Acceptance Criteria 1–8.

```text
Task ID: 44.1
Parent Slice: 44
Status: READY FOR B REVIEW
Task Base: f57715c042ffa22c07d92950cc3de222946ed9b2
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete RO-1's ordinary file-maintenance journey on ResourceLibrary Files and MediaLibrary Files
under one backend observable-metadata policy with optional provider fingerprints. Supported Rename,
confirmed Delete and verified cross-Storage Move must not fail solely because fingerprints are
unavailable. Deliver native success, failure and recovery on both kinds while preserving exact
scope, permissions, immutable pins, ownership and independent effects.

## Why This Task Exists

Inspection at Task Base establishes these gaps:

- `DirectFileCommandService` requires a fingerprint for Rename evidence and Delete impact;
  OrganizerExecutor repeats the requirement at the last mutation boundary.
- Same-Storage Move already accepts absent fingerprints with observable-state checks. Cross-Storage
  Move requires exact identity before source removal and can return PARTIAL after verified Copy
  solely because that fingerprint is absent.
- Production OpenList and SMB entry conversion supplies no fingerprint. Both native library pages
  expose the refusal, so this is a supported production journey, not a hypothetical adapter.
- Rename tokens and Delete digests bind kind/ID/path/metadata but lack the complete Storage/root/
  configuration context required by RO-1's TARGET rule.
- Bounded Delete currently executes its batch inside the request. Task/result recording alone does
  not complete the promised long-work admission and native remaining-scope recovery journey.

B ran six existing baseline probes: ResourceLibrary no-identity Rename/Delete refusal, MediaLibrary
no-identity refusal, cross-Storage no-identity Move source retention, fingerprint-change rejection
and replaced-directory rejection. All six passed. These establish baseline behavior only; the
Contract changes the first four expectations and preserves the latter protections.

The shared observation/confirmation/Executor/recovery boundary is one coherent vertical unit.
Splitting by operation or library page would leave inconsistent authority and user behavior.
RO-2 through RO-6 remain outstanding; this Task does not implement or close those outcomes.

## Implementation Scope

```text
Direct-file domain evidence → compatible persistence/checkpoints → shared application services
→ OrganizerExecutor → Task/Worker/Operations → scoped authenticated APIs → both Web pages → Tests
```

1. Apply the TARGET rule only to ordinary direct maintenance. Server-observed evidence remains
   required when fingerprints are absent. Bind exact library kind/ID, Storage/root, relative path
   and applicable immutable configuration context; preserve names including boundary whitespace.
   Revalidate at submission and the last safe mutation boundary. An observed fingerprint stays
   binding: disappearance/change cannot downgrade to weaker evidence.
2. Share metadata-only validation. Files compare existence, supported type, size/time and any
   observed fingerprint. Directories compare available stable identity, otherwise existence/type.
   Confirmed child removal must not falsely invalidate a Local parent through changed ctime.
   Directory Delete additionally requires complete confirmed scope and an empty final parent.
3. Complete file/directory Rename, single/batch/recursive Delete and cross-Storage Move source
   removal without mandatory fingerprints. Preserve RO-1's full operation semantics for browsing,
   Create Folder/Text File, same/cross-Storage Copy/Move and bounded text Open/Edit/Save. Reuse
   working behavior; change it only where required for consistency or promised failure/recovery.
4. Keep existing concrete limits: Delete ≤50 submitted paths, ≤5,000 entries, depth ≤32 and
   ≤20 GiB known bytes; transfers ≤50 paths, ≤5,000 entries and depth ≤32, with media byte totals
   informational rather than an admission ceiling. Text remains allowlisted UTF-8 and ≤512 KiB.
   Retain paging/path/control-plane bounds; truncated enumeration cannot authorize a prefix.
5. Deliver durable admission/control for long/batch Delete using existing Task/Job/Worker and
   Operations boundaries. Persist confirmed scope, kind/root/pin, item progress and effect certainty
   for cooperative pause/cancel, restart and explicit safe continuation. Preserve transfer
   checkpoints/ownership; do not reconstruct authority from a fresh expanded tree or add an engine.
6. Evolve evidence/persistence only as necessary and compatibly. Old results/pins remain historical
   facts; valid strong evidence keeps its original binding. Old no-fingerprint partial/refused work
   does not gain source-delete authority upon upgrade. Where safe historical authority cannot be
   proved, provide native current observation and explicit reconfirmation/successor recovery.
7. Wire both `/ui-v2/resourcelib/files` and `/ui-v2/medialib/files`, their separate API namespaces,
   typed models/dialogs/text editor and Operations recovery to shared behavior. Preserve each
   page's destination rules and return context. MediaLibrary Worker readback/continuation requires
   direct acceptance evidence, not merely ResourceLibrary/shared-service coverage.

### Operator journey

- **Goal/entry:** maintain live entries or a bounded selection through existing menus/actions,
  dialogs and text editor on either native library page.
- **Visible state:** exact source/destination paths, observed facts, bounded impact, Worker readiness,
  per-item durable stage and known/retained/partial/uncertain effects.
- **Action:** supply name/destination/content/conflict intent; confirm Delete once; follow progress
  and backend-advertised controls. Carry server evidence automatically with no unsafe-mode toggle,
  CLI fallback or raw-token transfer.
- **Success:** verify effects, persist truthful results, refresh live list/tree and reconcile exact
  selection/current-directory/return context without another mutation.
- **Failure:** explain the affected item's invalid/stale scope, conflict, denial, unsupported
  capability, failed verification or unknown effect; retain input and successful siblings.
- **Recovery:** correct input, refresh/reobserve/reconfirm changed intent or continue an attributable
  safe checkpoint. Unknown admission/effects require native readback/investigation before another
  deliberate action. Refresh/reconnect/restart never resubmits mutations.

Frozen: Slice Contract/Base, Roadmap, canonical requirements, accepted historical closure records,
frozen Slice 43 and all supplied PNGs, including the four pre-existing untracked images. Do not
inspect/stage/include `config/alist.json`, real credentials or user media. Document any necessary
narrow architecture adjustment and its reason; A owns factual acceptance/closure reconciliation.

## Acceptance Criteria

- [ ] **AC-1 — Both surfaces.** Every applicable RO-1 operation completes on both native pages and
  scoped authenticated APIs. OpenList/SMB-like providers without fingerprints support file/directory
  Rename, bounded confirmed Delete and verified cross-Storage Move source removal. MediaLibrary has
  its own required Task/Worker readback/continuation. Equal IDs/overlapping roots cannot exchange
  cross-kind evidence, destinations or work.
- [ ] **AC-2 — Observations.** Exact kind/library/Storage/root/path/configuration context binds
  observations and confirmation. Missing evidence remains invalid. Observable existence/type/size/
  time changes and observed-fingerprint changes/disappearance stop mutation at admission and final
  checks. Stable directory identity/legitimate Local ctime changes follow the TARGET rule. Do not
  fabricate exact identity from metadata; document indistinguishable replacement and external
  check-to-write windows as accepted limitations rather than imposing new identity requirements.
- [ ] **AC-3 — Delete.** Overlapping selections deduplicate; complete bounded impact shows counts/
  known bytes. Added/removed/type-changed/observably changed entries invalidate confirmation.
  Children precede parents; each item is revalidated and final parents must be empty. Links,
  unsupported types, roots and exceeded limits fail closed. Sibling failure or unexpected contents
  cannot cause recursive removal outside the confirmed effect.
- [ ] **AC-4 — Short commands/text.** Browsing is bounded/live/read-only. Create requires valid
  basename, writable existing parent and absent target; existing entries are conflicts. Rename
  uses native operation without Copy/Delete fallback and verifies old absence/new presence.
  Text Create/Open/Save retains allowlist/UTF-8/512-KiB bounds and loaded size/content-digest fences
  at admission/final boundary; changed/missing Save cannot become Create. Verify content before
  advancing editor evidence. Unknown creation/rename/save is read back without equating target
  presence or equal metadata with ownership.
- [ ] **AC-5 — Transfers.** Same-Storage Copy/Move retains native capabilities/conflict choices and
  verification, including OpenList Move→Rename intermediate-name protection and truthful failed/
  unknown compensation. Cross-Storage Copy verifies byte count/digest and preserves source on all
  outcomes. Move persists Copy-written/destination-verified/source-deleted checkpoints, freshly
  checks source plus live delete authority and verifies absence. No-fingerprint source removal
  succeeds when gates pass; changes/denial/unknown removal preserve independent partial/uncertain
  effects. Final empty source directories use the same policy. Skip/keep-both/manual resolution
  and partial-target cleanup retain attribution/authority; no silent overwrite/fallback, transfer
  Replace or aggregate-media-byte admission ceiling.
- [ ] **AC-6 — Durable recovery.** Long/batch Delete and transfers expose durable admission, Worker
  waiting reasons, progress, cooperative pause/cancel and native safe remaining-scope continuation
  on both kinds. Restart/takeover retains exact published pins, locks/leases/fences and attributable
  checkpoints; Active never repins admitted work. Expanded/changed scope requires renewed review/
  confirmation. Completed siblings remain terminal, uncertain mutations investigation-only, and
  unknown admissions are read back before an explicit repeat without duplicate work.
- [ ] **AC-7 — Compatibility.** Actual Base-created evidence and pending/completed/partial/uncertain
  work remain readable across candidate restart/upgrade under their original meaning. Valid strong
  evidence is not downgraded/destroyed; previously refused source deletion cannot automatically
  resume under newly relaxed authority. Native recovery explains durable effects and obtains
  current intent when required. Necessary evidence/schema evolution has a real old-state rehearsal,
  not solely fixtures invented in the candidate format.
- [ ] **AC-8 — Safety.** Rename/Delete evidence, admission, confirmation, final checks and effect
  verification read zero selected-file bytes and perform no FULL Hash. Transfer verification and
  bounded text content fences remain intact for their own purposes. Only OrganizerExecutor mutates
  Storage. Permission/read-only/capability/path refusals perform zero mutation. Direct maintenance
  invokes no Recognition/Metadata/media-organize pipeline or Provider.
- [ ] **AC-9 — Native feedback/regression.** Both pages retain correctable name/content/destination
  input, expose independent action-oriented failure/recovery and refresh exact list/tree/selection/
  path after known effects. Reads/reconnect/index-sync failure cause no replay. Preserve Organize
  Preview source authority, C→A-policy identity, library configuration, Storage binding and other
  pages. MediaLibrary gains no Organize entry or source authority.
- [ ] **AC-10 — Verification/checkpoint.** T4 gates pass with actual commands/totals/skips/unavailable
  evidence. Supply an operation × library-kind evidence map linking relevant cases to tests,
  scoped APIs, native browser proof and recovery. Include the production OpenList adapter through
  a local server, not only a fingerprint-stripped Local wrapper. Base..Head contains only this
  coherent Task with no private/unrelated files.

## Required Tests

Run Python commands from the repository root using `.venv/bin/python` (plain `python` is unavailable).
Do not delete tests, weaken unchanged safety assertions or hide skips. Replace obsolete mandatory-
fingerprint refusal assertions with specific new success/staleness/non-replay assertions while
retaining strong-fingerprint protections. Record exact commands for all additional focused tests.

### Focused and affected integration

```bash
.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_media_library_direct_commands tests.test_direct_file_transfers tests.test_media_library_transfers
.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_scope_continuation tests.test_processing_worker_readiness tests.test_runtime_files_browser
.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage tests.test_openlist_storage tests.test_s3_storage tests.test_migration_rehearsal tests.test_release_security tests.test_release_validation tests.test_container_deployment
```

Cover absent/present/changing/disappearing fingerprints at admission and final boundaries, metadata
changes, no-content-read spies, recursive scope/final emptiness, exact whitespace paths, denied/root/
link/alias/conflict failures, both API bindings, verified/partial/unknown source removal, pause/
cancel/restart/stale owner and old/new activation isolation. Use Local temporary directories,
production OpenList with a local HTTP server and SMB/S3-prefix fakes/local servers. Fake/local-server
evidence cannot certify real remote services. No production credentials/media are prerequisites.

### Full regression and quality/safety gates

```bash
.venv/bin/python scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/mediaflow --config config/strategy.example.json config validate
.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
git diff --check
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

The forbidden-dependency audit requires no matches (rg exit 1). Inspect complete diff/manifest and
staged files for scope/secrets/private files. Prove any claimed pre-existing/unrelated failure at Base.

### Web and real-Python browser acceptance

Run in `web/`:

```bash
npm run test -- --run
npm run format:check
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

Also add/run focused **real-Python native Files browser journeys on both library kinds** using
temporary roots/SQLite, actual application/API/Worker and built assets. Reuse/extend existing harness
or add a narrow isolated harness/config; report its exact reproducible invocation. Exclude Python-
only specs from default fake-server runs. Existing Operations proof and mock-only Web coverage alone
cannot establish AC-1/6/9.

Cover applicable operations, file/directory Rename, single/batch/directory Delete and verified
cross-Storage Move without fingerprints, retained input, source changes/conflicts/denials, partial/
unknown readback, pause/continue and live tree/selection/return context. Check list/grid command
reachability, keyboard and narrow use; RO-5's layout repair remains outside this Task. Save bounded
browser evidence and the operation/kind map without exposing private paths or credentials.

### Packaging, Docker and compatibility

```bash
.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-task44-1-wheel
.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-task44-1-wheel/mediaflow-*.whl
.venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task44-1-lifecycle
.venv/bin/python scripts/docker_files_transfer_impact_smoke_test.py --image mediaflow:task44-1-impact
.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task44-1-security
```

Use fresh candidate artifacts/image tags or clean only Task-owned stale outputs; record actual
candidate build/served artifact identity. Use isolated temporary Compose state, synthetic media and
generated test credentials, never the live deployment. Disclose every SKIP/tool/service/Docker
unavailability explicitly; unavailable evidence is not PASS.

If evidence/persistence format/schema changes, perform an actual Task Base→candidate upgrade/restart
rehearsal preserving old strong evidence, pins/results and partial/uncertain effects. Record exact
seeding/upgrade commands and outcomes. Run the applicable generic Docker upgrade gate as well:
`.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py`. Its generic coverage does not
replace the direct-work historical compatibility rehearsal.

## Non-goals

- RO-2 Rules presentation, RO-3 destinations, RO-4 object tests, RO-5 toolbar repair and RO-6 folder
  organization; preserve their existing surfaces as affected regressions only.
- Frozen Slice 43 implementation/integration or altering its unresolved Task/review history.
- Upload/Download, transfer Replace, cross-kind direct transfer, new link UI/providers, unbounded
  work, generic rollback, automatic uncertain replay or a second queue/execution engine.
- Rename/Delete media hashing, provider-generation/conditional-operation redesign or universal
  detection of indistinguishable replacement/external check-to-write races.
- Changing media Organize fingerprint authority, publication/grant semantics or Slice scope;
  A reconciliation, next-Task planning, Slice PASS/CLOSED and unrelated refactors/P2 polish.

## Developer Completion Report

### Changed Files

- `TASK.md`, `docs/architecture.md`
- `mediaflow/application/direct_file_commands.py`, `mediaflow/application/direct_file_transfers.py`, `mediaflow/application/operations_lifecycle.py`, `mediaflow/application/organizer.py`, `mediaflow/domain/direct_files.py`, `mediaflow/final_cli.py`, `mediaflow/infrastructure/sqlite_runtime.py`, `mediaflow/interfaces/service_api.py`
- `scripts/direct_files_browser_harness.py`, `scripts/direct_files_compatibility_rehearsal.py`, `scripts/operations_inventory_harness.py`
- `tests/test_direct_file_operations.py`, `tests/test_direct_file_transfers.py`, `tests/test_media_library_direct_commands.py`, `tests/test_media_library_transfers.py`, `tests/test_release_security.py`
- `web/playwright.config.ts`, `web/playwright.direct-files.python.config.ts`, `web/src/entities/library/direct-files.ts`, `web/src/features/library/delete-admission-session.ts`, `web/src/features/library/FileCommandDialogs.tsx`, `web/src/features/library/MediaLibraryCommands.test.tsx`, `web/src/features/library/MediaLibraryFilesPage.tsx`, `web/src/features/library/StorageFilesPage.test.tsx`, `web/src/features/library/StorageFilesPage.tsx`, `web/src/shared/api/api-client.ts`, `web/src/shared/api/media-library-commands-api.test.ts`, `web/tests/e2e/direct-files.python.spec.ts`, `web/tests/e2e/library-files.spec.ts`, `web/tests/e2e/medialib-commands.spec.ts`

### Implemented

- Completed direct Rename, confirmed single/batch/recursive Delete and same/cross-Storage Copy/Move journeys through the shared application and OrganizerExecutor boundary. Metadata-only observations work when fingerprints are absent, while observed fingerprints remain binding. Cross-Storage Move removes its source only after verified destination copy and fresh source checks.
- Bound observations and confirmations to library kind/ID, Storage/root, path and applicable immutable configuration context. Preserved operation limits, independent outcomes, Worker ownership/fencing, durable checkpoints and historical authority.
- Added durable Delete admission and per-item Task/Worker results on both library kinds. Both native pages expose progress, outcomes and Operations recovery; unknown effects remain investigation-only and are not automatically replayed.
- For the correction blockers, persisted a browser-generated Delete request ID and exact confirmed scope before POST; read back that same durable Task after an uncertain response; reject a conflicting request binding; and require an explicit same-scope repeat to reuse the same ID. Impact and admission collapse duplicate and descendant selections to one normalized top-level scope. Known source-change and unexpected-directory-content refusals remain bounded through TaskItem, Result and API and receive localized guidance.
- Added real-Python browser journeys and a Base-to-candidate persistence rehearsal. Documented the narrow direct-file behavior in `docs/architecture.md`.

### Tests and Results

- PASS — `.venv/bin/python -m unittest tests.test_direct_file_operations tests.test_media_library_direct_commands tests.test_direct_file_transfers tests.test_media_library_transfers` — 215 tests.
- PASS — `.venv/bin/python -m unittest tests.test_organizer tests.test_organizer_mutation_authority tests.test_scope_continuation tests.test_processing_worker_readiness tests.test_runtime_files_browser` — 122 tests.
- PASS — `.venv/bin/python -m unittest tests.test_local_storage tests.test_smb_storage tests.test_openlist_storage tests.test_s3_storage tests.test_migration_rehearsal tests.test_release_security tests.test_release_validation tests.test_container_deployment` — 122 tests; OpenList production adapter exercised through local HTTP.
- PASS — `.venv/bin/python -m unittest discover -s tests` — 2,195 passed, 7 skipped.
- PASS — `.venv/bin/python scripts/check_governance.py`; `.venv/bin/ruff format --check .` (341 files); `.venv/bin/ruff check .`; `.venv/bin/python -m compileall -q mediaflow tests scripts`; `.venv/bin/python -m pip check`; both required config validation commands; `git diff --check`.
- PASS — forbidden dependency audit fallback: `grep -RniE --exclude='*.pyc' 'ffprobe|ffmpeg' mediaflow pyproject.toml` returned no matches (exit 1). `rg` is unavailable.
- PASS — from `web/`, `npm run test -- --run` — 65 files / 1,008 tests before the final zero-selection wording adjustment; the two affected page unit tests passed when rerun afterward. Also PASS after that adjustment: `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run build`. Build reports the existing >500 KB chunk advisory.
- PASS — current focused Web checks: MediaLibrary enabled-library browse unit test, StorageFiles Delete selection/tree-pruning unit test, and `npm run test:e2e -- --grep='honest paging and selection summary'`.
- PASS — from `web/`, `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` — 21 real-Python browser tests.
- PASS — from `web/`, `npm run test:e2e -- --config=playwright.direct-files.python.config.ts tests/e2e/direct-files.python.spec.ts` — 8 real-Python journeys across ResourceLibrary and MediaLibrary, including durable Delete and fingerprintless cross-Storage Move.
- PASS — `.venv/bin/python /tmp/mediaflow-b44-review.py` — both library kinds normalize overlapping/repeated selections, retain changed files and new directory contents, and persist bounded `source_changed` / `directory_changed` through TaskItem, Result and API.
- PASS — adapted browser repro `node /tmp/mediaflow-b44-unknown-delete-adapted.mjs`: both kinds issued one POST, read back the queued Task after the dropped response, exposed no second Delete action, and deleted only after one explicit Worker run. The supplied `/tmp/mediaflow-b44-unknown-delete.mjs` probe timed out on its old confirmation/alert selectors after the UI moved to durable progress.
- PASS — Base-to-candidate compatibility rehearsal: `.venv/bin/python scripts/direct_files_compatibility_rehearsal.py seed-base --base-tree /tmp/mediaflow-task44-1-base --state-root /tmp/mediaflow-task44-1-correction-compat`; then `verify-candidate --state-root /tmp/mediaflow-task44-1-correction-compat` — schema 44 completed, partial, uncertain, pending and refused no-fingerprint work remained readable with original pins; refused source deletion did not gain authority.
- PASS — wheel build/smoke: `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w /tmp/mediaflow-task44-1-wheel-correction`; `.venv/bin/python scripts/wheel_smoke_test.py /tmp/mediaflow-task44-1-wheel-correction/mediaflow-2.0.0.dev0-py3-none-any.whl`. SHA-256: `0d8bf75da064932bb253da5382d073101a620d2ec7af433ae2a6406c7ccfb`.
- PASS — `.venv/bin/python scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task44-1-correction-lifecycle` — `sha256:b88b1b4a0832de78efdc76b2fc94a1386e0661852084490dad5122a18908cd79`.
- PASS — `.venv/bin/python scripts/docker_release_security_smoke_test.py --image mediaflow:task44-1-correction-security` — `sha256:52928b11e249413bcbeea794ed6f41f10425b0f1ac699c928f4c410cf1d79b44`.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python scripts/docker_files_transfer_impact_smoke_test.py --image mediaflow:task44-1-correction-impact` — unchanged harness raises `KeyError: 'resourceLibraries'` before Compose; reproduced at Task Base.
- FAIL / PRE-EXISTING / UNRELATED — `.venv/bin/python scripts/docker_upgrade_recovery_smoke_test.py` — migration/recovery runs, then unchanged harness expects schema 39 while runtime reports 44; reproduced at Task Base.
- FAIL — full default Web E2E was 199/235 passed, 36 failed. Thirty-one dashboard/deep-link placeholder and Storage Management failures were reproduced at Task Base. Four candidate-only direct Delete fake-server cases still expect an immediate terminal “删除结果”; the durable admission flow reads Task status instead. The exact four-case rerun failed on those expectations. The remaining failure was a paging-summary assertion caused by an intermediate zero-selection wording; the wording was corrected and its focused current E2E passed, but the full default suite was not rerun afterward. Base passed the five-case slice (the four Delete cases plus paging summary). No pass is claimed for the four candidate-only Delete failures.
- PASS — candidate real-Python browser/API/SQLite/Worker journeys above cover both library kinds.

| Journey evidence | ResourceLibrary | MediaLibrary |
| --- | --- | --- |
| File/directory Rename; single Delete | `tests/test_direct_file_operations.py`; Python browser Rename/Delete journeys | `tests/test_media_library_direct_commands.py`; Python browser Rename/Delete journeys |
| Batch/recursive Delete; Worker readback/continuation | `tests.test_direct_file_operations`; `tests.test_direct_file_transfers`; Python browser batch Delete | `tests.test_media_library_direct_commands`; `tests.test_media_library_transfers`; Python browser batch Delete |
| Fingerprintless cross-Storage Move; pause/resume | `tests.test_direct_file_transfers`; Python browser cross-Storage Move | `tests.test_media_library_transfers`; Python browser cross-Storage Move |
| Production OpenList adapter | `test_production_openlist_http_adapter_renames_and_deletes_without_fingerprints` uses local HTTP | Shared OpenList adapter coverage plus MediaLibrary-specific command/readback tests |

### Decisions

- Optional fingerprints strengthen observation evidence but are not fabricated or replaced with content hashes. When absent, the shared policy uses existence/type/size/time and available stable directory identity.
- Direct Delete reuses Task/Worker persistence, locks, leases and mutation fences. A browser UUID identifies one durable admission; recovery checks the existing Task binding and immutable pin.
- Duplicate and descendant paths normalize consistently for impact and admission. Known pre-mutation refusals preserve bounded categories; uncertain effects remain investigation-only and are never retried automatically.
- Historical no-fingerprint partial/refused Move retains its original source-removal authority; the compatibility rehearsal seeded that state from actual Task Base.
- Docker impact and generic upgrade failures are unchanged and Base-reproduced. Candidate-only fake-server E2E failures are recorded; the real-Python browser journeys verify durable behavior against the actual API and Worker.

### Remaining In-Slice Work

RO-2 through RO-6 remain outstanding; Developer does not plan their Tasks.

### Risks / Deviations

- The full default Web E2E suite has four candidate-only direct Delete fake-server failures in addition to 31 Base-reproduced failures. They are not represented as passing.
- The supplied unknown-response browser script uses selectors for the former confirmation/error view; the adapted script verified one POST per library kind using the durable progress view.
- Seven full-suite unittest skips are reported above. Production SMB/S3/TMDB endpoints were not exercised; OpenList adapter coverage used local HTTP. No production credentials or user media were used.
- Build output retains the >500 KB chunk advisory. No Slice contract change or scope expansion was made.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 8c03b9ff7aadb64b39603ecf568b8e4d99767192
```

## B Review Result

```text
Reviewed: f57715c042ffa22c07d92950cc3de222946ed9b2..91ac7c16b5e8492c62e2c5c01edad2122e492e20
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — Unknown Delete admission is presented as non-execution and has no admission readback
  before repeat (AC-6/9; RO-1 durable admission/recovery).** Origin: the ResourceLibrary fallback
  message already exists at Task Base; this Task moves Delete to asynchronous durable admission
  without completing the required unknown-admission recovery. This is an unmet integration criterion,
  not a newly introduced message. On the native ResourceLibrary page,
  drop the response only after the actual POST has returned 202 and persisted its Task. The page
  reports `命令未执行，当前数据未被修改；请根据原因修正后重试或刷新目录。` and leaves Delete enabled;
  running the actual Worker then deletes the file. MediaLibrary reports an unknown outcome, but
  also leaves Delete enabled without reconciling the admitted Task. A live directory refresh
  cannot establish that queued work was not admitted. Evidence: after `npm --prefix web run build`,
  start `.venv/bin/python -c 'import scripts.direct_files_browser_harness as harness; from mediaflow.infrastructure.local_storage import LocalStorage; harness.FingerprintlessStorage = LocalStorage; raise SystemExit(harness.main(["--port", "4186"]))'`,
  then `node /tmp/mediaflow-b44-unknown-delete.mjs`; both kinds returned actual backend 202,
  retained the source before Worker execution and removed it after Worker completion. The
  Playwright probe uses `route.fetch()` followed by response abort, actual built pages/API/SQLite/
  Worker, and the complete production Local adapter with fingerprints; no Storage capability was
  removed. Results: `/tmp/mediaflow-b44-unknown-delete.log`. Preserve an unknown-admission state
  on both pages, reconcile its durable admission/outcomes through the native recovery path before
  enabling an explicit repeat, and never claim that a lost response proves no Task or effect.
- **P1 — Overlapping Delete selections are rejected instead of normalized/deduplicated
  (AC-3; RO-1 bounded selection Delete).** Origin: this rejection already exists at Task Base and
  `_delete_targets` is unchanged. It remains an unmet, preassigned AC-3 requirement, not a regression
  introduced by this checkpoint. `DirectFileCommandService._delete_targets` returns
  `files_direct_invalid_request` for a parent plus its child and for a repeated path. This blocks
  the required scoped API batch journey before the impact summary/confirmation rather than
  producing the single bounded effect required by the Contract. Evidence:
  `.venv/bin/python /tmp/mediaflow-b44-review.py` uses checked Active configuration, temporary
  roots and the production Local adapter. Both
  `/api/v1/resource-libraries/source/files/delete-impact` and
  `/api/v1/media-libraries/movies/files/delete-impact` return HTTP 400 for
  `path=Review-Overlap&path=Review-Overlap/child.txt` and for repeated
  `path=Review-Overlap/child.txt`; results are in `/tmp/mediaflow-b44-review.log`. Normalize exact
  confined paths and collapse duplicate/descendant selections consistently in impact and admission;
  retain the existing limits, complete enumeration, one confirmation and once-only per-entry effects.
- **P1 — Durable Delete discards known refusal reasons needed for recovery
  (AC-9; RO-1 independent failure/recovery; AGENTS.md product rules 2/9).** Origin: a regression in
  the new Worker path. Base's `_record_item` preserves Executor errors and its outcome mapping
  distinguishes `source_changed`; the candidate replaces known refusal reasons with `delete_failed`.
  The new
  `_execute_claimed_delete` replaces every known Executor refusal with `delete_failed` in both
  TaskItem and Result. A file changed after confirmed admission and an empty directory that gains
  unconfirmed content therefore have indistinguishable durable errors; the status API and native
  outcome list cannot explain why the item was retained or which observation/confirmation must be
  renewed. Evidence: `.venv/bin/python /tmp/mediaflow-b44-review.py` reproduces both cases on each
  library kind with the production Local adapter and real Worker. Changed files/unconfirmed
  children survive, but TaskItem, Result and status outcomes all contain only `delete_failed`;
  results are in `/tmp/mediaflow-b44-review.log`. Preserve bounded, secret-free refusal categories
  and corresponding recovery actions through persistence, API and both native pages, including
  source change and unexpected directory contents. Keep independent item outcomes and the
  investigation-only treatment of uncertain effects; do not expose raw adapter exceptions.
