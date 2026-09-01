# Task 24.5 — Reload-Discoverable Exact Execution and Complete Secret-Free Outcomes

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md). It is the one focused correction Task required by A's Slice
Final Review; `SLICE.md` therefore remains in its workflow-defined `FIX REQUIRED` correction state
while this Task is implemented and reviewed.

```text
Task ID: 24.5
Parent Slice: 24 — Files / Media Detail and Manual Organize
Status: READY FOR B REVIEW
Task Base: 818aab87a3e4a102b10ceef9ff1ab036af3d0593
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Correct the RO-6/RO-7 and secret-free safety blockers identified by A so an exact manual execution
retains every selected and unselected item, an authenticated operator can rediscover its durable
authorization/execution and permitted reconciliation after a restart through normal API/Web
journey links, and no new manual Preview/execution persistence or response leaks secret-bearing
operator text or Authorization credentials.

The corrected journey is:

```text
Open a durable intent / Preview or linked manual Task after reload
→ see the complete selected and unselected exact scope
→ follow bounded durable authorization / execution links
→ inspect terminal or interrupted per-item state
→ reconcile ADMITTED/RUNNING work explicitly when permitted
→ observe only bounded, fully redacted evidence
```

This Task does not reopen Tasks 24.1–24.4 or change their accepted behavior beyond the direct root
causes listed in A Final Review.

## Why This Task Exists

A's review of `4ff5479d9f4a81906ee52a9f784931b65cd9ab90..e1ed8c136966885fa2dff88ab5d49ff46f9bcf2c`
found three in-Slice P1 defects:

- when a multi-item Preview authorizes only a subset, the other Previewed item is omitted from both
  the durable execution's `unselectedItemIds` and Operator Web instead of remaining independently
  visible as unselected;
- persisted manual authorizations/executions can be read or reconciled only by an opaque ID already
  known to the caller, so a fresh browser/process cannot navigate from the Preview or linked
  Task/File journey to interrupted work without repository knowledge;
- authorization notes are persisted and returned without secret filtering, and the new redactors
  leave the credential tail of `Authorization: Bearer ...` errors visible.

These defects break one coherent post-Preview execution/result/recovery journey. Correcting only a
field, route, button or test would leave RO-6/RO-7 incomplete, so this Task covers the required
durable relationship, shared projection, API/Web navigation and redaction evidence together.

## Implementation Scope

Implement one vertical correction across:

```text
Domain / bounded projections
→ restart-safe SQLite relationships and queries
→ exact execution application service
→ authenticated versioned API
→ Operator Web reload/navigation/result/reconciliation
→ T4 regression and falsification evidence
```

- Correct exact-execution selection accounting so the durable selected set is exactly the
  authorization scope and the durable unselected set is the complete bounded complement from the
  reviewed Preview/intent. This includes Preview items that were executable but deliberately not
  authorized, as well as items already represented by the Preview as unselected. Selected and
  unselected identities must be disjoint, deterministic, reload-stable and bounded.
- Preserve the existing rule that only selected exact plans create TaskItems, Results, effects,
  locks or OrganizerExecutor calls. Unselected siblings must be visible but must never acquire
  execution authority, mutate Storage, become synthetic Results, or be replayed by execution or
  recovery.
- Add the minimum durable, bounded relationship/query needed to rediscover authorizations and
  executions from normal current journey state after restart. At minimum, the current manual
  Preview/intent journey and the admitted execution's existing Task/TaskItem journey must expose a
  deterministic link to the relevant authorization/execution; terminal and interrupted state must
  remain distinguishable. Do not require a caller to retain, guess or obtain an opaque ID from the
  repository.
- Project those relationships through the shared application behavior and authenticated versioned
  API with bounded ordering/limits, READ permission for read-only discovery, the existing dedicated
  manual-execution permission for execute/reconcile, and no audit, Task, Job, Provider, planning or
  Storage side effect on reads.
- Update Operator Web so a fresh page can navigate from the durable intent/Preview or linked
  manual Task state to the exact authorization/execution, visibly report every selected and
  unselected item, reload terminal outcomes, and offer reconciliation only for the existing
  permitted `ADMITTED`/`RUNNING` states with explicit confirmation. Navigation and refresh must not
  consume authority, replan, invoke OrganizerExecutor or replay mutation.
- Make all new manual-intent/Preview/execution authorization, result, error, audit and relationship
  projections secret-free. Secret-bearing authorization notes must be rejected, omitted, or fully
  redacted before persistence and response; fake credential material must not remain recoverable
  from SQLite. Redaction must consume complete Authorization credential forms, including
  `Authorization: Bearer <credential>`, rather than replacing only the scheme.
- Apply the redaction correction to the directly affected Slice 24 evidence/error helpers so API,
  Web and durable evidence use one equivalent rule. Keep bounded legitimate operator explanations
  and Storage-relative media evidence; do not perform a broad logging subsystem refactor.
- Preserve all existing exact-plan, optimistic-version, one-shot authority, source/destination
  fencing, capability/conflict/destructive-authority, uncertain-effect and OrganizerExecutor-only
  mutation behavior.
- Preserve A's existing uncommitted `SLICE.md` Final Review exactly. Do not change Slice User Goal,
  Required Outcomes, Required Surfaces, Safety Invariants, Explicitly Deferred, Base SHA, current
  `FIX REQUIRED` state, Roadmap or Closure Packet. The Developer checkpoint must not absorb that
  pre-existing A-owned file change.

## Acceptance Criteria

- [ ] Given one intent whose exact Preview contains at least two executable items, authorizing and
      executing only one persists and reloads exactly that item as selected and every other intent/
      Preview item as independently visible unselected. API and Web show the same complete scope.
- [ ] An unselected executable sibling creates no TaskItem, Result, effect, fence or Storage call,
      remains unchanged on disk, and is not replayed by repeated execute, reconciliation or another
      selected item's recovery.
- [ ] After closing and reopening SQLite and creating a fresh API/Web session, an authenticated
      operator can start from the durable manual intent/Preview or linked manual Task/TaskItem,
      discover the current authorization/execution without knowing its UUID, and open the same
      exact reload-stable state.
- [ ] The restart journey covers active authorization, consumed/terminal execution and an injected
      `ADMITTED` or `RUNNING` interruption. Web exposes the existing explicit reconciliation only
      for an admissible interrupted state, and reconciliation releases the fence and records safe
      checkpoint/effect evidence without invoking OrganizerExecutor or replaying mutation.
- [ ] Discovery and relationship collections are bounded, deterministic and permission-aware;
      malformed, duplicate, ambiguous, missing, cross-intent/Preview/Task and over-limit requests
      fail explicitly without widening scope or revealing unrelated work.
- [ ] GET/navigation/reload paths create no audit row, authorization, Task, Job, Result, Provider
      request, plan, lock or Storage mutation and do not expire/consume an otherwise active
      authority merely because it was viewed.
- [ ] A fake secret submitted through the authorization note path is either rejected before
      persistence or irreversibly redacted/omitted. The fake secret is absent from SQLite text,
      application documents, API responses, Web-visible data and audit/error evidence.
- [ ] Preview/execution/evidence errors containing fake forms such as
      `Authorization: Bearer closure-review-secret`, `token=closure-review-secret`, cookies and API
      keys return and persist no credential value or credential tail while retaining a bounded,
      actionable non-secret error.
- [ ] Existing Type C → downstream policy A identity, exact plan fingerprints, one-shot admission,
      RBAC, stale-state rejection, batch independence, conflict/capability/destructive gates,
      Move/Copy/HardLink/SoftLink behavior, attachment/effect persistence and uncertain-mutation
      investigation remain unchanged and pass regression.
- [ ] Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner, Files/detail,
      selection, Preview and discovery perform zero Storage mutation; every permitted mutation still
      reaches Storage only through OrganizerExecutor with no silent fallback/overwrite/delete.
- [ ] All T4 Required Tests pass truthfully, `config/alist.json` remains ignored/untracked/unstaged,
      and the checkpoint contains only this correction and its Developer Completion Report.

## Required Tests

Use only temporary SQLite databases, temporary Local roots and fake/in-memory Providers/Storage.
Do not use production credentials, remote services or user media.

1. Focused exact execution, complete selection, restart discovery, reconciliation and redaction:

   ```bash
   .venv/bin/python -m unittest tests.test_manual_organize_execution
   ```

   Add direct regressions for executable multi-item Preview → authorized subset → reloaded complete
   selected/unselected scope and Web projection; active/consumed/interrupted discovery after closing
   and reopening SQLite through normal API/Web entry points; no-ID reconciliation navigation; GET
   zero-side-effects/RBAC/bounds; and fake-secret absence from SQLite and every returned projection.

2. Directly affected manual journey, File/Task linkage, persistence, checkpoint, API and Web
   regression:

   ```bash
   .venv/bin/python -m unittest \
     tests.test_manual_organize_execution \
     tests.test_manual_organize_preview \
     tests.test_manual_organize_intent \
     tests.test_file_media_detail \
     tests.test_file_catalog \
     tests.test_file_catalog_api \
     tests.test_operator_ui \
     tests.test_processing_checkpoint \
     tests.test_task_persistence \
     tests.test_execution_authorization \
     tests.test_final_integration \
     tests.test_resource_library_pipeline \
     tests.test_migration_rehearsal \
     tests.test_upgrade_preflight
   ```

3. Complete offline regression:

   ```bash
   .venv/bin/python -m unittest discover -s tests
   ```

4. Quality, safety, configuration and private-file gates:

   ```bash
   .venv/bin/ruff format --check .
   .venv/bin/ruff check .
   .venv/bin/python -m compileall -q mediaflow tests scripts
   .venv/bin/python -m pip check
   .venv/bin/mediaflow --config config/strategy.example.json config validate
   .venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
   test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
   git diff --check
   git check-ignore -q config/alist.json
   test -z "$(git ls-files --error-unmatch config/alist.json 2>/dev/null || true)"
   ```

5. Build and isolated installed-wheel smoke because the Task changes durable execution discovery
   and may extend SQLite persistence/query behavior:

   ```bash
   mediaflow_release_dir=$(mktemp -d /tmp/mediaflow-task-24.5-release.XXXXXX)
   .venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w "$mediaflow_release_dir"
   .venv/bin/python scripts/wheel_smoke_test.py "$mediaflow_release_dir"/mediaflow-*.whl
   ```

Before checkpointing, inspect `git status --short`, the complete Task Base..Head diff and exact
manifest. Confirm no deleted/weakened tests, hidden skips, unrelated files, real credentials/private
paths, tracked/staged `config/alist.json`, or A-owned `SLICE.md` change is included in the Developer
checkpoint. Report every gate as `PASS`, `FAIL`, `SKIP`, or `UNAVAILABLE`.

## Non-goals

- Changes to the Slice Contract, Closure Packet, Roadmap, stable requirements or A's Final Review.
- Scheduled unattended execution, automatic crash replay, universal compensation, historical
  rollback, distributed leases, remote Storage setup/probing or Provider switching.
- A free-form path/operation/plan editor, arbitrary Storage command, unbounded history browser or
  new parallel Task/Result/recovery model.
- Reopening unrelated accepted behavior in Tasks 24.1–24.4, general secret-store design, broad log
  subsystem refactoring, wording polish, P2 cleanup or optional proof not required above.
- Defining the next Task or next Slice, or declaring this Slice PASS/CLOSED.

## Developer Completion Report

### Changed Files
- `mediaflow/application/manual_organize_execution.py`
- `mediaflow/application/manual_organize_preview.py`
- `mediaflow/domain/manual_execution.py`
- `mediaflow/domain/manual_organize_preview.py`
- `mediaflow/domain/manual_safety.py`
- `mediaflow/domain/task_persistence.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/interfaces/service_api.py`
- `tests/test_manual_organize_execution.py`
- `tests/test_operator_ui.py`

### Implemented
- Exact execution now records the complete intent complement as unselected while creating
  TaskItems, Results, effects, fences, and Storage calls only for authorized selected items.
- Added bounded, deterministic restart discovery from manual intent/Preview, Task/TaskItem, and
  indexed source journeys, with permission-controlled API projections and linked reconciliation
  only for `ADMITTED`/`RUNNING` executions.
- Added Operator Web projections for durable execution discovery and explicit selected/unselected
  scope, including terminal state reload and interrupted-state reconciliation navigation.
- Made Preview GET/latest/list projections read-only with respect to stale-state publication, and
  made authorization detail reads avoid TTL expiry; read-only journey GETs avoid security-audit
  mutation.
- Centralized manual evidence redaction, rejected credential-shaped authorization notes before
  persistence, and consumed complete `Authorization: Bearer|Basic <credential>` forms without
  altering exact persisted plan fingerprints.

### Tests and Results
- `.venv/bin/python -m unittest tests.test_manual_organize_execution` — PASS (23 tests, 0
  failures).
- `.venv/bin/python -m unittest tests.test_manual_organize_execution tests.test_manual_organize_preview tests.test_manual_organize_intent tests.test_file_media_detail tests.test_file_catalog tests.test_file_catalog_api tests.test_operator_ui tests.test_processing_checkpoint tests.test_task_persistence tests.test_execution_authorization tests.test_final_integration tests.test_resource_library_pipeline tests.test_migration_rehearsal tests.test_upgrade_preflight` — PASS (140 tests, 0 failures).
- `.venv/bin/python -m unittest discover -s tests` — PASS (1001 tests, 0 failures, 7 skipped).
- `.venv/bin/ruff format --check .` — PASS (338 files already formatted).
- `.venv/bin/ruff check .` — PASS.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `.venv/bin/python -m pip check` — PASS (no broken requirements).
- Both required `mediaflow config validate` commands — PASS.
- FFprobe/FFmpeg dependency scan — PASS (no matches).
- `git diff --check` — PASS.
- `git check-ignore -q config/alist.json` and tracked-file check — PASS; the private config remains
  ignored and untracked.
- Wheel build plus `scripts/wheel_smoke_test.py` — PASS (wheel built; migration rehearsal, restore,
  verify, and upgrade preflight all passed on schema 27).

### Decisions
- Discovery is implemented as read-only repository relations with bounded `limit + 1` reads and
  deterministic ordering; the API exposes links from existing authenticated journey surfaces.
- Preview staleness is projected in memory for GET paths so reload does not publish stale state;
  explicit analysis/execute paths retain their existing persistence behavior.
- Plan JSON remains exact in SQLite so the existing plan fingerprint and execution integrity checks
  remain unchanged; redaction is applied to operator-facing documents and non-plan evidence.

### Remaining In-Slice Work
- None known for this Task; the correction checkpoint is ready for B's review.

### Risks / Deviations
- The full suite emitted existing `ResourceWarning` messages for unclosed SQLite connections but
  exited successfully; no new failure or hidden skip was introduced.
- The full suite reported 7 skipped tests; no test was deleted, weakened, or newly skipped by this
  Task. No external service, production credential, or schema migration was required.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 7a0e2e0b44cbe137205161f98d6497fbcd4c50a1
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: NO
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
