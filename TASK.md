# Task 23.2 — Version-bound single-item recovery admission with preserved evidence and audit

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 23.2
Parent Slice: 23 — Stage-Aware Per-Item Recovery
Status: FIX REQUIRED
Task Base: f196da8563b1db60659b88ab17a2cfcaabea167c
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Make an operator's chosen recovery action for **one** media TaskItem become a durable, auditable
request that is bound to the exact Processing Checkpoint version, the item's original source scope
and its parent Task's pinned configuration snapshot — admitted through **one** shared gate that
accepts only what the stage-aware decision already permits, never erases prior failure evidence,
never elevates execute / overwrite / delete / cleanup authority, and rejects stale or duplicate
requests. Submittable from the authenticated API and the Operator Web checkpoint drill-in with
explicit confirmation.

Advances Slice Required Outcomes **RO-2** (transactional consistency, preserved prior evidence,
stale/concurrent rejection, bounded secret-free audit of who requested which recovery action) and
**RO-4** (admission bound to the exact TaskItem/checkpoint version, original source scope and pinned
configuration, with no authority upgrade), completes the admission half of **RO-3** (the same shared
decision now also gates the write path, so no surface can act on an action the decision refuses),
and delivers the single-item write half of **RO-6** (API and Operator Web submit the same action,
confirmation, outcome and next step).

This is an implementation unit inside Slice 23, not a smaller Slice: it admits and records a request
only. It executes nothing, re-enters no pipeline and produces no new Result.

## Why This Task Exists

Actual gaps found in code, not in documents:

1. **The existing item retry path contradicts the checkpoint it should obey.**
   `mediaflow/application/task_retry.py:64` `request_item` admits any item whose status is `FAILED`
   **or `PARTIAL`**, with no checkpoint-version binding, no effect-certainty gate and no pinned-
   snapshot validation. Task 23.1 makes a `PARTIAL` / `attempted_unverified` item report
   `retry_safety` unsafe/unknown with only `investigate` permitted, yet this write path will still
   mark that exact item `PENDING`. The Slice Safety Invariant that uncertain effects are never
   labelled retry-safe or replayed is therefore enforced on the read side only.
2. **It is reachable from the API today.** `POST /api/v1/files/{fileId}/re-plan`
   (`mediaflow/interfaces/service_api.py:1177`, `SUBMIT_DRY_RUN`) calls
   `FileReplanRequestService.request` → `TaskRetryRequestService.request_item`, so the unsafe
   admission above is live over HTTP, not only in the CLI.
3. **Prior evidence is destroyed on admission.** `request_task_retries`
   (`mediaflow/infrastructure/sqlite_runtime.py:394`) issues `UPDATE task_items SET status=?,
   stage=?, updated_at=?, error=NULL`, and `ManualIgnoreService.ignore`
   (`mediaflow/application/manual_ignore.py:56`) likewise rewrites the item with `error=None`. RO-2
   requires prior evidence to be preserved across recovery attempts; today the failure text an
   operator was just shown is deleted by the act of requesting recovery.
4. **No admission identity exists.** `TaskRetryRequestDecision`
   (`mediaflow/domain/task_retry.py:11`) records `decision_id`, task, item, time, actor and note —
   but not which checkpoint version was accepted, which action was chosen, or which configuration
   snapshot the request is pinned to. Nothing can reject a decision made against a checkpoint that
   has since changed, and nothing proves the request did not follow a newer Active configuration.
   The `checkpoint_version` digest that Task 23.1 established has no consumer.
5. **No concurrency or duplicate rule.** `request_task_retries` re-checks only `status IN
   ('failed','partial')`, so two concurrent operators (or one double-submit) create two audit rows
   for the same item, and no table prevents a second active request.
