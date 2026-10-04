# Task 42.4 — Native controls and safe queued paused-scope continuation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 42.4
Parent Slice: 42
Status: FIX REQUIRED
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

Correction round 1 (B `FIX REQUIRED`) — modified/added:
- `mediaflow/domain/scope_continuation.py` — `NO_REMAINING_SCOPE`,
  `CONTINUATION_OWNED_ELSEWHERE`, and the `get_scope_continuation_for_new_task` Protocol read.
- `mediaflow/application/scope_continuation.py` — chain-aware `remaining_scope`, `continuation_chain`,
  `chain_owner`, `_active_continuation`, the `exclude_job_id` self-refusal guard and the public
  `obstacle` accessor.
- `mediaflow/application/manual_organize_preview.py` — `create_remaining_scope_from_task`,
  `_scope_library`, `_remaining_scope_sources` and the explicit `skip_current_snapshot_check` opt-in.
- `mediaflow/application/manual_organize.py` — the explicit `pinned_snapshot` opt-in.
- `mediaflow/application/operations_lifecycle.py` — `scope_continuation_operator_document`,
  `continuation_blocked_code` and the `preview` recovery entry on the withheld Continue action.
- `mediaflow/interfaces/service_api.py` — the redacted 202 continuation envelope, the run-overview
  `continuation` field and `POST /api/v1/tasks/{taskId}/remaining-scope-previews`.
- `mediaflow/infrastructure/sqlite_runtime.py` — `get_scope_continuation_for_new_task`.
- `web/src/entities/operations/lifecycle.ts` (+ test) — the fail-closed `recovery` normalizer.
- `web/src/entities/operations/run.ts` (+ test) — the bounded `continuation` projection.
- `web/src/features/operations/RunLifecycleControls.tsx` (+ test) — the native Preview recovery entry.
- `web/src/features/operations/OperationsLanding.tsx`, `OperationsInventory.test.tsx` — the recovery
  admission, the linked-run entry and their journeys.
- `web/src/shared/api/api-client.ts` (+ test) — `submitRemainingScopePreview`.
- `web/tests/fake-server.mjs`, `web/tests/e2e/operations-inventory.python.spec.ts`,
  `scripts/operations_inventory_harness.py` — the mirrored projection, route and fixture scope.

Tests:
- `tests/test_scope_continuation.py` (new, 55 cases) — the focused continuation matrix.
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

### Correction Round 1 (B Review `FIX REQUIRED`)

All three B blockers are fixed. Only the listed blockers and their direct root causes were touched;
no unrelated P2/P3 work, no assertion loosening and no history amendment.

**P1-1 — a finished continuation could be admitted and executed again.**
`mediaflow/application/scope_continuation.py` now resolves the whole recorded continuation **chain**
through the explicit durable links only (`scope_continuations.source_task_id` / `new_task_id`, via
the new `get_scope_continuation_for_new_task` repository read) — never by filename, label or
creation time. `remaining_scope()` aggregates every chain Task's items and results and computes the
budget from the **root** Task, so `already_recorded` covers sources any attempt already owns.
`continuation_obstacle()` now returns two new closed reasons: `CONTINUATION_OWNED_ELSEWHERE` when a
later non-terminal chain Task owns the remaining scope, and `NO_REMAINING_SCOPE` when the chain
already consumed the whole admitted budget. The lifecycle projection, the API admission and the
Worker all read this one decision, and the Worker excludes the exact Job it already claimed
(`exclude_job_id`) so it can never refuse itself. The run overview publishes a bounded
`continuation` projection, and the run detail renders a native entry that selects the linked
continuation run, so the operator is never told to "follow the linked run" without a surface.

