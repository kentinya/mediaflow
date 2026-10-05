# Task 42.5 — Native task-item decisions and bounded failed-analysis recovery

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 42.5
Parent Slice: 42
Status: READY FOR B REVIEW
Task Base: 0370eada28e2a4911bedaa7cea7fa7eb18bc35be
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete RO-6 and its RO-2/RO-3/RO-7 recovery integration: an operator inspects a selected run's
failed/waiting/partial item, resolves its supported Recognition/Metadata/Classification/conflict
decision or explicitly retries eligible failed analysis, follows the bounded queued analysis,
reviews the exact resulting plan and separately authorizes mutation when needed, and sees linked
independent results in native V2. Successful/ignored siblings and unknown effects never replay.

## Why This Task Exists

Previous Task42.4 B review:

```text
Reviewed: d52ce9299671ab05141f64848b8475cd4db11126..73b171254f626f40364d910fe15583dd896e6da1; completion report at 0370eada28e2a4911bedaa7cea7fa7eb18bc35be
Decision: PASS
Slice Required Outcomes all satisfied: NO
Next: NEXT TASK
```

Fourth correction resolved the original legal Definition/API/Worker repause identity reproduction:
exactly three runs after two continuations and restart; admission links show the paused Task's
actual progress/results. Independent B full Python2180 (2173 passed/7 existing skips), focused
121/73/86/217/56, scope58 and safety19 PASS; full Web63 files/991 PASS; Files browser40 and actual
Python/Worker browser16 PASS. Required affected fake browser66 PASS/2 FAIL remains the same
independently Base-proven deep-link failures, not PASS. Python/Web quality/config/wheel smoke,
genuine Base42→44 preservation and Docker release-security PASS. Earlier failures/unavailable
attempts remain in Git/prior logs. Detailed full previous Task/report/PASS archive:
`/tmp/mediaflow-b-task42-4-r5-pass.md`; actual command/criterion evidence:
`/tmp/mediaflow-b42-4-r5-review-evidence.md`.

Immediately after PASS, B rechecked RO-1 through RO-7: RO-1 inventory/navigation, RO-2 authorized
linked queries/counts/history, RO-3 progress/detail/records/export and RO-4 live-file admission/return
are delivered; RO-5 controls/safe queued continuation/exact-Preview fallback is now complete. RO-6
native task-item decisions and failed-analysis recovery are not complete, including their required
new links/projections in RO-2/RO-3 and recovery integration in RO-7. RO-7's delivered read/admission/
control/privacy/restart behavior passes. No Contract issue waits for A; Slice remains ACTIVE and no
Slice Final is appropriate. New Task Base is the actual current committed report HEAD above;
42.4 Task Base and Slice Base remain immutable.

After four correction rounds B reassessed overall complexity: the resolved issue was at the shared
claim-fenced identity boundary, fixed using14 production lines and existing persisted links, with
no additional schema/queue/state machine. This next unit must reuse current review/recovery/Worker
services and minimal necessary projections rather than add another recovery framework or per-form
Task sequence. One coherent fifth Task covers the remaining task-item recovery journey.


Actual current code already has ProcessingCheckpoint, RecognitionReviewService,
MetadataReviewService, MetadataCorrectionService, ClassificationReviewService, ConfirmationService,
RecoveryAdmissionService, RecoveryContinuationService/WorkerService,
RecoveryBatchContinuationService and ManualRecoveryContinuationService. The retained Task/item
recovery API and resident processing Worker provide the safe execution boundary. The selected
Operations run currently displays item evidence and controls; typed V2 forms and end-to-end item
recovery are missing. Legacy Task detail links to `/review` (`TaskDetailPage.tsx:393–394`); the selected
`OperationsLanding.tsx` has RO-5 control/exact-Preview continuation but no RO-6 item decision or
failed-analysis command composition. `api-client.ts` lacks those task-item bindings.
Backend services and V1 handoff alone do not fulfill RO-6.

The remaining unit is one task-scoped diagnose → decide/analyze → reviewed execution → linked
outcome journey, including independently selected failed-analysis batches. Keep the existing
application gates and Worker engine; the decision families are alternatives within the same item
journey, not separate Tasks for individual forms/fields/tests. This is the fifth coherent Slice Task.

## Implementation Scope

