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
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```
