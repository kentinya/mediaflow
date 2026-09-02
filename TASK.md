# Task 25.8 — Per-mutation unattended authority enforcement

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 25.8
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: READY FOR B REVIEW
Task Base: f1fd94252ca012210715c8f76afe1f52aa535de0
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Close the remaining Slice 25 `RO-5` and `RO-6` P1 safety gap by enforcing the current persistent
unattended grant and granting-principal permission immediately before every actual Storage mutation
inside one scheduled automatic-organization item. If authority becomes invalid after an earlier
effect, the next mutation is refused and the existing TaskItem/Result/checkpoint journey records the
completed, unperformed and uncertain effects truthfully without automatic replay.

## Why This Task Exists

A's Final Review found that production composition performs a live authority check only once per
media item. `MediaOrganizerService.process_file()` calls `before_execute` immediately before
`OrganizerExecutor.execute()` (`mediaflow/application/media_organizer.py:400-402`), but one Executor
invocation may then create destination directories, execute multiple attachment operations, execute
the primary operation and delete source-directory entries
(`mediaflow/application/organizer.py:473-551,593-708`). Cross-Storage Move and rollback can also
contain more than one mutating Storage call.

The existing correction evidence proves current-permission and grant revalidation between sibling
items, not between mutations inside one item. Revocation or permission loss after an attachment,
target write or primary effect can therefore leave later not-yet-performed mutations unchecked.
This violates the Slice's explicit live-authority boundary and makes the prior Closure Packet's
per-effect statement untrue.

This is one coherent high-risk correction because the authority hook, OrganizerExecutor mutation
sequence, Worker composition and durable per-item outcome must agree. A test-only assertion or a
second check around the outer Executor call would not close the gap.

## Implementation Scope

```text
Application orchestration
→ OrganizerExecutor mutation boundary
→ unattended live-authority callback
→ ExecutionResult / TaskItem / Result / Processing Checkpoint
→ production Worker composition
→ tests
```

- Add one optional, fail-closed mutation-authority hook owned and invoked by
  `OrganizerExecutor`. Scheduled automatic organization supplies the hook from the existing
  `UnattendedExecutionGrantService.assert_live(job, definition)` behavior; non-scheduled callers do
  not gain unattended authority and retain their existing admission semantics.
- Invoke the hook immediately before each actual mutating Storage call that has not yet begun,
  including:
  - destination directory creation;
  - every attachment Move/Copy/HardLink/SoftLink operation;
  - the primary same-Storage Move/Copy/HardLink/SoftLink operation;
  - cross-Storage target writes and the later source delete as distinct mutation boundaries;
  - every source-directory cleanup file or directory delete;
  - every rollback/compensation write, move or delete that would otherwise run after a failure.
- A Storage call already in progress remains an in-flight external call and is not claimed to be
  force-interruptible. Once it returns, authority must be read again before the next mutation; a
  once-per-item, once-per-Executor-call or cached permission answer is insufficient.
- Keep the hook descriptor, if one is introduced, internal, bounded and derived only from the
  accepted `OrganizePlan` and current Executor step. API, Web, Automation definitions and Jobs must
  not supply arbitrary paths, operations or mutation commands through it.
- Preserve the current pre-Task `authorize()` gate and the exact grant/Preview/definition/snapshot/
  ResourceLibrary/source-scope/run-mode/workload binding. Per-mutation checks are an additional
  dynamic gate, not a replacement for admission or plan validation.
- Treat live-authority refusal before the first mutation as a verified zero-effect failure. Treat
  refusal after verified effects as a partial outcome with the exact completed operations retained;
  retain uncertain evidence if an earlier Storage call was attempted but could not be verified.
  No later mutation, cleanup, rollback or sibling replay may run merely to make the item appear
  complete.
- Preserve the stable unattended-authority category, bounded durable state, retry safety and one
  explicit recovery action through `MediaOrganizerItemResult`, persistent Result, TaskItem,
  Processing Checkpoint, Automation occurrence summary and existing API/Web projections. Do not
  misclassify a live-authority refusal as an ordinary Storage failure.
