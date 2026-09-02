# Task 25.5 — Persistent revocable unattended execution grant and authorized automatic organization

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to the
current [`SLICE.md`](SLICE.md).

```text
Task ID: 25.5
Parent Slice: 25 — Scheduled Automation and Unattended Organization
Status: FIX REQUIRED
Task Base: 94044e4d2e7678fc866e4c3400d74e1b41672f8c
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Make automatic organization possible only through a separate, explicit, persistent and independently
revocable unattended execution grant that is bound to one exact Automation Task Definition identity,
ResourceLibrary, normalized sub-scope, run mode and bounded workload; and let a due
`automatic-organization` occurrence, when that grant is live and still matches, run the existing
Scan → Parse → Recognition → RecognitionType → RecognitionTypePolicy → Metadata → Naming →
Classification → OrganizePlan chain through to real `OrganizerExecutor` mutation with the live grant
revalidated immediately before every not-yet-performed mutation.

This Task advances RO-5, completes the "only when authorized, OrganizerExecutor → Result/Log" half
of RO-4, and adds the grant/revoke portions of RO-7. It does not close the Slice.

## Why This Task Exists

Task 25.4 delivered the definition-scoped Worker handoff, but
`mediaflow/application/automation_definition_execution.py:76-83` still refuses every
`automatic-organization` occurrence unconditionally with `unattended_execution_authority_missing`,
because no grant object exists anywhere in the product. The consequence in code today:

- `PersistentTaskCoordinator.create(..., execute_authorized=False)` and
  `MediaOrganizerService.process_library(..., execute=False)` are hard-coded for every definition
  run, so no scheduled occurrence can reach `OrganizerExecutor.execute` at
  `mediaflow/application/media_organizer.py:365`.
- The only execution authorities that exist are one-shot and manual/remote: `ExecutionAuthorization`
  (`mediaflow/application/execution_authorization.py`) and `ManualExecutionAuthorization`
  (`mediaflow/application/manual_organize_execution.py`). Neither is persistent, neither is bound to
  an Automation definition, and RO-5 plus the Slice's Explicitly Deferred list forbid redesigning
  them.
- `ApiPermission` (`mediaflow/domain/security.py:17-35`) has no unattended-execution authority, so
  there is nothing to permission-check and nothing to audit.
- The Scheduler correctly emits definition Jobs with `execute_authorized` left False
  (`mediaflow/application/automation.py:619-635`) and must keep owning no authority decision, so the
  authority has to be resolved at claim/run time from durable state.

The grant and the authorized execution path are one behavior, not two: a grant that nothing consumes
is not an acceptable user outcome, and an authorized run without a revocable grant would violate the
Slice. This is therefore the largest independently acceptable unit — after it, the operator can
grant unattended execution, watch a scheduled occurrence actually organize, and revoke that
authority to stop the next one.

## Implementation Scope

```text
Domain → Persistence/Migration → Application → Worker/Execution → API → Web → Tests
```

Domain

- A new `UnattendedExecutionGrant` value object with bounded, secret-free, timezone-aware fields:
  grant id, definition id, resource library id, normalized source scope, allowed run mode, bounded
  `max_items_per_run`, status (`active` / `revoked`), granting principal, granted-at, optional
  revoking principal / revoked-at, bounded reason text, and — recorded as evidence only — the
  definition fingerprint and configuration snapshot id/digest/version observed at grant time.
- A grant audit record following the existing `ManualExecutionAuthorizationAudit`
  (`mediaflow/domain/manual_execution.py:79-108`) shape, and a repository Protocol.
- `ApiPermission.GRANT_UNATTENDED_EXECUTION`. `ApiRole.ADMIN` inherits it through the existing
  `frozenset(ApiPermission)`; `VIEWER`, `OPERATOR`, `EXECUTOR` and `AUDITOR` sets stay byte-for-byte
  unchanged so no existing token silently gains unattended mutation authority.

Persistence / Migration

- New SQLite table(s) for grants and grant audit, `SCHEMA_VERSION` 29 → 30 with a forward migration
  that preserves every existing schedule, definition, preview, due-state, occurrence, Job, Task,
  TaskItem and Result row, and works on a database created by the current released schema.
- Grant and revoke each commit their row plus their audit record inside one single
  `with self._lock, self._connection:` transaction. Reads are bounded and indexed by definition id;
  no unbounded scan and no N+1 in the definition/occurrence projections.

Application

- A grant service exposing grant / revoke / get / list with permission checks, audit, bounded
  validation and safe idempotent semantics for a repeated revoke.
- Authority resolution used by execution: a grant authorizes a claimed occurrence only when it is
  `active` and its bound `definition_id`, `resource_library_id`, normalized `source_scope`,
  `run_mode` and workload bound all still match the claimed Job's pins, with the Job's effective
  item bound `<= max_items_per_run`. Any inequality — including scope widening, scope narrowing, a
  mode change or a raised item limit — fails closed and requires an explicit new grant. A differing
  definition fingerprint is surfaced as visible "definition changed since grant" evidence.
- Enable/disable of a definition and grant/revoke of unattended execution stay independent: neither
  action mutates or invalidates the other.

Worker / Execution

- `DefinitionScopedExecutionService` replaces the unconditional automatic-organization refusal with
  the live grant check, performed before adapter construction and before Task creation. Without a
  live grant the existing `unattended_execution_authority_missing` category and its zero-Task,
  zero-adapter behavior are preserved; a revoked, mismatched, widened or over-limit grant fails
  closed with its own distinct bounded category.
- When authorized, the Task is created with `execute_authorized=True` and the existing chain runs
  with `execute=True`, so mutation happens only inside `OrganizerExecutor`.
- Immediately before each per-item mutation, the live grant is re-read from the repository — not
  from a cached object captured at run start — and the item is refused if the grant is no longer
  valid. Refusal leaves already-completed items and their Results intact, records a bounded per-item
  reason, retry safety and one explicit next action, and stops attempting further mutations without
  concealing or replaying any sibling.
- Wire the grant repository into the Worker construction path in `mediaflow/final_cli.py`
  (`_run_definition_scoped_workflow`). The Scheduler stays frozen: no emission-time authority flag,
  no Storage, Provider, policy or pipeline work is added to it.

API / Web

- Authenticated versioned grant, revoke and grant-state surfaces under the existing
  `/api/v1/automation/task-definitions/{id}/...` shape, gated by the new permission, using the same
  application service, validation, audit, bounded secret-free error contract and RBAC as the rest of
  the Automation surfaces.
- The definition detail projection exposes current grant state, its exact bound scope/mode/workload,
  granting principal and timestamps, whether the definition changed since the grant, and the next
  action.
- The Operator Web Automation detail view gains a distinct explicit grant confirmation that states
  the exact scope and implications before granting, plus an independent revoke action, following the
  existing `confirmAutomationPreview` confirmation pattern
  (`mediaflow/interfaces/operator_ui.py:2280-2293`). Granting must not be reachable as a side effect
  of enabling, previewing or opening any view.

Frozen in this Task

- `ManualExecutionAuthorization` and `ExecutionAuthorization` semantics, statuses and surfaces.
- `IntervalScheduler` / definition emission logic and `AutomationJobService.submit`'s refusal of
  definition-pinned Jobs.
- `OrganizePlanner`, `OrganizerExecutor`, `RecognitionTypePolicy` ownership, conflict strategies and
  the Processing Checkpoint contract.

## Acceptance Criteria

- [ ] An authenticated principal holding the new permission can grant unattended execution for one
      exact definition through the API and through the Operator Web explicit confirmation, and the
      grant survives process restart with its bound definition id, ResourceLibrary, normalized
      scope, run mode, workload bound, principal, timestamps and audit intact.
- [ ] A principal without the new permission — including `OPERATOR` and `EXECUTOR` tokens — is
      refused grant and revoke with the standard bounded error contract, and the `VIEWER`,
      `OPERATOR`, `EXECUTOR` and `AUDITOR` permission sets are unchanged.
- [ ] With no grant, an `automatic-organization` occurrence still fails closed exactly as today:
      category `unattended_execution_authority_missing`, no Task, no TaskItem, no Result, no
      Scanner, Provider registry, planner or `OrganizerExecutor` construction, and zero Storage
      mutation.
- [ ] With a live matching grant, a bounded `automatic-organization` occurrence over temporary Local
      roots really organizes: the Task is `execute_authorized`, files move through
      `OrganizerExecutor` only, and Definition → Job → Task → TaskItem → Result/Log links survive
      reload. `scan-only` and `scan-and-plan` occurrences remain zero-mutation and unauthorized.
- [ ] A revoked grant, a grant whose definition scope, run mode or item limit no longer matches, and
      a grant whose workload bound is below the occurrence's item bound each fail closed before any
      mutation with a distinct bounded secret-free category, durable state, retry safety and one
      explicit next action; no Storage mutation occurs and no plan or operation is substituted.
- [ ] Revocation committed after a run has started stops the next not-yet-performed mutation:
      already-completed items keep their Results and known effects, the refused item records its own
      bounded reason and next action, remaining items are visibly not executed rather than silently
      skipped, and no successful sibling is replayed. The authority is re-read live at that
      boundary, not cached.
- [ ] The grant grants nothing beyond scheduled organization: Overwrite, Delete, MOVE source
      removal, source-directory cleanup, rollback, operation fallback and any path outside the bound
      scope remain denied by their own independent authorities, and an unsupported operation still
      fails explicitly.
- [ ] Enabling or disabling a definition neither creates nor invalidates a grant; revoking a grant
      neither disables scheduling nor rewrites completed Job/Task/Result history. A definition edit
      that changes the bound scope, mode or workload cannot inherit the older grant.
- [ ] API and Web expose the same grant state, actions, confirmations, RBAC, validation, audit,
      failures and recovery text; after reload the operator can see grant state, its exact bounds,
      whether the definition changed since the grant, and the linked occurrence/Task/Result history.
      Opening or refreshing any view creates no grant, Job, Task, Provider request or Storage probe.
- [ ] `SCHEMA_VERSION` is 30, the forward migration from the current released schema preserves all
      existing rows and is proven by an actual migration run, and every test asserting the runtime
      schema marker is updated with no other change in those files.
- [ ] Mixed RecognitionTypes inside one authorized occurrence still select their own configured
      Providers, MediaLibraries, destinations and operations, and RecognitionType C remains C
      through plan, execution and Result while reusing NamingPolicy A and ClassificationPolicy A.
- [ ] No credential, token, authorization header, private endpoint or private configuration value
      enters grant rows, audit, Job, Task, Result, occurrence, API/Web projections or logs;
      `config/alist.json` and `config/strategy.json` remain ignored, untracked and unstaged.
- [ ] Test Level T4 passes with actual reported evidence, and the checkpoint contains only this
      Task.

## Required Tests

Test Level T4. Every command below must be run and its actual result reported. A new focused module
is expected (for example `tests/test_automation_unattended_grant.py`); its name is the Developer's
choice, but the coverage below is not optional.

Focused:

- `./.venv/bin/python -m unittest tests.test_automation_unattended_grant` — grant/revoke lifecycle
  and restart persistence; permission enforcement for grant and revoke including an `OPERATOR` and
  an `EXECUTOR` principal; bounded validation and repeated-revoke idempotency; authority matching
  for definition id, ResourceLibrary, normalized scope, run mode and workload bound; scope widening,
  scope narrowing, mode change and raised item limit each failing closed; definition-changed
  evidence; grant/revoke independence from enable/disable; audit records.
- `./.venv/bin/python -m unittest tests.test_automation_definition_execution` — extended for the
  authorized path: real `automatic-organization` execution over temporary Local roots with per-item
  Results; unauthorized and revoked refusals with no Task and no mutation; revocation between items
  proving live re-read, preserved completed effects, a bounded per-item reason and no sibling
  replay; `scan-only` / `scan-and-plan` still zero-mutation; mixed RecognitionTypes; RecognitionType
  C remaining C; item-limit and sub-scope bounds still enforced under execution.
- Persistence/migration coverage in `tests.test_migration_rehearsal` or an adjacent module —
  migration from the current released schema to 30 preserving legacy schedule, definition, preview,
  due-state, occurrence, Job, Task, TaskItem and Result rows; grant and audit rows surviving
  close/reopen; bounded grant reads with no unbounded scan and no N+1.
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui
  tests.test_api_security` — grant/revoke routes, RBAC refusal, grant state in the definition
  projection, explicit Web confirmation, zero-mutation view load and the bounded secret-free error
  contract.

