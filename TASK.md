# Task 27.4 — Current-Source Analysis Preview

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 27.4
Parent Slice: 27 - Manual Operations and File Lifecycle
Status: PLANNED
Task Base: 5eae50b79172082ef6481009fad95fa3d731360b
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 27 RO-4: from the real `Files` or indexed `FileIndex` journey, an authenticated
operator can select one exact current source item or a bounded ResourceLibrary selection and run the
complete analysis-only parse -> recognition -> metadata -> naming -> classification -> plan path
against one immutable Active runtime snapshot. The resulting Preview is durable, bounded,
explainable and inspectable through the same Web/API behavior, while performing zero Storage media
mutation and creating no execution authority or mandatory review backlog merely because analysis
found a blocker.

## Why This Task Exists

Task 27.1 established the real configured Storage browser, Task 27.2 established current source
occurrence and processing disposition, and Task 27.3 added durable bounded discovery refresh. The
next user-visible gap is the analysis decision after discovery: the operator can see a current source
but cannot yet carry that exact current identity through the complete production-equivalent Preview
journey from the Slice 27 Files/FileIndex entry points.

The existing manual-organize intent and Preview foundations are reusable, but this Task must bind
them to the current FileIndex occurrence/fingerprint and the bounded ResourceLibrary scope, preserve
the exact Active snapshot, and expose the persisted findings and blockers without turning Preview
into execution. This is the largest reasonable next unit because manual Organize and recovery must
consume an exact, durable Preview rather than reconstructing analysis inputs later.

## Implementation Scope

```text
Current-source selection -> Preview domain identity -> persistence -> analysis runner -> versioned API -> Operator Web -> tests
```

- **Domain and application:** admit only a bounded set of current FileIndex identities, or one
  configured ResourceLibrary scope resolved to a bounded set of current items. Validate each
  `fileId`, occurrence ID and fingerprint against the current FileIndex before analysis; stale,
  missing, unstable, ambiguous or replaced sources fail closed with an actionable bounded result.
  Reuse the established manual intent and Preview services and the existing production parser,
  RecognitionType policy, Metadata provider, Naming, Classification and OrganizePlan authorities.
- **Snapshot and persistence:** pin the exact immutable Active runtime snapshot consumed by the
  Preview, persist source occurrence/fingerprint, selected choices, input evidence, normalized
  explanations, target/conflict/capability information, zero-mutation declaration, bounded item
  status and next action. Reloaded Preview data must be identical and must not be rebuilt or mutated
  merely by a read.
- **Analysis boundary:** use read-only Storage guards and the existing provider abstractions. Preview
  may read source metadata and configured target preflight evidence required by the existing planner,
  but it must not invoke OrganizerExecutor, execution authority, mutating Storage operations, source
  deletion, overwrite, cleanup, or an implicit Worker/subprocess. RecognitionType identity must remain
  unchanged when downstream policies reuse another policy definition.
- **API:** expose strict authenticated versioned admission and detail/list behavior through the
  shared application services for FileIndex selection and bounded ResourceLibrary selection. Reject
  arbitrary paths, Provider payloads, operations, authority fields and unbounded selections. Preserve
  RBAC, optimistic version/snapshot validation, audit, redaction, bounded pagination and actionable
  stale/provider/configuration/conflict errors; read-only viewers cannot admit or mutate Preview work.
- **Operator Web:** add Preview actions to the real `Files` and `FileIndex` journeys and the bounded
  ResourceLibrary selection flow. Show the durable Preview scope, pinned snapshot, per-item findings,
  recognition/identity/naming/classification/destination explanations, warnings, conflicts,
  capability blockers, zero-mutation state and one concrete next action. Keep successful and blocked
  siblings independently visible. Do not expose execution authorization as an automatic Preview
  consequence.
- **Tests:** use temporary Local roots, fake Storage, isolated repositories and fake/local metadata
  providers. Cover exact current identity, ResourceLibrary bounds, stale replacement, provider and
  configuration failures, bounded findings, reload, sibling isolation, API/Web parity, RBAC,
  redaction and zero Storage mutation.

Frozen unless a listed Acceptance Criterion cannot be met without a minimal compatible change:

- `SLICE.md`, its Base SHA, Required Outcomes, Required Surfaces, Safety Invariants and Explicitly
  Deferred entries;
- Task 27.1 real-Storage Files browser, Task 27.2 current-occurrence/disposition contracts and
  Task 27.3 scoped Scan semantics;
- manual Organize admission/execution, one-shot authority, attachment transfer and mutation
  behavior (RO-5);
- conflict/review/recovery continuation, automatic replay and Worker registration/readiness/fencing
  (RO-6 and RO-7);