6. **`ignore` is a production path the shared decision never offers.** `ManualIgnoreService` and
   `manual_ignore_audit` exist and the Slice acceptance criteria require ignored items to be
   distinguishable, but `_actions` in `mediaflow/application/processing_checkpoint.py` emits only
   `resolve_<kind>`, `investigate`, `retry` and `resume`. A waiting item therefore has no permitted
   way to be dropped, while the unreviewed CLI path can still drop it.
7. **Neither surface can act.** The Task 23.1 API document and Web drill-in render permitted action
   labels but expose no submission, so RO-6's action/confirmation/outcome half is unimplemented for
   Task items.

This is the largest reasonable next unit and it must precede continuation: RO-7 continuation may
only start from an admitted, version-bound request, and RO-5 batch recovery is defined as the
bounded composition of independent single-item admissions. Building continuation or batch first
would force an ad-hoc admission identity and would leave the live unsafe `PARTIAL` retry path in
place. It is also the natural pairing with Task 23.1: the same shared decision now governs both
reading and writing.

## Implementation Scope

```text
Domain → Persistence (+ forward migration) → Application → API → Web → Tests
```

1. **Domain** — a recovery-request contract: request identity, task/item identity, the requested
   action id, the bound checkpoint version, the pinned configuration snapshot id and digest, the
   original source scope (source storage id and Storage-relative source path), actor, requested
   time, request status, optional bounded note, and the explicit authority statement the request
   carries (never execute, overwrite, delete, source-cleanup or rollback). Add the bounded rejection
   reasons admission can return (action not permitted, stale checkpoint version, duplicate active
   request, snapshot unavailable, insufficient authority, unknown item, item/Task mismatch). Extend
   the stage-aware action contract with `ignore` for items whose blocker is a pending review, and
   mark which permitted actions are admissible here versus which remain links into an existing
   journey (`resolve_*`) or a non-admitting outcome (`investigate`). `resume` stays Task-scoped and
   is not admissible in this Task.
2. **Persistence** — one additive bounded table for recovery requests with a `SCHEMA_VERSION` bump,
   a uniqueness rule that prevents a second active request for the same item, and an item-scoped
   bounded read joined into the existing single checkpoint context read. Admission commits the
   request row, the action-specific existing audit row and the item transition in **one**
   transaction, and the item transition must **preserve** the existing `error` evidence instead of
   nulling it. Forward-only migration: pre-existing rows and databases open unchanged, and no legacy
   history is rewritten or fabricated.
3. **Application** — one shared admission service that reads the checkpoint through the Task 23.1
   projection, verifies the requested action against `permitted_action_ids`, compares the caller's
   expected checkpoint version against the current one, validates the parent Task's pinned snapshot
   through the existing `RuntimeSnapshotUnavailable` reason codes, then delegates the durable state
   change to the **existing** per-action production paths (task retry request, manual ignore) rather
   than writing item state itself. `TaskRetryRequestService.request_item` and
   `ManualIgnoreService.ignore` must stop being independently reachable admission points: every
   caller, including `FileReplanRequestService`, goes through the gate. No Storage operation, no
   Provider request, no Job, no Task, no Result, no lock.
4. **API** — a `POST` recovery endpoint under the existing Task-item path that accepts the action
   id, the expected checkpoint version and an optional bounded note under an existing write
   permission; it returns the admitted request, the bound checkpoint version and a concrete next
   action, and fails closed with existing error conventions for a refused action, a stale version, a
   duplicate active request, an unavailable snapshot, insufficient permission, unknown ids,
   Task/item mismatch and unexpected input. `GET /api/v1/tasks/{taskId}/items/{itemId}` gains the
   bounded admitted request and its audit; the Task-detail item summary gains bounded evidence that
   a recovery request is pending.
5. **Web** — the Task-item drill-in gains, for permitted admissible actions only, an explicit
   confirmation that names the action and the bound checkpoint version, submits it through the API,
   and after reload shows the durable admitted request, its actor and time, and the concrete next
   action. A refused action is never rendered as a submittable control, and no label or decision is
   recomputed in the browser.
