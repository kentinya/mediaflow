# Task 23.1 — Durable per-item Processing Checkpoint with stage-aware permitted actions

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 23.1
Parent Slice: 23 — Stage-Aware Per-Item Recovery
Status: READY FOR B REVIEW
Task Base: 5b12ef92ed2720692fb1a1cfc39520d180780588
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Give every persisted media TaskItem a durable, restart-safe **Processing Checkpoint** that
truthfully states where the item stopped, which effects are already durable, which effects are
explicitly uncertain, what is blocking it, and exactly which recovery actions are permitted right
now — readable through the authenticated API and the Operator Web Task detail with zero mutation.

Advances Slice Required Outcomes **RO-1** (durable per-item checkpoint) and **RO-3** (one shared
stage-aware decision that never presents a generic Retry when safety cannot be established), plus
the read half of **RO-6** (API + Operator Web parity of the same facts). It also establishes the
checkpoint version identity that RO-4 admission will later bind to.

This is an implementation unit inside Slice 23, not a smaller Slice: it does not accept or execute
any recovery action.

## Why This Task Exists

Actual gaps found in code, not in documents:

1. **No checkpoint concept exists.** `mediaflow/domain/task_persistence.py` stores `stage` as a
   free-form string, written independently by many services (`pipeline`, `lock`, `scanned`,
   `waiting_confirm`, `strategy`, `paused`, `cancelled`, `completed`, `failed`, `*_resolved`,
   `*_retry_requested`, `ignored_by_operator`). There is no stage contract, no per-item decision,
   and no place that answers "what may I safely do with this item".
2. **Effect certainty is not durable.** `PersistentResultRecord` persists `completed_operations`,
   `cleanup_status` and `cleanup_step_count`, but the rollback outcome is not persisted:
   `mediaflow/application/organizer.py` appends rollback step actions into `completed_operations`
   and only writes `rollback ... failed` into the error text. Today the sole way to distinguish a
   fully rolled-back failure from a genuinely partial mutation is parsing exception text, which
   REQ-RECOVERY-001 / UX-002 forbid and which RO-1 explicitly rules out.
3. **Blockers are per-item in storage but never joined.** `get_recognition_review_for_item`,
   `get_metadata_review_for_item`, `get_metadata_correction_for_item`,
   `get_classification_review_for_item` and conflict confirmations all exist, yet nothing assembles
   them into a single per-item answer; `list_file_review_links` is File-scoped and covers only three
   of the five blocker kinds.
4. **Neither surface shows recovery state.** `GET /api/v1/tasks/{id}` returns raw item and result
   rows; the Operator Web Task detail renders read-only Items/Results tables with no drill-in, no
   blocker link, no effect certainty and no permitted action.
5. `docs/architecture.md` records "Per-item recovery architecture: CURRENT" as not implemented and
   fragmented, which matches items 1–4.

This is the largest reasonable first unit because every remaining Slice 23 outcome must bind to an
exact checkpoint version and to one shared allowed-action decision. Implementing admission or
continuation first would force an ad-hoc version identity and a per-surface duplicate of the
decision, which RO-3 forbids. It is also the safe first unit: it is pure diagnosis with zero
mutation, while still crossing Domain → Persistence → Application → API → Web → Tests, and it
delivers Slice Acceptance Criteria 1–2 on its own (REQ-RECOVERY-006, UX-002, Journey E).

## Implementation Scope

```text
Domain → Persistence (+ forward migration) → Application → API → Web → Tests
```

1. **Domain** — Processing Checkpoint contract and its value objects: a bounded durable stage
   classification derived from `TaskItemStatus` plus the stage strings production code actually
   writes (map them; do not rename or rewrite persisted values); effect certainty
   (`verified_complete` / `attempted_unverified` / `none` / `unknown`); blocker link (kind, id,
   status, existing resolution surface); a stable error-category taxonomy (codes, never parsed
   exception text); a retry-safety verdict; a recovery-action contract (action identity, whether it
   needs confirmation, which authority it would require, which existing journey it targets)
   including an explicit refusal with reason; and the checkpoint version digest.
2. **Persistence** — persist durable effect-certainty evidence (rollback outcome / verified effect
   state) for newly completed executions through the existing completion path; forward-only additive
   migration with a `SCHEMA_VERSION` bump that leaves pre-existing rows at `unknown` and never
   rewrites or fabricates legacy history; one item-scoped consistent bounded read returning the
   item, its Task's pinned configuration identity, its latest and preserved prior results, all five
   blocker kinds, and the existing per-item recovery audit rows. Bounded queries only; no unbounded
   scans.