```text
Existing checkpoint/review/recovery Domain → durable decision/attempt links → shared Application
→ typed task-scoped API → native V2 item forms/analysis/Preview/return → real Worker and Tests
```

### Operator journey

- **Entry:** selected run's paged items/evidence in `操作与任务`, supported Task/Job/item links and
  the existing failed Manual Organize result. Preserve current list filters, run, item and detail tab.
- **Visible state:** stage/blocker, durable item/checkpoint/decision, known steps/effects, certainty,
  retry safety and actual permitted actions. Distinguish waiting decision, admitted analysis,
  Worker waiting, Preview-ready, mutation admission and final outcome; analysis is not file success.
- **Action:** resolve the exact pending decision using legal choices; explicitly search/correct
  Metadata where supported; ignore where allowed; retry one eligible failed-analysis item or an
  explicitly selected bounded batch from this run. Review the exact plan and express execution/
  destructive intent only where required. No raw token/checkpoint/revision input or CLI/V1 handoff.
- **Success:** the saved decision remains non-executing; bounded analysis is admitted promptly and
  claimed by the real resident Worker. A separately authorized exact execution produces linked
  outcomes accessible from the original item/run, with successful siblings retained after reload.
- **Failure:** stale item/decision/source/plan, denied permission, missing historical pin/dependency,
  Provider/Storage failure, queue/readiness refusal and unknown response retain truthful durable
  state and correctable input. Batch children retain independent accepted/refused/waiting outcomes.
- **Recovery:** refresh exact durable command/attempt identity before any repeat; repair named
  prerequisites, return from Settings/Rules and recheck eligibility without historical repinning.
  Follow the original item and linked attempt/Preview/execution. Unknown mutation remains evidence/
  investigation/export only, never Retry/Execute or automatic reconciliation.

### Required behavior and boundaries

1. Compose bounded task/item recovery detail from explicit durable checkpoint/review/confirmation/
   continuation links. Resolve the exact original item and newest applicable linked decision,
   retaining earlier evidence. Do not load a global review inbox or join by names/time/source labels.
   Passive page reads/refresh/filter/export must not call Provider, create work or mutate Storage.
2. Add native typed forms for all RO-6 decision families through existing legal application choices:
   Recognition selection/ignore, Metadata candidate selection/correction/ignore, Classification
   decision and conflict resolution. Explain why each choice is legal, including target/operation/
   destructive implications where relevant. Preserve C identity and RecognitionType-bound policies.
   Bounded explicit Metadata search/correction may call the existing configured Provider; merely
   opening a page, polling or fetching saved candidates never initiates lookup.
3. Backend rechecks current RBAC, exact Task/item/checkpoint/decision versions, live SourceIdentity,
   pin and legal choices. Saving a decision is persistence-only and grants no mutation authority.
   Use optimistic rejection and existing duplicate protection; stale forms retain safe input and
   require a fresh deliberate submission. Auth/principal changes clear selections/forms/query cache.
4. Single eligible failed-analysis recovery and explicitly selected bounded failed-item batches
   reuse RecoveryAdmission/Continuation/Batch gates and real queued Worker processing. Selection
   binds exact original item/version, not a status query containing future failures. Handle mixed
   eligible/stale/successful/ignored/unknown selections independently on the server; display each
   accepted/refused child and its recovery action without discarding siblings. Preserve existing
   batch admission/restart behavior and limits; no reset-all-failed or batch auto-execution.
5. A meaningful explicit continuation may compose safe decision persistence and analysis admission
   using existing boundaries; avoid extra user clicks to carry internal request IDs between steps.
   HTTP coordinates/admit/reads; long analysis runs in the resident Worker with original immutable
   pin, source revalidation, checkpoints, leases/fences and restart semantics. Do not shell out to
   CLI, add a parallel queue, silently use current Active or retry unknown mutations.
6. Complete analysis → exact eligible Preview → separate explicit execution → original run/item
   outcome using existing manual recovery/Preview/execution authority where applicable. Expose the
   full exact reviewed plan before mutation; changed source/plan/authority rejects safely and leads
   to renewed review. No consumed one-shot reissue, revoked unattended grant bypass, implicit
   overwrite/delete/cleanup, or authority from a saved decision/execute boolean. Known partial
   effects only continue where the existing safety gate proves the specific next operation safe.