**P1-2 — no native exact Preview / fresh-intent recovery under a historical pin.**
`ManualOrganizePreviewService.create_remaining_scope_from_task` admits a zero-mutation exact Preview
of the run's **durable remaining scope** under the run's **own immutable pin**. It reuses
`remaining_scope` (so it can never broaden the admitted budget or re-offer a decided sibling),
resolves the run's scope against the *pinned* runtime's ResourceLibrary roots, re-verifies every
source live from Storage, and refuses an unresolvable or ambiguous scope (`scope_unresolved`) rather
than widening it to a whole library. `ManualOrganizeIntentService.create_from_sources` gained the
single explicit `pinned_snapshot=True` opt-in, which loads the revision through the same managed
authority (`ACTIVE` or `SUPERSEDED`, integrity verified) the Worker uses; the ordinary Files path
still hard-requires the current Active revision, and `ManualOrganizePreviewService.create` gained
the matching explicit `skip_current_snapshot_check` opt-in. The new route
`POST /api/v1/tasks/{taskId}/remaining-scope-previews` (`MANAGE_MANUAL_ORGANIZE`, 201) is advertised
as a `preview` recovery entry on the withheld Continue action for exactly the `authority_required`
refusal and for a principal that really holds the permission. The Web renders that entry as a real
button and routes the operator to the ordinary organize Preview review, where one fresh explicit
Execute intent is still required. Execution is still refused on the basis of the execute flag, a
consumed authorization or a revoked grant alone.

**P1-3 — the Continue API response leaked an absolute host path.**
The 202 acceptance response now publishes `scope_continuation_operator_document(...)` instead of the
raw `submission.continuation.document()`. The new projection in
`mediaflow/application/operations_lifecycle.py` carries only bounded identifiers and bounded
evidence: no `scope_path`, no configuration pin identity, no actor. The same projection is used by
the run-overview `continuation` field, and the duplicate/conflict read path was reviewed (it
publishes no continuation body at all). The Worker's internal durable row keeps the complete
original scope and pin, so redaction never weakens execution; front-end hiding alone was not used.
`tests/test_scope_continuation.py` gained a legal absolute-scope API privacy regression that asserts
the host root never appears in the accepted body while the stored row still holds it verbatim.

#### Correction evidence

```text
.venv/bin/python -m unittest tests.test_scope_continuation
  -> Ran 55 tests, OK   (was 42; +13 correction cases)
.venv/bin/python -m unittest discover -s tests -t .
  -> Ran 2176 tests, OK (skipped=7)
python3 scripts/check_governance.py                -> governance check: PASS
.venv/bin/ruff check .                             -> All checks passed
.venv/bin/ruff format --check .                    -> 338 files already formatted
.venv/bin/python -m compileall -q mediaflow tests scripts -> OK
.venv/bin/python -m pip check                      -> No broken requirements found
.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate           -> PASS
.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate -> PASS
.venv/bin/python -m unittest tests.test_release_security tests.test_release_validation tests.test_migration_rehearsal tests.test_upgrade_preflight
                                                   -> Ran 19 tests, OK
wheel smoke test                                   -> Schema: 43 / Status: PASS
git diff --check                                   -> clean
git check-ignore config/alist.json                 -> config/alist.json (untracked; nothing staged)
```

Web (`web/`):

```text
NODE_ENV=test npx vitest run                       -> 63 files, 987 tests passed, 0 failed
npm run typecheck                                  -> PASS
npm run lint                                       -> PASS
npm run format:check                               -> All matched files use Prettier code style
npm run build                                      -> PASS
NODE_ENV=test npx playwright test tests/e2e/operations.spec.ts tests/e2e/manual-organize.spec.ts tests/e2e/manual-operations.spec.ts
                                                   -> 54 passed
NODE_ENV=test npx playwright test --config playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
                                                   -> 16 passed
NODE_ENV=test npx playwright test                  -> 204 passed / 31 failed (all 31 pre-existing)
```

New correction cases: chain-aware remaining scope (a finished continuation chain has no remaining
scope; a still-paused descendant owns it; the linked continuation is projected), the Worker
never refusing the continuation it claimed, the native remaining-scope Preview (only the eligible
items, zero mutation, no Task/Job/execution/authority, exact remaining scope, no host-path leak),
its `no_remaining_scope` / `scope_unresolved` / permission / unresolvable-pin refusals, the
`authority_required`-only Preview advertisement, the permission gate on the projection, and the
opt-in-only historical pin. Web cases: the recovery entry renders only from the backend projection,
is disabled in flight, the linked continuation entry selects the linked run without a POST, the
recovery POST sends only the run identity, and the redacted continuation envelope is asserted
end-to-end.