3. **Application** — a checkpoint projection service built on that single read, plus one shared
   stage-aware recovery-decision function that every surface consumes. Pinned-snapshot availability
   is reported through the existing `RuntimeSnapshotUnavailable` reason codes with zero Storage,
   Provider or media work, and never silently substitutes the current Active configuration. No Task,
   Job, review or Storage write of any kind.
4. **API** — `GET /api/v1/tasks/{taskId}/items/{itemId}` returns the full checkpoint document under
   the existing read permission; the existing `GET /api/v1/tasks/{id}` item rows gain a bounded
   checkpoint summary (durable stage, blocker kind, effect certainty, retry safety, permitted action
   ids, checkpoint version). Unknown ids, an item that does not belong to that Task, and unexpected
   input fail closed using existing error conventions.
5. **Web** — Operator Task detail item rows become a drill-in that renders, from the API document
   only: durable stage, pinned configuration identity and availability, plan/result linkage,
   verified and explicitly uncertain effects, the blocker with a link into its existing resolution
   journey, the error category, the retry-safety statement, and either the permitted action labels
   or the explicit refusal reason. No action submission in this Task. No generic "Retry" label
   anywhere the decision does not establish safety.
6. **Tests** — as specified under Required Tests.

Explicitly frozen in this Task: OrganizerExecutor mutation behavior (other than recording durable
effect-certainty evidence for new results); Recognition, Metadata, Naming, Classification and
Planner policy ownership; `SLICE.md` Contract sections; `docs/roadmap.md`; `docs/progress.md`.

## Acceptance Criteria

- [ ] Every `TaskItemStatus` value and every stage string production code currently writes projects
      a checkpoint carrying durable stage, effect certainty, error category (when failed),
      retry-safety verdict, and either permitted actions or an explicit refusal reason. No status
      raises, returns a placeholder, or falls through to a default "retry".
- [ ] `SUCCESS`, `DRY_RUN`, `SKIPPED` and `IGNORED` items expose no replay action and an explicit
      refusal reason stating why replay is not offered; a generic Retry label is never produced.
- [ ] A `PARTIAL` or otherwise unverified execution reports its known completed operations **and**
      its explicitly uncertain effects, refuses automatic replay, and still offers investigation as
      a valid outcome.
- [ ] Rows written before this Task report effect certainty `unknown` and are never inferred from
      error text, `completed_operations` content or status alone.
- [ ] Each of `WAITING_CONFIRM`, `WAITING_RECOGNITION`, `WAITING_METADATA`,
      `WAITING_METADATA_CORRECTION` and `WAITING_CLASSIFICATION` exposes the blocking review or
      conflict id, its current status, and the existing resolution surface as the stage-appropriate
      next step.
- [ ] The checkpoint reports the parent Task's pinned configuration snapshot id and digest plus
      whether that snapshot is still resolvable, using the existing bounded reason codes; an
      unpinned or unresolvable snapshot is visible as such and is never replaced by the current
      Active configuration.
- [ ] The checkpoint version digest is stable across repeated reads of unchanged durable state and
      changes when item status, stage, attempts, the latest result, or blocker resolution changes.
      It survives a process restart and a fresh repository instance over the same database.
- [ ] `GET /api/v1/tasks/{taskId}/items/{itemId}` and the Task-detail item summary expose the same
      facts as the application projection; the read permission is required, an unauthenticated or
      insufficiently permissioned request is rejected, and unknown ids or a Task/item mismatch fail
      closed without leaking existence details beyond current conventions.
- [ ] Operator Web Task detail shows per-item durable stage, blocker, effect certainty and retry
      safety and opens the full checkpoint; all rendered evidence and action labels come from the
      API document rather than being recomputed in the browser.
- [ ] Reading a checkpoint through application, API and Web performs zero Storage operations, zero
      metadata Provider requests, and creates zero Tasks, Jobs, reviews, locks or Result rows.
- [ ] The new durable effect-certainty evidence is written by the existing completion path for new
      executions; a database created before this Task migrates forward with all prior rows
      preserved, and a database already at the new version still opens. `tests/test_api_security.py`
      schema expectation is updated to the new version while keeping its migrate-from-old-version
      assertion.
- [ ] A `RecognitionType C` item using NamingPolicy A and ClassificationPolicy A still reports
      RecognitionType C in its checkpoint.
- [ ] No secret, token, credential, authorization header, cookie, private endpoint, absolute
      user-private path or raw exception text appears in the checkpoint document or in logs.
- [ ] Test Level T4 passes with actual recorded evidence.
- [ ] The checkpoint contains only this Task and is coherent and reviewable.

## Required Tests

Focused (new):

