# Task 25.7 — Preview-gated unattended authority and live permission revalidation

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 25.7
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: READY FOR B REVIEW
Task Base: e9f9baf24a6616a47ec651f17ef7eed57428cf7d
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Close both P1 blockers from A Final Review as one coherent unattended-authority lifecycle: an
operator can create a persistent grant only from current, exact, acceptable Automation Preview
evidence, and every automatic-organization admission and not-yet-performed effect revalidates the
granting subject's current unattended permission. This completes the remaining Slice 25 `RO-2`,
`RO-5`, `RO-6` and `RO-7` behavior without changing the normal media pipeline or granting any
destructive authority.

## Why This Task Exists

The current API checks request RBAC and the Active configuration revision but calls
`UnattendedExecutionGrantService.grant()` without consulting persisted Preview evidence
(`mediaflow/interfaces/service_api.py:826-860`). The Operator Web renders the grant action before it
loads Preview history (`mediaflow/interfaces/operator_ui.py:2246-2268,2322-2354`). An authorized API
caller can therefore skip the Contract's Validate/Test → exact Preview/DryRun → explicit unattended
grant sequence.

The runtime does re-read the persistent grant immediately before an effect, but
`UnattendedExecutionGrantService.assert_live()` checks only grant state and its pinned
definition/scope/mode/limit/configuration tuple
(`mediaflow/application/unattended_execution.py:347-369,450-511`). The stored
`granting_principal` is never resolved against the current configured permission authority. Removing,
disabling or downgrading that subject after the grant therefore cannot stop the next mutation.

These are not independent feature requests: together they define whether one persistent unattended
authority is valid when created and remains valid when consumed. The correction must be shared by
Application, API, Web and Worker rather than implemented as transport-only checks. It remains inside
the existing grant, Preview, Task/TaskItem/Result and OrganizerExecutor boundaries and does not
require a new identity-management product.

## Implementation Scope

```text
Domain → Persistence → Application → Runtime composition → API → Web → Tests
```

- Domain/Application — define one bounded, deterministic unattended-grant eligibility result over
  an explicitly selected persisted Preview. It must bind the Preview identity, definition
  fingerprint, Active configuration revision/version/digest, ResourceLibrary/Storage, normalized
  source scope, automatic-organization mode and effective workload bound to the requested grant.
- Application — require `previewId` at shared grant admission and re-read that Preview at the
  creation boundary. Evidence is eligible only when it is current, zero-mutation, exact for the
  requested Active definition/configuration and free of analysis failures, unavailable state,
  boundary errors, stale items or item blockers. Benign non-executable discovery facts such as
  excluded, currently unstable, truncated-by-limit or an empty current scope may remain visible and
  do not themselves grant those items mutation authority; every item that the Preview presents as
  executable must have a successful plan with no blocker.
- Application/Persistence — durably link the admitted grant and its secret-free audit/projection to
  the exact Preview evidence so the relationship survives reload. Use existing persistence where it
  can represent the fact without ambiguity; if a new column or constraint is necessary, use one
  additive schema migration with rollback-safe migration rehearsal and updated schema markers.
- Application — define a read-only current-permission authority for a principal ID and
  `grant_unattended_execution`. `authorize()` must consult it before automatic work constructs a
  Task, adapter, Provider or Storage pipeline, and `assert_live()` must consult it again immediately
  before every not-yet-performed effect. Removed, disabled, downgraded, malformed or unavailable
  current authority fails closed. A Job-pinned snapshot, the grant-time principal object or a
  once-per-run cached answer is not current permission evidence.
- Runtime composition — wire API and definition-scoped Worker execution to the same permission
  semantics backed by the existing configured API-principal definitions/roles. Direct service tests
  may inject a deterministic fake, but production composition must not default automatic mutation to
  allowed when the authority is missing. Permission lookup needs only principal identity and roles;
  it must not persist, return or log bearer tokens or resolved environment secret values.
- Application/Task evidence — a permission-invalid or permission-authority-unavailable occurrence
  before Task creation leaves bounded Job/occurrence failure evidence and no pipeline side effects.
  Permission loss between items preserves completed sibling effects and Results, refuses the next
  item before OrganizerExecutor, and leaves that TaskItem/Result/checkpoint with durable state,
  retry safety and exactly one explicit recovery action. It never automatically replays a completed
  or uncertain effect.
- API — make the existing grant route require the explicit reviewed `previewId` and return the same
  application eligibility, Preview linkage, current-permission state, error and recovery projection
  used elsewhere. Missing, unknown, cross-definition, stale, failed, unavailable, blocker-bearing or
  concurrently invalidated evidence fails before a grant/audit row is created. Existing RBAC,
  optimistic Active revision binding, explicit confirmation and bounded secret-free errors remain.