#### Pre-existing failures (unchanged, not caused by this Task)

The 31 fake-server browser failures are the **same set** on the untouched Task Base: a throwaway
worktree at `HEAD` reproduced all 31 (and the baseline full run additionally failed 80, a superset).
They are confined to `storage-management.spec.ts` (28), `deep-link.spec.ts` (2) and
`dashboard.spec.ts` (1) — none in this Task's `operations*.spec.ts` / `manual-*.spec.ts` journeys.
Label: `FAIL / PRE-EXISTING / UNRELATED`; the "does not affect PASS" judgement is left to B.
The 7 skipped backend tests remain the pre-existing environment-blocked real SMB/S3/OpenList/
endurance acceptance matrices; no skip was added and no assertion was weakened.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: f4aace533c2d62aead50f9b6a4fde81f0061bf24
```

### Correction Round 2 — Developer Completion Report

#### Changed Files

- Backend: `mediaflow/application/automation.py`, `manual_organize_preview.py`,
  `media_organizer.py`, `operations_lifecycle.py`, `scope_continuation.py`;
  `mediaflow/domain/manual_organize_preview.py`, `scope_continuation.py`;
  `mediaflow/final_cli.py`, `mediaflow/infrastructure/sqlite_runtime.py`,
  `mediaflow/interfaces/service_api.py`.
- Tests: `tests/test_scope_continuation.py`, `tests/test_automation_definition_execution.py`,
  `tests/test_task_persistence.py`, and the five managed configuration tests whose runtime-schema
  expectation advances from 43 to 44.
- Web: operations `run`/`preview` models and tests, `OperationsLanding.tsx`,
  `OperationsInventory.test.tsx`, `OrganizePreviewPage.tsx`, `OrganizeRouter.test.tsx`, and the
  API-backed `manual-operations.json` fixture.
- `TASK.md` — this report; the B review blockers below remain unchanged.

#### Implemented

- Exact remaining-scope Previews persist their source Task ID. The existing ManualExecution-to-Task
  record completes the durable Preview → execution → new Task link. Remaining-scope accounting
  traverses these explicit links along with queued continuations, charges execution items to the
  original Task budget, and refuses a further Preview when no admitted budget remains. The selected
  source run exposes the exact Preview, execution and resulting Task; Preview navigation preserves
  the task-center query, and a successful recovery Execute returns to the original run.
- Definition-scoped continuations validate the original Task/Job against the pinned Definition,
  including fingerprint, command, ResourceLibrary, Storage-relative source scope and item limit.
  The Worker resolves that exact sub-scope through Storage and keeps its display root for results;
  it does not broaden to the ResourceLibrary root.
- Runtime schema 44 adds nullable `manual_previews.recovery_source_task_id` and its index. Schema 42
  upgrades preserve existing Tasks, pins, items, Results and authority state without inventing
  recovery links.

#### Tests and Results

- Focused Python gates: all PASS — `tests.test_task_pause_resume` / persistence / workspace / run
  inventory / run detail (121); automation API / admission / fencing / readiness / authorization
  (73); unattended grants / Definition execution / authorized matrix / configuration snapshot (86);
  transfer / manual execution / V2 / API security (217); recovery / admission / checkpoints / manual
  operations contract (56).
- `.venv/bin/python -m unittest tests.test_scope_continuation tests.test_task_persistence tests.test_automation_definition_execution`
  → 94 tests PASS, including the exact Preview budget, schema-42-to-44 preservation and Definition
  Storage-relative Worker scope cases.
- The first full Python run found five configuration tests still expecting schema 43. I updated those
  direct version assertions to 44 and reran them (5/5 PASS). The unchanged full command then passed:
  `.venv/bin/python -m unittest discover -s tests` → 2,178 tests, PASS, 7 skipped.
- Required Web-focused command → 42 files, 698 tests PASS. Full `npm run test -- --run` → 63 files,
  991 tests PASS. `npm run typecheck`, `npm run lint`, and `npm run format:check` PASS;
  `npm run build` PASS with the existing >500 kB chunk-size advisory.
- Browser command for Operations, Manual Organize, Manual Operations and deep links → 66 PASS, 2
  FAIL in `deep-link.spec.ts` (route-choice boundary timeout and V1 handoff heading). These are the
  same two failures B recorded on the untouched Task Base; see Risks / Deviations. Files browser →
  40 PASS. Python-backed Operations browser → 16 PASS, including resident Worker Continue and
  restart coverage.
- `.venv/bin/python /tmp/mediaflow-b42-4-r2-definition-proof-fixed.py` → PASS: the real Definition
  Task paused at `scopePath="Authority"`, admitted Continue (202), and completed in the Worker
  with an exactly linked new Task. The preview-budget API/Manual Worker integration test also
  passed in the focused and full Python suites. The separate
  `node /tmp/mediaflow-b42-4-r2-recovery-budget.mjs` reproduction was UNAVAILABLE because its
  Playwright harness was not running at `localhost:4185`.
- Governance, Ruff format/check, compileall, pip check, both configuration validations and release /
  migration tests (19) PASS. Candidate-tree Docker release-security smoke PASS. Wheel build and
  `scripts/wheel_smoke_test.py` PASS with runtime Schema 44.
- `git diff --check` and Base-to-working-tree `git diff --check` were clean; reference image SHA-256
  is `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`; `config/alist.json`
  remains ignored and untracked; the forbidden FFmpeg/FFprobe dependency search has no matches.

#### Decisions

- A nullable origin Task ID on the ordinary Preview is sufficient durable ancestry: the existing
  ManualExecution row supplies the explicit new Task ID. No parallel execution queue or stored
  authority was added.
- Recovery links participate in the same chain-wide remaining-scope calculation as queued
  continuations. The immutable root Task remains the item-budget authority.
- Definition scope resolution requires matching immutable Definition and Job evidence, then uses
  the configured Storage interface for the exact Storage-relative path. The direct CLI path stays
  confined under its configured ResourceLibrary display root.
- Recovery navigation uses the normal Preview and explicit Execute journey, retaining the selected
  Operations run as the return target.

#### Remaining In-Slice Work

RO-6 remains: task-linked Recognition / Metadata / Classification / conflict decisions and single /
failed-analysis batch retry. This Task adds only the RO-5 exact Preview / fresh Execute recovery
needed when paused work cannot safely retain execution authority.

#### Risks / Deviations

- `FAIL / PRE-EXISTING / UNRELATED`: the two fake-browser failures are the same unchanged
  `deep-link.spec.ts` failures B recorded against the untouched Task Base; no deep-link code or
  assertions changed here. Their Task-level disposition remains for B.
- The separate budget reproduction could not connect because its local Playwright harness was
  unavailable at port 4185. The equivalent repository integration test exercises real API
  admission, Manual Worker execution, linked history, reopened SQLite state and exhausted-budget
  refusal; it passed.
- Seven full-suite skips are the existing environment-blocked external-service/endurance cases; no
  skip or assertion was added or weakened.
- Docker smoke used isolated candidate `8433180915062648b9339763bfcd0c635c6de6a0`, whose application,
  test and fixture tree matches the implementation checkpoint below; only this completion report
  was not present in that candidate tree.

#### Checkpoint

Status: READY FOR B REVIEW

Head SHA: `887e744e48feb170744629708936fa9584e97d79`

## B Review Result

```text
Reviewed: d52ce9299671ab05141f64848b8475cd4db11126..f4aace533c2d62aead50f9b6a4fde81f0061bf24
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — exact Preview 恢复执行未计入源运行的范围、预算和关联历史（AC-T4/T6；Scope 4/5/7；RO-5/RO-7）。**
  当前合法 managed Local `organize --execute` 形态的暂停运行（有效历史 pin、scope 为配置显示根内的目录、limit=2），从原生“查看剩余范围的精确预览”生成 201 Preview，再明确 Execute 返回 202，真实 Manual Worker 完成 2 个文件。回到原运行后它仍为 paused、`continuation=null`；在该目录新增一份测试媒体，原生剩余范围 Preview 再次返回 201，Execute 再次返回 202，真实 Worker 又完成第 3 个文件。用户通过同一原运行的恢复入口突破了已耗尽的原限额，且原运行无法查看恢复执行的关联历史。
  证据：`node /tmp/mediaflow-b42-4-r2-proof.mjs`（校准合法显示根后的日志 `/tmp/mediaflow-b42-4-r2-proof-v2.log`），以及 `node /tmp/mediaflow-b42-4-r2-recovery-budget.mjs`；预算断言 exit 1。源 Task `027acd51-0814-4ec8-b63c-ad00e1da753e` 限额 2，后续 Task `90c754f6-e53e-49cb-ad2c-fe949bcd8270` completed/2 items，第二次恢复 Task `b3783c7e-b869-4af4-9973-eff3fbbf00c8` completed/1 item。首轮 Preview 导航还丢失 `returnOps`，Execute 后进入独立 execution 页，未返回任务中心选择关联运行。`runTaskId` 只附在 Preview 受理响应中，未形成 `remaining_scope()` 可追踪的持久恢复关联。
  修正：使原运行→remaining Preview→fresh intent→execution/Task 的关联与预算消耗持久化，并由后端 remaining-scope 判定/受理/Worker 共同使用；耗尽范围拒绝再次恢复，保存成功/ignored/uncertain 排除规则、原 pin 和历史。原生 Preview 保留任务中心返回上下文，成功受理后选择关联运行，并能从源运行查看后续结果。证据 JSON：`/tmp/mediaflow-b42-4-r2-proof.json`、`/tmp/mediaflow-b42-4-r2-recovery-budget.json`。

