# Task 37.2 — Files ResourceLibrary Save and Atomic Activation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 37.2
Parent Slice: 37
Status: IN PROGRESS
Task Base: c654ed4edc5439b9298c1ab19ccdf1908935f7a8
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 37 **RO-4 ResourceLibrary drawer and activation** as one Web-native vertical
journey: an authorized operator completes the existing three-step `添加资源库` drawer and chooses
`保存` once; the backend validates the complete candidate against the save-time Active
configuration, performs the applicable read-only checked-activation work, atomically publishes and
binds the successor runtime on success, or preserves the previous Active and the operator's
recoverable Files context on every failure.

This Task also advances **RO-9 Actionable recovery**, **RO-10 Non-Files behavior continuity**,
**RO-11 Test reconciliation** and **RO-12 Security model continuity**. It does not implement common
file-management commands or change organize execution authority.

## Why This Task Exists

Task 37.1 delivered the reference-aligned drawer presentation, but its final `保存` control is
intentionally disabled and says activation belongs to a later Task. The existing generic managed
configuration APIs expose successor-Draft creation, object mutation, validation and activation as
separate administrative operations. Requiring a Files operator to orchestrate those revision-level
steps would violate the Slice's page-local, low-friction ResourceLibrary journey and would expose
internal lifecycle ceremony.

The missing behavior crosses configuration validation, persistence, runtime rebinding, API
authorization and the Files UI, so it is one coherent high-risk vertical unit. It must reuse the
existing managed configuration authority instead of introducing a second configuration store or a
frontend-owned Active state.

## Implementation Scope

```text
Managed configuration/application command → persistence and runtime binding → authenticated API → Files drawer → tests
```

- Add one focused application behavior for page-local ResourceLibrary Save. It accepts only the
  bounded business candidate needed by the drawer: ResourceLibrary ID, name, enabled state, an
  existing enabled Active Storage ID and a safe Storage-relative root path. It starts from one
  verified save-time Active snapshot and reuses the canonical ResourceLibrary normalization,
  reference validation, managed successor, validation, evidence and activation semantics.
- Keep the operation backend-authoritative and one-action from the browser. The browser must not
  create or sequence Draft revisions, submit revision/digest/checkpoint identifiers, supply Storage
  roots or credentials, or infer that a candidate is Active merely because an intermediate row
  exists.
- Require the existing API-principal permissions for both configuration management and activation.
  A principal missing either authority fails before publication; read-only/viewer access remains
  non-mutating.
- Validate the ResourceLibrary ID against the drawer contract, bounded name, duplicate ID,
  enabled/known Storage reference and safe relative path on the server even when the browser has
  already validated them. Absolute paths, separators in the ID, traversal, backslashes, NUL,
  malformed/oversized fields, disabled or missing Storage and conflicting IDs fail closed.
- Perform every applicable connection/evidence step as a bounded read-only check. Saving a
  ResourceLibrary must not scan media, call Metadata Providers, create a Job/Task, invoke
  OrganizerExecutor or perform any Storage mutation. Existing Active policy and destination
  invariants must remain valid for the exact successor that is published.
- Preserve optimistic concurrency across the whole page-level operation. If Active changes after
  the command starts, the competing winner remains Active and this request returns an actionable
  stale/conflict result without overwriting either the winner or an unrelated open Draft.
- Publish the candidate only when the exact successor has passed complete validation and applicable
  checked-activation admission and can be consumed by runtime. The success response must correspond
  to the exact immutable Active snapshot now used by the running process. Validation, Storage
  evidence, activation, persistence or runtime-binding failure must keep the previous Active
  authoritative and must not present the candidate as saved.
- Record bounded, secret-free audit evidence for the page-level action and its success or failure.
  Intermediate revision identifiers may remain backend evidence but are not ordinary Files UI
  steps or displayed authority.
- Add an authenticated API command for this one application behavior. Return bounded stable error
  categories and recovery guidance for invalid input, duplicate ID, forbidden authority, missing or
  stale Active, Storage/evidence failure, concurrency conflict and runtime publication failure.