7. Persist and project original item → decision/recovery request → analysis attempt → Preview/
   execution/Result links. Reuse records; minimal additive fields/projections are permitted only
   where needed for this journey. Keep original Results inspectable, run counts truthful and
   independent child outcomes durable. Linked attempt failure cannot hide original success or
   detach the operator from the affected item; expose unsupported legacy evidence honestly.
8. Commands send once. Unknown/lost/5xx/malformed outcomes reconcile from exact durable identity
   before another explicit submission; a failed read cannot authorize replay. Use current run/item
   context, bounded polling/backoff/hidden-page behavior, narrow/keyboard/focus, reload/history and
   memory-only authentication. Compatible V1/API, Files/Preview/execution returns, native controls,
   transfers, Rules, Settings, Automation and Notifications remain functional.

Frozen: Slice Contract/Base, canonical requirements/Product Experience/Roadmap/reference image;
retired direct-file recovery endpoints; recognition/policy/Provider/operation semantics, Storage
confinement, destructive permission, immutable configuration authority, OrganizerExecutor-only
mutation and uncertain-effect prohibition. Do not generalize this into a global Review workspace
or recovery engine. If the current Contract cannot be met, identify its exact clause and return to B.

## Acceptance Criteria

- [ ] **AC-T1 — Native diagnosis and entry:** all current RO-6 item families are reachable from the
      selected run with stage/blocker/durable state/effect certainty/retry safety/backend actions;
      linked item/context survives navigation/auth/reload. Unknown effects are investigation-only.
- [ ] **AC-T2 — Complete supported decisions:** typed Recognition, Metadata/correction,
      Classification and conflict forms use actual legal choices/services, support applicable
      selection/ignore, reject stale/invalid choices and preserve useful input. No ordinary CLI,
      V1, raw internal-token/version entry or newly required policy/provider semantics.
- [ ] **AC-T3 — Decision safety:** saving never executes or grants authority; reads invoke no
      Provider/work/mutation. Explicit bounded search uses Provider abstraction and redaction.
      Current RBAC, source, pin and optimistic checks protect every command; C stays C.
- [ ] **AC-T4 — Single/mixed batch analysis:** actual API admission and resident Worker recover
      only explicitly selected eligible analysis items. Each accepted/refused/stale/unknown child
      remains durable and independently actionable; success/ignored/unknown and future failures
      never enter execution or replay. Lost Worker/claim/pin and restart have truthful next actions.
- [ ] **AC-T5 — Recovery reaches linked outcome:** supported decision/failed-analysis recovery
      reaches an exact reviewed Preview and separately authorized execution when appropriate;
      source/plan/authority changes refuse safely, destructive intent remains explicit, original
      item and linked Result are visible, and siblings/history/pin/limits survive Active A→B/restart.
- [ ] **AC-T6 — Unknown outcome and compatibility:** transport/5xx/malformed command responses
      lock repeat until durable reconciliation; failed reads preserve evidence. Principal isolation,
      filters/item/tab/return/back, narrow/keyboard and existing affected journeys remain usable.
- [ ] **AC-T7 — Real production proof:** Python-backed browser drives native decision → saved
      zero-mutation state → queued real Worker analysis → reviewed explicit execution → linked
      result; also proves single failed-analysis retry, mixed batch accepted/refused outcomes,
      success/unknown sibling exclusion and restart/auth return. Legal fixtures and timing hooks
      retain actual current production capabilities/authority; API-fixture-only paths are insufficient.
- [ ] **AC-T8 — T4 checkpoint:** required focused/integration/full/quality/security/package and
      affected migration evidence is honest, with totals/skips/unavailable/intermediate failures.
      No removed/weakened tests, hidden skips, real credentials, private config or unrelated edits.

## Required Tests

Temporary SQLite/media and synthetic Providers/local servers only. Never production data/services
or credentials. Record every attempt and actual skip/unavailable; unchanged serial reruns are allowed
without waiving unexplained failures. Run browser commands sequentially.

### Focused and integration

Extend coherent existing suites and a real Python/browser recovery harness where needed. Cover all
four legal decision paths and failed-analysis boundaries, stale/invalid/duplicate/concurrent commands,
current permissions, source/pin/dependency changes, explicit search, exact Preview/authority, known
partial/unknown effects, independent mixed batches, original/attempt linkage, Active A→B, restart/
claim loss/fences, zero-mutation decisions and zero-Provider reads. Report exact new-module commands.