- Preserve OrganizerExecutor as the only application component that invokes mutating Storage
  methods. Scanner, Parser, Recognition, Metadata, Naming, Classification, Planner, Preview,
  Scheduler and read/history projections remain zero-mutation.
- Preserve existing operation, conflict, capability and destructive rules. The hook grants no
  Overwrite, Delete, source cleanup, rollback, operation fallback or out-of-scope authority; those
  actions remain available only when their existing independent policy and safety gates permit
  them.
- Add focused unit and production-composition evidence for intra-item revocation/current-permission
  loss. Use temporary Local roots and deterministic fakes only; no production Storage, Provider
  credentials or user media.

Frozen unless an Acceptance Criterion cannot be met without a narrow compatible change, which must
be reported:

- Slice User Goal, Required Outcomes, Required Surfaces, Safety Invariants, Explicitly Deferred and
  Base SHA;
- Automation Task Definition, Preview eligibility, grant creation/revocation, Scheduler due
  emission, Job pinning/capacity, API/Web grant journey and schema 31 persistence;
- RecognitionTypePolicy ownership, conflict resolution, Storage capability semantics and the
  planned operation;
- manual/remote one-shot execution admission and its API/Web journey;
- automatic replay of uncertain effects, universal compensation, historical rollback, distributed
  leases and forced interruption of an in-flight external Storage call.

## Acceptance Criteria

- [ ] 1. Scheduled automatic organization passes one live unattended-authority hook into the real
      `OrganizerExecutor`; scan-only, scan-and-plan, Preview/DryRun and read paths never invoke it
      and remain zero-mutation.
- [ ] 2. The hook re-reads the active grant, exact persisted Preview linkage and the granting
      principal's current `grant_unattended_execution` permission. It is invoked immediately before
      every not-yet-started mutating Storage call and does not use a cached admission result.
- [ ] 3. Destination directory creation, each attachment operation, the primary operation,
      cross-Storage target write and source delete, every cleanup delete, and every rollback/
      compensation mutation are all covered. A focused mutation-sequence test fails if any one of
      these paths omits the hook.
- [ ] 4. A revoked/missing/mismatched grant, removed/disabled/downgraded principal or unavailable/
      malformed current permission authority before the first mutation produces no Storage
      mutation and retains the existing fail-closed Job/TaskItem/Result recovery semantics.
- [ ] 5. In one item containing at least one attachment plus a primary operation, revoking the
      grant or current permission after the first verified effect prevents the next operation.
      The first effect remains truthfully recorded, the untouched source/destination bytes remain
      unchanged, and no automatic replay occurs after authority is restored.
- [ ] 6. In a cross-Storage Move, invalidating authority after the verified target write but before
      source deletion leaves the source intact, records the target copy as a completed partial
      effect, refuses cleanup/rollback mutations that lack live authority and exposes an
      investigation-only recovery path.
- [ ] 7. When a primary Move succeeds but authority becomes invalid before source-directory
      cleanup, no ignored file or directory is deleted. The completed primary effect and skipped
      cleanup boundary are durably distinguishable; the item is not reported as full success.
- [ ] 8. Rollback/compensation never bypasses the dynamic gate. If authority remains valid, existing
      rollback policy behavior is unchanged; if it becomes invalid, no new rollback mutation occurs
      and the remaining effect state is reported as partial or uncertain rather than fabricated as
      rolled back.
- [ ] 9. A live-authority refusal inside OrganizerExecutor retains a stable unattended-authority
      failure category, bounded secret-free message, accurate completed operations/effect certainty,
      correct retry safety and exactly one explicit next action in Result and Processing Checkpoint.
- [ ] 10. Successful scheduled Move/Copy/HardLink/SoftLink, attachment and configured cleanup paths
      still complete when authority remains valid. Unsupported capabilities and Manual/Overwrite
      conflicts still fail before mutation with no fallback or authority widening.