- OrganizerExecutor, Storage mutation/fallback policy, scheduled automation and configuration
  lifecycle behavior.

## Acceptance Criteria

- [ ] Authenticated operator/admin Web and API can start Preview for exactly one verified current
      FileIndex item or one bounded configured ResourceLibrary selection, with strict bounded request
      fields and no arbitrary path, operation, Provider or execution fields.
- [ ] Every selected source is checked against the current FileIndex `fileId`, occurrence and
      fingerprint plus required discovery/stability state. Stale, missing, ambiguous, unstable,
      replaced or unavailable inputs fail closed with no Preview that claims to represent the new
      source and with a concrete next action.
- [ ] Accepted Preview consumes and persists one exact immutable Active snapshot. Reloaded detail
      exposes the same scope, source evidence, choices, findings, explanations, plan, blockers,
      snapshot identity and bounded item outcomes without read-time mutation.
- [ ] The complete applicable production analysis/planning path runs for each selected item and
      preserves RecognitionType identity, downstream policy reuse, metadata/provider semantics,
      naming/classification decisions, target path, conflict result and Storage capability evidence.
- [ ] Preview is strictly zero-mutation for media Storage: no OrganizerExecutor, execution
      authority, move/copy/link/delete/overwrite/cleanup or implicit Worker startup is invoked. A
      finding or blocker does not create a mandatory review backlog or authorize execution.
- [ ] Findings and failures identify the affected item and stage, preserve independent sibling
      outcomes, redact secrets, bound all persisted evidence, and expose an actionable next step for
      stale source, provider, configuration, conflict, capability and analysis failures.
- [ ] API and Operator Web use matching application behavior, validation, permissions, audit,
      redaction, pagination and recovery-safe state. Viewer/read access cannot admit Preview work or
      mutate Preview state.
- [ ] Focused and required T4 tests cover success, invalid/stale input, provider/configuration
      failure, conflict/capability blocker, bounded selection, reload, sibling isolation, RBAC,
      redaction and zero-mutation safety. The checkpoint contains only this Task and no private
      configuration, credentials, endpoints or user media.

## Required Tests

Run from the repository root with the project environment:

```bash
.venv/bin/python -m unittest \
  tests.test_manual_preview \
  tests.test_manual_organize_preview \
  tests.test_manual_organize_intent \
  tests.test_manual_organize_execution \
  tests.test_manual_scan \
  tests.test_file_index_lifecycle \
  tests.test_api_security \
  tests.test_operator_ui
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check mediaflow tests
.venv/bin/ruff check mediaflow tests
.venv/bin/python -m compileall -q mediaflow tests
.venv/bin/pip check
git diff --check
```

Also run applicable migration/persistence checks, configuration validation, Markdown local-link
validation, private-config/secret scan and forbidden FFprobe/FFmpeg scan. Record production
SMB/OpenList/AWS S3/Cloudflare R2, live TMDB and multi-process gates as `SKIP / UNAVAILABLE` unless
an explicitly isolated environment is available. Use no production credentials, private endpoints
or user media. Full regression failures may be treated as pre-existing only when reproduced from
this Task Base or otherwise proven unrelated.

## Non-goals

- Manual Organize admission/execution, one-shot authority, attachment mutation, overwrite/delete or
  any OrganizerExecutor operation (RO-5).
- Conflict/Review decision persistence as execution continuation, automatic replay, batch recovery
  or uncertain-mutation handling (RO-6).
- Worker registration/readiness/fencing, queue supervision or API health integration (RO-7).
- New Storage or Metadata providers, provider switching, arbitrary host-path browsing, unbounded
  recursive selection, media streaming, poster/background download, NFO generation or upgrades.
- Redesign of the closed Scanner, Parser, Recognition, Metadata, Naming, Classification, planner,
  manual execution or configuration lifecycle semantics beyond the minimum Preview integration.
- Slice 28 administration, Slice 29 Docker release, optional proof, broad UI redesign, P2/P3
  cleanup or work outside Slice 27.

## Developer Completion Report

### Changed Files
- `mediaflow/domain/manual_organize.py`
- `mediaflow/domain/manual_organize_preview.py`
- `mediaflow/application/manual_organize.py`
- `mediaflow/application/manual_organize_preview.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_manual_preview.py`

### Implemented
- Added exact current-source Preview admission from FileIndex and bounded ResourceLibrary scopes.
  File selections require the current `fileId`, verified occurrence ID and fingerprint; every
  selected source is checked for discovery/stability state, configured ResourceLibrary authority and
  the live read-only Storage occurrence before analysis.