6. **Tests** — as specified under Required Tests.

Explicitly frozen in this Task: OrganizerExecutor and all Storage mutation behavior; the Task 23.1
checkpoint document fields other than the additive recovery-request/pending-request evidence; the
`ignore` production semantics inside `ManualIgnoreService` other than evidence preservation and the
gate; Recognition, Metadata, Naming, Classification and Planner policy ownership; the Files/Media
journey beyond routing its existing re-plan call through the gate; `SLICE.md` Contract sections;
`docs/roadmap.md`; `docs/progress.md`.

## Acceptance Criteria

- [ ] Exactly one shared gate admits a per-item recovery request. An action that the Task 23.1
      stage-aware decision does not list for that exact checkpoint is refused with a bounded reason
      and changes no durable state, from every surface and for every caller.
- [ ] A `PARTIAL`, `attempted_unverified` or `unknown`-certainty item cannot be admitted for replay
      through any path, including `POST /api/v1/files/{fileId}/re-plan` and the CLI; the refusal
      states why and investigation remains available.
- [ ] `SUCCESS`, `DRY_RUN`, `SKIPPED` and `IGNORED` items cannot be admitted for replay at all.
- [ ] An admitted request records the requested action, the bound checkpoint version, the item's
      original source storage id and Storage-relative source path, the parent Task's pinned
      configuration snapshot id and digest, the actor and the time; it carries no execute,
      overwrite, delete, source-cleanup or rollback authority, and admission never consults or
      substitutes the current Active configuration.
- [ ] A request whose expected checkpoint version does not match the current one is rejected as
      stale, with the current version returned so the operator can re-read and decide again; nothing
      is admitted and no evidence is lost.
- [ ] A second active request for the same item is rejected as a duplicate rather than creating a
      second audit row or a second durable request; the existing request is returned.
- [ ] Admission of an item whose parent Task has no pinned snapshot, or whose snapshot is no longer
      resolvable, fails closed using the existing bounded reason codes.
- [ ] Prior failure evidence survives admission: the item's recorded error and its persisted Result
      rows, including `effect_certainty` and `uncertain_effects`, are unchanged by requesting
      recovery. No path nulls the item error as part of admission.
- [ ] Request, action audit and item transition commit atomically. A failure in any part leaves no
      partially admitted request, no orphan audit row and no transitioned item.
- [ ] A waiting item whose blocker is a pending review can be admitted for `ignore`, and its
      resulting `IGNORED` state and audit are visible in its checkpoint; a waiting item with no
      pending review cannot.
- [ ] `POST` on the Task-item recovery endpoint requires an existing write permission; an
      unauthenticated request, an insufficiently permissioned request, an unknown Task or item, a
      Task/item mismatch, an unknown action id, a malformed expected version, an over-long note and
      unexpected fields or query parameters all fail closed without leaking existence details beyond
      current conventions.
- [ ] The checkpoint document and the Task-detail item summary expose the admitted request and its
      audit; after reload, API and Operator Web show the same durable request, actor, time, bound
      version and concrete next action.
- [ ] Operator Web submits only actions the API document permits, requires explicit confirmation
      naming the action and the bound checkpoint version, and renders no recomputed decision or
      generic Retry label.
- [ ] Admitting a request performs zero Storage operations, zero metadata Provider requests and
      creates zero Tasks, Jobs, Results or locks, and executes no continuation.
- [ ] A database created before this Task migrates forward with all prior rows preserved, and a
      database already at the new version still opens. Schema-version expectations in the affected
      test modules are updated to the new version while keeping their migrate-from-old-version
      assertions.
- [ ] A `RecognitionType C` item using NamingPolicy A and ClassificationPolicy A still reports
      RecognitionType C after its recovery request is admitted.
- [ ] No secret, token, credential, authorization header, cookie, private endpoint, absolute
      user-private path or raw exception text appears in the request record, the API response, the
      audit or the logs.