- Web — load and render the latest exact Preview and grant eligibility before presenting an enabled
  grant action. Show the selected Preview identity/status/binding, why grant is unavailable, and the
  single recovery action to run or inspect a fresh Preview. Confirmation submits that exact
  `previewId`; a stale/change race is rejected by the shared Application service. After reload, show
  the durable Preview linkage and current-permission validity, while revoke remains independently
  available for an existing grant.
- Tests — add non-vacuous admission, concurrency, reload, permission-loss, per-item independence,
  API-bypass, Web journey, zero-mutation, redaction and production-wiring evidence described below.

Frozen unless an Acceptance Criterion cannot be met without a narrow change, which must be reported:

- Slice User Goal, Required Outcomes, Required Surfaces, Safety Invariants, Explicitly Deferred and
  Base SHA;
- Scheduler due evaluation/emission, AutomationJob capacity/idempotency, definition schedule
  enable/disable and immutable Job configuration pinning;
- Scanner, Parser, Recognition, Metadata, Naming, Classification, conflict semantics, OrganizePlan
  and OrganizerExecutor operation/mutation ownership;
- manual/remote one-shot authorization, destructive Overwrite/Delete/cleanup authority, operation
  fallback and existing recovery admission semantics;
- configured API role meanings. `GRANT_UNATTENDED_EXECUTION` remains admin-only; do not add a new
  identity administration surface, credential store or permission-management API.

## Acceptance Criteria

- [ ] 1. Grant admission requires an explicit persisted `previewId`; request RBAC, explicit
      confirmation and Active revision/version checks remain necessary but are not substitutes for
      Preview eligibility.
- [ ] 2. The shared Application service re-reads the selected Preview and verifies current/zero-
      mutation state plus the exact definition fingerprint, Active configuration
      revision/version/digest, ResourceLibrary/Storage, normalized source scope, automatic run mode
      and effective workload bound before creating a grant.
- [ ] 3. No Preview, an unknown or cross-definition Preview, stale evidence, failed/unavailable
      analysis, a boundary error, a stale/blocked/failed/unavailable item, or any mismatched binding
      refuses admission with no grant/audit row and no Job, Task, Provider, Storage probe or media
      mutation. The response states what remains durable, whether retry is safe and exactly one
      bounded recovery action.
- [ ] 4. Excluded, currently unstable, truncated-by-limit and empty-scope evidence is represented as
      non-executable rather than mutation authority. It may coexist with an otherwise exact Preview,
      but a grant never overrides those facts or any later normal source-stability, recognition,
      metadata, classification, conflict, capability or destructive-operation gate.
- [ ] 5. A successful admission durably and secret-freely links the grant/audit/projection to the
      exact Preview identity and binding after repository/API/Web reload. Repeating the same request
      remains idempotent; a different Preview or bound cannot silently replace an active grant.
- [ ] 6. Preview invalidation or an Active definition/configuration change racing grant creation
      cannot produce an effective grant for the new or mismatched state. The operation either refuses
      atomically or leaves authority that is provably unusable before any mutation.
- [ ] 7. API callers cannot bypass Preview through omitted, forged, stale, cross-definition or
      transport-only data. API and Web obtain grant eligibility and recovery from the same
      Application behavior under unchanged RBAC and optimistic concurrency rules.
- [ ] 8. The Web journey is visibly ordered as exact Preview/DryRun → eligibility review → explicit
      unattended grant. The enabled grant action and confirmation identify the reviewed Preview and
      exact scope; ineligible state points to the fresh-Preview recovery action. Read/refresh remains
      zero-mutation, and revoke stays independently available.
- [ ] 9. Before automatic occurrence admission, the service resolves the stored granting principal
      against the current configured permission authority and requires
      `grant_unattended_execution`. A removed, disabled or downgraded principal, or an unavailable/
      malformed authority, creates no Task, adapter, Provider request, Storage probe or mutation and
      leaves bounded occurrence failure/recovery evidence.
- [ ] 10. The same current-permission check is repeated immediately before every not-yet-performed
      effect. It is not satisfied by the Job-pinned configuration, the grant-time principal object,
      API-server startup state or a once-per-run cached answer.
- [ ] 11. If current permission is lost after one item completes, that item's effect and Result
      remain intact; the next item is refused before OrganizerExecutor with zero partial effect,
      durable TaskItem/Result/checkpoint evidence, correct retry safety and one next action. No
      completed, blocked or uncertain sibling is automatically replayed.
