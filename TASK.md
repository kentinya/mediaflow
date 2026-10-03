# Task 42.4 — Native controls and safe queued paused-scope continuation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 42.4
Parent Slice: 42
Status: PLANNED
Task Base: d52ce9299671ab05141f64848b8475cd4db11126
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice RO-5 and its RO-2/RO-7 control, continuation-history and failure integration:
from the selected native task-center run, an operator requests supported Pause/Cancel, observes the
actual cooperative outcome, and uses native Continue for the exact remaining scope of supported
safely paused asynchronous operator work. Durable queued continuation runs through the resident
Worker, preserves the original immutable pin and item history, and never repeats terminal success
or uncertain mutation or obtains execution authority from a stored boolean.

## Why This Task Exists

At Task Base, `OperationsLanding.tsx` renders the unified run/detail/records and new-task journey,
but its selected panel does not expose lifecycle controls. Legacy `TaskDetailPage.tsx` and
`api-client.ts` already consume backend lifecycle actions and exact optimistic versions.
`operations_lifecycle.py` advertises cooperative operator-workflow Pause/Cancel, yet generic Resume
is withheld with a CLI next action. `/api/v1/tasks/{id}/resume` requeues only the two existing Files
transfer command families; other paused operator workflows have no durable queued continuation.
`final_cli.py`'s `_continue_paused_scope` shows existing processing behavior, but calling a CLI from
HTTP or copying its `execute_authorized` check would not satisfy this Slice's authority boundary.

The coherent unit is the entire selected-run control → observed stop → safe queued Continue →
linked remaining outcome journey, including execution-authority refusal/re-Preview and restart.
Reuse existing lifecycle, checkpoints, pin resolution, queue, Worker, Storage and Executor ports.
No new task engine, generic workflow framework or unrelated recovery workspace is needed.

Previous Task 42.3 B review:

```text
Reviewed: c55bb3cef6efa8b51158831f4136d7bc3d5fd490..c0559eba2585fc6cd5650e21e24b3125f7526e01; completion report at d52ce9299671ab05141f64848b8475cd4db11126
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

The original default-entry/empty-auth P1 was resolved in one correction round; both original legal
real API/Local Storage/Worker repros now pass with one Execute and exact selected Task linkage.
Independent B: Python full 2119 (2112 passed / 7 explicit skips), focused 103/114/176 and safety 19;
Web focused 659, final full 952, real Python browser 14, Files browser 40; quality/config/wheel,
governance/whitespace/private/reference checks passed. Preserve the first full Web 951/1 heading-wait
failure and unchanged rerun. Fake browser remains 66/2, the same clean-Base-proven deep-link failures.
Docker health wait failed in two current attempts and independently on the immutable Task Base
image, with the unchanged 3-second probes timing out; this unrelated baseline gate is FAIL, never
PASS. No assertions/timeouts were changed. All Developer and B intermediate failures are retained.
Full previous Task/report/PASS record: `/tmp/mediaflow-b-task42-3-r2-pass.md`; B logs and evidence:
`/tmp/mediaflow-b42-3-r2-*`. Git preserves the Developer report at the explicit report SHA.

Immediately after PASS B reevaluated RO-1–RO-7 against actual code: inventory/read/navigation,
queries/history, detail/evidence/export and RO-4 admission/return are delivered; RO-5 native controls/
safe queued Continue and RO-6 native decisions/failed-analysis recovery remain. RO-7's controls/
recovery integration remains with those outcomes. There is no pending Contract issue. Slice remains
ACTIVE; no Slice Final is appropriate yet. This is the fourth coherent Task, not a field/test Task.


## Implementation Scope

```text
Existing lifecycle/checkpoint/authority semantics → atomic durable queued continuation and links
→ shared Application/API/Worker behavior → native selected-run controls/return/re-Preview → Tests
```

### Operator journey

- **Entry:** selected `操作与任务` run, including supported Task/Job deep links, a waiting queue
  admission and existing Files transfer links.
- **Visible state:** backend-advertised available/unavailable actions; queued/running, requested
  Pause/Cancel versus observed stopping; completed effects, independent remaining items, pin/Worker
  blockers and original/continuation history. Explain unavailable controls in bounded Chinese copy.
- **Action:** deliberately request Pause/Cancel or Continue when allowed. Ask for explicit execution
  intent only when authority or a changed exact plan requires it; no raw IDs/tokens or CLI ceremony.
- **Success:** control targets the actual owner; a safe Continue promptly admits exactly the remaining
  bounded work for Worker pickup. Its progress/results and source run/item links survive restart.
- **Failure:** stale version, duplicate/concurrent control, permission change, lost Worker, missing
  pin/dependency/secret, changed source/capability/plan, insufficient/revoked authority and unknown
  response remain distinct. Nothing claims an in-flight call was interrupted or effects undone.
- **Recovery:** read exact durable owner/admission state before another explicit command; repair
  the named prerequisite; preserve safe input/history; use native exact Preview and fresh explicit
  execution intent if required. Unknown media effects stay investigation-only.

### Required behavior and boundaries

1. Compose controls for the exact unified run through existing durable Job/Task/manual-execution
   links and the actual execution owner. Render backend actions and reasons in the selected panel;
   no generic status-based authority or command guessed from a label. Pre-Task cancellation, linked
   Task controls, terminal work and historical unsupported paths retain truthful behavior.
2. Revalidate current RBAC, exact owner/state, optimistic version and relevant scope at submission.
   Protect duplicate/concurrent Pause/Cancel/Continue atomically; commands send once. Reconcile
   transport/5xx/malformed/lost responses from exact durable state before enabling another command.
   Acceptance of a request is not acknowledgement of stopping, completion or rollback.
3. Implement the missing bounded durable queued Continue boundary for current supported safely
   paused async operator workflows which offer Pause, using existing processing/checkpoint and
   Worker ports. Audit the legal Task-Base command/execution paths and record the supported matrix
   in the completion report. Preserve both ResourceLibrary and MediaLibrary Files transfer Resume.
   Legacy/synchronous paths lacking safe durable evidence show the real reason/next action; do not
   remove current Pause capability to avoid delivering Continue for a supported async path.
4. Continue binds the original pin and exact remaining admitted scope, command, source identities,
   limits and independent item checkpoints. Discovery/continuation never broadens the original
   admitted scope/limits. No current Active repin, resetting all statuses, replay of successful/
   ignored terminal siblings or uncertain effects.
   For a partially discovered scoped scan, preserve its original bounded discovery contract and
   checkpoint/limit, rather than interpreting current configuration as new admission authority.
   Known partial effects proceed only where the existing gate proves the exact next operation safe.
5. Revalidate live source, capability, applicable current permissions and execution authority both
   at admission and before mutation. Preserve one-shot consumption and unattended-grant revocation;
   `execute_authorized` alone cannot authorize Continue. Use existing durable authority for legally
   permitted remaining work. A changed plan or insufficient authority leads through native exact
   Preview and meaningful fresh explicit intent for only the eligible remaining scope, preserving
   the historical pin and return run. Decision/retry forms from RO-6 are outside this Task.
6. HTTP only coordinates/admit/reads; the resident Worker claims queued continuation under existing
   locks/leases/fences and invokes the existing pipeline/OrganizerExecutor. Preserve stale-claim
   refusal, slow-call heartbeat, cancellation ownership, startup without Active and pin reconstruction.
   No shell subprocess, long synchronous continuation or automatic uncertain-mutation replay.
7. Reuse current repositories and explicit links; a minimal additive admission/link/authority record
   is allowed only where needed for this exact continuation boundary. Original history and per-item
   Results remain inspectable; unified inventory counts each run once and links attempts truthfully.
   Do not create a parallel queue, shadow Task lifecycle or replace existing runtime authority.
8. Preserve task-center filters/run/detail, browser back/history, narrow-screen/keyboard/focus and
   memory-only auth continuation. Clear forms/caches across principals. Existing new-task default/
   filtered origins, ordinary Files organize, Scan/Preview, detail/records/export, transfers, Rules,
   Settings, Automation, Notifications, V1 and API clients remain compatible. Reads/refresh/export/
   control coordination are zero Storage mutation and invoke no Provider; explicit bounded analysis
   and Worker execution use existing abstractions and secret-free evidence.

Frozen: Slice Contract/Base, Roadmap, canonical requirements/Product Experience and reference image;
recognition/rule/policy semantics, providers/operations, Storage confinement, destructive permission,
immutable snapshot authority, OrganizerExecutor-only mutation and retired file recovery endpoints.
Refine the existing continuation boundary, not these invariants. If the Contract cannot be met,
identify the exact Contract clause and return to B before inventing a workaround or changing it.

## Acceptance Criteria

- [ ] **AC-T1 — Native authoritative controls:** selected unified run exposes exact backend actions
      and unavailable reasons; supported Pause/Cancel reaches the actual queue/execution owner,
      including pre-Task work. Current permissions/state/version are rechecked by API/Application.
- [ ] **AC-T2 — Truthful cooperative outcome:** request versus acknowledgement stays distinct;
      in-flight Provider/Storage calls complete under their fences, recorded effects stay durable,
      no next item starts after the observed stop, and cancellation never implies rollback/delete.
- [ ] **AC-T3 — Complete safe Continue:** every current supported safely paused async operator
      path that offers Pause has native queued Continue for its exact remaining scope, through the
      real resident Worker. Both Files transfer kinds remain supported. Honest legacy/synchronous
      exclusions cannot hide a currently supported pauseable async path or require ordinary CLI use.
- [ ] **AC-T4 — Exact scope, pin and authority:** completed/ignored/unknown effects are excluded;
      independent checkpoints/results, original limits and historical pin survive Active A→B and
      restart. Live source/capability/permissions and applicable one-shot/unattended authority are
      revalidated. Revoked grants or stored `execute_authorized` cannot authorize mutation; changed
      plans/insufficient authority have the native exact Preview/explicit-intent path promised by RO-5.
- [ ] **AC-T5 — Atomic and recoverable admission:** duplicate/concurrent/stale controls or claims
      cannot queue/execute the remaining work twice or overwrite newer ownership/results. Unknown
      command response locks resubmission until exact durable reconciliation; lost Worker, missing
      pin/secret/dependency and incompatible schema remain actionable with zero new media mutation.
- [ ] **AC-T6 — Linked native history and compatibility:** original/continued run and per-item
      outcomes remain inspectable without double count, overwritten success or raw token handling.
      Filters/detail/auth/back/restart and principal isolation work; read/evidence/export does not
      create work, call Provider or mutate Storage. Existing affected journeys remain usable.
- [ ] **AC-T7 — Real production journey:** Python-backed browser uses actual native controls on
      legal queued processing work, observes a safe Pause after one item completes, Continues only
      remaining work through the real resident Worker, and verifies exact linked results after
      restart. Prove cancellation during an in-flight call, authority refusal/re-Preview and unknown
      response reconciliation. Harness hooks may coordinate timing, not replace production admission,
      worker/authority/capability behavior or manufacture failures by removing supported abilities.
- [ ] **AC-T8 — Reviewable T4 checkpoint:** all required focused/full, quality/security/package and
      affected migration gates have honest attempts/totals/skips/unavailable results. No weakened
      assertions, hidden skips, real credentials/private config, unrelated changes or Contract edits.

## Required Tests

Use temporary SQLite/media and synthetic Providers/local servers. Never use production services,
credentials or user files. Keep all attempts; an unchanged serial rerun is allowed, never a waiver
for an unexplained current failure. Run browser invocations sequentially.

### Focused and integration

Extend existing suites and add a coherent continuation suite where needed. Cover the current legal
command matrix, owner links, pause acknowledgement/cancel during slow work, original remaining scope,
per-item exclusions, safe known partial effects, unsupported legacy evidence, source/capability change,
RBAC revocation, versions, concurrent admission, claim loss/heartbeat/fences, one-shot consumption,
unattended grant revocation, exact re-Preview, pin/dependency failures, A→B isolation, restart and
unknown-response reconciliation. Add exact commands for a new module to the completion report.

```sh
.venv/bin/python -m unittest tests.test_task_pause_resume tests.test_task_persistence tests.test_operations_workspace tests.test_operations_run_inventory tests.test_operations_run_detail
.venv/bin/python -m unittest tests.test_automation_api tests.test_automation_admission tests.test_automation_job_fencing tests.test_processing_worker_readiness tests.test_execution_authorization
.venv/bin/python -m unittest tests.test_automation_unattended_grant tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_configuration_snapshot
.venv/bin/python -m unittest tests.test_direct_file_transfers tests.test_media_library_transfers tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_api_security
.venv/bin/python -m unittest tests.test_recovery_continuation tests.test_processing_recovery_admission tests.test_processing_checkpoint tests.test_manual_operations_contract
```

Web typed models/API/query/forms cover backend action availability, optimistic controls, pause request
versus stop, Continue/refusals/re-Preview, unknown outcome lock, linked history, permission/principal
changes, terminal/missing evidence, keyboard/narrow/auth/history and return context.

From `web/`:

```sh
npm run test -- --run src/entities/operations src/features/operations src/features/library src/shared/api src/shared/navigation src/routes
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/manual-organize.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/deep-link.spec.ts
npm run test:e2e -- tests/e2e/library-files.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

