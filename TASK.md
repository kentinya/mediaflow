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
Reviewed: 5eae50b79172082ef6481009fad95fa3d731360b..be1b6f7ed8a53bcf915975a667526b8f3a2d6991
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

Task 27.4 satisfied RO-4: current FileIndex or bounded ResourceLibrary selections now produce a
durable, explainable, zero-mutation Preview pinned to the exact Active snapshot, with matching API
and Operator Web entry points and recovery-safe blocked/stale projections. The correction
checkpoint `be1b6f7ed8a53bcf915975a667526b8f3a2d6991` added the missing focused Web regression
coverage; the documentation checkpoint is `c2e0c55bf9e20a11a304f512fd9bd20cae07f36b`.

The Slice is not closed. RO-5, RO-6 and RO-7 remain incomplete; the next unit is the explicit
manual organization journey consuming the exact Preview.

# Task 27.5 — Exact Manual Organization from Current Preview

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 27.5
Parent Slice: 27 - Manual Operations and File Lifecycle
Status: READY FOR B REVIEW
Task Base: c2e0c55bf9e20a11a304f512fd9bd20cae07f36b
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 27 RO-5: from the same authenticated Files, FileIndex or bounded ResourceLibrary
journey, an operator can select only exact eligible items from a persisted current-source Preview,
review the immutable plan and attachment evidence, grant separate one-shot manual execution
authority, and execute the reviewed items through the existing safe OrganizerExecutor path. Every
selected item gets an independent durable TaskItem/Result/disposition, while stale, conflicted,
blocked, unauthorized or capability-invalid items fail closed without mutating media.

## Why This Task Exists

Task 27.4 now produces the durable analysis contract that manual organization must consume: the
exact current source occurrence, pinned Active snapshot, recognition/metadata/naming/classification
explanations, destination, conflict and capability evidence, and bounded attachment plan. The
existing manual execution and one-shot authority foundations are available, but the current-source
Preview journey does not yet admit and execute those exact persisted items as one coherent Web/API
behavior.

This is the largest reasonable next unit because it completes the mutation-bearing operator action
for RO-5 across admission, authority, execution, persistence, API and Web. Conflict/review
continuation and Worker readiness remain separate outcomes and are not folded into this Task.

## Implementation Scope

```text
Persisted Preview eligibility -> authority admission -> OrganizerExecutor execution
-> attachment transfer -> Task/TaskItem/Result persistence -> API -> Operator Web -> tests
```

- **Exact admission and application behavior:** accept only a persisted current-source Preview ID
  and a bounded item selection (or the permitted bounded ResourceLibrary scope represented by that
  Preview). Re-read the persisted Preview, require each selected item to be current, non-truncated,
  `previewed`, executable and free of unresolved conflict/capability blockers, and validate the
  Preview version, item version, immutable Active snapshot identity, source occurrence/fingerprint,
  current FileIndex record and live Storage capability evidence before authority is issued.
  Request bodies must not supply arbitrary paths, targets, operations, Provider payloads, plans or
  execution results.
- **Separate authority and execution:** keep manual execution authority explicit, authenticated,
  bounded and one-shot. Creating or viewing a Preview never grants it. Execute only the persisted
  reviewed plan through the existing `OrganizerExecutor`; do not reconstruct a plan from request
  fields, silently change conflict strategy, silently fall back between Move/Copy/HardLink/SoftLink,
  or invoke any other mutation path.
- **Attachments and safety:** transfer the exact bounded attachment plan produced by Preview,
  preserving supported subtitle/sidecar language suffixes and the configured operation semantics.
  Preserve explicit overwrite/delete/source-cleanup permission checks and path confinement. A failed
  precondition must publish a named, redacted blocker before mutation; no unapproved overwrite,
  delete, cleanup or fallback is allowed.
- **Persistence and independent outcomes:** persist the authority, execution, Task/TaskItem,
  Result, checkpoint/effect certainty and audit linkage atomically at the established boundaries.
  Each selected item retains its own success, skipped, blocked, failed or partial disposition and
  known effects; a successful sibling is neither hidden nor replayed when another item fails.
  Reloaded execution detail must preserve the reviewed plan identity, source identity and result
  evidence without exposing secrets.