- Complete all three drawer steps. Step transitions validate the current fields; Storage choices
  come from the current safe Active projection; the confirmation step shows the complete candidate;
  `保存` submits exactly once while pending. Failure keeps the drawer values and affected step,
  explains that the previous Active remains in use and offers correction/retry or refresh. Success
  refreshes the authoritative system status and live ResourceLibrary list, selects the newly Active
  enabled library, resets incompatible path/cursor/selection state and closes or clearly completes
  the drawer. A successfully saved disabled library is represented truthfully and is not fabricated
  as browseable.
- Keep `+ 添加资源库` available as a recovery entry when an Active configuration has Storage but no
  enabled ResourceLibrary. Missing Active or missing eligible Storage must show the prerequisite and
  safe next action rather than silently disabling the only recovery route.
- Add focused Python application/API/persistence tests, frontend model/API/component coverage and
  deterministic Playwright coverage for success, validation, authorization, stale/concurrent state,
  checked-activation/runtime failure and retry. Prove the old Active and Files browsing remain
  truthful on every failed save.
- Preserve the pre-existing working-tree modification to `docs/pics/文件页.png`; it is outside this
  Task and must not be staged, reverted, overwritten or used to hide a functional failure.

## Acceptance Criteria

- [ ] An authorized operator can complete `基本信息 → 存储位置 → 确认 → 保存` entirely from
      `/ui-v2/library/files` without CLI fallback, raw token transfer, revision/digest entry or
      separate Draft/Validate/Activate actions.
- [ ] The server accepts only a bounded ResourceLibrary candidate, requires both manage and activate
      authority, revalidates all fields/references/path confinement and rejects invalid, duplicate,
      missing/disabled-Storage or excessive input with stable action-oriented errors.
- [ ] One Save is based on one verified Active snapshot. A concurrent Active change or stale
      publication cannot silently overwrite the winner or an unrelated Draft and leaves the actual
      current Active/runtime identity truthful.
- [ ] Success means the exact validated successor is atomically Active and is the immutable runtime
      snapshot consumed by subsequent Files reads. An enabled new ResourceLibrary appears and can
      be selected immediately; a disabled one is saved truthfully but is not shown as browseable.
- [ ] Every validation, evidence, persistence, activation or runtime-binding failure preserves the
      previous Active runtime, reports that durable fact and provides a concrete correction, refresh
      or retry action. The UI never reports or renders a failed candidate as saved.
- [ ] The drawer preserves entered values and the relevant step on recoverable failure, prevents
      duplicate submission while pending, refreshes authoritative state after success and clears
      stale browse path, cursor and selection when switching to the newly activated library.
- [ ] The add-library recovery entry remains usable when Active contains eligible Storage but no
      enabled ResourceLibrary; missing Active/Storage states explain the prerequisite rather than
      leaving an unexplained disabled control.
- [ ] Save and all automatic checks perform zero media/Storage mutation and create no Scan, Job,
      Task, Provider request or organize execution. The operation emits bounded secret-free audit
      evidence and introduces no new identity, session or frontend authority.
- [ ] Existing generic Configuration workflows, non-Files V2 routes, V1 `/ui`, Files browsing and
      server-authoritative Preview behavior remain functional and retain their current permissions,
      failure/recovery semantics and immutable Active rules.
- [ ] Focused tests cover success, invalid and malformed input, duplicate ID, permission denial,
      missing/corrupt Active, missing/disabled Storage, path escape, evidence/check failure,
      concurrent Active replacement, runtime publication failure, safe retry and zero-side-effect
      behavior. The assigned T4 commands pass without weakened assertions or hidden skips.
- [ ] The checkpoint contains only Task 37.2 implementation, tests and its completion report. The
      pre-existing modified `docs/pics/文件页.png`, private configuration, credentials and unrelated
      files are excluded.

## Required Tests

