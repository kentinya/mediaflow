# Task 29.1 — Jobs Execution-Boundary Completeness

This Task follows [the development workflow](docs/development-workflow.md) and is subordinate to
the current [`SLICE.md`](SLICE.md).

```text
Task ID: 29.1
Parent Slice: 29
Parent Slice Name: Docker Production Self-hosted Release
Parent Required Outcome: RO-8 — Pre-release execution-boundary completeness
Status: PLANNED
Task Base: e0ecbefe4048d62d1b67fb3f752bf9db5e8d50ee
Difficulty: High
Test Level: T4
Planner / Reviewer: B
```

## Goal

Complete the shared Jobs and Job Preview execution boundary as one operator journey:

```text
Jobs → Queue Job → Scan / Preview / Organize

Scan
  → SUBMIT_DRY_RUN
  → Worker analysis
  → zero Storage mutation

Preview
  → SUBMIT_DRY_RUN
  → inspectable analysis/findings
  → zero Storage mutation
  → organize-plan conflict is evidence, not a mandatory backlog item

Organize
  → existing one-shot real-execution authority
  → explicit confirmation
  → Worker
  → current-state revalidation
  → existing pipeline
  → OrganizerExecutor-only Storage mutation
  → existing conflict recovery when a real attempt remains unresolved
```

This Task advances Slice 29 RO-8 only. It must also make
`Configuration → Active revision → Queue first DryRun Preview` inherit the same shared Job Preview
semantics. It does not implement the Docker release outcomes RO-1 through RO-7.

## Why This Task Exists

The audit at Task Base found a narrow but product-blocking mismatch:

- `POST /api/v1/jobs` already has a protected `organize` branch requiring
  `execute=true`, `REMOTE_EXECUTE`, the enabled remote-execution gate and
  `X-MediaFlow-Execution-Token`. `ExecutionAuthorizationService.submit_organize()` creates the
  existing one-shot, execute-authorized Job and consumes the authority atomically.
- Ordinary `AutomationJobService.submit()` intentionally admits only `scan` and `preview`.
- The Jobs Web surface currently renders only `Queue DryRun job` with `['scan', 'preview']`; it has
  no single Queue Job entry or Organize review/confirmation surface.
- Configuration's existing `Queue first DryRun Preview` posts the same `command=preview` Job and
  therefore must be corrected through the shared Job Preview boundary, not through a
  Configuration-specific filter.
- In `MediaOrganizerService.process_file()`, an unresolved organize-plan conflict currently calls
  `PersistentTaskCoordinator.wait_for_confirmation()` regardless of whether the run is a DryRun.
  That persists `ConflictConfirmation`, changes the `TaskItem` to `WAITING_CONFIRM`, and increases
  the Dashboard pending-conflict count.
- `PipelineEvidence` and the existing result/task persistence already carry bounded plan conflict,
  source/destination, operation, configured policy and capability evidence. The existing `DRY_RUN`
  and `SKIPPED` completion states are available candidates for an analysis-only durable outcome.
  No new `TaskItemStatus` is authorized by default.
- Files/FileIndex Manual Preview already has independent analysis-only conflict findings and zero
  mutation tests. Automation Definition Preview and scheduled/unattended execution have separate
  behavior and must remain regression-only in this Task.

This is the largest reasonable first implementation unit because the user-visible outcome crosses
Jobs Web/API, shared admission, Worker handoff, Task/Result evidence, conflict continuation and
Dashboard observation. Splitting it into a dropdown, API, conflict filter, configuration fix and
Dashboard fix would leave the same journey incomplete and would obscure the authority boundary.

## Operator Journey Contract

The Developer must implement and test the complete journey for each affected entry point:

### Jobs → Scan

- Entry: authenticated Jobs view, `Queue Job`, command `Scan`.
- Visible state: `Authority: DRY_RUN`; `Storage mutation: NONE`.
- Action: review and explicitly confirm queueing the DryRun Job.
- Success: `SUBMIT_DRY_RUN` Job is admitted, handed to the Worker and produces normal scan/task
  evidence with zero Storage mutation.
- Failure: invalid command, permission, queue admission or Worker/runtime failure is bounded and
  identifies durable state and next action.
- Recovery: use existing Job/Task status and safe retry/recovery semantics; no mutation authority is
  created by retrying or inspecting the Job.

### Jobs → Preview