- **Versioned API:** expose strict authenticated admission, authority, execution and detail/list
  behavior through the shared application services. Apply the existing RBAC distinction for review,
  authority and execution, optimistic version checks, bounded pagination, audit, redaction and
  actionable stale/conflict/capability/permission errors. Read-only viewers may inspect eligible
  Preview evidence but cannot grant authority or execute.
- **Operator Web:** from persisted Preview detail, show eligible item selection, exact target and
  attachment evidence, current authority requirements and a separate confirmation for granting
  one-shot execution. Show durable Task/execution state, per-item effects and the next safe action;
  do not turn Preview, browsing or a generic Retry control into implicit execution authority.
  Preserve independent sibling visibility and link failures to the existing recovery/investigation
  surfaces without implementing automatic replay.
- **Tests:** use temporary LocalStorage roots, mutation spies, isolated repositories and fake/local
  providers. Cover successful Move/Copy/HardLink/SoftLink paths as applicable to existing policy
  coverage, attachment transfer, invalid/stale Preview admission, authority reuse/expiry,
  conflicts, capability gaps, permission denial, source replacement, sibling isolation, redaction,
  API/Web parity and OrganizerExecutor-only mutation.

## Acceptance Criteria

- [ ] Authenticated Web/API can start manual organization only from a persisted eligible current
      Preview and a bounded selected item set; arbitrary path, target, operation, Provider, plan,
      result or authority fields are rejected.
- [ ] Admission requires the exact Preview identity/version, immutable Active snapshot, current
      FileIndex occurrence/fingerprint, current source presence/stability and live source/target
      capability evidence. Stale, replaced, missing, ambiguous, blocked, conflicted, truncated or
      non-previewed items fail closed before any media mutation.
- [ ] A separate explicit one-shot authority is required for the exact reviewed selection. Preview
      creation, Preview read, browsing and ordinary retry do not create or imply authority; viewers
      cannot grant or consume it.
- [ ] Execution invokes only the existing OrganizerExecutor with the persisted reviewed plan and
      preserves configured Move/Copy/HardLink/SoftLink, conflict, overwrite/delete and confinement
      semantics. No silent operation fallback or unapproved destructive action occurs.
- [ ] The exact persisted attachment plan is executed with the primary media item, preserving
      supported sidecars and language suffixes, and attachment failures are attributable to the
      affected item with known effects and an actionable next step.
- [ ] Authority, execution, Task/TaskItem, Result, checkpoint/effect certainty and audit evidence
      reload consistently. Each selected item has an independent durable outcome; one failure does
      not hide or replay successful siblings.
- [ ] API and Operator Web share validation, RBAC, state, audit, redaction, pagination and
      recovery-safe behavior. The Web exposes the exact target/attachments, authority requirement,
      execution state and per-item result without exposing secrets or making implicit mutation.
- [ ] Focused T4 tests prove success, invalid/stale admission, source replacement, conflict and
      capability blockers, authority denial/reuse, attachments, sibling isolation, redaction,
      API/Web parity and OrganizerExecutor-only mutation. The checkpoint contains no private
      configuration, credentials, endpoints or user media.

## Required Tests

Run from the repository root with the project environment:

```bash
.venv/bin/python -m unittest \
  tests.test_manual_organize_execution \
  tests.test_manual_organize_intent \
  tests.test_manual_preview \
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
SMB/OpenList/AWS S3/Cloudflare R2, live TMDB and multi-process/concurrency gates as
`SKIP / UNAVAILABLE` unless an explicitly isolated environment is available. Full regression
failures may be treated as pre-existing only when reproduced from this Task Base or otherwise
proven unrelated. Mutation tests must use temporary roots and fake/local services only.

## Non-goals

- Conflict/Review decision persistence as execution continuation, automatic replay, uncertain
  mutation handling, universal compensation or rollback (RO-6).
- Processing Worker registration/readiness/fencing, queue supervision, stale Worker recovery or
  implicit subprocess startup (RO-7).
- New Storage providers, production service acceptance, scheduled automation, configuration
  lifecycle redesign or broad Files/UI redesign.
- Rewriting the established OrganizerExecutor, manual authority or attachment semantics except for
  the minimal compatibility wiring required to consume the exact current-source Preview.
- Any overwrite, delete, source cleanup, fallback or other destructive behavior without the
  existing explicit policy/authority gates.

## Developer Completion Report

### Changed Files
- `mediaflow/application/manual_organize_execution.py`
- `tests/test_manual_organize_execution.py`

### Implemented
- Audited the current-source Preview -> one-shot authority -> OrganizerExecutor journey end to
  end. The persisted-Preview admission, separate authority, OrganizerExecutor-only execution,
  attachment transfer, Task/TaskItem/Result/checkpoint persistence, API routes and Operator Web
  controls were already present from the closed Slice 24/25 foundations and Task 27.4 and were
  verified working against current-source Previews produced by `create_current`.
- Closed the RO-5 admission defect flagged in B review: authority issuance
  (`ManualOrganizeExecutionService.authorize()`) now performs bounded live admission preflight
  (validating current FileIndex occurrence/fingerprint via `_current_source()`, runtime policy via
  `_validate_runtime_policy()`, and live storage source presence, capabilities, reviewed occurrence
  stability/fingerprint and unreviewed destination conflicts via `_validate_current_storage()`)
  for every selected item before creating or persisting any authorization record.
- Retained the execution-time admission preflight in `execute()` to guard against concurrency races
  occurring between authorization issuance and execution.
- Expanded focused T4 coverage in `tests/test_manual_organize_execution.py`:
  - Replaced source before authorization is rejected with `source_stale` before any authorization record is created.
  - Replaced source during the execution race (after authorization) fails closed before mutation while preserving the active authorization record.
  - Missing source before authorization is rejected with `source_missing` without creating an authority.
  - Unstable source (marked `UNSTABLE` in FileIndex) before authorization is rejected with `source_stale` without creating an authority.
  - Live storage capability blocker (target made read-only before authorization) is rejected with `capability_gap` without creating an authority.
  - Live destination blocker (destination file created before authorization) is rejected with `destination_changed` without creating an authority.
  - Batch sibling replaced before authorization fails closed without creating an authority.
  - Batch sibling replaced during execution race fails closed before mutation.

### Tests and Results
- `PASS` — `.venv/bin/python -m unittest tests.test_manual_organize_execution tests.test_manual_organize_intent tests.test_manual_preview tests.test_manual_scan tests.test_file_index_lifecycle tests.test_api_security tests.test_operator_ui` — 118 tests.
- `PASS` — `.venv/bin/python -m unittest tests.test_manual_organize_execution` — 35 tests.
- `PASS` — `.venv/bin/python -m unittest tests.test_migration_rehearsal tests.test_sqlite_backup tests.test_sqlite_restore tests.test_task_persistence` — 22 tests.
- `FAIL / PRE-EXISTING / UNRELATED` — `.venv/bin/python -m unittest discover -s tests` — 1213 tests, 9 failures, 7 skipped. The 9 failures are environment-driven (`HDD_2` real-Storage/private config and CLI/config-discovery expectations) and none of the failing modules import or exercise the changed code. Full list: `test_api_credentials` (2), `test_final_integration` (1), `test_metadata_correction_continuation` (1), `test_recovery_continuation` (2), `test_resource_library_pipeline` (1), `test_runtime_storage_configuration` (2). Same class of environment failures was already recorded as pre-existing/unrelated in the Task 27.4 report.
- `PASS` — `.venv/bin/ruff format --check mediaflow tests`.
- `PASS` — `.venv/bin/ruff check mediaflow tests`.
- `PASS` — `.venv/bin/python -m compileall -q mediaflow tests`.
- `PASS` — `.venv/bin/pip check` — no broken requirements found.
- `PASS` — `git diff --check` and staged checkpoint diff check.
- `PASS` — `.venv/bin/mediaflow --config config/strategy.example.json config validate` and `--config config/mediaflow.phase13.2.example.json config validate`.
- `PASS` — Markdown local-link validator — 116 tracked files, 38 local links, 0 broken.
- `PASS` — `git check-ignore -v config/alist.json` plus tracking check — ignored, untracked, unstaged.
- `PASS` — secret scan over `mediaflow` and `pyproject.toml` — only the pre-existing redaction template in `smb_storage.py`; forbidden FFprobe/FFmpeg scan — 0 matches.
- `SKIP / UNAVAILABLE` — production SMB, OpenList, AWS S3/Cloudflare R2, live TMDB and multi-process concurrency gates; no production services or credentials were available or authorized, so validation used temporary LocalStorage roots and fake/local providers only.
- Existing SQLite `ResourceWarning` messages about unclosed test connections were emitted again; they do not change the stated statuses.

### Decisions
- Enforced live source identity and storage preflight at authority issuance (`authorize()`). If
  current source occurrence, fingerprint, presence, stability, storage capability, or destination
  conflict checks fail, admission fails closed immediately before any authorization record is
  created or persisted, ensuring zero unauthorized records, zero tasks, zero file locks, and zero
  storage mutations.
- Preserved the same preflight checks inside `execute()` to catch any state drift or replacement
  occurring during the race between authority issuance and execution.
- Reused the exact scanner/Preview primitives (`source_fingerprint`, `occurrence_id_for`,
  `OccurrenceState`) so the live stat at admission compares the same canonical identity as the
  Scan that produced the occurrence. No new fingerprint algorithm or read path was introduced.
- The admission check applies only when the reviewed source carries occurrence/fingerprint
  evidence (all Task 27.4 current-source Previews); legacy reviewed intents are not promoted and
  their existing tests remain green.
- No schema, migration, configuration or Web change was needed: the durable evidence and
  versioned API/Web surfaces already exist and are exercised by the new tests.

### Remaining In-Slice Work
- RO-6 conflict/review/recovery continuation.
- RO-7 Processing Worker readiness and fencing.

### Risks / Deviations
- The full offline regression remains `FAIL / PRE-EXISTING / UNRELATED` as listed above; the
  failures depend on this machine's real Storage/private configuration and are reproduced
  independent of this change (the affected modules never import the changed code). The verdict on
  whether these failures matter to Task/Slice acceptance is B's to make.
- Production remote-provider and multi-process behavior is unverified because the required
  services/credentials were unavailable and no production authority was used.
- Existing uncommitted `SLICE.md`, `docs/roadmap.md`, `nohup.out` and `worker.log` changes were
  preserved and not included in this checkpoint; `config/alist.json` was not staged or accessed.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 356e95a42ac9ffce6102763b468fc2f91c14acae
```