```sh
.venv/bin/python -m unittest tests.test_recognition_review tests.test_metadata_review tests.test_metadata_correction tests.test_classification_review tests.test_conflict_resolution
.venv/bin/python -m unittest tests.test_processing_recovery_admission tests.test_recovery_continuation tests.test_recovery_batch tests.test_metadata_correction_continuation
.venv/bin/python -m unittest tests.test_processing_checkpoint tests.test_manual_operations_contract tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_execution_authorization tests.test_api_security
.venv/bin/python -m unittest tests.test_scope_continuation tests.test_task_pause_resume tests.test_task_persistence tests.test_operations_workspace tests.test_operations_run_inventory tests.test_operations_run_detail
.venv/bin/python -m unittest tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_unattended_grant tests.test_automation_definition_execution tests.test_processing_worker_readiness
```

From `web/`:

```sh
npm run test -- --run src/entities/operations src/features/operations src/features/library src/shared/api src/shared/navigation src/routes
npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/manual-organize.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/deep-link.spec.ts
npm run test:e2e -- tests/e2e/library-files.spec.ts
npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts
```

Extend this real Python harness/spec or add one cohesive real recovery spec under the same boundary
and run/report its exact command. Preserve the two independently Base-proven deep-link failures as
FAIL/PRE-EXISTING/UNRELATED only while unchanged; new affected failures have no waiver.

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
git diff --check 0370eada28e2a4911bedaa7cea7fa7eb18bc35be
sha256sum docs/pics/操作与任务.png
git check-ignore config/alist.json
git ls-files config/alist.json
rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml
```

Build a wheel with `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <temporary-output>`
and run `.venv/bin/python scripts/wheel_smoke_test.py <built-wheel>`. If persistence changes, create a
real Task-Base schema44 database through Base code and prove preservation of existing pins, consumed
authority, locks/ownership, decisions/continuations, original Results and links; incompatible/failed
upgrade fails closed. Prove real resident recovery after restart in the supported deployment boundary.
Docker may use isolated daemon-visible task-owned TMPDIR; record exact environment/resources/results.
Reference checksum stays `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`;
private config stays ignored/untracked/unstaged; audit full range/staged manifests without exposing it.

From `web/`:

```sh
npm run test -- --run
npm run typecheck
npm run lint
npm run format:check
npm run build
```

## Non-goals

- Changing/closing Slice, Contract/Base, canonical requirements, reference image or Roadmap.
- Global Review inbox, cross-task bulk review/recovery, arbitrary historical Reprocess, unbounded
  rescan/organize, new Providers/operations/policy semantics or retired direct-file API restoration.
- History deletion/retention, task rename/priority, Automation/Notification/dashboard redesign,
  distributed Worker, parallel queue/engine, shell continuation, long HTTP processing or V1 retirement.
- Reset-all-failed, automatic uncertain replay/reconciliation, batch auto-execution, stored-boolean
  authority, silent repinning/fallback or weakened destructive permission. P2 cleanup is not a Task.

## Developer Completion Report

### Changed Files

- Backend/API: `mediaflow/application/manual_recovery_continuation.py`, `mediaflow/application/operations_lifecycle.py`, `mediaflow/application/processing_checkpoint.py`, `mediaflow/application/recovery_batch.py`, `mediaflow/application/recovery_continuation.py`, `mediaflow/application/task_item_recovery.py`, `mediaflow/domain/security.py`, `mediaflow/final_cli.py`, `mediaflow/infrastructure/sqlite_runtime.py`, `mediaflow/interfaces/service_api.py`.
- Web: `web/src/entities/operations/__fixtures__/manual-operations.json`, `web/src/entities/operations/manual-operations-contract.test.ts`, `web/src/entities/operations/preview.test.ts`, `web/src/entities/operations/preview.ts`, `web/src/entities/operations/task-item-recovery.test.ts`, `web/src/entities/operations/task-item-recovery.ts`, `web/src/features/operations/ManualOperationsRouter.test.tsx`, `web/src/features/operations/OperationsLanding.tsx`, `web/src/features/operations/OrganizePreviewPage.tsx`, `web/src/features/operations/RunDetailTabs.test.tsx`, `web/src/features/operations/RunDetailTabs.tsx`, `web/src/features/operations/TaskDetailPage.tsx`, `web/src/features/operations/TaskItemRecoveryPanel.test.tsx`, `web/src/features/operations/TaskItemRecoveryPanel.tsx`, `web/src/features/operations/recovery-batch-session.ts`, `web/src/features/operations/run-detail-query.ts`, `web/src/shared/api/api-client.ts`, `web/src/shared/api/auth-store.test.ts`, `web/src/shared/api/auth-store.ts`, `web/src/shared/auth/principal-session-data.ts`.
- Harness/tests: `scripts/operations_inventory_harness.py`, `tests/test_manual_operations_contract.py`, `tests/test_recovery_batch.py`, `tests/test_recovery_continuation.py`, `web/tests/e2e/operations-inventory.python.spec.ts`.
- `TASK.md` — Developer Completion Report.

### Implemented

- Added task-scoped, bounded recovery detail, explicit Metadata search, and version-fenced Recognition, Metadata, Metadata correction, Classification, conflict and ignore decisions through existing review services. Reads do not call Providers; decision persistence does not grant execution authority.
- Composed an eligible decision with existing safe DryRun admission and durable Worker continuation. Checkpoint projections admit only structured, durable zero-effect states; unknown effects remain investigation-only. Corrected Worker parser input to use the ResourceLibrary-relative source path rather than its Storage-qualified display label.
- Added single-item and explicitly selected batch recovery to native V2 run detail. Batch commands keep one browser-persisted request UUID, bind each item to its captured checkpoint, reconcile an uncertain response against the same durable batch, and preserve independent accepted/refused outcomes.
- Connected completed analysis to existing manual recovery Preview and separately authorized execution. Preview shows the exact Storage-relative target composed by the reviewed plan, without disclosing a host root, and links the resulting execution and Result back to the original item.
- Replaced the batch result's root-relative anchor with native V2 navigation to the exact linked Task detail. The return context keeps the original run, submitted list/detail state and exact source item, and the Task detail's return action restores that item.
- Added principal-session cleanup registration for recovery batch commands. Explicit disconnect and direct replacement of an active principal clear the persisted batch hint; page reload and the rejected-authority/auth-return path retain the exact ID for durable reconciliation. API tokens remain memory-only.
- Added a real Python API/SQLite/Worker harness and browser coverage for decision recovery, single retry, mixed batch outcomes, restart/auth return, zero-mutation analysis, separately authorized execution, linked-analysis return and disconnect/account-switch recovery.

### Tests and Results

All commands below passed unless marked otherwise. Python commands ran from the repository root; npm commands ran from `web/`.

- PASS — `.venv/bin/python -m unittest tests.test_recognition_review tests.test_metadata_review tests.test_metadata_correction tests.test_classification_review tests.test_conflict_resolution` — 34 tests.
- PASS — `.venv/bin/python -m unittest tests.test_processing_recovery_admission tests.test_recovery_continuation tests.test_recovery_batch tests.test_metadata_correction_continuation` — 105 tests.
- PASS — `.venv/bin/python -m unittest tests.test_processing_checkpoint tests.test_manual_operations_contract tests.test_manual_organize_execution tests.test_v2_manual_organize tests.test_execution_authorization tests.test_api_security` — 117 tests.
- PASS — `.venv/bin/python -m unittest tests.test_scope_continuation tests.test_task_pause_resume tests.test_task_persistence tests.test_operations_workspace tests.test_operations_run_inventory tests.test_operations_run_detail` — 179 tests.
- PASS — `.venv/bin/python -m unittest tests.test_automation_admission tests.test_automation_job_fencing tests.test_automation_unattended_grant tests.test_automation_definition_execution tests.test_processing_worker_readiness` — 71 tests.
- PASS — `.venv/bin/python -m unittest discover -s tests` — 2,183 tests, 7 skipped, 0 failures.
- PASS — `.venv/bin/python -m unittest tests.test_release_security tests.test_release_validation tests.test_migration_rehearsal tests.test_upgrade_preflight` — 19 tests.
- PASS — `python3 scripts/check_governance.py`; `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .`; `.venv/bin/python -m compileall -q mediaflow tests scripts`; `.venv/bin/python -m pip check`.
- PASS — `.venv/bin/python -m mediaflow.cli --config config/strategy.example.json config validate` and `.venv/bin/python -m mediaflow.cli --config config/mediaflow.phase13.2.example.json config validate`.
- PASS — `.venv/bin/python scripts/docker_release_security_smoke_test.py` — isolated four-service release-security smoke.
- PASS — `.venv/bin/python -m pip wheel . --no-deps --no-build-isolation -w <temporary-output>` and `.venv/bin/python scripts/wheel_smoke_test.py <built-wheel>` — wheel smoke covered CLI/config, backup/restore, migration rehearsal and upgrade preflight.
- PASS — focused Web command from Task: `npm run test -- --run src/entities/operations src/features/operations src/features/library src/shared/api src/shared/navigation src/routes` — 44 files / 704 tests.
- PASS — full Web suite: `npm run test -- --run` — 65 files / 997 tests.
- PASS — `npm run test:e2e -- --config=playwright.python.config.ts tests/e2e/operations-inventory.python.spec.ts` — 19/19 tests, including both correction regressions and same-principal restart/auth-return recovery.
- PASS — `npm run test:e2e -- tests/e2e/library-files.spec.ts` — 40/40 tests.
- FAIL / PRE-EXISTING / UNRELATED — `npm run test:e2e -- tests/e2e/operations.spec.ts tests/e2e/manual-organize.spec.ts tests/e2e/manual-operations.spec.ts tests/e2e/deep-link.spec.ts` — 66 passed, 2 failed. Base-proven unchanged failures: `deep-link.spec.ts:211` cannot find the “Review & Recovery” link; `deep-link.spec.ts:481` expects the retired V1 handoff heading. Neither file changed in this Task.
- PASS — `npm run typecheck`, `npm run lint`, `npm run format:check` and `npm run build`.
- PASS — `git diff --check` and `git diff --check 0370eada28e2a4911bedaa7cea7fa7eb18bc35be`.
- PASS — `sha256sum docs/pics/操作与任务.png` matched `a8a5dc329891207b0feb487fa60690e97072d11b73da1136324459bf79915f86`; `git check-ignore -v config/alist.json` confirmed it is ignored and `git ls-files -- config/alist.json` returned no tracked file.
- PASS — `rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml` returned no matches.
- FAIL (initial attempt, recovered) — the concurrent two-file component run had 25/26 tests pass because a storage-notice test could not find its batch region. Its isolated rerun passed, the serial two-file rerun passed 26/26, and the required focused and full Web suites passed afterward.
- FAIL (initial attempt, recovered) — the new account-switch browser test expected the resubmit control before clicking the visible “核对这个批次” reconciliation action. After correcting the test sequence, its isolated run and final 19-test Python-backed browser suite passed.

### Decisions

- Kept the MediaLibrary-relative destination field for context and added a separate Storage-relative planned path for the exact reviewed target. It contains no host root and prevents Preview from displaying a path different from the one OrganizerExecutor will use.
- Reused existing recovery admission, checkpoint, Worker, manual Preview and one-shot execution authority. No schema or second queue was added.
- Made the batch UUID caller-stable and reuse conditional on an exact Task, actor and item/checkpoint selection match. Duplicate delivery returns the existing durable batch and never creates a second batch job.
- Reused the existing TanStack V2 Task detail route and bounded `returnOps` context instead of adding another route or API.
- Kept batch hints in sessionStorage so the same browser session can reconcile after reload, while registering feature-owned cleanup with the shared auth lifecycle. No API token or token-derived key is stored.

### Remaining In-Slice Work

No separate in-Slice implementation work was identified during this Task. B must reevaluate the Slice Required Outcomes after reviewing this checkpoint; this report does not assess Slice completion or plan a next Task.

### Risks / Deviations

- The two deep-link browser failures above remain `FAIL / PRE-EXISTING / UNRELATED`; no assertion was changed or suppressed.
- Python tests emitted SQLite `ResourceWarning` messages for unclosed test connections. Vitest emitted jsdom scroll/navigation notices. Vite build succeeded with an approximately 1.1 MB chunk-size warning.
- The initial and intermediate failures listed above were rerun as recorded; no failed test was hidden or waived except the two unchanged Base-proven deep-link failures, which remain for B's review.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 0e8e93f0d080006f98f3bdcb24882a5767669453
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```