- Entry: the same authenticated `Queue Job` surface, command `Preview`.
- Visible state: `Authority: DRY_RUN`; `Storage mutation: NONE`.
- Action: review and explicitly confirm queueing the DryRun Job.
- Success: the complete analysis pipeline runs and persists inspectable findings/results without
  Storage mutation.
- Conflict finding: source, destination, operation, conflict type, configured strategy,
  capability/evidence, status and next action remain visible through existing bounded
  Task/Result/evidence projections, but no `PENDING ConflictConfirmation`, no `WAITING_CONFIRM`
  TaskItem and no new real Conflicts backlog item are created.
- Recovery: a Preview finding is not execution authority. The operator must use the explicit real
  Organize path and fresh authority/revalidation when organization is desired.

### Jobs → Organize

- Entry: the same authenticated `Queue Job` surface, command `Organize`.
- Visible state: `Authority: REAL EXECUTION`; `Storage mutation: POSSIBLE`; explicit warning that
  execution authority and confirmation are required.
- Action: review and choose an explicit `Confirm Organize` action before the mutation-capable Job is
  admitted. `OK`, `Run` or `Proceed` alone is not the final mutation confirmation label.
- Success: the existing one-shot `REMOTE_EXECUTE` authority admits one execute-authorized Job; the
  Worker invokes the existing pipeline and only `OrganizerExecutor` can mutate Storage.
- Failure: missing/invalid/expired/consumed/revoked/mismatched authority, disabled gate, stale
  snapshot/source/occurrence/destination/capability/conflict state, or missing Worker fails closed
  without unauthorized mutation.
- Recovery: an actually attempted real Organize that revalidates into an unresolved conflict may
  use the existing `PENDING ConflictConfirmation` / `WAITING_CONFIRM` / Conflicts recovery path.
  Uncertain mutation is never automatically replayed.

### Configuration → first DryRun Preview

Keep the existing Configuration lifecycle/forms and exact Active snapshot semantics unchanged. The
active revision action must continue to queue `POST /api/v1/jobs` with `command=preview`, and the
shared Job Preview implementation must provide the same conflict finding, zero-mutation and
no-backlog behavior as Jobs Preview. Do not add a Configuration-specific conflict filter or
parallel Preview implementation.

### Files/FileIndex Manual Preview

Keep `/api/v1/manual-previews` and the existing Files/FileIndex Manual Preview design unchanged.
Regression must prove it still has no Task, no review/conflict backlog, no execution authority and
no Storage mutation.

### Automation

Automation Task Definition Preview, validation, unattended grant/revoke, Scheduler/Cron/interval,
scheduled occurrence emission, definition-scoped Jobs, scheduled automatic organization and
Automation history are regression-only. Any required change to those product behaviors is a scope
alarm: stop and report to B rather than expanding this Task.

## Implementation Scope

Implement one vertical behavior across only the layers actually required by the audit:

```text
Jobs command model/admission
→ shared queued Worker workflow
→ MediaOrganizer conflict branch and durable Task/Result evidence
→ authenticated Service API
→ Operator Web Queue Job journey
→ focused/integration/regression tests
```

Expected ownership/surfaces:

- `mediaflow/interfaces/operator_ui.py`
  - Replace the Jobs-only DryRun form with one bounded Queue Job entry exposing Scan, Preview and
    Organize.
  - Render the authority/mutation state for each command.
  - Require a final, clearly labelled `Confirm Organize` action for real execution.
  - Keep execution tokens out of browser JavaScript and preserve existing API/RBAC behavior.
- `mediaflow/interfaces/service_api.py`
  - Preserve one shared `/api/v1/jobs` route and its existing read/submit permissions.
  - Map Scan/Preview to `SUBMIT_DRY_RUN` and Organize only to the existing protected real-execution
    branch; reject DryRun attempts to Organize and all malformed/unauthorized variants without
    mutation.
  - Preserve exact configuration snapshot pinning and bounded, secret-free errors.
- `mediaflow/application/automation.py`
  - Adjust only shared Job admission/dispatch behavior proven necessary for the command matrix;
    ordinary `AutomationJobService` admission must remain DryRun-only, while the existing
    `ExecutionAuthorizationService` remains the only real Organize admission authority.
  - Preserve Worker claim, heartbeat, fencing, cancellation and terminal persistence behavior.
- `mediaflow/final_cli.py` or the equivalent existing queued-workflow bridge, if required by the
  actual implementation:
  - Keep Job → Worker → existing pipeline handoff coherent for Scan, Preview and authorized
    Organize.
  - Ensure real Organize does not silently fall back to a DryRun or bypass current snapshot/source
    and capability checks.