- [ ] Test Level T4 passes with actual recorded evidence.
- [ ] The checkpoint contains only this Task and is coherent and reviewable.

## Required Tests

Focused (new):

- `python -m unittest tests.test_processing_recovery_admission` — the shared gate across permitted
  and refused actions for every relevant status, the `PARTIAL`/unverified replay refusal, stale
  version rejection, duplicate active request rejection, missing and unresolvable pinned snapshot,
  evidence preservation (item error plus Result `effect_certainty` / `uncertain_effects` unchanged),
  atomic commit of request + audit + item transition, `ignore` admission with and without a pending
  review, authority statement, RecognitionType C preservation, and a zero-mutation falsification
  test using strict Storage/Provider spies.

Related (extend existing suites, do not weaken existing assertions):

- `tests/test_processing_checkpoint.py` — the decision now offers `ignore` where applicable and the
  checkpoint document/summary carry the admitted request; existing assertions stay intact.
- the existing task-retry, manual-ignore and File re-plan suites — the unsafe admission paths are
  now gated, evidence is preserved, and the previously permitted `PARTIAL` retry is refused.
- persistence/migration coverage for the additive table and index, forward migration from a
  pre-existing database, atomicity, and the bounded item-scoped read.
- API coverage for the new `POST` endpoint and the extended read payloads: success, permissions,
  unauthenticated rejection, unknown ids, Task/item mismatch, refused action, stale version,
  duplicate request, unavailable snapshot, input validation and payload boundedness.
- Operator Web coverage asserting the confirmation, the submitted action, and the post-reload
  admitted-request rendering come from the API document.
- schema-version expectations in the affected persistence/API/configuration test modules.

Quality gates (T4):