Integration and affected regression:

- `./.venv/bin/python -m unittest tests.test_automation_unattended_grant
  tests.test_automation_definition_execution tests.test_automation_task_definition
  tests.test_automation_task_definition_preview tests.test_automation_definition_occurrence
  tests.test_automation_api tests.test_automation_admission tests.test_automation_job_fencing
  tests.test_cron_scheduler tests.test_execution_authorization tests.test_manual_organize_execution
  tests.test_task_persistence tests.test_task_pause_resume tests.test_task_retry
  tests.test_organizer tests.test_organizer_rollback tests.test_resource_library_pipeline
  tests.test_scanner tests.test_recognition tests.test_processing_checkpoint
  tests.test_configuration_snapshot tests.test_api_credentials tests.test_api_security
  tests.test_operator_ui tests.test_migration_rehearsal tests.test_final_integration` — adjust only
  if a module name does not exist, and report the substitution.

Full regression:

- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` with actual run/skip totals. Any
  failure claimed pre-existing must be reproduced at Task Base
  `94044e4d2e7678fc866e4c3400d74e1b41672f8c` or on a clean `git archive` tree, with the reproduction
  command and cause recorded. The six known environment failures caused by the ignored local runtime
  database and `config/strategy.json` (`test_api_credentials` x2, `test_final_integration`,
  `test_resource_library_pipeline`, `test_runtime_storage_configuration` x2) are accepted as
  pre-existing only with that evidence. No test, assertion or skip may be weakened to obtain a green
  run.

Falsification evidence (record the command and observed result, not a claim):

- Byte-level before/after comparison of the source and destination trees proves that an
  unauthorized, revoked or mismatched `automatic-organization` occurrence mutates nothing, and that
  an authorized one mutates only through `OrganizerExecutor`; a refusing or counting Storage double
  observes zero mutation calls in the unauthorized cases.
- Revoking the grant after the first item is executed leaves that item's effect and Result intact,
  refuses the next item before its mutation, and leaves no partially applied second effect.
- Deliberate regressions applied to a throwaway `git archive HEAD` copy (workspace untouched) — for
  example accepting a revoked grant, comparing only the definition id instead of the full bound
  tuple, caching the grant for the whole run instead of re-reading it per mutation, granting the new
  permission to `OPERATOR`, or setting `execute_authorized=True` without a grant — make the new
  tests fail, proving the evidence is non-vacuous.
- A grant for definition X cannot authorize an occurrence of definition Y, an occurrence outside the
  bound sub-scope, or an occurrence whose item bound exceeds the granted workload.
- Opening or refreshing the Automation list, detail, occurrence and Preview views creates no grant,
  Job, Task, Provider request or Storage probe.
- No credential, token, authorization header, private endpoint or private configuration value
  appears in grant rows, audit, Job, Task, TaskItem, Result, occurrence, API/Web projections or
  logs.

Quality and safety gates:

- `./.venv/bin/ruff check .`
- `./.venv/bin/ruff format --check .`
- `./.venv/bin/python -m compileall -q mediaflow tests scripts`
- `./.venv/bin/pip check`
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate`
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate`
- forbidden `ffprobe`/`ffmpeg` runtime scan (no matches)
- wheel build plus isolated installed-wheel smoke (`scripts/wheel_smoke_test.py`); `python -m build`
  is unavailable in this virtualenv, so `pip wheel . --no-deps --no-build-isolation` plus the smoke
  script is the accepted substitute and must be reported as such, including the reported supported
  and runtime schema versions and whether migration is required
- schema-marker check: every test asserting the runtime schema version is updated to 30 and nothing
  else in those files changes
- Markdown relative-link existence check for changed documents
- private-config/secret scan: `config/alist.json` and `config/strategy.json` remain ignored,
  untracked and unstaged; no credential-like value in `Task Base..Head`
- `git diff --check` and `git diff --cached --check`

External gates: report PASS/FAIL/SKIP/UNAVAILABLE honestly. Real production Storage, Provider
credentials and user media are not required and must not be used; use temporary Local roots plus
fake/in-memory Provider and adapter doubles.

## Non-goals

- The broad automatic-run safety matrix left to the next Task: Copy/HardLink/SoftLink and attachment
  execution matrices, collision handling across Skip/Rename/Manual/authorized Overwrite, source
  directory cleanup, injected partial or uncertain failure, and the complete per-item recovery and
  linked-history Web/API projections beyond the grant state required here.
- Redesigning, replacing or extending `ManualExecutionAuthorization` or `ExecutionAuthorization`, or
  unifying them with the new grant.
- Any Scheduler change: new emission fields, an emission-time authority flag, or any Storage,
  Provider, policy or pipeline work inside the Scheduler.
- A CLI grant/revoke command, grant expiry or scheduling windows, multi-principal approval, grant
  templates, and cross-definition or global grants.
- Anything in the Slice's Explicitly Deferred list, including automatic replay of uncertain
  mutation, Provider switching lifecycle, notification Provider management and a Secret Store.
- Unrelated refactors, copy polish and P2 cleanup not required by these Acceptance Criteria.

## Developer Completion Report

### Changed Files

- `mediaflow/domain/unattended_execution.py`
- `mediaflow/application/unattended_execution.py`
- `mediaflow/domain/security.py`
- `mediaflow/infrastructure/sqlite_runtime.py`
- `mediaflow/application/automation_definition_execution.py`
- `mediaflow/application/automation_definition_occurrence.py`
- `mediaflow/application/media_organizer.py`
- `mediaflow/final_cli.py`
- `mediaflow/interfaces/service_api.py`
- `mediaflow/interfaces/operator_ui.py`
- `tests/test_automation_unattended_grant.py`
- `tests/test_automation_definition_execution.py`
- runtime schema-marker assertions in
  `tests/test_configuration_classification.py`,
  `tests/test_configuration_destination.py`,
  `tests/test_configuration_destination_activation.py`,
  `tests/test_configuration_destination_precheck.py`, and
  `tests/test_configuration_organize.py`

### Implemented

- Added a bounded, secret-free persistent unattended grant domain object, grant/revoke audit
  record, repository seam, exact definition/ResourceLibrary/scope/mode/workload/snapshot binding,
  permission checks, and idempotent revoke behavior.
- Added SQLite schema 30 additive grant and audit tables/indexes with atomic grant and revoke
  transactions and restart-safe reads.
- Added live authority resolution before adapter/Task creation and a live grant re-read immediately
  before each eligible item mutation; authorized runs reuse the existing Task/TaskItem/Result and
  OrganizerExecutor pipeline, while scan-only and scan-and-plan remain zero-mutation.
- Added bounded API grant/state/audit/revoke routes, definition/detail grant projections and
  explicit Operator Web grant/revoke confirmations.  Added the new grant permission without
  changing non-admin role sets.
- Added migration, RBAC, exact-bound, no-mutation, real Local execution, RecognitionType C, and
  revocation-boundary regression coverage.

### Tests and Results

- `./.venv/bin/ruff check .` — PASS.
- `./.venv/bin/ruff format --check .` — PASS (351 files formatted).
- `./.venv/bin/python -m compileall -q mediaflow tests scripts` — PASS.
- `./.venv/bin/pip check` — PASS.
- `./.venv/bin/mediaflow --config config/strategy.example.json config validate` — PASS.
- `./.venv/bin/mediaflow --config config/mediaflow.phase13.2.example.json config validate` — PASS.
- Forbidden `ffprobe`/`ffmpeg` scan — PASS (no runtime matches); schema marker check — PASS
  (`SCHEMA_VERSION=30`); private-config check — PASS (`config/alist.json` and
  `config/strategy.json` remain ignored/untracked).
- `./.venv/bin/python -m unittest tests.test_automation_unattended_grant` — PASS, 7 tests.
- `./.venv/bin/python -m unittest tests.test_automation_definition_execution` — PASS, 15 tests
  (run in clean detached checkpoint worktree with the shared virtualenv).
- `./.venv/bin/python -m unittest tests.test_automation_api tests.test_operator_ui tests.test_api_security`
  — PASS, 64 tests (clean detached checkpoint worktree).
- `./.venv/bin/python -m unittest tests.test_migration_rehearsal` — PASS, 4 tests (clean detached
  checkpoint worktree).
- Required cross-module integration command — PASS, 360 tests (clean detached checkpoint
  worktree at `da1355a`).
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` — PASS, 1077 tests, 7 skips
  (clean detached checkpoint worktree at `da1355a`).