- [ ] 12. Grant revocation, definition/snapshot/scope/mode/limit matching, per-item plan validation,
      cancellation and existing conflict/capability/destructive gates remain live and independent.
      Preview or current permission never implies Overwrite, Delete, source cleanup, rollback or
      operation fallback.
- [ ] 13. Grant/permission/Preview projections, audit, failures, logs, TaskItem, Result, checkpoint,
      API and Web remain bounded and secret-free; no bearer token, token environment value,
      credential, authorization header, cookie or private endpoint is persisted or exposed.
- [ ] 14. No new media mutation path is introduced. Preview, eligibility projection, current-
      permission resolution, API/Web reads and rejected admissions perform zero Storage mutation;
      only OrganizerExecutor performs an accepted effect.
- [ ] 15. Existing scan-only and scan-and-plan zero-mutation behavior, mixed-item independence,
      RecognitionTypePolicy ownership and RecognitionType C → downstream A policies while remaining
      C regressions continue to pass.
- [ ] 16. Test Level T4 passes with actual totals/skips/unavailable gates reported. No test is
      deleted, assertion relaxed, skip hidden or pre-existing failure claimed without reproduction at
      Task Base.
- [ ] 17. The checkpoint is one coherent Task Base..Head correction containing no private
      configuration, credential or unrelated change.

## Required Tests

Test Level T4. Every command/gate below must be run and its actual result reported. New focused test
modules are allowed; the named behavior is mandatory even if the Developer chooses different module
names.

Focused:

- `./.venv/bin/python -m unittest tests.test_automation_unattended_grant
  tests.test_automation_task_definition_preview` — missing/unknown/cross-definition/stale/failed/
  unavailable/boundary-error/blocker evidence refusal; exact binding and requested limit checks;
  acceptable no-op discovery facts; successful durable Preview linkage; close/reopen; idempotency;
  concurrent invalidation/activation; no rejected grant or audit write; bounded errors and redaction.
- `./.venv/bin/python -m unittest tests.test_automation_definition_execution
  tests.test_automation_authorized_execution_matrix` — current permission valid at admission and
  every effect; principal removed/disabled/downgraded before admission; permission-authority failure;
  loss after the first completed item; no second mutation; preserved sibling Result/checkpoint;
  recovery and no replay; grant/Preview never overriding conflicts, stability, capabilities or
  destructive gates; all accepted effects still passing only through OrganizerExecutor.
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui
  tests.test_api_security` — required `previewId`, API bypass attempts, stale/change race, shared
  eligibility/error projection, current-permission visibility, RBAC, explicit Web ordering and
  confirmation, reload/revoke journey, read-only view load and secret-free bounds.
- Add production-composition coverage in an existing CLI/runtime test module: change a temporary
  configured principal from enabled admin to disabled/removed/non-admin between two effect
  boundaries and prove the definition-scoped Worker reads current authority rather than the pinned
  Job snapshot or the initial answer. Legacy configured admin behavior must remain compatible when
  still valid; no real credential value may enter assertions or output.
- If persistence/schema changes, extend `tests.test_migration_rehearsal` and the applicable
  persistence tests for a real Task-Base database upgrade, grant/Preview linkage survival, atomic
  failure rollback, supported/runtime schema agreement and legacy-row fail-closed behavior.

Integration and affected regression:

- `./.venv/bin/python -m unittest tests.test_automation_unattended_grant
  tests.test_automation_task_definition_preview tests.test_automation_definition_execution
  tests.test_automation_authorized_execution_matrix tests.test_automation_definition_occurrence
  tests.test_automation_task_definition tests.test_automation_api tests.test_automation_admission
  tests.test_automation_job_fencing tests.test_cron_scheduler tests.test_execution_authorization
  tests.test_processing_checkpoint tests.test_processing_recovery_admission
  tests.test_recovery_continuation tests.test_recovery_batch tests.test_task_persistence
  tests.test_task_pause_resume tests.test_task_retry tests.test_organizer tests.test_organizer_rollback
  tests.test_conflict_resolution tests.test_resource_library_pipeline tests.test_scanner
  tests.test_recognition tests.test_configuration_snapshot tests.test_configuration_management
  tests.test_api_credentials tests.test_api_security tests.test_operator_ui
  tests.test_migration_rehearsal tests.test_final_integration` — adjust only for a genuinely renamed or
  new focused module and report the exact substitution.

Full regression:

- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` with actual run and skip totals.
  Any failure claimed pre-existing/unrelated must be reproduced at Task Base
  `e9f9baf24a6616a47ec651f17ef7eed57428cf7d` or in a clean `git archive` of that SHA, with command and
  cause recorded. Known ignored-local-state failures are not automatically accepted without that
  reproduction. No test, assertion or skip may be weakened to obtain a green result.