- `mediaflow/application/media_organizer.py`,
  `mediaflow/application/task_runtime.py` and, only if necessary,
  `mediaflow/application/evidence_capture.py`:
  - Separate analysis-only conflict findings from real-execution conflict continuation.
  - Persist full bounded conflict/plan/capability evidence.
  - Use an existing completion-type durable state such as `DRY_RUN` or `SKIPPED` only when it
    accurately describes the Preview outcome; do not create a new TaskItem enum/state.
  - Keep real Organize unresolved conflicts on the existing
    `ConfirmationService`/`WAITING_CONFIRM` path.
- `mediaflow/application/conflict_resolution.py`:
  - Change only the call boundary needed to prevent Preview from creating mandatory continuation
    side effects; preserve real Organize confirmation creation, resolution, overwrite safeguards and
    audit behavior.
- `mediaflow/application/execution_authorization.py` and
  `mediaflow/domain/automation.py` / `mediaflow/domain/task_persistence.py`:
  - Treat as existing authority/state contracts. Modify only for minimal compatibility glue if
    actual code proves it necessary. Do not create a second authority system or a new TaskItem
    state.
- Relevant tests in `tests/`, including new vertical tests where no existing fixture can prove the
  journey. Tests must use temporary roots, fakes and local services.

Frozen unless B explicitly authorizes a scope correction:

- `SLICE.md`, `docs/roadmap.md`, `docs/requirements.md`, `docs/product-experience.md`,
  `docs/architecture.md` and the canonical Chinese requirements specification.
- Dockerfile, Compose, production WSGI, `/data` persistence, health checks, upgrade/migration and
  release packaging work.
- Automation Task Definition behavior, Automation Preview behavior, unattended authority,
  Scheduler/Cron/interval, occurrences, definition-scoped Job emission and Automation history.
- Files/FileIndex Manual Preview redesign and Configuration lifecycle/forms redesign.
- Global conflict/review queue redesign, new domain state, new execution-authority subsystem and
  new OrganizerExecutor.

If implementation requires rewriting the Task system, conflict persistence model, Worker
architecture or execution authorization architecture, stop and return a `PARTIAL / RESCOPE`
recommendation to A. Do not hide architecture redesign inside this Task.

## Acceptance Criteria

- [ ] Jobs exposes one `Queue Job` entry with exactly the bounded commands `Scan`, `Preview` and
      `Organize`; the API and Web use the same command/permission/validation behavior.
- [ ] Jobs Scan remains `SUBMIT_DRY_RUN`, performs zero Storage mutation, and visibly states
      `Authority: DRY_RUN` and `Storage mutation: NONE`.
- [ ] Jobs Preview remains `SUBMIT_DRY_RUN`, performs zero Storage mutation, and visibly states
      `Authority: DRY_RUN` and `Storage mutation: NONE`.
- [ ] A Job Preview organize-plan conflict is preserved as inspectable durable
      Preview/Task/Result evidence including source, destination, operation, conflict type,
      configured strategy, capability/evidence, status and next action.
- [ ] A Job Preview conflict creates no `PENDING ConflictConfirmation`, no `WAITING_CONFIRM`
      TaskItem and no real Conflicts backlog item; existing pending conflicts remain unchanged.
- [ ] Preview conflict handling uses an existing accurate completion-type durable state or existing
      result semantics. No new `TaskItemStatus` is added. If no existing state can express the
      finding accurately, implementation stops and reports an architecture blocker to B/A.
- [ ] Configuration's `Queue first DryRun Preview` remains pinned to the exact Active revision and
      inherits the shared Job Preview semantics without a Configuration-only conflict filter.
- [ ] A Configuration first Preview conflict is visible, has zero Storage mutation, creates no
      pending confirmation or `WAITING_CONFIRM`, and leaves Dashboard Pending conflicts at `N`.
- [ ] `SUBMIT_DRY_RUN` admission accepts only Scan/Preview and denies Organize; denial does not
      create an execute-authorized Job or perform unauthorized Storage mutation.
- [ ] Jobs Organize uses the existing `REMOTE_EXECUTE` / `ExecutionAuthorizationService` one-shot
      authority. No second authority or browser-carried execution token is introduced.