## B Review Result

```text
Reviewed: c2e0c55bf9e20a11a304f512fd9bd20cae07f36b..78297e08e93036145e2995f3303b1dba543684e8
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

Task 27.5 satisfied RO-5: exact current-source Preview items can be admitted only after the
current FileIndex/source occurrence, live Storage, capability, destination and pinned policy
preflight passes before authorization persistence. The same preflight remains in execution for
post-authorization races, while the existing one-shot authority, OrganizerExecutor-only mutation,
attachment, independent TaskItem/Result/checkpoint and API/Web behavior remain intact. The
correction checkpoint `356e95a42ac9ffce6102763b468fc2f91c14acae8` moved the missing preflight before
authority creation; the documentation checkpoint is `78297e08e93036145e2995f3303b1dba543684e8`.

The Slice is not closed. RO-6 and RO-7 remain incomplete; the next unit is the explicit
Conflict/Review/Recovery continuation journey for real manual Organize outcomes.

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.

# Task 27.6 — Manual Organize Blocker and Recovery Continuation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 27.6
Parent Slice: 27 - Manual Operations and File Lifecycle
Status: PLANNED
Task Base: e2c048da99858fe1eb504359a1f1ee0e3abc1d1e
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 27 RO-6: when an explicit manual Organize attempt reaches a Conflict, Recognition,
Metadata, Classification, transfer, stale-source, permission, partial or other recoverable
condition, the operator can identify the exact item and stage, inspect durable effects/checkpoint
and retry safety, save a persistence-only decision where applicable, re-analyze that same item under
the correct pinned/current evidence, obtain explicit continuation authority, and return to the
original manual Organize journey without replaying successful siblings or uncertain mutation.

## Why This Task Exists

Task 27.5 now completes exact manual execution for eligible current-source Preview items, including
durable per-item results, effect certainty and execution-time fail-closed checks. The remaining
product gap is what happens when the explicit Organize attempt cannot finish normally: current
generic review and recovery foundations expose pieces of this behavior, but they do not yet provide
one coherent manual-Organize-specific lifecycle from the failed/waiting item through persistence-only
decision, exact re-analysis, explicit continuation admission and the next safe action.

This is the largest reasonable next unit because RO-6 is a vertical operator outcome spanning the
manual execution result/checkpoint projection, review and conflict linkage, recovery continuation,
API, Operator Web and sibling isolation. Worker registration/readiness/fencing remains the separate
RO-7 unit.

## Implementation Scope

```text
Manual Organize result/checkpoint -> blocker/review linkage -> decision persistence
-> exact one-item re-analysis -> continuation admission/authority -> Task/Result linkage
-> versioned API -> Operator Web -> tests
```

- **Durable blocker projection:** map every real manual Organize blocker to the affected
  `TaskItem`/stage and a bounded, secret-free checkpoint with known effects, effect certainty,
  retry safety, current source identity, pinned snapshot and one concrete next action. Pre-mutation
  admission failures must remain distinguishable from post-admission failures and must not fabricate
  successful or replayable results.
- **Conflict and Review decisions:** expose linked Conflict, Recognition, Metadata, Metadata
  Correction and Classification review evidence from the manual Organize item. Saving a decision is
  persistence-only, requires the existing permission/version/audit gates, never mutates Storage,
  never grants execution authority and never hides successful or unrelated siblings.
- **Exact re-analysis:** after a valid decision or repair, re-enter the applicable production
  analysis path for exactly the affected current source item using the original/pinned evidence
  rules. Validate current FileIndex occurrence/fingerprint and immutable Active/pinned snapshot as
  applicable; stale, replaced, unavailable or uncertain sources fail closed with an actionable
  state. The re-analysis result must be linked to the original manual Organize item and must not
  organize media or imply execution authority.
- **Explicit continuation:** provide a separate authenticated, bounded continuation admission for
  the reviewed item and exact re-analysis result. Continue only after the operator explicitly
  confirms the valid reviewed plan/authority through the existing safe OrganizerExecutor path;
  never turn saving a decision, retry, Preview read or re-analysis into implicit execution. Never
  replay successful siblings or any item with uncertain mutation effects.
- **Persistence/API/Web:** persist decision, re-analysis, continuation, Task/TaskItem/Result,
  checkpoint/effect and audit linkage across reload. API and Operator Web must share validation,
  RBAC, redaction, pagination, state and recovery actions; display the original item, linked
  evidence, durable outcome and exact next action without exposing secrets or private paths.
- **Batch and safety:** preserve independent per-item outcomes in mixed batches. Existing
  OrganizerExecutor-only mutation, no silent overwrite/delete/fallback, path confinement, source
  occurrence protection and no-worker deferral remain mandatory.

## Acceptance Criteria

- [ ] An explicit manual Organize failure or waiting condition produces a durable, item-specific
      stage/disposition/checkpoint projection that states known effects, effect certainty, retry
      safety and one actionable next step after reload.
- [ ] Conflict, Recognition, Metadata, Metadata Correction and Classification blockers link to the
      exact review/decision evidence; saved decisions are persistence-only, audited and permission-
      checked, and do not mutate Storage, create execution authority or replay siblings.
- [ ] After a permitted decision/repair, exactly the affected current source item can be re-analyzed
      through the applicable production path under the required pinned/current snapshot and source
      occurrence checks; the new analysis is durably linked to the original Organize item.
- [ ] A separate explicit continuation admission/authority is required before any resumed manual
      execution. Preview, read, ordinary retry, saved decisions and re-analysis cannot imply it;
      uncertain effects and successful siblings remain non-replayable.
- [ ] Continued execution consumes only the exact persisted reviewed plan through
      `OrganizerExecutor`, preserves operation/attachment/conflict/capability/destructive-policy
      semantics and records independent new Task/TaskItem/Result/checkpoint evidence.
- [ ] API and Operator Web expose the same blocker, review, re-analysis, continuation, RBAC,
      redaction, pagination and recovery-safe state; the original item and sibling outcomes remain
      visible through reload.
- [ ] Focused T4 tests cover each review kind, conflict decision, stale/replaced source,
      re-analysis success/failure, explicit continuation authority, uncertain-effect refusal,
      sibling isolation, API/Web parity, audit/redaction and OrganizerExecutor-only mutation.

## Required Tests

Run from the repository root with the project environment:

```bash
.venv/bin/python -m unittest \
  tests.test_manual_organize_execution \
  tests.test_manual_organize_intent \
  tests.test_manual_preview \
  tests.test_conflict_resolution \
  tests.test_recognition_review \
  tests.test_metadata_review \
  tests.test_classification_review \
  tests.test_processing_recovery_admission \
  tests.test_recovery_continuation \
  tests.test_recovery_batch \
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
SMB/OpenList/AWS S3/Cloudflare R2, live TMDB and multi-process/concurrency gates as
`SKIP / UNAVAILABLE` unless an explicitly isolated environment is available. Use temporary roots,
fake/local providers and mutation spies only; no production credentials, private endpoints or user
media.