- `python3 scripts/check_governance.py`
- `scripts/docker_release_security_smoke_test.py`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/python -m unittest discover -s tests`
- `.venv/bin/python -m compileall -q mediaflow tests scripts`
- `ruff format --check .`
- `ruff check .`
- `python -m unittest tests.test_resource_library_activation`
- `python -m unittest tests.test_configuration_successor_draft tests.test_configuration_objects tests.test_configuration_destination_activation tests.test_runtime_files_browser tests.test_api_security`
- `python -m unittest discover -s tests`
- `python -m compileall -q mediaflow tests scripts`
- `python -m pip check`
- `mediaflow --config config/strategy.example.json config validate`
- `mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"`
- `cd web && npm run format:check`
- `cd web && npm run typecheck`
- `cd web && npm run lint`
- `cd web && npm run test -- --run`
- `cd web && npm run build`
- `cd web && npm run test:e2e`
- `python -m pip wheel . --no-deps -w dist`
- `python scripts/wheel_smoke_test.py dist/mediaflow-*.whl`
- `git diff --check`
- Inspect `git status --short`, the exact Task Base..Head diff and staged manifest; confirm
  `config/alist.json`, credentials, the pre-existing modified `docs/pics/文件页.png` and unrelated
  files are unstaged and absent from the checkpoint.

All tests use mocks, fakes, temporary roots and local test servers only. No production
SMB/OpenList/S3/TMDB service, production credential or real media directory is permitted.

## Non-goals

- Create Folder/Text File, Rename, Copy, Move, Delete, text Edit, Upload, Download, destination
  picker or transfer progress; those remain later common file-management Tasks.
- Changes to OrganizerExecutor, Storage mutation semantics, organize execution authority or
  terminal Organize-result/FileIndex synchronization.
- Redesign of the general Configuration UI or removal of its explicit successor Draft,
  Validate/Test and checked Activate administration journey.
- Storage creation or editing inside the Files drawer; the candidate may reference only an eligible
  Storage already present in the verified Active configuration.
- New database schema, provider, Storage adapter/capability, identity/session system, FFmpeg,
  FFprobe, media probing or arbitrary host-path access.
- Pixel-polish work, reference-image changes, non-Files page-body redesign, unrelated refactors,
  optional proof and P2/P3 cleanup.

## Developer Completion Report

### Changed Files

- `mediaflow/application/configuration_objects.py`
- `mediaflow/domain/configuration_management.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_resource_library_activation.py`
- `web/src/features/library/StorageFilesPage.tsx`
- `web/src/features/library/StorageFilesPage.test.tsx`
- `web/src/shared/api/api-client.ts`
- `web/src/shared/api/library-api.test.ts`
- `TASK.md`

### Implemented

- Added bounded, secret-free Save failure details for candidate state, durable Active state and
  recovery guidance. Missing, corrupt and unreadable Active states now differ from a failed
  candidate runtime binding and from a concurrent winner.
- Scoped the winner/no-Active error semantics to the Files Save route so generic Configuration
  API failure contracts remain unchanged. The management-only dispatch still admits this one
  page-local recovery command without creating workflow work.
- Kept the drawer mounted through recoverable Save failures and authoritative status refreshes,
  preserving its entered values and current step. The page invalidates system-status and live
  Files queries when Active may have changed or become unavailable, with no automatic retry.
- Added backend coverage for missing/corrupt/unreadable and disabled Active/Storage cases,
  malformed and oversized fields, persistence/validation/activation failures, explicit retry,
  and falsifiable zero Scan/Job/Task/Provider/OrganizerExecutor and Storage-mutation behavior.
- Added frontend API/component coverage for bounded failure details, corrected messages and
  authoritative refresh while retaining the failed form context.

### Tests and Results

- `python3 scripts/check_governance.py` — PASS.
- `scripts/docker_release_security_smoke_test.py` — UNAVAILABLE: the committed script is not
  executable (`Permission denied`). Equivalent `python3 scripts/docker_release_security_smoke_test.py`
  ran and is FAIL / PRE-EXISTING / UNRELATED at the existing manual Organize `expectedVersion`
  contract (HTTP 400), before any ResourceLibrary Save assertion.
- `.venv/bin/ruff format --check .` — FAIL / PRE-EXISTING / UNRELATED: only the existing
  `mediaflow/application/manual_organize_preview.py` formatting violations remain.
- `.venv/bin/ruff check .` — FAIL / PRE-EXISTING / UNRELATED: five existing E501 violations in
  `mediaflow/application/manual_organize_preview.py` and one existing F841 in
  `mediaflow/application/storage_browser.py`.