Falsification evidence (record the command and observed failure, not only a claim):

- On a throwaway `git archive HEAD` copy, bypassing the Preview read/binding check or accepting a
  stale/blocked Preview makes the new grant/API tests fail.
- On a throwaway copy, caching current permission at grant time or run admission, or replacing the
  per-effect lookup with unconditional allow, makes the mid-run permission-loss test fail.
- A counting/refusing Storage double observes zero mutation calls for missing/mismatched/ineligible
  Preview, invalid/unavailable current permission, revoked grant, unsupported capability and
  unattended Overwrite conflict cases.
- A deliberate principal change after the first successful sibling leaves its bytes/Result intact
  and the next source/destination bytes unchanged; restoring permission does not automatically
  replay either item.
- Opening/refreshing Automation list/detail/Preview/grant/history performs no grant, audit, Job,
  Task, Provider request, Storage probe or mutation. A rejected grant leaves no grant/audit row.
- Credential-shaped canaries in configured token environment values, headers and adapter errors do
  not appear in grant/Preview linkage, permission failure, audit, logs, TaskItem/Result/checkpoint or
  API/Web payloads.

Quality and safety gates:

- `./.venv/bin/ruff check .`
- `./.venv/bin/ruff format --check .`
- `./.venv/bin/python -m compileall -q mediaflow tests scripts`
- `./.venv/bin/pip check`
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- forbidden `ffprobe`/`ffmpeg` runtime scan with no production matches
- wheel build via `./.venv/bin/pip wheel . --no-deps --no-build-isolation` plus isolated installed-
  wheel smoke through `scripts/wheel_smoke_test.py`, reporting supported/runtime schema and whether
  migration is required; report `python -m build` as UNAVAILABLE if this environment still lacks its
  executable module rather than hiding the substitution
- if and only if schema changes: Task-Base upgrade rehearsal and every schema-marker test updated;
  otherwise report the unchanged schema explicitly
- Markdown relative-link existence check for changed documents
- private-config/secret scan: `config/alist.json` and `config/strategy.json` remain ignored,
  untracked and unstaged; no credential-like value appears in Task Base..Head
- `git diff --check` and `git diff --cached --check`

External gates must be reported as PASS/FAIL/SKIP/UNAVAILABLE. Do not use production Storage,
Provider credentials or user media; temporary Local roots and fake/in-memory services are sufficient.

## Non-goals

- Any change to the Slice Contract, Base SHA, Roadmap, Closure Packet or A Final Review decision.
- A new identity-administration product, principal/role management Web/API, credential store, token
  rotation workflow or changes to the configured role-permission matrix.
- Requiring an interactive Preview or Execute click for every scheduled occurrence; one valid
  persistent grant remains reusable while its exact bounds and all live gates stay valid.
- Replacing the normal scheduled analysis/planning pipeline with persisted Preview plans, or making
  Scheduler select items, Providers, policies, destinations, plans or operations.
- Redesigning Scheduler, Worker claims, manual/remote one-shot authorization, Task/TaskItem/Result,
  Processing Checkpoint, recovery, OrganizerExecutor, conflict handling or Storage adapters.
- New Overwrite/Delete/cleanup/rollback/fallback authority, automatic replay of uncertain effects,
  distributed leases, forced interruption of an in-flight Storage call or universal compensation.
- P2/P3 cleanup from the prior Closure Packet, copy polish, optional proof or unrelated refactoring.

## Developer Completion Report

### Changed Files