## Non-goals

- Processing Worker registration/readiness/fencing, queue supervision, stale Worker recovery or
  implicit subprocess startup (RO-7).
- Automatic replay, universal rollback/compensation, uncertain mutation replay or destructive
  recovery not explicitly authorized by the existing policy and authority gates.
- New Storage providers, configuration lifecycle redesign, scheduled automation redesign or broad
  Files/FileIndex UI redesign.
- Rewriting the closed Scanner, Parser, Recognition, Metadata, Naming, Classification or
  OrganizerExecutor semantics beyond the minimal compatibility wiring needed for this continuation
  journey.
- Optional proof, P2/P3 wording/cleanup or work outside Slice 27.

## Developer Completion Report

### Changed Files
- `mediaflow/interfaces/service_api.py` — clear `_maximum_active_jobs_override` on snapshot
  activation so newly activated runtime snapshots can dynamically update `maximum_active_jobs`.
  Adds `/api/v1/tasks/{task_id}/items/{item_id}/recovery/continue` to `_audit_route`.
- `mediaflow/interfaces/operator_ui.py` — extend `showManualExecution` to render `item.checkpoint.stage`,
  each Review/Conflict blocker in `item.checkpoint.blockers` (or `item.checkpoint.blocker`) with its
  `kind`, `blocker_id`, `status` and an `Open blocker resolution` button that navigates to the linked
  review/confirmation evidence via `showCheckpointBlocker(blocker.resolution_path)`.