- Focused `.venv/bin/ruff check` over the changed Python source/tests — PASS; focused format check
  over the changed Python source/tests — PASS.
- `.venv/bin/python -m unittest tests.test_resource_library_activation` — PASS (14 tests).
- `.venv/bin/python -m unittest tests.test_configuration_successor_draft tests.test_configuration_objects tests.test_configuration_destination_activation tests.test_runtime_files_browser tests.test_api_security` — PASS (132 tests).
- `.venv/bin/python -m unittest tests.test_release_security` — PASS (6 tests).
- `.venv/bin/python -m unittest discover -s tests` — FAIL / PRE-EXISTING / UNRELATED: 1537 tests,
  3 failures, 7 skips. Failures are the existing configuration-status `root_path` assertion and
  two real Preview contract tests rejected by the Task-Base `fileId` allowlist omission; no new
  failure or missing-`httpx` error remains in the isolated environment.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- Bare `ruff format --check .`, `ruff check .`, all required bare `python -m unittest`/
  `compileall` commands and `python -m pip check` — UNAVAILABLE: this environment has no
  `ruff` or `python` executable on PATH.
- `.venv/bin/python -m pip check` — PASS.
- Bare `mediaflow --config ... config validate` commands — UNAVAILABLE: the installed entry point
  is not on PATH. `.venv/bin/mediaflow --config config/strategy.example.json config validate` and
  the phase 13.2 variant — PASS.
- `test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"` — PASS.
- `cd web && npm run format:check` — PASS.
- `cd web && npm run typecheck` — PASS.
- `cd web && npm run lint` — PASS.
- `cd web && npm run test -- --run` — PASS (32 files, 411 tests).
- `cd web && npm run build` — PASS; Vite emitted only the existing chunk-size warning.
- `npx vitest run src/features/library/StorageFilesPage.test.tsx` — PASS (1 file, 6 tests).
- `cd web && npm run test:e2e` — FAIL / PRE-EXISTING / UNRELATED: 92 passed, 10 failed;
  failures are existing FileIndex/Preview/manual-operation journeys. The ResourceLibrary Save
  test passed.
- Bare `python -m pip wheel . --no-deps -w dist` and bare wheel smoke — UNAVAILABLE because
  `python` is not on PATH. `.venv/bin/python -m pip wheel --no-build-isolation . --no-deps -w dist`
  — PASS; `.venv/bin/python scripts/wheel_smoke_test.py dist/mediaflow-*.whl` — PASS, including
  installed CLI startup, configuration validation, database backup/restore/verify and upgrade
  preflight.
- `.venv/bin/python -m unittest tests.test_resource_library_activation tests.test_release_security`
  — PASS (20 tests).

### Decisions

- Files Save error projections carry only bounded state fields; raw server messages and internal
  diagnostics remain outside the frontend API model.
- Winner/no-Active durable-state wording is selected only for the Files Save route; generic
  Configuration API contracts keep their previous semantics.
- The drawer remains mounted when Save or its status refresh fails, so entered values and the
  current step survive while system-status/Files queries are invalidated when authority may have
  changed. No automatic retry or replay was added.
- The Save path remains read-only with respect to media and Storage, and its focused test patches
  Scan, Job, Task, Metadata Provider and OrganizerExecutor entry points in addition to checking
  Storage mutation counters.
- The pre-existing `docs/pics/文件页.png` modification and B's Review Result were preserved; the
  image is excluded from the correction checkpoint.

### Remaining In-Slice Work

No additional correction work is known inside this Task. Other Slice outcomes remain for B to
assess against the Slice Contract; no next Task is being defined here.

### Risks / Deviations

- The full Python and Playwright gates remain non-green only for the documented
  pre-existing/unrelated Preview/FileIndex/manual-operation issues; these were not changed or
  hidden. The isolated environment removed the prior optional `httpx` availability error.
- The bare `python`, `ruff` and `mediaflow` commands are unavailable, and the release smoke
  script lacks an executable bit. Supported `.venv` equivalents were run; the release smoke's
  Python invocation still reaches the unrelated manual Organize `expectedVersion` failure.
- Full Ruff remains non-green for pre-existing files outside this Task; changed-file Ruff checks,
  compile, dependency, wheel and installed-artifact smoke checks pass.