- [ ] 11. Manual organization, one-shot remote organization and direct OrganizerExecutor callers
      remain backward compatible and do not require or receive unattended authority. Their existing
      mutation, result and rollback tests continue to pass.
- [ ] 12. RecognitionType C remains C through scheduled planning, execution, Result and checkpoint
      evidence while downstream A policy ownership remains visible.
- [ ] 13. Grant, permission, mutation-hook, Result, checkpoint, audit, log and API/Web evidence
      contains no bearer token, token environment value, credential, authorization header, cookie,
      private endpoint or unbounded raw exception.
- [ ] 14. No schema migration is expected. If implementation proves one unavoidable, stop and
      report the reason before changing schema; do not silently move beyond runtime schema 31.
- [ ] 15. The Task Base..Head diff contains only this correction, its tests and the Developer
      Completion Report. It does not edit `SLICE.md`, Roadmap, Progress, canonical requirements or
      CURRENT product/architecture claims.
- [ ] 16. All T4 focused, integration, full-regression, packaging, private-config and safety gates
      are run and reported with honest PASS/FAIL/SKIP/UNAVAILABLE results.

## Required Tests

Focused authority and execution tests:

- Add a focused test module or coherent cases that exercise the real OrganizerExecutor mutation
  sequence with an observable live hook. It must cover directory creation, multiple attachment
  operations, primary operation, cross-Storage Move write/delete separation, cleanup deletes and
  rollback mutations.
- Add a production-composition test through
  `AutomationWorker → DefinitionScopedExecutionService → MediaOrganizerService → OrganizerExecutor`
  that changes the real configured granting principal or revokes its grant after one verified
  mutation inside a single item. Assert source/target bytes, mutation order, Result, TaskItem,
  Processing Checkpoint, occurrence summary and no replay after permission restoration.
- Run:

```text
./.venv/bin/python -m unittest \
  tests.test_automation_definition_execution \
  tests.test_automation_authorized_execution_matrix \
  tests.test_automation_preview_grant_gate \
  tests.test_automation_unattended_grant \
  tests.test_configuration_snapshot \
  tests.test_processing_checkpoint \
  tests.test_organizer \
  tests.test_attachments \
  tests.test_source_directory_cleanup \
  tests.test_organizer_rollback
```

Related regression:

```text
./.venv/bin/python -m unittest \
  tests.test_automation_definition_occurrence \
  tests.test_automation_task_definition_preview \
  tests.test_automation_api \
  tests.test_operator_ui \
  tests.test_api_security \
  tests.test_manual_organize_execution \
  tests.test_execution_authorization \
  tests.test_final_integration
```

Full regression:

```text
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

- Run the full regression from the primary worktree and from a clean `git archive` of Task Head
  with the archive itself as the working directory. Report totals and skips separately. Any
  primary-worktree failure attributed to ignored local configuration must be reproduced at Task
  Base or otherwise proven unrelated; do not call the contaminated run PASS.

Quality and safety gates:

```text
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
./.venv/bin/python -m compileall -q mediaflow tests scripts
./.venv/bin/pip check
./.venv/bin/mediaflow --config config/strategy.example.json config validate
./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate
```

- Verify runtime schema remains 31 and run the relevant schema-marker/migration regression even
  though no schema change is expected.
- Build a wheel with `./.venv/bin/pip wheel . --no-deps --no-build-isolation` and run isolated
  `scripts/wheel_smoke_test.py`. Report `python -m build` as UNAVAILABLE if this environment still
  lacks its executable module rather than hiding the substitution.
- Run a forbidden runtime dependency scan for FFprobe/FFmpeg references, Markdown relative-link
  validation for changed documents, `git diff --check` and `git diff --cached --check`.
- Confirm `config/alist.json` and `config/strategy.json` remain ignored, untracked and unstaged.
  Scan Task Base..Head for credential-shaped values and private endpoints.
- Falsification evidence must show:
  - replacing the per-mutation hook with the old once-per-item check makes the intra-item test fail;
  - skipping the hook before cross-Storage source delete, cleanup or rollback makes the relevant
    focused test fail;
  - authority loss after one attachment or target-write effect prevents the next mutation and is
    not reported as zero-effect, full success or an ordinary Storage failure;
  - restoring authority does not automatically replay the partial item.
- Report real Scheduler endurance/process-stop, production SMB/OpenList/S3/R2, Provider credential
  and destructive acceptance gates as PASS/FAIL/SKIP/UNAVAILABLE. They may remain SKIP/UNAVAILABLE
  in this offline environment; never use production data or credentials.

## Non-goals

- Any edit to the Slice Contract, Base SHA, Roadmap, Progress, canonical requirements,
  Product Experience or Architecture documentation.
- Rewriting the stale Slice Closure Packet. B will run Slice Final and replace it only after this
  Task passes.
- A new grant type, permission, UI/API action, identity-management product, token store or schema
  migration.
- Requiring another interactive Preview or Execute click for every occurrence.
- Persisting or reusing the original Preview's per-file plans for later scheduled runs; each run
  continues to build and validate the normal current plan under its pinned snapshot.
- Changing Scheduler occurrence semantics, AutomationJob admission, grant eligibility, Preview
  staleness, definition editing, policy ownership, conflict strategy or Storage capabilities.
- Granting Overwrite, Delete, source cleanup, rollback, fallback or broader path authority.
- Forced interruption of an in-flight external Storage call, automatic uncertain-effect replay,
  universal compensation, historical rollback or distributed leases.
- P2/P3 cleanup, copy polish, unrelated refactoring or optional proof beyond the required
  falsification cases.

## Developer Completion Report

### Changed Files

- `mediaflow/application/organizer.py`
- `mediaflow/application/media_organizer.py`
- `mediaflow/application/automation_definition_execution.py`
- `mediaflow/application/failure_explanation.py`
- `mediaflow/domain/organizer.py`
- `tests/test_organizer_mutation_authority.py` (new)
- `tests/test_automation_definition_execution.py`
- `tests/test_automation_authorized_execution_matrix.py`
- `tests/test_configuration_snapshot.py`
- `TASK.md`

### Implemented

- Added an optional fail-closed `mutation_authority` hook to the real
  `OrganizerExecutor` and invoked it immediately before every not-yet-started
  mutating Storage call with a bounded plan/step descriptor: destination
  directory creation, every attachment operation, the primary operation,
  cross-Storage target write and source delete, cleanup file/directory deletes,
  and rollback/compensation mutations.
- Scheduled automatic organization now supplies the hook from
  `UnattendedExecutionGrantService.assert_live(job, definition)` through
  `DefinitionScopedExecutionService` and `MediaOrganizerService`; DryRun,
  scan-only, scan-and-plan, read, manual and remote one-shot paths never invoke
  it and retain their existing semantics.
- A live-authority refusal is converted by the executor into a truthful
  `ExecutionResult`: zero verified effect is `FAILED` with certainty `none`;
  refusal after verified effects is `PARTIAL` with exact completed operations
  and certainty `verified_complete`; cross-Storage copy-before-delete refusals
  retain the verified copy as a completed partial effect. No cleanup, rollback
  or sibling replay runs merely to make the item appear complete.
- Rollback and cleanup paths re-read authority before each mutation. Authority
  loss there stops further mutation and is reported as partial/refused rather
  than fabricated rollback or ordinary Storage failure, using stable
  `DirectoryCleanupStatus.REFUSED` / `RollbackStatus.REFUSED` evidence.
- Failure classification and sanitization now emit the stable bounded
  `unattended_authority` category with one explicit next action through
  TaskItem error, persistent Result, Processing Checkpoint and occurrence
  projections. No bearer token, credential, private endpoint or raw adapter
  exception enters evidence or logs.

### Tests and Results

- Focused authority/execution suite:
  `./.venv/bin/python -m unittest tests.test_automation_definition_execution
  tests.test_automation_authorized_execution_matrix
  tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant
  tests.test_configuration_snapshot tests.test_processing_checkpoint
  tests.test_organizer tests.test_attachments
  tests.test_source_directory_cleanup tests.test_organizer_rollback
  tests.test_organizer_mutation_authority`
  → PASS, 171 tests.
- Related regression suite:
  `./.venv/bin/python -m unittest tests.test_automation_definition_occurrence
  tests.test_automation_task_definition_preview tests.test_automation_api
  tests.test_operator_ui tests.test_api_security
  tests.test_manual_organize_execution tests.test_execution_authorization
  tests.test_final_integration`
  → PASS, 140 tests.
- Full regression from the primary worktree:
  `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
  → PASS, 1124 tests, 7 skips.