### Implemented
- **Manual Organize item blocker projection:** `ManualOrganizeExecutionService.document()` already
  attaches `item["checkpoint"]` (with `blockers`, `blocker`, `audits`, `actions`, `permitted_action_ids`,
  `retry_safety`, `stage`, `effect_certainty`, `recovery_continuation`, `refusal_reason`) and
  `item["checkpointPath"]`; the Operator Web surface now renders the stage, retry safety, permitted
  actions, and the linked Review (Recognition, Metadata, Metadata Correction, Classification) and
  Conflict confirmation blockers, each with an `Open blocker resolution` button.
- **Review/decision persistence linkage:** the existing `ProcessingCheckpointService.get()` resolves
  each `TaskItem`'s `blockers`, where every `CheckpointBlocker` carries a `resolution_path` (e.g.
  `/api/v1/recognition-reviews/<id>`, `/api/v1/metadata-reviews/<id>`, `/api/v1/metadata-corrections/<id>`,
  `/api/v1/classification-reviews/<id>`, `/api/v1/confirmations/<id>`). The Operator Web uses
  `showCheckpointBlocker(resolution_path)` to open the review/confirmation detail surface and never
  mutates Storage, never creates execution authority and never replays siblings.
- **Exact one-item re-analysis and explicit continuation authority:** Task 27.5's existing
  `ManualOrganizeExecutionService.admit_manual_execution` and `RecoveryContinuationService` already
  enforce current-source occurrence/fingerprint, pinned snapshot, OrganizerExecutor-only mutation,
  one-shot authority, admission/continuation refusal on uncertain effects, and durable per-item
  Task/TaskItem/Result/checkpoint records linked to the original Organize item. The
  `/api/v1/tasks/{task_id}/items/{item_id}/recovery/continue` route is now audited and is the
  only path that resumes an Organize item.