- The same full-regression command in the primary worktree — FAIL / PRE-EXISTING / UNRELATED:
  1077 tests, 6 failures, 7 skips.  Failures were the two credential checks, final integration,
  resource-library scan, and two runtime-storage checks; the worktree's ignored
  `.mediaflow/mediaflow.sqlite3` and `config/strategy.json` supplied stale local configuration.
  The exact 23-test affected set at Task Base, run in a throwaway copy with those ignored files
  copied in, reproduced the same 6 failures; the clean Task Base run passed the affected set.
  Running the full command at Task Base `94044e4d2e7678fc866e4c3400d74e1b41672f8c` in a clean
  detached worktree produced 1067 tests, 0 failures, 7 skips; the clean `da1355a` worktree also
  produced 1077 tests, 0 failures, 7 skips.
- `./.venv/bin/pip wheel . --no-deps --no-build-isolation --wheel-dir /tmp/mediaflow-wheel-final`
  plus `scripts/wheel_smoke_test.py` — PASS; `python -m build` was not used because it is
  unavailable in this virtualenv.  Installed-wheel smoke reported supported/runtime schema 30
  and migration required `NO`.
- `git diff --check` and staged diff check — PASS.

### Decisions

- Kept unattended authority separate from one-shot manual/remote execution and kept Scheduler
  emission unchanged; the Worker resolves the grant from durable state at claim/run time.