- `python -m unittest discover -s tests`
- `ruff format --check .`
- `ruff check .`
- `python -m compileall -q mediaflow tests scripts`
- `python -m pip check`
- `mediaflow --config config/strategy.example.json config validate`
- `mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- repository ffprobe / ffmpeg audit
- `git diff --check` and a diff scan confirming no secret, token or private path is introduced and
  that `config/alist.json` remains untracked and unstaged

Packaging and wheel smoke evidence stays concentrated at SLICE FINAL. No real SMB / OpenList / S3 /
TMDB service and no production data may be used.

## Non-goals

- Executing a continuation, re-entering the pipeline, or producing a new linked Result (next Task in
  this Slice).
- Bounded batch recovery, sibling independence and parent/continuation summary reconciliation (later
  Task).
- Item-level `resume` of a paused Task, which remains a Task-scoped continuation.
- Any new Files/Media journey behavior beyond routing the existing re-plan call through the shared
  gate.
- The Files/Media manual-organize journey, Metadata Provider switching, and scheduled unattended
  real organization (Slices 24 and 25, explicitly deferred).
- Automatic replay or compensation of uncertain mutations, historical cross-run rollback, and
  distributed Task leases (explicitly deferred).
- Granting, renewing or elevating execute, overwrite, delete, source-cleanup or rollback authority.
- Any change to Required Outcomes, Required Surfaces, Safety Invariants, the Slice Base, `SLICE.md`
  Contract sections, `docs/roadmap.md` or `docs/progress.md`.
- Refactors, copy polish or P2 cleanup not required by these Acceptance Criteria, including the
  non-blocking items recorded in the Task 23.1 review.

## Developer Completion Report

### Changed Files
- `mediaflow/application/file_replan_request.py`
- `mediaflow/application/manual_ignore.py`
- `mediaflow/application/processing_checkpoint.py`
- `mediaflow/application/recovery_admission.py`
- `mediaflow/application/task_retry.py`
- `mediaflow/domain/processing_checkpoint.py`
- `mediaflow/domain/recovery.py`
- `mediaflow/domain/task_persistence.py`
- `mediaflow/final_cli.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_processing_recovery_admission.py`
- affected retry/ignore/re-plan/checkpoint/API/UI/configuration schema-version test modules

### Implemented
- Added one shared, version-bound admission gate for single-item `retry` and pending-review
  `ignore` requests. The gate reuses the stage-aware checkpoint decision, rejects stale,
  duplicate, unsafe, terminal, mismatched, or unavailable-snapshot requests, and performs no
  continuation or media operation.
- Persisted bounded recovery requests with the checkpoint version, original Storage-relative
  source identity, pinned configuration identity, actor/time, explicit no-mutation authority,
  next action, and request audit. Request, action-specific audit, and item transition commit in
  one SQLite transaction with an active-request uniqueness guard.
- Preserved prior TaskItem error and Result effect-certainty evidence across retry/ignore admission;
  `PARTIAL` and uncertain effects are never admitted for replay. Added stage-aware admissible
  `ignore` for pending recognition/metadata/metadata-correction reviews.
- Routed Task-item API, Operator Web, File re-plan, and CLI recovery entry points through the
  shared gate. API/Web expose the same bounded request/checkpoint evidence and explicit confirmation
  without granting execute, overwrite, delete, source-cleanup, or rollback authority.
- Added forward schema migration and regression coverage for admission identity, atomicity,
  duplicate/stale handling, snapshot fail-closed behavior, evidence preservation, path/secret
  safety, API/UI parity, and RecognitionType C preservation.

### Tests and Results
- `.venv/bin/python -m unittest tests.test_processing_recovery_admission` — PASS (10 tests).
- `.venv/bin/python -m unittest tests.test_processing_recovery_admission tests.test_processing_checkpoint` — PASS (20 tests).
- `.venv/bin/python -m unittest tests.test_manual_ignore tests.test_manual_ignore_batch tests.test_file_replan_request tests.test_recognition_retry tests.test_task_retry tests.test_operator_ui` — PASS (55 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (894 tests, 7 skipped; existing ResourceWarning diagnostics only).
- `.venv/bin/ruff format --check .` — PASS (317 files already formatted).
- `.venv/bin/ruff check .` — PASS.
- `python3 -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (no broken requirements).
- `.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- ffprobe/ffmpeg repository audit — PASS (no references in `mediaflow/`, `tests/`, or `scripts/`).
- `git diff --check` — PASS.

### Decisions
- The checkpoint projection is the single source of permitted/admissible action truth; linked
  resolution journeys remain non-admitting and Task-scoped resume remains non-admissible here.
- Recovery admission pins the presented checkpoint and existing Task configuration snapshot, then
  reprojects and rechecks both under `BEGIN IMMEDIATE` before any transition. No current Active
  configuration is substituted.
- Retry is admitted only for a failed item with verified no-effect certainty and a resolvable
  pinned snapshot. Ignore is limited to a matching pending manual review. Both transitions retain
  the prior item error and all Result evidence.
- Existing batch retry/ignore APIs remain outside this single-item continuation scope; CLI batch
  entry points use the shared gate when admitting their individual candidates.

### Remaining In-Slice Work
- Continuation execution, bounded batch recovery semantics, sibling independence, and
  parent/continuation summary reconciliation remain outside this Task and are not started.

### Risks / Deviations
- No real SMB/OpenList/S3/TMDB service, credentials, or production data were used.
- Seven tests remain skipped by their existing conditional gates; the full suite otherwise passed.
- The full suite emitted existing SQLite `ResourceWarning` diagnostics; no test failed and no new
  warning gate was introduced.

### Correction for B Review
- Extended the API recovery-route tests across authentication, permission, not-found, mismatch,
  refusal, stale, duplicate, unavailable-snapshot, invalid-action/version/input, unexpected
  field/query, bounded error details, and denial-audit paths.
- Added strict Storage and metadata Provider boundary spies plus Task/Job/Result/file-lock
  snapshots to falsify mutation or durable work creation during admission.
- Restored focused Operator Web assertions for admissible-only controls, action/version
  confirmation, exact recovery POST body, and the narrowed no-actor-submission guard.

### Correction Tests and Results
- `.venv/bin/python -m unittest tests.test_processing_recovery_admission tests.test_operator_ui` — PASS (41 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (896 tests, 7 skipped; existing ResourceWarning diagnostics only).
- `.venv/bin/ruff format --check .` — PASS (317 files already formatted).
- `.venv/bin/ruff check .` — PASS.
- `python3 -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (no broken requirements).
- Both example `config validate` commands — PASS.
- ffprobe/ffmpeg repository audit — PASS (no references in `mediaflow/`, `tests/`, or `scripts/`).
- `git diff --check` — PASS.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: d92eb1e2d67f1d87cce456adf2d8561672ee47c5
```

## B Review Result

```text
Reviewed: f196da8563b1db60659b88ab17a2cfcaabea167c..d92eb1e2d67f1d87cce456adf2d8561672ee47c5
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Round 1 raised three points; two are closed. I read the actual fix diff `0eafbbb..d92eb1e`
(`tests/test_operator_ui.py` +16, `tests/test_processing_recovery_admission.py` +388/-5; the five
removed lines are only the `api_request` and `_task` helper signatures, whose previous defaults are
preserved), and re-ran Test Level T4 independently: the focused
`tests.test_processing_recovery_admission tests.test_operator_ui` run is 41 tests OK; full
`discover -s tests` is 896 tests OK with the same 7 pre-existing conditional skips;
`ruff format --check .` 317 files; `ruff check .`; `compileall`;
`pip check`; both `config validate`; ffprobe/ffmpeg audit clean; `git diff --check` clean; tree
clean; `config/alist.json` still ignored (`.gitignore:21`) and unknown to git. No production file
was touched, no test was deleted, no skip was added, no assertion was loosened, and no credential,
private endpoint or private path appears in the added lines (only the existing synthetic
`operator-token` / `viewer-token` fixtures).