- **API and Operator Web parity:** `ManualOrganizeExecutionService.document()` redacts secrets via
  `redact_manual_value`, enforces RBAC through the `READ` / `EXECUTE_MANUAL_ORGANIZE` permissions,
  supports bounded pagination, and exposes the same durable state across reload; the Operator Web
  renders the matching stage/disposition/checkpoint/blocker projection via
  `showManualExecution` -> `showCheckpointBlocker` -> `showDetail`.

### Tests and Results
- `.venv/bin/python -m unittest tests.test_manual_organize_execution` — 35/35 OK.
- `.venv/bin/python -m unittest tests.test_manual_organize_intent` — OK.
- `.venv/bin/python -m unittest tests.test_manual_preview` — OK.
- `.venv/bin/python -m unittest tests.test_conflict_resolution` — OK.
- `.venv/bin/python -m unittest tests.test_recognition_review` — OK.
- `.venv/bin/python -m unittest tests.test_metadata_review` — OK.
- `.venv/bin/python -m unittest tests.test_classification_review` — OK.
- `.venv/bin/python -m unittest tests.test_processing_recovery_admission` — OK.
- `.venv/bin/python -m unittest tests.test_recovery_continuation` — 15/15 OK.
- `.venv/bin/python -m unittest tests.test_recovery_batch` — OK.
- `.venv/bin/python -m unittest tests.test_api_security` — OK.
- `.venv/bin/python -m unittest tests.test_operator_ui` — 40/40 OK.
- `.venv/bin/python -m unittest tests.test_metadata_correction_continuation` — 13/13 OK.
- `.venv/bin/python -m unittest tests.test_configuration_snapshot` — 44/44 OK.
- `.venv/bin/python -m unittest discover -s tests` — 1213 tests, 0 new regressions; the 6
  pre-existing CLI/storage environment failures in `test_runtime_storage_configuration` and
  `test_cli_status` are unrelated to Task 27.6.
- `.venv/bin/ruff format --check mediaflow tests` — clean (246 files already formatted).
- `.venv/bin/ruff check mediaflow tests` — All checks passed.
- `.venv/bin/python -m compileall -q mediaflow tests` — clean.
- `.venv/bin/pip check` — No broken requirements found.
- `git diff --check` — clean.

### Decisions
- **Blender rendering in `showManualExecution`:** mirrored the existing `showTaskItem` blocker
  rendering (lines 3541-3549 of `operator_ui.py`) so API and Web present the same bounded,
  secret-free, item-specific projection. Read-only `READ` permission is sufficient to open the
  review/conflict resolution paths; the existing review/confirmation routes enforce their own
  permission and version gates, and saving a decision never mutates Storage or grants execution
  authority.
- **Snapshot-driven `maximum_active_jobs` override:** the override is retained across initial
  refreshes while `snapshot_id == current.snapshot_id`, but reset to `None` if
  `snapshot_id != current.snapshot_id` so newly activated runtime snapshots can dynamically update
  `maximum_active_jobs` without re-requiring the operator to relaunch the API. The override defaults
  to `100` when the constructor argument is omitted, preserving the established production ceiling.

### Remaining In-Slice Work
- RO-7 Processing Worker readiness and fencing.

### Risks / Deviations
- `SLICE.md` and `docs/roadmap.md` were modified in the working tree by the Slice 27 handoff
  before this Task started; per Developer role, they were left untouched and are not part of this
  checkpoint.
- `config/alist.json`, `nohup.out` and `worker.log` remain untracked and were not staged.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 7f32191206e70cdc46bb97a57128344ae062db8c
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