- Preserved the existing complete media pipeline and placed the live authority callback directly
  before `OrganizerExecutor.execute`, so no alternate mutation path or silent operation fallback
  is introduced.
- Definition fingerprints still pin the full Scheduler document, while grant projection treats a
  pure enable/disable toggle as scheduling state and reports other definition changes as stale.

### Remaining In-Slice Work

- Other Slice Required Outcomes outside this Task remain for the subsequent Slice Tasks, including
  the broader definition/Preview journey, scheduler/worker completeness, and full recovery/history
  surfaces.

### Risks / Deviations

- The six primary-worktree full-regression failures above are environment-state failures only; no
  changed Task file or assertion was weakened, and clean Task Base/current-head runs are green.
- Existing test suites emit unrelated `ResourceWarning` messages for unclosed SQLite connections;
  they did not change exit status or test outcomes.
- Real production Storage, Provider credentials and user media were not used; execution evidence
  uses temporary Local roots and synthetic/fake providers and Storage doubles.

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: da1355ac45e8457c7ec7b7ca1df5d005c466cdcf
```

## B Review Result

```text
Reviewed: 94044e4d2e7678fc866e4c3400d74e1b41672f8c..da1355ac45e8457c7ec7b7ca1df5d005c466cdcf
Decision: FIX REQUIRED
Slice Required Outcomes all satisfied: NO
Next: SAME TASK FIX LOOP
```

Everything else in this Task was independently verified at the reported Head, including the full
regression (1077 tests, 7 skips, OK on a clean `git archive` tree), the five falsification probes
required by this Task, a real schema 29 → 30 upgrade of a database built by Task Base code, and every
quality/safety gate. Only the points below block the Task.

### 1. AC 9 unmet — the list/Web grant projection reports a stale grant after a re-grant (P1)

Where it fails: `mediaflow/application/unattended_execution.py:420-436`. `project_many` builds
`{value.definition_id: value for value in self._list(definition_ids=ids, limit=100)}` over rows
ordered `granted_at DESC, grant_id DESC`, so the dict comprehension keeps the **last** row iterated —
the **oldest** grant for that definition. The single-definition path
(`get_for_definition` → `get_latest_unattended_execution_grant`, lines 290-291) keeps the **latest**.
Any definition with grant history therefore projects two different grant states depending on which
surface the operator opens.

Evidence (run at `da1355a`, no test modified — grant, revoke, re-grant through the real API):

```text
POST /api/v1/automation/task-definitions/automatic/grant        -> 201
POST /api/v1/automation/task-definitions/automatic/grant/revoke -> 200
POST /api/v1/automation/task-definitions/automatic/grant        -> 201 (re-granted)