- `mediaflow/application/automation_task_definition_preview.py`
- `mediaflow/application/unattended_execution.py`
- `mediaflow/domain/unattended_execution.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `mediaflow/final_cli.py`
- `tests/test_automation_preview_grant_gate.py`
- `tests/test_automation_unattended_grant.py`
- `tests/test_automation_task_definition_preview.py`
- `tests/test_configuration_classification.py`
- `tests/test_configuration_destination.py`
- `tests/test_configuration_destination_activation.py`
- `tests/test_configuration_destination_precheck.py`
- `tests/test_configuration_organize.py`

### Implemented

- Added shared persisted Preview eligibility checks for unattended grant admission, including exact
  definition/configuration/ResourceLibrary/Storage/scope/mode/workload binding, zero-mutation and
  current-state checks, benign non-executable empty/excluded/unstable/truncated evidence, and
  fail-closed blocker handling.
- Persisted and projected the exact `previewId` linkage, included it in grant idempotency binding
  and grant audit evidence, and added the additive runtime schema 31 migration.
- Added current configured principal permission resolution before automatic Task creation and again
  immediately before each pending OrganizerExecutor effect; production CLI Worker composition reloads
  roles/enabled state without resolving or exposing credentials.
- Updated API and Operator Web grant flows to require and display the exact Preview linkage and
  current permission state, while keeping revoke independently available and reads mutation-free.
- Preserved Recognition/Planner/OrganizerExecutor boundaries and updated empty/benign Preview status
  semantics so exact no-op discovery evidence can be reviewed without becoming item authority.

### Tests and Results

- `./.venv/bin/python -m unittest tests.test_automation_preview_grant_gate tests.test_automation_unattended_grant tests.test_automation_task_definition_preview tests.test_automation_definition_execution tests.test_automation_authorized_execution_matrix tests.test_automation_api tests.test_operator_ui tests.test_api_security tests.test_migration_rehearsal`: PASS, 131 tests.
- Required affected integration command from this Task: FAIL, 434 tests, 4 failures. The failures are
  `test_scan_cli_needs_no_path_or_metadata_token`, the two API credential tests, and
  `test_runtime_configuration_and_final_analyze_cli`;
  the affected failures were reproduced at Task Base as pre-existing/unrelated. The exact current
  affected run reported 434 tests and 4 failures.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`: FAIL, 1101 tests, 6 failures,
  7 skips. All six failures were reproduced from clean Task Base `e9f9baf24a6616a47ec651f17ef7eed57428cf7d`
  and are PRE-EXISTING / UNRELATED ignored-local-state failures.
- Task Base reproduction command in a clean archive: `tests.test_api_credentials
  tests.test_final_integration tests.test_resource_library_pipeline tests.test_runtime_storage_configuration`:
  FAIL, 23 tests, 6 failures, same six local-state failures; no Task code was used.
- `./.venv/bin/ruff check .`: PASS.
- `./.venv/bin/ruff format --check .`: PASS, 355 files formatted.
- `./.venv/bin/python -m compileall -q mediaflow tests scripts`: PASS.
- `./.venv/bin/pip check`: PASS.
- Both required example configuration validation commands: PASS.
- Forbidden runtime `ffprobe`/`ffmpeg` scan: PASS, no production Python matches.
- `./.venv/bin/python -m unittest tests.test_migration_rehearsal`: PASS; schema 31 migration/rehearsal
  coverage passes and legacy rows remain readable.
- `./.venv/bin/pip wheel . --no-deps --no-build-isolation` and
  `scripts/wheel_smoke_test.py`: PASS; supported/runtime schema 31, migration required NO.
- `./.venv/bin/python -m build`: UNAVAILABLE because this environment has no `build.__main__`;
  the required pip-wheel substitute passed.
- `git diff --check`, `git diff --cached --check`, private-config/secret review: PASS;
  `config/alist.json` and `config/strategy.json` remained ignored, untracked and unstaged.

### Decisions

- The exact Preview identity is part of the grant binding, so a different Preview cannot silently
  replace an active grant even when the other bounds are equal.
- Direct legacy application test doubles without injected Preview/permission authorities retain their
  pre-managed compatibility behavior; API and production Worker composition always inject both
  authorities and fail closed when either is missing or invalid.
- Empty, excluded-only, unstable-only and truncated-only Preview discovery is accepted as exact,
  zero-mutation, non-executable evidence; no such item receives mutation authority.
- The new Preview linkage uses one nullable additive column and runtime schema 31. Existing legacy
  grants without linkage are refused by production definition-scoped execution before any Task or
  Storage effect.

### Remaining In-Slice Work

None identified within this implementation Task; B determines Task review and any remaining Slice
review work.

### Risks / Deviations

- The six full-regression failures are pre-existing/unrelated local configuration-state failures,
  with clean Task Base reproduction recorded above. They are not claimed as passing.
- Python `ResourceWarning` messages for pre-existing unclosed SQLite connections remain visible but
  did not change test outcomes.
- Real Scheduler endurance/process-stop, production SMB/OpenList/S3/R2, Provider credentials and
  destructive acceptance gates were not run in this environment; no production data, credentials or
  user media were used.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: 44ac7f8f8e5b03411a026b138e82c22935ef0562
```

## B Review Result

```text
Reviewed: PENDING
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, only unmet Task blockers are listed below this block. Corrections remain in Task
25.7. A PASS returns Slice 25 to `READY FOR A REVIEW`; B does not close the Slice.
