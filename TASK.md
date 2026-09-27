# Task 39.5 — Resident transfer continuity and truthful Worker readiness

This Task follows [the development workflow](docs/development-workflow.md) and the checkpointed
[A Scope Activation](SLICE.md#a-scope-activation--2026-09-26-worker-continuity).

```text
Task ID: 39.5
Parent Slice: 39
Status: IN PROGRESS
Task Base: d74822ce509512fcc10e5802bc6cc95602c77c3b
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete Slice 39 RO-8/RO-9: an operator can start the deployment, finish setup/activate configuration,
and explicitly submit a ResourceLibrary or MediaLibrary transfer that the already-running Worker
executes under the admitted immutable snapshot. Health and transfer progress truthfully explain
whether work can run, why it is waiting and how to recover without resubmission or uncertain replay.

## Why This Task Exists

The real resident composition creates a no-op transfer runner for its entire lifetime if there is
no Active at startup or initial Active construction fails. A reproduced the legitimate sequence
with temporary SQLite, actual Local Storage and checked activation: after Move admission, three
polls of the original runner leave the transfer `admitted`; a newly constructed runner is functional.
The existing per-task runtime rebuilder cannot help when the resident consumer was never installed.

Bootstrap registration also depends on worker ID/snapshot presence; current registration and
readiness primarily describe Automation commands. Worker container health currently checks deployment
preflight, which cannot prove that the Worker is registered or able to consume this command. These
are one user journey failure across runtime composition, persistence, API, Web and deployment.

A explicitly included this correction in Slice 39; Slice 38 remains closed. This is the fifth
coherent Task, not a Task per assertion, health field or regression. Reuse the existing transfer
queue and safety machinery; avoid a generic scheduler/runtime framework. Earlier Task Bases and
PASS decisions remain unchanged. High/T4 is required by actual media mutation, snapshot authority,
leases, restart recovery, durable registration and container execution.

## Implementation Scope

Durable admitted authority → resident claim/reconstruction → existing transfer service/Executor →
command-aware readiness and progress → API/Web → actual container lifecycle and regression tests.

1. **Resident assembly and snapshot binding.** Inspect the complete CLI startup and worker loop,
   including `_configuration`, `_managed_snapshot_reference`, `_files_transfer_worker_context`,
   `AutomationWorker` and `FilesTransferWorker`; do not fix only an isolated constructor that the
   real entrypoint cannot reach. With valid deployment/DB/schema, install and register the transfer
   consumer before any Active and keep it available during current-Active outages. Build the
   Resource/Media execution boundary from each admitted Task's durable command/kind, revision ID,
   digest and authority. Validate published snapshot/integrity, roots, capabilities, applicable
   permissions/secret readiness and confinement before any mutation. Bind the context for the whole
   attempt; close per-attempt resources reliably. A bounded reuse/cache is optional, not required.
2. **Admission versus execution.** Current Active remains authoritative for new admission. Existing
   admitted A work must remain executable from valid A when Active becomes B or disappears. Invalid
   task pins, unavailable required credentials, incompatible schema or unknown command fail closed
   with durable, bounded blocked/failure evidence. Never substitute current Active, JSON, a Draft or
   the other library kind. Preserve a still-valid admitted queue entry where recovery is possible;
   do not silently discard work, busy-loop or let one incompatible entry hide all eligible work.
3. **Ownership and restart.** Reuse atomic claims, owner tokens, lease keeper, persisted per-item
   checkpoints, mutation fences and uncertainty resolution. Ownership must cover reconstruction and
   slow provider calls. A later activation must not alter an in-flight attempt. Completed effects
   remain terminal; uncertain effects are resolved/explained without automatic mutation replay.
   Losing ownership blocks new effects/stale completion; do not claim that an already-issued remote
   operation can be undone. Retain pause/resume/cancel and safe not-started continuation semantics.
4. **Truthful health.** Make registration/heartbeat independent of business Active in production.
   Distinguish process liveness, registration/DB/schema readiness, and command/pin work readiness.
   Expose actual supported Resource/Media transfer commands separately from other Worker duties,
   current Active availability and bounded compatibility/reconstruction blockers. A healthy worker
   for another command cannot satisfy this transfer. Integrate the real container probe/Compose
   signal with service readiness, document exactly what healthy means, and avoid making no Active
   alone equivalent to a dead consumer. Probe/health reads perform no provider calls or mutations.
   Reuse current registration storage/projections; narrowly necessary durable evolution is allowed
   with migration/upgrade evidence, never an unversioned silent schema change.
5. **Visible waiting and recovery.** Reuse existing authenticated transfer submission/progress,
   Files and Operations revisit, Worker readiness API and typed Web models. Retain asynchronous
   durable admission; show `等待可用 Worker` or equivalent before or immediately after submission
   when work cannot yet be consumed. Explain no/stale Worker, unsupported command, DB/schema or
   unavailable pinned context, distinguish not admitted/admitted/running/partial/uncertain, and
   give the relevant safe next action. Refresh never resubmits. Repairing readiness lets safe
   eligible work continue without another submission. Viewer/read-only observation and backend
   permission checks stay authoritative; no internal tokens/digests as ordinary user input.
6. **Integration and documentation.** Cover both library kinds and their existing API/Web paths,
   plus compatibility with Automation jobs and admitted manual Organize. Use actual OpenList
   adapter HTTP against a controlled local service for the mandatory Move/slow-request proof.
   Extend an existing Docker harness or add `scripts/docker_files_transfer_lifecycle_smoke_test.py`
   with an `--image` option; use the committed image/entrypoint/real worker loop. Update factual
   deployment/API/architecture guidance necessary to describe delivered behavior, clearly separating
   remaining targets. Do not change A-owned Slice/requirement scope, Roadmap or acceptance criteria.

## Acceptance Criteria

- [ ] With no initial Active, a valid production Worker remains running and durably registered.
      First checked activation followed by OpenList Move executes without restarting/replacing
      that Worker. Both ResourceLibrary and MediaLibrary command dispatch are supported and isolated.
- [ ] Active A→B gives new admissions B. Already-admitted A and a Move blocked in a provider call
      during activation remain on A. Distinct roots/provider observations prove actual use, not
      just a revision label; equal library IDs do not cross Resource/Media authority.
- [ ] Missing/unusable current Active rejects new admission with zero Storage mutation, while a
      valid older admitted pin can still execute. Missing/corrupt/digest-mismatched/unpublished task
      snapshots and required missing secrets cause zero new Storage mutation and actionable durable
      evidence, with no fallback. Existing partial effects are reported truthfully, not rolled back
      in the UI or automatically replayed.
- [ ] Worker restart, competing ownership and lease expiry do not duplicate confirmed effects or
      replay uncertain operations. OpenList requests held longer than the configured test lease
      retain both relevant heartbeat/lease and mutation exclusion, and stale owners cannot publish
      over successors. Genuine process failure still permits the existing safe resolution path.
- [ ] Health reports liveness, base readiness and work readiness separately. No/stale registration,
      database failure, runtime schema mismatch, unsupported command and unavailable task context
      cannot be falsely reported as eligible execution. Current Active health does not veto a valid
      older pin. Compose verifies actual Worker readiness and its documented semantics match results.
- [ ] Real API/Web transfer submission, progress, reconnect and Operations revisit promptly show
      waiting reason/durable state/next action, and converge to actual progress after recovery without
      resubmission. A live Worker for a different command is not sufficient. Readiness reads and
      refresh generate no Storage access/probe, configuration publication or media work.
- [ ] Docker proves containers first → first checked activation → admitted OpenList Move with
      unchanged Worker container/process identity. Actual source/destination effects and durable
      results agree. A local HTTP provider may control timing/data; the application/consumer must
      not be replaced by a fake, `run-next`, or a Worker restart after activation.
- [ ] Required T4 gates pass with honest totals, skips and unavailable gates. Existing Storage
      configuration, Files, both transfer kinds, Automation/manual Organize, redaction/RBAC,
      boundedness, RecognitionType C identity and OrganizerExecutor-only mutation stay intact.

## Required Tests

Add regression tests to the existing relevant suites or a coherent new lifecycle suite. Use
synchronization/events for concurrency, bounded timeouts and real SQLite/production composition.
Do not hide a production capability in a test double to manufacture a defect. Do not use production
SMB/OpenList/S3/TMDB services, private config/credentials or user media. Do not remove or loosen tests.

Mandatory lifecycle matrix (all eight user-requested cases):

| Case | Required proof |
|---|---|
| 1. Worker before first activation | Real resident entrypoint/composition, then checked activation and OpenList Move; no restart. |
| 2. New work after A→B | Admit after switching; observe execution against distinct B configuration. |
| 3. Queued A work after A→B | Admit before switching; observe execution against A, including Worker reconstruction. |
| 4. Switch during Move | Hold an actual adapter request, publish B, release request; same A attempt/fence throughout. |
| 5. Missing/corrupt context or secrets | Missing current Active blocks new admission; intact A may execute. Missing/bad task pin, digest, schema or required credentials produces zero new mutations and truthful recovery. |
| 6. Restart | Completed and uncertain checkpoints do not reissue mutation; safe not-started siblings retain independent continuation. |
| 7. Slow OpenList | Hold request beyond a short configured lease; observe continued heartbeat/fence, reject competitor and stale completion, retain safe process-death resolution. |
| 8. Docker production order | Start all services without Active; activate through real checked API; submit Move and verify outcome with the same Worker process/container. |

Exact existing gates:

- `.venv/bin/python -m unittest tests.test_direct_file_transfers tests.test_media_library_transfers tests.test_processing_worker_readiness tests.test_container_probe tests.test_container_deployment tests.test_openlist_storage tests.test_configuration_snapshot tests.test_manual_organize_execution tests.test_automation_job_fencing`
  plus the new lifecycle module if one is added; include negative registration/command/schema and
  API parity cases and inspect persisted outcome/mutation counts, not only function calls.
- `cd web && npm test -- --run src/entities/operations/worker.test.ts src/shared/api/operations-api.test.ts src/features/library/StorageFilesPage.test.tsx src/features/library/MediaLibraryTransfers.test.tsx src/features/operations/OperationsRouter.test.tsx`
  plus new/affected typed waiting/progress component tests. Cover initial admission, durable revisit,
  recovery, viewer permissions, malformed/denied API, no retry-on-refresh and keyboard/narrow layout.
- `cd web && npm run build && npm run test:e2e -- tests/e2e/library-files.spec.ts tests/e2e/medialib-transfers.spec.ts tests/e2e/medialib-files.spec.ts`
  plus affected Operations/Worker browser coverage. At least one complete waiting→available→execution
  journey uses the real API/Worker and temporary state; resettable fake status alone is insufficient.
- `.venv/bin/python -m unittest discover -s tests` and `cd web && npm test -- --run`.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build`.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check .` and
  `.venv/bin/python -m compileall -q mediaflow tests scripts`.
- `python3 scripts/check_governance.py`, `git diff --check`, exact Base..Head manifest review,
  secret/private-config audit and FFmpeg/FFprobe exclusion audit.
- `python3 -u scripts/docker_health_smoke_test.py --image mediaflow:task39-5-health`.
- `python3 -u scripts/docker_files_transfer_impact_smoke_test.py --image mediaflow:task39-5-transfer`.
- `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-5-security`.
- If adding the lifecycle harness:
  `python3 -u scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task39-5-lifecycle`.
  If extending an existing harness instead, record its exact command and identify where the full
  startup-order/OpenList matrix runs. All Docker evidence must use the committed candidate. A
  harness that restarts Worker after activation cannot stand in for the new mandatory sequence.
- If durable registration/schema changes: additionally run
  `.venv/bin/python -m unittest tests.test_migration_rehearsal tests.test_upgrade_preflight` and
  prove previous-schema upgrade, already-admitted work preservation, no migration-time mutation and
  fail-closed incompatible-schema startup/recovery. Document the exact artifact migration command.

Unavailable Docker/external validation is reported with the real error, never converted into PASS
or silently skipped. No broad full-suite reruns are needed after an unchanged successful gate;
new changes or failures justify the necessary rerun. Developer reports all actual outcomes to B.

## Non-goals

- New transfer command/mode, overwrite fallback, cross-kind Resource↔Media transfers, bulk queue
  migration, universal rollback, automatic uncertain-effect replay or weakened lease/fence checks.
- A new scheduler, queue, repository authority, provider, generic runtime framework, distributed
  worker platform, secret store, hot secret rotation, identity/session system or token handoff.
- Automatic setup/activation or transfer submission; new scan/Preview/Organize semantics; general
  Configuration/Operations redesign. Preserve other worker roles and existing admitted work.
- Moving Slice Base, reopening passed Tasks or Slice 38, editing user/reference images, private
  `config/alist.json`, or declaring Slice PASS/CLOSED. After PASS B reevaluates RO-1–RO-9 and performs
  Slice Final; the prior Task 39.4 correction-return exception does not close this expanded scope.

## Developer Completion Report

### Changed Files

- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/application/direct_file_transfers.py`
- `tests/test_direct_file_transfers.py`
- `tests/test_media_library_transfers.py`

### Implemented

- Installed both transfer consumers before first Active and changed the resident boundary to claim
  by durable command, then reconstruct one exact revision/digest/library-kind context per attempt.
  Current Active remains new-admission authority; older valid pins continue without substitution.
- Preserved claims, lease renewal, mutation fences, checkpoints and uncertain-effect resolution;
  slow provider work also renews resident registration, and attempt-scoped adapters are closed.
- Made production Worker registration independent of Active and declared both transfer commands.
  Readiness separates process, registration/schema, current Active and per-command work readiness;
  Compose health now verifies the real registered transfer consumer without provider calls.
- Added actionable waiting evidence to API/Web transfer progress and Operations revisit. Refresh
  never resubmits, and unavailable pinned context remains durable with zero new mutation.
- Correction round 1: released reconstruction-blocked claims now update queue recency and are
  selected after other eligible admitted work, so one corrupt pin cannot starve later work.
  Readiness and transfer observation retain the last published binding and read durable progress
  while current Active is missing; new admission still refreshes and fails closed.
- Correction round 2: transfer-status GET routes now use a kind-pinned durable read projection when
  a restarted API has no process-local Active binding. The projection reads only persisted Task,
  transfer, item and Result state, preserves RBAC and Resource/Media isolation, performs no Storage
  access, and leaves new admission fail-closed. When Active is repaired, the same route converges
  back to the live binding and the admitted Task executes without resubmission.

### Tests and Results

- `python3 scripts/check_governance.py` — **PASS**.
- Correction regression tests for queue fairness and Active-outage progress/readiness — **PASS**.
- `.venv/bin/python -m unittest tests.test_direct_file_transfers tests.test_media_library_transfers tests.test_processing_worker_readiness` — **PASS**, 144 tests.
- `.venv/bin/ruff format --check mediaflow/interfaces/service_api.py mediaflow/infrastructure/sqlite_runtime.py tests/test_direct_file_transfers.py` — **PASS**.
- `.venv/bin/ruff check mediaflow/interfaces/service_api.py mediaflow/infrastructure/sqlite_runtime.py tests/test_direct_file_transfers.py` — **PASS**.
- `.venv/bin/python -m compileall -q mediaflow tests scripts` — **PASS**.
- `git diff --check` — **PASS**.
- `python3 -u scripts/docker_health_smoke_test.py --image mediaflow:task39-5-health` — **PASS**.
- `python3 -u scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task39-5-lifecycle-debug` — **PASS**.
- `python3 -u scripts/docker_files_transfer_impact_smoke_test.py --image mediaflow:task39-5-transfer` — **PASS**.
- `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-5-security` — **PASS**.
- Required focused Python gate — **PASS**, 273 tests.
- `.venv/bin/python -m unittest discover -s tests` — **PASS**, 1,850 tests, 7 existing
  external/optional-profile skips.
- Required focused Web gate — **PASS**, 80 tests; `cd web && npm test -- --run` — **PASS**,
  727 tests / 47 files.
- `cd web && npm run typecheck && npm run lint && npm run format:check && npm run build` — **PASS**.
- Required browser gate for Files and MediaLibrary — **PASS**, 61 Chromium tests.
- Ruff format/lint, compileall, `git diff --check`, governance and manifest/private-config audits —
  **PASS**.
- `python3 -u scripts/docker_files_transfer_lifecycle_smoke_test.py --image mediaflow:task39-5-lifecycle-debug`
  — **PASS**: containers first, checked activation, unchanged Worker identity, real local HTTP
  OpenList Move, slow request beyond stale threshold, one mutation and matching durable result.
- `python3 -u scripts/docker_health_smoke_test.py --image mediaflow:task39-5-lifecycle-debug` —
  **PASS**.
- `python3 -u scripts/docker_files_transfer_impact_smoke_test.py --image mediaflow:task39-5-validation`
  — **PASS**.
- `python3 -u scripts/docker_release_security_smoke_test.py --image mediaflow:task39-5-validation`
  — **PASS**.

### Decisions

Reused existing admission, pinning, claims, fences and Executor. Command-filtered claims apply to
the new lazy dispatcher while legacy single-service incompatibility evidence remains compatible.
The production image installs `.[openlist]` because real OpenList execution otherwise lacks its HTTP
adapter dependency. No durable schema change or migration was required.

### Remaining In-Slice Work

No additional implementation work is known inside this Task. B decides whether Slice RO-8/RO-9 and
the full Slice outcomes are satisfied.

### Risks / Deviations

All required committed-candidate Docker gates passed. Existing `docs/pics` delete/modify/untracked changes are preserved and excluded. No credentials,
`config/alist.json`, FFmpeg/FFprobe dependency or private path was added.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: f458646d3dac280b118a511c60ec53a5d3075d67
```

## B Review Result

Review round: 2 (2026-09-26). Reviewed the corrected implementation checkpoint below; current HEAD
`cca246a53058cd56cc39342cb975d38317bf6934` adds only the correction completion report to that
checkpoint. B independently reran the exact focused Python gate: **275 tests PASS** (94.826s), and
the exact focused Web gate: **80 tests / 5 files PASS**. Full Python regression passed **1,850 tests
with 7 existing optional/external skips**; full Web regression passed **727 tests / 47 files**;
the required browser selection passed **61 Chromium tests**. Ruff format/lint, compileall, Web
typecheck/lint/format/build, governance, committed-range whitespace and the Docker transfer lifecycle
gate all passed. The 27-file Task manifest contains no private configuration or unrelated image
changes; `config/alist.json` remains absent and the existing user image changes remain excluded.
The previous queue-fairness and same-process Active-outage defects are corrected, but Slice Final is
not reached because the current production restart path still reproduces the blocker below.

```text
Reviewed: d74822ce509512fcc10e5802bc6cc95602c77c3b..4c78687783a345c5b02a9fc30c342cf30db50864
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

- **P1 — API restart during a current-Active outage still hides durable transfer progress.**
  The correction bypasses Active refresh for a transfer GET at
  `mediaflow/interfaces/service_api.py:1400`, but the route still requires
  `binding.direct_transfers` / `binding.direct_media_transfers` at lines 5487 and 5662. Those
  services exist only when `_build_runtime_binding` receives a runtime revision. Reproduction used
  temporary SQLite, actual Local Storage and the real `MediaFlowApi`: checked-activate A, admit a
  ResourceLibrary Copy through the authenticated API, mark current Active unavailable while keeping
  the published A revision and admitted Task intact, then construct a new API instance over the same
  repositories (the normal API process/container restart condition). GET of
  `/api/v1/resource-libraries/source/files/transfers/{taskId}` returned **HTTP 503 /
  `configuration_unavailable` / `managed_active_unavailable`**, although the Task and its immutable
  pin remained durable. The same composition makes the MediaLibrary route fail at its parallel
  guard. This is reachable after an API restart during configuration recovery; the operator's Files
  progress poll or Operations revisit loses the promised waiting/outcome/recovery view and cannot
  verify whether resubmission is safe. It violates Slice RO-9 and AC-12, Scope 5's durable revisit
  and reconnect requirement, and this Task's progress/reconnect acceptance criterion. Make the
  authenticated ResourceLibrary and MediaLibrary transfer-status reads reconstruct a bounded,
  kind-pinned projection from durable Task/transfer state when no process-local Active binding
  exists, including after API restart. Preserve RBAC, cross-kind isolation, redaction, zero Storage
  access/mutation and fail-closed new admission; do not present a superseded snapshot as current
  Active. Add real-repository API regressions for both kinds covering outage plus API reconstruction,
  progress/recovery visibility, repaired-Active convergence and no refresh resubmission.