- **P1 — 当前 Definition-scoped Preview 的 Continue 无法执行合法 Storage 相对 scope（AC-T3/T4/T7；Scope 3/4；RO-5）。**
  当前已检查并激活的 `scan-and-plan` Automation Definition（ResourceLibrary `source`、sourceScope=`Authority`、itemLimit=2）经真实 IntervalScheduler 发出 occurrence、真实 DefinitionScopedExecutionService 创建 Task；实际 Pause API 返回 200，生产执行在安全边界确认 paused，持久 command=`preview`、scope_path=`Authority`。当前 API 公告 Continue 可用并返回 202，但真实 claim/queued Worker 随即失败，continuation 与新 Task 均为 failed，0 items，异常为 `ValueError: path is not inside a configured ResourceLibrary`。用户在任务中心继续当前受支持的暂停 Definition Preview 会进入无法推进的失败循环。
  证据：`.venv/bin/python /tmp/mediaflow-b42-4-r2-definition-proof-v2.py`，生产路径断言 exit 1；源 Task `180ed1a4-ea23-41ec-b0bd-02438acc9a4b`，失败的新 Task `eee1143a-8611-4924-ba9c-15d423315dd7`。合法配置/源目录/完整 pin/权限/Local Storage/claim 均保持真实；原处理与 continuation 仅在外部 Provider 装配处使用相同完整 synthetic registry，没有删除或隐藏当前能力。失败发生在任何媒体 item/Provider lookup 之前，不以缺少 TMDB credential 的首次环境失败作为阻塞证据。当前 Definition 生产者持久化 Storage-relative scoped root，而 `_continue_scope_from_admission()` 对 preview/organize 把它交给宿主 `Path` / `_resource_library()` 解析。
  修正：依据当前生产 Task/Definition 的持久库身份与历史 pin，通过既有 Storage/ResourceLibrary scope 边界解析并执行原 scope，保留限额、排除集合和安全 checkpoint；让公告、受理与 Worker 支持矩阵一致，保留当前 Definition Pause/Continue 能力。覆盖合法 Definition 的实际暂停→排队继续→Worker 结果，不能用只含 CLI 绝对 scope 或 scan 全库 fixture 代替。证据 JSON/日志：`/tmp/mediaflow-b42-4-r2-definition-proof-v2.json`、`/tmp/mediaflow-b42-4-r2-definition-proof-v2.log`。