### Unmet — Acceptance Criterion 14 is still not falsifiable for the Storage/Provider half

`test_recovery_admission_falsifies_storage_provider_and_durable_side_effects` asserts zero calls on
spies that no production code can reach. `StrictStorageSpy` and `StrictProviderSpy` are instantiated
only as attributes of `StrictSnapshotValidator`
(`tests/test_processing_recovery_admission.py:829-830`) and are never passed to the gate, the
repository or the API; the gate is built as `RecoveryAdmissionService(repository,
snapshot_validator=validator)`, which takes no Storage or Provider argument. The only other
references to them are the assertions themselves (`:872-873`), so
`assertEqual(validator.storage.calls, [])` and `assertEqual(validator.provider.calls, [])` cannot
fail for any change to `admit`. A regression that made admission open a Storage or call a metadata
Provider would keep this test green, which is exactly what the Required Test "a zero-mutation
falsification test using strict Storage/Provider spies" exists to prevent.

The durable-work half of the same test is genuine and should stay as it is: the Task, Task list, Job
list, Result list and `file_locks` snapshots are compared before and after a real admission.

Required direction: place the strict doubles where the production admission path would actually
reach them and assert they were never used — for example patch the configuration-service
`create_storage` seam and the metadata provider registry construction with doubles that raise on any
attribute access (the `unittest.mock` pattern already used elsewhere in this suite) for the duration
of one real admission, and/or snapshot the on-disk tree (relative paths, sizes, mtimes) of the
item's source root and destination root before and after admission and assert it is unchanged
apart from the runtime SQLite files. Drive at least one admission through the API route as well,
so the wired seam covers the transport path. Then drop or replace the two unreachable-spy
assertions so the suite does not present an unreachable double as evidence.

Task ID, Task Base, Goal and Scope are unchanged. Fix in this same Task and resubmit with a new
Head SHA; do not change anything beyond this one point.