- `python -m unittest tests.test_processing_checkpoint` — domain contract and application projection
  across all statuses and production stage strings, effect-certainty combinations, legacy `unknown`,
  blocker linkage for all five kinds, refusal reasons, version digest stability/change,
  pinned-snapshot reporting, RecognitionType C preservation, and the zero-mutation falsification
  test using strict Storage/Provider/repository spies.

Related (extend existing suites, do not weaken existing assertions):

- persistence/migration coverage for the additive column(s), forward migration from a pre-existing
  database, preserved prior results, and bounded item-scoped read.
- API coverage for the new endpoint and the extended Task-detail item rows: success, permissions,
  unauthenticated rejection, unknown ids, Task/item mismatch, and payload boundedness.
- Operator Web coverage asserting the item drill-in renders stage, blocker link, effect certainty,
  retry-safety statement and permitted actions / refusal from the API document.
- `tests/test_api_security.py` schema-version expectation updated for the bump.

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

- Accepting, admitting or persisting a recovery request, including version-bound admission,
  authority validation and audit (next Task in this Slice).
- Executing a continuation, re-entering the pipeline, or producing a new linked Result (later Task).
- Bounded batch recovery, sibling independence and parent/continuation summary reconciliation (later
  Task).
- The Files/Media manual-organize journey, Metadata Provider switching, and scheduled unattended
  real organization (Slices 24 and 25, explicitly deferred).
- Automatic replay or compensation of uncertain mutations, historical cross-run rollback, and
  distributed Task leases (explicitly deferred).
- Any change to Required Outcomes, Required Surfaces, Safety Invariants, the Slice Base, `SLICE.md`
  Contract sections, `docs/roadmap.md` or `docs/progress.md`.
- Refactors, copy polish or P2 cleanup not required by these Acceptance Criteria.

## Developer Completion Report

### Changed Files
- `mediaflow/domain/processing_checkpoint.py`
- `mediaflow/application/processing_checkpoint.py`
- `mediaflow/domain/task_persistence.py`
- `mediaflow/application/task_runtime.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/infrastructure/sqlite_file_index.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_processing_checkpoint.py`
- schema-version expectations in the affected persistence/API/configuration test modules

### Implemented
- Added a bounded, read-only Processing Checkpoint domain contract and shared application
  projection with durable stage, effect certainty, blocker/audit links, error category,
  retry-safety decision, permitted actions/refusal, pinned configuration identity, and a stable
  version digest.
- Added schema-23 additive effect-certainty evidence and bounded item-scoped SQLite context reads;
  legacy result rows remain `unknown`, while new completion results record verified, unverified,
  or no-effect evidence without parsing error text.
- Exposed the projection through authenticated `GET /api/v1/tasks/{taskId}/items/{itemId}` and
  bounded Task-detail summaries, including fail-closed Task/item matching and review detail links.
- Added a read-only Operator Web Task-item drill-in that renders only API-provided checkpoint facts
  and action/refusal information; no recovery mutation is submitted.
- Preserved RecognitionType C identity, OrganizerExecutor mutation boundaries, pinned snapshot
  semantics, and secret/path redaction.

### Tests and Results
- `.venv/bin/python -m unittest tests.test_processing_checkpoint` — PASS (9 tests).
- `.venv/bin/python -m unittest discover -s tests` — PASS (883 tests, 7 skipped).
- `.venv/bin/ruff format --check .` — PASS.
- `.venv/bin/ruff check .` — PASS.
- `python3 -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS.
- `mediaflow --config config/strategy.example.json config validate` — PASS.
- `mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- ffprobe/ffmpeg repository audit — PASS (no production/test/script references).
- `git diff --check` — PASS.

### Decisions
- Effect certainty is persisted only by the existing completion path; legacy rows are never
  inferred from status, operation text, or exception text.
- Unknown/uncertain effects and unavailable or unvalidated pinned snapshots fail closed to
  investigation/refusal; only explicitly verified pre-mutation failures can expose a safe retry.
- API/Web reads use one bounded repository projection and do not refresh or substitute Active
  configuration on the checkpoint path.
- Absolute/private paths and unbounded/raw exception evidence are redacted from the checkpoint
  document; blocker links target existing read/resolution surfaces.

### Remaining In-Slice Work
- Recovery admission/continuation, version-bound authority checks, and bounded batch recovery remain
  outside this Task and are not implemented here.

### Risks / Deviations
- The system interpreter lacks the optional `httpx` dependency, so its full-suite attempt was
  unavailable/failed for that pre-existing environment condition; the project `.venv` (with the
  optional dependency) passed the complete suite.
- The suite reported 7 existing skips; no external Storage, Provider, credentials, or user media
  were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: df8c9dc550177f2715c847bd1e497c5f0423bc66
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
