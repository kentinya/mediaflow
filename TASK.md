# Task 27.4 — Current-Source Analysis Preview

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 27.4
Parent Slice: 27 - Manual Operations and File Lifecycle
Status: READY FOR B REVIEW
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
- `tests/test_operator_ui.py`
- `TASK.md`

### Implemented
- Correction round for the `FIX REQUIRED` decision recorded against
  03b744d4f26ee3dc77c9c4556806c201d47b2acf: added a focused
  `CurrentSourcePreviewWebTests` regression class to `tests/test_operator_ui.py` covering the
  Task 27.4 current-source Preview Web surfaces that previously had no assertions. No product
  code was changed; the existing API/security and zero-mutation tests are untouched.
- Files journey (`renderFiles`): the `Preview` table column, the per-item `Preview file` action
  built only from a verified current index membership, the explicit
  `Preview unavailable until a verified current item exists` fallback, and the bounded
  ResourceLibrary `Preview <id>` controls mounted on the same journey.
- FileIndex journey (`renderFileIndex`) and file detail (`showDetail`): the `Preview` column and
  row action from a verified current occurrence, the `Preview current source (DryRun)` entry
  point, and the actionable `select a verified ready current occurrence` fallback.
- Request strictness (`manualPreviewPayloadFromFile`, `manualPreviewPayloadFromMembership`):
  payloads admit only current-identity fields (`scopeKind`/`fileId`/`resourceLibraryId`/
  `occurrenceId`/`fingerprint`), fail closed without verified ready evidence, and carry no Scan
  mode, path, operation, authority or Provider field.
- `confirmCurrentPreview`: bounded-scope confirmation with a fail-closed guard message, POST to
  the versioned `/api/v1/manual-previews` route, persisted-detail reopen, explicit
  `Keep source unchanged` cancel, and both zero-mutation statements (`no Task, review backlog,
  execution authority or Storage mutation is created` / `Storage was not changed and no
  execution authority was created`).
- Persisted Preview detail (`showManualPreview`): reloaded `Preview scope`
  (`kind:id (N item(s))`), pinned snapshot identity, `Storage mutation NONE/INVALID`, execution
  state, next action, per-item stage, current occurrence/fingerprint/state evidence,
  RecognitionType/policy/target/capability lines, recognition explanation, per-item
  `Zero mutation` state, `Blocker/failure` and `Recovery` rows for blocked items, the stale
  `Request fresh Preview` recovery action, and the executable-items filter that keeps execution
  authorization gated to `previewed` + current + complete-plan items.

### Tests and Results
- `PASS` — `.venv/bin/python -m unittest tests.test_operator_ui` — 40 tests (33 existing + 7 new).
- `PASS` — `.venv/bin/python -m unittest tests.test_manual_preview tests.test_manual_organize_preview tests.test_manual_organize_intent tests.test_manual_organize_execution tests.test_manual_scan tests.test_file_index_lifecycle tests.test_api_security tests.test_operator_ui` — 118 tests.
- `PASS` — `.venv/bin/python -m unittest tests.test_migration_rehearsal tests.test_sqlite_backup tests.test_sqlite_restore tests.test_task_persistence` — 22 tests.
- `FAIL / PRE-EXISTING / UNRELATED` — `.venv/bin/python -m unittest discover -s tests` — 1202 tests, 9 failures, 7 skips. The nine failures are the same set recorded at the previous checkpoint (credential-status ×2, queue-full continuation ×3 including discover's duplicate module identity, final-integration CLI, ResourceLibrary CLI, runtime-Storage CLI ×2). Reproduction evidence: the two queue-full failures reproduce at Task Base `5eae50b` in a clean worktree; with this workspace's ignored local `.mediaflow/` Active-runtime database present, all eight distinct failures reproduce at Task Base code as well. This checkpoint's only product-side change is the test file above.
- `PASS` — `.venv/bin/ruff format --check mediaflow tests` — 246 files already formatted.
- `PASS` — `.venv/bin/ruff check mediaflow tests`.
- `PASS` — `.venv/bin/python -m compileall -q mediaflow tests`.
- `PASS` — `.venv/bin/pip check` — no broken requirements found.
- `PASS` — `.venv/bin/mediaflow --config config/strategy.example.json config validate`.
- `PASS` — `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`.
- `PASS` — Markdown local-link validator over tracked Markdown — 123 files, 36 local links, 0 broken.
- `PASS` — `git check-ignore -v config/alist.json config/strategy.json .mediaflow config/.mediaflow`, tracking/staging check and secret scan over the checkpoint diff; private configuration remains ignored, untracked and unstaged.
- `PASS` — `git diff --check`.
- `PASS` — forbidden FFprobe/FFmpeg scan over `mediaflow` and `pyproject.toml`; 0 matches.
- `SKIP / UNAVAILABLE` — production SMB, OpenList, AWS S3/Cloudflare R2, live TMDB and multi-process concurrency gates; no production services or credentials were available or authorized, so validation used temporary LocalStorage and fake/local providers only.

### Decisions
- Followed the file's established static-asset assertion style (function-body extraction plus
  exact served-`APP_JS` strings) so the new coverage pins the exact rendered controls, fallbacks,
  recovery actions and zero-mutation messaging without requiring a browser runtime.
- Scope kept to exactly the B blocker: only `tests/test_operator_ui.py` gained assertions; no
  product code, API behavior or existing test was modified.
- Treated the seven workspace-dependent full-regression failures as environment-specific after
  proving they reproduce at Task Base code only when this workspace's ignored `.mediaflow/`
  runtime state is present; the final PASS/FAIL judgment on the full suite remains with B.

### Remaining In-Slice Work
- Explicit current-Preview manual Organize admission/execution and attachment transfer (RO-5).
- Conflict/Review re-analysis, continuation and recovery outcomes (RO-6).
- Processing Worker registration, readiness and ownership/fencing projections (RO-7).

### Risks / Deviations
- Full regression is `FAIL / PRE-EXISTING / UNRELATED` as evidenced above; existing SQLite
  `ResourceWarning` messages about unclosed test connections were also emitted.
- Running the suite inside this workspace exercises the CLI test paths against the workspace's
  own ignored Active runtime (read-only CLI stages only); the same code passes those tests in a
  clean checkout, which is where the reproduction evidence comes from.
- Existing uncommitted `SLICE.md`, `docs/roadmap.md`, `nohup.out` and `worker.log` changes were
  preserved and are not part of this checkpoint; the `TASK.md` update also carries the
  previously uncommitted B Review Result text for the reviewed SHA.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: be1b6f7ed8a53bcf915975a667526b8f3a2d6991
```

## B Review Result

```text
Reviewed: 03b744d4f26ee3dc77c9c4556806c201d47b2acf
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Blockers:

- The Task's required API/Web parity evidence is incomplete: `tests/test_operator_ui.py` has no
  focused assertions for the new current-source Preview controls and state rendered from the real
  Files, FileIndex and ResourceLibrary journeys. The `tests.test_operator_ui` command passes but
  does not exercise the Task 27.4 Web entry points, persisted Preview detail, blocked/stale recovery
  action or zero-mutation messaging. Add focused Web regression coverage for those paths while
  keeping the existing API/security and zero-mutation tests intact.

Fixes remain in this Task. This result does not close the Slice or update Roadmap.