Extend the isolated real Python harness/spec to prove AC-T7, or add a cohesive real lifecycle spec
under the same production boundary and report/run its exact command. API-fixture-only controls are
insufficient. The two previously Base-proven deep-link failures remain explicitly reportable only
while unchanged and unrelated; no waiver applies to new affected failures.

### Full, quality, safety, packaging and migration

```sh
python3 scripts/check_governance.py
.venv/bin/python -m unittest discover -s tests
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/python -m compileall -q mediaflow tests scripts
.venv/bin/python -m pip check
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate
.venv/bin/python -m unittest tests.test_release_security tests.test_release_validation tests.test_migration_rehearsal tests.test_upgrade_preflight
.venv/bin/python scripts/docker_release_security_smoke_test.py
git diff --check
git diff --check d52ce9299671ab05141f64848b8475cd4db11126
sha256sum docs/pics/操作与任务.png
git check-ignore config/alist.json
git ls-files config/alist.json
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

Docker may use an isolated daemon-visible TMPDIR with suitable test-owned directory permissions;
record the exact command and clean only gate-owned resources. Build a wheel with `.venv/bin/python
-m pip wheel . --no-deps --no-build-isolation -w <temporary-output>` and run `.venv/bin/python
scripts/wheel_smoke_test.py <built-wheel>`. If persistence changes, use a real Task-Base schema 42
fixture to prove preservation of existing pins, ownership, consumed authority, original Results and
links; incompatible/failed upgrade must fail closed. Prove resident continuation after restart in
the supported deployment boundary, extending the isolated packaging harness when material.

From `web/`:

```sh
npm run test -- --run
npm run typecheck
npm run lint
npm run format:check
npm run build
```

Reference SHA-256 remains `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`.
Private config stays ignored/untracked/unstaged; forbidden dependency search has no matches. Audit
full Base..Head/staged manifests without displaying private configuration.

## Non-goals

- Changing Slice Contract/Base, Roadmap, canonical requirements, reference image or closing the Slice.
- RO-6's new task-linked Recognition/Metadata/Classification/conflict decision forms and single/
  failed-analysis batch retry. Preserve existing recovery services/links and implement only the
  exact re-Preview/explicit-intent behavior required by RO-5 when Continue cannot retain authority.
- A global Review inbox, cross-task bulk recovery, history deletion/retention, task rename/priority,
  unbounded rescan/manual organization, new providers/operations/policy semantics or V1 retirement.
- Queue/task-engine replacement, distributed Worker/supervisor, long HTTP work, shelling out to CLI,
  forced interruption, rollback, silent fallback, repinning, destructive-authority weakening or
  automatic uncertain replay; unrelated refactors or isolated wording/field/test cleanup.

## Developer Completion Report

### Changed Files

Backend — new:
- `mediaflow/domain/scope_continuation.py` — the durable continuation record: `ScopeContinuation`,
  `ScopeContinuationStatus`, `ScopeContinuationReason`, `ScopeContinuationError` (with bounded
  `durable_state`/`next_action`/`retry_safe`/`current_version`) and the repository Protocol.
- `mediaflow/application/scope_continuation.py` — the shared admission/worker boundary:
  `ScopeContinuationService`, `ScopeContinuationWorkerService`, `remaining_scope`,
  `continuation_obstacle` and `definition_occurrence_authority`.

Backend — modified:
- `mediaflow/infrastructure/sqlite_runtime.py` — `SCHEMA_VERSION` 42→43; the additive
  `scope_continuations` table + its partial unique index; `admit_scope_continuation`,
  `get_scope_continuation_for_job`, `get_scope_continuation_for_source_task`,
  `list_scope_continuations`, `mark_scope_continuation_running`, `bind_scope_continuation_task`,
  `complete_scope_continuation`, `fail_queued_scope_continuation`, `cancel_scope_continuation`,
  `require_scope_continuation_by_job`, `get_job_for_task`; `claim_next_job` gains the third bounded
  per-Job continuation exception.
- `mediaflow/domain/automation.py` — `AutomationCommand.SCOPE_CONTINUATION`.
- `mediaflow/application/automation.py` — the mirrored schema default 42→43.
- `mediaflow/application/operations_lifecycle.py` — `TaskExecutionContext.continuable` +
  the continuation obstacle, and the resume action for the continuable boundary.
- `mediaflow/final_cli.py` — the resident-Worker handler `_run_scope_continuation` plus
  `_resolved_continuation_snapshot`, `_scope_continuation_authority`,
  `_scope_continuation_mutation_authority` and `_continue_scope_from_admission`.
- `mediaflow/interfaces/service_api.py` — `POST /api/v1/tasks/{id}/resume` admits a continuation
  (202); the run-overview read publishes the selected run's `lifecycle` projection.

Web:
- `web/src/entities/operations/run.ts` (+ test), `lifecycle.ts` (+ test) — the optional run
  `lifecycle` projection and its fail-closed normalization.
- `web/src/features/operations/RunLifecycleControls.tsx` (+ test) — the native 运行控制 panel.
- `web/src/features/operations/OperationsLanding.tsx`, `OperationsInventory.test.tsx` — wiring.
- `web/tests/fake-server.mjs` — the projection and the resume envelope.
- `web/tests/e2e/operations-inventory.python.spec.ts` — the two AC-T7 browser journeys.

Tests:
- `tests/test_scope_continuation.py` (new, 42 cases) — the focused continuation matrix.
- `tests/test_task_persistence.py` — `Schema42To43UpgradeTests`.
- `tests/test_operations_workspace.py`, `test_operations_run_detail.py`,
  `test_configuration_*.py`, `test_resident_correction.py` — updated expectations.
- `scripts/operations_inventory_harness.py` — the paused-scope fixture and the three
  `__harness__/*` routes that drive the real Worker handler.

### Implemented

One selected unified run now exposes the backend's own 运行控制 panel: Cancel, Pause and, for a
durably paused Task of a continuable kind, **Continue remaining scope**. Continue queues a bounded
continuation Job for the resident Worker and returns 202 with the durable continuation document;
the request itself performs zero Storage work.

The continuation preserves the original command, scope path, item limit and immutable configuration
pin verbatim, and excludes every already-recorded `(storage_id, source_path)`. Terminal successes,
dry runs, skips, explicit ignores, waiting decisions and uncertain (`attempted_unverified`) effects
are never replayed; failures remain remaining work, matching the proven CLI continuation. The
continuation Task is created by the production coordinator and the walk reuses the proven
`_continue_paused_scope` semantics under the Worker's own claim fence.

Execution authority is never taken from the stored `execute_authorized` boolean. A mutation-
authorized Task must prove a **live** reusable authority through the production
`UnattendedExecutionGrantService`, re-checked at admission, in the projection and again at every
mutation boundary by the same hook. When it cannot, admission returns 409 `authority_required` with
the native exact-Preview/explicit-intent next action, and the Worker refuses before constructing any
Storage adapter.

`mediaflow tasks resume` remains the CLI path and is never advertised as ordinary recovery.

### Tests and Results

Task-required focused and integration commands, all PASS (run individually):

```text
.venv/bin/python -m unittest tests.test_task_pause_resume tests.test_task_persistence tests.test_operations_workspace tests.test_operations_run_inventory tests.test_operations_run_detail
  -> Ran 121 tests, OK
.venv/bin/python -m unittest tests.test_automation_api tests.test_automation_admission tests.test_automation_job_fencing tests.test_processing_worker_readiness tests.test_execution_authorization
  -> Ran 73 tests, OK
.venv/bin/python -m unittest tests.test_automation_unattended_grant tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_configuration_snapshot
  -> Ran 85 tests, OK
.venv/bin/python -m unittest tests.test_direct_file_transfers tests.test_media_library_transfers tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_api_security
  -> Ran 217 tests, OK
.venv/bin/python -m unittest tests.test_recovery_continuation tests.test_processing_recovery_admission tests.test_processing_checkpoint tests.test_manual_operations_contract
  -> Ran 56 tests, OK
.venv/bin/python -m unittest tests.test_scope_continuation
  -> Ran 42 tests, OK
```

New focused suite (`tests/test_scope_continuation.py`, 42 cases): the continuable command matrix and
its exclusions; the projection's advertised/withheld copy and its no-CLI guarantee; the
available-XOR-explained contract for every action and state; atomic admission with zero Storage
work; duplicate/stale/non-paused/unresolvable-pin refusal with zero queued work; the stored-boolean-
is-not-authority refusal; RBAC; bounded not-found; remaining-scope exclusion of terminal, ignored
and uncertain items; the remaining item budget; pin preservation across an Active revision change
and a real reopen; concurrent admission queueing the scope exactly once; Worker prepare refusal on a
changed scope/pin; truthful Worker outcomes; failed-attempt retryability; claim selection of a
pinned continuation Job and non-claimability after terminal; independently inspectable attempts; the
row round-trip; the shared obstacle function; the real grant authorize/revoke journey; the
fail-closed missing-hook refusal; and two real-Worker end-to-end journeys.

Full, quality, safety and packaging:

```text
python3 scripts/check_governance.py                          -> governance check: PASS
.venv/bin/python -m unittest discover -s tests               -> Ran 2163 tests, OK (skipped=7)
.venv/bin/ruff format --check .                              -> 338 files already formatted
.venv/bin/ruff check .                                       -> All checks passed
.venv/bin/python -m compileall -q mediaflow tests scripts    -> OK
.venv/bin/python -m pip check                                -> No broken requirements found
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate
                                                             -> PASS
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate
                                                             -> PASS
.venv/bin/python -m unittest tests.test_release_security tests.test_release_validation tests.test_migration_rehearsal tests.test_upgrade_preflight
                                                             -> Ran 19 tests, OK
wheel: .venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <tmp>  -> built
       .venv/bin/python scripts/wheel_smoke_test.py <wheel>  -> PASS (Schema: 43)
git diff --check                                             -> clean
git diff --check d52ce9299671ab05141f64848b8475cd4db11126  -> clean
sha256sum docs/pics/操作与任务.png                            -> a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86
git check-ignore config/alist.json                           -> config/alist.json
git ls-files config/alist.json                               -> (empty; untracked)
grep -rn -i 'ffprobe|ffmpeg' mediaflow pyproject.toml        -> no matches
```

Web (`web/`):

```text
npm run test -- --run                  -> 63 files, 972 tests passed, 0 failed, 0 skipped
npm run typecheck                      -> PASS
npm run lint                           -> PASS
npm run format:check                   -> All matched files use Prettier code style
npm run build                          -> PASS
npx playwright test                    -> 204 passed
npx playwright test --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
                                       -> 16 passed
```

Migration: `Schema42To43UpgradeTests` builds a genuine schema-42 runtime database (real tables, a
real paused Task with its complete pin, its item and its Result; only the schema-43 objects removed
and the marker rewound), proves the additive upgrade preserves every one of those facts, proves a
pre-existing Task is handed no fabricated continuation, proves idempotence, proves a newer-than-code
database still fails closed, and proves the migrated `scope_continuations` table accepts and loads
exactly like a freshly created one.

AC-T7 real-Python browser proof (`playwright.python.config.ts`, 16 passed): the paused fixture is
created by the production `PersistentTaskCoordinator`; the operator clicks the **rendered** native
继续剩余范围 control on the selected run; the real API admits it (202, `sideEffects: none`) and the
real Worker handler claims and completes it, processing exactly the one remaining source and never
the already-recorded one; the linked continuation stays independently inspectable after a real
restart; and a mutation-authorized paused run without live authority renders the withheld control
with the native next action and refuses a direct POST with 409 `authority_required`.

### Decisions

- **Authority.** Only a managed Automation Task Definition occurrence owns a reusable authority
  (its definition-bound unattended grant). The checker is shared by the projection, the API
  admission and the Worker, so the advertised control and the real boundary cannot disagree. A
  one-shot or revoked authority fails closed with the native exact-Preview journey.
- **A stored boolean is never authority.** The continuation Job is admitted with
  `execute_authorized=False`; the live grant hook is the real mutation gate, and the Worker refuses
  outright rather than handing the executor a `None` hook (which means "no check").
- **Remaining scope.** `_REMAINING_ITEM_STATUSES` deliberately matches the proven CLI
  `retryable_items(failed_only=False)`: failures remain remaining work. Terminal Results, ignores
  and uncertain effects stay excluded.
- **Pin.** A Task with no complete immutable pin is refused honestly (`snapshot_unavailable`)
  instead of being silently rebound to the current Active revision. The continuation never repins.
- **Schema.** 43 is additive; `claim_next_job` gains a third bounded per-Job continuation exception,
  matching the existing recovery/metadata-correction precedent.
- **Web state.** The projection is the only source of a rendered control; the client never derives
  authority from a run status, a route or cached data.

### Remaining In-Slice Work

RO-6 (task-linked Recognition/Metadata/Classification/conflict decision forms and single/
failed-analysis batch retry) is explicitly outside this Task and remains for a follow-up Task.
AC-T7's cancellation-during-an-in-flight-call and unknown-response-reconciliation proofs are covered
by unit/integration tests (cooperative cancel at a boundary; the client's unknown-outcome lock and
its single explicit reconciliation read) rather than by the isolated browser harness, which drives
synchronous fixture work and therefore cannot hold a real in-flight Provider call open.

### Risks / Deviations

- `scripts/docker_release_security_smoke_test.py` FAILS in this environment: the Docker daemon
  rejects the compose bind mounts because the smoke test's temporary context directory is not
  visible to it (`bind source path does not exist: /tmp/mediaflow-smoke-security-*/mediaflow.json`).
  The identical failure reproduces on the untouched Task Base `d52ce92` in a throwaway worktree, so
  it is environmental and not caused by this Task.
- `tests.test_v2_rules_workspace_commands.RulesWorkspaceCommandTests.test_simultaneous_saves_never_publish_a_mixed_or_lost_successor`
  is a pre-existing thread-race flake: under synthetic load it failed 2/25 on the untouched Task
  Base and 3/25 on this checkpoint. It passes in every serial full-suite run reported above.
- The 7 skipped tests are the pre-existing environment-blocked real SMB/S3/OpenList/endurance
  acceptance matrices; no new skip was introduced and no assertion was weakened.
- The harness fixture now keeps the managed configuration and the runtime rows in one SQLite file
  (the production shape), which the Worker's `configuration.database_path` resolution requires.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 8a60cab0a0f9306a434d785c35ebd26bac41a422
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