- Vite's bundle-size warning remains informational and unrelated to this Task.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 7dfdbde65c7eefe78dac9c538cf0198dd318732a
```

## B Review Result

```text
Reviewed: c654ed4edc5439b9298c1ab19ccdf1908935f7a8..752920dbfcb96ea1989108474fa0e17bcefa9ea5
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- ResourceLibrary Save failure recovery is not truthful for missing/corrupt or concurrently
  replaced Active state.
  - Evidence: `resourceLibrarySaveFailure()` in
    `web/src/features/library/StorageFilesPage.tsx` lines 85-107 maps both
    `resource_library_runtime_failed` and `configuration_unavailable` to “新配置无法绑定运行时，旧
    Active 仍在使用”. The backend `RuntimeSnapshotUnavailable` response in
    `mediaflow/interfaces/service_api.py` lines 1012-1045 instead reports
    `durableState=managed_active_unavailable`; for a missing or corrupt Active there may be no usable
    old Active at all, so the UI statement is a fabricated durable fact.
  - Evidence: the same frontend function maps `configuration_conflict` and
    `configuration_version_conflict` to “旧 Active 仍在使用”. In these races the backend refreshes
    its runtime binding to the competing winner before returning the conflict, so the winner—not
    necessarily the request's old Active—is authoritative. The failure path only sets `saveError`
    and does not invalidate system-status or Files queries, leaving the page on a potentially stale
    Active identity and ResourceLibrary list.
  - Required correction: distinguish unavailable Active, failed candidate runtime binding and
    concurrent-winner states. State that the candidate was not saved, describe the actual known
    durable state, and refresh authoritative status/browse truth when Active may have changed or
    become unavailable. Preserve the drawer values and current step, and never automatically retry
    or replay Save.
- The focused automation does not cover all failure and side-effect cases required by this Task.
  - Evidence: `tests/test_resource_library_activation.py` contains seven tests. They cover success,
    some invalid input, duplicate ID, missing Storage, read-check/runtime failure, a disabled
    ResourceLibrary, concurrency and permission denial. The Storage fake also proves that its
    mutating methods were not invoked in the exercised paths.
  - Missing required backend evidence: no ResourceLibrary Save test covers an entirely missing
    Active, corrupt/unreadable Active, an existing but disabled Storage, malformed field types,
    oversized name/ID/path values, successor persistence failure, validation/persistence lifecycle
    failure, activation/publication failure, or a real failure followed by a safe successful retry.
    “Missing Storage” does not prove “disabled Storage”, and the Playwright fake-server retry does
    not execute the real Python managed-configuration/evidence/activation path.
  - Missing required zero-side-effect evidence: checking the Storage fake's mutation counters does
    not prove that Save creates no Scan, Job or Task, issues no Metadata Provider request and never
    invokes OrganizerExecutor. These separate Task acceptance claims need explicit falsifiable
    assertions.
  - Required correction: add focused Python and frontend/component or Playwright coverage for the
    missing cases, including the corrected missing/corrupt/concurrent Active messages and
    authoritative refresh behavior. Keep the existing assertions intact and do not hide skips.
- The assigned T4 quality and packaging gate is incomplete.
  - Evidence: the completion report records `.venv/bin/ruff format --check .`,
    `.venv/bin/ruff check .`, the bare Ruff variants, `python -m pip check`, both installed
    `mediaflow ... config validate` commands and wheel build as unavailable; wheel smoke was skipped
    because no wheel was produced. Those Required Tests therefore have not passed.
  - The reported direct `final_main` configuration checks and `compileall` are useful partial
    evidence but do not prove Ruff compliance, dependency consistency, the installed CLI entry
    point, wheel contents, installation or installed-artifact startup.
  - Required correction: use a supported isolated development environment, run the specified Ruff,
    installed CLI, dependency and wheel build/smoke commands, and record their actual results.
  - The independently reproduced non-green full regressions are not this blocker and must remain
    reported truthfully: the Task Base has the same Python 3 failures plus one missing optional
    `httpx` error and the same 10 legacy FileIndex/Preview Playwright failures. They are
    pre-existing/unrelated under the review rule and must not be hidden, skipped or weakened.