- Reused the existing parser, RecognitionType policy, metadata-provider, naming, classification and
  OrganizePlan authorities under one immutable managed Active snapshot. Persisted plans include
  bounded parse/recognition/identity/policy/destination/conflict/capability explanations and an
  explicit zero-mutation declaration; RecognitionType identity remains separate from downstream
  policy reuse.
- Persisted current source occurrence/fingerprint evidence in manual intent items and persisted the
  exact Preview scope in SQLite, with additive compatibility migration and legacy reload fallback.
  Current-source reads/listing project stale evidence without publishing a read-time lifecycle
  mutation.
- Added independent bounded per-item source-admission outcomes for ResourceLibrary batches, strict
  authenticated API admission/detail/list routes, and matching Operator Web Preview actions from
  Files, FileIndex and ResourceLibrary controls. API/Web responses use the existing redaction and
  RBAC boundaries.
- Kept Preview analysis read-only: source and target adapters are guarded, no OrganizerExecutor,
  Task, Worker, execution authority or mandatory review backlog is created, and no move/copy/link/
  delete/overwrite/cleanup operation is invoked.

### Tests and Results
- `PASS` — `.venv/bin/python -m unittest tests.test_manual_preview tests.test_manual_organize_preview tests.test_manual_organize_intent tests.test_manual_organize_execution tests.test_manual_scan tests.test_file_index_lifecycle tests.test_api_security tests.test_operator_ui` — 111 tests.
- `PASS` — `.venv/bin/python -m unittest tests.test_migration_rehearsal tests.test_sqlite_backup tests.test_sqlite_restore tests.test_task_persistence` — 22 tests.
- `FAIL / PRE-EXISTING / UNRELATED` — `.venv/bin/python -m unittest discover -s tests` — 1195 tests, 9 failures, 7 skips. The nine failures reproduce the Task Base report's existing credential-status, final-integration CLI, queue-full continuation, ResourceLibrary CLI and runtime-Storage configuration assertions; none is in the current-source Preview path.
- `PASS` — `.venv/bin/ruff format --check mediaflow tests` — 246 files already formatted.
- `PASS` — `.venv/bin/ruff check mediaflow tests`.
- `PASS` — `.venv/bin/python -m compileall -q mediaflow tests`.
- `PASS` — `.venv/bin/pip check` — no broken requirements found.
- `PASS` — `git diff --check` and staged checkpoint diff check.
- `PASS` — `.venv/bin/mediaflow --config config/strategy.example.json config validate`.
- `PASS` — `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- `PASS` — Markdown local-link validator — 36 local links checked, 0 broken.
- `PASS` — `git check-ignore -v config/alist.json`, tracking check and private-config boundary check; `config/alist.json` remains ignored, untracked and unstaged.
- `PASS` — forbidden FFprobe/FFmpeg scan over `mediaflow` and `pyproject.toml`; 0 matches.
- `SKIP / UNAVAILABLE` — production SMB, OpenList, AWS S3/Cloudflare R2, live TMDB and multi-process concurrency gates; no production services or credentials were available or authorized, so validation used temporary LocalStorage and fake/local providers only.
- ResourceWarnings about unclosed SQLite connections were emitted by existing tests; they did not change the stated test statuses.

### Decisions
- Kept `SCHEMA_VERSION` at 32 and used additive, idempotent columns for source identity and
  Preview scope so current and legacy SQLite databases retain their existing compatibility contract.
- Used FileIndex occurrence plus Storage-derived SHA-256 evidence as the current-source boundary;
  the admission path accepts no arbitrary path, operation, Provider payload or execution field.
- Kept the existing manual intent/Preview and strategy/planner services as the behavior authorities,
  adding only current-source admission, immutable managed-snapshot checks and read-only Storage
  guards around them.
- For a bounded ResourceLibrary batch, a source admission failure is persisted as that item's
  bounded `STALE`, `BLOCKED` or `UNAVAILABLE` outcome while valid siblings continue independently;
  a single exact-file admission failure remains fail-closed with no Preview published.

### Remaining In-Slice Work
- Explicit current-Preview manual Organize admission/execution and attachment transfer (RO-5).
- Conflict/Review re-analysis, continuation and recovery outcomes (RO-6).
- Processing Worker registration, readiness and ownership/fencing projections (RO-7).

### Risks / Deviations
- Full regression is `FAIL / PRE-EXISTING / UNRELATED` as listed above; existing SQLite
  `ResourceWarning` messages about unclosed test connections were also emitted.
- Production remote-provider and multi-process behavior is unverified because the required
  services/credentials were unavailable and no production authority was used.
- Existing uncommitted `SLICE.md`, `docs/roadmap.md`, `nohup.out` and `worker.log` changes were
  preserved and not included in the implementation checkpoint; `config/alist.json` was not staged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 03b744d4f26ee3dc77c9c4556806c201d47b2acf
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