GET  /api/v1/automation/task-definitions/automatic             -> grant status='active'  grantId='abc2c154…'
GET  /api/v1/automation/task-definitions                       -> grant status='revoked' grantId='aa9c1882…'
GET  /api/v1/automation/task-definitions/automatic/grant-state -> grant status='active'
repository truth: active grant = abc2c154…
```

The service-level projection diverges on `status`, `active`, `grantId`, `grantedAt`, `revokedAt`,
`revokingPrincipal`, `reason` and `nextAction`. This reaches the Operator Web as the visible state and
as the wrong action: `operator_ui.py:2222` renders the detail panel from `items[index]` of the **list**
payload, `:2246` reads `item.unattendedExecutionGrant`, and `:2262` chooses the button from
`grant.active === true || grant.status === 'active'` — so the Web shows `Unattended grant: revoked`
with a `Revoked at` timestamp and offers **"Grant unattended execution"** for a definition whose grant
is live and will mutate media at the next occurrence. That is the opposite of the state the API detail
and `grant-state` routes report, and AC 9 requires them to be the same.

Required fix direction: make the batched projection resolve the same grant the single-definition path
resolves (active when present, otherwise latest) with a bounded read — do not rely on iteration order
of a multi-row page. Add a regression test that grants, revokes and re-grants one definition, then
asserts the list projection, the detail projection, `grant-state` and the list-derived Web state all
report `active` with one identical `grantId`.

### 2. AC 9 unmet — above 100 definitions the list silently reports no grant at all (P1)

Where it fails: `mediaflow/application/unattended_execution.py:428` passes every definition id of the
page to a repository read bounded at 100 ids (`mediaflow/infrastructure/sqlite_runtime.py:4846-4847`
raises `ValueError("unattended execution definition page is too large")`), and
`mediaflow/application/automation_definition_occurrence.py:87-94` swallows that `ValueError` into
`grants = {}`. The list projection then omits grant state for every definition, and the Web — whose
detail panel is built from that same payload — shows `Unattended grant: none` and offers
"Grant unattended execution" for definitions that already hold a live grant.

Evidence (run at `da1355a`, one active grant on `definition-000`):

```text
100 definitions: project_many -> definition-000 status='active'
100 definitions: list projection -> definition-000 grant status='active' (repository truth: active)
101 definitions: project_many raised ValueError: unattended execution definition page is too large
101 definitions: list projection -> definition-000 grant status=None  (repository truth: active)
```

Required fix direction: keep the read bounded but complete for the page actually rendered (chunk the
definition ids against the repository bound instead of sending the whole page in one call), and stop
degrading a failed grant read into a silent "no grant" display — an unreadable grant state must
surface as an explicit bounded error with one next action, never as absence of authority. Add a
regression test that crosses the 100-definition bound and asserts the granted definition still
projects its active grant.

Fixes remain in this Task: Task ID, Task Base, Goal and Implementation Scope are unchanged. No test,
assertion or skip may be weakened to close these points.