- Full regression from a clean archive of the Task Head (tracked files at the
  implementation checkpoint plus the completion report, run with the archive as
  the working directory): PASS, 1124 tests, 7 skips.
- Ruff lint and format, `compileall`, `pip check`, both example configuration
  validations, Markdown relative-link check, forbidden FFprobe/FFmpeg scan,
  credential-shaped diff scan and `git diff --check`: PASS.
- Schema/migration regressions (`tests.test_migration_rehearsal`,
  `tests.test_upgrade_preflight`): PASS; runtime schema remains 31; migration
  required NO.
- Wheel build plus isolated installed-wheel smoke:
  `./.venv/bin/pip wheel . --no-deps --no-build-isolation` +
  `scripts/wheel_smoke_test.py` → PASS, schema 31.
- `./.venv/bin/python -m build`: UNAVAILABLE (this virtualenv has no executable
  `build.__main__`); the approved `pip wheel` substitute passed.
- Real Scheduler endurance/process-stop, production SMB/OpenList/S3/R2,
  Provider credentials and destructive acceptance gates:
  SKIP / UNAVAILABLE in this offline environment; no production Storage,
  Provider credentials or user media were used.

### Decisions

- The authority hook is owned by `OrganizerExecutor` and passes only the
  accepted plan plus an internal bounded boundary label. No API/Web/Job input
  can supply paths, operations or mutation commands through it.
- Refusals are converted to `ExecutionResult` inside the executor so completed
  effects and retry safety survive in the durable TaskItem/Result/checkpoint
  journey instead of being lost in a generic exception path.
- `DirectoryCleanupStatus.REFUSED` and `RollbackStatus.REFUSED` were added as
  string-only domain evidence so a skipped cleanup or refused rollback is
  durably distinguishable from success, safe-stop or ordinary failure without a
  schema migration.
- Per-item authority failures use the stable `unattended_authority` failure
  category; the specific grant/permission code remains visible on pre-Task
  admission and in bounded executor evidence where useful.
- Existing between-item tests were updated to revoke at the per-mutation
  boundary count instead of the old once-per-item call count.

### Remaining In-Slice Work

- No remaining work is known inside this Task. The stale Slice Closure Packet
  reconciliation and any Slice-level review decision belong to B/A.

### Risks / Deviations

- The primary worktree full and related regressions pass at Task Head. An
  earlier related-regression failure from stale ignored root `.mediaflow`
  managed-activation state was reproduced as environment-only; the same test
  passes after refreshed ignored local state and in the clean archive.
- `config/alist.json` and `config/strategy.json` remain ignored, untracked and
  unstaged; no credential-shaped or private-endpoint values were introduced in
  the Task Base..Head diff.
- Real external-service and destructive gates remain SKIP/UNAVAILABLE as
  reported above.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: d4da92879b99f1c44ddd717fba1a26e4b0a73493
```

## B Review Result

```text
Reviewed: [Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Corrections remain in Task 25.8. A PASS returns
Slice 25 to `READY FOR A REVIEW`; B then runs Slice Final and replaces the stale Closure Packet
before handing the Slice back to A.