- [ ] Jobs Organize visibly states `Storage mutation: POSSIBLE`, requires explicit confirmation
      before queueing real work, and cannot be queued by `execute=true` alone without valid
      one-shot authority.
- [ ] Organize rejects missing, invalid, expired, consumed, revoked or mismatched authority
      fail-closed; normal bearer authentication is not treated as mutation authority; one-shot
      authority cannot be silently reused.
- [ ] A valid one-shot authority plus explicit `Confirm Organize` admits exactly one
      execute-authorized Job, and the Worker handoff preserves `execute_authorized` without
      silently downgrading to DryRun.
- [ ] A real Organize that revalidates into an unresolved current conflict still creates the
      existing `PENDING ConflictConfirmation`, `WAITING_CONFIRM` TaskItem and visible Conflicts
      backlog, with no Storage mutation before resolution.
- [ ] Organize revalidates current source/occurrence, pinned configuration snapshot, destination,
      required Storage capabilities, conflict state and live execution authority. Stale or
      mismatched Preview/source/occurrence/destination/capability/authority fails closed or
      requires reanalysis; a Preview is never execution authority.
- [ ] Overwrite, source deletion, cleanup, HardLink and SoftLink safety remains explicit; no
      unsupported operation silently falls back; uncertain mutation is never automatically replayed.
- [ ] `OrganizerExecutor` remains the sole component invoking mutating Storage operations. Tests or
      an equivalent trace prove Scan mutation calls = 0, Job Preview mutation calls = 0,
      Configuration first Preview mutation calls = 0, and real Organize mutations route only
      through OrganizerExecutor.
- [ ] Files/FileIndex Manual Preview retains no Task, no review/conflict backlog, no execution
      authority and no Storage mutation.
- [ ] Automation definitions, Automation Preview, validation, unattended grants, Scheduler,
      occurrences, definition-scoped Job emission and scheduled automatic organization remain
      behaviorally unchanged.
- [ ] The implementation exposes bounded success, failure and recovery state for each affected
      journey, preserves independent per-item outcomes, and does not expose secrets or private
      authorization material.
- [ ] The checkpoint contains only this Task's coherent changes and tests; no Docker work, private
      config, credentials, production media or unrelated cleanup is included.

## Required Tests

### Focused and vertical tests

The Developer must add or update tests for all of the following, using temporary files/directories,
fake Storage mutation recorders, local providers and SQLite repositories:

- Jobs UI/API command matrix: Scan, Preview, Organize; one Queue Job entry; RBAC; malformed
  commands; `SUBMIT_DRY_RUN` → Organize denial; `REMOTE_EXECUTE` and explicit confirmation.
- Scan and Job Preview Worker handoff with zero Storage mutation, including a trace that does not
  infer safety solely from `execute=False`.
- Job Preview conflict fixture: visible/persisted conflict evidence, no new confirmation, no
  `WAITING_CONFIRM`, no Dashboard pending-conflict increase, independent sibling outcome.
- Configuration Active revision → first DryRun Preview conflict fixture with:

  ```text
  pending conflicts before = N
  pending conflicts after  = N
  Storage mutation count   = 0
  WAITING_CONFIRM created  = NO
  ```

- Real Organize conflict fixture with valid one-shot authority and current unresolved conflict:
  pending confirmation, `WAITING_CONFIRM`, Dashboard `N → N + 1`, and zero mutation before
  resolution.
- One-shot authority matrix: normal bearer token is insufficient; missing/invalid/expired/consumed/
  revoked/mismatched authority fails closed; valid authority is single-use and snapshot-pinned.
- Preview-at-T1 then source/occurrence/destination/capability/snapshot/authority change before
  Organize-at-T2: stale execution is refused or forced through the existing reanalysis path.
- Mutation tracing for Scan, Job Preview, Configuration first Preview and real Organize, including
  OrganizerExecutor-only mutation enforcement and no hard/soft-link fallback.
- Files/FileIndex Manual Preview regression: no Task/backlog/authority/mutation.
- Automation regression: Automation Task Definition, Automation Preview, validation, grant/revoke,
  Scheduler/Cron/interval, occurrence emission, definition-scoped Jobs, scheduled organization,
  history and Worker claim/fencing.
- Existing conflict resolution, recovery, Task/TaskItem persistence, Dashboard, configuration
  snapshot, OrganizerExecutor and Worker tests.

### Required commands

Focused/related suites:

```bash
python3 -m unittest \
  tests.test_operator_job_submission \
  tests.test_operator_ui \
  tests.test_execution_authorization \
  tests.test_automation_api \
  tests.test_task_persistence \
  tests.test_conflict_resolution \
  tests.test_dashboard \
  tests.test_configuration_snapshot \
  tests.test_manual_preview \
  tests.test_organizer_mutation_authority \
  tests.test_processing_worker_readiness \
  tests.test_automation_job_fencing \
  tests.test_automation_definition_execution \
  tests.test_automation_task_definition_preview \
  tests.test_automation_preview_grant_gate \
  tests.test_automation_unattended_grant \
  tests.test_cron_scheduler \
  tests.test_recovery_continuation \
  tests.test_processing_recovery_admission
```

T4 full repository and safety gates:

```bash
python3 scripts/check_governance.py
ruff format --check .
ruff check .
python3 -m unittest discover -s tests
python3 -m compileall -q mediaflow tests scripts
python3 -m pip check
python3 -m pip wheel . --no-deps -w dist
python3 scripts/wheel_smoke_test.py dist/mediaflow-*.whl
test -z "$(rg -n -i 'ffprobe|ffmpeg' mediaflow pyproject.toml || true)"
git diff --check
```

Run Markdown/link checks and any repository-provided canonical configuration validation where
available. If Docker, external Storage, TMDB, reverse-proxy or another external gate is unavailable,
report `SKIP` / `UNAVAILABLE` with the exact boundary; never report an unsupported PASS. The
pre-existing unrelated `FinalIntegrationTests.test_runtime_configuration_and_final_analyze_cli`
failure observed during planning must be re-run, explained and kept separate from RO-8 evidence
unless this Task demonstrably changes its cause.

## Safety / Regression Fences

- `normal bearer token != mutation authority`.
- `SUBMIT_DRY_RUN → Scan/Preview only`; it can never authorize Organize.
- `REMOTE_EXECUTE` remains disabled by default where configured, separate from ordinary API auth,
  one-shot, bounded, expiring, consumable, revocable and fail-closed.
- Configuration snapshot ID/digest stays pinned from Job admission through Worker execution.
- Real Organize revalidates current source/occurrence, destination, capabilities, conflict and live
  authority; stale data cannot be blindly executed.
- Preview is evidence, not authority. Preview conflicts remain inspectable and do not become
  mandatory operator work.
- Real unresolved conflicts retain the existing confirmation/recovery path.
- Overwrite and source deletion remain explicit; HardLink/SoftLink never silently fall back.
- Uncertain mutation is not automatically replayed.
- OrganizerExecutor remains the only Storage mutator.
- Batch items keep independent durable status, evidence and recovery.
- Secret-free logs, evidence, API projections and UI; never persist or expose execution tokens,
  token digests, authorization headers, cookies or provider secrets.
- Files/FileIndex Manual Preview and Automation behavior remain unchanged.

## Explicit Non-goals

- Dockerfile, Docker Compose implementation, production WSGI, `/data` persistence, Docker health
  checks, Docker upgrade/migration work, image packaging or release acceptance.
- Automation UI redesign, Automation Task Definition changes, Automation Preview redesign,
  unattended grant redesign, Scheduler/Cron/interval changes, scheduled occurrence changes,
  definition-scoped Job behavior changes or Automation history changes.
- Files/FileIndex redesign or Manual Preview redesign.
- Configuration lifecycle/forms redesign; only the existing Configuration first Preview entry is
  covered as a shared Job Preview consumer.
- Global conflict/review queue redesign.
- New TaskItem state unless escalated to A; no new execution-authority subsystem; no new
  OrganizerExecutor.
- Frontend framework migration, broad UI cleanup, help-text/copy polish or unrelated P2 cleanup.
- Provider switching, new Storage providers, built-in identity/OIDC, Secret Store integration,
  distributed workers, uncertain-mutation replay or historical rollback.

## Developer Completion Report

### Changed Files

### Implemented

### Tests and Results

### Decisions

### Remaining In-Slice Work

### Risks / Deviations

### Checkpoint

```text
Status: READY FOR B REVIEW
Head SHA: [full SHA]
```

## B Review Result

```text
Reviewed: [Head SHA or Task Base..Head]
Decision: PENDING
Slice Required Outcomes all satisfied: PENDING
Next: PENDING
```

If `FIX REQUIRED`, list only blockers for this Task. Fixes remain in this Task unless B explicitly
finds a genuinely independent business goal. This result does not close the Slice or update Roadmap.
